# Phase 16 — Context Intelligence

Three features that transform CoDRAG from "semantic search tool" to "context intelligence layer."

## Feature 1: Native Embeddings (no Ollama required)

### Problem
Today, `OllamaEmbedder` is the **only** real embedding implementation. Without Ollama installed and running, there's no semantic search — only structural Trace Index + keyword/FTS5. This makes the marketing story awkward ("embeddings are optional") when semantic search is a core product function.

### Solution: Built-in ONNX embedder
Ship a `NativeEmbedder` that runs `nomic-embed-text` via ONNX Runtime. No Ollama, no torch, no cloud API.

**Why ONNX and not sentence-transformers?**
- `sentence-transformers` pulls in `torch` (~2 GB). Way too heavy for a desktop app.
- `onnxruntime` is ~50 MB. `tokenizers` (Rust-backed) is ~5 MB.
- `nomic-embed-text` ONNX model is ~274 MB, downloaded once on first use.
- ONNX runs well on CPU. GPU acceleration via `onnxruntime-gpu` is optional.

**Why not Rust/candle (yet)?**
- Candle in the engine crates is the ideal long-term target (single binary, no Python deps).
- But it's significantly more work. ONNX in Python is pragmatic for v1.
- The `Embedder` ABC means we can swap implementations later without touching search/index code.

### Implementation plan

1. **New class**: `NativeEmbedder(Embedder)` in `src/codrag/core/embedder.py`
   - Uses `onnxruntime.InferenceSession` + `tokenizers.Tokenizer`
   - Auto-downloads model from HuggingFace Hub on first use to `~/.prep/models/nomic-embed-text/`
   - Implements `embed()` and `embed_batch()` (batch is actually efficient with ONNX)
   - Mean-pooling + L2 normalization (matching nomic-embed-text's expected usage)

2. **New dependencies** in `pyproject.toml`:
   ```
   "onnxruntime>=1.17.0",
   "tokenizers>=0.15.0",
   "huggingface-hub>=0.20.0",
   ```

3. **Embedder selection logic** in `server.py`:
   - Default: `NativeEmbedder` (no config needed)
   - If user configures `ollama_url`: use `OllamaEmbedder` (backwards compatible)
   - Config key: `embedding_source: "native" | "ollama"` (default: `"native"`)

4. **CLI**: `codrag models download` — pre-downloads the ONNX model (for air-gapped setups)

5. **Tests**: Verify `NativeEmbedder` produces same-dimension vectors as `OllamaEmbedder` with nomic-embed-text

### Marketing impact
- Embeddings become a **built-in core feature**, not an optional add-on
- "Install CoDRAG → semantic search works immediately. No Ollama, no API keys, no setup."
- Ollama becomes a **power-user option** (use a different model, GPU acceleration, etc.)

---

## Feature 2: User-Defined Path Weights (Folder/File Context Weighting)

### Problem
A project like CoDRAG has 70k+ lines of planning docs alongside source code. When searching, you don't always want docs and code weighted equally. Sometimes `docs/Phase00_Initial-Concept/` is background context (0.5 weight) while `src/codrag/core/` is the focus (1.5 weight).

### Is this possible? YES — the infrastructure is 80% built.

**What already exists in `index.py`:**
- `role_weights` — per-role multipliers applied at search time (code=1.0, docs=0.95, tests=0.98)
- `_intent_role_multipliers()` — query-intent-based role boosting
- `_primer_boosts()` — score boosts for primer docs (AGENTS.md, etc.)
- `_keyword_boosts()` — path-based keyword matching
- `classify_rel_path()` — classifies files by directory into roles

**What already exists in `repo_policy.py`:**
- `role_weights: Dict[str, float]` — stored in repo_policy.json per project
- `path_roles: List[Dict]` — maps top-level dirs to roles

**What's MISSING: per-path weight overrides.**

### Solution: `path_weights` in repo policy

Add `path_weights: Dict[str, float]` to the repo policy. Keys are path prefixes (glob-like), values are multipliers.

```json
{
  "path_weights": {
    "docs/Phase00_Initial-Concept/**": 0.5,
    "docs/Phase16_ContextIntelligence/**": 1.2,
    "src/codrag/core/**": 1.5,
    "tests/**": 0.8
  }
}
```

### Implementation plan

1. **Backend** (`index.py` search method):
   - After computing cosine similarity + keyword/FTS boosts, apply path weight multipliers
   - For each doc, find the most specific matching path prefix → apply weight
   - This is identical to how `role_weights` work, but matching on `source_path` instead of `role`

2. **Policy** (`repo_policy.py`):
   - Add `path_weights` field to policy schema
   - Add `_normalize_path_weights()` validator
   - Store in `repo_policy.json` alongside `role_weights`

3. **API** (`server.py`):
   - Extend `PUT /projects/{id}` to accept `path_weights` updates
   - Extend `GET /projects/{id}/status` to return current `path_weights`

4. **UI** (FolderTree component):
   - Add weight slider (0.0–2.0) next to each folder in the file tree
   - Default: 1.0 (no change)
   - Visual indicator: dimmed folders (< 1.0), highlighted folders (> 1.0)
   - "Reset all weights" button

5. **MCP**: Path weights can be set via `codrag_update_project` tool

### Why this matters
- User selects `docs/` → sets weight to 0.5 → docs are in context but don't dominate
- User selects `src/codrag/core/` → sets weight to 1.5 → core code surfaces first
- Works at search time — no rebuild needed, weights apply instantly
- Composable with existing role_weights and intent multipliers

---

## Priority Order

| # | Feature | Effort | Impact | Ship order |
|---|---------|--------|--------|------------|
| 1 | Native Embeddings (ONNX) | Medium | **Critical** — makes semantic search zero-config | First |
| 2 | Path Weights | Low–Medium | **High** — immediate user control over context relevance | Second |

### Dependency chain
- Native Embeddings: standalone, no prerequisites
- Path Weights: standalone, no prerequisites

---

## Marketing copy changes needed

Once native embeddings ship:
- **TechStackMatrix**: Replace "CoDRAG Core vs CoDRAG + Ollama" with "CoDRAG (everything built in)" vs "Optional: Ollama (use a different model)"
- **Hero/feature copy**: "Semantic search works out of the box" instead of "add Ollama for semantic search"
- **BYOK framing**: shifts to LLM (user's own Claude/GPT key for generation), not embeddings
- **Path weights**: new marketing angle — "Control what matters. Weight folders so AI focuses where you do."

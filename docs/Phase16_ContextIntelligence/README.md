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

## Feature 3: CLaRa Context Compression (Query-time)

### Problem
With 70k+ lines of docs (and growing), retrieved context can easily blow past LLM token budgets. Top-k retrieval helps, but you lose nuance. CLaRa compresses context while preserving the important parts — so you fit more signal into the same budget.

### Is CLaRa worth it? When?

**CLaRa makes sense when:**
- Codebase > 50k lines AND heavy documentation (design docs, ADRs, planning)
- Working with small-context models (8k, 16k windows)
- Multi-repo setups where context spans multiple projects
- The user has adequate hardware (CLaRa-7B needs ~7 GB RAM quantized, ~14 GB full)

**CLaRa doesn't add much when:**
- Small codebases (< 20k lines) where top-5 chunks fit easily
- Using 128k+ context window models
- Hardware-constrained (laptop with 8 GB RAM total)

**For this project specifically**: 70k lines of markdown docs + source code + tests = CLaRa is a clear win. AI-assisted engineering produces enormous doc volumes (exactly the user's workflow). CLaRa compresses the retrieved planning/design context so the LLM gets the key decisions without drowning in prose.

### Current state
- Design doc: `docs/Phase00_Initial-Concept/STAGE2_CLARA_QUERYTIME.md` (complete)
- Config placeholder: `server.py` line 151 (`"clara": {"enabled": False}`)
- Optional dependency: `pyproject.toml` `[project.optional-dependencies] clara = ["torch>=2.1.0"]`
- **Existing standalone server**: [`EricBintner/CLaRa-Remembers-It-All`](https://github.com/EricBintner/CLaRa-Remembers-It-All) — same author, Apache-2.0

### Integration strategy: Git subtree + sidecar HTTP

CLaRa-Remembers-It-All is **already** the sidecar architecture that Stage 2 proposed:
- FastAPI server on `:8765`
- `POST /compress` — accepts `memories[]` + `query`, returns compressed answer + stats
- `GET /status` — model info, auto-unload timing
- `GET /health` — health check
- Supports CUDA, MPS, CPU backends
- Ollama-style auto-unload (configurable `--keep-alive`)

**Why subtree (not submodule or pip dep)?**
- Matches the established pattern: `public/codrag-mcp/` is already a git subtree with `scripts/publish_codrag_mcp_subtree.sh`
- Code lives in the monorepo → edit CLaRa in CoDRAG, push changes back upstream via `git subtree split`
- Single place to manage CLaRa code across both repos
- No PyPI publishing needed, no submodule pain

**Subtree location**: `vendor/clara-server/` ← `github.com/EricBintner/CLaRa-Remembers-It-All`

### Implementation plan

**Stage 1: Subtree + adapter interface**
1. `git subtree add --prefix vendor/clara-server https://github.com/EricBintner/CLaRa-Remembers-It-All.git main --squash`
2. Add `scripts/publish_clara_subtree.sh` (mirror of codrag-mcp script)
3. Define compression adapter ABC in `src/codrag/core/compressor.py`:

```python
class ContextCompressor(ABC):
    @abstractmethod
    def compress(self, text: str, *, budget_chars: int, level: str = "standard") -> CompressResult: ...

@dataclass
class CompressResult:
    compressed: str
    input_chars: int
    output_chars: int
    timing_ms: float
    error: Optional[str] = None
```

4. Implement `ClaraCompressor(ContextCompressor)` — thin HTTP client calling `http://localhost:8765/compress`

**Stage 2A: Final-string compression** (simplest, ship first)
- After `get_context()` assembles the context string, pass through CLaRa sidecar
- New API params: `compression="clara"`, `compression_level="light|standard|aggressive"`
- Fallback: if CLaRa server unavailable or times out, return uncompressed context + error metadata

**Stage 2B: Per-chunk compression** (better citations, follow-up)
- Compress each chunk individually, preserve boundaries
- Citations remain accurate

**CLaRa server lifecycle management:**
- **Local mode**: CoDRAG can auto-start `clara-server` as a subprocess from `vendor/clara-server/`
- **Remote mode**: User points to existing CLaRa server on network (e.g., GPU workstation)
- Config: `clara.url` (default `http://localhost:8765`), `clara.auto_start` (default `false`)
- Health check: CoDRAG polls `/health` before attempting compression

**Deployment options (all from CLaRa-Remembers-It-All):**
- Local: `pip install -e vendor/clara-server/ && clara-server`
- Docker: `docker run -p 8765:8765 --gpus all ghcr.io/ericbintner/clara-remembers-it-all`
- Network GPU: run CLaRa on beefy machine, point CoDRAG at its URL

---

## Priority Order

| # | Feature | Effort | Impact | Ship order |
|---|---------|--------|--------|------------|
| 1 | Native Embeddings (ONNX) | Medium | **Critical** — makes semantic search zero-config | First |
| 2 | Path Weights | Low–Medium | **High** — immediate user control over context relevance | Second |
| 3 | CLaRa Compression | Medium–High | **Medium-High** — power-user feature for large codebases | Third |

### Dependency chain
- Native Embeddings: standalone, no prerequisites
- Path Weights: standalone, no prerequisites
- CLaRa: standalone, but benefits most when combined with path weights (compress after weighting)

---

## Marketing copy changes needed

Once native embeddings ship:
- **TechStackMatrix**: Replace "CoDRAG Core vs CoDRAG + Ollama" with "CoDRAG (everything built in)" vs "Optional: Ollama (use a different model)" vs "Optional: CLaRa (context compression for large codebases)"
- **Hero/feature copy**: "Semantic search works out of the box" instead of "add Ollama for semantic search"
- **BYOK framing**: shifts to LLM (user's own Claude/GPT key for generation), not embeddings
- **Path weights**: new marketing angle — "Control what matters. Weight folders so AI focuses where you do."

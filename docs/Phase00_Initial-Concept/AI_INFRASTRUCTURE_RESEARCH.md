# Phase 69 — AI Infrastructure Research

## Current AI Stack Overview

The system involves **two distinct AI workloads** that can run concurrently:

| Workload | Model | Runtime | Purpose |
|----------|-------|---------|---------|
| **Embeddings** | `nomic-embed-text` | Ollama | Semantic vector encoding for RAG retrieval |
| **Augmentation** | Mistral/Llama/etc | Ollama or llama.cpp | Summaries, tags, trace synthesis |

Related research:
- `IMPLEMENTATION.md` — Current CoDRAG + code_index implementation status
- `TRACE_INDEX_RESEARCH.md` — Trace index / codebase graph concept and roadmap
- `COMPETITORS_AND_CUTTING_EDGE.md` — Competitor landscape + cutting-edge feature targets

---

## 1. Embeddings: Ollama + nomic-embed-text

### Why Ollama?
- **Yes, Ollama is required** for the current embedding approach
- `nomic-embed-text` is a 137M param model optimized for retrieval
- Ollama provides a simple HTTP API (`POST /api/embeddings`) with model management

### Could we build our own?
Alternatives if we want to avoid Ollama dependency:

| Option | Pros | Cons |
|--------|------|------|
| **Ollama (current)** | Easy setup, model management | External dependency |
| **Direct HF Transformers** | No Ollama needed | More code, slower cold start |
| **sentence-transformers** | Python-native, many models | Dependency, no auto-download |
| **llama.cpp embeddings** | Unified with LLM runtime | Fewer embedding models |
| **OpenAI-compatible servers** | Standard API | Still need a server |

**Recommendation:** Stick with Ollama for now—it's the simplest path and already works.

---

## 2. LLM Augmentation: Mistral / Llama

### Can llama.cpp run Mistral?

**Yes.** llama.cpp supports Mistral models in GGUF format:

```bash
# Download a quantized Mistral
huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Run with llama.cpp
./llama-server -m mistral-7b-instruct-v0.2.Q4_K_M.gguf -c 8192 --port 8081
```

Or via Ollama:
```bash
ollama pull mistral
ollama run mistral "Summarize this code..."
```

### Where LLM augmentation fits in the trace index

| Stage | Use Case | Timing |
|-------|----------|--------|
| **Build-time** | Per-file/symbol summaries | Expensive, cached |
| **Build-time** | Auto-tagging for retrieval | Expensive, cached |
| **Query-time** | "What does this module do?" | On-demand |
| **Query-time** | Trace synthesis ("how does auth flow work?") | On-demand |

### Recommended stack for augmentation

| Scenario | Recommended Runtime |
|----------|---------------------|
| **Local-first, Apple Silicon** | Ollama (easiest) or MLX |
| **Local-first, NVIDIA** | Ollama or llama.cpp server |
| **Maximum compatibility** | Ollama (works everywhere) |
| **BYOK cloud** | OpenAI-compatible endpoint |

---

## 3. agents.md: Standard for AI Coding Agents

### What is agents.md?

From https://agents.md/:
> AGENTS.md is a simple, open format for guiding coding agents. Think of it as a README for agents.

It's a **standardized file** that AI coding tools read to understand:
- Build/test commands
- Code style guidelines
- Project structure hints
- Security considerations

### Compatibility
agents.md works with: Windsurf, Cursor, Codex, GitHub Copilot, Aider, Devin, VS Code, Zed, and many others.

### How agents.md relates to the trace index

The trace index could **auto-generate** an AGENTS.md file:

```
 Trace Index                      AGENTS.md
 ┌─────────────────────┐         ┌─────────────────────────────────────┐
 │ - File inventory    │         │ # AGENTS.md                         │
 │ - Symbol index      │ ──────► │ ## Project structure                │
 │ - Endpoint map      │         │ - src/: Backend / core engine       │
 │ - Import graph      │         │ - code_index/: RAG library          │
 │ - Test coverage     │         │ ## Build commands                   │
 └─────────────────────┘         │ - pip install -e .                  │
                                │ - python -m code_index              │
                                │ ## Key modules                      │
                                │ - embedder.py: Ollama embeddings    │
                                │ - index.py: Hybrid search           │
                                └─────────────────────────────────────┘
```

### Potential integration points

1. **Auto-generate AGENTS.md from trace**
   - Extract endpoints, build commands, key modules
   - Include code style inferred from linters/.editorconfig

2. **Use AGENTS.md as trace input**
   - If repo already has AGENTS.md, parse it as a "curated" trace source
   - Treat it like your existing `_MASTER_CROSSREFERENCE` but lighter

3. **agents.md as an output format**
   - Generate multiple agents.md files per subsystem (mono-repo support)
   - Keep them updated as trace index changes

---

## 5. Automating `_MASTER_CROSSREFERENCE` with Trace Index

Your existing framework (`FRAMEWORK_V2.md`, `SCHEMA.md`) is a **curated trace index**:
- XREF-IDs
- Semantic link types (implements, depends_on, documents, etc.)
- Multi-pass AI processing (direct discovery → semantic inference → validation → transitive)

### How the trace index can automate this

| Current (Manual) | Automated (Trace Index) |
|------------------|-------------------------|
| Human creates XREF entries | Static analysis extracts nodes |
| Human defines `implements` links | Import graph + naming heuristics |
| Human sets `confidence: high/medium/low` | Automated = medium, explicit ref = high |
| AI Pass 1-4 runs periodically | Incremental rebuild on file change |
| `.validation/` reports orphans | Trace manifest tracks orphans automatically |

### Proposed architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Trace Index Layer                            │
├─────────────────────────────────────────────────────────────────────┤
│  Static Analyzers                                                   │
│  ├── Python: AST → symbols, imports, decorators                     │
│  ├── Markdown: headings → doc_section nodes                         │
│  ├── Config: package.json/pyproject.toml → metadata                 │
│  └── Endpoints: Flask/FastAPI route decorators → endpoint nodes     │
├─────────────────────────────────────────────────────────────────────┤
│  Graph Store                                                        │
│  ├── trace_nodes.jsonl (or SQLite)                                  │
│  ├── trace_edges.jsonl                                              │
│  └── trace_manifest.json                                            │
├─────────────────────────────────────────────────────────────────────┤
│  Optional LLM Augmentation                                          │
│  ├── Per-node summaries (Mistral via Ollama)                        │
│  ├── Auto-tagging                                                   │
│  └── Link confidence refinement                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Output Adapters                                                    │
│  ├── → Embedding chunks (for code_index)                            │
│  ├── → XREF entries (for _MASTER_CROSSREFERENCE)                    │
│  ├── → AGENTS.md (for AI coding tools)                              │
│  └── → Coverage reports / orphan detection                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Mapping XREF schema to trace nodes

| XREF Field | Trace Node Field |
|------------|------------------|
| `id: XREF-CODE-abc123` | `id: hash(kind, path, span)` |
| `type: Code` | `kind: symbol` |
| `path` | `file_path` |
| `links.implements` | edge `(plan_node, code_node, "implements")` |
| `links.depends_on` | edge `(code_node, dep_node, "imports")` |
| `status.state` | `metadata.status` |
| `tags` | `metadata.tags` |
| `summary` | `metadata.summary` (LLM-generated) |
| `origin.rationale` | `metadata.rationale` (from ADR or LLM) |

### Automation strategy

1. **Bootstrap from existing XREF**
   - Parse `_MASTER_CROSSREFERENCE/` entries
   - Import as trace nodes with `source: "xref"` and `confidence: high`

2. **Enrich via static analysis**
   - Run Python/Markdown analyzers on codebase
   - Create new nodes for discovered symbols/sections
   - Add `imports` edges from AST

3. **Reconcile**
   - Match XREF entries to discovered nodes
   - Flag orphans (XREF with no matching code)
   - Flag undocumented (code with no XREF)

4. **LLM augmentation (optional)**
   - Generate summaries for nodes missing them
   - Suggest tags based on content
   - Refine confidence levels

5. **Export**
   - Write updated XREF entries back to `_MASTER_CROSSREFERENCE/`
   - Generate AGENTS.md for external tools
   - Update embeddings for changed nodes

---

## 6. Complete AI Service Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User / IDE (Windsurf/Cursor)                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ MCP tools
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CoDRAG Server (FastAPI @ :8400)                    │
├─────────────────────────────────────────────────────────────────────────┤
│  /status, /build, /search, /context                                     │
│  /trace/status, /trace/build, /trace/search (future)                    │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │    Ollama @ :11434      │
    │ ┌─────────────────────┐ │
    │ │ nomic-embed-text    │ │
    │ │ (embeddings)        │ │
    │ ├─────────────────────┤ │
    │ │ mistral             │ │
    │ │ (augmentation)      │ │
    │ └─────────────────────┘ │
    │  llama.cpp underneath   │
    └─────────────────────────┘
```

### Port summary

| Service | Default Port | Purpose |
|---------|--------------|---------|
| Ollama | 11434 | Embeddings + LLM augmentation |
| CoDRAG daemon | 8400 | RAG API |
| Dashboard | (varies) | UI |

---

## 7. Open Questions / Decisions Needed

1. **Single Ollama vs separate embedding + LLM servers?**
   - Ollama can serve both embeddings and chat models
   - May want separate instances for isolation

2. **Where does trace index live?**
   - Same directory as embeddings (`index_dir/trace_*`)?
   - Separate directory?

4. **AGENTS.md generation**
   - Auto-generate on each trace build?
   - User-triggered?
   - Both (auto-generate draft, user curates)?

5. **_MASTER_CROSSREFERENCE migration**
   - Keep as source of truth, trace index enriches?
   - Trace index becomes source of truth, XREF is generated output?
   - Hybrid: both are valid inputs, reconciled?

---

## 8. Recommended Next Steps

### Phase T0.5: Document + Decide
- [ ] Decide on question 3 (trace location)
- [ ] Decide on question 5 (XREF relationship)

### Phase T1: Trace Index MVP
- [ ] Python symbol extractor (AST-based)
- [ ] Markdown heading extractor
- [ ] Import graph builder
- [ ] `trace_nodes.jsonl` / `trace_edges.jsonl` output

### Phase T2: Integration
- [ ] Trace-driven chunking (symbols → chunks)
- [ ] agents.md generator
- [ ] XREF reconciler (trace ↔ _MASTER_CROSSREFERENCE)

### Phase T3: LLM Augmentation
- [ ] Summary generator (Mistral via Ollama)
- [ ] Auto-tagging
- [ ] Confidence refinement

### Phase T4: UI
- [ ] Trace tab in dashboard
- [ ] Node browser + graph visualization

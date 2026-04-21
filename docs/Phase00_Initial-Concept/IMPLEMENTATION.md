# Phase 69 — CoDRAG / Code Index

## Goal
Build a reusable, local-first “code index” subsystem that lets the app (and other apps) **index a codebase/docs** and perform **hybrid retrieval**:

- Semantic search (embeddings via Ollama `nomic-embed-text`)
- Keyword search (SQLite FTS5 when available)
- Context fetching (return full chunks + source metadata)

This will power:

- **CoDRAG** (a standalone multi-project daemon)
- A **dashboard** (React/Vite → native wrapper later) for search/context/trace
- Optional embedded/team mode (index stored alongside a repo)

## Key product decisions
- **Standalone dashboard**: React/Vite
- **Reuse workflow**: Multi-project daemon + optional embedded indexes
- **Naming**:
  - “**CoDRAG**” = the standalone app
  - “**Code Index**” = the underlying per-project indexing + retrieval capability

## MCP integration (Cascade/Windsurf)
This repo includes an MCP stdio server wrapper so **Cascade (Windsurf IDE assistant)** can call local retrieval as a tool.

Documentation:
- `docs/Phase00_Initial-Concept/MCP.md`

Related research:
- `docs/Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md`

## Current backend state
CoDRAG provides a working Python implementation with a stable HTTP API.

Current API endpoints (standalone, multi-project):
- `GET /projects/{id}/status`
- `POST /projects/{id}/build` (async)
- `POST /projects/{id}/search`
- `POST /projects/{id}/context`

Optional trace endpoints:
- `GET /projects/{id}/trace/status`
- `POST /projects/{id}/trace/search`
- `POST /projects/{id}/trace/node`
- `POST /projects/{id}/trace/neighbors`

LLM service endpoints:
- `GET /llm/status`

Notes:
- Keyword index is optional to avoid failures if FTS5/bm25 isn’t supported.

## Target architecture (reusable + language-agnostic)
We keep the **core index format + HTTP contract** language-agnostic, while the first implementation stays in Python.

### A) `code_index` core (public/submodule-ready)
A minimal, CoDRAG-free module that provides:

- **Index building**
  - File walking + include/exclude
  - Chunking
  - Embedding
  - Persistence
- **Retrieval**
  - Vector similarity (cosine)
  - Optional keyword boosts via SQLite FTS
  - `get_chunk` by chunk id

Keep the on-disk artifacts simple and documented so other languages can consume them:

- `documents.json` (chunk text + metadata)
- `embeddings.npy` (float32 embeddings)
- `fts.sqlite3` (optional)
- `manifest.json` (config + model + timestamps + version)

### B) Optional embedded-mode adapter
A thin layer that:

- Stores index data in a repo-local directory (e.g. `.prep/`)
- Exposes the same HTTP contract

### C) Standalone server
A small server that exposes the same HTTP API contract, pointing at:

- `repo_root` (what to index)
- `index_dir` (where to store)

Implementation detail:
- First iteration can remain Python (Flask or FastAPI).
- “Language-agnostic” is achieved through:
  - clean HTTP API
  - clean on-disk file formats
  - avoiding CoDRAG-specific semantics in the core

### D) React/Vite dashboard
A minimal UI that can run against:

- CoDRAG daemon (`/projects/{id}/*`)

## API contract (dashboard + server)
Keep the JSON schema stable so UI can talk to either backend.

CoDRAG keeps the “core” contract stable per project:

- `/projects/{id}/{status|build|search|context}`

### `GET /status`
Returns:

- `index`: stats object (always present)
- `building`: boolean
- `last_build`: nullable object
- `last_error`: nullable string
- `context_defaults`: `{k, max_chars}`
- `config` (repo_root/index_dir/ollama_url/model)

### `POST /build` (async)
Request body:

- `repo_root` (string, required unless stored in project config)
- `include_globs` / `exclude_globs` (string[], optional)
- `max_file_bytes` (int, optional)

Response:

- `started`: boolean
- `building`: boolean (may be returned when a build is already running)

### `POST /search`
Body:

- `query` (string, required)
- `k` (int, default: 8)
- `min_score` (float, default: 0.15)

Response:

- `results`: list of `{doc, score}`

### `POST /context`
Body:

- `query` (string, required)
- `k` (int, default: 5)
- `max_chars` (int, default: 6000)
- `include_sources` (bool, default: true)
- `include_scores` (bool, default: false)
- `min_score` (float, default: 0.15)
- `structured` (bool, default: false)

Response:

- `structured=false`: `{ "context": "..." }`
- `structured=true`: `{ "context": "...", "chunks": [...], "total_chars": N, "estimated_tokens": N }`

Endpoint differences:

- Optional:
  - `POST /projects/{id}/chunk` (get a chunk by id)

## Indexing scope (Phase 69)
Phase 69 starts with:

- `_MASTER_CROSSREFERENCE/**/*.md`
- Selected `docs/**/*.md`
- Selected `src/**/*` (core engine + API)

## Chunking strategy (Phase 69)
- Markdown: heading-based chunking (current)
- Code: size-based fallback (Phase 69)
- Code: Tree-sitter semantic chunking (future improvement)

## Incremental indexing strategy (Phase 69+)
- Phase 69: full rebuild (already works)
- Next:
  - store per-file hash + mtime in `manifest.json`
  - only re-embed changed chunks
  - keep stable `chunk_id`s derived from `path + span + hash`

## Competitive landscape implications
The competitor landscape suggests vector top-k alone is becoming table-stakes. To keep `code_index` cutting-edge while staying local-first and operationally simple, the technical roadmap should bias toward:

- **Trace/graph layer (no graph DB required)**
  - introduce a lightweight trace/edge representation (imports, symbol boundaries, adjacency)
  - enable bounded graph expansion during `/context` assembly (GraphRAG-style traversal)
- **Hybrid ranking beyond “vector + FTS”**
  - keep FTS as a baseline, but add explicit structural signals (path heuristics, symbol/type metadata, trace proximity)
- **Surgical edit workflows (structure-aware)**
  - make symbol-level targeting (functions/classes) a first-class concept so edits are “replace symbol X” instead of “replace lines N–M”
- **Evaluation harness (measurable retrieval quality)**
  - maintain a small suite of gold queries per repo area with expected citations (paths / xref IDs)
  - track recall@k and duplication/coherence metrics so improvements are measurable
- **Multi-index support (optional, progressive)**
  - summaries/symbol index as a lightweight layer above chunks to improve breadth-first retrieval
  - keep the on-disk format transparent and language-agnostic

## TODOs (implementation checklist)

### 0) Documentation + project hygiene
- [x] Write/maintain this doc as the authoritative plan
- [x] Define public-friendly naming (avoid project-specific terms in reusable code)

### 1) Smoke test existing CoDRAG backend (end-to-end)
- [x] Confirm Ollama is running + `nomic-embed-text` is installed
- [x] Call `/projects/{id}/build` against a test project
- [x] Validate `/projects/{id}/search` returns sensible results
- [x] Confirm keyword boosts behave when FTS5 is available

### 2) Dev UI panel (uses existing endpoints)
- [x] Add Dev UI: build button, status polling, search box
- [x] Results list with score + file path + preview
- [x] Context viewer panel

### 3) Refactor into reusable `code_index` core (submodule-ready)
- [x] Create CoDRAG-free `code_index/` core (submodule-ready)
- [ ] Switch CoDRAG `/projects/{id}/*` to use `code_index/` as a thin adapter (remove duplicate implementation)
- [x] Document on-disk format + config schema

### 4) Standalone server (points at any repo)
- [x] Create minimal Python server exposing the same API contract
- [x] Add CLI flags: `--repo-root`, `--index-dir`, `--ollama-url`, `--model`
- [x] Ensure CORS works for the Vite dashboard

### 5) React/Vite dashboard (reusable)
- [x] Scaffold Vite app
- [x] Configure base URL (CoDRAG vs standalone)
- [x] Build + status + search + context UX
- [x] Nice error states (Ollama not running, build failed, etc.)

### 6) Public/submodule packaging
- [x] Create a clean repo layout so this folder can become a git submodule
- [x] Add minimal README for external reuse
- [x] Avoid any private prompts/data paths in the reusable portion

## Unification plan (prototype -> reusable core)
The goal of this phase of work is to keep indexing/retrieval logic centralized in a reusable core, with thin adapters at the edges (daemon, MCP, UI).

### Desired end state
- CoDRAG owns the stable public HTTP contract.
- A thin adapter layer configures the reusable core per project (embed model, include/exclude patterns).
- Indexing/retrieval logic is not duplicated across implementations.

### API mapping (CodeIndex vs SelfRagIndex)

| Feature | `CodeIndex` | `SelfRagIndex` | Adapter strategy |
|---------|-------------|----------------|------------------|
| **Constructor** | `(index_dir, embedder)` | `(embeddings_dir, embed_model)` auto-creates embedder | Derive path from `StorageConfig`, create `OllamaEmbedder` |
| **Build params** | `repo_root, include_globs, exclude_globs, max_file_bytes` | adds `roots` (sub-directories to walk) | Custom build that walks each root, calls CodeIndex chunking, adds XREF metadata |
| **Doc schema** | `id, source_path, file_hash, section, content` | adds `xref_id, xref_type, name, tags` | Enrich docs during build (XREF YAML parsing) |
| **Context headers** | `section, @source_path` | `name, xref_id, section, @source_path` | Override `get_context*` to include richer headers |
| **FTS columns** | 4 columns | 7 columns (incl. xref_id, name, tags) | Extend FTS schema in adapter |
| **Manifest** | `manifest.json` with `config` | `index.json` with `roots` | Use same file, add `roots` field |

### Work plan
- [x] Keep the reusable core isolated from app-specific concerns.
- [x] Keep MCP tooling as a thin proxy over the HTTP API.
- [x] Keep the HTTP contract stable across releases.

## Progress log

### 2026-01-30 (unification work)
- Documented API mapping between `CodeIndex` and a project-scoped adapter (see table above)
- Designed adapter strategy: wrap `CodeIndex`, add XREF enrichment during build, richer headers in context
- Verified the reusable `code_index` module works independently
- Kept the HTTP contract stable while adapters evolve

### 2026-01-29 (session 1)
- Implemented a Dev UI panel for build/status/search/context.
- Fixed a markdown chunking bug where a large section could be incorrectly emitted unsplit (leading to oversized embedding prompts).
- Hardened Ollama embedding calls with retry/backoff to reduce intermittent `/api/embeddings` failures.
- Smoke test result (local):
  - `/projects/{id}/build` succeeded for a test project.
  - `/projects/{id}/search` and `/projects/{id}/context` returned results.

### 2026-01-29 (session 2)
- Created reusable `code_index/` module at repo root:
  - `code_index/__init__.py` - Public API exports
  - `code_index/embedder.py` - `Embedder` ABC + `OllamaEmbedder` with retry/backoff
  - `code_index/chunking.py` - `chunk_markdown()` and `chunk_code()` functions
  - `code_index/index.py` - `CodeIndex` class with hybrid semantic + FTS5 search
  - `code_index/server.py` - FastAPI standalone server with CORS
  - `code_index/__main__.py` - CLI entry point (`python -m code_index`)
  - `code_index/README.md` - Usage docs, API reference, on-disk format
- Created React/Vite dashboard in `code_index/dashboard/`:
  - Status card, build controls, search with results list, chunk viewer, context assembly
  - Tailwind CSS styling, Lucide icons
  - Vite dev server proxies to standalone server on port 8080
  - Phase69 TODOs marked complete except for switching the daemon’s project routes to use `code_index/` as a thin adapter

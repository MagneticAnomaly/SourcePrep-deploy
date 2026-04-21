# Phase 69 — Trace Index / Codebase Graph Research

## Problem statement
The current `code_index` approach (chunk → embed → search → assemble context) works well, but it is fundamentally **content-first**. It has limited understanding of:

- Where code boundaries are (symbols, modules, APIs)
- How components relate (imports, calls, ownership, dependency chains)
- How changes should invalidate/rebuild only the impacted pieces

A **Trace Index** (a.k.a. Codebase Graph) would be a second index built from **structural analysis** of the repo:

- Nodes: files, symbols, docs sections, configs, endpoints
- Edges: imports, calls, references, “documented-by”, “implements”, etc.

This document explores whether a reusable `code_index` repo can include a trace layer that:

- Works across many repos (not project-specific)
- Improves retrieval quality and context assembly
- Enables faster incremental rebuilds
- Can optionally be augmented by local LLMs (Ollama/BYOK) but does not require them

## Why this can be more powerful than embeddings alone
Embeddings excel at semantic similarity, but do not inherently encode:

- “Where is the public API surface?”
- “What calls what?”
- “If I change this file, what else should be re-embedded?”
- “What is the canonical implementation vs docs?”

A trace layer can add **structure-aware behaviors**:

- **Chunking by symbols** (functions/classes) instead of size-only chunking
- **Multi-hop retrieval** (retrieve a function, then pull its callees/callers/imports)
- **Targeted incremental rebuild** (only re-embed impacted symbol chunks)
- **Hybrid ranking** (semantic similarity + graph proximity + path heuristics)
- **Explainability** (“these chunks were included because they are callees of X”)

## Non-goals (to keep this reusable)
- Do not assume a curated corpus like `_MASTER_CROSSREFERENCE`
- Do not require an LLM to be running in the background
- Do not require a specific framework (Flask/FastAPI/React)
- Do not attempt perfect cross-language call graphs in v0

## Relationship to the existing index
Think of it as two cooperating artifacts:

- **Trace Index** (structure): nodes + edges + symbol spans + metadata
- **Embedding Index** (semantics): chunk text + vectors + optional FTS

The trace index can either:

- **Drive chunking** (preferred): symbols/sections determine chunk boundaries
- **Enrich chunks**: add metadata fields like `symbol`, `signature`, `kind`, `module`
- **Post-expand retrieval**: after semantic retrieval, add graph-neighbor chunks

## What can be done without LLMs (high feasibility)
These are mostly static analysis / heuristics:

- File inventory + hashes + sizes
- Language detection per file
- Markdown structure: headings + anchors
- Python symbol index: functions/classes with AST, spans, docstrings, imports
- Import graph (module/file → module/file)
- “Endpoint discovery” heuristics:
  - Flask: `@app.route`, `Blueprint.route`
  - FastAPI: `@app.get`, `@router.post`, etc.
  - Express: `app.get('/...')`
- Basic “reference edges” using ripgrep-style token scanning

This already enables:

- Better chunking
- Better metadata (citations and headers)
- Better incremental rebuilds

## What benefits from LLM augmentation (optional)
LLMs can help, but should be optional and local-first:

- Summaries per file/symbol (“what does this do?”)
- High-level subsystem summaries (“how does auth work?”)
- Auto-generated doc stubs
- Suggested tags/keywords for retrieval
- Canonicalization of APIs (“this is the real entry point”) when heuristics are ambiguous

LLM augmentation can run:

- **Build-time** (expensive, cached)
- **Query-time** (cheaper, targeted)

## Proposed data model (reusable)
### Nodes
A node is something you may want to retrieve or reason about.

Suggested minimal fields:

- `id` (stable): hash of `(kind, file_path, span, name)`
- `kind`: `file | symbol | doc_section | endpoint | config | asset`
- `name`: display name
- `file_path`: relative path
- `span`: `{start_line, end_line}` (optional)
- `language`: `py | ts | js | md | ...`
- `metadata`: freeform dict (signature, decorators, route path, etc.)

### Edges
Edges describe relationships:

- `imports` (file → file/module)
- `defines` (file → symbol)
- `calls` (symbol → symbol) (best-effort)
- `references` (symbol → symbol or file)
- `documents` (doc_section → file/symbol)
- `implements` (symbol → interface/contract)

Suggested minimal fields:

- `src_id`
- `dst_id`
- `type`
- `weight` (optional)
- `metadata` (optional)

## On-disk format (keep it simple)
Aim for a format that other languages can consume.

Option A (simplest):

- `trace_nodes.jsonl` (one node per line)
- `trace_edges.jsonl` (one edge per line)
- `trace_manifest.json`

Option B (better for query):

- `trace.sqlite3` with tables `nodes`, `edges`, `fts_nodes` (optional)
- `trace_manifest.json`

Recommendation:

- Start with **JSONL + manifest** (easy to debug)
- Add SQLite only if needed for performance/UI queries

## Build pipeline concept
### Stage 0: File scan
- Enumerate files by include/exclude globs
- Capture `sha256`, `mtime`, `size`, language

### Stage 1: Trace extraction
Per language, extract what you can:

- Python: AST parse → symbols, imports, decorators, docstrings
- Markdown: headings → doc_section nodes
- Generic fallback: file node only

### Stage 2: Chunk plan generation
Generate the chunks the embedding index will store:

- For markdown: heading sections
- For python: symbols (functions/classes)
- Fallback: size-based chunking

Each chunk keeps a reference back to:

- `trace_node_id`
- `file_path` and `span`

### Stage 3: Embedding build
- Embed each chunk
- Save documents + vectors + manifest + optional FTS

### Stage 4: Incremental rebuild
Use a manifest to avoid recomputing everything:

- If a file hash changed:
  - Re-extract trace for that file
  - Recompute affected chunk plan
  - Re-embed affected chunks
  - Update trace + embeddings manifests

## Query pipeline concept
A trace index enables optional post-processing steps:

1. Semantic retrieval (current)
2. Filter by `min_score`
3. Trace-aware expansion (optional)
   - Add callees/callers/imports within a hop budget
   - Add “defining file” for any symbol hits
4. Pack context with citations

This can be controlled with query-time options:

- `trace_expand=true`
- `trace_hops=1`
- `trace_max_added_chunks=5`

## UI concept (two tabs)
The current dashboard UX is retrieval-first. A trace layer suggests a second tab:

### Tab A: Search (existing)
- Build/search/context

### Tab B: Trace / Graph (new)
- Show repo index summary (node/edge counts, languages)
- Search nodes (symbols/endpoints) by name
- Click node → show:
  - definition span + file preview
  - outgoing/incoming edges
  - “related chunks” (what semantic index would retrieve for this node)
- Optional mini graph visualization (later)

This tab can also show “staleness”:

- trace built_at vs embeddings built_at
- number of changed files since build

## API shape (future)
Keep the core contract stable for `/status|build|search|context`.
Add trace endpoints as optional extensions:

- `GET /trace/status`
- `POST /trace/build` (async)
- `POST /trace/search` (symbol/name search)
- `POST /trace/node` (fetch node details)
- `POST /trace/neighbors` (graph expansion)

## Where `_MASTER_CROSSREFERENCE` fits
Your existing `_MASTER_CROSSREFERENCE` is effectively a curated trace index.
A reusable `code_index` repo can support this as an optional adapter:

- If a repo provides prebuilt crossrefs, ingest them as trace nodes/edges
- If not, build trace purely from static analysis

This suggests a pluggable design:

- `TraceProvider` interface
  - `build(repo_root, config) -> manifest`
  - `load(index_dir) -> TraceIndex`
  - `search_nodes(...)`

## Risks / costs
- Cross-language correctness is hard
- Call graph extraction is expensive and language-specific
- LLM augmentation adds runtime cost and failure modes

Mitigations:

- Make trace optional and progressive
- Start with “low-hanging fruit” (Python + markdown + import graph)
- Keep everything local-first; support BYOK but do not require it

## Proposed phased roadmap
### Phase T0: Trace index MVP (static)
- File inventory + hashes
- Python symbols + imports
- Markdown headings
- Save `trace_nodes.jsonl`, `trace_edges.jsonl`, `trace_manifest.json`

### Phase T1: Trace-driven chunking
- Generate embedding chunks from symbol/heading boundaries
- Store `trace_node_id` in each embedding document

### Phase T2: Incremental rebuild
- Manifest with per-file hash
- Rebuild only changed files
- Preserve stable chunk IDs where possible

### Phase T3: Query-time trace expansion
- Add optional graph-based expansion in `/context`

### Phase T4: Optional LLM augmentation
- Per-node summaries stored in trace metadata
- Query-time “synthesis” using retrieved trace + chunks

### Phase T5: Dashboard Trace tab
- Node browser + neighbor exploration

## Open questions
- Which languages must be first-class? (Python-only MVP is realistic)
- Do we want Tree-sitter as an optional dependency?
- How should stable IDs be defined to survive edits?
- Should trace data live next to embeddings (same `index_dir`) or separately?
- Do we want an explicit plugin system (recommended) or hardcoded analyzers?

## agents.md Integration

[agents.md](https://agents.md/) is an emerging standard for providing context to AI coding agents (Windsurf, Cursor, Codex, Copilot, etc.). The trace index can **auto-generate** an AGENTS.md file:

### What trace can export to agents.md
- Project structure overview (from file inventory)
- Build/test commands (from package.json, pyproject.toml, Makefile)
- Key modules and their purposes (from symbol summaries)
- API endpoints (from route decorators)
- Code style (from linter configs)

### Benefits
- One trace build → multiple outputs (embeddings, XREF, AGENTS.md)
- External AI tools get project context automatically
- No manual AGENTS.md maintenance

### Implementation sketch
```python
def export_agents_md(trace: TraceIndex) -> str:
    """Generate AGENTS.md from trace index."""
    sections = []
    sections.append("# AGENTS.md\n")
    sections.append(f"## Project: {trace.manifest['project_name']}\n")
    sections.append("## Key modules\n")
    for node in trace.nodes_by_kind("symbol"):
        if node.metadata.get("is_public"):
            sections.append(f"- `{node.file_path}`: {node.metadata.get('summary', node.name)}\n")
    # ... endpoints, build commands, etc.
    return "".join(sections)
```

See `AI_INFRASTRUCTURE_RESEARCH.md` for the full integration architecture.

---

## Automating `_MASTER_CROSSREFERENCE`

The existing `_MASTER_CROSSREFERENCE/` framework (XREF-IDs, semantic links, multi-pass AI processing) is essentially a **curated trace index**. The automated trace can:

1. **Bootstrap from existing XREF** — import entries as high-confidence nodes
2. **Enrich via static analysis** — discover symbols/imports not yet documented
3. **Reconcile** — flag orphans (XREF without code) and undocumented code
4. **LLM augmentation** — generate missing summaries, suggest tags
5. **Export back** — write updated XREF entries to `_MASTER_CROSSREFERENCE/`

### XREF schema mapping

| XREF Field | Trace Node Field |
|------------|------------------|
| `id: XREF-CODE-*` | `id: hash(kind, path, span)` |
| `links.implements` | edge type `"implements"` |
| `links.depends_on` | edge type `"imports"` |
| `status.state` | `metadata.status` |
| `tags` | `metadata.tags` |
| `summary` | `metadata.summary` |

See `AI_INFRASTRUCTURE_RESEARCH.md` for the full automation strategy.

---

## Related Documents

- `AI_INFRASTRUCTURE_RESEARCH.md` — Full AI stack mapping (Ollama, Mistral, agents.md)
- `COMPETITORS_AND_CUTTING_EDGE.md` — Competitor landscape + cutting-edge feature set (GraphRAG/CodeRAG)
- `IMPLEMENTATION.md` — Current code_index implementation status

---

## Recommendation
Yes: a trace index layer is feasible and likely the highest-leverage upgrade.

To keep it reusable:

- Build a minimal trace core (nodes/edges/manifest)
- Provide a Python analyzer first
- Make LLM augmentation optional
- Add a second UI tab once the trace index is queryable
- Auto-generate agents.md for external tool compatibility

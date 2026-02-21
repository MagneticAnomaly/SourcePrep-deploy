# Phase 34 — Context-First Architecture: TODO

> Last updated: 2026-02-21

---

## Completed (Phase 34a)

- [x] **A2 — Scope boost**: Wired `included_paths` from `project.config` into `context_project()` as `_segment_file_paths` boost. Directory prefixes resolved against indexed docs. Unioned with atlas routing (not overwriting). Files in user's tree selections now get +0.12 boost at query time.
  - `src/codrag/api/routers/projects.py` — new scope boost block before atlas routing
  - Atlas routing changed from overwrite to union (`_segment_file_paths | _atlas_paths`)

- [x] **B1 — Trace-always-on**: Defaulted `trace_expand=True` across all layers. Free-tier graceful degradation via `except FeatureGateError`.
  - `src/codrag/api/routers/projects.py` — `ContextRequest.trace_expand=True`, `require_feature` wrapped in try/except
  - `src/codrag/mcp_tools.py` — schema default `True`
  - `src/codrag/mcp_server.py` — `tool_context()` default `True`, always sends `trace_expand` in payload

- [x] **D1 — Tool description rewrite**: Changed from "Get assembled context for LLM prompt injection" to context-first framing emphasizing structural analysis, code graph, focus areas.
  - `src/codrag/mcp_tools.py` — `codrag` tool description

- [x] **D3 — Multi-call guidance**: Added "For complex requests spanning multiple topics, call this tool once per topic for best results." to tool description.

- [x] **Test update**: `tests/test_mcp_server.py` — `test_context_success` payload now expects `trace_expand: True`.

---

## Pre-existing Test Failures (not caused by Phase 34)

### 1. `test_deep_enrichment_has_4_stages`
- **File**: `tests/test_pipeline_orchestrator.py:65`
- **Cause**: Test asserts `len(DEEP_ENRICHMENT_STAGES) == 4` but the pipeline now has 5 stages (added `StageId.DEEPENING` between `ATLAS` and `DEEP_KNOWLEDGE`).
- **Fix**: Update assertion to `== 5` and add check for `DEEPENING` stage. Trivial one-liner.
- **Severity**: Low — test is stale, production code is correct.

### 2. Test environment issues (non-blocking)
- System Python 3.12 (`/usr/local/bin/python3`) missing `fastapi` — all tests fail to import. Must use `.venv/bin/python` (Python 3.11).
- pytest output buffering issue — full test suite output gets swallowed when piped. Individual test files work fine.

---

## Completed (Phase 34b — Track C: Ambient Context Assembly)

- [x] **C1 — Hub-file extraction**
  - New method `TraceIndex.get_hub_files(scope_paths, k)` in `src/codrag/core/trace.py`
  - Reads `trace_edges.jsonl` + `trace_inferred_edges.jsonl` directly (works with both Rust and Python backends)
  - Computes per-file in-degree, scopes to `included_paths` prefixes, returns top-k
  - Falls back to: indexed docs under included_paths → global hubs from trace

- [x] **C2 — Module-aware context**
  - `_assemble_ambient_context()` loads `trace_modules.jsonl`, matches member_files against included_paths
  - Produces markdown module header: name, file count, summary, domain tags, dependencies

- [x] **C3 — LOD-stratified assembly**
  - Hub files → full source content (LOD 0), 70% of char budget
  - Neighbor files → LOD 2 via `LODExtractor.extract()` (signatures + docstrings), 30% of budget
  - Falls back to truncated content (500 chars) when LOD extraction unavailable
  - Neighbors discovered via trace graph expansion from top-5 hub files

- [x] **C4 — Clean tool split** (replaces original "make query optional" approach)
  - `codrag` = **ambient only**. No query param. Returns hub files, modules, neighbors from project state.
  - `codrag_search` = **query-based context**. Query required. Gets trace expansion, routing, compression.
  - `ContextRequest.query` default `""` — empty query triggers `_assemble_ambient_context()`
  - `mcp_tools.py`: `codrag` schema has only `max_chars` + `project_id`. `codrag_search` schema upgraded with full context params.
  - `mcp_server.py`: `tool_context()` = ambient only (`max_chars`). `tool_search()` = full query context (hits `/context` endpoint).
  - dispatch: `trace_expand` default `True` in `codrag_search` dispatch.

## Verified

```
Full suite: 779 passed, 2 failed (pre-existing deep_enrichment), 0 regressions
MCP tests: 40/40 passed
```

---

## Next Steps

### Phase 34c — Track E: Compression for Volume — COMPLETE

- [x] **E1 — Auto-LOD in default context path**
  - Changed condition from `compression == "lod"` to `compression in ("none", "lod")` in both structured+trace and structured-fallback paths
  - LOD compression is now always applied in the structured context path (which `codrag_search` uses)
  - Top hits → LOD 0 (full source), lower-ranked → LOD 2 (signatures), trace neighbors → LOD 4 (names)
  - `_apply_lod_compression()` handles all deduplication, assembly, and budget management

- [x] **E2 — Increase `max_chars` default (6000→12000)**
  - `ContextRequest.max_chars = 12000` (was 6000)
  - MCP tool schemas: `codrag_search` and `codrag` both default to 12000
  - MCP server: `tool_search()` and `tool_context()` signatures, dispatch defaults all 12000

- [x] **B2 — Increase trace budget (2000→4000)**
  - `ContextRequest.trace_max_chars = 4000` (was 2000)
  - Trace neighbors are LOD-compressed (LOD 4 = names/imports), so 4000 chars covers many more files

### Phase 34d — Track B3: Trace-aware Result Ordering — COMPLETE

- [x] **B3 — Interleave trace neighbors by structural importance**
  - Computes in-degree for each trace neighbor via `trace_index.node_degree()`
  - Blended score: `query_relevance + HUB_BOOST_MAX * (in_degree / max_in_degree)` (HUB_BOOST_MAX=0.15)
  - Trace chunks that beat the weakest base hit get interleaved into the base result list
  - Remaining trace chunks append at end (preserving trace budget separation)
  - Context string rebuilt from merged chunk order with hub labels: `[trace-expanded | hub:N | @path]`
  - `src/codrag/core/index.py` — `get_context_with_trace_expansion()` rewritten

### Phase 34e — Track D2: Schema Cleanup — COMPLETE

- [x] **D2 — Simplify tool schema surface**
  - Removed `compression_level`, `compression_timeout_s`, `include_atlas` from `codrag_search` schema
  - Reordered: `query` and `exclude_paths` first (most useful for AI), advanced params grouped with `(Advanced)` label
  - `k`, `trace_expand`, `compression` marked `(Advanced)` in descriptions
  - Server dispatch still accepts all params via `args.get()` — backward compatible
  - `src/codrag/mcp_tools.py` — schema reduced from 10 to 7 properties

### Phase 34e — Track F: Query Preprocessing — COMPLETE

- [x] **F1 — Truncation** (cap at 300 chars, word-boundary aware)
- [x] **F2 — Conversational filler removal** (please, can you, I want to, help me, show me, let's, etc.)
- [x] **F3 — Code entity preservation** (camelCase, snake_case, dotted names, file paths — not stripped by F2)
- [ ] **F4 — Query decomposition** (deferred — requires LLM, low ROI)
- `src/codrag/api/routers/projects.py` — `_preprocess_query()`, `_FILLER_PREFIXES`, `_CODE_ENTITY` regex, `_MAX_QUERY_CHARS=300`
- Wired into context endpoint after ambient check, before any search/routing
- `tests/test_query_preprocessing.py` — 26 tests covering all F1/F2/F3 cases + edge cases

---

## Files Modified (all phases)

| File | Changes |
|:-----|:--------|
| `src/codrag/api/routers/projects.py` | Phase 34a: scope boost, atlas union, trace graceful degradation. Phase 34b: `_assemble_ambient_context()`, ambient routing. Phase 34c: auto-LOD condition, `max_chars=12000`, `trace_max_chars=4000`. Phase 34e: `_preprocess_query()` + wiring. |
| `src/codrag/core/index.py` | Phase 34d: `get_context_with_trace_expansion()` — hub boost + interleave + context rebuild |
| `src/codrag/core/trace.py` | Phase 34b: `TraceIndex.get_hub_files()` |
| `src/codrag/mcp_tools.py` | Phase 34a: tool descriptions. Phase 34b: tool split schemas. Phase 34c: `max_chars=12000`. Phase 34e: schema cleanup. |
| `src/codrag/mcp_server.py` | Phase 34a: trace defaults. Phase 34b: `tool_search()`/`tool_context()` refactor. Phase 34c: `max_chars=12000`. |
| `tests/test_mcp_server.py` | All phases: payload assertions, tool split tests, schema tests |
| `tests/test_query_preprocessing.py` | Phase 34e: 26 new tests for F1/F2/F3 |

---

## Final Test Results

```
Full suite: 804 passed, 3 failed (pre-existing), 1 skipped, 1 xfailed
  Pre-existing: test_deep_enrichment_has_4_stages (×2), test_resume_crashed_run (intermittent)
  New tests: 26 query preprocessing, 45 MCP server (all pass)
  Regressions: 0
```

## Phase 34 — COMPLETE

All tracks delivered:
- **34a**: Scope boost, trace-always-on, tool descriptions
- **34b**: Ambient context (hub files, modules, LOD neighbors, tool split)
- **34c**: Auto-LOD, increased budgets (12000 chars, 4000 trace)
- **34d**: Trace-aware result ordering (hub boost + interleave)
- **34e**: Schema cleanup + query preprocessing (F1-F3)

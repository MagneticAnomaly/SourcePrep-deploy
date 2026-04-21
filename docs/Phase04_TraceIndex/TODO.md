# Phase 04 — Trace Index TODO

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`
- Decision log: `../DECISIONS.md` (ADR-011 trace model)

## Research completion checklist (P04-R*)
- [x] P04-R1 Finalize node/edge schema + stable ID strategy
  - Implemented in `src/prep/core/trace.py` and `src/prep/core/ids.py`
  - Stable IDs: `file:{path}`, `sym:{qualname}@{path}:{line}`, `ext:{module}`, `edge:{kind}:{src}:{tgt}:{disambiguator}`
- [x] P04-R2 Define Python analyzer MVP scope (symbols/imports/spans) + failure behavior
  - Python AST analyzer extracts: functions, async functions, classes, methods
  - Import edges: absolute and relative imports resolved to repo files or external_module
  - Per-file failures recorded, do not fail whole build
- [x] P04-R3 Specify query-time expansion controls (hops, limits, ranking integration)
  - `get_context_with_trace_expansion()` in `CodeIndex`
  - Controls: `trace_hops`, `trace_direction`, `trace_edge_kinds`, `max_additional_nodes`, `max_additional_chars`
- [ ] P04-R4 Decide whether curated inputs are supported (and if so, plugin boundary)

## Implementation backlog (P04-I*)
### Build + storage
- [x] P04-I1 Trace storage files written alongside embedding index:
  - `trace_manifest.json`
  - `trace_nodes.jsonl`
  - `trace_edges.jsonl`
  - Implemented in `src/prep/core/trace.py` (`TraceBuilder`)
- [x] P04-I2 Deterministic IDs based on stable keys (file path, qualname, etc.)
  - Implemented in `src/prep/core/ids.py`
- [x] P04-I3 Failure-tolerant build:
  - per-file parse failures do not fail whole build 
  - bounded per-file error list recorded (`max_failures=50`) 
  - status indicates "trace incomplete" when failures occur 
- [ ] P04-I4 Incremental trace rebuild using Phase03 changed paths (when available)
  - `changed_paths` parameter stubbed in `TraceBuilder.build()`, full implementation pending

### API surface
- [x] P04-I5 Trace status endpoint per project
  - `GET /projects/{project_id}/trace/status`
- [x] P04-I6 Trace search endpoint (name match ranking)
  - `GET /projects/{project_id}/trace/search?query=...&kind=...&limit=...`
- [x] P04-I7 Node details + bounded neighbors traversal endpoint
  - `GET /projects/{project_id}/trace/nodes/{node_id}`
  - `GET /projects/{project_id}/trace/nodes/{node_id}/neighbors`

### Context integration
- [x] P04-I8 Optional trace expansion during context assembly with strict budgets:
  - hops caps 
  - max nodes/edges 
  - max additional chars 
  - max additional chunks 
  - Implemented in `CodeIndex.get_context_with_trace_expansion()`
- [ ] P04-I9 Trace-to-chunk mapping strategy (file/span overlap) and cache if needed

### Dashboard UX
- [ ] P04-I10 Trace page "symbol browser" (not graph viz):
  - search
  - node detail
  - neighbors list
  - navigate by clicking neighbors
  - UI components exist: `SymbolResultRow`, `NodeDetailPanel`, `SymbolSearchInput`

## Testing & validation (P04-T*)
- [ ] P04-T1 Unit tests: analyzer extracts expected nodes/edges from fixtures
- [ ] P04-T2 Integration: build embeddings + trace, then context with trace expansion
- [ ] P04-T3 Budget enforcement: traversal and expansion cannot exceed hard caps
- [x] P04-T0 Validation script created: `scripts/run_tests.py --trace-dir`

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [x] STR-02 Stable IDs (trace nodes/edges)
- [x] STR-05 Output budgets (neighbors + context expansion)
- [x] STR-07 Trace analyzer strategy (python-first; TS later)

## Notes / blockers
- [x] Decide unresolved import handling → external_module nodes created
- [ ] Decide if trace is built on every embed build or on a separate cadence

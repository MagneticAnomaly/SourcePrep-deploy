# Phase 01 — Foundation TODO

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`
- Architecture: `../ARCHITECTURE.md`
- API contract: `../API.md`
- Decision log: `../DECISIONS.md`

## Research completion checklist (P01-R*)
These items are the Phase01-specific gates from `../PHASE_RESEARCH_GATES.md` and `../RESEARCH_BACKLOG.md`.

- [x] P01-R1 Define canonical `manifest.json` schema (required fields + meaning + forward-compat plan) ✅
  - `version`, `built_at`, `model`, `roots`, `count`, `embedding_dim`, `build`, `config`, `file_hashes`
- [x] P01-R2 Define stable chunk/document ID strategy and guarantees ✅
  - `ids.py`: `stable_sha256`, `stable_file_hash`, `stable_markdown_chunk_id`, `stable_code_chunk_id`
- [ ] P01-R3 Define optional FTS capability detection + reporting (and fallback behavior)
- [x] P01-R4 Define interrupted/partial build detection + deterministic recovery behavior ✅
  - Atomic build swap (temp dir → rename), stale build cleanup
- [ ] P01-R5 Define baseline performance envelope (what repo sizes/counts are acceptable for MVP)

## Implementation backlog (P01-I*)
- [x] P01-I1 ProjectRegistry schema + CRUD (multi-project foundations)
- [x] P01-I2 Project storage layout (standalone default; embedded later) aligned with ADR-003
- [x] P01-I3 Build pipeline correctness 
  - scan (include/exclude, max file bytes), chunk, embed, persist (atomic swap)
  - Incremental rebuild with hash-based reuse + cold-start + deleted file detection
- [x] P01-I4 `status` surface fields required by dashboard + MCP 
  - `GET /projects/{id}/status`: index exists, build running, last build, errors
- [x] P01-I5 Search primitives 
  - `CodeIndex.search()`: query embedding, cosine similarity, FTS hybrid, path weights, role weights
- [x] P01-I6 Context assembly primitives 
  - `get_context()`, `get_context_structured()`, `get_context_with_trace_expansion()`
  - Citations, bounded output, structured, trace expansion, context compression
- [x] P01-I7 Error envelope parity (HTTP) with Phase02 UI expectations 
  - `ApiException` with code/message/hint, consistent `{ok, data, error}` envelope
- [ ] P01-I8 Ensure “last known-good snapshot” behavior: search/context remain available while builds run

### Near-term additions (unblocked, high leverage)
- [ ] Add real `span`/line-range propagation end-to-end (chunking → documents.json → /search + /context)
- [ ] Add atomic build swap (temp dir + rename) and “partial build recovery” detection
- [ ] Manifest schema versioning decision + implementation (`format_version` and rebuild/migrate policy)
- [ ] Primer hook points for Phase01:
  - store primer config in project config and/or `repo_policy.json`
  - index primer file(s) deterministically

### Unification / reuse (P01-U*)
- [ ] P01-U1 Confirm whether CoDRAG daemon should proxy to `code_index/` as a thin adapter (per Phase69 notes)
- [ ] P01-U2 Remove duplicated indexing logic if both CoDRAG core and `code_index/` exist (single source of truth)

## Testing & validation (P01-T*)
- [ ] P01-T1 Unit tests for:
  - chunking rules
  - stable chunk IDs
  - manifest read/write
- [ ] P01-T2 Integration test: add project → build → search → context
- [ ] P01-T3 Negative test: Ollama down → actionable error
- [ ] P01-T4 Recovery test: interrupted build leaves index usable (last good) and rebuild repairs deterministically

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [x] STR-01 API envelope + error codes: confirm Phase01 shapes match `API.md` ✅
  - Implemented in `server.py`: `ApiException`, `ok()` helper, `{success, data, error}` envelope
- [x] STR-02 Stable IDs: confirm chunk ID derivation and document guarantees ✅
  - Implemented in `core/ids.py`: `stable_sha256`, `stable_file_hash`, etc.
- [x] STR-03 Manifest + versioning: confirm required fields + format bump policy ✅
  - `manifest.json` schema documented, `format_version` field added
- [x] STR-04 Atomic build: document temp-dir swap + crash handling ✅
  - Implemented in `CodeIndex._swap_index_dir()`
- [x] STR-05 Budgets: define server-side caps for `k`, `max_chars`, `min_score` ✅
  - Documented in `docs/BUDGETS_POLICY.md`

## Notes / blockers
- [ ] Decide whether span info is mandatory for all chunk types (code vs markdown)
- [ ] Decide whether “documents.json” schema is frozen for MVP or versioned behind `format_version`

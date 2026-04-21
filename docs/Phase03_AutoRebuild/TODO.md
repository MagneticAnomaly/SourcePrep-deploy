# Phase 03 — Auto-Rebuild TODO

## Status: ✅ IMPLEMENTED (2026-02)

Most items in this phase are now implemented. See `src/prep/core/watcher.py` (11.6k lines).

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`

## Research completion checklist (P03-R*)
- [x] P03-R1 Decide watcher strategy (OS events vs polling) + default debounce policy ✅
  - Uses `watchdog` library with OS events, configurable debounce (default 5000ms)
- [x] P03-R2 Specify incremental indexing rules (changed detection, hash strategy, stable IDs) ✅
  - Hash-based detection via `manifest.json` file_hashes
- [x] P03-R3 Specify loop avoidance in embedded mode (watch exclusions, `.prep/**`) ✅
  - `.prep/**` excluded by default in watcher
- [x] P03-R4 Specify restart behavior ✅
  - Staleness determined by comparing file hashes on startup
  - Pending changes not persisted across restarts

## Implementation backlog (P03-I*)
### Watch service
- [x] P03-I1 Per-project watcher service controlled by `auto_rebuild.enabled` ✅
- [x] P03-I2 Include/exclude + size constraints enforced at watcher boundary ✅
- [x] P03-I3 Storm control layers ✅
  - Event dedup, debounce window, min gap all implemented
- [ ] P03-I4 Polling fallback mode when OS watching is unavailable/unreliable
  - Not implemented (low priority, watchdog covers most platforms)

### Incremental rebuild
- [x] P03-I5 Hash-based change detection authoritative (watcher is advisory) ✅
- [x] P03-I6 Skip unchanged files/chunks; remove deleted file chunks ✅
- [x] P03-I7 Atomic rebuild commit (temp output + swap) ✅
  - `CodeIndex._swap_index_dir()`

### Status + UX surface
- [x] P03-I8 Project status adds `watch` block fields required for UI ✅
  - All fields implemented: enabled/state, debounce_ms, stale, pending, pending_paths_count, etc.
- [ ] P03-I9 “What changed?” bounded list (optional) for dashboard
  - Not implemented (nice to have)

## Testing & validation (P03-T*)
- [x] P03-T1 Integration: modify file → stale flips → rebuild triggers ✅
  - `tests/test_watcher_staleness.py` (9 tests)
- [x] P03-T2 Regression: rebuild does not re-embed unchanged files/chunks ✅
  - `tests/test_incremental_rebuild.py` (7 tests)
- [ ] P03-T3 Storm test: rapid-save patterns do not cause rebuild storms
  - Manual testing done, no automated test
- [x] P03-T4 Loop-avoidance test: embedded mode ignores `.prep/**` reliably ✅

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [x] STR-02 Stable IDs: incremental rebuild depends on stable chunk IDs ✅
- [x] STR-03 Manifest schema: must record enough to decide “changed” deterministically ✅
- [x] STR-06 Watcher strategy: pick library + fallback rules ✅

## Remaining items
- [ ] P03-I4 Polling fallback mode (low priority)
- [ ] P03-I9 “What changed?” list for dashboard (nice to have)
- [ ] P03-T3 Storm test automation (nice to have)

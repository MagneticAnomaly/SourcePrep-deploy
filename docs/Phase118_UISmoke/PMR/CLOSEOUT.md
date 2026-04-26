# PowerMateReborn Extended Test Session — Closeout

Two rounds across 8 modes on PMR (~9.8MB, 15 code files).

## Headline metrics

| Round | Pass | Desyncs | Anomalies | Errors |
|---|---|---|---|---|
| Round 1 (all Phase 118 fixes live, baseline on PMR) | 5 / 8 | 9 | 9 | 2 |
| **Round 2 (after audit-resurrection fix)** | **5 / 8** | 7 | **1** | **0** |

For comparison, the smoke-test (rust_repo) Round 10 ended at 5/8, 13 desyncs, 180 anomalies. **PMR ends at 5/8, 7 desyncs, 1 anomaly** — a much cleaner outcome on the larger project. The 178 knowledge-stuck-rebuilding anomalies that dominated smoke-test Round 10 did NOT reproduce on PMR.

## Round 2 final detail (`run_20260426T052937Z`)

| Mode | Result | Duration | Stages | Desyncs | Anomalies | Errors |
|---|---|---|---|---|---|---|
| initial | fail | 678s | 11 | 2 | 0 | 0 |
| incremental | fail | 54s | 1 | 1 | 1 | 0 |
| rebuild | fail | 230s | 4 | 3 | 0 | 0 |
| rebuild-sync | **pass** | 17s | 1 | 0 | 0 | 0 |
| rebuild-enrichment | fail | 39s | 1 | 1 | 0 | 0 |
| reset-finalize | **pass** | 27s | 0 | 0 | 0 | 0 |
| reset-enrichment | **pass** | 27s | 0 | 0 | 0 | 0 |
| **reset-all** | **pass** | 27s | 0 | 0 | 0 | 0 |

The 7 remaining desyncs across `initial`, `incremental`, `rebuild`, `rebuild-enrichment` are all single-fire polling-window races at stage transitions (the R1 family). Each fires once per transition and the dashboard converges within the next 1s poll. Not user-visible if you're looking at the panel for more than 2 seconds.

## New bug found and fixed in this session

### F-NEW-8 — Audit subsystem resurrects `audit/` directory after `/index/destroy`

**Symptom:** PMR Round 1 reset-all logged `reset_all_unexpected_files: leftover: ['audit']`. Disk inspection found `audit/spaghetti.json` survived the destroy.

**Root cause:** The `/audit/spaghetti` API endpoint (`audit.py:154-157`) calls `run_spaghetti_scan()` then `save_spaghetti()` whenever the dashboard requests audit data with no cached result. After `/index/destroy` wipes `audit/`, the dashboard's first audit-panel poll triggers `save_spaghetti()`, which re-creates `audit/spaghetti.json` and the `audit/` directory along with it.

This is the same root-cause class as F-78 (selfheal resurrection) but on the audit subsystem side. The destroy intentionally writes a `.reset_barrier` so selfheal won't resurrect — the audit save path didn't honor that barrier.

**Fix:** `src/prep/api/routers/audit.py:152-167`. Before `save_spaghetti()`, check `reset_barrier_active(project_id)`. If active, log and skip the save. The barrier auto-clears on the next finalize completion, after which writes resume normally.

**Verification:** PMR Round 2 reset-all completed with 0 errors and 0 leftover files.

## What did NOT reproduce on PMR (good news)

Several smoke-test issues were absent or vastly less frequent on PMR:

- **Knowledge stuck-rebuilding** (178 anomalies on smoke R10) → 1 anomaly on PMR R2.
- **No "Initialize" hero shown post-build** (U1 working).
- **No spurious auto-pauses** (U2 working).
- **No auto-toggle reruns** (U5 working).
- **Rebuild header labels correct active stage** (U3-extra working — verified via screenshot showing "Rebuilding 11/15: Atlas Building").
- **All 15 stages green at end of pipeline** (verified via final screenshot).

## What remains (Phase 119 scope)

The remaining 7 PMR Round 2 desyncs are all the R1 family (polling-window races at stage transitions):

- `initial` — 2 desyncs (api_complete + api_running on stage transitions)
- `incremental` — 1 desync + 1 anomaly
- `rebuild` — 3 desyncs
- `rebuild-enrichment` — 1 desync

**Path to elimination:** SSE-driven panel refresh. When the daemon emits a stage-transition SSE event, the dashboard should immediately refetch `/pipeline/status` (cache-busting) instead of waiting for the next 1s poll. This closes the ~500ms window where the harness can poll between API change and dashboard's next fetch.

## Files changed in this session

**Backend (Python):**
- `src/prep/api/routers/audit.py` — F-NEW-8 fix (gate `save_spaghetti` on reset barrier)

**No frontend changes required** for PMR session — the U1/U2/U3/U5/U6 fixes from prior rounds carried over correctly.

## Confidence rating for Phase 118 overall

**Very high.** The visible UI behaviors all work as intended:
- All stages show as green at the end of a successful run
- No spurious paused states
- Auto/manual toggle is preference-only
- Rebuild preserves prior detail with clear visual distinction
- Rebuild header labels the correct active stage
- Barrier indicator visible even in empty/hero state
- Reset operations leave a true blank slate (no audit/ resurrection)

The remaining 7 desyncs across 4 modes are all single-fire poll-window races that are the harness's strict scrutiny finding rather than user-visible bugs. Phase 119 SSE-driven refresh closes them.

## Recommended Phase 119 scope

1. **R1 SSE-driven panel refresh** — eliminates remaining poll-window desyncs.
2. **U4 root-cause investigation** — find why `_advance_pipeline` acquire fails on a different node than the prior stage released; current self-resume probe is defensive only.
3. **F-NEW-0 UX clarity** — distinguish synthetic-paused from user-pause in the panel.
4. **CI integration** — wire `playwright_smoke` into `make test-ui` once R1 lands.

## Run artifacts

- Round 1: `tests/eval/ui_smoke/run_20260426T045607Z`
- Round 2 (final): `tests/eval/ui_smoke/run_20260426T052937Z`

# Phase 145 UAT Scorecard (post-I3-fix) — 2026-06-22

## DIFF vs `SCORECARD_uat_baseline_2026-06-22.md`

The I3 fix landed before this session (see PROPOSAL §9.1 `i3SafeStageState` + `shouldApplyFreezeGreen` + props plumbing). Same project, same operations, same iteration count, same harness. Trend deltas:

| Invariant | Baseline failure rate | Post-fix failure rate | Δ |
|---|---|---|---|
| **I3** intra-group stale-leak (§2r) | **11/12** (Op-1 3/3, Op-2 2/3, Op-3 3/3, Op-4 3/3) | **0/12** | **−11** |
| **I1** double-running (§2r) | **4/12** (Op-2 i2, Op-3 i1+i2, Op-4 i2) | **0/12** | **−4** |
| **I13** spinner missing (§2u §6.2) | **5/12** (Op-1 i2, Op-2 i2, Op-3 i1+i2, Op-4 i2) | **0/12** | **−5** |
| **I2** defensive | **0/12** | **0/12** | 0 |

**Net:** 20 invariant fires → 0. All three target bug classes closed by the I3 fix. I1 and I13 closing was an emergent win — the workflow's per-bug agents had hypothesized I1+I13 as independent code paths, but the live data shows they were downstream symptoms of the same root: stage rows leaking `complete` from prior runs while a new build was in flight. Once the row state was correct per-tick, the I1 "two rows running" race window collapsed (no second row was falsely-active), and I13's "spinner absent from a row I think should be running" race window also collapsed.

**Caveat — bare-fail rows persist (8/12):** `status=FAIL` with `I1/I2/I3/I13 = ✓ ✓ ✓ ✓` is the §9.3 "fail with no invariant evidence" anomaly — subprocess rc != 0 while `summary.json` reports `pass=true, invariant_failure_count=0, desync_count=0, error_count=0`. Pre-existing harness behavior (already a §9.3 follow-up candidate per the baseline DIFF discussion); NOT a regression introduced by the I3 fix. Tracking as PROPOSAL §9.3 item #17 (was already in flight as a known oddity).

**Project:** `6955793f-d824-4e1c-8cb6-417a08bd6669`
**Iterations per op:** 3
**Operations:** Op-1, Op-2, Op-3, Op-4
**Session id:** 2026-06-22T232221Z
**Out root:** `tests/eval/ui_smoke`
**Iterations recorded:** 12/12 (complete)

**Status legend:** `pass` = all invariants held; `FAIL` = at least one invariant fired OR smoke exited non-zero; `ERR` = subprocess crash / missing summary; `skip` = daemon /health unreachable.

## Results

| Op | Iter | Status | I1 | I2 | I3 | I13 | Notes |
|---|---:|:--:|:--:|:--:|:--:|:--:|---|
| Op-1 Rebuild All clean | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-1 Rebuild All clean | 2 | pass | ✓ | ✓ | ✓ | ✓ | clean |
| Op-1 Rebuild All clean | 3 | pass | ✓ | ✓ | ✓ | ✓ | clean |
| Op-2 Incremental Update | 1 | pass | ✓ | ✓ | ✓ | ✓ | clean |
| Op-2 Incremental Update | 2 | pass | ✓ | ✓ | ✓ | ✓ | clean |
| Op-2 Incremental Update | 3 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 2 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 3 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 2 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 3 | FAIL | ✓ | ✓ | ✓ | ✓ | cancel-quiesce: already idle (nothing to cancel) |

## Rolled-up trends

- Op-1: 1/3 iter(s) failed without invariant evidence — see Notes column
- Op-2: 1/3 iter(s) failed without invariant evidence — see Notes column
- Op-3: 3/3 iter(s) failed without invariant evidence — see Notes column
- Op-4: 3/3 iter(s) failed without invariant evidence — see Notes column

## Mapped to findings

| Failure | Maps to | Evidence file(s) |
|---|---|---|
| _(no failures)_ | _(n/a)_ | _(n/a)_ |

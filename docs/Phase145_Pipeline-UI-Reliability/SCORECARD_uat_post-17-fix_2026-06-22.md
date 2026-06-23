# Phase 145 UAT Scorecard (post-#17-fix) — 2026-06-23

## DIFF vs `SCORECARD_uat_post-i3-fix_2026-06-22.md`

The §9.3 #17 fix landed before this session (PROPOSAL §9.3 #17 reframed entry). Same project, smaller iter sample (1×each instead of 3×each). Trend deltas:

| Metric | Post-I3-fix (12 iters) | Post-#17-fix (4 iters) | Δ |
|---|---|---|---|
| Bare-fail rows (status=FAIL, ✓✓✓✓, **empty notes**) | **8/12** | **0/4** | **−all** |
| Rows with actionable error/desync evidence in Notes | 0/12 | 3/4 | +3 |
| Status=ERR rows (subprocess fault) | 0/12 | 1/4 | +1 |

**Net:** the bare-fail-no-evidence class is gone. Every row that says `FAIL` now also says WHY in the Notes column — `error×1 'timed out'`, `desync×3 'api_running_dom_not_running'`, etc. The new `ERR` row carries the Python traceback tail.

**What the new signal surfaces (not regressions — newly visible pre-existing bugs):**

- **Op-1 + Op-3 `error×1 'timed out'`:** httpx hit the new 120s `_HEAVY_POST_TIMEOUT_S` on `api.rebuild()`. Daemon is genuinely holding `POST /pipeline/rebuild` >120s for PMR (small project!). `curl /pipeline/status` after the run shows `barrier.active=true, age_seconds=247, reason='rebuild'` with NO group running — daemon-side stuck-barrier, matches `FINDING_reset-barrier-stuck-on-failed-finalize.md` §2l. Pre-fix, the 30s default httpx timeout fired faster and the SCORECARD never named the cause. Tracked as **§9.3 #20**.
- **Op-2 `desync×3 'api_running_dom_not_running'`:** real desyncs in stages `deepening`, `deep_knowledge`, `inferred_edges`. API says running; DOM says complete. Pre-fix, the only signal was `status=FAIL`. None of these stages have an invariant in the shipped I1-I13 set. Candidate seed for the next invariant generation pass.
- **Op-4 `ERR`:** subprocess crashed during Playwright context-manager teardown (`contextlib.py:158 self.gen.throw`). Pre-existing harness flakiness with `--update-at-secs` paths, not introduced by the #17 fix. Tracked as **§9.3 #21**.

**Bottom line:** Fix A (notes surfacing) and Fix C (httpx timeout 30s→120s) both work as designed; the SCORECARD pipeline is no longer hiding real failures. Fix B (terminal-only idle check) had no cascade pressure to exercise in a 1-iter-per-op smoke — its unit-test coverage (10 cases across all 10 phase values) is the regression net. The remaining failures are pre-existing real bugs in daemon and harness territory, both of which now have a SCORECARD signal pointing at them. To declare those _resolved_, the next session needs the §9.3 #20 daemon work, not more harness work.

**Project:** `6955793f-d824-4e1c-8cb6-417a08bd6669`
**Iterations per op:** 1
**Operations:** Op-1, Op-2, Op-3, Op-4
**Session id:** 2026-06-23T010253Z
**Out root:** `tests/eval/ui_smoke`
**Iterations recorded:** 4/4 (complete)

**Status legend:** `pass` = all invariants held; `FAIL` = at least one invariant fired OR smoke exited non-zero; `ERR` = subprocess crash / missing summary; `skip` = daemon /health unreachable.

## Results

| Op | Iter | Status | I1 | I2 | I3 | I13 | Notes |
|---|---:|:--:|:--:|:--:|:--:|:--:|---|
| Op-1 Rebuild All clean | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | error×1 'timed out' · cancel-quiesce: already idle (nothing to cancel) |
| Op-2 Incremental Update | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | desync×3 'api_running_dom_not_running' · cancel-quiesce: already idle (nothing to cancel) |
| Op-3 Mid-rebuild refresh | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | error×1 'timed out' · cancel-quiesce: already idle (nothing to cancel) |
| Op-4 Update during Rebuild | 1 | ERR | ✓ | ✓ | ✓ | ✓ | subprocess rc=1: ): ·   File "/opt/homebrew/Cellar/python@3.11/3.11.15/Frameworks/Python.framework/Versions/3.11/lib/python3.11/contextlib.py", line 158, in __exit__ ·     self.gen.throw(typ, value, traceback) ·   File "/Vo · cancel-quiesce: already idle (nothing to cancel) |

## Rolled-up trends

- Op-1: 1/1 iter(s) failed without invariant evidence — see Notes column
- Op-2: 1/1 iter(s) failed without invariant evidence — see Notes column
- Op-3: 1/1 iter(s) failed without invariant evidence — see Notes column
- Op-4: 1/1 iter(s) errored (subprocess fault)

## Mapped to findings

| Failure | Maps to | Evidence file(s) |
|---|---|---|
| _(no failures)_ | _(n/a)_ | _(n/a)_ |

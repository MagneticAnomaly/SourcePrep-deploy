# Phase 145 UAT Scorecard — 2026-07-22 (revalidation)

> **CONTEXT.** First harness run since the 2026-06-23 post-#17-fix smoke — a
> single Op-2 (incremental) iteration against PowerMateReborn, run as the
> "does the harness still work" probe before shipping the T5 orchestration
> layer. Daemon had been up long-term (NOT restarted — Applivation-Android
> holds a deliberately-paused deep_enrichment run ~9.7 days old; see the
> uat-orchestrator skill's safety rules).
>
> **INTERPRETATION.**
> - Harness plumbing: fully working. Full incremental pipeline (catalogue →
>   atlas) completed in 65s on PMR; all 4 shipped invariants held; scorecard,
>   manifest, screenshots, and #17-fix Notes evidence all produced correctly.
> - Product signal: **3 real desyncs in one 65-second run** — the §2r/§2b
>   family is still live post-I3-fix, in desync-subtype territory the shipped
>   invariants deliberately do not cover:
>   1. `group_reasoning` — `api_complete_dom_still_running` (stale spinner
>      after API completion; §2r shape).
>   2. `clustering` — `api_running_dom_not_running` (row failed to advance
>      to running; §2r shape).
>   3. `atlas` — `dom_claims_running_while_api_idle` at DOM progress 67%
>      (the classic 96D/§2b symptom, **cross-group**: a finalize-group row
>      claiming activity — adjacent to the §9.3 #18 cross-group known gap).
> - Evidence: `tests/eval/ui_smoke/run_20260722T065440Z/incremental/`
>   (`events.jsonl`, `009_desync_group_reasoning_api_complete_dom_still_running.png`
>   et al).


**Project:** `6955793f-d824-4e1c-8cb6-417a08bd6669`
**Iterations per op:** 1
**Operations:** Op-2
**Session id:** 2026-07-22T065422Z
**Out root:** `tests/eval/ui_smoke`
**Iterations recorded:** 1/1 (complete)

**Status legend:** `pass` = all invariants held; `FAIL` = at least one invariant fired OR smoke exited non-zero; `ERR` = subprocess crash / missing summary; `skip` = daemon /health unreachable.

## Results

| Op | Iter | Status | I1 | I2 | I3 | I13 | Notes |
|---|---:|:--:|:--:|:--:|:--:|:--:|---|
| Op-2 Incremental Update | 1 | FAIL | ✓ | ✓ | ✓ | ✓ | desync×3 'api_complete_dom_still_running'+'api_running_dom_not_running'+'dom_claims_running_while_api_idle' · cancel-quiesce: already idle (nothing to cancel) |

## Rolled-up trends

- Op-2: 1/1 iter(s) failed without invariant evidence — see Notes column

## Mapped to findings

| Failure | Maps to | Evidence file(s) |
|---|---|---|
| _(no failures)_ | _(n/a)_ | _(n/a)_ |

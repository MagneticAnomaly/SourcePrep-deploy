# Phase 119 — Swarm Orchestration Audit

Date: 2026-04-26
Author: Phase 119 follow-up
Scope: verify whether the dashboard's "Swarming" badge is truthful, and
whether the codebase's "swarm" actually runs the three-phase
(coordinator → fan-out → synthesis) shape it claims.

## TL;DR

1. **The pre-fix `is_swarm` flag is NOT runtime-authoritative.** It was
   computed from a static capability check
   (`is_swarm_active_for_stage(stage, provider, model)`) gated only by
   `live_workers >= 2`. With 2+ concurrent independent calls to a
   "swarm-capable" model on a "swarm-capable" stage, the badge fires
   even if the orchestrator never opened a swarm window. The runtime
   evidence — `pipeline_scheduler.get_swarm_window()` — was not consulted.

2. **Two of the five "swarm-capable" stages are NOT real swarms.**

   | Stage | Opens swarm window? | Runs 3-phase orchestrator? | Pre-fix badge fires? | Verdict |
   |---|---|---|---|---|
   | `group_reasoning` | YES — via orchestrator.py:2180 | YES — `SwarmOrchestrator.execute()` runs `_coordinate` → `_fan_out` → `_synthesize` (group_reasoning.py:542) | YES | **truthful** |
   | `clustering` | YES — same code path | YES — `SwarmOrchestrator.execute()` (cluster.py:1406) | YES | **truthful** |
   | `atlas` | YES — same code path | YES — `SwarmOrchestrator.execute()` (atlas/generator.py:1014) | YES | **truthful** |
   | `concepts` | YES — same code path | YES — `SwarmOrchestrator.execute()` (concept_seeder.py:565) | YES | **truthful** |
   | `audit` | YES — same code path | **NO** — `AuditSynthesizer._synthesize_parallel` is a fixed 5-document `ThreadPoolExecutor`. **There is no coordinator and no synthesizer phase.** Comment in synthesizer.py:50 even calls it "parallel-fixed-fan-out". | YES | **misleading — actually parallel** |

3. **Telemetry currently has no per-call `swarm_role` label.** Active
   requests (`token_telemetry.get_active_requests`) only carry
   `project_id`, `task_id`, `model`, `provider`, `model_slot`. There is
   no way to distinguish a coordinator call from a worker call from a
   synthesizer call. The dashboard cannot show the three-phase split
   because the data isn't there.

## Where `open_swarm_window` actually fires

```
src/prep/services/pipeline/orchestrator.py:2180
    pipeline_scheduler.open_swarm_window(run.project_id, stage, node_id)
```

Guard: `stage.value in SWARM_CAPABLE_STAGES` AND
`is_swarm_active_for_stage(stage, provider, model)` returns true. The
orchestrator opens the window for **all five** stages in
`SWARM_CAPABLE_STAGES`, including audit, even though audit doesn't run
a true swarm.

`SWARM_CAPABLE_STAGES = frozenset({"group_reasoning", "clustering", "atlas", "concepts", "audit"})`

## What "real" 3-phase swarm looks like

`SwarmOrchestrator.execute()` (swarm_orchestrator.py:513) runs:

1. `_coordinate()` — single LLM call to `coordinator_llm` with
   `COORDINATOR_SYSTEM` prompt. Decomposes work into `WorkerAssignment`
   list.
2. `_fan_out()` — `ThreadPoolExecutor` running `worker_fn` per item
   against `worker_llm`.
3. `_synthesize()` — single LLM call to `coordinator_llm` with
   `SYNTHESIS_SYSTEM` prompt. Aggregates worker outputs.

This is what runs for `group_reasoning`, `clustering`, `atlas`, and
`concepts`.

For `audit`, `synthesize_all` jumps straight into a parallel fan-out of
5 fixed document generators — no LLM coordinator, no LLM synthesizer.
This is parallel, not swarm.

## How telemetry tags calls today

`LLMClient._track_active("start")` calls
`telemetry.track_active_request(model, provider, model_slot)` (no role).
`set_telemetry_context(project_id, task_id)` is a `ContextVar` so worker
threads in a `ThreadPoolExecutor` may not inherit it on Python 3.11
(the file has a `_fallback_ctx` dance to compensate).

There is **no** field today that distinguishes coordinator-phase calls
from worker-phase calls from synthesis-phase calls.

## Smoking-gun check

At the time of writing, `/compute/scheduler` reports:

```json
{ "swarm_window": null, "swarm_cooldown_until": null }
```

with no running tasks. Without a live swarm sweep happening to
observe, we cannot prove the orchestrator opens windows in production.
However, the code path at orchestrator.py:2180 is unambiguous: when a
swarm-eligible stage starts AND `is_swarm_active_for_stage` returns
True, `open_swarm_window` IS invoked. Tests
(`test_pipeline_scheduler.py::TestSwarmWindow`) verify the lifecycle.

The plausible failure mode is `is_swarm_active_for_stage` returning
False because of the low-resource guardrail: it returns False when
`pipeline_scheduler._get_max_dynamic_capacity() <= 3`. On the user's
4-thread machine this can suppress swarm window opening entirely while
still letting `concurrent_workers >= 2` calls fly via standard fan-out
paths — exactly the scenario the user feared ("3 concurrent
independent LLM calls" labeled as "Swarming").

## Fixes applied (Tasks 2/3 of this iteration)

1. **`is_swarm` made runtime-authoritative.** `llm.py` and `queue.py`
   now require `pipeline_scheduler.get_swarm_window()` to return a
   window matching the running task's `project_id` AND `stage` AND
   `live_workers >= 2`. The static `is_swarm_active_for_stage(...)` is
   no longer used to drive the live badge — it is reserved for
   "this stage WILL swarm next" predictions.

2. **Telemetry tagged with `swarm_role`.** `LLMClient` accepts a
   `swarm_role` ContextVar (`coordinator` | `worker` | `synthesizer`).
   The `SwarmOrchestrator` wraps each phase in
   `set_swarm_role(...)`, propagating to child threads via the same
   fallback pattern used for telemetry context. Each running task
   surfaces a `swarm_phases` breakdown in `/llm/slots/status`.

3. **UI** renders the three-phase breakdown when a swarm is active.
   When `swarm_phases` is `None` (audit, or non-swarm stages, or
   single-call states), nothing is rendered — no fabricated
   coordinator row.

## Honest verdict on `audit`

`audit` is **structurally not a swarm**. We keep the orchestrator
opening a "swarm window" on it (it serializes the budget so other
projects don't trample) but the `is_swarm` badge never fires for audit
unless `swarm_phases` reports actual coordinator/synthesizer roles —
which it won't for audit because there are none. Rendering "Swarming"
on audit was the misleading pre-fix behavior; rendering "concurrent"
or "parallel" is more truthful.

If we want audit to be a real swarm later, the synthesizer needs an
LLM coordinator decomposition (e.g. "which findings cluster together,
which need their own report?") and an LLM synthesizer pass over the
5 generated documents. Today it's just five hard-coded generators in a
threadpool.

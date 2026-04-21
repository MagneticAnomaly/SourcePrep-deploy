# Group State Machine

Defined in `src/prep/services/pipeline/state_machine.py:94-200` (`_TRANSITIONS` dict).

## States (10)

| State | Meaning | On-disk effect |
|---|---|---|
| `idle` | Not scheduled | none |
| `queued` | Waiting for compute capacity | journal row inserted |
| `running` | Stage executing | stage manifest in progress; worker slots held |
| `pausing` | Pause requested, draining | checkpoint being written |
| `paused` | Stopped cleanly, resumable | checkpoint in `.checkpoints/`; journal status = `paused` |
| `cancelling` | Cancel requested, draining | checkpoint being removed |
| `cancelled` | Stopped, not resumable | journal status = `cancelled`; no checkpoint |
| `recovering` | Crash detected on daemon start | selfheal running |
| `completed` | All stages done | all manifests written |
| `failed` | Stage errored | journal status = `failed`; error recorded |

## Notable transitions

| From | To | Trigger | Notes |
|---|---|---|---|
| `idle` | `queued` | `run_all()` / `resume()` | always via scheduler |
| `queued` | `running` | capacity acquired | |
| `queued` | `stage_completed` | capacity acquired between queue and start | rare, valid |
| `running` | `pausing` | `POST /pipeline/pause` | |
| `pausing` | `paused` | checkpoint flush complete | |
| `paused` | `running` | `POST /pipeline/resume` | re-reads LLM config |
| `paused` | `cancelling` | pause + cancel chain | valid — not a bug |
| `cancelling` | `cancelled` | drain complete | |
| `running` | `recovering` | daemon restart detected mid-stage | on startup only |
| `recovering` | `running` | selfheal rehydrates state | |
| any | `failed` | stage exception | recovery depends on stage |

## Invariants under test

1. **Disk reflects state.** If state is `paused`, a checkpoint file must exist. If `completed`, all manifests must exist. If `cancelled`, no checkpoint.
2. **Journal and state machine agree.** `pipeline_runs.status` column matches in-memory group state. Hydration on restart depends on this.
3. **Baseline preserved.** `progress_baseline` in manifest (F-66) survives restart. After restart, `/pipeline/status` shows `progress_current >= progress_baseline`, not reset to 0.
4. **Resets are durable.** After `DELETE /enrichment/full-reset`, `.reset_barrier` file blocks selfheal from resurrecting stages 6–15 until next finalize completion.

## Pause + resume re-reads config

On resume, `pipeline_orchestrator.resume_paused()` re-reads LLM config. This means you can **swap models between pause and resume** — useful for testing model-failover scenarios. The resumed run uses the new model from the next stage onward.

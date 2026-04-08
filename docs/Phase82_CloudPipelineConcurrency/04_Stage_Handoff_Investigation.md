# Stage Handoff Race Condition — Investigation

> Date: 2026-04-08
> Triggered by: Haley pipeline stuck at deepening → deep_knowledge transition overnight
> Related: Phase 72 (scheduler), Phase 75 (ghost guard), Phase 76 (state machine)

## Symptom

Pipeline completed deepening (10 iterations, logs show "Converged: budget_exhausted") but never advanced to deep_knowledge. UI showed "Error" state. Restarting the daemon didn't help — the pipeline was in a zombie state.

## Root Cause: Non-Atomic Stage Handoff

The stage transition in `_on_build_transition()` (orchestrator.py:1534-1815) executes these steps **sequentially, without holding a lock across them**:

```
1. State machine: STAGE_COMPLETED (line 1574)
   → current_stage_index incremented
   → state machine says "RUNNING" on next stage

2. scheduler.release() (line 1594)
   → project removed from slot.active_stages
   → scheduler says "no lock held"
   → may dequeue next waiting pipeline

3. ~200 lines of bookkeeping (lines 1596-1658)
   → manifest writing
   → atlas/rules generation
   → integrity checks
   → journal writes
   → all wrapped in try/except

4. _advance_pipeline() (line 1799)
   → scheduler.acquire() for next stage
   → launch next build worker
```

**The race window is between steps 2 and 4.** During this window:
- No scheduler lock is held for the project
- No build thread is alive (`is_any_active()` → False)
- The state machine says RUNNING (step 1 already happened)
- The ghost guard fires (triggered by UI polling `/system/pipeline-queue`)

## Ghost Guard as Symptom, Not Cause

The ghost guard (Phase 75) was designed as a safety net for crashed workers. It cross-checks `scheduler.active_stages` against `build_orchestrator.is_any_active()`. When both are False, it purges the lock.

But the race window creates a legitimate state where both are False — the worker completed and the scheduler released, but the next stage hasn't started yet. The ghost guard can't distinguish "worker crashed" from "between stages."

The band-aid fix (checking the pipeline state machine) helps but doesn't address the fundamental issue: the scheduler and state machine disagree about pipeline status for hundreds of milliseconds during every stage transition.

## The Deeper Problem

The pipeline has **three independent sources of truth** that go out of sync during transitions:

| Source | Says | When |
|--------|------|------|
| **State Machine** | "RUNNING stage N+1" | After line 1574 |
| **Scheduler** | "no lock held" | After line 1594, before line 1420 |
| **Build Orchestrator** | "no active threads" | After worker thread exits |

All three need to agree, but they're updated at different times with different locking scopes. The Phase 72 refactor moved I/O outside the lock (correct for performance), but didn't address the resulting consistency gap.

## Frontend Impact

The frontend polls `/system/pipeline-queue` which calls `_build_queue_item()` → reads from both the state machine and the scheduler. When they disagree:
- State machine: `phase=running`, `current_stage=deepening`
- Scheduler: `concurrent_workers=1` (default, no lock found)
- Ghost guard: purges lock → state machine never advances → zombie

The Graph Enrichment panel polls `/projects/{id}/deepening/status` which reads from the build slot. Build slot progress is cleared when the worker finishes (build_orchestrator.py:207-210), so the frontend sees `iteration=0, max_iterations=undefined` → shows "Iteration 0/?".

## Proposed Fix: Lock-Then-Advance

Instead of release-bookkeeping-acquire, the stage transition should:

1. **Keep the scheduler lock through the transition** — don't release until the next stage has acquired
2. Release the OLD stage's lock only after the NEW stage's lock is acquired (or the pipeline completes)
3. Bookkeeping runs with the lock held (it's fast — manifest writes and journal entries)

Alternatively, use a "transition lock" on the pipeline run that prevents the ghost guard from purging during transitions:

```python
# In PipelineGroupStateMachine:
transitioning: bool = False  # Set True during stage handoff

# In ghost guard:
if pipeline_orch.is_transitioning(project_id):
    continue  # Skip — in handoff window
```

## Secondary Fix: Frontend Resilience

The frontend should not show "Iteration 0/?" when the stage is complete. The `computeDeepeningState()` function should check the manifest (settled_ratio) before checking build slot progress. If the manifest shows convergence, show complete — don't fall back to build slot iteration counts.

## Files Involved

| File | Role | Issue |
|------|------|-------|
| `orchestrator.py:1594` | Releases lock before advance | Race window opens |
| `orchestrator.py:1799` | Advances pipeline after bookkeeping | Too late |
| `ghost_guard.py:66` | Purges lock during window | Symptom, not cause |
| `scheduler.py:release()` | Removes project from active_stages | Non-atomic with advance |
| `build_orchestrator.py:207-210` | Clears progress on completion | Frontend sees stale data |
| `enrichment.py:567-622` | Returns deepening status | No fallback to manifest |
| `GraphEnrichmentPipeline.tsx:434-455` | Renders deepening state | Trusts stale build slot |

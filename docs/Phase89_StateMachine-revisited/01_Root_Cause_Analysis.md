# Phase 89: Pipeline State Machine — Root Cause Analysis

> Date: 2026-04-08
> Triggered by: Haley pipeline stuck at deepening → deep_knowledge overnight
> Prior art: Phase 72 (pipeline refactor), Phase 75 (ghost guard), Phase 76 (state machine)

## The Problem

The pipeline reliably stalls between stages. A worker thread completes its stage, logs success, but the pipeline never advances to the next stage. The UI shows "Error" or "0%" on the completed stage. This has happened multiple times across different stages and projects.

## Three Sources of Truth That Disagree

The pipeline's liveness is tracked in three independent systems that go out of sync during every stage transition:

| System | What it tracks | Lock |
|--------|---------------|------|
| **PipelineGroupStateMachine** | Pipeline run state (RUNNING/QUEUED/COMPLETED), current_stage_index | `state_machine._lock` |
| **PipelineScheduler** | Which project holds a compute slot on which node | `scheduler._lock` |
| **BuildOrchestrator** | Whether a worker thread is alive (slot.phase, thread.is_alive) | `build_orchestrator._lock` |

Each has its own lock. There is no coordinating lock across all three. During stage transitions, they update sequentially — creating windows where they disagree.

## The Exact Timeline of a Stage Handoff

When a worker thread completes (e.g., deepening finishes):

```
T0: Worker function returns
    BuildOrchestrator._lock: slot.phase = COMPLETED
    BuildOrchestrator._lock released

T1: _notify() fires listener callback (still in worker thread)
    → orchestrator._on_build_transition() called

T2: orchestrator._lock acquired (briefly)
    Lookup matching_run + stage
    orchestrator._lock released

T3: State machine transition: STAGE_COMPLETED
    state_machine._lock: current_stage_index++ (state stays RUNNING)
    state_machine._lock released

T4: scheduler.release() — THE CRITICAL MOMENT
    scheduler._lock: active_stages.pop(project_id)
    scheduler._lock: dequeue next waiting pipeline (if any)
    scheduler._lock released
    → Project has NO scheduler lock
    → State machine says RUNNING
    → BuildOrchestrator says no active threads (slot.phase = COMPLETED)

T5-T8: ~200 lines of bookkeeping (OUTSIDE any lock)
    - Manifest writing
    - Journal entries
    - Atlas/rules generation
    - Integrity checks
    - Write guard checks
    All wrapped in try/except Exception (failures are swallowed)

T9: _resume_queued_pipeline() (if another pipeline was dequeued at T4)
    → Transitions the OTHER pipeline from QUEUED → RUNNING
    → Calls _advance_pipeline() on the OTHER pipeline
    → The other pipeline may acquire the slot we just released

T10: queue_changed event emitted
    → UI polls /system/pipeline-queue
    → Ghost guard fires: purge_ghost_locks()
    → Sees: no scheduler lock + no active threads → "ghost lock" → purges

T11: _advance_pipeline(matching_run) — THE ORIGINAL PIPELINE
    → scheduler.acquire() for next stage
    → May fail if slot was taken by resumed pipeline at T9
    → May fail if ghost guard purged something at T10
    → If fails: pipeline enters QUEUED state (may never be dequeued)
```

**The race window is T4 → T11.** During this window, the pipeline has no scheduler lock, no active build thread, but the state machine says RUNNING. Any observer (ghost guard, UI polling, another pipeline) can interfere.

## Why This Causes the Specific Failure

In the Haley deepening case:

1. Deepening worker completed at 03:50:04 (T0)
2. `scheduler.release()` freed the slot at ~03:50:04 (T4)
3. UI polled at 03:50:09, triggering ghost guard (T10)
4. Ghost guard saw: no active threads + no scheduler lock → purged
5. `_advance_pipeline()` never ran (or ran and found no slot available)
6. Pipeline stuck in RUNNING state with current_stage=deepening, but:
   - No scheduler lock
   - No build thread
   - State machine says RUNNING but nothing is happening

## The Architectural Mistake

Phase 72 moved all I/O outside the orchestrator lock to prevent API timeouts. This was correct for performance. But it created a fundamental invariant violation:

**The pipeline promises "if state = RUNNING, then either a build thread is active or a scheduler slot is held." But between `scheduler.release()` and `_advance_pipeline()`, neither is true.**

The ghost guard (Phase 75) was added as a safety net for crashed workers. But it can't distinguish "worker crashed" from "between stages" — both look identical from the outside:

```
                    | Crashed Worker | Between Stages |
--------------------|----------------|----------------|
scheduler lock      | held (ghost)   | NOT held       |
active threads      | none           | none           |
state machine       | RUNNING        | RUNNING        |
```

Wait — actually in the "between stages" case, the scheduler lock is NOT held (it was released at T4). So the ghost guard's check is actually: "scheduler lock held + no threads = ghost." The issue isn't the ghost guard purging a lock — by T4, the lock is already released. The real issue is that `_advance_pipeline()` at T11 calls `scheduler.acquire()` which may FAIL because:

1. **Single-project case**: The slot was released at T4 and the node has capacity, so `acquire()` should succeed. But the ghost guard emits `queue_changed` which triggers UI re-polling which triggers ANOTHER ghost guard run... This is a side-effect cascade, not a direct lock conflict.

2. **Multi-project case**: Another project was dequeued at T4 and acquired the slot at T9, before our `_advance_pipeline()` runs at T11. Our pipeline gets re-enqueued but may never be dequeued.

3. **Exception during bookkeeping**: If any of the ~200 lines of bookkeeping (T5-T8) throw an exception, it's caught by the broad `except Exception` at line 1640. The code logs "pipeline will still advance" and continues to T11. But if the exception corrupted state, `_advance_pipeline()` may behave unexpectedly.

## Root Causes (Priority Order)

### 1. Non-Atomic Release-Acquire

`scheduler.release()` and `scheduler.acquire()` are separated by ~200 lines of code and ~5+ seconds of I/O. There is no mechanism to "hold the spot" for the next stage while doing bookkeeping.

### 2. No Transition State

The state machine has no TRANSITIONING state. It goes RUNNING → (STAGE_COMPLETED event) → RUNNING. External observers can't tell if the pipeline is actively running a stage or between stages.

### 3. Deferred Resume Race

When `scheduler.release()` dequeues a waiting pipeline, that pipeline's `_advance_pipeline()` runs BEFORE the original pipeline's `_advance_pipeline()`. On a single-slot node, the dequeued pipeline takes the slot and the original pipeline gets re-enqueued.

### 4. Ghost Guard Over-Sensitivity

The ghost guard fires on EVERY queue read (UI polls every 3 seconds). During the T4-T11 window, it may fire multiple times. The Phase 82 patch checks the state machine, but the state machine says RUNNING (correctly) — so the patch works for the ghost guard case. But it doesn't fix the underlying non-atomic handoff.

### 5. Frontend Polling vs SSE Inconsistency

The frontend uses both SSE (real-time) and polling (3-second intervals) for pipeline state. When the backend state changes rapidly during a transition, the frontend can see inconsistent snapshots — e.g., "deepening running" from one endpoint and "no active workers" from another.

## What Would Fix This

See `02_Design_Proposals.md` for proposed solutions.

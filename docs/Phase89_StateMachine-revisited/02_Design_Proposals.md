# Phase 89: Design Proposals — Atomic Stage Handoff

> Date: 2026-04-08
> Prereq: 01_Root_Cause_Analysis.md

## Approach A (Recommended): Release-After-Advance

**Core idea**: Don't release the old stage's scheduler lock until the new stage's lock is acquired. The pipeline always holds at least one lock during transitions.

### How It Works

```python
# In _on_build_transition(), replace the current flow:

# CURRENT (broken):
#   1. transition(STAGE_COMPLETED)
#   2. scheduler.release(old_stage)     ← lock gone
#   3. ~200 lines of bookkeeping        ← vulnerable window
#   4. _advance_pipeline()              ← acquire new lock (may fail)

# PROPOSED:
#   1. transition(STAGE_COMPLETED)
#   2. bookkeeping (manifest, journal, etc.)
#   3. _advance_pipeline()              ← acquire new lock FIRST
#   4. scheduler.release(old_stage)     ← release old lock AFTER
```

### Implementation

Add a new method `_advance_and_release()` that combines steps 3-4 atomically:

```python
def _advance_and_release(
    self, run, completed_stage, release_node_id
):
    """Advance to next stage then release the old stage's slot.
    
    Ensures the pipeline always holds at least one scheduler lock
    during transitions. The old lock is released only after the
    new stage has acquired its own lock (or the pipeline completes).
    """
    # Try to start the next stage
    self._advance_pipeline(run)
    
    # Now release the old stage's lock
    deferred_resume = pipeline_scheduler.release(
        run.project_id, completed_stage, release_node_id,
    )
    
    # Resume any queued pipeline that was waiting for this slot
    if deferred_resume:
        self._resume_queued_pipeline(
            deferred_resume.project_id, deferred_resume.stage,
        )
```

**Edge case: _advance_pipeline() enqueues the pipeline** (node is full for the next stage's model). In this case, the old lock is still released after — the pipeline goes from "running old stage" to "queued for new stage" without a gap.

**Edge case: Pipeline completes** (all stages done). `_advance_pipeline()` transitions to COMPLETED, then the old lock is released. No gap.

**Edge case: Next stage uses a different node** (e.g., embedding → LLM). The old lock is on one node, the new lock is on another. Both can be held simultaneously. Release the old after acquiring the new.

### Impact

- Ghost guard never sees a "no lock, no thread" state during transitions
- Dequeued pipelines don't race for the same slot
- The bookkeeping runs BEFORE the release, so failures don't orphan the pipeline
- The `_weighted_share()` budget calculation temporarily sees one extra project on the node (the completing project still holds its old lock). This is conservative — it gives slightly less budget to other projects for a few hundred milliseconds.

### Risk: Deadlock?

Could holding two locks (old + new) deadlock? No:
- The scheduler lock is acquired/released inside `scheduler.acquire()` and `scheduler.release()` — it's not held across the entire transition
- The orchestrator lock is only held during the initial lookup (lines 1555-1567)
- The state machine lock is only held during transitions
- No two locks are nested (Phase 72 specifically designed this)

### Files Changed

| File | Change |
|------|--------|
| `orchestrator.py:1580-1815` | Reorder: bookkeeping → advance → release (was: release → bookkeeping → advance) |
| `ghost_guard.py` | Can simplify back to just `is_any_active()` check — the transition window no longer exists |

---

## Approach B: Transition Lock

**Core idea**: Add a `transitioning` flag to the state machine. Ghost guard and external observers check this flag.

```python
# In PipelineGroupStateMachine:
transitioning: bool = False

# In _on_build_transition:
matching_run.transitioning = True
try:
    scheduler.release(...)
    bookkeeping...
    _advance_pipeline(...)
finally:
    matching_run.transitioning = False

# In ghost_guard:
if pipeline_orch.is_transitioning(project_id):
    continue  # Skip — legitimate transition window
```

### Pros
- Minimal code change
- Explicit about what's happening
- Other observers can also check the flag

### Cons
- Doesn't fix the underlying non-atomicity — just hides it from the ghost guard
- The deferred resume race still exists
- If the transition crashes (exception in bookkeeping), `transitioning` stays True forever unless there's a finally block with timeout
- Adds yet another source of truth to check

**Not recommended** — treats the symptom, not the disease.

---

## Approach C: Scheduler "Reserve" Mechanism

**Core idea**: Instead of release-then-acquire, use `scheduler.transition(old_stage, new_stage)` that atomically swaps the lock.

```python
def transition_stage(
    self, project_id, old_stage, new_stage, old_node, new_node,
) -> Optional[QueueEntry]:
    """Atomically transition from one stage to another.
    
    Releases the old slot and acquires the new one in a single
    locked operation. If the new slot can't be acquired, the
    project is enqueued for the new stage but the old slot is
    still released (no deadlock).
    """
    with self._lock:
        old_slot = self._get_slot(old_node or self._default_node_id)
        old_slot.release(project_id)
        
        new_resolved = self._resolve_node_for_stage(new_stage, new_node)
        new_slot = self._get_slot(new_resolved)
        
        if new_slot.acquire(project_id, new_stage.value):
            # Dequeue from old node's queue
            queue = self._get_queue(old_node)
            if queue and old_slot.has_capacity:
                return queue.popleft()
            return None
        else:
            # Can't acquire new — enqueue for new stage
            self._get_queue(new_resolved).append(
                QueueEntry(project_id, new_stage)
            )
            # Still release old slot and dequeue
            queue = self._get_queue(old_node)
            if queue and old_slot.has_capacity:
                return queue.popleft()
            return None
```

### Pros
- Truly atomic — single lock acquisition covers both release and acquire
- No window for ghost guard or other observers to see inconsistent state
- Clean API for the orchestrator

### Cons
- More complex scheduler API
- The "can't acquire new" case still puts the pipeline in QUEUED state
- Embedding → LLM transitions (different nodes) work but the atomicity within a single `self._lock` only protects the scheduler's own state, not the build orchestrator or state machine

**Viable but more invasive than Approach A.**

---

## Recommendation: Approach A (Release-After-Advance)

It's the simplest fix that eliminates the root cause:
1. Reorder three existing method calls (no new abstractions)
2. The pipeline always holds at least one lock during transitions
3. Ghost guard can be simplified
4. No new state or API changes needed

The key insight: **bookkeeping doesn't need the slot to be released**. Manifest writes, journal entries, and integrity checks don't interact with the scheduler at all. They can run while the old lock is still held.

## Frontend Resilience (Secondary Fix)

Regardless of the backend fix, the frontend should be resilient to transient state inconsistencies:

1. **Deepening status endpoint** (`enrichment.py:567-622`): When `running=False` and `settled_ratio >= 0.5`, return `state: "complete"` even if `iteration` is undefined. Don't let missing build slot progress override manifest data.

2. **Graph Enrichment panel** (`GraphEnrichmentPipeline.tsx:434-455`): The `computeDeepeningState()` function should check manifest-based completion before build slot progress. Stale build slot data should never override a completed manifest.

3. **SSE completion event**: Ensure the `pipeline_status` SSE event fires AFTER the state machine transition AND the manifest write, not before. The frontend hydration on SSE receipt should see the final state.

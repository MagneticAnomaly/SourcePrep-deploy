# Phase 89: Implementation Strategy — Atomic Pipeline Transitions

> Date: 2026-04-08
> Prereqs: 01_Root_Cause_Analysis.md, 02_Design_Proposals.md

## Scope

This is not just a stage handoff fix — the audit uncovered **four categories of scheduler lock bugs** that share the same root cause: the scheduler and state machine don't share a coordination protocol. This strategy addresses all four.

## Bug Inventory

### Category 1: Non-Atomic Stage Handoff (Primary)
**Where**: `orchestrator.py:1594` (release) → `orchestrator.py:1799` (_advance_pipeline)
**Impact**: Pipeline stalls between stages. Ghost guard fires during transition window.
**Frequency**: Every stage transition has a ~5s vulnerability window.

### Category 2: Cancel Doesn't Release Scheduler Lock
**Where**: `orchestrator.py:1816-1846` (`_cancel_group`)
**Impact**: Cancelled pipeline holds scheduler slot forever, blocking other projects.
**Frequency**: Every cancel + every deactivation.

### Category 3: Pause Doesn't Release Scheduler Lock
**Where**: `orchestrator.py:1848-1921` (`_pause_group`)
**Impact**: Paused pipeline holds scheduler slot indefinitely, starving other projects.
**Frequency**: Every pause + every model swap.

### Category 4: clear_project Doesn't Release Scheduler Lock
**Where**: `orchestrator.py:973-981` (`clear_project`)
**Impact**: Ghost locks left behind when project is deleted/cleared.
**Frequency**: Every project clear.

### Shared Root Cause
The orchestrator manages the **semantic** lifecycle (start, pause, cancel, complete) but doesn't always manage the corresponding **resource** lifecycle (scheduler lock acquire/release). The scheduler and state machine are out of sync because there's no contract that says "when the state machine leaves RUNNING, the scheduler lock must be released."

---

## Implementation: Five Workstreams

### WS1: Release-After-Advance (Category 1 fix)

**The change**: In `_on_build_transition()` (COMPLETED path), reorder so bookkeeping and advance happen BEFORE releasing the old lock.

**Current order** (orchestrator.py:1572-1799):
```
1. transition(STAGE_COMPLETED)           — SM: stage N+1, state=RUNNING
2. scheduler.release(old_stage)          — SLOT FREED, vulnerable
3. bookkeeping (manifests, journal, etc) — ~200 lines, no lock
4. _resume_queued_pipeline()             — dequeued project runs
5. _advance_pipeline()                   — acquire new slot (may fail)
```

**New order**:
```
1. transition(STAGE_COMPLETED)           — SM: stage N+1, state=RUNNING
2. bookkeeping (manifests, journal, etc) — still holding old slot
3. _advance_pipeline()                   — acquire new slot FIRST
4. scheduler.release(old_stage)          — release old slot AFTER
5. _resume_queued_pipeline()             — dequeued project gets freed slot
```

**Same-node case** (e.g., enrichment→group_reasoning, both on cloud:ep-1):
- Step 3 acquires a second slot on the same node for the same project
- Step 4 releases the first slot
- Net effect: project continuously holds a slot — no gap

**Cross-node case** (e.g., knowledge (embedding) → enrichment (LLM)):
- Step 3 acquires on the new node (LLM)
- Step 4 releases on the old node (embedding)
- Both held briefly simultaneously — no conflict (different nodes)

**Pipeline completion case** (all stages done):
- Step 3 transitions to COMPLETED instead of acquiring
- Step 4 releases the final slot
- Clean completion, no dangling locks

**Edge case: Step 3 fails** (node full for next stage):
- `_advance_pipeline()` enqueues the pipeline (QUEUED state)
- Step 4 still releases the old slot
- Step 5 dequeues and resumes a waiting project (possibly us)
- This is correct behavior — the pipeline gives up its old slot and waits for the new one

**Edge case: Step 2 throws** (bookkeeping exception):
- Currently caught by `except Exception` at line 1640, continues to advance
- With new order, the old slot is still held, so no ghost lock danger
- If advance also fails, fall through to release in a `finally` block

**Implementation pattern**:
```python
# In _on_build_transition, COMPLETED path:
_release_node = getattr(matching_run, '_current_node_id', None)
_release_stage = stage  # The COMPLETED stage (not the next one)

try:
    # Step 2: Bookkeeping (still holding old slot)
    self._post_stage_bookkeeping(matching_run, stage, ...)
    
    # Step 3: Advance to next stage (acquires new slot or completes)
    if matching_run.is_active and not _abort:
        self._advance_pipeline(matching_run)
finally:
    # Step 4: Always release old slot (even if advance/bookkeeping failed)
    _deferred_resume = pipeline_scheduler.release(
        project_id, _release_stage, _release_node,
    )

# Step 5: Resume queued pipeline
if _deferred_resume:
    self._resume_queued_pipeline(...)
```

**Note on `_weighted_share()` during dual-hold**: While the project holds both old and new slots (steps 3-4), `_weighted_share()` counts it as 2 active stages on the node. This is conservative (gives slightly less budget to others) but correct — it only lasts milliseconds.

### WS2: Cancel Releases Lock (Category 2 fix)

**The change**: `_cancel_group()` must release the scheduler lock after cancelling the build worker.

```python
def _cancel_group(self, project_id: str, group: str) -> bool:
    # ... existing lookup and state transition ...
    
    # Cancel the current stage's build
    if current_str:
        bt = STAGE_BUILD_TYPE[StageId(current_str)]
        self._orchestrator.cancel(project_id, bt)
    
    # Complete the CANCELLING → CANCELLED transition
    if run.state == PipelineState.CANCELLING:
        run.transition(Event.STAGE_STOPPED)
    
    # NEW: Release scheduler lock
    if current_str:
        stage = StageId(current_str)
        _release_node = getattr(run, '_current_node_id', None)
        next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
        if next_entry:
            self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)
    
    # journal...
    return True
```

**Consideration**: The `_on_build_transition()` callback will also fire when the build is cancelled (with `new_phase=FAILED`). The FAILED handler at line 1661 already releases the lock (line 1695). So there's a potential double-release. The fix: check if `_cancel_group` is the one releasing (via a flag on the run, or by checking if the lock is still held before releasing).

**Simpler approach**: Let `_on_build_transition()` handle ALL lock releases, including for cancelled builds. The FAILED path already does this. Just ensure the FAILED path fires reliably after cancel. Current code: cancel sets `cancel_token.cancel()` → worker checks between batches → worker raises → slot transitions to FAILED → `_on_build_transition()` fires with FAILED → lock released at line 1695. This already works — but only if the worker cooperatively checks the cancel token. If it doesn't (long LLM call), the cancel timeout at line 1887 fires and the worker is force-paused.

**Recommendation**: Add lock release to `_cancel_group` as a safety net, with a guard to prevent double-release:
```python
# Only release if still held (build transition callback may have already released)
if current_str and pipeline_scheduler.is_held_by(project_id):
    ...release...
```

### WS3: Pause Releases Lock (Category 3 fix)

**The change**: `_pause_group()` should release the scheduler lock after the worker flushes. When resumed, `_advance_pipeline()` re-acquires.

This is the trickiest case because:
- Pause should be resumable (the paused stage re-runs from where it left off)
- If we release the lock on pause, another project can take the slot
- When we resume, we may have to wait in the queue

**Two options**:

**Option A (Recommended): Release on pause, re-acquire on resume**
- Pause releases the lock → other projects can run
- Resume calls `_advance_pipeline()` which calls `scheduler.acquire()` → may get queued
- Fair: a paused pipeline doesn't hog resources
- This is how it should work conceptually

**Option B: Keep lock on pause**
- Current behavior (minus the bug where it's never released if the project is cancelled while paused)
- Starves other projects while paused
- Simpler to implement (no change needed)

**Recommendation**: Option A. A paused pipeline shouldn't hog a compute slot. The resume path already handles the case where `acquire()` fails (pipeline gets queued).

```python
def _pause_group(self, project_id: str, group: str) -> bool:
    # ... existing pause logic ...
    
    # PAUSING → PAUSED transition
    run.transition(Event.STAGE_FLUSHED)
    
    # NEW: Release scheduler lock so other projects can run
    if current_str:
        stage = StageId(current_str)
        _release_node = getattr(run, '_current_node_id', None)
        next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
        if next_entry:
            self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)
    
    # ... emit SSE, journal ...
```

### WS4: clear_project Releases Lock (Category 4 fix)

**The change**: `clear_project()` must cancel any running builds and release scheduler locks before removing state machines.

```python
def clear_project(self, project_id: str) -> None:
    # Cancel any running builds first
    self.cancel_fast_sync(project_id)
    self.cancel_deep_enrichment(project_id)
    # Now safe to remove state machines
    with self._lock:
        keys_to_remove = [k for k in self._runs if k[0] == project_id]
        for k in keys_to_remove:
            del self._runs[k]
```

Since `cancel_*` now releases locks (WS2), this is sufficient.

### WS5: Simplify Ghost Guard

Once WS1-WS4 are done, the ghost guard becomes much simpler. The only remaining case for ghost locks is actual crashes (OOM kill, segfault, etc.) where the callback never fires.

```python
def purge_ghost_locks(...) -> int:
    # Only purge if:
    # 1. Scheduler says lock held
    # 2. BuildOrchestrator says no active threads
    # 3. Pipeline state machine says NOT active (COMPLETED/FAILED/CANCELLED/IDLE)
    # All three must agree before purging.
    
    for project_id in locked_projects:
        if build_orchestrator.is_any_active(project_id):
            continue  # Thread alive — valid
        
        if pipeline_orch is not None:
            ps = pipeline_orch.status(project_id)
            if any(g.get("is_active") for g in [ps.get("fast_sync", {}), ps.get("deep_enrichment", {})] if isinstance(g, dict)):
                continue  # Pipeline active — transition window or legitimate hold
        
        # All three agree: no thread, no active pipeline → ghost lock
        scheduler.clean_locks(project_id)
        purged += 1
```

This is what the Phase 82 patch already does — WS5 just formalizes it as the permanent behavior after WS1-WS4 close the transition window.

---

## Fast Sync → Deep Enrichment Chaining

**Current behavior** (`orchestrator.py:1302-1369`):
When fast_sync completes (all stages done), `_advance_pipeline()` checks if deep enrichment should auto-chain. If yes, it calls `self.run_deep_enrichment()` directly.

**Impact of WS1**: The last fast_sync stage's lock is released AFTER `_advance_pipeline()` completes. Since `_advance_pipeline()` calls `run_deep_enrichment()` which calls `_start_group()` which calls `_advance_pipeline()` for deep enrichment's first stage — the fast_sync lock is released only after deep enrichment's first stage acquires its lock.

**Cross-group lock**: Fast_sync's last stage is `knowledge` (embedding node). Deep enrichment's first stage is `enrichment` (LLM node). These are different nodes, so both can be held simultaneously without conflict.

**No change needed** — the chaining already works correctly with WS1's release-after-advance pattern, because the chain call is inside `_advance_pipeline()`.

---

## Priority/Queue Considerations

**Impact of WS1 on priority**: When using release-after-advance, the original project acquires the next stage's slot BEFORE releasing the old one. This means a priority project waiting in the queue won't get the slot until after the original project advances. Is this fair?

**Yes** — because the alternative (current behavior) is worse: the priority project gets the slot, the original project gets re-queued, and the original project may never get back. The priority project should wait the ~100ms it takes for the advance to complete.

**Impact of WS3 on priority**: When a paused pipeline releases its lock, queued priority projects should jump in. The `scheduler.release()` returns the next dequeued entry, which respects queue order (priority projects are at the front). This is correct.

**Exclusive priority during transition**: If project A is exclusive and project B just completed a stage, project B should advance to its next stage before releasing the old slot. With WS1, B holds the old slot during advance, which means A can't start during this window. This is acceptable — the window is milliseconds.

---

## Implementation Order

```
WS1 (release-after-advance)  ← Fixes the overnight stall bug
 ↓
WS2 (cancel releases lock)   ← Prevents ghost locks on cancel
 ↓
WS3 (pause releases lock)    ← Prevents slot starvation on pause
 ↓
WS4 (clear_project cleanup)  ← Prevents ghost locks on project clear
 ↓
WS5 (simplify ghost guard)   ← Clean up the safety net
```

WS1 is the critical fix. WS2-WS4 are important but not urgent (the ghost guard catches these cases, just noisily). WS5 is cleanup.

---

## Testing Strategy

1. **Unit: Stage handoff atomicity** — Mock scheduler + build orchestrator. Verify that during stage transition, the project always holds at least one scheduler lock.

2. **Unit: Cancel releases lock** — Start a pipeline, cancel mid-stage, verify scheduler lock is released.

3. **Unit: Pause releases lock** — Start a pipeline, pause mid-stage, verify scheduler lock is released. Resume, verify lock re-acquired.

4. **Unit: Ghost guard with active pipeline** — Verify ghost guard skips projects with active state machine.

5. **Integration: Multi-project handoff** — Run two projects on the same node. Verify project A's stage completion doesn't starve project B, and vice versa.

6. **Regression: Fast_sync→deep_enrichment chain** — Verify auto-chain still works with release-after-advance ordering.

---

## Files Changed

| File | Workstream | Change |
|------|-----------|--------|
| `orchestrator.py:1572-1815` | WS1 | Reorder: bookkeeping → advance → release |
| `orchestrator.py:1816-1846` | WS2 | Add lock release after cancel |
| `orchestrator.py:1848-1921` | WS3 | Add lock release after pause |
| `orchestrator.py:973-981` | WS4 | Cancel builds before clearing state |
| `ghost_guard.py` | WS5 | Simplify — all three sources must agree |
| `scheduler.py` | Support | Add `is_held_by(project_id)` helper for double-release guard |
| `tests/test_pipeline_scheduler.py` | Tests | New tests for lock lifecycle |
| `tests/test_ghost_guard.py` | Tests | Update for simplified ghost guard |

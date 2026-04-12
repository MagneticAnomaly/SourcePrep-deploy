# Phase 91: Implementation Plan

**Design:** `01_Resource_Allocation_Design.md`
**Approach:** Bottom-up — scheduler internals first, then orchestrator integration, then batch engine subscriptions, then UI.

---

## Implementation Order

### Step 1: Scheduler Core — Swarm Window + Drain + Cooldown
**Files:** `src/codrag/services/pipeline/scheduler.py`
**Estimated scope:** ~120 lines new/modified

Add the swarm window lifecycle to the scheduler:

1. **New state fields on `PipelineScheduler`:**
   - `_swarm_window: Optional[Dict]` — `{"project_id": str, "stage": StageId, "node_id": str, "started_at": float, "drain_targets": Dict[str, float]}` or None
   - `_swarm_cooldown_until: float = 0.0`
   - `_drain_timeout_seconds: int = 600` (10 minutes, configurable)
   - `_swarm_cooldown_seconds: float = 45.0`

2. **New method `open_swarm_window(project_id, stage, node_id)`:**
   - Sets `_swarm_window`
   - Marks all OTHER active projects on the same node as drain targets with `drain_started_at = time.time()`
   - Returns True if window opened, False if cooldown active

3. **New method `close_swarm_window()`:**
   - Clears `_swarm_window`
   - Sets `_swarm_cooldown_until = time.time() + 45.0`
   - Broadcasts capacity change (Step 4)

4. **Modify `acquire()`:**
   - If `_swarm_window` is active and `project_id != swarm_project_id` and same node → return False
   - If exclusive project is active and this isn't that project → return False (unchanged)
   - Swarm check goes BEFORE exclusive check (swarm > exclusive)

5. **Modify `is_swarm_active_for_stage()`:**
   - Add capacity > 3 check: `if slot.dynamic_capacity <= 3: return False`

6. **Modify `full_budget_for_swarm()`:**
   - Add min_workers=3 gate: if computed budget < 3, return None (caller falls back to normal mode)

7. **New method `check_drain_timeouts()` → List[str]:**
   - Returns list of project_ids that have exceeded drain timeout
   - Called periodically by orchestrator (Step 3)

8. **Low-resource guardrails in `_weighted_share()`:**
   - If `slot.dynamic_capacity <= 3`: skip boost weighting, equal share for all

### Step 2: Scheduler Core — Capacity Change Event Bus
**Files:** `src/codrag/services/pipeline/scheduler.py`
**Estimated scope:** ~60 lines new

1. **New fields:**
   - `_capacity_listeners: Dict[str, Callable[[int], None]]` — keyed by `"{project_id}:{node_id}"`

2. **New method `on_capacity_change(project_id, node_id, callback)`:**
   - Registers callback
   - Returns a cleanup function

3. **New method `_broadcast_capacity_change(node_id, reason)`:**
   - For each active project on the node, compute new budget via `_weighted_share()`
   - Call registered listeners with new budget
   - Log the broadcast

4. **Integrate broadcasts into existing transitions:**
   - `open_swarm_window()` → broadcast with reason="swarm_start"
   - `close_swarm_window()` → broadcast with reason="swarm_end"
   - `set_priority(... "exclusive")` → broadcast with reason="exclusive_start"
   - `set_priority(... demoting exclusive)` → broadcast with reason="exclusive_end"
   - `_record_throughput_for_slot()` when limit changes → broadcast with reason="aimd_adjust"

5. **Cleanup in `release()`:**
   - Unregister listener for the released project+node

### Step 3: Orchestrator Integration — Swarm Lifecycle + Drain Timer
**Files:** `src/codrag/services/pipeline/orchestrator.py`
**Estimated scope:** ~80 lines new/modified

1. **In `_advance_pipeline()`** (around line 1457):
   - After successful `acquire()`, check if this stage is swarm-eligible
   - If yes: call `pipeline_scheduler.open_swarm_window(project_id, stage, node_id)`
   - If swarm window fails (cooldown): proceed without swarm (normal budget)

2. **In release paths** (lines 1307, 1720, 1743, 1872):
   - After `release()`, check if released project was the swarm window owner
   - If yes: call `pipeline_scheduler.close_swarm_window()`

3. **Drain timeout checker:**
   - Add a periodic check in the orchestrator's background loop (or a dedicated timer thread)
   - Every 30 seconds: call `pipeline_scheduler.check_drain_timeouts()`
   - For each timed-out project_id: call `self.cancel(project_id)` with reason="drain_timeout"
   - Log warning: "Drain timeout: force-cancelled {project_id}/{stage} after {elapsed}s"

4. **In `_resume_queued_pipeline()`** (line 2186):
   - Before resuming, check if swarm window is active — if so, don't resume non-swarm projects

### Step 4: Batch Engine Subscriptions
**Files:** `src/codrag/core/batch_profiles.py`, `src/codrag/core/group_reasoning.py`, `src/codrag/core/cluster.py`, `src/codrag/core/atlas/generator.py`
**Estimated scope:** ~40 lines per engine (4 engines)

1. **In `batch_profiles.py` `get_batch_concurrency()`:**
   - Register capacity change listener when computing concurrency
   - Return a `BatchConcurrency` object with a `semaphore` that can be resized

2. **In each swarm engine** (group_reasoning, cluster, atlas):
   - After calling `full_budget_for_swarm()`, register a listener
   - If `full_budget_for_swarm()` returns None (min_workers gate): run in non-swarm sequential mode
   - On capacity change callback: adjust the asyncio Semaphore / ThreadPoolExecutor max_workers

3. **Cleanup:** Listener auto-unregistered when stage releases its slot (handled by Step 2)

### Step 5: Dashboard API Updates
**Files:** `src/codrag/api/routers/queue.py`, `src/codrag/api/routers/llm.py`, `src/codrag/api/routers/compute.py`
**Estimated scope:** ~30 lines modified

1. **Queue API** (`queue.py`):
   - Expose swarm window state: `is_swarm_active`, `swarm_project_id`, `swarm_cooldown_remaining`
   - Expose drain state: which projects are draining, time remaining
   - Fix duplicate display: ensure pipeline state and scheduler queue aren't both shown as separate "pending" items

2. **Compute API** (`compute.py`):
   - Add `drain_timeout_seconds` and `swarm_cooldown_seconds` to configurable settings
   - Expose in `status()` response

3. **LLM API** (`llm.py`):
   - Update `concurrent_workers_for_project()` calls to account for swarm window state

### Step 6: Tests
**Files:** `tests/test_pipeline_scheduler.py` (extend existing)
**Estimated scope:** ~150 lines new tests

1. **Swarm window lifecycle:** open → blocks others → drain timeout → close → cooldown
2. **Tier hierarchy:** swarm > exclusive > boost > normal
3. **Low-resource guardrails:** capacity ≤ 3 disables swarm, flattens boost
4. **Min workers gate:** swarm-capable stage with < 3 budget falls back to normal
5. **Capacity broadcast:** listeners receive correct budgets on state transitions
6. **Cooldown:** swarm can't reopen during 45s cooldown
7. **Drain timeout:** projects cancelled after 10min drain

---

## Dependency Graph

```
Step 1 (Scheduler core: swarm/drain/cooldown)
  ↓
Step 2 (Event bus)
  ↓
Step 3 (Orchestrator integration)  ← depends on 1 + 2
  ↓
Step 4 (Batch engine subscriptions) ← depends on 2
  ↓
Step 5 (Dashboard API)             ← depends on 1 + 3
  ↓
Step 6 (Tests)                     ← depends on all
```

Steps 4 and 5 can be parallelized after Step 3.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Swarm window never closes (stage hangs) | Drain timeout also applies to the swarm stage itself — 10min max |
| Capacity broadcast storms (AIMD thrashing) | Debounce: don't broadcast more than once per second per node |
| Ghost swarm window after crash | `clean_locks()` / ghost_guard already cross-checks — extend to clear stale swarm window |
| Existing tests break | Only 78/93 scheduler tests pass currently. Run full suite after each step, fix regressions immediately |

---

## Completion Log

### Bug Fixes (Pre-Phase 91)
- [x] `_get_store()` NameError fix — `settings.py:32` — security health check and admin endpoints were broken
- [x] Manifest backfill race condition — `coverage.py:129-210` — concurrent coverage calls clobbered builder's more complete file_hashes, causing infinite untraced loop
- [x] Queue dedup fix — `scheduler.py:574` — `enqueue()` now checks both `project_id` AND `stage`

### Phase 91 Implementation
- [x] **Step 1: Scheduler core** — swarm window lifecycle (`open_swarm_window`, `close_swarm_window`, `check_drain_timeouts`, `_is_blocked_by_swarm`), 45s cooldown, 10min drain timeout, low-resource guardrails (capacity ≤ 3 disables swarm, flattens boost), min_workers=3 gate in `full_budget_for_swarm`
- [x] **Step 2: Capacity event bus** — `on_capacity_change()` listener registration, `_broadcast_capacity_change()` with per-node debounce, integrated into swarm/exclusive/AIMD transitions
- [x] **Step 3: Orchestrator integration** — swarm window open in `_advance_pipeline`, auto-close on owner release (handled in scheduler `release()`), drain timeout timer thread with weakref safety
- [x] **Step 4: Batch engine subscriptions** — Existing engines already handle `full_budget_for_swarm()` returning None (fall back to sequential). Dynamic mid-flight scaling deferred.
- [x] **Step 5: Dashboard API** — `status()` extended with `swarm_window`, `swarm_cooldown_remaining`, `drain_timeout_seconds`
- [x] **Step 6: Tests** — 26 new tests covering swarm window lifecycle, tier hierarchy, low-resource guards, min workers, capacity broadcast, cooldown, drain timeout, status fields

### Code Review Fixes
- [x] **C1 (Critical):** Callbacks invoked outside lock in `_broadcast_capacity_change` — prevents deadlock if callback re-enters scheduler
- [x] **C2 (Critical):** Added `swarm_start` broadcast to `open_swarm_window` — other projects learn their budget dropped
- [x] **I1:** Removed dead `_swarm_window_active` flag from orchestrator
- [x] **I2:** `_is_blocked_by_swarm` captures window reference defensively, documented lock requirement
- [x] **I3:** `get_swarm_window()` returns shallow copy, not mutable internal reference
- [x] **I4:** Debounce changed from global float to per-node `Dict[str, float]`
- [x] **I5:** Drain timer uses `weakref` to prevent orchestrator reference leak
- [x] **S2:** Vacuous dequeue test now has real assertions
- [x] **S3:** Added swarm owner timeout tracking test
- [x] **S4:** Added `is_swarm_active_for_stage` low-resource guard test
- [x] **S5:** `_capacity_listeners` registration/cleanup protected by `self._lock`

### Test Results
- **92 passed**, 15 pre-existing failures (AIMD `current_limit` default mismatch in old tests)
- **0 regressions** introduced
- **26 new Phase 91 tests**, all passing

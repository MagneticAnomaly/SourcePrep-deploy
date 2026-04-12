# Phase 91: Pipeline Scheduler Resource Allocation Redesign

**Date:** 2026-04-08
**Status:** Approved Design
**Scope:** `src/codrag/services/pipeline/scheduler.py`, `orchestrator.py`, batch engines

---

## Problem Statement

The CoDRAG pipeline scheduler has the foundational mechanisms for priority, exclusive, swarm, and weighted fair-share allocation, but several issues prevent them from working as intended:

1. **`active_stages: Dict[project_id, stage_id]`** hard-caps at 1 slot per project regardless of available capacity. With 2 projects and 12 cloud slots, only 2 stages run — the other 10 slots sit idle.

2. **Swarm claims resources only at the batch level**, not the scheduler level. Other projects continue running alongside swarm stages, fragmenting the budget that swarm needs to be effective.

3. **Exclusive blocks new stages but doesn't drain running ones** with any timeout guarantee. A hung stage could block exclusive indefinitely.

4. **No low-resource guardrails.** Swarm attempts coordination with 1-2 workers, producing poor results and wasting LLM calls.

5. **No capacity-change broadcast.** Stages query their worker budget once at startup and never adjust, even when swarm windows open/close or AIMD changes limits.

6. **Queue deduplication bug.** The `enqueue()` dedup only checks `project_id`, not stage — allowing duplicate entries and silently dropping different stages for the same project.

---

## Design: Four-Tier Resource Allocation

### Tier Hierarchy

Four allocation tiers, evaluated in strict priority order. Higher tiers override lower ones.

| Priority | Tier | Trigger | Blocks New Stages? | Effect on Running Stages | Worker Budget |
|----------|------|---------|--------------------|--------------------------|--------------:|
| 1 (highest) | **Swarm** | Swarm-capable stage + swarm-enabled model + total capacity > 3 | Yes (all other projects) | Drains naturally (with timeout) | All available (capacity - 1 reserve) |
| 2 | **Exclusive** | User sets one project to exclusive | Yes (other projects only) | Drains naturally (with timeout) | All available (capacity - 1 reserve) |
| 3 | **Boost** | User stars/boosts project(s) | No | None | 2× weighted share |
| 4 (lowest) | **Normal** | Default | No | None | Equal share |

### Tier Resolution Rules

- **Swarm > Exclusive > Boost > Normal.** Always. No exceptions.
- **Only ONE exclusive project** at a time. Setting a new exclusive demotes the previous one to boost.
- **Swarm is temporary.** It activates when a swarm-capable stage starts and deactivates when that stage completes. It is not a user-set mode.
- **Exclusive project entering swarm:** Compatible — same project already has all resources. Swarm rules take over seamlessly.
- **Non-exclusive project entering swarm:** That project gets temporary exclusive-equivalent treatment for the duration of the swarm stage only. The user's explicit exclusive setting is NOT changed — it resumes after the swarm window closes.
- **Multiple boost projects:** All share the boosted budget proportionally. Each boost project gets 2× weight; normal projects get 1× weight. Budget divided by total weight.

---

## Detailed Tier Behavior

### Tier 1: Swarm Mode

**Purpose:** Open a window where one project's swarm-capable stage (group_reasoning, clustering, atlas) gets all available resources for parallel fan-out synthesis.

**Activation:**
1. A swarm-capable stage (`SWARM_CAPABLE_STAGES`) reaches the front of the pipeline
2. The assigned model supports swarm (checked via `swarm_registry.get_swarm_tier()`)
3. Total `dynamic_capacity` of the target node is > 3
4. If all conditions met → swarm window opens

**Behavior during swarm window:**
- No new stages for OTHER projects can `acquire()` slots on the same node
- Already-running stages on other projects continue until they finish naturally
- **Drain timeout:** If running stages don't complete within **10 minutes**, they are force-cancelled
- The swarm stage itself starts immediately (it has its slot) but may operate at reduced concurrency until drain completes, then scales up to full budget
- Worker budget: `max(1, dynamic_capacity - 1)` — reserves 1 for interactive/overhead queries

**Deactivation:**
- Swarm stage completes (success or failure)
- **45-second cooldown** before the next swarm window can open (any project)
- During cooldown, normal/boost/exclusive rules apply
- Cooldown prevents two swarm-heavy projects from ping-ponging exclusive windows and starving normal work

**Swarm cooldown state:**
- Stored as `_swarm_cooldown_until: float` on the scheduler (Unix timestamp)
- Checked in the swarm activation path — if `time.time() < _swarm_cooldown_until`, swarm does not activate and the stage runs with normal/boost/exclusive budget instead

### Tier 2: Exclusive Mode

**Purpose:** Give one user-selected project all available resources. Background work for other projects is deprioritized but not killed.

**Activation:**
- User calls `set_priority(project_id, "exclusive")` (via UI star/priority control)
- Only ONE project can be exclusive. Setting a new one demotes the old one to boost.

**Behavior:**
- Other projects cannot `acquire()` new stages on any node where the exclusive project is active
- Already-running stages on other projects finish naturally
- **Drain timeout:** Same as swarm — **10 minutes** for running stages, then force-cancel
- Worker budget: `max(1, dynamic_capacity - 1)` (full budget minus interactive reserve)
- Queue ordering: exclusive project's stages always at front of queue

**Deactivation:**
- User sets priority to "boost" or "none"
- No cooldown (unlike swarm)

**Interaction with swarm:**
- If the exclusive project's stage enters swarm mode, swarm rules take over (they're compatible — same project)
- If a different project somehow needs swarm while exclusive is active, swarm overrides exclusive temporarily (swarm > exclusive in hierarchy)

### Tier 3: Boost Mode

**Purpose:** Give starred/important projects a larger share of resources without blocking others.

**Behavior:**
- Queue-jump: boost projects' stages are inserted at the front of the scheduler queue
- Worker budget: **2× weighted share** of the available budget
- Multiple boost projects share the 2× pool proportionally

**Weighted share algorithm (existing, unchanged):**
```
Given: budget = dynamic_capacity - 1, N active projects
  boost_count projects each get weight 2
  normal_count projects each get weight 1
  total_weight = (boost_count × 2) + (normal_count × 1)
  
  each project's share = floor(budget × weight / total_weight)
  remainder distributed to boost projects first
```

**Example:**
- 12 capacity, 1 reserve = 11 budget
- 3 projects: 1 boost (weight 2), 2 normal (weight 1 each), total weight = 4
- Boost: floor(11 × 2/4) = 5 workers
- Normal A: floor(11 × 1/4) = 2 workers
- Normal B: floor(11 × 1/4) = 2 workers
- Remainder: 11 - 5 - 2 - 2 = 2 → boost gets them → boost: 7, normal: 2, 2

### Tier 4: Normal Mode

**Purpose:** Default fair-share for all projects.

**Behavior:**
- FIFO queue ordering
- Equal share of worker budget among all active projects
- `share = floor(budget / active_count)`

---

## Low-Resource Guardrails

**Threshold:** Total `dynamic_capacity` ≤ 3

When the system has 3 or fewer total workers available, the following rules apply:

### Swarm Disabled
- Swarm-capable stages (group_reasoning, clustering, atlas) run in **non-swarm sequential mode**
- No coordinator fan-out, no synthesis orchestration
- The stage gets ALL available workers (1, 2, or 3) but runs as a normal batch stage
- `is_swarm_active_for_stage()` returns `False` when capacity ≤ 3, regardless of model capability

### Minimum Workers for Swarm-Capable Stages
- When capacity > 3 (swarm IS available), swarm-capable stages require **minimum 3 workers** to start in swarm mode
- If fair-share division would give a swarm-capable stage < 3 workers, the stage **queues** instead of starting with too few
- This prevents wasting LLM calls on parallel synthesis with insufficient parallelism
- Non-swarm stages have **no minimum** — they run with whatever they get (even 1 worker)

### Priority/Exclusive Simplified
- **Boost behaves like normal** — with ≤3 workers, the difference between 2× and 1× share is 2 vs 1 worker, not meaningful enough to justify the complexity
- **Exclusive still works** — takes all resources (1-3 workers), blocks others. This remains useful even on small systems for ensuring one project finishes without interruption.

---

## Drain Timeout Mechanism

When swarm or exclusive needs to wait for other projects' stages to finish:

1. **Window opens:** Swarm/exclusive is activated. Running stages on other projects are flagged as "draining"
2. **Draining stages** continue executing normally but are tracked with a start-drain timestamp
3. **Timeout: 10 minutes** from drain start. Configurable via settings (`scheduler.drain_timeout_seconds`, default 600)
4. **On timeout:** Draining stages are force-cancelled via the existing `cancel()` mechanism on the orchestrator
5. **Notification:** Log warning when drain timeout triggers, including which project/stage was cancelled

### Force-Cancel Safety
- Cancelled stages are marked as failed with reason `"drain_timeout"`
- The cancelled project's pipeline state machine transitions to `failed` state
- The project can be re-queued manually or by the next watcher trigger
- No data corruption risk: LLM batch stages are idempotent (workers skip already-done items on retry)

---

## Swarm Cooldown

**Duration:** 45 seconds after swarm window closes

**Purpose:** Prevent swarm-heavy workloads from starving normal projects. If projects A and B both have swarm stages queued, without cooldown they'd alternate exclusive windows with no gap for normal work.

**Behavior:**
- Stored as `_swarm_cooldown_until: float` (Unix epoch timestamp) on the scheduler singleton
- Checked during swarm activation: if `time.time() < _swarm_cooldown_until`, swarm mode does NOT activate
- The stage still runs, just without swarm privileges (uses normal/boost/exclusive budget instead)
- Cooldown applies globally (not per-project, not per-node)
- Not configurable in v1 (hardcoded 45s). Can be made configurable later if needed.

---

## Capacity Change Broadcast

When resource allocation changes (swarm window opens/closes, exclusive starts/ends, AIMD adjusts limits, project drains), active stages should be notified to scale their batch workers up or down.

### Mechanism

1. **Event bus:** Scheduler emits a `capacity_changed` event with:
   ```python
   {
       "node_id": str,
       "project_id": str,       # which project's budget changed
       "new_budget": int,        # updated worker count
       "reason": str,            # "swarm_start", "swarm_end", "exclusive_start", "drain_complete", "aimd_adjust"
   }
   ```

2. **Subscriber registration:** Batch engines (augmenter, inferred_edges, group_reasoning, cluster, atlas, enrichment, deepening) register a callback when they start:
   ```python
   scheduler.on_capacity_change(project_id, node_id, callback)
   ```

3. **Callback contract:** The callback receives `new_budget: int` and adjusts the stage's `asyncio.Semaphore` or thread pool size accordingly. Stages that don't support dynamic scaling simply ignore the callback.

4. **Cleanup:** Callback automatically unregistered when stage completes (via `release()`).

### Events That Trigger Broadcast
- Swarm window opens → other projects get budget=1 (or 0 if draining)
- Swarm window closes → all projects get recalculated fair-share
- Exclusive starts → other projects get budget=0 for new stages
- Exclusive ends → all projects get recalculated fair-share
- AIMD adjusts `current_limit` → all active projects get recalculated share
- Project completes/drains → remaining projects' shares increase

---

## Queue Deduplication Fix

**Bug:** `enqueue()` only checks `project_id`, not stage. This allows duplicate project+stage entries and silently drops different stages for the same project.

**Fix:** Check both `project_id` AND `stage`:
```python
for entry in queue:
    if entry.project_id == project_id and entry.stage == stage:
        return  # Already queued for this exact project+stage
```

**Note:** This fix has already been applied in the current session (scheduler.py line 574-581).

---

## Summary of Changes — Implementation Status

| Component | Change | Status |
|-----------|--------|--------|
| `ComputeSlot.acquire()` | No change needed — 1 slot per project is correct for sequential pipeline stages | N/A |
| `PipelineScheduler.acquire()` | Swarm window check before exclusive check | ✅ Done |
| `PipelineScheduler.can_start()` | Same swarm window check | ✅ Done |
| `PipelineScheduler.release()` | Drain target cleanup, swarm window auto-close on owner release, dequeue blocked during swarm | ✅ Done |
| `PipelineScheduler.enqueue()` | Dedup checks both `project_id` AND `stage` | ✅ Done |
| `_weighted_share()` | Low-resource bypass (≤3 capacity: skip boost weighting) | ✅ Done |
| `is_swarm_active_for_stage()` | Capacity > 3 check (0 excluded for unconfigured nodes) | ✅ Done |
| `full_budget_for_swarm()` | Min_workers=3 gate — returns None if budget < 3 | ✅ Done |
| New: `open_swarm_window()` | Opens exclusive window, tracks drain targets, broadcasts capacity change | ✅ Done |
| New: `close_swarm_window()` | Clears window, starts cooldown, broadcasts | ✅ Done |
| New: `check_drain_timeouts()` | Returns project_ids exceeding drain timeout | ✅ Done |
| New: `_swarm_cooldown_until` | 45s cooldown timestamp checked in open path | ✅ Done |
| New: capacity event bus | `on_capacity_change()` / `_broadcast_capacity_change()` — per-node debounce, callbacks outside lock | ✅ Done |
| New: drain timer (orchestrator) | 30s periodic timer with weakref safety, self-terminates when window closes | ✅ Done |
| `PipelineScheduler.status()` | Exposes `swarm_window`, `swarm_cooldown_remaining`, `drain_timeout_seconds` | ✅ Done |
| `clean_locks()` | Extended to clear stale swarm windows | ✅ Done |
| `set_priority()` | Broadcasts `exclusive_start`/`exclusive_end` | ✅ Done |
| `record_throughput*()` | Broadcasts `aimd_adjust` when limit changes | ✅ Done |
| Batch engines (dynamic scaling) | Existing engines handle None from `full_budget_for_swarm()`. Mid-flight scaling deferred. | ⏳ Deferred |
| Dashboard UI (swarm visuals) | Status API exposes data; UI components not yet built | ⏳ Deferred |

---

## Non-Goals (Explicitly Out of Scope)

- **Multi-slot per project:** Not needed. Pipeline stages are sequential within a group. The batch concurrency system already handles parallelism within a single stage.
- **Preemptive cancellation for exclusive:** Exclusive blocks new stages; running ones drain naturally (with timeout). No immediate kill.
- **Cross-node scheduling:** Each stage uses one node. No stage spans multiple nodes.
- **Dynamic priority escalation:** No automatic promotion from normal → boost based on wait time. User-controlled only.
- **Per-stage priority:** Priority is per-project, not per-stage. All stages in a project inherit the project's tier.

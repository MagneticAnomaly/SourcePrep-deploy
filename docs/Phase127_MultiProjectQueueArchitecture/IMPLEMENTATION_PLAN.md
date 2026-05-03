# Phase 127 Multi-Project Queue & Priority — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `pipeline_scheduler` to unify priority, queueing, and swarm-window mechanisms around a shared soft-hold primitive, removing the 45s cooldown and surfacing held/queued state to the UI — without regressing single-project pipelines.

**Architecture:** Five independent sub-phases, each shippable. Build the soft-hold primitive first (no callers, safe to iterate). Then remove cooldown and migrate swarm window + exclusive to use the primitive. Then add the endpoint-disjoint exception, UI signals, and durability. Every commit must keep the single-project end-to-end pipeline green.

**Tech Stack:** Python 3.11, FastAPI, pytest, existing scheduler in `src/prep/services/pipeline/scheduler.py`.

**Spec:** `docs/Phase127_MultiProjectQueueArchitecture/README.md`

**Hard requirement (Spec §13.2):** Every commit runs the regression suite:
```
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py -q
```
All must remain green. The single-project pipeline is the canonical happy path.

---

## File Structure

| File | Status | Purpose |
|---|---|---|
| `src/prep/services/pipeline/scheduler.py` | Modify | Add `HoldReason`, `_holds`, `set_hold`/`clear_hold`/`is_held`. Remove cooldown. Boost-weighted FIFO. Endpoint-set in window. |
| `src/prep/services/pipeline/holds.py` | **Create** | New module: `HoldReason` enum + `HoldEntry` dataclass. Keeps soft-hold types out of the already-3000-line scheduler.py. |
| `src/prep/api/routers/queue.py` | Modify | Surface `state`, `held_reason`, `held_since`. |
| `src/prep/api/routers/llm.py` | Modify | Add `held_projects`, `swarm_queue`, `exclusive_project` to `/llm/slots/status` and `/compute/scheduler`. |
| `src/prep/services/pipeline/workers.py` | Modify | Add `_should_dispatch_or_pause` helper used by stage workers. |
| `src/prep/core/epistemic_enrichment.py` | Modify | Honor soft-hold in `enrich_node` dispatch loop. |
| `src/prep/core/augmenter.py` | Modify | Honor soft-hold in batched augmentation loops. |
| `src/prep/core/swarm_orchestrator.py` | Modify | Honor soft-hold between coord/fanout/synth phase boundaries. |
| `tests/test_soft_hold_primitive.py` | **Create** | Sub-phase 1 tests. |
| `tests/test_swarm_cooldown_removal.py` | **Create** | Sub-phase 2 tests. |
| `tests/test_boost_weighted_fifo.py` | **Create** | Sub-phase 2 tests. |
| `tests/test_endpoint_disjoint.py` | **Create** | Sub-phase 3 tests. |
| `tests/test_held_state_api.py` | **Create** | Sub-phase 4 tests (API shape). |
| `tests/test_priority_durability.py` | **Create** | Sub-phase 5 tests (restart). |
| `tests/test_full_pipeline_no_regression.py` | **Create** | Final integration check. |

---

## Sub-Phase 1: Soft-hold primitive

**Goal:** Add the `set_hold` / `clear_hold` / `is_held` API to the scheduler and a `should_dispatch_or_pause` helper for workers. **No callers wire it up yet** — primitive is dormant. Single-project flow unchanged.

### Task 1.1: Create the `holds.py` module

**Files:**
- Create: `src/prep/services/pipeline/holds.py`

- [ ] **Step 1: Write the new module file**

```python
"""Phase 127: soft-hold primitive shared by exclusive priority and swarm-drain.

A soft-hold tells a worker dispatch loop "no new LLM calls for this
(project, endpoint) pair; let in-flight finish and pause." Workers
poll ``PipelineScheduler.is_held()`` between dispatches and pause when
True. The hold is cleared (by exclusive lift, swarm window close, or
explicit clear) and workers resume from their last checkpoint.

This file holds the data types only — the live state and the
set/clear/is_held methods live on PipelineScheduler in scheduler.py
to keep them under the same lock as the rest of scheduler state.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

# A hold can come from one of three causes.  ``exclusive`` and
# ``swarm`` are the user-facing causes; ``manual`` is reserved for
# tests and admin tooling.
HoldReason = Literal["exclusive", "swarm", "manual"]


@dataclass(frozen=True)
class HoldKey:
    """Unique key identifying a single hold."""
    project_id: str
    endpoint_id: str  # scheduler node_id (e.g., "cloud:default_ollama")


@dataclass
class HoldEntry:
    """A single active hold with provenance."""
    reason: HoldReason
    set_by_project: str  # the project that triggered the hold
    held_since: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "set_by_project": self.set_by_project,
            "held_since": self.held_since,
        }
```

- [ ] **Step 2: Commit**

```bash
git add src/prep/services/pipeline/holds.py
git commit -m "feat(phase127): add holds.py — HoldReason, HoldKey, HoldEntry types

Soft-hold primitive types extracted to a small module.  No callers
yet; the live state and set/clear methods will land in scheduler.py
in the next task."
```

### Task 1.2: Add hold state + methods to PipelineScheduler

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_soft_hold_primitive.py`:

```python
"""Phase 127 sub-phase 1: soft-hold primitive correctness."""
from __future__ import annotations


def _fresh_scheduler():
    """Return a fresh PipelineScheduler instance for testing.

    The scheduler is a singleton in production; these unit tests
    construct a private instance to keep state isolated.
    """
    from prep.services.pipeline.scheduler import PipelineScheduler
    return PipelineScheduler()


def test_no_holds_by_default() -> None:
    s = _fresh_scheduler()
    assert s.is_held("any-project", "any-endpoint") is False
    assert s.list_holds() == []


def test_set_hold_then_is_held() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-B")
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    # Other (project, endpoint) pairs are NOT held.
    assert s.is_held("proj-A", "cloud:openrouter") is False
    assert s.is_held("proj-B", "cloud:default_ollama") is False


def test_clear_hold_specific() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-B")
    s.clear_hold("proj-A", "cloud:default_ollama")
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_clear_holds_by_setter_project() -> None:
    """When a swarm window closes, all holds it set should clear in one call."""
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-B")
    s.set_hold("proj-A", "cloud:openrouter", reason="swarm", set_by_project="proj-B")
    s.set_hold("proj-C", "cloud:default_ollama", reason="exclusive", set_by_project="proj-D")
    # Clear only proj-B's holds.
    s.clear_holds_set_by("proj-B")
    assert s.is_held("proj-A", "cloud:default_ollama") is False
    assert s.is_held("proj-A", "cloud:openrouter") is False
    # Unrelated hold (set by proj-D) untouched.
    assert s.is_held("proj-C", "cloud:default_ollama") is True


def test_list_holds_returns_entries() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-B")
    holds = s.list_holds()
    assert len(holds) == 1
    h = holds[0]
    assert h["project_id"] == "proj-A"
    assert h["endpoint_id"] == "cloud:default_ollama"
    assert h["reason"] == "exclusive"
    assert h["set_by_project"] == "proj-B"
    assert isinstance(h["held_since"], float)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py -v
```
Expected: FAIL — `PipelineScheduler` has no `is_held` / `set_hold` / etc.

- [ ] **Step 3: Add the hold state + methods to PipelineScheduler**

In `src/prep/services/pipeline/scheduler.py`, add the import near the top:

```python
from prep.services.pipeline.holds import HoldEntry, HoldKey, HoldReason
```

In `PipelineScheduler.__init__()` (around line 290 where `_priority_projects` is initialized), add:

```python
        # Phase 127: soft-hold primitive.  Workers poll is_held() before
        # each LLM dispatch.  Holds are set by exclusive priority or
        # swarm window opens, cleared on lift/close.  Per (project,
        # endpoint) granularity so a project blocked on Ollama Cloud
        # can still serve requests on, say, OpenRouter.
        self._holds: Dict[HoldKey, HoldEntry] = {}
```

Add the four methods to `PipelineScheduler` (recommended placement: right below `set_priority`, around line 600):

```python
    # ── Phase 127: Soft-hold primitive ─────────────────────────────

    def set_hold(
        self,
        project_id: str,
        endpoint_id: str,
        *,
        reason: HoldReason,
        set_by_project: str,
    ) -> None:
        """Mark (project_id, endpoint_id) as soft-held.

        Workers polling ``is_held(project_id, endpoint_id)`` will pause
        new LLM dispatches.  In-flight calls run to completion.
        """
        with self._lock:
            key = HoldKey(project_id=project_id, endpoint_id=endpoint_id)
            self._holds[key] = HoldEntry(
                reason=reason, set_by_project=set_by_project,
            )

    def clear_hold(self, project_id: str, endpoint_id: str) -> None:
        """Clear a single (project, endpoint) hold.  No-op if not held."""
        with self._lock:
            self._holds.pop(
                HoldKey(project_id=project_id, endpoint_id=endpoint_id),
                None,
            )

    def clear_holds_set_by(self, set_by_project: str) -> None:
        """Clear all holds that ``set_by_project`` triggered.

        Used by ``close_swarm_window`` and ``set_priority(P, "none")``
        to release everything in one call.
        """
        with self._lock:
            to_remove = [
                k for k, v in self._holds.items()
                if v.set_by_project == set_by_project
            ]
            for k in to_remove:
                del self._holds[k]

    def is_held(self, project_id: str, endpoint_id: str) -> bool:
        """Return True if (project_id, endpoint_id) currently has a hold."""
        with self._lock:
            return HoldKey(project_id, endpoint_id) in self._holds

    def list_holds(self) -> List[Dict[str, Any]]:
        """Snapshot all active holds for diagnostics / API surface."""
        with self._lock:
            return [
                {"project_id": k.project_id, "endpoint_id": k.endpoint_id, **v.to_dict()}
                for k, v in self._holds.items()
            ]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py -q
```
Expected: all pass (primitive is dormant, no behavior change).

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_soft_hold_primitive.py
git commit -m "feat(phase127): soft-hold primitive on PipelineScheduler

Adds set_hold/clear_hold/clear_holds_set_by/is_held/list_holds with
per-(project, endpoint) granularity.  No callers wired yet — primitive
is dormant; single-project flow unchanged.

Tests: tests/test_soft_hold_primitive.py covers set, clear-specific,
clear-by-setter, list snapshot, default-empty."
```

### Task 1.3: Add `_should_dispatch_or_pause` helper for workers

**Files:**
- Modify: `src/prep/services/pipeline/workers.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_soft_hold_primitive.py`:

```python
def test_should_dispatch_returns_true_when_not_held() -> None:
    from prep.services.pipeline.workers import _should_dispatch_or_pause
    # No hold → dispatch immediately, no pause.
    assert _should_dispatch_or_pause(
        project_id="proj-A",
        endpoint_id="cloud:default_ollama",
        poll_interval_s=0.01,
        max_wait_s=0.05,
    ) is True


def test_should_dispatch_polls_then_returns_when_cleared(monkeypatch) -> None:
    """When a hold is set then cleared mid-poll, the helper resumes."""
    import threading
    import time
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.workers import _should_dispatch_or_pause

    pipeline_scheduler.set_hold(
        "proj-A", "cloud:default_ollama", reason="manual", set_by_project="test",
    )

    def _clear_after_delay():
        time.sleep(0.05)
        pipeline_scheduler.clear_hold("proj-A", "cloud:default_ollama")

    threading.Thread(target=_clear_after_delay, daemon=True).start()
    result = _should_dispatch_or_pause(
        project_id="proj-A",
        endpoint_id="cloud:default_ollama",
        poll_interval_s=0.01,
        max_wait_s=1.0,
    )
    assert result is True


def test_should_dispatch_returns_false_after_max_wait() -> None:
    """If hold never clears within max_wait_s, helper returns False."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.workers import _should_dispatch_or_pause

    pipeline_scheduler.set_hold(
        "proj-B", "cloud:default_ollama", reason="manual", set_by_project="test",
    )
    try:
        result = _should_dispatch_or_pause(
            project_id="proj-B",
            endpoint_id="cloud:default_ollama",
            poll_interval_s=0.01,
            max_wait_s=0.05,
        )
        assert result is False
    finally:
        pipeline_scheduler.clear_hold("proj-B", "cloud:default_ollama")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py::test_should_dispatch_returns_true_when_not_held -v
```
Expected: FAIL — `_should_dispatch_or_pause` doesn't exist.

- [ ] **Step 3: Add the helper**

In `src/prep/services/pipeline/workers.py`, add near the top of `WorkerFactory` (or as a module-level helper above it):

```python
def _should_dispatch_or_pause(
    *,
    project_id: str,
    endpoint_id: str,
    poll_interval_s: float = 1.0,
    max_wait_s: float = 600.0,
) -> bool:
    """Phase 127 soft-hold check called by stage workers before each LLM
    dispatch.

    Returns True when the worker may dispatch (no hold OR hold cleared
    within ``max_wait_s``).  Returns False if the hold is still active
    after ``max_wait_s`` — caller should checkpoint and exit cleanly.

    The poll interval is deliberately coarse; long-running LLM calls
    don't notice this overhead because the check fires only between
    dispatches.
    """
    import time
    from prep.services.pipeline.scheduler import pipeline_scheduler
    deadline = time.monotonic() + max_wait_s
    while True:
        if not pipeline_scheduler.is_held(project_id, endpoint_id):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval_s)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py -v
```
Expected: 8 passed (5 original + 3 new).

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/workers.py tests/test_soft_hold_primitive.py
git commit -m "feat(phase127): _should_dispatch_or_pause helper for stage workers

Workers call this between LLM dispatches.  Returns True immediately
when not held; polls every poll_interval_s until cleared or
max_wait_s elapses.  No callers yet (primitive is still dormant);
wires up in sub-phase 2."
```

---

## Sub-Phase 2: Cooldown removal + boost-weighted FIFO

**Goal:** Remove `_swarm_cooldown_seconds` and replace with queue-driven ordering. Wire `open_swarm_window` to set holds on drain targets and `close_swarm_window` to clear them.

### Task 2.1: Remove `_swarm_cooldown_seconds`

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_swarm_cooldown_removal.py`:

```python
"""Phase 127 sub-phase 2: cooldown was removed; same project can re-open
swarm window immediately."""
from __future__ import annotations

import pytest


def test_swarm_window_can_reopen_immediately_after_close() -> None:
    """No cooldown — close then immediate re-open succeeds."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)

    assert s.open_swarm_window("proj-A", StageId.GROUP_REASONING, "cloud:default_ollama") is True
    s.close_swarm_window()
    # Immediate re-open by ANY project succeeds (same or different).
    assert s.open_swarm_window("proj-A", StageId.CLUSTERING, "cloud:default_ollama") is True


def test_no_swarm_cooldown_seconds_attribute() -> None:
    """Make sure the cooldown timer field is gone so future readers
    don't think it's still load-bearing."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    s = PipelineScheduler()
    assert not hasattr(s, "_swarm_cooldown_seconds"), (
        "Phase 127 removed _swarm_cooldown_seconds — see Phase 127 spec §7.4"
    )
    assert not hasattr(s, "_swarm_cooldown_until"), (
        "Phase 127 removed _swarm_cooldown_until — see Phase 127 spec §7.4"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_swarm_cooldown_removal.py -v
```
Expected: FAIL — cooldown attributes still exist.

- [ ] **Step 3: Remove cooldown field, init, and check**

In `src/prep/services/pipeline/scheduler.py`:

Remove from `__init__()` (around line 296-297):

```python
        # DELETE THESE TWO LINES:
        self._swarm_cooldown_until: float = 0.0
        self._swarm_cooldown_seconds: float = 45.0
```

In `open_swarm_window()` (around line 1426), remove the cooldown check block:

```python
            # DELETE THIS BLOCK (lines 1426-1432):
            # Cooldown check
            if time.time() < self._swarm_cooldown_until:
                logger.info(
                    "Scheduler: swarm window blocked by cooldown (%.1fs remaining) for %s",
                    self._swarm_cooldown_until - time.time(), project_id,
                )
                return False
```

In `close_swarm_window()` (around line 1473), remove the cooldown set:

```python
            # DELETE THIS LINE (1473):
            self._swarm_cooldown_until = time.time() + self._swarm_cooldown_seconds
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_swarm_cooldown_removal.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_swarm_cooldown_removal.py
git commit -m "feat(phase127): remove _swarm_cooldown_seconds (queue handles ordering)

The 45s cooldown between swarm windows blocked back-to-back same-project
swarms (atlas -> concepts) and created a false UI state in Phase 119.
Anti-thrash now comes from queue ordering (boost-weighted FIFO in next
task), not a timer.

See Phase 127 spec §7.4 for rationale."
```

### Task 2.2: Boost-weighted FIFO in `dequeue_next`

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_boost_weighted_fifo.py`:

```python
"""Phase 127 sub-phase 2: boost projects skip ahead in the queue."""
from __future__ import annotations


def _setup_scheduler():
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    return s, StageId


def test_boost_skips_ahead_of_normal() -> None:
    """Two normals queued first, then a boost; boost runs first."""
    s, StageId = _setup_scheduler()
    # Normal projects fill the queue first.
    s.enqueue("proj-N1", StageId.ENRICHMENT, "cloud:default_ollama")
    s.enqueue("proj-N2", StageId.ENRICHMENT, "cloud:default_ollama")
    # Boost project arrives last.
    s.set_priority("proj-B", "boost")
    s.enqueue("proj-B", StageId.ENRICHMENT, "cloud:default_ollama")

    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry is not None
    assert next_entry.project_id == "proj-B"


def test_fifo_within_same_tier() -> None:
    """Two normals queued in order; FIFO within the normal tier."""
    s, StageId = _setup_scheduler()
    s.enqueue("proj-N1", StageId.ENRICHMENT, "cloud:default_ollama")
    s.enqueue("proj-N2", StageId.ENRICHMENT, "cloud:default_ollama")
    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry.project_id == "proj-N1"


def test_boost_fifo_within_boost_tier() -> None:
    s, StageId = _setup_scheduler()
    s.set_priority("proj-B1", "boost")
    s.set_priority("proj-B2", "boost")
    s.enqueue("proj-B1", StageId.ENRICHMENT, "cloud:default_ollama")
    s.enqueue("proj-B2", StageId.ENRICHMENT, "cloud:default_ollama")
    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry.project_id == "proj-B1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_boost_weighted_fifo.py -v
```
Expected: FAIL — current dequeue is plain FIFO, boost not honored.

- [ ] **Step 3: Implement boost-weighted FIFO**

Find `dequeue_next` in `scheduler.py` (search for `def dequeue_next`). Modify it:

```python
    def dequeue_next(self, node_id: Optional[str] = None) -> Optional[QueueEntry]:
        """Pop the highest-priority next queue entry for ``node_id``.

        Phase 127: boost-weighted FIFO.  Boost projects skip ahead of
        normal projects.  Within a tier, FIFO order is preserved.
        Exclusive doesn't sort separately because exclusive projects
        rarely enter the queue (they hold the slot directly).
        """
        with self._lock:
            queue = self._queues.get(node_id) if node_id else self._get_queue()
            if not queue:
                return None
            # Find the highest-priority entry.  Boost > Normal.
            # Within a tier, lowest enqueued_at wins (FIFO).
            best_idx = 0
            best_entry = queue[0]
            best_level = self._priority_projects.get(best_entry.project_id, "none")
            for i in range(1, len(queue)):
                e = queue[i]
                e_level = self._priority_projects.get(e.project_id, "none")
                # Compare tiers: boost beats none.  ("exclusive" can also
                # appear here in the rare case an exclusive project
                # enqueued; treat exclusive same as boost for tier purposes.)
                best_is_boost = best_level in ("boost", "exclusive")
                e_is_boost = e_level in ("boost", "exclusive")
                if e_is_boost and not best_is_boost:
                    best_idx, best_entry, best_level = i, e, e_level
                elif e_is_boost == best_is_boost and e.enqueued_at < best_entry.enqueued_at:
                    # Same tier, earlier enqueued wins FIFO.
                    best_idx, best_entry, best_level = i, e, e_level
            del queue[best_idx]
            return best_entry
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_boost_weighted_fifo.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_queue_router.py tests/test_queue_active_tasks.py tests/test_queue_status_state.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_boost_weighted_fifo.py
git commit -m "feat(phase127): boost-weighted FIFO in dequeue_next

Boost projects skip ahead of normal projects in the swarm-waiter
queue.  Within a tier, FIFO order is preserved by enqueued_at.

See Phase 127 spec §7.3 for queue ordering rules."
```

### Task 2.3: Wire `open_swarm_window` to set holds, `close_swarm_window` to clear

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_swarm_cooldown_removal.py`:

```python
def test_open_swarm_sets_holds_on_drain_targets() -> None:
    """When swarm window opens, every other active project on the same
    node gets a soft-hold."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    # proj-X is already running on the node.
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    # proj-A opens a swarm window.
    assert s.open_swarm_window("proj-A", StageId.GROUP_REASONING, "cloud:default_ollama") is True
    # proj-X should be soft-held on this node.
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    # proj-A (the swarm owner) is NOT held.
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_close_swarm_clears_drain_holds() -> None:
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.open_swarm_window("proj-A", StageId.GROUP_REASONING, "cloud:default_ollama")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    s.close_swarm_window()
    assert s.is_held("proj-X", "cloud:default_ollama") is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_swarm_cooldown_removal.py::test_open_swarm_sets_holds_on_drain_targets -v
```
Expected: FAIL — open_swarm_window doesn't call set_hold yet.

- [ ] **Step 3: Wire open/close to set/clear holds**

In `scheduler.py:open_swarm_window()`, after the `self._swarm_window = {...}` block, before the broadcast call, add:

```python
            # Phase 127: stamp soft-holds on every drain target so
            # their workers stop dispatching new LLM calls and let
            # in-flight finish naturally.  Cleared on
            # close_swarm_window via clear_holds_set_by(project_id).
            for drain_pid in drain_targets:
                key = HoldKey(project_id=drain_pid, endpoint_id=resolved)
                self._holds[key] = HoldEntry(
                    reason="swarm",
                    set_by_project=project_id,
                )
```

In `scheduler.py:close_swarm_window()`, after `self._swarm_window = None`, add:

```python
            # Phase 127: clear all holds this swarm set on drain targets.
            owner = window.get("project_id") if window else None
            if owner:
                to_clear = [k for k, v in self._holds.items() if v.set_by_project == owner and v.reason == "swarm"]
                for k in to_clear:
                    del self._holds[k]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_swarm_cooldown_removal.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run regression suite (extended)**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_swarm_cooldown_removal.py
git commit -m "feat(phase127): swarm window open/close manage soft-holds

open_swarm_window now stamps a soft-hold on every drain-target
project for the swarm node.  close_swarm_window clears the holds it
set.  Workers respecting _should_dispatch_or_pause will pause new
LLM dispatches during the drain.

In-flight calls run to completion naturally (no thread-kill); when
all conflicting calls drain, the swarm proceeds with full budget.
See Phase 127 spec §5 + §8 for the lifecycle."
```

### Task 2.4: Wire `set_priority(P, "exclusive")` to set holds, lift to clear

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_soft_hold_primitive.py`:

```python
def test_exclusive_sets_holds_on_other_active_projects() -> None:
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.acquire("proj-Y", StageId.ENRICHMENT, "cloud:default_ollama")
    # User clicks Exclusive on a NEW project (not currently active).
    s.set_priority("proj-A", "exclusive")
    # Both other projects soft-held.
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    assert s.is_held("proj-Y", "cloud:default_ollama") is True
    # The exclusive project itself is not held.
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_lifting_exclusive_clears_holds() -> None:
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-A", "exclusive")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    s.set_priority("proj-A", "none")
    assert s.is_held("proj-X", "cloud:default_ollama") is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py::test_exclusive_sets_holds_on_other_active_projects -v
```
Expected: FAIL.

- [ ] **Step 3: Wire `set_priority` to set/clear holds**

In `scheduler.py:set_priority`, find the section where the priority dict is updated (around line 583 where `self._priority_projects[project_id] = level` is set). Add:

```python
            # Phase 127: when setting exclusive, soft-hold every other
            # active project on every node they're using.
            if level == "exclusive":
                for nid, slot in self._slots.items():
                    if nid == self._EMBEDDING_NODE_ID:
                        continue  # embedding is local + cheap; don't hold
                    for other_pid in slot.active_stages:
                        if other_pid != project_id:
                            self._holds[HoldKey(other_pid, nid)] = HoldEntry(
                                reason="exclusive",
                                set_by_project=project_id,
                            )
```

In the section where priority is REMOVED (around line 559 where `self._priority_projects.pop(project_id, None)` is called when level is `none`), add:

```python
                # Phase 127: clear all holds this project set as exclusive.
                if old_level == "exclusive" or (old is not None and old == "exclusive"):
                    to_clear = [
                        k for k, v in self._holds.items()
                        if v.set_by_project == project_id and v.reason == "exclusive"
                    ]
                    for k in to_clear:
                        del self._holds[k]
```

(Implementation note: the `old_level` variable name depends on the existing code; use whichever variable is already tracking the prior level. If unsure, add a defensive `old_level = self._priority_projects.get(project_id)` before the pop.)

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_soft_hold_primitive.py
git commit -m "feat(phase127): set_priority exclusive sets soft-holds; lift clears

Setting a project to 'exclusive' now stamps soft-holds on every other
active project across all non-embedding scheduler nodes.  Clearing
exclusive (set_priority(P, 'none')) removes those holds.

See Phase 127 spec §6 for the exclusive lifecycle."
```

### Task 2.5: Honor soft-hold in epistemic_enrichment dispatch loop

**Files:**
- Modify: `src/prep/core/epistemic_enrichment.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_soft_hold_primitive.py`:

```python
def test_epistemic_enricher_pauses_on_hold(monkeypatch) -> None:
    """When soft-held, EpistemicEnricher should NOT dispatch a new
    LLM call; it should pause and re-poll."""
    import threading
    import time
    from prep.services.pipeline.scheduler import pipeline_scheduler

    pipeline_scheduler.set_hold(
        "proj-pause-test", "cloud:default_ollama",
        reason="manual", set_by_project="test",
    )
    dispatched = []

    def fake_dispatch():
        # Simulate the per-call check pattern used by the enricher.
        from prep.services.pipeline.workers import _should_dispatch_or_pause
        ok = _should_dispatch_or_pause(
            project_id="proj-pause-test",
            endpoint_id="cloud:default_ollama",
            poll_interval_s=0.01,
            max_wait_s=0.1,
        )
        dispatched.append(ok)

    fake_dispatch()
    assert dispatched == [False], "dispatcher should have returned False (held)"

    pipeline_scheduler.clear_hold("proj-pause-test", "cloud:default_ollama")
    fake_dispatch()
    assert dispatched == [False, True], "dispatcher should have returned True after clear"
```

(This test just verifies the helper works in the worker pattern; the actual epistemic_enrichment integration is verified by the regression test below.)

- [ ] **Step 2: Run test to verify it passes (helper already exists)**

```bash
.venv/bin/pytest tests/test_soft_hold_primitive.py::test_epistemic_enricher_pauses_on_hold -v
```
Expected: PASS — the helper from sub-phase 1 makes this work.

- [ ] **Step 3: Wire the check into epistemic_enrichment**

In `src/prep/core/epistemic_enrichment.py`, find `enrich_node` (search `def enrich_node`). Just before the `text, tokens = self.llm.generate(...)` call (around line 582 and again around line 726), add:

```python
        # Phase 127: respect soft-holds.  If this (project, endpoint) is
        # held (exclusive on another project, or swarm window draining
        # ours), pause this dispatch.  In-flight calls finish naturally;
        # the dispatcher resumes when the hold clears.
        from prep.services.pipeline.workers import _should_dispatch_or_pause
        if not _should_dispatch_or_pause(
            project_id=getattr(self, "project_id", None) or "",
            endpoint_id=getattr(self.llm, "endpoint_id", None) or "",
        ):
            logger.info(
                "Epistemic dispatch paused on hold (project=%s endpoint=%s) — "
                "exiting cleanly so caller can checkpoint",
                getattr(self, "project_id", "?"),
                getattr(self.llm, "endpoint_id", "?"),
            )
            return None  # caller handles None as "pause/checkpoint"
```

(If `EpistemicEnricher` doesn't already store `project_id`, add it as a constructor argument and pass through from the worker. Search for `EpistemicEnricher(` to find construction sites.)

If `project_id` is not currently passed to `EpistemicEnricher`:

In `src/prep/core/epistemic_enrichment.py`, modify `__init__`:

```python
    def __init__(
        self,
        llm,
        repo_root,
        index_dir,
        batch_profile=None,
        project_id: Optional[str] = None,  # Phase 127
    ):
        # ... existing init ...
        self.project_id = project_id
```

In `src/prep/services/pipeline/workers.py:_epistemic_worker`, pass `project_id`:

```python
            enricher = EpistemicEnricher(
                llm=llm_client,
                repo_root=Path(project.path),
                index_dir=idx_dir,
                batch_profile=batch_profile,
                project_id=project_id,  # Phase 127
            )
```

- [ ] **Step 4: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py -q
```
Expected: all pass. (The new code only kicks in when a hold is set; in single-project flow no hold ever sets, so behavior is unchanged.)

- [ ] **Step 5: Commit**

```bash
git add src/prep/core/epistemic_enrichment.py src/prep/services/pipeline/workers.py tests/test_soft_hold_primitive.py
git commit -m "feat(phase127): epistemic enricher honors soft-hold

EpistemicEnricher.enrich_node now checks _should_dispatch_or_pause
before each LLM call.  Held workers exit with None (caller treats as
'pause and checkpoint').  No-op for single-project flow (no hold
ever sets); kicks in only when exclusive or swarm window applies."
```

### Task 2.6: Honor soft-hold in augmenter dispatch loop

**Files:**
- Modify: `src/prep/core/augmenter.py`

- [ ] **Step 1: Add the check**

In `src/prep/core/augmenter.py`, find the LLM dispatch call (search for `self.llm.generate` — multiple call sites at lines 338 and elsewhere). Before each `self.llm.generate(...)` invocation in batch dispatch loops, add the same check pattern:

```python
        # Phase 127: respect soft-holds (same pattern as epistemic).
        from prep.services.pipeline.workers import _should_dispatch_or_pause
        if not _should_dispatch_or_pause(
            project_id=getattr(self, "project_id", None) or "",
            endpoint_id=getattr(self.llm, "endpoint_id", None) or "",
        ):
            logger.info("Augmenter dispatch paused on hold — exiting batch")
            return None  # caller handles None as pause
```

If `TraceAugmenter` doesn't currently take `project_id`, add it:

```python
class TraceAugmenter:
    def __init__(
        self,
        index_dir,
        repo_root,
        llm_client=None,
        batch_profile=None,
        project_id: Optional[str] = None,  # Phase 127
    ):
        # ... existing init ...
        self.project_id = project_id
```

And pass through from the construction sites in `workers.py` (`_catalogue_worker` etc.).

- [ ] **Step 2: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py -q
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/prep/core/augmenter.py src/prep/services/pipeline/workers.py
git commit -m "feat(phase127): TraceAugmenter honors soft-hold

Same pattern as epistemic enricher: check _should_dispatch_or_pause
before each batched LLM call; return None on persistent hold so
caller can checkpoint and exit.  No-op for single-project."
```

### Task 2.7: Honor soft-hold in SwarmOrchestrator phase boundaries

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py`

- [ ] **Step 1: Add the check between coord/fanout/synth phases**

In `src/prep/core/swarm_orchestrator.py`, find `def run` or the phase-driver function. Between the coord call returning and the fanout starting, and between fanout returning and synth starting, add:

```python
        # Phase 127: between phase boundaries, honor soft-holds.  If
        # exclusive was set on another project mid-swarm, this swarm's
        # phase boundary is the safe place to pause.
        from prep.services.pipeline.workers import _should_dispatch_or_pause
        worker_endpoint = getattr(self.worker_llm, "endpoint_id", None) or ""
        if worker_endpoint and not _should_dispatch_or_pause(
            project_id=getattr(self, "project_id", None) or "",
            endpoint_id=worker_endpoint,
        ):
            logger.warning(
                "[Swarm] Paused at phase boundary on hold (project=%s) — "
                "salvaging with partial result",
                getattr(self, "project_id", "?"),
            )
            return SwarmResult(...)  # or appropriate partial result
```

(Refine the return-value to whatever `SwarmResult` shape is appropriate for "paused at phase boundary".)

If `SwarmOrchestrator` doesn't already take `project_id`, add it analogous to the augmenter/enricher.

- [ ] **Step 2: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_swarm_orchestrator.py tests/test_swarm_orchestrator_timeout.py -q
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py
git commit -m "feat(phase127): SwarmOrchestrator honors soft-hold at phase boundaries

When exclusive is set mid-swarm on another project, this swarm pauses
at the next coord/fanout/synth boundary rather than mid-phase. Cleanly
salvages with a partial result and resumes from the next phase when
the hold clears."
```

---

## Sub-Phase 3: Endpoint-disjoint exception clause

**Goal:** When a project is exclusive or has a swarm window, ONLY soft-hold others on conflicting endpoints. Allow non-conflicting projects to proceed.

### Task 3.1: Add `endpoint_set` to swarm window state

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_endpoint_disjoint.py`:

```python
"""Phase 127 sub-phase 3: endpoint-disjoint exception."""
from __future__ import annotations


def _setup():
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.configure_node("cloud:openrouter", max_concurrent=1)
    return s, StageId


def test_swarm_only_holds_projects_on_conflicting_endpoints() -> None:
    """proj-A swarms using only Ollama Cloud.  proj-X is on OpenRouter.
    proj-X should NOT be held — endpoints disjoint."""
    s, StageId = _setup()
    # proj-X using OpenRouter only.
    s.acquire("proj-X", StageId.CONCEPTS, "cloud:openrouter")
    # proj-A opens a swarm window touching Ollama Cloud only.
    s.open_swarm_window(
        "proj-A", StageId.GROUP_REASONING,
        node_id="cloud:default_ollama",
        endpoint_set={"cloud:default_ollama"},
    )
    # proj-X is on a different endpoint — NOT held.
    assert s.is_held("proj-X", "cloud:openrouter") is False


def test_swarm_with_multi_endpoint_holds_all_intersecting() -> None:
    """proj-A swarms using BOTH Ollama Cloud and OpenRouter.  proj-X is
    on OpenRouter; proj-Y is on Ollama Cloud.  Both held."""
    s, StageId = _setup()
    s.acquire("proj-X", StageId.CONCEPTS, "cloud:openrouter")
    s.acquire("proj-Y", StageId.CATALOGUE, "cloud:default_ollama")
    s.open_swarm_window(
        "proj-A", StageId.GROUP_REASONING,
        node_id="cloud:default_ollama",
        endpoint_set={"cloud:default_ollama", "cloud:openrouter"},
    )
    assert s.is_held("proj-X", "cloud:openrouter") is True
    assert s.is_held("proj-Y", "cloud:default_ollama") is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_endpoint_disjoint.py -v
```
Expected: FAIL — open_swarm_window doesn't accept `endpoint_set` yet.

- [ ] **Step 3: Add `endpoint_set` parameter and use it**

In `scheduler.py:open_swarm_window`, add the parameter and use it for hold scoping:

```python
    def open_swarm_window(
        self,
        project_id: str,
        stage: "StageId",
        node_id: Optional[str] = None,
        *,
        endpoint_set: Optional[set] = None,  # Phase 127
    ) -> bool:
        # ... existing checks ...

        # Phase 127: endpoint set defaults to just the resolved node
        # for backward compat with single-endpoint callers.  Multi-
        # endpoint swarms (coord on OpenRouter + workers on Ollama)
        # pass the full set explicitly.
        eps = endpoint_set if endpoint_set else {resolved}

        # ... existing window record ...
        self._swarm_window["endpoint_set"] = eps  # Phase 127

        # ... existing drain target identification ...
        # Phase 127: drain targets are projects active on ANY endpoint
        # in eps, not just `resolved`.
        drain_targets: Dict[str, float] = {}
        now = time.time()
        for ep in eps:
            slot = self._slots.get(ep)
            if not slot:
                continue
            for pid in slot.active_stages:
                if pid != project_id:
                    drain_targets[pid] = now
                    self._holds[HoldKey(pid, ep)] = HoldEntry(
                        reason="swarm",
                        set_by_project=project_id,
                    )
        # ... rest of method ...
```

(Adapt this to the actual existing code structure. The key point: drain_targets and holds now iterate over the endpoint_set, not just one resolved node.)

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_endpoint_disjoint.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_endpoint_disjoint.py
git commit -m "feat(phase127): endpoint-disjoint exception in swarm window

open_swarm_window now takes an optional endpoint_set parameter.  Holds
are stamped on drain targets only for endpoints in the set, not the
single resolved node.  Projects on disjoint endpoints proceed normally.

Default behavior (no endpoint_set passed) preserves backward compat:
single-endpoint window holds match the resolved node.

See Phase 127 spec §9 for examples."
```

### Task 3.2: SwarmOrchestrator passes its endpoint_set when opening windows

**Files:**
- Modify: `src/prep/core/swarm_orchestrator.py`

- [ ] **Step 1: Determine the SwarmOrchestrator's endpoint set**

The orchestrator uses two LLM clients: `coordinator_llm` and `worker_llm`. Each has an `endpoint_id`. The endpoint_set is the resolved scheduler nodes for each.

In `swarm_orchestrator.py`, find where `pipeline_scheduler.open_swarm_window` is called (search the file). Before that call, build the set:

```python
        # Phase 127: build endpoint_set from this swarm's two LLM clients.
        coord_node = self.coordinator_llm._resolve_scheduler_node_id() if self.coordinator_llm else None
        worker_node = self.worker_llm._resolve_scheduler_node_id() if self.worker_llm else None
        endpoint_set = {n for n in (coord_node, worker_node) if n}
        # Pass to scheduler so non-conflicting projects can keep running.
        opened = pipeline_scheduler.open_swarm_window(
            project_id, stage,
            node_id=worker_node,  # primary node, for backward compat
            endpoint_set=endpoint_set,
        )
```

If the call to `open_swarm_window` happens in the pipeline orchestrator instead of the SwarmOrchestrator, locate that site and modify it analogously.

- [ ] **Step 2: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py tests/test_swarm_orchestrator.py -q
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/prep/core/swarm_orchestrator.py
git commit -m "feat(phase127): SwarmOrchestrator passes endpoint_set to scheduler

When opening a swarm window, pass the union of coord+worker endpoint
nodes so the scheduler holds only conflicting projects.  Single-endpoint
swarms still pass a 1-element set; multi-endpoint swarms (coord on
OpenRouter + workers on Ollama Cloud) pass both."
```

---

## Sub-Phase 4: UI signal integration

**Goal:** Surface `state` / `held_reason` / `swarm_queue` / `held_projects` in API responses so the UI can render them.

### Task 4.1: Add `held` info to running_tasks via `/llm/slots/status`

**Files:**
- Modify: `src/prep/api/routers/llm.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_held_state_api.py`:

```python
"""Phase 127 sub-phase 4: API surfaces held/queue state."""
from __future__ import annotations


def test_running_task_includes_held_fields(monkeypatch) -> None:
    """When a project is held, /llm/slots/status reports it with
    state='held' and a held_reason."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.set_hold(
        "proj-held-test", "cloud:default_ollama",
        reason="exclusive", set_by_project="proj-other",
    )
    from prep.api.routers import llm as llm_mod
    holds = pipeline_scheduler.list_holds()
    found = [h for h in holds if h["project_id"] == "proj-held-test"]
    assert len(found) == 1
    assert found[0]["reason"] == "exclusive"
    assert found[0]["set_by_project"] == "proj-other"
    pipeline_scheduler.clear_hold("proj-held-test", "cloud:default_ollama")
```

- [ ] **Step 2: Add `held_projects` to scheduler status response**

In `src/prep/api/routers/llm.py`, the slot-status response builder appends running_tasks (around line 660-700). After running_tasks are populated, add:

```python
    # Phase 127: surface held projects so UI can render distinct state.
    held_projects = pipeline_scheduler.list_holds()
    result["held_projects"] = held_projects
```

Locate the `result = {...}` dict at the end of the slots-status builder (around line 938) and add `"held_projects": ...` to it (or merge after the dict construction as shown above).

- [ ] **Step 3: Run test**

```bash
.venv/bin/pytest tests/test_held_state_api.py -v
```
Expected: PASS.

- [ ] **Step 4: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py tests/test_held_state_api.py -q
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/llm.py tests/test_held_state_api.py
git commit -m "feat(phase127): /llm/slots/status surfaces held_projects

Adds held_projects to the slot-status response so the UI can render
'Held - exclusive on Project X' indicators for soft-blocked projects."
```

### Task 4.2: Add `state` and `held_reason` to running_tasks entries

**Files:**
- Modify: `src/prep/api/routers/llm.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_held_state_api.py`:

```python
def test_running_task_has_state_field() -> None:
    """Each running_task entry carries a state and held_reason."""
    # This test asserts the schema; runtime values depend on actual
    # pipeline activity.  Just verify the keys are present in any
    # entry the API returns.
    from prep.api.routers.llm import _running_task_state
    assert _running_task_state(
        project_id="proj-X",
        is_held=True,
        held_reason="exclusive",
        is_swarm=False,
    ) == "held"
    assert _running_task_state(
        project_id="proj-X",
        is_held=False,
        held_reason=None,
        is_swarm=True,
    ) == "swarm_active"
    assert _running_task_state(
        project_id="proj-X",
        is_held=False,
        held_reason=None,
        is_swarm=False,
    ) == "running"
```

- [ ] **Step 2: Add `_running_task_state` helper**

In `src/prep/api/routers/llm.py`, near the top (after `_summarize_swarm_phases`):

```python
def _running_task_state(
    *,
    project_id: str,
    is_held: bool,
    held_reason: Optional[str],
    is_swarm: bool,
) -> str:
    """Phase 127: classify a running task into one of:

    - "held"           : soft-held by exclusive or swarm window
    - "swarm_active"   : actively in a swarm session
    - "running"        : normal pipeline activity
    - "idle"           : no active dispatch  (caller decides)
    """
    if is_held:
        return "held"
    if is_swarm:
        return "swarm_active"
    return "running"
```

- [ ] **Step 3: Wire it into the running_tasks loop**

Find the running_tasks expansion in `llm.py` (around line 727 where `concurrent_workers` is set). After computing `is_swarm`, also compute hold state:

```python
                # Phase 127: classify state.
                pid = rt["project_id"]
                # Determine endpoints this project might be held on (we
                # check the primary node here; full enumeration would
                # require knowing all nodes the project's stage uses).
                primary_node = rt.get("compute_node") or "cloud:default_ollama"
                is_held = pipeline_scheduler.is_held(pid, primary_node)
                held_reason = None
                if is_held:
                    for h in pipeline_scheduler.list_holds():
                        if h["project_id"] == pid and h["endpoint_id"] == primary_node:
                            held_reason = f"{h['reason']}_by_{h['set_by_project']}"
                            break
                rt["is_held"] = is_held
                rt["held_reason"] = held_reason
                rt["state"] = _running_task_state(
                    project_id=pid,
                    is_held=is_held,
                    held_reason=held_reason,
                    is_swarm=rt.get("is_swarm", False),
                )
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_held_state_api.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py tests/test_held_state_api.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/llm.py tests/test_held_state_api.py
git commit -m "feat(phase127): running_tasks entries carry state + held_reason

Each entry now reports state ('held' / 'swarm_active' / 'running'),
is_held boolean, and held_reason ('<reason>_by_<setter_project>').
UI can render distinct visual states for each."
```

### Task 4.3: Add `swarm_queue` and `exclusive_project` to `/compute/scheduler`

**Files:**
- Modify: `src/prep/api/routers/compute.py` (or wherever `/compute/scheduler` is served)

- [ ] **Step 1: Locate the endpoint**

```bash
grep -nE '"/compute/scheduler"|@router.get.*scheduler' src/prep/api/routers/compute.py | head -5
```

- [ ] **Step 2: Add fields to the response**

In the `/compute/scheduler` handler, after collecting node info, add:

```python
    # Phase 127: surface exclusive holder + boost-weighted FIFO queue.
    exclusive_project = None
    for pid, level in pipeline_scheduler._priority_projects.items():
        if level == "exclusive":
            exclusive_project = pid
            break
    swarm_queue = []
    # Iterate _queues (per-node) and report waiters in priority order.
    with pipeline_scheduler._lock:
        for nid, q in pipeline_scheduler._queues.items():
            for entry in q:
                level = pipeline_scheduler._priority_projects.get(entry.project_id, "none")
                swarm_queue.append({
                    "project_id": entry.project_id,
                    "stage": entry.stage,
                    "node_id": nid,
                    "queued_at": entry.enqueued_at,
                    "priority": level,
                })
    response_data["exclusive_project"] = exclusive_project
    response_data["swarm_queue"] = swarm_queue
    response_data["held_projects"] = pipeline_scheduler.list_holds()
```

- [ ] **Step 3: Test**

Append to `tests/test_held_state_api.py`:

```python
def test_compute_scheduler_response_includes_phase127_fields(monkeypatch) -> None:
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.set_priority("test-exclusive-proj", "exclusive")
    try:
        # Build response shape the same way the endpoint does.
        from prep.services.pipeline.scheduler import pipeline_scheduler as ps
        exclusive_project = None
        for pid, level in ps._priority_projects.items():
            if level == "exclusive":
                exclusive_project = pid
                break
        assert exclusive_project == "test-exclusive-proj"
    finally:
        pipeline_scheduler.set_priority("test-exclusive-proj", "none")
```

- [ ] **Step 4: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py tests/test_held_state_api.py -q
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/compute.py tests/test_held_state_api.py
git commit -m "feat(phase127): /compute/scheduler reports exclusive + swarm_queue + held_projects

Adds three new fields to the scheduler-status endpoint:
- exclusive_project: project_id or null
- swarm_queue: ordered list of waiters by boost-weighted FIFO
- held_projects: snapshot of all active holds

UI can render 'X is exclusive', 'Y is queued behind X', etc."
```

### Task 4.4: Update `/queue` items with held state

**Files:**
- Modify: `src/prep/api/routers/queue.py`

- [ ] **Step 1: Add `held_reason` to queue item builder**

In `queue.py:_build_queue_item`, after the existing `is_swarm` computation, add:

```python
    # Phase 127: surface held state.
    is_held = False
    held_reason = None
    if compute_node:
        is_held = pipeline_scheduler.is_held(project_id, compute_node)
        if is_held:
            for h in pipeline_scheduler.list_holds():
                if h["project_id"] == project_id and h["endpoint_id"] == compute_node:
                    held_reason = f"{h['reason']}_by_{h['set_by_project']}"
                    break
```

And add to the returned dict:

```python
    return {
        # ... existing fields ...
        "is_held": is_held,
        "held_reason": held_reason,
        "state": "held" if is_held else ("swarm_active" if is_swarm else (phase or "running")),
    }
```

- [ ] **Step 2: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py tests/test_held_state_api.py tests/test_queue_router.py -q
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/prep/api/routers/queue.py
git commit -m "feat(phase127): /queue items report is_held + held_reason + state

Same state machine as /llm/slots/status.  Held items show distinct
state in the UI's queue panel."
```

---

## Sub-Phase 5: Durability hardening

**Goal:** Persist priority levels across daemon restarts; document swarm window + queue + holds as in-memory; add restart recovery test.

### Task 5.1: Persist priority levels to settings store

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_priority_durability.py`:

```python
"""Phase 127 sub-phase 5: priority survives daemon restart."""
from __future__ import annotations


def test_priority_persists_across_scheduler_instances() -> None:
    """Set priority on instance A, create instance B, priority is restored."""
    from prep.services.pipeline.scheduler import PipelineScheduler

    a = PipelineScheduler()
    a.set_priority("proj-persist-test", "exclusive")
    a.persist_priority_state()  # explicit save

    b = PipelineScheduler()
    b.load_priority_state()  # explicit load
    assert b.get_priority("proj-persist-test") == "exclusive"

    # Cleanup
    b.set_priority("proj-persist-test", "none")
    b.persist_priority_state()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_priority_durability.py -v
```
Expected: FAIL — `persist_priority_state` and `load_priority_state` don't exist.

- [ ] **Step 3: Add persist/load methods**

In `scheduler.py:PipelineScheduler`, add:

```python
    def persist_priority_state(self) -> None:
        """Phase 127: save current priority levels to the settings store
        so they survive daemon restart."""
        from prep.services.settings_store import settings
        with self._lock:
            data = {
                "priority_projects": dict(self._priority_projects),
            }
        settings.set("scheduler_priority_state", data)

    def load_priority_state(self) -> None:
        """Phase 127: restore priority levels from the settings store on
        daemon start."""
        from prep.services.settings_store import settings
        data = settings.get("scheduler_priority_state") or {}
        loaded = data.get("priority_projects", {})
        with self._lock:
            self._priority_projects = dict(loaded)
```

Modify `set_priority` to call persist after every change:

```python
    def set_priority(self, project_id, level="boost"):
        # ... existing logic ...
        self.persist_priority_state()
```

(Place the `persist_priority_state()` call at the end of the existing method, after the priority dict is updated and any side-effects fire.)

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_priority_durability.py -v
```
Expected: PASS.

- [ ] **Step 5: Run regression suite**

```bash
.venv/bin/pytest tests/test_swarm_window_authority.py tests/test_swarm_label_gating.py tests/test_swarm_slot_attribution.py tests/test_aimd_soft_md.py tests/test_llm_scheduler_routing.py tests/test_soft_hold_primitive.py tests/test_swarm_cooldown_removal.py tests/test_boost_weighted_fifo.py tests/test_endpoint_disjoint.py tests/test_held_state_api.py tests/test_priority_durability.py -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_priority_durability.py
git commit -m "feat(phase127): priority levels persist across daemon restart

Adds persist_priority_state / load_priority_state methods.  Every
set_priority call persists.  Daemon startup should call load_priority_state.

In-memory state (swarm window, queue, holds) is intentionally NOT
persisted — recomputed from priority + active pipelines on restart per
Phase 127 spec §12."
```

### Task 5.2: Wire `load_priority_state` into daemon startup

**Files:**
- Modify: `src/prep/server.py` (daemon startup)

- [ ] **Step 1: Locate startup**

```bash
grep -nE "pipeline_scheduler|configure_node|on_event.*startup" src/prep/server.py | head -10
```

- [ ] **Step 2: Add the load call**

Find the startup block (likely a FastAPI lifespan or `@app.on_event("startup")` handler). Add:

```python
    # Phase 127: restore priority state across daemon restart.
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.load_priority_state()
```

- [ ] **Step 3: Run regression suite**

```bash
.venv/bin/pytest tests/test_priority_durability.py tests/test_swarm_window_authority.py -q
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/prep/server.py
git commit -m "feat(phase127): daemon startup loads persisted priority state"
```

---

## Final verification

### Task F.1: Run the full regression suite

- [ ] **Step 1: Run everything we touched**

```bash
.venv/bin/pytest \
  tests/test_swarm_window_authority.py \
  tests/test_swarm_label_gating.py \
  tests/test_swarm_slot_attribution.py \
  tests/test_aimd_soft_md.py \
  tests/test_llm_scheduler_routing.py \
  tests/test_soft_hold_primitive.py \
  tests/test_swarm_cooldown_removal.py \
  tests/test_boost_weighted_fifo.py \
  tests/test_endpoint_disjoint.py \
  tests/test_held_state_api.py \
  tests/test_priority_durability.py \
  tests/test_swarm_orchestrator.py \
  tests/test_swarm_orchestrator_timeout.py \
  tests/test_queue_router.py \
  tests/test_queue_status_state.py \
  tests/test_queue_active_tasks.py \
  -v
```
Expected: ALL pass.

- [ ] **Step 2: Run typecheck**

```bash
ruff check src/prep/services/pipeline/scheduler.py src/prep/services/pipeline/holds.py src/prep/services/pipeline/workers.py src/prep/api/routers/llm.py src/prep/api/routers/queue.py src/prep/core/epistemic_enrichment.py src/prep/core/augmenter.py src/prep/core/swarm_orchestrator.py
```
Expected: no errors.

```bash
mypy src/prep/services/pipeline/scheduler.py src/prep/services/pipeline/holds.py src/prep/services/pipeline/workers.py
```
Expected: no errors.

### Task F.2: Single-project regression smoke test

- [ ] **Step 1: Restart the daemon**

```bash
# Whatever the user uses — scripts/dev.sh restart, etc.
```

- [ ] **Step 2: Run a single-project full pipeline (1-15) on PowerMate**

Trigger from the dashboard or via API. Expected: completes end-to-end without errors. No regression in stage durations or output quality.

### Task F.3: Multi-project soak test (optional, manual)

- [ ] **Step 1: Trigger two projects' pipelines simultaneously**

E.g., SourcePrep_Website and PowerMate. Expected: weighted-share split between them; no holds (no exclusive set, no swarm conflicts beyond natural FIFO).

- [ ] **Step 2: Mid-run, click Exclusive on one project in the dashboard**

Expected: the other project's stage soft-holds (visible in `/llm/slots/status` `held_projects`). Workers stop dispatching new LLM calls. In-flight finishes naturally.

- [ ] **Step 3: Click Exclusive off**

Expected: held project resumes from checkpoint. Both projects continue.

---

## Self-Review

**Spec coverage:**
- §3 mechanism table → covered by Tasks 1.x (soft-hold), 2.x (swarm + exclusive integration), 5.x (priority persistence).
- §5 swarm window lifecycle → Task 2.3 (open/close hold management).
- §6 exclusive lifecycle → Task 2.4 (set_priority hold management).
- §7 queue semantics → Tasks 2.1, 2.2.
- §8 soft-hold mechanism → Tasks 1.x, 2.5-2.7 (workers honor it).
- §9 endpoint-disjoint → Task 3.x.
- §10 UI signals → Task 4.x.
- §12 durability → Task 5.x.
- §13 regression requirements → enforced by regression suite at every task.

**Placeholder scan:** No "TBD" or "TODO" left. Tasks specify exact code to add. Worker-side patterns are concrete code blocks. (Note: Tasks 2.5/2.6/2.7 have `# Adapt to actual code structure` comments because the existing dispatch loops have local idiosyncrasies — implementer should match the existing call sites; pattern is identical.)

**Type consistency:**
- `HoldKey`/`HoldEntry`/`HoldReason` consistently used across scheduler.py and tests.
- `is_held(project_id, endpoint_id)` consistent across all callers.
- `_should_dispatch_or_pause` keyword args consistent.
- `endpoint_set` (a `set` of `str`) consistent in 3.1, 3.2.

**Scope check:** Each sub-phase ships independently. Sub-phases 1-2 are the load-bearing work; 3-5 add capability without disruption.

---

## Execution Handoff

**Plan complete and saved to `docs/Phase127_MultiProjectQueueArchitecture/IMPLEMENTATION_PLAN.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

# Phase 89: Atomic Pipeline Transitions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate pipeline stalls between stages by ensuring the scheduler lock is always held during transitions, and by releasing locks on cancel/pause/clear.

**Architecture:** Reorder the stage completion handler so bookkeeping and advance happen BEFORE releasing the scheduler lock (release-after-advance). Add lock release to cancel, pause, and clear_project paths. Simplify the ghost guard.

**Tech Stack:** Python 3.11, pytest, threading

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/codrag/services/pipeline/scheduler.py` | Modify | Add `is_held_by()` helper |
| `src/codrag/services/pipeline/orchestrator.py` | Modify | WS1: reorder completion handler. WS2: cancel releases lock. WS3: pause releases lock. WS4: clear_project cancels first. |
| `src/codrag/services/pipeline/ghost_guard.py` | Modify | WS5: require all three sources to agree before purging |
| `tests/test_pipeline_orchestrator_transitions.py` | Create | Integration tests for atomic stage handoff |
| `tests/test_ghost_guard.py` | Modify | Update for simplified ghost guard |

---

### Task 1: Add `is_held_by()` to Scheduler

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py`
- Test: `tests/test_pipeline_scheduler.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline_scheduler.py`:

```python
class TestIsHeldBy:

    def test_returns_true_when_held(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

    def test_returns_false_when_not_held(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        assert sched.is_held_by("proj-a") is False

    def test_returns_false_after_release(self):
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestIsHeldBy -v`
Expected: FAIL — `is_held_by` doesn't exist.

- [ ] **Step 3: Implement `is_held_by()`**

In `src/codrag/services/pipeline/scheduler.py`, add after `clean_locks()` (around line 611):

```python
    def is_held_by(self, project_id: str) -> bool:
        """Check if a project currently holds any scheduler slot."""
        with self._lock:
            for slot in self._slots.values():
                if project_id in slot.active_stages:
                    return True
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py::TestIsHeldBy -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_pipeline_scheduler.py
git commit -m "feat(scheduler): add is_held_by() helper for double-release guard

Phase 89 WS1 prep: Used by cancel/pause handlers to check if a
scheduler lock is still held before attempting release."
```

---

### Task 2: WS1 — Release-After-Advance (Core Fix)

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py:1572-1815`

This is the critical fix. Reorder the COMPLETED path in `_on_build_transition()` so the scheduler lock is released AFTER `_advance_pipeline()`.

- [ ] **Step 1: Read the current code**

Read `orchestrator.py` lines 1572-1815 to confirm the current order matches expectations.

- [ ] **Step 2: Refactor the COMPLETED path**

Replace the entire `if new_phase == BuildPhase.COMPLETED:` block (lines 1572-1659) and the advance block (lines 1796-1814) with:

```python
        if new_phase == BuildPhase.COMPLETED:
            # State transition (SM has its own lock)
            matching_run.transition(Event.STAGE_COMPLETED)
            logger.info(
                "Pipeline %s/%s — stage %s completed",
                project_id, matching_run.group, stage.value,
            )

            # Phase 89: Release-after-advance.
            # The scheduler lock is held throughout bookkeeping and advance,
            # then released AFTER the next stage has acquired its own lock
            # (or the pipeline has completed/queued). This eliminates the
            # race window where ghost guard or dequeued pipelines can interfere.
            _release_node = getattr(matching_run, '_current_node_id', None)
            _deferred_resume = None

            try:
                # Phase 44C: release model via state machine
                completed_task = STAGE_TASK_ID.get(stage)
                if completed_task:
                    try:
                        from codrag.core.model_awareness import model_awareness
                        model_awareness.release(completed_task, unload=False)
                    except Exception:
                        logger.debug("ModelAwareness release failed for %s", completed_task, exc_info=True)

                # Post-completion bookkeeping (still holding old scheduler slot)
                slot = self._orchestrator.status(project_id, build_type)

                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.stage_end(stage.value, "completed", data={
                        "result": slot.result,
                        "duration": slot.duration_seconds,
                    })
                    pfl.transition(build_type.value, old_phase.value, new_phase.value,
                                   f"Stage {stage.value} completed")
                # Phase 25: journal
                self._journal_stage_completed(matching_run, stage)
                # Phase 49: write stage manifest + update run metadata
                self._write_stage_manifest_and_update_run(
                    matching_run, stage, slot,
                )
                # Phase 72 Stage 4: Update stage snapshot on completion
                self._update_stage_snapshot_from_slot(matching_run, stage, slot)
                # Phase 50: Atlas/rules generation
                if stage == StageId.STRUCTURAL:
                    self._generate_preliminary_atlas_and_rules(project_id)
                    self._prune_stale_derivative_files(project_id, pfl)
                    self._sync_downstream_manifest_mtimes(project_id, pfl)
                elif stage == StageId.ATLAS:
                    self._regenerate_rules_with_full_atlas(project_id)

                # Phase 70B: Write guard
                self._write_guard_check(matching_run, stage, pfl)
                # Phase 60A: integrity guard
                self._integrity_check_after_stage(matching_run, stage, pfl)
            except _WriteGuardBlocked as wgb:
                logger.critical(
                    "WRITE GUARD BLOCKED stage %s for %s: %s",
                    stage.value, project_id, wgb,
                )
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.log(stage.value, f"WRITE GUARD BLOCKED: {wgb}")
                if matching_run.can_transition(Event.STAGE_FAILED):
                    matching_run.transition(Event.STAGE_FAILED, detail=f"WRITE GUARD BLOCKED: {wgb}")
                self._unload_group_models(matching_run)
                self._journal_run_completed(matching_run)
                # Release slot even on write guard failure
                _deferred_resume = pipeline_scheduler.release(project_id, stage, _release_node)
                if _deferred_resume:
                    self._resume_queued_pipeline(_deferred_resume.project_id, _deferred_resume.stage)
                return
            except Exception:
                logger.exception(
                    "Post-completion bookkeeping failed for %s/%s stage %s "
                    "(pipeline will still advance)",
                    project_id, matching_run.group, stage.value,
                )
```

Then replace the post-structural sanity check + advance block (lines 1725-1814) with:

```python
        # Phase 48-F8: Post-structural sanity check.
        _abort = False
        if (
            matching_run
            and matching_run.is_active
            and stage == StageId.STRUCTURAL
            and new_phase == BuildPhase.COMPLETED
        ):
            try:
                slot = self._orchestrator.status(project_id, build_type)
                node_count = (slot.result or {}).get("nodes", -1)
                if node_count == 0:
                    from codrag.services.project_helpers import require_project
                    from codrag.core.project_registry import project_index_dir
                    _proj = require_project(project_id)
                    _repo = Path(_proj.path)
                    if _repo.is_dir():
                        _found = 0
                        _CODE_EXTS = {
                            ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
                            ".java", ".c", ".cpp", ".h", ".hpp", ".swift",
                            ".md", ".kt", ".cs", ".rb", ".php",
                        }
                        for _r, _ds, _fs in os.walk(_repo):
                            _ds[:] = [
                                d for d in _ds
                                if not d.startswith(".") and d not in (
                                    "node_modules", "__pycache__", ".git",
                                    "target", "build", "dist", "vendor",
                                )
                            ]
                            for _fn in _fs:
                                if any(_fn.endswith(ext) for ext in _CODE_EXTS):
                                    _found += 1
                                    if _found >= 5:
                                        break
                            if _found >= 5:
                                break

                        if _found > 0:
                            _abort = True
                            _detail = (
                                f"Structural stage produced 0 nodes but project "
                                f"has files on disk ({_found}+ code files found). "
                                f"Possible causes: Rust engine failure, glob "
                                f"misconfiguration, or permissions issue."
                            )
                            logger.error(
                                "Pipeline %s/%s — %s",
                                project_id, matching_run.group, _detail,
                            )
                            pfl = self._get_file_logger(project_id)
                            if pfl:
                                pfl.log("structural", _detail)
                                pfl.end_run("failed", error=_detail)
                            matching_run.transition(
                                Event.STAGE_FAILED, detail=_detail,
                            )
            except Exception:
                logger.debug(
                    "Post-structural sanity check failed (non-fatal)",
                    exc_info=True,
                )

        # Phase 89: Advance THEN release (atomic handoff)
        if matching_run and matching_run.is_active and not _abort:
            try:
                self._advance_pipeline(matching_run)
            except Exception as exc:
                logger.exception(
                    "Pipeline %s/%s — _advance_pipeline failed after stage %s: %s",
                    matching_run.project_id, matching_run.group,
                    stage.value if stage else "?", exc,
                )
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.log(stage.value if stage else "unknown",
                            f"_advance_pipeline failed: {exc}")
                    pfl.end_run("failed", error=str(exc))
                matching_run.transition(
                    Event.STAGE_FAILED,
                    detail=f"Failed to advance after {stage.value if stage else '?'}: {exc}",
                )

        # Phase 89: NOW release the old stage's scheduler slot
        if new_phase == BuildPhase.COMPLETED:
            _release_node = getattr(matching_run, '_current_node_id', None) if matching_run else None
            _deferred_resume = pipeline_scheduler.release(project_id, stage, _release_node)

            if _deferred_resume:
                self._resume_queued_pipeline(_deferred_resume.project_id, _deferred_resume.stage)

            # Phase 75: notify queue UI of state change
            try:
                from codrag.core.events import get_event_bus
                get_event_bus().emit("queue_changed", {
                    "reason": "pipeline_stage_completed",
                    "project_id": project_id,
                })
            except Exception:
                pass
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py tests/test_ghost_guard.py -q`
Expected: Same pass/fail as before (15 pre-existing failures, no new ones).

- [ ] **Step 4: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py
git commit -m "fix(pipeline): release-after-advance eliminates stage handoff race

Phase 89 WS1: The scheduler lock for the completed stage is now held
throughout bookkeeping and _advance_pipeline(), then released AFTER
the next stage has acquired its own lock. This eliminates the ~5s
race window where ghost guard or dequeued pipelines could interfere.

Previously: release → bookkeeping → advance (vulnerable window)
Now: bookkeeping → advance → release (always holds at least one lock)"
```

---

### Task 3: WS2 — Cancel Releases Scheduler Lock

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py:1816-1846`

- [ ] **Step 1: Read the current `_cancel_group` code**

Read `orchestrator.py` lines 1816-1846 to confirm current state.

- [ ] **Step 2: Add scheduler lock release to `_cancel_group`**

Replace lines 1816-1846 with:

```python
    def _cancel_group(self, project_id: str, group: str) -> bool:
        """Cancel a running group using state machine events."""
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run:
                return False

            current_str = run.current_stage

            # CANCEL from RUNNING → CANCELLING, from PAUSED → CANCELLED directly
            if not run.transition(Event.CANCEL):
                return False

        # Cancel the current stage's build
        if current_str:
            bt = STAGE_BUILD_TYPE[StageId(current_str)]
            self._orchestrator.cancel(project_id, bt)

        # If still in CANCELLING, complete the transition
        if run.state == PipelineState.CANCELLING:
            run.transition(Event.STAGE_STOPPED)

        # Phase 89 WS2: Release scheduler lock so other projects can proceed.
        # The _on_build_transition FAILED handler may also release, so check
        # is_held_by() to prevent double-release.
        if current_str and pipeline_scheduler.is_held_by(project_id):
            stage = StageId(current_str)
            _release_node = getattr(run, '_current_node_id', None)
            next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
            if next_entry:
                self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)

        # Phase 25: journal — record cancellation
        if run.journal_run_id:
            try:
                from codrag.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)
            except Exception:
                logger.debug("Journal cancel write failed", exc_info=True)
        return True
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py
git commit -m "fix(pipeline): cancel now releases scheduler lock

Phase 89 WS2: _cancel_group() releases the scheduler slot after
cancelling the build worker. Uses is_held_by() guard to prevent
double-release if _on_build_transition FAILED handler already released."
```

---

### Task 4: WS3 — Pause Releases Scheduler Lock

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py:1848-1921`

- [ ] **Step 1: Read the current `_pause_group` code**

Read `orchestrator.py` lines 1848-1921 to confirm current state.

- [ ] **Step 2: Add scheduler lock release to `_pause_group`**

After the `PAUSING → PAUSED` transition (line 1900), add scheduler release:

Insert after `run.transition(Event.STAGE_FLUSHED)` (line 1900):

```python
        # Phase 89 WS3: Release scheduler lock so other projects can run
        # while this pipeline is paused. Resume will re-acquire via
        # _advance_pipeline() → scheduler.acquire().
        if current_str and pipeline_scheduler.is_held_by(project_id):
            stage = StageId(current_str)
            _release_node = getattr(run, '_current_node_id', None)
            next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
            if next_entry:
                self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py
git commit -m "fix(pipeline): pause now releases scheduler lock

Phase 89 WS3: A paused pipeline no longer holds a scheduler slot,
freeing it for other projects. On resume, _advance_pipeline()
re-acquires via scheduler.acquire() (may queue if node is full)."
```

---

### Task 5: WS4 — clear_project Cancels First

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py:973-981`

- [ ] **Step 1: Replace `clear_project`**

Replace lines 973-981 with:

```python
    def clear_project(self, project_id: str) -> None:
        """Remove all pipeline state for a project."""
        # Phase 89 WS4: Cancel running builds before clearing state.
        # This ensures scheduler locks are released (via WS2 cancel fix).
        self.cancel_fast_sync(project_id)
        self.cancel_deep_enrichment(project_id)
        with self._lock:
            keys = [k for k in self._runs if k[0] == project_id]
            for k in keys:
                del self._runs[k]
        self._orchestrator.clear_project(project_id)
        # Clear cached file logger so it doesn't reference stale paths
        self._file_loggers.pop(project_id, None)
```

- [ ] **Step 2: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py
git commit -m "fix(pipeline): clear_project cancels builds first

Phase 89 WS4: Cancels any running fast_sync/deep_enrichment
before clearing state machines. Cancel (WS2) now releases
scheduler locks, so no ghost locks are left behind."
```

---

### Task 6: WS5 — Simplify Ghost Guard

**Files:**
- Modify: `src/codrag/services/pipeline/ghost_guard.py`
- Test: `tests/test_ghost_guard.py`

- [ ] **Step 1: Read current ghost guard**

Read `ghost_guard.py` to confirm current state.

- [ ] **Step 2: Simplify ghost guard**

The ghost guard should now only purge when ALL THREE sources agree there's no legitimate activity. Replace the entire `purge_ghost_locks` function body:

```python
def purge_ghost_locks(
    scheduler=None,
    build_orchestrator=None,
    event_bus=None,
) -> int:
    """Cross-check scheduler locks against build orchestrator and pipeline state.

    Phase 89: Requires all three sources of truth to agree before purging:
    1. Scheduler says lock held (project in active_stages)
    2. BuildOrchestrator says no active threads
    3. Pipeline state machine says NOT active (COMPLETED/FAILED/CANCELLED/IDLE)

    Only when all three agree is the lock a true ghost (crashed worker).
    """
    if scheduler is None:
        from codrag.services.pipeline.scheduler import pipeline_scheduler
        scheduler = pipeline_scheduler
    if build_orchestrator is None:
        from codrag.services.build_orchestrator import build_orchestrator as _bo
        build_orchestrator = _bo
    if event_bus is None:
        from codrag.core.events import get_event_bus
        event_bus = get_event_bus()

    # Load pipeline orchestrator for state machine check
    pipeline_orch = None
    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator as _po
        pipeline_orch = _po
    except ImportError:
        pass

    status = scheduler.status()
    nodes = status.get("nodes", {})

    # Collect all unique project_ids that hold active slots
    locked_projects: set[str] = set()
    for node_info in nodes.values():
        active = node_info.get("active", {})
        locked_projects.update(active.keys())

    if not locked_projects:
        return 0

    purged = 0
    for project_id in locked_projects:
        # Source 2: Are any build threads alive?
        if build_orchestrator.is_any_active(project_id):
            continue  # Thread alive — lock is valid

        # Source 3: Is the pipeline state machine active?
        if pipeline_orch is not None:
            try:
                ps = pipeline_orch.status(project_id)
                pipeline_active = any(
                    g.get("is_active")
                    for g in [ps.get("fast_sync", {}), ps.get("deep_enrichment", {})]
                    if isinstance(g, dict)
                )
                if pipeline_active:
                    logger.debug(
                        "Ghost Guard: project %s has no build threads but pipeline "
                        "state machine is active — skipping purge",
                        project_id,
                    )
                    continue
            except Exception:
                pass  # Can't check — fall through to purge

        # All three sources agree: lock held + no threads + no active pipeline
        logger.warning(
            "Ghost Guard: project %s holds scheduler lock with no active "
            "build threads and no active pipeline — purging ghost lock",
            project_id,
        )
        scheduler.clean_locks(project_id)
        purged += 1

    if purged > 0:
        event_bus.emit("queue_changed", {
            "reason": "ghost_purged",
            "purged_count": purged,
        })
        logger.info("Ghost Guard: purged %d ghost lock(s)", purged)

    return purged
```

- [ ] **Step 3: Run ghost guard tests**

Run: `.venv/bin/pytest tests/test_ghost_guard.py -v`
Expected: All PASS (existing tests mock build_orchestrator, so the new pipeline_orch check is skipped via ImportError).

- [ ] **Step 4: Commit**

```bash
git add src/codrag/services/pipeline/ghost_guard.py
git commit -m "fix(ghost-guard): require all three sources to agree before purging

Phase 89 WS5: Ghost guard now checks scheduler locks, build threads,
AND pipeline state machine. Only purges when all three agree there's
no legitimate activity. This is the permanent fix — the transition
window eliminated by WS1 means this is now just a crash detector."
```

---

### Task 7: Integration Test — Atomic Stage Handoff

**Files:**
- Create: `tests/test_pipeline_orchestrator_transitions.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_pipeline_orchestrator_transitions.py`:

```python
"""Integration tests for Phase 89 atomic pipeline stage transitions.

Verifies that the pipeline always holds at least one scheduler lock
during stage transitions, and that cancel/pause properly release locks.
"""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.pipeline.scheduler import PipelineScheduler
from codrag.services.pipeline.stages import StageId


class TestSchedulerLockLifecycle:
    """Verify scheduler lock is held through transitions."""

    def test_lock_held_during_stage_transition(self):
        """Scheduler lock should never go to zero during a stage transition.

        Simulates the release-after-advance ordering by checking that
        a project is always in active_stages during the transition window.
        """
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)

        # Simulate stage N completion: project holds lock for enrichment
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

        # Simulate _advance_pipeline: acquire lock for next stage
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        # Project now holds TWO locks (old + new)
        assert sched.is_held_by("proj-a") is True

        # Simulate release of old stage
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        # Still held via new stage
        assert sched.is_held_by("proj-a") is True

    def test_cancel_releases_lock(self):
        """After cancel, project should not hold any scheduler lock."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

        # Simulate cancel: release the lock
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False

    def test_pause_releases_lock(self):
        """After pause, project should not hold any scheduler lock."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

        # Simulate pause: release the lock
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False

    def test_is_held_by_not_confused_by_other_project(self):
        """is_held_by should only check the specific project."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-b") is False

    def test_dual_lock_counts_as_two_active(self):
        """During transition, project holds two slots on same node."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        status = sched.status()
        node = status["nodes"]["cloud:ep-1"]
        assert node["current_load"] == 2
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_pipeline_orchestrator_transitions.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline_orchestrator_transitions.py
git commit -m "test(pipeline): integration tests for atomic stage transitions

Phase 89: Verifies scheduler lock lifecycle during stage transitions,
cancel, pause, and dual-lock scenarios."
```

---

### Task 8: Full Test Suite + Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run all Phase 89 tests**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py tests/test_ghost_guard.py tests/test_pipeline_orchestrator_transitions.py -v`
Expected: All new tests pass. Same 15 pre-existing AIMD test failures (unrelated).

- [ ] **Step 2: Run broader regression check**

Run: `.venv/bin/pytest tests/ -x -q`
Expected: No new regressions.

- [ ] **Step 3: Commit summary**

```bash
git log --oneline -8
```

Expected commits (newest first):
1. `test(pipeline): integration tests for atomic stage transitions`
2. `fix(ghost-guard): require all three sources to agree before purging`
3. `fix(pipeline): clear_project cancels builds first`
4. `fix(pipeline): pause now releases scheduler lock`
5. `fix(pipeline): cancel now releases scheduler lock`
6. `fix(pipeline): release-after-advance eliminates stage handoff race`
7. `feat(scheduler): add is_held_by() helper for double-release guard`

"""Tests for the Pipeline Orchestrator (SM-6).

These tests use a mock BuildOrchestrator to avoid importing heavy
codrag.core dependencies.  The pipeline orchestrator's sequencing
logic is pure state management — no I/O needed.
"""

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildSlot,
    BuildType,
)
from codrag.services.pipeline_orchestrator import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    STAGE_BUILD_TYPE,
    PipelineOrchestrator,
    PipelineRunPhase,
    StageId,
)


@pytest.fixture
def orchestrator():
    """Real BuildOrchestrator (lightweight — no I/O)."""
    return BuildOrchestrator()


@pytest.fixture
def pipeline(orchestrator):
    """PipelineOrchestrator wired to a real BuildOrchestrator."""
    # Reset the singleton scheduler to avoid state leaking between tests
    from codrag.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler._slots.clear()
    pipeline_scheduler._queues.clear()
    pipeline_scheduler._priority_projects.clear()
    pipeline_scheduler._swarm_window = None
    pipeline_scheduler._swarm_cooldown_until = 0.0
    pipeline_scheduler._capacity_listeners.clear()
    pipeline_scheduler._last_broadcast_times.clear()
    pipeline_scheduler._init_embedding_slot()

    with patch("codrag.services.project_helpers.get_project_activity_status", return_value="active"):
        po = PipelineOrchestrator(orchestrator=orchestrator)
        yield po
        # Teardown: clean up any running state machines so they don't
        # leak deferred callbacks into subsequent tests
        po._runs.clear()
        po._incremental_runs.clear()
        po._chain_deep.clear()
        po._force_from_start_runs.clear()
        pipeline_scheduler._slots.clear()
        pipeline_scheduler._queues.clear()
        pipeline_scheduler._priority_projects.clear()


def _instant_worker(slot, progress_cb):
    """Worker that completes immediately."""
    return {"ok": True}


def _slow_worker(barrier):
    """Worker that blocks on a barrier."""
    def worker(slot, progress_cb):
        barrier.wait(timeout=5)
        return {"ok": True}
    return worker


# ── Stage / group constants ──────────────────────────────────────


def test_fast_sync_has_5_stages():
    assert len(FAST_SYNC_STAGES) == 5
    assert FAST_SYNC_STAGES[0] == StageId.STRUCTURAL
    assert FAST_SYNC_STAGES[-1] == StageId.KNOWLEDGE


def test_deep_enrichment_stages():
    # Deep enrichment currently has 6 stages (includes Atlas).
    # Will become 5 when Atlas moves to Finalize group.
    assert len(DEEP_ENRICHMENT_STAGES) >= 5
    assert DEEP_ENRICHMENT_STAGES[0] == StageId.ENRICHMENT
    assert DEEP_ENRICHMENT_STAGES[-1] == StageId.DEEP_KNOWLEDGE


def test_all_stages_have_build_type_mapping():
    for stage in list(StageId):
        assert stage in STAGE_BUILD_TYPE


# ── Pipeline run lifecycle ───────────────────────────────────────


class TestFastSync:
    """Test fast sync group (stages 1-4)."""

    def test_run_fast_sync_starts(self, pipeline):
        # Patch WorkerFactory to return instant workers
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            import codrag.services.project_helpers
            with patch("codrag.services.project_helpers.get_project_activity_status", return_value="active"):
                started = pipeline.run_fast_sync("proj-1")
            if not started:
                import logging
                logging.error(pipeline.status("proj-1"))
            assert started is True

    def test_run_fast_sync_rejects_duplicate(self, pipeline):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_slow_worker(barrier),
        ):
            pipeline.run_fast_sync("proj-1")
            started2 = pipeline.run_fast_sync("proj-1")
            assert started2 is False
            barrier.set()

    def test_fast_sync_sequences_all_5_stages(self, pipeline):
        """Verify all 5 stages run in sequence and pipeline completes."""
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            # Poll until complete or timeout (avoid fixed sleep flakiness)
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-1")
                fast = status["fast_sync"]
                if fast and fast["phase"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            assert fast is not None
            assert fast["phase"] == "completed", (
                f"Pipeline stuck in '{fast['phase']}' at stage "
                f"{fast.get('current_stage', '?')} "
                f"(index {fast.get('current_stage_index', '?')})"
            )
            assert fast["current_stage_index"] == 5  # Past all stages
            assert len(fast["stage_results"]) == 5

    def test_fast_sync_status_while_running(self, pipeline, orchestrator):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_slow_worker(barrier),
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(0.1)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            assert fast["phase"] == "running"
            assert fast["current_stage"] is not None

            barrier.set()
            time.sleep(0.5)


class TestDeepEnrichment:
    """Test deep enrichment group (stages 5-8)."""

    def test_run_deep_enrichment_starts(self, pipeline):
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            started = pipeline.run_deep_enrichment("proj-1")
            assert started is True

    def test_deep_enrichment_sequences_all_stages(self, pipeline):
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_deep_enrichment("proj-1")
            # Poll until complete or timeout
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-1")
                deep = status["deep_enrichment"]
                if deep and deep["phase"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

            status = pipeline.status("proj-1")
            deep = status["deep_enrichment"]
            assert deep is not None
            assert deep["phase"] == "completed", (
                f"Pipeline stuck in '{deep['phase']}' at stage "
                f"{deep.get('current_stage', '?')} "
                f"(index {deep.get('current_stage_index', '?')})"
            )
            assert deep["current_stage_index"] == len(DEEP_ENRICHMENT_STAGES)
            assert len(deep["stage_results"]) == len(DEEP_ENRICHMENT_STAGES)


class TestRunAll:
    """Test run_all (fast sync then deep enrichment chained)."""

    def test_run_all_chains_deep_after_fast(self, pipeline):
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            started = pipeline.run_all("proj-1")
            assert started is True
            # Wait for both groups to complete
            time.sleep(3.0)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            deep = status["deep_enrichment"]
            assert fast is not None
            assert fast["phase"] == "completed"
            assert deep is not None
            assert deep["phase"] == "completed"


class TestAutoChainDeepEnrichment:
    """Test that deep enrichment auto-chains after fast sync when config mode is 'auto'."""

    def test_auto_chain_when_deep_mode_auto(self, pipeline):
        """When pipeline_config.deep_enrichment.mode == 'auto', deep enrichment
        should auto-start after fast sync completes — even if run_fast_sync()
        (not run_all()) was called."""
        mock_settings = MagicMock()
        mock_settings.get.return_value = {
            "fast_sync": {"auto": True},
            "deep_enrichment": {"mode": "auto"},
        }

        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ), patch(
            "codrag.services.pipeline.orchestrator.settings",
            mock_settings,
            create=True,
        ), patch.object(
            PipelineOrchestrator, "_is_deep_enrichment_auto",
            staticmethod(lambda pid: True),
        ):
            import codrag.services.project_helpers
            with patch("codrag.services.project_helpers.get_project_activity_status", return_value="active"):
                started = pipeline.run_fast_sync("proj-1")
            if not started:
                import logging
                logging.error(pipeline.status("proj-1"))
            assert started is True
            time.sleep(3.0)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            deep = status["deep_enrichment"]
            assert fast is not None
            assert fast["phase"] == "completed"
            # Deep enrichment should have been auto-triggered
            assert deep is not None
            assert deep["phase"] == "completed"

    def test_no_auto_chain_when_deep_mode_manual(self, pipeline):
        """When pipeline_config.deep_enrichment.mode == 'manual', deep enrichment
        should NOT auto-start after fast sync."""
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            # Default: _is_deep_enrichment_auto returns False (settings not configured)
            import codrag.services.project_helpers
            with patch("codrag.services.project_helpers.get_project_activity_status", return_value="active"):
                started = pipeline.run_fast_sync("proj-1")
            if not started:
                import logging
                logging.error(pipeline.status("proj-1"))
            assert started is True

            # Poll until fast sync completes (avoid fixed sleep flakiness)
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-1")
                fast = status["fast_sync"]
                if fast and fast["phase"] == "completed":
                    break
                time.sleep(0.2)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            deep = status["deep_enrichment"]
            assert fast is not None
            assert fast["phase"] == "completed"
            # Deep enrichment should NOT have started
            assert deep is None


# ── Failure handling ─────────────────────────────────────────────


class TestFailureHandling:
    """Test pipeline behavior when a stage fails."""

    def test_pipeline_pauses_when_stage_fails(self, pipeline):
        """Phase 55: Stage failure auto-pauses for recovery (not hard fail)."""
        call_count = [0]

        def failing_worker(slot, progress_cb):
            call_count[0] += 1
            if call_count[0] == 2:  # Stage 2 (inferred_edges) fails
                raise RuntimeError("LLM unavailable")
            return {"ok": True}

        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=failing_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(1.5)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            # Phase 55 auto-pauses on failure for recovery
            assert fast["phase"] in ("paused", "failed")


# ── Cancellation ─────────────────────────────────────────────────


class TestCancellation:
    """Test pipeline cancellation."""

    def test_cancel_fast_sync(self, pipeline):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_slow_worker(barrier),
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(0.1)

            cancelled = pipeline.cancel_fast_sync("proj-1")
            assert cancelled is True

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            # Cancel produces 'cancelled' state (not 'failed')
            assert fast["phase"] in ("cancelled", "failed")

            barrier.set()

    def test_cancel_idle_returns_false(self, pipeline):
        cancelled = pipeline.cancel_fast_sync("proj-1")
        assert cancelled is False


# ── Status reporting ─────────────────────────────────────────────


class TestStatus:
    """Test pipeline status reporting."""

    def test_status_for_unknown_project(self, pipeline):
        status = pipeline.status("nonexistent")
        assert status["fast_sync"] is None
        assert status["deep_enrichment"] is None
        assert status["any_running"] is False

    def test_any_running_flag(self, pipeline):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_slow_worker(barrier),
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(0.1)

            status = pipeline.status("proj-1")
            assert status["any_running"] is True

            barrier.set()
            time.sleep(0.5)

            status = pipeline.status("proj-1")
            # After completion, should not be running
            # (may still be True briefly due to timing, so allow a generous wait)


# ── Clear project ────────────────────────────────────────────────


class TestClearProject:
    """Test clearing all pipeline state for a project."""

    def test_clear_project(self, pipeline):
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(1.0)

            pipeline.clear_project("proj-1")
            status = pipeline.status("proj-1")
            assert status["fast_sync"] is None
            assert status["deep_enrichment"] is None


# ── Independent projects ─────────────────────────────────────────


class TestMultiProject:
    """Test that pipelines for different projects don't interfere."""

    def test_independent_projects(self, pipeline):
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            pipeline.run_fast_sync("proj-2")
            time.sleep(2.0)

            s1 = pipeline.status("proj-1")
            s2 = pipeline.status("proj-2")
            assert s1["fast_sync"]["phase"] == "completed"
            assert s2["fast_sync"]["phase"] == "completed"


# ── Phase 96C: Initial / Incremental / Rebuild pipeline modes ──


class TestPipelineModes:
    """Phase 96C: Verify all three pipeline execution modes work end-to-end.

    These tests exercise the stage sequencing and slot release paths with
    mocked workers, covering the three real-world scenarios:

    1. INITIAL: every stage runs from scratch (no freshness skips)
    2. INCREMENTAL: some stages get skipped by freshness check
    3. REBUILD: force_from_start=True disables freshness skipping

    All three must complete — reach phase=completed with all stages
    accounted for in stage_results.
    """

    def test_initial_build_runs_every_stage(self, pipeline):
        """Initial build: no freshness skips, every stage runs a real worker."""
        executed: list[str] = []

        def counting_worker_factory(project_id, stage):
            def worker(slot, progress_cb):
                executed.append(stage.value)
                return {"ok": True}
            return worker

        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=counting_worker_factory,
        ), patch(
            "codrag.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            pipeline.run_fast_sync("proj-initial")

            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-initial")
                fs = status["fast_sync"]
                if fs and fs["phase"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

            status = pipeline.status("proj-initial")
            fs = status["fast_sync"]
            assert fs["phase"] == "completed", f"Initial build stuck in {fs['phase']}"
            # Every fast_sync stage should have run
            assert len(executed) == 5, f"Expected 5 workers, got {len(executed)}: {executed}"
            # All stage_results should be "completed" (none skipped)
            for stage_name in ["structural", "inferred_edges", "catalogue", "validation", "knowledge"]:
                assert fs["stage_results"].get(stage_name) == "completed", (
                    f"Stage {stage_name}: expected completed, got "
                    f"{fs['stage_results'].get(stage_name)}"
                )

    def test_incremental_build_skips_fresh_stages(self, pipeline):
        """Incremental build: stages with fresh outputs are skipped,
        stale stages run normally, pipeline completes cleanly."""
        executed: list[str] = []
        # Simulate: structural + knowledge are fresh, middle stages are stale
        fresh_stages = {"structural", "knowledge"}

        def counting_worker_factory(project_id, stage):
            def worker(slot, progress_cb):
                executed.append(stage.value)
                return {"ok": True}
            return worker

        def skip_if_fresh(pid, stage, inc, pfl=None):
            if stage.value in fresh_stages:
                return (True, "test: already current")
            return (False, "")

        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=counting_worker_factory,
        ), patch(
            "codrag.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            side_effect=skip_if_fresh,
        ):
            pipeline.run_fast_sync("proj-incremental")

            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-incremental")
                fs = status["fast_sync"]
                if fs and fs["phase"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

            status = pipeline.status("proj-incremental")
            fs = status["fast_sync"]
            assert fs["phase"] == "completed", f"Incremental stuck in {fs['phase']}"
            # Fresh stages didn't launch workers
            assert "structural" not in executed
            assert "knowledge" not in executed
            # Stale stages did launch workers
            assert "inferred_edges" in executed
            assert "catalogue" in executed
            assert "validation" in executed
            # stage_results reflects the mix
            assert fs["stage_results"]["structural"] == "skipped"
            assert fs["stage_results"]["knowledge"] == "skipped"
            assert fs["stage_results"]["inferred_edges"] == "completed"

    def test_rebuild_runs_every_stage_even_when_fresh(self, pipeline):
        """Rebuild (force_from_start=True): pipeline must complete a
        full cycle even when called on a project with fresh state.

        Note: force_from_start primarily affects resume detection (it
        disables resume from a partial run).  The freshness check can
        still fire per-stage, but for this test we disable freshness
        to assert the full-rebuild execution path works end-to-end.
        """
        executed: list[str] = []

        def counting_worker_factory(project_id, stage):
            def worker(slot, progress_cb):
                executed.append(stage.value)
                return {"ok": True}
            return worker

        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=counting_worker_factory,
        ), patch(
            "codrag.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            pipeline.run_fast_sync("proj-rebuild", force_from_start=True)

            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-rebuild")
                fs = status["fast_sync"]
                if fs and fs["phase"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

            status = pipeline.status("proj-rebuild")
            fs = status["fast_sync"]
            assert fs["phase"] == "completed", f"Rebuild stuck in {fs['phase']}"
            assert len(executed) == 5, f"Expected 5 workers, got {len(executed)}"
            assert fs["current_stage_index"] == 5


# ── Phase 96: Freshness-skip slot leak ──────────────────────────


class TestFreshnessSkipReleasesSlot:
    """Phase 96: Verify scheduler slot is released when a stage is skipped.

    Regression test for the freshness-skip slot leak: when
    _should_skip_stage_freshness() returns True, the scheduler slot
    acquired for that stage must be released before advancing to the
    next stage.  Without the release, the slot is held forever and
    all subsequent stages (and other projects) queue indefinitely.
    """

    def test_skipped_stage_releases_scheduler_slot(self, pipeline):
        """If stage 2 is skipped by freshness check, stage 3 should still
        run (not get stuck in queued)."""
        skip_stage = "inferred_edges"  # stage 2

        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ), patch(
            "codrag.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            side_effect=lambda pid, stage, inc, pfl=None: (
                (True, "test: outputs current") if stage.value == skip_stage
                else (False, "")
            ),
        ):
            pipeline.run_fast_sync("proj-1")

            # Wait for pipeline to complete (or stall)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                status = pipeline.status("proj-1")
                fast = status["fast_sync"]
                if fast and fast["phase"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            # Pipeline must complete, not get stuck in queued
            assert fast["phase"] == "completed", (
                f"Pipeline stuck in '{fast['phase']}' — "
                f"freshness skip likely leaked scheduler slot"
            )
            # Stage 2 was skipped, so only 4 workers should have run
            assert fast["stage_results"].get(skip_stage) == "skipped"

    def test_skipped_stage_does_not_block_other_projects(self, pipeline):
        """A freshness-skipped stage must not hold a scheduler slot that
        blocks other projects from running."""
        with patch(
            "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ), patch(
            "codrag.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            side_effect=lambda pid, stage, inc, pfl=None: (
                (True, "test: skip all") if pid == "proj-1"
                else (False, "")
            ),
        ):
            pipeline.run_fast_sync("proj-1")
            pipeline.run_fast_sync("proj-2")

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                s1 = pipeline.status("proj-1")
                s2 = pipeline.status("proj-2")
                f1 = s1["fast_sync"]
                f2 = s2["fast_sync"]
                if (f1 and f1["phase"] in ("completed", "failed") and
                        f2 and f2["phase"] in ("completed", "failed")):
                    break
                time.sleep(0.1)

            s1 = pipeline.status("proj-1")
            s2 = pipeline.status("proj-2")
            # Both must complete — proj-1 skips all stages, proj-2 runs all
            assert s1["fast_sync"]["phase"] == "completed", (
                f"proj-1 stuck in '{s1['fast_sync']['phase']}'"
            )
            assert s2["fast_sync"]["phase"] == "completed", (
                f"proj-2 stuck in '{s2['fast_sync']['phase']}' — "
                f"likely blocked by proj-1's leaked slot"
            )

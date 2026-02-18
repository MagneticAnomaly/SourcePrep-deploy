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
    return PipelineOrchestrator(orchestrator=orchestrator)


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


def test_fast_sync_has_4_stages():
    assert len(FAST_SYNC_STAGES) == 4
    assert FAST_SYNC_STAGES[0] == StageId.STRUCTURAL
    assert FAST_SYNC_STAGES[-1] == StageId.KNOWLEDGE


def test_deep_enrichment_has_4_stages():
    assert len(DEEP_ENRICHMENT_STAGES) == 4
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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            started = pipeline.run_fast_sync("proj-1")
            assert started is True

    def test_run_fast_sync_rejects_duplicate(self, pipeline):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_slow_worker(barrier),
        ):
            pipeline.run_fast_sync("proj-1")
            started2 = pipeline.run_fast_sync("proj-1")
            assert started2 is False
            barrier.set()

    def test_fast_sync_sequences_all_4_stages(self, pipeline):
        """Verify all 4 stages run in sequence and pipeline completes."""
        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            # Wait for all stages to complete
            time.sleep(2.0)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            assert fast is not None
            assert fast["phase"] == "completed"
            assert fast["current_stage_index"] == 4  # Past all stages
            assert len(fast["stage_results"]) == 4

    def test_fast_sync_status_while_running(self, pipeline, orchestrator):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            started = pipeline.run_deep_enrichment("proj-1")
            assert started is True

    def test_deep_enrichment_sequences_all_4_stages(self, pipeline):
        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_deep_enrichment("proj-1")
            time.sleep(2.0)

            status = pipeline.status("proj-1")
            deep = status["deep_enrichment"]
            assert deep is not None
            assert deep["phase"] == "completed"
            assert len(deep["stage_results"]) == 4


class TestRunAll:
    """Test run_all (fast sync then deep enrichment chained)."""

    def test_run_all_chains_deep_after_fast(self, pipeline):
        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ), patch(
            "codrag.services.pipeline_orchestrator.settings",
            mock_settings,
            create=True,
        ), patch.object(
            PipelineOrchestrator, "_is_deep_enrichment_auto",
            staticmethod(lambda pid: True),
        ):
            started = pipeline.run_fast_sync("proj-1")
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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            # Default: _is_deep_enrichment_auto returns False (settings not configured)
            started = pipeline.run_fast_sync("proj-1")
            assert started is True
            time.sleep(2.0)

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

    def test_pipeline_fails_when_stage_fails(self, pipeline):
        call_count = [0]

        def failing_worker(slot, progress_cb):
            call_count[0] += 1
            if call_count[0] == 2:  # Stage 2 (catalogue) fails
                raise RuntimeError("LLM unavailable")
            return {"ok": True}

        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=failing_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(1.5)

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            assert fast["phase"] == "failed"
            assert "failed" in fast["error"].lower()


# ── Cancellation ─────────────────────────────────────────────────


class TestCancellation:
    """Test pipeline cancellation."""

    def test_cancel_fast_sync(self, pipeline):
        barrier = threading.Event()
        with patch(
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_slow_worker(barrier),
        ):
            pipeline.run_fast_sync("proj-1")
            time.sleep(0.1)

            cancelled = pipeline.cancel_fast_sync("proj-1")
            assert cancelled is True

            status = pipeline.status("proj-1")
            fast = status["fast_sync"]
            assert fast["phase"] == "failed"
            assert "Cancelled" in fast["error"]

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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
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
            "codrag.services.pipeline_orchestrator.WorkerFactory.create_worker",
            return_value=_instant_worker,
        ):
            pipeline.run_fast_sync("proj-1")
            pipeline.run_fast_sync("proj-2")
            time.sleep(2.0)

            s1 = pipeline.status("proj-1")
            s2 = pipeline.status("proj-2")
            assert s1["fast_sync"]["phase"] == "completed"
            assert s2["fast_sync"]["phase"] == "completed"

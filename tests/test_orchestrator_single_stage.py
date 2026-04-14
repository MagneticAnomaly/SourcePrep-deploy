"""Tests for PipelineOrchestrator.run_single_stage (Phase 105a)."""
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.build_orchestrator import BuildOrchestrator
from codrag.services.pipeline_orchestrator import (
    PipelineOrchestrator,
    StageId,
)


@pytest.fixture
def pipeline():
    return PipelineOrchestrator(BuildOrchestrator())


def test_run_single_stage_rejects_non_finalize_stages(pipeline):
    """Only finalize stages can be run solo."""
    with pytest.raises(ValueError, match="not a finalize stage"):
        pipeline.run_single_stage("proj-1", StageId.STRUCTURAL)
    with pytest.raises(ValueError, match="not a finalize stage"):
        pipeline.run_single_stage("proj-1", StageId.DEEPENING)


def test_run_single_stage_calls_start_group_with_single_element(pipeline):
    """The method should delegate to _start_group with a one-stage list."""
    with patch.object(pipeline, "_check_project_active", return_value=True), \
         patch.object(pipeline, "_selfheal_group"), \
         patch.object(pipeline, "_start_group", return_value=True) as start_group:
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is True

    start_group.assert_called_once_with(
        "proj-1", "atlas", [StageId.ATLAS], resume_from=0,
    )


def test_run_single_stage_refuses_when_enrich_active(pipeline):
    """Must not launch a solo finalize while enrich is active/paused."""
    from codrag.services.pipeline_orchestrator import PipelineRun
    enrich_run = MagicMock(spec=PipelineRun)
    enrich_run.is_active = True
    enrich_run.is_paused = False
    enrich_run.state = MagicMock(value="running")
    enrich_run.current_stage = "deepening"
    with patch.object(pipeline, "_check_project_active", return_value=True):
        pipeline._runs[("proj-1", "deep_enrichment")] = enrich_run
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is False


def test_run_single_stage_refuses_when_fast_sync_active(pipeline):
    """Must not launch a solo finalize while fast_sync is active/paused.

    Solo finalize stages expect a quiescent pipeline — stricter than
    run_finalize's enrich-only guard because solo runs are opportunistic.
    """
    from codrag.services.pipeline_orchestrator import PipelineRun
    fast_run = MagicMock(spec=PipelineRun)
    fast_run.is_active = True
    fast_run.is_paused = False
    fast_run.state = MagicMock(value="running")
    fast_run.current_stage = "structural"
    with patch.object(pipeline, "_check_project_active", return_value=True):
        pipeline._runs[("proj-1", "fast_sync")] = fast_run
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is False


def test_run_single_stage_refuses_when_fast_sync_paused(pipeline):
    """Paused (not active) fast_sync must also block a solo finalize.

    The guard is `is_active or is_paused` — exercising the paused-only
    branch ensures a paused pipeline still protects downstream state.
    """
    from codrag.services.pipeline_orchestrator import PipelineRun
    fast_run = MagicMock(spec=PipelineRun)
    fast_run.is_active = False
    fast_run.is_paused = True
    fast_run.state = MagicMock(value="paused")
    fast_run.current_stage = "structural"
    with patch.object(pipeline, "_check_project_active", return_value=True):
        pipeline._runs[("proj-1", "fast_sync")] = fast_run
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is False


def test_run_single_stage_refuses_when_project_inactive(pipeline):
    """Inactive projects cannot start anything."""
    with patch.object(pipeline, "_check_project_active", return_value=False):
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is False


def test_run_single_stage_group_identity_matches_stage(pipeline):
    """The group name written to history is the stage value."""
    captured = {}

    def capture(project_id, group, stages, **kwargs):
        captured["group"] = group
        captured["stages"] = stages
        return True

    with patch.object(pipeline, "_check_project_active", return_value=True), \
         patch.object(pipeline, "_selfheal_group"), \
         patch.object(pipeline, "_start_group", side_effect=capture):
        pipeline.run_single_stage("proj-1", StageId.CONCEPTS)

    assert captured["group"] == "concepts"
    assert captured["stages"] == [StageId.CONCEPTS]


def test_run_single_stage_force_bypasses_selfheal_and_resume(pipeline):
    """force=True skips selfheal pre-flight (consistent with run_finalize)."""
    with patch.object(pipeline, "_check_project_active", return_value=True), \
         patch.object(pipeline, "_selfheal_group") as selfheal, \
         patch.object(pipeline, "_start_group", return_value=True):
        pipeline.run_single_stage("proj-1", StageId.ATLAS, force=True)

    selfheal.assert_not_called()

"""Regression tests for the freshness-skip metadata bug.

When a stage hits the freshness check at orchestrator.py
``_should_skip_stage_freshness`` and skips, the in-memory state machine
records ``run.stage_results[stage] = "skipped"``, but the
``pipeline_run_metadata.json`` file is never updated. Its stage entry
keeps the initial ``status: "pending"`` from ``create_run_metadata``,
and downstream consumers (the dashboard ``/pipeline/status`` endpoint,
the React panels) read it as "still running" — surfacing as the
"Iteration 0/?" / "Enriching..." UI freeze observed on SourcePrep
(stage 6, 2026-05-18 08:31) and SkyPath-Restart (stage 9, 2026-05-18
10:24) after daemon restart.

These tests pin the desired behavior:

1. ``pipeline_metadata.mark_stage_skipped`` exists and sets the stage's
   ``status`` to ``"skipped"`` with ``finished_at`` and a reason string.
2. ``PipelineOrchestrator._should_skip_stage_freshness`` calls into the
   in-memory ``_run_metadata`` mapping so the next ``save_run_metadata``
   persists the skip — closing the gap with the normal completion path
   at ``_update_run_metadata_for_stage``.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.services.pipeline_metadata import (
    create_run_metadata,
    save_run_metadata,
)

# ── Unit: mark_stage_skipped ───────────────────────────────────────


def test_mark_stage_skipped_sets_status_and_finished_at():
    """``mark_stage_skipped`` flips the stage from ``pending`` to
    ``skipped`` and stamps ``finished_at``. Reason is preserved in
    ``worker_result`` so the UI can surface the rationale."""
    from prep.services.pipeline_metadata import mark_stage_skipped

    meta = create_run_metadata(
        run_id="run-test-1",
        project_id="proj-skip",
        group="finalize",
        stage_ids=["atlas", "rules", "concepts", "audit", "antibodies"],
    )
    # Sanity: all stages start pending
    for s in meta.stages:
        assert s.status == "pending"

    mark_stage_skipped(meta, "audit", reason="all outputs newer than inputs")

    audit = next(s for s in meta.stages if s.stage_id == "audit")
    assert audit.status == "skipped"
    assert audit.finished_at is not None
    assert audit.elapsed_seconds == 0.0
    assert isinstance(audit.worker_result, dict)
    assert audit.worker_result.get("skipped") is True
    assert audit.worker_result.get("reason") == "all outputs newer than inputs"

    # Other stages remain pending — we only touched ``audit``.
    for s in meta.stages:
        if s.stage_id != "audit":
            assert s.status == "pending", (
                f"{s.stage_id} should stay pending, got {s.status}"
            )


def test_mark_stage_skipped_missing_stage_is_noop():
    """Calling ``mark_stage_skipped`` for a stage not in ``meta.stages``
    must not raise (the freshness-skip path can fire for stages that
    haven't been added if a future stage list changes)."""
    from prep.services.pipeline_metadata import mark_stage_skipped

    meta = create_run_metadata(
        run_id="run-test-2",
        project_id="proj-noop",
        group="finalize",
        stage_ids=["atlas"],
    )
    mark_stage_skipped(meta, "nonexistent_stage", reason="test")
    # No exception, no mutation
    assert meta.stages[0].stage_id == "atlas"
    assert meta.stages[0].status == "pending"


def test_mark_stage_skipped_round_trips_through_disk(tmp_path: Path):
    """The persisted JSON survives a save → load cycle with the
    ``"skipped"`` status intact."""
    from prep.services.pipeline_metadata import (
        load_run_metadata,
        mark_stage_skipped,
    )

    meta = create_run_metadata(
        run_id="run-test-3",
        project_id="proj-disk",
        group="deep_enrichment",
        stage_ids=["enrichment", "group_reasoning", "clustering",
                   "deepening", "deep_knowledge"],
    )
    mark_stage_skipped(meta, "deepening", reason="outputs newer than inputs")
    save_run_metadata(meta, tmp_path)

    loaded = load_run_metadata(tmp_path)
    assert loaded is not None
    deep = next(s for s in loaded.stages if s.stage_id == "deepening")
    assert deep.status == "skipped"
    assert deep.worker_result.get("skipped") is True


# ── Integration: orchestrator freshness skip ──────────────────────


@pytest.fixture
def pipeline_with_real_project(tmp_path: Path):
    """Pipeline orchestrator wired to a real on-disk index_dir so we can
    inspect the persisted ``pipeline_run_metadata.json`` after a run.

    The project is a stub — only its ``id`` and ``path`` matter, and
    the index_dir is the tmp dir. We patch ``require_project`` and
    ``project_index_dir`` so the orchestrator's metadata writer paths
    that depend on them resolve to the tmp dir.
    """
    from prep.services.build_orchestrator import BuildOrchestrator
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline_orchestrator import PipelineOrchestrator

    # Reset the singleton scheduler — same pattern as the existing fixture.
    pipeline_scheduler._slots.clear()
    pipeline_scheduler._queues.clear()
    pipeline_scheduler._priority_projects.clear()
    pipeline_scheduler._swarm_window = None
    pipeline_scheduler._capacity_listeners.clear()
    pipeline_scheduler._last_broadcast_times.clear()
    pipeline_scheduler._init_embedding_slot()

    idx_dir = tmp_path / "idx"
    idx_dir.mkdir()

    class _StubProject:
        id = "proj-fresh-skip"
        path = str(tmp_path / "repo")
        name = "FreshSkipTest"
        config: dict = {}

    project = _StubProject()
    Path(project.path).mkdir(parents=True, exist_ok=True)

    with patch(
        "prep.services.project_helpers.get_project_activity_status",
        return_value="active",
    ), patch(
        "prep.services.project_helpers.require_project",
        return_value=project,
    ), patch(
        "prep.core.project_registry.project_index_dir",
        return_value=idx_dir,
    ):
        po = PipelineOrchestrator(orchestrator=BuildOrchestrator())
        yield po, idx_dir
        po._runs.clear()
        po._incremental_runs.clear()
        po._chain_deep.clear()
        po._force_from_start_runs.clear()
        po._run_metadata.clear()
        pipeline_scheduler._slots.clear()
        pipeline_scheduler._queues.clear()
        pipeline_scheduler._priority_projects.clear()


def test_freshness_skip_persists_skipped_status_to_disk(pipeline_with_real_project):
    """Reproduces the dogfooding bug: a freshness-skipped stage must end
    up with ``status == "skipped"`` in ``pipeline_run_metadata.json``,
    not the initial ``"pending"`` from ``create_run_metadata``.

    Pre-fix: the on-disk file's stage entry stays ``"pending"`` because
    ``_should_skip_stage_freshness`` only updates the in-memory state
    machine, not ``_run_metadata`` + ``save_run_metadata``.
    """
    from prep.services.pipeline_metadata import (
        METADATA_FILENAME,
        load_run_metadata,
    )

    pipeline, idx_dir = pipeline_with_real_project
    skip_stage = "audit"

    def worker_factory(project_id, stage):
        def worker(slot, progress_cb):
            return {"ok": True}
        return worker

    def skip_if(pid, stage, inc, pfl=None):
        return (True, "test-freshness") if stage.value == skip_stage else (False, "")

    with patch(
        "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
        side_effect=worker_factory,
    ), patch(
        "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
        side_effect=skip_if,
    ):
        pipeline.run_finalize("proj-fresh-skip")
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            status = pipeline.status("proj-fresh-skip")
            fin = status.get("finalize")
            if fin and fin["phase"] in ("completed", "failed"):
                break
            time.sleep(0.1)

    # On-disk file is the source of truth for the dashboard.
    metadata_path = idx_dir / METADATA_FILENAME
    assert metadata_path.exists(), (
        f"{METADATA_FILENAME} was never written — check fixture wiring"
    )
    loaded = load_run_metadata(idx_dir)
    assert loaded is not None
    stage_records = {s.stage_id: s for s in loaded.stages}
    audit = stage_records.get(skip_stage)
    assert audit is not None, f"{skip_stage} missing from persisted stages"
    assert audit.status == "skipped", (
        f"Persisted status for {skip_stage} is {audit.status!r} (expected 'skipped'). "
        "The freshness-skip path is not updating pipeline_run_metadata.json — "
        "this is the bug that surfaces as stuck 'Iteration 0/?' / 'Enriching...' "
        "in the dashboard."
    )
    # The reason string from should_skip_stage_freshness is round-tripped.
    assert audit.worker_result.get("reason") == "test-freshness"

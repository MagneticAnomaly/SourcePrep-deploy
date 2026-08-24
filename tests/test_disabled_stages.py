"""Tests for per-stage `disabled_stages` project config (T-S1.5).

The profile model (scrutiny M1) needs a per-stage enable/disable surface at
the orchestrator: today gating is per stage-GROUP (auto_config.{fastSync,
deepEnrichment, finalize}), so a project that wants atlas ON but concepts
OFF (both in the finalize group) has no mechanism. `disabled_stages:
[list of stage ids]` in project config is that mechanism.

Behavior contract pinned here:
- A disabled stage is never dispatched to WorkerFactory, marks
  ``stage_results[stage] = "skipped"``, and the group completes.
- The orchestrator writes a REAL provenance manifest
  (``status: "disabled_by_config"``) for the disabled stage so
  resume-point detection (provenance_exists) flows past it instead of
  pinning the group at the disabled stage forever.
- The manifest must NOT look like a selfheal stub (``restored: true``) —
  stubs are treated as incomplete during rebuilds (resume.py:204+).
- Run metadata records the stage as ``skipped`` with a reason naming the
  config key (dashboard label, not error).
- Core graph stages (structural/validation/knowledge/deep_knowledge) can
  never be disabled — refusing them would corrupt the trace graph; the
  config entry is ignored with a warning.
- Absent the config, behavior is byte-identical: no manifests written by
  the orchestrator, all stages dispatched.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from prep.services.build_orchestrator import BuildOrchestrator
from prep.services.pipeline_orchestrator import PipelineOrchestrator


@pytest.fixture
def pipeline(tmp_path: Path):
    """PipelineOrchestrator with a real BuildOrchestrator, clean scheduler,
    and a fake project rooted at tmp_path (embedded index dir)."""
    from prep.services.pipeline.scheduler import pipeline_scheduler

    pipeline_scheduler._slots.clear()
    pipeline_scheduler._queues.clear()
    pipeline_scheduler._priority_projects.clear()
    pipeline_scheduler._swarm_window = None
    pipeline_scheduler._capacity_listeners.clear()
    pipeline_scheduler._last_broadcast_times.clear()
    pipeline_scheduler._init_embedding_slot()

    project = SimpleNamespace(
        id="proj-disabled",
        path=str(tmp_path),
        mode="embedded",
        config={},
    )

    with patch(
        "prep.services.project_helpers.get_project_activity_status",
        return_value="active",
    ), patch(
        "prep.services.project_helpers.require_project",
        return_value=project,
    ):
        po = PipelineOrchestrator(orchestrator=BuildOrchestrator())
        yield po, project, tmp_path / ".sourceprep"
        po._runs.clear()
        po._incremental_runs.clear()
        po._chain_deep.clear()
        po._force_from_start_runs.clear()
        pipeline_scheduler._slots.clear()
        pipeline_scheduler._queues.clear()
        pipeline_scheduler._priority_projects.clear()


def _instant_workers(executed: list[str]):
    def worker_factory(project_id, stage):
        def worker(slot, progress_cb):
            executed.append(stage.value)
            return {"ok": True}

        return worker

    return worker_factory


def _wait_done(po: PipelineOrchestrator, pid: str, group: str, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = po.status(pid)
        g = status.get(group)
        if g and g["phase"] in ("completed", "failed"):
            return g
        time.sleep(0.05)
    raise AssertionError(f"pipeline group {group} never settled: {po.status(pid)}")


class TestDisabledStages:
    def test_disabled_stage_is_skipped_not_dispatched(self, pipeline):
        po, project, idx_dir = pipeline
        project.config = {"disabled_stages": ["concepts"]}
        executed: list[str] = []

        with patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=_instant_workers(executed),
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            po.run_finalize(project.id)
            fin = _wait_done(po, project.id, "finalize")

        assert fin["phase"] == "completed", f"final phase: {fin['phase']}"
        assert "concepts" not in executed, f"disabled stage dispatched: {executed}"
        assert executed == ["atlas", "rules", "audit", "antibodies"]
        assert fin["stage_results"].get("concepts") == "skipped"

    def test_disabled_stage_writes_disabled_by_config_manifest(self, pipeline):
        """Resume pinning guard: the disabled stage MUST have a real
        provenance manifest afterwards, marked disabled_by_config, that is
        not a selfheal stub."""
        po, project, idx_dir = pipeline
        project.config = {"disabled_stages": ["concepts"]}
        executed: list[str] = []

        with patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=_instant_workers(executed),
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            po.run_finalize(project.id)
            _wait_done(po, project.id, "finalize")

        manifest_path = idx_dir / "concepts_manifest.json"
        assert manifest_path.exists(), "no provenance manifest for disabled stage"
        data = json.loads(manifest_path.read_text())
        assert data.get("status") == "disabled_by_config", data

        from prep.services.pipeline.manifest_store import ManifestStore
        from prep.services.pipeline.stages import StageId

        store = ManifestStore(idx_dir)
        assert store.provenance_exists(StageId.CONCEPTS)
        assert not store.is_stub_manifest(StageId.CONCEPTS), (
            "disabled manifest must not look like a selfheal stub"
        )

    def test_disabled_stage_does_not_pin_resume_point(self, pipeline):
        """A group re-invoked after a run with a disabled stage must flow
        PAST it: stages before it (with manifests) are not re-run."""
        po, project, idx_dir = pipeline
        project.config = {"disabled_stages": ["concepts"]}
        idx_dir.mkdir(parents=True, exist_ok=True)

        # Simulate a previous run: atlas + rules completed, then the
        # disabled concepts manifest, but audit/antibodies never ran.
        from prep.services.pipeline.manifest_store import ManifestStore
        from prep.services.pipeline.stages import StageId

        store = ManifestStore(idx_dir)
        for stage in (StageId.ATLAS, StageId.RULES):
            store.write_provenance(stage, {
                "stage_id": stage.value,
                "status": "ok",
                "finished_at": "2026-08-24T00:00:00Z",
            })
        store.write_provenance(StageId.CONCEPTS, {
            "stage_id": StageId.CONCEPTS.value,
            "status": "disabled_by_config",
            "finished_at": "2026-08-24T00:01:00Z",
        })

        executed: list[str] = []
        with patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=_instant_workers(executed),
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            po.run_finalize(project.id)
            fin = _wait_done(po, project.id, "finalize")

        assert fin["phase"] == "completed"
        assert "concepts" not in executed
        # atlas + rules resume-skipped (manifests exist), audit + antibodies ran
        assert executed == ["audit", "antibodies"], f"executed: {executed}"

    def test_run_metadata_records_disabled_skip_reason(self, pipeline):
        po, project, idx_dir = pipeline
        project.config = {"disabled_stages": ["concepts"]}
        executed: list[str] = []

        with patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=_instant_workers(executed),
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            po.run_finalize(project.id)
            _wait_done(po, project.id, "finalize")

        meta_path = idx_dir / "pipeline_run_metadata.json"
        assert meta_path.exists(), "run metadata not persisted"
        meta = json.loads(meta_path.read_text())
        stage = next(s for s in meta["stages"] if s["stage_id"] == "concepts")
        assert stage["status"] == "skipped"
        result = stage.get("worker_result") or {}
        assert "disabled" in str(result.get("reason", "")).lower()

    def test_absent_config_dispatches_everything(self, pipeline):
        """Back-compat: no disabled_stages config → all 5 finalize stages
        dispatch and NO disabled manifests appear."""
        po, project, idx_dir = pipeline
        executed: list[str] = []

        with patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=_instant_workers(executed),
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            po.run_finalize(project.id)
            fin = _wait_done(po, project.id, "finalize")

        assert fin["phase"] == "completed"
        assert executed == ["atlas", "rules", "concepts", "audit", "antibodies"]
        # No stage marked skipped, and no disabled_by_config manifests: the
        # normal completion path writes provenance for each stage, but none
        # of them carry the disabled marker.
        assert "skipped" not in fin["stage_results"].values()
        for mp in idx_dir.glob("*_manifest.json"):
            data = json.loads(mp.read_text())
            assert data.get("status") != "disabled_by_config", mp.name

    def test_core_graph_stages_cannot_be_disabled(self, pipeline, caplog):
        """disabled_stages: ['structural'] must be ignored (with a warning)
        — disabling graph/embed stages corrupts the trace pipeline."""
        po, project, idx_dir = pipeline
        project.config = {"disabled_stages": ["structural"]}
        executed: list[str] = []

        import logging

        def worker_factory(project_id, stage):
            def worker(slot, progress_cb):
                executed.append(stage.value)
                return {"ok": True}

            return worker

        with caplog.at_level(logging.WARNING), patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=worker_factory,
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            # structural belongs to fast_sync; disable attempt must not
            # prevent its dispatch.
            po.run_fast_sync(project.id)
            fin = _wait_done(po, project.id, "fast_sync")

        assert "structural" in executed, (
            f"core stage was disabled: executed={executed}"
        )
        assert any("disabled" in r.message.lower() for r in caplog.records)

    def test_unknown_stage_name_ignored_with_warning(self, pipeline, caplog):
        po, project, idx_dir = pipeline
        project.config = {"disabled_stages": ["not_a_stage"]}
        executed: list[str] = []

        import logging

        with caplog.at_level(logging.WARNING), patch(
            "prep.services.pipeline.orchestrator.WorkerFactory.create_worker",
            side_effect=_instant_workers(executed),
        ), patch(
            "prep.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
            return_value=(False, ""),
        ):
            po.run_finalize(project.id)
            fin = _wait_done(po, project.id, "finalize")

        assert fin["phase"] == "completed"
        assert executed == ["atlas", "rules", "concepts", "audit", "antibodies"]
        assert any("not_a_stage" in r.message for r in caplog.records)

"""Phase 145 — Finalize must re-run on incremental changes.

Bug (2026-06-15): after an incremental run, Finalize (atlas/rules/concepts/
audit/antibodies) never auto-chained even with auto_config.finalize=auto.
``run_deep_enrichment`` has a Phase 89 escape hatch — when all stage
manifests look complete but the run is incremental it resets resume=0 to
reprocess new files (orchestrator.py:956-970). ``run_finalize`` had no
such hatch: ``if resume >= len(FINALIZE_STAGES): return False`` always,
so finalize bailed whenever its 5 manifests existed.

``is_incremental`` is consumed by ``run_deep_enrichment`` before the
deep→finalize chain fires, so the durable signal for finalize is the
changeset itself: if ``cs.added or cs.modified`` is non-empty there is new
work to finalize. This pins the helper that encodes that decision.
"""
from __future__ import annotations

from pathlib import Path

import prep.core.project_registry as _pr
import prep.services.project_helpers as _ph
from prep.services.pipeline.changeset import Changeset, write_changeset
from prep.services.pipeline.orchestrator import PipelineOrchestrator


class _FakeProject:
    def __init__(self, pid: str):
        self.id = pid
        self.path = "/tmp/whatever"
        self.config = {}


def _point_index_dir(monkeypatch, idx: Path, pid: str):
    monkeypatch.setattr(_pr, "project_index_dir", lambda project: idx)
    monkeypatch.setattr(_ph, "require_project", lambda project_id: _FakeProject(pid))


def _write_cs(idx: Path, *, added=(), modified=(), unchanged=()):
    write_changeset(
        idx,
        Changeset(
            added=frozenset(added),
            modified=frozenset(modified),
            deleted=frozenset(),
            unchanged=frozenset(unchanged),
            run_id="run-x",
            base_run_id="run-prev",
        ),
    )


def test_incremental_work_when_changeset_has_added(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    idx.mkdir()
    _point_index_dir(monkeypatch, idx, "p1")
    _write_cs(idx, added=["docs/new.md"], unchanged=["a.swift"])
    assert PipelineOrchestrator._finalize_has_incremental_work("p1") is True


def test_incremental_work_when_changeset_has_modified(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    idx.mkdir()
    _point_index_dir(monkeypatch, idx, "p1")
    _write_cs(idx, modified=["a.swift"], unchanged=["b.swift"])
    assert PipelineOrchestrator._finalize_has_incremental_work("p1") is True


def test_no_incremental_work_when_changeset_all_unchanged(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    idx.mkdir()
    _point_index_dir(monkeypatch, idx, "p1")
    _write_cs(idx, unchanged=["a.swift", "b.swift"])
    assert PipelineOrchestrator._finalize_has_incremental_work("p1") is False


def test_no_incremental_work_when_no_changeset(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    idx.mkdir()
    _point_index_dir(monkeypatch, idx, "p1")
    # no changeset.json written
    assert PipelineOrchestrator._finalize_has_incremental_work("p1") is False

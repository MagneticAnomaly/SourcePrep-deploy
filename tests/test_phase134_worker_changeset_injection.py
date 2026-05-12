"""Phase 134 — WorkerFactory loads the Changeset and injects it into
each worker before construction returns. Workers consume via
self.changeset.should_process(path)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from prep.services.pipeline.changeset import Changeset, write_changeset


def test_worker_factory_loads_changeset_from_disk(tmp_path: Path):
    """When WorkerFactory.create_worker is invoked, it reads the
    project's .sourceprep/changeset.json and the resulting worker has
    .changeset set."""
    from prep.services.pipeline.stages import StageId
    from prep.services.pipeline.workers.factory import WorkerFactory

    idx = tmp_path / "index"
    idx.mkdir()
    cs = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="run-test",
        base_run_id=None,
    )
    write_changeset(idx, cs)

    fake_proj = MagicMock()
    fake_proj.id = "test-proj"
    fake_proj.path = str(tmp_path / "repo")

    with patch("prep.services.project_helpers.require_project", return_value=fake_proj), \
         patch("prep.core.project_registry.project_index_dir", return_value=idx):
        worker = WorkerFactory.create_worker("test-proj", StageId.STRUCTURAL)

    assert worker.changeset is not None
    assert worker.changeset.run_id == "run-test"
    assert worker.changeset.should_process("new.py") is True
    assert worker.changeset.should_process("old.py") is False


def test_worker_factory_injects_none_when_changeset_missing(tmp_path: Path):
    """If no changeset.json exists on disk yet (e.g. very first build
    before Task 2 has emitted one), WorkerFactory injects None.
    Workers fall back to processing everything (defensive)."""
    from prep.services.pipeline.stages import StageId
    from prep.services.pipeline.workers.factory import WorkerFactory

    idx = tmp_path / "index"
    idx.mkdir()  # no changeset.json

    fake_proj = MagicMock()
    fake_proj.id = "test-proj"
    fake_proj.path = str(tmp_path / "repo")

    with patch("prep.services.project_helpers.require_project", return_value=fake_proj), \
         patch("prep.core.project_registry.project_index_dir", return_value=idx):
        worker = WorkerFactory.create_worker("test-proj", StageId.STRUCTURAL)

    assert worker.changeset is None


def test_worker_should_process_none_changeset_returns_true():
    """The defensive fallback: if changeset is None, should_process
    returns True (process everything). This protects against the
    orchestrator forgetting to inject during a refactor."""
    from prep.services.pipeline.workers.base import Worker

    class TestWorker(Worker):
        pass

    w = TestWorker()
    w.changeset = None
    assert w.should_process("anything.py") is True


def test_worker_should_process_with_changeset():
    from prep.services.pipeline.workers.base import Worker

    class TestWorker(Worker):
        pass

    w = TestWorker()
    w.changeset = Changeset(
        added=frozenset({"new.py"}),
        modified=frozenset({"changed.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"old.py"}),
        run_id="r1",
        base_run_id=None,
    )
    assert w.should_process("new.py") is True
    assert w.should_process("changed.py") is True
    assert w.should_process("old.py") is False
    assert w.should_process("never-seen.py") is False

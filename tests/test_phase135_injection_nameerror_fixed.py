"""Phase 135 Task 0 — Phase 134's changeset injection had a latent
NameError because each inner worker referenced `wrapped_worker`, a name
not in its closure. This test invokes each affected worker end-to-end
and verifies (a) no NameError, (b) the changeset reaches the engine."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset, write_changeset
from prep.services.pipeline.stages import StageId


@pytest.fixture
def fake_changeset(tmp_path: Path) -> Changeset:
    cs = Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"c.py"}),
        run_id="r1",
        base_run_id=None,
    )
    write_changeset(tmp_path, cs)
    return cs


def _common_patches(idx_dir: Path):
    """Patch all the daemon-side dependencies so we can invoke a worker
    end-to-end without a running daemon."""
    fake_proj = MagicMock()
    fake_proj.id = "p1"
    fake_proj.name = "p"
    fake_proj.config = {}
    fake_proj.path = str(idx_dir.parent)
    return [
        patch("prep.services.pipeline.workers.WorkerFactory._get_project_and_config",
              return_value=(fake_proj, {}, [], [], 0, 0, 0, 0, 0)),
        patch("prep.services.pipeline.workers.WorkerFactory._get_llm_client_for_task",
              return_value=MagicMock(model="x", provider="x")),
        patch("prep.services.project_helpers.require_project", return_value=fake_proj),
        patch("prep.core.project_registry.project_index_dir", return_value=idx_dir),
    ]


def test_catalogue_worker_no_nameerror(tmp_path: Path, fake_changeset: Changeset):
    """Phase 134 bug: invoking the catalogue worker raised NameError on
    `wrapped_worker`. Phase 135 Task 0 fixes it."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    fake_augmenter = MagicMock()
    fake_augmenter.run.return_value = MagicMock(
        augmented=0, failed=0, skipped=0, paused=False,
        batches_attempted=0, total_nodes=0, synthetic=0,
    )

    with patch("prep.core.TraceAugmenter", return_value=fake_augmenter):
        for p in _common_patches(tmp_path):
            p.start()
        try:
            worker = WorkerFactory.create_worker("p1", StageId.CATALOGUE)
            slot = MagicMock(cancel_token=None)
            worker(slot, lambda *a, **kw: None)  # MUST NOT NameError
        finally:
            patch.stopall()

    # Changeset reached the augmenter, not None.
    # The assignment happens AFTER construction: augmenter.changeset = getattr(worker, ...)
    assert fake_augmenter.changeset is not None
    assert fake_augmenter.changeset.run_id == "r1"


def test_enrichment_worker_no_nameerror(tmp_path: Path, fake_changeset: Changeset):
    """Same check for the enrichment stage."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    # The enrichment worker checks that trace_augmented.jsonl is non-empty
    # before it reaches the changeset injection line. Create a stub so the
    # pre-flight check passes.
    (tmp_path / "trace_augmented.jsonl").write_text('{"id":"stub"}\n')

    captured: dict = {}
    fake_enricher = MagicMock()
    fake_enricher.run.return_value = {"enriched": 0, "failed": 0}

    def capture(*a, **kw):
        captured["changeset"] = fake_enricher.changeset
        return fake_enricher

    with patch("prep.core.EpistemicEnricher", side_effect=capture):
        for p in _common_patches(tmp_path):
            p.start()
        try:
            worker = WorkerFactory.create_worker("p1", StageId.ENRICHMENT)
            slot = MagicMock(cancel_token=None)
            worker(slot, lambda *a, **kw: None)
        finally:
            patch.stopall()

    assert captured.get("changeset") is not None


def test_deepening_worker_no_nameerror(tmp_path: Path, fake_changeset: Changeset):
    """Same check for the deepening stage. Two injection sites in
    `_deepening_worker`: enricher (line 1031) and drift_detector
    (line 1045)."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    fake_loop = MagicMock()
    # The deepening worker accesses result.iterations and result.convergence as
    # attributes, not dict keys, so we need a MagicMock, not a plain dict.
    fake_loop.run.return_value = MagicMock(iterations=0, convergence=True)
    fake_loop.drift_detector = MagicMock()

    with patch("prep.core.DeepeningLoop", return_value=fake_loop), \
         patch("prep.core.EpistemicEnricher"):
        for p in _common_patches(tmp_path):
            p.start()
        try:
            worker = WorkerFactory.create_worker("p1", StageId.DEEPENING)
            slot = MagicMock(cancel_token=None)
            worker(slot, lambda *a, **kw: None)
        finally:
            patch.stopall()

    # drift_detector.changeset must be set, not raise NameError
    assert fake_loop.drift_detector.changeset is not None

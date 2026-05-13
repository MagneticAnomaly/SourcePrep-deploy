"""Phase 135 — verify the three workers attach the Changeset to their
engine instance before invoking it.

Uses contextlib.ExitStack for patch cleanup (Task 0 reviewer's
suggested pattern — safer than patch.stopall() in finally because
ExitStack guarantees per-patch cleanup even if .start() throws)."""
from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.changeset import Changeset


@pytest.fixture
def fake_changeset() -> Changeset:
    return Changeset(
        added=frozenset({"a.py"}),
        modified=frozenset({"b.py"}),
        deleted=frozenset(),
        unchanged=frozenset({"c.py"}),
        run_id="r1",
        base_run_id=None,
    )


def _common_patches() -> list:
    fake_proj = MagicMock()
    fake_proj.id = "p1"
    fake_proj.name = "p"
    fake_proj.config = {}
    return [
        patch("prep.services.pipeline.workers.WorkerFactory._get_project_and_config",
              return_value=(fake_proj, {}, [], [], 0, 0, 0, 0, 0)),
        patch("prep.services.pipeline.workers.WorkerFactory._get_llm_client_for_task",
              return_value=MagicMock(model="x", provider="x")),
    ]


def test_group_reasoning_worker_injects_changeset(fake_changeset: Changeset) -> None:
    """_group_reasoning_worker attaches the Changeset to the engine
    instance before calling .run()."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    captured: dict = {}

    def fake_run(self, *args, **kwargs):
        captured["changeset"] = self.changeset
        return {"analyzed": 0, "reused": 0, "failed": 0}

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("prep.core.group_reasoning.GroupReasoningEngine.run", fake_run))
        for p in _common_patches():
            stack.enter_context(p)

        worker_fn = WorkerFactory._group_reasoning_worker("p1")
        # Simulate the _build_worker injection that sets the closure attr:
        worker_fn.changeset = fake_changeset  # type: ignore[attr-defined]

        slot = MagicMock()
        slot.cancel_token = None
        worker_fn(slot, lambda *a, **kw: None)

    assert captured.get("changeset") is fake_changeset


def test_cluster_worker_injects_changeset(fake_changeset: Changeset) -> None:
    """_cluster_worker attaches the Changeset to ClusterSynthesizer."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    captured: dict = {}

    def fake_run(self, *args, **kwargs):
        captured["changeset"] = self.changeset
        return {"synthesized": 0, "reused": 0, "failed": 0}

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("prep.core.cluster.ClusterSynthesizer.run", fake_run))
        for p in _common_patches():
            stack.enter_context(p)

        worker_fn = WorkerFactory._cluster_worker("p1")
        worker_fn.changeset = fake_changeset  # type: ignore[attr-defined]

        slot = MagicMock()
        slot.cancel_token = None
        worker_fn(slot, lambda *a, **kw: None)

    assert captured.get("changeset") is fake_changeset


def test_deep_knowledge_worker_injects_changeset_and_use_flag(fake_changeset: Changeset) -> None:
    """_knowledge_worker with is_deep=True attaches Changeset AND sets
    use_changeset=True. The flag-reset behavior is covered by Task 3's
    test_cached_instance_use_changeset_resets_for_stage5; this test
    focuses on the positive set on the deep call."""
    from prep.services.pipeline.workers.factory import WorkerFactory

    fake_idx = MagicMock()
    fake_idx.use_changeset = False
    fake_idx.changeset = None
    fake_idx.build.return_value = {"count": 0, "status": "empty"}

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(
            "prep.services.build_manager.build_manager.get_project_knowledge_index",
            return_value=fake_idx,
        ))
        for p in _common_patches():
            stack.enter_context(p)

        worker_fn = WorkerFactory._knowledge_worker("p1", is_deep=True)
        worker_fn.changeset = fake_changeset  # type: ignore[attr-defined]

        slot = MagicMock()
        slot.cancel_token = None
        worker_fn(slot, lambda *a, **kw: None)

    assert fake_idx.use_changeset is True
    assert fake_idx.changeset is fake_changeset

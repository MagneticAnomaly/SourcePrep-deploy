"""Phase 117: /pipeline/rebuild/stop atomic cancel + barrier clear."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_project(monkeypatch):
    monkeypatch.setattr(
        "prep.services.project_helpers.require_project_writable", lambda _pid: None
    )
    return "proj-test"


def test_rebuild_stop_clears_barrier_when_idle(client, fake_project, monkeypatch):
    """If no rebuild is active, endpoint still returns success and no-ops."""
    from prep.services.pipeline import recovery

    monkeypatch.setattr(recovery, "read_reset_barrier", lambda _pid: None)
    monkeypatch.setattr(recovery, "clear_reset_barrier", lambda _pid: False)

    orch = MagicMock()
    orch._cancel_group = MagicMock(return_value=False)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/rebuild/stop")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["stopped"] is True
    assert body["was_active"] is False


def test_rebuild_stop_cancels_active_group_and_clears_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery

    monkeypatch.setattr(
        recovery, "read_reset_barrier",
        lambda _pid: {"reason": "rebuild", "scope": "sync", "written_at": 1.0, "age_seconds": 0.0},
    )
    cleared = {"v": False}
    def _clear(_pid):
        cleared["v"] = True
        return True
    monkeypatch.setattr(recovery, "clear_reset_barrier", _clear)

    orch = MagicMock()
    orch.cancel_fast_sync = MagicMock(return_value=True)
    orch.cancel_deep_enrichment = MagicMock(return_value=False)
    orch.cancel_finalize = MagicMock(return_value=False)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/rebuild/stop")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["was_active"] is True
    assert cleared["v"] is True
    # Sync scope → cancels fast_sync
    orch.cancel_fast_sync.assert_called_once_with(fake_project)


def test_rebuild_stop_enrichment_scope_cancels_deep(client, fake_project, monkeypatch):
    from prep.services.pipeline import recovery

    monkeypatch.setattr(
        recovery, "read_reset_barrier",
        lambda _pid: {"reason": "rebuild", "scope": "enrichment", "written_at": 1.0, "age_seconds": 0.0},
    )
    monkeypatch.setattr(recovery, "clear_reset_barrier", lambda _pid: True)

    orch = MagicMock()
    orch.cancel_deep_enrichment = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/rebuild/stop")
    assert resp.status_code == 200
    orch.cancel_deep_enrichment.assert_called_once_with(fake_project)

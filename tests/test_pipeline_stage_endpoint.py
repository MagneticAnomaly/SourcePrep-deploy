"""Tests for POST /projects/{id}/pipeline/stages/{stage_id}/run (Phase 105a)."""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()
    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "test", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def test_post_stage_run_invalid_stage_returns_400(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    res = client.post(f"/projects/{pid}/pipeline/stages/not-a-stage/run")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_STAGE_ID"


def test_post_stage_run_sync_stage_returns_400(client, tmp_path):
    """Sync/enrich stages cannot be run solo — they must use group endpoints."""
    pid = _add_embedded_project(client, tmp_path)
    res = client.post(f"/projects/{pid}/pipeline/stages/structural/run")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_STAGE_ID"


def test_post_stage_run_atlas_returns_200(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator.run_single_stage",
        return_value=True,
    ):
        res = client.post(f"/projects/{pid}/pipeline/stages/atlas/run")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["started"] is True
    assert body["data"]["group"] == "atlas"


def test_post_stage_run_orchestrator_rejects_returns_409(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator.run_single_stage",
        return_value=False,
    ):
        res = client.post(f"/projects/{pid}/pipeline/stages/atlas/run")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "PIPELINE_GROUP_ACTIVE"


def test_post_stage_run_accepts_force_query_param(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator.run_single_stage",
        return_value=True,
    ) as mock_run:
        res = client.post(f"/projects/{pid}/pipeline/stages/atlas/run?force=true")
    assert res.status_code == 200
    _args, kwargs = mock_run.call_args
    assert kwargs.get("force") is True


def test_cancel_accepts_solo_finalize_group(client, tmp_path):
    """A solo atlas run must be cancelable via POST /pipeline/cancel?group=atlas."""
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator._cancel_group",
        return_value=True,
    ) as mock_cancel:
        res = client.post(f"/projects/{pid}/pipeline/cancel", json={"group": "atlas"})
    assert res.status_code == 200
    assert res.json()["data"]["cancelled"] is True
    # Verify the orchestrator got called with the raw stage name.
    args, _ = mock_cancel.call_args
    assert args[1] == "atlas"


def test_pause_accepts_solo_finalize_group(client, tmp_path):
    """A solo atlas run must be pausable via POST /pipeline/pause?group=atlas."""
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator._pause_group",
        return_value=True,
    ) as mock_pause:
        res = client.post(f"/projects/{pid}/pipeline/pause", json={"group": "atlas"})
    assert res.status_code == 200
    assert res.json()["data"]["paused"] is True
    # Verify the orchestrator got called with the raw stage name.
    args, _ = mock_pause.call_args
    assert args[1] == "atlas"


def test_cancel_unknown_group_returns_400(client, tmp_path):
    """Groups not in the allow-list must return 400 INVALID_GROUP."""
    pid = _add_embedded_project(client, tmp_path)
    res = client.post(f"/projects/{pid}/pipeline/cancel", json={"group": "not_a_group"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_GROUP"


def test_pause_unknown_group_returns_400(client, tmp_path):
    """Groups not in the allow-list must return 400 INVALID_GROUP."""
    pid = _add_embedded_project(client, tmp_path)
    res = client.post(f"/projects/{pid}/pipeline/pause", json={"group": "not_a_group"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_GROUP"

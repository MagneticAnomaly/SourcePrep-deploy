from __future__ import annotations
from pathlib import Path

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
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post("/projects", json={"path": str(repo_root), "name": "t", "mode": "embedded"})
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def test_pipeline_status_reports_barrier_inactive_by_default(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    body = res.json()
    data = body["data"]
    assert "barrier" in data
    assert data["barrier"]["active"] is False
    assert data["barrier"]["age_seconds"] is None
    assert data["barrier"]["reason"] is None
    assert data["barrier"]["written_at"] is None


def test_pipeline_status_reports_barrier_active_after_rebuild(client, tmp_path):
    from codrag.services.pipeline.recovery import write_reset_barrier
    pid = _add_embedded_project(client, tmp_path)
    assert write_reset_barrier(pid, "manual_test")

    # Bust the /pipeline/status cache so the next call re-reads disk.
    from codrag.api.routers.pipeline import _status_cache, _status_cache_lock
    with _status_cache_lock:
        _status_cache.pop(pid, None)

    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["barrier"]["active"] is True
    assert data["barrier"]["reason"] == "manual_test"
    assert data["barrier"]["age_seconds"] is not None
    assert data["barrier"]["age_seconds"] >= 0.0
    assert data["barrier"]["written_at"] is not None

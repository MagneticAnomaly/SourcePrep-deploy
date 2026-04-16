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


def _add_embedded(client: TestClient, repo: Path) -> str:
    res = client.post("/projects", json={"path": str(repo), "name": "t", "mode": "embedded"})
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def test_delete_reset_barrier_when_active(client, tmp_path):
    from codrag.services.pipeline.recovery import write_reset_barrier, reset_barrier_active
    pid = _add_embedded(client, tmp_path)
    assert write_reset_barrier(pid, "stale_from_aborted_rebuild")
    assert reset_barrier_active(pid)

    res = client.delete(f"/projects/{pid}/pipeline/reset-barrier")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["cleared"] is True
    assert data["previous_reason"] == "stale_from_aborted_rebuild"
    assert not reset_barrier_active(pid)


def test_delete_reset_barrier_when_inactive_is_noop(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.delete(f"/projects/{pid}/pipeline/reset-barrier")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["cleared"] is False
    assert data["previous_reason"] is None

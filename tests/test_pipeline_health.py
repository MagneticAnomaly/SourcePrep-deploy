from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry, project_index_dir
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


def test_pipeline_health_fresh_project(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/health")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["project_id"] == pid
    assert data["barrier"]["active"] is False
    assert isinstance(data["stages"], list)
    # Fresh project: 15 stages tracked, all missing manifests
    assert len(data["stages"]) == 15
    for stage in data["stages"]:
        assert stage["manifest_exists"] is False
        assert stage["backup_count"] == 0
    assert data["stuck_runs"] == 0


def test_pipeline_health_flags_stale_barrier(client, tmp_path):
    import time as _time
    pid = _add_embedded(client, tmp_path)

    project_obj = server._registry.get_project(pid)
    idx_dir = project_index_dir(project_obj)
    idx_dir.mkdir(parents=True, exist_ok=True)
    barrier_file = idx_dir / ".reset_barrier"
    old_ts = _time.time() - 3 * 3600
    barrier_file.write_text(f"{old_ts}\nstale_test\n")

    res = client.get(f"/projects/{pid}/pipeline/health")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["barrier"]["active"] is True
    # Warning for stale barrier > 1h old
    assert any("stale" in w.lower() for w in data["warnings"])

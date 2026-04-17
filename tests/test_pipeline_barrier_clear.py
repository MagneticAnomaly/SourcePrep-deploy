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


def test_barrier_lifecycle_end_to_end(client, tmp_path):
    """Full lifecycle: write → health sees active → DELETE → health sees inactive.

    Phase 114 audit #7: unit tests covered DELETE in isolation but never confirmed
    that `GET /pipeline/health` and `GET /pipeline/status` actually reflect the
    cleared state afterwards. This test locks the contract across endpoints.
    """
    from codrag.services.pipeline.recovery import write_reset_barrier, reset_barrier_active
    pid = _add_embedded(client, tmp_path)

    # 1. Write barrier directly (simulates a Reset/Rebuild)
    assert write_reset_barrier(pid, "enrichment_reset")
    assert reset_barrier_active(pid)

    # 2. Health endpoint must report barrier.active=true with matching reason
    res = client.get(f"/projects/{pid}/pipeline/health")
    assert res.status_code == 200
    health = res.json()["data"]
    assert health["barrier"]["active"] is True
    assert health["barrier"]["reason"] == "enrichment_reset"
    # age_seconds should be present and non-negative
    assert "age_seconds" in health["barrier"]
    assert health["barrier"]["age_seconds"] >= 0

    # 3. Pipeline status endpoint should also carry the barrier field
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    status = res.json()["data"]
    assert status.get("barrier", {}).get("active") is True

    # 4. DELETE the barrier
    res = client.delete(f"/projects/{pid}/pipeline/reset-barrier")
    assert res.status_code == 200
    assert res.json()["data"]["cleared"] is True

    # 5. File is gone on disk
    assert not reset_barrier_active(pid)

    # 6. Health endpoint reflects cleared state
    res = client.get(f"/projects/{pid}/pipeline/health")
    assert res.status_code == 200
    health = res.json()["data"]
    assert health["barrier"]["active"] is False

    # 7. Pipeline status also reflects cleared state
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    status = res.json()["data"]
    assert status.get("barrier", {}).get("active") is False

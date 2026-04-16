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


def _seed_golden(idx_dir: Path, stage_manifest: str):
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / stage_manifest).write_text('{"status":"complete"}')


def _seed_branch_snapshot(idx_dir: Path, dir_name: str, stage_manifest: str):
    import json as _json, time as _time
    snap = idx_dir / ".branch_snapshots" / dir_name
    snap.mkdir(parents=True, exist_ok=True)
    (snap / stage_manifest).write_text('{"status":"complete"}')
    (snap / "_snapshot_meta.json").write_text(_json.dumps({
        "created_at": "2026-04-15T12:00:00+00:00",
    }))


def test_stage_backups_empty_for_fresh_project(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/stages/atlas/backups")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["stage_id"] == "atlas"
    assert data["backups"] == []


def test_stage_backups_lists_golden(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    project_obj = server._registry.get_project(pid)
    idx_dir = project_index_dir(project_obj)
    _seed_golden(idx_dir, "atlas_manifest.json")

    res = client.get(f"/projects/{pid}/pipeline/stages/atlas/backups")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["backups"]) == 1
    bk = data["backups"][0]
    assert bk["kind"] == "golden"
    assert bk["snapshot_id"] == "golden"
    assert bk["branch"] is None
    assert isinstance(bk["created_at"], (int, float))
    assert bk["size_bytes"] > 0
    assert bk["file_count"] >= 1


def test_stage_backups_lists_branch_snapshot(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    project_obj = server._registry.get_project(pid)
    idx_dir = project_index_dir(project_obj)
    _seed_branch_snapshot(idx_dir, "feature--foo", "atlas_manifest.json")

    res = client.get(f"/projects/{pid}/pipeline/stages/atlas/backups")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["backups"]) == 1
    bk = data["backups"][0]
    assert bk["kind"] == "branch"
    assert bk["snapshot_id"] == "feature--foo"
    assert bk["branch"] == "feature/foo"
    assert isinstance(bk["created_at"], (int, float))


def test_stage_backups_uses_canonical_manifest_name(client, tmp_path):
    """Regression: structural uses trace_manifest.json, not structural_manifest.json."""
    pid = _add_embedded(client, tmp_path)
    project_obj = server._registry.get_project(pid)
    idx_dir = project_index_dir(project_obj)
    _seed_golden(idx_dir, "trace_manifest.json")

    res = client.get(f"/projects/{pid}/pipeline/stages/structural/backups")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["backups"]) == 1
    assert data["backups"][0]["kind"] == "golden"


def test_stage_backups_rejects_unknown_stage(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/stages/not-a-real-stage/backups")
    assert res.status_code == 404

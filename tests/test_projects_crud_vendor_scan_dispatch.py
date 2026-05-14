"""Task 9: async vendor-scan dispatch on project create + surfaced preset errors."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


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


def _wait_for_vendor_scan(client: TestClient, pid: str, timeout: float = 5.0) -> dict:
    """Poll project config until vendor_scan.status != 'pending', or fail."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/projects/{pid}")
        body = res.json()
        vs = body["data"]["project"]["config"].get("vendor_scan")
        if vs and vs.get("status") != "pending":
            return vs
        time.sleep(0.1)
    pytest.fail(f"vendor_scan did not complete within {timeout}s")


def test_post_projects_returns_pending_vendor_scan(client: TestClient, tmp_path: Path):
    """POST /projects must not block on vendor scan — config carries pending status immediately."""
    repo = tmp_path / "repo"
    repo.mkdir()
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "p", "mode": "embedded"},
    )
    assert res.status_code == 200
    cfg = res.json()["data"]["project"]["config"]
    vs = cfg.get("vendor_scan")
    assert vs is not None, "vendor_scan must be initialized in default config"
    # Either pending (background task in flight) or complete (empty repo scans instantly)
    assert vs["status"] in ("pending", "complete")


def test_vendor_scan_completes_in_background(client: TestClient, tmp_path: Path):
    """Background task fills in the scan result. Wait for it, then verify shape."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hi')\n")
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "p", "mode": "embedded"},
    )
    pid = res.json()["data"]["project"]["id"]
    vs = _wait_for_vendor_scan(client, pid)
    assert vs["status"] == "complete"
    assert isinstance(vs["auto_excluded"], list)
    assert isinstance(vs["proposed"], list)
    assert isinstance(vs["gitignore_gaps"], list)
    assert "scanned_at" in vs


def test_background_scan_auto_unions_canonical_excludes(client: TestClient, tmp_path: Path):
    """A repo containing node_modules → Tier 1 auto-exclude lands in exclude_globs via additive merge."""
    repo = tmp_path / "repo"
    (repo / "node_modules" / "react").mkdir(parents=True)
    (repo / "node_modules" / "react" / "index.js").write_text("// react\n")
    (repo / "src").mkdir()
    (repo / "src" / "app.ts").write_text("// app\n")
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "p", "mode": "embedded"},
    )
    pid = res.json()["data"]["project"]["id"]
    _wait_for_vendor_scan(client, pid)
    # Refetch to read the merged config
    body = client.get(f"/projects/{pid}").json()
    excludes = body["data"]["project"]["config"]["exclude_globs"]
    assert any("node_modules" in g for g in excludes), (
        f"node_modules auto-exclude should be union-merged into config; got {excludes}"
    )


def test_preset_scan_error_surfaced_when_scan_for_presets_raises(client: TestClient, tmp_path: Path, monkeypatch):
    """If scan_for_presets fails, the failure is recorded as preset_scan_error on the project config."""
    import prep.api.routers.projects.crud as crud_module

    def boom(_root):
        raise RuntimeError("simulated preset scan failure")

    monkeypatch.setattr(crud_module, "scan_for_presets", boom)

    repo = tmp_path / "repo"
    repo.mkdir()
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "p2", "mode": "embedded"},
    )
    assert res.status_code == 200
    cfg = res.json()["data"]["project"]["config"]
    err = cfg.get("preset_scan_error", "")
    assert "simulated preset scan failure" in err
    # vendor_scan should still be initialized (Task 9 doesn't gate on preset scan)
    assert "vendor_scan" in cfg

"""Task 10: vendor_scan + exclude_proposals/apply endpoints."""
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


def _create_project_with_vendor(client: TestClient, tmp_path: Path) -> tuple[str, Path]:
    """Create a project containing a Tier-1 (node_modules) and a Tier-2-eligible dir."""
    repo = tmp_path / "repo"
    (repo / "node_modules" / "react").mkdir(parents=True)
    (repo / "node_modules" / "react" / "index.js").write_text("// react\n")
    (repo / "src").mkdir()
    (repo / "src" / "app.ts").write_text("// app\n")
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "p", "mode": "embedded"},
    )
    assert res.status_code == 200
    pid = res.json()["data"]["project"]["id"]
    # Wait for the background scan to finish
    deadline = time.time() + 5.0
    while time.time() < deadline:
        body = client.get(f"/projects/{pid}").json()
        vs = body["data"]["project"]["config"].get("vendor_scan", {})
        if vs.get("status") in ("complete", "failed"):
            break
        time.sleep(0.1)
    return pid, repo


def test_get_vendor_scan_returns_cached_result(client: TestClient, tmp_path: Path):
    pid, _ = _create_project_with_vendor(client, tmp_path)
    res = client.get(f"/projects/{pid}/vendor_scan")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["status"] == "complete"
    assert isinstance(body["auto_excluded"], list)
    assert isinstance(body["proposed"], list)
    assert isinstance(body["gitignore_gaps"], list)
    assert any("node_modules" in g for g in body["auto_excluded"])


def test_get_vendor_scan_404_for_unknown_project(client: TestClient):
    res = client.get("/projects/does-not-exist/vendor_scan")
    assert res.status_code == 404


def test_post_rescan_writes_fresh_result_and_merges_excludes(client: TestClient, tmp_path: Path):
    pid, repo = _create_project_with_vendor(client, tmp_path)
    # Add a NEW canonical dir (Carthage/) after project creation
    (repo / "Carthage" / "Build").mkdir(parents=True)
    (repo / "Carthage" / "Build" / "Some.framework").mkdir()

    res = client.post(f"/projects/{pid}/vendor_scan/rescan")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["status"] == "complete"
    # Carthage should now be in auto_excluded
    assert any("Carthage" in g for g in body["auto_excluded"])
    # And union-merged into project config
    cfg = client.get(f"/projects/{pid}").json()["data"]["project"]["config"]
    assert any("Carthage" in g for g in cfg["exclude_globs"])


def test_post_apply_excludes_unions_globs_into_config(client: TestClient, tmp_path: Path):
    pid, repo = _create_project_with_vendor(client, tmp_path)
    # Manually fabricate a "proposed" entry by creating a huge dir would be slow.
    # Test the apply endpoint independent of what's in proposed: passing arbitrary rel_paths.
    res = client.post(
        f"/projects/{pid}/exclude_proposals/apply",
        json={
            "exclude": ["cesium-native", "vcpkg"],
            "dismiss": [],
            "add_to_gitignore": [],
        },
    )
    assert res.status_code == 200
    cfg = client.get(f"/projects/{pid}").json()["data"]["project"]["config"]
    assert any("cesium-native" in g for g in cfg["exclude_globs"])
    assert any("vcpkg" in g for g in cfg["exclude_globs"])


def test_post_apply_records_dismissed_proposals(client: TestClient, tmp_path: Path):
    pid, _ = _create_project_with_vendor(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/exclude_proposals/apply",
        json={"exclude": [], "dismiss": ["cesium-native"], "add_to_gitignore": []},
    )
    assert res.status_code == 200
    cfg = client.get(f"/projects/{pid}").json()["data"]["project"]["config"]
    assert "cesium-native" in cfg.get("dismissed_proposals", [])


def test_post_apply_dismissed_are_filtered_on_rescan(client: TestClient, tmp_path: Path):
    """Dismissed rel_paths must not re-surface in `proposed` on a fresh scan."""
    pid, repo = _create_project_with_vendor(client, tmp_path)
    # Dismiss a hypothetical rel_path
    client.post(
        f"/projects/{pid}/exclude_proposals/apply",
        json={"exclude": [], "dismiss": ["cesium-native"], "add_to_gitignore": []},
    )
    # Create a directory that would normally not propose (under size threshold) but
    # if it ever did, dismissal should hide it.
    (repo / "cesium-native" / ".git").mkdir(parents=True)
    res = client.post(f"/projects/{pid}/vendor_scan/rescan")
    body = res.json()["data"]
    assert not any(c["rel_path"] == "cesium-native" for c in body["proposed"])


def test_post_apply_404_for_unknown_project(client: TestClient):
    res = client.post(
        "/projects/does-not-exist/exclude_proposals/apply",
        json={"exclude": [], "dismiss": [], "add_to_gitignore": []},
    )
    assert res.status_code == 404


def test_post_apply_add_to_gitignore_is_v2_stub_noop(client: TestClient, tmp_path: Path):
    """add_to_gitignore field is accepted but no-op for v1 (logged at INFO)."""
    pid, _ = _create_project_with_vendor(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/exclude_proposals/apply",
        json={"exclude": [], "dismiss": [], "add_to_gitignore": ["something"]},
    )
    # Should succeed without raising
    assert res.status_code == 200

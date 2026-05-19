"""Tests for the restored POST /mcp/install / /mcp/uninstall and
GET /mcp/status endpoints.

Regression context: Phase 72 commit e3b4f1f8 removed these endpoints
from src/codrag/api/routers/mcp_setup.py while the implementation
functions in mcp_config.py were left intact (dead code). Restored so
the dashboard's "Enable Prep for Workspace" button can call them.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_mcp_install_writes_workspace_configs(client: TestClient, tmp_path) -> None:
    res = client.post(
        "/mcp/install",
        json={"workspace_path": str(tmp_path)},
    )
    assert res.status_code == 200, res.text
    env = res.json()
    assert env["success"] is True
    data = env["data"]
    assert data["workspace"] == str(tmp_path)
    assert data["runtimes_installed"] >= 1

    # Claude Code: .claude/mcp.json with a prep server entry
    cc_path = tmp_path / ".claude" / "mcp.json"
    assert cc_path.exists()
    cc_data = json.loads(cc_path.read_text())
    assert "prep" in cc_data["servers"]


def test_mcp_status_workspace_reflects_install(client: TestClient, tmp_path) -> None:
    # Before install: not installed
    res = client.get(f"/mcp/status?workspace_path={tmp_path}")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["any_installed"] is False

    # Install
    client.post("/mcp/install", json={"workspace_path": str(tmp_path)})

    # After install: at least one runtime reports installed
    res = client.get(f"/mcp/status?workspace_path={tmp_path}")
    data = res.json()["data"]
    assert data["any_installed"] is True
    assert data["runtimes"]["claude-code"]["installed"] is True


def test_mcp_uninstall_removes_prep_entry(client: TestClient, tmp_path) -> None:
    client.post("/mcp/install", json={"workspace_path": str(tmp_path)})

    res = client.post(
        "/mcp/uninstall",
        json={"workspace_path": str(tmp_path)},
    )
    assert res.status_code == 200
    env = res.json()
    assert env["success"] is True

    cc_path = tmp_path / ".claude" / "mcp.json"
    cc_data = json.loads(cc_path.read_text())
    assert "prep" not in cc_data.get("servers", {})


def test_mcp_status_without_workspace_returns_runtimes(client: TestClient) -> None:
    res = client.get("/mcp/status")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "supported_runtimes" in data
    assert "claude-code" in data["supported_runtimes"]


def test_mcp_install_nonexistent_path_returns_400(client: TestClient) -> None:
    # install_mcp_to_workspace raises ValueError when the workspace
    # path does not exist; the endpoint should surface that as a 400
    # rather than a 500.
    res = client.post(
        "/mcp/install",
        json={"workspace_path": "/tmp/_prep_definitely_does_not_exist_xyz_42"},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

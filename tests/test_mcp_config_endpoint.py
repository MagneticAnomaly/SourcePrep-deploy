import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_mcp_config_default_daemon_url_uses_base_url(client: TestClient) -> None:
    res = client.get("/mcp/config?ide=cursor&mode=auto")
    assert res.status_code == 200
    env = res.json()
    assert env["success"] is True
    data = env["data"]
    assert data["daemon_url"] == "http://testserver"
    assert data["file"] == ".cursor/mcp.json"
    assert "config" in data


def test_mcp_config_cursor_auto_with_explicit_daemon_url(client: TestClient) -> None:
    res = client.get(
        "/mcp/config?ide=cursor&mode=auto&daemon_url=http://127.0.0.1:8400"
    )
    assert res.status_code == 200
    env = res.json()
    assert env["success"] is True
    data = env["data"]

    assert data["daemon_url"] == "http://127.0.0.1:8400"
    assert data["file"] == ".cursor/mcp.json"

    cfg = data["config"]
    server_cfg = cfg["mcpServers"]["prep"]
    # _detect_prep_command resolves to an absolute path when one is
    # available so spawn-context consumers (Claude Desktop, Cursor) can
    # find the binary without inheriting the shell PATH.
    assert server_cfg["command"] == "prep" or server_cfg["command"].endswith("/prep")
    assert server_cfg["args"][0] == "mcp"
    assert "--auto" in server_cfg["args"]
    assert "--daemon" in server_cfg["args"]


def test_mcp_config_project_mode_requires_project_id(client: TestClient) -> None:
    res = client.get(
        "/mcp/config?ide=cursor&mode=project&daemon_url=http://127.0.0.1:8400"
    )
    assert res.status_code == 400


def test_mcp_config_project_mode_includes_project_arg(client: TestClient) -> None:
    res = client.get(
        "/mcp/config?ide=cursor&mode=project&project_id=proj_123&daemon_url=http://127.0.0.1:8400"
    )
    assert res.status_code == 200
    env = res.json()
    assert env["success"] is True
    data = env["data"]

    cfg = data["config"]
    server_cfg = cfg["mcpServers"]["prep"]
    assert "--project" in server_cfg["args"]
    assert "proj_123" in server_cfg["args"]


def test_mcp_config_all_returns_configs_object(client: TestClient) -> None:
    res = client.get(
        "/mcp/config?ide=all&mode=auto&daemon_url=http://127.0.0.1:8400"
    )
    assert res.status_code == 200
    env = res.json()
    assert env["success"] is True
    data = env["data"]
    assert "configs" in data
    assert "cursor" in data["configs"]
    assert "vscode" in data["configs"]

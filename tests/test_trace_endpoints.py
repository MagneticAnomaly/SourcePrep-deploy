from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
from codrag.core.ids import stable_file_node_id
from codrag.core.project_registry import ProjectRegistry
from codrag.core.trace import TraceBuilder
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg

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
    body = res.json()
    assert body["success"] is True
    return str(body["data"]["project"]["id"])


def _enable_trace(client: TestClient, project_id: str) -> None:
    res = client.get(f"/projects/{project_id}")
    assert res.status_code == 200
    body = res.json()
    cfg = dict(body["data"]["project"]["config"] or {})
    cfg["trace"] = {"enabled": True}

    res2 = client.put(f"/projects/{project_id}", json={"config": cfg})
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["success"] is True


def _disable_trace(client: TestClient, project_id: str) -> None:
    res = client.get(f"/projects/{project_id}")
    assert res.status_code == 200
    body = res.json()
    cfg = dict(body["data"]["project"]["config"] or {})
    cfg["trace"] = {"enabled": False}

    res2 = client.put(f"/projects/{project_id}", json={"config": cfg})
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["success"] is True
    
    # Verify it stuck
    res3 = client.get(f"/projects/{project_id}")
    body3 = res3.json()
    trace_cfg = body3["data"]["project"]["config"]["trace"]
    assert trace_cfg["enabled"] is False


def _build_trace_index(project_id: str, repo_root: Path) -> None:
    proj = server._get_registry().get_project(project_id)
    assert proj is not None

    cfg = proj.config or {}
    include_globs = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_globs = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)

    builder = TraceBuilder(
        repo_root=repo_root,
        index_dir=repo_root / ".codrag",
        include_globs=list(include_globs) if isinstance(include_globs, list) else None,
        exclude_globs=list(exclude_globs) if isinstance(exclude_globs, list) else None,
        max_file_bytes=max_file_bytes,
    )
    builder.build()


def test_trace_node_and_neighbors_require_trace_enabled(client: TestClient, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "a.py").write_text("def alpha():\n    return 1\n")

    project_id = _add_embedded_project(client, repo_root)
    _disable_trace(client, project_id)

    node_id = quote(stable_file_node_id("a.py"), safe="")

    res = client.get(f"/projects/{project_id}/trace/node/{node_id}")
    assert res.status_code == 409
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TRACE_DISABLED"

    res2 = client.get(f"/projects/{project_id}/trace/neighbors/{node_id}")
    assert res2.status_code == 409
    body2 = res2.json()
    assert body2["success"] is False
    assert body2["error"]["code"] == "TRACE_DISABLED"


def test_trace_search_node_and_neighbors_endpoints(client: TestClient, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    (repo_root / "a.py").write_text("import b\n\n\ndef alpha():\n    return 1\n")
    (repo_root / "b.py").write_text("class B:\n    pass\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    res = client.post(
        f"/projects/{project_id}/trace/search",
        json={"query": "alpha", "kinds": ["symbol"], "limit": 20},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    nodes = body["data"]["nodes"]
    assert any(n.get("kind") == "symbol" and n.get("name") == "alpha" for n in nodes)

    res_get = client.get(f"/projects/{project_id}/trace/search", params={"query": "alpha", "kind": "symbol"})
    assert res_get.status_code == 200
    body_get = res_get.json()
    assert body_get["success"] is True
    nodes_get = body_get["data"]["nodes"]
    assert any(n.get("kind") == "symbol" and n.get("name") == "alpha" for n in nodes_get)

    file_node_id = quote(stable_file_node_id("a.py"), safe="")

    res_node = client.get(f"/projects/{project_id}/trace/node/{file_node_id}")
    assert res_node.status_code == 200
    body_node = res_node.json()
    assert body_node["success"] is True
    assert body_node["data"]["node"]["id"] == stable_file_node_id("a.py")

    res_node_alias = client.get(f"/projects/{project_id}/trace/nodes/{file_node_id}")
    assert res_node_alias.status_code == 200
    body_node_alias = res_node_alias.json()
    assert body_node_alias["success"] is True
    assert body_node_alias["data"]["node"]["id"] == stable_file_node_id("a.py")

    res_neighbors_default = client.get(f"/projects/{project_id}/trace/neighbors/{file_node_id}")
    assert res_neighbors_default.status_code == 200
    body_neighbors_default = res_neighbors_default.json()
    assert body_neighbors_default["success"] is True

    nodes_default = body_neighbors_default["data"]["nodes"]
    edges_default = body_neighbors_default["data"]["edges"]

    node_ids = {n.get("id") for n in nodes_default}
    assert stable_file_node_id("a.py") in node_ids
    assert stable_file_node_id("b.py") in node_ids

    assert all(e.get("kind") == "imports" for e in edges_default)

    res_neighbors_both = client.get(
        f"/projects/{project_id}/trace/neighbors/{file_node_id}?edge_kinds=imports&edge_kinds=contains"
    )
    assert res_neighbors_both.status_code == 200
    body_neighbors_both = res_neighbors_both.json()
    assert body_neighbors_both["success"] is True
    edge_kinds = {e.get("kind") for e in body_neighbors_both["data"]["edges"]}
    assert "imports" in edge_kinds
    assert "contains" in edge_kinds


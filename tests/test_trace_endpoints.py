from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.ids import stable_file_node_id
from codrag.core.project_registry import ProjectRegistry
from codrag.core.trace import TraceBuilder
from codrag.server import app


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


def test_trace_node_and_neighbors_when_trace_disabled_and_no_data(client: TestClient, tmp_path: Path) -> None:
    """F-49: read endpoints no longer gate on `trace.enabled` — they serve
    disk data regardless of the auto-build preference flag.  When
    `enabled=false` AND no trace data exists on disk, the response is now
    `TRACE_NOT_BUILT` (was `TRACE_DISABLED`).  See registry F-49 / F-50 for
    rationale: `enabled` is the auto-rebuild preference, not a data-presence
    flag, so read access should not be gated on it.
    """
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
    assert body["error"]["code"] == "TRACE_NOT_BUILT"

    res2 = client.get(f"/projects/{project_id}/trace/neighbors/{node_id}")
    assert res2.status_code == 409
    body2 = res2.json()
    assert body2["success"] is False
    assert body2["error"]["code"] == "TRACE_NOT_BUILT"


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


# ═══════════════════════════════════════════════════════════════
# W4a: Impact Graph Tests (Phase 39)
# ═══════════════════════════════════════════════════════════════

def test_impact_graph_known_callers(client: TestClient, tmp_path: Path) -> None:
    """A file that imports another should appear as a dependent in the impact graph."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    # b.py imports a → b depends on a → b is in a's impact graph
    (repo_root / "a.py").write_text("def helper():\n    return 1\n")
    (repo_root / "b.py").write_text("import a\n\ndef caller():\n    return a.helper()\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    file_node_id = quote(stable_file_node_id("a.py"), safe="")

    res = client.get(f"/projects/{project_id}/trace/impact/{file_node_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True

    data = body["data"]
    assert data["target"]["id"] == stable_file_node_id("a.py")
    assert data["total_dependents"] >= 1

    dep_paths = [d["path"] for d in data["dependents"]]
    assert any("b.py" in p for p in dep_paths), f"Expected b.py in dependents, got: {dep_paths}"


def test_impact_graph_max_hops_1(client: TestClient, tmp_path: Path) -> None:
    """With max_hops=1, only direct dependents should appear."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    # c imports b imports a → with max_hops=1 on a, only b should appear
    (repo_root / "a.py").write_text("X = 1\n")
    (repo_root / "b.py").write_text("import a\nY = a.X\n")
    (repo_root / "c.py").write_text("import b\nZ = b.Y\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    file_node_id = quote(stable_file_node_id("a.py"), safe="")

    res = client.get(f"/projects/{project_id}/trace/impact/{file_node_id}?max_hops=1")
    assert res.status_code == 200
    data = res.json()["data"]

    # All dependents should be distance=1
    for dep in data["dependents"]:
        assert dep["distance"] == 1, f"Expected distance=1, got {dep['distance']} for {dep['path']}"


def test_impact_graph_no_dependents(client: TestClient, tmp_path: Path) -> None:
    """A leaf file with no importers should return an empty impact graph."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    (repo_root / "leaf.py").write_text("X = 42\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    file_node_id = quote(stable_file_node_id("leaf.py"), safe="")

    res = client.get(f"/projects/{project_id}/trace/impact/{file_node_id}")
    assert res.status_code == 200
    data = res.json()["data"]

    # File-level node may have symbol children as "dependents" via contains edges,
    # but since we only follow in-edges (callers/importers), a truly isolated file
    # should have zero dependents at file level.
    assert data["total_dependents"] == 0
    assert data["dependents"] == []


def test_impact_graph_not_found(client: TestClient, tmp_path: Path) -> None:
    """Impact graph for a non-existent node returns 404."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "a.py").write_text("X = 1\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    res = client.get(f"/projects/{project_id}/trace/impact/nonexistent_node_id")
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════
# W1a: LSP Edge Ingestion Tests (Phase 39)
# ═══════════════════════════════════════════════════════════════

def test_lsp_edges_accepted(client: TestClient, tmp_path: Path) -> None:
    """Valid LSP edges with known source/target are accepted and persisted."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "a.py").write_text("import b\n")
    (repo_root / "b.py").write_text("X = 1\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    src_id = stable_file_node_id("a.py")
    tgt_id = stable_file_node_id("b.py")

    res = client.post(
        f"/projects/{project_id}/trace/lsp-edges",
        json={"edges": [{"source": src_id, "target": tgt_id, "kind": "calls"}]},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["accepted"] == 1
    assert data["rejected_unknown_node"] == 0
    assert data["rejected_duplicate"] == 0

    # Verify the LSP edges file was created
    lsp_path = repo_root / ".codrag" / "trace_lsp_edges.jsonl"
    assert lsp_path.exists()
    import json
    edges = [json.loads(line) for line in lsp_path.read_text().strip().split("\n") if line.strip()]
    assert len(edges) == 1
    assert edges[0]["source"] == src_id
    assert edges[0]["target"] == tgt_id
    assert edges[0]["kind"] == "calls"
    assert edges[0]["origin"] == "lsp"


def test_lsp_edges_rejects_unknown_nodes(client: TestClient, tmp_path: Path) -> None:
    """LSP edges referencing non-existent nodes are rejected."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "a.py").write_text("X = 1\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    src_id = stable_file_node_id("a.py")

    res = client.post(
        f"/projects/{project_id}/trace/lsp-edges",
        json={"edges": [{"source": src_id, "target": "file:nonexistent.py", "kind": "calls"}]},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["accepted"] == 0
    assert data["rejected_unknown_node"] == 1


def test_lsp_edges_deduplicates(client: TestClient, tmp_path: Path) -> None:
    """Submitting the same LSP edge twice should deduplicate."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "a.py").write_text("import b\n")
    (repo_root / "b.py").write_text("X = 1\n")

    project_id = _add_embedded_project(client, repo_root)
    _enable_trace(client, project_id)
    _build_trace_index(project_id, repo_root)

    src_id = stable_file_node_id("a.py")
    tgt_id = stable_file_node_id("b.py")
    edge_payload = {"edges": [{"source": src_id, "target": tgt_id, "kind": "calls"}]}

    # First submit
    res1 = client.post(f"/projects/{project_id}/trace/lsp-edges", json=edge_payload)
    assert res1.json()["data"]["accepted"] == 1

    # Second submit — same edge — should be deduped
    res2 = client.post(f"/projects/{project_id}/trace/lsp-edges", json=edge_payload)
    data2 = res2.json()["data"]
    assert data2["accepted"] == 0
    assert data2["rejected_duplicate"] == 1


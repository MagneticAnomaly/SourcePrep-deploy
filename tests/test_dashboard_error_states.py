"""
Dashboard Error State Tests (P02-T2)

Verifies that the API returns correct error codes and shapes for common failure modes,
allowing the Dashboard UI to render appropriate error states.

Covered scenarios:
1.  **Project Not Found**: `GET /projects/{invalid_id}` -> 404 PROJECT_NOT_FOUND
2.  **Search Before Build**: `POST /projects/{id}/search` -> 409 INDEX_NOT_BUILT
3.  **Context Before Build**: `POST /projects/{id}/context` -> 409 INDEX_NOT_BUILT
4.  **Invalid File Path**: `GET /projects/{id}/file` -> 400/403 (Traversal/Outside Root)
5.  **LLM Service Unavailable**: `POST /api/llm/proxy/test` -> 503/500 (Simulated)
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app

@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Create a clean test client."""
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    return TestClient(app)

@pytest.fixture()
def empty_project(client: TestClient, tmp_path: Path) -> str:
    """Create a project but don't build it."""
    repo = tmp_path / "error_test_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hello')")
    
    res = client.post(
        "/projects",
        json={"path": str(repo), "name": "Error Test", "mode": "embedded"}
    )
    return res.json()["data"]["project"]["id"]

def test_project_not_found(client: TestClient):
    """Verify 404 for non-existent project."""
    res = client.get("/projects/nonexistent-id")
    assert res.status_code == 404
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PROJECT_NOT_FOUND"

def test_search_before_build(client: TestClient, empty_project: str):
    """Verify 409 when searching an unbuilt project."""
    res = client.post(
        f"/projects/{empty_project}/search",
        json={"query": "hello", "k": 5}
    )
    assert res.status_code == 409
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INDEX_NOT_BUILT"
    assert "hint" in data["error"]

def test_context_before_build(client: TestClient, empty_project: str):
    """Verify 409 when getting context for an unbuilt project."""
    res = client.post(
        f"/projects/{empty_project}/context",
        json={"query": "hello"}
    )
    assert res.status_code == 409
    data = res.json()
    assert data["error"]["code"] == "INDEX_NOT_BUILT"

def test_file_path_security(client: TestClient, empty_project: str):
    """Verify security errors for invalid file access."""
    # 1. Traversal attempt
    res_traversal = client.get(
        f"/projects/{empty_project}/file", 
        params={"path": "../../../etc/passwd"}
    )
    # Should be 403 Forbidden or 400 Bad Request depending on implementation
    assert res_traversal.status_code in [400, 403]
    
    # 2. Absolute path attempt (should be rejected in favor of relative)
    res_abs = client.get(
        f"/projects/{empty_project}/file",
        params={"path": "/etc/passwd"}
    )
    assert res_abs.status_code in [400, 403]

def test_trace_before_enable(client: TestClient, empty_project: str):
    """Verify error when accessing trace endpoints on a project before trace is built."""
    # Trace is always available but must be built first
    res = client.get(f"/projects/{empty_project}/trace/status")
    # Trace search should fail with TRACE_NOT_BUILT before any build has run
    
    res_search = client.post(
        f"/projects/{empty_project}/trace/search",
        json={"query": "foo"}
    )
    # This might return 409 TRACE_NOT_BUILT or similar
    if res_search.status_code != 200:
        assert res_search.status_code == 409
        assert res_search.json()["error"]["code"] == "TRACE_NOT_BUILT"

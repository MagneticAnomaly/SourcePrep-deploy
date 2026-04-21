"""
Dashboard End-to-End Smoke Test (P02-T1)

This test suite verifies the critical "Trust Loop" user journey from the perspective of the Dashboard frontend.
It ensures that the backend API contracts match what the UI components expect.

Covered flows:
1.  **Add Project**: `POST /projects`
2.  **Initial Status**: `GET /projects/{id}/status`
3.  **Trigger Build**: `POST /projects/{id}/build`
4.  **Poll Completion**: Loop `GET /projects/{id}/status`
5.  **Search**: `POST /projects/{id}/search`
6.  **Read File (Pin/Open)**: `GET /projects/{id}/file?path=...` (New P02 feature)
7.  **Assemble Context**: `POST /projects/{id}/context`
"""

import time
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Create a clean test client."""
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg

    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    server._project_watchers.clear()

    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()

    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()

    return TestClient(app)


@pytest.fixture()
def mini_repo(tmp_path: Path) -> Path:
    """Create a minimal repo for testing."""
    repo = tmp_path / "dashboard_test_repo"
    repo.mkdir()

    (repo / "main.py").write_text('print("Hello Dashboard")\n')
    (repo / "README.md").write_text("# Dashboard Test\n\nVerifying P02 flows.")
    (repo / "docs").mkdir()
    (repo / "docs" / "arch.md").write_text("Architecture documentation.")
    
    return repo


def _wait_for_build(client: TestClient, project_id: str, timeout: float = 10.0):
    """Poll status until build is complete."""
    start = time.time()
    while time.time() - start < timeout:
        res = client.get(f"/projects/{project_id}/status")
        assert res.status_code == 200
        data = res.json()["data"]
        
        # Check if index exists and not building
        if data["index"]["exists"] and not data.get("building", False):
            return data
        
        time.sleep(0.1)
    raise TimeoutError("Build timed out")


def test_dashboard_trust_loop(client: TestClient, mini_repo: Path):
    """
    Simulate the full user journey:
    Add -> Check Status -> Build -> Search -> Inspect File -> Get Context
    """
    
    # 1. Add Project
    res_add = client.post(
        "/projects",
        json={"path": str(mini_repo), "name": "Dashboard Demo", "mode": "embedded"}
    )
    assert res_add.status_code == 200
    project = res_add.json()["data"]["project"]
    project_id = project["id"]
    assert project["name"] == "Dashboard Demo"

    # 2. Initial Status
    res_status = client.get(f"/projects/{project_id}/status")
    assert res_status.status_code == 200
    status = res_status.json()["data"]
    assert status["index"]["exists"] is False
    assert status.get("building") is False

    # 3. Trigger Build
    res_build = client.post(f"/projects/{project_id}/build")
    assert res_build.status_code == 200
    assert res_build.json()["success"] is True

    # 4. Poll Completion
    status_final = _wait_for_build(client, project_id)
    assert status_final["index"]["total_chunks"] >= 2  # main.py, README.md, arch.md

    # 5. Search
    res_search = client.post(
        f"/projects/{project_id}/search",
        json={"query": "Hello Dashboard", "k": 5}
    )
    assert res_search.status_code == 200
    results = res_search.json()["data"]["results"]
    assert len(results) > 0
    
    # Verify result structure matches UI expectations
    first_result = results[0]
    assert "source_path" in first_result
    assert "preview" in first_result
    assert "score" in first_result
    
    # 6. Read File (New P02 feature for Pinned Files / Inspection)
    # Get the file content for one of the search results
    target_path = "main.py"
    res_file = client.get(f"/projects/{project_id}/file", params={"path": target_path})
    assert res_file.status_code == 200
    file_data = res_file.json()["data"]["file"]
    
    assert file_data["path"] == target_path
    assert "print(\"Hello Dashboard\")" in file_data["content"]
    assert file_data["bytes"] > 0

    # Test file reading security (path traversal)
    res_bad = client.get(f"/projects/{project_id}/file", params={"path": "../../../etc/passwd"})
    assert res_bad.status_code == 403 or res_bad.status_code == 400
    
    # 7. Assemble Context
    res_context = client.post(
        f"/projects/{project_id}/context",
        json={"query": "Explain the architecture", "k": 3}
    )
    assert res_context.status_code == 200
    context_data = res_context.json()["data"]
    assert "context" in context_data
    assert len(context_data["context"]) > 0
    
    print("\n✅ Dashboard Trust Loop E2E Test Passed!")

"""
Integration tests for the core trust loop: add → build → search → context.

These tests verify the HTTP API endpoints work correctly end-to-end.
Run with: pytest tests/test_trust_loop_integration.py -v
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import prep.server as server
from prep.core import FakeEmbedder
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Create a test client with fresh state."""
    import prep.services.project_helpers as ph
    from prep.services.build_manager import build_manager as bm

    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    # Reset both the server-level and service-level registry singletons
    server._registry = reg
    ph._registry = reg

    # Reset build manager caches
    bm.project_indexes.clear()
    bm.project_trace_indexes.clear()
    bm.project_knowledge_indexes.clear()
    server._project_watchers.clear()

    with bm.build_lock:
        bm.build_threads.clear()
        bm.last_build_result.clear()
        bm.last_build_error.clear()

    with bm.trace_build_lock:
        bm.trace_build_threads.clear()

    return TestClient(app)


@pytest.fixture()
def mini_repo(tmp_path: Path) -> Path:
    """Create a minimal test repository with deterministic content."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    (repo / "main.py").write_text(
        '''"""Main module for the application."""

def main() -> str:
    """Return hello world."""
    return "hello world"

def greet(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(main())
'''
    )

    (repo / "utils.py").write_text(
        '''"""Utility functions."""

def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
'''
    )

    (repo / "README.md").write_text(
        """# Test Repository

This is a minimal test repository for integration testing.

## Features

- Hello world greeting
- Basic math utilities
"""
    )

    return repo


def _add_project(client: TestClient, repo_root: Path, name: str = "test") -> str:
    """Add a project and return its ID."""
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": name, "mode": "embedded"},
    )
    assert res.status_code == 200, f"Failed to add project: {res.text}"
    body = res.json()
    assert body["success"] is True, f"Add project failed: {body}"
    return str(body["data"]["project"]["id"])


def _wait_for_build(client: TestClient, project_id: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Wait for build to complete and return status."""
    start = time.time()
    while time.time() - start < timeout:
        res = client.get(f"/projects/{project_id}/status")
        assert res.status_code == 200
        body = res.json()
        status = body["data"]
        if status.get("building") is False and status.get("index", {}).get("exists") is True:
            return status
        time.sleep(0.1)
    raise TimeoutError(f"Build did not complete within {timeout}s")


class TestProjectLifecycle:
    """Test project add/list/get/delete operations."""

    def test_list_projects_empty(self, client: TestClient) -> None:
        """Empty registry should return empty list."""
        res = client.get("/projects")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["projects"] == []

    def test_add_project(self, client: TestClient, mini_repo: Path) -> None:
        """Adding a project should succeed."""
        project_id = _add_project(client, mini_repo)
        assert project_id is not None
        assert len(project_id) > 0

    def test_get_project(self, client: TestClient, mini_repo: Path) -> None:
        """Getting a project should return its details."""
        project_id = _add_project(client, mini_repo)

        res = client.get(f"/projects/{project_id}")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["project"]["id"] == project_id
        assert body["data"]["project"]["name"] == "test"
        assert body["data"]["project"]["path"] == str(mini_repo)

    def test_list_projects_with_project(self, client: TestClient, mini_repo: Path) -> None:
        """List should include added projects."""
        project_id = _add_project(client, mini_repo)

        res = client.get("/projects")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]["projects"]) == 1
        assert body["data"]["projects"][0]["id"] == project_id

    def test_delete_project(self, client: TestClient, mini_repo: Path) -> None:
        """Deleting a project should remove it."""
        project_id = _add_project(client, mini_repo)

        res = client.delete(f"/projects/{project_id}")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True

        res2 = client.get("/projects")
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["data"]["projects"] == []

    def test_get_nonexistent_project(self, client: TestClient) -> None:
        """Getting a nonexistent project should return 404."""
        res = client.get("/projects/nonexistent-id")
        assert res.status_code == 404
        body = res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PROJECT_NOT_FOUND"


class TestBuildOperations:
    """Test index build operations."""

    def test_build_project(self, client: TestClient, mini_repo: Path) -> None:
        """Building a project with explicit scope should populate the index.

        2026-05: untouched projects no longer default to "embed everything".
        The build request must carry explicit ``included_paths`` (or the
        project must have them in config) for any documents to be embedded.
        """
        project_id = _add_project(client, mini_repo)

        res = client.post(
            f"/projects/{project_id}/build",
            json={"included_paths": ["main.py", "utils.py", "README.md"]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        # Build returns either started status or building info
        assert "building" in body["data"] or "started" in body["data"]

        status = _wait_for_build(client, project_id)
        assert status["index"]["exists"] is True
        assert status["index"]["total_chunks"] > 0

    def test_build_status_before_build(self, client: TestClient, mini_repo: Path) -> None:
        """Status before build should show empty index."""
        project_id = _add_project(client, mini_repo)

        res = client.get(f"/projects/{project_id}/status")
        assert res.status_code == 200
        body = res.json()
        status = body["data"]
        assert status["index"]["exists"] is False
        assert status["index"]["total_chunks"] == 0


class TestSearchOperations:
    """Test semantic search operations."""

    def test_search_after_build(self, client: TestClient, mini_repo: Path) -> None:
        """Search should return results after build."""
        project_id = _add_project(client, mini_repo)
        client.post(
            f"/projects/{project_id}/build",
            json={"included_paths": ["main.py", "utils.py", "README.md"]},
        )
        _wait_for_build(client, project_id)

        res = client.post(
            f"/projects/{project_id}/search",
            json={"query": "hello world greeting", "k": 5},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]["results"]) > 0

        first_result = body["data"]["results"][0]
        assert "source_path" in first_result
        assert "score" in first_result
        assert "preview" in first_result

    def test_search_before_build(self, client: TestClient, mini_repo: Path) -> None:
        """Search before build should return error."""
        project_id = _add_project(client, mini_repo)

        res = client.post(
            f"/projects/{project_id}/search",
            json={"query": "hello", "k": 5},
        )
        # Search before build returns 409 INDEX_NOT_BUILT
        assert res.status_code == 409
        body = res.json()
        assert body["error"]["code"] == "INDEX_NOT_BUILT"

    def test_search_with_min_score(self, client: TestClient, mini_repo: Path) -> None:
        """Search with min_score should filter results."""
        project_id = _add_project(client, mini_repo)
        client.post(
            f"/projects/{project_id}/build",
            json={"included_paths": ["main.py", "utils.py", "README.md"]},
        )
        _wait_for_build(client, project_id)

        res = client.post(
            f"/projects/{project_id}/search",
            json={"query": "hello", "k": 10, "min_score": 0.99},
        )
        assert res.status_code == 200
        body = res.json()
        for result in body["data"]["results"]:
            assert result["score"] >= 0.99


class TestContextOperations:
    """Test context assembly operations."""

    def test_context_after_build(self, client: TestClient, mini_repo: Path) -> None:
        """Context assembly should return formatted context after build."""
        project_id = _add_project(client, mini_repo)
        client.post(
            f"/projects/{project_id}/build",
            json={"included_paths": ["main.py", "utils.py", "README.md"]},
        )
        _wait_for_build(client, project_id)

        res = client.post(
            f"/projects/{project_id}/context",
            json={"query": "greeting function", "k": 5, "min_score": 0.0},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "context" in body["data"]
        assert len(body["data"]["context"]) > 0

    def test_context_with_max_chars(self, client: TestClient, mini_repo: Path) -> None:
        """Context with max_chars should respect the limit."""
        project_id = _add_project(client, mini_repo)
        client.post(
            f"/projects/{project_id}/build",
            json={"included_paths": ["main.py", "utils.py", "README.md"]},
        )
        _wait_for_build(client, project_id)

        res = client.post(
            f"/projects/{project_id}/context",
            json={"query": "hello", "k": 10, "max_chars": 100, "min_score": 0.0},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        # Context is truncated to max_chars (with some buffer for headers)
        assert len(body["data"]["context"]) <= 100 + 500


class TestTrustLoopEndToEnd:
    """End-to-end test of the complete trust loop."""

    def test_full_trust_loop(self, client: TestClient, mini_repo: Path) -> None:
        """Test the complete add → build → search → context flow."""
        project_id = _add_project(client, mini_repo, name="trust_loop_test")

        res_get = client.get(f"/projects/{project_id}")
        assert res_get.status_code == 200
        assert res_get.json()["data"]["project"]["name"] == "trust_loop_test"

        res_build = client.post(
            f"/projects/{project_id}/build",
            json={"included_paths": ["main.py", "utils.py", "README.md"]},
        )
        assert res_build.status_code == 200

        status = _wait_for_build(client, project_id)
        assert status["index"]["exists"] is True
        assert status["index"]["total_chunks"] >= 3

        res_search = client.post(
            f"/projects/{project_id}/search",
            json={"query": "add two numbers", "k": 5},
        )
        assert res_search.status_code == 200
        search_body = res_search.json()
        assert len(search_body["data"]["results"]) > 0

        found_utils = any(
            "utils.py" in r.get("source_path", "") for r in search_body["data"]["results"]
        )
        assert found_utils, "Expected to find utils.py in search results"

        res_context = client.post(
            f"/projects/{project_id}/context",
            json={"query": "multiply numbers", "k": 3, "min_score": 0.0},
        )
        assert res_context.status_code == 200
        context_body = res_context.json()
        assert context_body["success"] is True
        assert len(context_body["data"]["context"]) > 0

        res_list = client.get("/projects")
        assert res_list.status_code == 200
        projects = res_list.json()["data"]["projects"]
        assert len(projects) == 1
        assert projects[0]["id"] == project_id


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_project_id(self, client: TestClient) -> None:
        """Invalid project ID should return 404."""
        res = client.get("/projects/invalid-uuid")
        assert res.status_code == 404
        body = res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_search_invalid_project(self, client: TestClient) -> None:
        """Search on invalid project should return 404."""
        res = client.post(
            "/projects/invalid-id/search",
            json={"query": "test", "k": 5},
        )
        assert res.status_code == 404

    def test_build_invalid_project(self, client: TestClient) -> None:
        """Build on invalid project should return 404."""
        res = client.post("/projects/invalid-id/build")
        assert res.status_code == 404

    def test_context_invalid_project(self, client: TestClient) -> None:
        """Context on invalid project should return 404."""
        res = client.post(
            "/projects/invalid-id/context",
            json={"query": "test", "k": 5},
        )
        assert res.status_code == 404

"""Tests for architecture router endpoints."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a minimal FastAPI app with the architecture router."""
    from fastapi import FastAPI
    from codrag.api.routers.architecture import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_project(tmp_path):
    """Mock project with trace modules data."""
    proj = MagicMock()
    proj.id = "test-project"
    proj.path = str(tmp_path / "repo")

    # Create index dir with module synthesis data
    idx_dir = tmp_path / "index"
    idx_dir.mkdir()

    modules = [
        {
            "module_id": "mod_auth",
            "name": "Authentication",
            "summary": "User auth and session management",
            "member_files": ["src/auth/login.py", "src/auth/session.py"],
            "domain_tags": ["security", "auth"],
            "architecture_layers": ["service"],
            "component_status": "complete",
            "file_count": 2,
            "avg_epistemic_confidence": 0.85,
            "dependencies": ["mod_db"],
        },
        {
            "module_id": "mod_db",
            "name": "Database",
            "summary": "Database access layer",
            "member_files": ["src/db/connection.py"],
            "domain_tags": ["data"],
            "architecture_layers": ["infrastructure"],
            "component_status": "complete",
            "file_count": 1,
            "avg_epistemic_confidence": 0.92,
            "dependencies": [],
        },
    ]
    modules_path = idx_dir / "trace_modules.jsonl"
    with open(modules_path, "w") as f:
        for m in modules:
            f.write(json.dumps(m) + "\n")

    # Create trace edges
    edges = [
        {"source": "file:src/auth/login.py", "target": "file:src/db/connection.py", "kind": "imports"},
        {"source": "file:src/auth/session.py", "target": "file:src/db/connection.py", "kind": "imports"},
    ]
    edges_path = idx_dir / "trace_edges.jsonl"
    with open(edges_path, "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")

    return proj, idx_dir


class TestGetArchitectureGraph:
    def test_returns_modules_and_edges(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/graph")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["exists"] is True
        assert len(data["modules"]) == 2
        assert data["stats"]["total_modules"] == 2
        # Should have aggregated edge from auth -> db
        assert len(data["edges"]) == 1
        assert data["edges"][0]["source"] == "mod_auth"
        assert data["edges"][0]["target"] == "mod_db"
        assert data["edges"][0]["count"] == 2

    def test_returns_empty_when_no_modules(self, client, mock_project):
        proj, idx_dir = mock_project
        (idx_dir / "trace_modules.jsonl").unlink()
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/graph")
        data = resp.json()["data"]
        assert data["exists"] is False
        assert data["modules"] == []

    def test_drill_into_module(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/graph?layer_path=mod_auth")
        data = resp.json()["data"]
        assert data["exists"] is True
        assert len(data["files"]) == 2
        assert data["modules"] == []
        # Should have external ref to mod_db
        assert len(data["external_refs"]) == 1
        assert data["external_refs"][0]["module_id"] == "mod_db"


class TestArchitectureSummary:
    def test_returns_summary(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.get(f"/projects/{proj.id}/architecture/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["module_count"] == 2
        assert data["file_count"] == 3
        assert data["note_count"] == 0


class TestNotesEndpoints:
    def test_create_and_list_notes(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Migrating to OAuth2", "note_type": "adr", "author": "user"},
            )
            assert resp.status_code == 200
            note = resp.json()["data"]
            assert note["content"] == "Migrating to OAuth2"

            resp = client.get(f"/projects/{proj.id}/architecture/notes")
            assert len(resp.json()["data"]) == 1

    def test_update_note(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Draft", "note_type": "comment", "author": "user"},
            )
            note_id = resp.json()["data"]["id"]

            resp = client.put(
                f"/projects/{proj.id}/architecture/notes/{note_id}",
                json={"content": "Final"},
            )
            assert resp.json()["data"]["content"] == "Final"

    def test_delete_note(self, client, mock_project):
        proj, idx_dir = mock_project
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Temp", "note_type": "comment", "author": "user"},
            )
            note_id = resp.json()["data"]["id"]

            resp = client.delete(f"/projects/{proj.id}/architecture/notes/{note_id}")
            assert resp.json()["data"]["deleted"] is True

            resp = client.get(f"/projects/{proj.id}/architecture/notes")
            assert len(resp.json()["data"]) == 0


class TestStatePersistence:
    def test_save_and_load_state(self, client, mock_project):
        proj, idx_dir = mock_project
        state = {
            "layouts": {
                "root": {
                    "layer_path": "",
                    "positions": [{"id": "mod_auth", "x": 100, "y": 200}],
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                }
            },
            "module_overrides": {},
        }
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            resp = client.put(f"/projects/{proj.id}/architecture/state", json=state)
            assert resp.status_code == 200

            resp = client.get(f"/projects/{proj.id}/architecture/state")
            loaded = resp.json()["data"]
            assert loaded["layouts"]["root"]["positions"][0]["x"] == 100


class TestArchitectureContext:
    def test_returns_mcp_context(self, client, mock_project):
        proj, idx_dir = mock_project
        # Add a note first
        with patch("codrag.api.routers.architecture._require_project", return_value=proj), \
             patch("codrag.api.routers.architecture._project_index_dir", return_value=idx_dir):
            client.post(
                f"/projects/{proj.id}/architecture/notes",
                json={"node_id": "mod_auth", "content": "Migrating to OAuth2", "note_type": "adr", "author": "user"},
            )

            resp = client.get(f"/projects/{proj.id}/architecture/context")
            data = resp.json()["data"]
            assert data["exists"] is True
            assert "Authentication" in data["text"]
            assert "Migrating to OAuth2" in data["text"]

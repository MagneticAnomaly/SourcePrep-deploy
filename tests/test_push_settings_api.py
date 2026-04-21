"""Tests for consensus and push summary API endpoints."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from fastapi import FastAPI
    from prep.api.routers.collaboration import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_consensus_endpoint_returns_scores(client):
    mock_store = MagicMock()
    mock_store.get_consensus_scores.return_value = [
        {
            "file_path": "src/auth.py",
            "agents": ["researcher", "custodian"],
            "agent_count": 2,
            "total_active_agents": 3,
            "consensus_score": 0.67,
            "latest_observation_at": 1000.0,
        }
    ]

    with patch(
        "prep.api.routers.collaboration._get_obs_store",
        return_value=mock_store,
    ):
        resp = client.get("/projects/proj-1/collaboration/consensus")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["scores"]) == 1
    assert data["scores"][0]["file_path"] == "src/auth.py"


def test_consensus_endpoint_empty(client):
    mock_store = MagicMock()
    mock_store.get_consensus_scores.return_value = []

    with patch(
        "prep.api.routers.collaboration._get_obs_store",
        return_value=mock_store,
    ):
        resp = client.get("/projects/proj-1/collaboration/consensus")

    assert resp.status_code == 200
    assert resp.json()["data"]["scores"] == []

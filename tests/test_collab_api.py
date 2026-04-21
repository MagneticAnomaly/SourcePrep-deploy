"""Tests for FastAPI collaboration routes."""
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from prep.api.routers.collaboration import router
from prep.services.collaboration import CollaborationHub
from prep.services.observation_store import ObservationStore


@pytest.fixture
def app_and_client(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(router)

    hub = CollaborationHub(tmp_path / "test.db")
    obs = ObservationStore()
    obs.init(tmp_path / "test.db")

    # Patch the helper functions to return our test instances
    import prep.api.routers.collaboration as mod
    monkeypatch.setattr(mod, "_get_hub", lambda: hub)
    monkeypatch.setattr(mod, "_get_obs_store", lambda: obs)

    client = TestClient(app)
    yield client, hub, obs
    obs.close()


def test_get_activity_empty(app_and_client):
    client, hub, obs = app_and_client
    resp = client.get("/projects/proj-1/collaboration/activity")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["entries"] == []


def test_get_activity_with_entries(app_and_client):
    client, hub, obs = app_and_client
    hub.activity.log("proj-1", "pi/watchdog", "scan", "Test scan")

    resp = client.get("/projects/proj-1/collaboration/activity")
    assert resp.status_code == 200
    entries = resp.json()["data"]["entries"]
    assert len(entries) == 1
    assert entries[0]["agent_role"] == "pi/watchdog"


def test_get_observations_by_agent(app_and_client):
    client, hub, obs = app_and_client
    obs.save("proj-1", "Researcher note", created_by="researcher")
    obs.save("proj-1", "Custodian note", created_by="custodian")

    resp = client.get(
        "/projects/proj-1/collaboration/observations",
        params={"created_by": "researcher"},
    )
    assert resp.status_code == 200
    entries = resp.json()["data"]["observations"]
    assert len(entries) == 1
    assert entries[0]["created_by"] == "researcher"


def test_get_delta_no_snapshots(app_and_client):
    client, hub, obs = app_and_client
    resp = client.get("/projects/proj-1/collaboration/delta")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_empty"] is True


def test_get_conflicts_empty(app_and_client):
    client, hub, obs = app_and_client
    resp = client.get("/projects/proj-1/collaboration/conflicts")
    assert resp.status_code == 200
    assert resp.json()["data"]["conflicts"] == []


def test_get_claims_empty(app_and_client):
    client, hub, obs = app_and_client
    resp = client.get("/projects/proj-1/collaboration/claims")
    assert resp.status_code == 200
    assert resp.json()["data"]["claims"] == []


def test_create_and_get_claim(app_and_client):
    client, hub, obs = app_and_client
    resp = client.post(
        "/projects/proj-1/collaboration/claims",
        params={
            "agent_role": "researcher",
            "path": "src/auth.py",
            "reason": "Researching",
        },
    )
    assert resp.status_code == 200
    claim_id = resp.json()["data"]["id"]
    assert claim_id

    resp = client.get("/projects/proj-1/collaboration/claims")
    claims = resp.json()["data"]["claims"]
    assert len(claims) == 1
    assert claims[0]["path"] == "src/auth.py"


def test_release_claim(app_and_client):
    client, hub, obs = app_and_client
    claim_id = hub.claims.claim(
        "proj-1", "researcher", "src/auth.py", "Research",
    )

    resp = client.delete(
        f"/projects/proj-1/collaboration/claims/{claim_id}",
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["released"] is True

    claims = hub.claims.get_active("proj-1")
    assert len(claims) == 0

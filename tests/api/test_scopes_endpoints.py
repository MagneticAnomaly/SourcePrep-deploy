from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_includes_synthetic_global(client: TestClient, project):
    r = client.get(f"/projects/{project.id}/scopes")
    assert r.status_code == 200
    body = r.json()["data"]
    ids = [s["id"] for s in body["scopes"]]
    assert "global" in ids


def test_create_returns_record(client, project):
    r = client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "Marketing", "paths": ["websites/marketing/"]},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["id"] == "marketing"
    assert body["paths"] == ["websites/marketing/"]


def test_get_global_synthesizes_from_included_paths(client, project):
    project.config["included_paths"] = ["src/"]
    r = client.get(f"/projects/{project.id}/scopes/global")
    body = r.json()["data"]
    assert body["id"] == "global"
    assert body["paths"] == ["src/"]


def test_delete_global_is_rejected(client, project):
    r = client.delete(f"/projects/{project.id}/scopes/global")
    assert r.status_code == 400


def test_delete_named_scope(client, project):
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": []},
    )
    r = client.delete(f"/projects/{project.id}/scopes/m")
    assert r.status_code == 200
    r2 = client.get(f"/projects/{project.id}/scopes/m")
    assert r2.status_code == 404


def test_unknown_scope_get_returns_404(client, project):
    r = client.get(f"/projects/{project.id}/scopes/nope")
    assert r.status_code == 404


def test_update_partial_preserves_role(client, project):
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": [], "assigned_to_role": "writer"},
    )
    r = client.put(f"/projects/{project.id}/scopes/m", json={"display_name": "Marketing"})
    assert r.status_code == 200
    assert r.json()["data"]["assigned_to_role"] == "writer"


def test_update_can_clear_role_via_explicit_null(client, project):
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": [], "assigned_to_role": "writer"},
    )
    r = client.put(f"/projects/{project.id}/scopes/m", json={"assigned_to_role": None})
    assert r.status_code == 200
    assert r.json()["data"]["assigned_to_role"] is None

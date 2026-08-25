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


def test_add_paths_to_global_writes_included_paths(client, project):
    r = client.post(
        f"/projects/{project.id}/scopes/global/add",
        json={"paths": ["src/foo.py"]},
    )
    assert r.status_code == 200
    # The fake registry's mutate_config updates project.config in-place.
    assert "src/foo.py" in project.config["included_paths"]


def test_add_paths_to_named_scope_writes_record(client, project):
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": []},
    )
    r = client.post(
        f"/projects/{project.id}/scopes/m/add",
        json={"paths": ["websites/marketing/"]},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["paths"] == ["websites/marketing/"]


def test_add_to_named_scope_triggers_orchestrator_when_outside_global(
    client, project, mock_orchestrator
):
    project.config["included_paths"] = ["src/"]
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": []},
    )
    client.post(
        f"/projects/{project.id}/scopes/m/add",
        json={"paths": ["websites/marketing/"]},
    )
    assert mock_orchestrator.added == [(project.id, ["websites/marketing/"])]


def test_add_to_named_scope_skips_orchestrator_when_inside_global(
    client, project, mock_orchestrator
):
    project.config["included_paths"] = ["src/"]
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": []},
    )
    client.post(
        f"/projects/{project.id}/scopes/m/add",
        json={"paths": ["src/foo.py"]},
    )
    # src/foo.py is already in compute_index_membership via global → no new embed
    assert mock_orchestrator.added == []


def test_create_defaults_pipeline_profile_code(client, project):
    r = client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "Marketing", "paths": ["websites/marketing/"]},
    )
    assert r.status_code == 200
    assert r.json()["data"]["pipeline_profile"] == "code"
    # summary in list view also carries it
    listing = client.get(f"/projects/{project.id}/scopes").json()["data"]["scopes"]
    rec = next(s for s in listing if s["id"] == "marketing")
    assert rec["pipeline_profile"] == "code"


def test_create_with_pipeline_profile_round_trips(client, project):
    r = client.post(
        f"/projects/{project.id}/scopes",
        json={
            "display_name": "Docs",
            "paths": ["knowledge/linux/"],
            "pipeline_profile": "prose_docs",
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["pipeline_profile"] == "prose_docs"
    # GET returns it
    got = client.get(f"/projects/{project.id}/scopes/docs").json()["data"]
    assert got["pipeline_profile"] == "prose_docs"


def test_create_unknown_pipeline_profile_is_409(client, project):
    r = client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "Bad", "paths": [], "pipeline_profile": "nope"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SCOPE_INVALID"


def test_update_changes_pipeline_profile(client, project):
    client.post(
        f"/projects/{project.id}/scopes",
        json={"display_name": "M", "paths": [], "pipeline_profile": "code"},
    )
    r = client.put(
        f"/projects/{project.id}/scopes/m",
        json={"pipeline_profile": "system_config"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["pipeline_profile"] == "system_config"
    # update omits the field → unchanged
    r2 = client.put(f"/projects/{project.id}/scopes/m", json={"display_name": "M2"})
    assert r2.json()["data"]["pipeline_profile"] == "system_config"
    # update with unknown → 409
    r3 = client.put(
        f"/projects/{project.id}/scopes/m", json={"pipeline_profile": "bogus"}
    )
    assert r3.status_code == 409


def test_global_scope_synthesizes_code_profile(client, project):
    r = client.get(f"/projects/{project.id}/scopes/global")
    assert r.status_code == 200
    assert r.json()["data"]["pipeline_profile"] == "code"

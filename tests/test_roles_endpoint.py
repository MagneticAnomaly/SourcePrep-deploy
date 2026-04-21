"""
Tests for GET /roles — Phase 104 scrutiny.

The endpoint exposes the built-in RoleVectors so the dashboard can avoid
a hardcoded copy of role_vectors.py. These tests lock the contract:
shape, non-empty, sorted, matches RoleVector.to_dict().
"""
from __future__ import annotations

from prep.api.routers.roles_endpoints import list_builtin_roles


def _data(envelope):
    return envelope["data"] if "data" in envelope else envelope


def test_returns_nonempty_sorted_list():
    payload = _data(list_builtin_roles())
    assert payload["count"] > 0
    assert len(payload["roles"]) == payload["count"]
    names = [r["display_name"] for r in payload["roles"]]
    assert names == sorted(names)


def test_each_role_has_required_payload_fields():
    payload = _data(list_builtin_roles())
    for role in payload["roles"]:
        assert isinstance(role["role_id"], str) and role["role_id"]
        assert isinstance(role["display_name"], str) and role["display_name"]
        assert isinstance(role["layer_weights"], dict)
        assert isinstance(role["domain_affinity"], list)
        assert isinstance(role["centrality_weight"], float)
        assert isinstance(role["detail_level"], float)
        assert isinstance(role["max_chars"], int)
        assert 200 <= role["max_chars"] <= 20000


def test_includes_known_builtin_roles():
    payload = _data(list_builtin_roles())
    ids = {r["role_id"] for r in payload["roles"]}
    # Minimal set we know ships in BUILT_IN_ROLES.
    assert {"ceo", "engineering", "architect", "security"} <= ids

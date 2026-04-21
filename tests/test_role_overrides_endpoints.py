"""
Tests for role_overrides_endpoints — Phase 104 Step 2.

Exercises the FastAPI handlers directly (avoiding full TestClient boot)
and injects a fake store, a fake _srv, and a fake project resolver.

Covers: list/get/put/delete, pin/unpin, validation (char budget bounds).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from prep.api.routers.projects import role_overrides_endpoints as ep
from prep.services.role_overrides_store import RoleOverridesStore


class _FakeSettings:
    def __init__(self):
        self._data: dict[str, dict[str, object]] = {}

    def project_get(self, project_id, key, default=None):
        return self._data.get(project_id, {}).get(key, default)

    def project_set(self, project_id, key, value):
        self._data.setdefault(project_id, {})[key] = value

    def project_delete(self, project_id, key):
        bucket = self._data.get(project_id, {})
        if key in bucket:
            del bucket[key]
            return True
        return False

    def project_get_all(self, project_id):
        return dict(self._data.get(project_id, {}))


class _FakeProject:
    pass


class _FakeSrv:
    def _require_project(self, project_id):
        return _FakeProject()


@pytest.fixture(autouse=True)
def patch_module(monkeypatch):
    """Replace the singleton store and the _srv() lookup for each test."""
    fake_store = RoleOverridesStore(settings=_FakeSettings())
    monkeypatch.setattr(ep, "role_overrides_store", fake_store)
    monkeypatch.setattr(ep, "_srv", lambda: _FakeSrv())
    yield fake_store


def _data(envelope):
    """Unwrap the ok() envelope to the inner data dict."""
    return envelope["data"] if "data" in envelope else envelope


# ── Upsert validation ───────────────────────────────────────────────


def test_upsert_rejects_max_chars_below_minimum():
    with pytest.raises(ValidationError):
        ep.RoleOverrideUpsertRequest(max_chars=100)


def test_upsert_rejects_max_chars_above_maximum():
    with pytest.raises(ValidationError):
        ep.RoleOverrideUpsertRequest(max_chars=25000)


def test_upsert_accepts_none_max_chars():
    # Allowed because upsert can be used to update other fields later.
    req = ep.RoleOverrideUpsertRequest()
    assert req.max_chars is None


def test_upsert_accepts_boundary_values():
    # Boundaries (200 and 20000) must be inclusive.
    assert ep.RoleOverrideUpsertRequest(max_chars=200).max_chars == 200
    assert ep.RoleOverrideUpsertRequest(max_chars=20000).max_chars == 20000


# ── GET flows ───────────────────────────────────────────────────────


def test_get_returns_none_when_no_override():
    envelope = ep.get_role_override("proj-1", "engineering")
    assert _data(envelope)["override"] is None


def test_get_returns_override_when_set(patch_module):
    patch_module.upsert("proj-1", "engineering", max_chars=3500)
    envelope = ep.get_role_override("proj-1", "engineering")
    ov = _data(envelope)["override"]
    assert ov is not None
    assert ov["max_chars"] == 3500
    assert ov["role_id"] == "engineering"


def test_list_empty_project_returns_zero(patch_module):
    envelope = ep.list_role_overrides("proj-empty")
    data = _data(envelope)
    assert data["count"] == 0
    assert data["overrides"] == []


def test_list_returns_all_configured_roles(patch_module):
    patch_module.upsert("proj-1", "engineering", max_chars=3500)
    patch_module.upsert("proj-1", "ceo", max_chars=1500)
    envelope = ep.list_role_overrides("proj-1")
    data = _data(envelope)
    assert data["count"] == 2
    role_ids = {ov["role_id"] for ov in data["overrides"]}
    assert role_ids == {"engineering", "ceo"}


# ── PUT flows ───────────────────────────────────────────────────────


def test_put_upserts_max_chars():
    req = ep.RoleOverrideUpsertRequest(max_chars=3500)
    envelope = ep.upsert_role_override("proj-1", "engineering", req)
    ov = _data(envelope)["override"]
    assert ov["max_chars"] == 3500


def test_put_twice_overwrites():
    ep.upsert_role_override(
        "proj-1", "engineering", ep.RoleOverrideUpsertRequest(max_chars=3500)
    )
    envelope = ep.upsert_role_override(
        "proj-1", "engineering", ep.RoleOverrideUpsertRequest(max_chars=2000)
    )
    assert _data(envelope)["override"]["max_chars"] == 2000


# ── DELETE flows ────────────────────────────────────────────────────


def test_delete_returns_true_when_something_existed(patch_module):
    patch_module.upsert("proj-1", "engineering", max_chars=3500)
    envelope = ep.delete_role_override("proj-1", "engineering")
    assert _data(envelope)["deleted"] is True
    assert patch_module.get("proj-1", "engineering") is None


def test_delete_returns_false_for_missing():
    envelope = ep.delete_role_override("proj-1", "never-set")
    assert _data(envelope)["deleted"] is False


def test_delete_clears_pinned_concepts_too(patch_module):
    patch_module.upsert("proj-1", "engineering", max_chars=3500)
    patch_module.pin_concept("proj-1", "engineering", "c1")
    patch_module.pin_concept("proj-1", "engineering", "c2")
    ep.delete_role_override("proj-1", "engineering")
    assert patch_module.list_pinned_concepts("proj-1", "engineering") == []


# ── Pin / Unpin ─────────────────────────────────────────────────────


def test_pin_adds_concept(patch_module):
    req = ep.PinConceptRequest(concept_id="c1")
    envelope = ep.pin_concept_to_role("proj-1", "engineering", req)
    assert _data(envelope)["pinned_concept_ids"] == ["c1"]


def test_pin_rejects_empty_concept_id():
    with pytest.raises(ValidationError):
        ep.PinConceptRequest(concept_id="")


def test_pin_is_idempotent_on_same_id(patch_module):
    req = ep.PinConceptRequest(concept_id="c1")
    ep.pin_concept_to_role("proj-1", "engineering", req)
    envelope = ep.pin_concept_to_role("proj-1", "engineering", req)
    assert _data(envelope)["pinned_concept_ids"] == ["c1"]


def test_unpin_removes_concept(patch_module):
    patch_module.pin_concept("proj-1", "engineering", "c1")
    patch_module.pin_concept("proj-1", "engineering", "c2")
    envelope = ep.unpin_concept_from_role("proj-1", "engineering", "c1")
    assert _data(envelope)["pinned_concept_ids"] == ["c2"]


def test_unpin_missing_concept_is_noop(patch_module):
    patch_module.pin_concept("proj-1", "engineering", "c1")
    envelope = ep.unpin_concept_from_role(
        "proj-1", "engineering", "never-pinned"
    )
    assert _data(envelope)["pinned_concept_ids"] == ["c1"]


# ── Reverse query (Phase 104 Step 4) ────────────────────────────────


def test_pinned_roles_empty_when_concept_never_pinned():
    envelope = ep.list_roles_pinning_concept("proj-1", "c-never")
    data = _data(envelope)
    assert data["role_ids"] == []
    assert data["count"] == 0


def test_pinned_roles_returns_every_role_sorted(patch_module):
    patch_module.pin_concept("proj-1", "engineering", "c1")
    patch_module.pin_concept("proj-1", "security", "c1")
    patch_module.pin_concept("proj-1", "ceo", "c1")
    envelope = ep.list_roles_pinning_concept("proj-1", "c1")
    data = _data(envelope)
    assert data["role_ids"] == ["ceo", "engineering", "security"]
    assert data["count"] == 3

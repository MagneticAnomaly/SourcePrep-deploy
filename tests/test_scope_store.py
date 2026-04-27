from __future__ import annotations

import pytest

from prep.core.scope_store import GLOBAL_SCOPE_ID, ScopeStore


def test_create_get_round_trip(tmp_settings):
    store = ScopeStore()
    rec = store.create("proj-1", display_name="Marketing",
                      paths=["websites/marketing/"], assigned_to_role=None)
    assert rec.id == "marketing"
    assert rec.display_name == "Marketing"
    assert rec.paths == ["websites/marketing/"]
    fetched = store.get("proj-1", "marketing")
    assert fetched == rec


def test_slug_collision_auto_suffix(tmp_settings):
    store = ScopeStore()
    a = store.create("proj-1", display_name="Marketing", paths=[])
    b = store.create("proj-1", display_name="Marketing", paths=[])
    assert a.id == "marketing"
    assert b.id == "marketing_2"


def test_global_id_is_reserved(tmp_settings):
    store = ScopeStore()
    with pytest.raises(ValueError, match="reserved"):
        store.create("proj-1", display_name="global", paths=[])


def test_list_excludes_global(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="Marketing", paths=[])
    store.create("proj-1", display_name="Data Cleaning", paths=[])
    ids = [r.id for r in store.list("proj-1")]
    assert ids == ["data_cleaning", "marketing"]
    assert GLOBAL_SCOPE_ID not in ids


def test_assigned_to_role_uniqueness(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="A", paths=[], assigned_to_role="cto")
    with pytest.raises(ValueError, match="already assigned"):
        store.create("proj-1", display_name="B", paths=[], assigned_to_role="cto")


def test_delete(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="Marketing", paths=["x/"])
    assert store.delete("proj-1", "marketing") is True
    assert store.get("proj-1", "marketing") is None
    assert store.delete("proj-1", "marketing") is False


def test_update_can_clear_assigned_to_role(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="A", paths=[], assigned_to_role="cto")
    rec = store.update("proj-1", "a", assigned_to_role=None)
    assert rec.assigned_to_role is None
    # And another scope can now claim that role.
    rec2 = store.create("proj-1", display_name="B", paths=[], assigned_to_role="cto")
    assert rec2.assigned_to_role == "cto"


def test_update_omitting_role_leaves_it_unchanged(tmp_settings):
    store = ScopeStore()
    store.create("proj-1", display_name="A", paths=[], assigned_to_role="cto")
    # Update display_name only; role assignment stays.
    rec = store.update("proj-1", "a", display_name="A2")
    assert rec.display_name == "A2"
    assert rec.assigned_to_role == "cto"

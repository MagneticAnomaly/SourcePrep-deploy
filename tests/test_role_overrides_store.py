"""
Tests for RoleOverridesStore — Phase 104 Step 2.

Covers: get/list/upsert/delete for overrides, pin/unpin/list for concept pins,
edge cases (missing project data, clearing fields), ordering guarantees.

Uses a fake settings_store backed by an in-memory dict so we don't need
a real sqlite file and avoid the WAL-on-USB quirk during tests.
"""
from __future__ import annotations

from typing import Any

import pytest

from codrag.services.role_overrides_store import RoleOverride, RoleOverridesStore

# ── Fake settings store ─────────────────────────────────────────────


class _FakeSettings:
    """In-memory fake of the settings_store project API used by the store."""

    def __init__(self):
        # { project_id: { key: value } }
        self._data: dict[str, dict[str, Any]] = {}

    def project_get(self, project_id: str, key: str, default: Any = None) -> Any:
        return self._data.get(project_id, {}).get(key, default)

    def project_set(self, project_id: str, key: str, value: Any) -> None:
        self._data.setdefault(project_id, {})[key] = value

    def project_delete(self, project_id: str, key: str) -> bool:
        bucket = self._data.get(project_id, {})
        if key in bucket:
            del bucket[key]
            return True
        return False

    def project_get_all(self, project_id: str) -> dict[str, Any]:
        return dict(self._data.get(project_id, {}))


@pytest.fixture
def store() -> RoleOverridesStore:
    return RoleOverridesStore(settings=_FakeSettings())


# ── RoleOverride dataclass ──────────────────────────────────────────


def test_role_override_is_empty_when_no_fields_set():
    ov = RoleOverride(role_id="engineering")
    assert ov.is_empty() is True


def test_role_override_not_empty_with_max_chars():
    ov = RoleOverride(role_id="engineering", max_chars=3000)
    assert ov.is_empty() is False


def test_role_override_not_empty_with_pins():
    ov = RoleOverride(role_id="engineering", pinned_concept_ids=["c1"])
    assert ov.is_empty() is False


def test_role_override_from_dict_round_trip():
    d = {"max_chars": 3500, "pinned_concept_ids": ["a", "b"], "updated_at": 42.0}
    ov = RoleOverride.from_dict("ceo", d)
    assert ov.role_id == "ceo"
    assert ov.max_chars == 3500
    assert ov.pinned_concept_ids == ["a", "b"]
    assert ov.updated_at == 42.0


# ── Overrides CRUD ──────────────────────────────────────────────────


def test_get_returns_none_for_missing_override(store: RoleOverridesStore):
    assert store.get("proj-1", "engineering") is None


def test_upsert_persists_max_chars(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    ov = store.get("proj-1", "engineering")
    assert ov is not None
    assert ov.max_chars == 3500
    assert ov.role_id == "engineering"
    assert ov.updated_at > 0


def test_upsert_without_max_chars_preserves_existing(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    # Second call without max_chars must NOT clear it.
    store.upsert("proj-1", "engineering")
    ov = store.get("proj-1", "engineering")
    assert ov is not None
    assert ov.max_chars == 3500


def test_upsert_overwrites_max_chars_when_provided(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    store.upsert("proj-1", "engineering", max_chars=2000)
    ov = store.get("proj-1", "engineering")
    assert ov is not None
    assert ov.max_chars == 2000


def test_delete_removes_override_and_pins(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    store.pin_concept("proj-1", "engineering", "c1")
    assert store.delete("proj-1", "engineering") is True
    assert store.get("proj-1", "engineering") is None
    assert store.list_pinned_concepts("proj-1", "engineering") == []


def test_delete_returns_false_when_nothing_exists(store: RoleOverridesStore):
    assert store.delete("proj-1", "engineering") is False


# ── Per-project listing ─────────────────────────────────────────────


def test_list_returns_all_roles_with_overrides_or_pins(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    store.upsert("proj-1", "ceo", max_chars=1500)
    # Role with only pins (no max_chars override) should still appear.
    store.pin_concept("proj-1", "security", "c-auth")
    overrides = store.list("proj-1")
    roles = {ov.role_id for ov in overrides}
    assert roles == {"engineering", "ceo", "security"}

    by_role = {ov.role_id: ov for ov in overrides}
    assert by_role["engineering"].max_chars == 3500
    assert by_role["ceo"].max_chars == 1500
    assert by_role["security"].max_chars is None
    assert by_role["security"].pinned_concept_ids == ["c-auth"]


def test_list_scoped_to_project(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    store.upsert("proj-2", "engineering", max_chars=2000)
    assert {ov.role_id for ov in store.list("proj-1")} == {"engineering"}
    assert store.list("proj-1")[0].max_chars == 3500


def test_get_merges_pins_into_override(store: RoleOverridesStore):
    store.upsert("proj-1", "engineering", max_chars=3500)
    store.pin_concept("proj-1", "engineering", "c1")
    store.pin_concept("proj-1", "engineering", "c2")
    ov = store.get("proj-1", "engineering")
    assert ov is not None
    assert ov.max_chars == 3500
    assert set(ov.pinned_concept_ids) == {"c1", "c2"}


# ── Concept pinning ─────────────────────────────────────────────────


def test_pin_concept_first_time(store: RoleOverridesStore):
    pinned = store.pin_concept("proj-1", "engineering", "c1")
    assert pinned == ["c1"]
    assert store.list_pinned_concepts("proj-1", "engineering") == ["c1"]


def test_pin_concept_is_idempotent_but_updates_timestamp(
    store: RoleOverridesStore,
    monkeypatch,
):
    import codrag.services.role_overrides_store as mod

    monkeypatch.setattr(mod.time, "time", lambda: 100.0)
    store.pin_concept("proj-1", "engineering", "c1")

    monkeypatch.setattr(mod.time, "time", lambda: 200.0)
    pinned = store.pin_concept("proj-1", "engineering", "c1")

    # List stays a single-element idempotent list.
    assert pinned == ["c1"]
    # But the underlying timestamp should have bumped from 100 → 200.
    raw = store._store().project_get("proj-1", "role_pins/engineering")
    assert raw["c1"] == 200.0


def test_pin_preserves_insertion_order(store: RoleOverridesStore):
    store.pin_concept("proj-1", "engineering", "first")
    store.pin_concept("proj-1", "engineering", "second")
    store.pin_concept("proj-1", "engineering", "third")
    assert store.list_pinned_concepts("proj-1", "engineering") == [
        "first",
        "second",
        "third",
    ]


def test_unpin_removes_concept(store: RoleOverridesStore):
    store.pin_concept("proj-1", "engineering", "c1")
    store.pin_concept("proj-1", "engineering", "c2")
    remaining = store.unpin_concept("proj-1", "engineering", "c1")
    assert remaining == ["c2"]


def test_unpin_last_concept_cleans_up_key(store: RoleOverridesStore):
    store.pin_concept("proj-1", "engineering", "c1")
    store.unpin_concept("proj-1", "engineering", "c1")
    assert store.list_pinned_concepts("proj-1", "engineering") == []


def test_unpin_missing_concept_is_noop(store: RoleOverridesStore):
    store.pin_concept("proj-1", "engineering", "c1")
    remaining = store.unpin_concept("proj-1", "engineering", "does-not-exist")
    assert remaining == ["c1"]


def test_list_pinned_empty_when_nothing_pinned(store: RoleOverridesStore):
    assert store.list_pinned_concepts("proj-1", "engineering") == []


def test_list_pinned_handles_corrupt_data_gracefully(store: RoleOverridesStore):
    # Simulate old/bad data shape — a list instead of a dict.
    store._store().project_set("proj-1", "role_pins/engineering", ["c1", "c2"])
    assert store.list_pinned_concepts("proj-1", "engineering") == []


def test_get_ignores_non_dict_override_value(store: RoleOverridesStore):
    # Simulate corrupt data shape.
    store._store().project_set(
        "proj-1", "role_overrides/engineering", "garbage"
    )
    assert store.get("proj-1", "engineering") is None

"""
Phase 104 Step 4: deleting a concept cleans up any role pins referencing it.

Uses real ConceptStore (in-memory sqlite) and real RoleOverridesStore
backed by a fake in-memory settings store so we exercise the actual
lazy-import path from concept_store.delete → role_overrides_store.
"""
from __future__ import annotations

from typing import Any

import pytest

from prep.services import role_overrides_store as ros_module
from prep.services.concept_store import ConceptStore
from prep.services.role_overrides_store import RoleOverridesStore


class _FakeSettings:
    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}

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


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Concept store with a real sqlite; overrides store sharing a fake
    settings backend. Patch the module-level singleton so concept_store's
    lazy import finds the test instance."""
    concepts = ConceptStore()
    concepts.init(tmp_path / "concepts.db")

    fake_settings = _FakeSettings()
    overrides = RoleOverridesStore(settings=fake_settings)
    monkeypatch.setattr(ros_module, "role_overrides_store", overrides)

    yield concepts, overrides
    concepts.close()


def test_deleting_concept_removes_pins_from_all_roles(wired):
    concepts, overrides = wired
    # Seed a concept and pin it to two roles.
    cid = concepts.save(
        project_id="proj-1",
        title="JWT Auth",
        content="Uses RS256.",
        category="security",
    )
    overrides.pin_concept("proj-1", "engineering", cid)
    overrides.pin_concept("proj-1", "security", cid)

    assert sorted(overrides.list_roles_pinning_concept("proj-1", cid)) == [
        "engineering",
        "security",
    ]

    # Deleting the concept should cascade into the override store.
    assert concepts.delete(cid) is True
    assert overrides.list_roles_pinning_concept("proj-1", cid) == []
    assert overrides.list_pinned_concepts("proj-1", "engineering") == []
    assert overrides.list_pinned_concepts("proj-1", "security") == []


def test_deleting_missing_concept_is_safe(wired):
    concepts, overrides = wired
    assert concepts.delete("nonexistent-id") is False
    # Nothing to clean up — no crash.


def test_pin_cleanup_preserves_other_pins_on_same_role(wired):
    concepts, overrides = wired
    cid1 = concepts.save(project_id="proj-1", title="A", content=".")
    cid2 = concepts.save(project_id="proj-1", title="B", content=".")
    overrides.pin_concept("proj-1", "engineering", cid1)
    overrides.pin_concept("proj-1", "engineering", cid2)

    concepts.delete(cid1)
    # cid2 still pinned.
    assert overrides.list_pinned_concepts("proj-1", "engineering") == [cid2]


def test_pin_cleanup_scoped_to_project(wired):
    concepts, overrides = wired
    cid = concepts.save(project_id="proj-1", title="Shared", content=".")
    overrides.pin_concept("proj-1", "engineering", cid)
    overrides.pin_concept("proj-2", "engineering", cid)  # unrelated project

    concepts.delete(cid)
    # Only proj-1's pin should be cleaned (cid belonged to proj-1).
    assert overrides.list_roles_pinning_concept("proj-1", cid) == []
    assert overrides.list_roles_pinning_concept("proj-2", cid) == ["engineering"]

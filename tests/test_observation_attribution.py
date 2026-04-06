"""Tests for observation attribution (created_by + visibility)."""
import pytest

from codrag.services.observation_store import ObservationStore


@pytest.fixture
def store(tmp_path):
    s = ObservationStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_save_with_created_by(store):
    obs_id = store.save("proj-1", "Auth uses JWT", created_by="researcher")
    obs = store.get_for_query("proj-1", "JWT")
    assert len(obs) >= 1
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].created_by == "researcher"


def test_save_without_created_by_defaults_to_none(store):
    obs_id = store.save("proj-1", "Legacy observation")
    obs = store.get_for_query("proj-1", "Legacy")
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].created_by is None


def test_save_with_visibility(store):
    obs_id = store.save(
        "proj-1", "Private note",
        created_by="researcher", visibility="private",
    )
    obs = store.get_for_query("proj-1", "Private")
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].visibility == "private"


def test_visibility_defaults_to_shared(store):
    obs_id = store.save("proj-1", "Default visibility")
    obs = store.get_for_query("proj-1", "Default visibility")
    match = [o for o in obs if o.id == obs_id]
    assert len(match) == 1
    assert match[0].visibility == "shared"

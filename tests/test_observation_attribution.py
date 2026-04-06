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


# ── get_by_agent tests ──────────────────────────────────────────


def test_get_by_agent_filters_by_created_by(store):
    store.save("proj-1", "Researcher note 1", created_by="researcher")
    store.save("proj-1", "Custodian note 1", created_by="custodian")
    store.save("proj-1", "Researcher note 2", created_by="researcher")

    results = store.get_by_agent("proj-1", "researcher")
    assert len(results) == 2
    assert all(o.created_by == "researcher" for o in results)


def test_get_by_agent_excludes_stale_by_default(store):
    store.save("proj-1", "Will go stale", created_by="researcher",
               file_path="src/a.py")
    store.mark_stale_batch("proj-1", ["src/a.py"], reason="test")
    store.save("proj-1", "Fresh note", created_by="researcher")

    results = store.get_by_agent("proj-1", "researcher", include_stale=False)
    assert all(not o.stale for o in results)


def test_get_by_agent_visibility_filter(store):
    store.save("proj-1", "Shared note", created_by="researcher",
               visibility="shared")
    store.save("proj-1", "Private note", created_by="researcher",
               visibility="private")

    shared = store.get_by_agent("proj-1", "researcher",
                                visibility_filter="shared")
    assert len(shared) == 1
    assert shared[0].content == "Shared note"


def test_get_by_agent_respects_limit(store):
    for i in range(10):
        store.save("proj-1", f"Note {i}", created_by="researcher")

    results = store.get_by_agent("proj-1", "researcher", limit=3)
    assert len(results) == 3


def test_get_by_agent_empty_for_unknown_agent(store):
    store.save("proj-1", "Some note", created_by="researcher")
    results = store.get_by_agent("proj-1", "unknown_agent")
    assert len(results) == 0

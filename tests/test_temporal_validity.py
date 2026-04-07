"""Tests for temporal validity (valid_from / valid_to) on concept and observation stores."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from codrag.services.concept_store import ConceptStore
from codrag.services.observation_store import ObservationStore


# ── Observation Store Fixtures ───────────────────────────────────


@pytest.fixture
def obs_store(tmp_path: Path) -> ObservationStore:
    s = ObservationStore()
    s.init(tmp_path / "test_obs.db")
    yield s
    s.close()


# ── Observation Store Tests ──────────────────────────────────────


def test_observation_has_valid_from_set(obs_store: ObservationStore) -> None:
    before = time.time()
    obs_id = obs_store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
    after = time.time()

    results = obs_store.get_for_file("proj-1", "src/auth.py")
    assert len(results) == 1
    assert results[0].valid_from is not None
    assert before <= results[0].valid_from <= after
    assert results[0].valid_to is None


def test_observation_mark_stale_sets_valid_to(obs_store: ObservationStore) -> None:
    obs_store.save("proj-1", "Note about auth", file_path="src/auth.py")

    obs_store.mark_stale_batch("proj-1", ["src/auth.py"], "file changed")

    results = obs_store.get_for_file("proj-1", "src/auth.py")
    assert len(results) == 1
    assert results[0].stale is True
    assert results[0].valid_to is not None


def test_observation_to_dict_includes_temporal_fields(obs_store: ObservationStore) -> None:
    """to_dict() must include valid_from and valid_to when set."""
    obs_store.save("proj-1", "Auth note", file_path="src/auth.py")
    obs_store.mark_stale_batch("proj-1", ["src/auth.py"], "changed")

    results = obs_store.get_for_file("proj-1", "src/auth.py")
    d = results[0].to_dict()
    assert "valid_from" in d
    assert "valid_to" in d
    assert isinstance(d["valid_from"], float)
    assert isinstance(d["valid_to"], float)


def test_observation_get_recent_as_of(obs_store: ObservationStore) -> None:
    """get_recent(as_of=...) returns observations valid at that time."""
    obs_store.save("proj-1", "Early note", file_path="src/early.py")
    time.sleep(0.05)
    t_mid = time.time()
    time.sleep(0.05)

    obs_store.mark_stale_batch("proj-1", ["src/early.py"], "changed")
    obs_store.save("proj-1", "Late note", file_path="src/late.py")

    # At t_mid: "Early note" was valid, "Late note" didn't exist yet
    results = obs_store.get_recent("proj-1", as_of=t_mid)
    contents = {r.content for r in results}
    assert "Early note" in contents
    assert "Late note" not in contents


def test_concept_dedup_update_resets_temporal(store: ConceptStore) -> None:
    """Re-saving a concept with the same title resets valid_from and clears valid_to."""
    cid = store.save("proj-1", "Auth Design", "Original", anchors=["src/auth.py"])
    original = store.get(cid)
    time.sleep(0.05)

    # Mark stale then re-save with same title
    store.mark_stale_batch("proj-1", ["src/auth.py"], "changed")
    stale_concept = store.get(cid)
    assert stale_concept.valid_to is not None

    store.save("proj-1", "Auth Design", "Updated content")
    updated = store.get(cid)
    assert updated.valid_to is None  # Cleared
    assert updated.valid_from > original.valid_from  # Reset to new time


# ── Concept Store Fixtures ───────────────────────────────────────


@pytest.fixture
def store(tmp_path: Path) -> ConceptStore:
    s = ConceptStore()
    s.init(tmp_path / "test_concepts.db")
    yield s
    s.close()


# ── Concept Store Tests ──────────────────────────────────────────


def test_new_concept_has_valid_from_set(store: ConceptStore) -> None:
    before = time.time()
    cid = store.save("proj-1", "Auth Design", "JWT-based auth")
    after = time.time()

    concept = store.get(cid)
    assert concept is not None
    assert concept.valid_from is not None
    assert before <= concept.valid_from <= after
    assert concept.valid_to is None


def test_mark_stale_sets_valid_to(store: ConceptStore) -> None:
    cid = store.save("proj-1", "Auth Design", "JWT-based auth", anchors=["src/auth.py"])

    store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified")

    concept = store.get(cid)
    assert concept is not None
    assert concept.stale is True
    assert concept.valid_to is not None
    assert concept.valid_to >= concept.valid_from


def test_list_concepts_as_of_past(store: ConceptStore) -> None:
    t1 = time.time()
    cid = store.save("proj-1", "Old Design", "Monolith", anchors=["src/app.py"])
    time.sleep(0.05)
    t2 = time.time()

    store.mark_stale_batch("proj-1", ["src/app.py"], "refactored")
    time.sleep(0.05)

    store.save("proj-1", "New Design", "Microservices", anchors=["src/app.py"])
    time.sleep(0.05)
    t3 = time.time()

    # Query at t2: should see "Old Design" (still valid), not "New Design" (not yet created)
    results = store.list_concepts("proj-1", as_of=t2)
    titles = {c.title for c in results}
    assert "Old Design" in titles
    assert "New Design" not in titles

    # Query at t3: "New Design" exists and is valid; "Old Design" has valid_to set before t3
    results = store.list_concepts("proj-1", as_of=t3)
    titles = {c.title for c in results}
    assert "New Design" in titles
    assert "Old Design" not in titles


def test_list_concepts_default_shows_only_current(store: ConceptStore) -> None:
    store.save("proj-1", "Current", "Still valid")
    cid_old = store.save("proj-1", "Expired", "Was valid", anchors=["src/old.py"])
    store.mark_stale_batch("proj-1", ["src/old.py"], "deleted")

    results = store.list_concepts("proj-1", include_stale=False)
    titles = {c.title for c in results}
    assert "Current" in titles
    assert "Expired" not in titles

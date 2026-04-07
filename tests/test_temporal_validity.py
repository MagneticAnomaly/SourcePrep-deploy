"""Tests for temporal validity (valid_from / valid_to) on concept and observation stores."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

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

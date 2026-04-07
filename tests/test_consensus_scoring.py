"""Tests for consensus scoring on ObservationStore."""
import tempfile
from pathlib import Path

import pytest

from codrag.services.observation_store import ObservationStore


@pytest.fixture
def store(tmp_path):
    s = ObservationStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_no_observations_returns_empty(store):
    results = store.get_consensus_scores("proj-1")
    assert results == []


def test_single_agent_per_file_returns_empty(store):
    store.save("proj-1", "Auth uses JWT", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "Config loads env", file_path="src/config.py", created_by="researcher")
    results = store.get_consensus_scores("proj-1", min_agents=2)
    assert results == []


def test_two_agents_same_file_returns_consensus(store):
    store.save("proj-1", "Auth JWT pattern", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "Auth dead code", file_path="src/auth.py", created_by="custodian")
    results = store.get_consensus_scores("proj-1", min_agents=2)
    assert len(results) == 1
    assert results[0]["file_path"] == "src/auth.py"
    assert results[0]["agent_count"] == 2
    assert set(results[0]["agents"]) == {"researcher", "custodian"}
    assert results[0]["consensus_score"] == pytest.approx(1.0)


def test_stale_observations_excluded(store):
    store.save("proj-1", "Auth JWT", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "Auth dead", file_path="src/auth.py", created_by="custodian")
    store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified")
    results = store.get_consensus_scores("proj-1", min_agents=2)
    assert results == []


def test_since_days_filter(store):
    store.save("proj-1", "Old obs", file_path="src/auth.py", created_by="researcher")
    store.save("proj-1", "New obs", file_path="src/auth.py", created_by="custodian")
    results = store.get_consensus_scores("proj-1", min_agents=2, since_days=30)
    assert len(results) == 1

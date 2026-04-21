"""Tests for ActivityStore — append-only agent action log."""
import time

import pytest

from prep.services.collaboration.activity import ActivityStore


@pytest.fixture
def store(tmp_path):
    s = ActivityStore(tmp_path / "test.db")
    yield s
    s.close()


def test_log_returns_id(store):
    entry_id = store.log("proj-1", "pi/watchdog", "delta_scan", "3 new")
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0


def test_get_recent_returns_logged_entries(store):
    store.log("proj-1", "pi/watchdog", "delta_scan", "3 new findings")
    store.log("proj-1", "researcher", "topic_selection", "Selected auth")

    entries = store.get_recent("proj-1")
    assert len(entries) == 2


def test_get_recent_ordered_by_time_desc(store):
    store.log("proj-1", "pi/watchdog", "scan_1", "First")
    time.sleep(0.01)
    store.log("proj-1", "researcher", "scan_2", "Second")

    entries = store.get_recent("proj-1")
    assert entries[0].summary == "Second"
    assert entries[1].summary == "First"


def test_get_recent_respects_limit(store):
    for i in range(10):
        store.log("proj-1", "pi/watchdog", f"scan_{i}", f"Entry {i}")

    entries = store.get_recent("proj-1", limit=3)
    assert len(entries) == 3


def test_get_recent_since_filters_by_time(store):
    store.log("proj-1", "pi/watchdog", "old_scan", "Old entry")
    cutoff = time.time()
    time.sleep(0.01)
    store.log("proj-1", "pi/watchdog", "new_scan", "New entry")

    entries = store.get_recent("proj-1", since=cutoff)
    assert len(entries) == 1
    assert entries[0].summary == "New entry"


def test_get_recent_isolates_projects(store):
    store.log("proj-1", "pi/watchdog", "scan", "Project 1")
    store.log("proj-2", "pi/watchdog", "scan", "Project 2")

    entries = store.get_recent("proj-1")
    assert len(entries) == 1
    assert entries[0].summary == "Project 1"


def test_log_with_details(store):
    store.log(
        "proj-1", "pi/watchdog", "delta_scan", "Summary",
        details={"new": 3, "resolved": 1},
    )
    entries = store.get_recent("proj-1")
    assert entries[0].details == {"new": 3, "resolved": 1}


def test_prune_removes_old_entries(store):
    store.log("proj-1", "pi/watchdog", "scan", "Old entry")
    time.sleep(0.01)

    pruned = store.prune("proj-1", max_age_days=0)
    assert pruned >= 1

    entries = store.get_recent("proj-1")
    assert len(entries) == 0

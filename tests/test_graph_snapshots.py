"""Tests for GraphSnapshotStore — persist + diff graph state."""
import time

import pytest

from codrag.services.collaboration.snapshots import GraphSnapshotStore


HUBS_V1 = [
    {"path": "src/config.py", "dependents_count": 20, "rank": 1},
    {"path": "src/utils.py", "dependents_count": 15, "rank": 2},
    {"path": "src/auth.py", "dependents_count": 10, "rank": 3},
]

MODULES_V1 = [
    {"name": "core", "file_count": 12, "domain_tags": ["backend", "api"]},
    {"name": "auth", "file_count": 5, "domain_tags": ["security"]},
]

HUBS_V2 = [
    {"path": "src/config.py", "dependents_count": 22, "rank": 1},
    {"path": "src/gateway.py", "dependents_count": 18, "rank": 2},
    {"path": "src/utils.py", "dependents_count": 15, "rank": 3},
]

MODULES_V2 = [
    {"name": "core", "file_count": 12, "domain_tags": ["backend", "api"]},
    {"name": "auth", "file_count": 3, "domain_tags": ["security"]},
    {"name": "gateway", "file_count": 4, "domain_tags": ["api"]},
]


@pytest.fixture
def store(tmp_path):
    s = GraphSnapshotStore(tmp_path / "test.db")
    yield s
    s.close()


def test_capture_returns_id(store):
    snap_id = store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    assert isinstance(snap_id, str)


def test_get_latest_returns_most_recent(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    latest = store.get_latest("proj-1")
    assert latest is not None
    assert len(latest.hubs) == len(HUBS_V2)


def test_get_latest_returns_none_when_empty(store):
    assert store.get_latest("proj-1") is None


def test_compute_delta_detects_new_hub(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    delta = store.compute_delta("proj-1", since=before)
    new_hubs = [h for h in delta.hub_changes if h["change"] == "new"]
    assert any(h["path"] == "src/gateway.py" for h in new_hubs)


def test_compute_delta_detects_removed_hub(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    delta = store.compute_delta("proj-1", since=before)
    removed = [h for h in delta.hub_changes if h["change"] == "removed"]
    assert any(h["path"] == "src/auth.py" for h in removed)


def test_compute_delta_detects_new_module(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V2, modules=MODULES_V2)

    delta = store.compute_delta("proj-1", since=before)
    new_mods = [m for m in delta.module_changes if m["change"] == "new"]
    assert any(m["name"] == "gateway" for m in new_mods)


def test_compute_delta_empty_when_no_changes(store):
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
    before = time.time()
    time.sleep(0.01)
    store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)

    delta = store.compute_delta("proj-1", since=before)
    assert delta.is_empty


def test_compute_delta_no_snapshots(store):
    delta = store.compute_delta("proj-1", since=0.0)
    assert delta.is_empty


def test_prune_keeps_recent(store):
    for i in range(15):
        store.capture("proj-1", hubs=HUBS_V1, modules=MODULES_V1)
        time.sleep(0.01)

    pruned = store.prune("proj-1", keep=5)
    assert pruned == 10

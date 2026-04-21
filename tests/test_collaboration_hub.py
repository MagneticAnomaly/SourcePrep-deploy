"""Integration tests for CollaborationHub — cross-store workflows."""
import time

import pytest

from prep.services.collaboration import CollaborationHub


@pytest.fixture
def hub(tmp_path):
    return CollaborationHub(tmp_path / "test.db")


def test_hub_initializes_all_stores(hub):
    assert hub.activity is not None
    assert hub.claims is not None
    assert hub.conflicts is not None
    assert hub.snapshots is not None


def test_claim_then_check_workflow(hub):
    """Researcher claims a file, custodian checks and skips."""
    hub.claims.claim("proj-1", "researcher", "src/auth.py",
                     "Researching auth")

    assert hub.claims.is_claimed(
        "proj-1", "src/auth.py", exclude_agent="custodian",
    )

    hub.activity.log("proj-1", "custodian", "claim_check",
                     "Skipped src/auth.py — claimed by researcher")

    entries = hub.activity.get_recent("proj-1")
    assert len(entries) == 1
    assert "claimed by researcher" in entries[0].summary


def test_snapshot_then_delta_workflow(hub):
    """Capture two snapshots, compute delta."""
    hubs_v1 = [
        {"path": "src/a.py", "dependents_count": 10, "rank": 1},
    ]
    mods_v1 = [
        {"name": "core", "file_count": 5, "domain_tags": []},
    ]

    hub.snapshots.capture("proj-1", hubs=hubs_v1, modules=mods_v1)
    before = time.time()
    time.sleep(0.01)

    hubs_v2 = [
        {"path": "src/a.py", "dependents_count": 10, "rank": 1},
        {"path": "src/b.py", "dependents_count": 8, "rank": 2},
    ]
    hub.snapshots.capture("proj-1", hubs=hubs_v2, modules=mods_v1)

    delta = hub.snapshots.compute_delta("proj-1", since=before)
    assert not delta.is_empty
    new_hubs = [h for h in delta.hub_changes if h["change"] == "new"]
    assert any(h["path"] == "src/b.py" for h in new_hubs)


def test_conflict_save_and_retrieve(hub):
    """Save a conflict, retrieve active ones."""
    from prep.services.collaboration.conflicts import AgentConflict

    conflict = AgentConflict(
        id="c1", project_id="proj-1", file_path="src/auth.py",
        agent_a="researcher", agent_a_assessment="Keep it",
        agent_b="custodian", agent_b_assessment="Delete it",
        detected_at=time.time(),
    )
    hub.conflicts.save(conflict)

    active = hub.conflicts.get_active("proj-1")
    assert len(active) == 1
    assert active[0].agent_a == "researcher"

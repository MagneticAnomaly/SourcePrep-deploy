"""Tests for ConflictStore + ConflictDetector."""
import time

import pytest

from prep.services.collaboration.conflicts import (
    AgentConflict, ConflictDetector, ConflictStore,
)
from prep.services.observation_store import Observation


@pytest.fixture
def store(tmp_path):
    s = ConflictStore(tmp_path / "test.db")
    yield s
    s.close()


def test_save_and_get_active(store):
    conflict = AgentConflict(
        id="c1", project_id="proj-1", file_path="src/auth.py",
        agent_a="researcher", agent_a_assessment="Important pattern",
        agent_b="custodian", agent_b_assessment="Dead code",
        conflict_type="contradictory", detected_at=time.time(),
    )
    store.save(conflict)

    active = store.get_active("proj-1")
    assert len(active) == 1
    assert active[0].file_path == "src/auth.py"
    assert active[0].resolution == "deferred"


def test_resolve_conflict(store):
    conflict = AgentConflict(
        id="c1", project_id="proj-1", file_path="src/auth.py",
        agent_a="researcher", agent_a_assessment="Important",
        agent_b="custodian", agent_b_assessment="Dead code",
        detected_at=time.time(),
    )
    store.save(conflict)

    assert store.resolve("c1", "agent_a_wins") is True
    assert len(store.get_active("proj-1")) == 0


def test_get_active_excludes_resolved(store):
    for i, res in enumerate(["deferred", "agent_a_wins", "deferred"]):
        c = AgentConflict(
            id=f"c{i}", project_id="proj-1",
            file_path=f"src/file{i}.py",
            agent_a="researcher", agent_a_assessment="A",
            agent_b="custodian", agent_b_assessment="B",
            resolution=res, detected_at=time.time(),
        )
        store.save(c)

    active = store.get_active("proj-1")
    assert len(active) == 2


# ── ConflictDetector tests ──────────────────────────────────


def test_detect_same_file_different_agents():
    obs_list = [
        Observation(
            id="o1", project_id="proj-1",
            content="Important pattern",
            file_path="src/auth.py", created_by="researcher",
            created_at=1.0,
        ),
        Observation(
            id="o2", project_id="proj-1",
            content="Dead code candidate",
            file_path="src/auth.py", created_by="custodian",
            created_at=2.0,
        ),
        Observation(
            id="o3", project_id="proj-1",
            content="Unrelated",
            file_path="src/other.py", created_by="researcher",
            created_at=3.0,
        ),
    ]

    detector = ConflictDetector()
    conflicts = detector.detect_from_observations("proj-1", obs_list)

    assert len(conflicts) == 1
    assert conflicts[0].file_path == "src/auth.py"
    assert {conflicts[0].agent_a, conflicts[0].agent_b} == {
        "researcher", "custodian",
    }


def test_detect_no_conflict_same_agent():
    obs_list = [
        Observation(
            id="o1", project_id="proj-1", content="Note 1",
            file_path="src/auth.py", created_by="researcher",
            created_at=1.0,
        ),
        Observation(
            id="o2", project_id="proj-1", content="Note 2",
            file_path="src/auth.py", created_by="researcher",
            created_at=2.0,
        ),
    ]

    detector = ConflictDetector()
    conflicts = detector.detect_from_observations("proj-1", obs_list)
    assert len(conflicts) == 0


def test_detect_no_conflict_no_file_path():
    obs_list = [
        Observation(
            id="o1", project_id="proj-1", content="Note 1",
            created_by="researcher", created_at=1.0,
        ),
        Observation(
            id="o2", project_id="proj-1", content="Note 2",
            created_by="custodian", created_at=2.0,
        ),
    ]

    detector = ConflictDetector()
    conflicts = detector.detect_from_observations("proj-1", obs_list)
    assert len(conflicts) == 0

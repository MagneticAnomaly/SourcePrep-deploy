import pytest
from codrag.core.concept_conflicts import detect_conflicts, ConceptConflict


def _make_concept(id, title, anchors, category="architecture", status="active", created_at=1000.0):
    return {"id": id, "title": title, "anchors": anchors, "category": category, "status": status, "created_at": created_at}


def test_no_conflicts_when_no_overlap():
    concepts = [
        _make_concept("c1", "Auth uses JWT", ["src/auth.py"]),
        _make_concept("c2", "DB uses SQLite", ["src/db.py"]),
    ]
    assert detect_conflicts(concepts) == []


def test_detects_conflict_on_shared_anchors():
    concepts = [
        _make_concept("c1", "Server uses dispatch", ["src/server.py"], created_at=1000),
        _make_concept("c2", "Server uses inline", ["src/server.py"], created_at=2000),
    ]
    conflicts = detect_conflicts(concepts)
    assert len(conflicts) == 1
    assert conflicts[0].concept_a_id == "c1"
    assert conflicts[0].concept_b_id == "c2"


def test_oldest_wins():
    concepts = [
        _make_concept("c1", "Old", ["src/server.py"], created_at=1000),
        _make_concept("c2", "New", ["src/server.py"], created_at=2000),
    ]
    conflicts = detect_conflicts(concepts)
    assert conflicts[0].winner_id == "c1"


def test_ignores_non_active():
    concepts = [
        _make_concept("c1", "Active", ["src/server.py"], status="active"),
        _make_concept("c2", "Archived", ["src/server.py"], status="archived"),
    ]
    assert detect_conflicts(concepts) == []


def test_only_constraint_and_architecture():
    concepts = [
        _make_concept("c1", "A", ["src/server.py"], category="convention"),
        _make_concept("c2", "B", ["src/server.py"], category="convention"),
    ]
    assert detect_conflicts(concepts) == []


def test_constraint_vs_architecture():
    concepts = [
        _make_concept("c1", "Constraint", ["src/server.py"], category="constraint"),
        _make_concept("c2", "Architecture", ["src/server.py"], category="architecture"),
    ]
    assert len(detect_conflicts(concepts)) == 1

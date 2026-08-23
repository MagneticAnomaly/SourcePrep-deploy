"""Tests for directory-scoped concept retrieval."""
from pathlib import Path

import pytest

from prep.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path: Path) -> ConceptStore:
    s = ConceptStore()
    s.init(tmp_path / "test.db")
    yield s
    s.close()


def test_get_for_anchors_directory_returns_matching_concepts(store: ConceptStore) -> None:
    store.save("proj-1", "JWT Auth", "We use JWT for auth", anchors=["src/auth/login.py"], kind="concept")
    store.save("proj-1", "Rate Limiting", "Rate limits on auth", anchors=["src/auth/middleware.py"], kind="concept")
    store.save("proj-1", "DB Schema", "Postgres schema design", anchors=["src/db/schema.py"], kind="concept")

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert len(results) == 2
    titles = {c.title for c in results}
    assert titles == {"JWT Auth", "Rate Limiting"}


def test_get_for_anchors_directory_matches_any_anchor(store: ConceptStore) -> None:
    store.save(
        "proj-1", "Cross-cutting",
        "Spans auth and db",
        anchors=["src/auth/login.py", "src/db/schema.py"],
        kind="concept",
    )

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert len(results) == 1
    assert results[0].title == "Cross-cutting"


def test_get_for_anchors_directory_empty_for_no_match(store: ConceptStore) -> None:
    store.save("proj-1", "Unrelated", "Not anchored to auth", anchors=["src/db/schema.py"], kind="concept")

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert results == []


def test_get_for_anchors_directory_excludes_archived(store: ConceptStore) -> None:
    cid = store.save("proj-1", "Old Auth", "Deprecated", anchors=["src/auth/old.py"], kind="concept")
    store.update(cid, status="archived")

    results = store.get_for_anchors_directory("proj-1", "src/auth")
    assert results == []


def test_get_for_anchors_directory_respects_limit(store: ConceptStore) -> None:
    for i in range(10):
        store.save("proj-1", f"Concept {i}", f"Content {i}", anchors=[f"src/auth/f{i}.py"], kind="concept")

    results = store.get_for_anchors_directory("proj-1", "src/auth", limit=3)
    assert len(results) == 3

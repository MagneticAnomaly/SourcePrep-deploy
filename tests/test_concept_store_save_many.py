"""Phase 96 / F-36: Tests for concept_store.save_many() batch path.

Verifies the batch save behavior added to fix the SQLITE_BUSY contention
that hit the swarm path during concept seeding (26 concepts saved in
tight succession blocked by other store writes).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from unittest.mock import patch

import pytest

from prep.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path):
    s = ConceptStore()
    s.init(tmp_path / "test_save_many.db")
    yield s
    s.close()


def _concept(title: str, content: str = "Default content for the concept") -> dict:
    return {
        "title": title,
        "content": content,
        "category": "technical",
        "confidence": 0.7,
        "anchors": ["src/foo.py"],
        "tags": ["test"],
        "kind": "concept",
    }


# ── Basic batch save ─────────────────────────────────────────────


class TestSaveManyBasic:
    def test_save_many_persists_all_concepts(self, store):
        concepts = [_concept(f"Concept {i}") for i in range(10)]
        saved, skipped = store.save_many("proj-1", concepts)

        assert saved == 10
        assert skipped == 0

        items = store.list_concepts(project_id="proj-1")
        assert len(items) == 10

    def test_save_many_empty_list_returns_zero(self, store):
        saved, skipped = store.save_many("proj-1", [])
        assert saved == 0
        assert skipped == 0

    def test_save_many_skips_empty_title(self, store):
        concepts = [
            _concept("Valid"),
            {"title": "", "content": "x"},
            {"title": "   ", "content": "x"},
        ]
        saved, skipped = store.save_many("proj-1", concepts)
        assert saved == 1
        assert skipped == 2

    def test_save_many_skips_empty_content(self, store):
        concepts = [
            _concept("Valid"),
            {"title": "T", "content": ""},
            {"title": "T", "content": "   "},
        ]
        saved, skipped = store.save_many("proj-1", concepts)
        assert saved == 1
        assert skipped == 2

    def test_save_many_dedups_existing_titles(self, store):
        # First batch creates 3 concepts
        store.save_many("proj-1", [
            _concept("Alpha"),
            _concept("Beta"),
            _concept("Gamma"),
        ])

        # Second batch overlaps on Alpha and Beta — those get updated,
        # not duplicated.  Delta is new.
        saved, skipped = store.save_many("proj-1", [
            _concept("Alpha", "updated alpha content"),
            _concept("Beta", "updated beta content"),
            _concept("Delta", "new concept content"),
        ])

        assert saved == 3  # all three processed
        assert skipped == 0

        items = store.list_concepts(project_id="proj-1")
        # Should be 4 total: alpha (updated), beta (updated), gamma, delta
        assert len(items) == 4

        titles = sorted(c.title for c in items)
        assert titles == ["Alpha", "Beta", "Delta", "Gamma"]

        # Verify alpha was updated
        alpha = next(c for c in items if c.title == "Alpha")
        assert "updated" in alpha.content

    def test_save_many_default_categories_for_invalid(self, store):
        concepts = [
            {"title": "T1", "content": "c", "category": "made_up_cat"},
            {"title": "T2", "content": "c"},  # no category
        ]
        saved, skipped = store.save_many("proj-1", concepts)
        assert saved == 2

        items = store.list_concepts(project_id="proj-1")
        for c in items:
            assert c.category == "technical"  # default fallback


# ── Single transaction (the F-36 fix point) ────────────────────


class TestSaveManySingleTransaction:
    def test_save_many_uses_one_commit(self, store):
        """Verify that save_many() commits exactly once for the whole batch.

        This is the core F-36 fix: instead of N commits (each opening a
        BEGIN..COMMIT pair that competes for the writer lock), one commit
        holds the lock once for the entire batch.

        We can't patch sqlite3.Connection.commit (it's a C built-in), so
        we use set_trace_callback to count COMMIT statements.
        """
        concepts = [_concept(f"C{i}") for i in range(5)]

        statements: list[str] = []
        store._conn.set_trace_callback(lambda sql: statements.append(sql))
        try:
            store.save_many("proj-1", concepts)
        finally:
            store._conn.set_trace_callback(None)

        commit_count = sum(1 for s in statements if s.strip().upper() == "COMMIT")
        # Exactly one COMMIT for the whole batch
        assert commit_count == 1, (
            f"Expected 1 COMMIT for save_many batch, got {commit_count}. "
            f"Statements: {statements}"
        )


# ── Retry behavior on database lock ────────────────────────────


class TestSaveManyRetryOnLocked:
    def test_save_many_retries_on_database_locked(self, store):
        """If the inner save raises 'database is locked' once, save_many
        should retry with backoff and succeed on the second attempt."""
        concepts = [_concept(f"R{i}") for i in range(3)]

        attempt = [0]
        original = store._save_many_locked

        def flaky_inner(conn, project_id, normalized):
            attempt[0] += 1
            if attempt[0] == 1:
                raise sqlite3.OperationalError("database is locked")
            return original(conn, project_id, normalized)

        with patch.object(store, "_save_many_locked", side_effect=flaky_inner):
            saved, skipped = store.save_many("proj-1", concepts)

        # First attempt failed, second succeeded
        assert attempt[0] == 2
        assert saved == 3
        assert skipped == 0

    def test_save_many_propagates_after_max_retries(self, store):
        """After max_retries failed attempts, the error should propagate."""
        concepts = [_concept("X")]

        with patch.object(
            store, "_save_many_locked",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                store.save_many("proj-1", concepts)

    def test_save_many_does_not_retry_other_errors(self, store):
        """Non-lock errors should propagate immediately, not retry."""
        concepts = [_concept("X")]

        attempt = [0]

        def raise_constraint(conn, project_id, normalized):
            attempt[0] += 1
            raise sqlite3.IntegrityError("UNIQUE constraint failed")

        with patch.object(store, "_save_many_locked", side_effect=raise_constraint):
            with pytest.raises(sqlite3.IntegrityError):
                store.save_many("proj-1", concepts)

        # Only one attempt
        assert attempt[0] == 1


# ── Configuration: bumped busy_timeout ─────────────────────────


class TestBusyTimeoutBumped:
    def test_busy_timeout_is_30_seconds(self, store):
        """Phase 96 / F-36 bumped busy_timeout from 10s to 30s."""
        result = store._conn.execute("PRAGMA busy_timeout").fetchone()
        # PRAGMA busy_timeout returns a sqlite3.Row when row_factory is set
        timeout_ms = result[0] if result else 0
        assert timeout_ms == 30000, (
            f"Expected busy_timeout=30000ms, got {timeout_ms}"
        )

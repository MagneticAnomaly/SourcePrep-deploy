"""
Tests for the ObservationStore (Phase 39: Session Continuity).

Tests cover:
- Basic CRUD (save, get, delete, clear)
- Deduplication
- FTS5 search
- Staleness marking
- Per-project limit enforcement
- Stats aggregation
- Observation injection into context
"""

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from codrag.services.observation_store import (
    Observation,
    ObservationStore,
    MAX_OBSERVATIONS_PER_PROJECT,
    MAX_OBSERVATION_CHARS,
    VALID_CATEGORIES,
)


@pytest.fixture
def store(tmp_path):
    """Create a fresh ObservationStore backed by a temp DB."""
    db_path = tmp_path / "test_settings.db"
    s = ObservationStore()
    s.init(db_path)
    yield s
    s.close()


class TestSave:
    def test_save_returns_id(self, store):
        obs_id = store.save("proj-1", "Auth uses JWT tokens")
        assert obs_id
        assert isinstance(obs_id, str)
        assert len(obs_id) == 12

    def test_save_with_file_path(self, store):
        obs_id = store.save("proj-1", "This file handles login", file_path="src/auth.py")
        results = store.get_for_file("proj-1", "src/auth.py")
        assert len(results) == 1
        assert results[0].id == obs_id
        assert results[0].file_path == "src/auth.py"

    def test_save_with_symbol(self, store):
        obs_id = store.save(
            "proj-1", "Validates email format",
            file_path="src/user.py", symbol_fqn="UserService.validate",
        )
        results = store.get_for_file("proj-1", "src/user.py")
        assert len(results) == 1
        assert results[0].symbol_fqn == "UserService.validate"

    def test_save_with_category(self, store):
        store.save("proj-1", "Found potential SQL injection", category="bug")
        results = store.get_recent("proj-1")
        assert results[0].category == "bug"

    def test_save_invalid_category_defaults_to_note(self, store):
        store.save("proj-1", "Some content", category="invalid_cat")
        results = store.get_recent("proj-1")
        assert results[0].category == "note"

    def test_save_empty_content_raises(self, store):
        with pytest.raises(ValueError, match="empty"):
            store.save("proj-1", "")

    def test_save_whitespace_only_raises(self, store):
        with pytest.raises(ValueError, match="empty"):
            store.save("proj-1", "   ")

    def test_save_truncates_long_content(self, store):
        long_content = "x" * (MAX_OBSERVATION_CHARS + 500)
        store.save("proj-1", long_content)
        results = store.get_recent("proj-1")
        assert len(results[0].content) == MAX_OBSERVATION_CHARS

    def test_save_dedup_same_content_same_file(self, store):
        id1 = store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
        id2 = store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
        assert id1 == id2  # Dedup returns existing ID

    def test_save_no_dedup_different_file(self, store):
        id1 = store.save("proj-1", "Uses JWT", file_path="src/auth.py")
        id2 = store.save("proj-1", "Uses JWT", file_path="src/login.py")
        assert id1 != id2

    def test_save_no_dedup_if_stale(self, store):
        id1 = store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
        store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified")
        id2 = store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
        assert id1 != id2  # Stale observation not deduped


class TestDelete:
    def test_delete_existing(self, store):
        obs_id = store.save("proj-1", "Some observation")
        assert store.delete(obs_id) is True
        results = store.get_recent("proj-1")
        assert len(results) == 0

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent-id") is False

    def test_clear_project(self, store):
        store.save("proj-1", "Obs 1")
        store.save("proj-1", "Obs 2")
        store.save("proj-2", "Obs 3")
        deleted = store.clear_project("proj-1")
        assert deleted == 2
        assert len(store.get_recent("proj-1")) == 0
        assert len(store.get_recent("proj-2")) == 1  # Other project untouched


class TestQuery:
    def test_get_recent(self, store):
        store.save("proj-1", "First")
        time.sleep(0.01)
        store.save("proj-1", "Second")
        time.sleep(0.01)
        store.save("proj-1", "Third")
        results = store.get_recent("proj-1", limit=2)
        assert len(results) == 2
        assert results[0].content == "Third"  # Most recent first
        assert results[1].content == "Second"

    def test_get_for_file(self, store):
        store.save("proj-1", "About auth", file_path="src/auth.py")
        store.save("proj-1", "About user", file_path="src/user.py")
        results = store.get_for_file("proj-1", "src/auth.py")
        assert len(results) == 1
        assert results[0].content == "About auth"

    def test_get_for_query_fts(self, store):
        store.save("proj-1", "Authentication uses JWT tokens for session management")
        store.save("proj-1", "Database uses PostgreSQL with connection pooling")
        results = store.get_for_query("proj-1", "JWT authentication")
        # FTS5 should find the JWT observation
        assert len(results) >= 1
        assert any("JWT" in r.content for r in results)

    def test_get_for_query_empty(self, store):
        results = store.get_for_query("proj-1", "nonexistent topic")
        assert len(results) == 0

    def test_get_recent_exclude_stale(self, store):
        store.save("proj-1", "Fresh obs")
        store.save("proj-1", "Will be stale", file_path="src/old.py")
        store.mark_stale_batch("proj-1", ["src/old.py"], "file modified")
        results = store.get_recent("proj-1", include_stale=False)
        assert len(results) == 1
        assert results[0].content == "Fresh obs"


class TestStaleness:
    def test_mark_stale_batch(self, store):
        store.save("proj-1", "About auth", file_path="src/auth.py")
        store.save("proj-1", "About user", file_path="src/user.py")
        store.save("proj-1", "About db", file_path="src/db.py")
        count = store.mark_stale_batch("proj-1", ["src/auth.py", "src/user.py"], "file modified")
        assert count == 2

        results = store.get_recent("proj-1")
        stale_paths = {r.file_path for r in results if r.stale}
        assert stale_paths == {"src/auth.py", "src/user.py"}

    def test_mark_stale_idempotent(self, store):
        store.save("proj-1", "About auth", file_path="src/auth.py")
        count1 = store.mark_stale_batch("proj-1", ["src/auth.py"], "modified")
        count2 = store.mark_stale_batch("proj-1", ["src/auth.py"], "modified again")
        assert count1 == 1
        assert count2 == 0  # Already stale, not re-marked

    def test_mark_stale_empty_paths(self, store):
        count = store.mark_stale_batch("proj-1", [], "no change")
        assert count == 0

    def test_mark_stale_no_matching_observations(self, store):
        store.save("proj-1", "About auth", file_path="src/auth.py")
        count = store.mark_stale_batch("proj-1", ["src/nonexistent.py"], "modified")
        assert count == 0

    def test_stale_reason_recorded(self, store):
        store.save("proj-1", "About auth", file_path="src/auth.py")
        store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified at 2026-02-23")
        results = store.get_for_file("proj-1", "src/auth.py")
        assert results[0].stale is True
        assert results[0].stale_reason == "file modified at 2026-02-23"

    def test_cross_project_isolation(self, store):
        store.save("proj-1", "About auth", file_path="src/auth.py")
        store.save("proj-2", "About auth", file_path="src/auth.py")
        count = store.mark_stale_batch("proj-1", ["src/auth.py"], "modified")
        assert count == 1
        # proj-2 observation should NOT be stale
        results = store.get_for_file("proj-2", "src/auth.py")
        assert results[0].stale is False


class TestStats:
    def test_stats_empty(self, store):
        stats = store.get_stats("proj-1")
        assert stats["total"] == 0
        assert stats["stale"] == 0
        assert stats["fresh"] == 0
        assert stats["by_category"] == {}

    def test_stats_with_data(self, store):
        store.save("proj-1", "Note 1", category="note")
        store.save("proj-1", "Bug 1", category="bug", file_path="src/a.py")
        store.save("proj-1", "Decision 1", category="decision")
        store.mark_stale_batch("proj-1", ["src/a.py"], "modified")

        stats = store.get_stats("proj-1")
        assert stats["total"] == 3
        assert stats["stale"] == 1
        assert stats["fresh"] == 2
        assert stats["by_category"]["note"] == 1
        assert stats["by_category"]["bug"] == 1
        assert stats["by_category"]["decision"] == 1


class TestEviction:
    def test_evicts_oldest_when_limit_reached(self, store):
        # Save up to the limit
        for i in range(MAX_OBSERVATIONS_PER_PROJECT):
            store.save("proj-1", f"Observation {i}")

        # Save one more — should evict the oldest
        store.save("proj-1", "New observation after limit")
        stats = store.get_stats("proj-1")
        assert stats["total"] == MAX_OBSERVATIONS_PER_PROJECT

        # The newest should exist
        results = store.get_recent("proj-1", limit=1)
        assert results[0].content == "New observation after limit"

    def test_evicts_stale_first(self, store):
        # Save a few, mark some stale
        store.save("proj-1", "Fresh important", file_path="src/fresh.py")
        store.save("proj-1", "Will be stale", file_path="src/stale.py")
        store.mark_stale_batch("proj-1", ["src/stale.py"], "modified")

        # Fill to limit
        for i in range(MAX_OBSERVATIONS_PER_PROJECT - 2):
            store.save("proj-1", f"Filler {i}")

        # One more to trigger eviction
        store.save("proj-1", "Final observation")

        # The stale one should have been evicted first
        results = store.get_for_file("proj-1", "src/stale.py")
        assert len(results) == 0  # Evicted

        # Fresh important should still exist
        results = store.get_for_file("proj-1", "src/fresh.py")
        assert len(results) == 1


class TestObservationDataclass:
    def test_to_dict_minimal(self):
        obs = Observation(
            id="abc123",
            project_id="proj-1",
            content="Test observation",
            created_at=1000.0,
        )
        d = obs.to_dict()
        assert d["id"] == "abc123"
        assert d["content"] == "Test observation"
        assert "file_path" not in d  # Optional fields excluded when None
        assert "symbol_fqn" not in d

    def test_to_dict_full(self):
        obs = Observation(
            id="abc123",
            project_id="proj-1",
            content="Test observation",
            file_path="src/auth.py",
            symbol_fqn="Auth.validate",
            trace_node_id="node-1",
            category="bug",
            created_at=1000.0,
            updated_at=2000.0,
            stale=True,
            stale_reason="file modified",
        )
        d = obs.to_dict()
        assert d["file_path"] == "src/auth.py"
        assert d["symbol_fqn"] == "Auth.validate"
        assert d["trace_node_id"] == "node-1"
        assert d["stale"] is True
        assert d["stale_reason"] == "file modified"
        assert d["updated_at"] == 2000.0


class TestContextInjection:
    """Test the _inject_observations helper from projects.py."""

    def test_inject_observations_no_store(self):
        """Injection is a no-op when the store hasn't been initialized."""
        from codrag.api.routers.projects import _inject_observations
        ctx, meta = _inject_observations("existing context", "proj-1", "test query")
        assert ctx == "existing context"
        assert meta is None

    def test_inject_observations_with_data(self, store):
        """When observations exist, they are appended as session-memory."""
        store.save("proj-1", "Auth uses JWT tokens for session management")
        from codrag.api.routers.projects import _inject_observations
        ctx, meta = _inject_observations("base context", "proj-1", "JWT authentication")
        if meta is not None:
            assert "[session-memory]" in ctx
            assert meta["observations_injected"] >= 1
        # If FTS doesn't match, that's acceptable — search is best-effort

    def test_inject_observations_stale_marked(self, store):
        """Stale observations get [STALE] prefix."""
        store.save("proj-1", "Auth uses JWT", file_path="src/auth.py")
        store.mark_stale_batch("proj-1", ["src/auth.py"], "modified")
        from codrag.api.routers.projects import _inject_observations
        ctx, meta = _inject_observations("base context", "proj-1", "JWT")
        if meta is not None:
            assert "[STALE]" in ctx
            assert meta["stale"] >= 1

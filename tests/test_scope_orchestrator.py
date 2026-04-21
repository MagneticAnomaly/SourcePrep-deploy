"""Tests for the Scope Orchestrator (SM-8: Knowledge Scope Pipeline)."""

import threading
import time
from typing import Set

import pytest

from prep.services.scope_orchestrator import (
    ScopeOrchestrator,
    ScopeState,
)


@pytest.fixture
def orchestrator():
    """Fresh scope orchestrator with short debounce for fast tests."""
    return ScopeOrchestrator(debounce_ms=200, auto_rebuild=True)


def _make_build_fn(results: list, delay: float = 0):
    """Create a build function that records calls and optionally delays."""
    def build_fn(added: Set[str], removed: Set[str], changed: Set[str]) -> bool:
        if delay:
            time.sleep(delay)
        results.append({"added": added, "removed": removed, "changed": changed})
        return True
    return build_fn


def _make_failing_build_fn():
    """Create a build function that always fails."""
    def build_fn(added, removed, changed):
        raise RuntimeError("Build exploded")
    return build_fn


# ── Basic lifecycle ──────────────────────────────────────────────


def test_initial_status_is_idle(orchestrator):
    status = orchestrator.status("proj-1")
    assert status["state"] == ScopeState.IDLE
    assert status["total_pending"] == 0
    assert status["is_stale"] is False


def test_add_files_triggers_rebuild(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))
    orchestrator.on_files_added("proj-1", ["/src/main.py", "/src/utils.py"])

    # Wait for debounce + build
    time.sleep(0.8)

    assert len(results) == 1
    assert results[0]["added"] == {"/src/main.py", "/src/utils.py"}
    assert results[0]["removed"] == set()


def test_remove_files_triggers_rebuild(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))
    orchestrator.on_files_removed("proj-1", ["/src/old.py"])

    time.sleep(0.8)

    assert len(results) == 1
    assert results[0]["removed"] == {"/src/old.py"}


def test_changed_files_triggers_rebuild(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))
    orchestrator.on_files_changed("proj-1", ["/src/main.py"])

    time.sleep(0.8)

    assert len(results) == 1
    assert results[0]["changed"] == {"/src/main.py"}


# ── Debouncing ───────────────────────────────────────────────────


def test_rapid_changes_debounced_into_one_build(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))

    # Rapid-fire changes within debounce window
    orchestrator.on_files_added("proj-1", ["/a.py"])
    time.sleep(0.05)
    orchestrator.on_files_added("proj-1", ["/b.py"])
    time.sleep(0.05)
    orchestrator.on_files_removed("proj-1", ["/c.py"])

    # Wait for debounce + build
    time.sleep(0.8)

    # Should be a single build with all changes batched
    assert len(results) == 1
    assert "/a.py" in results[0]["added"]
    assert "/b.py" in results[0]["added"]
    assert "/c.py" in results[0]["removed"]


def test_add_then_remove_cancels_out(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))

    orchestrator.on_files_added("proj-1", ["/a.py"])
    orchestrator.on_files_removed("proj-1", ["/a.py"])

    time.sleep(0.8)

    # The file was added then removed — should cancel out
    assert len(results) == 1
    assert "/a.py" not in results[0]["added"]
    assert "/a.py" in results[0]["removed"]


# ── Status during states ─────────────────────────────────────────


def test_status_during_debounce(orchestrator):
    orchestrator.register_build_fn("proj-1", _make_build_fn([]))
    orchestrator.on_files_added("proj-1", ["/a.py"])

    # Check immediately — should be debouncing
    status = orchestrator.status("proj-1")
    assert status["state"] == ScopeState.DEBOUNCING
    assert status["pending_adds"] == 1
    assert status["is_stale"] is True

    time.sleep(0.8)


def test_status_after_successful_build(orchestrator):
    orchestrator.register_build_fn("proj-1", _make_build_fn([]))
    orchestrator.on_files_added("proj-1", ["/a.py"])

    time.sleep(0.8)

    status = orchestrator.status("proj-1")
    assert status["state"] == ScopeState.IDLE
    assert status["total_pending"] == 0
    assert status["is_stale"] is False
    assert status["last_rebuild_at"] is not None
    assert status["error"] is None


# ── Failure handling ─────────────────────────────────────────────


def test_failed_build_sets_error(orchestrator):
    orchestrator.register_build_fn("proj-1", _make_failing_build_fn())
    orchestrator.on_files_added("proj-1", ["/a.py"])

    time.sleep(0.8)

    status = orchestrator.status("proj-1")
    assert status["state"] == ScopeState.FAILED
    assert "exploded" in status["error"]


# ── Free tier (no auto-rebuild) ──────────────────────────────────


def test_no_auto_rebuild_marks_stale():
    orch = ScopeOrchestrator(debounce_ms=200, auto_rebuild=False)
    results = []
    orch.register_build_fn("proj-1", _make_build_fn(results))
    orch.on_files_added("proj-1", ["/a.py"])

    time.sleep(0.5)

    # Should NOT have triggered a build
    assert len(results) == 0

    status = orch.status("proj-1")
    assert status["state"] == ScopeState.STALE
    assert status["is_stale"] is True
    assert status["stale_since"] is not None


def test_manual_trigger_on_stale():
    orch = ScopeOrchestrator(debounce_ms=200, auto_rebuild=False)
    results = []
    orch.register_build_fn("proj-1", _make_build_fn(results))
    orch.on_files_added("proj-1", ["/a.py"])

    time.sleep(0.3)

    # Manually trigger
    started = orch.trigger_rebuild("proj-1")
    assert started is True

    time.sleep(0.5)

    assert len(results) == 1
    status = orch.status("proj-1")
    assert status["state"] == ScopeState.IDLE


def test_manual_trigger_no_pending_returns_false(orchestrator):
    orchestrator.register_build_fn("proj-1", _make_build_fn([]))
    started = orchestrator.trigger_rebuild("proj-1")
    assert started is False


# ── Multi-project independence ───────────────────────────────────


def test_independent_projects(orchestrator):
    results1 = []
    results2 = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results1))
    orchestrator.register_build_fn("proj-2", _make_build_fn(results2))

    orchestrator.on_files_added("proj-1", ["/a.py"])
    orchestrator.on_files_added("proj-2", ["/b.py"])

    time.sleep(0.8)

    assert len(results1) == 1
    assert len(results2) == 1
    assert results1[0]["added"] == {"/a.py"}
    assert results2[0]["added"] == {"/b.py"}


# ── Clear project ────────────────────────────────────────────────


def test_clear_project(orchestrator):
    orchestrator.register_build_fn("proj-1", _make_build_fn([]))
    orchestrator.on_files_added("proj-1", ["/a.py"])
    orchestrator.clear_project("proj-1")

    status = orchestrator.status("proj-1")
    assert status["state"] == ScopeState.IDLE
    assert status["total_pending"] == 0


# ── Empty changes ignored ────────────────────────────────────────


def test_empty_adds_ignored(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))
    orchestrator.on_files_added("proj-1", [])

    time.sleep(0.5)
    assert len(results) == 0


def test_empty_removes_ignored(orchestrator):
    results = []
    orchestrator.register_build_fn("proj-1", _make_build_fn(results))
    orchestrator.on_files_removed("proj-1", [])

    time.sleep(0.5)
    assert len(results) == 0


# ── Configuration ────────────────────────────────────────────────


def test_debounce_ms_minimum():
    orch = ScopeOrchestrator(debounce_ms=100)
    orch.debounce_ms = 200
    assert orch.debounce_ms == 500  # Minimum is 500ms


def test_auto_rebuild_toggle():
    orch = ScopeOrchestrator(auto_rebuild=True)
    assert orch.auto_rebuild is True
    orch.auto_rebuild = False
    assert orch.auto_rebuild is False

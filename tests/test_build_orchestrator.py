"""Tests for the Build Orchestrator (SM-4)."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from prep.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildSlot,
    BuildType,
)


@pytest.fixture
def orchestrator():
    """Fresh orchestrator for each test."""
    return BuildOrchestrator()


# ── Basic lifecycle ──────────────────────────────────────────────


def test_initial_status_is_idle(orchestrator):
    slot = orchestrator.status("proj-1", BuildType.TRACE)
    assert slot.phase == BuildPhase.IDLE
    assert not slot.is_active


def test_start_transitions_to_running(orchestrator):
    def worker(slot, progress_cb):
        time.sleep(0.1)
        return {"ok": True}

    started = orchestrator.start("proj-1", BuildType.TRACE, worker)
    assert started is True

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    assert slot.phase == BuildPhase.RUNNING
    assert slot.is_active
    assert slot.started_at is not None


def test_successful_build_completes(orchestrator):
    event = threading.Event()

    def worker(slot, progress_cb):
        return {"files": 42}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    # Wait for thread to finish
    time.sleep(0.3)

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    assert slot.phase == BuildPhase.COMPLETED
    assert slot.result == {"files": 42}
    assert slot.finished_at is not None
    assert slot.error is None


def test_failed_build_transitions_to_failed(orchestrator):
    def worker(slot, progress_cb):
        raise RuntimeError("disk full")

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    assert slot.phase == BuildPhase.FAILED
    assert "disk full" in slot.error
    assert slot.finished_at is not None


def test_cannot_start_while_active(orchestrator):
    barrier = threading.Event()

    def worker(slot, progress_cb):
        barrier.wait(timeout=5)
        return {}

    started1 = orchestrator.start("proj-1", BuildType.TRACE, worker)
    assert started1 is True

    started2 = orchestrator.start("proj-1", BuildType.TRACE, worker)
    assert started2 is False

    barrier.set()
    time.sleep(0.2)


def test_can_restart_after_completion(orchestrator):
    def worker(slot, progress_cb):
        return {"run": 1}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    assert orchestrator.status("proj-1", BuildType.TRACE).phase == BuildPhase.COMPLETED

    def worker2(slot, progress_cb):
        return {"run": 2}

    started = orchestrator.start("proj-1", BuildType.TRACE, worker2)
    assert started is True
    time.sleep(0.3)

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    assert slot.phase == BuildPhase.COMPLETED
    assert slot.result == {"run": 2}


# ── Progress reporting ───────────────────────────────────────────


def test_progress_callback(orchestrator):
    progress_events = []

    def worker(slot, progress_cb):
        progress_cb("Scanning", 0, 100)
        progress_cb("Building", 50, 100)
        progress_cb("Done", 100, 100)
        return {}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    # Last progress should be visible
    assert slot.progress_message == "Done"
    assert slot.progress_current == 100
    assert slot.progress_total == 100


# ── Cancellation ─────────────────────────────────────────────────


def test_cancel_running_build(orchestrator):
    barrier = threading.Event()

    def worker(slot, progress_cb):
        barrier.wait(timeout=5)
        return {}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    cancelled = orchestrator.cancel("proj-1", BuildType.TRACE)
    assert cancelled is True

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    assert slot.phase == BuildPhase.FAILED
    assert "Cancelled" in slot.error

    barrier.set()


def test_cancel_idle_returns_false(orchestrator):
    cancelled = orchestrator.cancel("proj-1", BuildType.TRACE)
    assert cancelled is False


# ── Multi-project / multi-type ───────────────────────────────────


def test_independent_slots_per_project(orchestrator):
    def worker(slot, progress_cb):
        return {"project": slot.project_id}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    orchestrator.start("proj-2", BuildType.TRACE, worker)
    time.sleep(0.3)

    s1 = orchestrator.status("proj-1", BuildType.TRACE)
    s2 = orchestrator.status("proj-2", BuildType.TRACE)
    assert s1.result == {"project": "proj-1"}
    assert s2.result == {"project": "proj-2"}


def test_independent_slots_per_type(orchestrator):
    def worker(slot, progress_cb):
        return {"type": slot.build_type.value}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    orchestrator.start("proj-1", BuildType.KNOWLEDGE, worker)
    time.sleep(0.3)

    s1 = orchestrator.status("proj-1", BuildType.TRACE)
    s2 = orchestrator.status("proj-1", BuildType.KNOWLEDGE)
    assert s1.result == {"type": "trace"}
    assert s2.result == {"type": "knowledge"}


# ── Listener system ──────────────────────────────────────────────


def test_listener_notified_on_completion(orchestrator):
    events = []

    def listener(project_id, build_type, old_phase, new_phase):
        events.append((project_id, build_type, old_phase, new_phase))

    orchestrator.add_listener(listener)

    def worker(slot, progress_cb):
        return {}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    # Should have RUNNING + COMPLETED transitions
    assert len(events) >= 2
    # First event: transition to RUNNING
    assert events[0] == ("proj-1", BuildType.TRACE, BuildPhase.IDLE, BuildPhase.RUNNING)
    # Last event: transition to COMPLETED
    assert events[-1] == ("proj-1", BuildType.TRACE, BuildPhase.RUNNING, BuildPhase.COMPLETED)


def test_listener_notified_on_failure(orchestrator):
    events = []

    def listener(project_id, build_type, old_phase, new_phase):
        events.append((project_id, build_type, old_phase, new_phase))

    orchestrator.add_listener(listener)

    def worker(slot, progress_cb):
        raise ValueError("boom")

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    assert events[-1] == ("proj-1", BuildType.TRACE, BuildPhase.RUNNING, BuildPhase.FAILED)


# ── Zombie detection ─────────────────────────────────────────────


def test_zombie_thread_detected(orchestrator):
    """Simulate a thread that dies without proper cleanup."""
    slot = BuildSlot(project_id="proj-1", build_type=BuildType.TRACE)
    slot.phase = BuildPhase.RUNNING
    slot.started_at = time.time()
    # Create a dead thread
    t = threading.Thread(target=lambda: None)
    t.start()
    t.join()  # Wait for it to die
    slot.thread = t

    orchestrator._slots[("proj-1", BuildType.TRACE)] = slot

    # Status check should detect the zombie
    result = orchestrator.status("proj-1", BuildType.TRACE)
    assert result.phase == BuildPhase.FAILED
    assert "died unexpectedly" in result.error


# ── Utility methods ──────────────────────────────────────────────


def test_is_any_active(orchestrator):
    assert orchestrator.is_any_active("proj-1") is False

    barrier = threading.Event()

    def worker(slot, progress_cb):
        barrier.wait(timeout=5)
        return {}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    assert orchestrator.is_any_active("proj-1") is True

    barrier.set()
    time.sleep(0.3)
    assert orchestrator.is_any_active("proj-1") is False


def test_all_slots(orchestrator):
    def worker(slot, progress_cb):
        return {}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    orchestrator.start("proj-2", BuildType.KNOWLEDGE, worker)
    time.sleep(0.3)

    all_slots = orchestrator.all_slots()
    assert len(all_slots) == 2

    proj1_slots = orchestrator.all_slots(project_id="proj-1")
    assert len(proj1_slots) == 1
    assert proj1_slots[0].project_id == "proj-1"


def test_clear_project(orchestrator):
    def worker(slot, progress_cb):
        return {}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    orchestrator.clear_project("proj-1")
    assert orchestrator.all_slots(project_id="proj-1") == []


def test_slot_to_dict(orchestrator):
    def worker(slot, progress_cb):
        progress_cb("Working", 5, 10)
        return {"ok": True}

    orchestrator.start("proj-1", BuildType.TRACE, worker)
    time.sleep(0.3)

    slot = orchestrator.status("proj-1", BuildType.TRACE)
    d = slot.to_dict()
    assert d["project_id"] == "proj-1"
    assert d["build_type"] == "trace"
    assert d["phase"] == "completed"
    assert d["started_at"] is not None
    assert d["finished_at"] is not None
    assert d["error"] is None
    assert "progress" in d
    assert d["progress"]["message"] == "Working"

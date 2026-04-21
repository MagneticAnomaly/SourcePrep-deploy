"""
Tests for Pipeline State Machine (Phase 25B)
=============================================

Tests the formal state machine logic independently of the actual pipeline
orchestrator. No LLM or server required — pure state transition tests.
"""

import pytest
import threading
import time

from prep.services.pipeline.state_machine import (
    PipelineState,
    PipelineGroupStateMachine,
    Event,
    TransitionGuard,
    ActiveProjectGuard,
    StageSnapshot,
    TERMINAL_STATES,
    ACTIVE_STATES,
    _TRANSITIONS,
)


# ── Helpers ──────────────────────────────────────────────────────

def make_sm(stages=None, project_id="test-proj", group="fast_sync"):
    """Create a state machine with default stages."""
    if stages is None:
        stages = ["structural", "inferred_edges", "catalogue", "validation", "knowledge"]
    return PipelineGroupStateMachine(
        project_id=project_id,
        group=group,
        stages=stages,
    )


# ── Basic lifecycle tests ────────────────────────────────────────

class TestBasicLifecycle:
    """Test the happy path: IDLE → RUNNING → stage completions → COMPLETED."""

    def test_initial_state_is_idle(self):
        sm = make_sm()
        assert sm.state == PipelineState.IDLE
        assert not sm.is_active
        assert not sm.is_terminal
        assert not sm.is_paused

    def test_start_transitions_to_running(self):
        sm = make_sm()
        ok = sm.transition(Event.START)
        assert ok
        assert sm.state == PipelineState.RUNNING
        assert sm.is_active
        assert sm.started_at is not None

    def test_cannot_start_twice(self):
        sm = make_sm()
        sm.transition(Event.START)
        ok = sm.transition(Event.START)
        assert not ok  # RUNNING + START is not a valid transition
        assert sm.state == PipelineState.RUNNING

    def test_stage_completed_stays_running(self):
        sm = make_sm(["s1", "s2", "s3"])
        sm.transition(Event.START)
        assert sm.current_stage == "s1"

        ok = sm.transition(Event.STAGE_COMPLETED)
        assert ok
        assert sm.state == PipelineState.RUNNING
        assert sm.current_stage == "s2"
        assert sm.stage_results.get("s1") == "completed"

    def test_all_stages_done_completes(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # s1 done
        sm.transition(Event.STAGE_COMPLETED)  # s2 done

        ok = sm.transition(Event.ALL_STAGES_DONE)
        assert ok
        assert sm.state == PipelineState.COMPLETED
        assert sm.is_terminal
        assert not sm.is_active
        assert sm.finished_at is not None

    def test_full_happy_path(self):
        sm = make_sm(["structural", "catalogue", "knowledge"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # structural
        sm.transition(Event.STAGE_COMPLETED)  # catalogue
        sm.transition(Event.STAGE_COMPLETED)  # knowledge
        sm.transition(Event.ALL_STAGES_DONE)

        assert sm.state == PipelineState.COMPLETED
        assert sm.stage_results == {
            "structural": "completed",
            "catalogue": "completed",
            "knowledge": "completed",
        }


# ── Pause / Resume tests ────────────────────────────────────────

class TestPauseResume:
    """Test the pause → resume lifecycle."""

    def test_pause_from_running(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # s1 done, now on s2

        ok = sm.transition(Event.PAUSE)
        assert ok
        assert sm.state == PipelineState.PAUSING

    def test_stage_flushed_completes_pause(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)
        sm.transition(Event.PAUSE)

        ok = sm.transition(Event.STAGE_FLUSHED)
        assert ok
        assert sm.state == PipelineState.PAUSED
        assert sm.is_paused
        assert not sm.is_active
        assert sm.finished_at is not None

    def test_resume_from_paused(self):
        sm = make_sm(["s1", "s2", "s3"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # s1 done
        sm.transition(Event.PAUSE)
        sm.transition(Event.STAGE_FLUSHED)

        assert sm.state == PipelineState.PAUSED
        assert sm.current_stage == "s2"  # Paused at s2

        ok = sm.transition(Event.RESUME)
        assert ok
        assert sm.state == PipelineState.RUNNING
        assert sm.current_stage == "s2"  # Resumes at same stage
        assert sm.error is None
        assert sm.finished_at is None

    def test_cannot_pause_when_idle(self):
        sm = make_sm()
        ok = sm.transition(Event.PAUSE)
        assert not ok
        assert sm.state == PipelineState.IDLE

    def test_cannot_resume_when_running(self):
        sm = make_sm()
        sm.transition(Event.START)
        ok = sm.transition(Event.RESUME)
        assert not ok

    def test_pause_resume_continues_from_same_stage(self):
        sm = make_sm(["s1", "s2", "s3"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # s1 done
        # Now running s2
        assert sm.current_stage == "s2"

        sm.transition(Event.PAUSE)
        sm.transition(Event.STAGE_FLUSHED)
        assert sm.current_stage == "s2"  # Still at s2

        sm.transition(Event.RESUME)
        assert sm.current_stage == "s2"  # Resumed at s2, not s1

        sm.transition(Event.STAGE_COMPLETED)  # s2 done
        assert sm.current_stage == "s3"


# ── Cancel tests ─────────────────────────────────────────────────

class TestCancel:
    """Test cancellation from various states."""

    def test_cancel_from_running(self):
        sm = make_sm()
        sm.transition(Event.START)

        ok = sm.transition(Event.CANCEL)
        assert ok
        assert sm.state == PipelineState.CANCELLING

        ok = sm.transition(Event.STAGE_STOPPED)
        assert ok
        assert sm.state == PipelineState.CANCELLED
        assert sm.is_terminal

    def test_cancel_from_paused(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.PAUSE)
        sm.transition(Event.STAGE_FLUSHED)

        ok = sm.transition(Event.CANCEL)
        assert ok
        assert sm.state == PipelineState.CANCELLED  # Immediate, no CANCELLING needed

    def test_cancel_during_pausing(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.PAUSE)

        ok = sm.transition(Event.CANCEL)
        assert ok
        assert sm.state == PipelineState.CANCELLING


# ── Failure tests ────────────────────────────────────────────────

class TestFailure:
    """Test stage failure handling."""

    def test_stage_failure_from_running(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # s1 done

        ok = sm.transition(Event.STAGE_FAILED, detail="LLM timeout on s2")
        assert ok
        assert sm.state == PipelineState.FAILED
        assert sm.error == "LLM timeout on s2"
        assert sm.stage_results.get("s2") == "failed"
        assert sm.is_terminal

    def test_failure_during_pausing(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.PAUSE)

        ok = sm.transition(Event.STAGE_FAILED, detail="Worker crashed")
        assert ok
        assert sm.state == PipelineState.FAILED


# ── Crash recovery tests ────────────────────────────────────────

class TestCrashRecovery:
    """Test crash detection and recovery."""

    def test_crash_detected_from_idle(self):
        sm = make_sm(["s1", "s2", "s3"])
        ok = sm.transition(Event.CRASH_DETECTED)
        assert ok
        assert sm.state == PipelineState.RECOVERING

    def test_recovery_succeeded(self):
        sm = make_sm(["s1", "s2", "s3"])
        sm.current_stage_index = 2  # Was on s3 when crashed
        sm.stage_results = {"s1": "completed", "s2": "completed"}

        sm.transition(Event.CRASH_DETECTED)
        ok = sm.transition(Event.RECOVERY_SUCCEEDED)
        assert ok
        assert sm.state == PipelineState.RUNNING
        assert sm.current_stage == "s3"  # Resumes at s3

    def test_recovery_failed(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.CRASH_DETECTED)

        ok = sm.transition(Event.RECOVERY_FAILED, detail="Checkpoint corrupted")
        assert ok
        assert sm.state == PipelineState.FAILED
        assert sm.error == "Checkpoint corrupted"


# ── Reset tests ──────────────────────────────────────────────────

class TestReset:
    """Test reset from terminal states back to IDLE."""

    def test_reset_from_completed(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)
        sm.transition(Event.ALL_STAGES_DONE)

        ok = sm.transition(Event.RESET)
        assert ok
        assert sm.state == PipelineState.IDLE
        assert sm.current_stage_index == 0
        assert sm.stage_results == {}

    def test_reset_from_failed(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_FAILED)

        ok = sm.transition(Event.RESET)
        assert ok
        assert sm.state == PipelineState.IDLE

    def test_reset_from_cancelled(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.CANCEL)
        sm.transition(Event.STAGE_STOPPED)

        ok = sm.transition(Event.RESET)
        assert ok
        assert sm.state == PipelineState.IDLE

    def test_reset_from_paused(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.PAUSE)
        sm.transition(Event.STAGE_FLUSHED)

        ok = sm.transition(Event.RESET)
        assert ok
        assert sm.state == PipelineState.IDLE

    def test_cannot_reset_from_running(self):
        sm = make_sm()
        sm.transition(Event.START)
        ok = sm.transition(Event.RESET)
        assert not ok


# ── Guard tests ──────────────────────────────────────────────────

class TestGuards:
    """Test transition guards."""

    def test_custom_guard_blocks_start(self):
        sm = make_sm()

        class AlwaysBlock(TransitionGuard):
            def check(self, sm, event, **kwargs):
                if event == Event.START:
                    return "Blocked for testing"
                return None

        sm.add_guard(AlwaysBlock())
        ok = sm.transition(Event.START)
        assert not ok
        assert sm.state == PipelineState.IDLE

    def test_guard_allows_other_events(self):
        """Guards that only block START should allow other transitions."""
        sm = make_sm()

        class OnlyBlockStart(TransitionGuard):
            def check(self, sm, event, **kwargs):
                if event == Event.START:
                    return "Blocked"
                return None

        sm.add_guard(OnlyBlockStart())
        # Manually set to RUNNING to test other transitions
        sm.state = PipelineState.RUNNING
        ok = sm.transition(Event.PAUSE)
        assert ok  # Guard doesn't block PAUSE


# ── History tests ────────────────────────────────────────────────

class TestHistory:
    """Test transition history recording."""

    def test_history_recorded(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)
        sm.transition(Event.ALL_STAGES_DONE)

        assert len(sm.history) == 3
        assert sm.history[0].from_state == PipelineState.IDLE
        assert sm.history[0].to_state == PipelineState.RUNNING
        assert sm.history[0].event == Event.START
        assert sm.history[2].to_state == PipelineState.COMPLETED

    def test_rejected_transitions_not_in_history(self):
        sm = make_sm()
        sm.transition(Event.PAUSE)  # Invalid from IDLE
        assert len(sm.history) == 0

    def test_history_bounded(self):
        sm = make_sm(["s1"] * 200)
        sm._max_history = 10
        sm.transition(Event.START)
        for _ in range(200):
            sm.transition(Event.STAGE_COMPLETED)
        assert len(sm.history) <= 10


# ── Thread safety tests ─────────────────────────────────────────

class TestThreadSafety:
    """Test that concurrent transitions don't corrupt state."""

    def test_concurrent_starts_only_one_succeeds(self):
        sm = make_sm()
        results = []

        def try_start():
            ok = sm.transition(Event.START)
            results.append(ok)

        threads = [threading.Thread(target=try_start) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 1  # Only one START should succeed
        assert sm.state == PipelineState.RUNNING


# ── Serialization tests ─────────────────────────────────────────

class TestSerialization:
    """Test to_dict() backward compatibility."""

    def test_to_dict_matches_old_format(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)

        d = sm.to_dict()
        assert d["project_id"] == "test-proj"
        assert d["group"] == "fast_sync"
        assert d["phase"] == "running"
        assert d["current_stage"] == "s2"
        assert d["current_stage_index"] == 1
        assert d["total_stages"] == 2
        assert d["started_at"] is not None
        assert d["finished_at"] is None
        assert d["error"] is None
        assert d["stage_results"] == {"s1": "completed"}
        assert d["is_active"] is True
        assert d["is_paused"] is False

    def test_to_dict_paused(self):
        sm = make_sm(["s1"])
        sm.transition(Event.START)
        sm.transition(Event.PAUSE)
        sm.transition(Event.STAGE_FLUSHED)

        d = sm.to_dict()
        assert d["phase"] == "paused"
        assert d["is_paused"] is True
        assert d["is_active"] is False


# ── Queue tests ──────────────────────────────────────────────────

class TestQueuing:
    """Test the QUEUED state for multi-project compute scheduling."""

    def test_enqueue_from_idle(self):
        sm = make_sm(["s1", "s2"])
        ok = sm.transition(Event.ENQUEUE)
        assert ok
        assert sm.state == PipelineState.QUEUED
        assert sm.is_queued
        assert sm.is_active  # Queued counts as active

    def test_capacity_available_starts_running(self):
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.ENQUEUE)

        ok = sm.transition(Event.CAPACITY_AVAILABLE)
        assert ok
        assert sm.state == PipelineState.RUNNING

    def test_cancel_from_queued(self):
        sm = make_sm(["s1"])
        sm.transition(Event.ENQUEUE)

        ok = sm.transition(Event.CANCEL)
        assert ok
        assert sm.state == PipelineState.CANCELLED

    def test_reset_from_queued(self):
        sm = make_sm(["s1"])
        sm.transition(Event.ENQUEUE)

        ok = sm.transition(Event.RESET)
        assert ok
        assert sm.state == PipelineState.IDLE

    def test_between_stage_queuing(self):
        """When a running pipeline hits a stage that needs a full compute node."""
        sm = make_sm(["s1", "s2", "s3"])
        sm.transition(Event.START)
        sm.transition(Event.STAGE_COMPLETED)  # s1 done

        # Next stage (s2) needs a compute slot that is full
        ok = sm.transition(Event.ENQUEUE)
        assert ok
        assert sm.state == PipelineState.QUEUED
        assert sm.current_stage == "s2"

        # Slot frees up
        ok = sm.transition(Event.CAPACITY_AVAILABLE)
        assert ok
        assert sm.state == PipelineState.RUNNING
        assert sm.current_stage == "s2"  # Resumes at same stage

    def test_full_lifecycle_with_queuing(self):
        """IDLE → QUEUED → RUNNING → stage completions → COMPLETED."""
        sm = make_sm(["s1", "s2"])
        sm.transition(Event.ENQUEUE)          # No capacity
        sm.transition(Event.CAPACITY_AVAILABLE)  # Got a slot
        sm.transition(Event.STAGE_COMPLETED)  # s1 done
        sm.transition(Event.STAGE_COMPLETED)  # s2 done
        sm.transition(Event.ALL_STAGES_DONE)

        assert sm.state == PipelineState.COMPLETED
        assert sm.stage_results == {"s1": "completed", "s2": "completed"}

    def test_to_dict_queued(self):
        sm = make_sm(["s1"])
        sm.transition(Event.ENQUEUE)

        d = sm.to_dict()
        assert d["phase"] == "queued"
        assert d["is_queued"] is True
        assert d["is_active"] is True
        assert d["is_paused"] is False


# ── Transition table completeness ────────────────────────────────

class TestTransitionTable:
    """Verify the transition table is consistent."""

    def test_all_states_have_at_least_one_outgoing(self):
        states_with_outgoing = set()
        for (state, _) in _TRANSITIONS:
            states_with_outgoing.add(state)
        # Every non-terminal state should have outgoing transitions
        for state in PipelineState:
            if state not in TERMINAL_STATES or state == PipelineState.PAUSED:
                assert state in states_with_outgoing, \
                    f"State {state.value} has no outgoing transitions"

    def test_terminal_states_only_allow_reset(self):
        for state in TERMINAL_STATES:
            allowed_events = [
                ev for (s, ev) in _TRANSITIONS if s == state
            ]
            assert all(ev == Event.RESET for ev in allowed_events), \
                f"Terminal state {state.value} allows non-RESET events: {allowed_events}"


# ── Stage Snapshot Tests ────────────────────────────────────────

class TestStageSnapshot:
    def test_snapshot_immutable(self):
        snap = StageSnapshot(stage_id="enrichment", item_count=100)
        assert snap.stage_id == "enrichment"
        assert snap.item_count == 100
        with pytest.raises(AttributeError):
            snap.item_count = 200  # frozen dataclass

    def test_snapshot_to_dict(self):
        snap = StageSnapshot(stage_id="enrichment", exists=True, item_count=50, total_items=100)
        d = snap.to_dict()
        assert d["stage_id"] == "enrichment"
        assert d["exists"] is True
        assert d["item_count"] == 50
        assert d["total_items"] == 100

    def test_snapshot_extra_fields_merged_into_dict(self):
        snap = StageSnapshot(stage_id="atlas", extra={"mode": "llm", "char_count": 5000})
        d = snap.to_dict()
        assert d["mode"] == "llm"
        assert d["char_count"] == 5000


class TestStageSnapshotOnSM:
    def test_update_creates_snapshot(self):
        sm = make_sm()
        sm.update_stage_snapshot("enrichment", exists=True, item_count=100)
        snap = sm.get_stage_snapshot("enrichment")
        assert snap is not None
        assert snap.exists is True
        assert snap.item_count == 100

    def test_update_preserves_existing_fields(self):
        sm = make_sm()
        sm.update_stage_snapshot("enrichment", exists=True, item_count=100)
        sm.update_stage_snapshot("enrichment", avg_confidence=0.87)
        snap = sm.get_stage_snapshot("enrichment")
        assert snap.item_count == 100  # preserved
        assert snap.avg_confidence == 0.87  # updated

    def test_get_stage_snapshots_returns_copy(self):
        sm = make_sm()
        sm.update_stage_snapshot("enrichment", item_count=50)
        sm.update_stage_snapshot("clustering", item_count=600)
        snaps = sm.get_stage_snapshots()
        assert len(snaps) == 2
        assert "enrichment" in snaps
        assert "clustering" in snaps

    def test_get_stage_snapshot_returns_none_for_unknown(self):
        sm = make_sm()
        assert sm.get_stage_snapshot("nonexistent") is None

    def test_extra_kwargs_go_to_extra_dict(self):
        sm = make_sm()
        sm.update_stage_snapshot("atlas", exists=True, mode="llm", char_count=5000)
        snap = sm.get_stage_snapshot("atlas")
        assert snap.exists is True
        assert snap.extra["mode"] == "llm"
        assert snap.extra["char_count"] == 5000

    def test_progress_fields(self):
        sm = make_sm()
        sm.update_stage_snapshot("catalogue",
            running=True,
            progress_current=150,
            progress_total=500,
            progress_baseline=100,
        )
        snap = sm.get_stage_snapshot("catalogue")
        assert snap.running is True
        assert snap.progress_current == 150
        assert snap.progress_total == 500
        assert snap.progress_baseline == 100

    def test_thread_safe_updates(self):
        """Multiple threads can update snapshots concurrently without errors."""
        sm = make_sm()
        errors = []

        def updater(stage_id, count):
            try:
                for i in range(100):
                    sm.update_stage_snapshot(stage_id, item_count=i)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=updater, args=(f"stage_{i}", i))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        snaps = sm.get_stage_snapshots()
        assert len(snaps) == 5


# ── Finalize group tests ───────────────────────────────────────


def make_finalize_sm():
    return make_sm(
        stages=["atlas", "rules", "concepts", "audit", "antibodies"],
        group="finalize",
    )


class TestFinalizeGroup:
    """Test finalize group state machine behavior."""

    def test_finalize_sm_has_5_stages(self):
        sm = make_finalize_sm()
        assert len(sm.stages) == 5

    def test_finalize_lifecycle(self):
        sm = make_finalize_sm()
        sm.transition(Event.START)
        assert sm.state == PipelineState.RUNNING
        for _ in range(5):
            sm.transition(Event.STAGE_COMPLETED)
        sm.transition(Event.ALL_STAGES_DONE)
        assert sm.state == PipelineState.COMPLETED

    def test_finalize_pause_resume(self):
        sm = make_finalize_sm()
        sm.transition(Event.START)
        sm.transition(Event.PAUSE)
        assert sm.state == PipelineState.PAUSING
        sm.transition(Event.STAGE_FLUSHED)
        assert sm.state == PipelineState.PAUSED
        sm.transition(Event.RESUME)
        assert sm.state == PipelineState.RUNNING

"""Integration tests for Phase 89 atomic pipeline stage transitions.

Verifies that the pipeline always holds at least one scheduler lock
during stage transitions, and that cancel/pause properly release locks.

Note: The scheduler tracks one active stage per project per node
(active_stages is a dict keyed by project_id). A second acquire for the
same project updates the stage value in place rather than adding a second
slot. Tests reflect this design.
"""
import pytest

from codrag.services.pipeline.scheduler import PipelineScheduler
from codrag.services.pipeline.stages import StageId


class TestSchedulerLockLifecycle:
    """Verify scheduler lock is held through transitions."""

    def test_lock_held_during_stage_transition(self):
        """Scheduler lock should remain held when stage advances.

        Simulates the release-after-advance ordering: acquire the new stage
        lock first (which updates active_stages in place), then release.
        Since acquire for the same project updates the slot rather than
        removing it, is_held_by stays True throughout.
        """
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)

        # Simulate stage N: project holds lock for enrichment
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

        # Simulate _advance_pipeline: overwrite with next stage (same slot key)
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        # Project still holds its slot — stage was updated in place
        assert sched.is_held_by("proj-a") is True

        # Simulate release after advancing
        sched.release("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False

    def test_cancel_releases_lock(self):
        """After cancel, project should not hold any scheduler lock."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

        # Simulate cancel: release the lock
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False

    def test_pause_releases_lock(self):
        """After pause, project should not hold any scheduler lock."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is True

        # Simulate pause: release the lock
        sched.release("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-a") is False

    def test_is_held_by_not_confused_by_other_project(self):
        """is_held_by should only check the specific project."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        assert sched.is_held_by("proj-b") is False

    def test_stage_update_counts_as_one_active(self):
        """A project always occupies exactly one slot, even across stage updates.

        The scheduler's active_stages dict is keyed by project_id, so
        acquiring a second stage for the same project updates the entry
        rather than adding a new slot. Current load stays at 1.
        """
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-a", StageId.GROUP_REASONING, "cloud:ep-1")
        status = sched.status()
        node = status["nodes"]["cloud:ep-1"]
        # Stage update overwrites the slot — load stays at 1
        assert node["current_load"] == 1

    def test_two_distinct_projects_count_as_two_active(self):
        """Two different projects each occupy one slot, load == 2."""
        sched = PipelineScheduler()
        sched.configure_node("cloud:ep-1", 10)
        sched.acquire("proj-a", StageId.ENRICHMENT, "cloud:ep-1")
        sched.acquire("proj-b", StageId.GROUP_REASONING, "cloud:ep-1")
        status = sched.status()
        node = status["nodes"]["cloud:ep-1"]
        assert node["current_load"] == 2

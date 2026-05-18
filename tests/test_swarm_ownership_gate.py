"""Phase 136 Part 13 regression — swarm-eligible stages MUST consult
the scheduler before launching a SwarmOrchestrator.

Pre-Phase-136 dogfood evidence (2026-05-18): the Thinking endpoint
hosted three concurrent loads on a single rebuild — Module Synthesis
(4× Swarm on SourcePrep), Group Reasoning (6× swarm on SourcePrep),
and Deep Reasoning on a different project (SkyPath-Restart).  By
design the swarm window reserves the endpoint's capacity for one
stage; two SwarmOrchestrators racing for it defeats the contract.

The root cause: `cluster.py` and `group_reasoning.py` made an
INDEPENDENT decision to launch swarm based only on `(model can
coordinate AND swarm_enabled AND group_count >= threshold)`.  They
never asked whether the scheduler had granted THIS stage the window.

The fix: gate swarm launch on `pipeline_scheduler.is_my_swarm_window(
project_id, stage)`, falling back to non-swarm dispatch otherwise.
"""
from __future__ import annotations

from prep.services.pipeline.scheduler import (
    HoldEntry,
    HoldKey,
    PipelineScheduler,
)
from prep.services.pipeline.stages import StageId


def _scheduler() -> PipelineScheduler:
    """Fresh scheduler instance — avoid singleton state pollution."""
    return PipelineScheduler()


class TestIsMySwarmWindow:
    def test_returns_false_when_no_window_open(self):
        sched = _scheduler()
        assert sched.is_my_swarm_window("proj1", StageId.CLUSTERING) is False

    def test_returns_true_for_owner_project_and_stage(self):
        sched = _scheduler()
        opened = sched.open_swarm_window(
            "proj1", StageId.CLUSTERING, "node1",
        )
        assert opened
        assert sched.is_my_swarm_window("proj1", StageId.CLUSTERING) is True

    def test_returns_false_for_different_project(self):
        sched = _scheduler()
        sched.open_swarm_window("owner", StageId.CLUSTERING, "node1")
        assert sched.is_my_swarm_window("intruder", StageId.CLUSTERING) is False

    def test_returns_false_for_different_stage_same_project(self):
        # Same project, different stage — the stage that owns the
        # window is CLUSTERING; GROUP_REASONING for the same project
        # must NOT think it owns the window.  Without this, the second
        # stage would launch its own SwarmOrchestrator and the two
        # would race for endpoint capacity (the dogfood symptom).
        sched = _scheduler()
        sched.open_swarm_window("proj1", StageId.CLUSTERING, "node1")
        assert sched.is_my_swarm_window("proj1", StageId.GROUP_REASONING) is False

    def test_stage_none_matches_any_stage_for_project(self):
        sched = _scheduler()
        sched.open_swarm_window("proj1", StageId.CLUSTERING, "node1")
        assert sched.is_my_swarm_window("proj1") is True

    def test_accepts_string_stage(self):
        # Defensive: callers might pass `stage.value` rather than the enum.
        sched = _scheduler()
        sched.open_swarm_window("proj1", StageId.CLUSTERING, "node1")
        assert sched.is_my_swarm_window("proj1", "clustering") is True


class TestArrivalHoldOnSwarmActive:
    """Gap #2: a project that arrives AFTER the swarm window opened
    must also be soft-held on the endpoint, not only the projects that
    were active at open time.  Without this, a worker that bypasses the
    stage-level acquire (e.g. via `acquire_request` for in-flight LLM
    calls) could dispatch against the held endpoint."""

    def test_arrival_during_swarm_stamps_soft_hold(self):
        sched = _scheduler()
        # Open swarm for owner project on node1 — no other project
        # is currently active, so drain_targets is empty.
        sched.open_swarm_window("owner", StageId.CLUSTERING, "node1")
        # An intruder project arrives and tries to acquire on the
        # held endpoint.
        acquired = sched.acquire("intruder", StageId.GROUP_REASONING, "node1")
        assert acquired is False, "swarm gate must block cross-project acquire"
        # And critically, the arrival must now appear in the holds map
        # so any worker that polls `is_held` will pause.
        assert sched.is_held("intruder", "node1") is True, (
            "Phase 136 Part 13 Gap #2: arrival-during-swarm must stamp "
            "a soft-hold on the (intruder, endpoint) pair"
        )

    def test_owner_acquire_does_not_self_hold(self):
        sched = _scheduler()
        sched.open_swarm_window("owner", StageId.CLUSTERING, "node1")
        # The owner project re-acquiring its own slot is fine — it
        # owns the window.
        ok = sched.acquire("owner", StageId.CLUSTERING, "node1")
        assert ok is True
        assert sched.is_held("owner", "node1") is False

    def test_no_hold_stamped_when_no_window_active(self):
        sched = _scheduler()
        # No swarm window — acquire must NOT stamp a hold even when
        # the slot is otherwise full.
        sched.acquire("a", StageId.CLUSTERING, "node1")
        sched.acquire("b", StageId.GROUP_REASONING, "node1")
        # Neither project is held.
        assert sched.is_held("a", "node1") is False
        assert sched.is_held("b", "node1") is False

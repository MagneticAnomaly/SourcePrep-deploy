"""Phase 127 sub-phase 4: API surfaces held/queue state."""
from __future__ import annotations


def test_running_task_includes_held_fields() -> None:
    """When a project is held, list_holds reports it correctly."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.set_hold(
        "proj-held-test", "cloud:default_ollama",
        reason="exclusive", set_by_project="proj-other",
    )
    try:
        holds = pipeline_scheduler.list_holds()
        found = [h for h in holds if h["project_id"] == "proj-held-test"]
        assert len(found) == 1
        assert found[0]["reason"] == "exclusive"
        assert found[0]["set_by_project"] == "proj-other"
    finally:
        pipeline_scheduler.clear_hold("proj-held-test", "cloud:default_ollama")


def test_running_task_state_helper() -> None:
    """The state classification helper returns the right buckets."""
    from prep.api.routers.llm import _running_task_state
    assert _running_task_state(
        project_id="proj-X",
        is_held=True,
        held_reason="exclusive",
        is_swarm=False,
    ) == "held"
    assert _running_task_state(
        project_id="proj-X",
        is_held=False,
        held_reason=None,
        is_swarm=True,
    ) == "swarm_active"
    assert _running_task_state(
        project_id="proj-X",
        is_held=False,
        held_reason=None,
        is_swarm=False,
    ) == "running"

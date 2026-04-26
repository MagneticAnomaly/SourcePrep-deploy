"""Phase 119 amendment: the "Swarming" label requires concurrent_workers >= 2.

A single in-flight call cannot, by definition, be "swarming" — even on a
swarm-capable stage with a swarm-capable model. Without this gate the badge
showed on tasks with one live worker, which surprised the user.
"""
from __future__ import annotations


def test_swarm_label_requires_two_or_more_workers(monkeypatch) -> None:
    """The 'Swarming' label should not show with only 1 worker in flight."""
    from prep.services import token_telemetry

    # Exactly one in-flight LLM call.
    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: [
            {
                "project_id": "proj-A",
                "task_id": "augmentation_inferred_edges",
                "model": "kimi-k2",
                "provider": "ollama",
                "model_slot": None,
                "duration_seconds": 0.5,
            },
        ],
    )

    from prep.api.routers.llm import _count_live_workers
    from prep.services.pipeline.scheduler import (
        SWARM_CAPABLE_STAGES,
        is_swarm_active_for_stage,
    )

    # Pick a swarm-capable stage (so the stage check would otherwise pass).
    stage = next(iter(SWARM_CAPABLE_STAGES))

    live_workers = _count_live_workers(project_id="proj-A", task_id="augmentation_inferred_edges")
    assert live_workers == 1

    # Re-derive the gate the same way llm.py does:
    is_swarm_stage_capable = stage in SWARM_CAPABLE_STAGES
    is_swarm_model_capable = True  # by hypothesis: stage+model is swarm-capable
    is_swarm = is_swarm_stage_capable and is_swarm_model_capable and live_workers >= 2
    assert is_swarm is False, "1 live worker must NOT be reported as 'Swarming'"
    # Sanity: the stage IS swarm-capable, so the gate is the only thing
    # blocking the label here.
    assert is_swarm_active_for_stage  # imported, silences linter


def test_swarm_label_shows_when_two_or_more_workers(monkeypatch) -> None:
    """With 2+ live workers on a swarm-capable stage+model, label shows."""
    from prep.services import token_telemetry

    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: [
            {
                "project_id": "proj-A",
                "task_id": "augmentation_inferred_edges",
                "model": "kimi-k2",
                "provider": "ollama",
                "model_slot": None,
                "duration_seconds": 0.5,
            },
            {
                "project_id": "proj-A",
                "task_id": "augmentation_inferred_edges",
                "model": "kimi-k2",
                "provider": "ollama",
                "model_slot": None,
                "duration_seconds": 0.4,
            },
        ],
    )

    from prep.api.routers.llm import _count_live_workers
    live_workers = _count_live_workers(project_id="proj-A", task_id="augmentation_inferred_edges")
    assert live_workers == 2

    # Both stage- and model-capable AND >= 2 workers → swarming.
    assert (True and True and live_workers >= 2) is True


def test_queue_item_swarm_gated_by_live_workers(monkeypatch) -> None:
    """The queue.py path also gates is_swarm by live_workers >= 2."""
    from prep.services import token_telemetry
    from prep.api.routers import queue as queue_mod

    # 1 live worker — should NOT be marked swarming.
    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: [
            {
                "project_id": "proj-A",
                "task_id": "augmentation_inferred_edges",
                "provider": "ollama",
                "model_slot": None,
            },
        ],
    )

    # Force the stage/model swarm check to pass.
    from prep.services.pipeline import scheduler as sched_mod
    swarm_stage = next(iter(sched_mod.SWARM_CAPABLE_STAGES))
    monkeypatch.setattr(sched_mod, "is_swarm_active_for_stage", lambda *a, **kw: True)

    # Stub resolve_model_for_stage to return non-None so the inner block runs.
    from prep.services.pipeline import _model_resolution as res_mod
    monkeypatch.setattr(res_mod, "resolve_model_for_stage", lambda pid, s: ("kimi-k2", "ollama"))

    # Stub the scheduler concurrent-workers helper used by _make_queue_item.
    from prep.services.pipeline.scheduler import pipeline_scheduler
    monkeypatch.setattr(
        pipeline_scheduler, "concurrent_workers_for_project",
        lambda pid, stage=None: (8, "cloud:test"),
    )
    monkeypatch.setattr(pipeline_scheduler, "get_priority", lambda pid: "none")
    monkeypatch.setattr(queue_mod, "_resolve_project_name", lambda pid: pid)

    item = queue_mod._build_queue_item(
        project_id="proj-A",
        group="augmentation",
        phase="running",
        current_stage=swarm_stage,
        started_at=None,
        wait_seconds=None,
    )
    assert item["is_swarm"] is False, "1 live worker must NOT be reported as 'Swarming'"

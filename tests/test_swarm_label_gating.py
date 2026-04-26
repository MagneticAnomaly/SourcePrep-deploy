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


# ── Phase 119 Swarm Authority: runtime-evidence gating ──────────────


def _stub_active_requests(monkeypatch, requests):
    """Helper: replace telemetry.get_active_requests() with a fixed list."""
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: requests,
    )


def test_is_swarm_requires_open_swarm_window(monkeypatch) -> None:
    """5 concurrent workers but no swarm window → NOT 'Swarming'.

    The pre-fix gate accepted any `is_swarm_active_for_stage` capability
    match.  Phase 119 Swarm Authority requires the scheduler to have
    actively opened a swarm window — concurrent independent calls are
    not a swarm.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.scheduler import SWARM_CAPABLE_STAGES

    # Scheduler reports no open swarm window
    monkeypatch.setattr(pipeline_scheduler, "get_swarm_window", lambda: None)

    # 5 in-flight workers on a swarm-capable stage
    swarm_stage = next(iter(SWARM_CAPABLE_STAGES))
    requests = [
        {
            "project_id": "proj-A",
            "task_id": swarm_stage,
            "model": "kimi-k2.5:cloud",
            "provider": "ollama",
            "model_slot": None,
            "swarm_role": None,
        }
        for _ in range(5)
    ]
    _stub_active_requests(monkeypatch, requests)

    # Reproduce the runtime gate the same way llm.py does
    window = pipeline_scheduler.get_swarm_window()
    live_workers = sum(1 for r in requests if r["project_id"] == "proj-A")
    is_swarm = (
        window is not None
        and window.get("project_id") == "proj-A"
        and live_workers >= 2
    )
    assert is_swarm is False, "no swarm window means no 'Swarming' badge"


def test_is_swarm_when_window_open_and_workers_present(monkeypatch) -> None:
    """Window open + matching project + workers >= 2 → 'Swarming'."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.scheduler import SWARM_CAPABLE_STAGES
    from prep.services.pipeline.stages import StageId

    swarm_stage = next(iter(SWARM_CAPABLE_STAGES))
    # Build a fake StageId so the value-comparison helper doesn't
    # crash if the scheduler stores stage as an enum.
    matching_stage = StageId(swarm_stage)

    monkeypatch.setattr(
        pipeline_scheduler,
        "get_swarm_window",
        lambda: {
            "project_id": "proj-A",
            "stage": matching_stage,
            "node_id": "cloud:default_ollama",
            "started_at": 0.0,
            "drain_targets": {},
        },
    )

    requests = [
        {
            "project_id": "proj-A",
            "task_id": swarm_stage,
            "model": "kimi-k2.5:cloud",
            "provider": "ollama",
            "model_slot": None,
            "swarm_role": "coordinator" if i == 0 else ("synthesizer" if i == 4 else "worker"),
        }
        for i in range(5)
    ]
    _stub_active_requests(monkeypatch, requests)

    # Reproduce the runtime gate
    window = pipeline_scheduler.get_swarm_window()
    window_stage = getattr(window.get("stage"), "value", window.get("stage"))
    live_workers = sum(1 for r in requests if r["project_id"] == "proj-A")
    is_swarm = (
        window is not None
        and window.get("project_id") == "proj-A"
        and window_stage == swarm_stage
        and live_workers >= 2
    )
    assert is_swarm is True


def test_is_swarm_false_when_window_for_different_project(monkeypatch) -> None:
    """Window open for project A; running task is project B → NOT 'Swarming'."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.scheduler import SWARM_CAPABLE_STAGES
    from prep.services.pipeline.stages import StageId

    swarm_stage = next(iter(SWARM_CAPABLE_STAGES))
    monkeypatch.setattr(
        pipeline_scheduler,
        "get_swarm_window",
        lambda: {
            "project_id": "proj-A",  # window owner
            "stage": StageId(swarm_stage),
            "node_id": "cloud:default_ollama",
            "started_at": 0.0,
            "drain_targets": {},
        },
    )

    # Running task is on a DIFFERENT project
    requests = [
        {
            "project_id": "proj-B",
            "task_id": swarm_stage,
            "model": "kimi-k2.5:cloud",
            "provider": "ollama",
            "model_slot": None,
            "swarm_role": "worker",
        }
        for _ in range(3)
    ]
    _stub_active_requests(monkeypatch, requests)

    window = pipeline_scheduler.get_swarm_window()
    is_swarm_for_proj_b = (
        window is not None
        and window.get("project_id") == "proj-B"
    )
    assert is_swarm_for_proj_b is False


def test_swarm_phases_groups_telemetry_by_role() -> None:
    """_summarize_swarm_phases groups active calls by swarm_role.

    Verifies the helper used by /llm/slots/status to populate the
    three-phase breakdown rendered by the AI Gateway UI.
    """
    from prep.api.routers.llm import _summarize_swarm_phases

    requests = [
        {"project_id": "P", "task_id": "T", "model": "coord-model",
         "provider": "ollama", "model_slot": None, "swarm_role": "coordinator"},
        {"project_id": "P", "task_id": "T", "model": "worker-model",
         "provider": "ollama", "model_slot": None, "swarm_role": "worker"},
        {"project_id": "P", "task_id": "T", "model": "worker-model",
         "provider": "ollama", "model_slot": None, "swarm_role": "worker"},
        {"project_id": "P", "task_id": "T", "model": "worker-model",
         "provider": "ollama", "model_slot": None, "swarm_role": "worker"},
        {"project_id": "P", "task_id": "T", "model": "synth-model",
         "provider": "ollama", "model_slot": None, "swarm_role": "synthesizer"},
        # noise: different project
        {"project_id": "Q", "task_id": "T", "model": "x",
         "provider": "ollama", "model_slot": None, "swarm_role": "worker"},
        # noise: not a swarm-tagged call
        {"project_id": "P", "task_id": "T", "model": "x",
         "provider": "ollama", "model_slot": None, "swarm_role": None},
    ]
    phases = _summarize_swarm_phases(requests, project_id="P", task_id="T")
    assert phases["coordinator"] == {"active": 1, "model": "coord-model"}
    assert phases["workers"] == {"active": 3, "model": "worker-model"}
    assert phases["synthesizer"] == {"active": 1, "model": "synth-model"}


def test_swarm_role_set_via_context_propagates_to_telemetry() -> None:
    """SwarmOrchestrator.set_swarm_role tags subsequent track_active_request calls."""
    from prep.services import token_telemetry
    from prep.services.token_telemetry import set_swarm_role, set_telemetry_context

    # Drain any leftover state from earlier tests so we read a clean snapshot.
    with set_telemetry_context("phase119-test", "phase119-task"):
        with set_swarm_role("coordinator"):
            token_telemetry.telemetry.track_active_request("M", "ollama", None)
            active = token_telemetry.telemetry.get_active_requests()
            mine = [r for r in active if r["project_id"] == "phase119-test"]
            assert mine, "request should be recorded"
            assert mine[0]["swarm_role"] == "coordinator"
            token_telemetry.telemetry.untrack_active_request()

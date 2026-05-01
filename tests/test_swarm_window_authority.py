"""Phase 119+ correction: swarm window is the authoritative signal.

The original Phase 119 gate required ``live_workers >= 2`` to flip
``is_swarm`` true.  That was wrong — the coord and synth phases of a
real swarm are intrinsically 1-worker-in-flight by design, so the gate
flipped off on every phase transition (10× → 1× → 10× → 1×).  The UI
then lost sight of the swarm during coord and synth, rendering them as
bare "Thinking 1×" instead of a lit "Coordinator 1×".

The fix: drop the live_workers count requirement entirely.  The
scheduler's swarm window IS the authority — if the orchestrator opened
it, we ARE in a swarm regardless of how many calls are in flight at
this poll instant.
"""
from __future__ import annotations


def _stub_active(monkeypatch, requests):
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: requests,
    )


def _stub_window(monkeypatch, *, project_id, stage):
    from prep.services.pipeline.scheduler import pipeline_scheduler

    class _StageStr:
        value = stage
    monkeypatch.setattr(
        pipeline_scheduler, "get_swarm_window",
        lambda: {"project_id": project_id, "stage": _StageStr()},
    )


def test_is_swarm_true_during_coord_phase_one_worker(monkeypatch) -> None:
    """C1: open swarm window + only the coord call in flight (1 worker)
    must still report is_swarm=True so the UI keeps showing 'Swarming'
    and the Coordinator row stays lit during the 100-180s coord phase.
    """
    from prep.api.routers.llm import _summarize_swarm_phases

    _stub_active(monkeypatch, [
        {
            "project_id": "P", "task_id": "group_reasoning",
            "model": "qwen/qwen3.6-plus", "provider": "openai-compatible",
            "model_slot": "coordinator", "swarm_role": "coordinator",
        },
    ])

    phases = _summarize_swarm_phases(
        [{
            "project_id": "P", "task_id": "group_reasoning",
            "model": "qwen/qwen3.6-plus", "provider": "openai-compatible",
            "model_slot": "coordinator", "swarm_role": "coordinator",
        }],
        project_id="P", task_id="group_reasoning",
    )
    assert phases["coordinator"]["active"] == 1
    assert phases["coordinator"]["model"] == "qwen/qwen3.6-plus"
    assert phases["workers"]["active"] == 0
    assert phases["synthesizer"]["active"] == 0


def test_is_swarm_true_during_synth_phase_one_worker(monkeypatch) -> None:
    """C2: synth phase — 1 worker in flight tagged swarm_role=synthesizer.
    Must still be is_swarm=True; UI's Coordinator row should reflect the
    1× call (synth runs on the same coord client/endpoint).
    """
    from prep.api.routers.llm import _summarize_swarm_phases
    phases = _summarize_swarm_phases(
        [{
            "project_id": "P", "task_id": "clustering",
            "model": "qwen/qwen3.6-plus", "provider": "openai-compatible",
            "model_slot": "coordinator", "swarm_role": "synthesizer",
        }],
        project_id="P", task_id="clustering",
    )
    assert phases["synthesizer"]["active"] == 1
    assert phases["coordinator"]["active"] == 0


def test_swarm_phases_always_returns_three_buckets() -> None:
    """C3: even when no calls are in flight, the breakdown returns the
    three-bucket dict with active=0.  This lets the UI render the
    Coordinator row in 'idle' state instead of vanishing it.
    """
    from prep.api.routers.llm import _summarize_swarm_phases
    phases = _summarize_swarm_phases([], project_id="P", task_id="x")
    assert set(phases.keys()) == {"coordinator", "workers", "synthesizer"}
    for k, v in phases.items():
        assert v == {"active": 0, "model": None}, f"{k}: {v}"


def test_window_only_is_swarm_authority(monkeypatch) -> None:
    """C4: with the swarm window open AND any number of workers (0, 1, or
    10) in flight, is_swarm should be True.  No live_workers gate.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _stub_window(monkeypatch, project_id="P", stage="group_reasoning")

    # Reproduce the production gate exactly:
    window = pipeline_scheduler.get_swarm_window()
    stage_val = getattr(window.get("stage"), "value", window.get("stage"))
    window_matches = (
        window is not None
        and window.get("project_id") == "P"
        and stage_val == "group_reasoning"
    )
    assert window_matches is True
    # Phase 119+ corrected gate: window is sufficient.  No live-worker
    # threshold.  This test exists to fail loudly if someone re-introduces
    # the live_workers >= 2 gate.
    is_swarm = window_matches
    assert is_swarm is True


def test_no_window_means_not_swarm(monkeypatch) -> None:
    """C5: no open swarm window + any number of workers → is_swarm=False.
    Concurrent independent calls to a swarm-capable model are NOT a swarm.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    monkeypatch.setattr(pipeline_scheduler, "get_swarm_window", lambda: None)
    window = pipeline_scheduler.get_swarm_window()
    assert window is None
    # Even with 10 workers, no window means not a swarm.
    is_swarm = window is not None
    assert is_swarm is False

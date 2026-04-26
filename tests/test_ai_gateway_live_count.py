"""Phase 82 completion: the AI Gateway UI displays LIVE in-flight
API call count, not the scheduler's configured maximum.

The filter is ``(project_id, task_id)`` — ``model_slot`` is intentionally
NOT part of the composite key. ``LLMClient._model_slot`` is not reliably
set anywhere in the codebase, so telemetry entries carry
``model_slot=None``; filtering on it would always return 0.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_running_tasks_use_live_telemetry_count(monkeypatch) -> None:
    """When 3 LLM requests are in-flight for a project + task_id,
    the running_tasks list should report concurrent_workers=3."""
    from prep.services import token_telemetry

    fake_requests = [
        {"project_id": "proj-A", "task_id": "inferred_edges", "model": "qwen3-coder",
         "provider": "ollama", "model_slot": None, "duration_seconds": 1.2},
        {"project_id": "proj-A", "task_id": "inferred_edges", "model": "qwen3-coder",
         "provider": "ollama", "model_slot": None, "duration_seconds": 0.8},
        {"project_id": "proj-A", "task_id": "inferred_edges", "model": "qwen3-coder",
         "provider": "ollama", "model_slot": None, "duration_seconds": 0.3},
    ]
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests", lambda: list(fake_requests),
    )

    from prep.api.routers.llm import _count_live_workers

    count = _count_live_workers(project_id="proj-A", task_id="inferred_edges")
    assert count == 3


def test_running_tasks_live_count_zero_when_nothing_inflight(monkeypatch) -> None:
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests", lambda: [],
    )
    from prep.api.routers.llm import _count_live_workers
    assert _count_live_workers(project_id="proj-A", task_id="inferred_edges") == 0


def test_agent_task_workers_reflect_live_count(monkeypatch) -> None:
    """Previously hardcoded to 1; now from telemetry count."""
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests",
        lambda: [
            {"project_id": "proj-A", "task_id": "agent_call", "model": "gemini-2.5-flash",
             "provider": "gemini", "model_slot": None, "duration_seconds": 0.1},
            {"project_id": "proj-A", "task_id": "agent_call", "model": "gemini-2.5-flash",
             "provider": "gemini", "model_slot": None, "duration_seconds": 0.2},
        ],
    )
    from prep.api.routers.llm import _count_live_workers
    assert _count_live_workers(project_id="proj-A", task_id="agent_call") == 2


def test_count_ignores_model_slot_value(monkeypatch) -> None:
    """Filter matches on (project_id, task_id) only. Model_slot may be
    anything (None, empty, mismatched label) and the count still works."""
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests",
        lambda: [
            {"project_id": "proj-A", "task_id": "concepts",
             "model": "x", "provider": "ollama", "model_slot": None,
             "duration_seconds": 0.1},
            {"project_id": "proj-A", "task_id": "concepts",
             "model": "x", "provider": "ollama", "model_slot": "large_model",
             "duration_seconds": 0.1},
            {"project_id": "proj-A", "task_id": "concepts",
             "model": "x", "provider": "ollama", "model_slot": "small",
             "duration_seconds": 0.1},
        ],
    )
    from prep.api.routers.llm import _count_live_workers
    assert _count_live_workers(project_id="proj-A", task_id="concepts") == 3


def test_count_filters_by_project(monkeypatch) -> None:
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests",
        lambda: [
            {"project_id": "proj-A", "task_id": "t1", "model": "x",
             "provider": "p", "model_slot": None, "duration_seconds": 0.1},
            {"project_id": "proj-B", "task_id": "t1", "model": "x",
             "provider": "p", "model_slot": None, "duration_seconds": 0.1},
        ],
    )
    from prep.api.routers.llm import _count_live_workers
    assert _count_live_workers(project_id="proj-A", task_id="t1") == 1


def test_count_empty_task_id_matches_all_in_project(monkeypatch) -> None:
    """When task_id='' the filter is optional — all requests for the
    project count."""
    from prep.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests",
        lambda: [
            {"project_id": "proj-A", "task_id": "t1", "model": "x",
             "provider": "p", "model_slot": None, "duration_seconds": 0.1},
            {"project_id": "proj-A", "task_id": "t2", "model": "x",
             "provider": "p", "model_slot": None, "duration_seconds": 0.1},
        ],
    )
    from prep.api.routers.llm import _count_live_workers
    assert _count_live_workers(project_id="proj-A", task_id="") == 2


def test_real_llmclient_registers_in_telemetry_for_live_count() -> None:
    """Integration: exercise the real LLMClient -> telemetry -> count chain.

    Full import-chain test required by project convention
    (feedback_test_full_import_chain.md). The critical seam — the
    LLMClient -> token_telemetry bridge — is NOT mocked. Only the
    innermost HTTP-doing method is stubbed.

    Regression target: C1 — the _count_live_workers model_slot filter
    defeated live counting because LLMClient never writes _model_slot
    on itself. With the filter relaxed to (project_id, task_id), this
    test passes.
    """
    from prep.core.llm_client import LLMClient
    from prep.services import token_telemetry
    from prep.services.token_telemetry import set_telemetry_context
    from prep.api.routers.llm import _count_live_workers

    # Reset telemetry so the test is hermetic.
    token_telemetry._active_requests.clear()

    client = LLMClient(
        endpoint_url="http://localhost:11434",
        model="qwen3-coder:30b-cloud",
        provider="ollama",
    )

    captured = {"inflight": -1}

    def fake_internal(*args, **kwargs):
        # While we're inside the fake HTTP call, telemetry should show
        # one in-flight request for this project/task.
        captured["inflight"] = _count_live_workers(
            project_id="proj-test", task_id="concepts",
        )
        return ("ok", 1)

    with set_telemetry_context(project_id="proj-test", task_id="concepts"):
        with patch.object(LLMClient, "_generate_internal", new=fake_internal):
            client.generate("hi", json_mode=False)

    assert captured["inflight"] >= 1, (
        "LLMClient did not register in telemetry, or _count_live_workers "
        "failed to count it. C1 regression: filter defeated live counting."
    )
    # After the call, the telemetry entry should be untracked.
    assert _count_live_workers(project_id="proj-test", task_id="concepts") == 0


def test_gate_blocked_threads_are_not_counted_as_active() -> None:
    """Threads waiting at the AIMD request gate must NOT count as 'active'.

    Regression: pre-fix, _track_active('start') ran before acquire_request_ctx,
    so N threads blocked in the condition-variable wait were all counted as
    in-flight. With AIMD dynamic_capacity=1 and 4 concurrent calls, only 1
    LLM call is actually talking to the provider; the other 3 are queued.
    The fix moves tracking inside the gate. This test proves the new ordering.
    """
    import threading

    from prep.core.llm_client import LLMClient
    from prep.services import token_telemetry
    from prep.services.pipeline.scheduler import ComputeSlot, pipeline_scheduler
    from prep.services.token_telemetry import set_telemetry_context
    from prep.api.routers.llm import _count_live_workers

    node_id = "cloud:gate_test"
    # Reset telemetry and register a tiny cloud slot with capacity 1.
    token_telemetry._active_requests.clear()
    with pipeline_scheduler._lock:
        pipeline_scheduler._slots[node_id] = ComputeSlot(
            node_id=node_id,
            max_concurrent=1,
            current_limit=1,
            min_limit=1,
        )

    try:
        enter = threading.Event()
        release = threading.Event()
        readings: list[int] = []

        def fake_internal(*args, **kwargs):
            enter.set()
            release.wait(timeout=5.0)
            return ("ok", 1)

        def resolve_fixed_node(self):
            return node_id

        def one_call():
            client = LLMClient(
                endpoint_url="http://localhost:11434",
                model="x:cloud",
                provider="ollama",
            )
            with set_telemetry_context(project_id="p", task_id="t"):
                client.generate("hi", json_mode=False)

        with patch.object(LLMClient, "_generate_internal", new=fake_internal), \
                patch.object(LLMClient, "_resolve_scheduler_node_id", new=resolve_fixed_node):
            threads = [threading.Thread(target=one_call, daemon=True) for _ in range(4)]
            for t in threads:
                t.start()

            enter.wait(timeout=5.0)
            # First call is inside _generate_internal; the other 3 are blocked
            # at pipeline_scheduler.acquire_request waiting for capacity.
            readings.append(_count_live_workers(project_id="p", task_id="t"))

            release.set()
            for t in threads:
                t.join(timeout=5.0)

        # Only the 1 thread actually making the HTTP call should be counted.
        # Pre-fix this was 4 — all threads including the 3 blocked at the gate.
        assert readings[0] == 1, (
            f"Gate-blocked threads leaked into the active count: {readings[0]} "
            "expected 1 (pre-fix: 4). Tracking must happen AFTER the gate."
        )
        # All calls should have completed and cleaned up.
        assert _count_live_workers(project_id="p", task_id="t") == 0
    finally:
        with pipeline_scheduler._lock:
            pipeline_scheduler._slots.pop(node_id, None)

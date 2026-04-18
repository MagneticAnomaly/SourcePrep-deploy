"""Phase 82 completion: the AI Gateway UI displays LIVE in-flight
API call count, not the scheduler's configured maximum.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_running_tasks_use_live_telemetry_count(monkeypatch) -> None:
    """When 3 LLM requests are in-flight for a project + model_slot,
    the running_tasks list should report concurrent_workers=3, not
    the scheduler's max."""
    from codrag.services import token_telemetry

    fake_requests = [
        {"project_id": "proj-A", "task_id": "inferred_edges", "model": "qwen3-coder",
         "provider": "ollama", "model_slot": "large_model", "duration_seconds": 1.2},
        {"project_id": "proj-A", "task_id": "inferred_edges", "model": "qwen3-coder",
         "provider": "ollama", "model_slot": "large_model", "duration_seconds": 0.8},
        {"project_id": "proj-A", "task_id": "inferred_edges", "model": "qwen3-coder",
         "provider": "ollama", "model_slot": "large_model", "duration_seconds": 0.3},
    ]
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests", lambda: list(fake_requests),
    )

    from codrag.api.routers.llm import _count_live_workers

    count = _count_live_workers(
        project_id="proj-A", task_id="inferred_edges", model_slot="large_model",
    )
    assert count == 3


def test_running_tasks_live_count_zero_when_nothing_inflight(monkeypatch) -> None:
    from codrag.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests", lambda: [],
    )
    from codrag.api.routers.llm import _count_live_workers
    assert _count_live_workers(
        project_id="proj-A", task_id="inferred_edges", model_slot="large_model",
    ) == 0


def test_agent_task_workers_reflect_live_count(monkeypatch) -> None:
    """Previously hardcoded to 1; now from telemetry count."""
    from codrag.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests",
        lambda: [
            {"project_id": "proj-A", "task_id": "agent_call", "model": "gemini-2.5-flash",
             "provider": "gemini", "model_slot": "large_model", "duration_seconds": 0.1},
            {"project_id": "proj-A", "task_id": "agent_call", "model": "gemini-2.5-flash",
             "provider": "gemini", "model_slot": "large_model", "duration_seconds": 0.2},
        ],
    )
    from codrag.api.routers.llm import _count_live_workers
    assert _count_live_workers(
        project_id="proj-A", task_id="agent_call", model_slot="large_model",
    ) == 2

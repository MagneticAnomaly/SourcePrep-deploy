"""
Tests for the Queue API Router — Phase 75 Task 2.

Tests endpoint functions directly with mocked dependencies.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers to build mock objects
# ---------------------------------------------------------------------------


def _mock_state_machine(
    project_id: str,
    group: str,
    state_value: str = "running",
    current_stage: str | None = "catalogue",
    started_at: float | None = None,
) -> MagicMock:
    sm = MagicMock()
    sm.project_id = project_id
    sm.group = group
    sm.state = MagicMock()
    sm.state.value = state_value
    sm.current_stage = current_stage
    sm.started_at = started_at or time.time() - 142.5
    return sm


def _mock_scheduler_status(active: dict | None = None, queued: list | None = None) -> dict:
    """Build a scheduler status dict with one default node."""
    return {
        "nodes": {
            "local:default_ollama": {
                "max_concurrent": 1,
                "current_load": 1 if active else 0,
                "active": active or {},
                "queued": queued or [],
            },
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }


# ---------------------------------------------------------------------------
# Test: running pipeline returns correct queue item
# ---------------------------------------------------------------------------


@patch("codrag.api.routers.queue._resolve_project_name", return_value="DebateHaus")
@patch("codrag.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("codrag.api.routers.queue.pipeline_scheduler")
@patch("codrag.api.routers.queue.pipeline_orchestrator")
def test_running_pipeline_in_queue(
    mock_orch, mock_sched, mock_purge, mock_name,
):
    from codrag.api.routers.queue import get_queue

    pid = "uuid-1234"
    sm = _mock_state_machine(pid, "fast_sync", "running", "catalogue")

    mock_orch._runs = {(pid, "fast_sync"): sm}

    mock_sched.status.return_value = _mock_scheduler_status(
        active={pid: "catalogue"},
    )
    mock_sched.get_priority.return_value = "none"
    mock_sched.concurrent_workers_for_project.return_value = (3, "local:default_ollama")

    result = get_queue()

    assert result["success"] is True
    data = result["data"]
    assert len(data["queue"]) == 1

    item = data["queue"][0]
    assert item["project_id"] == pid
    assert item["project_name"] == "DebateHaus"
    assert item["group"] == "fast_sync"
    assert item["phase"] == "running"
    assert item["current_stage"] == "catalogue"
    assert item["priority"] == "none"
    assert item["concurrent_workers"] == 3
    assert item["compute_node"] == "local:default_ollama"
    assert item["elapsed_seconds"] is not None
    assert data["ghost_locks_purged"] == 0

    mock_purge.assert_called_once()


# ---------------------------------------------------------------------------
# Test: queued entries from scheduler are included
# ---------------------------------------------------------------------------


@patch("codrag.api.routers.queue._resolve_project_name", return_value="TestProject")
@patch("codrag.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("codrag.api.routers.queue.pipeline_scheduler")
@patch("codrag.api.routers.queue.pipeline_orchestrator")
def test_queued_entries_included(
    mock_orch, mock_sched, mock_purge, mock_name,
):
    from codrag.api.routers.queue import get_queue

    pid = "uuid-queued"
    mock_orch._runs = {}  # no active state machines

    mock_sched.status.return_value = _mock_scheduler_status(
        queued=[
            {
                "project_id": pid,
                "stage": "catalogue",
                "waiting_seconds": 30.5,
            }
        ],
    )
    mock_sched.get_priority.return_value = "boost"
    mock_sched.concurrent_workers_for_project.return_value = (1, None)

    result = get_queue()
    data = result["data"]

    # The queued entry should appear
    assert len(data["queue"]) == 1
    item = data["queue"][0]
    assert item["project_id"] == pid
    assert item["phase"] == "queued"
    assert item["wait_seconds"] == 30.5
    assert item["priority"] == "boost"


# ---------------------------------------------------------------------------
# Test: empty state returns empty queue
# ---------------------------------------------------------------------------


@patch("codrag.api.routers.queue._resolve_project_name", return_value="X")
@patch("codrag.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("codrag.api.routers.queue.pipeline_scheduler")
@patch("codrag.api.routers.queue.pipeline_orchestrator")
def test_empty_state_empty_queue(
    mock_orch, mock_sched, mock_purge, mock_name,
):
    from codrag.api.routers.queue import get_queue

    mock_orch._runs = {}
    mock_sched.status.return_value = _mock_scheduler_status()

    result = get_queue()
    data = result["data"]
    assert data["queue"] == []
    assert data["ghost_locks_purged"] == 0


# ---------------------------------------------------------------------------
# Test: priority endpoint delegates to scheduler
# ---------------------------------------------------------------------------


@patch("codrag.api.routers.queue.get_event_bus")
@patch("codrag.api.routers.queue.pipeline_scheduler")
def test_set_priority_delegates(mock_sched, mock_bus):
    from codrag.api.routers.queue import PriorityRequest, set_priority

    req = PriorityRequest(project_id="uuid-1234", level="boost")
    result = set_priority(req)

    assert result["success"] is True
    mock_sched.set_priority.assert_called_once_with("uuid-1234", "boost")
    mock_bus().emit.assert_called_once()


# ---------------------------------------------------------------------------
# Test: ordering — running before queued before failed
# ---------------------------------------------------------------------------


@patch("codrag.api.routers.queue._resolve_project_name", return_value="P")
@patch("codrag.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("codrag.api.routers.queue.pipeline_scheduler")
@patch("codrag.api.routers.queue.pipeline_orchestrator")
def test_ordering_running_before_failed(
    mock_orch, mock_sched, mock_purge, mock_name,
):
    from codrag.api.routers.queue import get_queue

    sm_running = _mock_state_machine("p1", "fast_sync", "running", "catalogue")
    sm_failed = _mock_state_machine("p2", "fast_sync", "failed", None)

    mock_orch._runs = {
        ("p2", "fast_sync"): sm_failed,
        ("p1", "fast_sync"): sm_running,
    }
    mock_sched.status.return_value = _mock_scheduler_status()
    mock_sched.get_priority.return_value = "none"
    mock_sched.concurrent_workers_for_project.return_value = (1, None)

    result = get_queue()
    items = result["data"]["queue"]
    assert len(items) == 2
    assert items[0]["phase"] == "running"
    assert items[1]["phase"] == "failed"


# ---------------------------------------------------------------------------
# Test: completed/idle runs are excluded
# ---------------------------------------------------------------------------


@patch("codrag.api.routers.queue._resolve_project_name", return_value="P")
@patch("codrag.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("codrag.api.routers.queue.pipeline_scheduler")
@patch("codrag.api.routers.queue.pipeline_orchestrator")
def test_completed_excluded(
    mock_orch, mock_sched, mock_purge, mock_name,
):
    from codrag.api.routers.queue import get_queue

    sm_done = _mock_state_machine("p1", "fast_sync", "completed", None)
    sm_idle = _mock_state_machine("p2", "deep_enrichment", "idle", None)

    mock_orch._runs = {
        ("p1", "fast_sync"): sm_done,
        ("p2", "deep_enrichment"): sm_idle,
    }
    mock_sched.status.return_value = _mock_scheduler_status()

    result = get_queue()
    assert result["data"]["queue"] == []

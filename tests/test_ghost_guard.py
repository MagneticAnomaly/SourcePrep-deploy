"""Tests for the ghost lock cross-check guard."""
import pytest
from unittest.mock import MagicMock, patch


def test_purge_ghost_locks_cleans_orphaned_lock():
    """If scheduler says project holds a lock but no build threads are alive, purge it."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {
            "local:default_ollama": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-dead": "catalogue"},
                "queued": [],
            }
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_build_orch.is_any_active.return_value = False

    mock_event_bus = MagicMock()

    from codrag.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 1
    mock_scheduler.clean_locks.assert_called_once_with("proj-dead")
    mock_event_bus.emit.assert_called_once()
    call_args = mock_event_bus.emit.call_args
    assert call_args[0][0] == "queue_changed"
    assert call_args[0][1]["reason"] == "ghost_purged"


def test_purge_ghost_locks_no_op_when_threads_alive():
    """If build threads are alive for a locked project, do nothing."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {
            "local:default_ollama": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-alive": "catalogue"},
                "queued": [],
            }
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_build_orch.is_any_active.return_value = True

    mock_event_bus = MagicMock()

    from codrag.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 0
    mock_scheduler.clean_locks.assert_not_called()
    mock_event_bus.emit.assert_not_called()


def test_purge_ghost_locks_multiple_nodes():
    """Purges across multiple compute nodes in one pass."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {
            "local:ollama1": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-a": "catalogue"},
                "queued": [],
            },
            "cloud:openai": {
                "max_concurrent": 3,
                "current_load": 1,
                "active": {"proj-b": "epistemic"},
                "queued": [],
            },
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_build_orch.is_any_active.side_effect = lambda pid: pid == "proj-a"

    mock_event_bus = MagicMock()

    from codrag.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 1
    mock_scheduler.clean_locks.assert_called_once_with("proj-b")


def test_purge_ghost_locks_empty_scheduler():
    """No active slots means nothing to purge."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {},
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_event_bus = MagicMock()

    from codrag.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 0

"""Regression tests for the unified pipeline queue.

Bug symptom: a stuck index/trace build silently blocked /full-reset with
"Cannot reset while index build is running" while the queue panel
displayed "No active pipelines" — the queue endpoint and the reset
gate disagreed on what was actually running.

Contract pinned here:

1. Every active task tracked by ProgressManager (index_build, trace_build,
   knowledge_build, delta_build) appears in /system/pipeline-queue. The
   queue is the single source of truth for "what's running outside the
   pipeline orchestrator."
2. POST /projects/{id}/pipeline/cancel with the task's group routes to
   ProgressManager.request_cancel — flipping the worker's cancel_event
   so the next progress callback raises BuildCancelledError and unwinds.
3. DELETE /projects/{id}/index/destroy?force=true bypasses the
   running-build gate. Used as the user's last-resort escape hatch when
   a worker ignores cancellation.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import prep.server as server
import prep.services.project_helpers as ph
from prep.core.events import get_progress_manager
from prep.core.project_registry import ProjectRegistry
from prep.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    with server._project_build_lock:
        server._project_build_threads.clear()
        server._project_last_build_result.clear()
        server._project_last_build_error.clear()
    with server._project_trace_build_lock:
        server._project_trace_build_threads.clear()
    # Drain anything left over from previous tests in the singleton
    pm = get_progress_manager()
    with pm._lock:
        pm.active_tasks.clear()
    return TestClient(app)


def _add_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "p", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def _queue_groups_for(client: TestClient, project_id: str) -> list[str]:
    res = client.get("/system/pipeline-queue")
    assert res.status_code == 200
    return [
        item["group"]
        for item in res.json()["data"]["queue"]
        if item["project_id"] == project_id
    ]


def test_progress_manager_task_surfaces_in_queue(client, tmp_path):
    pid = _add_project(client, tmp_path)
    pm = get_progress_manager()

    task_id = pm.start_task("index_build", pid)
    try:
        groups = _queue_groups_for(client, pid)
        assert "index_build" in groups, (
            f"index_build task should surface in /system/pipeline-queue, got {groups}"
        )
    finally:
        pm.finish_task(task_id)

    # After finish_task it must clear from the queue.
    assert "index_build" not in _queue_groups_for(client, pid)


def test_cancel_endpoint_signals_progress_manager_event(client, tmp_path):
    pid = _add_project(client, tmp_path)
    pm = get_progress_manager()

    task_id = pm.start_task("trace_build", pid)
    cancel_event = threading.Event()
    pm.register_cancel_event(task_id, cancel_event)

    try:
        res = client.post(
            f"/projects/{pid}/pipeline/cancel",
            json={"group": "trace_build"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["cancelled"] is True
        # The worker's cancel event must be set so its next progress
        # callback can raise BuildCancelledError.
        assert cancel_event.is_set(), "cancel event must be set after cancel request"

        # Queue still shows the task — but as 'cancelling' until the
        # worker actually unwinds. Zombie state stays visible.
        res = client.get("/system/pipeline-queue")
        item = next(
            i for i in res.json()["data"]["queue"]
            if i["project_id"] == pid and i["group"] == "trace_build"
        )
        assert item["phase"] == "cancelling"
    finally:
        pm.finish_task(task_id)


def test_cancel_endpoint_returns_409_when_no_task_to_cancel(client, tmp_path):
    pid = _add_project(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/pipeline/cancel",
        json={"group": "index_build"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "NOT_RUNNING"


def test_full_reset_force_bypasses_running_gate(client, tmp_path):
    pid = _add_project(client, tmp_path)
    pm = get_progress_manager()

    # Simulate a stuck build: register a task and a thread that's still
    # alive (uses an Event so it never actually exits during the test).
    task_id = pm.start_task("index_build", pid)
    block = threading.Event()
    cancel_event = threading.Event()
    pm.register_cancel_event(task_id, cancel_event)
    t = threading.Thread(target=block.wait, daemon=True)
    t.start()
    try:
        with server._project_build_lock:
            server._project_build_threads[pid] = t

        # Without force: gate refuses.
        res = client.delete(f"/projects/{pid}/index/destroy")
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "PIPELINE_RUNNING"
        assert "force" in (res.json()["error"].get("hint") or "").lower()

        # With force: cancel event is set (so a real worker would unwind)
        # AND the reset proceeds despite the still-alive thread.
        res = client.delete(f"/projects/{pid}/index/destroy?force=true")
        assert res.status_code == 200, res.text
        assert cancel_event.is_set(), (
            "force reset must still signal cancel so the worker can unwind"
        )
    finally:
        block.set()
        t.join(timeout=1)
        pm.finish_task(task_id)
        with server._project_build_lock:
            server._project_build_threads.pop(pid, None)

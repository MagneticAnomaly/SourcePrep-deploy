"""Phase 136 Part 15 — concurrency visibility fixes + diagnostic.

Three plain UI/observability fixes plus a diagnostic primitive, all
prompted by dogfooding 2026-05-18:
  * Queue card showed ``10 / 19`` for ``cloud:default_ollama`` while the
    real ceiling was ``max_concurrent = dynamic_capacity = 10``.  The
    badge was reading AIMD's growable ``current_limit`` which on
    no-auto-detect providers floats meaninglessly above ``max``.
  * Non-swarm stages (``inferred_edges`` in particular) were badged
    "Swarming" because ``token_telemetry._active_requests`` had stale
    entries with ``swarm_role="worker"`` from a prior swarm stage and
    ``queue.py`` / ``llm.py`` derived ``is_swarm`` purely from
    ``role_tagged > 0`` with no stage check.
  * No way to introspect ``_active_requests`` to find out which threads
    carry stale role tags — needed to actually find the leak.

This test suite encodes the contract for all four fixes.  They all
fail BEFORE the implementation lands and pass after.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List
from unittest.mock import patch

from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────
#  Fix B — Queue serializer exposes dynamic_capacity
# ─────────────────────────────────────────────────────────────

def test_pipeline_queue_node_summary_exposes_dynamic_capacity(
    monkeypatch, tmp_path,
) -> None:
    """``/system/pipeline-queue`` node summary must include ``dynamic_capacity``.

    Before Phase 136 Part 15 the dashboard had to choose between
    ``max_concurrent`` (sometimes 0 for the Auto sentinel) and
    ``current_limit`` (AIMD's growable headroom, can float above max).
    ``dynamic_capacity`` is the slot property that already encodes the
    correct ceiling in both modes — we just need to expose it.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.server import app

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    pipeline_scheduler.configure_node("cloud:dyn-cap-test", max_concurrent=10)
    slot = pipeline_scheduler._slots["cloud:dyn-cap-test"]
    # Simulate AIMD having grown current_limit beyond max_concurrent
    # (the exact scenario the dashboard was mis-rendering as "10/19").
    slot.current_limit = 19

    client = TestClient(app)
    resp = client.get("/system/pipeline-queue")
    assert resp.status_code == 200
    body = resp.json()
    nodes = body.get("nodes") or body.get("data", {}).get("nodes")
    n = nodes["cloud:dyn-cap-test"]

    assert "dynamic_capacity" in n, (
        "queue serializer must expose dynamic_capacity so the dashboard "
        "stops displaying current_limit as the denominator"
    )
    # For Ollama-Cloud-style providers (no-auto-detect, max_concurrent>0),
    # dynamic_capacity == max_concurrent regardless of AIMD's
    # internal current_limit drift.
    assert n["dynamic_capacity"] == 10
    # And current_limit is still exposed for the Concurrency Health panel.
    assert n["current_limit"] == 19


# ─────────────────────────────────────────────────────────────
#  Fix C — is_swarm gated on SWARM_CAPABLE_STAGES
# ─────────────────────────────────────────────────────────────

def test_is_swarm_false_on_non_swarm_stage_even_with_role_tagged(
    monkeypatch,
) -> None:
    """A non-swarm stage with stale role-tagged telemetry must not be
    flagged as swarming.

    Reproduces the dashboard bug where ``inferred_edges`` (NOT in
    ``SWARM_CAPABLE_STAGES``) was labelled "Swarming" because stale
    ``_active_requests`` entries with ``swarm_role="worker"`` from a
    prior swarm stage tripped the
    ``window_matches or role_tagged > 0`` heuristic.
    """
    from prep.services import token_telemetry
    from prep.services.pipeline.scheduler import (
        SWARM_CAPABLE_STAGES,
        pipeline_scheduler,
    )

    pid = "test-non-swarm-proj"
    stage = "inferred_edges"
    assert stage not in SWARM_CAPABLE_STAGES, (
        "Precondition for this test: inferred_edges must NOT be swarm-capable"
    )

    # Stale telemetry from a prior swarm worker that didn't clean up.
    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: [
            {
                "project_id": pid,
                "task_id": stage,
                "model": "kimi-k2.6:cloud",
                "provider": "ollama",
                "model_slot": "large",
                "swarm_role": "worker",   # <- stale leak from earlier swarm
                "duration_seconds": 0.7,
            },
            {
                "project_id": pid,
                "task_id": stage,
                "model": "kimi-k2.6:cloud",
                "provider": "ollama",
                "model_slot": "large",
                "swarm_role": "worker",
                "duration_seconds": 0.5,
            },
        ],
    )

    # Force the scheduler swarm window to be empty (no real swarm).
    monkeypatch.setattr(
        pipeline_scheduler, "get_swarm_window", lambda: None,
    )

    from prep.api.routers.queue import _build_queue_item

    item = _build_queue_item(
        project_id=pid,
        group="fast_sync",
        phase="running",
        current_stage=stage,
        started_at=time.time(),
        wait_seconds=None,
    )
    assert item["is_swarm"] is False, (
        "Stale role-tagged telemetry must not make a non-swarm stage "
        "appear as swarming"
    )
    assert item["state"] != "swarm_active"


def test_is_swarm_true_on_swarm_capable_stage_with_role_tagged(
    monkeypatch,
) -> None:
    """A swarm-capable stage WITH role-tagged telemetry is still swarm-active.

    Confirms Fix C only excludes non-swarm stages — the original
    "brief window during phase transition" coverage from the
    role_tagged heuristic is preserved on legitimately swarm-capable
    stages (``audit``, ``concepts``, ``clustering``, ``atlas``,
    ``group_reasoning``).
    """
    from prep.services import token_telemetry
    from prep.services.pipeline.scheduler import (
        SWARM_CAPABLE_STAGES,
        pipeline_scheduler,
    )

    pid = "test-swarm-proj"
    # Pick any swarm-capable stage.
    stage = next(iter(SWARM_CAPABLE_STAGES))

    monkeypatch.setattr(
        token_telemetry.telemetry,
        "get_active_requests",
        lambda: [
            {
                "project_id": pid,
                "task_id": stage,
                "model": "kimi-k2.6:cloud",
                "provider": "ollama",
                "model_slot": "large",
                "swarm_role": "worker",
                "duration_seconds": 0.3,
            },
        ],
    )
    monkeypatch.setattr(
        pipeline_scheduler, "get_swarm_window", lambda: None,
    )

    from prep.api.routers.queue import _build_queue_item

    item = _build_queue_item(
        project_id=pid,
        group="finalize",
        phase="running",
        current_stage=stage,
        started_at=time.time(),
        wait_seconds=None,
    )
    assert item["is_swarm"] is True


# ─────────────────────────────────────────────────────────────
#  Diagnostic — dump_active_state surfaces stale entries
# ─────────────────────────────────────────────────────────────

def test_dump_active_state_returns_per_tid_with_thread_metadata() -> None:
    """``TokenTelemetryStore.dump_active_state()`` returns one dict per
    entry in ``_active_requests`` annotated with thread name + alive
    flag + age, so a leak hunter can tell whether stale entries are
    on dead swarm-fanout threads or live augmenter threads.
    """
    from prep.services import token_telemetry as tt

    # Wipe any pre-existing state for test isolation.
    with tt._active_requests_lock:
        tt._active_requests.clear()

    # Inject a synthetic entry on this thread.
    with tt.set_telemetry_context("diag-proj", "diag-task"):
        tt.telemetry.track_active_request("dummy-model", "ollama", "large")
        try:
            state = tt.telemetry.dump_active_state()
        finally:
            tt.telemetry.untrack_active_request()

    assert isinstance(state, list)
    assert len(state) == 1
    entry = state[0]
    # Fields a leak-hunter actually needs:
    for key in (
        "tid",
        "thread_name",
        "thread_alive",
        "age_seconds",
        "project_id",
        "task_id",
        "model",
        "model_slot",
        "swarm_role",
    ):
        assert key in entry, f"dump_active_state must include {key!r}"
    assert entry["project_id"] == "diag-proj"
    assert entry["task_id"] == "diag-task"
    assert entry["model_slot"] == "large"
    assert entry["thread_alive"] is True
    assert entry["thread_name"] == threading.current_thread().name
    assert entry["age_seconds"] >= 0


def test_dump_active_state_marks_dead_thread_entries() -> None:
    """When the recorded ``tid`` no longer corresponds to a live thread,
    ``thread_alive`` is ``False`` and ``thread_name`` is ``None``.

    This is the signal a leak hunter looks for: a stale entry whose
    thread died without calling ``untrack_active_request``.
    """
    from prep.services import token_telemetry as tt

    with tt._active_requests_lock:
        tt._active_requests.clear()
        # Synthesize a stale entry on a tid that doesn't exist anymore.
        fake_tid = 999_999_999
        tt._active_requests[fake_tid] = tt.ActiveLLMRequest(
            project_id="dead-proj",
            task_id="dead-task",
            model="kimi-k2.6:cloud",
            provider="ollama",
            start_time=time.time() - 120.0,  # 2 min stale
            model_slot="large",
            swarm_role="worker",
        )

    try:
        state = tt.telemetry.dump_active_state()
        match = [e for e in state if e["tid"] == fake_tid]
        assert len(match) == 1
        entry = match[0]
        assert entry["thread_alive"] is False
        assert entry["thread_name"] is None
        assert entry["age_seconds"] >= 100.0
        assert entry["swarm_role"] == "worker"
    finally:
        # Cleanup
        with tt._active_requests_lock:
            tt._active_requests.pop(fake_tid, None)


# ─────────────────────────────────────────────────────────────
#  Verbose logging — pipeline_logger snapshots concurrency at
#  stage transitions
# ─────────────────────────────────────────────────────────────

def test_pipeline_logger_emits_concurrency_snapshot_at_stage_start(
    tmp_path, monkeypatch,
) -> None:
    """PipelineFileLogger writes a ``concurrency_snapshot`` event on
    ``stage_start`` carrying the scheduler slot state and the active
    request dump.

    Past-run analysis: with this in the log we can grep for
    ``concurrency_snapshot`` and see exactly how many workers were in
    flight + which threads were holding tags at each stage boundary.
    """
    from prep.services.pipeline_logger import PipelineFileLogger
    from prep.services.pipeline.scheduler import pipeline_scheduler

    # Set up a slot so the snapshot has something to record.
    pipeline_scheduler.configure_node("cloud:snap-test", max_concurrent=4)

    idx_dir = tmp_path / ".sourceprep"
    idx_dir.mkdir()
    pfl = PipelineFileLogger(idx_dir)
    pfl.start_run("fast_sync", ["structural", "inferred_edges"], project_id="snap-proj")
    try:
        pfl.stage_start("inferred_edges")
    finally:
        pfl.end_run()

    # The log file is JSONL — one event per line.
    log_text = pfl.log_path.read_text(encoding="utf-8")
    lines = [l for l in log_text.splitlines() if l.strip()]
    import json
    events = [json.loads(l) for l in lines]
    snaps = [e for e in events if e.get("event") == "concurrency_snapshot"]

    assert snaps, "stage_start must emit a concurrency_snapshot event"
    snap = snaps[-1]
    data = snap.get("data") or {}
    assert "slots" in data, "snapshot must include scheduler slot states"
    assert "active_requests" in data, (
        "snapshot must include per-tid active request dump"
    )
    # Slot we configured should be present.
    assert any(
        nid == "cloud:snap-test" for nid in data["slots"].keys()
    )
    # Fields that matter for past-run analysis:
    slot_snap = data["slots"]["cloud:snap-test"]
    for k in ("max_concurrent", "dynamic_capacity", "in_flight_requests", "current_limit"):
        assert k in slot_snap, f"slot snapshot must include {k!r}"

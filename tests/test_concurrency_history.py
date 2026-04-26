"""Phase 119 Task 15: per-slot AIMD ring buffer + /compute/concurrency/history.

The "Concurrency Health" weather-report panel needs a recent-events feed
to show how the latency-aware AIMD has moved a node's concurrency over
time.  This module covers:

  * the event helper appends to the per-slot ring buffer
  * a demand-gated grow appends a ``demand_recovery`` event
  * a backoff in CA mode appends both a ``backoff`` and an ``edge_lock`` event
  * the GET ``/compute/concurrency/history`` endpoint returns the buffer

In-memory only — does not survive daemon restart.
"""
from __future__ import annotations

import time

from fastapi.testclient import TestClient


# ── Fixtures / helpers ───────────────────────────────────────────


def _make_app():
    from prep.server import app
    return app


def _fresh_slot(node_id: str = "cloud:hist-test"):
    """Configure a fresh cloud slot with an empty ring buffer."""
    from prep.services.pipeline.scheduler import pipeline_scheduler

    # Drop any prior slot from earlier tests.
    pipeline_scheduler._slots.pop(node_id, None)
    pipeline_scheduler._queues.pop(node_id, None)
    pipeline_scheduler.configure_node(node_id, max_concurrent=1)
    slot = pipeline_scheduler._slots[node_id]
    slot._history.clear()
    return slot


# ── _record_history primitive ────────────────────────────────────


def test_record_history_appends_event_with_required_fields() -> None:
    from prep.services.pipeline.scheduler import pipeline_scheduler

    slot = _fresh_slot("cloud:rec-1")
    with pipeline_scheduler._lock:
        pipeline_scheduler._record_history(slot, 5, 10, "additive_increase")
    assert len(slot._history) == 1
    ev = slot._history[0]
    assert set(ev.keys()) >= {
        "ts", "node_id", "before", "after", "reason", "in_flight", "mode",
    }
    assert ev["node_id"] == "cloud:rec-1"
    assert ev["before"] == 5
    assert ev["after"] == 10
    assert ev["reason"] == "additive_increase"


def test_record_history_respects_maxlen() -> None:
    """The ring buffer caps at maxlen=50; old events drop off the left."""
    from prep.services.pipeline.scheduler import pipeline_scheduler

    slot = _fresh_slot("cloud:rec-cap")
    with pipeline_scheduler._lock:
        for i in range(60):
            pipeline_scheduler._record_history(slot, i, i + 1, "additive_increase")
    assert len(slot._history) == 50
    # Oldest retained event is the 11th one we recorded (60 - 50 = 10).
    assert slot._history[0]["before"] == 10


# ── Demand-gated recovery → demand_recovery event ────────────────


def test_demand_recovery_appends_event() -> None:
    """When _maybe_demand_recover successfully grows the limit, a
    ``demand_recovery`` event is appended."""
    from prep.services.pipeline.scheduler import pipeline_scheduler

    slot = _fresh_slot("cloud:demand-1")
    # Set up the conditions for demand_recovery to fire:
    #   - past the backoff cooldown
    #   - past the idle recovery interval
    #   - gate_binding_until is in the future (someone hit the gate recently)
    #   - current_limit < discovered_ceiling (or no ceiling)
    now = time.time()
    slot.current_limit = 5
    slot.discovered_ceiling = None
    slot._last_backoff_time = now - 1000  # well past cooldown
    slot._last_recovery_time = now - 1000  # well past interval
    slot._gate_binding_until = now + 30    # gate currently binding

    with pipeline_scheduler._lock:
        pipeline_scheduler._maybe_demand_recover(slot)

    # Confirm the grow happened AND was logged.
    assert slot.current_limit == 6
    assert len(slot._history) == 1
    ev = slot._history[-1]
    assert ev["reason"] == "demand_recovery"
    assert ev["before"] == 5
    assert ev["after"] == 6


# ── Backoff in CA mode → backoff + edge_lock events ──────────────


def test_backoff_in_ca_mode_appends_backoff_and_edge_lock(
    monkeypatch, tmp_path,
) -> None:
    """A backoff while ``mode == "congestion_avoidance"`` records both
    a ``backoff`` event (the limit shrinking) and an ``edge_lock`` event
    (the discovered ceiling being persisted).
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    # Redirect persistence to tmp so we don't touch real state.
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    slot = _fresh_slot("cloud:backoff-1")
    slot.current_limit = 16
    slot.in_flight_requests = 8  # so MD picks min(8, 8) = 8
    slot.mode = "congestion_avoidance"
    slot._last_backoff_time = 0.0  # ensure cooldown doesn't suppress

    with pipeline_scheduler._lock:
        pipeline_scheduler._record_throughput_for_slot(
            slot, queue_time_ms=0.0, is_429_or_timeout=True,
        )

    reasons = [ev["reason"] for ev in slot._history]
    assert "backoff" in reasons, f"expected backoff event, got {reasons}"
    assert "edge_lock" in reasons, f"expected edge_lock event, got {reasons}"
    # The backoff event records the shrink.
    backoff_ev = next(ev for ev in slot._history if ev["reason"] == "backoff")
    assert backoff_ev["before"] == 16
    assert backoff_ev["after"] < 16


def test_backoff_in_jumpstart_mode_does_not_lock_edge(
    monkeypatch, tmp_path,
) -> None:
    """A backoff while ``mode == "jumpstart"`` records ``backoff`` but
    NOT ``edge_lock`` — jumpstart doublings aren't a confirmed edge."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    slot = _fresh_slot("cloud:backoff-js")
    slot.current_limit = 8
    slot.in_flight_requests = 4
    slot.mode = "jumpstart"
    slot._last_backoff_time = 0.0

    with pipeline_scheduler._lock:
        pipeline_scheduler._record_throughput_for_slot(
            slot, queue_time_ms=0.0, is_429_or_timeout=True,
        )

    reasons = [ev["reason"] for ev in slot._history]
    assert "backoff" in reasons
    assert "edge_lock" not in reasons


# ── /compute/concurrency/history endpoint ───────────────────────


def test_history_endpoint_returns_per_node_buffer() -> None:
    from prep.services.pipeline.scheduler import pipeline_scheduler

    slot = _fresh_slot("cloud:api-hist")
    with pipeline_scheduler._lock:
        pipeline_scheduler._record_history(slot, 1, 2, "additive_increase")
        pipeline_scheduler._record_history(slot, 2, 4, "jumpstart")

    app = _make_app()
    client = TestClient(app)
    resp = client.get("/compute/concurrency/history")
    assert resp.status_code == 200
    body = resp.json()
    assert "history" in body
    assert "cloud:api-hist" in body["history"]
    events = body["history"]["cloud:api-hist"]
    assert len(events) == 2
    assert events[0]["reason"] == "additive_increase"
    assert events[1]["reason"] == "jumpstart"
    # All required fields present
    for ev in events:
        assert set(ev.keys()) >= {
            "ts", "node_id", "before", "after", "reason", "in_flight", "mode",
        }


def test_history_endpoint_filters_by_node_id() -> None:
    from prep.services.pipeline.scheduler import pipeline_scheduler

    slot_a = _fresh_slot("cloud:api-filter-a")
    slot_b = _fresh_slot("cloud:api-filter-b")
    with pipeline_scheduler._lock:
        pipeline_scheduler._record_history(slot_a, 1, 2, "jumpstart")
        pipeline_scheduler._record_history(slot_b, 3, 4, "additive_increase")

    app = _make_app()
    client = TestClient(app)
    resp = client.get(
        "/compute/concurrency/history",
        params={"node_id": "cloud:api-filter-a"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "cloud:api-filter-a" in body["history"]
    assert "cloud:api-filter-b" not in body["history"]


def test_history_endpoint_respects_limit() -> None:
    from prep.services.pipeline.scheduler import pipeline_scheduler

    slot = _fresh_slot("cloud:api-limit")
    with pipeline_scheduler._lock:
        for i in range(20):
            pipeline_scheduler._record_history(
                slot, i, i + 1, "additive_increase",
            )

    app = _make_app()
    client = TestClient(app)
    resp = client.get(
        "/compute/concurrency/history",
        params={"node_id": "cloud:api-limit", "limit": 5},
    )
    assert resp.status_code == 200
    events = resp.json()["history"]["cloud:api-limit"]
    assert len(events) == 5
    # Last 5 events — i.e. before values 15..19
    assert events[0]["before"] == 15
    assert events[-1]["before"] == 19

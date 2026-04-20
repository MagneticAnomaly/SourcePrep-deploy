"""Phase 82 follow-up: per-request AIMD gate.

Tests the new acquire_request/release_request API on PipelineScheduler.
The existing ``acquire`` method is stage-level (one entry per project-stage);
these tests exercise per-REQUEST gating backed by Condition/counter.
"""
from __future__ import annotations

import threading
import time

import pytest

from codrag.services.pipeline.scheduler import (
    ComputeSlot,
    PipelineScheduler,
)


def _seeded_cloud_scheduler(limit: int = 3) -> tuple[PipelineScheduler, str]:
    sched = PipelineScheduler()
    node_id = "cloud:ep-test"
    sched.configure_node(node_id, max_concurrent=limit)
    slot = sched._slots[node_id]
    slot.current_limit = limit
    slot.mode = "congestion_avoidance"
    return sched, node_id


def test_acquire_release_cycle_tracks_in_flight() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=3)
    slot = sched._slots[node_id]

    token = sched.acquire_request(node_id, timeout=1.0)
    assert token is not None
    assert slot.in_flight_requests == 1

    sched.release_request(token)
    assert slot.in_flight_requests == 0


def test_acquire_blocks_when_at_limit_then_wakes_on_release() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=2)
    slot = sched._slots[node_id]

    t1 = sched.acquire_request(node_id, timeout=1.0)
    t2 = sched.acquire_request(node_id, timeout=1.0)
    assert t1 is not None and t2 is not None
    assert slot.in_flight_requests == 2

    waiter_token = {"value": "unset"}

    def _waiter() -> None:
        waiter_token["value"] = sched.acquire_request(node_id, timeout=2.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)
    assert slot.in_flight_requests == 2
    sched.release_request(t1)
    th.join(timeout=2.0)

    assert waiter_token["value"] is not None, "waiter never woke"
    assert slot.in_flight_requests == 2

    sched.release_request(t2)
    sched.release_request(waiter_token["value"])
    assert slot.in_flight_requests == 0


def test_acquire_times_out_returns_none() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=1)
    held = sched.acquire_request(node_id, timeout=1.0)
    assert held is not None

    t_start = time.monotonic()
    result = sched.acquire_request(node_id, timeout=0.2)
    elapsed = time.monotonic() - t_start

    assert result is None
    assert 0.15 <= elapsed <= 0.5, f"timeout elapsed={elapsed}"

    sched.release_request(held)


def test_limit_decrease_via_aimd_does_not_evict_in_flight() -> None:
    """AIMD backoff reduces current_limit — existing in-flight requests must
    NOT be forcibly released. They finish naturally; new acquires block until
    in_flight drops below the new limit."""
    sched, node_id = _seeded_cloud_scheduler(limit=4)
    slot = sched._slots[node_id]

    tokens = [sched.acquire_request(node_id, timeout=1.0) for _ in range(4)]
    assert all(t is not None for t in tokens)
    assert slot.in_flight_requests == 4

    sched._record_throughput_for_slot(slot, is_429_or_timeout=True)
    assert slot.current_limit < 4
    assert slot.in_flight_requests == 4

    new_token = {"value": "unset"}

    def _waiter() -> None:
        new_token["value"] = sched.acquire_request(node_id, timeout=2.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)
    assert new_token["value"] == "unset"

    for t in tokens:
        sched.release_request(t)
    th.join(timeout=2.0)
    assert new_token["value"] is not None

    sched.release_request(new_token["value"])


def test_unknown_node_id_returns_none() -> None:
    sched = PipelineScheduler()
    assert sched.acquire_request("cloud:does-not-exist", timeout=0.1) is None


def test_release_idempotent_on_stale_token() -> None:
    """Releasing the same token twice must not drive in_flight negative."""
    sched, node_id = _seeded_cloud_scheduler(limit=2)
    slot = sched._slots[node_id]

    t = sched.acquire_request(node_id, timeout=1.0)
    sched.release_request(t)
    assert slot.in_flight_requests == 0

    sched.release_request(t)
    assert slot.in_flight_requests == 0


def test_context_manager_releases_on_exception() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=1)
    slot = sched._slots[node_id]

    with pytest.raises(RuntimeError):
        with sched.acquire_request_ctx(node_id, timeout=1.0):
            assert slot.in_flight_requests == 1
            raise RuntimeError("boom")

    assert slot.in_flight_requests == 0


def test_context_manager_yields_none_on_timeout() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=1)
    held = sched.acquire_request(node_id, timeout=1.0)
    assert held is not None

    entered = {"value": False}
    with sched.acquire_request_ctx(node_id, timeout=0.1) as token:
        entered["value"] = True
        assert token is None

    assert entered["value"] is True
    sched.release_request(held)

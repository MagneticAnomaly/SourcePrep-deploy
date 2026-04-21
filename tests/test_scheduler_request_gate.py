"""Phase 82 follow-up: per-request AIMD gate.

Tests the new acquire_request/release_request API on PipelineScheduler.
The existing ``acquire`` method is stage-level (one entry per project-stage);
these tests exercise per-REQUEST gating backed by Condition/counter.
"""
from __future__ import annotations

import threading
import time

import pytest

from prep.services.pipeline.scheduler import (
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


def test_capacity_growth_via_aimd_wakes_blocked_waiter() -> None:
    """When AIMD grows current_limit, blocked waiters must wake, not sleep
    until the 120s timeout. This is the F-28 idle-recovery case."""
    sched = PipelineScheduler()
    node_id = "cloud:ep-growth"
    sched.configure_node(node_id, max_concurrent=1)
    slot = sched._slots[node_id]
    slot.current_limit = 1
    slot.mode = "congestion_avoidance"

    # Hold the one slot.
    held = sched.acquire_request(node_id, timeout=1.0)
    assert held is not None
    assert slot.in_flight_requests == 1

    # Block a waiter.
    waiter_result = {"token": "unset"}

    def _waiter() -> None:
        waiter_result["token"] = sched.acquire_request(node_id, timeout=3.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)
    assert waiter_result["token"] == "unset"  # still blocked

    # Simulate AIMD jumpstart doubling: 1 → 2, while WITHOUT releasing `held`.
    # Drive it via the real _record_throughput_for_slot to exercise the
    # notify hook in that path.  _record_throughput_for_slot requires the
    # scheduler lock to be held by the caller (same as all production callers).
    slot.mode = "jumpstart"
    # success_streak needs to reach batch_size (=current_limit) to trigger a step.
    limit_snapshot = slot.current_limit
    for _ in range(limit_snapshot):
        with sched._lock:
            sched._record_throughput_for_slot(slot, queue_time_ms=50.0)

    assert slot.current_limit >= 2  # grew
    th.join(timeout=2.0)
    assert waiter_result["token"] is not None, (
        "waiter did not wake after capacity growth"
    )

    sched.release_request(held)
    sched.release_request(waiter_result["token"])


def test_notify_all_wakes_multiple_waiters_on_release() -> None:
    """With multiple blocked waiters, a single release must wake them all
    (via notify_all). Those that still can't proceed re-wait — the rest
    acquire."""
    sched = PipelineScheduler()
    node_id = "cloud:ep-multi"
    sched.configure_node(node_id, max_concurrent=1)
    slot = sched._slots[node_id]
    # Seed limit=2 so after release there is room for one waiter.
    slot.current_limit = 2
    slot.mode = "congestion_avoidance"

    t1 = sched.acquire_request(node_id, timeout=1.0)
    t2 = sched.acquire_request(node_id, timeout=1.0)
    assert t1 is not None and t2 is not None

    waiters = [{"token": "unset"}, {"token": "unset"}]

    def _waiter(idx: int) -> None:
        waiters[idx]["token"] = sched.acquire_request(node_id, timeout=3.0)

    threads = [threading.Thread(target=_waiter, args=(i,)) for i in range(2)]
    for th in threads:
        th.start()
    time.sleep(0.1)
    assert all(w["token"] == "unset" for w in waiters)

    # Release one token — notify_all wakes both; exactly one wins.
    sched.release_request(t1)

    # Wait briefly for threads to resolve.
    for th in threads:
        th.join(timeout=2.0)

    awakened = [w for w in waiters if w["token"] not in (None, "unset")]
    assert len(awakened) == 1, (
        f"expected exactly 1 waiter to acquire, got {len(awakened)}"
    )

    # Clean up: release remaining acquires
    sched.release_request(t2)
    for w in waiters:
        tok = w["token"]
        if tok not in (None, "unset"):
            sched.release_request(tok)


def test_configure_node_grow_wakes_waiters() -> None:
    """configure_node with a higher max_concurrent must wake threads blocked
    at the gate — not make them wait the full 120 s timeout."""
    sched = PipelineScheduler()
    node_id = "local:test-grow"
    sched.configure_node(node_id, max_concurrent=1)
    slot = sched._slots[node_id]
    # Local slot: current_limit = max_concurrent = 1
    assert slot.current_limit == 1

    # Acquire the one available token.
    held = sched.acquire_request(node_id, timeout=1.0)
    assert held is not None

    # Block a second acquire (limit=1, in_flight=1 → no headroom).
    waiter_result: dict[str, object] = {"token": "unset"}

    def _waiter() -> None:
        waiter_result["token"] = sched.acquire_request(node_id, timeout=3.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)
    assert waiter_result["token"] == "unset"  # still blocked

    # Raise the ceiling to 4 — waiter should wake immediately (< 1 s).
    t_start = time.monotonic()
    sched.configure_node(node_id, max_concurrent=4)
    th.join(timeout=1.0)
    elapsed = time.monotonic() - t_start

    assert waiter_result["token"] is not None, "waiter never woke after configure_node grow"
    assert elapsed < 1.0, f"waiter took {elapsed:.2f}s — expected <1 s"

    sched.release_request(held)
    sched.release_request(waiter_result["token"])  # type: ignore[arg-type]


def test_configure_embedding_grow_wakes_waiters() -> None:
    """configure_embedding_concurrency with a higher max must wake threads
    blocked at the embedding gate — not make them wait the full timeout."""
    sched = PipelineScheduler()
    emb_id = PipelineScheduler._EMBEDDING_NODE_ID
    sched.configure_embedding_concurrency(1)
    slot = sched._slots[emb_id]
    assert slot.current_limit == 1

    # Acquire the one available token.
    held = sched.acquire_request(emb_id, timeout=1.0)
    assert held is not None

    waiter_result: dict[str, object] = {"token": "unset"}

    def _waiter() -> None:
        waiter_result["token"] = sched.acquire_request(emb_id, timeout=3.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)
    assert waiter_result["token"] == "unset"  # still blocked

    # Raise embedding ceiling to 4.
    t_start = time.monotonic()
    sched.configure_embedding_concurrency(4)
    th.join(timeout=1.0)
    elapsed = time.monotonic() - t_start

    assert waiter_result["token"] is not None, (
        "waiter never woke after configure_embedding_concurrency grow"
    )
    assert elapsed < 1.0, f"waiter took {elapsed:.2f}s — expected <1 s"

    sched.release_request(held)
    sched.release_request(waiter_result["token"])  # type: ignore[arg-type]


def test_status_exposes_in_flight_requests() -> None:
    """PipelineScheduler.status() must include in_flight_requests per node."""
    sched, node_id = _seeded_cloud_scheduler(limit=5)

    t1 = sched.acquire_request(node_id, timeout=1.0)
    t2 = sched.acquire_request(node_id, timeout=1.0)
    assert t1 is not None and t2 is not None

    status = sched.status()
    assert node_id in status["nodes"]
    assert status["nodes"][node_id]["in_flight_requests"] == 2

    sched.release_request(t1)
    sched.release_request(t2)

"""Phase 119: recovery only fires when the gate has recently been binding."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from prep.services.pipeline.scheduler import ComputeSlot, PipelineScheduler


def _cloud_slot(node_id: str = "cloud:ep-test", current_limit: int = 6) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=1,
        current_limit=current_limit,
        min_limit=3,
        mode="congestion_avoidance",
    )


def _set_slot(sched: PipelineScheduler, slot: ComputeSlot) -> ComputeSlot:
    sched._slots[slot.node_id] = slot
    return slot


def test_demand_recovery_skipped_when_idle() -> None:
    """If nothing was waiting on the gate, current_limit must NOT grow."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))

    fake_now = 10_000.0
    with patch("prep.services.pipeline.scheduler.time.time", return_value=fake_now):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 6


def test_demand_recovery_grows_when_gate_was_binding(monkeypatch) -> None:
    """When acquire_request observed the gate binding within the demand
    window, the next acquire after cooldown grows current_limit by 1."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))

    base = 10_000.0
    # Simulate gate having been binding 5 seconds ago.
    slot._gate_binding_until = base + 30   # within window from base
    slot._last_backoff_time = 0.0          # well past cooldown
    slot._last_recovery_time = 0.0         # well past recovery interval

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 7


def test_demand_recovery_skipped_during_backoff_cooldown() -> None:
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))
    base = 10_000.0
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = base - 5   # 5 s ago — still in 30 s cooldown
    slot._last_recovery_time = 0.0

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 6


def test_demand_recovery_clamps_at_locked_ceiling() -> None:
    """When a discovered ceiling is locked, recovery cannot grow past it."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=11))
    slot.discovered_ceiling = 12
    slot.ceiling_locked_until = 99_999_999.0
    base = 10_000.0
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = 0.0
    slot._last_recovery_time = 0.0

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)
    assert slot.current_limit == 12

    # Second tick — already at ceiling, no further growth.
    slot._last_recovery_time = 0.0
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)
    assert slot.current_limit == 12


def test_acquire_request_marks_gate_binding(monkeypatch) -> None:
    """Phase 119: acquire_request stamps slot._gate_binding_until when the
    waiter actually had to wait. We test the marking by directly setting
    in_flight to current_limit and checking the stamp."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=2))
    slot.in_flight_requests = 2  # gate is full

    base = 10_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)
    monkeypatch.setattr(
        "prep.services.pipeline.scheduler.time.monotonic",
        lambda: 0.0,
    )

    # Acquire with timeout=0 (won't actually block, but must observe binding).
    token = sched.acquire_request("cloud:ep-test", timeout=0.0)
    assert token is None  # gate full, returned None

    # _gate_binding_until should have been stamped.
    assert slot._gate_binding_until > base

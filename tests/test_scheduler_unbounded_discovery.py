"""Phase 82 completion: cloud AIMD is unbounded; local remains VRAM-capped."""
from __future__ import annotations

import pytest

from codrag.services.pipeline.scheduler import (
    ComputeSlot,
    PipelineScheduler,
)


def _cloud_slot(node_id: str = "cloud:ep-test", seed: int = 5) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=seed,
        current_limit=seed,
        min_limit=3,
    )


def _local_slot(node_id: str = "local:ep-test", max_c: int = 1) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=max_c,
        min_limit=1,
    )


def test_cloud_dynamic_capacity_ignores_max_concurrent() -> None:
    slot = _cloud_slot()
    slot.current_limit = 40  # AIMD discovered a higher ceiling than the seed
    assert slot.dynamic_capacity == 40


def test_local_dynamic_capacity_still_clamps_at_max_concurrent() -> None:
    """Local slots have a real hardware ceiling (VRAM). Must still clamp."""
    slot = _local_slot(max_c=2)
    slot.current_limit = 10  # should be impossible but verify clamp
    assert slot.dynamic_capacity == 2


def test_cloud_aimd_doubling_past_max_concurrent(monkeypatch) -> None:
    """Cloud slot in jumpstart mode should double past its initial max_concurrent."""
    sched = PipelineScheduler()
    slot = _cloud_slot(seed=5)
    slot.mode = "jumpstart"
    sched._slots["cloud:ep-test"] = slot

    # Simulate 5 successful calls (batch_size = current_limit = 5) to trigger
    # a doubling step in jumpstart mode.
    for _ in range(5):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.current_limit == 10, (
        f"Expected doubling from 5→10, got current_limit={slot.current_limit}"
    )

    # Trigger another 10 successes — should double to 20 (uncapped).
    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.current_limit == 20, (
        f"Expected second doubling to 20 (past original max_concurrent=5), "
        f"got current_limit={slot.current_limit}"
    )


def test_local_aimd_does_not_exceed_max_concurrent() -> None:
    """Local VRAM ceiling must be respected — no doubling past max_concurrent."""
    sched = PipelineScheduler()
    slot = _local_slot(max_c=1)
    slot.mode = "congestion_avoidance"
    sched._slots["local:ep-test"] = slot

    for _ in range(50):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)

    assert slot.current_limit == 1, (
        f"Local slot exceeded VRAM ceiling: current_limit={slot.current_limit}"
    )

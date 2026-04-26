"""Phase 119 Phase A: cloud slots respect ``max_concurrent`` when the user has
set it (the soft cap from their plan dropdown). The Phase 82 bypass remains
when ``max_concurrent == 0`` (the "Auto" / unset case).
"""
from __future__ import annotations

from prep.services.pipeline.scheduler import ComputeSlot


def test_cloud_slot_clamps_at_max_concurrent_when_set() -> None:
    """User picked Max plan (10 concurrent). AIMD discovered/walked to 40.
    dynamic_capacity must return 10, not 40."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=10,    # user's plan-tier choice
        current_limit=40,     # AIMD walked here pre-fix
        min_limit=3,
    )
    assert slot.dynamic_capacity == 10


def test_cloud_slot_unbounded_when_max_concurrent_is_zero() -> None:
    """User picked 'Auto' (zero sentinel). Phase 82 unbounded behavior preserved."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=0,    # 'Auto' / unset
        current_limit=40,
        min_limit=3,
    )
    assert slot.dynamic_capacity == 40


def test_cloud_slot_clamps_at_max_concurrent_when_current_limit_lower() -> None:
    """When AIMD's current_limit is below the soft cap, return current_limit
    (we don't promote AIMD beyond what it discovered)."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=10,
        current_limit=4,
        min_limit=3,
    )
    assert slot.dynamic_capacity == 4


def test_local_slot_behavior_unchanged() -> None:
    """Local slot clamping at max_concurrent already works; ensure no regression."""
    slot = ComputeSlot(
        node_id="local:test",
        max_concurrent=2,
        current_limit=5,
        min_limit=1,
    )
    assert slot.dynamic_capacity == 2


def test_cloud_slot_floor_min_one_when_max_concurrent_is_negative() -> None:
    """Defensive: invalid negative max_concurrent should not crash."""
    slot = ComputeSlot(
        node_id="cloud:test",
        max_concurrent=-1,    # invalid input
        current_limit=10,
        min_limit=3,
    )
    # Treat negative same as zero (Phase 82 unbounded), don't crash.
    assert slot.dynamic_capacity == 10

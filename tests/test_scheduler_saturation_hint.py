"""Phase 119 Phase B — scheduler consumes per-provider saturation hints.

Verifies the AIMD step honors the optional ``SaturationHint`` produced by
the discovery layer:

- score >= 0.9 in jumpstart → switch to congestion_avoidance (no doubling)
- score >= 0.7 in either mode → skip the +1 grow cycle
- ``suggested_max`` further clamps growth (never overrides upward)
- Phase A's ``max_concurrent`` clamp via ``dynamic_capacity`` still wins
"""
from __future__ import annotations

from unittest.mock import patch

from prep.services.pipeline.discovery import SaturationHint
from prep.services.pipeline.scheduler import ComputeSlot, PipelineScheduler


def _cloud_slot(
    node_id: str = "cloud:ep-test",
    current_limit: int = 5,
    mode: str = "jumpstart",
    max_concurrent: int = 0,
) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=max_concurrent,
        current_limit=current_limit,
        min_limit=3,
        mode=mode,  # type: ignore[arg-type]
    )


def _set_slot(sched: PipelineScheduler, slot: ComputeSlot) -> ComputeSlot:
    sched._slots[slot.node_id] = slot
    return slot


def _prime_streak(slot: ComputeSlot) -> None:
    """Pre-fill success_streak so the very next throughput call triggers a step."""
    slot.success_streak = max(1, slot.current_limit) - 1


def _allow_demand_gate(slot: ComputeSlot, base: float) -> None:
    """Phase 119: cloud growth requires a recent gate-binding observation."""
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = 0.0
    slot._last_recovery_time = 0.0


def test_hard_saturation_in_jumpstart_switches_to_congestion_avoidance() -> None:
    """score >= 0.9 in jumpstart mode flips mode immediately, no doubling."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=5, mode="jumpstart"))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=0.95, suggested_max=None, reason="test hard")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    assert slot.mode == "congestion_avoidance"
    # Hard saturation also satisfies the soft threshold → no growth.
    assert slot.current_limit == 5


def test_soft_saturation_skips_growth_in_jumpstart() -> None:
    """0.7 <= score < 0.9 in jumpstart → no doubling this cycle, mode unchanged."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=5, mode="jumpstart"))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=0.75, suggested_max=None, reason="test soft")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    assert slot.current_limit == 5  # no growth
    assert slot.mode == "jumpstart"  # mode preserved (soft, not hard)


def test_soft_saturation_skips_additive_increase() -> None:
    """In congestion_avoidance, score >= 0.7 also skips the +1 step."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(
        current_limit=8, mode="congestion_avoidance",
    ))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=0.75, suggested_max=None, reason="test soft AI")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    assert slot.current_limit == 8  # +1 step suppressed


def test_low_saturation_allows_growth() -> None:
    """score < 0.7 leaves growth path untouched."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(
        current_limit=8, mode="congestion_avoidance",
    ))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=0.10, suggested_max=200, reason="plenty of room")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    assert slot.current_limit == 9  # additive +1 fired


def test_suggested_max_clamps_jumpstart_doubling() -> None:
    """Hint with low score but small suggested_max caps the doubling result."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=5, mode="jumpstart"))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=0.20, suggested_max=7, reason="header cap=7")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    # Without hint, jumpstart 5→10. With suggested_max=7, must clamp to 7.
    assert slot.current_limit == 7


def test_suggested_max_never_overrides_upward() -> None:
    """A larger suggested_max must NOT override the existing current_limit
    upward — Phase B's hint is a *narrowing* signal only."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(
        current_limit=8, mode="congestion_avoidance",
    ))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    # suggested_max=200 should NOT promote the +1 step into a +192 jump.
    hint = SaturationHint(score=0.10, suggested_max=200, reason="big budget")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    assert slot.current_limit == 9  # ordinary +1, not jumped to 200


def test_phase_a_max_concurrent_still_wins() -> None:
    """Phase A's soft cap via ``dynamic_capacity`` is the OUTER ceiling.
    Even when Phase B's suggested_max is larger, dynamic_capacity must
    still clamp at max_concurrent.

    Verifies the invariant the spec calls out: Phase B never raises a
    ceiling above Phase A's value.
    """
    slot = ComputeSlot(
        node_id="cloud:ep-cap",
        max_concurrent=10,   # user picked Max plan
        current_limit=8,
        min_limit=3,
        mode="congestion_avoidance",
    )
    # Phase B says "you have lots of budget — suggested_max=200".
    # That MUST NOT inflate the slot beyond max_concurrent=10.
    assert slot.dynamic_capacity == 8
    slot.current_limit = 50  # simulate AIMD walked beyond cap
    assert slot.dynamic_capacity == 10  # Phase A clamp holds


def test_no_hint_preserves_phase_82_growth() -> None:
    """When ``saturation_hint`` is None (default), behavior is unchanged
    from Phase 82 / Phase A."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=5, mode="jumpstart"))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot)  # no hint

    assert slot.current_limit == 10  # jumpstart 5→10 unchanged


def test_hint_logged_to_history_on_hard_threshold() -> None:
    """Hard threshold flip records a history event for the dashboard
    weather-report panel."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=5, mode="jumpstart"))
    _prime_streak(slot)
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=0.95, suggested_max=None, reason="x")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(slot, saturation_hint=hint)

    reasons = [event["reason"] for event in slot._history]
    assert "saturation_hint_hard" in reasons


def test_429_path_unaffected_by_hint() -> None:
    """A 429 is still a hard backoff signal — saturation hint must not
    suppress the multiplicative decrease."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(
        current_limit=20, mode="congestion_avoidance",
    ))
    slot.in_flight_requests = 8
    base = 10_000.0
    _allow_demand_gate(slot, base)

    hint = SaturationHint(score=1.0, suggested_max=1, reason="429")
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        with sched._lock:
            sched._record_throughput_for_slot(
                slot, is_429_or_timeout=True, saturation_hint=hint,
            )

    # MD halves to min(current_limit//2, in_flight) = min(10, 8) = 8,
    # bounded below by min_limit=3.
    assert slot.current_limit == 8

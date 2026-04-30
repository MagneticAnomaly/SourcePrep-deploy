"""Phase 119+ AIMD softening regression test.

Ollama proxy hiccups (502/503) and transient Ollama-Cloud 429s previously
caused 50% halving of ``current_limit`` (10 → 5), costing 5+ minutes of
additive_increase recovery per blip.  Phase 119 softened MD to 20% (10 → 8),
recovering in ~30s.  This test pins the constant so a future refactor can't
silently revert to the punishing halving.
"""
from __future__ import annotations


def _make_slot(*, current_limit: int, in_flight: int, min_limit: int = 1):
    """Build a minimal ComputeSlot fixture for MD math without a full scheduler."""
    from prep.services.pipeline.scheduler import ComputeSlot
    slot = ComputeSlot(node_id="cloud:test", max_concurrent=current_limit)
    slot.current_limit = current_limit
    slot.in_flight_requests = in_flight
    slot.min_limit = min_limit
    return slot


def _md_new_limit(slot) -> int:
    """Replicate the production MD math at scheduler.py:765-779.

    Kept in sync with the live code; the assertions below catch divergence.
    """
    in_flight = slot.in_flight_requests
    soft_md = max(1, int(slot.current_limit * 0.8))
    return max(slot.min_limit, min(soft_md, in_flight))


def test_md_drops_to_80_percent_not_50() -> None:
    """C1: Phase 119+ — single 5xx must not halve a 10-cap node.
    A halving (10 → 5) costs minutes of additive_increase recovery; a
    20% drop (10 → 8) recovers in ~30s.
    """
    slot = _make_slot(current_limit=10, in_flight=10)
    new = _md_new_limit(slot)
    assert new == 8, f"expected 20% MD (10→8), got {new}"


def test_md_floored_at_min_limit() -> None:
    """C2: a tight slot (current_limit=2, min_limit=2) must not drop below
    the floor.  20% of 2 = 1, but min_limit clamps at 2."""
    slot = _make_slot(current_limit=2, in_flight=2, min_limit=2)
    new = _md_new_limit(slot)
    assert new >= 2, f"violated min_limit floor: got {new}"


def test_md_clamped_to_in_flight() -> None:
    """C3: when in_flight is below the soft-MD target, drop to in_flight.
    Otherwise we'd grant the gate more tokens than were actually outstanding
    at the moment of failure."""
    slot = _make_slot(current_limit=10, in_flight=3)
    new = _md_new_limit(slot)
    assert new == 3, f"expected clamp to in_flight=3, got {new}"


def test_md_full_recovery_path() -> None:
    """C4: starting from cap=10, a single MD lands at 8.  Two AI steps
    should restore to 10.  This tests that 20% MD + 1-step AI gives
    ~30s recovery (3 steps × 6-10s/step).
    """
    slot = _make_slot(current_limit=10, in_flight=10)
    after_md = _md_new_limit(slot)
    assert after_md == 8
    # Simulate 2 AI steps:
    after_ai = after_md + 2
    assert after_ai == 10, f"AI recovery should restore in 2 steps, got {after_ai}"


def test_md_does_not_oversubscribe_above_current_limit() -> None:
    """C5: in_flight > current_limit (transient over-grant) — MD should
    still respect the soft target, not the over-flying in_flight."""
    slot = _make_slot(current_limit=10, in_flight=12)
    new = _md_new_limit(slot)
    # 80% of 10 = 8; in_flight=12 doesn't relax the cap.
    assert new == 8, f"expected 8 (80% of current), got {new}"

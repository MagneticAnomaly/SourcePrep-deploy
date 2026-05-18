"""Phase 136 Part 14 regression — cloud slot's dynamic_capacity must
respect the user's stated max_concurrent when supports_auto_detect is
unknown (None).

Pre-Phase-136 the no-auto-detect short-circuit at
``ComputeSlot.dynamic_capacity`` fired only on the explicit boolean
``supports_auto_detect is False``.  But the dataclass default is
``None``, and a startup race (configure_node runs before
settings_store finishes loading) leaves the cached flag as ``None`` —
``_provider_supports_auto_detect`` falls through to "no saved
endpoint matches" and returns the legacy ``True``, which the slot
cache stores as-is.  Once stuck, dynamic_capacity returns
``min(max_concurrent, current_limit) = min(10, 5) = 5`` — silently
halving the user's plan tier.

Observed dogfood 2026-05-18: swarm stages stuck at 5/10 even though
the user picked Ollama Cloud "Max" (10 concurrent).

The fix: treat ``supports_auto_detect is not True`` (i.e. False OR
None) as the no-auto-detect path.  Conservative default — when we
don't know, the user's stated cap is authoritative.
"""
from __future__ import annotations

from prep.services.pipeline.scheduler import ComputeSlot


def _slot(supports: object) -> ComputeSlot:
    return ComputeSlot(
        node_id="cloud:default_ollama",
        max_concurrent=10,
        current_limit=5,  # AIMD jumpstart seed
        min_limit=1,
        supports_auto_detect=supports,  # type: ignore[arg-type]
    )


class TestDynamicCapacityRespectsUserMax:
    """For cloud slots with a stated max_concurrent, dynamic_capacity
    must return max_concurrent unless we KNOW (True) that AIMD
    auto-detection is supported."""

    def test_explicit_no_auto_detect_returns_max(self):
        slot = _slot(False)
        assert slot.dynamic_capacity == 10

    def test_unknown_auto_detect_returns_max(self):
        # The Phase 136 Part 14 fix: None must behave like False, not True.
        slot = _slot(None)
        assert slot.dynamic_capacity == 10, (
            "When supports_auto_detect is unknown (None) — e.g. startup "
            "race before settings load — the user's max_concurrent must "
            "still be honored, not silently halved by AIMD jumpstart."
        )

    def test_explicit_auto_detect_returns_aimd_bound(self):
        # For providers with rate-limit headers (OpenAI / Anthropic), AIMD
        # bounding is correct.  Don't regress that behavior.
        slot = _slot(True)
        assert slot.dynamic_capacity == 5

    def test_local_slot_unaffected(self):
        # Local slots are VRAM-bound; supports_auto_detect doesn't matter.
        slot = ComputeSlot(
            node_id="local:gpu-0",
            max_concurrent=4,
            current_limit=4,
            min_limit=1,
            supports_auto_detect=None,
        )
        assert slot.dynamic_capacity == 4

    def test_cloud_zero_max_concurrent_unbounded(self):
        # max_concurrent=0 ("Auto" sentinel — unbounded discovery).
        # supports_auto_detect should not affect this branch.
        slot = ComputeSlot(
            node_id="cloud:ep",
            max_concurrent=0,
            current_limit=42,
            min_limit=1,
            supports_auto_detect=None,
        )
        assert slot.dynamic_capacity == 42

"""Phase 82 completion: cloud dispatch must go through the scheduler,
not short-circuit on a hardcoded plan-tier value.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from codrag.core import batch_profiles


def test_cloud_dispatch_does_not_return_plan_tier_constant() -> None:
    """Before fix: cloud dispatch returned PLAN_TIER_CONCURRENCY['free'] = 1.
    After fix: it routes through the scheduler and returns the discovered
    dynamic capacity.
    """
    from codrag.services.pipeline.scheduler import pipeline_scheduler

    pipeline_scheduler.configure_node("cloud:ep-test-unbounded", max_concurrent=1)
    slot = pipeline_scheduler._slots["cloud:ep-test-unbounded"]
    slot.current_limit = 40  # simulate post-discovery

    with patch.object(
        batch_profiles, "_LOCAL_PROVIDERS", set()
    ):  # force cloud classification
        concurrency = batch_profiles.get_batch_concurrency(
            provider="ollama",
            model="qwen3-coder",
            node_id="cloud:ep-test-unbounded",
        )

    assert concurrency > 1, (
        f"Cloud dispatch should reflect scheduler's discovered ceiling, "
        f"got {concurrency}. This means the PLAN_TIER early-return is still "
        f"clipping discovery at the free-tier hardcode."
    )


def test_plan_tier_helpers_are_removed() -> None:
    """The plan-tier helper fns are gone — no fallbacks, no ambiguity."""
    assert not hasattr(batch_profiles, "_get_plan_tier")
    assert not hasattr(batch_profiles, "_resolve_plan_tier_concurrency")

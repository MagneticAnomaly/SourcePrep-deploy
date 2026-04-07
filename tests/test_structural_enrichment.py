"""Tests for StructuralContext and complexity tier computation."""
import pytest

from codrag.adapters.pm_models import StructuralContext, compute_complexity_tier


def test_empty_context_is_lightweight():
    ctx = StructuralContext()
    assert compute_complexity_tier(ctx) == "lightweight"


def test_one_hub_is_standard():
    ctx = StructuralContext(
        hub_files_involved=["src/gateway.py"],
        hub_count=1,
        total_dependents=10,
    )
    assert compute_complexity_tier(ctx) == "standard"


def test_two_hubs_is_heavyweight():
    ctx = StructuralContext(
        hub_files_involved=["src/gateway.py", "src/config.py"],
        hub_count=2,
        total_dependents=30,
    )
    assert compute_complexity_tier(ctx) == "heavyweight"


def test_cross_module_is_heavyweight():
    ctx = StructuralContext(
        modules_spanned=["api_gateway", "core_config", "auth"],
        cross_module=True,
        hub_count=0,
        total_dependents=3,
    )
    assert compute_complexity_tier(ctx) == "heavyweight"


def test_high_dependents_is_heavyweight():
    ctx = StructuralContext(
        hub_count=1,
        total_dependents=25,
    )
    assert compute_complexity_tier(ctx) == "heavyweight"


def test_low_dependents_no_hubs_is_lightweight():
    ctx = StructuralContext(
        hub_count=0,
        total_dependents=2,
        modules_spanned=["core"],
        cross_module=False,
    )
    assert compute_complexity_tier(ctx) == "lightweight"

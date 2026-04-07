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


from unittest.mock import MagicMock
from codrag.adapters.push_engine import PushEngine
from codrag.services.collaboration.snapshots import GraphSnapshot


def _make_snapshot(hubs, modules):
    return GraphSnapshot(
        id="snap-1", project_id="proj-1",
        hubs=hubs, modules=modules,
        created_at=1000.0,
    )


def test_enrich_no_snapshot_returns_none():
    adapter = MagicMock()
    engine = PushEngine(adapter)
    ctx = engine._enrich_with_structural_context(
        affected_files=["src/foo.py"],
        project_id="proj-1",
    )
    assert ctx is None


def test_enrich_with_hub_files():
    adapter = MagicMock()
    snapshot_store = MagicMock()
    snapshot_store.get_latest.return_value = _make_snapshot(
        hubs=[
            {"path": "src/gateway.py", "dependents_count": 14, "rank": 2},
            {"path": "src/config.py", "dependents_count": 18, "rank": 3},
        ],
        modules=[
            {"name": "api_gateway", "files": ["src/gateway.py", "src/routes.py"]},
            {"name": "core_config", "files": ["src/config.py"]},
        ],
    )
    engine = PushEngine(adapter, snapshot_store=snapshot_store)
    ctx = engine._enrich_with_structural_context(
        affected_files=["src/gateway.py", "src/config.py"],
        project_id="proj-1",
    )
    assert ctx is not None
    assert ctx.hub_count == 2
    assert ctx.total_dependents == 32
    assert ctx.cross_module is True
    assert ctx.complexity_tier == "heavyweight"


def test_enrich_leaf_files_only():
    adapter = MagicMock()
    snapshot_store = MagicMock()
    snapshot_store.get_latest.return_value = _make_snapshot(
        hubs=[{"path": "src/gateway.py", "dependents_count": 14, "rank": 2}],
        modules=[{"name": "utils", "files": ["src/utils.py", "src/helpers.py"]}],
    )
    engine = PushEngine(adapter, snapshot_store=snapshot_store)
    ctx = engine._enrich_with_structural_context(
        affected_files=["src/utils.py"],
        project_id="proj-1",
    )
    assert ctx is not None
    assert ctx.hub_count == 0
    assert ctx.complexity_tier == "lightweight"

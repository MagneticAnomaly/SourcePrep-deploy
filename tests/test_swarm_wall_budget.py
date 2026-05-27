"""Tests for compute_swarm_wall_budget — Phase 141 (2026-05-27).

Background: The fixed 900s wall cap silently dropped 99/160 swarm
workers in production on 2026-05-26 when a full-rebuild group_reasoning
run legitimately needed ~1170s.  The helper scales the budget with
workload so this stops happening at the next growth episode.
"""
from __future__ import annotations

from prep.core.swarm_orchestrator import (
    _WALL_CEILING_S,
    _WALL_FLOOR_CLOUD_S,
    _WALL_FLOOR_LOCAL_S,
    compute_swarm_wall_budget,
)


def test_tiny_workload_hits_cloud_floor():
    """A 5-group cloud workload should get the 900s floor, not 5*80s."""
    budget = compute_swarm_wall_budget(n_items=5, concurrency=10, is_cloud=True)
    assert budget == _WALL_FLOOR_CLOUD_S


def test_tiny_workload_hits_local_floor():
    """Local floor is higher because local models serialize through ollama."""
    budget = compute_swarm_wall_budget(n_items=5, concurrency=4, is_cloud=False)
    assert budget == _WALL_FLOOR_LOCAL_S


def test_medium_cloud_workload_scales_above_floor():
    """160 groups at conc=10 needs more than the 900s floor.

    Regression target: the 2026-05-26 incident.  160 * 80s / 10 * 1.5 = 1920s
    — which must be the actual computed budget, not capped at 900s.
    """
    budget = compute_swarm_wall_budget(n_items=160, concurrency=10, is_cloud=True)
    assert budget > _WALL_FLOOR_CLOUD_S
    assert budget == 160 * 80.0 / 10 * 1.5  # 1920s


def test_huge_workload_hits_ceiling():
    """A pathological workload (1000 items) shouldn't disable the wall cap."""
    budget = compute_swarm_wall_budget(n_items=10_000, concurrency=10, is_cloud=True)
    assert budget == _WALL_CEILING_S


def test_concurrency_zero_treated_as_one():
    """Don't divide by zero — treat conc=0 as conc=1 (sequential)."""
    budget = compute_swarm_wall_budget(n_items=10, concurrency=0, is_cloud=True)
    # 10 * 80 / 1 * 1.5 = 1200, above the 900s floor
    assert budget == 10 * 80.0 / 1 * 1.5


def test_n_items_zero_treated_as_one():
    """n=0 shouldn't produce a zero-budget swarm."""
    budget = compute_swarm_wall_budget(n_items=0, concurrency=10, is_cloud=True)
    # 1 * 80 / 10 * 1.5 = 12 → clamps to floor
    assert budget == _WALL_FLOOR_CLOUD_S


def test_local_workload_uses_higher_per_worker_estimate():
    """Local per-worker estimate (120s) > cloud (80s), so same shape
    workload gets a bigger budget on local.
    """
    cloud = compute_swarm_wall_budget(n_items=200, concurrency=5, is_cloud=True)
    local = compute_swarm_wall_budget(n_items=200, concurrency=5, is_cloud=False)
    assert local > cloud
    # Local: 200 * 120 / 5 * 1.5 = 7200 → ceiling 5400
    # Cloud: 200 * 80 / 5 * 1.5 = 4800
    assert cloud == 4800.0
    assert local == _WALL_CEILING_S


def test_default_max_wall_unchanged_does_not_regress_below_floor():
    """The SwarmOrchestrator class-level default must not be below the
    cloud floor — otherwise direct instantiation without the helper
    re-introduces the 2026-05-26 regression.
    """
    from prep.core.swarm_orchestrator import SwarmOrchestrator
    assert SwarmOrchestrator.DEFAULT_MAX_WALL_TIME_S >= _WALL_FLOOR_CLOUD_S

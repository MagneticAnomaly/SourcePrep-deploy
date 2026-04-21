"""Tests for ContextTier enum and tier_from_budget."""

from __future__ import annotations

import pytest

from prep.core.context_tier import ContextTier, tier_from_budget


class TestEnumValues:
    def test_tier_1_value(self) -> None:
        assert ContextTier.TIER_1 == 1

    def test_tier_2_value(self) -> None:
        assert ContextTier.TIER_2 == 2

    def test_tier_2_5_value(self) -> None:
        assert ContextTier.TIER_2_5 == 3


class TestTierFromBudget:
    @pytest.mark.parametrize("budget", [50_000, 75_000, 40_000, 100_000])
    def test_large_budget_returns_tier_1(self, budget: int) -> None:
        assert tier_from_budget(budget) is ContextTier.TIER_1

    @pytest.mark.parametrize("budget", [30_000, 24_000, 22_000, 39_999])
    def test_medium_budget_returns_tier_2(self, budget: int) -> None:
        assert tier_from_budget(budget) is ContextTier.TIER_2

    @pytest.mark.parametrize("budget", [20_000, 15_000, 6_000, 21_999])
    def test_small_budget_returns_tier_2_5(self, budget: int) -> None:
        assert tier_from_budget(budget) is ContextTier.TIER_2_5


class TestTier1Properties:
    tier = ContextTier.TIER_1

    def test_hub_count(self) -> None:
        assert self.tier.hub_count == 10

    def test_hub_lod(self) -> None:
        assert self.tier.hub_lod == 0

    def test_hub_budget_pct(self) -> None:
        assert self.tier.hub_budget_pct == 0.55

    def test_neighbor_lod(self) -> None:
        assert self.tier.neighbor_lod == 1

    def test_neighbor_budget_pct(self) -> None:
        assert self.tier.neighbor_budget_pct == 0.25

    def test_min_score(self) -> None:
        assert self.tier.min_score == 0.15

    def test_trace_max_chars(self) -> None:
        assert self.tier.trace_max_chars == 6000

    def test_lod_full(self) -> None:
        assert self.tier.lod_full == 0.40

    def test_lod_sig(self) -> None:
        assert self.tier.lod_sig == 0.25

    def test_lod_names(self) -> None:
        assert self.tier.lod_names == 0.15

    def test_module_min_files_significant(self) -> None:
        assert self.tier.module_min_files_significant == 5

    def test_module_show_small(self) -> None:
        assert self.tier.module_show_small is True

    def test_module_show_tiny(self) -> None:
        assert self.tier.module_show_tiny is True


class TestTier2Properties:
    tier = ContextTier.TIER_2

    def test_hub_count(self) -> None:
        assert self.tier.hub_count == 6

    def test_hub_lod(self) -> None:
        assert self.tier.hub_lod == 0

    def test_hub_budget_pct(self) -> None:
        assert self.tier.hub_budget_pct == 0.50

    def test_neighbor_lod(self) -> None:
        assert self.tier.neighbor_lod == 25  # LOD 2.5

    def test_neighbor_budget_pct(self) -> None:
        assert self.tier.neighbor_budget_pct == 0.25

    def test_min_score(self) -> None:
        assert self.tier.min_score == 0.20

    def test_trace_max_chars(self) -> None:
        assert self.tier.trace_max_chars == 4000

    def test_lod_full(self) -> None:
        assert self.tier.lod_full == 0.50

    def test_lod_sig(self) -> None:
        assert self.tier.lod_sig == 0.35

    def test_lod_names(self) -> None:
        assert self.tier.lod_names == 0.20

    def test_module_min_files_significant(self) -> None:
        assert self.tier.module_min_files_significant == 5

    def test_module_show_small(self) -> None:
        assert self.tier.module_show_small is True

    def test_module_show_tiny(self) -> None:
        assert self.tier.module_show_tiny is False


class TestTier25Properties:
    tier = ContextTier.TIER_2_5

    def test_hub_count(self) -> None:
        assert self.tier.hub_count == 4

    def test_hub_lod(self) -> None:
        assert self.tier.hub_lod == 25  # LOD 2.5

    def test_hub_budget_pct(self) -> None:
        assert self.tier.hub_budget_pct == 0.45

    def test_neighbor_lod(self) -> None:
        assert self.tier.neighbor_lod == 4

    def test_neighbor_budget_pct(self) -> None:
        assert self.tier.neighbor_budget_pct == 0.20

    def test_min_score(self) -> None:
        assert self.tier.min_score == 0.25

    def test_trace_max_chars(self) -> None:
        assert self.tier.trace_max_chars == 2000

    def test_lod_full(self) -> None:
        assert self.tier.lod_full == 0.60

    def test_lod_sig(self) -> None:
        assert self.tier.lod_sig == 0.40

    def test_lod_names(self) -> None:
        assert self.tier.lod_names == 0.25

    def test_module_min_files_significant(self) -> None:
        assert self.tier.module_min_files_significant == 5

    def test_module_show_small(self) -> None:
        assert self.tier.module_show_small is False

    def test_module_show_tiny(self) -> None:
        assert self.tier.module_show_tiny is False


class TestModuleDisplayAcrossTiers:
    """Verify module display degrades gracefully across tiers."""

    def test_tier_1_shows_all(self) -> None:
        t = ContextTier.TIER_1
        assert t.module_show_small is True
        assert t.module_show_tiny is True

    def test_tier_2_hides_tiny(self) -> None:
        t = ContextTier.TIER_2
        assert t.module_show_small is True
        assert t.module_show_tiny is False

    def test_tier_2_5_hides_small_and_tiny(self) -> None:
        t = ContextTier.TIER_2_5
        assert t.module_show_small is False
        assert t.module_show_tiny is False

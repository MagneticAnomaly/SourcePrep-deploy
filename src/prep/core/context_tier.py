"""Tier-adaptive compression parameters for MCP context serving.

Different AI coding clients have different context budgets (20K–50K chars)
and model window sizes. ContextTier encapsulates per-tier parameters so the
rest of the system can adapt hub selection, LOD thresholds, neighbor fidelity,
and module display accordingly.
"""

from __future__ import annotations

from enum import IntEnum
from typing import NamedTuple


class _TierParams(NamedTuple):
    """Internal parameter bundle for a single context tier."""

    # Hub selection
    hub_count: int
    hub_lod: int
    hub_budget_pct: float

    # Neighbor context
    neighbor_lod: int
    neighbor_budget_pct: float

    # Scoring / trace
    min_score: float
    trace_max_chars: int

    # LOD thresholds (fraction of budget at which to downgrade fidelity)
    lod_full: float
    lod_sig: float
    lod_names: float

    # Module display
    module_min_files_significant: int
    module_show_small: bool
    module_show_tiny: bool


_TIER_PARAMS: dict[int, _TierParams] = {
    1: _TierParams(
        hub_count=10,
        hub_lod=0,
        hub_budget_pct=0.55,
        neighbor_lod=1,
        neighbor_budget_pct=0.25,
        min_score=0.15,
        trace_max_chars=6000,
        lod_full=0.40,
        lod_sig=0.25,
        lod_names=0.15,
        module_min_files_significant=5,
        module_show_small=True,
        module_show_tiny=True,
    ),
    2: _TierParams(
        hub_count=6,
        hub_lod=0,
        hub_budget_pct=0.50,
        neighbor_lod=25,  # LOD 2.5: sigs + docstrings, strips module constants (2-5x vs 1.2-2.7x)
        neighbor_budget_pct=0.25,
        min_score=0.20,
        trace_max_chars=4000,
        lod_full=0.50,
        lod_sig=0.35,
        lod_names=0.20,
        module_min_files_significant=5,
        module_show_small=True,
        module_show_tiny=False,
    ),
    3: _TierParams(
        hub_count=4,
        hub_lod=25,  # LOD 2.5 for hub files too — tighter budget needs better compression
        hub_budget_pct=0.45,
        neighbor_lod=4,
        neighbor_budget_pct=0.20,
        min_score=0.25,
        trace_max_chars=2000,
        lod_full=0.60,
        lod_sig=0.40,
        lod_names=0.25,
        module_min_files_significant=5,
        module_show_small=False,
        module_show_tiny=False,
    ),
}


class ContextTier(IntEnum):
    """Context compression tier keyed to client budget and model window size.

    TIER_1   — Claude/Gemini: 50K budget, 1M token windows
    TIER_2   — Cursor/Windsurf: 24–30K budget, 200–250K windows
    TIER_2_5 — Cline/Roo: 20K budget, local models
    """

    TIER_1 = 1
    TIER_2 = 2
    TIER_2_5 = 3

    # -- private helper --------------------------------------------------

    @property
    def _params(self) -> _TierParams:
        return _TIER_PARAMS[self.value]

    # -- hub selection ---------------------------------------------------

    @property
    def hub_count(self) -> int:
        """Maximum number of hub files to include."""
        return self._params.hub_count

    @property
    def hub_lod(self) -> int:
        """Default level-of-detail for hub file content (0 = full)."""
        return self._params.hub_lod

    @property
    def hub_budget_pct(self) -> float:
        """Fraction of total budget allocated to hub content."""
        return self._params.hub_budget_pct

    # -- neighbor context ------------------------------------------------

    @property
    def neighbor_lod(self) -> int:
        """Default level-of-detail for neighbor file content."""
        return self._params.neighbor_lod

    @property
    def neighbor_budget_pct(self) -> float:
        """Fraction of total budget allocated to neighbor content."""
        return self._params.neighbor_budget_pct

    # -- scoring / trace -------------------------------------------------

    @property
    def min_score(self) -> float:
        """Minimum relevance score for inclusion."""
        return self._params.min_score

    @property
    def trace_max_chars(self) -> int:
        """Character budget for trace graph summaries."""
        return self._params.trace_max_chars

    # -- LOD thresholds --------------------------------------------------

    @property
    def lod_full(self) -> float:
        """Budget-fraction threshold below which full content is used."""
        return self._params.lod_full

    @property
    def lod_sig(self) -> float:
        """Budget-fraction threshold below which signature-only is used."""
        return self._params.lod_sig

    @property
    def lod_names(self) -> float:
        """Budget-fraction threshold below which names-only is used."""
        return self._params.lod_names

    # -- module display --------------------------------------------------

    @property
    def module_min_files_significant(self) -> int:
        """Minimum file count for a module to be considered significant."""
        return self._params.module_min_files_significant

    @property
    def module_show_small(self) -> bool:
        """Whether to include small modules in the module listing."""
        return self._params.module_show_small

    @property
    def module_show_tiny(self) -> bool:
        """Whether to include tiny modules in the module listing."""
        return self._params.module_show_tiny


def tier_from_budget(max_chars: int) -> ContextTier:
    """Select the appropriate context tier based on the client's character budget.

    Args:
        max_chars: Maximum characters the client can accept.

    Returns:
        The most appropriate ContextTier for the given budget.
    """
    if max_chars >= 40_000:
        return ContextTier.TIER_1
    if max_chars >= 22_000:
        return ContextTier.TIER_2
    return ContextTier.TIER_2_5

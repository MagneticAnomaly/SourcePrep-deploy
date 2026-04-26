"""Phase 119 Phase B — base types for header-driven concurrency discovery.

Discovery adapters parse provider rate-limit headers into a normalized
``SaturationHint`` that the ``PipelineScheduler`` can consume to slow AIMD
growth proactively (before a 429 fires).

Per Phase 119 Phase B design (docs/Phase119_ConcurrencyStability/
05_Cross_Provider_Concurrency_Design.md §4.B), this layer sits BELOW the
Phase A soft cap. ``suggested_max`` from a hint is only consulted as an
additional UPPER bound on growth; the Phase A clamp at ``max_concurrent``
is never overridden upward.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol


@dataclass
class SaturationHint:
    """Predictive signal returned by header-driven discovery adapters.

    score: float in [0.0, 1.0]
        0.0 = plenty of headroom (grow freely)
        0.5 = approaching limits (slow growth)
        1.0 = at or beyond ceiling (do not grow; consider backoff)
    suggested_max: int | None
        If set, scheduler treats this as the effective ceiling for
        growth purposes. None means "no opinion; use soft cap".
    reason: str
        Human-readable explanation for logs / health view.
    """
    score: float
    suggested_max: Optional[int]
    reason: str


class DiscoveryAdapter(Protocol):
    """Protocol all per-provider header parsers implement."""

    def from_response(
        self, headers: Mapping[str, str], status: int
    ) -> SaturationHint: ...


def _clamp_score(value: float) -> float:
    """Clamp a saturation score into [0.0, 1.0]."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value

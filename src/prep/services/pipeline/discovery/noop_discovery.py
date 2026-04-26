"""Phase 119 Phase B — no-op discovery adapter.

Used by providers that do not expose predictive rate-limit headers
(Ollama Cloud, Google Gemini direct, Moonshot Kimi direct, and any
unknown provider). The Phase A soft cap is the operating ceiling for
these providers; the discovery layer must not perturb growth.
"""
from __future__ import annotations

from typing import Mapping

from .base import SaturationHint


_NOOP_REASON = "provider has no predictive headers"


class NoopDiscoveryAdapter:
    """Returns a neutral ``SaturationHint`` regardless of headers."""

    def from_response(
        self, headers: Mapping[str, str], status: int
    ) -> SaturationHint:
        return SaturationHint(score=0.0, suggested_max=None, reason=_NOOP_REASON)

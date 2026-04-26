"""Phase 119 Phase B — Anthropic header-driven saturation discovery.

Anthropic exposes the densest header set of any major provider (Phase B
design §1.3):

- ``anthropic-ratelimit-requests-limit`` / ``-remaining`` / ``-reset``
- ``anthropic-ratelimit-tokens-limit``   / ``-remaining``  (combined)
- ``anthropic-ratelimit-input-tokens-limit``  / ``-remaining`` (cache-aware)
- ``anthropic-ratelimit-output-tokens-limit`` / ``-remaining``
- ``retry-after`` on 429

Saturation score is the *worst* (smallest remaining/limit ratio) across
all observed budgets. Anthropic is a token-bucket service where short
bursts above limit are tolerated; this adapter slows growth as ANY of
the buckets approach drain so we do not race the bucket back to empty.
"""
from __future__ import annotations

from typing import Mapping, Optional

from .base import SaturationHint, _clamp_score


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _ratio(remaining: Optional[int], limit: Optional[int]) -> Optional[float]:
    """remaining / limit, clamped to [0, 1]. None when either side missing."""
    if remaining is None or limit is None or limit <= 0:
        return None
    if remaining < 0:
        remaining = 0
    if remaining > limit:
        remaining = limit
    return remaining / limit


class AnthropicDiscoveryAdapter:
    """Discovery adapter for ``provider == "anthropic"``."""

    def from_response(
        self, headers: Mapping[str, str], status: int
    ) -> SaturationHint:
        lower = {k.lower(): v for k, v in headers.items()}

        if status == 429:
            return SaturationHint(
                score=1.0,
                suggested_max=1,
                reason="anthropic 429 — rate limit exceeded; backing off to 1",
            )

        rem_req = _parse_int(lower.get("anthropic-ratelimit-requests-remaining"))
        lim_req = _parse_int(lower.get("anthropic-ratelimit-requests-limit"))
        rem_tok = _parse_int(lower.get("anthropic-ratelimit-tokens-remaining"))
        lim_tok = _parse_int(lower.get("anthropic-ratelimit-tokens-limit"))
        rem_in = _parse_int(lower.get("anthropic-ratelimit-input-tokens-remaining"))
        lim_in = _parse_int(lower.get("anthropic-ratelimit-input-tokens-limit"))
        rem_out = _parse_int(lower.get("anthropic-ratelimit-output-tokens-remaining"))
        lim_out = _parse_int(lower.get("anthropic-ratelimit-output-tokens-limit"))

        ratios = []
        for rem, lim in (
            (rem_req, lim_req),
            (rem_tok, lim_tok),
            (rem_in, lim_in),
            (rem_out, lim_out),
        ):
            r = _ratio(rem, lim)
            if r is not None:
                ratios.append(r)
        if not ratios:
            return SaturationHint(
                score=0.0,
                suggested_max=None,
                reason="anthropic headers absent — no predictive signal",
            )

        # Worst (smallest) remaining-fraction across all observed buckets.
        worst_remaining = min(ratios)
        score = _clamp_score(1.0 - worst_remaining)

        # ``suggested_max``: half of the remaining-requests budget when
        # available. Tokens-only readings do not translate cleanly to a
        # request-count ceiling, so we leave ``suggested_max`` unset in
        # that case and rely on the score to slow growth.
        suggested_max: Optional[int] = None
        if rem_req is not None and rem_req > 0:
            suggested_max = max(1, rem_req // 2)
        elif rem_req == 0:
            suggested_max = 1

        reason = (
            f"anthropic worst_remaining={worst_remaining:.2f} "
            f"req={rem_req}/{lim_req} tok={rem_tok}/{lim_tok} "
            f"in={rem_in}/{lim_in} out={rem_out}/{lim_out} score={score:.2f}"
        )
        return SaturationHint(
            score=score, suggested_max=suggested_max, reason=reason,
        )

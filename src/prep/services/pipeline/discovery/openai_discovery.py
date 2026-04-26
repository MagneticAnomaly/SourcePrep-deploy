"""Phase 119 Phase B — OpenAI header-driven saturation discovery.

OpenAI exposes per-response rate-limit headers (see Phase 119 Phase B
design §1.2):

- ``x-ratelimit-limit-requests`` / ``x-ratelimit-remaining-requests``
- ``x-ratelimit-limit-tokens``  / ``x-ratelimit-remaining-tokens``
- ``retry-after`` on 429

We translate these into a normalized ``SaturationHint``:

- ``score`` = ``1.0 - max(remaining_req_ratio, remaining_tok_ratio)``,
  picking the larger remaining-fraction so we are not pessimistic when
  one budget (requests vs tokens) is tight while the other has plenty.
  In practice OpenAI traffic is usually request-bound at small batch
  sizes and token-bound at large ones — taking the max keeps the score
  meaningful in both regimes.
- ``suggested_max`` = ``floor(remaining_requests / 2)`` — keep 50%
  headroom so sustained growth does not immediately race the budget.
  This is the documented heuristic in the Phase B spec.
- On 429, ``score = 1.0`` and ``suggested_max = 1`` (back to one
  request until the bucket refills).
"""
from __future__ import annotations

from typing import Mapping, Optional

from .base import SaturationHint, _clamp_score


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Best-effort int parse from a header value. Returns None on failure."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class OpenAIDiscoveryAdapter:
    """Discovery adapter for ``provider == "openai"``."""

    def from_response(
        self, headers: Mapping[str, str], status: int
    ) -> SaturationHint:
        # Headers are case-insensitive over HTTP, but ``Mapping[str, str]``
        # makes no guarantees. Build a lower-cased view for safe lookup.
        lower = {k.lower(): v for k, v in headers.items()}

        if status == 429:
            return SaturationHint(
                score=1.0,
                suggested_max=1,
                reason="openai 429 — rate limit exceeded; backing off to 1",
            )

        rem_req = _parse_int(lower.get("x-ratelimit-remaining-requests"))
        lim_req = _parse_int(lower.get("x-ratelimit-limit-requests"))
        rem_tok = _parse_int(lower.get("x-ratelimit-remaining-tokens"))
        lim_tok = _parse_int(lower.get("x-ratelimit-limit-tokens"))

        # If neither budget is parseable, we have no signal.
        ratios = []
        if rem_req is not None and lim_req is not None and lim_req > 0:
            ratios.append(rem_req / lim_req)
        if rem_tok is not None and lim_tok is not None and lim_tok > 0:
            ratios.append(rem_tok / lim_tok)
        if not ratios:
            return SaturationHint(
                score=0.0,
                suggested_max=None,
                reason="openai headers absent — no predictive signal",
            )

        # Take the LARGER remaining-fraction (= less saturated of the two
        # budgets). Saturation = 1 - that.
        best_remaining = max(ratios)
        score = _clamp_score(1.0 - best_remaining)

        # ``suggested_max`` heuristic: half of remaining requests. This keeps
        # 50% headroom for sustained growth without 429s. We only set it
        # when we have a concrete remaining-requests reading; the tokens
        # path alone does not directly translate to a request count.
        suggested_max: Optional[int] = None
        if rem_req is not None and rem_req > 0:
            suggested_max = max(1, rem_req // 2)
        elif rem_req == 0:
            suggested_max = 1

        reason = (
            f"openai remaining_req={rem_req} limit_req={lim_req} "
            f"remaining_tok={rem_tok} limit_tok={lim_tok} score={score:.2f}"
        )
        return SaturationHint(
            score=score, suggested_max=suggested_max, reason=reason,
        )

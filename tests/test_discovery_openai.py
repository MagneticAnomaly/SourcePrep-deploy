"""Phase 119 Phase B — OpenAI saturation hint parsing.

Validates that ``predict_saturation("openai", headers, status)`` produces
expected normalized ``SaturationHint`` values across realistic header
fixtures: low usage, mid usage, near-saturation, 429, and missing headers.
"""
from __future__ import annotations

from prep.services.pipeline.discovery import SaturationHint, predict_saturation


def _h(**kw: object) -> dict[str, str]:
    """Build a header dict with stringified values to mimic real HTTP."""
    return {k.replace("_", "-"): str(v) for k, v in kw.items()}


def test_openai_low_usage_returns_low_score() -> None:
    """Tier-1 fresh state: 5/5 requests, 30k/30k tokens. Score ~ 0."""
    headers = _h(
        **{
            "x-ratelimit-limit-requests": 500,
            "x-ratelimit-remaining-requests": 475,
            "x-ratelimit-limit-tokens": 30000,
            "x-ratelimit-remaining-tokens": 28500,
        }
    )
    hint = predict_saturation("openai", headers, 200)
    assert isinstance(hint, SaturationHint)
    assert hint.score < 0.10
    # ``suggested_max`` = floor(remaining_requests / 2).
    assert hint.suggested_max == 475 // 2


def test_openai_medium_usage_returns_mid_score() -> None:
    """~50% of one budget consumed → score around 0.5."""
    headers = _h(
        **{
            "x-ratelimit-limit-requests": 500,
            "x-ratelimit-remaining-requests": 250,
            "x-ratelimit-limit-tokens": 30000,
            "x-ratelimit-remaining-tokens": 27000,
        }
    )
    hint = predict_saturation("openai", headers, 200)
    # We take the LARGER remaining-fraction (less saturated of the two).
    # tokens has 90% remaining, so score = 1 - 0.9 = 0.10.
    assert 0.05 <= hint.score <= 0.15
    assert hint.suggested_max == 125


def test_openai_near_saturation_returns_high_score() -> None:
    """Both budgets nearly drained → score ≥ 0.85."""
    headers = _h(
        **{
            "x-ratelimit-limit-requests": 500,
            "x-ratelimit-remaining-requests": 50,
            "x-ratelimit-limit-tokens": 30000,
            "x-ratelimit-remaining-tokens": 4500,
        }
    )
    hint = predict_saturation("openai", headers, 200)
    # Larger remaining: requests at 10% → score = 1 - 0.10 = 0.90.
    assert hint.score >= 0.85
    assert hint.suggested_max == 25


def test_openai_429_returns_score_one() -> None:
    """429 → score=1.0, suggested_max=1."""
    headers = _h(
        **{
            "x-ratelimit-limit-requests": 500,
            "x-ratelimit-remaining-requests": 0,
            "retry-after": 30,
        }
    )
    hint = predict_saturation("openai", headers, 429)
    assert hint.score == 1.0
    assert hint.suggested_max == 1
    assert "429" in hint.reason


def test_openai_missing_headers_returns_neutral_hint() -> None:
    """No usable headers → score=0, suggested_max=None."""
    hint = predict_saturation("openai", {}, 200)
    assert hint.score == 0.0
    assert hint.suggested_max is None


def test_openai_score_is_clamped_to_unit_interval() -> None:
    """Defensive: weird header values must not produce out-of-range scores."""
    headers = _h(
        **{
            "x-ratelimit-limit-requests": 100,
            # Pathological — remaining > limit.
            "x-ratelimit-remaining-requests": 200,
        }
    )
    hint = predict_saturation("openai", headers, 200)
    assert 0.0 <= hint.score <= 1.0


def test_openai_zero_remaining_requests_suggests_one() -> None:
    """When remaining_requests==0 (but not 429 yet), suggested_max=1."""
    headers = _h(
        **{
            "x-ratelimit-limit-requests": 500,
            "x-ratelimit-remaining-requests": 0,
            "x-ratelimit-limit-tokens": 30000,
            "x-ratelimit-remaining-tokens": 5000,
        }
    )
    hint = predict_saturation("openai", headers, 200)
    assert hint.suggested_max == 1


def test_openai_case_insensitive_headers() -> None:
    """HTTP headers are case-insensitive; adapter must handle mixed-case."""
    headers = {
        "X-RateLimit-Limit-Requests": "500",
        "X-RateLimit-Remaining-Requests": "100",
    }
    hint = predict_saturation("openai", headers, 200)
    assert hint.suggested_max == 50
    assert hint.score == 0.8

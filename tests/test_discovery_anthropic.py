"""Phase 119 Phase B — Anthropic saturation hint parsing.

Validates the densest-header-set adapter: requests + combined tokens +
split input/output tokens. The adapter must report the WORST (most
saturated) of all observed buckets.
"""
from __future__ import annotations

from prep.services.pipeline.discovery import SaturationHint, predict_saturation


def _h(**kw: object) -> dict[str, str]:
    return {k.replace("_", "-"): str(v) for k, v in kw.items()}


def test_anthropic_low_usage_returns_low_score() -> None:
    """All four buckets at >90% remaining → score < 0.10."""
    headers = _h(
        **{
            "anthropic-ratelimit-requests-limit": 1000,
            "anthropic-ratelimit-requests-remaining": 950,
            "anthropic-ratelimit-tokens-limit": 450000,
            "anthropic-ratelimit-tokens-remaining": 440000,
            "anthropic-ratelimit-input-tokens-limit": 450000,
            "anthropic-ratelimit-input-tokens-remaining": 442000,
            "anthropic-ratelimit-output-tokens-limit": 90000,
            "anthropic-ratelimit-output-tokens-remaining": 85000,
        }
    )
    hint = predict_saturation("anthropic", headers, 200)
    assert isinstance(hint, SaturationHint)
    assert hint.score < 0.10
    assert hint.suggested_max == 475


def test_anthropic_picks_worst_bucket() -> None:
    """Output tokens nearly drained while requests fresh → score from output."""
    headers = _h(
        **{
            "anthropic-ratelimit-requests-limit": 1000,
            "anthropic-ratelimit-requests-remaining": 990,
            "anthropic-ratelimit-output-tokens-limit": 90000,
            "anthropic-ratelimit-output-tokens-remaining": 9000,  # 10% left
        }
    )
    hint = predict_saturation("anthropic", headers, 200)
    # Worst remaining = 0.10 → score = 0.90.
    assert hint.score >= 0.85
    assert hint.suggested_max == 495  # half of remaining requests


def test_anthropic_input_tokens_cache_aware_variant() -> None:
    """Cache-aware input-tokens header observed alongside combined tokens.

    Both should be considered; the adapter picks the worst (smallest)
    remaining-fraction across all buckets it can read.
    """
    headers = _h(
        **{
            "anthropic-ratelimit-requests-limit": 1000,
            "anthropic-ratelimit-requests-remaining": 800,
            # Combined token bucket is healthy (cache hits keep this high).
            "anthropic-ratelimit-tokens-remaining": 400000,
            "anthropic-ratelimit-tokens-limit": 450000,
            # But raw input-tokens bucket is tight.
            "anthropic-ratelimit-input-tokens-limit": 450000,
            "anthropic-ratelimit-input-tokens-remaining": 67500,  # 15% left
        }
    )
    hint = predict_saturation("anthropic", headers, 200)
    # Worst remaining ratio is 0.15 → score = 0.85.
    assert 0.80 <= hint.score <= 0.90
    assert hint.suggested_max == 400


def test_anthropic_429_returns_score_one() -> None:
    headers = _h(
        **{
            "anthropic-ratelimit-requests-remaining": 0,
            "retry-after": 60,
        }
    )
    hint = predict_saturation("anthropic", headers, 429)
    assert hint.score == 1.0
    assert hint.suggested_max == 1
    assert "429" in hint.reason


def test_anthropic_missing_headers_returns_neutral_hint() -> None:
    hint = predict_saturation("anthropic", {}, 200)
    assert hint.score == 0.0
    assert hint.suggested_max is None


def test_anthropic_partial_headers_still_useful() -> None:
    """Requests-only response (e.g. token headers absent) still yields a
    saturation read from the requests bucket."""
    headers = _h(
        **{
            "anthropic-ratelimit-requests-limit": 1000,
            "anthropic-ratelimit-requests-remaining": 200,  # 20% left
        }
    )
    hint = predict_saturation("anthropic", headers, 200)
    assert 0.75 <= hint.score <= 0.85
    assert hint.suggested_max == 100


def test_anthropic_score_clamped() -> None:
    """Pathological header values must not break the [0, 1] invariant."""
    headers = _h(
        **{
            "anthropic-ratelimit-requests-limit": 100,
            "anthropic-ratelimit-requests-remaining": -5,
        }
    )
    hint = predict_saturation("anthropic", headers, 200)
    assert 0.0 <= hint.score <= 1.0


def test_anthropic_case_insensitive_headers() -> None:
    headers = {
        "Anthropic-RateLimit-Requests-Limit": "1000",
        "Anthropic-RateLimit-Requests-Remaining": "100",
    }
    hint = predict_saturation("anthropic", headers, 200)
    assert hint.suggested_max == 50
    assert 0.85 <= hint.score <= 0.95

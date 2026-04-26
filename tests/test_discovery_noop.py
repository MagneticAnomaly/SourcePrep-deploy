"""Phase 119 Phase B — providers without predictive headers route to no-op.

The Phase A soft cap is the operating ceiling for these providers; the
discovery layer must return a neutral ``SaturationHint`` that does not
perturb scheduler growth.
"""
from __future__ import annotations

import pytest

from prep.services.pipeline.discovery import SaturationHint, predict_saturation


@pytest.mark.parametrize(
    "provider",
    ["ollama", "ollama_cloud", "google", "gemini", "kimi", "moonshot",
     "azure-openai", "unknown_provider", "", "OpenRouter"],
)
def test_noop_returns_neutral_hint(provider: str) -> None:
    hint = predict_saturation(provider, {"x-ratelimit-limit-requests": "500"}, 200)
    assert isinstance(hint, SaturationHint)
    assert hint.score == 0.0
    assert hint.suggested_max is None
    assert "no predictive headers" in hint.reason


def test_noop_ignores_429_status() -> None:
    """No-op adapter does not react to 429 either — scheduler still has its
    own 429 path via ``is_429_or_timeout`` in ``_record_throughput``."""
    hint = predict_saturation("ollama_cloud", {"retry-after": "30"}, 429)
    assert hint.score == 0.0
    assert hint.suggested_max is None


def test_noop_ignores_headers() -> None:
    """Even if Ollama starts surfacing OpenAI-style headers in some future
    release, the dispatch table still routes ``ollama`` to no-op until we
    ship a real adapter for it."""
    headers = {
        "x-ratelimit-limit-requests": "10",
        "x-ratelimit-remaining-requests": "0",
    }
    hint = predict_saturation("ollama", headers, 200)
    assert hint.score == 0.0


def test_noop_handles_none_headers() -> None:
    """Defensive: predict_saturation must accept None gracefully."""
    hint = predict_saturation("unknown", None, 200)  # type: ignore[arg-type]
    assert hint.score == 0.0


def test_noop_handles_zero_status() -> None:
    """Defensive: ``status=0`` (e.g. connection error before HTTP) routes
    to default 200-style handling rather than crashing."""
    hint = predict_saturation("ollama", {}, 0)
    assert hint.score == 0.0

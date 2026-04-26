"""Phase 119 Phase B — per-provider header-driven concurrency discovery.

Public API:
    from prep.services.pipeline.discovery import predict_saturation, SaturationHint

``predict_saturation(provider, headers, status)`` dispatches to the
provider-specific adapter and returns a normalized ``SaturationHint``.
Unknown providers (and providers without predictive headers — Ollama
Cloud, Gemini, Kimi direct) get a no-op hint that keeps the Phase A
soft cap as the operating ceiling.

See ``base.SaturationHint`` for the wire shape and
``docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md``
for the full design.
"""
from __future__ import annotations

from typing import Mapping

from .base import DiscoveryAdapter, SaturationHint
from .anthropic_discovery import AnthropicDiscoveryAdapter
from .noop_discovery import NoopDiscoveryAdapter
from .openai_discovery import OpenAIDiscoveryAdapter

__all__ = [
    "DiscoveryAdapter",
    "SaturationHint",
    "predict_saturation",
]


_NOOP = NoopDiscoveryAdapter()
_OPENAI = OpenAIDiscoveryAdapter()
_ANTHROPIC = AnthropicDiscoveryAdapter()

# Providers that carry predictive headers worth parsing. Anything not
# listed (ollama, ollama_cloud, google, gemini, kimi, moonshot, azure-*,
# unknown) routes to the no-op adapter and relies on Phase A's soft cap.
_ADAPTERS: dict[str, DiscoveryAdapter] = {
    "openai": _OPENAI,
    "anthropic": _ANTHROPIC,
}


def predict_saturation(
    provider: str,
    headers: Mapping[str, str],
    status: int,
) -> SaturationHint:
    """Dispatch to the provider-specific discovery adapter.

    ``provider`` is normalized to lower-case before lookup so callers
    can pass either canonical (``"openai"``) or legacy (``"OpenAI"``)
    forms. Unknown providers return the no-op hint.
    """
    key = (provider or "").strip().lower()
    adapter = _ADAPTERS.get(key, _NOOP)
    return adapter.from_response(headers or {}, status if status else 200)

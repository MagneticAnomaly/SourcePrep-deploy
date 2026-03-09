"""
EA-H4: Cost estimation engine.

Maps token counts to dollar estimates based on model pricing.
Used by the Usage & Stress tab in the Enterprise Admin panel
and budget enforcement (EA-H5).

Pricing data is approximate and updated periodically. Enterprise
customers may override these with their negotiated rates.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# ── Model pricing (per 1M tokens, USD) ────────────────────────
# Source: Provider pricing pages as of March 2026
# Format: (input_price_per_1M, output_price_per_1M)

MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "o4-mini": (1.10, 4.40),
    "o3": (10.00, 40.00),
    "o3-mini": (1.10, 4.40),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "gpt-4-turbo": (10.00, 30.00),

    # Anthropic
    "claude-4.6-sonnet": (5.00, 25.00),
    "claude-4.5-haiku": (0.50, 2.50),
    "claude-3.5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-opus": (15.00, 75.00),

    # Google Gemini
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-3-pro-preview": (1.25, 5.00),
    "gemini-3-flash-preview": (0.075, 0.30),

    # Local models (free)
    # Not listed — cost is always $0 for ollama/lm-studio
}

# Prefix fallbacks for model variants not explicitly listed
_PRICING_PREFIXES = [
    ("gpt-4.1-mini", (0.40, 1.60)),
    ("gpt-4.1-nano", (0.10, 0.40)),
    ("gpt-4.1", (2.00, 8.00)),
    ("gpt-4o-mini", (0.15, 0.60)),
    ("gpt-4o", (2.50, 10.00)),
    ("o4-mini", (1.10, 4.40)),
    ("o3-mini", (1.10, 4.40)),
    ("o1-mini", (3.00, 12.00)),
    ("claude-4.6", (5.00, 25.00)),
    ("claude-4.5-haiku", (0.50, 2.50)),
    ("claude-3.5-sonnet", (3.00, 15.00)),
    ("claude-3.5-haiku", (0.80, 4.00)),
    ("claude-3-haiku", (0.25, 1.25)),
    ("claude-3-opus", (15.00, 75.00)),
    ("gemini-2.5-pro", (1.25, 5.00)),
    ("gemini-2.5-flash", (0.075, 0.30)),
    ("gemini-2.0-flash", (0.075, 0.30)),
    ("gemini-1.5-pro", (1.25, 5.00)),
    ("gemini-1.5-flash", (0.075, 0.30)),
    ("gemini-3-pro", (1.25, 5.00)),
    ("gemini-3-flash", (0.075, 0.30)),
]

# Local providers — always $0
LOCAL_PROVIDERS = {"ollama", "lm-studio"}


def get_model_pricing(model: str, provider: str = "") -> Optional[Tuple[float, float]]:
    """Look up pricing for a model. Returns (input_per_1M, output_per_1M) or None.

    Local providers always return (0, 0). Cloud models use exact match
    then prefix fallback.
    """
    if provider in LOCAL_PROVIDERS:
        return (0.0, 0.0)

    # Exact match
    pricing = MODEL_PRICING.get(model)
    if pricing:
        return pricing

    # Prefix fallback (handles versioned model names like gpt-4o-2024-08-06)
    model_lower = model.lower()
    for prefix, price in _PRICING_PREFIXES:
        if model_lower.startswith(prefix):
            return price

    return None


def estimate_cost(
    tokens: int,
    model: str,
    provider: str = "",
    input_ratio: float = 0.8,
) -> Dict[str, Any]:
    """Estimate the dollar cost of a token usage.

    Args:
        tokens: Total tokens used (input + output combined)
        model: Model name
        provider: Provider name (used to detect local models)
        input_ratio: Assumed ratio of input tokens to total (default 80%)

    Returns:
        {
            "estimated_cost_usd": 0.0035,
            "model": "gemini-2.5-flash",
            "tokens": 1500,
            "pricing_found": True,
            "input_price_per_1M": 0.075,
            "output_price_per_1M": 0.30,
        }
    """
    pricing = get_model_pricing(model, provider)

    if pricing is None:
        return {
            "estimated_cost_usd": None,
            "model": model,
            "tokens": tokens,
            "pricing_found": False,
        }

    input_price, output_price = pricing
    input_tokens = int(tokens * input_ratio)
    output_tokens = tokens - input_tokens

    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price

    return {
        "estimated_cost_usd": round(cost, 6),
        "model": model,
        "tokens": tokens,
        "pricing_found": True,
        "input_price_per_1M": input_price,
        "output_price_per_1M": output_price,
    }


def estimate_usage_cost(usage: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate total cost from a get_token_usage() result.

    Takes the output of AuditLog.get_token_usage() and adds cost estimates.
    """
    by_model = usage.get("by_model", {})
    total_cost = 0.0
    model_costs: Dict[str, float] = {}
    unknown_models: list = []

    for model, tokens in by_model.items():
        est = estimate_cost(tokens, model)
        if est["pricing_found"]:
            cost = est["estimated_cost_usd"]
            total_cost += cost
            model_costs[model] = cost
        else:
            unknown_models.append(model)

    return {
        "total_estimated_cost_usd": round(total_cost, 4),
        "by_model": model_costs,
        "unknown_models": unknown_models,
        "total_tokens": usage.get("total_tokens", 0),
        "call_count": usage.get("call_count", 0),
    }

"""Dynamic Swarm batching & concurrency optimizer.

Centralizes quality/throughput constants for the three Swarm phases:
- Phase 1 (Coordinator): Gemini — one JSON planning call
- Phase 2 (Workers): Kimi — deep per-file reasoning, fan-out
- Phase 3 (Synthesis): Gemini — large-context aggregation

See docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md §7 for the rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Literal

# ── Kimi (Worker) ──────────────────────────────────────────────────
# Per-file attention lever.  Beyond ~10 items per prompt, thinking-
# preamble attention dilutes and JSON schemas degrade regardless of
# context window size.
KIMI_MAX_BATCH: int = 10

# ── Gemini (Coordinator + Synthesis) ───────────────────────────────
# Item-count cap protects against degenerate cases (many tiny outputs
# packing into one call but blowing item-wise attention).
GEMINI_MAX_BATCH_ITEMS: int = 200

# Payload cap where Gemini 3 Flash cross-reference attention stays
# sharp.  Primary quality lever for Phase 3 synthesis.
GEMINI_ATTENTION_QUALITY_CEILING_TOKENS: int = 200_000

# Hard safety cap at 80% of 1M window — leaves headroom for system
# prompt + generated output.
GEMINI_HARD_CONTEXT_TOKENS: int = 800_000

# ── Plan tier concurrency ──────────────────────────────────────────
# Ollama Cloud per-plan concurrent-model limits.
PlanTier = Literal["free", "pro", "max"]
PLAN_TIER_CONCURRENCY: dict[str, int] = {
    "free": 1,
    "pro": 3,
    "max": 10,
}


@dataclass(frozen=True)
class SwarmConfig:
    """Runtime swarm configuration for one phase."""

    role: str  # "coordinator" | "worker" | "synthesis"
    concurrency: int  # max parallel calls
    batch_size: int  # items per call
    expected_waves: int = 1  # worker-only: concurrency-dependent waves
    expected_calls: int = 1  # synthesis-only: sequential calls


def get_optimal_swarm_config(
    role: Literal["coordinator", "worker", "synthesis"],
    plan_tier: str,
    total_items: int,
    avg_item_tokens: int = 1_000,
) -> SwarmConfig:
    """Return the optimal (concurrency, batch_size) for a swarm phase.

    Quality-first: smaller batches keep per-item attention sharp.
    Throughput is the secondary optimizer only for the Worker role.

    Args:
        role: Which swarm phase (coordinator | worker | synthesis).
        plan_tier: Ollama Cloud plan ("free" | "pro" | "max").
        total_items: Number of items to process in this phase.
        avg_item_tokens: Mean tokens per item (used for synthesis payload
                         sizing).

    Raises:
        ValueError: if plan_tier is not a recognized tier.
    """
    if plan_tier not in PLAN_TIER_CONCURRENCY:
        raise ValueError(
            f"Unknown plan_tier '{plan_tier}'. "
            f"Expected one of: {sorted(PLAN_TIER_CONCURRENCY)}"
        )
    max_concurrency = PLAN_TIER_CONCURRENCY[plan_tier]

    if role == "worker":
        concurrency = max_concurrency
        batch_size = KIMI_MAX_BATCH
        prompts_needed = ceil(total_items / batch_size) if total_items > 0 else 0
        waves = ceil(prompts_needed / concurrency) if prompts_needed > 0 else 0
        return SwarmConfig(
            role="worker",
            concurrency=concurrency,
            batch_size=batch_size,
            expected_waves=waves,
        )

    if role in ("synthesis", "coordinator"):
        # Coordinator is always a single call over all items;
        # synthesis may split at the quality ceiling.
        token_cap_batch = GEMINI_ATTENTION_QUALITY_CEILING_TOKENS // max(
            avg_item_tokens, 1
        )
        batch_size = min(
            GEMINI_MAX_BATCH_ITEMS, token_cap_batch, total_items or 1
        )
        if role == "coordinator":
            # Coordinator ingests summaries and returns a plan — always
            # 1 call.
            return SwarmConfig(
                role="coordinator",
                concurrency=1,
                batch_size=total_items,
                expected_calls=1,
            )
        calls = ceil(total_items / batch_size) if total_items > 0 else 0
        return SwarmConfig(
            role="synthesis",
            concurrency=1,
            batch_size=batch_size,
            expected_calls=calls,
        )

    raise ValueError(f"Unknown role '{role}'")

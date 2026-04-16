"""Dynamic Swarm batching & concurrency optimizer.

Centralizes quality/throughput constants for the three Swarm phases:
- Phase 1 (Coordinator): Gemini — one JSON planning call
- Phase 2 (Workers): Kimi — deep per-file reasoning, fan-out
- Phase 3 (Synthesis): Gemini — large-context aggregation

See docs/Phase112_Gemini/SWARM_UI_PLAN_v2.md §7 for the rationale.
"""
from __future__ import annotations

from typing import Dict, Literal

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
PLAN_TIER_CONCURRENCY: Dict[str, int] = {
    "free": 1,
    "pro": 3,
    "max": 10,
}

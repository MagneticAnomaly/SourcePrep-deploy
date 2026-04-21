"""Dynamic Swarm batching & concurrency constants.

Centralizes quality/throughput constants for the three Swarm phases:
- Phase 1 (Coordinator): Gemini — one JSON planning call
- Phase 2 (Workers): Kimi — deep per-file reasoning, fan-out
- Phase 3 (Synthesis): Gemini — large-context aggregation

Concurrency is no longer computed here. Phase 82 replaced the
hardcoded ``PLAN_TIER_CONCURRENCY`` mapping with AIMD-discovered
capacity in ``pipeline_scheduler`` — callers read ``full_budget_for_swarm``
or ``available_batch_workers`` instead.

See docs/Phase82_CloudPipelineConcurrency/05_Completion_Plan.md.
"""
from __future__ import annotations

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

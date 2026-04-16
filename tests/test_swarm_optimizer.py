from codrag.core.swarm_optimizer import (
    KIMI_MAX_BATCH,
    GEMINI_MAX_BATCH_ITEMS,
    GEMINI_ATTENTION_QUALITY_CEILING_TOKENS,
    GEMINI_HARD_CONTEXT_TOKENS,
    PLAN_TIER_CONCURRENCY,
)


def test_constants_match_spec():
    assert KIMI_MAX_BATCH == 10
    assert GEMINI_MAX_BATCH_ITEMS == 200
    assert GEMINI_ATTENTION_QUALITY_CEILING_TOKENS == 200_000
    assert GEMINI_HARD_CONTEXT_TOKENS == 800_000
    assert PLAN_TIER_CONCURRENCY == {"free": 1, "pro": 3, "max": 10}

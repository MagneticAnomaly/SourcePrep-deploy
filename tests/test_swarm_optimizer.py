from codrag.core.swarm_optimizer import (
    GEMINI_ATTENTION_QUALITY_CEILING_TOKENS,
    GEMINI_HARD_CONTEXT_TOKENS,
    GEMINI_MAX_BATCH_ITEMS,
    KIMI_MAX_BATCH,
    PLAN_TIER_CONCURRENCY,
    get_optimal_swarm_config,
)


def test_constants_match_spec():
    assert KIMI_MAX_BATCH == 10
    assert GEMINI_MAX_BATCH_ITEMS == 200
    assert GEMINI_ATTENTION_QUALITY_CEILING_TOKENS == 200_000
    assert GEMINI_HARD_CONTEXT_TOKENS == 800_000
    assert PLAN_TIER_CONCURRENCY == {"free": 1, "pro": 3, "max": 10}


def test_worker_max_plan_155_groups():
    cfg = get_optimal_swarm_config(role="worker", plan_tier="max", total_items=155)
    assert cfg.concurrency == 10
    assert cfg.batch_size == 10
    # 155 items / (10 conc × 10 batch) = 2 waves
    assert cfg.expected_waves == 2


def test_worker_pro_plan_155_groups():
    cfg = get_optimal_swarm_config(role="worker", plan_tier="pro", total_items=155)
    assert cfg.concurrency == 3
    assert cfg.batch_size == 10
    # 16 prompts / 3 conc = 6 waves (5 waves of 3 + 1 wave of 1)
    assert cfg.expected_waves == 6


def test_worker_free_plan_100_items():
    cfg = get_optimal_swarm_config(role="worker", plan_tier="free", total_items=100)
    assert cfg.concurrency == 1
    assert cfg.batch_size == 10
    # 10 prompts / 1 conc = 10 waves
    assert cfg.expected_waves == 10


def test_synthesis_small_payload_single_call():
    cfg = get_optimal_swarm_config(
        role="synthesis", plan_tier="max", total_items=155,
        avg_item_tokens=1000,
    )
    assert cfg.concurrency == 1
    # 200K ceiling / 1000 tokens = 200; 155 < 200 → 155 items/call
    assert cfg.batch_size == 155
    assert cfg.expected_calls == 1


def test_synthesis_large_payload_splits():
    cfg = get_optimal_swarm_config(
        role="synthesis", plan_tier="max", total_items=602,
        avg_item_tokens=1000,
    )
    # 200 items per call (quality ceiling) → 4 calls (3x200 + 1x2, rounds to 4)
    assert cfg.batch_size == 200
    assert cfg.expected_calls == 4  # ceil(602 / 200)


def test_synthesis_respects_item_cap_at_high_density():
    # Tiny outputs (100 tokens) would pack 2000/call by token math,
    # but the item cap holds at 200.
    cfg = get_optimal_swarm_config(
        role="synthesis", plan_tier="max", total_items=500,
        avg_item_tokens=100,
    )
    assert cfg.batch_size == 200


def test_coordinator_always_one_call():
    cfg = get_optimal_swarm_config(
        role="coordinator", plan_tier="max", total_items=155,
        avg_item_tokens=500,
    )
    assert cfg.concurrency == 1
    assert cfg.expected_calls == 1


def test_unknown_plan_tier_raises():
    import pytest
    with pytest.raises(ValueError, match="plan_tier"):
        get_optimal_swarm_config(role="worker", plan_tier="enterprise", total_items=10)

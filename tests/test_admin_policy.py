"""Tests for AdminPolicy parsing and enforcement utilities in team_config.py."""

import pytest

from prep.core.team_config import (
    AdminPolicy,
    BudgetPolicy,
    DataPolicy,
    ModelPolicy,
    NetworkPolicy,
    ProviderPolicy,
    SyncPolicy,
    check_policy_violation,
    filter_models_by_policy,
    is_model_allowed,
    is_provider_allowed,
    parse_admin_policy,
)


# ── Fixtures ──────────────────────────────────────────────────


def _make_policy(**overrides) -> AdminPolicy:
    """Helper to build an AdminPolicy with specific overrides."""
    defaults = {
        "provider": ProviderPolicy(),
        "model": ModelPolicy(),
        "data": DataPolicy(),
        "sync": SyncPolicy(),
        "network": NetworkPolicy(),
        "budgets": BudgetPolicy(),
        "enforcement_mode": "suggest",
    }
    defaults.update(overrides)
    return AdminPolicy(**defaults)


FULL_CONFIG = {
    "format_version": 1,
    "admin_policy": {
        "enforcement_mode": "enforce",
        "provider": {
            "allowed_providers": ["ollama", "openai"],
            "blocked_providers": ["anthropic"],
            "allow_local_providers": True,
            "allow_user_endpoints": False,
            "locked_endpoints": [
                {"name": "Corp OpenAI", "provider": "openai", "url": "https://api.openai.com/v1"}
            ],
        },
        "model": {
            "allowed_models": ["qwen3", "gpt-4o"],
            "blocked_models": ["llama2"],
            "require_approved_models": True,
        },
        "data": {
            "never_send_globs": ["*.key", "secrets/**"],
            "redact_patterns": [r"sk-[a-zA-Z0-9]{20,}"],
            "block_unapproved_cloud": True,
            "allowed_destinations": ["openai"],
        },
        "sync": {
            "require_s3_https": True,
            "allowed_s3_endpoints": ["https://s3.us-east-1.amazonaws.com"],
        },
        "network": {
            "block_metadata_endpoints": True,
            "allowed_ports": [11434, 1234],
        },
        "budgets": {
            "monthly_token_limit": 1000000,
            "monthly_cost_limit_usd": 50.0,
            "alert_threshold_percent": 0.8,
        },
    },
}


# ── parse_admin_policy tests ──────────────────────────────────


class TestParseAdminPolicy:
    def test_empty_config_returns_defaults(self):
        policy = parse_admin_policy({})
        assert policy.enforcement_mode == "suggest"
        assert policy.provider.allow_local_providers is True
        assert policy.provider.allow_user_endpoints is True
        assert policy.model.require_approved_models is False

    def test_no_admin_policy_key(self):
        policy = parse_admin_policy({"format_version": 1})
        assert policy.enforcement_mode == "suggest"

    def test_full_config_parsed(self):
        policy = parse_admin_policy(FULL_CONFIG)
        assert policy.enforcement_mode == "enforce"
        assert policy.provider.allowed_providers == ["ollama", "openai"]
        assert policy.provider.blocked_providers == ["anthropic"]
        assert policy.provider.allow_local_providers is True
        assert policy.provider.allow_user_endpoints is False
        assert len(policy.provider.locked_endpoints) == 1
        assert policy.provider.locked_endpoints[0]["name"] == "Corp OpenAI"

    def test_model_policy_parsed(self):
        policy = parse_admin_policy(FULL_CONFIG)
        assert policy.model.allowed_models == ["qwen3", "gpt-4o"]
        assert policy.model.blocked_models == ["llama2"]
        assert policy.model.require_approved_models is True

    def test_data_policy_parsed(self):
        policy = parse_admin_policy(FULL_CONFIG)
        assert policy.data.never_send_globs == ["*.key", "secrets/**"]
        assert len(policy.data.redact_patterns) == 1
        assert policy.data.block_unapproved_cloud is True
        assert policy.data.allowed_destinations == ["openai"]

    def test_sync_policy_parsed(self):
        policy = parse_admin_policy(FULL_CONFIG)
        assert policy.sync.require_s3_https is True
        assert len(policy.sync.allowed_s3_endpoints) == 1

    def test_network_policy_parsed(self):
        policy = parse_admin_policy(FULL_CONFIG)
        assert policy.network.block_metadata_endpoints is True
        assert policy.network.allowed_ports == [11434, 1234]

    def test_budget_policy_parsed(self):
        policy = parse_admin_policy(FULL_CONFIG)
        assert policy.budgets.monthly_token_limit == 1000000
        assert policy.budgets.monthly_cost_limit_usd == 50.0
        assert policy.budgets.alert_threshold_percent == 0.8

    def test_invalid_enforcement_mode_defaults_to_suggest(self):
        config = {"admin_policy": {"enforcement_mode": "invalid"}}
        policy = parse_admin_policy(config)
        assert policy.enforcement_mode == "suggest"

    def test_admin_policy_not_dict(self):
        policy = parse_admin_policy({"admin_policy": "string"})
        assert policy.enforcement_mode == "suggest"

    def test_missing_sub_sections(self):
        config = {"admin_policy": {"enforcement_mode": "enforce"}}
        policy = parse_admin_policy(config)
        assert policy.enforcement_mode == "enforce"
        assert policy.provider.allowed_providers == []
        assert policy.model.allowed_models == []

    def test_to_dict_roundtrip(self):
        policy = parse_admin_policy(FULL_CONFIG)
        d = policy.to_dict()
        assert isinstance(d, dict)
        assert d["enforcement_mode"] == "enforce"
        assert d["provider"]["allowed_providers"] == ["ollama", "openai"]
        assert d["budgets"]["monthly_token_limit"] == 1000000

    def test_non_string_items_filtered(self):
        config = {"admin_policy": {"provider": {"allowed_providers": ["ollama", 123, None, "openai"]}}}
        policy = parse_admin_policy(config)
        assert policy.provider.allowed_providers == ["ollama", "openai"]

    def test_empty_string_items_filtered(self):
        config = {"admin_policy": {"provider": {"allowed_providers": ["ollama", "", "  ", "openai"]}}}
        policy = parse_admin_policy(config)
        assert policy.provider.allowed_providers == ["ollama", "openai"]


# ── is_provider_allowed tests ─────────────────────────────────


class TestIsProviderAllowed:
    def test_default_policy_allows_all(self):
        policy = _make_policy()
        assert is_provider_allowed("ollama", policy) is True
        assert is_provider_allowed("openai", policy) is True
        assert is_provider_allowed("anthropic", policy) is True

    def test_local_providers_always_allowed(self):
        policy = _make_policy(
            provider=ProviderPolicy(allowed_providers=["openai"], allow_local_providers=True)
        )
        assert is_provider_allowed("ollama", policy) is True
        assert is_provider_allowed("lm-studio", policy) is True

    def test_local_providers_blocked_when_disabled(self):
        policy = _make_policy(
            provider=ProviderPolicy(allowed_providers=["openai"], allow_local_providers=False)
        )
        assert is_provider_allowed("ollama", policy) is False

    def test_allowlist_filters(self):
        policy = _make_policy(
            provider=ProviderPolicy(allowed_providers=["openai", "anthropic"])
        )
        assert is_provider_allowed("openai", policy) is True
        assert is_provider_allowed("anthropic", policy) is True
        assert is_provider_allowed("google", policy) is False

    def test_blocklist_overrides(self):
        policy = _make_policy(
            provider=ProviderPolicy(blocked_providers=["anthropic"])
        )
        assert is_provider_allowed("anthropic", policy) is False
        assert is_provider_allowed("openai", policy) is True

    def test_case_insensitive(self):
        policy = _make_policy(
            provider=ProviderPolicy(allowed_providers=["OpenAI"])
        )
        assert is_provider_allowed("openai", policy) is True
        assert is_provider_allowed("OPENAI", policy) is True

    def test_blocklist_wins_over_allowlist(self):
        policy = _make_policy(
            provider=ProviderPolicy(
                allowed_providers=["openai", "anthropic"],
                blocked_providers=["anthropic"],
            )
        )
        assert is_provider_allowed("anthropic", policy) is False

    def test_empty_lists_allow_all(self):
        policy = _make_policy(
            provider=ProviderPolicy(allowed_providers=[], blocked_providers=[])
        )
        assert is_provider_allowed("anything", policy) is True


# ── is_model_allowed tests ────────────────────────────────────


class TestIsModelAllowed:
    def test_default_policy_allows_all(self):
        policy = _make_policy()
        assert is_model_allowed("qwen3:8b", policy) is True
        assert is_model_allowed("anything", policy) is True

    def test_blocklist_blocks(self):
        policy = _make_policy(
            model=ModelPolicy(blocked_models=["llama2"])
        )
        assert is_model_allowed("llama2:7b", policy) is False
        assert is_model_allowed("llama2", policy) is False
        assert is_model_allowed("qwen3:8b", policy) is True

    def test_require_approved_models(self):
        policy = _make_policy(
            model=ModelPolicy(
                allowed_models=["qwen3", "gpt-4o"],
                require_approved_models=True,
            )
        )
        assert is_model_allowed("qwen3:8b", policy) is True
        assert is_model_allowed("qwen3", policy) is True
        assert is_model_allowed("gpt-4o", policy) is True
        assert is_model_allowed("llama3:8b", policy) is False

    def test_non_strict_allows_unlisted(self):
        policy = _make_policy(
            model=ModelPolicy(
                allowed_models=["qwen3"],
                require_approved_models=False,
            )
        )
        assert is_model_allowed("llama3:8b", policy) is True

    def test_case_insensitive_blocklist(self):
        policy = _make_policy(
            model=ModelPolicy(blocked_models=["LLaMA2"])
        )
        assert is_model_allowed("llama2:7b", policy) is False

    def test_prefix_matching_for_blocklist(self):
        policy = _make_policy(
            model=ModelPolicy(blocked_models=["llama"])
        )
        assert is_model_allowed("llama2:7b", policy) is False
        assert is_model_allowed("llama3:70b", policy) is False
        assert is_model_allowed("qwen3:8b", policy) is True

    def test_empty_allowlist_with_require_still_blocks(self):
        policy = _make_policy(
            model=ModelPolicy(allowed_models=[], require_approved_models=True)
        )
        # Empty allowlist + require = allow all (no list to check against)
        assert is_model_allowed("anything", policy) is True


# ── filter_models_by_policy tests ─────────────────────────────


class TestFilterModelsByPolicy:
    def test_no_restrictions(self):
        policy = _make_policy()
        models = ["qwen3:8b", "llama2:7b", "gpt-4o"]
        assert filter_models_by_policy(models, policy) == models

    def test_blocklist_filters(self):
        policy = _make_policy(
            model=ModelPolicy(blocked_models=["llama2"])
        )
        models = ["qwen3:8b", "llama2:7b", "gpt-4o"]
        assert filter_models_by_policy(models, policy) == ["qwen3:8b", "gpt-4o"]

    def test_require_approved_filters(self):
        policy = _make_policy(
            model=ModelPolicy(
                allowed_models=["qwen3", "gpt-4o"],
                require_approved_models=True,
            )
        )
        models = ["qwen3:8b", "llama2:7b", "gpt-4o", "mistral:7b"]
        assert filter_models_by_policy(models, policy) == ["qwen3:8b", "gpt-4o"]

    def test_empty_list(self):
        policy = _make_policy()
        assert filter_models_by_policy([], policy) == []


# ── check_policy_violation tests ──────────────────────────────


class TestCheckPolicyViolation:
    def test_no_violation(self):
        policy = _make_policy()
        allowed, reason = check_policy_violation("test", policy, provider="openai")
        assert allowed is True
        assert reason == ""

    def test_suggest_mode_allows_but_reports(self):
        policy = _make_policy(
            enforcement_mode="suggest",
            provider=ProviderPolicy(allowed_providers=["openai"]),
        )
        allowed, reason = check_policy_violation("test", policy, provider="anthropic")
        assert allowed is True
        assert "not allowed" in reason

    def test_enforce_mode_blocks(self):
        policy = _make_policy(
            enforcement_mode="enforce",
            provider=ProviderPolicy(allowed_providers=["openai"]),
        )
        allowed, reason = check_policy_violation("test", policy, provider="anthropic")
        assert allowed is False
        assert "not allowed" in reason

    def test_model_violation(self):
        policy = _make_policy(
            enforcement_mode="enforce",
            model=ModelPolicy(blocked_models=["llama2"]),
        )
        allowed, reason = check_policy_violation("test", policy, model="llama2:7b")
        assert allowed is False
        assert "not allowed" in reason

    def test_both_provider_and_model_violation(self):
        policy = _make_policy(
            enforcement_mode="enforce",
            provider=ProviderPolicy(allowed_providers=["openai"]),
            model=ModelPolicy(blocked_models=["llama2"]),
        )
        allowed, reason = check_policy_violation(
            "test", policy, provider="anthropic", model="llama2:7b"
        )
        assert allowed is False
        assert "Provider" in reason
        assert "Model" in reason

    def test_no_checks_when_none_provided(self):
        policy = _make_policy(enforcement_mode="enforce")
        allowed, reason = check_policy_violation("test", policy)
        assert allowed is True
        assert reason == ""

    def test_suggest_mode_with_model(self):
        policy = _make_policy(
            enforcement_mode="suggest",
            model=ModelPolicy(blocked_models=["llama2"]),
        )
        allowed, reason = check_policy_violation("test", policy, model="llama2:7b")
        assert allowed is True
        assert "not allowed" in reason

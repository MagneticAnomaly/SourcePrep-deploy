"""Tests for swarm model registry."""
import pytest
from prep.core.swarm_registry import SwarmTier, get_swarm_tier, get_min_groups_threshold


class TestSwarmTier:
    def test_coordinator_can_coordinate(self):
        assert SwarmTier.COORDINATOR.can_coordinate is True

    def test_both_can_coordinate(self):
        assert SwarmTier.BOTH.can_coordinate is True

    def test_worker_cannot_coordinate(self):
        assert SwarmTier.WORKER.can_coordinate is False

    def test_unsuitable_cannot_coordinate(self):
        assert SwarmTier.UNSUITABLE.can_coordinate is False


class TestGetSwarmTier:
    def test_kimi_via_ollama(self):
        assert get_swarm_tier("ollama", "kimi-k2.5:cloud") == SwarmTier.BOTH

    def test_kimi_case_insensitive(self):
        assert get_swarm_tier("ollama", "Kimi-K2.5") == SwarmTier.BOTH

    def test_claude_sonnet_anthropic(self):
        assert get_swarm_tier("anthropic", "claude-sonnet-4.6") == SwarmTier.BOTH

    def test_claude_sonnet_openai_compatible(self):
        assert get_swarm_tier("openai-compatible", "claude-sonnet-4.6") == SwarmTier.BOTH

    def test_claude_opus_is_coordinator(self):
        assert get_swarm_tier("anthropic", "claude-opus-4.6") == SwarmTier.COORDINATOR

    def test_gpt5_via_openai(self):
        assert get_swarm_tier("openai", "gpt-5.4") == SwarmTier.BOTH

    def test_gemini_pro_is_coordinator(self):
        assert get_swarm_tier("openai-compatible", "gemini-3.1-pro") == SwarmTier.COORDINATOR

    def test_grok_via_compatible(self):
        assert get_swarm_tier("openai-compatible", "grok-4.20") == SwarmTier.BOTH

    def test_unknown_model_is_unsuitable(self):
        assert get_swarm_tier("ollama", "llama3.3:70b") == SwarmTier.UNSUITABLE

    def test_unknown_provider_is_unsuitable(self):
        assert get_swarm_tier("lm-studio", "kimi-k2.5") == SwarmTier.UNSUITABLE

    def test_qwen_local_is_unsuitable(self):
        assert get_swarm_tier("ollama", "qwen3:32b") == SwarmTier.UNSUITABLE


class TestThreshold:
    def test_default_threshold_is_3(self):
        assert get_min_groups_threshold() == 3

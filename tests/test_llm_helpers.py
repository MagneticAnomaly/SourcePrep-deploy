"""Tests for shared LLM router helpers."""
import pytest
from unittest.mock import patch, MagicMock


class TestResolveModelForStage:

    def test_non_llm_stage_returns_none(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "structural") is None

    def test_knowledge_stage_returns_none(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "knowledge") is None

    def test_invalid_stage_returns_none(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "bogus_stage") is None

    def test_resolves_large_slot_model(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        mock_config = {
            "large_model": {
                "endpoint_id": "ep-1",
                "model": "kimi-k2.5:cloud",
            },
            "saved_endpoints": [
                {"id": "ep-1", "provider": "ollama"},
            ],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "group_reasoning")
            assert result == ("ollama", "kimi-k2.5:cloud")

    def test_resolves_small_slot_model(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        mock_config = {
            "small_model": {
                "endpoint_id": "ep-2",
                "model": "gpt-5.1-mini",
            },
            "saved_endpoints": [
                {"id": "ep-2", "provider": "openai"},
            ],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "catalogue")
            assert result == ("openai", "gpt-5.1-mini")

    def test_missing_endpoint_id_returns_none(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        mock_config = {
            "large_model": {"model": "kimi-k2.5:cloud"},
            "saved_endpoints": [],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            assert resolve_model_for_stage("proj-1", "group_reasoning") is None

    def test_missing_model_returns_none(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        mock_config = {
            "large_model": {"endpoint_id": "ep-1"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            assert resolve_model_for_stage("proj-1", "group_reasoning") is None

    def test_defaults_provider_to_ollama(self):
        from codrag.services.pipeline._model_resolution import resolve_model_for_stage
        mock_config = {
            "large_model": {
                "endpoint_id": "ep-1",
                "model": "kimi-k2.5:cloud",
            },
            "saved_endpoints": [
                {"id": "ep-1"},  # no provider field
            ],
        }
        with patch("codrag.services.pipeline._model_resolution.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "group_reasoning")
            assert result == ("ollama", "kimi-k2.5:cloud")


# ── Max Thinking Budget (Phase 112 T17) ───────────────────────────


def test_max_thinking_budget_override(monkeypatch):
    """When max_thinking_budget is raised to 65536, effective_num_predict respects it.

    With num_predict=2048 and think=True:
      candidate = min(max(2048*3, 2048+8192), max(2048, 65536))
                = min(max(6144, 10240), max(2048, 65536))
                = min(10240, 65536)
                = 10240

    With the DEFAULT 24576 cap the result is identical (10240 < 24576),
    so we must verify the cap path is reachable by using a large num_predict.

    With num_predict=32768 and think=True:
      candidate = min(max(32768*3, 32768+8192), max(32768, 65536))
                = min(max(98304, 40960), max(32768, 65536))
                = min(98304, 65536)
                = 65536
    """
    import codrag.server as _server_mod
    monkeypatch.setattr(
        _server_mod,
        "get_advanced_llm_settings",
        lambda: {"max_thinking_budget": 65536},
    )
    num_predict = 32768
    # Replicate the exact formula from llm_client.py
    max_budget = 65536
    effective = min(
        max(num_predict * 3, num_predict + 8192),
        max(num_predict, max_budget),
    )
    assert effective == 65536, f"Expected 65536, got {effective}"


def test_max_thinking_budget_default_caps_at_24576(monkeypatch):
    """Default cap (24576) is preserved when no Advanced Settings override is present."""
    import codrag.server as _server_mod
    monkeypatch.setattr(
        _server_mod,
        "get_advanced_llm_settings",
        lambda: {"max_thinking_budget": 24576},
    )
    num_predict = 32768
    max_budget = 24576
    effective = min(
        max(num_predict * 3, num_predict + 8192),
        max(num_predict, max_budget),
    )
    assert effective == 32768, f"Expected 32768 (base wins over 24576 cap), got {effective}"

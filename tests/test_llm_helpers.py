"""Tests for shared LLM router helpers."""
import pytest
from unittest.mock import patch, MagicMock


class TestResolveModelForStage:

    def test_non_llm_stage_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "structural") is None

    def test_knowledge_stage_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "knowledge") is None

    def test_invalid_stage_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        assert resolve_model_for_stage("proj-1", "bogus_stage") is None

    def test_resolves_large_slot_model(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {
                "endpoint_id": "ep-1",
                "model": "kimi-k2.5:cloud",
            },
            "saved_endpoints": [
                {"id": "ep-1", "provider": "ollama"},
            ],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "group_reasoning")
            assert result == ("ollama", "kimi-k2.5:cloud")

    def test_resolves_small_slot_model(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "small_model": {
                "endpoint_id": "ep-2",
                "model": "gpt-5.1-mini",
            },
            "saved_endpoints": [
                {"id": "ep-2", "provider": "openai"},
            ],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "catalogue")
            assert result == ("openai", "gpt-5.1-mini")

    def test_missing_endpoint_id_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {"model": "kimi-k2.5:cloud"},
            "saved_endpoints": [],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            assert resolve_model_for_stage("proj-1", "group_reasoning") is None

    def test_missing_model_returns_none(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {"endpoint_id": "ep-1"},
            "saved_endpoints": [{"id": "ep-1", "provider": "ollama"}],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            assert resolve_model_for_stage("proj-1", "group_reasoning") is None

    def test_defaults_provider_to_ollama(self):
        from codrag.api.routers._llm_helpers import resolve_model_for_stage
        mock_config = {
            "large_model": {
                "endpoint_id": "ep-1",
                "model": "kimi-k2.5:cloud",
            },
            "saved_endpoints": [
                {"id": "ep-1"},  # no provider field
            ],
        }
        with patch("codrag.api.routers._llm_helpers.settings") as mock_settings:
            mock_settings.get.return_value = mock_config
            result = resolve_model_for_stage("proj-1", "group_reasoning")
            assert result == ("ollama", "kimi-k2.5:cloud")

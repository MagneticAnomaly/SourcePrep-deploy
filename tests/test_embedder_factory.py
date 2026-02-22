"""
Tests for embedder_factory.py — Phase 23 (S-23.6)
"""

from unittest.mock import patch, MagicMock

import pytest

from codrag.services.embedder_factory import create_embedder


_DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "model": "nomic-embed-text",
    "embedding_source": "native",
}


@pytest.fixture(autouse=True)
def mock_server_config():
    """Provide default server config for all tests."""
    import codrag.server
    orig_config = getattr(codrag.server, '_config', {})
    orig_load = getattr(codrag.server, '_load_ui_config', lambda: {})
    codrag.server._config = dict(_DEFAULT_CONFIG)
    codrag.server._load_ui_config = lambda: {}
    yield
    codrag.server._config = orig_config
    codrag.server._load_ui_config = orig_load


class TestEmbedderFactory:
    """Tests for the multi-source embedder creation logic."""

    def test_explicit_ollama_source(self):
        """embedding_source='ollama' returns OllamaEmbedder."""
        embedder = create_embedder("ollama")
        assert type(embedder).__name__ == "OllamaEmbedder"

    def test_explicit_native_source_available(self):
        """embedding_source='native' returns NativeEmbedder when deps available."""
        with patch('codrag.services.embedder_factory.NativeEmbedder') as MockNative:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = True
            MockNative.return_value = mock_instance

            result = create_embedder("native")
            assert result is mock_instance

    def test_explicit_native_source_unavailable_falls_through(self):
        """embedding_source='native' falls through to CLI config when NativeEmbedder unavailable."""
        with patch('codrag.services.embedder_factory.NativeEmbedder') as MockNative:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = False
            MockNative.return_value = mock_instance

            embedder = create_embedder("native")
            assert type(embedder).__name__ == "OllamaEmbedder"

    def test_dashboard_huggingface_source(self):
        """Dashboard config with source='huggingface' returns NativeEmbedder."""
        import codrag.server
        codrag.server._load_ui_config = lambda: {
            "llm_config": {"embedding": {"source": "huggingface"}},
        }
        with patch('codrag.services.embedder_factory.NativeEmbedder') as MockNative:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = True
            MockNative.return_value = mock_instance

            result = create_embedder()
            assert result is mock_instance

    def test_dashboard_endpoint_source_ollama(self):
        """Dashboard config with endpoint pointing to Ollama returns OllamaEmbedder."""
        import codrag.server
        codrag.server._load_ui_config = lambda: {
            "llm_config": {
                "embedding": {"source": "endpoint", "endpoint_id": "ep-1", "model": "mxbai-embed-large"},
                "saved_endpoints": [{"id": "ep-1", "provider": "ollama", "url": "http://gpu:11434"}],
            },
        }
        embedder = create_embedder()
        assert type(embedder).__name__ == "OllamaEmbedder"
        assert embedder.base_url == "http://gpu:11434"
        assert embedder.model == "mxbai-embed-large"

    def test_cli_ollama_fallback(self):
        """CLI embedding_source='ollama' returns OllamaEmbedder."""
        import codrag.server
        codrag.server._config = {
            "ollama_url": "http://remote:11434",
            "model": "custom-embed",
            "embedding_source": "ollama",
        }
        embedder = create_embedder()
        assert type(embedder).__name__ == "OllamaEmbedder"
        assert embedder.model == "custom-embed"

    def test_default_native_when_available(self):
        """Default (no explicit source) returns NativeEmbedder when available."""
        with patch('codrag.services.embedder_factory.NativeEmbedder') as MockNative:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = True
            MockNative.return_value = mock_instance

            result = create_embedder()
            assert result is mock_instance

    def test_default_ollama_when_native_unavailable(self):
        """Default falls back to OllamaEmbedder when NativeEmbedder deps missing."""
        with patch('codrag.services.embedder_factory.NativeEmbedder') as MockNative:
            mock_instance = MagicMock()
            mock_instance.is_available.return_value = False
            MockNative.return_value = mock_instance

            embedder = create_embedder()
            assert type(embedder).__name__ == "OllamaEmbedder"

    def test_dashboard_config_error_falls_through(self):
        """If dashboard config throws, we fall through to CLI/default."""
        import codrag.server
        codrag.server._load_ui_config = MagicMock(side_effect=Exception("disk error"))
        # Should not raise — falls through to CLI config
        embedder = create_embedder()
        assert embedder is not None

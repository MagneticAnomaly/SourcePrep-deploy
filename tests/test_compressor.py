"""
Tests for ContextCompressor / ClaraCompressor / NoopCompressor.

Covers:
- NoopCompressor pass-through behavior
- ClaraCompressor graceful failure when sidecar is offline
- ClaraCompressor successful compression (mocked HTTP)
- ClaraCompressor timeout handling
- Integration: compression wired into server ContextRequest
- CompressResult data integrity

Run with: pytest tests/test_compressor.py -v
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from codrag.core.compressor import (
    ClaraCompressor,
    CompressResult,
    ContextCompressor,
    NoopCompressor,
)


# ---------------------------------------------------------------------------
# NoopCompressor
# ---------------------------------------------------------------------------

class TestNoopCompressor:
    def test_is_available(self):
        c = NoopCompressor()
        assert c.is_available() is True

    def test_returns_text_unchanged(self):
        c = NoopCompressor()
        text = "def hello():\n    return 42\n\n---\n\nclass Foo: pass"
        result = c.compress(text, query="test")
        assert result.compressed == text
        assert result.input_chars == len(text)
        assert result.output_chars == len(text)
        assert result.error is None

    def test_empty_text(self):
        c = NoopCompressor()
        result = c.compress("", query="test")
        assert result.compressed == ""
        assert result.input_chars == 0
        assert result.output_chars == 0


# ---------------------------------------------------------------------------
# ClaraCompressor — offline / unavailable
# ---------------------------------------------------------------------------

class TestClaraCompressorOffline:
    def test_is_available_returns_false_when_offline(self):
        c = ClaraCompressor(base_url="http://localhost:99999")
        assert c.is_available() is False

    def test_compress_returns_original_when_offline(self):
        c = ClaraCompressor(base_url="http://127.0.0.1:19876")
        text = "some context about authentication"
        result = c.compress(text, query="auth")
        assert result.compressed == text
        assert result.input_chars == len(text)
        assert result.output_chars == len(text)
        assert result.error is not None

    def test_status_when_offline(self):
        c = ClaraCompressor(base_url="http://localhost:99999")
        info = c.status()
        assert info["available"] is False
        assert info["url"] == "http://localhost:99999"


# ---------------------------------------------------------------------------
# ClaraCompressor — mocked HTTP (simulating live sidecar)
# ---------------------------------------------------------------------------

class TestClaraCompressorMocked:
    def _make_mock_response(self, data: dict, status_code: int = 200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = data
        resp.raise_for_status.return_value = None
        return resp

    @patch("codrag.core.compressor.requests.post")
    def test_successful_compression(self, mock_post):
        mock_post.return_value = self._make_mock_response({
            "success": True,
            "answer": "The user authenticates via OAuth2.",
            "original_tokens": 150,
            "compressed_tokens": 12,
            "compression_ratio": 12.5,
            "latency_ms": 250,
        })

        c = ClaraCompressor(base_url="http://localhost:8765")
        text = (
            "[auth.py]\ndef authenticate(user, password):\n    return check_oauth2(user)\n\n"
            "---\n\n"
            "[config.py]\nOAUTH2_PROVIDER = 'google'"
        )
        result = c.compress(text, query="how does authentication work?")

        assert result.compressed == "The user authenticates via OAuth2."
        assert result.input_chars == len(text)
        assert result.output_chars == len("The user authenticates via OAuth2.")
        assert result.input_tokens == 150
        assert result.output_tokens == 12
        assert result.compression_ratio == 12.5
        assert result.timing_ms > 0
        assert result.error is None

        # Verify the request was made correctly
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert len(payload["memories"]) == 2  # split by ---
        assert payload["query"] == "how does authentication work?"

    @patch("codrag.core.compressor.requests.post")
    def test_compression_with_budget(self, mock_post):
        long_answer = "A" * 500
        mock_post.return_value = self._make_mock_response({
            "success": True,
            "answer": long_answer,
            "original_tokens": 200,
            "compressed_tokens": 100,
            "compression_ratio": 2.0,
        })

        c = ClaraCompressor()
        result = c.compress("some text", query="test", budget_chars=100)
        assert len(result.compressed) == 100  # truncated to budget

    @patch("codrag.core.compressor.requests.post")
    def test_compression_failure_returns_original(self, mock_post):
        mock_post.return_value = self._make_mock_response({
            "success": False,
            "error": "Model not loaded",
        })

        c = ClaraCompressor()
        text = "original context text"
        result = c.compress(text, query="test")
        assert result.compressed == text  # fallback to original
        assert result.error is not None
        assert "success=false" in result.error.lower() or "Model not loaded" in result.error

    @patch("codrag.core.compressor.requests.post")
    def test_http_error_returns_original(self, mock_post):
        import requests as req
        mock_post.side_effect = req.Timeout("timed out")

        c = ClaraCompressor()
        text = "original context"
        result = c.compress(text, query="test", timeout_s=1.0)
        assert result.compressed == text
        assert result.error is not None
        assert "timed out" in result.error.lower()

    @patch("codrag.core.compressor.requests.get")
    def test_is_available_when_healthy(self, mock_get):
        mock_get.return_value = self._make_mock_response({"status": "ok"})
        c = ClaraCompressor()
        assert c.is_available() is True

    @patch("codrag.core.compressor.requests.get")
    def test_status_when_available(self, mock_get):
        mock_get.return_value = self._make_mock_response({
            "model": "apple/CLaRa-7B-Instruct",
            "device": "mps",
            "loaded": True,
        })
        c = ClaraCompressor()
        info = c.status()
        assert info["available"] is True
        assert info["model"] == "apple/CLaRa-7B-Instruct"
        assert info["device"] == "mps"


# ---------------------------------------------------------------------------
# CompressResult data integrity
# ---------------------------------------------------------------------------

class TestCompressResult:
    def test_frozen_dataclass(self):
        r = CompressResult(
            compressed="short",
            input_chars=100,
            output_chars=5,
            input_tokens=25,
            output_tokens=2,
            compression_ratio=12.5,
            timing_ms=150.0,
        )
        assert r.compressed == "short"
        assert r.compression_ratio == 12.5
        assert r.error is None

        with pytest.raises(AttributeError):
            r.compressed = "modified"  # type: ignore

    def test_default_values(self):
        r = CompressResult(compressed="text", input_chars=4, output_chars=4)
        assert r.input_tokens == 0
        assert r.output_tokens == 0
        assert r.compression_ratio == 1.0
        assert r.timing_ms == 0.0
        assert r.error is None


# ---------------------------------------------------------------------------
# ABC contract
# ---------------------------------------------------------------------------

class TestABCContract:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ContextCompressor()  # type: ignore

    def test_noop_is_subclass(self):
        assert issubclass(NoopCompressor, ContextCompressor)

    def test_clara_is_subclass(self):
        assert issubclass(ClaraCompressor, ContextCompressor)


# ---------------------------------------------------------------------------
# Integration: ContextRequest compression fields
# ---------------------------------------------------------------------------

class TestContextRequestCompression:
    """Test that the server's ContextRequest model accepts compression fields."""

    def test_default_compression_none(self):
        from codrag.api.routers.projects import ContextRequest
        req = ContextRequest(query="test")
        assert req.compression == "none"
        assert req.compression_level == "standard"
        assert req.compression_target_chars is None
        assert req.compression_timeout_s == 30.0

    def test_clara_compression_params(self):
        from codrag.api.routers.projects import ContextRequest
        req = ContextRequest(
            query="test",
            compression="clara",
            compression_level="aggressive",
            compression_target_chars=2000,
            compression_timeout_s=10.0,
        )
        assert req.compression == "clara"
        assert req.compression_level == "aggressive"
        assert req.compression_target_chars == 2000
        assert req.compression_timeout_s == 10.0

"""
Tests for codrag.core.model_readiness module.

Uses unittest.mock to simulate Ollama API responses without requiring
a live Ollama server.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module directly to avoid heavy codrag.core.__init__.py chain
_mod_path = Path(__file__).resolve().parent.parent / "src" / "codrag" / "core" / "model_readiness.py"
_spec = importlib.util.spec_from_file_location("codrag.core.model_readiness", _mod_path)
_mr = importlib.util.module_from_spec(_spec)
sys.modules["codrag.core.model_readiness"] = _mr
_spec.loader.exec_module(_mr)

# Shorthand aliases
ModelStatus = _mr.ModelStatus
ModelReadinessResult = _mr.ModelReadinessResult
normalise_model_name = _mr.normalise_model_name
_names_match = _mr._names_match
ollama_server_reachable = _mr.ollama_server_reachable
ollama_model_exists = _mr.ollama_model_exists
ollama_model_loaded = _mr.ollama_model_loaded
ollama_list_loaded = _mr.ollama_list_loaded
ollama_get_status = _mr.ollama_get_status
ollama_ensure_ready = _mr.ollama_ensure_ready
get_model_status = _mr.get_model_status
ensure_model_ready = _mr.ensure_model_ready

# Module-level patch target (avoids string-based patching through codrag.* path)
_MR = "codrag.core.model_readiness"


# ---------------------------------------------------------------------------
# normalise_model_name / _names_match
# ---------------------------------------------------------------------------

class TestModelNameNormalisation:
    def test_strips_latest_tag(self):
        assert normalise_model_name("mistral:latest") == "mistral"

    def test_preserves_other_tags(self):
        assert normalise_model_name("llama3.2:8b") == "llama3.2:8b"

    def test_no_tag(self):
        assert normalise_model_name("nomic-embed-text") == "nomic-embed-text"

    def test_whitespace(self):
        assert normalise_model_name("  mistral:latest  ") == "mistral"

    def test_names_match_with_latest(self):
        assert _names_match("mistral", "mistral:latest")
        assert _names_match("mistral:latest", "mistral")

    def test_names_match_same(self):
        assert _names_match("llama3.2:8b", "llama3.2:8b")

    def test_names_no_match(self):
        assert not _names_match("mistral", "llama3.2")


# ---------------------------------------------------------------------------
# ollama_server_reachable
# ---------------------------------------------------------------------------

def _mock_requests_get(return_value=None, side_effect=None):
    """Patch requests.get on the already-loaded module object."""
    return patch.object(_mr.requests, "get", return_value=return_value, side_effect=side_effect)


def _mock_requests_post(return_value=None, side_effect=None):
    """Patch requests.post on the already-loaded module object."""
    return patch.object(_mr.requests, "post", return_value=return_value, side_effect=side_effect)


class TestOllamaServerReachable:
    def test_reachable(self):
        with _mock_requests_get(return_value=MagicMock(status_code=200)):
            assert ollama_server_reachable("http://localhost:11434") is True

    def test_not_reachable(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert ollama_server_reachable("http://localhost:11434") is False

    def test_bad_status(self):
        with _mock_requests_get(return_value=MagicMock(status_code=500)):
            assert ollama_server_reachable("http://localhost:11434") is False


# ---------------------------------------------------------------------------
# ollama_model_exists
# ---------------------------------------------------------------------------

class TestOllamaModelExists:
    def test_exists_via_show(self):
        with _mock_requests_post(return_value=MagicMock(status_code=200)):
            assert ollama_model_exists("http://localhost:11434", "mistral") is True

    def test_not_exists(self):
        """Model not found in /api/show (404) nor /api/tags."""
        show_resp = MagicMock(status_code=404)
        tags_resp = MagicMock(status_code=200)
        tags_resp.json.return_value = {"models": [{"name": "other-model:latest"}]}
        with _mock_requests_post(return_value=show_resp), \
             _mock_requests_get(return_value=tags_resp):
            assert ollama_model_exists("http://localhost:11434", "nonexistent") is False

    def test_show_500_but_exists_in_tags(self):
        """/api/show returns 500 (e.g. ministral template bug) but model is in /api/tags."""
        show_resp = MagicMock(status_code=500)
        tags_resp = MagicMock(status_code=200)
        tags_resp.json.return_value = {"models": [{"name": "ministral-3:3b"}]}
        with _mock_requests_post(return_value=show_resp), \
             _mock_requests_get(return_value=tags_resp):
            assert ollama_model_exists("http://localhost:11434", "ministral-3:3b") is True

    def test_connection_error(self):
        with _mock_requests_post(side_effect=ConnectionError("refused")), \
             _mock_requests_get(side_effect=ConnectionError("refused")):
            assert ollama_model_exists("http://localhost:11434", "mistral") is False


# ---------------------------------------------------------------------------
# ollama_model_loaded
# ---------------------------------------------------------------------------

class TestOllamaModelLoaded:
    def test_loaded(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"model": "mistral:latest", "size": 5000}]}
        with _mock_requests_get(return_value=resp):
            assert ollama_model_loaded("http://localhost:11434", "mistral") is True

    def test_loaded_with_latest_match(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"model": "mistral", "size": 5000}]}
        with _mock_requests_get(return_value=resp):
            assert ollama_model_loaded("http://localhost:11434", "mistral:latest") is True

    def test_not_loaded(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": [{"model": "llama3.2:8b", "size": 5000}]}
        with _mock_requests_get(return_value=resp):
            assert ollama_model_loaded("http://localhost:11434", "mistral") is False

    def test_empty_list(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"models": []}
        with _mock_requests_get(return_value=resp):
            assert ollama_model_loaded("http://localhost:11434", "mistral") is False

    def test_server_down(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert ollama_model_loaded("http://localhost:11434", "mistral") is False


# ---------------------------------------------------------------------------
# ollama_list_loaded
# ---------------------------------------------------------------------------

class TestOllamaListLoaded:
    def test_lists_models(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "models": [
                {"model": "mistral:latest"},
                {"model": "nomic-embed-text:latest"},
            ]
        }
        with _mock_requests_get(return_value=resp):
            result = ollama_list_loaded("http://localhost:11434")
        assert len(result) == 2
        assert "mistral:latest" in result

    def test_empty_on_error(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert ollama_list_loaded("http://localhost:11434") == []


# ---------------------------------------------------------------------------
# ollama_get_status
# ---------------------------------------------------------------------------

class TestOllamaGetStatus:
    def test_ready(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=True), \
             patch.object(_mr, "ollama_model_exists", return_value=True), \
             patch.object(_mr, "ollama_model_loaded", return_value=True), \
             patch.object(_mr, "ollama_list_loaded", return_value=["mistral:latest"]):
            result = ollama_get_status("http://localhost:11434", "mistral")
        assert result.status == ModelStatus.READY

    def test_not_found(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=True), \
             patch.object(_mr, "ollama_model_exists", return_value=False):
            result = ollama_get_status("http://localhost:11434", "nonexistent")
        assert result.status == ModelStatus.NOT_FOUND

    def test_downloaded_not_loaded(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=True), \
             patch.object(_mr, "ollama_model_exists", return_value=True), \
             patch.object(_mr, "ollama_model_loaded", return_value=False):
            result = ollama_get_status("http://localhost:11434", "mistral")
        assert result.status == ModelStatus.DOWNLOADED

    def test_server_unreachable(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=False):
            result = ollama_get_status("http://localhost:11434", "mistral")
        assert result.status == ModelStatus.ERROR


# ---------------------------------------------------------------------------
# ollama_ensure_ready
# ---------------------------------------------------------------------------

class TestOllamaEnsureReady:
    def test_already_ready(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=True), \
             patch.object(_mr, "ollama_model_exists", return_value=True), \
             patch.object(_mr, "ollama_model_loaded", return_value=True), \
             patch.object(_mr, "ollama_list_loaded", return_value=["mistral:latest"]):
            result = ollama_ensure_ready("http://localhost:11434", "mistral", timeout_s=5)
        assert result.status == ModelStatus.READY

    def test_server_unreachable(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=False):
            result = ollama_ensure_ready("http://localhost:11434", "mistral", timeout_s=5)
        assert result.status == ModelStatus.ERROR

    def test_model_not_found(self):
        with patch.object(_mr, "ollama_server_reachable", return_value=True), \
             patch.object(_mr, "ollama_model_exists", return_value=False):
            result = ollama_ensure_ready("http://localhost:11434", "nonexistent", timeout_s=5)
        assert result.status == ModelStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# get_model_status (generic provider dispatch)
# ---------------------------------------------------------------------------

class TestGetModelStatus:
    def test_dispatches_to_ollama(self):
        mock_result = ModelReadinessResult(
            status=ModelStatus.READY, message="ok", model="mistral", provider="ollama"
        )
        with patch.object(_mr, "ollama_get_status", return_value=mock_result) as mock_fn:
            result = get_model_status("ollama", "http://localhost:11434", "mistral")
        assert result.status == ModelStatus.READY
        mock_fn.assert_called_once()

    def test_openai_reachable(self):
        with _mock_requests_get(return_value=MagicMock(status_code=200)):
            result = get_model_status("openai", "https://api.openai.com/v1", "gpt-4", api_key="sk-test")
        assert result.status == ModelStatus.READY


# ---------------------------------------------------------------------------
# ModelReadinessResult.to_dict
# ---------------------------------------------------------------------------

class TestModelReadinessResultSerialization:
    def test_to_dict(self):
        result = ModelReadinessResult(
            status=ModelStatus.READY,
            message="Model is ready",
            model="mistral",
            provider="ollama",
            details={"load_time_s": 2.5},
        )
        d = result.to_dict()
        assert d["status"] == "ready"
        assert d["message"] == "Model is ready"
        assert d["model"] == "mistral"
        assert d["provider"] == "ollama"
        assert d["details"]["load_time_s"] == 2.5

    def test_all_statuses_serialize(self):
        for status in ModelStatus:
            result = ModelReadinessResult(status=status, message="test", model="m")
            d = result.to_dict()
            assert d["status"] == status.value

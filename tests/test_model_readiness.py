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

# LM Studio aliases
_lmstudio_api_base = _mr._lmstudio_api_base
_lmstudio_key_matches = _mr._lmstudio_key_matches
lmstudio_server_reachable = _mr.lmstudio_server_reachable
lmstudio_model_exists = _mr.lmstudio_model_exists
lmstudio_model_loaded = _mr.lmstudio_model_loaded
lmstudio_list_loaded = _mr.lmstudio_list_loaded
_lmstudio_resolve_key = _mr._lmstudio_resolve_key
_lmstudio_get_instance_id = _mr._lmstudio_get_instance_id
lmstudio_load = _mr.lmstudio_load
lmstudio_unload = _mr.lmstudio_unload
lmstudio_get_status = _mr.lmstudio_get_status
lmstudio_ensure_ready = _mr.lmstudio_ensure_ready

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


# ===========================================================================
# LM Studio tests
# ===========================================================================

_LMSTUDIO_MODELS_RESPONSE = {
    "models": [
        {
            "type": "llm",
            "publisher": "qwen",
            "key": "qwen3-4b-2507",
            "display_name": "Qwen 3 4B",
            "architecture": "qwen3",
            "quantization": {"name": "Q4_0", "bits_per_weight": 4},
            "size_bytes": 2500000000,
            "params_string": "4B",
            "loaded_instances": [
                {"id": "qwen3-4b-2507", "config": {"context_length": 8192}}
            ],
            "max_context_length": 32768,
            "format": "gguf",
        },
        {
            "type": "llm",
            "publisher": "lmstudio-community",
            "key": "gemma-3-270m-it-qat",
            "display_name": "Gemma 3 270m",
            "architecture": "gemma3",
            "quantization": {"name": "Q4_0", "bits_per_weight": 4},
            "size_bytes": 241410208,
            "params_string": "270M",
            "loaded_instances": [],
            "max_context_length": 32768,
            "format": "gguf",
        },
        {
            "type": "embedding",
            "publisher": "gaianet",
            "key": "text-embedding-nomic-embed-text-v1.5-embedding",
            "display_name": "Nomic Embed Text v1.5",
            "quantization": {"name": "F16", "bits_per_weight": 16},
            "size_bytes": 274290560,
            "params_string": None,
            "loaded_instances": [],
            "max_context_length": 2048,
            "format": "gguf",
        },
    ]
}


class TestLmstudioApiBase:
    def test_bare_url(self):
        assert _lmstudio_api_base("http://localhost:1234") == "http://localhost:1234/api/v1"

    def test_trailing_slash(self):
        assert _lmstudio_api_base("http://localhost:1234/") == "http://localhost:1234/api/v1"

    def test_with_v1_openai_path(self):
        assert _lmstudio_api_base("http://localhost:1234/v1") == "http://localhost:1234/api/v1"

    def test_already_api_v1(self):
        assert _lmstudio_api_base("http://localhost:1234/api/v1") == "http://localhost:1234/api/v1"

    def test_custom_port(self):
        assert _lmstudio_api_base("http://192.168.1.100:5678") == "http://192.168.1.100:5678/api/v1"


class TestLmstudioKeyMatches:
    def test_exact_match(self):
        assert _lmstudio_key_matches("qwen3-4b-2507", "qwen3-4b-2507")

    def test_case_insensitive(self):
        assert _lmstudio_key_matches("Qwen3-4B-2507", "qwen3-4b-2507")

    def test_key_with_publisher_prefix(self):
        assert _lmstudio_key_matches("qwen/qwen3-4b-2507", "qwen3-4b-2507")

    def test_user_specifies_full_key(self):
        assert _lmstudio_key_matches("qwen/qwen3-4b-2507", "qwen/qwen3-4b-2507")

    def test_partial_match(self):
        assert _lmstudio_key_matches("lmstudio-community/gemma-3-270m-it-qat", "gemma-3-270m")

    def test_no_match(self):
        assert not _lmstudio_key_matches("qwen3-4b-2507", "llama3-8b")


class TestLmstudioServerReachable:
    def test_reachable(self):
        with _mock_requests_get(return_value=MagicMock(status_code=200)):
            assert lmstudio_server_reachable("http://localhost:1234") is True

    def test_not_reachable(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert lmstudio_server_reachable("http://localhost:1234") is False

    def test_bad_status(self):
        with _mock_requests_get(return_value=MagicMock(status_code=500)):
            assert lmstudio_server_reachable("http://localhost:1234") is False


class TestLmstudioModelExists:
    def test_exists(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert lmstudio_model_exists("http://localhost:1234", "qwen3-4b-2507") is True

    def test_not_exists(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert lmstudio_model_exists("http://localhost:1234", "nonexistent-model") is False

    def test_partial_name_match(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert lmstudio_model_exists("http://localhost:1234", "gemma-3-270m") is True

    def test_server_error(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert lmstudio_model_exists("http://localhost:1234", "qwen3-4b-2507") is False


class TestLmstudioModelLoaded:
    def test_loaded(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert lmstudio_model_loaded("http://localhost:1234", "qwen3-4b-2507") is True

    def test_not_loaded(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert lmstudio_model_loaded("http://localhost:1234", "gemma-3-270m-it-qat") is False

    def test_nonexistent_model(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert lmstudio_model_loaded("http://localhost:1234", "nonexistent") is False

    def test_server_down(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert lmstudio_model_loaded("http://localhost:1234", "qwen3-4b-2507") is False


class TestLmstudioListLoaded:
    def test_lists_loaded(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            result = lmstudio_list_loaded("http://localhost:1234")
        assert result == ["qwen3-4b-2507"]

    def test_empty_on_error(self):
        with _mock_requests_get(side_effect=ConnectionError("refused")):
            assert lmstudio_list_loaded("http://localhost:1234") == []


class TestLmstudioResolveKey:
    def test_resolves_exact(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert _lmstudio_resolve_key("http://localhost:1234", "qwen3-4b-2507") == "qwen3-4b-2507"

    def test_resolves_partial(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert _lmstudio_resolve_key("http://localhost:1234", "gemma-3-270m") == "gemma-3-270m-it-qat"

    def test_returns_none_not_found(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert _lmstudio_resolve_key("http://localhost:1234", "nonexistent") is None


class TestLmstudioGetInstanceId:
    def test_gets_instance_id(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert _lmstudio_get_instance_id("http://localhost:1234", "qwen3-4b-2507") == "qwen3-4b-2507"

    def test_returns_none_not_loaded(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=resp):
            assert _lmstudio_get_instance_id("http://localhost:1234", "gemma-3-270m-it-qat") is None


class TestLmstudioLoad:
    def test_load_success(self):
        models_resp = MagicMock(status_code=200)
        models_resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        load_resp = MagicMock(status_code=200)
        load_resp.json.return_value = {
            "type": "llm", "instance_id": "gemma-3-270m-it-qat",
            "load_time_seconds": 3.5, "status": "loaded",
        }
        with _mock_requests_get(return_value=models_resp), \
             _mock_requests_post(return_value=load_resp):
            assert lmstudio_load("http://localhost:1234", "gemma-3-270m-it-qat") is True

    def test_load_model_not_found(self):
        models_resp = MagicMock(status_code=200)
        models_resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=models_resp):
            assert lmstudio_load("http://localhost:1234", "nonexistent") is False

    def test_load_with_context_length(self):
        models_resp = MagicMock(status_code=200)
        models_resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        load_resp = MagicMock(status_code=200)
        load_resp.json.return_value = {
            "type": "llm", "instance_id": "gemma-3-270m-it-qat",
            "load_time_seconds": 4.0, "status": "loaded",
        }
        with _mock_requests_get(return_value=models_resp), \
             _mock_requests_post(return_value=load_resp) as mock_post:
            assert lmstudio_load("http://localhost:1234", "gemma-3-270m-it-qat", context_length=16384) is True
            call_args = mock_post.call_args
            assert call_args[1]["json"]["context_length"] == 16384


class TestLmstudioUnload:
    def test_unload_success(self):
        models_resp = MagicMock(status_code=200)
        models_resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        unload_resp = MagicMock(status_code=200)
        unload_resp.json.return_value = {"instance_id": "qwen3-4b-2507"}
        with _mock_requests_get(return_value=models_resp), \
             _mock_requests_post(return_value=unload_resp):
            assert lmstudio_unload("http://localhost:1234", "qwen3-4b-2507") is True

    def test_unload_not_loaded(self):
        models_resp = MagicMock(status_code=200)
        models_resp.json.return_value = _LMSTUDIO_MODELS_RESPONSE
        with _mock_requests_get(return_value=models_resp):
            assert lmstudio_unload("http://localhost:1234", "gemma-3-270m-it-qat") is True


class TestLmstudioGetStatus:
    def test_ready(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=True), \
             patch.object(_mr, "lmstudio_model_exists", return_value=True), \
             patch.object(_mr, "lmstudio_model_loaded", return_value=True), \
             patch.object(_mr, "lmstudio_list_loaded", return_value=["qwen3-4b-2507"]):
            result = lmstudio_get_status("http://localhost:1234", "qwen3-4b-2507")
        assert result.status == ModelStatus.READY
        assert result.provider == "lm-studio"

    def test_not_found(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=True), \
             patch.object(_mr, "lmstudio_model_exists", return_value=False):
            result = lmstudio_get_status("http://localhost:1234", "nonexistent")
        assert result.status == ModelStatus.NOT_FOUND

    def test_downloaded_not_loaded(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=True), \
             patch.object(_mr, "lmstudio_model_exists", return_value=True), \
             patch.object(_mr, "lmstudio_model_loaded", return_value=False):
            result = lmstudio_get_status("http://localhost:1234", "qwen3-4b-2507")
        assert result.status == ModelStatus.DOWNLOADED

    def test_server_unreachable(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=False):
            result = lmstudio_get_status("http://localhost:1234", "qwen3-4b-2507")
        assert result.status == ModelStatus.ERROR


class TestLmstudioEnsureReady:
    def test_already_ready(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=True), \
             patch.object(_mr, "lmstudio_model_exists", return_value=True), \
             patch.object(_mr, "lmstudio_model_loaded", return_value=True), \
             patch.object(_mr, "lmstudio_list_loaded", return_value=["qwen3-4b-2507"]):
            result = lmstudio_ensure_ready("http://localhost:1234", "qwen3-4b-2507", timeout_s=5)
        assert result.status == ModelStatus.READY

    def test_server_unreachable(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=False):
            result = lmstudio_ensure_ready("http://localhost:1234", "qwen3-4b-2507", timeout_s=5)
        assert result.status == ModelStatus.ERROR

    def test_model_not_found(self):
        with patch.object(_mr, "lmstudio_server_reachable", return_value=True), \
             patch.object(_mr, "lmstudio_model_exists", return_value=False):
            result = lmstudio_ensure_ready("http://localhost:1234", "nonexistent", timeout_s=5)
        assert result.status == ModelStatus.NOT_FOUND


class TestGenericDispatchLmStudio:
    def test_get_model_status_dispatches_to_lmstudio(self):
        mock_result = ModelReadinessResult(
            status=ModelStatus.READY, message="ok",
            model="qwen3-4b-2507", provider="lm-studio",
        )
        with patch.object(_mr, "lmstudio_get_status", return_value=mock_result) as mock_fn:
            result = get_model_status("lm-studio", "http://localhost:1234", "qwen3-4b-2507")
        assert result.status == ModelStatus.READY
        assert result.provider == "lm-studio"
        mock_fn.assert_called_once()

    def test_ensure_model_ready_dispatches_to_lmstudio(self):
        mock_result = ModelReadinessResult(
            status=ModelStatus.READY, message="ok",
            model="qwen3-4b-2507", provider="lm-studio",
        )
        with patch.object(_mr, "lmstudio_ensure_ready", return_value=mock_result) as mock_fn:
            result = ensure_model_ready("lm-studio", "http://localhost:1234", "qwen3-4b-2507")
        assert result.status == ModelStatus.READY
        mock_fn.assert_called_once()

"""
Tests for the on-demand Ollama Cloud model discovery endpoint
(`POST /api/llm/proxy/cloud-models`) and the shared ``_ollama_show_detail``
helper.

Background: Ollama's ``GET /api/tags`` only enumerates cloud models the user
has *subscribed/pinned*. On-demand cloud models (e.g. ``glm-5.2:cloud``) are
served via ``/api/show`` + chat but never appear in ``/api/tags``, so the AI
Gateway picker can't see them. The endpoint probes a curated candidate list
via ``/api/show`` and returns only the ones Ollama actually serves, minus
anything already in ``/api/tags`` (no duplication).

These tests simulate Ollama API responses with ``unittest.mock`` — no live
Ollama server required. They pin the three behaviors that matter:
  1. an on-demand cloud model NOT in /api/tags is returned;
  2. an inaccessible candidate is pruned (``/api/show`` errors);
  3. a subscribed cloud model already in /api/tags is NOT duplicated.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prep.api.routers import llm as llm_mod
from prep.api.routers.llm import LLMProxyRequest, proxy_cloud_models, _fmt_param_size
from prep.core import ollama_cloud_catalog as catalog


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    """The endpoint caches probes per (url, catalog_version); clear between
    tests so a cached result from one test doesn't satisfy the next."""
    llm_mod._cloud_probe_cache.clear()
    yield
    llm_mod._cloud_probe_cache.clear()


def _tags_response(models: list[str]) -> MagicMock:
    return MagicMock(status_code=200, json=lambda: {"models": [{"name": m} for m in models]})


def _show_ok(ctx: int, family: str, param_size: str) -> MagicMock:
    return MagicMock(
        status_code=200,
        json=lambda: {
            "model_info": {"x.context_length": ctx},
            "details": {"family": family, "parameter_size": param_size, "quantization_level": ""},
        },
    )


def _show_not_found() -> MagicMock:
    # Ollama returns 200 with an error body for unknown/inaccessible cloud models
    return MagicMock(status_code=200, json=lambda: {"error": "model not found"})


def _post_side_effect(name_to_response: dict[str, MagicMock]):
    """Route requests.post to the right mock based on the `name` in its json body."""

    def _impl(url, *args, **kwargs):
        name = (kwargs.get("json") or {}).get("name")
        return name_to_response.get(name, _show_not_found())

    return _impl


def _unwrap(r: dict) -> dict:
    return r["data"] if isinstance(r, dict) and "data" in r else r


# ---------------------------------------------------------------------------
# proxy_cloud_models
# ---------------------------------------------------------------------------

class TestProxyCloudModels:
    def test_returns_on_demand_cloud_model_not_in_tags(self):
        candidates = ["glm-5.2:cloud", "bogus:cloud", "kimi-k2.5:cloud"]
        with patch.object(catalog, "OLLAMA_CLOUD_CANDIDATES", candidates), \
             patch.object(llm_mod.requests, "get", return_value=_tags_response(["kimi-k2.5:cloud", "qwen3:8b"])), \
             patch.object(llm_mod.requests, "post", side_effect=_post_side_effect({
                 "glm-5.2:cloud": _show_ok(1_000_000, "glm5.2", "756162687872"),
                 # bogus:cloud → default not_found
             })):
            r = proxy_cloud_models(LLMProxyRequest(provider="ollama", url="http://127.0.0.1:11434"))

        data = _unwrap(r)
        # Only the on-demand accessible model is returned.
        assert data["cloud_models"] == ["glm-5.2:cloud"]
        assert len(data["cloud_model_details"]) == 1
        d = data["cloud_model_details"][0]
        assert d["name"] == "glm-5.2:cloud"
        assert d["context_window"] == "1000k"
        assert d["cost_tier"] == "756B"
        assert d["on_demand_cloud"] is True
        assert d["family"] == "glm5.2"
        # Inaccessible candidate pruned.
        assert "bogus:cloud" not in data["cloud_models"]
        # Subscribed cloud model NOT duplicated (it's already in /api/tags).
        assert "kimi-k2.5:cloud" not in data["cloud_models"]

    def test_non_ollama_provider_returns_empty_without_probing(self):
        post = MagicMock()
        with patch.object(llm_mod.requests, "post", post):
            r = proxy_cloud_models(
                LLMProxyRequest(provider="openai", url="https://api.openai.com", api_key="k")
            )
        data = _unwrap(r)
        assert data["cloud_models"] == []
        assert data["cloud_model_details"] == []
        # Cloud-via-Ollama is the only case; non-Ollama must not probe.
        assert post.call_count == 0

    def test_cache_avoids_reprobing_on_repeated_call(self):
        candidates = ["glm-5.2:cloud"]
        with patch.object(catalog, "OLLAMA_CLOUD_CANDIDATES", candidates), \
             patch.object(llm_mod.requests, "get", return_value=_tags_response([])), \
             patch.object(llm_mod.requests, "post", side_effect=_post_side_effect({
                 "glm-5.2:cloud": _show_ok(1_000_000, "glm5.2", "756162687872"),
             })) as post_mock:
            proxy_cloud_models(LLMProxyRequest(provider="ollama", url="http://127.0.0.1:11434"))
            # Second call within the TTL must hit the cache, not re-probe.
            proxy_cloud_models(LLMProxyRequest(provider="ollama", url="http://127.0.0.1:11434"))
        assert post_mock.call_count == 1

    def test_all_inaccessible_candidates_returns_empty(self):
        candidates = ["bogus-a:cloud", "bogus-b:cloud"]
        with patch.object(catalog, "OLLAMA_CLOUD_CANDIDATES", candidates), \
             patch.object(llm_mod.requests, "get", return_value=_tags_response([])), \
             patch.object(llm_mod.requests, "post", side_effect=_post_side_effect({})):
            r = proxy_cloud_models(LLMProxyRequest(provider="ollama", url="http://127.0.0.1:11434"))
        data = _unwrap(r)
        assert data["cloud_models"] == []
        assert data["cloud_model_details"] == []


# ---------------------------------------------------------------------------
# _fmt_param_size
# ---------------------------------------------------------------------------

class TestFmtParamSize:
    def test_humanizes_large_param_count(self):
        assert _fmt_param_size("756162687872") == "756B"
        assert _fmt_param_size("8000000000") == "8B"
        assert _fmt_param_size("7000000") == "7M"
        assert _fmt_param_size("5000") == "5K"

    def test_passes_through_human_readable_local_values(self):
        # Local Ollama models already arrive as "8B" etc.
        assert _fmt_param_size("8B") == "8B"
        assert _fmt_param_size("") == ""

    def test_passes_through_small_numeric(self):
        assert _fmt_param_size("42") == "42"
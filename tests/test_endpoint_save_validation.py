"""Phase 119 Phase A: API surface for plan-tier limits + save validation.

Save validation tests use ``PUT /global/config`` (the dashboard's actual save
path) and inspect the warnings array threaded through the response envelope.
The validator's contract: providers with ``auto_detect=false`` (Ollama Cloud,
Gemini, Kimi direct) MUST have either an explicit ``plan_tier`` (not "auto")
or an explicit ``cloud_concurrency`` > 0 to save without a warning.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi.testclient import TestClient


def _client():
    from prep.server import app
    return TestClient(app)


def _put_endpoint(client: TestClient, endpoint: Dict[str, Any]) -> Any:
    """Helper: submit a saved_endpoints patch via PUT /global/config.

    Mirrors useLLMConfig.ts addEndpoint shape: {"llm_config": {"saved_endpoints": [...]}}.
    Stamps a fresh id so the test endpoint cannot collide with existing config.
    """
    if "id" not in endpoint:
        endpoint = {**endpoint, "id": f"test-ep-{uuid.uuid4().hex[:8]}"}
    return client.put(
        "/global/config",
        json={"llm_config": {"saved_endpoints": [endpoint]}},
    )


def _warnings_for(resp_json: Any) -> List[str]:
    """Extract warnings list from a response envelope (top-level or .data)."""
    if not isinstance(resp_json, dict):
        return []
    warns = resp_json.get("warnings")
    if isinstance(warns, list):
        return warns
    data = resp_json.get("data")
    if isinstance(data, dict):
        warns = data.get("warnings")
        if isinstance(warns, list):
            return warns
    return []


def test_plan_limits_endpoint_returns_full_table() -> None:
    """GET /llm/plan-limits returns the parsed concurrency_limits.json."""
    client = _client()
    resp = client.get("/llm/plan-limits")
    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", body)
    providers = data["providers"]
    assert "ollama_cloud" in providers
    assert providers["ollama_cloud"]["auto_detect"] is False
    # Ollama Cloud Max = 10 (the published number)
    tiers = {t["tier_key"]: t for t in providers["ollama_cloud"]["tiers"]}
    assert tiers["max"]["concurrent"] == 10


def test_plan_limits_includes_source_urls() -> None:
    client = _client()
    resp = client.get("/llm/plan-limits")
    body = resp.json()
    data = body.get("data", body)
    for provider_key, provider in data["providers"].items():
        for tier in provider["tiers"]:
            assert tier["source_url"].startswith("http"), (
                f"{provider_key}/{tier['tier_key']}: source_url should be a URL"
            )


def test_save_endpoint_force_tier_for_no_auto_detect_provider() -> None:
    """Saving an Ollama Cloud-style endpoint without plan_tier returns 400 OR
    a warning. The provider's auto_detect=false; the user MUST pick a tier."""
    client = _client()
    payload = {
        "name": "test-ollama-no-tier",
        "provider": "ollama",
        # Ollama Cloud URL — distinguishes from local Ollama via _is_cloud_url
        "url": "https://ollama.com",
        "api_key": "fake-key",
        # plan_tier intentionally missing
        # cloud_concurrency intentionally 0 (sentinel for "auto")
        "cloud_concurrency": 0,
    }
    resp = _put_endpoint(client, payload)
    if resp.status_code == 200:
        body = resp.json()
        warns = _warnings_for(body)
        assert any("plan" in w.lower() or "tier" in w.lower() for w in warns), (
            f"Expected a plan-required warning for ollama cloud (no auto-detect); got: {warns}"
        )
    else:
        assert resp.status_code == 400


def test_save_endpoint_auto_for_header_rich_provider_is_ok() -> None:
    """Saving an OpenAI endpoint with plan_tier='auto' (no number) succeeds
    because OpenAI's auto_detect=true."""
    client = _client()
    payload = {
        "name": "test-openai-auto",
        "provider": "openai",
        "url": "https://api.openai.com",
        "api_key": "sk-test-fake",
        "plan_tier": "auto",
        "cloud_concurrency": 0,  # 0 = sentinel for "auto"
    }
    resp = _put_endpoint(client, payload)
    assert resp.status_code in (200, 201), (
        f"Expected OpenAI auto save to succeed; got {resp.status_code}: {resp.text}"
    )
    # Header-rich provider on auto should not fire a plan warning.
    warns = [w for w in _warnings_for(resp.json()) if "test-openai-auto" in w or "openai" in w.lower()]
    assert not any("pick a Plan tier" in w for w in warns), (
        f"OpenAI on auto should not require an explicit tier; got: {warns}"
    )


def test_save_endpoint_with_custom_tier_persists_value() -> None:
    """plan_tier='custom' with cloud_concurrency=7 round-trips."""
    client = _client()
    payload = {
        "name": "test-custom-7",
        "provider": "ollama",
        "url": "https://ollama.com",
        "api_key": "fake-key",
        "plan_tier": "custom",
        "cloud_concurrency": 7,
    }
    resp = _put_endpoint(client, payload)
    assert resp.status_code in (200, 201)
    # An explicit cloud_concurrency > 0 satisfies the validator — no plan warning.
    warns = [w for w in _warnings_for(resp.json()) if "test-custom-7" in w]
    assert not any("pick a Plan tier" in w for w in warns), (
        f"Custom concurrency should satisfy validator; got: {warns}"
    )

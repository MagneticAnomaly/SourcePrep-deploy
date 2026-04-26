"""Phase 119 Phase A: API surface for plan-tier limits + save validation."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _client():
    from prep.server import app
    return TestClient(app)


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

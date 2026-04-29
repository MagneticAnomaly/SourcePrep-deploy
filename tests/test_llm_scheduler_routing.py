"""Phase 119+ correctness — LLMClient → scheduler-slot routing.

When a project configures a separate Swarm Coordinator on an
openai-compatible cloud endpoint (OpenRouter, Together, Groq) AND the
default endpoint is Ollama Cloud, ``_resolve_scheduler_node_id``
must route the coordinator's calls to the OpenRouter slot, NOT the
first-found cloud slot (which is typically the Ollama node).

The pre-fix bug: ``provider="openai-compatible"`` is not in
``CLOUD_PROVIDERS``, so the resolver fell back to ``prefix="local:"``
and returned the first local slot — sending Qwen-on-OpenRouter calls
through ``local:default_ollama`` (max=1), starving the AIMD signal on
the real OpenRouter slot and bottlenecking coordinator latency.

The fix introduces three resolution layers in order:
  1. exact ``endpoint_id`` match (cloud:{ep} or local:{ep})
  2. URL-host classification (localhost/private → local, public → cloud)
  3. legacy provider-prefix fallback
"""
from __future__ import annotations
from unittest.mock import patch


def _client_with_slots(monkeypatch, *, endpoint_url, provider, endpoint_id=None):
    """Build an LLMClient against a fake scheduler with two cloud slots
    and one local slot, matching the live PowerMate config:
      cloud:default_ollama  (Kimi via Ollama Cloud)
      cloud:ep_openrouter   (Qwen via OpenRouter)
      local:default_ollama  (Ollama localhost)
    """
    from prep.core.llm_client import LLMClient

    class _FakeSlot:
        pass
    fake_slots = {
        "__embedding__": _FakeSlot(),
        "local:default_ollama": _FakeSlot(),
        "cloud:default_ollama": _FakeSlot(),
        "local:ep_openrouter": _FakeSlot(),
        "cloud:ep_openrouter": _FakeSlot(),
    }

    class _FakeScheduler:
        _slots = fake_slots

    import prep.services.pipeline.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "pipeline_scheduler", _FakeScheduler())

    return LLMClient(
        endpoint_url=endpoint_url,
        model="any-model",
        provider=provider,
        endpoint_id=endpoint_id,
    )


def test_endpoint_id_routes_to_correct_cloud_slot(monkeypatch) -> None:
    """C1: Qwen on OpenRouter with endpoint_id resolves to cloud:{ep},
    NOT cloud:default_ollama (which is the Kimi node)."""
    client = _client_with_slots(
        monkeypatch,
        endpoint_url="https://openrouter.ai/api/v1",
        provider="openai-compatible",
        endpoint_id="ep_openrouter",
    )
    assert client._resolve_scheduler_node_id() == "cloud:ep_openrouter"


def test_endpoint_id_falls_back_to_local_when_no_cloud_slot(monkeypatch) -> None:
    """C2: when the endpoint only has a local: slot, route there."""
    from prep.core.llm_client import LLMClient

    class _FakeSlot:
        pass
    fake_slots = {
        "__embedding__": _FakeSlot(),
        "local:ep_lmstudio": _FakeSlot(),
    }

    class _FakeScheduler:
        _slots = fake_slots

    import prep.services.pipeline.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "pipeline_scheduler", _FakeScheduler())

    client = LLMClient(
        endpoint_url="http://localhost:1234/v1",
        model="any",
        provider="openai-compatible",
        endpoint_id="ep_lmstudio",
    )
    assert client._resolve_scheduler_node_id() == "local:ep_lmstudio"


def test_url_host_classifies_public_host_as_cloud(monkeypatch) -> None:
    """C3: without endpoint_id, openai-compatible with public host should
    still classify as cloud — fixes the bug where every openai-compatible
    call landed on a local slot regardless of URL.

    Pre-fix: provider="openai-compatible" → not in CLOUD_PROVIDERS →
    is_cloud=False → prefix="local:" → returned cloud:default_ollama
    by accident? No, returned LOCAL — bug.
    """
    client = _client_with_slots(
        monkeypatch,
        endpoint_url="https://openrouter.ai/api/v1",
        provider="openai-compatible",
        endpoint_id=None,  # legacy caller path
    )
    nid = client._resolve_scheduler_node_id()
    assert nid is not None and nid.startswith("cloud:"), (
        f"public-host openai-compatible should route to a cloud: slot, got {nid}"
    )


def test_url_host_classifies_localhost_as_local(monkeypatch) -> None:
    """C4: localhost/127.0.0.1 openai-compatible (LM Studio) routes local."""
    client = _client_with_slots(
        monkeypatch,
        endpoint_url="http://localhost:1234/v1",
        provider="openai-compatible",
        endpoint_id=None,
    )
    nid = client._resolve_scheduler_node_id()
    assert nid is not None and nid.startswith("local:"), (
        f"localhost openai-compatible should route to a local: slot, got {nid}"
    )


def test_legacy_cloud_provider_still_routes_via_prefix(monkeypatch) -> None:
    """C5: explicit cloud providers (openai/anthropic/google/azure-openai)
    still resolve via the legacy prefix path when endpoint_id is missing."""
    client = _client_with_slots(
        monkeypatch,
        endpoint_url="https://api.openai.com/v1",
        provider="openai",
        endpoint_id=None,
    )
    nid = client._resolve_scheduler_node_id()
    assert nid is not None and nid.startswith("cloud:")


def test_endpoint_id_overrides_url_classification(monkeypatch) -> None:
    """C6: endpoint_id is the authoritative signal.  Even if the URL
    looks like cloud, an explicit endpoint_id pointing to a local: slot
    should win."""
    from prep.core.llm_client import LLMClient

    class _FakeSlot:
        pass
    fake_slots = {
        "local:ep_proxy": _FakeSlot(),
        "cloud:default_ollama": _FakeSlot(),  # decoy
    }

    class _FakeScheduler:
        _slots = fake_slots

    import prep.services.pipeline.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "pipeline_scheduler", _FakeScheduler())

    client = LLMClient(
        endpoint_url="https://example.com/api",
        model="x",
        provider="openai-compatible",
        endpoint_id="ep_proxy",
    )
    assert client._resolve_scheduler_node_id() == "local:ep_proxy"

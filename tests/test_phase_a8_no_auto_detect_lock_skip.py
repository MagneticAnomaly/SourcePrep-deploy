"""Phase A 8: edge-lock is skipped for auto_detect=false providers.

For Ollama Cloud, Gemini, and Kimi the user's plan tier is the single
source of truth — there are no rate-limit signals to "discover" a
ceiling from.  A transient 429 must NOT persist a discovered_ceiling
that overrides the user's stated max on every restart.

Header-rich providers (OpenAI / Anthropic) and OSS Ollama (probable
via /api/ps) keep the existing AIMD edge-lock behavior.
"""
from __future__ import annotations


def _fresh_slot(node_id: str = "cloud:phase-a8"):
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler._slots.pop(node_id, None)
    pipeline_scheduler._queues.pop(node_id, None)
    pipeline_scheduler.configure_node(node_id, max_concurrent=10)
    slot = pipeline_scheduler._slots[node_id]
    slot._history.clear()
    return slot


def test_no_auto_detect_provider_skips_edge_lock(monkeypatch, tmp_path) -> None:
    """When the slot's provider is auto_detect=false (Ollama Cloud), a
    backoff in CA mode logs the backoff but does NOT persist a
    discovered_ceiling — the user's plan tier max_concurrent is
    authoritative.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: False,
    )

    slot = _fresh_slot("cloud:no-auto-detect")
    slot.current_limit = 10
    slot.in_flight_requests = 5
    slot.mode = "congestion_avoidance"
    slot._last_backoff_time = 0.0

    with pipeline_scheduler._lock:
        pipeline_scheduler._record_throughput_for_slot(
            slot, queue_time_ms=0.0, is_429_or_timeout=True,
        )

    reasons = [ev["reason"] for ev in slot._history]
    assert "backoff" in reasons, f"expected backoff event, got {reasons}"
    assert "edge_lock" not in reasons, (
        f"no-auto-detect provider must not record edge_lock; got {reasons}"
    )
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0


def test_auto_detect_provider_keeps_edge_lock(monkeypatch, tmp_path) -> None:
    """OpenAI / Anthropic / OSS Ollama still record edge_lock on a CA
    backoff — that's where the lock is genuinely useful (real ceiling).
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: True,
    )

    slot = _fresh_slot("cloud:auto-detect")
    slot.current_limit = 16
    slot.in_flight_requests = 8
    slot.mode = "congestion_avoidance"
    slot._last_backoff_time = 0.0

    with pipeline_scheduler._lock:
        pipeline_scheduler._record_throughput_for_slot(
            slot, queue_time_ms=0.0, is_429_or_timeout=True,
        )

    reasons = [ev["reason"] for ev in slot._history]
    assert "edge_lock" in reasons, (
        f"auto-detect provider must record edge_lock; got {reasons}"
    )
    assert slot.discovered_ceiling is not None
    assert slot.ceiling_locked_until > 0.0


def test_user_tier_change_clears_stale_lock(monkeypatch, tmp_path) -> None:
    """When the user picks a new max via the Plan dropdown for a
    no-auto-detect provider, configure_node snaps current_limit to
    the new max and clears any leftover discovered_ceiling/lock — the
    user's choice is authoritative.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: False,
    )

    node_id = "cloud:user-tier-change"
    pipeline_scheduler._slots.pop(node_id, None)
    pipeline_scheduler._queues.pop(node_id, None)
    pipeline_scheduler.configure_node(node_id, max_concurrent=3)
    slot = pipeline_scheduler._slots[node_id]
    # Simulate a stale lock the user is overriding.
    slot.current_limit = 1
    slot.discovered_ceiling = 1
    slot.ceiling_locked_until = 9_999_999_999.0
    slot._history.clear()

    pipeline_scheduler.configure_node(node_id, max_concurrent=10)

    slot = pipeline_scheduler._slots[node_id]
    assert slot.max_concurrent == 10
    assert slot.current_limit == 10
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0
    reasons = [ev["reason"] for ev in slot._history]
    assert "user_tier_set" in reasons


# ── Resolver tests (M3): exercise _provider_supports_auto_detect against
# real settings shapes instead of monkey-patching the helper itself. ──


def _seed_settings_endpoints(
    monkeypatch, endpoints: list,
) -> None:
    """Seed settings_store.get('llm_config') with the given saved_endpoints
    list so _provider_supports_auto_detect's lookup path runs end-to-end.
    """
    from prep.services import settings_store
    fake_cfg = {"llm_config": {"saved_endpoints": endpoints}}
    monkeypatch.setattr(
        settings_store.settings,
        "get",
        lambda key, default=None: (
            fake_cfg.get(key) if key == "llm_config"
            else (default if default is not None else None)
        ),
    )


def test_resolver_ollama_cloud_via_slot_prefix(monkeypatch) -> None:
    """``cloud:`` prefix Ollama is no-auto-detect even at localhost URL.

    OSS Ollama at localhost can proxy *:cloud models out to ollama.com
    on the user's behalf — the slot prefix encodes the destination, not
    the URL host.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _seed_settings_endpoints(monkeypatch, [
        {"id": "default_ollama", "provider": "ollama", "url": "http://localhost:11434"},
    ])
    assert pipeline_scheduler._provider_supports_auto_detect(
        "cloud:default_ollama"
    ) is False


def test_resolver_ollama_local_via_slot_prefix(monkeypatch) -> None:
    """``local:`` prefix Ollama supports auto-detect via /api/ps probe."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _seed_settings_endpoints(monkeypatch, [
        {"id": "default_ollama", "provider": "ollama", "url": "http://localhost:11434"},
    ])
    assert pipeline_scheduler._provider_supports_auto_detect(
        "local:default_ollama"
    ) is True


def test_resolver_kimi_via_openai_compatible(monkeypatch) -> None:
    """C2: Kimi saved as ``provider=openai-compatible`` (the only option
    the UI exposes) must still resolve to ``moonshot_kimi`` and report
    no-auto-detect — Kimi publishes per-tier concurrent limits but does
    not expose predictive headers.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _seed_settings_endpoints(monkeypatch, [
        {
            "id": "kimi_endpoint",
            "provider": "openai-compatible",
            "url": "https://api.moonshot.ai/v1",
        },
    ])
    assert pipeline_scheduler._provider_supports_auto_detect(
        "cloud:kimi_endpoint"
    ) is False


def test_resolver_openai_compatible_unknown_host_defaults_to_oai(monkeypatch) -> None:
    """A generic openai-compatible endpoint (not Moonshot) is treated as
    OpenAI for auto-detect purposes — the OAI shape implies rate-limit
    headers.  Conservative: don't disable AIMD when we can't classify.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _seed_settings_endpoints(monkeypatch, [
        {
            "id": "generic",
            "provider": "openai-compatible",
            "url": "https://api.example.com/v1",
        },
    ])
    assert pipeline_scheduler._provider_supports_auto_detect(
        "cloud:generic"
    ) is True


def test_resolver_unknown_endpoint_logs_warning_and_defaults_true(
    monkeypatch, caplog,
) -> None:
    """When the cloud:<id> doesn't match any saved endpoint, the helper
    must default to True (legacy AIMD) AND emit a WARNING so the user
    has a breadcrumb if 1/1 reappears.
    """
    import logging
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _seed_settings_endpoints(monkeypatch, [])
    with caplog.at_level(logging.WARNING):
        result = pipeline_scheduler._provider_supports_auto_detect(
            "cloud:nonexistent"
        )
    assert result is True
    assert any(
        "no saved endpoint matches" in rec.message
        for rec in caplog.records
    )


def test_resolver_anthropic_keeps_auto_detect(monkeypatch) -> None:
    """Anthropic exposes anthropic-ratelimit-* headers; AIMD edge-lock
    stays enabled for it."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    _seed_settings_endpoints(monkeypatch, [
        {
            "id": "claude_endpoint",
            "provider": "anthropic",
            "url": "https://api.anthropic.com",
        },
    ])
    assert pipeline_scheduler._provider_supports_auto_detect(
        "cloud:claude_endpoint"
    ) is True


# ── Hydration discard (M4): regression for the user's exact bug. ──


def test_configure_node_discards_persisted_lock_for_no_auto_detect(
    monkeypatch, tmp_path,
) -> None:
    """The user's reported bug: a pre-Phase-A AIMD backoff persisted
    ``ceiling=1, locked_until=future`` for cloud:default_ollama.  On
    daemon restart, configure_node hydrated this stale record and the
    Plan dropdown's Max=10 was overridden to 1/1.

    After Phase A 8: configure_node MUST discard a persisted record for
    no-auto-detect providers, clear the store row, and seed at
    max_concurrent in CA mode.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: False,
    )

    node_id = "cloud:hydration-discard"
    # Pre-seed the persisted lock the way the old AIMD code would have.
    import time
    store_mod.concurrency_store().save_edge(
        node_id, "__default__",
        ceiling=1,
        locked_until=time.time() + 24 * 3600,
        edge_observed_at=time.time(),
    )
    pipeline_scheduler._slots.pop(node_id, None)
    pipeline_scheduler._queues.pop(node_id, None)

    pipeline_scheduler.configure_node(node_id, max_concurrent=10)

    slot = pipeline_scheduler._slots[node_id]
    assert slot.max_concurrent == 10
    assert slot.current_limit == 10, (
        f"expected current_limit=10 (user's max), got {slot.current_limit}"
    )
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0
    assert slot.mode == "congestion_avoidance"
    # The store row should also be cleared so it doesn't haunt the next
    # restart cycle.
    record = store_mod.concurrency_store().load_full(node_id, "__default__")
    assert record is None, f"expected store cleared, found {record!r}"


def test_configure_node_keeps_persisted_lock_for_auto_detect(
    monkeypatch, tmp_path,
) -> None:
    """For header-rich providers (OpenAI / Anthropic / OSS Ollama) the
    persisted ceiling is genuinely useful — restart should hydrate it
    so AIMD doesn't replay 5→10→20→40 doubling on every daemon boot.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: True,
    )

    node_id = "cloud:hydration-keep"
    import time
    locked_until = time.time() + 24 * 3600
    store_mod.concurrency_store().save_edge(
        node_id, "__default__",
        ceiling=20,
        locked_until=locked_until,
        edge_observed_at=time.time(),
    )
    pipeline_scheduler._slots.pop(node_id, None)
    pipeline_scheduler._queues.pop(node_id, None)

    pipeline_scheduler.configure_node(node_id, max_concurrent=80)

    slot = pipeline_scheduler._slots[node_id]
    assert slot.max_concurrent == 80
    assert slot.current_limit == 20  # hydrated from store
    assert slot.discovered_ceiling == 20
    assert slot.ceiling_locked_until == locked_until


# ── Clear endpoint (M5): /compute/concurrency/clear honors Phase A 8. ──


def test_clear_endpoint_resets_no_auto_detect_to_max_in_ca(
    monkeypatch, tmp_path,
) -> None:
    """The clear endpoint historically reset cloud slots to jumpstart=5.
    For no-auto-detect providers the user's max IS the answer — reset
    must seed at max_concurrent in CA mode, not the legacy ramp seed.
    """
    from fastapi.testclient import TestClient
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.server import app

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: False,
    )

    node_id = "cloud:clear-noad"
    pipeline_scheduler._slots.pop(node_id, None)
    pipeline_scheduler._queues.pop(node_id, None)
    pipeline_scheduler.configure_node(node_id, max_concurrent=10)
    # Force a degraded current_limit to mimic post-backoff state.
    pipeline_scheduler._slots[node_id].current_limit = 3

    client = TestClient(app)
    resp = client.post(
        "/compute/concurrency/clear",
        params={"node_id": node_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["new_limit"] == 10
    assert body["new_mode"] == "congestion_avoidance"


# ── _persist_cloud_ceiling gate (I4) ──


def test_persist_cloud_ceiling_skipped_for_no_auto_detect(
    monkeypatch, tmp_path,
) -> None:
    """``_persist_cloud_ceiling`` is called from the AIMD backoff path
    (multiplicative-decrease writes the new ceiling to ConcurrencyStore).
    For no-auto-detect providers, the persisted ceiling would override
    the user's max on the next restart — even with hydration discard,
    a within-run 429 would still cap growth.  Gate it so a transient
    backoff writes nothing.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import (
        ComputeSlot, pipeline_scheduler,
    )

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    monkeypatch.setattr(
        pipeline_scheduler,
        "_provider_supports_auto_detect",
        lambda _node_id: False,
    )

    slot = ComputeSlot(
        node_id="cloud:persist-noad",
        max_concurrent=10,
        current_limit=5,
    )
    pipeline_scheduler._persist_cloud_ceiling(slot)

    record = store_mod.concurrency_store().load_full(
        "cloud:persist-noad", "__default__",
    )
    assert record is None, (
        f"expected store empty for no-auto-detect; got {record!r}"
    )

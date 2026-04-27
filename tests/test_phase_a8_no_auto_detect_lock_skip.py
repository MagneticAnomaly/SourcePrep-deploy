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

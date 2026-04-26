"""Phase 119: queue/status node_summary exposes ceiling-lock state."""
from __future__ import annotations

import time
from unittest.mock import patch

from fastapi.testclient import TestClient


def _make_app():
    from prep.server import app
    return app


def test_node_summary_includes_state_fields(monkeypatch, tmp_path) -> None:
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    pipeline_scheduler.configure_node("cloud:status-test", max_concurrent=1)
    slot = pipeline_scheduler._slots["cloud:status-test"]
    slot.current_limit = 8
    slot.discovered_ceiling = 10
    slot.ceiling_locked_until = time.time() + 3600

    app = _make_app()
    client = TestClient(app)
    resp = client.get("/system/pipeline-queue")
    body = resp.json()
    assert resp.status_code == 200
    nodes = body.get("nodes") or body.get("data", {}).get("nodes")
    n = nodes["cloud:status-test"]
    assert n["discovered_ceiling"] == 10
    assert n["locked_until"] > time.time()
    assert n["aimd_mode"] in ("jumpstart", "congestion_avoidance")
    assert n["state"] in ("probing", "locked", "backing_off", "recovering")


def test_state_locked_when_within_ttl() -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=10,
        ceiling_locked_until=time.time() + 3600,
        last_backoff_time=time.time() - 600,
        backoff_cooldown_s=30.0,
    )
    assert s == "locked"


def test_state_backing_off_when_recent_backoff() -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=10,
        ceiling_locked_until=time.time() + 3600,
        last_backoff_time=time.time() - 5,   # 5 s ago < cooldown 30 s
        backoff_cooldown_s=30.0,
    )
    assert s == "backing_off"


def test_state_recovering_when_lock_expired() -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=10,
        ceiling_locked_until=time.time() - 1,
        last_backoff_time=time.time() - 6000,
        backoff_cooldown_s=30.0,
    )
    assert s == "recovering"


def test_state_probing_when_no_lock_no_backoff() -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=None,
        ceiling_locked_until=0.0,
        last_backoff_time=0.0,
        backoff_cooldown_s=30.0,
    )
    assert s == "probing"


def test_clear_concurrency_endpoint_invalidates_lock(monkeypatch, tmp_path) -> None:
    """POST /compute/concurrency/clear?node_id=... clears the persisted lock."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    pipeline_scheduler.configure_node("cloud:lock-test", max_concurrent=1)
    slot = pipeline_scheduler._slots["cloud:lock-test"]
    slot.discovered_ceiling = 10
    slot.ceiling_locked_until = time.time() + 3600
    store_mod.concurrency_store().save_edge(
        "cloud:lock-test", "__default__",
        ceiling=10, locked_until=slot.ceiling_locked_until, edge_observed_at=time.time(),
    )

    app = _make_app()
    client = TestClient(app)
    # Use the actual mounted path. The compute router prefix needs to be
    # verified in the router file; if it's "/compute" then "/compute/concurrency/clear",
    # otherwise adjust accordingly.
    resp = client.post("/compute/concurrency/clear", params={"node_id": "cloud:lock-test"})
    assert resp.status_code in (200, 204)

    # Slot lock cleared in-memory.
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0
    # Persisted record gone.
    assert store_mod.concurrency_store().load_full("cloud:lock-test", "__default__") is None


def test_clear_concurrency_full_reset_cloud_default(monkeypatch, tmp_path) -> None:
    """Phase 119 Task 16: full-reset semantics for the canonical Ollama slot.

    Pre-Task-16 the endpoint cleared `discovered_ceiling` only; the test
    pins the new behavior — `current_limit` actually drops back to the
    fresh probe / jumpstart seed, mode resets to ``jumpstart`` for
    cloud:* slots, and a ``reset`` event lands in the history buffer.
    """
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline import ollama_probe as probe_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    # Force the probe to a deterministic value so the test doesn't
    # depend on a real Ollama daemon being reachable.
    monkeypatch.setattr(
        probe_mod, "probe_ollama_concurrency", lambda host, timeout=1.5: 9,
    )

    pipeline_scheduler.configure_node("cloud:default_ollama", max_concurrent=1)
    slot = pipeline_scheduler._slots["cloud:default_ollama"]
    # Simulate the post-jumpstart "stuck at 53" state the user reported.
    slot.current_limit = 53
    slot.mode = "congestion_avoidance"
    slot.success_streak = 7
    slot._last_backoff_time = time.time()
    slot.discovered_ceiling = 53
    slot.ceiling_locked_until = time.time() + 3600

    app = _make_app()
    client = TestClient(app)
    resp = client.post(
        "/compute/concurrency/clear",
        params={"node_id": "cloud:default_ollama"},
    )
    assert resp.status_code in (200, 204)
    body = resp.json()
    assert body["status"] == "ok"
    assert body["node_id"] == "cloud:default_ollama"
    assert body["old_limit"] == 53
    # probe_ollama_concurrency stub returns 9 → new_limit must follow.
    assert body["new_limit"] == 9
    assert body["new_mode"] == "jumpstart"

    # In-memory state actually changed (the bug the user reported).
    assert slot.current_limit == 9
    assert slot.mode == "jumpstart"
    assert slot.success_streak == 0
    assert slot._last_backoff_time == 0.0
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0

    # Reset event landed in the per-slot history ring buffer.
    history = list(slot._history)
    assert any(
        e.get("reason") == "reset" and e.get("before") == 53 and e.get("after") == 9
        for e in history
    ), f"expected reset event in history, got: {history}"


def test_clear_concurrency_full_reset_other_cloud_slot(monkeypatch, tmp_path) -> None:
    """Phase 119 Task 16: non-Ollama cloud slots reset to jumpstart=5."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    pipeline_scheduler.configure_node("cloud:openrouter_anthropic", max_concurrent=1)
    slot = pipeline_scheduler._slots["cloud:openrouter_anthropic"]
    slot.current_limit = 22
    slot.mode = "congestion_avoidance"

    app = _make_app()
    client = TestClient(app)
    resp = client.post(
        "/compute/concurrency/clear",
        params={"node_id": "cloud:openrouter_anthropic"},
    )
    body = resp.json()
    assert body["new_limit"] == 5  # jumpstart seed
    assert body["new_mode"] == "jumpstart"
    assert slot.current_limit == 5
    assert slot.mode == "jumpstart"


def test_clear_concurrency_local_slot_normalizes(monkeypatch, tmp_path) -> None:
    """Phase 119 Task 16: local slots normalize current_limit to max_concurrent."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    pipeline_scheduler.configure_node("local:gpu0", max_concurrent=4)
    slot = pipeline_scheduler._slots["local:gpu0"]
    slot.current_limit = 1  # Pretend AIMD shrank it during a transient blip
    slot.success_streak = 3

    app = _make_app()
    client = TestClient(app)
    resp = client.post(
        "/compute/concurrency/clear", params={"node_id": "local:gpu0"},
    )
    body = resp.json()
    # Local slots clamp to max_concurrent rather than rediscovering.
    assert body["new_limit"] == 4
    assert slot.current_limit == 4
    assert slot.success_streak == 0


def test_node_summary_shape_is_documented(monkeypatch, tmp_path) -> None:
    """Pin the field set so silent contract changes break tests."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline.scheduler import pipeline_scheduler

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    pipeline_scheduler.configure_node("cloud:contract-test", max_concurrent=1)

    app = _make_app()
    client = TestClient(app)
    resp = client.get("/system/pipeline-queue")
    body = resp.json()
    nodes = body.get("nodes") or body.get("data", {}).get("nodes")
    n = nodes["cloud:contract-test"]
    expected = {
        "max_concurrent", "current_load", "in_flight_requests",
        "current_limit", "discovered_ceiling", "locked_until",
        "aimd_mode", "state", "active", "queued",
    }
    assert set(n.keys()) >= expected, f"missing fields: {expected - set(n.keys())}"

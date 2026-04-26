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

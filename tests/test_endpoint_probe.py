"""Phase 119 Phase C: capacity probe orchestration + saturation detection.

The probe fires ``burst_size`` parallel calibrated requests at a saved
endpoint, measures per-request wall-clock, and detects a saturation
point on the latency staircase. We never make real HTTP calls in tests
— ``_dispatch_request`` is monkey-patched out.

Coverage:
  * ``run_probe`` looks up the saved endpoint (error path included)
  * burst orchestration honors ``burst_size`` and the ≤50 hard cap
  * staircase saturation detection finds the cliff
  * header-hint short-circuits the staircase path
  * histogram persistence writes a JSON record
  * probe_history ring buffer per-endpoint
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest


# ── Fixtures / helpers ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_probe_state(monkeypatch, tmp_path: Path):
    """Redirect data_dir to tmp and clear the in-memory ring per test."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import endpoint_probe

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    endpoint_probe.probe_history.clear()
    yield
    endpoint_probe.probe_history.clear()


def _stub_settings(monkeypatch, endpoints: List[Dict[str, Any]]) -> None:
    """Stub the settings module so probe code finds our test endpoints."""
    from prep.services import settings_store

    class _StubSettings:
        def get(self, key: str) -> Any:
            if key == "llm_config":
                return {"saved_endpoints": endpoints}
            return None

    monkeypatch.setattr(settings_store, "settings", _StubSettings())


def _make_dispatch(latencies: List[float], status: str = "ok"):
    """Build a fake ``_dispatch_request`` that returns each latency in turn.

    Latencies are seconds. Each call sleeps for the next latency and
    returns ``(status, headers, error)``.
    """
    counter = {"i": 0}
    lock = asyncio.Lock()

    async def _dispatch(*, endpoint, model, timeout_s):
        async with lock:
            i = counter["i"]
            counter["i"] += 1
        delay = latencies[i % len(latencies)]
        await asyncio.sleep(delay)
        return status, {}, None

    return _dispatch


# ── Saturation detection (pure logic) ────────────────────────────


def test_detect_saturation_finds_latency_cliff() -> None:
    """A staircase profile (fast first 5, then slow) should fire at ~6."""
    from prep.services.pipeline.endpoint_probe import _RequestSample, detect_saturation

    base = time.time()
    # First 5 are fast (~50ms), the rest are 5x slower (~250ms).
    samples: List[_RequestSample] = []
    for i in range(20):
        dispatch = base + i * 0.001
        d_ms = 50.0 if i < 5 else 250.0
        samples.append(
            _RequestSample(
                index=i, dispatch_at=dispatch, complete_at=dispatch + d_ms / 1000.0,
                duration_ms=d_ms, status="ok",
            )
        )

    sat, method = detect_saturation(samples)
    assert method == "latency_staircase"
    assert sat is not None
    assert 6 <= sat <= 10, f"expected saturation in 6..10, got {sat}"


def test_detect_saturation_returns_none_when_flat() -> None:
    """No latency cliff = no saturation point."""
    from prep.services.pipeline.endpoint_probe import _RequestSample, detect_saturation

    base = time.time()
    samples = [
        _RequestSample(
            index=i, dispatch_at=base + i * 0.001, complete_at=base + 0.05,
            duration_ms=50.0, status="ok",
        )
        for i in range(20)
    ]
    sat, method = detect_saturation(samples)
    assert sat is None
    assert method == "none"


def test_detect_saturation_header_hint_short_circuits() -> None:
    """A header hint with score≥0.5 + suggested_max wins over staircase."""
    from prep.services.pipeline.endpoint_probe import _RequestSample, detect_saturation

    base = time.time()
    samples = [
        _RequestSample(
            index=i, dispatch_at=base + i * 0.001, complete_at=base + 0.05,
            duration_ms=50.0, status="ok",
        )
        for i in range(20)
    ]
    sat, method = detect_saturation(
        samples, header_hint_score=0.8, header_hint_suggested_max=12,
    )
    assert sat == 12
    assert method == "header"


# ── run_probe orchestration ──────────────────────────────────────


def test_run_probe_unknown_endpoint_raises(monkeypatch) -> None:
    """Probing a non-existent endpoint raises ValueError."""
    from prep.services.pipeline import endpoint_probe

    _stub_settings(monkeypatch, [])  # no endpoints saved
    with pytest.raises(ValueError, match="Unknown endpoint id"):
        asyncio.run(endpoint_probe.run_probe("missing", burst_size=4))


def test_run_probe_persists_histogram_and_appends_history(monkeypatch, tmp_path) -> None:
    """A successful probe writes a JSON record AND pushes to ring."""
    from prep.services.pipeline import endpoint_probe

    _stub_settings(monkeypatch, [{
        "id": "ep-1", "provider": "openai", "url": "https://api.openai.test",
        "api_key": "sk-test",
    }])
    # All fast — flat profile, no saturation.
    monkeypatch.setattr(
        endpoint_probe, "_dispatch_request", _make_dispatch([0.01] * 8),
    )
    result = asyncio.run(endpoint_probe.run_probe("ep-1", burst_size=8))

    assert result.endpoint_id == "ep-1"
    assert result.successes == 8
    assert result.errors == 0
    assert result.histogram_path is not None
    assert Path(result.histogram_path).exists()

    # Ring buffer received it
    history = endpoint_probe.probe_history.get("ep-1")
    assert len(history) == 1
    assert history[0]["endpoint_id"] == "ep-1"


def test_run_probe_clamps_burst_size(monkeypatch) -> None:
    """burst_size > 50 is clamped to 50; < 1 is clamped to 1."""
    from prep.services.pipeline import endpoint_probe

    _stub_settings(monkeypatch, [{
        "id": "ep-1", "provider": "ollama", "url": "http://localhost:11434",
    }])
    monkeypatch.setattr(
        endpoint_probe, "_dispatch_request", _make_dispatch([0.001] * 60),
    )

    high = asyncio.run(endpoint_probe.run_probe("ep-1", burst_size=999))
    assert high.burst_size == 50
    assert high.successes == 50

    low = asyncio.run(endpoint_probe.run_probe("ep-1", burst_size=0))
    assert low.burst_size == 1


def test_run_probe_recommends_one_below_saturation(monkeypatch) -> None:
    """When saturation is detected, recommended = saturation - 1."""
    from prep.services.pipeline import endpoint_probe

    _stub_settings(monkeypatch, [{
        "id": "ep-stair", "provider": "anthropic", "url": "https://api.anthropic.test",
        "api_key": "sk-ant-test",
    }])
    # Staircase: first 4 fast (~10ms), next 16 slow (~80ms).
    latencies = [0.01] * 4 + [0.08] * 16
    monkeypatch.setattr(
        endpoint_probe, "_dispatch_request", _make_dispatch(latencies),
    )
    result = asyncio.run(endpoint_probe.run_probe("ep-stair", burst_size=20))

    # Some saturation should be detected because fast-cluster median * 2
    # is comfortably below the slow cluster's p90.
    if result.saturation_point is not None:
        assert result.recommended_concurrent == result.saturation_point - 1
        assert 1 <= result.recommended_concurrent <= 20


# ── In-memory history store ──────────────────────────────────────


def test_probe_history_ring_per_endpoint() -> None:
    """The history store is keyed by endpoint and ring-buffer-bounded."""
    from prep.services.pipeline.endpoint_probe import probe_history

    for i in range(15):
        probe_history.append("ep-A", {"i": i, "endpoint_id": "ep-A"})
    probe_history.append("ep-B", {"i": 99, "endpoint_id": "ep-B"})

    a_hist = probe_history.get("ep-A", limit=20)
    # Default maxlen is 10
    assert len(a_hist) == 10
    # Newest at the end
    assert a_hist[-1]["i"] == 14
    # ep-B isolated
    b_hist = probe_history.get("ep-B")
    assert len(b_hist) == 1
    assert b_hist[0]["i"] == 99


def test_probe_history_endpoint_returns_records(monkeypatch, tmp_path) -> None:
    """The /compute/endpoint-probe/history endpoint returns the buffer."""
    from fastapi.testclient import TestClient

    from prep.core import paths as paths_mod
    from prep.server import app
    from prep.services.pipeline import endpoint_probe

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    endpoint_probe.probe_history.clear()
    endpoint_probe.probe_history.append("ep-history", {
        "endpoint_id": "ep-history",
        "probed_at": time.time(),
        "burst_size": 8,
        "wall_clock_ms": {"p50": 50.0, "p90": 100.0, "p99": 200.0},
        "saturation_point": 6,
        "saturation_method": "latency_staircase",
        "recommended_concurrent": 5,
        "successes": 8,
        "errors": 0,
    })

    client = TestClient(app)
    resp = client.get(
        "/compute/endpoint-probe/history",
        params={"endpoint_id": "ep-history"},
    )
    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", body)
    assert data["endpoint_id"] == "ep-history"
    assert len(data["probes"]) == 1
    assert data["probes"][0]["recommended_concurrent"] == 5


def test_endpoint_probe_post_endpoint_returns_404_for_missing(monkeypatch) -> None:
    """POST /compute/endpoint-probe returns 404 when the endpoint id is unknown."""
    from fastapi.testclient import TestClient

    from prep.server import app

    _stub_settings(monkeypatch, [])

    client = TestClient(app)
    resp = client.post(
        "/compute/endpoint-probe",
        json={"endpoint_id": "missing", "burst_size": 4},
    )
    assert resp.status_code == 404
    body = resp.json()
    # Envelope error shape: {"error": {"code": ...}} or fastapi default
    error_code = (
        body.get("error", {}).get("code")
        or body.get("detail", {}).get("error", {}).get("code")
    )
    assert error_code == "ENDPOINT_NOT_FOUND"

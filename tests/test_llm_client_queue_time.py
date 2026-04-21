"""queue_time_ms computation: use Ollama's server-reported total_duration.

The AIMD scheduler no longer uses queue_time_ms as a backoff trigger (that
signal was semantically wrong — it measured unaccounted inference overhead,
not queue depth; see Ollama issue #10860). The field is now diagnostic only,
logged for observability and reserved for future per-token / tokens-per-second
signals.

These tests pin the measurement semantics: when Ollama reports total_duration
in the `done` chunk, use that as the reference (server-side elapsed, excludes
network RTT); otherwise fall back to wall time.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


def _ollama_done_chunk(
    *,
    response_text: str = "ok",
    eval_duration_ns: int = 1_000_000_000,
    prompt_eval_duration_ns: int = 500_000_000,
    load_duration_ns: int = 0,
    total_duration_ns: int = 1_500_000_000,
    eval_count: int = 3,
    prompt_eval_count: int = 10,
) -> str:
    """Build an Ollama /api/generate NDJSON response body (one final 'done' chunk)."""
    chunk = {
        "response": response_text,
        "done": True,
        "eval_count": eval_count,
        "prompt_eval_count": prompt_eval_count,
        "eval_duration": eval_duration_ns,
        "prompt_eval_duration": prompt_eval_duration_ns,
        "load_duration": load_duration_ns,
        "total_duration": total_duration_ns,
    }
    return json.dumps(chunk)


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200, headers: dict | None = None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def close(self) -> None:
        pass


def _make_client():
    from prep.core.llm_client import LLMClient
    return LLMClient(
        endpoint_url="http://localhost:11434",
        model="kimi-k2.5:cloud",
        provider="ollama",
    )


def test_queue_time_uses_server_total_duration_not_wall_time():
    """Ollama Cloud: wall_time is dominated by network, telemetry must report server-side only."""
    client = _make_client()

    # Server reports: 1.5s total, of which 1.5s was compute.
    # Client measures: 10s wall (because 8.5s was network upload/download).
    # Old formula: 10s - 1.5s = 8.5s → inflated by network RTT.
    # New formula: 1.5s (server total) - 1.5s (compute) = 0s → clean signal.
    body = _ollama_done_chunk(
        eval_duration_ns=1_000_000_000,
        prompt_eval_duration_ns=500_000_000,
        load_duration_ns=0,
        total_duration_ns=1_500_000_000,
    )

    captured: dict = {}

    def fake_record(self, queue_time_ms: float = 0.0, **_):
        captured["queue_time_ms"] = queue_time_ms

    with patch.object(client._session, "post", return_value=_FakeResponse(body)), \
         patch("prep.core.llm_client.LLMClient._record_throughput", new=fake_record), \
         patch("time.monotonic", side_effect=[0.0, 10.0]):  # 10s wall clock
        client._generate_internal(prompt="hi", json_mode=False)

    assert "queue_time_ms" in captured, "_record_throughput was not called"
    # queue_time_ms should be ~0 (server_total - exec), NOT ~8500
    assert captured["queue_time_ms"] < 100.0, (
        f"queue_time_ms={captured['queue_time_ms']} — should reflect server-side "
        f"elapsed only, not client wall time. Wall time would leak network RTT "
        f"into the telemetry signal."
    )


def test_queue_time_reflects_real_server_queue():
    """Server IS congested — queue_time should reflect the delta."""
    client = _make_client()

    # Server reports: 5s total, of which 1.5s was compute.  Server queued 3.5s.
    # Client wall: 10s (5s server + 5s network).
    # Expected queue_time: 3.5s (real server queue, not inflated by network).
    body = _ollama_done_chunk(
        eval_duration_ns=1_000_000_000,
        prompt_eval_duration_ns=500_000_000,
        load_duration_ns=0,
        total_duration_ns=5_000_000_000,
    )

    captured: dict = {}

    def fake_record(self, queue_time_ms: float = 0.0, **_):
        captured["queue_time_ms"] = queue_time_ms

    with patch.object(client._session, "post", return_value=_FakeResponse(body)), \
         patch("prep.core.llm_client.LLMClient._record_throughput", new=fake_record), \
         patch("time.monotonic", side_effect=[0.0, 10.0]):
        client._generate_internal(prompt="hi", json_mode=False)

    assert captured["queue_time_ms"] == pytest.approx(3500.0, abs=10.0)


def test_queue_time_falls_back_to_wall_time_when_total_duration_missing():
    """Providers that don't return total_duration fall back to wall-time delta."""
    client = _make_client()

    # Response has NO total_duration field.  Only eval/prompt_eval durations.
    chunk = {
        "response": "ok",
        "done": True,
        "eval_count": 3,
        "prompt_eval_count": 10,
        "eval_duration": 1_000_000_000,
        "prompt_eval_duration": 500_000_000,
        "load_duration": 0,
        # total_duration intentionally omitted
    }
    body = json.dumps(chunk)

    captured: dict = {}

    def fake_record(self, queue_time_ms: float = 0.0, **_):
        captured["queue_time_ms"] = queue_time_ms

    with patch.object(client._session, "post", return_value=_FakeResponse(body)), \
         patch("prep.core.llm_client.LLMClient._record_throughput", new=fake_record), \
         patch("time.monotonic", side_effect=[0.0, 10.0]):
        client._generate_internal(prompt="hi", json_mode=False)

    # Fallback: wall (10s) - exec (1.5s) = 8.5s
    assert captured["queue_time_ms"] == pytest.approx(8500.0, abs=10.0)

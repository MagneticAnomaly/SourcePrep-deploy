"""Phase 82 follow-up: LLMClient threads every HTTP call through the
PipelineScheduler per-request gate, so AIMD's discovered ceiling becomes
the effective concurrency limit.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from codrag.core.llm_client import LLMClient
from codrag.services.pipeline.scheduler import PipelineScheduler


def _seed_scheduler(limit: int = 2) -> tuple[PipelineScheduler, str]:
    """Seed the shared scheduler with a cloud slot at the given limit."""
    from codrag.services.pipeline import scheduler as sched_mod
    sched = sched_mod.pipeline_scheduler
    node_id = "cloud:gate-test"
    sched.configure_node(node_id, max_concurrent=limit)
    slot = sched._slots[node_id]
    slot.current_limit = limit
    slot.mode = "congestion_avoidance"
    slot.in_flight_requests = 0
    slot._live_tokens = set()
    return sched, node_id


@pytest.fixture(autouse=True)
def _reset_scheduler():
    """Clear scheduler state between tests to avoid cross-test leakage."""
    from codrag.services.pipeline import scheduler as sched_mod
    sched_mod.pipeline_scheduler._slots.clear()
    sched_mod.pipeline_scheduler._queues.clear()
    sched_mod.pipeline_scheduler._init_embedding_slot()
    yield
    sched_mod.pipeline_scheduler._slots.clear()
    sched_mod.pipeline_scheduler._queues.clear()
    sched_mod.pipeline_scheduler._init_embedding_slot()


def _mock_ollama_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = (
        '{"response": "ok", "thinking": "", "done": false, '
        '"eval_count": 0, "prompt_eval_count": 0}\n'
        '{"response": "", "thinking": "", "done": true, '
        '"eval_count": 10, "prompt_eval_count": 5, '
        '"eval_duration": 1000000, "prompt_eval_duration": 500000, '
        '"load_duration": 100000, "total_duration": 1600000}'
    )
    resp.close = MagicMock()
    resp.raise_for_status = MagicMock()
    return resp


def test_llm_call_increments_in_flight_during_http() -> None:
    """While the HTTP call is in flight, slot.in_flight_requests == 1."""
    sched, node_id = _seed_scheduler(limit=2)
    slot = sched._slots[node_id]

    observed = {}

    def _fake_post(*_a, **_kw):
        observed["in_flight_during_http"] = slot.in_flight_requests
        return _mock_ollama_response()

    client = LLMClient(endpoint_url="http://localhost:11434", provider="ollama", model="kimi-k2.5:cloud")
    with patch.object(client._session, "post", side_effect=_fake_post):
        client.generate(prompt="hi", json_mode=False, num_predict=8)

    assert observed["in_flight_during_http"] == 1
    assert slot.in_flight_requests == 0


def test_llm_call_blocks_when_gate_full() -> None:
    """With limit=1, the second concurrent call must block until first completes."""
    sched, node_id = _seed_scheduler(limit=1)
    slot = sched._slots[node_id]

    release_event = threading.Event()
    entered_count = {"value": 0}
    entered_lock = threading.Lock()

    def _slow_post(*_a, **_kw):
        with entered_lock:
            entered_count["value"] += 1
        release_event.wait(timeout=5.0)
        return _mock_ollama_response()

    client = LLMClient(endpoint_url="http://localhost:11434", provider="ollama", model="kimi-k2.5:cloud")

    def _call() -> None:
        with patch.object(client._session, "post", side_effect=_slow_post):
            client.generate(prompt="hi", json_mode=False, num_predict=8)

    t1 = threading.Thread(target=_call)
    t2 = threading.Thread(target=_call)
    t1.start()
    t2.start()

    time.sleep(0.3)
    assert entered_count["value"] == 1
    assert slot.in_flight_requests == 1

    release_event.set()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert entered_count["value"] == 2
    assert slot.in_flight_requests == 0


def test_gate_releases_even_on_exception() -> None:
    """If the HTTP call raises, the gate token must still be released."""
    import requests
    sched, node_id = _seed_scheduler(limit=1)
    slot = sched._slots[node_id]

    def _failing_post(*_a, **_kw):
        raise requests.exceptions.ConnectionError("network down")

    client = LLMClient(endpoint_url="http://localhost:11434", provider="ollama", model="kimi-k2.5:cloud")
    with patch.object(client._session, "post", side_effect=_failing_post):
        with pytest.raises(requests.exceptions.ConnectionError):
            client.generate(prompt="hi", json_mode=False, num_predict=8)

    assert slot.in_flight_requests == 0


def test_gate_timeout_falls_back_to_raw_call() -> None:
    """If the gate times out, LLMClient should proceed with the HTTP call
    uncapped rather than hang forever — blocked pipelines are worse than
    briefly exceeding current_limit; AIMD catches overload via 429/5xx."""
    sched, node_id = _seed_scheduler(limit=1)
    slot = sched._slots[node_id]
    pre_token = sched.acquire_request(node_id, timeout=0.5)
    assert pre_token is not None

    client = LLMClient(endpoint_url="http://localhost:11434", provider="ollama", model="kimi-k2.5:cloud")
    with patch.object(client._session, "post", return_value=_mock_ollama_response()):
        with patch(
            "codrag.core.llm_client._REQUEST_GATE_TIMEOUT_S", 0.3
        ):
            t_start = time.monotonic()
            text, tokens = client.generate(
                prompt="hi", json_mode=False, num_predict=8,
            )
            elapsed = time.monotonic() - t_start

    # Proceeded despite the gate being full.
    assert 0.25 <= elapsed <= 1.5, f"elapsed={elapsed}"

    sched.release_request(pre_token)


def test_get_llm_concurrency_honors_explicit_cap_when_above_default(monkeypatch) -> None:
    """A user-set ``llm_concurrency_deep=24`` caps the return value at 24 even
    when AIMD has discovered a larger budget. Explicit settings above the
    default of 1 are treated as an upper bound (VRAM protection use case).
    """
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings
    from codrag.services.pipeline import scheduler as sched_mod

    def _fake_get(k, default=None):
        if k == "pipeline_config":
            return {"llm_concurrency_deep": 24}
        return default

    monkeypatch.setattr(settings, "get", _fake_get)
    sched = sched_mod.pipeline_scheduler
    sched.configure_node("cloud:kimi", max_concurrent=10)
    sched._slots["cloud:kimi"].current_limit = 49  # AIMD discovered 49

    assert _get_llm_concurrency("deep") == 24


def test_get_llm_concurrency_clamps_to_pool_ceiling(monkeypatch) -> None:
    """A value > pool max_workers (shared LLM pool's ceiling) is still clamped."""
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings
    from codrag.services.pipeline import scheduler as sched_mod
    from codrag.services.pipeline.thread_pool import llm_pool

    def _fake_get(k, default=None):
        if k == "pipeline_config":
            return {"llm_concurrency_deep": 100}
        return default

    monkeypatch.setattr(settings, "get", _fake_get)
    sched = sched_mod.pipeline_scheduler
    sched.configure_node("cloud:kimi", max_concurrent=10)
    sched._slots["cloud:kimi"].current_limit = 100

    assert _get_llm_concurrency("deep") == llm_pool.max_workers


def test_get_llm_concurrency_scales_with_aimd_when_setting_stale(monkeypatch) -> None:
    """Phase 82 completion: when stored setting is 1 (stale/default) but AIMD
    has discovered dynamic_capacity=20 on a cloud slot, the function must
    return the discovered budget — not the stored 1. This is the same
    mechanism get_batch_concurrency uses; all LLM fan-out paths converge on
    the scheduler-driven budget.
    """
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings
    from codrag.services.pipeline import scheduler as sched_mod

    def _fake_get(k, default=None):
        if k == "pipeline_config":
            return {"llm_concurrency_deep": 1, "llm_concurrency_fast": 1}
        return default

    monkeypatch.setattr(settings, "get", _fake_get)

    sched = sched_mod.pipeline_scheduler
    sched.configure_node("cloud:kimi", max_concurrent=10)
    slot = sched._slots["cloud:kimi"]
    slot.current_limit = 20  # dynamic_capacity for cloud slots = max(1, current_limit)

    assert _get_llm_concurrency("fast") == 20
    assert _get_llm_concurrency("deep") == 20


def test_get_llm_concurrency_clamps_aimd_to_pool_ceiling(monkeypatch) -> None:
    """If AIMD discovers dynamic_capacity > shared-pool max_workers, clamp to
    the pool ceiling — submitting beyond pool size has no parallelism benefit.
    """
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings
    from codrag.services.pipeline import scheduler as sched_mod
    from codrag.services.pipeline.thread_pool import llm_pool

    def _fake_get(k, default=None):
        if k == "pipeline_config":
            return {}
        return default

    monkeypatch.setattr(settings, "get", _fake_get)

    sched = sched_mod.pipeline_scheduler
    sched.configure_node("cloud:gem3", max_concurrent=10)
    slot = sched._slots["cloud:gem3"]
    slot.current_limit = 200

    assert _get_llm_concurrency("fast") == llm_pool.max_workers


def test_get_llm_concurrency_ignores_embedding_slot(monkeypatch) -> None:
    """Embedding slot has dynamic_capacity=2 (memory-detected); it must NOT
    drive LLM fan-out concurrency. Only non-embedding scheduler slots matter.
    """
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings
    from codrag.services.pipeline import scheduler as sched_mod

    def _fake_get(k, default=None):
        if k == "pipeline_config":
            return {}
        return default

    monkeypatch.setattr(settings, "get", _fake_get)

    sched = sched_mod.pipeline_scheduler
    # Inflate embedding slot to a high value to catch code that accidentally
    # consults it when computing LLM fan-out. A single local LLM slot at
    # current_limit=1 is the only legitimate LLM budget here.
    embed_slot = sched._slots["__embedding__"]
    embed_slot.current_limit = 16
    sched.configure_node("local:solo", max_concurrent=1)
    slot = sched._slots["local:solo"]
    slot.current_limit = 1

    assert _get_llm_concurrency("fast") == 1


def test_gate_timeout_survives_slot_removal() -> None:
    """If the slot is removed between gate-timeout and the warning log,
    generate() must still proceed uncapped rather than raise KeyError."""
    from codrag.services.pipeline import scheduler as sched_mod
    sched, node_id = _seed_scheduler(limit=1)
    pre_token = sched.acquire_request(node_id, timeout=0.5)
    assert pre_token is not None

    client = LLMClient(endpoint_url="http://localhost:11434", provider="ollama", model="kimi-k2.5:cloud")

    # Before the gate acquire_request_ctx returns (None on timeout),
    # remove the slot so the warning-log path must handle the missing slot.
    original_acquire_ctx = sched.acquire_request_ctx

    from contextlib import contextmanager

    @contextmanager
    def _acquire_ctx_then_remove(nid, timeout):
        with original_acquire_ctx(nid, timeout=timeout) as tok:
            if tok is None:
                sched.remove_node(nid)
            yield tok

    with patch.object(sched_mod.pipeline_scheduler, "acquire_request_ctx", _acquire_ctx_then_remove):
        with patch.object(client._session, "post", return_value=_mock_ollama_response()):
            with patch("codrag.core.llm_client._REQUEST_GATE_TIMEOUT_S", 0.2):
                text, tokens = client.generate(
                    prompt="hi", json_mode=False, num_predict=8,
                )
    # No KeyError raised — call succeeded.
    sched.release_request(pre_token)  # safe no-op since slot is gone

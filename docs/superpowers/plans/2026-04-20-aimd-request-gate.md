# Per-Request AIMD Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AIMD-discovered ceiling the only effective concurrency limit for LLM calls, so the scheduler actually gates requests (not per-stage ThreadPoolExecutor static caps).

**Architecture:** Today, `PipelineScheduler` discovers a real concurrency ceiling per cloud node (e.g. Ollama Cloud grows 5 → 15 → 40 via AIMD), but nothing consults that ceiling at LLM request time. Each pipeline stage creates its own `ThreadPoolExecutor(max_workers=concurrency)` where `concurrency = _get_llm_concurrency(stage)` is hard-capped at 8. The scheduler's slot system only tracks one `active_stages[project_id] → stage_id` entry per project per node — it's coarse-grained stage gating, not request gating. We fix this by adding per-request `acquire_request` / `release_request` API backed by a `threading.Condition` on each `ComputeSlot`, wrapping every LLM call in that gate, then removing the static caps so AIMD becomes the only gate.

**Tech Stack:** Python 3.11, `threading.Condition`, `contextmanager`, `pytest` (asyncio_mode=auto), existing `PipelineScheduler` / `ComputeSlot` infrastructure.

---

## Context for the Implementer

**What's already been done (don't redo):**
- Phase 82 AIMD is implemented in `src/codrag/services/pipeline/scheduler.py`. `ComputeSlot.current_limit` grows via jumpstart doubling + additive increase, shrinks via multiplicative decrease on explicit rejection signals only (429/5xx/timeout).
- Commit `f0b15afc` fixed the broken wall-clock backoff formula. `_record_throughput_for_slot` at `scheduler.py:482-574` now does rejection-primary AIMD.
- `LLMClient._record_throughput` at `llm_client.py:461-473` is already called from every provider path on success and failure (429/5xx/timeout).
- A shared bounded LLM thread pool exists at `src/codrag/services/pipeline/thread_pool.py` (default size 6, max 32 via `CODRAG_LLM_POOL_SIZE`). Some stages use it; deepening creates its own pool.

**The bug:**
- `src/codrag/core/deepening.py:456` creates `ThreadPoolExecutor(max_workers=concurrency)` where `concurrency = _get_llm_concurrency("deep")`.
- `_get_llm_concurrency` at `src/codrag/core/llm_client.py:225` returns `max(1, min(8, int(value)))` — hard cap of 8.
- If AIMD discovers a ceiling of 40, deepening still only submits 8 concurrent calls. The ceiling is a phantom — nothing consults it at request time.
- User observed: "deep reasoning go from 4 then 3 then 2, it should be moving up since there's availability." That's each stage sizing its pool once at start and never growing.

**The fix (rollout order in these 4 tasks):**
1. Add request-level gate to scheduler (new API, no callers). Tests first. No behavior change.
2. Wire `LLMClient._generate_internal` to call the gate around the HTTP call (Ollama path first, then OpenAI/Google). Gate is active but stages still have low caps, so nothing regresses.
3. Raise per-stage pool sizes to the shared pool max (32) and remove the `min(8, ...)` clamp in `_get_llm_concurrency`. AIMD is now the only gate.
4. Observability — expose per-slot `in_flight_requests` and `current_limit` to the dashboard so users can see the gate working.

**Design decisions locked in (don't re-debate):**
- Use `threading.Condition` wrapped around the existing `threading.RLock` (`scheduler.py:201`). Don't introduce a separate lock.
- Add an in-flight integer counter on `ComputeSlot`, not a deque of tokens. Release accepts a token stamped at acquire time for double-release detection.
- Bound the acquire with a 120s timeout — longer than any reasonable LLM call, short enough to surface deadlocks.
- Context manager wrapper `acquire_request_ctx(node_id)` so callers use `with` for try/finally safety.
- Local `__embedding__` and local-LLM slots also participate in gating — same code path, same semantics. AIMD just never grows them past `max_concurrent` for non-cloud slots.
- Preserve the existing stage-level `active_stages` tracking; don't try to unify it with per-request tracking in this plan (separate concerns, separate refactor).

---

## File Structure

| File | Responsibility | Change Type |
|------|----------------|-------------|
| `src/codrag/services/pipeline/scheduler.py` | `ComputeSlot` gets `in_flight_requests` + `_cond`. `PipelineScheduler` gets `acquire_request` / `release_request` / `acquire_request_ctx`. | Modify |
| `tests/test_scheduler_request_gate.py` | Unit tests for the new scheduler API. | Create |
| `src/codrag/core/llm_client.py` | `_generate_internal` wraps HTTP calls in `acquire_request_ctx`. Remove `min(8, ...)` clamp in `_get_llm_concurrency`. | Modify |
| `tests/test_llm_client_request_gate.py` | Integration-style tests that run `LLMClient._generate_internal` through a mocked HTTP session and verify concurrency is bounded by the scheduler's `current_limit`. | Create |
| `src/codrag/core/deepening.py` | Remove the static ThreadPool cap — use shared `llm_pool` or bump to scheduler-visible size. | Modify |
| `src/codrag/api/routers/pipeline.py` (or wherever scheduler status is exposed) | Surface `in_flight_requests` per slot. | Modify |
| `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` | Display `in_flight / current_limit` per slot. | Modify |

---

## Task 1: Scheduler per-request gate (new API, no callers)

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py`
- Create: `tests/test_scheduler_request_gate.py`

**What this task accomplishes:** Adds `acquire_request` / `release_request` / `acquire_request_ctx` to `PipelineScheduler` without wiring any callers. Ships safely because it's unused.

- [ ] **Step 1.1: Write failing tests**

Create `tests/test_scheduler_request_gate.py`:

```python
"""Phase 82 follow-up: per-request AIMD gate.

Tests the new acquire_request/release_request API on PipelineScheduler.
The existing ``acquire`` method is stage-level (one entry per project-stage);
these tests exercise per-REQUEST gating backed by Condition/counter.
"""
from __future__ import annotations

import threading
import time

import pytest

from codrag.services.pipeline.scheduler import (
    ComputeSlot,
    PipelineScheduler,
)


def _seeded_cloud_scheduler(limit: int = 3) -> tuple[PipelineScheduler, str]:
    sched = PipelineScheduler()
    node_id = "cloud:ep-test"
    sched.configure_node(node_id, max_concurrent=limit)
    slot = sched._slots[node_id]
    slot.current_limit = limit
    slot.mode = "congestion_avoidance"
    return sched, node_id


def test_acquire_release_cycle_tracks_in_flight() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=3)
    slot = sched._slots[node_id]

    token = sched.acquire_request(node_id, timeout=1.0)
    assert token is not None
    assert slot.in_flight_requests == 1

    sched.release_request(token)
    assert slot.in_flight_requests == 0


def test_acquire_blocks_when_at_limit_then_wakes_on_release() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=2)
    slot = sched._slots[node_id]

    t1 = sched.acquire_request(node_id, timeout=1.0)
    t2 = sched.acquire_request(node_id, timeout=1.0)
    assert t1 is not None and t2 is not None
    assert slot.in_flight_requests == 2

    # Third acquire must block.  Release t1 from another thread after
    # a short delay and verify the waiter wakes up.
    waiter_token = {"value": "unset"}

    def _waiter() -> None:
        waiter_token["value"] = sched.acquire_request(node_id, timeout=2.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)  # ensure _waiter is blocked on the condition
    assert slot.in_flight_requests == 2
    sched.release_request(t1)
    th.join(timeout=2.0)

    assert waiter_token["value"] is not None, "waiter never woke"
    assert slot.in_flight_requests == 2  # t2 + waiter

    sched.release_request(t2)
    sched.release_request(waiter_token["value"])
    assert slot.in_flight_requests == 0


def test_acquire_times_out_returns_none() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=1)
    held = sched.acquire_request(node_id, timeout=1.0)
    assert held is not None

    # Second acquire with a short timeout must return None without waking.
    t_start = time.monotonic()
    result = sched.acquire_request(node_id, timeout=0.2)
    elapsed = time.monotonic() - t_start

    assert result is None
    assert 0.15 <= elapsed <= 0.5, f"timeout elapsed={elapsed}"

    sched.release_request(held)


def test_limit_decrease_via_aimd_does_not_evict_in_flight() -> None:
    """AIMD backoff reduces current_limit — existing in-flight requests must
    NOT be forcibly released. They finish naturally; new acquires block until
    in_flight drops below the new limit."""
    sched, node_id = _seeded_cloud_scheduler(limit=4)
    slot = sched._slots[node_id]

    tokens = [sched.acquire_request(node_id, timeout=1.0) for _ in range(4)]
    assert all(t is not None for t in tokens)
    assert slot.in_flight_requests == 4

    # Simulate AIMD backoff: limit drops 4 -> 2.
    sched._record_throughput_for_slot(slot, is_429_or_timeout=True)
    assert slot.current_limit < 4
    assert slot.in_flight_requests == 4  # still holding all 4

    # A new acquire must block until 2 of the 4 finish.
    new_token = {"value": "unset"}

    def _waiter() -> None:
        new_token["value"] = sched.acquire_request(node_id, timeout=2.0)

    th = threading.Thread(target=_waiter)
    th.start()
    time.sleep(0.1)
    assert new_token["value"] == "unset"  # still blocked

    # Releasing the in-flight ones should eventually let the waiter through
    # once in_flight < current_limit.
    for t in tokens:
        sched.release_request(t)
    th.join(timeout=2.0)
    assert new_token["value"] is not None

    sched.release_request(new_token["value"])


def test_unknown_node_id_returns_none() -> None:
    sched = PipelineScheduler()
    assert sched.acquire_request("cloud:does-not-exist", timeout=0.1) is None


def test_release_idempotent_on_stale_token() -> None:
    """Releasing the same token twice must not drive in_flight negative."""
    sched, node_id = _seeded_cloud_scheduler(limit=2)
    slot = sched._slots[node_id]

    t = sched.acquire_request(node_id, timeout=1.0)
    sched.release_request(t)
    assert slot.in_flight_requests == 0

    # Second release of the same token should be a no-op.
    sched.release_request(t)
    assert slot.in_flight_requests == 0


def test_context_manager_releases_on_exception() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=1)
    slot = sched._slots[node_id]

    with pytest.raises(RuntimeError):
        with sched.acquire_request_ctx(node_id, timeout=1.0):
            assert slot.in_flight_requests == 1
            raise RuntimeError("boom")

    assert slot.in_flight_requests == 0


def test_context_manager_yields_none_on_timeout() -> None:
    sched, node_id = _seeded_cloud_scheduler(limit=1)
    held = sched.acquire_request(node_id, timeout=1.0)
    assert held is not None

    entered = {"value": False}
    with sched.acquire_request_ctx(node_id, timeout=0.1) as token:
        entered["value"] = True
        assert token is None  # signals caller "no slot available"

    assert entered["value"] is True
    sched.release_request(held)
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scheduler_request_gate.py -v`
Expected: Collection errors or all FAIL — `PipelineScheduler` has no `acquire_request`, `release_request`, or `acquire_request_ctx` methods; `ComputeSlot` has no `in_flight_requests` or `_cond`.

- [ ] **Step 1.3: Add `in_flight_requests` and `_cond` to `ComputeSlot`**

In `src/codrag/services/pipeline/scheduler.py`, modify the `ComputeSlot` dataclass (around lines 90-133). Add two fields:

```python
@dataclass
class ComputeSlot:
    """Tracks current load on a compute node."""
    node_id: str
    max_concurrent: int
    active_stages: Dict[str, str] = field(default_factory=dict)  # project_id -> stage_id

    # ... existing AIMD fields (current_limit, min_limit, mode, success_streak,
    # _last_backoff_time, _last_recovery_time) ...
    current_limit: int = 0
    min_limit: int = 1
    mode: Literal["jumpstart", "congestion_avoidance"] = "congestion_avoidance"
    success_streak: int = 0
    _last_backoff_time: float = 0.0
    _last_recovery_time: float = 0.0

    # Phase 82 follow-up: per-request gate. `in_flight_requests` counts
    # LLM calls currently in flight against this slot. `_cond` is the
    # Condition new requests wait on when in_flight_requests >= current_limit.
    # Both are seeded lazily by PipelineScheduler.acquire_request — doing
    # it in __post_init__ creates a Condition per slot even when the gate
    # is never used (cheap but surprises tests that snapshot the slot).
    in_flight_requests: int = 0
    _cond: Any = None  # threading.Condition, lazy-initialized
    # Per-acquire monotonic counter for token stamping; stale tokens get
    # rejected by release_request via the _live_tokens set.
    _request_stamp_seq: int = 0
    _live_tokens: Set[int] = field(default_factory=set)

    def __post_init__(self):
        # ... existing body unchanged ...
```

The `_cond` field is typed as `Any` because `threading.Condition` isn't a real type in typing stubs and we want to avoid a forward-reference import. Don't add a `repr` customization — the default still works.

- [ ] **Step 1.4: Verify `ComputeSlot` still initializes correctly**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py -v`
Expected: PASS — the dataclass field addition must not regress any existing behavior.

- [ ] **Step 1.5: Add `acquire_request`, `release_request`, `acquire_request_ctx` to `PipelineScheduler`**

In `src/codrag/services/pipeline/scheduler.py`, add three methods to the `PipelineScheduler` class. Insert them in the "Slot management" section, after `_maybe_idle_recover` (around line 695).

```python
    # ── Per-request gate (Phase 82 follow-up) ─────────────────────

    def _slot_condition(self, slot: ComputeSlot) -> threading.Condition:
        """Lazily attach a Condition to the slot, reusing the scheduler's lock.

        Caller MUST hold ``self._lock``. The Condition wraps ``self._lock``
        (which is an RLock) so ``wait()`` releases the scheduler lock while
        suspended, and reacquires it on wake. Reusing the scheduler lock
        keeps ``current_limit`` reads consistent across waiters.
        """
        if slot._cond is None:
            slot._cond = threading.Condition(self._lock)
        return slot._cond

    def acquire_request(
        self, node_id: str, timeout: float = 120.0,
    ) -> Optional[Tuple[str, int]]:
        """Acquire one in-flight request slot on ``node_id``.

        Blocks up to ``timeout`` seconds waiting for
        ``in_flight_requests < current_limit``. Returns an opaque token
        (node_id, stamp) that must be passed to ``release_request``.
        Returns ``None`` on timeout or if the node doesn't exist.

        The token stamp is monotonic per slot; ``release_request`` uses
        it to reject stale or double-release attempts.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lock:
            slot = self._slots.get(node_id)
            if slot is None:
                return None
            cond = self._slot_condition(slot)

            while slot.in_flight_requests >= slot.dynamic_capacity:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                # wait_for releases the lock during wait; returns True if
                # predicate became true, False on timeout.
                woke = cond.wait(timeout=remaining)
                if not woke:
                    # Spurious return from wait — loop and re-check.
                    continue

            slot.in_flight_requests += 1
            slot._request_stamp_seq += 1
            stamp = slot._request_stamp_seq
            slot._live_tokens.add(stamp)
            return (node_id, stamp)

    def release_request(self, token: Optional[Tuple[str, int]]) -> None:
        """Release a previously-acquired request slot.

        Safe to call with ``None`` (no-op) or a stale token (no-op — won't
        drive ``in_flight_requests`` negative or wake extra waiters).
        """
        if token is None:
            return
        node_id, stamp = token
        with self._lock:
            slot = self._slots.get(node_id)
            if slot is None:
                return
            if stamp not in slot._live_tokens:
                return  # stale / double-release
            slot._live_tokens.discard(stamp)
            if slot.in_flight_requests > 0:
                slot.in_flight_requests -= 1
            cond = self._slot_condition(slot)
            cond.notify()  # wake one waiter

    from contextlib import contextmanager

    @contextmanager
    def acquire_request_ctx(
        self, node_id: str, timeout: float = 120.0,
    ):
        """Context-manager wrapper around acquire_request / release_request.

        Yields the token (or ``None`` on timeout). Always releases, even
        on exception. Callers typically check ``if token is None`` inside
        the ``with`` block to decide whether to proceed.
        """
        token = self.acquire_request(node_id, timeout=timeout)
        try:
            yield token
        finally:
            self.release_request(token)
```

Move the `from contextlib import contextmanager` to the top of the file (with the other imports) rather than inline inside the class. That's cleaner and matches the file's style.

- [ ] **Step 1.6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scheduler_request_gate.py -v`
Expected: PASS on all 7 test functions.

- [ ] **Step 1.7: Run the broader scheduler suite to confirm no regressions**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py tests/test_scheduler_unbounded_discovery.py -v`
Expected: PASS (same result as before this task).

- [ ] **Step 1.8: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_scheduler_request_gate.py
git commit -m "feat(scheduler): add per-request AIMD gate (acquire_request/release_request)"
```

---

## Task 2: Wire the gate into `LLMClient._generate_internal`

**Files:**
- Modify: `src/codrag/core/llm_client.py`
- Create: `tests/test_llm_client_request_gate.py`

**What this task accomplishes:** Every LLM call now goes through `acquire_request_ctx` before `session.post(...)`. If the scheduler says "full", the caller blocks until a slot frees up. Stages still have their old low concurrency caps, so user-visible throughput doesn't change — but the gate is installed and exercised.

- [ ] **Step 2.1: Write failing test — Ollama path uses the gate**

Create `tests/test_llm_client_request_gate.py`:

```python
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
    """Seed a shared scheduler with a cloud slot at the given limit."""
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

    client = LLMClient(provider="ollama", model="qwen3:4b-cloud")
    with patch.object(client._session, "post", side_effect=_fake_post):
        client.generate(prompt="hi", json_mode=False, num_predict=8)

    assert observed["in_flight_during_http"] == 1
    # And after completion, the counter is back to 0.
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

    client = LLMClient(provider="ollama", model="qwen3:4b-cloud")

    def _call() -> None:
        with patch.object(client._session, "post", side_effect=_slow_post):
            client.generate(prompt="hi", json_mode=False, num_predict=8)

    t1 = threading.Thread(target=_call)
    t2 = threading.Thread(target=_call)
    t1.start()
    t2.start()

    time.sleep(0.3)
    # Only one HTTP call has started — the other is blocked at the gate.
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

    client = LLMClient(provider="ollama", model="qwen3:4b-cloud")
    with patch.object(client._session, "post", side_effect=_failing_post):
        with pytest.raises(requests.exceptions.ConnectionError):
            client.generate(prompt="hi", json_mode=False, num_predict=8)

    assert slot.in_flight_requests == 0


def test_gate_timeout_falls_back_to_raw_call() -> None:
    """If the gate times out (120s wait exhausted), we don't want to hang
    forever — LLMClient should log and proceed with the HTTP call uncapped.

    This is a policy choice: blocking pipelines is worse than occasionally
    exceeding current_limit. We'd rather issue the call and let the AIMD
    backoff path catch overload via 429/5xx."""
    sched, node_id = _seed_scheduler(limit=1)
    slot = sched._slots[node_id]
    # Pre-fill the gate so any acquire_request times out.
    pre_token = sched.acquire_request(node_id, timeout=0.5)
    assert pre_token is not None

    client = LLMClient(provider="ollama", model="qwen3:4b-cloud")
    # Patch the scheduler's timeout to something short for the test.
    with patch.object(client._session, "post", return_value=_mock_ollama_response()):
        with patch(
            "codrag.core.llm_client._REQUEST_GATE_TIMEOUT_S", 0.3
        ):
            t_start = time.monotonic()
            text, tokens = client.generate(
                prompt="hi", json_mode=False, num_predict=8,
            )
            elapsed = time.monotonic() - t_start

    # The call should have proceeded (not raised), taking ~0.3s for the
    # gate timeout plus tiny overhead for the mocked HTTP.
    assert text == "ok" or text == ""  # response body is "ok"
    assert 0.25 <= elapsed <= 1.5, f"elapsed={elapsed}"

    sched.release_request(pre_token)
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_client_request_gate.py -v`
Expected: All 4 tests FAIL — `LLMClient._generate_internal` doesn't call the gate yet; `_REQUEST_GATE_TIMEOUT_S` doesn't exist.

- [ ] **Step 2.3: Add the gate wiring to `LLMClient`**

In `src/codrag/core/llm_client.py`:

1. Add a module-level constant near the top of the file (after the existing constants):

```python
# Phase 82 follow-up: per-request AIMD gate timeout.  If the scheduler
# can't issue us a slot within this window, we proceed uncapped — a
# blocked pipeline is worse than briefly exceeding current_limit.  AIMD
# will catch real overload via 429/5xx signals.
_REQUEST_GATE_TIMEOUT_S = 120.0
```

2. Add a helper method on `LLMClient`, right next to `_record_throughput` (around line 461):

```python
    def _resolve_scheduler_node_id(self) -> Optional[str]:
        """Resolve the PipelineScheduler node_id this client should gate on.

        Mirrors PipelineScheduler.record_throughput_for_provider's prefix
        logic so gate + AIMD agree on which slot a given LLM call belongs to.
        Returns None if no matching slot exists (gate is skipped).
        """
        try:
            from codrag.services.pipeline.scheduler import (
                CLOUD_PROVIDERS,
                pipeline_scheduler,
            )
        except Exception:  # pragma: no cover — import guard
            return None

        is_cloud = self.provider in CLOUD_PROVIDERS
        if not is_cloud and self.model:
            try:
                from codrag.core.batch_profiles import is_cloud_model_via_ollama
                if is_cloud_model_via_ollama(self.provider, self.model):
                    is_cloud = True
            except ImportError:
                pass

        prefix = "cloud:" if is_cloud else "local:"
        # Return the first matching slot — in the common single-endpoint
        # setup there's one slot per prefix. Multi-endpoint scheduling is
        # a separate concern.
        try:
            for nid in pipeline_scheduler._slots.keys():
                if nid.startswith(prefix):
                    return nid
        except Exception:  # pragma: no cover — defensive
            return None
        return None
```

3. Wrap `_generate_internal` so it gates around the HTTP call. The simplest pattern: extract the existing body into `_generate_internal_unchecked` (or keep it and pass the token down), and have `generate` acquire / release via the ctx manager.

   Since `_generate_internal` is ~400+ lines and contains three provider branches (Ollama, OpenAI, Google), wrap at the `generate()` caller level — that way we only wrap once:

   Modify `generate()` at `llm_client.py:475` to:

```python
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        num_predict: int = 2048,
        json_mode: bool = True,
        temperature: float = 0.1,
        response_schema: Optional[Dict[str, Any]] = None,
        think: Optional[bool] = None,
        max_chars: int = 0,
        num_ctx: Optional[int] = None,
    ) -> Tuple[str, int]:
        self._track_active("start")
        node_id = self._resolve_scheduler_node_id()
        try:
            if node_id is None:
                # No scheduler slot matches — skip the gate entirely.
                return self._generate_internal(
                    prompt=prompt, system=system, num_predict=num_predict,
                    json_mode=json_mode, temperature=temperature,
                    response_schema=response_schema, think=think,
                    max_chars=max_chars, num_ctx=num_ctx,
                )

            from codrag.services.pipeline.scheduler import pipeline_scheduler
            with pipeline_scheduler.acquire_request_ctx(
                node_id, timeout=_REQUEST_GATE_TIMEOUT_S,
            ) as token:
                if token is None:
                    logger.warning(
                        "LLM request gate: timed out waiting on %s "
                        "(current_limit=%d, in_flight=%d). Proceeding uncapped.",
                        node_id,
                        pipeline_scheduler._slots[node_id].current_limit,
                        pipeline_scheduler._slots[node_id].in_flight_requests,
                    )
                return self._generate_internal(
                    prompt=prompt, system=system, num_predict=num_predict,
                    json_mode=json_mode, temperature=temperature,
                    response_schema=response_schema, think=think,
                    max_chars=max_chars, num_ctx=num_ctx,
                )
        finally:
            self._track_active("stop")
```

Note: when `token is None` (timeout), we still proceed — the context manager's `__exit__` will `release_request(None)` which is a no-op. That's the explicit fallback behavior the tests specify.

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_llm_client_request_gate.py -v`
Expected: PASS on all 4 tests.

- [ ] **Step 2.5: Run the full LLMClient test suite to catch regressions**

Run: `.venv/bin/pytest tests/test_llm_client_queue_time.py tests/test_llm_client.py -v`
Expected: PASS. Known pre-existing failures in `test_llm_task_resolver.py` are unrelated — ignore.

- [ ] **Step 2.6: Commit**

```bash
git add src/codrag/core/llm_client.py tests/test_llm_client_request_gate.py
git commit -m "feat(llm_client): gate every LLM call via PipelineScheduler per-request API"
```

---

## Task 3: Remove static concurrency caps — let AIMD be the only gate

**Files:**
- Modify: `src/codrag/core/llm_client.py` (`_get_llm_concurrency`)
- Modify: `src/codrag/core/deepening.py` (remove per-stage ThreadPool sizing)
- Modify: `tests/test_llm_client.py` or wherever `_get_llm_concurrency` is tested

**What this task accomplishes:** Stages submit as many concurrent calls as their pool can run. AIMD's `current_limit` becomes the only effective throttle. This is the step that delivers the user-visible throughput improvement.

- [ ] **Step 3.1: Find existing tests for `_get_llm_concurrency`**

Run: `grep -rn "_get_llm_concurrency\b" tests/ src/`
Expected output will list call sites and any existing tests. Note any test that asserts the cap is `8` — those need updating.

- [ ] **Step 3.2: Update or write failing test asserting no hard cap at 8**

If a test exists, modify it. Otherwise add to `tests/test_llm_client.py` (create a section if needed):

```python
def test_get_llm_concurrency_no_hard_cap_at_8(monkeypatch) -> None:
    """Phase 82 follow-up: concurrency is gated by AIMD current_limit at
    request time, not by a static per-stage cap. _get_llm_concurrency now
    returns the raw configured value (clamped only to [1, 32]) and relies
    on the request gate to enforce the dynamic ceiling.
    """
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings

    original = settings.get("pipeline_config") or {}
    monkeypatch.setattr(
        settings, "get",
        lambda k, default=None: (
            {"llm_concurrency_deep": 24} if k == "pipeline_config" else original.get(k, default)
        ),
    )
    assert _get_llm_concurrency("deep") == 24


def test_get_llm_concurrency_clamps_to_pool_max(monkeypatch) -> None:
    """A value > 32 (the shared pool's max_workers) is still clamped,
    because nothing downstream can run more than that many concurrent
    HTTP calls regardless of AIMD."""
    from codrag.core.llm_client import _get_llm_concurrency
    from codrag.services.settings_store import settings

    monkeypatch.setattr(
        settings, "get",
        lambda k, default=None: (
            {"llm_concurrency_deep": 100} if k == "pipeline_config" else default
        ),
    )
    assert _get_llm_concurrency("deep") == 32
```

- [ ] **Step 3.3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_llm_client.py -v -k "get_llm_concurrency"`
Expected: FAIL — current implementation caps at 8.

- [ ] **Step 3.4: Update `_get_llm_concurrency` at `llm_client.py:225`**

Replace:
```python
        return max(1, min(8, int(value)))
```

With:
```python
        # Phase 82 follow-up: AIMD current_limit is the runtime cap.
        # This function only clamps to [1, 32] — 32 matches the shared
        # LLM pool's max_workers, above which nothing can run in
        # parallel anyway.
        return max(1, min(32, int(value)))
```

- [ ] **Step 3.5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_llm_client.py -v -k "get_llm_concurrency"`
Expected: PASS.

- [ ] **Step 3.6: Update `deepening.py` to use the shared pool**

In `src/codrag/core/deepening.py`, replace the per-stage pool creation at line 456:

```python
                pool = ThreadPoolExecutor(max_workers=concurrency)
```

With:
```python
                from codrag.services.pipeline.thread_pool import llm_pool
                # Phase 82 follow-up: use the shared bounded pool. AIMD's
                # request gate enforces the dynamic ceiling at submit-time.
                # The per-stage ``concurrency`` value is no longer a hard
                # cap — it's the MAX we'd ever submit in parallel; the
                # gate may block many of those until current_limit allows.
                pool = llm_pool
```

And remove the `try:` / `finally: pool.shutdown(...)` block around it — the shared pool is never shut down. Read the surrounding code first (`deepening.py:420-510`) to understand the exact cleanup path and preserve timeout behavior. Adapt the code to use `llm_pool.submit` directly without the TPE context-manager semantics.

Concretely:
- `pool = ThreadPoolExecutor(max_workers=concurrency)` → `pool = llm_pool`
- Remove `pool.shutdown(wait=False, cancel_futures=True)` calls (they'd shut down the shared pool for the whole daemon).
- Keep `as_completed(futures, timeout=batch_timeout_sec)` and `future.cancel()` — those are per-future, not per-pool.

- [ ] **Step 3.7: Run the deepening and pipeline test suites**

Run: `.venv/bin/pytest tests/test_deepening*.py tests/test_pipeline_orchestrator.py -v`
Expected: PASS.

- [ ] **Step 3.8: Commit**

```bash
git add src/codrag/core/llm_client.py src/codrag/core/deepening.py tests/test_llm_client.py
git commit -m "feat(pipeline): remove static concurrency caps; AIMD gate is the only throttle"
```

---

## Task 4: Observability — expose in-flight and current_limit to the dashboard

**Files:**
- Modify: `src/codrag/api/routers/pipeline.py` (or `scheduler` — find whichever router exposes slot status)
- Modify: `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`
- Create/modify: tests for the API endpoint

**What this task accomplishes:** The user can see `in_flight / current_limit` per slot in the dashboard sidebar, so the gate's effect is visible while they're watching a long build.

- [ ] **Step 4.1: Find where slot status is currently exposed to the UI**

Run: `grep -rn "current_limit\|dynamic_capacity\|active_stages" src/codrag/api/routers/ | head -20`

Expected: at least one router (likely `pipeline.py` or `queue.py`) serializes slot state. Read that file end-to-end before modifying.

- [ ] **Step 4.2: Write failing test for the serialized `in_flight_requests` field**

Add to the appropriate router test file (e.g. `tests/test_api_pipeline.py` or similar):

```python
def test_scheduler_status_exposes_in_flight_requests(client) -> None:
    """Phase 82 follow-up: per-slot in_flight_requests must be visible
    to the dashboard so the request gate's effect is observable."""
    from codrag.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.configure_node("cloud:obs-test", max_concurrent=4)
    slot = pipeline_scheduler._slots["cloud:obs-test"]
    slot.current_limit = 8
    slot.in_flight_requests = 3

    resp = client.get("/scheduler/status")  # adjust URL to actual endpoint
    assert resp.status_code == 200
    body = resp.json()
    slots = {s["node_id"]: s for s in body["slots"]}
    assert slots["cloud:obs-test"]["in_flight_requests"] == 3
    assert slots["cloud:obs-test"]["current_limit"] == 8
```

Adjust the endpoint path and response shape to match the actual router. Read the existing tests for that router first.

- [ ] **Step 4.3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_api_pipeline.py -v -k "in_flight"`
Expected: FAIL — field not serialized.

- [ ] **Step 4.4: Add `in_flight_requests` to the serializer**

Find the function that builds the slot dict for the API response (look for `current_limit`, `max_concurrent` being serialized together). Add:

```python
            "in_flight_requests": slot.in_flight_requests,
```

right next to `"current_limit": slot.current_limit`.

- [ ] **Step 4.5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_api_pipeline.py -v -k "in_flight"`
Expected: PASS.

- [ ] **Step 4.6: Surface `in_flight_requests` in the sidebar UI**

Read `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` to understand how slot data is currently rendered. Look for the existing `current_limit` / `max_concurrent` display — add `in_flight_requests` beside it.

Typical pattern (adjust to the existing JSX):

```tsx
<div className="text-xs text-muted-foreground">
  {slot.in_flight_requests} / {slot.current_limit} in flight
  {slot.current_limit !== slot.max_concurrent && (
    <span className="text-[10px] ml-1">(max {slot.max_concurrent})</span>
  )}
</div>
```

Also update the TypeScript type that describes slots — look for the type definition matching the server response (likely in `packages/ui/src/types/` or imported from a generated types file) and add `in_flight_requests: number`.

- [ ] **Step 4.7: Verify the UI renders without TypeScript errors**

Run: `npm run typecheck --workspace=@codrag/ui`
Expected: no errors.

- [ ] **Step 4.8: Manual smoke test**

Start the dev environment:
```bash
scripts/dev.sh --kill && scripts/dev.sh
```

Open the dashboard at http://localhost:5174, trigger a pipeline rebuild, and watch the sidebar slot panel. Expected: `in_flight / current_limit` updates every ~1s during the LLM-heavy stages (deepening, concepts, audit). During congestion, `in_flight` should sit at `current_limit`. During slack, `in_flight` drops while `current_limit` grows.

- [ ] **Step 4.9: Commit**

```bash
git add src/codrag/api/routers/ packages/ui/src/ tests/
git commit -m "feat(dashboard): expose per-slot in_flight_requests to show AIMD gate state"
```

---

## After All Tasks

Run the full test suite one more time:

```bash
.venv/bin/pytest tests/ -v --ignore=tests/test_llm_task_resolver.py
```

Expected: PASS. (The 4 pre-existing `test_llm_task_resolver.py` failures are model-config drift unrelated to this work — verified via `git stash` on HEAD before starting.)

Then smoke-test with a real rebuild:

```bash
# Terminal 1 — daemon
scripts/dev.sh --kill && scripts/dev.sh

# Terminal 2 — watch concurrency events
python /tmp/watch_concurrency.py

# Terminal 3 — trigger rebuild on a small test repo
# (use the dashboard or API)
```

Expected output in the monitor:
- `PEAK` lines climbing well past 8 (the old cap) — e.g. 10, 12, 15, 20 — as AIMD discovers ceiling.
- `AI` (additive increase) lines growing the ceiling as calls succeed.
- `MD` (multiplicative decrease) only on real rejections, not random latency.
- `STAGE` boundaries showing deepening, concepts, audit all using >8 concurrent calls.

If peak still pins at 8, the static cap isn't fully removed. Grep for `min(8` and `max_workers=8` in the codebase — there may be another site.

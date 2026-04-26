# Phase 119 Concurrency Stability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the "67 → 3 → 60" AIMD whiplash on cloud concurrency by gating growth on real demand, locking discovered ceilings with a 24 h TTL, fixing the misleading `(max 1)` UI annotation, and probing Ollama for a sensible seed instead of falling through to `1`.

**Architecture:** Phase 82 latency-aware AIMD stays as the discovery primitive; Phase 119 stabilizes it with three changes — demand-gated recovery, persisted ceiling-with-TTL, honest UI state. F-28's `_maybe_idle_recover` becomes `_maybe_demand_recover` (only grows when the gate has been binding). `ConcurrencyStore` schema gains `locked_until` and `edge_observed_at` so a backoff edge persists as a discovered ceiling. `node_summary` API gains a `state` field so the frontend can drop the misleading `(max N)` annotation. A new `ollama_probe.py` reads `OLLAMA_NUM_PARALLEL` / `/api/ps` to seed new slots intelligently.

**Tech Stack:** Python 3.11 (stdlib sqlite3, threading), pytest with monkeypatch + `time.time` mocking, FastAPI, React + TypeScript.

---

## File Structure

**Create:**
- `src/prep/services/pipeline/ollama_probe.py` — Best-effort Ollama capacity probe. One responsibility: return an integer seed.
- `tests/test_concurrency_store_lock.py` — Lock TTL + migration tests for `ConcurrencyStore`.
- `tests/test_scheduler_demand_recovery.py` — Demand-gated recovery + ceiling lock-in behavioral tests.
- `tests/test_ollama_probe.py` — Env → `/api/ps` → default fallback ordering.
- `tests/test_queue_status_state.py` — API surface for the new `state` / `discovered_ceiling` / `locked_until` fields.

**Modify:**
- `src/prep/services/pipeline/concurrency_store.py` — Schema migration; new `load_full()` and `save_edge()` methods; preserve existing `load()`/`save()`/`clear()` for callers.
- `src/prep/services/pipeline/scheduler.py` — Replace `_maybe_idle_recover` with `_maybe_demand_recover`; add ceiling-aware clamp; record edge on MD; expose `state` in `status()`.
- `src/prep/api/routers/queue.py` — Pass new fields into `node_summary`.
- `src/prep/api/routers/compute.py` — Add `POST /compute/concurrency/clear` to invalidate a lock.
- `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` — State pill replaces `(max N)`.
- `docs/Phase96-fix-pipeline/05_FINDINGS_AND_BUGS_REGISTRY.md` — Add a follow-up note under F-28 pointing at Phase 119.

---

## Task 0: Baseline — capture current state before changes

**Files:** (read-only)

- [ ] **Step 1: Run the full pytest suite, record pass/fail count.**

Run: `.venv/bin/pytest tests/ -x --tb=short -q 2>&1 | tail -20`
Expected: capture baseline. Record pre-existing failures so we don't misattribute later.

- [ ] **Step 2: Confirm the bug reproduces on a small repo.**

Start the daemon, then:

```bash
sqlite3 ~/.local/share/sourceprep/concurrency_store.db \
  "SELECT node_id, ceiling FROM discovered_ceilings;"
```

Record the current persisted ceiling for `cloud:default_ollama`. After implementation it should not grow without backoff edges.

- [ ] **Step 3: Tail the live log to confirm idle-recovery noise.**

Run: `tail -f /Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/sample_repos/generated/rust_repo/.sourceprep/logs/pipeline_*.log | grep -E "(idle recovery|jumpstart|Backing off)"`

Expected: lines like `idle recovery 56 -> 57 (max=1, floor=1)` with no preceding evidence the gate was binding. This is the bug.

- [ ] **Step 4: No commit — observational task.**

---

## Task 1: ConcurrencyStore schema migration — add `locked_until`, `edge_observed_at`

**Files:**
- Modify: `src/prep/services/pipeline/concurrency_store.py`
- Create: `tests/test_concurrency_store_lock.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/test_concurrency_store_lock.py`:

```python
"""Tests for Phase 119 lock-with-TTL extension to ConcurrencyStore.

Schema migration adds two columns:
  - locked_until: float — unix seconds; ceiling is locked until this time.
  - edge_observed_at: float — when the backoff edge that established
    the ceiling was observed.

Both default to 0 for legacy rows so a fresh-install boot sees them
as "unlocked" (i.e. probing) until a real edge fires.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from prep.services.pipeline.concurrency_store import ConcurrencyStore


@pytest.fixture
def store(tmp_path: Path) -> ConcurrencyStore:
    return ConcurrencyStore(tmp_path / "concurrency.db")


def test_load_full_returns_ceiling_lock_edge(store: ConcurrencyStore) -> None:
    now = time.time()
    store.save_edge("cloud:ep-1", "__default__", ceiling=12, locked_until=now + 3600, edge_observed_at=now)
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["ceiling"] == 12
    assert abs(record["locked_until"] - (now + 3600)) < 1.0
    assert abs(record["edge_observed_at"] - now) < 1.0


def test_load_full_missing_returns_none(store: ConcurrencyStore) -> None:
    assert store.load_full("cloud:none", "__default__") is None


def test_save_edge_overwrites_in_place(store: ConcurrencyStore) -> None:
    now = time.time()
    store.save_edge("cloud:ep-1", "__default__", ceiling=12, locked_until=now + 3600, edge_observed_at=now)
    store.save_edge("cloud:ep-1", "__default__", ceiling=14, locked_until=now + 7200, edge_observed_at=now + 10)
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["ceiling"] == 14
    assert abs(record["locked_until"] - (now + 7200)) < 1.0


def test_legacy_save_still_works_and_reads_back_with_zero_lock(store: ConcurrencyStore) -> None:
    """Pre-Phase-119 callers using the original save() must keep working."""
    store.save("cloud:ep-1", "__default__", ceiling=20)
    assert store.load("cloud:ep-1", "__default__") == 20
    record = store.load_full("cloud:ep-1", "__default__")
    assert record is not None
    assert record["ceiling"] == 20
    assert record["locked_until"] == 0.0
    assert record["edge_observed_at"] == 0.0


def test_migration_from_legacy_schema(tmp_path: Path) -> None:
    """A pre-Phase-119 DB with only (node_id, model_family, ceiling, updated_at)
    must migrate to the new schema on first connect, preserving existing rows.
    """
    db_path = tmp_path / "concurrency.db"
    legacy_schema = """
        CREATE TABLE discovered_ceilings (
            node_id TEXT NOT NULL,
            model_family TEXT NOT NULL,
            ceiling INTEGER NOT NULL,
            updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (node_id, model_family)
        )
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(legacy_schema)
        conn.execute(
            "INSERT INTO discovered_ceilings (node_id, model_family, ceiling) VALUES (?, ?, ?)",
            ("cloud:legacy", "__default__", 30),
        )
        conn.commit()
    finally:
        conn.close()

    # Opening the store triggers migration.
    store = ConcurrencyStore(db_path)
    record = store.load_full("cloud:legacy", "__default__")
    assert record is not None
    assert record["ceiling"] == 30
    assert record["locked_until"] == 0.0
    assert record["edge_observed_at"] == 0.0


def test_clear_removes_lock_too(store: ConcurrencyStore) -> None:
    now = time.time()
    store.save_edge("cloud:ep-1", "__default__", ceiling=12, locked_until=now + 3600, edge_observed_at=now)
    store.clear("cloud:ep-1", "__default__")
    assert store.load_full("cloud:ep-1", "__default__") is None


def test_save_edge_rejects_bad_ceiling(store: ConcurrencyStore) -> None:
    with pytest.raises(ValueError):
        store.save_edge("cloud:ep-1", "__default__", ceiling=0, locked_until=0, edge_observed_at=0)
```

- [ ] **Step 2: Run tests to verify they fail.**

Run: `.venv/bin/pytest tests/test_concurrency_store_lock.py -v`
Expected: ALL fail with `AttributeError: 'ConcurrencyStore' object has no attribute 'save_edge'` or `load_full`.

- [ ] **Step 3: Add the migration + new methods to `concurrency_store.py`.**

Open `src/prep/services/pipeline/concurrency_store.py`. Replace the `_SCHEMA` constant and `_init_schema` method as follows; keep the existing `load`/`save`/`clear` methods intact (they continue to work — `save()` writes a row with `locked_until=0` and `edge_observed_at=0`).

Replace this block (currently around lines 24-32):

```python
_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovered_ceilings (
    node_id TEXT NOT NULL,
    model_family TEXT NOT NULL,
    ceiling INTEGER NOT NULL,
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (node_id, model_family)
)
"""
```

with:

```python
_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovered_ceilings (
    node_id TEXT NOT NULL,
    model_family TEXT NOT NULL,
    ceiling INTEGER NOT NULL,
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    locked_until REAL NOT NULL DEFAULT 0,
    edge_observed_at REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (node_id, model_family)
)
"""

_LEGACY_COLUMNS = {"locked_until", "edge_observed_at"}
```

Replace `_init_schema` (currently around lines 48-51):

```python
    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            conn.commit()
```

with:

```python
    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(discovered_ceilings)").fetchall()
            }
            for col in _LEGACY_COLUMNS - existing:
                conn.execute(
                    f"ALTER TABLE discovered_ceilings ADD COLUMN {col} REAL NOT NULL DEFAULT 0"
                )
            conn.commit()
```

Below the existing `clear()` method, add:

```python
    def load_full(self, node_id: str, model_family: str) -> dict | None:
        """Load the full ceiling record (ceiling, locked_until, edge_observed_at)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ceiling, locked_until, edge_observed_at "
                "FROM discovered_ceilings WHERE node_id = ? AND model_family = ?",
                (node_id, model_family),
            ).fetchone()
        if row is None:
            return None
        return {
            "ceiling": int(row[0]),
            "locked_until": float(row[1] or 0),
            "edge_observed_at": float(row[2] or 0),
        }

    def save_edge(
        self,
        node_id: str,
        model_family: str,
        *,
        ceiling: int,
        locked_until: float,
        edge_observed_at: float,
    ) -> None:
        """Persist a ceiling locked until ``locked_until`` based on the edge
        observed at ``edge_observed_at``. Distinct from ``save()`` which is
        used for jumpstart growth (no lock)."""
        if ceiling < 1:
            raise ValueError(f"ceiling must be >= 1, got {ceiling!r}")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO discovered_ceilings "
                "(node_id, model_family, ceiling, locked_until, edge_observed_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(node_id, model_family) DO UPDATE SET "
                "ceiling = excluded.ceiling, "
                "locked_until = excluded.locked_until, "
                "edge_observed_at = excluded.edge_observed_at, "
                "updated_at = strftime('%s', 'now')",
                (node_id, model_family, int(ceiling), float(locked_until), float(edge_observed_at)),
            )
            conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass.**

Run: `.venv/bin/pytest tests/test_concurrency_store_lock.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Run the existing concurrency_store tests for regressions.**

Run: `.venv/bin/pytest tests/test_concurrency_store.py -v`
Expected: PASS (no behavioral changes to existing API).

- [ ] **Step 6: Commit.**

```bash
git add src/prep/services/pipeline/concurrency_store.py tests/test_concurrency_store_lock.py
git commit -m "feat(phase119): add ceiling lock + edge-observed columns to ConcurrencyStore

Schema migration adds locked_until and edge_observed_at. New
save_edge() persists the (ceiling, locked_until, edge_observed_at)
tuple atomically. Legacy save()/load() unchanged — they keep working
with locked_until=0 (treated as 'not locked')."
```

---

## Task 2: Ollama probe — read OLLAMA_NUM_PARALLEL or /api/ps

**Files:**
- Create: `src/prep/services/pipeline/ollama_probe.py`
- Create: `tests/test_ollama_probe.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/test_ollama_probe.py`:

```python
"""Tests for the Ollama capacity probe used to seed new cloud slots."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prep.services.pipeline.ollama_probe import probe_ollama_concurrency


def test_env_var_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "12")
    # Even if the API would say something else, env wins.
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": [{}, {}, {}]}
        )
        assert probe_ollama_concurrency("http://localhost:11434") == 12


def test_env_var_invalid_falls_through_to_api(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "not-a-number")
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": [{}, {}, {}, {}, {}, {}, {}]}
        )
        assert probe_ollama_concurrency("http://localhost:11434") == 7


def test_env_unset_uses_ps_count(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": [{} for _ in range(10)]}
        )
        assert probe_ollama_concurrency("http://localhost:11434") == 10


def test_falls_back_to_default_on_error(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.side_effect = Exception("connection refused")
        assert probe_ollama_concurrency("http://localhost:11434") == 5


def test_ps_returns_zero_models_falls_to_default(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_NUM_PARALLEL", raising=False)
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(
            status_code=200, json=lambda: {"models": []}
        )
        # Zero loaded models means we have no capacity hint — use default.
        assert probe_ollama_concurrency("http://localhost:11434") == 5


def test_clamps_to_reasonable_range(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "9999")
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(status_code=200, json=lambda: {"models": []})
        # Wildly large values get clamped — 256 is more than any real provider.
        assert probe_ollama_concurrency("http://localhost:11434") == 256

    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "-3")
    with patch("prep.services.pipeline.ollama_probe.requests") as rq:
        rq.get.return_value = MagicMock(status_code=200, json=lambda: {"models": []})
        # Negative falls through to API → empty → default.
        assert probe_ollama_concurrency("http://localhost:11434") == 5
```

- [ ] **Step 2: Run tests to verify they fail.**

Run: `.venv/bin/pytest tests/test_ollama_probe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prep.services.pipeline.ollama_probe'`.

- [ ] **Step 3: Implement the probe.**

Create `src/prep/services/pipeline/ollama_probe.py`:

```python
"""Best-effort probe of an Ollama daemon's parallel-request capacity.

Phase 119: when configuring a new cloud:* slot for an Ollama-proxied
endpoint with no persisted ceiling, we'd like a smarter seed than the
Phase 82 default of 5. Read OLLAMA_NUM_PARALLEL from the environment
first; fall back to GET /api/ps and count loaded models; finally
default to 5.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_DEFAULT = 5
_HARD_CAP = 256


def probe_ollama_concurrency(host: str, timeout: float = 1.5) -> int:
    """Return a sensible seed for a new cloud-via-Ollama slot.

    Order of precedence:
      1. OLLAMA_NUM_PARALLEL env var (if a positive int).
      2. GET <host>/api/ps — count of currently-loaded models.
      3. Default seed (5).

    Result is clamped to [1, 256]. Network/parse errors fall through.
    """
    env = os.getenv("OLLAMA_NUM_PARALLEL")
    if env:
        try:
            n = int(env)
            if n > 0:
                return min(n, _HARD_CAP)
        except ValueError:
            logger.debug("OLLAMA_NUM_PARALLEL=%r is not an int; falling back", env)

    try:
        resp = requests.get(f"{host.rstrip('/')}/api/ps", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            count = len(data.get("models") or [])
            if count > 0:
                return min(count, _HARD_CAP)
    except Exception as exc:
        logger.debug("Ollama probe failed for %s: %s", host, exc)

    return _DEFAULT
```

- [ ] **Step 4: Run tests to verify they pass.**

Run: `.venv/bin/pytest tests/test_ollama_probe.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/services/pipeline/ollama_probe.py tests/test_ollama_probe.py
git commit -m "feat(phase119): probe Ollama for a sensible concurrency seed

probe_ollama_concurrency() reads OLLAMA_NUM_PARALLEL or /api/ps and
falls back to 5. Used by the scheduler when a new cloud slot has no
persisted ceiling — replaces the hard-coded 5-from-Phase-82 seed."
```

---

## Task 3: Scheduler — track gate-binding window for demand-gated recovery

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`
- Create: `tests/test_scheduler_demand_recovery.py`

- [ ] **Step 1: Write the failing test for demand-gating.**

Create `tests/test_scheduler_demand_recovery.py`:

```python
"""Phase 119: recovery only fires when the gate has recently been binding."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from prep.services.pipeline.scheduler import ComputeSlot, PipelineScheduler


def _cloud_slot(node_id: str = "cloud:ep-test", current_limit: int = 6) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=1,
        current_limit=current_limit,
        min_limit=3,
        mode="congestion_avoidance",
    )


def _set_slot(sched: PipelineScheduler, slot: ComputeSlot) -> ComputeSlot:
    sched._slots[slot.node_id] = slot
    return slot


def test_demand_recovery_skipped_when_idle() -> None:
    """If nothing was waiting on the gate, current_limit must NOT grow."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))

    fake_now = 10_000.0
    with patch("prep.services.pipeline.scheduler.time.time", return_value=fake_now):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 6


def test_demand_recovery_grows_when_gate_was_binding(monkeypatch) -> None:
    """When acquire_request observed the gate binding within the demand
    window, the next acquire after cooldown grows current_limit by 1."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))

    base = 10_000.0
    # Simulate gate having been binding 5 seconds ago.
    slot._gate_binding_until = base + 30   # within window from base
    slot._last_backoff_time = 0.0          # well past cooldown
    slot._last_recovery_time = 0.0         # well past recovery interval

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 7


def test_demand_recovery_skipped_during_backoff_cooldown() -> None:
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=6))
    base = 10_000.0
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = base - 5   # 5 s ago — still in 30 s cooldown
    slot._last_recovery_time = 0.0

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)

    assert slot.current_limit == 6


def test_demand_recovery_clamps_at_locked_ceiling() -> None:
    """When a discovered ceiling is locked, recovery cannot grow past it."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=11))
    slot.discovered_ceiling = 12
    slot.ceiling_locked_until = 99_999_999.0
    base = 10_000.0
    slot._gate_binding_until = base + 30
    slot._last_backoff_time = 0.0
    slot._last_recovery_time = 0.0

    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)
    assert slot.current_limit == 12

    # Second tick — already at ceiling, no further growth.
    slot._last_recovery_time = 0.0
    with patch("prep.services.pipeline.scheduler.time.time", return_value=base):
        sched._maybe_demand_recover(slot)
    assert slot.current_limit == 12


def test_acquire_request_marks_gate_binding(monkeypatch) -> None:
    """Phase 119: acquire_request stamps slot._gate_binding_until when the
    waiter actually had to wait. We test the marking by directly setting
    in_flight to current_limit and checking the stamp."""
    sched = PipelineScheduler()
    slot = _set_slot(sched, _cloud_slot(current_limit=2))
    slot.in_flight_requests = 2  # gate is full

    base = 10_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)
    monkeypatch.setattr(
        "prep.services.pipeline.scheduler.time.monotonic",
        lambda: 0.0,
    )

    # Acquire with timeout=0 (won't actually block, but must observe binding).
    token = sched.acquire_request("cloud:ep-test", timeout=0.0)
    assert token is None  # gate full, returned None

    # _gate_binding_until should have been stamped.
    assert slot._gate_binding_until > base
```

- [ ] **Step 2: Run tests to verify they fail.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py -v`
Expected: FAIL — `_maybe_demand_recover` does not exist; `slot._gate_binding_until` not initialized.

- [ ] **Step 3: Add the gate-binding field and demand-recovery method to scheduler.**

In `src/prep/services/pipeline/scheduler.py`, find the `ComputeSlot` dataclass field block (around lines 113-130). After `_last_recovery_time: float = 0.0`, add:

```python
    # Phase 119: demand-gating for recovery. Stamped by acquire_request
    # when a waiter observes the gate is binding (in_flight >= limit).
    # _maybe_demand_recover() only grows current_limit if now < this stamp.
    _gate_binding_until: float = 0.0
    # Phase 119: discovered ceiling lock (mirrors ConcurrencyStore record).
    # When set, recovery + AI cannot grow current_limit above this value
    # until ceiling_locked_until passes.
    discovered_ceiling: int | None = None
    ceiling_locked_until: float = 0.0
```

Find `_maybe_idle_recover` (around line 686). Rename it to `_maybe_demand_recover` and replace the body:

```python
    def _maybe_demand_recover(self, slot: ComputeSlot) -> None:
        """Grow ``slot.current_limit`` by 1 if recent demand justifies it.

        Caller MUST hold ``self._lock``.

        Phase 119 supersedes Phase 96 F-28's idle recovery: the original
        version grew on every acquire() call regardless of demand, which
        produced an unbounded random walk on cloud slots. The new
        version requires that ``acquire_request`` recently observed the
        gate as binding (``slot._gate_binding_until`` > now) before
        growing.

        Local slots cap at ``max_concurrent`` (VRAM is a real ceiling).
        Cloud slots cap at ``discovered_ceiling`` when locked, otherwise
        unbounded per Phase 82.
        """
        is_cloud = slot.node_id.startswith("cloud:")

        # Cap check — local has VRAM; cloud has the optional locked ceiling.
        if not is_cloud and slot.current_limit >= slot.max_concurrent:
            return
        if is_cloud and slot.discovered_ceiling is not None:
            if slot.current_limit >= slot.discovered_ceiling:
                return

        now = time.time()
        if now - slot._last_backoff_time < self._BACKOFF_COOLDOWN_S:
            return
        if now - slot._last_recovery_time < self._IDLE_RECOVERY_INTERVAL_S:
            return

        # Phase 119 demand gate — must have been binding within the window.
        if now >= slot._gate_binding_until:
            return

        if is_cloud:
            new_limit = slot.current_limit + 1
            if slot.discovered_ceiling is not None:
                new_limit = min(new_limit, slot.discovered_ceiling)
        else:
            new_limit = min(slot.max_concurrent, slot.current_limit + 1)

        if new_limit > slot.current_limit:
            logger.info(
                "Scheduler: Node %s demand-gated recovery %d -> %d "
                "(max=%d, floor=%d, ceiling=%s)",
                slot.node_id, slot.current_limit, new_limit,
                slot.max_concurrent, slot.min_limit,
                slot.discovered_ceiling,
            )
            slot.current_limit = new_limit
            slot._last_recovery_time = now
            self._persist_cloud_ceiling(slot)
            self._wake_slot_waiters(slot)
```

Update the call site in `acquire()` (around line 1118): change `self._maybe_idle_recover(slot)` to `self._maybe_demand_recover(slot)`.

Just below the class constants (around line 683, near `_BACKOFF_COOLDOWN_S = 30.0`), add:

```python
    # Phase 119 demand window: when acquire_request observes the gate
    # binding, the next 60 s allow recovery to fire.
    _DEMAND_WINDOW_S = 60.0
```

In `acquire_request` (around line 752), find the `while slot.in_flight_requests >= slot.dynamic_capacity` loop. Just before the `while`, add the gate-binding stamp:

```python
            cond = self._slot_condition(slot)

            # Phase 119: stamp gate-binding observations so demand-gated
            # recovery can fire later. Only stamp when the gate would
            # actually have been binding (in_flight at or above limit).
            if slot.in_flight_requests >= slot.dynamic_capacity:
                slot._gate_binding_until = time.time() + self._DEMAND_WINDOW_S

            while slot.in_flight_requests >= slot.dynamic_capacity:
                ...
```

(Replace the existing `cond = self._slot_condition(slot)` line with the block above.)

- [ ] **Step 4: Run tests to verify they pass.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Run broader scheduler tests for regressions.**

Run: `.venv/bin/pytest tests/ -k "scheduler" -v 2>&1 | tail -40`
Expected: no new failures relative to Task 0 baseline. (F-28's tests for `_maybe_idle_recover` will need rename or replacement — see Task 7.)

- [ ] **Step 6: Commit.**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_scheduler_demand_recovery.py
git commit -m "fix(phase119): gate AIMD recovery on real demand, not idle ticks

Replaces F-28 _maybe_idle_recover with _maybe_demand_recover. Recovery
only grows current_limit when acquire_request recently observed the
gate as binding (in_flight >= dynamic_capacity within last 60 s).

Stops the random-walk growth that produced the '60 with max=1' UI
display. Cloud slots clamped at discovered_ceiling when locked
(see follow-up for the lock mechanism)."
```

---

## Task 4: Scheduler — record edge on backoff, lock ceiling for TTL

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`
- Modify: `tests/test_scheduler_demand_recovery.py`

- [ ] **Step 1: Write the failing tests.**

Append to `tests/test_scheduler_demand_recovery.py`:

```python
def test_first_backoff_records_ceiling_with_lock(monkeypatch, tmp_path) -> None:
    """A backoff in congestion_avoidance mode persists a 24 h-locked ceiling."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-edge", max_concurrent=1)
    slot = sched._slots["cloud:ep-edge"]
    slot.current_limit = 16
    slot.in_flight_requests = 8
    slot.mode = "congestion_avoidance"

    base = 1_000_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    sched._record_throughput_for_slot(slot, queue_time_ms=0.0, is_429_or_timeout=True)

    # In-memory state
    assert slot.discovered_ceiling is not None
    assert slot.discovered_ceiling == slot.current_limit
    assert slot.ceiling_locked_until == base + 24 * 3600

    # Persisted state
    record = store_mod.concurrency_store().load_full("cloud:ep-edge", "__default__")
    assert record is not None
    assert record["ceiling"] == slot.discovered_ceiling
    assert record["locked_until"] == slot.ceiling_locked_until
    assert record["edge_observed_at"] == base


def test_jumpstart_backoff_does_not_lock(monkeypatch, tmp_path) -> None:
    """Backoff during jumpstart is exploration, not a confirmed edge — no lock."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-jump", max_concurrent=1)
    slot = sched._slots["cloud:ep-jump"]
    slot.mode = "jumpstart"
    slot.current_limit = 10
    slot.in_flight_requests = 5

    base = 1_000_000.0
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    sched._record_throughput_for_slot(slot, queue_time_ms=0.0, is_429_or_timeout=True)

    # The backoff still happens, but no lock is recorded.
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0
    record = store_mod.concurrency_store().load_full("cloud:ep-jump", "__default__")
    # save() may have been called for the backoff itself (legacy path) but
    # without a lock — assert the record reflects that.
    if record is not None:
        assert record["locked_until"] == 0.0


def test_locked_ceiling_blocks_growth_above(monkeypatch, tmp_path) -> None:
    """Once locked, congestion_avoidance AI cannot push current_limit past ceiling."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-cap", max_concurrent=1)
    slot = sched._slots["cloud:ep-cap"]
    slot.mode = "congestion_avoidance"
    slot.current_limit = 9
    slot.discovered_ceiling = 10

    # Patch time so the lock is unambiguously in the future.
    base = 1_000_000.0
    slot.ceiling_locked_until = base + 3600
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    # 9 successful calls = batch_size complete in CA → would normally grow.
    for _ in range(9):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)

    # Allowed to climb to ceiling, not above.
    assert slot.current_limit == 10

    # Another full window — still capped.
    for _ in range(20):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)
    assert slot.current_limit == 10


def test_lock_expires_after_ttl(monkeypatch, tmp_path) -> None:
    """After locked_until passes, growth is permitted again (one cautious probe)."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-ttl", max_concurrent=1)
    slot = sched._slots["cloud:ep-ttl"]
    slot.mode = "congestion_avoidance"
    slot.current_limit = 10
    slot.discovered_ceiling = 10
    slot.ceiling_locked_until = 100.0  # already in the past

    base = 100_000.0  # well after locked_until
    monkeypatch.setattr("prep.services.pipeline.scheduler.time.time", lambda: base)

    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)
    # One cautious +1 probe permitted.
    assert slot.current_limit == 11
```

- [ ] **Step 2: Run tests to verify they fail.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py::test_first_backoff_records_ceiling_with_lock tests/test_scheduler_demand_recovery.py::test_locked_ceiling_blocks_growth_above -v`
Expected: FAIL.

- [ ] **Step 3: Add edge recording to backoff path.**

In `src/prep/services/pipeline/scheduler.py`, find `_record_throughput_for_slot` (around line 503). At the top of the class add a constant near `_DEMAND_WINDOW_S`:

```python
    # Phase 119: how long a discovered ceiling stays locked. 24 h is
    # the project default; can be overridden via settings("concurrency_lock_ttl_s").
    _DEFAULT_LOCK_TTL_S = 24 * 3600
```

Add a helper method below `_persist_cloud_ceiling`:

```python
    def _record_ceiling_edge(self, slot: ComputeSlot, now: float) -> None:
        """Persist a discovered ceiling with TTL after a confirmed edge.

        Phase 119: only called from the backoff path when ``mode`` is
        already ``congestion_avoidance`` — i.e., a real edge, not
        jumpstart exploration. Caller MUST hold ``self._lock``.
        """
        if not slot.node_id.startswith("cloud:"):
            return
        try:
            from prep.services.settings_store import settings as _settings
            ttl = float(_settings.get("concurrency_lock_ttl_s") or self._DEFAULT_LOCK_TTL_S)
        except Exception:
            ttl = self._DEFAULT_LOCK_TTL_S

        slot.discovered_ceiling = slot.current_limit
        slot.ceiling_locked_until = now + ttl
        try:
            concurrency_store().save_edge(
                slot.node_id, "__default__",
                ceiling=slot.current_limit,
                locked_until=slot.ceiling_locked_until,
                edge_observed_at=now,
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.debug(
                "concurrency_store.save_edge failed for %s: %s",
                slot.node_id, exc,
            )
```

In the same method's MD branch (around line 537-567), after `slot._last_backoff_time = now` and `slot._last_recovery_time = now`, add:

```python
                # Phase 119: a backoff in CA is a confirmed edge — lock the ceiling.
                if slot.mode == "congestion_avoidance":
                    self._record_ceiling_edge(slot, now)
```

Note: the existing assignment `slot.mode = "congestion_avoidance"` happens BEFORE the MD math. Move it to AFTER the MD assignment, so the edge-recording branch sees the pre-MD mode (`jumpstart` or `congestion_avoidance`) — change the order so the order is:

```python
            if now - slot._last_backoff_time > 2.0:
                old_mode = slot.mode
                # Compute new_limit (existing MD math)
                ...
                if slot.current_limit > new_limit:
                    slot.current_limit = new_limit
                    self._persist_cloud_ceiling(slot)
                slot._last_backoff_time = now
                slot._last_recovery_time = now
                # Phase 119: only mode==congestion_avoidance is a confirmed edge.
                if old_mode == "congestion_avoidance":
                    self._record_ceiling_edge(slot, now)
                slot.mode = "congestion_avoidance"
                slot.success_streak = 0
```

In the AI/jumpstart branch (around line 569-603), before computing `new_limit`, add the locked-ceiling check inside the `if slot.success_streak >= batch_size:` block:

```python
            if slot.success_streak >= batch_size:
                slot.success_streak = 0
                allow_increase = is_cloud or slot.current_limit < slot.max_concurrent
                # Phase 119: locked ceiling blocks growth above the discovered point
                # until TTL passes. After TTL, one cautious +1 probe is allowed.
                if (
                    is_cloud
                    and slot.discovered_ceiling is not None
                    and slot.current_limit >= slot.discovered_ceiling
                    and time.time() < slot.ceiling_locked_until
                ):
                    allow_increase = False
                if allow_increase:
                    ... # existing jumpstart/CA branches
```

Modify the AI/jumpstart branches to clamp `new_limit` at `discovered_ceiling` when locked:

```python
                    if slot.mode == "jumpstart":
                        new_limit = slot.current_limit * 2
                        if not is_cloud:
                            new_limit = min(slot.max_concurrent, new_limit)
                        elif slot.discovered_ceiling is not None and time.time() < slot.ceiling_locked_until:
                            new_limit = min(slot.discovered_ceiling, new_limit)
                        ...
                    else:
                        new_limit = slot.current_limit + 1
                        if not is_cloud:
                            new_limit = min(slot.max_concurrent, new_limit)
                        elif slot.discovered_ceiling is not None and time.time() < slot.ceiling_locked_until:
                            new_limit = min(slot.discovered_ceiling, new_limit)
                        ...
```

- [ ] **Step 4: Run tests to verify they pass.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_scheduler_demand_recovery.py
git commit -m "feat(phase119): lock discovered ceiling for 24 h after first backoff edge

A backoff that fires while in congestion_avoidance mode is a confirmed
ceiling edge — record (ceiling, locked_until = now + 24h) via
ConcurrencyStore.save_edge. Subsequent AI/recovery growth clamps at
the locked ceiling until TTL expires, then a single cautious +1 probe
is allowed. Jumpstart backoffs are exploration, not edges — no lock."
```

---

## Task 5: Scheduler — hydrate ceiling lock on configure_node

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`
- Modify: `tests/test_scheduler_demand_recovery.py`

- [ ] **Step 1: Write the failing test.**

Append to `tests/test_scheduler_demand_recovery.py`:

```python
def test_configure_node_hydrates_lock_from_store(monkeypatch, tmp_path) -> None:
    """A daemon restart preserves the (ceiling, locked_until) record."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    base = 1_000_000.0
    store_mod.concurrency_store().save_edge(
        "cloud:ep-restart", "__default__",
        ceiling=12, locked_until=base + 1000, edge_observed_at=base - 60,
    )

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-restart", max_concurrent=1)
    slot = sched._slots["cloud:ep-restart"]

    assert slot.discovered_ceiling == 12
    assert slot.ceiling_locked_until == base + 1000
    # current_limit hydrates to the ceiling (we know it was achievable).
    assert slot.current_limit == 12
    # Mode is congestion_avoidance: we have a known edge, not exploration.
    assert slot.mode == "congestion_avoidance"
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py::test_configure_node_hydrates_lock_from_store -v`
Expected: FAIL — slot has `discovered_ceiling=None`.

- [ ] **Step 3: Modify `configure_node` to use `load_full`.**

In `src/prep/services/pipeline/scheduler.py`, find `configure_node` (around line 250-316). In the `else` branch (new slot creation), find the `if is_cloud:` persisted-load block and replace its body:

```python
                if is_cloud:
                    try:
                        record = concurrency_store().load_full(node_id, "__default__")
                    except Exception as exc:
                        logger.debug(
                            "concurrency_store.load_full failed for %s: %s",
                            node_id, exc,
                        )
                        record = None
                    if record is not None:
                        seed = record["ceiling"]
                        mode = "congestion_avoidance"
                        # Phase 119: hydrate lock state too.
                        discovered_ceiling = record["ceiling"] if record["locked_until"] > 0 else None
                        ceiling_locked_until = record["locked_until"]
                    else:
                        discovered_ceiling = None
                        ceiling_locked_until = 0.0
                else:
                    discovered_ceiling = None
                    ceiling_locked_until = 0.0
```

(Initialize `discovered_ceiling = None` and `ceiling_locked_until = 0.0` for the local-slot path too.)

When constructing `ComputeSlot`, pass the hydrated lock state:

```python
                self._slots[node_id] = ComputeSlot(
                    node_id=node_id,
                    max_concurrent=new_max,
                    current_limit=seed,
                    min_limit=self._compute_min_limit(node_id, new_max),
                    mode=mode,
                    discovered_ceiling=discovered_ceiling,
                    ceiling_locked_until=ceiling_locked_until,
                )
```

- [ ] **Step 4: Run tests to verify they pass.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_scheduler_demand_recovery.py
git commit -m "feat(phase119): hydrate discovered ceiling and lock from store on restart

configure_node now reads (ceiling, locked_until) via load_full and
seeds the slot in congestion_avoidance mode at the locked ceiling.
The user no longer sees the limit reset to 5 after every daemon
restart — they see the ceiling that was discovered and locked."
```

---

## Task 6: Scheduler — use Ollama probe for new cloud slot seed

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py`
- Modify: `tests/test_scheduler_demand_recovery.py`

- [ ] **Step 1: Write the failing test.**

Append to `tests/test_scheduler_demand_recovery.py`:

```python
def test_new_cloud_slot_uses_ollama_probe_when_no_persistence(monkeypatch, tmp_path) -> None:
    """First-time configuration of a cloud-via-Ollama slot probes /api/ps."""
    from prep.core import paths as paths_mod
    from prep.services.pipeline import concurrency_store as store_mod
    from prep.services.pipeline import ollama_probe as probe_mod

    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    store_mod._store = None
    monkeypatch.setattr(probe_mod, "probe_ollama_concurrency", lambda host, timeout=1.5: 12)

    sched = PipelineScheduler()
    sched.configure_node("cloud:default_ollama", max_concurrent=1)
    slot = sched._slots["cloud:default_ollama"]

    # Probe seeded the slot at 12 (not the legacy 5 default, not max_concurrent=1).
    assert slot.current_limit == 12
    assert slot.mode == "jumpstart"  # still exploring above the probe
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py::test_new_cloud_slot_uses_ollama_probe_when_no_persistence -v`
Expected: FAIL — `current_limit == 5`.

- [ ] **Step 3: Wire the probe into configure_node.**

At the top of `src/prep/services/pipeline/scheduler.py` add:

```python
from prep.services.pipeline.ollama_probe import probe_ollama_concurrency
```

In `configure_node`'s new-cloud-slot path, after the `if record is not None` branch, add an `else` arm that probes:

```python
                if is_cloud:
                    ...  # existing load_full block, sets seed if record exists
                    if record is None and node_id == "cloud:default_ollama":
                        # Phase 119: probe Ollama instead of seeding at the static 5.
                        try:
                            from prep.services.settings_store import settings as _s
                            llm_config = _s.get("llm_config") or {}
                            host = ""
                            for ep in llm_config.get("saved_endpoints", []):
                                if ep.get("id") == "default_ollama":
                                    host = ep.get("base_url") or "http://localhost:11434"
                                    break
                            host = host or "http://localhost:11434"
                            seed = probe_ollama_concurrency(host)
                        except Exception as exc:
                            logger.debug("Ollama probe error for seed: %s", exc)
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `.venv/bin/pytest tests/test_scheduler_demand_recovery.py::test_new_cloud_slot_uses_ollama_probe_when_no_persistence -v`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/services/pipeline/scheduler.py tests/test_scheduler_demand_recovery.py
git commit -m "feat(phase119): seed new cloud:default_ollama slots from /api/ps

When configuring cloud:default_ollama with no persisted ceiling, probe
the Ollama daemon for OLLAMA_NUM_PARALLEL or /api/ps slot count
instead of using the static Phase 82 seed of 5. Other cloud endpoints
(true cloud APIs) keep the 5 default."
```

---

## Task 7: Update F-28 tests — they tested the now-removed `_maybe_idle_recover`

**Files:**
- Modify: `tests/test_pipeline_scheduler.py` (or wherever F-28 tests live)

- [ ] **Step 1: Find F-28 tests.**

Run: `grep -rn "test_idle_recovery\|_maybe_idle_recover" tests/ | head -20`

- [ ] **Step 2: For each test that exercised `_maybe_idle_recover`:**

Each test fits one of two categories:
- **Demand-relevant** (e.g., "recovery happens after backoff cooldown"): rename method call, add `slot._gate_binding_until = time.time() + 60` to satisfy demand gate, keep otherwise.
- **Demand-irrelevant** (e.g., "recovery skipped during cooldown"): rename method call, set `_gate_binding_until` to make the test cover the F-28 invariant.

Concrete rename: `_maybe_idle_recover` → `_maybe_demand_recover`. For each test, also stamp `slot._gate_binding_until = time.time() + sched._DEMAND_WINDOW_S` before the call (otherwise the demand gate blocks all of them and the F-28 invariants don't get exercised).

- [ ] **Step 3: Run the suite.**

Run: `.venv/bin/pytest tests/test_pipeline_scheduler.py -v 2>&1 | tail -30`
Expected: all F-28 tests PASS with the new method name and demand stamp.

- [ ] **Step 4: Commit.**

```bash
git add tests/test_pipeline_scheduler.py
git commit -m "test(phase119): port F-28 idle-recovery tests onto demand-recovery

The method was renamed to _maybe_demand_recover and gated on a real
demand stamp. Tests stamp _gate_binding_until before calling so the
original F-28 invariants (cooldown gating, ceiling clamp) still
exercise. New invariant — demand-gating itself — is covered in
tests/test_scheduler_demand_recovery.py."
```

---

## Task 8: Status API — surface `state`, `discovered_ceiling`, `locked_until`

**Files:**
- Modify: `src/prep/services/pipeline/scheduler.py` (`status()` method)
- Modify: `src/prep/api/routers/queue.py`
- Create: `tests/test_queue_status_state.py`

- [ ] **Step 1: Write the failing test.**

Create `tests/test_queue_status_state.py`:

```python
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
    resp = client.get("/queue/status")
    body = resp.json()
    assert resp.status_code == 200
    nodes = body.get("nodes") or body.get("data", {}).get("nodes")
    n = nodes["cloud:status-test"]
    assert n["discovered_ceiling"] == 10
    assert n["locked_until"] > time.time()
    assert n["aimd_mode"] in ("jumpstart", "congestion_avoidance")
    assert n["state"] in ("probing", "locked", "backing_off", "recovering")


def test_state_locked_when_within_ttl(tmp_path, monkeypatch) -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=10,
        ceiling_locked_until=time.time() + 3600,
        last_backoff_time=time.time() - 600,
        backoff_cooldown_s=30.0,
    )
    assert s == "locked"


def test_state_backing_off_when_recent_backoff(tmp_path, monkeypatch) -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=10,
        ceiling_locked_until=time.time() + 3600,
        last_backoff_time=time.time() - 5,   # 5 s ago < cooldown 30 s
        backoff_cooldown_s=30.0,
    )
    assert s == "backing_off"


def test_state_recovering_when_lock_expired(tmp_path, monkeypatch) -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=10,
        ceiling_locked_until=time.time() - 1,
        last_backoff_time=time.time() - 6000,
        backoff_cooldown_s=30.0,
    )
    assert s == "recovering"


def test_state_probing_when_no_lock_no_backoff(tmp_path, monkeypatch) -> None:
    from prep.services.pipeline.scheduler import _derive_node_state

    s = _derive_node_state(
        discovered_ceiling=None,
        ceiling_locked_until=0.0,
        last_backoff_time=0.0,
        backoff_cooldown_s=30.0,
    )
    assert s == "probing"
```

- [ ] **Step 2: Run tests to verify they fail.**

Run: `.venv/bin/pytest tests/test_queue_status_state.py -v`
Expected: FAIL — `_derive_node_state` doesn't exist; `node_summary` lacks new fields.

- [ ] **Step 3: Add `_derive_node_state` and surface fields.**

In `src/prep/services/pipeline/scheduler.py`, add at module level (above `PipelineScheduler` class):

```python
def _derive_node_state(
    *,
    discovered_ceiling: int | None,
    ceiling_locked_until: float,
    last_backoff_time: float,
    backoff_cooldown_s: float,
) -> str:
    """Derive a presentation-layer state for a compute slot.

    Phase 119 — replaces the misleading raw-number triplet in the UI.
    """
    now = time.time()
    if now - last_backoff_time < backoff_cooldown_s:
        return "backing_off"
    if discovered_ceiling is not None:
        if now < ceiling_locked_until:
            return "locked"
        return "recovering"
    return "probing"
```

In the existing `status()` method, add the new fields per node:

```python
                "discovered_ceiling": slot.discovered_ceiling,
                "locked_until": slot.ceiling_locked_until or None,
                "aimd_mode": slot.mode,
                "state": _derive_node_state(
                    discovered_ceiling=slot.discovered_ceiling,
                    ceiling_locked_until=slot.ceiling_locked_until,
                    last_backoff_time=slot._last_backoff_time,
                    backoff_cooldown_s=self._BACKOFF_COOLDOWN_S,
                ),
```

In `src/prep/api/routers/queue.py`, find `node_summary` construction (around line 220-229) and add the same fields:

```python
        node_summary[nid] = {
            "max_concurrent": node_info.get("max_concurrent", 1),
            "current_load": node_info.get("current_load", 0),
            "in_flight_requests": node_info.get("in_flight_requests", 0),
            "current_limit": node_info.get("current_limit", node_info.get("max_concurrent", 1)),
            "discovered_ceiling": node_info.get("discovered_ceiling"),
            "locked_until": node_info.get("locked_until"),
            "aimd_mode": node_info.get("aimd_mode"),
            "state": node_info.get("state", "probing"),
            "active": node_info.get("active", {}),
            "queued": node_info.get("queued", []),
        }
```

- [ ] **Step 4: Run tests to verify they pass.**

Run: `.venv/bin/pytest tests/test_queue_status_state.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/services/pipeline/scheduler.py src/prep/api/routers/queue.py tests/test_queue_status_state.py
git commit -m "feat(phase119): expose ceiling-lock state in /queue/status

node_summary now includes discovered_ceiling, locked_until, aimd_mode,
and a derived 'state' string in {probing, locked, backing_off,
recovering}. The frontend uses 'state' to drop the misleading
'(max N)' annotation and show a meaningful badge instead."
```

---

## Task 9: Admin endpoint — clear a lock for re-detection

**Files:**
- Modify: `src/prep/api/routers/compute.py`
- Modify: `tests/test_queue_status_state.py`

- [ ] **Step 1: Write the failing test.**

Append to `tests/test_queue_status_state.py`:

```python
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
    resp = client.post("/compute/concurrency/clear", params={"node_id": "cloud:lock-test"})
    assert resp.status_code in (200, 204)

    # Slot lock cleared in-memory.
    assert slot.discovered_ceiling is None
    assert slot.ceiling_locked_until == 0.0
    # Persisted record gone.
    assert store_mod.concurrency_store().load_full("cloud:lock-test", "__default__") is None
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `.venv/bin/pytest tests/test_queue_status_state.py::test_clear_concurrency_endpoint_invalidates_lock -v`
Expected: FAIL with 404.

- [ ] **Step 3: Add the endpoint.**

In `src/prep/api/routers/compute.py`, add:

```python
@router.post("/concurrency/clear")
def clear_concurrency_lock(node_id: str) -> dict[str, str]:
    """Phase 119: clear a discovered-ceiling lock so AIMD re-probes.

    Removes the persisted record AND resets the in-memory slot so the
    next call sees `state="probing"`. Useful when the user knows the
    backend capacity changed (plan upgrade, new endpoint).
    """
    from prep.services.pipeline.concurrency_store import concurrency_store
    from prep.services.pipeline.scheduler import pipeline_scheduler

    try:
        concurrency_store().clear(node_id, "__default__")
    except Exception:
        pass
    slot = pipeline_scheduler._slots.get(node_id)
    if slot is not None:
        slot.discovered_ceiling = None
        slot.ceiling_locked_until = 0.0
    return {"status": "ok", "node_id": node_id}
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `.venv/bin/pytest tests/test_queue_status_state.py::test_clear_concurrency_endpoint_invalidates_lock -v`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prep/api/routers/compute.py tests/test_queue_status_state.py
git commit -m "feat(phase119): add POST /compute/concurrency/clear admin endpoint

Manually invalidates a discovered-ceiling lock so AIMD re-probes.
Useful when the user upgrades a plan or swaps endpoints."
```

---

## Task 10: Frontend — drop `(max N)`, add state badge

**Files:**
- Modify: `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`

- [ ] **Step 1: Read the current rendering and the API contract type.**

Run: `grep -n 'max_concurrent\|current_limit\|in_flight' packages/ui/src/types/queue.ts 2>/dev/null || true`
Run: `grep -rn 'in_flight_requests' packages/ui/src/components/navigation/ | head`

Confirm the `node` shape that flows in. Add the new fields to the type definition:

```typescript
// packages/ui/src/types/queue.ts (or wherever NodeSummary is declared)
export interface NodeSummary {
  max_concurrent: number;
  current_load: number;
  in_flight_requests: number;
  current_limit: number;
  discovered_ceiling: number | null;
  locked_until: number | null;
  aimd_mode: 'jumpstart' | 'congestion_avoidance' | null;
  state: 'probing' | 'locked' | 'backing_off' | 'recovering';
  active: Record<string, string>;
  queued: unknown[];
}
```

- [ ] **Step 2: Replace the `(max N)` annotation with a state pill.**

In `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`, lines 270-282 currently render:

```tsx
{Object.entries(nodes).map(([nid, n]) => (
  <div key={nid} className="flex items-center justify-between text-[10px] text-text-muted tabular-nums">
    <span className="truncate max-w-[140px]" title={nid}>{nid}</span>
    <span>
      {n.in_flight_requests} / {n.current_limit}
      {n.current_limit !== n.max_concurrent && (
        <span className="ml-1 opacity-60">(max {n.max_concurrent})</span>
      )}
    </span>
  </div>
))}
```

Replace with:

```tsx
{Object.entries(nodes).map(([nid, n]) => {
  const ceiling = n.discovered_ceiling;
  // Primary number: in_flight / (locked ceiling or current_limit).
  const cap = ceiling != null && n.state === 'locked' ? ceiling : n.current_limit;
  const stateBadge = (() => {
    switch (n.state) {
      case 'locked': return { icon: '🔒', label: 'locked' };
      case 'backing_off': return { icon: '🔻', label: 'backing off' };
      case 'recovering': return { icon: '↗', label: 'recovering' };
      case 'probing':
      default: return { icon: '📈', label: 'probing' };
    }
  })();
  // Soft user cap (only when explicitly set below the discovered ceiling).
  const userCap =
    n.max_concurrent > 1 && ceiling != null && n.max_concurrent < ceiling
      ? n.max_concurrent
      : null;
  return (
    <div key={nid} className="flex items-center justify-between text-[10px] text-text-muted tabular-nums">
      <span className="truncate max-w-[140px]" title={nid}>{nid}</span>
      <span className="inline-flex items-center gap-1">
        {n.in_flight_requests} / {cap}
        <span title={stateBadge.label} aria-label={stateBadge.label} className="opacity-70">
          {stateBadge.icon}
        </span>
        {userCap != null && (
          <span className="ml-1 opacity-60">(cap {userCap})</span>
        )}
      </span>
    </div>
  );
})}
```

- [ ] **Step 3: Verify TypeScript and lint.**

Run: `cd packages/ui && npm run typecheck 2>&1 | tail -20`
Run: `cd packages/ui && npm run lint 2>&1 | tail -20`
Expected: clean.

- [ ] **Step 4: Manual smoke (where possible).**

Start dashboard: `scripts/dev.sh` (in another terminal). Browse to `http://localhost:5174`. With at least one cloud:* node configured, confirm:
- The label shows `in_flight / cap` followed by a state badge.
- No raw `(max 1)` text anymore.
- `(cap N)` appears only when `max_concurrent` is explicitly below the discovered ceiling.

If the agentic environment can't run a browser, skip — flag in the commit message.

- [ ] **Step 5: Commit.**

```bash
git add packages/ui/src/components/navigation/SidebarPipelineQueue.tsx \
        packages/ui/src/types/queue.ts 2>/dev/null || true
git add -u packages/ui/
git commit -m "feat(phase119-ui): replace misleading (max N) with state badge

The pipeline-queue panel now shows in_flight / discovered_ceiling
plus a state pill (probing | locked | backing off | recovering).
Soft user caps render as '(cap N)' only when explicitly set below
the discovered ceiling."
```

---

## Task 11: Frontend type + API contract test

**Files:**
- Modify: `tests/test_queue_status_state.py` (add a JSON-shape assertion)
- Optional: `packages/ui/src/types/queue.ts` (already added in Task 10)

- [ ] **Step 1: Append a contract test to ensure the API shape stays stable.**

```python
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
    resp = client.get("/queue/status")
    body = resp.json()
    nodes = body.get("nodes") or body.get("data", {}).get("nodes")
    n = nodes["cloud:contract-test"]
    expected = {
        "max_concurrent", "current_load", "in_flight_requests",
        "current_limit", "discovered_ceiling", "locked_until",
        "aimd_mode", "state", "active", "queued",
    }
    assert set(n.keys()) >= expected, f"missing fields: {expected - set(n.keys())}"
```

- [ ] **Step 2: Run.**

Run: `.venv/bin/pytest tests/test_queue_status_state.py -v`
Expected: PASS.

- [ ] **Step 3: Commit.**

```bash
git add tests/test_queue_status_state.py
git commit -m "test(phase119): pin /queue/status node_summary contract

Asserts the field set so unrelated refactors can't silently drop a
field the frontend depends on."
```

---

## Task 12: Live verification — re-run rust_repo sweep

**Files:** (read-only validation)

- [ ] **Step 1: Wipe the persisted ceiling for a clean test.**

```bash
sqlite3 ~/.local/share/sourceprep/concurrency_store.db \
  "DELETE FROM discovered_ceilings WHERE node_id = 'cloud:default_ollama';"
```

- [ ] **Step 2: Restart the daemon.**

```bash
pkill -f "prep serve"; sleep 2
.venv/bin/prep serve > /tmp/prep_phase119.log 2>&1 &
sleep 5
```

- [ ] **Step 3: Trigger a Finalize sweep on the test repo (small, fast).**

(Either via UI or API.) Watch the log for the new behavior:

```bash
tail -F /tmp/prep_phase119.log | grep -E "(jumpstart|demand-gated|edge|locked|Backing off)"
```

Expected:
- `Scheduler: Node cloud:default_ollama jumpstart 12 -> 24` (probe seeded at 12, doubles).
- After a backoff: `Scheduler: ... edge locked at 18 (locked_until=…)`.
- No more `idle recovery N -> N+1` lines in the absence of demand.

- [ ] **Step 4: Restart, confirm hydration.**

```bash
pkill -f "prep serve"; sleep 2
.venv/bin/prep serve > /tmp/prep_phase119_after.log 2>&1 &
sleep 5
curl -s http://localhost:8400/queue/status | python -m json.tool | grep -A 8 cloud:default_ollama
```

Expected: `discovered_ceiling: 18` (or whatever was locked), `state: locked`, `current_limit: 18` (hydrated). Confirms the lock survives restart.

- [ ] **Step 5: Visual inspection.**

Open `http://localhost:5174`. Confirm the queue panel shows e.g. `cloud:default_ollama  0 / 18 🔒` and no `(max 1)` annotation.

- [ ] **Step 6: No commit — observation only.**

If anything looks off, return to the relevant earlier task and fix.

---

## Task 13: Note Phase 119 in the bug registry + Phase 82 docs

**Files:**
- Modify: `docs/Phase96-fix-pipeline/05_FINDINGS_AND_BUGS_REGISTRY.md` — add a follow-up note under F-28
- Modify: `docs/Phase82_CloudPipelineConcurrency/01_Latency_Aware_Discovery.md` — add a "Stability follow-up" banner near the top

- [ ] **Step 1: Append a follow-up note to F-28 in the bug registry.**

After the existing F-28 closure (around line 416 of `05_FINDINGS_AND_BUGS_REGISTRY.md`), add:

```markdown

**Follow-up (2026-04-25, Phase 119):** F-28's idle recovery shipped without
demand-gating. On cloud slots — which Phase 82 makes unbounded on the upward
path — this produced a slow random walk: every 30 s `acquire()` call grew
`current_limit` by 1 regardless of whether anything was waiting on the gate.
Combined with backoffs that collapsed to `min_limit=3`, the net effect was
the "60 with max=1" UI display and 67 → 3 whiplash on transient timeouts.

Phase 119 supersedes F-28 by:
- Renaming `_maybe_idle_recover` → `_maybe_demand_recover`.
- Gating growth on `slot._gate_binding_until` (stamped by `acquire_request`
  when in-flight is at or above the cap).
- Locking discovered ceilings for 24 h after the first backoff edge in
  `congestion_avoidance` mode.

See `docs/Phase119_ConcurrencyStability/01_Design.md` for the full design.
```

- [ ] **Step 2: Banner on Phase 82 latency-aware discovery doc.**

Insert at the top of `docs/Phase82_CloudPipelineConcurrency/01_Latency_Aware_Discovery.md`:

```markdown
> **Stability follow-up (2026-04-25, Phase 119):** Phase 82 keeps unbounded
> upward discovery, but on its own it produced a "discovered ceiling that
> kept growing forever" symptom because F-28's idle recovery walked
> `current_limit` upward without real demand. Phase 119 adds demand-gating
> + 24 h ceiling lock on top of Phase 82. See
> `docs/Phase119_ConcurrencyStability/01_Design.md`.
```

- [ ] **Step 3: Commit.**

```bash
git add docs/Phase96-fix-pipeline/05_FINDINGS_AND_BUGS_REGISTRY.md \
        docs/Phase82_CloudPipelineConcurrency/01_Latency_Aware_Discovery.md
git commit -m "docs(phase119): cross-link from F-28 and Phase 82 to Phase 119

F-28 closure note explains why idle recovery needed demand-gating;
Phase 82 doc gets a stability follow-up banner pointing at the
discovered-ceiling lock work in Phase 119."
```

---

## Self-Review Checklist

After execution:

1. **Spec coverage:** Every Phase 119 design goal is covered by a task?
   - Demand-gated growth — Task 3 ✓
   - Ceiling lock with TTL — Task 4 ✓
   - Lock hydration on restart — Task 5 ✓
   - Ollama probe seed — Tasks 2 + 6 ✓
   - UI state badge replaces `(max N)` — Tasks 8 + 10 ✓
   - Admin clear endpoint — Task 9 ✓
   - F-28 test port — Task 7 ✓
   - Cross-doc references — Task 13 ✓

2. **Placeholder scan:** No "TBD", "similar to Task N", or vague "handle the case" in any step.

3. **Type consistency:** `_maybe_demand_recover`, `_DEMAND_WINDOW_S`, `_DEFAULT_LOCK_TTL_S`, `_record_ceiling_edge`, `_derive_node_state`, `discovered_ceiling`, `ceiling_locked_until`, `_gate_binding_until` — names match across all tasks. `ConcurrencyStore.load_full` / `save_edge` / `clear` API used consistently.

4. **No new unused code:** Every helper introduced (`probe_ollama_concurrency`, `_record_ceiling_edge`, `_derive_node_state`) has at least one production caller AND at least one test.

5. **No regressions to Phase 82:** Cloud slots remain unbounded *until* the first edge; jumpstart doubling untouched; congestion_avoidance MD math untouched. The only behavioral change is that a confirmed edge now persists with TTL and clamps subsequent growth.

---

## Execution Handoff

Plan complete and saved to `docs/Phase119_ConcurrencyStability/02_Implementation_Plan.md`.

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

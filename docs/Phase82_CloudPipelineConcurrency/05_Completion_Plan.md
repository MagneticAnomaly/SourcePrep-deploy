# Phase 82 Completion — Unbounded Latency-Aware Discovery

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 82 by removing the hardcoded Ollama-plan-tier concurrency cap reintroduced in Phase 112, uncapping AIMD discovery for cloud slots, persisting discovered ceilings across daemon restarts, and fixing the AI Gateway UI to show live in-flight API call counts instead of the configured maximum.

**Architecture:** The latency-aware discovery scheduler already exists (`src/codrag/services/pipeline/scheduler.py`, `record_throughput` + AIMD). The Phase 82 mechanism currently fails on two counts: (1) `ComputeSlot.dynamic_capacity = min(max_concurrent, current_limit)` clips the discovered limit at whatever the user typed into `cloud_concurrency`, and (2) `batch_profiles.get_batch_concurrency()` early-returns a hardcoded plan-tier number for cloud models before the scheduler is ever consulted. We remove both clips, initialize cloud slots at the Phase 82 seed (`current_limit = 5`, `mode = "jumpstart"`), and add a small SQLite-backed `ConcurrencyStore` that persists the discovered ceiling per `(endpoint_id, model_family)` so daemon restarts don't replay the jumpstart from scratch. The AI Gateway is rewired to read the live in-flight count from `token_telemetry._active_requests` instead of the scheduler's `dynamic_capacity`.

**Tech Stack:** Python 3.11 (asyncio, stdlib sqlite3), FastAPI, pytest-asyncio, React + TypeScript (frontend). SQLite DELETE mode (WAL unreliable on USB per project policy).

---

## File Structure

**Create:**
- `src/codrag/services/pipeline/concurrency_store.py` — SQLite-backed persistence for discovered per-(endpoint, model-family) ceilings. One responsibility: load/save ceiling integers, no business logic.
- `tests/test_concurrency_store.py` — Unit tests for the store.
- `tests/test_scheduler_unbounded_discovery.py` — Scheduler AIMD-past-max-concurrent + cloud seed + persistence integration tests.
- `tests/test_batch_profiles_no_plan_tier.py` — Regression tests confirming cloud dispatch goes through scheduler, not the removed early-return.

**Modify:**
- `src/codrag/services/pipeline/scheduler.py` — Remove the cloud cap, change cloud `current_limit` seed, wire persistence load/save into AIMD.
- `src/codrag/core/batch_profiles.py` — Delete the cloud early-return block and the two plan-tier helpers.
- `src/codrag/core/swarm_optimizer.py` — Delete `PLAN_TIER_CONCURRENCY` dict and `PlanTier` literal.
- `src/codrag/server.py` — Remove `ollama_plan_tier` and `custom_concurrency` from advanced-LLM-settings defaults.
- `src/codrag/api/routers/llm.py` — Rewire `_build_llm_slots_sync()` to use live telemetry counts, not scheduler config maxima.
- `packages/ui/src/components/settings/AdvancedLLMSettings.tsx` — Remove plan-tier dropdown and custom-concurrency slider.
- `docs/Phase82_CloudPipelineConcurrency/03_Implementation_Plan.md` — Note Phase 82 completion delta at top.

---

## Task 0: Baseline — capture current state before changes

**Files:** (read-only)

- [ ] **Step 1: Run full Python test suite and record pass/fail count**

Run: `.venv/bin/pytest tests/ -x --tb=short 2>&1 | tail -30`
Expected: record baseline. Note any pre-existing failures that are NOT related to this plan (so we don't misattribute them later).

- [ ] **Step 2: Confirm Phase 82 documents exist**

Run: `ls docs/Phase82_CloudPipelineConcurrency/`
Expected: `01_Latency_Aware_Discovery.md`, `02_Design_Spec.md`, `03_Implementation_Plan.md`, `04_Stage_Handoff_Investigation.md`. This plan becomes `05_Completion_Plan.md`.

- [ ] **Step 3: Confirm current bug reproduction — single-LLM-call execution**

Run: `.venv/bin/python -c "from codrag.core.batch_profiles import _get_plan_tier, _resolve_plan_tier_concurrency; print('tier:', _get_plan_tier()); print('concurrency:', _resolve_plan_tier_concurrency())"`
Expected: `tier: free` and `concurrency: 1`. This is the bug: cloud dispatch returns 1 regardless of what AIMD discovered.

- [ ] **Step 4: No commit — this task is observational.**

---

## Task 1: ConcurrencyStore — persisted ceiling per (endpoint, model-family)

**Files:**
- Create: `src/codrag/services/pipeline/concurrency_store.py`
- Create: `tests/test_concurrency_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_concurrency_store.py`:

```python
"""Tests for ConcurrencyStore — persisted AIMD ceilings.

Phase 82 completion: on daemon restart, the scheduler should
re-hydrate the discovered ceiling per (endpoint, model_family)
instead of replaying jumpstart from seed=5 every boot. The
mode/streak/backoff-time state deliberately does NOT survive
restart — only the ceiling carries forward.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from codrag.services.pipeline.concurrency_store import ConcurrencyStore


@pytest.fixture
def store(tmp_path: Path) -> ConcurrencyStore:
    return ConcurrencyStore(tmp_path / "concurrency.db")


def test_load_missing_returns_none(store: ConcurrencyStore) -> None:
    assert store.load("cloud:ep-1", "qwen3-coder") is None


def test_save_then_load_roundtrip(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    assert store.load("cloud:ep-1", "qwen3-coder") == 40


def test_save_overwrites(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=20)
    store.save("cloud:ep-1", "qwen3-coder", ceiling=80)
    assert store.load("cloud:ep-1", "qwen3-coder") == 80


def test_distinct_model_families_are_independent(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    store.save("cloud:ep-1", "gemini-2.5-flash", ceiling=10)
    assert store.load("cloud:ep-1", "qwen3-coder") == 40
    assert store.load("cloud:ep-1", "gemini-2.5-flash") == 10


def test_distinct_endpoints_are_independent(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    store.save("cloud:ep-2", "qwen3-coder", ceiling=80)
    assert store.load("cloud:ep-1", "qwen3-coder") == 40
    assert store.load("cloud:ep-2", "qwen3-coder") == 80


def test_clear_removes_entry(store: ConcurrencyStore) -> None:
    store.save("cloud:ep-1", "qwen3-coder", ceiling=40)
    store.clear("cloud:ep-1", "qwen3-coder")
    assert store.load("cloud:ep-1", "qwen3-coder") is None


def test_minimum_ceiling_is_rejected(store: ConcurrencyStore) -> None:
    """Ceilings below the jumpstart seed (5) are nonsensical — refuse them."""
    with pytest.raises(ValueError):
        store.save("cloud:ep-1", "qwen3-coder", ceiling=0)
    with pytest.raises(ValueError):
        store.save("cloud:ep-1", "qwen3-coder", ceiling=-1)


def test_uses_delete_journal_mode(tmp_path: Path) -> None:
    """Per project policy: WAL is unreliable on USB, use DELETE journal mode."""
    store = ConcurrencyStore(tmp_path / "concurrency.db")
    store.save("cloud:ep-1", "qwen3-coder", ceiling=10)
    import sqlite3

    conn = sqlite3.connect(tmp_path / "concurrency.db")
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == "delete"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_concurrency_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codrag.services.pipeline.concurrency_store'`.

- [ ] **Step 3: Write the implementation**

Create `src/codrag/services/pipeline/concurrency_store.py`:

```python
"""Persistence for Phase 82 discovered concurrency ceilings.

The AIMD scheduler learns each provider's real ceiling at runtime via
latency-aware discovery. Without persistence, every daemon restart
replays the jumpstart from seed=5 — wasteful when the user has already
been running for hours and the ceiling is known to be, say, 40.

Only the *ceiling* survives restart. Mode (jumpstart vs
congestion_avoidance), success streak, and last-backoff timestamp all
reset, because they're hot-loop state with no meaning across a restart
boundary.

Storage: single SQLite file at ``<data_dir>/concurrency_store.db``.
DELETE journal mode (WAL is unreliable on USB per project policy).
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovered_ceilings (
    node_id TEXT NOT NULL,
    model_family TEXT NOT NULL,
    ceiling INTEGER NOT NULL,
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (node_id, model_family)
)
"""


class ConcurrencyStore:
    """Persisted AIMD ceilings keyed by (node_id, model_family)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode = DELETE")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def load(self, node_id: str, model_family: str) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ceiling FROM discovered_ceilings "
                "WHERE node_id = ? AND model_family = ?",
                (node_id, model_family),
            ).fetchone()
        return int(row[0]) if row else None

    def save(self, node_id: str, model_family: str, *, ceiling: int) -> None:
        if ceiling < 1:
            raise ValueError(f"ceiling must be >= 1, got {ceiling!r}")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO discovered_ceilings (node_id, model_family, ceiling) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(node_id, model_family) DO UPDATE SET "
                "ceiling = excluded.ceiling, "
                "updated_at = strftime('%s', 'now')",
                (node_id, model_family, int(ceiling)),
            )
            conn.commit()

    def clear(self, node_id: str, model_family: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM discovered_ceilings "
                "WHERE node_id = ? AND model_family = ?",
                (node_id, model_family),
            )
            conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_concurrency_store.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/concurrency_store.py tests/test_concurrency_store.py
git commit -m "feat(phase82): add ConcurrencyStore for persisted AIMD ceilings

Per-(node_id, model_family) ceiling persistence so daemon restarts
don't replay jumpstart from seed=5. DELETE journal mode per project
policy (WAL unreliable on USB)."
```

---

## Task 2: Singleton ConcurrencyStore tied to daemon data dir

**Files:**
- Modify: `src/codrag/services/pipeline/concurrency_store.py`
- Modify: `tests/test_concurrency_store.py`

- [ ] **Step 1: Write the failing test for the module-level singleton**

Append to `tests/test_concurrency_store.py`:

```python
def test_default_store_uses_data_dir(monkeypatch, tmp_path: Path) -> None:
    """The module-level singleton reads from `data_dir() / concurrency_store.db`."""
    from codrag.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from codrag.services.pipeline import concurrency_store as mod

    # Force re-init by calling the accessor
    mod._store = None  # type: ignore[attr-defined]
    s = mod.concurrency_store()
    s.save("cloud:ep-1", "test-model", ceiling=10)
    assert (tmp_path / "concurrency_store.db").exists()
    assert s.load("cloud:ep-1", "test-model") == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_concurrency_store.py::test_default_store_uses_data_dir -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'concurrency_store'`.

- [ ] **Step 3: Add the accessor to `concurrency_store.py`**

Append to `src/codrag/services/pipeline/concurrency_store.py`:

```python
_store: Optional[ConcurrencyStore] = None


def concurrency_store() -> ConcurrencyStore:
    """Return the daemon-wide ConcurrencyStore singleton.

    Stored at ``<data_dir>/concurrency_store.db``. See
    ``codrag.core.paths.data_dir`` for the resolution rules.
    """
    global _store
    if _store is None:
        from codrag.core.paths import data_dir
        _store = ConcurrencyStore(data_dir() / "concurrency_store.db")
    return _store
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_concurrency_store.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/concurrency_store.py tests/test_concurrency_store.py
git commit -m "feat(phase82): add module-level ConcurrencyStore singleton

Anchored at data_dir()/concurrency_store.db via lazy accessor so
tests can monkeypatch paths.data_dir to isolate state."
```

---

## Task 3: Scheduler — uncap cloud discovery (AIMD past `max_concurrent`)

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py:100-135` and `481-492`
- Create: `tests/test_scheduler_unbounded_discovery.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scheduler_unbounded_discovery.py`:

```python
"""Phase 82 completion: cloud AIMD is unbounded; local remains VRAM-capped."""
from __future__ import annotations

import pytest

from codrag.services.pipeline.scheduler import (
    ComputeSlot,
    PipelineScheduler,
)


def _cloud_slot(node_id: str = "cloud:ep-test", seed: int = 5) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=seed,
        current_limit=seed,
        min_limit=3,
    )


def _local_slot(node_id: str = "local:ep-test", max_c: int = 1) -> ComputeSlot:
    return ComputeSlot(
        node_id=node_id,
        max_concurrent=max_c,
        min_limit=1,
    )


def test_cloud_dynamic_capacity_ignores_max_concurrent() -> None:
    slot = _cloud_slot()
    slot.current_limit = 40  # AIMD discovered a higher ceiling than the seed
    assert slot.dynamic_capacity == 40


def test_local_dynamic_capacity_still_clamps_at_max_concurrent() -> None:
    """Local slots have a real hardware ceiling (VRAM). Must still clamp."""
    slot = _local_slot(max_c=2)
    slot.current_limit = 10  # should be impossible but verify clamp
    assert slot.dynamic_capacity == 2


def test_cloud_aimd_doubling_past_max_concurrent(monkeypatch) -> None:
    """Cloud slot in jumpstart mode should double past its initial max_concurrent."""
    sched = PipelineScheduler()
    slot = _cloud_slot(seed=5)
    slot.mode = "jumpstart"
    sched._slots["cloud:ep-test"] = slot

    # Simulate 5 successful calls (batch_size = current_limit = 5) to trigger
    # a doubling step in jumpstart mode.
    for _ in range(5):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.current_limit == 10, (
        f"Expected doubling from 5→10, got current_limit={slot.current_limit}"
    )

    # Trigger another 10 successes — should double to 20 (uncapped).
    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=100.0)

    assert slot.current_limit == 20, (
        f"Expected second doubling to 20 (past original max_concurrent=5), "
        f"got current_limit={slot.current_limit}"
    )


def test_local_aimd_does_not_exceed_max_concurrent() -> None:
    """Local VRAM ceiling must be respected — no doubling past max_concurrent."""
    sched = PipelineScheduler()
    slot = _local_slot(max_c=1)
    slot.mode = "congestion_avoidance"
    sched._slots["local:ep-test"] = slot

    for _ in range(50):
        sched._record_throughput_for_slot(slot, queue_time_ms=10.0)

    assert slot.current_limit == 1, (
        f"Local slot exceeded VRAM ceiling: current_limit={slot.current_limit}"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py -v`
Expected: `test_cloud_dynamic_capacity_ignores_max_concurrent` and `test_cloud_aimd_doubling_past_max_concurrent` FAIL (both clipped at `max_concurrent=5`). `test_local_*` tests PASS.

- [ ] **Step 3: Modify `ComputeSlot.dynamic_capacity` and AIMD increase**

In `src/codrag/services/pipeline/scheduler.py`, find the `dynamic_capacity` property (around line 129–131):

```python
    @property
    def dynamic_capacity(self) -> int:
        return min(self.max_concurrent, self.current_limit)
```

Replace with:

```python
    @property
    def dynamic_capacity(self) -> int:
        """Phase 82: cloud slots discover their real ceiling at runtime;
        clipping by ``max_concurrent`` would defeat the discovery mechanism.
        Local slots keep the clamp — ``max_concurrent`` is a VRAM ceiling
        and a real hardware constraint.
        """
        if self.node_id.startswith("cloud:"):
            return max(1, self.current_limit)
        return min(self.max_concurrent, self.current_limit)
```

In the same file, find `_record_throughput_for_slot` (around line 476–492):

```python
        else:
            # Step 3: Additive Increase or Jumpstart (no congestion detected)
            slot.success_streak += 1

            batch_size = max(1, slot.current_limit)
            if slot.success_streak >= batch_size:
                slot.success_streak = 0
                if slot.current_limit < slot.max_concurrent:
                    if slot.mode == "jumpstart":
                        new_limit = min(slot.max_concurrent, slot.current_limit * 2)
                        logger.info(
                            "Scheduler: Node %s jumpstart %d -> %d",
                            slot.node_id, slot.current_limit, new_limit,
                        )
                        slot.current_limit = new_limit
                    else:
                        new_limit = min(slot.max_concurrent, slot.current_limit + 1)
                        slot.current_limit = new_limit
```

Replace with:

```python
        else:
            # Step 3: Additive Increase or Jumpstart (no congestion detected).
            # Phase 82 completion: cloud slots are unbounded — the ceiling is
            # discovered via congestion signals, not configured. Local slots
            # still respect max_concurrent (VRAM).
            slot.success_streak += 1

            is_cloud = slot.node_id.startswith("cloud:")
            batch_size = max(1, slot.current_limit)
            if slot.success_streak >= batch_size:
                slot.success_streak = 0
                allow_increase = is_cloud or slot.current_limit < slot.max_concurrent
                if allow_increase:
                    if slot.mode == "jumpstart":
                        new_limit = slot.current_limit * 2
                        if not is_cloud:
                            new_limit = min(slot.max_concurrent, new_limit)
                        logger.info(
                            "Scheduler: Node %s jumpstart %d -> %d",
                            slot.node_id, slot.current_limit, new_limit,
                        )
                        slot.current_limit = new_limit
                    else:
                        new_limit = slot.current_limit + 1
                        if not is_cloud:
                            new_limit = min(slot.max_concurrent, new_limit)
                        slot.current_limit = new_limit
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Run broader scheduler tests to catch regressions**

Run: `.venv/bin/pytest tests/ -k "scheduler" -v`
Expected: no new failures relative to Task 0 baseline.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_scheduler_unbounded_discovery.py
git commit -m "fix(phase82): uncap cloud AIMD discovery past max_concurrent

ComputeSlot.dynamic_capacity no longer clips cloud slots at the
user-configured cloud_concurrency value. AIMD additive increase and
jumpstart doubling can now raise current_limit above the initial
max_concurrent for cloud nodes. Local slots keep the VRAM clamp."
```

---

## Task 4: Scheduler — cloud slots seed at jumpstart (current_limit=5, mode=jumpstart)

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py:95-123`
- Modify: `tests/test_scheduler_unbounded_discovery.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scheduler_unbounded_discovery.py`:

```python
def test_new_cloud_slot_seeds_at_five_jumpstart() -> None:
    """Phase 82 spec: cloud slots seed at current_limit=5, mode=jumpstart."""
    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-new", max_concurrent=1)
    slot = sched._slots["cloud:ep-new"]
    assert slot.current_limit == 5
    assert slot.mode == "jumpstart"


def test_new_local_slot_keeps_max_concurrent_as_limit() -> None:
    """Local slots don't need discovery — VRAM ceiling is a hard known value."""
    sched = PipelineScheduler()
    sched.configure_node("local:ep-new", max_concurrent=2)
    slot = sched._slots["local:ep-new"]
    assert slot.current_limit == 2
    # Mode is irrelevant for non-discovery path but should default sanely.
    assert slot.mode in ("congestion_avoidance", "jumpstart")


def test_reconfigure_cloud_slot_preserves_discovered_limit() -> None:
    """Calling configure_node again on an existing cloud slot should NOT
    reset current_limit — the scheduler has already discovered a real
    ceiling and resetting to 5 would throw that away on a UI slider edit."""
    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-a", max_concurrent=1)
    slot = sched._slots["cloud:ep-a"]
    slot.current_limit = 40
    slot.mode = "congestion_avoidance"

    sched.configure_node("cloud:ep-a", max_concurrent=1)

    assert slot.current_limit == 40
    assert slot.mode == "congestion_avoidance"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py::test_new_cloud_slot_seeds_at_five_jumpstart -v`
Expected: FAIL. `slot.current_limit` is currently `max_concurrent` (1 or whatever was configured), not 5.

- [ ] **Step 3: Modify `ComputeSlot.__post_init__` and `PipelineScheduler.configure_node`**

In `src/codrag/services/pipeline/scheduler.py`, find `ComputeSlot.__post_init__` (around line 117):

```python
    def __post_init__(self):
        if self.current_limit <= 0 or self.current_limit > self.max_concurrent:
            self.current_limit = max(1, self.max_concurrent)
        if self.min_limit < 1:
            self.min_limit = 1
        if self.min_limit > self.max_concurrent:
            self.min_limit = self.max_concurrent
```

Replace with:

```python
    def __post_init__(self):
        # Phase 82: cloud slots seed at jumpstart=5 per the Latency-Aware
        # Discovery spec. Local slots seed at max_concurrent — the VRAM
        # ceiling is known a priori and doesn't need discovery.
        is_cloud = self.node_id.startswith("cloud:")
        if self.current_limit <= 0:
            self.current_limit = 5 if is_cloud else max(1, self.max_concurrent)
        elif not is_cloud and self.current_limit > self.max_concurrent:
            self.current_limit = max(1, self.max_concurrent)
        if is_cloud and self.mode not in ("jumpstart", "congestion_avoidance"):
            self.mode = "jumpstart"
        if self.min_limit < 1:
            self.min_limit = 1
        if self.min_limit > self.max_concurrent and not is_cloud:
            self.min_limit = self.max_concurrent
```

Find `configure_node` (search for `def configure_node`). It currently resets `current_limit` on every call — we need to preserve an already-discovered limit when the node exists. Locate the body and replace its reset logic with:

```python
    def configure_node(self, node_id: str, max_concurrent: int) -> None:
        """Create or update a compute slot.

        Phase 82: when reconfiguring an existing cloud slot, preserve the
        discovered ``current_limit`` and AIMD ``mode``. max_concurrent for
        cloud slots is used only as a starting seed for NEW slots — live
        discovery overrides it. For local slots, max_concurrent is the real
        hardware ceiling and is always enforced.
        """
        with self._lock:
            existing = self._slots.get(node_id)
            is_cloud = node_id.startswith("cloud:")
            if existing is not None:
                if is_cloud:
                    # Keep discovered current_limit and mode; update max only.
                    existing.max_concurrent = max(1, max_concurrent)
                else:
                    existing.max_concurrent = max(1, max_concurrent)
                    if existing.current_limit > existing.max_concurrent:
                        existing.current_limit = existing.max_concurrent
                return
            min_limit = 3 if is_cloud else 1
            slot = ComputeSlot(
                node_id=node_id,
                max_concurrent=max(1, max_concurrent),
                current_limit=5 if is_cloud else max(1, max_concurrent),
                min_limit=min_limit,
                mode="jumpstart" if is_cloud else "congestion_avoidance",
            )
            self._slots[node_id] = slot
```

> If `configure_node` already exists with different signature/semantics, leave any unchanged call sites intact — the ONLY change is preserving `current_limit`/`mode` on existing cloud slots and using the cloud seed for new ones.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Run broader suite for regressions**

Run: `.venv/bin/pytest tests/ -k "scheduler or pipeline" -v 2>&1 | tail -40`
Expected: no new failures relative to Task 0 baseline.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_scheduler_unbounded_discovery.py
git commit -m "feat(phase82): seed cloud slots at jumpstart=5, preserve discovered limit

New cloud slots initialize with current_limit=5 and mode=jumpstart per
Phase 82 spec. Reconfiguring an existing cloud slot (e.g. user edits
the UI slider — now legacy) preserves the AIMD-discovered current_limit
and mode. Local slots unchanged (VRAM is a real hardware ceiling)."
```

---

## Task 5: Scheduler — wire ConcurrencyStore into AIMD load/save

**Files:**
- Modify: `src/codrag/services/pipeline/scheduler.py` (new import + hooks)
- Modify: `tests/test_scheduler_unbounded_discovery.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scheduler_unbounded_discovery.py`:

```python
def test_new_cloud_slot_hydrates_from_store(monkeypatch, tmp_path) -> None:
    """configure_node reads the persisted ceiling and uses it as current_limit."""
    from codrag.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from codrag.services.pipeline import concurrency_store as mod
    mod._store = None

    # Persist a ceiling BEFORE creating the slot.
    store = mod.concurrency_store()
    store.save("cloud:ep-persisted", "__default__", ceiling=40)

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-persisted", max_concurrent=1)
    slot = sched._slots["cloud:ep-persisted"]

    assert slot.current_limit == 40, (
        f"Expected hydrated ceiling=40, got current_limit={slot.current_limit}"
    )
    # Mode/streak NOT persisted — starts fresh in jumpstart.
    assert slot.mode == "jumpstart"
    assert slot.success_streak == 0


def test_aimd_backoff_writes_new_ceiling(monkeypatch, tmp_path) -> None:
    from codrag.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from codrag.services.pipeline import concurrency_store as mod
    mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-backoff", max_concurrent=1)
    slot = sched._slots["cloud:ep-backoff"]
    slot.current_limit = 80
    slot.mode = "congestion_avoidance"

    # Trigger a backoff (queue_time_ms > 2000).
    sched._record_throughput_for_slot(slot, queue_time_ms=5000.0)

    persisted = mod.concurrency_store().load("cloud:ep-backoff", "__default__")
    assert persisted is not None and persisted < 80, (
        f"Expected backoff to persist a reduced ceiling, got {persisted}"
    )
    assert persisted == slot.current_limit


def test_aimd_doubling_writes_new_ceiling(monkeypatch, tmp_path) -> None:
    from codrag.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from codrag.services.pipeline import concurrency_store as mod
    mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("cloud:ep-grow", max_concurrent=1)
    slot = sched._slots["cloud:ep-grow"]

    # Force a jumpstart doubling step.
    for _ in range(5):
        sched._record_throughput_for_slot(slot, queue_time_ms=50.0)

    persisted = mod.concurrency_store().load("cloud:ep-grow", "__default__")
    assert persisted == 10, (
        f"Expected jumpstart doubling (5→10) to persist ceiling=10, got {persisted}"
    )


def test_local_slot_does_not_persist(monkeypatch, tmp_path) -> None:
    """Local slots have a known hardware ceiling — no discovery, no persist."""
    from codrag.core import paths as paths_mod
    monkeypatch.setattr(paths_mod, "data_dir", lambda: tmp_path)
    from codrag.services.pipeline import concurrency_store as mod
    mod._store = None

    sched = PipelineScheduler()
    sched.configure_node("local:ep-gpu", max_concurrent=2)
    slot = sched._slots["local:ep-gpu"]

    for _ in range(10):
        sched._record_throughput_for_slot(slot, queue_time_ms=50.0)
    sched._record_throughput_for_slot(slot, queue_time_ms=5000.0)

    persisted = mod.concurrency_store().load("local:ep-gpu", "__default__")
    assert persisted is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py -k "store or persist or hydrate or writes" -v`
Expected: the 4 new tests FAIL (no persistence wired yet).

- [ ] **Step 3: Wire persistence into scheduler**

At the top of `src/codrag/services/pipeline/scheduler.py`, add to existing imports:

```python
from codrag.services.pipeline.concurrency_store import concurrency_store
```

Modify `configure_node` to hydrate from the store when creating a NEW cloud slot (in Task 4's replacement, inside the `existing is None` branch, before constructing `slot`):

```python
            min_limit = 3 if is_cloud else 1
            seed = 5 if is_cloud else max(1, max_concurrent)
            mode = "jumpstart" if is_cloud else "congestion_avoidance"
            if is_cloud:
                persisted = concurrency_store().load(node_id, "__default__")
                if persisted is not None:
                    seed = persisted
                    mode = "congestion_avoidance"
            slot = ComputeSlot(
                node_id=node_id,
                max_concurrent=max(1, max_concurrent),
                current_limit=seed,
                min_limit=min_limit,
                mode=mode,
            )
            self._slots[node_id] = slot
```

Modify `_record_throughput_for_slot` to save after backoff or doubling. Find the backoff branch (after `slot.current_limit = new_limit`, around line 470):

```python
                if slot.current_limit > new_limit:
                    logger.warning(...)
                    slot.current_limit = new_limit
                slot._last_backoff_time = now
                slot._last_recovery_time = now
```

Add after the `slot._last_recovery_time = now` line:

```python
                if slot.node_id.startswith("cloud:"):
                    try:
                        concurrency_store().save(
                            slot.node_id, "__default__", ceiling=slot.current_limit,
                        )
                    except Exception as exc:  # pragma: no cover — persistence is best-effort
                        logger.debug(
                            "concurrency_store.save failed for %s: %s",
                            slot.node_id, exc,
                        )
```

Also add persistence inside the additive-increase branch after `slot.current_limit = new_limit` (both jumpstart and congestion-avoidance subpaths). Factor this into a helper to keep it DRY — inside the class add:

```python
    def _persist_cloud_ceiling(self, slot: ComputeSlot) -> None:
        if not slot.node_id.startswith("cloud:"):
            return
        try:
            concurrency_store().save(
                slot.node_id, "__default__", ceiling=slot.current_limit,
            )
        except Exception as exc:  # pragma: no cover — persistence is best-effort
            logger.debug(
                "concurrency_store.save failed for %s: %s",
                slot.node_id, exc,
            )
```

Replace the inline `try/except` from the backoff branch with `self._persist_cloud_ceiling(slot)`, and add the same call after each of the two `slot.current_limit = new_limit` lines inside the `else` (no-congestion) branch.

> "__default__" model_family is a forward-looking placeholder. A future task can split per-model if Qwen-Coder and Gemini-Flash need distinct ceilings for the same endpoint.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scheduler_unbounded_discovery.py -v`
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline/scheduler.py tests/test_scheduler_unbounded_discovery.py
git commit -m "feat(phase82): persist AIMD ceilings across daemon restart

configure_node hydrates cloud slots from ConcurrencyStore. Backoff
and additive-increase paths write the new ceiling back to the store.
Local slots opt out (no discovery needed). Mode/streak deliberately
not persisted — those are hot-loop state with no restart meaning."
```

---

## Task 6: Remove the cloud early-return in batch_profiles.get_batch_concurrency

**Files:**
- Modify: `src/codrag/core/batch_profiles.py:390-410`
- Create: `tests/test_batch_profiles_no_plan_tier.py`

- [ ] **Step 1: Write the failing regression test**

Create `tests/test_batch_profiles_no_plan_tier.py`:

```python
"""Phase 82 completion: cloud dispatch must go through the scheduler,
not short-circuit on a hardcoded plan-tier value.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from codrag.core import batch_profiles


def test_cloud_dispatch_does_not_return_plan_tier_constant() -> None:
    """Before fix: cloud dispatch returned PLAN_TIER_CONCURRENCY['free'] = 1.
    After fix: it routes through the scheduler and returns the discovered
    dynamic capacity.
    """
    from codrag.services.pipeline.scheduler import pipeline_scheduler

    pipeline_scheduler.configure_node("cloud:ep-test-unbounded", max_concurrent=1)
    slot = pipeline_scheduler._slots["cloud:ep-test-unbounded"]
    slot.current_limit = 40  # simulate post-discovery

    with patch.object(
        batch_profiles, "_LOCAL_PROVIDERS", set()
    ):  # force cloud classification
        concurrency = batch_profiles.get_batch_concurrency(
            provider="ollama",
            model="qwen3-coder",
            node_id="cloud:ep-test-unbounded",
        )

    assert concurrency > 1, (
        f"Cloud dispatch should reflect scheduler's discovered ceiling, "
        f"got {concurrency}. This means the PLAN_TIER early-return is still "
        f"clipping discovery at the free-tier hardcode."
    )


def test_plan_tier_helpers_are_removed() -> None:
    """The plan-tier helper fns are gone — no fallbacks, no ambiguity."""
    assert not hasattr(batch_profiles, "_get_plan_tier")
    assert not hasattr(batch_profiles, "_resolve_plan_tier_concurrency")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_batch_profiles_no_plan_tier.py -v`
Expected: both FAIL — the early-return still clips to 1, and the helpers still exist.

- [ ] **Step 3: Delete the early-return and helpers in `batch_profiles.py`**

In `src/codrag/core/batch_profiles.py`, delete lines 26–66 (`_get_plan_tier()` and `_resolve_plan_tier_concurrency()`).

Then delete lines 393–408 (the cloud early-return block). It reads:

```python
    # Cloud models: use Ollama Cloud plan tier to cap concurrency.
    # F-59 root cause (daemon hang from timeout misconfiguration) was
    # resolved on 2026-04-12 — see docs/Phase79_Swarm/07_Rework/
    # SWARM_HANG_INVESTIGATION.md.  Concurrent cloud requests now work
    # end-to-end inside the daemon; the real limit is the plan tier.
    _is_cloud = provider_lower not in _LOCAL_PROVIDERS
    if not _is_cloud and model:
        _is_cloud = is_cloud_model_via_ollama(provider_lower, model or "")
    if _is_cloud:
        tier = _get_plan_tier()
        plan_concurrency = _resolve_plan_tier_concurrency()
        logger.info(
            "Batch concurrency: %d (plan tier=%s, provider=%s, model=%s)",
            plan_concurrency, tier, provider_lower, model,
        )
        return plan_concurrency
```

Replace that entire block with a simple comment noting the change:

```python
    # Phase 82 completion: cloud dispatch no longer short-circuits on a
    # hardcoded plan-tier value. Both cloud and local go through the
    # scheduler, which discovers the real ceiling via AIMD for cloud and
    # uses the VRAM-bounded max_concurrent for local. See
    # docs/Phase82_CloudPipelineConcurrency/05_Completion_Plan.md.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_batch_profiles_no_plan_tier.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run full batch_profiles-adjacent suite**

Run: `.venv/bin/pytest tests/ -k "batch or concurrency or scheduler" -v 2>&1 | tail -30`
Expected: no new failures relative to Task 0 baseline. Tests that explicitly relied on `PLAN_TIER_CONCURRENCY` or the plan-tier helpers will need cleanup in Task 7.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/batch_profiles.py tests/test_batch_profiles_no_plan_tier.py
git commit -m "fix(phase82): remove plan-tier early-return from batch dispatch

Cloud batch dispatch now goes through the scheduler (same path as
local), so AIMD-discovered concurrency actually reaches the pipeline
instead of being clipped to the 'free'-tier hardcode of 1. Deletes
_get_plan_tier() and _resolve_plan_tier_concurrency() — no callers
remain after this commit (verified in task 7)."
```

---

## Task 7: Delete PLAN_TIER_CONCURRENCY dict + PlanTier literal + all call sites

**Files:**
- Modify: `src/codrag/core/swarm_optimizer.py`
- Modify: any other file grep finds referencing `PLAN_TIER_CONCURRENCY` or `PlanTier` or `_resolve_plan_tier_concurrency` or `_get_plan_tier`
- Modify: tests referencing these

- [ ] **Step 1: Enumerate every remaining reference**

Run these in parallel:

```bash
.venv/bin/python -m grep -rn "PLAN_TIER_CONCURRENCY" src/ tests/ packages/ 2>/dev/null
.venv/bin/python -m grep -rn "_resolve_plan_tier_concurrency" src/ tests/ 2>/dev/null
.venv/bin/python -m grep -rn "_get_plan_tier" src/ tests/ 2>/dev/null
.venv/bin/python -m grep -rn '"ollama_plan_tier"' src/ tests/ packages/ 2>/dev/null
```

> Use the Grep tool if running under an agent. Record every hit — each hit is a deletion target or a test that needs to be rewritten.

- [ ] **Step 2: Delete `PLAN_TIER_CONCURRENCY` and `PlanTier` from `swarm_optimizer.py`**

In `src/codrag/core/swarm_optimizer.py`, find and delete:

```python
PlanTier = Literal["free", "pro", "max"]

PLAN_TIER_CONCURRENCY: Dict[PlanTier, int] = {
    "free": 1,
    "pro": 3,
    "max": 10,
}
```

(Lines may differ slightly; remove the dict, the Literal, and any `Dict`/`Literal` imports that are no longer used.)

- [ ] **Step 3: Update or delete tests that exercised the plan-tier code path**

For each test file that hits the grep, either:
- **Delete** the test if its sole purpose was asserting plan-tier mapping (those are testing behavior that no longer exists).
- **Rewrite** the test to assert the new scheduler-routed behavior if it was testing a broader integration.

Document each test touched in the commit message.

- [ ] **Step 4: Run affected tests to verify they pass**

Run: `.venv/bin/pytest tests/ -v 2>&1 | tail -40`
Expected: no references to deleted names remain. Any broken tests from this deletion have been rewritten or removed.

- [ ] **Step 5: Re-grep for stragglers**

Run the same four grep commands from Step 1. Expected: zero hits in `src/`.

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "chore(phase82): delete PLAN_TIER_CONCURRENCY and PlanTier literal

Removes the hardcoded {free: 1, pro: 3, max: 10} dict that Phase 112
reintroduced against the Phase 82 design. Also removes the PlanTier
Literal type and all test cases that were testing the old mapping
behavior directly. See the Phase 82 completion plan for rationale."
```

---

## Task 8: Remove `ollama_plan_tier` + `custom_concurrency` from server.py advanced settings defaults

**Files:**
- Modify: `src/codrag/server.py:502-518` (function `get_advanced_llm_settings`)

- [ ] **Step 1: Read current function**

Run: `.venv/bin/python -c "from codrag.server import get_advanced_llm_settings; import json; print(json.dumps(get_advanced_llm_settings(), indent=2))"`
Expected: dict includes `ollama_plan_tier` and `custom_concurrency` keys — those are what we're removing.

- [ ] **Step 2: Locate and edit the function**

In `src/codrag/server.py`, find `get_advanced_llm_settings()` (around line 502). Remove the two defaults from the returned dict:

- Delete any line containing `"ollama_plan_tier"`.
- Delete any line containing `"custom_concurrency"`.

Keep `enforce_cloud_token_safety` and `max_thinking_budget` — those are unrelated to concurrency.

If the function also accepts writes (or there's a setter `set_advanced_llm_settings`), ensure the schema/validation there no longer rejects payloads that omit these keys, and that writes passing these keys are silently ignored (for clients that haven't yet updated).

- [ ] **Step 3: Write/update a test**

Add to `tests/test_batch_profiles_no_plan_tier.py`:

```python
def test_server_settings_no_longer_include_plan_tier() -> None:
    """The advanced-LLM settings API no longer exposes plan-tier fields."""
    from codrag.server import get_advanced_llm_settings

    settings = get_advanced_llm_settings()
    assert "ollama_plan_tier" not in settings
    assert "custom_concurrency" not in settings
```

- [ ] **Step 4: Run tests to verify**

Run: `.venv/bin/pytest tests/test_batch_profiles_no_plan_tier.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/server.py tests/test_batch_profiles_no_plan_tier.py
git commit -m "fix(phase82): remove ollama_plan_tier/custom_concurrency from settings

These plan-tier UI knobs were coupled to the hardcoded concurrency
dispatch deleted in the previous commits. The AI Gateway UI will be
updated in task 11 to drop the corresponding controls."
```

---

## Task 9: AI Gateway — rewire `_build_llm_slots_sync` to show LIVE in-flight count

**Files:**
- Modify: `src/codrag/api/routers/llm.py:626-673`
- Create: `tests/test_ai_gateway_live_count.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai_gateway_live_count.py`:

```python
"""Phase 82 completion: the AI Gateway UI displays LIVE in-flight
API call count, not the scheduler's configured maximum.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_running_tasks_use_live_telemetry_count(monkeypatch) -> None:
    """When 3 LLM requests are in-flight for a project + model_slot,
    the running_tasks list should report concurrent_workers=3, not
    the scheduler's max."""
    from codrag.services import token_telemetry

    fake_requests = [
        {
            "project_id": "proj-A",
            "task_id": "inferred_edges",
            "model": "qwen3-coder",
            "provider": "ollama",
            "model_slot": "large_model",
            "duration_seconds": 1.2,
        },
        {
            "project_id": "proj-A",
            "task_id": "inferred_edges",
            "model": "qwen3-coder",
            "provider": "ollama",
            "model_slot": "large_model",
            "duration_seconds": 0.8,
        },
        {
            "project_id": "proj-A",
            "task_id": "inferred_edges",
            "model": "qwen3-coder",
            "provider": "ollama",
            "model_slot": "large_model",
            "duration_seconds": 0.3,
        },
    ]
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests", lambda: list(fake_requests),
    )

    from codrag.api.routers.llm import _count_live_workers

    count = _count_live_workers(
        project_id="proj-A", task_id="inferred_edges", model_slot="large_model",
    )
    assert count == 3


def test_running_tasks_live_count_zero_when_nothing_inflight(monkeypatch) -> None:
    from codrag.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests", lambda: [],
    )
    from codrag.api.routers.llm import _count_live_workers
    assert _count_live_workers(
        project_id="proj-A", task_id="inferred_edges", model_slot="large_model",
    ) == 0


def test_agent_task_workers_reflect_live_count(monkeypatch) -> None:
    """Previously hardcoded to 1; now from telemetry count."""
    from codrag.services import token_telemetry
    monkeypatch.setattr(
        token_telemetry.telemetry, "get_active_requests",
        lambda: [
            {
                "project_id": "proj-A",
                "task_id": "agent_call",
                "model": "gemini-2.5-flash",
                "provider": "gemini",
                "model_slot": "large_model",
                "duration_seconds": 0.1,
            },
            {
                "project_id": "proj-A",
                "task_id": "agent_call",
                "model": "gemini-2.5-flash",
                "provider": "gemini",
                "model_slot": "large_model",
                "duration_seconds": 0.2,
            },
        ],
    )
    from codrag.api.routers.llm import _count_live_workers
    assert _count_live_workers(
        project_id="proj-A", task_id="agent_call", model_slot="large_model",
    ) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ai_gateway_live_count.py -v`
Expected: FAIL with `ImportError: cannot import name '_count_live_workers' from codrag.api.routers.llm`.

- [ ] **Step 3: Add the helper and rewire call sites in `llm.py`**

Near the top of `src/codrag/api/routers/llm.py` (above `_build_llm_slots_sync`), add:

```python
def _count_live_workers(*, project_id: str, task_id: str, model_slot: str) -> int:
    """Count in-flight LLM requests matching (project_id, task_id, model_slot).

    Phase 82 completion: the AI Gateway UI now reflects actual API call
    concurrency, not the scheduler's configured maximum. The scheduler
    has adaptive discovery and can run above or below its configured
    cloud_concurrency, so a static read is misleading. Live telemetry is
    authoritative.
    """
    from codrag.services.token_telemetry import telemetry

    count = 0
    for req in telemetry.get_active_requests():
        if req.get("project_id") != project_id:
            continue
        if task_id and req.get("task_id") != task_id:
            # For agent-path tasks the task_id may differ — accept any match
            # on model_slot below.
            if req.get("model_slot") != model_slot:
                continue
        if req.get("model_slot") != model_slot:
            continue
        count += 1
    return count
```

Then modify lines 626–646 (pipeline running tasks enrichment):

```python
        # Enrich running tasks with concurrent worker count from scheduler
        try:
            from codrag.services.pipeline.scheduler import (
                pipeline_scheduler, SWARM_CAPABLE_STAGES, is_swarm_active_for_stage,
            )
            from codrag.services.pipeline._model_resolution import resolve_model_for_stage
            for rt in running_tasks:
                workers, node_id = pipeline_scheduler.concurrent_workers_for_project(
                    rt["project_id"], stage=rt.get("stage"),
                )
                rt["concurrent_workers"] = workers
                rt["compute_node"] = node_id
                ...
```

Replace the `rt["concurrent_workers"] = workers` line with live telemetry:

```python
        try:
            from codrag.services.pipeline.scheduler import (
                pipeline_scheduler, SWARM_CAPABLE_STAGES, is_swarm_active_for_stage,
            )
            from codrag.services.pipeline._model_resolution import resolve_model_for_stage
            for rt in running_tasks:
                _scheduler_max, node_id = pipeline_scheduler.concurrent_workers_for_project(
                    rt["project_id"], stage=rt.get("stage"),
                )
                live_workers = _count_live_workers(
                    project_id=rt["project_id"],
                    task_id=rt.get("task_id", ""),
                    model_slot=rt.get("model_slot", "large_model"),
                )
                rt["concurrent_workers"] = live_workers
                rt["scheduler_capacity"] = _scheduler_max  # for debugging/observability
                rt["compute_node"] = node_id
                # Phase 82: Model-aware swarm flag
                rt["is_swarm"] = False
                stage = rt.get("stage", "")
                if stage in SWARM_CAPABLE_STAGES:
                    resolved = resolve_model_for_stage(rt["project_id"], stage)
                    if resolved:
                        rt["is_swarm"] = is_swarm_active_for_stage(stage, *resolved)
        except Exception:
            pass  # Scheduler not available — leave defaults
```

At lines 661–671 (telemetry-derived agent tasks), replace the hardcoded `"concurrent_workers": 1`:

```python
            running_tasks.append({
                "task_id": req["task_id"] or "agent_call",
                "project_id": req["project_id"],
                "project_name": proj_name,
                "group": "agent_ops",
                "stage": req["task_id"],
                "model_slot": req["model_slot"] or "large_model",
                "concurrent_workers": _count_live_workers(
                    project_id=req["project_id"],
                    task_id=req["task_id"] or "agent_call",
                    model_slot=req["model_slot"] or "large_model",
                ),
                "compute_node": "local",
                "is_swarm": False,
            })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ai_gateway_live_count.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Run LLM-router-adjacent suite**

Run: `.venv/bin/pytest tests/ -k "llm or gateway or telemetry" -v 2>&1 | tail -30`
Expected: no new failures relative to Task 0 baseline.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/api/routers/llm.py tests/test_ai_gateway_live_count.py
git commit -m "fix(phase82): AI Gateway shows live in-flight count, not config max

_build_llm_slots_sync no longer reports the scheduler's configured
max_concurrent as 'concurrent_workers'. It now counts actual
in-flight requests from token_telemetry._active_requests, grouped by
(project_id, task_id, model_slot). Agent-path tasks also reflect
live counts instead of the old hardcoded '1'. The scheduler capacity
is kept in a parallel field (scheduler_capacity) for debugging."
```

---

## Task 10: UI — remove plan-tier selector + custom-concurrency slider

**Files:**
- Modify: `packages/ui/src/components/settings/AdvancedLLMSettings.tsx`
- Modify: any test for AdvancedLLMSettings (if present)

- [ ] **Step 1: Locate controls**

Run (Grep tool): search `packages/ui/src/components/settings/` for `ollama_plan_tier` and `custom_concurrency`. Record every line number.

Also Grep for any dashboard-side usage (`src/codrag/dashboard/`) to confirm no consumer still reads these fields.

- [ ] **Step 2: Delete the controls**

In `AdvancedLLMSettings.tsx`:
- Remove the plan-tier `<Select>` (or equivalent) that sets `ollama_plan_tier`.
- Remove the custom-concurrency numeric input bound to `custom_concurrency`.
- Remove any associated labels, help text, and state (`useState` / context) for these fields.
- Remove any payload fields on save handlers that serialize these keys.

If there's a settings type (e.g. `AdvancedLLMSettings.types.ts`), delete the `ollama_plan_tier` and `custom_concurrency` field declarations.

- [ ] **Step 3: Verify no consumer crashes**

Run (Bash):

```bash
cd packages/ui && npm run typecheck 2>&1 | tail -30
cd packages/ui && npm run lint 2>&1 | tail -30
```

Expected: clean. Any TypeScript error here means a consumer still reads the removed field — delete that consumer line too.

- [ ] **Step 4: Smoke test — run dashboard, confirm controls are gone**

Run: `scripts/dev.sh` (in a separate terminal). Open `http://localhost:5174`, navigate to Settings → Advanced LLM. Confirm:
- No plan-tier dropdown.
- No custom-concurrency slider.
- The pane still renders and saves without error.

If you can't run a browser (agentic execution), skip to Step 5 but flag the manual verification as pending in the commit message.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/settings/AdvancedLLMSettings.tsx \
        packages/ui/src/components/settings/AdvancedLLMSettings.types.ts 2>/dev/null || true
git add -u packages/ui/
git commit -m "feat(phase82-ui): remove plan-tier selector + custom-concurrency slider

Cloud concurrency is discovered at runtime (see Phase 82 completion
plan); a user-facing selector for free/pro/max was the symptom of the
now-removed hardcoded dispatch path. Local concurrency (VRAM) retains
its slider because it's a real hardware ceiling."
```

---

## Task 11: Integration verification — end-to-end run with real pipeline

**Files:** (read-only validation)

- [ ] **Step 1: Start the daemon fresh**

```bash
.venv/bin/codrag serve &
sleep 5
```

- [ ] **Step 2: Confirm scheduler initialized at jumpstart**

```bash
curl -s http://localhost:8400/compute/scheduler | python -m json.tool | grep -A 5 cloud
```

Expected: each cloud slot shows `"mode": "jumpstart"` and `"current_limit": 5` (or hydrated value from a prior run).

- [ ] **Step 3: Trigger a pipeline build on a small test project**

Pick a small project from the registry and kick off a swarm-enabled stage (`inferred_edges` or `epistemic_code`):

```bash
curl -X POST http://localhost:8400/api/pipeline/<project_id>/run-stage \
  -H "Content-Type: application/json" \
  -d '{"stage": "inferred_edges"}'
```

Watch daemon logs for lines like `Scheduler: Node cloud:ep-* jumpstart 5 -> 10`. Expected: the limit grows as the batch runs.

- [ ] **Step 4: Open the dashboard and confirm UI reflects live counts**

Open `http://localhost:5174`. Watch the AI Gateway sidebar. Confirm:
- "N active" reflects the actual number of in-flight LLM calls (should be ≤ `dynamic_capacity`).
- "X× Thinking" badge on the task matches actual parallelism — not a static 10.
- When a burst triggers backoff (logs will show `Scheduler: Node ... congested`), the UI count drops correspondingly.

- [ ] **Step 5: Restart daemon, confirm ceiling persists**

```bash
pkill -f "codrag serve"
sleep 3
.venv/bin/codrag serve &
sleep 5
curl -s http://localhost:8400/compute/scheduler | python -m json.tool | grep -A 5 cloud
```

Expected: `current_limit` is the ceiling discovered in Step 3, NOT 5 (unless Step 3 never got past jumpstart).

- [ ] **Step 6: Confirm ConcurrencyStore DB exists and has rows**

```bash
.venv/bin/python -c "
from codrag.core.paths import data_dir
import sqlite3
p = data_dir() / 'concurrency_store.db'
print('DB path:', p, 'exists:', p.exists())
conn = sqlite3.connect(p)
for row in conn.execute('SELECT node_id, model_family, ceiling, updated_at FROM discovered_ceilings'):
    print(row)
"
```

Expected: at least one row for `cloud:*` node with a ceiling ≥ 5.

- [ ] **Step 7: No commit — this is verification only.**

If anything failed here, return to the appropriate earlier task and fix before proceeding.

---

## Task 12: Update Phase 82 design docs with completion note

**Files:**
- Modify: `docs/Phase82_CloudPipelineConcurrency/01_Latency_Aware_Discovery.md`
- Modify: `docs/Phase82_CloudPipelineConcurrency/03_Implementation_Plan.md`

- [ ] **Step 1: Add a completion banner to 01_Latency_Aware_Discovery.md**

At the very top of the file (before the existing content), insert:

```markdown
> **Completed 2026-04-18** — See `05_Completion_Plan.md` for the final
> delta. Phase 112 briefly regressed this design by reintroducing a
> hardcoded `PLAN_TIER_CONCURRENCY` dict and early-return in
> `batch_profiles.get_batch_concurrency()`; both have been removed.
> Cloud slots now seed at jumpstart=5, discover their real ceiling via
> AIMD, and persist it across daemon restart via `ConcurrencyStore`.
> The AI Gateway UI reflects live in-flight counts instead of the
> scheduler's configured maximum.

---
```

- [ ] **Step 2: Mark 03_Implementation_Plan.md as superseded**

At the top of `03_Implementation_Plan.md`, insert:

```markdown
> **Superseded 2026-04-18** by `05_Completion_Plan.md`, which finishes
> the unbounded-discovery work that this plan scoped partially.

---
```

- [ ] **Step 3: Commit**

```bash
git add docs/Phase82_CloudPipelineConcurrency/
git commit -m "docs(phase82): mark Phase 82 complete; link to 05_Completion_Plan

Phase 82 unbounded latency-aware discovery is fully wired end-to-end
after the completion plan. Documents get a banner pointing at the
final delta so future readers land on the right file."
```

---

## Self-Review Checklist

After execution:

1. **Spec coverage:** Every failure mode in the current system is fixed by a task?
   - Hardcoded `PLAN_TIER_CONCURRENCY` dict — Task 7 ✓
   - Cloud early-return in `batch_profiles` — Task 6 ✓
   - Scheduler caps cloud AIMD at `max_concurrent` — Task 3 ✓
   - Cloud slot seeds at wrong value — Task 4 ✓
   - No persistence across restart — Tasks 1+2+5 ✓
   - AI Gateway shows config max, not live — Task 9 ✓
   - UI plan-tier selector — Task 10 ✓
   - Settings API still advertises plan-tier fields — Task 8 ✓
   - Docs don't reflect the completion — Task 12 ✓

2. **Placeholder scan:** No TBD, TODO, "add appropriate handling", or vague "similar to Task N" refs in the plan.

3. **Type consistency:** `ConcurrencyStore` API matches across tasks (load/save/clear with keyword `ceiling`, `__default__` family placeholder, `concurrency_store()` accessor).

4. **No new unused code:** Helper `_count_live_workers` and `_persist_cloud_ceiling` are both used in ≥2 spots.

---

## Execution Handoff

Plan complete and saved to `docs/Phase82_CloudPipelineConcurrency/05_Completion_Plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

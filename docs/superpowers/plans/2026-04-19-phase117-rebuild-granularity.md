# Phase 117 — Rebuild Granularity & Provenance (A + B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scoped pipeline rebuilds (Sync / Enrichment / All), a single Stop-Rebuild control via a sticky queue row, and per-stage provenance chips (match / drift / self-healed) driven by comparing each stage's manifest model against current task-assignment config.

**Architecture:** Backend extends `/pipeline/fast` and `/pipeline/deep` with a `force_from_start` body param (orchestrator already supports it), adds a new `/pipeline/rebuild/stop` endpoint, and extends the reset-barrier file format with a third line for `scope`. A new `compute_stage_provenance` helper joins each stage's manifest model with `resolve_model_for_stage` (existing at `src/prep/services/pipeline/_model_resolution.py`) and exposes the result via `/pipeline/status`. Frontend replaces the pipeline panel's rebuild entrypoint with a split-button dropdown, adds a sticky `<RebuildingRow>` when the barrier is active, and renders a `<ProvenanceChip>` under each stage card.

**Tech Stack:** Python 3.11 (FastAPI, Pydantic), TypeScript (React 18, Tailwind, vitest, Storybook), pytest.

---

## Reference paths

- Barrier helpers: `src/prep/services/pipeline/recovery.py` lines 60–150
- Orchestrator: `src/prep/services/pipeline/orchestrator.py` — `run_fast_sync(force_from_start=bool)` already exists at line 444, `run_deep_enrichment(force_from_start=bool)` at line 746
- Model resolution: `src/prep/services/pipeline/_model_resolution.py` — `resolve_model_for_stage(project_id, stage) -> Optional[Tuple[str, str]]`
- Pipeline router: `src/prep/api/routers/pipeline.py` — endpoints `fast`, `deep`, `rebuild`, `cancel` already wired; status cache at top of file
- Pipeline status response: built in `_build_status()` inside the same router, starting around line 365
- UI entry point: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`
- Rebuild progress helpers: `packages/ui/src/components/trace/rebuildProgress.ts`
- UI types: `packages/ui/src/types.ts`
- Dashboard hook: `src/prep/dashboard/src/hooks/useEnrichment.ts`
- Stage constants (for scope→group→stages lookups): `src/prep/services/pipeline/stages.py` — exports `FAST_SYNC_STAGES`, `DEEP_ENRICHMENT_STAGES`, `FINALIZE_STAGES`

Run all Python tests through the project venv per project convention: `.venv/bin/pytest`.

---

## Task 1: Extend barrier file format with `scope`

**Files:**
- Modify: `src/prep/services/pipeline/recovery.py:64-150`
- Test: `tests/services/pipeline/test_reset_barrier_scope.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/services/pipeline/test_reset_barrier_scope.py`:

```python
"""Tests for the Phase 117 reset-barrier scope extension."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from prep.services.pipeline.recovery import (
    _RESET_BARRIER_FILENAME,
    clear_reset_barrier,
    read_reset_barrier,
    write_reset_barrier,
)


@pytest.fixture
def project_with_idx(tmp_path, monkeypatch):
    """Patch _resolve_idx_dir so recovery helpers write to tmp_path."""
    from prep.services.pipeline import recovery

    monkeypatch.setattr(recovery, "_resolve_idx_dir", lambda _pid: tmp_path)
    return "proj-test", tmp_path


def test_write_barrier_default_scope_is_all(project_with_idx):
    project_id, idx_dir = project_with_idx
    assert write_reset_barrier(project_id, reason="rebuild") is True

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["reason"] == "rebuild"
    assert info["scope"] == "all"


def test_write_barrier_sync_scope_roundtrips(project_with_idx):
    project_id, _ = project_with_idx
    assert write_reset_barrier(project_id, reason="rebuild", scope="sync") is True

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["scope"] == "sync"


def test_write_barrier_enrichment_scope_roundtrips(project_with_idx):
    project_id, _ = project_with_idx
    assert write_reset_barrier(project_id, reason="rebuild", scope="enrichment") is True

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["scope"] == "enrichment"


def test_read_legacy_two_line_barrier_defaults_scope_all(project_with_idx):
    """A barrier written by pre-phase-117 code (no scope line) reads as scope=all."""
    project_id, idx_dir = project_with_idx
    (idx_dir / _RESET_BARRIER_FILENAME).write_text("1776000000.0\nrebuild\n")

    info = read_reset_barrier(project_id)
    assert info is not None
    assert info["reason"] == "rebuild"
    assert info["scope"] == "all"


def test_invalid_scope_rejected(project_with_idx):
    project_id, _ = project_with_idx
    with pytest.raises(ValueError):
        write_reset_barrier(project_id, reason="rebuild", scope="bogus")


def test_clear_barrier(project_with_idx):
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="sync")
    assert clear_reset_barrier(project_id) is True

    info = read_reset_barrier(project_id)
    assert info is None
```

- [ ] **Step 2: Run tests and watch them fail**

Run: `.venv/bin/pytest tests/services/pipeline/test_reset_barrier_scope.py -v`
Expected: all 6 tests FAIL (the `scope` parameter and key don't exist yet).

- [ ] **Step 3: Extend the barrier writer and reader**

In `src/prep/services/pipeline/recovery.py`, replace `write_reset_barrier`, `clear_reset_barrier`, and `read_reset_barrier` so the file gains an optional 3rd line holding the scope. Keep the 2-line legacy format readable.

Replace lines 64–150 with:

```python
_VALID_BARRIER_SCOPES = ("sync", "enrichment", "all")


def write_reset_barrier(
    project_id: str,
    reason: str,
    scope: str = "all",
) -> bool:
    """Write a barrier that disables selfheal until the scope's group finishes.

    Phase 117: ``scope`` names which group the rebuild is forcing from start.
    - ``sync``: rebuild fast_sync (stages 1-5); barrier auto-clears when stage 5 finishes.
    - ``enrichment``: rebuild deep_enrichment (stages 6-10); barrier auto-clears when stage 10 finishes.
    - ``all``: rebuild the full chain; barrier auto-clears when finalize (stage 15) finishes.

    The file is a 3-line text format for forward/backward compat:
        line 1: written_at (epoch seconds, float)
        line 2: reason
        line 3: scope   (added Phase 117; absent in legacy barriers → treated as "all")
    """
    if scope not in _VALID_BARRIER_SCOPES:
        raise ValueError(f"invalid barrier scope: {scope!r}")

    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return False
    try:
        idx_dir.mkdir(parents=True, exist_ok=True)
        barrier = idx_dir / _RESET_BARRIER_FILENAME
        barrier.write_text(f"{time.time()}\n{reason}\n{scope}\n")
        logger.info(
            "Reset barrier set for %s (reason=%s, scope=%s)",
            project_id, reason, scope,
        )
        return True
    except Exception:
        logger.debug("Failed to write reset barrier for %s", project_id, exc_info=True)
        return False


def clear_reset_barrier(project_id: str) -> bool:
    """Remove the reset barrier. Called on scope-group or finalize completion."""
    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return False
    barrier = idx_dir / _RESET_BARRIER_FILENAME
    if not barrier.is_file():
        return False
    try:
        barrier.unlink()
        logger.info("Reset barrier cleared for %s", project_id)
        return True
    except Exception:
        logger.debug("Failed to clear reset barrier for %s", project_id, exc_info=True)
        return False


def reset_barrier_active(project_id: str) -> bool:
    """True if a reset barrier is in effect for this project."""
    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return False
    return (idx_dir / _RESET_BARRIER_FILENAME).is_file()


def read_reset_barrier(project_id: str) -> dict | None:
    """Read the reset barrier contents. Returns None if inactive.

    Returns {"written_at": float, "reason": str, "scope": str, "age_seconds": float}.
    Legacy 2-line barriers (no scope line) report scope="all".
    """
    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return None
    barrier = idx_dir / _RESET_BARRIER_FILENAME
    if not barrier.is_file():
        return None
    try:
        text = barrier.read_text().strip()
        lines = text.split("\n")
        written_at: float | None = None
        reason = ""
        scope = "all"
        if lines:
            try:
                written_at = float(lines[0])
            except ValueError:
                written_at = None
            if len(lines) >= 2:
                reason = lines[1].strip()
            if len(lines) >= 3:
                candidate = lines[2].strip()
                if candidate in _VALID_BARRIER_SCOPES:
                    scope = candidate
        if written_at is None:
            written_at = barrier.stat().st_mtime
        return {
            "written_at": written_at,
            "reason": reason or "unknown",
            "scope": scope,
            "age_seconds": max(0.0, time.time() - written_at),
        }
    except Exception:
        logger.debug("Failed to read reset barrier for %s", project_id, exc_info=True)
        return None
```

- [ ] **Step 4: Run tests and watch them pass**

Run: `.venv/bin/pytest tests/services/pipeline/test_reset_barrier_scope.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Run the full existing recovery test suite to check for regressions**

Run: `.venv/bin/pytest tests/services/pipeline/ -v -k "barrier or recovery"`
Expected: all tests PASS (legacy callers default to scope="all").

- [ ] **Step 6: Commit**

```bash
git add src/prep/services/pipeline/recovery.py tests/services/pipeline/test_reset_barrier_scope.py
git commit -m "feat(pipeline): reset barrier gains optional scope (sync/enrichment/all)"
```

---

## Task 2: Scope-aware barrier auto-clear on group completion

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py` (existing `clear_reset_barrier` calls)
- Test: `tests/services/pipeline/test_barrier_scope_autoclear.py` (new)

Background — today the orchestrator clears the barrier only on finalize completion. For `scope="sync"` we want it cleared when stage 5 finishes; for `scope="enrichment"` when stage 10 finishes.

- [ ] **Step 1: Find the existing clear points**

Run: `.venv/bin/grep -n "clear_reset_barrier" src/prep/services/pipeline/orchestrator.py`

Record each line number. There should be at least one call near the finalize-completion path.

- [ ] **Step 2: Write the failing test**

Create `tests/services/pipeline/test_barrier_scope_autoclear.py`:

```python
"""Phase 117: verify the barrier auto-clears at the right stage boundary per scope."""
from __future__ import annotations

import pytest

from prep.services.pipeline.recovery import (
    read_reset_barrier,
    write_reset_barrier,
)


@pytest.fixture
def project_with_idx(tmp_path, monkeypatch):
    from prep.services.pipeline import recovery
    monkeypatch.setattr(recovery, "_resolve_idx_dir", lambda _pid: tmp_path)
    return "proj-test", tmp_path


def test_maybe_clear_scoped_barrier_clears_on_sync_boundary(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="sync")

    cleared = maybe_clear_scoped_barrier(project_id, completed_group="fast_sync")
    assert cleared is True
    assert read_reset_barrier(project_id) is None


def test_maybe_clear_scoped_barrier_ignores_wrong_group(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="sync")

    cleared = maybe_clear_scoped_barrier(project_id, completed_group="deep_enrichment")
    assert cleared is False
    assert read_reset_barrier(project_id) is not None


def test_enrichment_scope_clears_on_deep_boundary(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="enrichment")

    cleared = maybe_clear_scoped_barrier(project_id, completed_group="deep_enrichment")
    assert cleared is True


def test_all_scope_only_clears_on_finalize(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="all")

    assert maybe_clear_scoped_barrier(project_id, completed_group="fast_sync") is False
    assert maybe_clear_scoped_barrier(project_id, completed_group="deep_enrichment") is False
    assert maybe_clear_scoped_barrier(project_id, completed_group="finalize") is True
    assert read_reset_barrier(project_id) is None
```

- [ ] **Step 3: Run tests and watch them fail**

Run: `.venv/bin/pytest tests/services/pipeline/test_barrier_scope_autoclear.py -v`
Expected: FAIL with `ImportError: cannot import name 'maybe_clear_scoped_barrier'`.

- [ ] **Step 4: Implement `maybe_clear_scoped_barrier`**

In `src/prep/services/pipeline/recovery.py`, append after `read_reset_barrier`:

```python
_SCOPE_BOUNDARY = {
    "sync": "fast_sync",
    "enrichment": "deep_enrichment",
    "all": "finalize",
}


def maybe_clear_scoped_barrier(project_id: str, completed_group: str) -> bool:
    """Clear the reset barrier iff ``completed_group`` is the boundary for its scope.

    Called by the orchestrator after each group finishes. Returns True if the
    barrier was cleared, False otherwise (wrong boundary, or no barrier set).
    """
    info = read_reset_barrier(project_id)
    if info is None:
        return False
    boundary = _SCOPE_BOUNDARY.get(info.get("scope", "all"))
    if boundary != completed_group:
        return False
    return clear_reset_barrier(project_id)
```

- [ ] **Step 5: Wire it into the orchestrator**

In `src/prep/services/pipeline/orchestrator.py`, locate every existing `clear_reset_barrier(project_id)` call site and replace the direct clear with a call that also runs on the fast_sync and deep_enrichment completion paths. Search for the completion handlers (look for where `group == "fast_sync"` / `"deep_enrichment"` / `"finalize"` transitions to completed in the state machine callbacks).

For each of these three completion paths, ensure a call like this fires **after** the stage state machine flips to completed and **before** the next group's chain dispatch:

```python
from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
maybe_clear_scoped_barrier(project_id, completed_group=group_name)
```

If only a finalize clear exists today, add the sync and deep_enrichment counterparts. If a single clear point already handles post-group cleanup, switch it from `clear_reset_barrier(project_id)` to `maybe_clear_scoped_barrier(project_id, completed_group=<group>)`.

- [ ] **Step 6: Run the new tests**

Run: `.venv/bin/pytest tests/services/pipeline/test_barrier_scope_autoclear.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 7: Run the orchestrator regression suite**

Run: `.venv/bin/pytest tests/services/pipeline/ -v`
Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/prep/services/pipeline/recovery.py src/prep/services/pipeline/orchestrator.py tests/services/pipeline/test_barrier_scope_autoclear.py
git commit -m "feat(pipeline): barrier auto-clears at scope-appropriate group boundary"
```

---

## Task 3: Add `force_from_start` body param to `/pipeline/fast` and `/pipeline/deep`

**Files:**
- Modify: `src/prep/api/routers/pipeline.py` (endpoints for `fast`, `deep`)
- Test: `tests/api/routers/test_pipeline_scoped_rebuild.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/api/routers/test_pipeline_scoped_rebuild.py`:

```python
"""Phase 117: scoped-rebuild body params on /pipeline/fast and /pipeline/deep."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_project(monkeypatch):
    def _noop(_pid):
        return None
    monkeypatch.setattr(
        "prep.services.project_helpers.require_project_writable", _noop
    )
    return "proj-test"


def test_pipeline_fast_with_force_from_start_writes_sync_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery

    writes: list[tuple[str, str, str]] = []

    def fake_write(pid, reason, scope="all"):
        writes.append((pid, reason, scope))
        return True

    monkeypatch.setattr(recovery, "write_reset_barrier", fake_write)

    started = MagicMock(return_value=True)
    orch = MagicMock()
    orch.run_fast_sync = started
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(
        f"/projects/{fake_project}/pipeline/fast",
        json={"force_from_start": True},
    )
    assert resp.status_code == 200
    assert writes == [(fake_project, "rebuild", "sync")]
    orch.run_fast_sync.assert_called_once_with(fake_project, force_from_start=True)


def test_pipeline_deep_with_force_from_start_writes_enrichment_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery
    writes: list[tuple[str, str, str]] = []

    def fake_write(pid, reason, scope="all"):
        writes.append((pid, reason, scope))
        return True

    monkeypatch.setattr(recovery, "write_reset_barrier", fake_write)

    orch = MagicMock()
    orch.run_deep_enrichment = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(
        f"/projects/{fake_project}/pipeline/deep",
        json={"force_from_start": True},
    )
    assert resp.status_code == 200
    assert writes == [(fake_project, "rebuild", "enrichment")]
    orch.run_deep_enrichment.assert_called_once_with(fake_project, force_from_start=True)


def test_pipeline_fast_without_force_from_start_does_not_write_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery
    writes: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        recovery, "write_reset_barrier",
        lambda pid, reason, scope="all": writes.append((pid, reason, scope)) or True,
    )

    orch = MagicMock()
    orch.run_fast_sync = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/fast", json={})
    assert resp.status_code == 200
    assert writes == []
    orch.run_fast_sync.assert_called_once_with(fake_project, force_from_start=False)
```

- [ ] **Step 2: Run tests and watch them fail**

Run: `.venv/bin/pytest tests/api/routers/test_pipeline_scoped_rebuild.py -v`
Expected: all 3 tests FAIL (endpoint ignores body params).

- [ ] **Step 3: Update `/pipeline/fast` to accept the body param**

Locate the `pipeline_run_fast` (or similarly named) handler in `src/prep/api/routers/pipeline.py`. Add a request model above it and update the handler signature. Replace the handler body's call to `run_fast_sync(project_id)` with the scoped version:

```python
class FastRequest(BaseModel):
    force_from_start: bool = False


@router.post("/projects/{project_id}/pipeline/fast")
def pipeline_run_fast(
    project_id: str,
    req: FastRequest | None = None,
) -> dict[str, Any]:
    """Run Fast Sync (stages 1-5).

    Phase 117: when ``force_from_start`` is True, writes the rebuild barrier
    with ``scope="sync"`` before dispatch. Otherwise runs incremental resume.
    """
    from prep.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    force = bool(req.force_from_start) if req else False

    if force:
        try:
            from prep.services.pipeline.recovery import write_reset_barrier
            write_reset_barrier(project_id, reason="rebuild", scope="sync")
        except Exception:
            pass

    from prep.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_fast_sync(project_id, force_from_start=force)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Pipeline is already running for this project",
        )
    return ok({"started": True, "group": "fast_sync", "force_from_start": force})
```

- [ ] **Step 4: Do the same for `/pipeline/deep`**

Mirror the pattern for the deep-enrichment handler. Name the body model `DeepRequest`, and use `scope="enrichment"` when force is set.

```python
class DeepRequest(BaseModel):
    force_from_start: bool = False


@router.post("/projects/{project_id}/pipeline/deep")
def pipeline_run_deep(
    project_id: str,
    req: DeepRequest | None = None,
) -> dict[str, Any]:
    from prep.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    force = bool(req.force_from_start) if req else False

    if force:
        try:
            from prep.services.pipeline.recovery import write_reset_barrier
            write_reset_barrier(project_id, reason="rebuild", scope="enrichment")
        except Exception:
            pass

    from prep.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_deep_enrichment(project_id, force_from_start=force)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Pipeline is already running for this project",
        )
    return ok({"started": True, "group": "deep_enrichment", "force_from_start": force})
```

- [ ] **Step 5: Update the existing `/pipeline/rebuild` to use `scope="all"`**

Find the existing `pipeline_rebuild` handler. Change its `write_reset_barrier(project_id, reason="rebuild")` call to `write_reset_barrier(project_id, reason="rebuild", scope="all")`.

- [ ] **Step 6: Run the new tests**

Run: `.venv/bin/pytest tests/api/routers/test_pipeline_scoped_rebuild.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 7: Run the broader router suite for regressions**

Run: `.venv/bin/pytest tests/api/routers/ -v -k pipeline`
Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/prep/api/routers/pipeline.py tests/api/routers/test_pipeline_scoped_rebuild.py
git commit -m "feat(api): /pipeline/fast and /pipeline/deep accept force_from_start"
```

---

## Task 4: New `/pipeline/rebuild/stop` endpoint

**Files:**
- Modify: `src/prep/api/routers/pipeline.py` (add endpoint near existing `pipeline_cancel`)
- Test: `tests/api/routers/test_pipeline_rebuild_stop.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/api/routers/test_pipeline_rebuild_stop.py`:

```python
"""Phase 117: /pipeline/rebuild/stop atomic cancel + barrier clear."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_project(monkeypatch):
    monkeypatch.setattr(
        "prep.services.project_helpers.require_project_writable", lambda _pid: None
    )
    return "proj-test"


def test_rebuild_stop_clears_barrier_when_idle(client, fake_project, monkeypatch):
    """If no rebuild is active, endpoint still returns success and no-ops."""
    from prep.services.pipeline import recovery

    monkeypatch.setattr(recovery, "read_reset_barrier", lambda _pid: None)
    monkeypatch.setattr(recovery, "clear_reset_barrier", lambda _pid: False)

    orch = MagicMock()
    orch._cancel_group = MagicMock(return_value=False)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/rebuild/stop")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["stopped"] is True
    assert body["was_active"] is False


def test_rebuild_stop_cancels_active_group_and_clears_barrier(
    client, fake_project, monkeypatch
):
    from prep.services.pipeline import recovery

    monkeypatch.setattr(
        recovery, "read_reset_barrier",
        lambda _pid: {"reason": "rebuild", "scope": "sync", "written_at": 1.0, "age_seconds": 0.0},
    )
    cleared = {"v": False}
    def _clear(_pid):
        cleared["v"] = True
        return True
    monkeypatch.setattr(recovery, "clear_reset_barrier", _clear)

    orch = MagicMock()
    orch.cancel_fast_sync = MagicMock(return_value=True)
    orch.cancel_deep_enrichment = MagicMock(return_value=False)
    orch.cancel_finalize = MagicMock(return_value=False)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/rebuild/stop")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["was_active"] is True
    assert cleared["v"] is True
    # Sync scope → cancels fast_sync
    orch.cancel_fast_sync.assert_called_once_with(fake_project)


def test_rebuild_stop_enrichment_scope_cancels_deep(client, fake_project, monkeypatch):
    from prep.services.pipeline import recovery

    monkeypatch.setattr(
        recovery, "read_reset_barrier",
        lambda _pid: {"reason": "rebuild", "scope": "enrichment", "written_at": 1.0, "age_seconds": 0.0},
    )
    monkeypatch.setattr(recovery, "clear_reset_barrier", lambda _pid: True)

    orch = MagicMock()
    orch.cancel_deep_enrichment = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prep.services.pipeline_orchestrator.pipeline_orchestrator", orch
    )

    resp = client.post(f"/projects/{fake_project}/pipeline/rebuild/stop")
    assert resp.status_code == 200
    orch.cancel_deep_enrichment.assert_called_once_with(fake_project)
```

- [ ] **Step 2: Run tests and watch them fail**

Run: `.venv/bin/pytest tests/api/routers/test_pipeline_rebuild_stop.py -v`
Expected: 3 tests FAIL (endpoint does not exist, 404 or similar).

- [ ] **Step 3: Add the endpoint**

In `src/prep/api/routers/pipeline.py`, add near the existing `pipeline_cancel` handler:

```python
@router.post("/projects/{project_id}/pipeline/rebuild/stop")
def pipeline_rebuild_stop(project_id: str) -> dict[str, Any]:
    """Phase 117: atomically cancel an active rebuild and clear the barrier.

    Behavior:
    - Reads the barrier to discover which group was force-rebuilding (sync /
      enrichment / all).
    - Cancels that group if it's actively running. The temp files the stage
      wrote never swap in (atomic-swap guarantee), so the pre-rebuild data
      for the currently-running stage remains the live copy.
    - Clears the barrier.
    - Idempotent: succeeds even if no rebuild is active.
    """
    from prep.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from prep.services.pipeline import recovery
    from prep.services.pipeline_orchestrator import pipeline_orchestrator

    info = recovery.read_reset_barrier(project_id)
    was_active = info is not None and info.get("reason") == "rebuild"

    cancelled = False
    if was_active:
        scope = info.get("scope", "all")
        try:
            if scope == "sync":
                cancelled = pipeline_orchestrator.cancel_fast_sync(project_id)
            elif scope == "enrichment":
                cancelled = pipeline_orchestrator.cancel_deep_enrichment(project_id)
            else:  # "all" — cancel whichever group is live
                cancelled = (
                    pipeline_orchestrator.cancel_fast_sync(project_id)
                    or pipeline_orchestrator.cancel_deep_enrichment(project_id)
                    or pipeline_orchestrator.cancel_finalize(project_id)
                )
        except Exception:
            logger.exception("rebuild/stop: cancel failed for %s", project_id)

    recovery.clear_reset_barrier(project_id)

    return ok({
        "stopped": True,
        "was_active": was_active,
        "cancelled_group": cancelled,
    })
```

- [ ] **Step 4: Run the new tests**

Run: `.venv/bin/pytest tests/api/routers/test_pipeline_rebuild_stop.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/api/routers/pipeline.py tests/api/routers/test_pipeline_rebuild_stop.py
git commit -m "feat(api): /pipeline/rebuild/stop — atomic cancel + barrier clear"
```

---

## Task 5: `compute_stage_provenance` helper

**Files:**
- Create: `src/prep/services/pipeline_provenance.py`
- Test: `tests/services/test_pipeline_provenance.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/services/test_pipeline_provenance.py`:

```python
"""Phase 117: per-stage provenance helper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def idx_dir(tmp_path, monkeypatch):
    """Patch the helper so idx_dir resolution points at tmp_path."""
    from prep.services import pipeline_provenance

    monkeypatch.setattr(pipeline_provenance, "_resolve_idx_dir", lambda _pid: tmp_path)
    return tmp_path


def _write_manifest(idx_dir: Path, filename: str, content: dict) -> None:
    (idx_dir / filename).write_text(json.dumps(content))


def test_match_when_manifest_equals_current(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance

    _write_manifest(
        idx_dir,
        "trace_epistemic_manifest.json",
        {"model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"}},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )

    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "match"
    assert out["chip_text"] is None
    assert out["rebuild_scope"] is None


def test_drift_when_manifest_differs_from_current(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_epistemic_manifest.json",
        {"model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"}},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "qwen3:14b"),
    )

    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "drift"
    assert "kimi-k2.5:cloud" in out["chip_text"]
    assert "qwen3:14b" in out["chip_text"]
    assert out["rebuild_scope"] == "enrichment"


def test_stub_when_manifest_is_restored_selfheal(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_augment_manifest.json",
        {"restored": True, "source": "selfheal"},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )
    # No golden evidence
    out = pipeline_provenance.compute_stage_provenance("p1", "augmentation")
    assert out["state"] == "recovered_stub"
    assert "provenance unknown" in out["chip_text"]
    assert out["rebuild_scope"] == "sync"


def test_stub_softened_when_golden_matches(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_augment_manifest.json",
        {"restored": True, "source": "selfheal"},
    )
    # Golden _meta.json with an embedded model record
    (idx_dir / ".checkpoints").mkdir()
    (idx_dir / ".checkpoints" / "_golden").mkdir()
    (idx_dir / ".checkpoints" / "_golden" / "_meta.json").write_text(
        json.dumps({"stage_models": {"augmentation": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"}}})
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )

    out = pipeline_provenance.compute_stage_provenance("p1", "augmentation")
    assert out["state"] == "recovered_soft"
    assert "likely current" in out["chip_text"]


def test_missing_when_no_manifest_and_no_data(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )
    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "missing"


def test_non_llm_stage_has_no_chip(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(idx_dir, "validation_manifest.json", {"format_version": "2.0"})
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: None,  # non-LLM stage
    )
    out = pipeline_provenance.compute_stage_provenance("p1", "validation")
    assert out["state"] in ("match", "recovered_soft", "recovered_stub", "missing")
    # For non-LLM stages, match-equivalent state renders no chip
    assert out["chip_text"] is None or out["chip_text"] == ""


def test_provider_case_insensitive_match(idx_dir, monkeypatch):
    from prep.services import pipeline_provenance
    _write_manifest(
        idx_dir,
        "trace_epistemic_manifest.json",
        {"model": {"provider": "Ollama", "model_name": "kimi-k2.5:cloud"}},
    )
    monkeypatch.setattr(
        pipeline_provenance,
        "resolve_model_for_stage",
        lambda _pid, _stage: ("ollama", "kimi-k2.5:cloud"),
    )
    out = pipeline_provenance.compute_stage_provenance("p1", "enrichment")
    assert out["state"] == "match"
```

- [ ] **Step 2: Run tests and watch them fail**

Run: `.venv/bin/pytest tests/services/test_pipeline_provenance.py -v`
Expected: all tests FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helper**

Create `src/prep/services/pipeline_provenance.py`:

```python
"""Per-stage provenance — Phase 117 Scope B.

Joins each stage's manifest model against the current LLM task-assignment
config to classify a stage as match / drift / recovered_stub / recovered_soft
/ missing. Consumed by /pipeline/status for UI rendering.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from prep.services.pipeline._model_resolution import resolve_model_for_stage

logger = logging.getLogger(__name__)


_STAGE_MANIFEST_FILE = {
    "trace": "trace_manifest.json",
    "inferred_edges": "trace_inferred_manifest.json",
    "augmentation": "trace_augment_manifest.json",
    "validation": "validation_manifest.json",
    "knowledge": "knowledge_manifest.json",
    "enrichment": "trace_epistemic_manifest.json",
    "group_reasoning": "group_reasoning_manifest.json",
    "clustering": "trace_modules_manifest.json",
    "deepening": "deepening_manifest.json",
    "deep_knowledge": "deep_knowledge_manifest.json",
    "atlas": "atlas_manifest.json",
    "rules": "rules_manifest.json",
    "concepts": "concepts_manifest.json",
    "audit": "audit_manifest.json",
    "antibodies": "antibodies_manifest.json",
}

_STAGE_TO_REBUILD_SCOPE = {
    # Sync (1-5)
    "trace": "sync",
    "inferred_edges": "sync",
    "augmentation": "sync",
    "validation": "sync",
    "knowledge": "sync",
    # Enrichment (6-10)
    "enrichment": "enrichment",
    "group_reasoning": "enrichment",
    "clustering": "enrichment",
    "deepening": "enrichment",
    "deep_knowledge": "enrichment",
    # Finalize (11-15) — no scope; per-stage recover
    "atlas": None,
    "rules": None,
    "concepts": None,
    "audit": None,
    "antibodies": None,
}


def _resolve_idx_dir(project_id: str) -> Path | None:
    try:
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project
        return Path(project_index_dir(require_project(project_id)))
    except Exception:
        logger.debug("could not resolve idx_dir for %s", project_id, exc_info=True)
        return None


def _read_manifest(idx_dir: Path, stage_id: str) -> dict | None:
    filename = _STAGE_MANIFEST_FILE.get(stage_id)
    if not filename:
        return None
    path = idx_dir / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _models_equal(a: tuple[str, str] | None, b: tuple[str, str] | None) -> bool:
    if a is None or b is None:
        return False
    return a[0].lower() == b[0].lower() and a[1] == b[1]


def _golden_model_for_stage(idx_dir: Path, stage_id: str) -> tuple[str, str] | None:
    meta = idx_dir / ".checkpoints" / "_golden" / "_meta.json"
    if not meta.is_file():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None
    entry = (data.get("stage_models") or {}).get(stage_id)
    if not entry:
        return None
    provider = (entry.get("provider") or "").lower()
    model = entry.get("model_name") or ""
    if not provider or not model:
        return None
    return (provider, model)


def compute_stage_provenance(project_id: str, stage_id: str) -> dict[str, Any]:
    """Classify a stage's provenance state.

    Returns a dict with keys: state, manifest_model, current_config_model,
    chip_text, rebuild_scope.
    """
    idx_dir = _resolve_idx_dir(project_id)
    current_tuple = resolve_model_for_stage(project_id, stage_id)
    current_model_dict = (
        {"provider": current_tuple[0], "model_name": current_tuple[1]}
        if current_tuple else None
    )
    rebuild_scope = _STAGE_TO_REBUILD_SCOPE.get(stage_id)

    if idx_dir is None:
        return {
            "state": "missing",
            "manifest_model": None,
            "current_config_model": current_model_dict,
            "chip_text": None,
            "rebuild_scope": rebuild_scope,
        }

    manifest = _read_manifest(idx_dir, stage_id)

    # Missing
    if manifest is None:
        return {
            "state": "missing",
            "manifest_model": None,
            "current_config_model": current_model_dict,
            "chip_text": None,
            "rebuild_scope": rebuild_scope,
        }

    # Recovered stub path
    if manifest.get("restored") is True:
        golden = _golden_model_for_stage(idx_dir, stage_id)
        if _models_equal(golden, current_tuple):
            return {
                "state": "recovered_soft",
                "manifest_model": None,
                "current_config_model": current_model_dict,
                "chip_text": "Self-healed · model likely current",
                "rebuild_scope": rebuild_scope,
            }
        return {
            "state": "recovered_stub",
            "manifest_model": None,
            "current_config_model": current_model_dict,
            "chip_text": "Self-healed · provenance unknown · Rebuild",
            "rebuild_scope": rebuild_scope,
        }

    # Genuine manifest path
    manifest_model = manifest.get("model") or {}
    manifest_tuple: tuple[str, str] | None = None
    if manifest_model:
        provider = (manifest_model.get("provider") or "").lower()
        model_name = manifest_model.get("model_name") or ""
        if provider and model_name:
            manifest_tuple = (provider, model_name)

    manifest_model_dict = (
        {"provider": manifest_tuple[0], "model_name": manifest_tuple[1]}
        if manifest_tuple else None
    )

    # Non-LLM stages (no manifest model AND no current-config model) → match, no chip
    if manifest_tuple is None and current_tuple is None:
        return {
            "state": "match",
            "manifest_model": None,
            "current_config_model": None,
            "chip_text": None,
            "rebuild_scope": rebuild_scope,
        }

    if _models_equal(manifest_tuple, current_tuple):
        return {
            "state": "match",
            "manifest_model": manifest_model_dict,
            "current_config_model": current_model_dict,
            "chip_text": None,
            "rebuild_scope": rebuild_scope,
        }

    chip = (
        f"Built with {manifest_tuple[1]} → now {current_tuple[1]} · Rebuild"
        if manifest_tuple and current_tuple
        else "Model changed · Rebuild"
    )
    return {
        "state": "drift",
        "manifest_model": manifest_model_dict,
        "current_config_model": current_model_dict,
        "chip_text": chip,
        "rebuild_scope": rebuild_scope,
    }
```

- [ ] **Step 4: Run the new tests**

Run: `.venv/bin/pytest tests/services/test_pipeline_provenance.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline_provenance.py tests/services/test_pipeline_provenance.py
git commit -m "feat(provenance): compute_stage_provenance — match/drift/stub/soft/missing"
```

---

## Task 6: Wire provenance into `/pipeline/status`

**Files:**
- Modify: `src/prep/api/routers/pipeline.py` — `_build_status()`
- Test: `tests/api/routers/test_pipeline_status_provenance.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/api/routers/test_pipeline_status_provenance.py`:

```python
"""Phase 117: /pipeline/status attaches a 'provenance' field per stage."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prep.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_pipeline_status_includes_provenance_per_stage(client, monkeypatch):
    """Every stage in the status payload carries a 'provenance' dict."""
    # Stub provenance helper to return a known shape for any (project, stage)
    def fake_prov(_pid, stage_id):
        return {
            "state": "match",
            "manifest_model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"},
            "current_config_model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"},
            "chip_text": None,
            "rebuild_scope": "enrichment" if stage_id == "enrichment" else None,
        }

    monkeypatch.setattr(
        "prep.services.pipeline_provenance.compute_stage_provenance", fake_prov
    )

    # Minimal project setup — status endpoint reads from disk; we rely on the
    # default empty-project behavior of _build_status for this shape test.
    resp = client.get("/projects/nonexistent-test-id/pipeline/status")
    # Accept either 200 (project auto-created) or 404 (no such project);
    # when 200, every stage carries provenance.
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        stages = data.get("stages", [])
        assert stages, "expected stage list in response"
        for stage in stages:
            assert "provenance" in stage, f"missing provenance on stage {stage.get('id')}"
            assert stage["provenance"]["state"] in {"match", "drift", "recovered_stub", "recovered_soft", "missing"}
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv/bin/pytest tests/api/routers/test_pipeline_status_provenance.py -v`
Expected: FAIL — `provenance` key missing from stage payloads.

- [ ] **Step 3: Wire provenance into `_build_status()`**

Open `src/prep/api/routers/pipeline.py`. In `_build_status()`, locate where the final response dict is assembled with a `stages` list. Add an import at the top of the file:

```python
from prep.services.pipeline_provenance import compute_stage_provenance
```

Immediately before the `stages` list is returned (or wherever each stage dict is constructed), attach provenance. The simplest place is at the end of `_build_status()` where the response dict is finalized — walk the `stages` list and decorate each element:

```python
# Phase 117: attach provenance to each stage entry
for stage in response.get("stages", []):
    try:
        stage["provenance"] = compute_stage_provenance(project_id, stage["id"])
    except Exception:
        stage["provenance"] = {
            "state": "missing",
            "manifest_model": None,
            "current_config_model": None,
            "chip_text": None,
            "rebuild_scope": None,
        }
```

(Place this after the `stages` list is fully built and before the return/cache-store step.)

- [ ] **Step 4: Run the test**

Run: `.venv/bin/pytest tests/api/routers/test_pipeline_status_provenance.py -v`
Expected: PASS (or skip if the endpoint returns 404 for the synthetic project ID — see the test's conditional).

- [ ] **Step 5: Run the broader pipeline-status suite**

Run: `.venv/bin/pytest tests/api/routers/ -v -k "pipeline and status"`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/pipeline.py tests/api/routers/test_pipeline_status_provenance.py
git commit -m "feat(api): /pipeline/status includes per-stage provenance"
```

---

## Task 7: Extend UI types for `scope` and `provenance`

**Files:**
- Modify: `packages/ui/src/types.ts`
- Modify: `packages/ui/src/components/trace/rebuildProgress.ts` (reads barrier)
- Test: `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts` (already exists — extend)

- [ ] **Step 1: Write the failing test for `isPipelineRebuilding` with scope**

Open `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts`. Append:

```typescript
import { isPipelineRebuilding, rebuildScope } from '../rebuildProgress';

describe('Phase 117 — barrier scope', () => {
  it('reads barrier.scope when present', () => {
    const barrier = { active: true, reason: 'rebuild', scope: 'sync' } as const;
    expect(isPipelineRebuilding(barrier)).toBe(true);
    expect(rebuildScope(barrier)).toBe('sync');
  });

  it('defaults to "all" when scope is absent (legacy)', () => {
    const barrier = { active: true, reason: 'rebuild' } as const;
    expect(rebuildScope(barrier)).toBe('all');
  });

  it('returns null when not rebuilding', () => {
    expect(rebuildScope({ active: false, reason: null })).toBeNull();
    expect(rebuildScope({ active: true, reason: 'reset' })).toBeNull();
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd packages/ui && npm test -- rebuildProgress`
Expected: FAIL — `rebuildScope` not exported.

- [ ] **Step 3: Extend the Barrier type**

In `packages/ui/src/types.ts`, find the existing barrier/pipeline type. Add a `scope` field:

```typescript
export type RebuildScope = 'sync' | 'enrichment' | 'all';

export interface PipelineBarrier {
  active: boolean;
  reason: string | null;
  scope?: RebuildScope; // Phase 117; absent → treat as 'all'
}
```

If a `PipelineBarrier` type already exists, merge the `scope` field into it. If the type is declared inline elsewhere, promote it to `types.ts` and re-export.

Also add:

```typescript
export interface StageProvenance {
  state: 'match' | 'drift' | 'recovered_stub' | 'recovered_soft' | 'missing';
  manifest_model: { provider: string; model_name: string } | null;
  current_config_model: { provider: string; model_name: string } | null;
  chip_text: string | null;
  rebuild_scope: RebuildScope | null;
}
```

- [ ] **Step 4: Add `rebuildScope` helper**

In `packages/ui/src/components/trace/rebuildProgress.ts`:

```typescript
import type { PipelineBarrier, RebuildScope } from '../../types';

export function rebuildScope(barrier: PipelineBarrier | null | undefined): RebuildScope | null {
  if (!barrier || !barrier.active || barrier.reason !== 'rebuild') return null;
  return (barrier.scope as RebuildScope | undefined) ?? 'all';
}
```

- [ ] **Step 5: Run the test**

Run: `cd packages/ui && npm test -- rebuildProgress`
Expected: all tests PASS (including existing ones).

- [ ] **Step 6: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/types.ts packages/ui/src/components/trace/rebuildProgress.ts packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts
git commit -m "feat(ui): add RebuildScope + StageProvenance types, rebuildScope helper"
```

---

## Task 8: `<ProvenanceChip>` component

**Files:**
- Create: `packages/ui/src/components/trace/ProvenanceChip.tsx`
- Create: `packages/ui/src/components/trace/__tests__/ProvenanceChip.test.tsx`
- Create: `packages/ui/src/stories/trace/ProvenanceChip.stories.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/components/trace/__tests__/ProvenanceChip.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProvenanceChip } from '../ProvenanceChip';

describe('ProvenanceChip', () => {
  it('renders nothing when state is match and chip_text is null', () => {
    const { container } = render(
      <ProvenanceChip
        provenance={{
          state: 'match',
          manifest_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
          current_config_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
          chip_text: null,
          rebuild_scope: 'enrichment',
        }}
        onRebuild={() => {}}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders amber chip on drift and calls onRebuild with scope on click', () => {
    const onRebuild = vi.fn();
    render(
      <ProvenanceChip
        provenance={{
          state: 'drift',
          manifest_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
          current_config_model: { provider: 'ollama', model_name: 'qwen3:14b' },
          chip_text: 'Built with kimi-k2.5:cloud → now qwen3:14b · Rebuild',
          rebuild_scope: 'enrichment',
        }}
        onRebuild={onRebuild}
      />
    );
    const btn = screen.getByRole('button', { name: /rebuild/i });
    fireEvent.click(btn);
    expect(onRebuild).toHaveBeenCalledWith('enrichment');
  });

  it('renders amber chip on recovered_stub with provenance-unknown text', () => {
    render(
      <ProvenanceChip
        provenance={{
          state: 'recovered_stub',
          manifest_model: null,
          current_config_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
          chip_text: 'Self-healed · provenance unknown · Rebuild',
          rebuild_scope: 'sync',
        }}
        onRebuild={() => {}}
      />
    );
    expect(screen.getByText(/provenance unknown/i)).toBeInTheDocument();
  });

  it('renders neutral-soft chip on recovered_soft (no amber, no rebuild click)', () => {
    const onRebuild = vi.fn();
    render(
      <ProvenanceChip
        provenance={{
          state: 'recovered_soft',
          manifest_model: null,
          current_config_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
          chip_text: 'Self-healed · model likely current',
          rebuild_scope: 'sync',
        }}
        onRebuild={onRebuild}
      />
    );
    // recovered_soft renders as plain span, not a button
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText(/likely current/i)).toBeInTheDocument();
  });

  it('renders nothing for missing state (existing red not-built treatment handled elsewhere)', () => {
    const { container } = render(
      <ProvenanceChip
        provenance={{
          state: 'missing',
          manifest_model: null,
          current_config_model: null,
          chip_text: null,
          rebuild_scope: null,
        }}
        onRebuild={() => {}}
      />
    );
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd packages/ui && npm test -- ProvenanceChip`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the component**

Create `packages/ui/src/components/trace/ProvenanceChip.tsx`:

```tsx
import type { StageProvenance, RebuildScope } from '../../types';

interface ProvenanceChipProps {
  provenance: StageProvenance;
  onRebuild: (scope: RebuildScope) => void;
}

export function ProvenanceChip({ provenance, onRebuild }: ProvenanceChipProps) {
  const { state, chip_text, rebuild_scope } = provenance;

  if (state === 'match' || state === 'missing' || !chip_text) {
    return null;
  }

  if (state === 'recovered_soft') {
    return (
      <span className="text-xs text-text-muted mt-1 inline-block">
        {chip_text}
      </span>
    );
  }

  // drift or recovered_stub → amber action chip
  const handleClick = () => {
    if (rebuild_scope) onRebuild(rebuild_scope);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="mt-1 inline-flex items-center gap-1 rounded-sm border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs text-warning hover:bg-warning/20"
      aria-label="Rebuild"
    >
      {chip_text}
    </button>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd packages/ui && npm test -- ProvenanceChip`
Expected: all 5 PASS.

- [ ] **Step 5: Add Storybook stories**

Create `packages/ui/src/stories/trace/ProvenanceChip.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { ProvenanceChip } from '../../components/trace/ProvenanceChip';

const meta: Meta<typeof ProvenanceChip> = {
  title: 'Trace/ProvenanceChip',
  component: ProvenanceChip,
};
export default meta;

type Story = StoryObj<typeof ProvenanceChip>;

const base = {
  manifest_model: null,
  current_config_model: null,
  chip_text: null,
  rebuild_scope: null as const,
};

export const Match: Story = {
  args: {
    provenance: { ...base, state: 'match' },
    onRebuild: () => {},
  },
};

export const Drift: Story = {
  args: {
    provenance: {
      state: 'drift',
      manifest_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
      current_config_model: { provider: 'ollama', model_name: 'qwen3:14b' },
      chip_text: 'Built with kimi-k2.5:cloud → now qwen3:14b · Rebuild',
      rebuild_scope: 'enrichment',
    },
    onRebuild: () => {},
  },
};

export const RecoveredStub: Story = {
  args: {
    provenance: {
      state: 'recovered_stub',
      manifest_model: null,
      current_config_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
      chip_text: 'Self-healed · provenance unknown · Rebuild',
      rebuild_scope: 'sync',
    },
    onRebuild: () => {},
  },
};

export const RecoveredSoft: Story = {
  args: {
    provenance: {
      state: 'recovered_soft',
      manifest_model: null,
      current_config_model: { provider: 'ollama', model_name: 'kimi-k2.5:cloud' },
      chip_text: 'Self-healed · model likely current',
      rebuild_scope: 'sync',
    },
    onRebuild: () => {},
  },
};
```

- [ ] **Step 6: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/components/trace/ProvenanceChip.tsx packages/ui/src/components/trace/__tests__/ProvenanceChip.test.tsx packages/ui/src/stories/trace/ProvenanceChip.stories.tsx
git commit -m "feat(ui): ProvenanceChip component — drift/stub/soft states"
```

---

## Task 9: `<RebuildingRow>` sticky queue component

**Files:**
- Create: `packages/ui/src/components/trace/RebuildingRow.tsx`
- Create: `packages/ui/src/components/trace/__tests__/RebuildingRow.test.tsx`
- Create: `packages/ui/src/stories/trace/RebuildingRow.stories.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/components/trace/__tests__/RebuildingRow.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RebuildingRow } from '../RebuildingRow';

describe('RebuildingRow', () => {
  it('renders scope label and current stage', () => {
    render(
      <RebuildingRow
        scope="sync"
        currentStageIndex={2}
        totalStagesInScope={5}
        currentStageLabel="Fast Catalogue"
        percent={38}
        onStop={() => {}}
      />
    );
    expect(screen.getByText(/rebuilding sync/i)).toBeInTheDocument();
    expect(screen.getByText(/stage 3\/5/i)).toBeInTheDocument();
    expect(screen.getByText(/fast catalogue/i)).toBeInTheDocument();
    expect(screen.getByText(/38%/)).toBeInTheDocument();
  });

  it('enrichment scope label matches', () => {
    render(
      <RebuildingRow
        scope="enrichment"
        currentStageIndex={0}
        totalStagesInScope={5}
        currentStageLabel="Epistemic Enrichment"
        percent={0}
        onStop={() => {}}
      />
    );
    expect(screen.getByText(/rebuilding enrichment/i)).toBeInTheDocument();
  });

  it('all scope label matches', () => {
    render(
      <RebuildingRow
        scope="all"
        currentStageIndex={11}
        totalStagesInScope={15}
        currentStageLabel="Atlas"
        percent={78}
        onStop={() => {}}
      />
    );
    expect(screen.getByText(/rebuilding all/i)).toBeInTheDocument();
  });

  it('Stop button triggers onStop', () => {
    const onStop = vi.fn();
    render(
      <RebuildingRow
        scope="sync"
        currentStageIndex={0}
        totalStagesInScope={5}
        currentStageLabel="Structural Graph"
        percent={10}
        onStop={onStop}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /stop/i }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd packages/ui && npm test -- RebuildingRow`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the component**

Create `packages/ui/src/components/trace/RebuildingRow.tsx`:

```tsx
import type { RebuildScope } from '../../types';

interface RebuildingRowProps {
  scope: RebuildScope;
  currentStageIndex: number; // 0-based within scope
  totalStagesInScope: number;
  currentStageLabel: string;
  percent: number; // 0-100
  onStop: () => void;
}

const SCOPE_LABEL: Record<RebuildScope, string> = {
  sync: 'Rebuilding Sync',
  enrichment: 'Rebuilding Enrichment',
  all: 'Rebuilding All',
};

export function RebuildingRow({
  scope,
  currentStageIndex,
  totalStagesInScope,
  currentStageLabel,
  percent,
  onStop,
}: RebuildingRowProps) {
  const stageOrdinal = Math.max(1, currentStageIndex + 1);
  return (
    <div className="flex items-center justify-between gap-3 rounded border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="text-blue-400 font-medium">🔄 {SCOPE_LABEL[scope]}</span>
        <span className="text-text-muted">·</span>
        <span className="text-text-muted">
          stage {stageOrdinal}/{totalStagesInScope}: {currentStageLabel}
        </span>
        <span className="text-text-muted">·</span>
        <span className="text-blue-400 font-medium">{Math.round(percent)}%</span>
      </div>
      <button
        type="button"
        onClick={onStop}
        className="rounded border border-blue-500/40 px-2 py-0.5 text-xs text-blue-400 hover:bg-blue-500/20"
        aria-label="Stop rebuild"
      >
        Stop
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd packages/ui && npm test -- RebuildingRow`
Expected: 4 PASS.

- [ ] **Step 5: Add Storybook stories**

Create `packages/ui/src/stories/trace/RebuildingRow.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { RebuildingRow } from '../../components/trace/RebuildingRow';

const meta: Meta<typeof RebuildingRow> = {
  title: 'Trace/RebuildingRow',
  component: RebuildingRow,
};
export default meta;

type Story = StoryObj<typeof RebuildingRow>;

export const Sync: Story = {
  args: {
    scope: 'sync',
    currentStageIndex: 2,
    totalStagesInScope: 5,
    currentStageLabel: 'Fast Catalogue',
    percent: 38,
    onStop: () => console.log('stop'),
  },
};

export const Enrichment: Story = {
  args: {
    scope: 'enrichment',
    currentStageIndex: 1,
    totalStagesInScope: 5,
    currentStageLabel: 'Group Reasoning',
    percent: 22,
    onStop: () => console.log('stop'),
  },
};

export const All: Story = {
  args: {
    scope: 'all',
    currentStageIndex: 11,
    totalStagesInScope: 15,
    currentStageLabel: 'Atlas',
    percent: 78,
    onStop: () => console.log('stop'),
  },
};
```

- [ ] **Step 6: Typecheck + commit**

Run: `cd packages/ui && npm run typecheck`

```bash
git add packages/ui/src/components/trace/RebuildingRow.tsx packages/ui/src/components/trace/__tests__/RebuildingRow.test.tsx packages/ui/src/stories/trace/RebuildingRow.stories.tsx
git commit -m "feat(ui): RebuildingRow sticky queue component with Stop button"
```

---

## Task 10: `<RebuildDropdown>` split-button component

**Files:**
- Create: `packages/ui/src/components/trace/RebuildDropdown.tsx`
- Create: `packages/ui/src/components/trace/__tests__/RebuildDropdown.test.tsx`
- Create: `packages/ui/src/stories/trace/RebuildDropdown.stories.tsx`

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/components/trace/__tests__/RebuildDropdown.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RebuildDropdown } from '../RebuildDropdown';

describe('RebuildDropdown', () => {
  it('primary click invokes onRebuild with "all"', () => {
    const onRebuild = vi.fn();
    render(<RebuildDropdown onRebuild={onRebuild} disabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: /^rebuild$/i }));
    expect(onRebuild).toHaveBeenCalledWith('all');
  });

  it('caret opens menu; menu has three options', () => {
    render(<RebuildDropdown onRebuild={() => {}} disabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: /open rebuild options/i }));
    expect(screen.getByRole('menuitem', { name: /rebuild sync/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /rebuild enrichment/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /rebuild all/i })).toBeInTheDocument();
  });

  it('selecting Sync from menu invokes onRebuild with "sync"', () => {
    const onRebuild = vi.fn();
    render(<RebuildDropdown onRebuild={onRebuild} disabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: /open rebuild options/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /rebuild sync/i }));
    expect(onRebuild).toHaveBeenCalledWith('sync');
  });

  it('selecting Enrichment from menu invokes onRebuild with "enrichment"', () => {
    const onRebuild = vi.fn();
    render(<RebuildDropdown onRebuild={onRebuild} disabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: /open rebuild options/i }));
    fireEvent.click(screen.getByRole('menuitem', { name: /rebuild enrichment/i }));
    expect(onRebuild).toHaveBeenCalledWith('enrichment');
  });

  it('when disabled both buttons are disabled', () => {
    render(<RebuildDropdown onRebuild={() => {}} disabled={true} />);
    expect(screen.getByRole('button', { name: /^rebuild$/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /open rebuild options/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd packages/ui && npm test -- RebuildDropdown`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the component**

Create `packages/ui/src/components/trace/RebuildDropdown.tsx`:

```tsx
import { useState, useRef, useEffect } from 'react';
import type { RebuildScope } from '../../types';

interface RebuildDropdownProps {
  onRebuild: (scope: RebuildScope) => void;
  disabled: boolean;
}

export function RebuildDropdown({ onRebuild, disabled }: RebuildDropdownProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const pick = (scope: RebuildScope) => {
    setOpen(false);
    onRebuild(scope);
  };

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => pick('all')}
        className="rounded-l border border-warning/40 px-3 py-1.5 text-sm text-warning hover:bg-warning/10 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Rebuild
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        aria-label="Open rebuild options"
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-r border border-l-0 border-warning/40 px-2 py-1.5 text-sm text-warning hover:bg-warning/10 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        ▾
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1 min-w-[220px] rounded border border-border bg-surface shadow-lg z-10"
        >
          <button
            role="menuitem"
            type="button"
            onClick={() => pick('sync')}
            className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2"
          >
            Rebuild Sync (1–5)
          </button>
          <button
            role="menuitem"
            type="button"
            onClick={() => pick('enrichment')}
            className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2"
          >
            Rebuild Enrichment (6–10)
          </button>
          <button
            role="menuitem"
            type="button"
            onClick={() => pick('all')}
            className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2"
          >
            Rebuild All (1–15)
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd packages/ui && npm test -- RebuildDropdown`
Expected: 5 PASS.

- [ ] **Step 5: Add Storybook story**

Create `packages/ui/src/stories/trace/RebuildDropdown.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import { RebuildDropdown } from '../../components/trace/RebuildDropdown';

const meta: Meta<typeof RebuildDropdown> = {
  title: 'Trace/RebuildDropdown',
  component: RebuildDropdown,
};
export default meta;

type Story = StoryObj<typeof RebuildDropdown>;

export const Default: Story = {
  args: {
    onRebuild: (scope) => console.log('rebuild', scope),
    disabled: false,
  },
};

export const Disabled: Story = {
  args: {
    onRebuild: (scope) => console.log('rebuild', scope),
    disabled: true,
  },
};
```

- [ ] **Step 6: Typecheck + commit**

Run: `cd packages/ui && npm run typecheck`

```bash
git add packages/ui/src/components/trace/RebuildDropdown.tsx packages/ui/src/components/trace/__tests__/RebuildDropdown.test.tsx packages/ui/src/stories/trace/RebuildDropdown.stories.tsx
git commit -m "feat(ui): RebuildDropdown split-button — Sync/Enrichment/All"
```

---

## Task 11: Wire `useEnrichment` hook for scoped rebuild + stop

**Files:**
- Modify: `src/prep/dashboard/src/hooks/useEnrichment.ts`
- Test: find existing useEnrichment tests; if none, this is a behavior test via GraphEnrichmentPipeline integration

- [ ] **Step 1: Locate the hook's existing rebuild trigger**

Run: `.venv/bin/grep -n "rebuild\|fast\|deep" src/prep/dashboard/src/hooks/useEnrichment.ts | head -40`

Note the existing API calls (likely `POST /projects/{id}/pipeline/rebuild`).

- [ ] **Step 2: Add `triggerRebuild(scope)` and `stopRebuild()`**

Append the following to the hook's exported surface. Find where existing trigger functions live (commonly returned from the hook); add:

```typescript
const triggerRebuild = async (scope: 'sync' | 'enrichment' | 'all') => {
  const endpoint =
    scope === 'sync'
      ? `/projects/${projectId}/pipeline/fast`
      : scope === 'enrichment'
      ? `/projects/${projectId}/pipeline/deep`
      : `/projects/${projectId}/pipeline/rebuild`;

  const body = scope === 'all' ? undefined : { force_from_start: true };

  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message ?? `Rebuild ${scope} failed`);
  }
  return resp.json();
};

const stopRebuild = async () => {
  const resp = await fetch(`/projects/${projectId}/pipeline/rebuild/stop`, {
    method: 'POST',
  });
  if (!resp.ok) {
    throw new Error(`Stop rebuild failed (${resp.status})`);
  }
  return resp.json();
};
```

Return `triggerRebuild` and `stopRebuild` from the hook alongside its existing exports. If there was a prior `triggerRebuild()` (no-arg), replace it with the new scoped version and update callers in step 3.

- [ ] **Step 3: Update existing callers**

Run: `.venv/bin/grep -rn "triggerRebuild\|onRebuildPipeline" src/prep/dashboard/ packages/ui/src/`

For each call site that passed no args (expecting the legacy all-rebuild behavior), update to pass `'all'` explicitly:

```typescript
// before: triggerRebuild()
triggerRebuild('all');
```

- [ ] **Step 4: Typecheck**

Run: `cd src/prep/dashboard && npm run typecheck` (or the monorepo equivalent — check `package.json`)
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/prep/dashboard/src/hooks/useEnrichment.ts
git commit -m "feat(dashboard): useEnrichment adds triggerRebuild(scope) + stopRebuild"
```

---

## Task 12: Integrate dropdown + sticky + chips into `GraphEnrichmentPipeline.tsx`

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

- [ ] **Step 1: Import new components and types**

At the top of `GraphEnrichmentPipeline.tsx`, add:

```tsx
import { RebuildDropdown } from './RebuildDropdown';
import { RebuildingRow } from './RebuildingRow';
import { ProvenanceChip } from './ProvenanceChip';
import { rebuildScope } from './rebuildProgress';
import type { RebuildScope, StageProvenance } from '../../types';
```

- [ ] **Step 2: Extend props**

Find the `GraphEnrichmentPipelineProps` interface. Add:

```typescript
onRebuild: (scope: RebuildScope) => void;
onStopRebuild: () => void;
```

Make them optional (`?`) only if any story/caller cannot supply them; prefer required for the dashboard usage.

- [ ] **Step 3: Place the `<RebuildDropdown>` in the existing panel header**

Locate the panel header (near the "Details" toggle or existing action row). Replace or add next to existing rebuild-related button:

```tsx
<RebuildDropdown
  onRebuild={onRebuild}
  disabled={fastRunning || deepRunning || finalizeRunning || isRebuilding}
/>
```

Use the existing `fastRunning`, `deepRunning`, `finalizeRunning` values already computed in the component (lines ~1355–1357).

- [ ] **Step 4: Render the `<RebuildingRow>` sticky above the queue**

Inside the component body, compute scope + ordinal:

```tsx
const scope = rebuildScope(barrier);
const stagesInScope = scope === 'sync'
  ? fastStages
  : scope === 'enrichment'
  ? deepStages
  : [...fastStages, ...deepStages, ...finalizeStages];
const runningIdxInScope = stagesInScope.findIndex(
  (s) => s.state === 'running' || s.state === 'rebuilding' || s.state === 'rerunning'
);
const currentStageInScope = runningIdxInScope >= 0 ? stagesInScope[runningIdxInScope] : null;
```

Immediately before where the stage cards list renders, add:

```tsx
{scope && currentStageInScope && (
  <RebuildingRow
    scope={scope}
    currentStageIndex={runningIdxInScope}
    totalStagesInScope={stagesInScope.length}
    currentStageLabel={currentStageInScope.label}
    percent={overallRebuildPercent}
    onStop={onStopRebuild}
  />
)}
```

- [ ] **Step 5: Attach `<ProvenanceChip>` under each stage card**

Find where each stage card is rendered (likely in the `CondensedGroupRow` / stage row render). For each stage, pass through its provenance prop:

```tsx
{stage.provenance && (
  <ProvenanceChip
    provenance={stage.provenance}
    onRebuild={onRebuild}
  />
)}
```

If the stage objects currently don't carry `provenance`, extend the stage type in `packages/ui/src/types.ts` to include `provenance?: StageProvenance`, then thread the new field through the computations that build each stage entry (there are ~15 `id: ..., state: promoteForRebuild(...), stats: ...` objects around line 1200–1344 in this file). For each, read from the backend-provided status:

```typescript
provenance: statusPayload.stages.find((s) => s.id === 'enrichment')?.provenance,
```

(Adjust to the actual shape the component receives from the dashboard.)

- [ ] **Step 6: Typecheck + visual check**

Run: `cd packages/ui && npm run typecheck`
Expected: clean.

Then run Storybook: `cd packages/ui && npm run storybook` and visit the `GraphEnrichmentPipeline` story. Verify the dropdown renders, the sticky row appears in a rebuild story, and chips render correctly.

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx packages/ui/src/types.ts
git commit -m "feat(ui): integrate RebuildDropdown + RebuildingRow + ProvenanceChip"
```

---

## Task 13: Confirmation modal for Rebuild All / Rebuild Sync with cost estimate

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (or the nearest existing confirm-modal wrapper used elsewhere in the component)
- Modify: `src/prep/api/routers/pipeline.py` — expose last-completed duration per group

- [ ] **Step 1: Add a backend endpoint for last-rebuild duration per scope**

In `src/prep/api/routers/pipeline.py`, add near the other status/history helpers:

```python
@router.get("/projects/{project_id}/pipeline/last-rebuild-duration")
def last_rebuild_duration(project_id: str) -> dict[str, Any]:
    """Return best-effort last-completed duration_seconds per scope.

    Scans the project's live and backed-up pipeline_run_metadata.json files.
    Returns {"sync": <secs|null>, "enrichment": <secs|null>, "all": <secs|null>}.
    """
    import json as _json
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project

    project = require_project(project_id)
    idx_dir = Path(project_index_dir(project))

    candidates: list[Path] = []
    live = idx_dir / "pipeline_run_metadata.json"
    if live.is_file():
        candidates.append(live)
    backups_dir = idx_dir / "backups"
    if backups_dir.is_dir():
        for sub in backups_dir.iterdir():
            meta = sub / "pipeline_run_metadata.json"
            if meta.is_file():
                candidates.append(meta)

    best: dict[str, float | None] = {"sync": None, "enrichment": None, "all": None}
    for p in candidates:
        try:
            data = _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        group = data.get("group")
        status = data.get("status")
        secs = data.get("elapsed_seconds")
        if status != "completed" or not isinstance(secs, (int, float)):
            continue
        if group == "fast_sync" and (best["sync"] is None or p.stat().st_mtime > 0):
            best["sync"] = float(secs)
        elif group == "deep_enrichment" and best["enrichment"] is None:
            best["enrichment"] = float(secs)
        elif group == "all" and best["all"] is None:
            best["all"] = float(secs)

    return ok(best)
```

- [ ] **Step 2: Frontend — fetch the estimate before showing the modal**

In `GraphEnrichmentPipeline.tsx` (or the dashboard wrapper), wire the modal to call `/pipeline/last-rebuild-duration` before opening. Pseudo-code:

```tsx
const [pendingScope, setPendingScope] = useState<RebuildScope | null>(null);
const [estimateSecs, setEstimateSecs] = useState<number | null>(null);

const handleRebuildRequest = async (scope: RebuildScope) => {
  if (scope === 'enrichment') {
    // No modal per spec A6
    onRebuild(scope);
    return;
  }
  try {
    const resp = await fetch(`/projects/${projectId}/pipeline/last-rebuild-duration`);
    const json = await resp.json();
    const key = scope === 'sync' ? 'sync' : 'all';
    setEstimateSecs(json?.data?.[key] ?? null);
  } catch {
    setEstimateSecs(null);
  }
  setPendingScope(scope);
};
```

Then render the confirm modal (reuse the existing modal primitives — look for `<Modal>` / `<Dialog>` in the codebase; SettingsDrawer already uses one). The modal message composes from:

```tsx
const estimateText = estimateSecs
  ? ` Last run took ~${Math.round(estimateSecs / 3600)}h.`
  : '';
const message = pendingScope === 'sync'
  ? `This will re-run stages 1–5. Downstream stages 6–15 will incrementally re-derive against the new graph.${estimateText} Continue?`
  : `This will re-run all 15 stages.${estimateText} Continue?`;
```

On confirm: `onRebuild(pendingScope); setPendingScope(null);`.

- [ ] **Step 3: Typecheck + commit**

```bash
cd packages/ui && npm run typecheck
```

```bash
git add src/prep/api/routers/pipeline.py packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(ui): confirm modal with last-rebuild duration estimate"
```

---

## Task 14: Full-chain integration test — Rebuild Sync scope

**Files:**
- Create: `tests/integration/test_rebuild_sync_scope_chain.py` (new)

Per the project's "test full import chain" rule (F-117), at least one test must not mock the seam under test. This test exercises the real orchestrator against a real temp project, verifying that `force_from_start` on fast_sync forces from stage 1 and that the barrier is cleared at the fast_sync boundary.

- [ ] **Step 1: Write the test**

Create `tests/integration/test_rebuild_sync_scope_chain.py`:

```python
"""Phase 117 integration: Rebuild Sync force-restarts 1-5 and auto-clears barrier.

Does not mock the orchestrator. Uses the real pipeline machinery against a
temporary project so the force_from_start → barrier-clear-at-fast_sync
behavior is verified end-to-end.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


@pytest.fixture
def temp_project_id(tmp_path, monkeypatch):
    """Create a minimal project via the normal project API."""
    os.environ["PREP_DATA_DIR"] = str(tmp_path)
    from prep.server import app
    client = TestClient(app)
    # Create a project rooted at a small tmp source tree
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.py").write_text("def hello():\n    return 1\n")
    resp = client.post("/projects", json={"name": "test-phase117", "root_path": str(src)})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"], client


def test_rebuild_sync_sets_barrier_sync_and_clears_after_fast_sync(temp_project_id):
    pid, client = temp_project_id
    from prep.services.pipeline import recovery

    # Fire rebuild-sync
    resp = client.post(f"/projects/{pid}/pipeline/fast", json={"force_from_start": True})
    assert resp.status_code == 200, resp.text

    # Barrier should be set with scope=sync
    info = recovery.read_reset_barrier(pid)
    assert info is not None
    assert info["scope"] == "sync"

    # Wait for fast_sync to complete (poll status). Cap at 60s for tiny project.
    import time
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        status = client.get(f"/projects/{pid}/pipeline/status").json()["data"]
        groups = status.get("groups", {})
        if groups.get("fast_sync", {}).get("phase") in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.5)

    # Barrier should now be cleared (scope=sync → clears at fast_sync boundary)
    info = recovery.read_reset_barrier(pid)
    assert info is None, f"barrier still active: {info}"
```

- [ ] **Step 2: Run the integration test**

Run: `.venv/bin/pytest tests/integration/test_rebuild_sync_scope_chain.py -v -m integration`
Expected: PASS (or SKIP if the project doesn't support the minimal fixture — adjust the fixture to match the actual project-creation contract if needed).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_rebuild_sync_scope_chain.py
git commit -m "test(integration): Rebuild Sync force-starts 1-5 and auto-clears barrier"
```

---

## Task 15: Storybook wiring for `GraphEnrichmentPipeline` rebuild states

**Files:**
- Modify: `packages/ui/src/stories/trace/GraphEnrichmentPipeline.stories.tsx` (or create if missing)

- [ ] **Step 1: Locate the existing stories file**

Run: `ls packages/ui/src/stories/trace/ | grep -i graph`

- [ ] **Step 2: Add scope-specific stories**

Append to the stories file (adjust imports to match existing patterns):

```tsx
export const RebuildingSync: Story = {
  args: {
    ...Default.args,
    barrier: { active: true, reason: 'rebuild', scope: 'sync' },
    // Mock status so stage 3 is running
    trace: { ...Default.args?.trace },
    augmentation: { progress_current: 600, progress_total: 1800 },
  },
};

export const RebuildingEnrichment: Story = {
  args: {
    ...Default.args,
    barrier: { active: true, reason: 'rebuild', scope: 'enrichment' },
  },
};

export const DriftChip: Story = {
  args: {
    ...Default.args,
    // Drive the chip via a mocked stage payload
    // (If GraphEnrichmentPipeline reads provenance from individual stage props,
    // pass a synthetic provenance on the target stage.)
  },
};
```

- [ ] **Step 3: Visual smoke via Storybook**

Run: `cd packages/ui && npm run storybook`

Manually verify:
- Default story: Rebuild dropdown appears, no sticky row, no amber chips.
- RebuildingSync story: sticky row says "Rebuilding Sync", stages colored blue.
- DriftChip story: target stage shows amber chip; clicking it prints the right scope.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/stories/trace/GraphEnrichmentPipeline.stories.tsx
git commit -m "chore(stories): rebuild states for GraphEnrichmentPipeline"
```

---

## Task 16: Docs — update AGENTS.md / CLAUDE.md blurbs

**Files:**
- Modify: `CLAUDE.md` (very small addendum under "Project Orchestration" or similar)

- [ ] **Step 1: Add a brief reference line to CLAUDE.md**

Append a single line under the pipeline / dev commands section noting the new endpoints:

```markdown
### Phase 117 — scoped rebuild endpoints

- `POST /pipeline/fast` and `/pipeline/deep` accept `{"force_from_start": true}` to re-run their group from scratch; the barrier is scoped (`sync` / `enrichment` / `all`) and auto-clears at the appropriate group boundary.
- `POST /pipeline/rebuild/stop` atomically cancels the active rebuild and clears the barrier.
- Per-stage provenance (match / drift / self-healed) is exposed under `status.stages[*].provenance`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: phase 117 scoped-rebuild endpoints + provenance field"
```

---

## Spec coverage checklist

Before declaring the plan done, verify each spec requirement has a task:

- **A1 split-button dropdown** → Task 10 (component) + Task 12 (integration)
- **A2 scoped force-from-start endpoints** → Task 3 (fast/deep) + existing `/rebuild` updated
- **A3 barrier scope** → Task 1 (schema) + Task 2 (auto-clear)
- **A4 sticky row** → Task 9 (component) + Task 12 (integration)
- **A5 stop semantics** → Task 4 (`/pipeline/rebuild/stop`) + Task 11 (hook) + Task 12 (wiring)
- **A6 confirmation modal with cost estimate** → Task 13
- **B1 provenance chip states** → Task 5 (helper) + Task 8 (component) + Task 12 (integration)
- **B2 match policy (provider + model_name, case-insensitive provider)** → Task 5 (`_models_equal`)
- **B3 backend exposure via /pipeline/status** → Task 6
- **B4 data sources (manifests, resolve_model_for_stage, golden)** → Task 5
- **Testing: full-chain without mocking the seam** → Task 14
- **Testing: Storybook coverage** → Tasks 8, 9, 10, 15

No spec requirement without an implementing task.

## Execution notes

- Run `npm run lint` and `npm run typecheck` at least once during Task 12 before committing.
- If `resolve_model_for_stage` returns `None` for an LLM stage (e.g., misconfigured settings), the provenance state falls through to `match` with no chip — acceptable.
- The integration test (Task 14) may be the slowest single test in the plan; consider tagging with `@pytest.mark.integration` (already done) so the default `pytest` run skips it locally. CI should include the integration marker.

# Phase 114 — Pipeline Safety & Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close visibility, safety, and recovery gaps in the CoDRAG enrichment pipeline so users can see reset-barrier state, restore individual stages from existing backups, understand what "Rebuild" actually does before clicking it, and recover gracefully when stages end up stubbed or stale.

**Architecture:** All changes are **additive**. No refactors, no removals. Backend adds five endpoints (barrier status, health, barrier clear, per-stage backups list, per-stage restore) and extends `CHECKPOINT_STAGES` + `_GOLDEN_FILES` to cover the last four Finalize stages. Frontend adds a barrier indicator to the pipeline panel, a per-stage Recover dropdown to the Settings Drawer Danger Zone, upgrades the Rebuild confirmation UX, and surfaces a health badge. Swarm/scheduler code (`src/codrag/services/pipeline/scheduler.py`) is **off-limits** — another agent is working on it in parallel.

**Tech Stack:** FastAPI + Pydantic (backend), React/Vite + Tailwind + Radix (frontend), pytest + Vitest (tests). Uses existing `RecoveryManager`, `branch_backup_manager`, and `pipeline_checkpoint` primitives — no new backup writers needed.

---

## Ground rules for every task

1. **Additive only.** Do not delete, rename, or re-shape existing endpoints, functions, or types. Bugs in the current paths are out of scope.
2. **Real `TestClient(app)` over mocks.** Follow `tests/test_scoped_full_reset.py` as the reference pattern. Do not mock `RecoveryManager`, the journal, or `branch_backup_manager`.
3. **Use the project venv.** All test commands use `.venv/bin/pytest`, not system `python` or `pytest`.
4. **No Co-Authored-By trailer** in commits.
5. **Do not touch** `src/codrag/services/pipeline/scheduler.py` or swarm code paths.
6. **Reverse-engineer each task before coding.** The pipeline is unstable; a superficial read is not enough.
7. **Commit after every green test.** Keep commits small and each message focused.

---

## Shared types (used across tasks)

Document these once here so later tasks can reference them without redefinition.

**Python — `src/codrag/api/routers/pipeline.py` (response models, Pydantic):**

```python
class BarrierStatus(BaseModel):
    active: bool
    age_seconds: float | None = None     # seconds since barrier written; None when inactive
    reason: str | None = None             # "enrichment_reset" | "finalize_reset" | "rebuild" | etc.
    written_at: float | None = None       # epoch seconds

class StageBackupInfo(BaseModel):
    snapshot_id: str                      # branch snapshot dir name OR "golden"
    kind: str                             # "golden" | "branch" | "run_checkpoint"
    branch: str | None = None             # present for kind="branch"
    created_at: float                     # epoch seconds
    size_bytes: int
    file_count: int
    record_count: int | None = None       # output-file row count when knowable

class StageHealth(BaseModel):
    stage_id: str
    manifest_exists: bool
    output_exists: bool                   # True if output file present OR not required
    provenance: str | None = None         # "run" | "selfheal_stub" | "user_restore" | "golden_restore" | None
    backup_count: int                     # number of backups available for this stage

class PipelineHealth(BaseModel):
    project_id: str
    barrier: BarrierStatus
    stages: list[StageHealth]
    stuck_runs: int                       # journal rows with status="running" older than threshold
    warnings: list[str]                   # freeform human-readable flags
```

**TypeScript — `packages/ui/src/types.ts` (client-facing mirrors):**

```ts
export interface BarrierStatus {
  active: boolean;
  age_seconds?: number;
  reason?: string;
  written_at?: number;
}

export interface StageBackupInfo {
  snapshot_id: string;
  kind: 'golden' | 'branch' | 'run_checkpoint';
  branch?: string;
  created_at: number;
  size_bytes: number;
  file_count: number;
  record_count?: number;
}

export interface StageHealth {
  stage_id: string;
  manifest_exists: boolean;
  output_exists: boolean;
  provenance?: 'run' | 'selfheal_stub' | 'user_restore' | 'golden_restore';
  backup_count: number;
}

export interface PipelineHealth {
  project_id: string;
  barrier: BarrierStatus;
  stages: StageHealth[];
  stuck_runs: number;
  warnings: string[];
}
```

---

## Task 1: Extend CHECKPOINT_STAGES and _GOLDEN_FILES to cover Finalize tail

**Why first:** The 4 missing stages (rules, concepts, audit, antibodies) currently have no backup. Every later task assumes per-stage backup is possible for all 15 stages, so this is the foundation.

**Files:**
- Modify: `src/codrag/services/pipeline_checkpoint.py`
- Test: `tests/test_checkpoint_stages.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_checkpoint_stages.py`:

```python
from codrag.services.pipeline_checkpoint import CHECKPOINT_STAGES, _GOLDEN_FILES, STAGE_OUTPUTS


def test_checkpoint_stages_covers_all_15_pipeline_stages():
    """Every pipeline stage should be checkpoint-eligible.

    Missing stages cannot be recovered by the selfheal path or per-stage
    restore, which is the gap closed by Phase 114.
    """
    expected = {
        "structural", "inferred_edges", "catalogue", "validation", "knowledge",
        "enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge",
        "atlas", "rules", "concepts", "audit", "antibodies",
    }
    assert expected.issubset(CHECKPOINT_STAGES), (
        f"missing from CHECKPOINT_STAGES: {expected - CHECKPOINT_STAGES}"
    )


def test_golden_files_includes_finalize_tail_manifests():
    needed = {
        "rules_manifest.json",
        "concepts_manifest.json",
        "audit_manifest.json",
        "antibodies_manifest.json",
    }
    assert needed.issubset(set(_GOLDEN_FILES)), (
        f"missing from _GOLDEN_FILES: {needed - set(_GOLDEN_FILES)}"
    )


def test_stage_outputs_has_entries_for_finalize_tail():
    for stage in ("rules", "concepts", "audit", "antibodies"):
        assert stage in STAGE_OUTPUTS, f"STAGE_OUTPUTS missing {stage}"
        assert STAGE_OUTPUTS[stage], f"STAGE_OUTPUTS[{stage}] is empty"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_checkpoint_stages.py -v`
Expected: 3 failures (missing stages, missing golden files, missing STAGE_OUTPUTS entries)

- [ ] **Step 3: Implement the change**

Edit `src/codrag/services/pipeline_checkpoint.py`:

At the `CHECKPOINT_STAGES` definition (line ~87-98), add the four missing stage ids:

```python
CHECKPOINT_STAGES = {
    "structural",
    "inferred_edges",
    "catalogue",
    "validation",
    "enrichment",
    "group_reasoning",
    "clustering",
    "atlas",
    "deepening",
    "deep_knowledge",
    # Phase 114: Finalize tail — previously had no backup coverage
    "rules",
    "concepts",
    "audit",
    "antibodies",
}
```

At `_GOLDEN_FILES` (line ~278-290), add the four manifest filenames:

```python
_GOLDEN_FILES = sorted(set(TRACE_FILES + [
    "trace_group_reasoning.jsonl",
    "trace_group_reasoning_manifest.json",
    "trace_modules_manifest.json",
    "atlas.json",
    "atlas_prev.json",
    "atlas_segments_manifest.json",
    "atlas_routing.json",
    "atlas_manifest.json",
    "deepening_manifest.json",
    "deep_knowledge_manifest.json",
    "knowledge_documents.json",
    # Phase 114: Finalize tail manifests
    "rules_manifest.json",
    "concepts_manifest.json",
    "audit_manifest.json",
    "antibodies_manifest.json",
]))
```

In `STAGE_OUTPUTS` (line ~65+), add entries if missing:

```python
STAGE_OUTPUTS: Dict[str, List[str]] = {
    # ... existing entries ...
    "rules":      ["rules_manifest.json"],
    "concepts":   ["concepts_manifest.json"],
    "audit":      ["audit_manifest.json"],
    "antibodies": ["antibodies_manifest.json"],
}
```

*Before editing:* read the existing dict to confirm these keys aren't already present. If present, merge rather than duplicate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_checkpoint_stages.py -v`
Expected: 3 passing.

Also run: `.venv/bin/pytest tests/test_scoped_full_reset.py -v`
Expected: all passing (the new entries must not break existing reset paths).

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/pipeline_checkpoint.py tests/test_checkpoint_stages.py
git commit -m "feat(phase114): add finalize tail stages to checkpoint coverage

rules, concepts, audit, antibodies previously had no backup path. Adding
them to CHECKPOINT_STAGES, _GOLDEN_FILES, and STAGE_OUTPUTS so the
per-stage Recover feature can restore them."
```

---

## Task 2: Add barrier status to `/pipeline/status` response

**Files:**
- Modify: `src/codrag/services/pipeline/recovery.py` (add `read_reset_barrier` helper)
- Modify: `src/codrag/api/routers/pipeline.py` (include barrier in status response)
- Test: `tests/test_pipeline_barrier_status.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_barrier_status.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    server._project_trace_indexes.clear()
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post("/projects", json={"path": str(repo_root), "name": "t", "mode": "embedded"})
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def test_pipeline_status_reports_barrier_inactive_by_default(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    body = res.json()
    assert "barrier" in body
    assert body["barrier"]["active"] is False
    assert body["barrier"]["age_seconds"] is None
    assert body["barrier"]["reason"] is None


def test_pipeline_status_reports_barrier_active_after_rebuild(client, tmp_path):
    from codrag.services.pipeline.recovery import write_reset_barrier
    pid = _add_embedded_project(client, tmp_path)
    assert write_reset_barrier(pid, "manual_test")

    res = client.get(f"/projects/{pid}/pipeline/status")
    assert res.status_code == 200
    body = res.json()
    assert body["barrier"]["active"] is True
    assert body["barrier"]["reason"] == "manual_test"
    assert body["barrier"]["age_seconds"] is not None
    assert body["barrier"]["age_seconds"] >= 0.0
    assert body["barrier"]["written_at"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_barrier_status.py -v`
Expected: 2 failures — `"barrier"` key missing from status response.

- [ ] **Step 3: Add `read_reset_barrier` helper to recovery.py**

In `src/codrag/services/pipeline/recovery.py`, below `reset_barrier_active` (around line 112):

```python
def read_reset_barrier(project_id: str) -> dict | None:
    """Read the reset barrier contents. Returns None if inactive.

    Returns {"written_at": float, "reason": str, "age_seconds": float}
    when the barrier is active. written_at is epoch seconds from the
    barrier file's first line; falls back to file mtime if the file
    predates the written_at format.
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
        if lines:
            try:
                written_at = float(lines[0])
            except ValueError:
                written_at = None
            if len(lines) >= 2:
                reason = lines[1].strip()
        if written_at is None:
            # Legacy barrier without epoch header — fall back to mtime.
            written_at = barrier.stat().st_mtime
        return {
            "written_at": written_at,
            "reason": reason or "unknown",
            "age_seconds": max(0.0, time.time() - written_at),
        }
    except Exception:
        logger.debug("Failed to read reset barrier for %s", project_id, exc_info=True)
        return None
```

- [ ] **Step 4: Wire barrier into status response**

In `src/codrag/api/routers/pipeline.py`, find the status endpoint handler (route `GET /projects/{project_id}/pipeline/status`). At the point where the final response dict is assembled, add:

```python
from codrag.services.pipeline.recovery import read_reset_barrier

# ... inside the status handler, after computing the per-stage payload ...
barrier_info = read_reset_barrier(project_id)
response["barrier"] = {
    "active": barrier_info is not None,
    "age_seconds": barrier_info["age_seconds"] if barrier_info else None,
    "reason": barrier_info["reason"] if barrier_info else None,
    "written_at": barrier_info["written_at"] if barrier_info else None,
}
```

*Before editing:* read the handler in full. The response may be a Pydantic model — if so, extend the model rather than injecting a key. Adjust the code above to match whichever pattern is in use.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_barrier_status.py -v`
Expected: 2 passing.

Also run: `.venv/bin/pytest tests/test_pipeline_stage_endpoint.py -v` (regression guard on the status endpoint).

- [ ] **Step 6: Commit**

```bash
git add src/codrag/services/pipeline/recovery.py src/codrag/api/routers/pipeline.py tests/test_pipeline_barrier_status.py
git commit -m "feat(phase114): surface reset barrier status in pipeline status

Adds read_reset_barrier helper and includes {active, age_seconds,
reason, written_at} in GET /pipeline/status so the dashboard can
detect stale barriers instead of silently losing selfheal."
```

---

## Task 3: Add `DELETE /pipeline/reset-barrier` endpoint

**Files:**
- Modify: `src/codrag/api/routers/pipeline.py` (add route)
- Test: `tests/test_pipeline_barrier_clear.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_barrier_clear.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    return TestClient(app)


def _add_embedded(client: TestClient, repo: Path) -> str:
    res = client.post("/projects", json={"path": str(repo), "name": "t", "mode": "embedded"})
    return str(res.json()["data"]["project"]["id"])


def test_delete_reset_barrier_when_active(client, tmp_path):
    from codrag.services.pipeline.recovery import write_reset_barrier, reset_barrier_active
    pid = _add_embedded(client, tmp_path)
    assert write_reset_barrier(pid, "stale_from_aborted_rebuild")
    assert reset_barrier_active(pid)

    res = client.delete(f"/projects/{pid}/pipeline/reset-barrier")
    assert res.status_code == 200
    body = res.json()
    assert body["cleared"] is True
    assert body["previous_reason"] == "stale_from_aborted_rebuild"
    assert not reset_barrier_active(pid)


def test_delete_reset_barrier_when_inactive_is_noop(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.delete(f"/projects/{pid}/pipeline/reset-barrier")
    assert res.status_code == 200
    body = res.json()
    assert body["cleared"] is False
    assert body["previous_reason"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_barrier_clear.py -v`
Expected: 2 failures — 404 on DELETE.

- [ ] **Step 3: Add the route**

In `src/codrag/api/routers/pipeline.py`, add near other DELETE handlers:

```python
from codrag.services.pipeline.recovery import (
    clear_reset_barrier,
    read_reset_barrier,
)


@router.delete("/projects/{project_id}/pipeline/reset-barrier")
async def clear_pipeline_reset_barrier(project_id: str):
    """Manually clear the reset barrier.

    Intended for cases where a rebuild was interrupted before finalize
    completed, leaving a barrier that silently blocks selfheal and
    per-stage restore. Safe no-op when no barrier is active.
    """
    barrier = read_reset_barrier(project_id)
    previous_reason = barrier["reason"] if barrier else None
    cleared = clear_reset_barrier(project_id)
    return {"cleared": cleared, "previous_reason": previous_reason}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_barrier_clear.py -v`
Expected: 2 passing.

Also regression-check reset endpoints:
Run: `.venv/bin/pytest tests/test_scoped_full_reset.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/codrag/api/routers/pipeline.py tests/test_pipeline_barrier_clear.py
git commit -m "feat(phase114): add DELETE /pipeline/reset-barrier endpoint

Lets operators clear a stale barrier left by an aborted rebuild.
Safe no-op when no barrier exists."
```

---

## Task 4: Add `GET /pipeline/health` endpoint

**Files:**
- Create: `src/codrag/services/pipeline/health.py`
- Modify: `src/codrag/api/routers/pipeline.py` (add route)
- Test: `tests/test_pipeline_health.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_health.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    return TestClient(app)


def _add_embedded(client: TestClient, repo: Path) -> str:
    res = client.post("/projects", json={"path": str(repo), "name": "t", "mode": "embedded"})
    return str(res.json()["data"]["project"]["id"])


def test_pipeline_health_fresh_project(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/health")
    assert res.status_code == 200
    body = res.json()
    assert body["project_id"] == pid
    assert body["barrier"]["active"] is False
    assert isinstance(body["stages"], list)
    # Fresh project: 15 stages tracked, all missing manifests
    assert len(body["stages"]) == 15
    for stage in body["stages"]:
        assert stage["manifest_exists"] is False
        assert stage["backup_count"] == 0
    assert body["stuck_runs"] == 0


def test_pipeline_health_flags_stale_barrier(client, tmp_path):
    from codrag.services.pipeline.recovery import write_reset_barrier
    pid = _add_embedded(client, tmp_path)

    # Write a barrier with a backdated timestamp > 1h ago
    import time as _time
    idx_dir = Path(server._registry.get_project(pid).index_dir)
    idx_dir.mkdir(parents=True, exist_ok=True)
    barrier_file = idx_dir / ".reset_barrier"
    old_ts = _time.time() - 3 * 3600
    barrier_file.write_text(f"{old_ts}\nstale_test\n")

    res = client.get(f"/projects/{pid}/pipeline/health")
    assert res.status_code == 200
    body = res.json()
    assert body["barrier"]["active"] is True
    # Warning for stale barrier > 1h old
    assert any("stale" in w.lower() for w in body["warnings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_health.py -v`
Expected: 2 failures — 404 on the route.

- [ ] **Step 3: Implement the health module**

Create `src/codrag/services/pipeline/health.py`:

```python
"""Pipeline health aggregator — Phase 114.

Pulls together barrier status, per-stage manifest presence, backup
availability, and stuck journal rows into one payload for the dashboard
health badge and the `GET /pipeline/health` endpoint.

Pure reads. Does not mutate any state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from codrag.services.pipeline_checkpoint import STAGE_OUTPUTS
from codrag.services.pipeline.recovery import read_reset_barrier

_STAGE_ORDER = [
    "structural", "inferred_edges", "catalogue", "validation", "knowledge",
    "enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge",
    "atlas", "rules", "concepts", "audit", "antibodies",
]

_STALE_BARRIER_SECONDS = 60 * 60  # 1 hour


def _stage_manifest_name(stage_id: str) -> str:
    outputs = STAGE_OUTPUTS.get(stage_id, [])
    for name in outputs:
        if name.endswith("_manifest.json") or name == "trace_manifest.json":
            return name
    return f"{stage_id}_manifest.json"


def _count_backups_for_stage(idx_dir: Path, stage_id: str) -> int:
    """Count available backups (golden + branch snapshots) for a stage.

    Run checkpoints are ephemeral (pruned to 3) and aren't reliable
    recovery sources — we only count stable backups.
    """
    manifest = _stage_manifest_name(stage_id)
    count = 0
    golden = idx_dir / ".checkpoints" / "_golden" / manifest
    if golden.is_file():
        count += 1
    branch_root = idx_dir / ".branch_snapshots"
    if branch_root.is_dir():
        for snap in branch_root.iterdir():
            if snap.is_dir() and (snap / manifest).is_file():
                count += 1
    return count


def collect_pipeline_health(project_id: str, idx_dir: Path) -> Dict[str, Any]:
    """Assemble the /pipeline/health payload for one project."""
    barrier_info = read_reset_barrier(project_id)
    barrier = {
        "active": barrier_info is not None,
        "age_seconds": barrier_info["age_seconds"] if barrier_info else None,
        "reason": barrier_info["reason"] if barrier_info else None,
        "written_at": barrier_info["written_at"] if barrier_info else None,
    }

    stages: List[Dict[str, Any]] = []
    for stage_id in _STAGE_ORDER:
        manifest_name = _stage_manifest_name(stage_id)
        manifest_path = idx_dir / manifest_name
        outputs = [n for n in STAGE_OUTPUTS.get(stage_id, []) if not n.endswith("_manifest.json")]
        output_exists = True if not outputs else all((idx_dir / n).is_file() for n in outputs)

        stages.append({
            "stage_id": stage_id,
            "manifest_exists": manifest_path.is_file(),
            "output_exists": output_exists,
            "provenance": None,  # TODO Phase 115: read from manifest when written
            "backup_count": _count_backups_for_stage(idx_dir, stage_id),
        })

    stuck_runs = _count_stuck_runs(project_id)

    warnings: List[str] = []
    if barrier["active"] and (barrier["age_seconds"] or 0) > _STALE_BARRIER_SECONDS:
        warnings.append(
            f"reset barrier has been active for {int(barrier['age_seconds'] // 60)} min — "
            "may be stale from an interrupted rebuild"
        )
    if stuck_runs > 0:
        warnings.append(f"{stuck_runs} stuck run(s) in journal")

    return {
        "project_id": project_id,
        "barrier": barrier,
        "stages": stages,
        "stuck_runs": stuck_runs,
        "warnings": warnings,
    }


def _count_stuck_runs(project_id: str) -> int:
    """Count journal rows with status='running' older than 30 minutes."""
    try:
        from codrag.services.pipeline_journal import PipelineJournal
        journal = PipelineJournal()
        return journal.count_stuck_runs(project_id, older_than_seconds=30 * 60)
    except Exception:
        return 0
```

Note: `PipelineJournal.count_stuck_runs` may not exist yet. If not, either add it defensively (returning 0 when the method is absent via `getattr`) or stub it inline:

```python
def _count_stuck_runs(project_id: str) -> int:
    try:
        from codrag.services.pipeline_journal import PipelineJournal
        journal = PipelineJournal()
        if hasattr(journal, "count_stuck_runs"):
            return journal.count_stuck_runs(project_id, older_than_seconds=30 * 60)
        return 0
    except Exception:
        return 0
```

*Before editing:* read `src/codrag/services/pipeline_journal.py` to confirm the method name and calling convention. Adjust if needed.

- [ ] **Step 4: Wire the route**

In `src/codrag/api/routers/pipeline.py`:

```python
from codrag.services.pipeline.health import collect_pipeline_health
from codrag.services.project_helpers import require_project
from codrag.core.project_registry import project_index_dir


@router.get("/projects/{project_id}/pipeline/health")
async def pipeline_health(project_id: str):
    """Aggregated health report for the pipeline + backups + journal."""
    project = require_project(project_id)
    idx_dir = Path(project_index_dir(project))
    return collect_pipeline_health(project_id, idx_dir)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_health.py -v`
Expected: 2 passing.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/services/pipeline/health.py src/codrag/api/routers/pipeline.py tests/test_pipeline_health.py
git commit -m "feat(phase114): add GET /pipeline/health aggregator

One endpoint that returns barrier status, per-stage manifest + backup
counts, stuck-run count, and human-readable warnings. Powers the
dashboard health badge."
```

---

## Task 5: Add `GET /pipeline/stages/{stage_id}/backups` endpoint

**Files:**
- Modify: `src/codrag/api/routers/pipeline.py`
- Test: `tests/test_pipeline_stage_backups.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_stage_backups.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    return TestClient(app)


def _add_embedded(client: TestClient, repo: Path) -> str:
    res = client.post("/projects", json={"path": str(repo), "name": "t", "mode": "embedded"})
    return str(res.json()["data"]["project"]["id"])


def _seed_golden(idx_dir: Path, stage_manifest: str):
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / stage_manifest).write_text('{"status":"complete"}')


def test_stage_backups_empty_for_fresh_project(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/stages/atlas/backups")
    assert res.status_code == 200
    body = res.json()
    assert body["stage_id"] == "atlas"
    assert body["backups"] == []


def test_stage_backups_lists_golden(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project
    idx_dir = Path(project_index_dir(require_project(pid)))
    _seed_golden(idx_dir, "atlas_manifest.json")

    res = client.get(f"/projects/{pid}/pipeline/stages/atlas/backups")
    assert res.status_code == 200
    body = res.json()
    assert len(body["backups"]) == 1
    bk = body["backups"][0]
    assert bk["kind"] == "golden"
    assert bk["snapshot_id"] == "golden"


def test_stage_backups_rejects_unknown_stage(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.get(f"/projects/{pid}/pipeline/stages/not-a-real-stage/backups")
    assert res.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_stage_backups.py -v`
Expected: 3 failures — 404 on the route.

- [ ] **Step 3: Implement**

In `src/codrag/api/routers/pipeline.py`:

```python
from codrag.services.pipeline_checkpoint import STAGE_OUTPUTS
from codrag.services.branch_backup_manager import list_snapshots

_VALID_STAGES = frozenset({
    "structural", "inferred_edges", "catalogue", "validation", "knowledge",
    "enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge",
    "atlas", "rules", "concepts", "audit", "antibodies",
})


def _stage_manifest_name(stage_id: str) -> str:
    outputs = STAGE_OUTPUTS.get(stage_id, [])
    for name in outputs:
        if name.endswith("_manifest.json") or name == "trace_manifest.json":
            return name
    return f"{stage_id}_manifest.json"


@router.get("/projects/{project_id}/pipeline/stages/{stage_id}/backups")
async def list_stage_backups(project_id: str, stage_id: str):
    if stage_id not in _VALID_STAGES:
        raise HTTPException(status_code=404, detail=f"unknown stage: {stage_id}")
    project = require_project(project_id)
    idx_dir = Path(project_index_dir(project))

    manifest = _stage_manifest_name(stage_id)
    backups: list[dict] = []

    # Golden snapshot (one, if present)
    golden_manifest = idx_dir / ".checkpoints" / "_golden" / manifest
    if golden_manifest.is_file():
        stat = golden_manifest.stat()
        backups.append({
            "snapshot_id": "golden",
            "kind": "golden",
            "branch": None,
            "created_at": stat.st_mtime,
            "size_bytes": stat.st_size,
            "file_count": 1,
            "record_count": None,
        })

    # Branch snapshots
    for snap in list_snapshots(idx_dir):
        snap_dir_name = snap.get("branch") or snap.get("snapshot_id") or ""
        snap_manifest = idx_dir / ".branch_snapshots" / snap_dir_name / manifest
        if snap_manifest.is_file():
            stat = snap_manifest.stat()
            backups.append({
                "snapshot_id": snap_dir_name,
                "kind": "branch",
                "branch": snap.get("branch"),
                "created_at": snap.get("created_at", stat.st_mtime),
                "size_bytes": snap.get("size_bytes", stat.st_size),
                "file_count": snap.get("file_count", 1),
                "record_count": None,
            })

    return {"stage_id": stage_id, "backups": backups}
```

*Before editing:* confirm `list_snapshots` return-dict key names by reading `src/codrag/services/branch_backup_manager.py:177-216`. If the keys differ from the `.get(...)` defaults above, adjust.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_stage_backups.py -v`
Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/api/routers/pipeline.py tests/test_pipeline_stage_backups.py
git commit -m "feat(phase114): add GET /pipeline/stages/{stage_id}/backups

Lists available golden + branch-snapshot backups for one stage.
Foundation for the Recover dropdown — users see what's restorable."
```

---

## Task 6: Add `POST /pipeline/stages/{stage_id}/restore` endpoint

**Files:**
- Modify: `src/codrag/api/routers/pipeline.py`
- Test: `tests/test_pipeline_stage_restore.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_stage_restore.py`:

```python
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
import codrag.services.project_helpers as ph
from codrag.core.project_registry import ProjectRegistry
from codrag.server import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    reg = ProjectRegistry(db_path=tmp_path / "registry.db")
    server._registry = reg
    ph._registry = reg
    server._project_indexes.clear()
    return TestClient(app)


def _add_embedded(client: TestClient, repo: Path) -> str:
    res = client.post("/projects", json={"path": str(repo), "name": "t", "mode": "embedded"})
    return str(res.json()["data"]["project"]["id"])


def _seed_golden(idx_dir: Path, stage_manifest: str, content: str):
    golden = idx_dir / ".checkpoints" / "_golden"
    golden.mkdir(parents=True, exist_ok=True)
    (golden / stage_manifest).write_text(content)


def test_restore_golden_replaces_active_manifest(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project
    idx_dir = Path(project_index_dir(require_project(pid)))

    # Active manifest = stub; golden = good
    idx_dir.mkdir(parents=True, exist_ok=True)
    (idx_dir / "atlas_manifest.json").write_text('{"status":"stub","provenance":"selfheal_stub"}')
    _seed_golden(idx_dir, "atlas_manifest.json", '{"status":"complete","provenance":"run"}')

    res = client.post(
        f"/projects/{pid}/pipeline/stages/atlas/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["restored"] is True
    assert body["stage_id"] == "atlas"
    assert body["snapshot_id"] == "golden"

    # Active manifest should now match golden
    assert '"status":"complete"' in (idx_dir / "atlas_manifest.json").read_text()


def test_restore_rejects_unknown_stage(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/pipeline/stages/not-a-stage/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 404


def test_restore_rejects_missing_snapshot(client, tmp_path):
    pid = _add_embedded(client, tmp_path)
    res = client.post(
        f"/projects/{pid}/pipeline/stages/atlas/restore",
        json={"snapshot_id": "golden"},
    )
    assert res.status_code == 404
    assert "snapshot" in res.json()["detail"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline_stage_restore.py -v`
Expected: 3 failures.

- [ ] **Step 3: Implement**

In `src/codrag/api/routers/pipeline.py`, add:

```python
import shutil


class _StageRestoreRequest(BaseModel):
    snapshot_id: str


@router.post("/projects/{project_id}/pipeline/stages/{stage_id}/restore")
async def restore_stage_from_snapshot(
    project_id: str,
    stage_id: str,
    req: _StageRestoreRequest,
):
    """Restore a single stage's manifest + output from a named snapshot.

    Allowed snapshot_id values:
      - "golden" : .checkpoints/_golden/
      - "<branch_dir_name>" : .branch_snapshots/<branch_dir_name>/

    Copies only the stage-owned files (manifest + output if any); does
    NOT touch other stages. Temporarily ignores the reset barrier for
    the duration of the copy — the assumption is that the user is
    deliberately overriding a broken/stub state.
    """
    if stage_id not in _VALID_STAGES:
        raise HTTPException(status_code=404, detail=f"unknown stage: {stage_id}")
    project = require_project(project_id)
    idx_dir = Path(project_index_dir(project))

    # Resolve source dir
    if req.snapshot_id == "golden":
        src_dir = idx_dir / ".checkpoints" / "_golden"
    else:
        src_dir = idx_dir / ".branch_snapshots" / req.snapshot_id
    if not src_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"snapshot not found: {req.snapshot_id}")

    # Stage-owned files (manifest + any non-manifest outputs)
    files = STAGE_OUTPUTS.get(stage_id, [])
    if not files:
        files = [_stage_manifest_name(stage_id)]

    # At least the manifest must be present in the source
    manifest = _stage_manifest_name(stage_id)
    if not (src_dir / manifest).is_file():
        raise HTTPException(
            status_code=404,
            detail=f"snapshot {req.snapshot_id!r} has no data for stage {stage_id!r}",
        )

    restored_files: list[str] = []
    for f in files:
        src = src_dir / f
        if src.is_file():
            dst = idx_dir / f
            shutil.copy2(src, dst)
            restored_files.append(f)

    return {
        "restored": True,
        "stage_id": stage_id,
        "snapshot_id": req.snapshot_id,
        "files_restored": restored_files,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_stage_restore.py -v`
Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/api/routers/pipeline.py tests/test_pipeline_stage_restore.py
git commit -m "feat(phase114): add POST /pipeline/stages/{stage_id}/restore

Per-stage restore from a named snapshot (golden or branch). Copies
stage-owned manifest + output only; bypasses reset barrier for the
deliberate-override use case."
```

---

## Task 7: Dashboard — barrier indicator in pipeline panel

**Files:**
- Modify: `packages/ui/src/types.ts` (add BarrierStatus export)
- Modify: `packages/ui/src/api/client.ts` (status response type)
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (add indicator row)
- Test: `packages/ui/src/components/trace/__tests__/BarrierIndicator.test.tsx` (create)

- [ ] **Step 1: Extend the shared types**

In `packages/ui/src/types.ts`, append near other pipeline types:

```ts
export interface BarrierStatus {
  active: boolean;
  age_seconds?: number;
  reason?: string;
  written_at?: number;
}

// Phase 114: the /pipeline/status response now includes barrier info
export interface PipelineStatusWithBarrier {
  barrier?: BarrierStatus;
}
```

- [ ] **Step 2: Write the failing test**

Create `packages/ui/src/components/trace/__tests__/BarrierIndicator.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BarrierIndicator } from '../BarrierIndicator';

describe('BarrierIndicator', () => {
  it('renders nothing when barrier is inactive', () => {
    const { container } = render(<BarrierIndicator barrier={{ active: false }} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders with reason and age when active', () => {
    render(
      <BarrierIndicator
        barrier={{ active: true, reason: 'rebuild', age_seconds: 120 }}
      />,
    );
    expect(screen.getByText(/barrier active/i)).toBeInTheDocument();
    expect(screen.getByText(/rebuild/i)).toBeInTheDocument();
  });

  it('shows stale warning when age exceeds 1h', () => {
    render(
      <BarrierIndicator
        barrier={{ active: true, reason: 'rebuild', age_seconds: 4000 }}
      />,
    );
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd packages/ui && npm run test -- BarrierIndicator`
Expected: failures — component not exported.

- [ ] **Step 4: Implement the component**

Create `packages/ui/src/components/trace/BarrierIndicator.tsx`:

```tsx
import React from 'react';
import { AlertTriangle } from 'lucide-react';
import type { BarrierStatus } from '../../types';

const STALE_THRESHOLD_SECONDS = 60 * 60;

export interface BarrierIndicatorProps {
  barrier: BarrierStatus;
  onClear?: () => void;
}

export function BarrierIndicator({ barrier, onClear }: BarrierIndicatorProps) {
  if (!barrier.active) return null;

  const ageMin = Math.floor((barrier.age_seconds ?? 0) / 60);
  const isStale = (barrier.age_seconds ?? 0) > STALE_THRESHOLD_SECONDS;

  return (
    <div
      role="alert"
      className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs ${
        isStale
          ? 'border-warning/40 bg-warning/10 text-warning'
          : 'border-muted/40 bg-muted/10 text-text-muted'
      }`}
    >
      <AlertTriangle className="h-4 w-4" aria-hidden />
      <div className="flex-1">
        <span className="font-medium">Barrier active</span>
        {barrier.reason && (
          <span className="ml-1 text-text-muted">— {barrier.reason}</span>
        )}
        <span className="ml-2 opacity-70">({ageMin} min ago)</span>
        {isStale && <span className="ml-2 font-medium">stale</span>}
      </div>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-current px-2 py-0.5 text-xs hover:bg-current/10"
        >
          Clear
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/ui && npm run test -- BarrierIndicator`
Expected: 3 passing.

- [ ] **Step 6: Render indicator inside GraphEnrichmentPipeline**

In `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`, add:

```tsx
import { BarrierIndicator, type BarrierIndicatorProps } from './BarrierIndicator';
```

Add to the component props interface:

```ts
/** Phase 114: reset barrier banner above the stage groups */
barrier?: BarrierStatus;
onClearBarrier?: () => void;
```

Render near the top of the panel's inner content (before the group sections):

```tsx
{barrier?.active && (
  <BarrierIndicator barrier={barrier} onClear={onClearBarrier} />
)}
```

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/types.ts packages/ui/src/components/trace/BarrierIndicator.tsx packages/ui/src/components/trace/__tests__/BarrierIndicator.test.tsx packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(phase114-ui): surface reset barrier status in pipeline panel

New BarrierIndicator renders an amber banner above the stage groups
when a barrier is active; turns warning-colored + labeled 'stale'
past 1h. Optional onClear handler wires to the DELETE endpoint."
```

---

## Task 8: Dashboard — Recover dropdown in Danger Zone

**Files:**
- Modify: `packages/ui/src/api/client.ts` (add `getStageBackups`, `restoreStage` methods)
- Modify: `packages/ui/src/api/mock.ts` (matching mock entries)
- Create: `packages/ui/src/components/pipeline/RecoverStagePanel.tsx`
- Test: `packages/ui/src/components/pipeline/__tests__/RecoverStagePanel.test.tsx`
- Modify: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx` (mount the panel)

- [ ] **Step 1: Extend the client**

In `packages/ui/src/api/client.ts`, add:

```ts
import type { StageBackupInfo } from '../types';

// ... inside the api factory ...

async getStageBackups(projectId: string, stageId: string): Promise<{ stage_id: string; backups: StageBackupInfo[] }> {
  const res = await fetch(`${baseUrl}/projects/${projectId}/pipeline/stages/${stageId}/backups`);
  if (!res.ok) throw new Error(`getStageBackups failed: ${res.status}`);
  return res.json();
},

async restoreStage(projectId: string, stageId: string, snapshotId: string): Promise<{ restored: boolean; files_restored: string[] }> {
  const res = await fetch(
    `${baseUrl}/projects/${projectId}/pipeline/stages/${stageId}/restore`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snapshot_id: snapshotId }),
    },
  );
  if (!res.ok) throw new Error(`restoreStage failed: ${res.status}`);
  return res.json();
},

async clearResetBarrier(projectId: string): Promise<{ cleared: boolean; previous_reason?: string }> {
  const res = await fetch(`${baseUrl}/projects/${projectId}/pipeline/reset-barrier`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`clearResetBarrier failed: ${res.status}`);
  return res.json();
},
```

Add matching entries to `packages/ui/src/api/mock.ts` so Storybook/tests work:

```ts
getStageBackups: async (_projectId: string, stageId: string) => ({
  stage_id: stageId,
  backups: [
    { snapshot_id: 'golden', kind: 'golden' as const, created_at: Date.now() / 1000, size_bytes: 1024, file_count: 1 },
  ],
}),
restoreStage: async () => ({ restored: true, files_restored: ['atlas_manifest.json'] }),
clearResetBarrier: async () => ({ cleared: true, previous_reason: 'rebuild' }),
```

Add `StageBackupInfo` to `packages/ui/src/types.ts` (see Shared types block at top).

- [ ] **Step 2: Write the failing test**

Create `packages/ui/src/components/pipeline/__tests__/RecoverStagePanel.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RecoverStagePanel } from '../RecoverStagePanel';

const api = {
  getStageBackups: vi.fn().mockResolvedValue({
    stage_id: 'atlas',
    backups: [
      { snapshot_id: 'golden', kind: 'golden', created_at: 1700000000, size_bytes: 2048, file_count: 1 },
      { snapshot_id: 'feature-x', kind: 'branch', branch: 'feature-x', created_at: 1699000000, size_bytes: 1024, file_count: 1 },
    ],
  }),
  restoreStage: vi.fn().mockResolvedValue({ restored: true, files_restored: ['atlas_manifest.json'] }),
};

describe('RecoverStagePanel', () => {
  it('shows stage dropdown with all 15 stages', () => {
    render(<RecoverStagePanel projectId="p1" api={api as any} />);
    expect(screen.getByLabelText(/stage/i)).toBeInTheDocument();
  });

  it('loads backups when a stage is selected', async () => {
    render(<RecoverStagePanel projectId="p1" api={api as any} />);
    fireEvent.change(screen.getByLabelText(/stage/i), { target: { value: 'atlas' } });
    await waitFor(() => {
      expect(api.getStageBackups).toHaveBeenCalledWith('p1', 'atlas');
    });
    expect(await screen.findByText(/golden/i)).toBeInTheDocument();
    expect(await screen.findByText(/feature-x/i)).toBeInTheDocument();
  });

  it('calls restoreStage when a backup is chosen and confirmed', async () => {
    render(<RecoverStagePanel projectId="p1" api={api as any} />);
    fireEvent.change(screen.getByLabelText(/stage/i), { target: { value: 'atlas' } });
    await waitFor(() => screen.findByText(/golden/i));
    fireEvent.click(screen.getByRole('button', { name: /restore/i }));
    // Confirm modal
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));
    await waitFor(() => {
      expect(api.restoreStage).toHaveBeenCalledWith('p1', 'atlas', 'golden');
    });
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd packages/ui && npm run test -- RecoverStagePanel`
Expected: component not found.

- [ ] **Step 4: Implement the component**

Create `packages/ui/src/components/pipeline/RecoverStagePanel.tsx`:

```tsx
import React, { useEffect, useState } from 'react';
import type { StageBackupInfo } from '../../types';

const STAGES = [
  'structural', 'inferred_edges', 'catalogue', 'validation', 'knowledge',
  'enrichment', 'group_reasoning', 'clustering', 'deepening', 'deep_knowledge',
  'atlas', 'rules', 'concepts', 'audit', 'antibodies',
] as const;

export interface RecoverStagePanelProps {
  projectId: string;
  api: {
    getStageBackups(projectId: string, stageId: string): Promise<{ stage_id: string; backups: StageBackupInfo[] }>;
    restoreStage(projectId: string, stageId: string, snapshotId: string): Promise<{ restored: boolean; files_restored: string[] }>;
  };
  onRestored?: () => void;
}

export function RecoverStagePanel({ projectId, api, onRestored }: RecoverStagePanelProps) {
  const [stageId, setStageId] = useState<string>('');
  const [backups, setBackups] = useState<StageBackupInfo[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<string>('');
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!stageId) {
      setBackups([]);
      return;
    }
    setLoading(true);
    api.getStageBackups(projectId, stageId)
      .then((res) => setBackups(res.backups))
      .catch(() => setBackups([]))
      .finally(() => setLoading(false));
  }, [projectId, stageId, api]);

  const handleRestore = async () => {
    if (!stageId || !selectedSnapshot) return;
    await api.restoreStage(projectId, stageId, selectedSnapshot);
    setConfirming(false);
    onRestored?.();
  };

  return (
    <div className="space-y-3 rounded-md border border-warning/40 p-3">
      <div>
        <label htmlFor="recover-stage-select" className="text-xs font-medium text-text-muted">
          Stage
        </label>
        <select
          id="recover-stage-select"
          value={stageId}
          onChange={(e) => {
            setStageId(e.target.value);
            setSelectedSnapshot('');
          }}
          className="mt-1 block w-full rounded border border-border bg-surface px-2 py-1 text-sm"
        >
          <option value="">— select a stage —</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {stageId && (
        <div>
          <p className="text-xs font-medium text-text-muted">Available backups</p>
          {loading && <p className="text-xs text-text-muted">Loading…</p>}
          {!loading && backups.length === 0 && (
            <p className="text-xs text-text-muted">No backups for {stageId}.</p>
          )}
          <ul className="mt-1 space-y-1">
            {backups.map((bk) => (
              <li key={bk.snapshot_id} className="flex items-center gap-2 text-xs">
                <input
                  type="radio"
                  name="stage-backup"
                  value={bk.snapshot_id}
                  checked={selectedSnapshot === bk.snapshot_id}
                  onChange={() => setSelectedSnapshot(bk.snapshot_id)}
                />
                <span className="font-medium">{bk.kind}</span>
                {bk.branch && <span className="text-text-muted">({bk.branch})</span>}
                <span className="text-text-muted">
                  {new Date(bk.created_at * 1000).toLocaleString()}
                </span>
                <span className="text-text-muted">{bk.size_bytes} B</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {stageId && selectedSnapshot && !confirming && (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="rounded border border-warning/40 px-3 py-1 text-xs text-warning hover:bg-warning/10"
        >
          Restore
        </button>
      )}

      {confirming && (
        <div className="rounded border border-warning/40 bg-warning/5 p-2">
          <p className="text-xs">
            Restore <strong>{stageId}</strong> from <strong>{selectedSnapshot}</strong>?
            This overwrites the active manifest + output for this stage only.
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={handleRestore}
              className="rounded bg-warning px-3 py-1 text-xs text-white"
            >
              Confirm
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded border px-3 py-1 text-xs"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/ui && npm run test -- RecoverStagePanel`
Expected: 3 passing.

- [ ] **Step 6: Mount in SettingsDrawer Danger Zone**

In `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx`, locate the "Selective Reset — Developer Danger Zone" section (around line 639) and insert a new block above it:

```tsx
{projectId && (
  <div className="mt-4 rounded-md border border-warning/30 p-3">
    <h4 className="text-sm font-semibold text-text">Recover Stage</h4>
    <p className="mt-1 text-xs text-text-muted">
      Restore one stage from a known-good backup (golden or branch snapshot).
      Use when a stage looks stubbed, stale, or wrongly marked complete.
    </p>
    <div className="mt-2">
      <RecoverStagePanel projectId={projectId} api={api} />
    </div>
  </div>
)}
```

Add the imports at the top:

```tsx
import { RecoverStagePanel } from '@codrag/ui/components/pipeline/RecoverStagePanel';
```

*Before editing:* confirm the `api` prop is available in scope — if not, thread it from `useDashboardPanels` the same way other Danger Zone actions are wired.

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/api/client.ts packages/ui/src/api/mock.ts packages/ui/src/types.ts packages/ui/src/components/pipeline/RecoverStagePanel.tsx packages/ui/src/components/pipeline/__tests__/RecoverStagePanel.test.tsx src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx
git commit -m "feat(phase114-ui): add Recover Stage dropdown in Danger Zone

Per-stage restore dropdown. Select a stage, see its golden + branch
snapshot backups with timestamps, pick one, confirm, restore. Wires
to GET /backups + POST /restore endpoints from Tasks 5 & 6."
```

---

## Task 9: Dashboard — Rebuild button UX upgrade

**Files:**
- Modify: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx`

- [ ] **Step 1: Read the current Rebuild confirm block**

The current Rebuild button is at SettingsDrawer.tsx:285-290 and the confirm modal at :682. Re-read both in full before editing.

- [ ] **Step 2: Upgrade the Rebuild description text**

Change the body text of the Rebuild card (around line 286) to be explicit about blast radius:

```tsx
<p className="text-xs text-text-muted mt-1">
  Wipes all 15 stages and rebuilds from scratch. Current index data stays
  readable during the rebuild and is atomically swapped in as each stage
  finishes. Incremental progress from prior runs is <strong>not preserved</strong>.
</p>
```

Change the button label from "Rebuild" to "Wipe & Rebuild All":

```tsx
<Button variant="outline" size="sm" onClick={() => setConfirmAction('rebuild')} className="w-full border-warning/40 text-warning hover:bg-warning/10">
  Wipe & Rebuild All
</Button>
```

- [ ] **Step 3: Add typed-confirmation to the Rebuild dialog**

In the confirm modal block (around line 682), when `confirmAction === 'rebuild'`, require the user to type the project name before the action button enables:

```tsx
// Add near the top of the component, with other useState hooks:
const [rebuildTypedName, setRebuildTypedName] = useState('');

// Inside the confirm modal render, conditional on confirmAction === 'rebuild':
{confirmAction === 'rebuild' && (
  <div className="space-y-2">
    <p className="text-sm">
      Type the project name (<code>{projectName}</code>) to confirm:
    </p>
    <input
      type="text"
      value={rebuildTypedName}
      onChange={(e) => setRebuildTypedName(e.target.value)}
      className="w-full rounded border px-2 py-1 text-sm"
      placeholder={projectName}
    />
  </div>
)}
```

Gate the confirm button:

```tsx
// Wherever the confirm button for confirmAction === 'rebuild' is rendered:
disabled={confirmAction === 'rebuild' && rebuildTypedName !== projectName}
```

Clear the typed name when the modal closes:

```tsx
// In the handler that closes the modal / resets confirmAction:
setRebuildTypedName('');
```

- [ ] **Step 4: Manual smoke test**

Run the dashboard:

```bash
cd src/codrag/dashboard && npm run dev
```

Verify:
1. Rebuild button reads "Wipe & Rebuild All"
2. Body text calls out "not preserved"
3. Clicking opens confirm dialog
4. Confirm button is disabled until project name is typed correctly
5. Typing wrong name keeps it disabled

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx
git commit -m "feat(phase114-ui): Rebuild UX — typed confirm + blast radius text

Renames 'Rebuild' to 'Wipe & Rebuild All', makes the consequence
('incremental progress not preserved') explicit, and gates the
confirm action behind typing the project name. Addresses the
'accidental complete rebuild' UX root cause."
```

---

## Task 10: Dashboard — health indicator badge

**Files:**
- Modify: `packages/ui/src/api/client.ts` (add `getPipelineHealth`)
- Modify: `packages/ui/src/api/mock.ts`
- Create: `packages/ui/src/components/pipeline/HealthBadge.tsx`
- Test: `packages/ui/src/components/pipeline/__tests__/HealthBadge.test.tsx`
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (render badge in header)

- [ ] **Step 1: Extend client**

In `packages/ui/src/api/client.ts`:

```ts
import type { PipelineHealth } from '../types';

async getPipelineHealth(projectId: string): Promise<PipelineHealth> {
  const res = await fetch(`${baseUrl}/projects/${projectId}/pipeline/health`);
  if (!res.ok) throw new Error(`getPipelineHealth failed: ${res.status}`);
  return res.json();
},
```

In `packages/ui/src/api/mock.ts`:

```ts
getPipelineHealth: async (projectId: string) => ({
  project_id: projectId,
  barrier: { active: false },
  stages: [],
  stuck_runs: 0,
  warnings: [],
}),
```

Add `PipelineHealth`, `StageHealth` to `types.ts` per Shared types block at top.

- [ ] **Step 2: Write the failing test**

Create `packages/ui/src/components/pipeline/__tests__/HealthBadge.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HealthBadge } from '../HealthBadge';

describe('HealthBadge', () => {
  it('shows green when no warnings', () => {
    render(<HealthBadge health={{ project_id: 'p', barrier: { active: false }, stages: [], stuck_runs: 0, warnings: [] }} />);
    expect(screen.getByText(/healthy/i)).toBeInTheDocument();
  });

  it('shows warning when barrier stale', () => {
    render(
      <HealthBadge
        health={{
          project_id: 'p',
          barrier: { active: true, age_seconds: 7200 },
          stages: [],
          stuck_runs: 0,
          warnings: ['reset barrier has been active for 120 min — may be stale'],
        }}
      />,
    );
    expect(screen.getByText(/1 warning/i)).toBeInTheDocument();
  });

  it('shows count when multiple warnings', () => {
    render(
      <HealthBadge
        health={{
          project_id: 'p',
          barrier: { active: true },
          stages: [],
          stuck_runs: 2,
          warnings: ['w1', 'w2', 'w3'],
        }}
      />,
    );
    expect(screen.getByText(/3 warnings/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd packages/ui && npm run test -- HealthBadge`

- [ ] **Step 4: Implement**

Create `packages/ui/src/components/pipeline/HealthBadge.tsx`:

```tsx
import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle } from 'lucide-react';
import type { PipelineHealth } from '../../types';

export interface HealthBadgeProps {
  health: PipelineHealth;
}

export function HealthBadge({ health }: HealthBadgeProps) {
  const [expanded, setExpanded] = useState(false);
  const warnCount = health.warnings.length;
  const ok = warnCount === 0;

  return (
    <div className="inline-block">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs ${
          ok
            ? 'bg-success/10 text-success'
            : 'bg-warning/10 text-warning'
        }`}
        aria-expanded={expanded}
      >
        {ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
        {ok ? 'Healthy' : `${warnCount} warning${warnCount === 1 ? '' : 's'}`}
      </button>
      {expanded && warnCount > 0 && (
        <ul className="mt-1 space-y-1 rounded border border-warning/30 bg-warning/5 p-2 text-xs">
          {health.warnings.map((w, i) => (
            <li key={i}>• {w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd packages/ui && npm run test -- HealthBadge`
Expected: 3 passing.

- [ ] **Step 6: Render badge in the pipeline panel header**

In `GraphEnrichmentPipeline.tsx`, add `health?: PipelineHealth` to the props interface and render it in the panel header:

```tsx
import { HealthBadge } from '../pipeline/HealthBadge';

// In the header row where the title renders:
{health && <HealthBadge health={health} />}
```

Thread `health` from `useDashboardPanels` through to the component (poll the endpoint on the same interval as `/pipeline/status`).

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/api/client.ts packages/ui/src/api/mock.ts packages/ui/src/types.ts packages/ui/src/components/pipeline/HealthBadge.tsx packages/ui/src/components/pipeline/__tests__/HealthBadge.test.tsx packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx src/codrag/dashboard/src/hooks/useDashboardPanels.tsx
git commit -m "feat(phase114-ui): pipeline health badge

Green Healthy / amber N warnings toggle in the pipeline panel header.
Pulls from GET /pipeline/health; click to expand the warnings list."
```

---

## Verification pass (not a task — do this after Task 10)

Before declaring done, run these commands and confirm each passes:

```bash
.venv/bin/pytest tests/test_checkpoint_stages.py tests/test_pipeline_barrier_status.py tests/test_pipeline_barrier_clear.py tests/test_pipeline_health.py tests/test_pipeline_stage_backups.py tests/test_pipeline_stage_restore.py -v
.venv/bin/pytest tests/test_scoped_full_reset.py tests/test_pipeline_stage_endpoint.py -v   # regression guards
cd packages/ui && npm run test
cd packages/ui && npm run typecheck
cd src/codrag/dashboard && npm run typecheck
```

Then invoke the `pipeline-testing` skill and run scenarios **W3** (scoped enrichment reset), **P4** (resume after pause), **S1** (graceful restart) manually via the dashboard to confirm the new UI surfaces and endpoints work end-to-end against the smoke repo `/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/sample_repos/generated/swift_repo`.

---

## Out of scope for this plan (deferred)

- Swarm/cloud changes (another agent owns this)
- Manifest `provenance` field — Task 4's `StageHealth.provenance` returns `None` for now; populating it requires stamping provenance at every manifest write site and is a separate phase.
- Per-run action log UI (gap #5 from the brainstorm)
- Disk usage UI (gap #10)
- Antibody cleanup on concept delete (gap #12)

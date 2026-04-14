# Phase 105a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewire the Atlas "Regenerate" button to queue through the pipeline orchestrator as an independent single-stage run, so it integrates with the queue, journal, history, and pipeline-panel stage state.

**Architecture:** Add `run_single_stage(project_id, stage_id, *, force=False)` to `PipelineOrchestrator` that validates the stage is in `FINALIZE_STAGES` and calls `_start_group(project_id, stage_id.value, [stage_id])`. Expose it as `POST /projects/{id}/pipeline/stages/{stage_id}/run`. Rewire `useAtlasLens.regenerate()` (renamed `runAtlasStage()`) to call the new endpoint. Delete the old direct-call `POST /projects/{id}/atlas/regenerate` path.

**Tech Stack:** Python (FastAPI, pytest), TypeScript (React, existing fetch pattern), ruff, mypy. No new dependencies.

---

## File Structure

### New

- `tests/test_orchestrator_single_stage.py` — unit tests for `run_single_stage`.
- `tests/test_pipeline_stage_endpoint.py` — HTTP tests for `POST /pipeline/stages/{stage_id}/run`.

### Modified

- `src/codrag/services/pipeline/orchestrator.py` — add `run_single_stage` method.
- `src/codrag/api/routers/pipeline.py` — add route handler for per-stage run.
- `packages/ui/src/api/client.ts` — add `runPipelineStage(projectId, stageId, force?)`. Remove `regenerateAtlas`.
- `packages/ui/src/api/mock.ts` — mock `runPipelineStage`. Remove `regenerateAtlas` mock.
- `src/codrag/dashboard/src/hooks/useAtlasLens.ts` — swap regenerate internals to the new endpoint. Rename method.
- `src/codrag/dashboard/src/components/AtlasLensContainer.tsx` — caller rename.
- `src/codrag/api/routers/projects/atlas_endpoints.py` — delete `regenerate_atlas` handler + its route.

---

## Task 1: Orchestrator `run_single_stage` method

**Files:**
- Modify: `src/codrag/services/pipeline/orchestrator.py` (add method near `run_finalize` around line 763)
- Test: `tests/test_orchestrator_single_stage.py`

- [ ] **Step 1.1: Write the failing unit tests**

Create `tests/test_orchestrator_single_stage.py`:

```python
"""Tests for PipelineOrchestrator.run_single_stage (Phase 105a)."""
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.pipeline_orchestrator import (
    FINALIZE_STAGES,
    PipelineOrchestrator,
    StageId,
)
from codrag.services.build_orchestrator import BuildOrchestrator


@pytest.fixture
def pipeline():
    return PipelineOrchestrator(BuildOrchestrator())


def test_run_single_stage_rejects_non_finalize_stages(pipeline):
    """Only finalize stages can be run solo."""
    with pytest.raises(ValueError, match="not a finalize stage"):
        pipeline.run_single_stage("proj-1", StageId.STRUCTURAL)
    with pytest.raises(ValueError, match="not a finalize stage"):
        pipeline.run_single_stage("proj-1", StageId.DEEPENING)


def test_run_single_stage_calls_start_group_with_single_element(pipeline):
    """The method should delegate to _start_group with a one-stage list."""
    with patch.object(pipeline, "_check_project_active", return_value=True), \
         patch.object(pipeline, "_selfheal_group") as selfheal, \
         patch.object(pipeline, "_start_group", return_value=True) as start_group:
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is True

    start_group.assert_called_once_with(
        "proj-1", "atlas", [StageId.ATLAS], resume_from=0,
    )


def test_run_single_stage_refuses_when_enrich_active(pipeline):
    """Must not launch a solo finalize while enrich is active/paused."""
    from codrag.services.pipeline_orchestrator import PipelineRun, PipelineRunPhase
    enrich_run = MagicMock(spec=PipelineRun)
    enrich_run.is_active = True
    enrich_run.is_paused = False
    enrich_run.state = MagicMock(value="running")
    enrich_run.current_stage = "deepening"
    with patch.object(pipeline, "_check_project_active", return_value=True):
        pipeline._runs[("proj-1", "deep_enrichment")] = enrich_run
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is False


def test_run_single_stage_refuses_when_project_inactive(pipeline):
    """Inactive project projects cannot start anything."""
    with patch.object(pipeline, "_check_project_active", return_value=False):
        assert pipeline.run_single_stage("proj-1", StageId.ATLAS) is False


def test_run_single_stage_group_identity_matches_stage(pipeline):
    """The group name written to history is the stage value."""
    captured = {}

    def capture(project_id, group, stages, **kwargs):
        captured["group"] = group
        captured["stages"] = stages
        return True

    with patch.object(pipeline, "_check_project_active", return_value=True), \
         patch.object(pipeline, "_selfheal_group"), \
         patch.object(pipeline, "_start_group", side_effect=capture):
        pipeline.run_single_stage("proj-1", StageId.CONCEPTS)

    assert captured["group"] == "concepts"
    assert captured["stages"] == [StageId.CONCEPTS]


def test_run_single_stage_force_bypasses_selfheal_and_resume(pipeline):
    """force=True skips selfheal pre-flight (consistent with run_finalize)."""
    with patch.object(pipeline, "_check_project_active", return_value=True), \
         patch.object(pipeline, "_selfheal_group") as selfheal, \
         patch.object(pipeline, "_start_group", return_value=True):
        pipeline.run_single_stage("proj-1", StageId.ATLAS, force=True)

    selfheal.assert_not_called()
```

- [ ] **Step 1.2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_orchestrator_single_stage.py -v`
Expected: All fail with `AttributeError: 'PipelineOrchestrator' object has no attribute 'run_single_stage'`.

- [ ] **Step 1.3: Implement `run_single_stage`**

Add to `src/codrag/services/pipeline/orchestrator.py`, directly below `run_finalize` (after line 799):

```python
def run_single_stage(
    self,
    project_id: str,
    stage_id: StageId,
    *,
    force: bool = False,
) -> bool:
    """Queue a single finalize stage through the orchestrator (Phase 105a).

    Routes the same path as run_finalize but with a one-element stage
    list and the stage_id as the group identity. This gives solo runs
    first-class presence in the queue, journal, history, and UI stage
    state.

    Args:
        project_id: Project to run against.
        stage_id: A StageId from FINALIZE_STAGES. Sync/enrich stages
            are rejected — they must run via their group-level methods.
        force: Skip the selfheal pre-flight.

    Returns:
        True when queued; False when rejected (project inactive, another
        group active, or orchestrator otherwise declined).

    Raises:
        ValueError: stage_id is not a finalize stage.
    """
    from .stages import FINALIZE_STAGES
    if stage_id not in FINALIZE_STAGES:
        raise ValueError(
            f"{stage_id!r} is not a finalize stage; use run_fast_sync / "
            "run_deep_enrichment for sync/enrich stages."
        )

    if not self._check_project_active(project_id):
        return False

    # Don't start a solo finalize stage while enrich is active or
    # paused — same guard as run_finalize.
    with self._lock:
        enrich_run = self._runs.get((project_id, "deep_enrichment"))
        if enrich_run and (enrich_run.is_active or enrich_run.is_paused):
            logger.info(
                "[%s] Skipping solo %s — enrich is %s (stage=%s)",
                project_id, stage_id.value, enrich_run.state.value,
                enrich_run.current_stage,
            )
            return False

    if not force:
        self._selfheal_group(project_id, [stage_id])

    return self._start_group(
        project_id, stage_id.value, [stage_id], resume_from=0,
    )
```

- [ ] **Step 1.4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_orchestrator_single_stage.py -v`
Expected: 6 passed.

- [ ] **Step 1.5: Ruff clean**

Run: `.venv/bin/ruff check src/codrag/services/pipeline/orchestrator.py tests/test_orchestrator_single_stage.py --fix`
Expected: no remaining errors on the changed regions (pre-existing style errors in the file are unrelated).

- [ ] **Step 1.6: Commit**

```bash
git add src/codrag/services/pipeline/orchestrator.py tests/test_orchestrator_single_stage.py
git commit -F - <<'MSGEND'
feat(phase105a): run_single_stage on PipelineOrchestrator

Queues one finalize stage through _start_group with the stage value
as the group identity. Rejects non-finalize stages with ValueError.
Refuses while enrich is active or the project is inactive (same
guards as run_finalize).

6 unit tests cover validation, delegation, guards, group identity,
and the force flag.
MSGEND
```

---

## Task 2: HTTP endpoint `POST /pipeline/stages/{stage_id}/run`

**Files:**
- Modify: `src/codrag/api/routers/pipeline.py` (add after `pipeline_run_finalize` around line 211)
- Test: `tests/test_pipeline_stage_endpoint.py`

- [ ] **Step 2.1: Write the failing HTTP tests**

Create `tests/test_pipeline_stage_endpoint.py`:

```python
"""Tests for POST /projects/{id}/pipeline/stages/{stage_id}/run (Phase 105a)."""
from pathlib import Path
from unittest.mock import patch

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
    with server._project_build_lock:
        server._project_build_threads.clear()
    return TestClient(app)


def _add_embedded_project(client: TestClient, repo_root: Path) -> str:
    res = client.post(
        "/projects",
        json={"path": str(repo_root), "name": "test", "mode": "embedded"},
    )
    assert res.status_code == 200
    return str(res.json()["data"]["project"]["id"])


def test_post_stage_run_invalid_stage_returns_400(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    res = client.post(f"/projects/{pid}/pipeline/stages/not-a-stage/run")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_STAGE_ID"


def test_post_stage_run_sync_stage_returns_400(client, tmp_path):
    """Sync/enrich stages cannot be run solo — they must use group endpoints."""
    pid = _add_embedded_project(client, tmp_path)
    res = client.post(f"/projects/{pid}/pipeline/stages/structural/run")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_STAGE_ID"


def test_post_stage_run_atlas_returns_200(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator.run_single_stage",
        return_value=True,
    ):
        res = client.post(f"/projects/{pid}/pipeline/stages/atlas/run")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["started"] is True
    assert body["data"]["group"] == "atlas"


def test_post_stage_run_orchestrator_rejects_returns_409(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator.run_single_stage",
        return_value=False,
    ):
        res = client.post(f"/projects/{pid}/pipeline/stages/atlas/run")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "PIPELINE_GROUP_ACTIVE"


def test_post_stage_run_accepts_force_query_param(client, tmp_path):
    pid = _add_embedded_project(client, tmp_path)
    with patch(
        "codrag.services.pipeline_orchestrator.pipeline_orchestrator.run_single_stage",
        return_value=True,
    ) as mock_run:
        res = client.post(f"/projects/{pid}/pipeline/stages/atlas/run?force=true")
    assert res.status_code == 200
    # Ensure force=True was passed through.
    _args, kwargs = mock_run.call_args
    assert kwargs.get("force") is True
```

- [ ] **Step 2.2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pipeline_stage_endpoint.py -v`
Expected: 5 fail with 404 (route does not exist).

- [ ] **Step 2.3: Implement the endpoint**

Add to `src/codrag/api/routers/pipeline.py` after `pipeline_run_finalize` (after line 210):

```python
@router.post("/projects/{project_id}/pipeline/stages/{stage_id}/run")
def pipeline_run_single_stage(
    project_id: str,
    stage_id: str,
    force: bool = False,
) -> Dict[str, Any]:
    """Run a single finalize stage (stages 11-15) through the orchestrator.

    Rejects sync/enrich stages (they must use the group endpoints).
    Returns 409 when another group is active or the orchestrator
    otherwise declines.
    """
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import (
        FINALIZE_STAGES,
        StageId,
        pipeline_orchestrator,
    )

    # Resolve stage_id string → StageId enum, reject unknowns + non-finalize.
    try:
        sid = StageId(stage_id)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="INVALID_STAGE_ID",
            message=f"Unknown stage_id '{stage_id}'.",
        ) from exc
    if sid not in FINALIZE_STAGES:
        raise ApiException(
            status_code=400,
            code="INVALID_STAGE_ID",
            message=(
                f"Stage '{stage_id}' is not a finalize stage. "
                "Use /pipeline/fast or /pipeline/deep for sync/enrich stages."
            ),
        )

    started = pipeline_orchestrator.run_single_stage(
        project_id, sid, force=force,
    )
    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_GROUP_ACTIVE",
            message=(
                f"Cannot run '{stage_id}' solo: another pipeline group is "
                "active, the stage is up-to-date, or the project is inactive."
            ),
        )

    return ok({"started": True, "group": stage_id})
```

- [ ] **Step 2.4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pipeline_stage_endpoint.py -v`
Expected: 5 passed.

- [ ] **Step 2.5: Ruff clean**

Run: `.venv/bin/ruff check src/codrag/api/routers/pipeline.py tests/test_pipeline_stage_endpoint.py --fix`

- [ ] **Step 2.6: Commit**

```bash
git add src/codrag/api/routers/pipeline.py tests/test_pipeline_stage_endpoint.py
git commit -F - <<'MSGEND'
feat(phase105a): POST /pipeline/stages/{stage_id}/run endpoint

Routes to orchestrator.run_single_stage. Returns 400 INVALID_STAGE_ID
for unknown or sync/enrich stages; 409 PIPELINE_GROUP_ACTIVE when
the orchestrator declines. Accepts ?force=true to bypass selfheal.

5 HTTP tests cover the full envelope + error paths.
MSGEND
```

---

## Task 3: TypeScript API client

**Files:**
- Modify: `packages/ui/src/api/client.ts` (interface + implementation)
- Modify: `packages/ui/src/api/mock.ts`

- [ ] **Step 3.1: Read the current `regenerateAtlas` block**

Read `packages/ui/src/api/client.ts` around lines 169–171 (interface) and around the `regenerateAtlas` implementation (currently around line 1141).

- [ ] **Step 3.2: Update the client interface**

In `packages/ui/src/api/client.ts`, find the interface block containing:

```ts
  // Codebase Atlas (Phase 29, extended Phase 104)
  getAtlas(projectId: string, role?: string): Promise<import('../types').AtlasStatus>;
  regenerateAtlas(projectId: string): Promise<import('../types').AtlasStatus>;
```

Replace with:

```ts
  // Codebase Atlas (Phase 29, extended Phase 104)
  getAtlas(projectId: string, role?: string): Promise<import('../types').AtlasStatus>;

  // Pipeline stage triggers (Phase 105a)
  runPipelineStage(projectId: string, stageId: string, opts?: { force?: boolean }): Promise<{ started: boolean; group: string }>;
```

(Note: `regenerateAtlas` is removed from the interface.)

- [ ] **Step 3.3: Update the client implementation**

In `packages/ui/src/api/client.ts`, find the `regenerateAtlas` method (currently around line 1138):

```ts
  async regenerateAtlas(projectId: string): Promise<import('../types').AtlasStatus> {
    return this.requestEnvelope<import('../types').AtlasStatus>(`/projects/${encodeURIComponent(projectId)}/atlas/regenerate`, {
      method: 'POST',
    });
  }
```

Replace with:

```ts
  async runPipelineStage(
    projectId: string,
    stageId: string,
    opts: { force?: boolean } = {},
  ): Promise<{ started: boolean; group: string }> {
    const pid = encodeURIComponent(projectId);
    const sid = encodeURIComponent(stageId);
    const qs = opts.force ? '?force=true' : '';
    return this.requestEnvelope(
      `/projects/${pid}/pipeline/stages/${sid}/run${qs}`,
      { method: 'POST' },
    );
  }
```

- [ ] **Step 3.4: Update the mock client**

In `packages/ui/src/api/mock.ts`, find the `regenerateAtlas` method (currently around line 551):

```ts
  async regenerateAtlas(_projectId: string): Promise<import('../types').AtlasStatus> {
    return this.getAtlas(_projectId);
  }
```

Replace with:

```ts
  async runPipelineStage(
    _projectId: string,
    stageId: string,
    _opts: { force?: boolean } = {},
  ): Promise<{ started: boolean; group: string }> {
    return { started: true, group: stageId };
  }
```

- [ ] **Step 3.5: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: exit 0. Dashboard typecheck will fail here because the hook still calls `regenerateAtlas` — that's the next task.

- [ ] **Step 3.6: Commit**

```bash
git add packages/ui/src/api/client.ts packages/ui/src/api/mock.ts
git commit -F - <<'MSGEND'
feat(phase105a): runPipelineStage on API client; drop regenerateAtlas

Client and mock now expose runPipelineStage(projectId, stageId, {force})
targeting POST /pipeline/stages/{stageId}/run. regenerateAtlas is
removed from the interface in the same commit — the dashboard hook
rewire in the next task picks up the new method.
MSGEND
```

---

## Task 4: Dashboard hook rewire

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useAtlasLens.ts`
- Modify: `src/codrag/dashboard/src/components/AtlasLensContainer.tsx`

- [ ] **Step 4.1: Read the current hook**

Read `src/codrag/dashboard/src/hooks/useAtlasLens.ts` to locate the `regenerate` function and its wiring into the return object.

- [ ] **Step 4.2: Rewire the hook**

In `src/codrag/dashboard/src/hooks/useAtlasLens.ts`, find the `regenerate` callback:

```ts
  const regenerate = useCallback(async () => {
    if (!projectId) return;
    setRegenerating(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/atlas/regenerate`,
        { method: 'POST' },
      );
      if (!res.ok) {
        throw new Error(`regenerate failed: ${res.status}`);
      }
      // Re-fetch so we show the fresh atlas + (if a role is active) the
      // updated role projection.
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRegenerating(false);
    }
  }, [projectId, refresh]);
```

Replace with:

```ts
  const runAtlasStage = useCallback(async () => {
    if (!projectId) return;
    setRegenerating(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/pipeline/stages/atlas/run`,
        { method: 'POST' },
      );
      if (!res.ok) {
        // 409 is "another group active" or "up-to-date" — surface to user.
        const body = await res.json().catch(() => ({}));
        const msg = body?.error?.message ?? `run atlas failed: ${res.status}`;
        throw new Error(msg);
      }
      // Re-fetch so we show the fresh atlas + (if a role is active) the
      // updated role projection. The orchestrator owns the pipeline panel's
      // stage-state update via its own channel.
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRegenerating(false);
    }
  }, [projectId, refresh]);
```

Also update the return object at the bottom of the hook: replace `regenerate,` with `runAtlasStage,` in the returned object, and rename the type's field in `UseAtlasLensReturn`:

```ts
export interface UseAtlasLensReturn {
  // ... existing fields ...
  regenerating: boolean;
  role: string | null;
  setRole: (next: string | null) => void;
  refresh: () => Promise<void>;
  runAtlasStage: () => Promise<void>;
}
```

(If the old type had `regenerate: () => Promise<void>;`, replace it with `runAtlasStage: () => Promise<void>;`.)

- [ ] **Step 4.3: Update the container caller**

In `src/codrag/dashboard/src/components/AtlasLensContainer.tsx`, find:

```ts
  const {
    atlasStatus, role, setRole, regenerate, regenerating, refresh,
    error: atlasError,
  } = useAtlasLens(projectId);
```

Replace `regenerate` with `runAtlasStage`:

```ts
  const {
    atlasStatus, role, setRole, runAtlasStage, regenerating, refresh,
    error: atlasError,
  } = useAtlasLens(projectId);
```

And update the prop passed to `AtlasLensPanel`:

```ts
      <AtlasLensPanel
        atlas={atlasStatus}
        role={role}
        onRoleChange={setRole}
        roleOptions={roleOptions.length > 0 ? roleOptions : undefined}
        regenerating={regenerating}
        onRegenerate={runAtlasStage}
```

(Change `onRegenerate={regenerate}` → `onRegenerate={runAtlasStage}`.)

- [ ] **Step 4.4: Typecheck**

Run: `cd src/codrag/dashboard && npx tsc --noEmit`
Expected: exit 0.

Run: `cd packages/ui && npm run typecheck`
Expected: exit 0.

- [ ] **Step 4.5: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useAtlasLens.ts src/codrag/dashboard/src/components/AtlasLensContainer.tsx
git commit -F - <<'MSGEND'
feat(phase105a): dashboard hook points atlas regenerate at orchestrator

useAtlasLens.runAtlasStage (renamed from regenerate) calls
POST /pipeline/stages/atlas/run. Surfaces 409 error body so "pipeline
group active" and "up-to-date" land in the existing error pill. Local
refresh still fires on success so the atlas card reflects the freshly
regenerated data; the pipeline panel's stage-state update arrives
separately via the orchestrator's own channel.

Renamed the return-object field + container caller in lockstep.
MSGEND
```

---

## Task 5: Delete the old `regenerate_atlas` endpoint

**Files:**
- Modify: `src/codrag/api/routers/projects/atlas_endpoints.py`

- [ ] **Step 5.1: Remove the handler and the route**

In `src/codrag/api/routers/projects/atlas_endpoints.py`, locate the block:

```python
@router.post("/projects/{project_id}/atlas/regenerate")
def regenerate_atlas(project_id: str) -> dict[str, Any]:
    """Manually trigger Atlas regeneration."""
    ...
```

Delete the entire function (decorator + body). If this leaves any now-unused imports (`Path`, `_build_atlas_response` is still used by GET so keep it), clean them up with ruff.

- [ ] **Step 5.2: Grep for lingering references**

Run: `grep -rn "atlas/regenerate\|regenerateAtlas\|regenerate_atlas" src packages tests docs` (excluding `docs/`).

Every non-doc hit must be cleaned up. Expected remaining hits: `docs/Phase104_SubAtlas/README.md` and similar historical docs — leave those.

- [ ] **Step 5.3: Run existing atlas tests**

Run: `.venv/bin/pytest tests/test_atlas_endpoints.py tests/test_atlas.py -q`
Expected: all passing.

- [ ] **Step 5.4: Ruff + typecheck**

Run:
- `.venv/bin/ruff check src/codrag/api/routers/projects/atlas_endpoints.py --fix`
- `cd packages/ui && npm run typecheck`
- `cd src/codrag/dashboard && npx tsc --noEmit`

All should be clean.

- [ ] **Step 5.5: Commit**

```bash
git add src/codrag/api/routers/projects/atlas_endpoints.py
git commit -F - <<'MSGEND'
chore(phase105a): delete POST /atlas/regenerate direct-call endpoint

Superseded by POST /pipeline/stages/atlas/run which routes through
the orchestrator. Last internal caller (useAtlasLens hook) was
migrated in the previous commit.

Historical docs that reference /atlas/regenerate are left alone —
they describe the state at their time.
MSGEND
```

---

## Task 6: Full-suite verification

- [ ] **Step 6.1: Run the full Python test suite touched by Phase 105a**

Run:
```bash
.venv/bin/pytest \
  tests/test_orchestrator_single_stage.py \
  tests/test_pipeline_stage_endpoint.py \
  tests/test_atlas_endpoints.py \
  tests/test_atlas.py \
  tests/test_role_overrides_endpoints.py \
  tests/test_role_projection_overrides.py \
  tests/test_roles_endpoint.py \
  tests/test_pipeline_orchestrator.py \
  -q
```

Expected: all passing.

- [ ] **Step 6.2: Ruff clean on changed Python files**

Run: `.venv/bin/ruff check src/codrag/services/pipeline/orchestrator.py src/codrag/api/routers/pipeline.py src/codrag/api/routers/projects/atlas_endpoints.py tests/test_orchestrator_single_stage.py tests/test_pipeline_stage_endpoint.py`

Expected: `All checks passed!` (after --fix pass). Pre-existing warnings in unrelated file regions may remain — ignore if untouched by this phase.

- [ ] **Step 6.3: Final typecheck on both TS workspaces**

Run:
- `cd packages/ui && npm run typecheck`
- `cd src/codrag/dashboard && npx tsc --noEmit`

Expected: exit 0 on both.

- [ ] **Step 6.4: Manual browser check**

This step cannot be automated with the current test setup.

Start the dev server: `scripts/dev.sh` (daemon on :8400, dashboard on :5174).

In the browser:

1. Open the dashboard, pick a project that has an atlas.
2. Confirm the atlas panel shows current status.
3. Click **Regenerate** on the atlas panel.
4. Within ~200ms, confirm a queue entry appears in the left-panel queue.
5. Confirm the Graph Enrichment Pipeline panel's atlas stage transitions to "running".
6. When complete, confirm:
   - The atlas panel's status flips to "Fresh".
   - All sub-atlas segments flip to "Fresh".
   - The pipeline panel shows the atlas stage as complete with an updated "last run" timestamp.
   - `pipeline_history` (via `GET /projects/{id}/pipeline/history` or the pipeline panel's history view) has a new entry with `group="atlas"`.

If any of the above fails, file a follow-up ticket — do not silently fix it inside 105a. That's a signal the orchestrator's `_start_group` makes a multi-stage assumption that needs a separate patch.

- [ ] **Step 6.5: Final commit (if any fixes surfaced during verification)**

Only commit if Steps 6.1–6.4 surfaced a regression that needed a fix. Otherwise, Phase 105a is complete on the branch.

---

## Self-review checklist (done while writing — recorded for visibility)

- **Spec coverage:** Each spec bullet maps to a task.
  - "`run_single_stage` method" → Task 1.
  - "HTTP endpoint" → Task 2.
  - "API client update" → Task 3.
  - "Hook rewire + container caller rename" → Task 4.
  - "Delete old endpoint" → Task 5.
  - "All four success criteria verified in browser" → Step 6.4.
- **Placeholders:** None. Every code block is complete.
- **Type consistency:** `runAtlasStage` used consistently (hook, container, spec). `runPipelineStage` on the client; interface + implementation + mock match.
- **Freshness-check deferral:** Spec mentioned `atlas.is_stale()` reuse for the "up-to-date" check. 105a relies on the orchestrator's own freshness/resume logic through `_start_group` and `_detect_resume_point` — see `run_finalize` for reference. No custom stale check added in this phase; if the orchestrator returns False due to staleness short-circuit, the 409 still surfaces to the user. If the user reports "I can't re-run atlas when it looks stale," that's a 105b follow-up to add `force=True` wiring to the button.

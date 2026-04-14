# Phase 105a — Orchestrator Single-Stage + Atlas Rewire

> **Scope.** Smallest coherent slice of Phase 105 that proves the three-groups-of-five model with orchestrator parity. Adds `run_single_stage` to the orchestrator, exposes it over HTTP, and rewires the Atlas "Regenerate" button to use it. Deletes the direct-call `/atlas/regenerate` path. Concepts + Audit rewires and the dependency-invalidation cascade are deferred to 105b.

## Success criteria

After 105a ships, pressing **Regenerate** in the AtlasLensPanel must:

- Add a queue entry to the left-panel queue within ~200ms.
- Write a `pipeline_history` row with `group="atlas"`, start/end timestamps, and terminal state.
- Advance the atlas stage's "last run" timestamp in the Graph Enrichment Pipeline panel.
- Flip the atlas stage's state indicator in the pipeline panel through running → complete.
- Flip the stale badge on the atlas panel + all sub-atlas segments to fresh when complete.
- Be cancelable + pausable via the same controls that act on group runs today.

> **Two independent "stale" signals to be aware of.** The atlas panel's badge reads `atlas.is_stale()` (fingerprint + hub-hash + file-count + segment-drift). The pipeline panel's atlas stage-state reads the orchestrator's stage-completion tracker. In Phase 104, the direct-call regenerate moved the first signal but not the second. 105a fixes the second by routing through the orchestrator. The first should also flip because `generate_segmented` already saves fresh fingerprints — verify this during dev-server verification and raise a separate bug if `is_stale()` returns `True` after a successful orchestrated run.

`POST /pipeline/finalize` must still queue all five stages in one history entry (no regression).

## Architecture

### Orchestrator

New method on `PipelineOrchestrator` (`src/codrag/services/pipeline/orchestrator.py`):

```python
def run_single_stage(
    self,
    project_id: str,
    stage_id: StageId,
    *,
    force: bool = False,
) -> bool:
    """Queue a single finalize stage through the orchestrator.

    Returns True when queued, False when rejected (up-to-date + not forced).

    Raises ValueError if stage_id is not in FINALIZE_STAGES.
    Raises RuntimeError-subclass if a sync or enrich run is active.
    """
```

Internal implementation:

1. Validate `stage_id in FINALIZE_STAGES` — reject with `ValueError` otherwise.
2. Guard: if fast_sync or deep_enrichment is running or paused for this project, refuse (same `active_or_paused` check `run_finalize` uses).
3. Freshness check: if the stage's `STAGE_OUTPUT_FILES` are up-to-date against `STAGE_INPUT_FILES` and `force=False`, return `False`. When `force=True`, skip the check.
4. Call `_start_group(project_id, group=stage_id.value, stages=[stage_id], resume_from=0)`.
5. Return `True`.

The second argument to `_start_group` is the group identity written to history. Passing the stage value (`"atlas"`) makes solo runs queryable as their own category without introducing new enum members.

### HTTP endpoint

New router in `src/codrag/api/routers/pipeline.py`:

```python
@router.post("/projects/{project_id}/pipeline/stages/{stage_id}/run")
def run_pipeline_stage(project_id: str, stage_id: str, force: bool = False) -> Dict[str, Any]:
    """Queue a single finalize stage through the orchestrator.

    - Accepts stage_id as a string; converted to StageId internally.
    - Reject with 400 if stage_id is not a valid finalize stage.
    - Reject with 409 if another group is active, or if up-to-date + not forced.
    - Return {started: True, group: stage_id, queued_at: <iso>} on success.
    """
```

Matches the existing `POST /pipeline/finalize` return shape for consistency.

### Frontend

The Atlas regenerate button flips from calling `POST /atlas/regenerate` (removed) to `POST /pipeline/stages/atlas/run`. Local state (`regenerating`, `stale`) derives from the orchestrator's pipeline-status feed rather than from the request's own response.

- `useAtlasLens.regenerate()` renamed to `runAtlasStage()` and updated. Caller rename in `AtlasLensContainer.tsx`.
- `StatusStrip` shows the button as running when `pipeline_status.stages.atlas.state === "running" || "queued"`. Disabled state, label, and spinner match the per-stage Run buttons rendered by `GraphEnrichmentPipeline.tsx`.

### Endpoint deletion

`POST /projects/{id}/atlas/regenerate` is **removed** (router function + route registration). The `regenerate_atlas` function in `atlas_endpoints.py` is deleted. Same-commit UI update removes the last caller. No deprecation window — the only consumer is internal.

## Data flow

```
UI click
  │
  ▼
POST /pipeline/stages/atlas/run
  │
  ▼
PipelineOrchestrator.run_single_stage(pid, StageId.ATLAS)
  │
  ├─→ validate + guard
  │
  ▼
_start_group(pid, "atlas", [StageId.ATLAS])
  │
  ├─→ journal entry created
  ├─→ queue entry created (status=queued)
  ├─→ worker thread picks up
  │     │
  │     ├─→ _start_stage → status=running
  │     ├─→ atlas worker (existing) runs generate_segmented
  │     ├─→ _complete_stage → status=complete
  │
  ├─→ pipeline history row written with group="atlas"
  └─→ stage_complete event emitted
        │
        ▼
  pipeline_status polling (or event subscription) updates
        │
        ▼
  AtlasLensPanel + GraphEnrichmentPipeline both re-render
```

## Interfaces touched

### New
- `PipelineOrchestrator.run_single_stage` (Python method)
- `POST /projects/{id}/pipeline/stages/{stage_id}/run` (HTTP)

### Modified
- `packages/ui/src/api/client.ts` — add `runPipelineStage(projectId, stageId)`.
- `packages/ui/src/api/mock.ts` — mock the new method; remove mock of `regenerateAtlas` (or keep for 105b — TBD in implementation).
- `src/codrag/dashboard/src/hooks/useAtlasLens.ts` — swap `regenerate()` internals to the new endpoint. Rename method to `runAtlasStage` for clarity.
- `src/codrag/dashboard/src/components/AtlasLensContainer.tsx` — caller rename.

### Removed
- `regenerate_atlas` function in `src/codrag/api/routers/projects/atlas_endpoints.py`.
- `POST /projects/{id}/atlas/regenerate` route.
- `regenerateAtlas()` methods on the API client + mock.

### Unchanged
- `atlas.generate_segmented()` — still exists, called by the atlas worker. Only the *trigger path* changes; the work itself is identical.
- `POST /pipeline/finalize` — continues to run all five stages in order with one history row.
- `GET /atlas`, `GET /atlas?role=X`, `GET /roles`, `/role-overrides/*` — no change.
- All other finalize stages — unchanged in 105a; deferred to 105b.

## Error handling

- **Invalid stage_id (sync/enrich)** — 400 Bad Request, code `INVALID_STAGE_ID`.
- **Non-existent stage_id string** — 400, code `INVALID_STAGE_ID`.
- **Another group is running** — 409 Conflict, code `PIPELINE_GROUP_ACTIVE`. This single 409 code also covers the "stage up-to-date" and "project inactive" cases in 105a; the orchestrator returns `False` for all three and the HTTP layer maps them to one code for simplicity. If UI differentiation becomes valuable (e.g., "you can't regenerate because nothing changed" vs "another run is active"), split into distinct codes in a follow-up.
- **Project not found or not writable** — 404, code `PROJECT_NOT_FOUND`.
- **Worker raises mid-run** — orchestrator handles per existing error paths; history row marks terminal state as `error`; UI renders the error badge.

## Testing

### Unit tests — `tests/test_orchestrator_single_stage.py` (new)
1. `run_single_stage` rejects non-finalize stages with `ValueError`.
2. Queues atlas solo with `group="atlas"`.
3. Refuses when sync is active.
4. Refuses when enrich is active.
5. Refuses when stage is up-to-date + `force=False`; accepts when `force=True`.

### HTTP tests — `tests/test_pipeline_stage_endpoint.py` (new)
1. `POST /pipeline/stages/atlas/run` returns 200 with `{started: True, group: "atlas"}`.
2. Unknown stage returns 400 `INVALID_STAGE_ID`.
3. Non-finalize stage (e.g. `"structural"`) returns 400 `INVALID_STAGE_ID`.
4. Conflict returns 409 `PIPELINE_GROUP_ACTIVE`.
5. Up-to-date + no force returns 409 `STAGE_UP_TO_DATE`.
6. `?force=true` bypasses up-to-date.

### Integration test — `tests/test_atlas_solo_run_integration.py` (new)
End-to-end: POST the endpoint, wait for completion, verify:
- A `pipeline_history` row exists with `group="atlas"`.
- Atlas `atlas.json` is fresh (mtime advanced).
- Stage state post-run is `complete`.

### Regression tests
- `run_finalize` still produces one history row, not one per stage.
- `pipeline/finalize` endpoint contract unchanged.

### UI verification
Manual browser check: start dev server, click Regenerate, confirm the four-symptoms list above. Cannot be fully automated without Playwright; no Playwright setup exists.

## Risks & mitigations

- **Risk:** `_start_group` assumes a multi-stage list somewhere internal (e.g., iteration loop, progress calculation). Single-element list may hit an edge case.
  **Mitigation:** Read `_start_group` end-to-end before implementing. Add a single-stage integration test as the first check.

- **Risk:** Freshness check for atlas duplicates `atlas.is_stale()` logic. Divergence later.
  **Mitigation:** In 105a, have the freshness check call `atlas.is_stale()` directly via the atlas instance. Don't reinvent it.

- **Risk:** Pipeline status poll cadence is slow; user perceives the button as unresponsive.
  **Mitigation:** Optimistic UI — when the POST returns 200, immediately set button state to `running` in local state until the next poll confirms. No change to polling cadence.

- **Risk:** Queue panel subscribes to queue events differently from pipeline panel.
  **Mitigation:** Spot-check queue panel after 105a dev-server test. If it doesn't update, raise in 105b and file a queue-subscription bug.

## Out of scope (moved to 105b or later)

- Concepts `Initialize Concepts` button rewire.
- Audit `Run Audit` button rewire.
- Dependency invalidation cascade (atlas run → rules stale, concepts run → antibodies stale).
- `seed_concepts` re-run semantics (replace / append / merge).
- Backend-only trigger endpoints for Rules and Antibodies.
- Prompt-cache optimization (Phase 105.5).
- Concurrent solo runs.
- Agent-ownership hand-off for stages.

## Implementation sequence

1. Write `run_single_stage` on the orchestrator. Unit tests.
2. Add `POST /pipeline/stages/{stage_id}/run` endpoint. HTTP tests.
3. Integration test for solo atlas run.
4. Add `runPipelineStage` to the API client + mock.
5. Rewire `useAtlasLens` to the new endpoint; rename method.
6. Update `AtlasLensContainer` caller name.
7. Update `StatusStrip` to derive button state from `pipeline_status`.
8. Delete `regenerate_atlas` function + route + API client method + mock.
9. Dev-server manual verification of the four-symptoms list.
10. Commit, typecheck, lint, ruff, full test suite.

Each step ends at a green checkpoint. No step should leave the app in a half-migrated state.

## Non-goals

- Changing any existing pipeline run behavior.
- Adding concurrent stage execution.
- Adding new UI surfaces.
- Touching the MCP integration.
- Modifying the atlas generation logic itself.

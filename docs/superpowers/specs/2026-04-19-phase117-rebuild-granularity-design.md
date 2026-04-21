# Phase 117 — Rebuild Granularity & Provenance (Scopes A + B)

**Status:** Draft
**Date:** 2026-04-19
**Predecessor:** Phase 116 (rebuild progress bar)
**Deferred to Phase 118:** History drawer (Scope C), pre-rebuild journaling (C-7)

## Problem

When the pipeline produces incorrect or questionable state, the user has three blunt instruments: a nuclear reset, a full rebuild (all 15 stages), or per-stage recover. Missing:

1. **Partial rebuild scope.** No way to force-rebuild just stages 1–5 (Sync) or just 6–10 (Enrichment). The only "force from start" path is all-or-nothing.
2. **Stoppable rebuild as a unit.** Users can cancel a *group*, but while a rebuild is running across three groups there's no single "Stop Rebuild" action, and queued/running items give no visual signal that they belong to a rebuild.
3. **Rebuild decisions are made blind.** "Incomplete" stages conflate three different states: data missing, manifest self-healed (data intact), and data produced by an older/different model than the user's current config. The user cannot tell whether rebuilding is necessary, cosmetic, or quality-relevant.

The observed cost of #3 is concrete: in the current `.prep/` state, stages 2 and 3 show as "incomplete" (self-heal stubs) but the on-disk outputs are valid and were consumed cleanly by a successful ~10-hour deep enrichment run (`run-f77cddd43f17`, `kimi-k2.5:cloud`, 1788/1788 items). A naive rebuild would re-spend ~6 hours re-enriching for no quality gain.

## Goal

Give users the granularity to rebuild what actually needs rebuilding, the control to stop a rebuild cleanly, and the visibility to know when rebuilding is justified — without adding new UI surfaces or panels.

## Non-goals

- Rebuild history timeline / drawer (Scope C; deferred to Phase 118)
- Pre-rebuild journaling of crashed-before-first-manifest attempts (C-7; deferred)
- Auto-recommendation engine beyond displaying the model-drift signal
- Finalize-group rebuild (existing per-stage recover is adequate)
- Cascading force-from-start (keep cascades incremental; only the user-selected scope is forced)

## Design

### Scope A: Granularity

#### A1. Split-button dropdown

Replaces the existing "Rebuild All" button in `GraphEnrichmentPipeline.tsx`.

- **Primary click** (`Rebuild`): runs `Rebuild All` — preserves current muscle memory.
- **Caret click**: dropdown with three options in this order:
  - `Rebuild Sync (1–5)` — confirms with cost estimate before triggering
  - `Rebuild Enrichment (6–10)` — triggers immediately (this is the cheap, high-frequency case)
  - `Rebuild All (1–15)` — confirms with cost estimate

The dropdown uses the existing button styling and positioning. No new component type, no panel changes.

#### A2. Scoped force-from-start backend

Extend existing endpoints with an optional body param; add one new control endpoint:

| Endpoint | Change |
|---|---|
| `POST /projects/{id}/pipeline/fast` | Accept `{"force_from_start": bool}` (default `false`). When `true`: write barrier `{reason: "rebuild", scope: "sync"}`, call orchestrator with `force_from_start=True`. |
| `POST /projects/{id}/pipeline/deep` | Same pattern, `scope: "enrichment"`. |
| `POST /projects/{id}/pipeline/rebuild` | Unchanged externally; now writes barrier with `scope: "all"` for symmetry. |
| `POST /projects/{id}/pipeline/rebuild/stop` | **New.** Atomically cancels the active group for this project AND clears the rebuild barrier. Idempotent — returns success even if no active rebuild. |

Cascade behavior: force-from-start applies **only to the user-selected scope**. Downstream groups chain incrementally via the orchestrator's existing run-all-then-chain behavior. If downstream inputs changed (they usually do after a force-rebuild), the incremental pass will re-derive. This is honest and cheap: we don't pretend to rebuild downstream, we just let the dependency model do its job.

#### A3. Barrier scope

Extend the barrier schema in `codrag.services.pipeline.recovery`:

```json
{
  "active": true,
  "reason": "rebuild",
  "scope": "sync" | "enrichment" | "all",
  "started_at": "2026-04-19T14:23:00Z",
  "scope_group_finished": false
}
```

`scope_group_finished` flips to `true` when the force-rebuilt group completes (e.g., stage 5 for `sync`, stage 10 for `enrichment`, stage 15 for `all`). The UI uses this to decide when to hide the sticky row; downstream incremental cascades that continue after flip look like normal pipeline activity.

The existing barrier auto-clear on finalize completion still applies for `scope: "all"`. For `scope: "sync"` and `scope: "enrichment"`, the barrier auto-clears when its force-rebuilt group finishes.

#### A4. Sticky "Rebuilding" queue row

A single row rendered at the top of the queue list in `GraphEnrichmentPipeline.tsx`, only while `barrier.reason === "rebuild"` and `barrier.scope_group_finished === false`:

```
┌─────────────────────────────────────────────────────────────┐
│ 🔄 Rebuilding Sync · stage 3/5: Fast Catalogue · 38%  [Stop]│
└─────────────────────────────────────────────────────────────┘
```

- Scope label derives from `barrier.scope`.
- Current-stage text derives from which stage in the scoped group is active.
- Percentage reuses `computeOverallRebuildPercent` from `packages/ui/src/components/trace/rebuildProgress.ts` with the range narrowed to the scoped group.
- `[Stop]` button calls `/pipeline/rebuild/stop`.

This removes the "which queue item is part of the rebuild?" ambiguity without per-row badges. Individual queued/running items retain their existing appearance; the sticky row is the single source of truth for "a rebuild is in progress."

#### A5. Stop semantics

When `/pipeline/rebuild/stop` fires:

1. Orchestrator cancels the active group's currently-running stage.
2. Temp files for that stage never swap into the live index (existing atomic-swap guarantee). Pre-rebuild data for that stage remains in place.
3. Barrier is cleared.
4. Stages already completed within this rebuild remain as they are. Their pre-rebuild backups live in `.prep/backups/enrichment_reset_*/` (existing behavior). If the user wants to roll those back, they use the existing per-stage recover UI — Phase 117 does not auto-rollback.
5. UI drops rebuild coloring (stages return to normal state classification).

#### A6. Confirmation modal

Reuse existing modal primitives. Copy:

- **Rebuild All**: "This will re-run all 15 stages. Last full rebuild took ~10h. Continue?"
- **Rebuild Sync**: "This will re-run stages 1–5. Downstream stages 6–15 will incrementally re-derive against the new graph. Last full rebuild took ~10h. Continue?"
- **Rebuild Enrichment**: no modal — single-click.

Estimated duration is best-effort. First preference: the most recent `pipeline_run_metadata.json` across `.prep/` and `.prep/backups/enrichment_reset_*/` whose `group` matches the scope and `status == "completed"`. Fallback when no such record exists: "may take several hours." If the estimate is stale or unavailable, the modal omits the duration rather than guessing.

### Scope B: Provenance

#### B1. Per-stage provenance chip

Each stage card in `GraphEnrichmentPipeline.tsx` gains a single inline chip under its existing stats line. Exactly one chip per stage, based on state:

| State | Chip | Color | Trigger condition |
|---|---|---|---|
| Match | None (or quiet `"Kimi2.5 · Apr 18"` when details toggle is on) | neutral | `manifest.model.model_name == current_task_config.model_name` AND `manifest.model.provider == current_task_config.provider` |
| Drift | `"Built with Kimi2.5 → now Qwen3 · Rebuild"` | amber | Match check fails |
| Recovered stub | `"Self-healed · provenance unknown · Rebuild"` | amber | `manifest.restored === true` AND no golden-checkpoint evidence |
| Recovered + golden match | `"Self-healed · model likely current"` | neutral-soft | `manifest.restored === true` AND golden `_meta.json` covers this stage AND current config matches the golden's embedded model |
| Missing | Existing "not built" treatment | red | No manifest AND no data file |

The chip text is a button. Clicking it dispatches the matching rebuild scope:
- Drift/stub on stages 1–5 → triggers `Rebuild Sync` (with confirmation modal per A6).
- Drift/stub on stages 6–10 → triggers `Rebuild Enrichment`.
- Drift/stub on stages 11–15 → triggers the stage's existing per-stage recover (finalize rebuilds are per-stage per non-goals).

#### B2. Match policy

Lookup uses the stage's `task_id` to find the current config (that's how task assignments are indexed). The equality comparison between manifest-model and current-config-model is on `provider + model_name` only. Task_id mismatch (e.g., `enrichment_v1` in the manifest vs `enrichment` in current config) does NOT cause a drift signal. Provider comparison is case-insensitive; model_name is exact match.

#### B3. Backend exposure

New helper in `src/codrag/services/pipeline_provenance.py`:

```python
def compute_stage_provenance(
    project_id: str,
    stage_id: str,
) -> StageProvenance:
    """Return {state, chip_text, manifest_model, current_config_model}."""
```

Called from `/pipeline/status` and attached to each stage's payload as a `provenance` field:

```json
{
  "id": "enrichment",
  "state": "complete",
  "stats": "1,788 items · 87.8% conf",
  "provenance": {
    "state": "match",
    "manifest_model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"},
    "current_config_model": {"provider": "ollama", "model_name": "kimi-k2.5:cloud"},
    "chip_text": null,
    "rebuild_scope": null
  }
}
```

The helper caches per-project with a short TTL (reuse the existing `_status_cache` in `pipeline.py`).

#### B4. Data sources

- **Manifest model**: read from per-stage manifest's `model` field for stages that have one. Stages without an LLM (1, 2, 4, 5 proper, 10's embedding side) return `None` and are never "drift".
- **Current config model**: resolved via existing LLM task-assignment lookup (`src/codrag/services/llm_coordinator` or equivalent). If no assignment exists for the task_id, fall back to project default.
- **Recovered flag**: manifest contains `"restored": true`.
- **Golden checkpoint**: `.prep/.checkpoints/_golden/_meta.json` plus the specific stage file's presence in the golden dir. Used only to soften the stub chip — never to upgrade a match/drift decision.

## Implementation map

### Files touched (expected)

**Backend:**
- `src/codrag/api/routers/pipeline.py` — body param on `fast`/`deep`; new `rebuild/stop` endpoint; status response includes `provenance`.
- `src/codrag/services/pipeline/recovery.py` — barrier schema adds `scope` + `scope_group_finished`; helper to flip/clear.
- `src/codrag/services/pipeline_orchestrator.py` — `run_fast_sync`/`run_deep_enrichment` accept `force_from_start`; finalize-complete callback flips barrier.
- `src/codrag/services/pipeline_provenance.py` — **new**, provenance helper.
- LLM task-assignment resolver (exact module location to be confirmed during plan phase — candidates: `src/codrag/services/llm_coordinator.py`, `src/codrag/core/llm/*`). Must expose a function returning `{provider, model_name}` for a given `task_id`.

**Frontend:**
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — split-button dropdown, sticky row, confirmation modal wiring, chip rendering on stage cards.
- `packages/ui/src/components/trace/rebuildProgress.ts` — scope-aware progress computation.
- `packages/ui/src/components/trace/ProvenanceChip.tsx` — **new**, small presentational component.
- `packages/ui/src/types.ts` — extend stage type with `provenance` field; extend barrier type with `scope` + `scope_group_finished`.
- `src/codrag/dashboard/src/hooks/useEnrichment.ts` — pass `force_from_start` / scope through API client calls; new hook wrapper for `rebuild/stop`.

**Storybook:**
- `packages/ui/src/stories/trace/GraphEnrichmentPipeline.stories.tsx` — stories covering each chip state and each sticky-row phase.
- New story file for `ProvenanceChip`.

### Data flow

```
User clicks Rebuild Enrichment
   ↓
UI calls POST /pipeline/deep {force_from_start: true}
   ↓
Router writes barrier {reason: "rebuild", scope: "enrichment"}
   ↓
Orchestrator runs 6–10 from zero, chains 11–15 incremental
   ↓
Stage 10 completes → barrier.scope_group_finished = true
   ↓
UI sticky row disappears; stages 11–15 continue as normal pipeline
   ↓
(User clicks Stop mid-run) POST /pipeline/rebuild/stop
   ↓
Orchestrator cancels active group; barrier cleared
   ↓
UI exits rebuild mode; completed stages stay; running stage reverts via atomic-swap
```

### Testing

**Backend unit (pytest):**
- `force_from_start=True` on `/pipeline/fast` writes barrier with `scope="sync"`.
- `/pipeline/rebuild/stop` is idempotent when no rebuild is active.
- `compute_stage_provenance` classifies all four states against synthetic manifests.
- Match policy compares `provider + model_name`, ignores `task_id`.

**Backend integration:**
- Full-chain test per the project's "test full import chain" rule: real sqlite manifests, real orchestrator, verify `Rebuild Sync` force-restarts 1–5 and chains 6–10 incrementally (not force-from-start). No mocked seam on the orchestrator itself.
- Barrier flips `scope_group_finished` at the right stage boundary for each scope.

**Frontend unit (vitest):**
- Chip state classification covers all 5 rows of the table in B1.
- Split-button click routing: primary → `all`, caret options → correct scope.
- Sticky row visibility predicate: active AND reason="rebuild" AND scope_group_finished=false.

**Frontend integration (Storybook + Playwright smoke):**
- All chip states render correctly.
- Sticky row appears and disappears at barrier transitions.
- Stop button fires the right endpoint.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `/pipeline/rebuild/stop` races with a stage finishing mid-cancel | Orchestrator cancel path already handles this; stop-endpoint wraps the existing per-group cancel and adds barrier-clear as a post-op. Both operations are idempotent. |
| Incremental cascade after force-rebuild triggers unexpected 10h enrichment run | The confirmation modal's cost estimate includes this — it describes the full chain, not just the forced scope. |
| Model-drift chip fires on embedding-only stages | Those stages return `None` from `compute_stage_provenance`; no chip rendered. |
| Golden-checkpoint evidence is misleading (golden copy is older than the current rebuild) | Never upgrade drift → match; golden is only used to *soften* the "provenance unknown" chip, never to override a positive drift signal. |
| Task-id rename between rebuilds causes false match | Policy explicitly ignores `task_id` (B2). |

## Open questions (none blocking)

All key decisions locked in the design discussion. No open items.

## Success criteria

1. User can click `Rebuild ▾ → Enrichment` and have stages 6–10 force-restart while 1–5 remain untouched.
2. User can click `Stop` in the sticky row mid-rebuild and the pipeline reverts cleanly (current stage to pre-rebuild data; completed stages remain).
3. A stage whose manifest model differs from the current task config shows an amber "built with X → now Y" chip, clicking it starts the right rebuild scope.
4. A self-healed stub stage shows an amber "provenance unknown" chip (or neutral-soft if golden confirms).
5. Full rebuild path (existing `Rebuild All`) is unchanged for users who don't open the dropdown.

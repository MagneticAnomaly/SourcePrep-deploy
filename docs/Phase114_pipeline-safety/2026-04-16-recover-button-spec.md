# Phase 114 — Recover Stage Button (Dashboard UI Spec)

> **For the AI agent picking this up next:** the backend is done and committed
> on `phase114-pipeline-safety`. This doc is the verbose spec for the
> dashboard-side work — Tasks 7-10 of the Phase 114 plan, with the Recover
> button as the headline. Treat this as the source of truth; the original
> plan (`2026-04-16-pipeline-safety-visibility-plan.md`) is more terse and
> predates the backend implementation choices.

## Why This Exists

CoDRAG's 15-stage pipeline occasionally leaves a stage in a "stub" state
(the placeholder manifest selfheal writes when a real run failed). Today
the only fix is a full rebuild — destroying *all* good work to restore
*one* stage. The Recover button gives users a precise scalpel: pick the
broken stage, pick a known-good backup (golden snapshot or per-branch
snapshot), restore just that stage's files, and continue.

The button lives in the **Danger Zone** of each stage row (or the stage
detail drawer) so users have to deliberately reach for it.

## Backend Contract (Already Shipped)

These three endpoints are live on `phase114-pipeline-safety`. Hit them
verbatim — no schema changes needed for the UI work.

### 1. `GET /projects/{project_id}/pipeline/stages/{stage_id}/backups`

**Purpose:** populate the Recover dropdown with available snapshots.

**Curl:**
```bash
curl http://localhost:8400/projects/$PID/pipeline/stages/atlas/backups
```

**Response envelope:**
```json
{
  "success": true,
  "data": {
    "stage_id": "atlas",
    "backups": [
      {
        "snapshot_id": "golden",
        "kind": "golden",
        "branch": null,
        "created_at": 1712345678.0,
        "size_bytes": 4321,
        "file_count": 1,
        "record_count": null
      },
      {
        "snapshot_id": "main_2026-04-15T12-00-00",
        "kind": "branch",
        "branch": "main",
        "created_at": 1712259278.0,
        "size_bytes": 8765,
        "file_count": 2,
        "record_count": null
      }
    ]
  },
  "error": null
}
```

Notes:
- `created_at` is **epoch seconds (float)** — convert to `Date` for display.
- `kind: "golden"` always has `snapshot_id: "golden"` (literal sentinel).
- `kind: "branch"` uses the on-disk dir name as `snapshot_id`. The
  `branch` field tells the user which branch the snapshot came from.
- Empty array means no backups exist — the UI must show a graceful
  "No backups available — run the pipeline at least once" empty state.
- Run checkpoints (`run-<uuid>`) are intentionally **not** returned —
  they're ephemeral (pruned to 3) and the Recover picker should only
  show snapshots that survive restarts.

**Errors:**
- `404 NOT_FOUND` — unknown `stage_id` (not a valid `StageId` enum value).

### 2. `POST /projects/{project_id}/pipeline/stages/{stage_id}/restore`

**Purpose:** the actual restore. Triggered when the user clicks "Restore"
after picking a snapshot from the dropdown.

**Curl:**
```bash
curl -X POST http://localhost:8400/projects/$PID/pipeline/stages/atlas/restore \
  -H "Content-Type: application/json" \
  -d '{"snapshot_id": "golden"}'
```

**Request body:** `{ "snapshot_id": string }` — either `"golden"` or a
branch snapshot's `dir_name` from the LIST response.

**Response envelope (success):**
```json
{
  "success": true,
  "data": {
    "restored": true,
    "stage_id": "atlas",
    "snapshot_id": "golden",
    "files_restored": ["atlas_manifest.json"]
  },
  "error": null
}
```

For stages with a non-None output file (`structural`, `inferred_edges`,
`catalogue`, `enrichment`, `group_reasoning`, `clustering`, `deepening`)
the `files_restored` array contains both the manifest and the JSONL.

**Errors:**
- `400 INVALID_PATH` — `snapshot_id` contains path separators (`..`,
  `/`, etc). Show the user a generic "Invalid snapshot" message and log
  the response body for debugging.
- `404 NOT_FOUND` — unknown stage, or snapshot dir doesn't exist, or
  snapshot has no manifest for this stage. The `error.message` field
  has a human-readable reason; surface it in the toast.

**Side effects to be aware of:**
- The reset barrier is **NOT** consulted — restore is a deliberate
  override. After a successful restore the UI should refresh the
  pipeline status (call the existing `/pipeline/status` endpoint) so
  the stage's cards re-render with the restored manifest's data.
- Other stages are untouched. Only the manifest + (optional) output
  file are copied.

### 3. `GET /projects/{project_id}/pipeline/health` (already wired in T4)

The Recover panel should consume `health.barrier` to show whether the
reset barrier is currently blocking selfheal — gives users context for
why their stage is stuck.

## Current Frontend State

- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — the
  main pipeline panel that lists all 15 stages. Each stage already has
  a row with status, progress, and stage-level actions.
- `packages/ui/src/api/client.ts` — typed wrapper around the backend.
  The new endpoints have **no** client methods yet.
- `packages/ui/src/types.ts` — shared types. Needs the new response
  shapes added.
- `src/codrag/dashboard/src/hooks/useEnrichment.ts` — the dashboard's
  enrichment hook; this is where most pipeline-action handlers
  (rebuild, regenerate, etc.) get wired.

## Type Additions

Append to `packages/ui/src/types.ts`:

```ts
// Phase 114 — per-stage restore
export type StageBackupKind = 'golden' | 'branch'

export interface StageBackup {
  /** "golden" sentinel, or the branch snapshot's on-disk dir name. */
  snapshot_id: string
  kind: StageBackupKind
  /** Source branch when kind === "branch", null for golden. */
  branch: string | null
  /** Epoch seconds when this snapshot was created. */
  created_at: number
  size_bytes: number
  file_count: number
  /** Reserved for future per-stage record counts; currently always null. */
  record_count: number | null
}

export interface StageBackupsResponse {
  stage_id: string
  backups: StageBackup[]
}

export interface StageRestoreResponse {
  restored: true
  stage_id: string
  snapshot_id: string
  files_restored: string[]
}
```

## API Client Methods

Append to `packages/ui/src/api/client.ts`. Match the existing envelope
unwrap pattern — every other client method already does
`return res.data` from the `{success, data, error}` shape.

```ts
async listStageBackups(
  projectId: string,
  stageId: string,
  signal?: AbortSignal,
): Promise<StageBackupsResponse> {
  const res = await this.fetch<StageBackupsResponse>(
    `/projects/${projectId}/pipeline/stages/${stageId}/backups`,
    { method: 'GET', signal },
  )
  return res
}

async restoreStageFromSnapshot(
  projectId: string,
  stageId: string,
  snapshotId: string,
): Promise<StageRestoreResponse> {
  const res = await this.fetch<StageRestoreResponse>(
    `/projects/${projectId}/pipeline/stages/${stageId}/restore`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snapshot_id: snapshotId }),
    },
  )
  return res
}
```

Also add the matching mock implementations in
`packages/ui/src/api/mock.ts` so Storybook stays standalone.

## Component: `RecoverStagePanel`

**File:** `packages/ui/src/components/trace/RecoverStagePanel.tsx` (new)

**Responsibility:** one-shot dropdown + confirm flow for restoring a
single stage from a backup. Stateless about which stage — the parent
passes `stageId` and the component owns the dropdown state plus loading
and confirm-modal state.

### Props

```ts
export interface RecoverStagePanelProps {
  projectId: string
  stageId: string
  /** Display name for the stage in the confirm dialog (e.g. "Atlas"). */
  stageLabel: string
  /** Disabled when pipeline is actively running this stage. */
  disabled?: boolean
  /** Called after a successful restore so the parent can refresh status. */
  onRestored?: (snapshotId: string) => void
}
```

### Visual

A `<details>`-style collapsible card under the stage's existing actions
row, with a "Recover Stage" affordance using the danger color palette
(red border, warning icon — `lucide-react`'s `ShieldAlert` or
`RotateCcw` work well). Closed state is a single button labeled
**"Recover…"**. Opening reveals:

1. A **Tremor `Select`** (or Radix `Select`, matching whatever
   GraphEnrichmentPipeline already uses) listing backups in
   reverse-chronological order:
   ```
   Golden snapshot — 4 KB • 2 hours ago
   main @ 2026-04-15 12:00 — 8 KB • 1 day ago
   feature/foo @ 2026-04-14 18:30 — 6 KB • 2 days ago
   ```
   - Empty state: disable the select, show "No backups for this stage
     yet — run the pipeline at least once."
2. A **Restore** button (filled red), disabled until a snapshot is
   picked.
3. A small footnote: "Restoring overwrites this stage's manifest and
   output. Other stages are untouched. The reset barrier is bypassed."

Clicking **Restore** shows a confirm modal:

```
Restore <stageLabel> from <snapshot label>?

This will overwrite the active <manifest filename>.
Other stages keep their current state.

[Cancel]  [Restore]
```

The confirm button is also danger-styled. Pressing Restore disables both
buttons, calls the API, and on success:
- Closes the modal and the panel
- Shows a success toast: "Restored {stageLabel} from {snapshot label}"
- Calls `onRestored(snapshotId)` so the parent can refresh

On failure: keep the modal open, show inline error from
`error.message`, leave the snapshot selection intact so the user can
retry or pick a different one.

### State (internal)

```ts
const [open, setOpen] = useState(false)
const [backups, setBackups] = useState<StageBackup[] | null>(null)
const [loadError, setLoadError] = useState<string | null>(null)
const [selected, setSelected] = useState<string | null>(null)
const [confirming, setConfirming] = useState(false)
const [restoring, setRestoring] = useState(false)
const [restoreError, setRestoreError] = useState<string | null>(null)
```

Fetch backups lazily when the panel opens (not on mount) — avoids 15
fetches just because the user expanded the pipeline view. Use an
`AbortController` keyed on `(projectId, stageId)` so closing the panel
mid-fetch doesn't update stale state.

### Backup label helper

Extract a small pure function so the test can verify formatting:

```ts
export function formatBackupLabel(b: StageBackup): string {
  const ago = formatRelative(new Date(b.created_at * 1000), new Date())
  const size = formatBytes(b.size_bytes)
  if (b.kind === 'golden') return `Golden snapshot — ${size} • ${ago}`
  return `${b.branch ?? 'unknown'} @ ${formatTimestamp(b.created_at)} — ${size} • ${ago}`
}
```

(`formatRelative`, `formatBytes`, `formatTimestamp` already exist in
`packages/ui/src/lib/format.ts` or similar — find and reuse, don't
duplicate.)

## Wiring Into `GraphEnrichmentPipeline`

The pipeline panel renders one row per stage. The Recover panel
attaches under the existing per-stage action row. Don't add it to every
stage's main visual — gate behind:

```ts
const showRecover = stage.status === 'failed'
                 || stage.provenance === 'selfheal_stub'
                 || userExpandedDangerZone
```

Where `userExpandedDangerZone` is a per-stage local-storage flag
(toggled by a tiny "Danger Zone" caret next to the stage actions).
Default state: hidden. Once a user opens it for a stage, remember.

### Refresh behavior on success

The `onRestored` callback should:
1. Invalidate the pipeline status fetch (refetch `/pipeline/status`).
2. Invalidate the per-stage trace data if the user is viewing it.
3. Toast.

The existing `useEnrichment` hook already has a `refresh()` method —
plumb it through.

## Test Plan

### Unit / component (Storybook + Vitest in `packages/ui`)

Create `packages/ui/src/components/trace/__tests__/RecoverStagePanel.test.tsx`:

1. **Renders closed state** — a single "Recover…" button, no fetch.
2. **Opens on click and fetches backups** — mock the API client, expect
   `listStageBackups(pid, sid)` to be called once.
3. **Renders empty state when API returns `[]`** — disabled select,
   helpful message.
4. **Renders backup list with golden + branch entries** — verify
   labels match `formatBackupLabel`.
5. **Restore button is disabled until a snapshot is picked.**
6. **Confirm modal flow** — click Restore → modal opens → click Restore
   in modal → API call → success toast → `onRestored` called.
7. **Error path** — API returns 404 → modal stays open, error message
   visible, snapshot selection preserved.
8. **Disabled prop** — when `disabled` is true, the open button is
   disabled and shows a tooltip "Pipeline is running — wait for the
   active stage to finish."

### Storybook stories

Add `packages/ui/src/stories/trace/RecoverStagePanel.stories.tsx`
with:
- `Default` — golden + 2 branch snapshots
- `EmptyBackups` — backups: `[]`
- `Loading` — fetch in flight
- `LoadError` — fetch failed
- `Restoring` — POST in flight
- `Disabled` — pipeline running

### Integration / smoke

Add a manual smoke item to the pipeline-testing skill runbook:

> **Recover Stage smoke:**
> 1. Run a full pipeline against
>    `/Volumes/4TB-BAD/HumanAI/CoDRAG/tests/eval/sample_repos/generated/swift_repo`
>    until atlas completes (golden snapshot is now written).
> 2. Manually corrupt `atlas_manifest.json` in the `.codrag/` index
>    dir (or set `provenance: "selfheal_stub"`).
> 3. Refresh the dashboard. Atlas row should show stub indicator.
> 4. Open Atlas's Danger Zone → Recover → pick "Golden snapshot" →
>    Restore.
> 5. Atlas row should refresh to non-stub state within 2 seconds.

## Acceptance Checklist

- [ ] `StageBackup`, `StageBackupsResponse`, `StageRestoreResponse`
      exported from `packages/ui/src/types.ts`.
- [ ] `listStageBackups` and `restoreStageFromSnapshot` methods on the
      API client (real + mock).
- [ ] `RecoverStagePanel` component renders, fetches lazily, surfaces
      error states, calls `onRestored` on success.
- [ ] `formatBackupLabel` is a pure exported function with its own
      unit tests.
- [ ] Wired into `GraphEnrichmentPipeline.tsx` behind a per-stage
      Danger Zone toggle.
- [ ] 8 Vitest tests pass in `packages/ui`.
- [ ] 6 Storybook stories render without error.
- [ ] Manual smoke against `swift_repo` passes.
- [ ] No new circular imports (the existing `GraphEnrichmentPipeline ↔
      pipelineRollup` cycle is the baseline).

## Out of Scope (Defer to Phase 115 or later)

- **Multi-stage restore** — picking several stages and restoring them
  atomically. Today the user must restore stages one at a time.
- **Pre-restore diff preview** — showing which fields will change.
  Useful but adds significant scope.
- **Automatic recommendation** — "your atlas is stub, want to restore
  from golden?" The backend `health.stages[*].manifest_status` already
  exposes the stub flag; surfacing a passive nudge in the UI is a
  reasonable follow-up but not part of this slice.
- **Audit log** — recording who restored what when. The journal
  currently doesn't track restore events. Either fold into observe
  notes via `codrag_observe` or add a journal entry in a follow-up.
- **Restore from run checkpoint** — intentionally excluded from the
  picker. If a user really wants it, they can use the CLI.

## Files Touched (When Implementing)

| File | Change |
|------|--------|
| `packages/ui/src/types.ts` | Add 4 type exports |
| `packages/ui/src/api/client.ts` | Add 2 client methods |
| `packages/ui/src/api/mock.ts` | Add 2 mock implementations |
| `packages/ui/src/components/trace/RecoverStagePanel.tsx` | New |
| `packages/ui/src/components/trace/__tests__/RecoverStagePanel.test.tsx` | New |
| `packages/ui/src/stories/trace/RecoverStagePanel.stories.tsx` | New |
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | Wire panel under per-stage actions |
| `src/codrag/dashboard/src/hooks/useEnrichment.ts` | Plumb `refresh()` to `onRestored` |
| `.claude/skills/pipeline-testing/SKILL.md` | Append the smoke section |

## Backend Sanity Reference

If anything in the contract section above doesn't match what the daemon
returns, the source of truth is:

- Endpoint definitions:
  `src/codrag/api/routers/pipeline.py:1100-1265`
- Path-traversal guard:
  `src/codrag/api/routers/pipeline.py:1230-1245`
- Stage manifest map:
  `src/codrag/services/pipeline/stages.py:186-202`
- Stage output map:
  `src/codrag/services/pipeline/stages.py:208-224`
- Backend tests covering every shape in this doc:
  `tests/test_pipeline_stage_backups.py`,
  `tests/test_pipeline_stage_restore.py`

---

**Implementer note:** When you start, dispatch a fresh subagent per
slice (types → client → component → wiring) with the relevant section
of this doc pasted into the prompt. Don't ask the subagent to read the
whole spec — give them the slice. The backend is solid; if a test
fails, suspect the UI wiring before touching pipeline.py.

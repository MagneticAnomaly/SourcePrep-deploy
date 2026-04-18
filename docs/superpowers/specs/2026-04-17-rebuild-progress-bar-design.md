# Rebuild Progress Bar Variant — Design

**Date:** 2026-04-17
**Status:** Approved — ready for implementation plan

## Problem

The dashboard's trace-pipeline panel currently has two progress-bar treatments:

- **Initialize** — single-color blue bar for first-time index builds
- **Incremental** — horizontal 2-tone (green done / orange stale) for rerun-of-subset runs (F-66 baseline preservation)

These collapse together in the user's head during a full **rebuild** (`POST /pipeline/rebuild`, barrier `rebuild`). A rebuild is semantically different from both: the old index is still serving queries the whole time, and the new index is being built from scratch on top of it. Neither existing bar communicates that.

## Solution

Introduce a third progress-bar variant — **rebuild** — that renders as a stacked-halves bar: solid green on the bottom half, orange fill on the top half.

- **Bottom half:** solid green across full width for the entire rebuild. Communicates "the existing index is still complete, saved, and serving queries."
- **Top half:** orange bar that fills 0 → 100% as the rebuild progresses.

Shown both per-stage (each of the 15 stage rows) and as a single overall bar at the top of the pipeline panel (visible in both expanded and collapsed views).

## Architecture

### Detection signal

`/pipeline/status` already returns a `reset_barrier` field. `GraphEnrichmentPipeline` treats `reset_barrier === 'rebuild'` as the pipeline-level "rebuild in progress" signal.

### Per-stage state extension

Extend the `StageState` union in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`:

```ts
type StageState =
  | 'disabled' | 'waiting' | 'queued' | 'running' | 'rerunning'
  | 'rebuilding'   // NEW
  | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';
```

A stage is `'rebuilding'` when `reset_barrier === 'rebuild'` **and** its underlying status is `running` or `queued`. When a stage completes during a rebuild, it transitions `'rebuilding' → 'complete'` — the whole bar becomes solid green, matching the atomic DB-swap semantics.

### Prop flow

```
/pipeline/status → GraphEnrichmentPipeline
                     │  derives isRebuilding, per-stage state
                     ├─→ StageRow × N → StageProgressBar(variant='rebuild', rebuildPercent=stageProgress)
                     └─→ OverallHeaderBar → StageProgressBar(variant='rebuild', rebuildPercent=aggregate)
```

### Overall aggregate math

```ts
const overallRebuildPercent =
  stages.reduce((sum, s) => sum + perStagePercent(s), 0) / stages.length;

function perStagePercent(stage: Stage): number {
  if (stage.state === 'complete') return 100;
  if (stage.state === 'rebuilding') return stage.progress ?? 0;
  return 0;
}
```

Smooth, updates continuously, finished stages contribute full 100% each.

## Component API

File: `packages/ui/src/components/trace/StageProgressBar.tsx`

```ts
interface StageProgressBarProps {
  progress?: number;        // 0-100 for initialize/incremental fills
  className?: string;
  color?: string;           // initialize fill color (e.g. bg-blue-500, bg-purple-500)
  rerun?: { donePercent: number; stalePercent: number };  // incremental trigger
  variant?: 'initialize' | 'incremental' | 'rebuild';     // NEW - explicit mode
  rebuildPercent?: number;  // NEW - 0-100 for rebuild's orange top half
}
```

### Variant selection priority (backward-compatible)

1. `variant === 'rebuild'` → stacked-halves render
2. `variant === 'incremental'` **or** `rerun` prop present → existing 3-segment horizontal bar
3. Otherwise → single-color fill using `color` prop (today's default)

The implicit `rerun`-triggers-incremental behavior is retained so existing callsites do not need edits. New callsites prefer the explicit `variant`.

### Rebuild render layout

```
┌──────────────────────────────────────────┐
│ █████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  top half: orange, width = rebuildPercent%
│ ████████████████████████████████████████ │  bottom half: solid green, always 100%
└──────────────────────────────────────────┘
```

- Outer container preserves current bar height and rounded corners.
- Two inner `<div>`s, each `h-1/2`, positioned top/bottom.
- Orange = `bg-orange-500` (matches the current incremental accent).
- Green = `bg-success` (the same token already used for the done segment of today's 3-segment incremental bar — solid, no opacity on the rebuild bottom half).

## Placement

### Expanded view

A new overall bar renders at the top of `GraphEnrichmentPipeline` (above the stage list) **only when** `isRebuilding === true`. Additive — no change to today's header in other modes.

### Collapsed view

The collapsed pipeline card already mirrors the expanded panel's top-line state. Extend the same overall bar into the collapsed card so the two views render the identical dual-tone bar during a rebuild. This matches the user's explicit requirement that collapsed = uncollapsed.

## Edge states

| Scenario | Treatment |
|---|---|
| **Paused rebuild** | Orange frozen at current %. Reuse whatever paused-state visual the existing initialize/incremental bars use today (consistency > invention). Green bottom stays fully saturated — the old index is still live. |
| **Failed stage during rebuild** | Stage state → `'error'`. Top half becomes `bg-red-500` full width. Green bottom stays intact. Overall header bar keeps dual-tone based on remaining viable stages. |
| **Cancelled rebuild** | Barrier clears → `isRebuilding` false → rebuild variant evaporates. Stages fall back to their natural post-cancel state. No special treatment. |
| **First-ever build** | No barrier (or barrier ≠ `rebuild`). Falls through to existing `'running'` + blue initialize variant. No regression. |
| **Incremental run** | Barrier ≠ `rebuild`. Stage rows keep today's 3-segment incremental bar. Overall header bar absent (unchanged from today). |
| **Barrier clears mid-frame** | `isRebuilding` flips false, overall bar disappears, stage rows transition to natural post-run state (`complete` if finished, `idle` otherwise). |

## Testing

- **Storybook** — add three stories to `StageProgressBar.stories.tsx`: `Initialize`, `Incremental`, `Rebuild`, each with a 0–100 percent knob.
- **Unit test** — verify the state-to-variant mapping in `GraphEnrichmentPipeline`: given a pipeline status fixture with `reset_barrier: 'rebuild'` and a stage in `running`, the derived `StageState` is `'rebuilding'` and the `StageProgressBar` receives `variant='rebuild'` + the correct `rebuildPercent`.
- **Integration** — one test that does **not** mock the `reset_barrier` seam (Phase 112 lesson about full-import-chain testing). Drive via a daemon fixture where `/pipeline/status` returns `reset_barrier: 'rebuild'`; assert the rendered DOM contains the rebuild bar in both the header slot and each stage row.

## Scope

**In scope:**
- `StageProgressBar` variant prop + stacked-halves render layout.
- `StageState` union extended with `'rebuilding'`.
- `GraphEnrichmentPipeline` detection logic (`reset_barrier === 'rebuild'`) and prop plumbing.
- New overall header bar rendered at the top of `GraphEnrichmentPipeline` (a second `StageProgressBar` instance with `variant='rebuild'` and the aggregate `rebuildPercent`), mirrored into the collapsed pipeline card so both views are identical.
- Storybook stories + unit + integration tests.

**Out of scope:**
- Changes to the blue initialize bar or the incremental 3-segment bar.
- Changes to `/pipeline/status` server-side (already returns `reset_barrier`).
- Changes to the barrier lifecycle (`reset_barrier` is already written by `POST /pipeline/rebuild`).
- Other progress-indicator surfaces (MCP CLI, logs, etc.).

## Open questions

None at design time — all clarifications resolved during brainstorming:
1. Scope: both per-stage and overall header (user confirmed).
2. Stage-complete-during-rebuild: whole bar flips solid green, matches atomic DB swap (user chose (b)).
3. Overall bar math: weighted by per-stage progress, continuous fill (user chose (b)).
4. Approach: extend `StageProgressBar` with explicit `variant` prop (user chose A).
5. Detection granularity: per-stage `state: 'rebuilding'` added to `StageState` (user chose (ii)).

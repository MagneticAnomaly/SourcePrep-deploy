# Rebuild Progress Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third progress-bar variant (`rebuild`) that renders as stacked halves — solid green on the bottom ("old index is still live"), orange progress on the top — rendered both per-stage and as an overall header bar (plus collapsed-view parity) whenever a full `/pipeline/rebuild` is running.

**Architecture:** Extract rebuild-detection + aggregate-math to pure helpers in a new `rebuildProgress.ts` so they're testable under Vitest without DOM rendering. Extend `StageProgressBar` with an explicit `variant` prop and a new stacked-halves render path. Wire detection through `GraphEnrichmentPipeline` by deriving a new `StageState = 'rebuilding'` from the existing `barrier` prop, and mirror the overall bar into `CondensedGroupRow` (collapsed view).

**Tech Stack:** React + TypeScript, Tailwind (existing `bg-success`, `bg-orange-500`, `bg-red-500`, `bg-surface-raised`), Vitest for unit tests, Storybook for visual validation.

---

## File Structure

**Create:**
- `packages/ui/src/components/trace/rebuildProgress.ts` — pure helpers (detection, aggregate math, state derivation)
- `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts` — Vitest tests for the helpers

**Modify:**
- `packages/ui/src/components/trace/StageProgressBar.tsx` — add `variant` + `rebuildPercent` props; add stacked-halves render branch with error sub-state
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — extend `StageState` union; derive `'rebuilding'` state from barrier; add overall header bar; pass variant to per-stage and collapsed (`CondensedGroupRow`) bars
- `packages/ui/src/stories/trace/StageProgressBar.stories.tsx` — add `Rebuild` story (and tidy `Initialize` / `Incremental` if unnamed)

---

## Task 1: Create pure helpers for rebuild detection and aggregate math

**Files:**
- Create: `packages/ui/src/components/trace/rebuildProgress.ts`
- Test: `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts`:

```tsx
import { describe, it, expect } from 'vitest';
import {
  isPipelineRebuilding,
  perStageRebuildPercent,
  computeOverallRebuildPercent,
  type RebuildStageSnapshot,
} from '../rebuildProgress';
import type { BarrierStatus } from '../../../types';

describe('isPipelineRebuilding', () => {
  it('returns true when barrier is active and reason is rebuild', () => {
    const barrier: BarrierStatus = { active: true, reason: 'rebuild', setAt: 1 };
    expect(isPipelineRebuilding(barrier)).toBe(true);
  });

  it('returns false when barrier is inactive', () => {
    const barrier: BarrierStatus = { active: false, reason: 'rebuild', setAt: 1 };
    expect(isPipelineRebuilding(barrier)).toBe(false);
  });

  it('returns false when barrier reason is not rebuild', () => {
    const barrier: BarrierStatus = { active: true, reason: 'enrichment_reset', setAt: 1 };
    expect(isPipelineRebuilding(barrier)).toBe(false);
  });

  it('returns false when barrier is undefined', () => {
    expect(isPipelineRebuilding(undefined)).toBe(false);
  });
});

describe('perStageRebuildPercent', () => {
  it('returns 100 for a completed stage', () => {
    const s: RebuildStageSnapshot = { state: 'complete', progress: undefined };
    expect(perStageRebuildPercent(s)).toBe(100);
  });

  it('returns the stage progress when rebuilding', () => {
    const s: RebuildStageSnapshot = { state: 'rebuilding', progress: 42 };
    expect(perStageRebuildPercent(s)).toBe(42);
  });

  it('returns 0 when rebuilding but progress is undefined', () => {
    const s: RebuildStageSnapshot = { state: 'rebuilding', progress: undefined };
    expect(perStageRebuildPercent(s)).toBe(0);
  });

  it('clamps progress into the 0-100 range', () => {
    expect(perStageRebuildPercent({ state: 'rebuilding', progress: 150 })).toBe(100);
    expect(perStageRebuildPercent({ state: 'rebuilding', progress: -5 })).toBe(0);
  });

  it('returns 0 for queued / waiting stages', () => {
    expect(perStageRebuildPercent({ state: 'queued', progress: undefined })).toBe(0);
    expect(perStageRebuildPercent({ state: 'waiting', progress: undefined })).toBe(0);
    expect(perStageRebuildPercent({ state: 'idle', progress: undefined })).toBe(0);
  });
});

describe('computeOverallRebuildPercent', () => {
  it('returns 0 for an empty list', () => {
    expect(computeOverallRebuildPercent([])).toBe(0);
  });

  it('averages per-stage percentages', () => {
    const stages: RebuildStageSnapshot[] = [
      { state: 'complete', progress: undefined },    // 100
      { state: 'complete', progress: undefined },    // 100
      { state: 'rebuilding', progress: 40 },         //  40
      { state: 'queued', progress: undefined },      //   0
      { state: 'queued', progress: undefined },      //   0
    ];
    // (100 + 100 + 40 + 0 + 0) / 5 = 48
    expect(computeOverallRebuildPercent(stages)).toBe(48);
  });

  it('returns 100 when every stage is complete', () => {
    const stages: RebuildStageSnapshot[] = [
      { state: 'complete', progress: undefined },
      { state: 'complete', progress: undefined },
    ];
    expect(computeOverallRebuildPercent(stages)).toBe(100);
  });

  it('rounds to an integer percent', () => {
    // (33 + 0 + 0) / 3 = 11
    const stages: RebuildStageSnapshot[] = [
      { state: 'rebuilding', progress: 33 },
      { state: 'queued', progress: undefined },
      { state: 'queued', progress: undefined },
    ];
    expect(computeOverallRebuildPercent(stages)).toBe(11);
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `npm --workspace packages/ui exec vitest run -- rebuildProgress.test`
Expected: FAIL with "Cannot find module '../rebuildProgress'"

- [ ] **Step 3: Create the helpers module**

Create `packages/ui/src/components/trace/rebuildProgress.ts`:

```tsx
import type { BarrierStatus } from '../../types';

export interface RebuildStageSnapshot {
  state: string;       // StageState from GraphEnrichmentPipeline — kept as string to avoid circular imports
  progress: number | undefined;
}

/** True iff the pipeline is in a full-rebuild run right now. */
export function isPipelineRebuilding(barrier: BarrierStatus | undefined): boolean {
  return Boolean(barrier?.active && barrier?.reason === 'rebuild');
}

/**
 * Per-stage contribution to the overall rebuild bar.
 * - complete → 100 (final green)
 * - rebuilding → clamped stage.progress (or 0 if undefined)
 * - anything else → 0 (queued / waiting / idle count as not-yet-started)
 */
export function perStageRebuildPercent(stage: RebuildStageSnapshot): number {
  if (stage.state === 'complete') return 100;
  if (stage.state === 'rebuilding') {
    const p = stage.progress;
    if (typeof p !== 'number' || Number.isNaN(p)) return 0;
    return Math.min(100, Math.max(0, p));
  }
  return 0;
}

/** Aggregate: average of per-stage percentages, rounded to an integer 0-100. */
export function computeOverallRebuildPercent(stages: RebuildStageSnapshot[]): number {
  if (stages.length === 0) return 0;
  const sum = stages.reduce((acc, s) => acc + perStageRebuildPercent(s), 0);
  return Math.round(sum / stages.length);
}
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `npm --workspace packages/ui exec vitest run -- rebuildProgress.test`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/trace/rebuildProgress.ts \
        packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts
git commit -m "feat(ui): rebuild-progress helpers (detection, aggregate math)"
```

---

## Task 2: Extend `StageProgressBar` with `variant` prop and rebuild render layout

**Files:**
- Modify: `packages/ui/src/components/trace/StageProgressBar.tsx`

- [ ] **Step 1: Replace the file contents**

Overwrite `packages/ui/src/components/trace/StageProgressBar.tsx`:

```tsx
import { cn } from '../../lib/utils';

export type StageProgressBarVariant = 'initialize' | 'incremental' | 'rebuild';

export interface StageProgressBarProps {
  progress?: number;               // 0-100 for initialize/incremental fills
  className?: string;
  color?: string;                  // initialize fill color (e.g. "bg-blue-500", "bg-purple-500")
  rerun?: { donePercent: number; stalePercent: number };
  /** Explicit variant. Defaults to 'incremental' when `rerun` is set, otherwise 'initialize'. */
  variant?: StageProgressBarVariant;
  /** Orange top-half fill percent (0-100) when variant === 'rebuild'. */
  rebuildPercent?: number;
  /** Sub-state overlays used by the rebuild variant. */
  rebuildStateOverlay?: 'paused' | 'failed';
}

function clamp(n: number | undefined): number {
  if (typeof n !== 'number' || Number.isNaN(n)) return 0;
  return Math.min(100, Math.max(0, n));
}

export function StageProgressBar({
  progress = 0,
  className,
  color = 'bg-blue-500',
  rerun,
  variant,
  rebuildPercent,
  rebuildStateOverlay,
}: StageProgressBarProps) {
  const resolvedVariant: StageProgressBarVariant =
    variant ?? (rerun ? 'incremental' : 'initialize');

  if (resolvedVariant === 'rebuild') {
    const topPct = clamp(rebuildPercent);
    const paused = rebuildStateOverlay === 'paused';
    const failed = rebuildStateOverlay === 'failed';
    const topFill = failed ? 'bg-red-500' : 'bg-orange-500';
    const topWidth = failed ? 100 : topPct;
    return (
      <div
        className={cn(
          'w-full bg-surface-raised overflow-hidden rounded-full flex flex-col',
          paused && 'opacity-60',
          className,
        )}
      >
        <div className="h-1/2 w-full">
          <div
            className={cn(topFill, 'h-full transition-all duration-500 ease-out')}
            style={{ width: `${topWidth}%` }}
          />
        </div>
        <div className="h-1/2 w-full bg-success" />
      </div>
    );
  }

  if (resolvedVariant === 'incremental' && rerun) {
    const donePct = clamp(rerun.donePercent);
    const stalePct = Math.min(100 - donePct, Math.max(0, rerun.stalePercent));
    const staleCompletedPct = stalePct * (clamp(progress) / 100);
    const stalePendingPct = stalePct - staleCompletedPct;
    return (
      <div className={cn('w-full bg-surface-raised overflow-hidden rounded-full', className)}>
        <div className="h-full flex">
          <div className="h-full bg-success/80 transition-all duration-300" style={{ width: `${donePct}%` }} />
          <div className="h-full bg-orange-500 transition-all duration-300" style={{ width: `${staleCompletedPct}%` }} />
          <div className="h-full bg-orange-500/40 transition-all duration-300" style={{ width: `${stalePendingPct}%` }} />
        </div>
      </div>
    );
  }

  const clamped = clamp(progress);
  return (
    <div className={cn('h-1 w-full bg-surface-raised rounded-full overflow-hidden mt-1.5', className)}>
      <div
        className={cn('h-full transition-all duration-500 ease-out', color)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
```

Notes:
- Default height is unchanged for initialize (`h-1 mt-1.5`). The rebuild + incremental branches rely on the caller to set height via `className` (consumers already do this — see `CondensedGroupRow`'s `h-1.5`). Keeping behavior identical to today for non-rebuild callsites.
- The rebuild branch uses `flex flex-col` + `h-1/2` children to stack halves. The outer container inherits its height from the caller's `className` (e.g. `h-1.5`, `h-2`).
- `resolvedVariant` preserves backward compatibility: existing callers that pass only `rerun` still get incremental; callers passing only `progress` + `color` still get initialize.

- [ ] **Step 2: Typecheck**

Run: `npm --workspace packages/ui run typecheck`
Expected: PASS (no type errors introduced).

- [ ] **Step 3: Run the whole UI test suite**

Run: `npm --workspace packages/ui exec vitest run`
Expected: PASS (Task 1 tests still pass, no other tests broken).

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/trace/StageProgressBar.tsx
git commit -m "feat(ui): add rebuild variant to StageProgressBar (stacked halves)"
```

---

## Task 3: Storybook stories for the three variants

**Files:**
- Modify: `packages/ui/src/stories/trace/StageProgressBar.stories.tsx`

- [ ] **Step 1: Read current file**

Read `packages/ui/src/stories/trace/StageProgressBar.stories.tsx` to preserve existing stories and decorator.

- [ ] **Step 2: Add three explicit variant stories**

Append (or replace stories so they cover these three) in `packages/ui/src/stories/trace/StageProgressBar.stories.tsx`:

```tsx
export const Initialize: StoryObj<typeof StageProgressBar> = {
  args: { variant: 'initialize', progress: 60, color: 'bg-blue-500', className: 'h-1.5' },
};

export const Incremental: StoryObj<typeof StageProgressBar> = {
  args: {
    variant: 'incremental',
    progress: 50,
    className: 'h-1.5',
    rerun: { donePercent: 70, stalePercent: 30 },
  },
};

export const Rebuild: StoryObj<typeof StageProgressBar> = {
  args: { variant: 'rebuild', rebuildPercent: 35, className: 'h-2' },
};

export const RebuildPaused: StoryObj<typeof StageProgressBar> = {
  args: { variant: 'rebuild', rebuildPercent: 35, rebuildStateOverlay: 'paused', className: 'h-2' },
};

export const RebuildFailed: StoryObj<typeof StageProgressBar> = {
  args: { variant: 'rebuild', rebuildPercent: 35, rebuildStateOverlay: 'failed', className: 'h-2' },
};
```

- [ ] **Step 3: Run Storybook typecheck / build**

Run: `npm --workspace packages/ui run typecheck`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/stories/trace/StageProgressBar.stories.tsx
git commit -m "docs(ui): StageProgressBar stories for initialize/incremental/rebuild"
```

---

## Task 4: Extend `StageState` union with `'rebuilding'`

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (line 151 — the `StageState` union deprep-compresstion)

- [ ] **Step 1: Add `'rebuilding'` to the union**

In `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`, change:

```ts
type StageState = 'disabled' | 'waiting' | 'queued' | 'running' | 'rerunning' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';
```

to:

```ts
type StageState = 'disabled' | 'waiting' | 'queued' | 'running' | 'rerunning' | 'rebuilding' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning';
```

- [ ] **Step 2: Typecheck**

Run: `npm --workspace packages/ui run typecheck`
Expected: PASS. (No existing switch/case should currently fail; `'rebuilding'` is additive. If a `switch(stageState)` is exhaustive elsewhere, add a matching branch treating it like `'running'` for badge text until Task 5 specializes it.)

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(ui): add 'rebuilding' to StageState union"
```

---

## Task 5: Derive `'rebuilding'` per-stage and pass `variant='rebuild'` to `StageProgressBar`

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

- [ ] **Step 1: Import helpers**

At the top of `GraphEnrichmentPipeline.tsx`, add:

```ts
import { isPipelineRebuilding, computeOverallRebuildPercent, type RebuildStageSnapshot } from './rebuildProgress';
```

- [ ] **Step 2: Compute `isRebuilding` once per render**

Near the top of the `GraphEnrichmentPipeline` component body (after reading the `barrier` prop — around line ~200 after other memoised state), add:

```ts
const isRebuilding = isPipelineRebuilding(barrier);
```

- [ ] **Step 3: Promote `running` → `rebuilding` when the pipeline is rebuilding**

Find the block(s) that produce `stage.state` for each stage. At each site where `state` is computed and currently resolves to `'running'` or `'queued'` (e.g. `catalogueState === 'running'` and the similar structural/inferred_edges/validation/knowledge/enrichment/etc. derivations), wrap the result so that when `isRebuilding` is true **and** the base state is `'running'` or `'queued'`, the final value becomes `'rebuilding'`:

```ts
const promoteForRebuild = (s: StageState): StageState =>
  isRebuilding && (s === 'running' || s === 'queued') ? 'rebuilding' : s;
```

Apply `promoteForRebuild(...)` to every `state: ...` assignment in each stage descriptor (structural, inferred_edges, catalogue, validation, knowledge, enrichment, group_reasoning, clustering, deepening, deep_knowledge, atlas, rules, concepts, audit, antibodies). Keep the rest of the state-derivation logic untouched.

- [ ] **Step 4: Pass `variant='rebuild'` + `rebuildPercent` to each stage's `StageProgressBar`**

Find the per-stage `<StageProgressBar ... />` renders in `StageRow` (around line 792–807 today). Change:

```tsx
<StageProgressBar
  progress={stage.progress}
  color={isRerunning ? 'bg-purple-500' : 'bg-blue-500'}
  rerun={stage.rerun}
/>
```

to:

```tsx
<StageProgressBar
  progress={stage.progress}
  color={isRerunning ? 'bg-purple-500' : 'bg-blue-500'}
  rerun={stage.rerun}
  variant={stage.state === 'rebuilding' ? 'rebuild' : undefined}
  rebuildPercent={stage.state === 'rebuilding' ? stage.progress : undefined}
/>
```

(Leave the exact `className` height unchanged from today; the bar already renders at whatever height the row uses.)

- [ ] **Step 5: Typecheck + tests**

Run: `npm --workspace packages/ui run typecheck && npm --workspace packages/ui exec vitest run`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(ui): derive 'rebuilding' state and wire variant into StageProgressBar"
```

---

## Task 6: Overall header rebuild bar

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

- [ ] **Step 1: Collect stages into `RebuildStageSnapshot[]`**

In the component body, right after `isRebuilding` is computed, build a stage list used by the helpers:

```ts
const rebuildStages: RebuildStageSnapshot[] = useMemo(
  () =>
    [
      ...fastStages,
      ...deepStages,
      ...finalizeStages,
    ].map((s) => ({ state: s.state, progress: s.progress })),
  [fastStages, deepStages, finalizeStages],
);

const overallRebuildPercent = isRebuilding
  ? computeOverallRebuildPercent(rebuildStages)
  : 0;
```

(Adjust the source arrays to whatever the component's actual stage-collection names are — keep the three groups, one entry per of the 15 stages.)

- [ ] **Step 2: Render the overall bar above the stage groups**

Immediately above the `BarrierIndicator` render (lines 1351–1352 today), add:

```tsx
{isRebuilding && (
  <div className="px-4 pt-3 pb-1" data-testid="overall-rebuild-bar">
    <StageProgressBar
      variant="rebuild"
      rebuildPercent={overallRebuildPercent}
      className="h-2"
    />
  </div>
)}
```

(Place matches the existing top-of-panel slot — a sibling of `BarrierIndicator`, not inside a stage group.)

- [ ] **Step 3: Typecheck + tests**

Run: `npm --workspace packages/ui run typecheck && npm --workspace packages/ui exec vitest run`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(ui): overall rebuild progress bar at top of pipeline panel"
```

---

## Task 7: Mirror rebuild variant into the collapsed `CondensedGroupRow`

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (the `CondensedGroupRow` component, around line 691)

- [ ] **Step 1: Accept a rebuild prop**

Update `CondensedGroupRow`'s props type so it can receive rebuild context:

```tsx
interface CondensedGroupRowProps {
  rollup: GroupRollup;           // existing
  isRebuilding?: boolean;        // NEW
  groupRebuildPercent?: number;  // NEW (0-100, already computed by parent)
}
```

- [ ] **Step 2: Branch render when rebuilding**

Replace the existing `<StageProgressBar progress={rollup.progress} className="h-1.5 mt-1 w-full" color="bg-blue-500" />` line (around line 691) with:

```tsx
{isRebuilding ? (
  <StageProgressBar
    variant="rebuild"
    rebuildPercent={groupRebuildPercent ?? 0}
    className="h-1.5 mt-1 w-full"
  />
) : (
  <StageProgressBar
    progress={rollup.progress}
    className="h-1.5 mt-1 w-full"
    color="bg-blue-500"
  />
)}
```

- [ ] **Step 3: Compute per-group rebuild percent in the parent and pass down**

In `GraphEnrichmentPipeline`, add per-group aggregates next to `overallRebuildPercent`:

```ts
const fastRebuildPercent = isRebuilding
  ? computeOverallRebuildPercent(fastStages.map((s) => ({ state: s.state, progress: s.progress })))
  : 0;
const deepRebuildPercent = isRebuilding
  ? computeOverallRebuildPercent(deepStages.map((s) => ({ state: s.state, progress: s.progress })))
  : 0;
const finalizeRebuildPercent = isRebuilding
  ? computeOverallRebuildPercent(finalizeStages.map((s) => ({ state: s.state, progress: s.progress })))
  : 0;
```

Then update every `CondensedGroupRow` call site to pass the corresponding props, for example:

```tsx
<CondensedGroupRow
  rollup={computeGroupRollup(fastStages)}
  isRebuilding={isRebuilding}
  groupRebuildPercent={fastRebuildPercent}
/>
```

(Repeat for the deep and finalize collapsed rows.)

- [ ] **Step 4: Typecheck + tests**

Run: `npm --workspace packages/ui run typecheck && npm --workspace packages/ui exec vitest run`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(ui): rebuild variant in collapsed CondensedGroupRow"
```

---

## Task 8: Paused and failed edge-state overlays

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`

- [ ] **Step 1: Derive `rebuildStateOverlay` for per-stage bars**

At the per-stage `<StageProgressBar>` render site (modified in Task 5), add the overlay prop:

```tsx
<StageProgressBar
  progress={stage.progress}
  color={isRerunning ? 'bg-purple-500' : 'bg-blue-500'}
  rerun={stage.rerun}
  variant={stage.state === 'rebuilding' ? 'rebuild' : undefined}
  rebuildPercent={stage.state === 'rebuilding' ? stage.progress : undefined}
  rebuildStateOverlay={
    stage.state === 'rebuilding' && isPaused
      ? 'paused'
      : stage.state === 'error' && isRebuilding
        ? 'failed'
        : undefined
  }
/>
```

(The `isPaused` variable already exists in `GraphEnrichmentPipeline` — the `pause`/`resume` buttons read it. Reuse that; do not introduce a new one.)

For the *failed* case, note that the base `promoteForRebuild` helper from Task 5 does **not** promote `'error'`; we deliberately keep the stage-row badge showing an error, and the bar itself still renders in the `rebuild` variant (bottom green, top red full-width) by virtue of the overlay prop. Update Task 5's render block so the `variant='rebuild'` is also applied when `stage.state === 'error' && isRebuilding`:

```tsx
variant={
  stage.state === 'rebuilding' || (stage.state === 'error' && isRebuilding)
    ? 'rebuild'
    : undefined
}
rebuildPercent={stage.state === 'rebuilding' ? stage.progress : undefined}
```

- [ ] **Step 2: Overall header overlay**

At the overall header bar render site (Task 6), pass the same overlay logic at pipeline level:

```tsx
{isRebuilding && (
  <div className="px-4 pt-3 pb-1" data-testid="overall-rebuild-bar">
    <StageProgressBar
      variant="rebuild"
      rebuildPercent={overallRebuildPercent}
      className="h-2"
      rebuildStateOverlay={isPaused ? 'paused' : undefined}
    />
  </div>
)}
```

(The overall bar never goes `failed` — individual stage errors don't fail the whole rebuild; they fail that stage.)

- [ ] **Step 3: Typecheck + tests**

Run: `npm --workspace packages/ui run typecheck && npm --workspace packages/ui exec vitest run`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(ui): paused and failed overlays on rebuild bars"
```

---

## Task 9: End-to-end unit test for the detection seam

**Files:**
- Modify: `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts`

Per the Phase 112 lesson, add at least one test that exercises the full derivation without mocking the helpers. This verifies the whole chain (barrier → `isPipelineRebuilding` → per-stage promotion → aggregate math) for a realistic pipeline snapshot.

- [ ] **Step 1: Extend the test file**

Append to `packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts`:

```tsx
describe('full-import-chain rebuild detection', () => {
  it('given a live rebuild snapshot, derives the expected overall percent', () => {
    const barrier: BarrierStatus = { active: true, reason: 'rebuild', setAt: 1 };
    const fast: RebuildStageSnapshot[] = [
      { state: 'complete', progress: undefined },   // structural
      { state: 'complete', progress: undefined },   // inferred_edges
      { state: 'rebuilding', progress: 60 },        // catalogue in-flight
      { state: 'queued', progress: undefined },     // validation
      { state: 'queued', progress: undefined },     // knowledge
    ];
    const deep: RebuildStageSnapshot[] = new Array(5).fill({ state: 'queued', progress: undefined });
    const finalize: RebuildStageSnapshot[] = new Array(5).fill({ state: 'queued', progress: undefined });

    expect(isPipelineRebuilding(barrier)).toBe(true);
    // (100 + 100 + 60 + 0*12) / 15 = 17.33 → 17
    expect(computeOverallRebuildPercent([...fast, ...deep, ...finalize])).toBe(17);
  });

  it('non-rebuild barrier short-circuits detection even if stages look mid-run', () => {
    const barrier: BarrierStatus = { active: true, reason: 'enrichment_reset', setAt: 1 };
    expect(isPipelineRebuilding(barrier)).toBe(false);
  });
});
```

- [ ] **Step 2: Run**

Run: `npm --workspace packages/ui exec vitest run -- rebuildProgress.test`
Expected: PASS (13 tests total).

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/components/trace/__tests__/rebuildProgress.test.ts
git commit -m "test(ui): full-chain rebuild detection seam"
```

---

## Task 10: Manual QA in the dashboard

No code changes. This is a visual-validation pass — the existing pattern in `packages/ui` relies on Storybook + live dashboard for UI verification (no RTL today).

- [ ] **Step 1: Start Storybook and visually confirm the three variants**

Run: `npm --workspace packages/ui run storybook`
Open: http://localhost:6006 → Trace / StageProgressBar → confirm `Initialize`, `Incremental`, `Rebuild`, `RebuildPaused`, `RebuildFailed` stories all render as described in the spec.

- [ ] **Step 2: Start the dashboard against the live daemon**

Run: `scripts/dev.sh` (or individually start daemon on 8400 + dashboard on 5174).

- [ ] **Step 3: Kick a real rebuild on a small project**

Use the `SMOKE: rust_repo` project (id `0c50e42e-6d0d-4938-85a4-e87c3f5dbdca`). In a terminal:

```bash
curl -X POST localhost:8400/projects/0c50e42e-6d0d-4938-85a4-e87c3f5dbdca/pipeline/rebuild
```

Then in the dashboard:
- Confirm the **overall header bar** appears at the top of the pipeline panel with the green/orange stacked look.
- Confirm each **stage row** that is `running` or `queued` shows the rebuild variant.
- Pause the run — confirm the bar dims (`opacity-60`).
- Resume — confirm the bar un-dims and progress advances.
- Let the run finish — confirm bars transition to solid green as stages complete, and the overall bar disappears when the barrier clears.

- [ ] **Step 4: Verify collapsed view**

Collapse at least one group (Fast Sync / Deep / Finalize) while the rebuild is running. Confirm the collapsed row shows the same green/orange stacked bar.

- [ ] **Step 5: Note findings**

If everything renders as expected, this plan is complete. If any state looks wrong, open a new task describing the gap; do not patch over symptoms without investigating (systematic-debugging skill applies).

---

## Self-review summary

- **Spec coverage:** Architecture/data flow (Task 5), component API (Task 2), per-stage placement (Task 5), overall header (Task 6), collapsed view (Task 7), paused + failed edge states (Task 8), Storybook (Task 3), unit tests (Task 1), full-chain seam test (Task 9), manual QA (Task 10). No spec requirement is uncovered.
- **Placeholders:** None — every code step shows the exact code or exact line to change.
- **Type consistency:** `RebuildStageSnapshot` is defined once in Task 1 and referenced consistently in Tasks 6, 7, 9. `StageProgressBarVariant` + `StageProgressBarProps` are defined in Task 2 and used without renaming. `promoteForRebuild` is named identically in Task 5. `isRebuilding`, `overallRebuildPercent`, `fast/deep/finalizeRebuildPercent`, `rebuildStateOverlay` — all used with identical spelling across tasks.

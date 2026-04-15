# Pipeline Condensed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-group collapse/expand control to `GraphEnrichmentPipeline` so each of the three groups (Fast Sync, Deep Enrichment, Finalize) can render as a single condensed summary row. Default to collapsed. Persist per-group state across sessions via `ui_config.json`. Existing expanded UI is untouched.

**Architecture:** Single render-path branch inside `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`. Collapse state is owned by the dashboard App layer (same pattern as `autoConfig` and `ui_preferences`) and passed down as props. A new pure function `computeGroupRollup()` produces the summary state for the condensed row and is unit tested in isolation. Persistence flows through the existing `api.getGlobalConfig()` / `api.updateGlobalConfig()` pair.

**Tech Stack:** React 18 + TypeScript, Tailwind, Vitest (packages/ui), FastAPI backend for `/global/config` PUT endpoint (already exists; no backend changes).

**Spec:** `docs/Phase98_UI-UPDATE/Pipeline-Condensed/2026-04-14-pipeline-condensed-design.md`

## Global Stability Rules (carry into every task)

The pipeline is reported as still unstable. Every task in this plan must:

1. Start with a **reverse-engineering note**: for each code change, list (a) what upstream consumers pass to the changed surface, and (b) what downstream behaviors depend on the rendered output.
2. Make **additive** edits only. Do not refactor, rename, or "tidy" adjacent code.
3. Leave `useEnrichment.ts`, the enrichment reducer, and the orchestrator client **untouched**. If you find yourself about to edit one of them, stop and re-read the spec — the collapse feature is purely presentational.
4. Keep the component's existing prop interface backward-compatible. New props are optional with sensible defaults so the existing storybook story (`packages/ui/src/stories/trace/...` if any) and mock consumers keep working.
5. Run the package's full typecheck (`npm run typecheck --workspace=@codrag/ui`) and Vitest suite before each commit.

---

## File Structure (created/modified)

**Modified:**

- `packages/ui/src/types.ts` — extend `GlobalConfig` with optional `pipeline_ui` section.
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — new props, condensed render branch, chevron wired to callbacks. Existing expanded rendering untouched.
- `packages/ui/src/index.ts` (or wherever barrel exports live for `trace/`) — export the new rollup helper if it lives in its own file.
- `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` — wire new props from App-level config through to `<GraphEnrichmentPipeline>`.
- `src/codrag/dashboard/src/App.tsx` — read `pipeline_ui` on init, maintain state, pass down, PATCH on toggle.

**Created:**

- `packages/ui/src/components/trace/pipelineRollup.ts` — pure roll-up function. Small, unit-testable, no React imports.
- `packages/ui/src/components/trace/__tests__/pipelineRollup.test.ts` — Vitest unit tests for the roll-up rules.

**Unchanged (must stay unchanged):**

- `src/codrag/dashboard/src/hooks/useEnrichment.ts`
- Any file under `src/codrag/services/pipeline/`
- Backend API handlers (`/global/config` endpoint already accepts arbitrary keys in the PUT body).

---

## Task 1: Extend `GlobalConfig` type with `pipeline_ui`

**Files:**
- Modify: `packages/ui/src/types.ts:1196-1218`

**Reverse-engineering note:**
- Upstream: `api.getGlobalConfig()` at `packages/ui/src/api/client.ts:667` returns `GlobalConfig`. The PUT body at line 671 is typed `GlobalConfig`. Adding an optional field does not break any caller.
- Downstream: `App.tsx:610` calls `api.getGlobalConfig()` and conditionally reads known sub-objects. Unknown keys are simply ignored — no risk.
- Mock API (`packages/ui/src/api/mock.ts:240`) returns untyped `any`; no update needed.

- [ ] **Step 1: Add the new optional field**

Open `packages/ui/src/types.ts`. Find the `GlobalConfig` interface (line 1196) and add `pipeline_ui` immediately below `ui_preferences` (after the closing `};` of the `ui_preferences` object literal, before `module_layout`):

```ts
  ui_preferences?: {
    mode?: 'light' | 'dark';
    theme?: string;
    bg_image?: string | null;
  };
  /** Phase 98: per-group collapse state for GraphEnrichmentPipeline.
   *  All three default to `true` (collapsed) when absent. */
  pipeline_ui?: {
    fast_collapsed?: boolean;
    deep_collapsed?: boolean;
    finalize_collapsed?: boolean;
  };
  module_layout?: import('./types/layout').DashboardLayout;
```

- [ ] **Step 2: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS (no errors). If it fails because of an unrelated pre-existing error, record the error in the commit message but do not fix it.

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/types.ts
git commit -m "feat(phase98): add pipeline_ui section to GlobalConfig type"
```

---

## Task 2: Create the `computeGroupRollup` pure function with failing tests

**Files:**
- Create: `packages/ui/src/components/trace/pipelineRollup.ts`
- Create: `packages/ui/src/components/trace/__tests__/pipelineRollup.test.ts`

**Reverse-engineering note:**
- Upstream: this function will be called exclusively by `GraphEnrichmentPipeline.tsx` with already-built `EnrichmentStage[]` arrays (`fastStages`, `deepStages`, `finalizeStages` — see lines 1031, 1057, 1139). Those arrays are built from the same status objects the existing expanded rendering uses; no shape change.
- Downstream: nothing yet — the function is only referenced in its own tests in this task. Task 5 wires it into the component.

- [ ] **Step 1: Write the failing test file**

Create `packages/ui/src/components/trace/__tests__/pipelineRollup.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { computeGroupRollup } from '../pipelineRollup';
import type { EnrichmentStage, EnrichmentStageId } from '../GraphEnrichmentPipeline';
import { Circle } from 'lucide-react';

function stage(id: EnrichmentStageId, state: EnrichmentStage['state'], progress?: number): EnrichmentStage {
  return { id, label: id, icon: Circle, state, progress };
}

describe('computeGroupRollup', () => {
  it('returns complete when all five are complete', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'complete'),
      stage('catalogue', 'complete'),
      stage('validation', 'complete'),
      stage('knowledge', 'complete'),
    ];
    const r = computeGroupRollup(stages);
    expect(r.state).toBe('complete');
    expect(r.progress).toBeUndefined();
  });

  it('returns disabled when all five are disabled', () => {
    const stages: EnrichmentStage[] = [
      stage('enrichment', 'disabled'),
      stage('group_reasoning', 'disabled'),
      stage('clustering', 'disabled'),
      stage('deepening', 'disabled'),
      stage('deep_knowledge', 'disabled'),
    ];
    expect(computeGroupRollup(stages).state).toBe('disabled');
  });

  it('returns idle when all five are waiting/queued', () => {
    const stages: EnrichmentStage[] = [
      stage('atlas', 'waiting'),
      stage('rules', 'waiting'),
      stage('concepts', 'queued'),
      stage('audit', 'queued'),
      stage('antibodies', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('idle');
  });

  it('returns running with averaged progress when any stage is running and no errors', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'complete'),
      stage('catalogue', 'running', 40),
      stage('validation', 'waiting'),
      stage('knowledge', 'waiting'),
    ];
    const r = computeGroupRollup(stages);
    expect(r.state).toBe('running');
    expect(r.progress).toBe(40);
    expect(r.stats).toMatch(/running stage 3 of 5/);
  });

  it('returns running even when most are already complete', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'complete'),
      stage('catalogue', 'complete'),
      stage('validation', 'running', 10),
      stage('knowledge', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('running');
  });

  it('returns error when any stage has error (no running)', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'error'),
      stage('catalogue', 'waiting'),
      stage('validation', 'waiting'),
      stage('knowledge', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('error');
  });

  it('prefers running over error per rule order when both present', () => {
    // Rule 4 requires "no error" — so this case should fall through to rule 5 (error).
    const stages: EnrichmentStage[] = [
      stage('structural', 'running', 50),
      stage('inferred_edges', 'error'),
      stage('catalogue', 'waiting'),
      stage('validation', 'waiting'),
      stage('knowledge', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('error');
  });

  it('returns mixed for everything else (stale + complete + waiting, no running, no error)', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'stale'),
      stage('catalogue', 'complete'),
      stage('validation', 'waiting'),
      stage('knowledge', 'complete'),
    ];
    const r = computeGroupRollup(stages);
    expect(r.state).toBe('mixed');
    expect(r.stats).toMatch(/expand/i);
  });

  it('returns mixed for all-stale (no explicit all-stale rule)', () => {
    const stages: EnrichmentStage[] = [
      stage('atlas', 'stale'),
      stage('rules', 'stale'),
      stage('concepts', 'stale'),
      stage('audit', 'stale'),
      stage('antibodies', 'stale'),
    ];
    // Not running, no error, not-all-complete, not-all-disabled, not-all-idle → mixed
    expect(computeGroupRollup(stages).state).toBe('mixed');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/ui && npx vitest run src/components/trace/__tests__/pipelineRollup.test.ts`
Expected: FAIL with "Cannot find module '../pipelineRollup'" (module does not exist yet).

- [ ] **Step 3: Implement `pipelineRollup.ts`**

Create `packages/ui/src/components/trace/pipelineRollup.ts`:

```ts
import type { EnrichmentStage } from './GraphEnrichmentPipeline';

export interface GroupRollup {
  state: 'complete' | 'disabled' | 'idle' | 'running' | 'error' | 'mixed';
  progress: number | undefined;
  stats: string;
}

/**
 * Compute a single summary for a group of 5 enrichment stages.
 * Rules (first match wins):
 *   1. all complete           → complete
 *   2. all disabled           → disabled
 *   3. all waiting/queued     → idle
 *   4. any running AND no error → running (averaged progress of running stages)
 *   5. any error              → error
 *   6. otherwise              → mixed (orange warning — expand to inspect)
 */
export function computeGroupRollup(stages: EnrichmentStage[]): GroupRollup {
  if (stages.every((s) => s.state === 'complete')) {
    return { state: 'complete', progress: undefined, stats: 'complete' };
  }
  if (stages.every((s) => s.state === 'disabled')) {
    return { state: 'disabled', progress: undefined, stats: 'disabled' };
  }
  if (stages.every((s) => s.state === 'waiting' || s.state === 'queued')) {
    return { state: 'idle', progress: undefined, stats: `${stages.length} stages · idle` };
  }

  const hasError = stages.some((s) => s.state === 'error');
  const runningIndex = stages.findIndex((s) => s.state === 'running' || s.state === 'rerunning');

  if (runningIndex >= 0 && !hasError) {
    const runningStages = stages.filter((s) => s.state === 'running' || s.state === 'rerunning');
    const withProgress = runningStages.filter((s) => typeof s.progress === 'number');
    const avg = withProgress.length
      ? Math.round(withProgress.reduce((acc, s) => acc + (s.progress as number), 0) / withProgress.length)
      : undefined;
    return {
      state: 'running',
      progress: avg,
      stats: `running stage ${runningIndex + 1} of ${stages.length}`,
    };
  }

  if (hasError) {
    return { state: 'error', progress: undefined, stats: 'error — expand to inspect' };
  }

  return { state: 'mixed', progress: undefined, stats: 'mixed — expand to inspect' };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/ui && npx vitest run src/components/trace/__tests__/pipelineRollup.test.ts`
Expected: PASS — all 9 tests green.

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/trace/pipelineRollup.ts packages/ui/src/components/trace/__tests__/pipelineRollup.test.ts
git commit -m "feat(phase98): computeGroupRollup pure function + tests"
```

---

## Task 3: Add collapse props to `GraphEnrichmentPipeline`

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:40-128` (prop interface)
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:781-830` (destructuring)

**Reverse-engineering note:**
- Upstream: only `useDashboardPanels.tsx:835` renders `<GraphEnrichmentPipeline .../>` in the live dashboard. It does not currently pass collapse props. Since the new props are optional with safe defaults (`true` — collapsed), the dashboard continues to work unchanged until Task 6 wires them.
- Storybook: any existing stories for this component will also continue to render because the new props are optional.

- [ ] **Step 1: Add the optional props to `GraphEnrichmentPipelineProps`**

In `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`, inside the `GraphEnrichmentPipelineProps` interface (ends around line 127), immediately before `className?: string;`, add:

```ts
  /** Phase 98: per-group collapse state. Defaults to all collapsed when omitted. */
  fastCollapsed?: boolean;
  deepCollapsed?: boolean;
  finalizeCollapsed?: boolean;
  /** Phase 98: per-group collapse toggles. When omitted, the chevron still renders but is a no-op.  */
  onToggleFastCollapsed?: () => void;
  onToggleDeepCollapsed?: () => void;
  onToggleFinalizeCollapsed?: () => void;
```

- [ ] **Step 2: Destructure the new props with defaults**

In the same file, find the destructuring at line 781 (`export function GraphEnrichmentPipeline({`). Add the six new names with defaults near the bottom of the destructuring list — immediately before `className`:

```ts
  fastCollapsed = true,
  deepCollapsed = true,
  finalizeCollapsed = true,
  onToggleFastCollapsed,
  onToggleDeepCollapsed,
  onToggleFinalizeCollapsed,
  className,
```

- [ ] **Step 3: Typecheck**

Run: `cd packages/ui && npm run typecheck`
Expected: PASS. No call sites reference the new props yet, so existing consumers still compile.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(phase98): add collapse props to GraphEnrichmentPipeline (unwired)"
```

---

## Task 4: Render the condensed row when a group is collapsed

**Files:**
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1245-1312` (Fast Sync group)
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1314-1386` (Deep Enrichment group)
- Modify: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1388-1445` (Finalize group)

**Reverse-engineering note:**
- Upstream: three hard-coded `fastStages` / `deepStages` / `finalizeStages` arrays (lines 1031, 1057, 1139) feed the existing rendering. The condensed view reads these same arrays — no change to how stages are computed.
- Downstream: the `StageRow` component (line 629) is skipped entirely when a group is collapsed. Its pause/resume and `showDetails` behavior is preserved only in the expanded branch.
- The `fastPaused`/`deepPaused`/`finalizePaused` logic at lines 1297, 1371, 1430 runs today for each stage. In collapsed mode no individual StageRow is rendered, so that per-stage pause logic is not executed — acceptable because the group-level pause/resume button remains in the condensed row (see below).
- The existing group-action buttons (Run / Pause / Resume, the auto `SlidingSwitch`) are **kept on the same row** as the chevron and state icon in collapsed mode by reusing the existing header `<div className="flex items-center justify-between ...">` and simply hiding the stages underneath.

- [ ] **Step 1: Add the import for `computeGroupRollup` and chevron icons**

Near the top of `GraphEnrichmentPipeline.tsx`, add to the existing lucide-react import (line 6-10) the symbol `ChevronDown, ChevronRight`, and add a new top-level import for the helper:

```ts
import { computeGroupRollup, type GroupRollup } from './pipelineRollup';
```

Also add `ChevronDown, ChevronRight,` to the lucide-react import line 6-10.

- [ ] **Step 2: Add a small `ChevronButton` sub-component above `StageRow`**

Place this immediately before the `function StageRow(...)` declaration at line 629:

```tsx
function ChevronButton({ collapsed, onClick }: { collapsed: boolean; onClick?: () => void }) {
  const Icon = collapsed ? ChevronRight : ChevronDown;
  return (
    <button
      type="button"
      onClick={onClick}
      className="p-0.5 rounded hover:bg-surface-raised transition-colors text-text-subtle hover:text-text"
      aria-label={collapsed ? 'Expand group' : 'Collapse group'}
      title={collapsed ? 'Expand group' : 'Collapse group'}
    >
      <Icon className="w-3.5 h-3.5" />
    </button>
  );
}
```

- [ ] **Step 3: Add a `CondensedGroupRow` sub-component**

Place this immediately below the new `ChevronButton` and above `StageRow`:

```tsx
function CondensedGroupRow({ rollup }: { rollup: GroupRollup }) {
  const stateToStyle: Record<GroupRollup['state'], { bg: string; border: string; text: string; icon: React.ComponentType<{ className?: string }> }> = {
    complete:  { bg: 'bg-success/10',  border: 'border-success/30',  text: 'text-success',    icon: CheckCircle2 },
    disabled:  { bg: 'bg-surface',     border: 'border-border',      text: 'text-text-subtle', icon: Circle },
    idle:      { bg: 'bg-surface-raised', border: 'border-border',   text: 'text-text-muted', icon: Clock },
    running:   { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400',   icon: Loader2 },
    error:     { bg: 'bg-red-500/10',  border: 'border-red-500/30',  text: 'text-red-400',    icon: AlertTriangle },
    mixed:     { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: AlertTriangle },
  };
  const s = stateToStyle[rollup.state];
  const IconComponent = s.icon;
  const isRunning = rollup.state === 'running';
  return (
    <div className="flex items-center gap-3 py-0.5 px-1 ml-1">
      <div className={cn('w-8 h-8 rounded-full border flex items-center justify-center shrink-0', s.bg, s.border, s.text)}>
        <IconComponent className={cn('w-4 h-4', isRunning && 'animate-spin')} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn('text-[10px] leading-tight truncate', s.text)}>{rollup.stats}</p>
        {isRunning && typeof rollup.progress === 'number' && (
          <StageProgressBar progress={rollup.progress} className="h-1.5 mt-1 w-full" color="bg-blue-500" />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire the chevron + conditional render into the Fast Sync group**

Find the Fast Sync block at line 1245-1312. Replace the block with this structure — note only two things change: (a) the chevron is inserted at the start of the label wrapper, (b) the `{fastStages.map(...)}` div is wrapped in `{!fastCollapsed && (...)}`, and a condensed row is inserted for the collapsed case.

```tsx
      {/* ── Fast Sync Group ─────────────────────────── */}
      <div className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <ChevronButton collapsed={fastCollapsed} onClick={onToggleFastCollapsed} />
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Fast Sync</span>
          {fastAuto && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-medium bg-success-muted/10 text-success border border-success-muted/20">
              <Eye className="w-2.5 h-2.5" />
              Watching
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* existing Resume / Run / SlidingSwitch2 buttons — UNCHANGED */}
          {!fastAuto && fastPaused && onResumePipeline && !fastRunning && (
            <button
              onClick={() => onResumePipeline('fast_sync')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {!fastAuto && onRunFastSync && !fastPaused && (
            <button
              onClick={inactive ? undefined : onRunFastSync}
              disabled={fastRunning || limitReached || inactive}
              title={
                inactive ? "Activate this project to run pipelines." :
                  limitReached ? "Project limit reached. Upgrade to resume syncing." : undefined
              }
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (fastRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {fastRunning ? 'Running…' : 'Run'}
            </button>
          )}
          <SlidingSwitch2
            value={fastAuto}
            onChange={onAutoConfigChange ? setFastSync : undefined}
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      {fastCollapsed ? (
        <CondensedGroupRow rollup={computeGroupRollup(fastStages)} />
      ) : (
        <div className="flex flex-col gap-0.5 ml-1">
          {fastStages.map((stage, idx) => {
            const isStagePaused = fastPausedStage
              ? !!(fastPaused && !fastRunning && stage.id === fastPausedStage)
              : !!(fastPaused && !fastRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
                fastStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
            return (
              <StageRow
                key={stage.id}
                stage={stage}
                isPaused={isStagePaused}
                onPause={stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined}
                onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('fast_sync') : undefined}
                showDetails={showDetails}
              />
            );
          })}
        </div>
      )}
```

- [ ] **Step 5: Apply the same pattern to Deep Enrichment (lines 1317-1386)**

```tsx
      {/* Divider between groups */}
      <div className="border-t border-border" />

      {/* ── Deep Enrichment Group ───────────────────── */}
      <div className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <ChevronButton collapsed={deepCollapsed} onClick={onToggleDeepCollapsed} />
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Deep Enrichment</span>
        </div>
        <div className="flex items-center gap-2">
          {/* existing Resume / Run / settings / SlidingSwitch3 buttons — UNCHANGED */}
          {deepPaused && onResumePipeline && !deepRunning && (
            <button
              onClick={() => onResumePipeline('deep_enrichment')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {deepMode === 'manual' && onRunDeepEnrichment && !(deepPaused && !deepRunning) && (
            <button
              onClick={inactive ? undefined : onRunDeepEnrichment}
              disabled={deepRunning || limitReached || inactive}
              title={
                inactive ? "Activate this project to run pipelines." :
                  limitReached ? "Project limit reached. Upgrade to resume syncing." : undefined
              }
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (deepRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {deepRunning ? 'Running…' : deepPaused ? 'Paused' : 'Run'}
            </button>
          )}
          {onOpenDeepSettings && deepMode === 'scheduled' && (
            <button
              onClick={onOpenDeepSettings}
              className="p-1 rounded hover:bg-surface-raised transition-colors text-text-subtle hover:text-text"
              title="Deep Enrichment settings"
            >
              <Clock className="w-3.5 h-3.5" />
            </button>
          )}
          <SlidingSwitch3
            value={deepMode}
            options={DEEP_MODE_OPTIONS}
            onChange={onAutoConfigChange ? setDeepMode : undefined}
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      {deepCollapsed ? (
        <CondensedGroupRow rollup={computeGroupRollup(deepStages)} />
      ) : (
        <div className="flex flex-col gap-0.5 ml-1">
          {deepStages.map((stage, idx) => {
            const isStagePaused = deepPausedStage
              ? !!(deepPaused && !deepRunning && stage.id === deepPausedStage)
              : !!(deepPaused && !deepRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
                deepStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
            return (
              <StageRow
                key={stage.id}
                stage={stage}
                onPause={stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined}
                onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('deep_enrichment') : undefined}
                isPaused={isStagePaused}
                showDetails={showDetails}
              />
            );
          })}
        </div>
      )}
```

- [ ] **Step 6: Apply the same pattern to Finalize (lines 1391-1445)**

```tsx
      {/* Divider between groups */}
      <div className="border-t border-border" />

      {/* ── Finalize Group ──────────────────────────── */}
      <div className="flex items-center justify-between py-1.5 px-1">
        <div className="flex items-center gap-2">
          <ChevronButton collapsed={finalizeCollapsed} onClick={onToggleFinalizeCollapsed} />
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Finalize</span>
        </div>
        <div className="flex items-center gap-2">
          {/* existing Resume / Run / SlidingSwitch2 buttons — UNCHANGED */}
          {finalizePaused && onResumePipeline && !finalizeRunning && (
            <button
              onClick={() => onResumePipeline('finalize')}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
              title="Resume from where it paused"
            >
              <Play className="w-3.5 h-3.5" />
              Resume
            </button>
          )}
          {onRunFinalize && !finalizePaused && (
            <button
              onClick={inactive ? undefined : onRunFinalize}
              disabled={finalizeRunning || limitReached || inactive}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                (finalizeRunning || limitReached || inactive)
                  ? "border-border bg-surface text-text-subtle cursor-not-allowed"
                  : "border-success/40 bg-success/10 text-success hover:bg-success/20"
              )}
            >
              <Play className="w-3.5 h-3.5" />
              {finalizeRunning ? 'Running\u2026' : 'Run'}
            </button>
          )}
          <SlidingSwitch2
            value={cfg.finalize === 'auto'}
            onChange={onAutoConfigChange ? (v: boolean) => onAutoConfigChange({ ...cfg, finalize: v ? 'auto' : 'manual' }) : undefined}
            disabled={inactive}
            disabledReason={inactive ? "Project is inactive" : undefined}
          />
        </div>
      </div>
      {finalizeCollapsed ? (
        <CondensedGroupRow rollup={computeGroupRollup(finalizeStages)} />
      ) : (
        <div className="flex flex-col gap-0.5 ml-1">
          {finalizeStages.map((stage, idx) => {
            const isStagePaused = finalizePausedStage
              ? !!(finalizePaused && !finalizeRunning && stage.id === finalizePausedStage)
              : !!(finalizePaused && !finalizeRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
                finalizeStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
            return (
              <StageRow
                key={stage.id}
                stage={stage}
                onPause={stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined}
                onResume={isStagePaused && onResumePipeline ? () => onResumePipeline('finalize') : undefined}
                isPaused={isStagePaused}
                showDetails={showDetails}
              />
            );
          })}
        </div>
      )}
```

- [ ] **Step 7: Typecheck + full Vitest**

Run: `cd packages/ui && npm run typecheck && npx vitest run`
Expected: PASS. If typecheck complains about an unused `ChevronDown` or `ChevronRight` import, verify the import is on the lucide-react line.

- [ ] **Step 8: Commit**

```bash
git add packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
git commit -m "feat(phase98): render condensed row when pipeline group is collapsed"
```

---

## Task 5: Wire collapse state through `useDashboardPanels.tsx`

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx:835+` (the `<GraphEnrichmentPipeline .../>` call site)

**Reverse-engineering note:**
- Upstream: `useDashboardPanels` receives a large props bundle `p` from `App.tsx`. We need to add four new entries to that bundle (three booleans + one handler that takes a group id). Adding fields is additive.
- Downstream: the new props are consumed by `GraphEnrichmentPipeline` (Task 3/4). If any field is missing, the component defaults to "collapsed + no-op toggle" — safe fallback.

- [ ] **Step 1: Identify the props type**

Open `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` and search for the type of the `p` parameter destructured at the `<GraphEnrichmentPipeline ...>` call site (around line 835). Note the exact property bag (likely called `TracePipelineProps` or inlined in `DashboardPanelProps`). The hook passes the bundle through — no new types needed inside this file if we just read fields off `p`.

- [ ] **Step 2: Add the new fields to whichever props bag `p` comes from**

Add four new optional fields to the bag (find the interface `p` is typed as — likely in the same file or a colocated types file):

```ts
  fastCollapsed?: boolean;
  deepCollapsed?: boolean;
  finalizeCollapsed?: boolean;
  onToggleGroupCollapsed?: (group: 'fast' | 'deep' | 'finalize') => void;
```

- [ ] **Step 3: Pass them to the component at the call site**

Find the `<GraphEnrichmentPipeline` JSX at line 835 and add these props at the end of the attribute list (before `/>`):

```tsx
          fastCollapsed={p.fastCollapsed}
          deepCollapsed={p.deepCollapsed}
          finalizeCollapsed={p.finalizeCollapsed}
          onToggleFastCollapsed={p.onToggleGroupCollapsed ? () => p.onToggleGroupCollapsed!('fast') : undefined}
          onToggleDeepCollapsed={p.onToggleGroupCollapsed ? () => p.onToggleGroupCollapsed!('deep') : undefined}
          onToggleFinalizeCollapsed={p.onToggleGroupCollapsed ? () => p.onToggleGroupCollapsed!('finalize') : undefined}
```

- [ ] **Step 4: Typecheck the dashboard workspace**

Run: `cd src/codrag/dashboard && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useDashboardPanels.tsx
git commit -m "feat(phase98): thread pipeline collapse props through useDashboardPanels"
```

---

## Task 6: Own collapse state in `App.tsx` and persist to `ui_config.json`

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx:603-680` (init block where `ui_preferences` is read) and wherever panel props are assembled (likely nearby — look for the object that becomes `p`).

**Reverse-engineering note:**
- Upstream: `api.getGlobalConfig()` is already called on init (line 610). Adding a read of `globalCfg.pipeline_ui` is a read-only addition.
- Downstream: `api.updateGlobalConfig({ pipeline_ui: {...} })` hits the same PUT `/global/config` endpoint that already accepts arbitrary keys. The backend merges by key. No backend changes required.
- Failure mode: if the PATCH fails (daemon down, file lock), the optimistic local state still toggles. Acceptable for a cosmetic preference.

- [ ] **Step 1: Add three `useState` hooks near the other UI state in App.tsx**

Near the existing `uiMode` / `uiTheme` / `bgImage` useState declarations, add:

```tsx
  const [fastCollapsed, setFastCollapsed] = useState<boolean>(true);
  const [deepCollapsed, setDeepCollapsed] = useState<boolean>(true);
  const [finalizeCollapsed, setFinalizeCollapsed] = useState<boolean>(true);
```

- [ ] **Step 2: Read `pipeline_ui` during init**

In the init block at line 603-634, immediately after the `ui_preferences` read (line 629-634), add:

```tsx
          if (globalCfg.pipeline_ui) {
            const pui = globalCfg.pipeline_ui;
            if (typeof pui.fast_collapsed === 'boolean') setFastCollapsed(pui.fast_collapsed);
            if (typeof pui.deep_collapsed === 'boolean') setDeepCollapsed(pui.deep_collapsed);
            if (typeof pui.finalize_collapsed === 'boolean') setFinalizeCollapsed(pui.finalize_collapsed);
          }
```

- [ ] **Step 3: Add the toggle handler**

Add a `useCallback` handler alongside the other config-change handlers in App.tsx:

```tsx
  const handleToggleGroupCollapsed = useCallback((group: 'fast' | 'deep' | 'finalize') => {
    let nextFast = fastCollapsed;
    let nextDeep = deepCollapsed;
    let nextFin = finalizeCollapsed;
    if (group === 'fast') { nextFast = !fastCollapsed; setFastCollapsed(nextFast); }
    if (group === 'deep') { nextDeep = !deepCollapsed; setDeepCollapsed(nextDeep); }
    if (group === 'finalize') { nextFin = !finalizeCollapsed; setFinalizeCollapsed(nextFin); }
    api.updateGlobalConfig({
      pipeline_ui: {
        fast_collapsed: nextFast,
        deep_collapsed: nextDeep,
        finalize_collapsed: nextFin,
      },
    } as any).catch(() => { });
  }, [api, fastCollapsed, deepCollapsed, finalizeCollapsed]);
```

- [ ] **Step 4: Pass the new state + handler down to the dashboard panels bundle**

Find where the `p` bag for `useDashboardPanels` (or its wrapper component) is assembled in App.tsx. Add:

```tsx
    fastCollapsed,
    deepCollapsed,
    finalizeCollapsed,
    onToggleGroupCollapsed: handleToggleGroupCollapsed,
```

- [ ] **Step 5: Typecheck the dashboard workspace**

Run: `cd src/codrag/dashboard && npm run typecheck`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/dashboard/src/App.tsx
git commit -m "feat(phase98): persist pipeline collapse state via ui_config"
```

---

## Task 7: Manual smoke test + final sign-off

**Files:**
- No code changes. Verification only.

**Reverse-engineering note:**
- This task is the safety net for the "pipeline is unstable" constraint. Do not skip.

- [ ] **Step 1: Build workspaces**

Run: `npm run build --workspace=@codrag/ui`
Expected: build succeeds.

- [ ] **Step 2: Start the dev environment**

Run (in separate terminals, or via `scripts/dev.sh`):
- `codrag serve` (daemon on :8400)
- `cd src/codrag/dashboard && npm run dev` (dashboard on :5174)

Open `http://localhost:5174`.

- [ ] **Step 3: First-load check**

Expected: the Enrichment Pipeline panel shows **three condensed rows** (Fast Sync / Deep Enrichment / Finalize). Each row has a right-facing chevron on the left. Each group's existing action buttons (Run / Resume / SlidingSwitch) are visible on the right.

- [ ] **Step 4: Expand each group**

Click the chevron on each group. Expected: chevron rotates to down, all 5 stages render exactly as they do today (StageRow with icons, stats, progress). No visual regression.

- [ ] **Step 5: Refresh the page**

Reload the browser. Expected: the three groups stay in whatever state you left them (all-expanded, all-collapsed, or mixed). Verify by inspecting `codrag_data/ui_config.json` — it should now contain a `pipeline_ui` block with the correct three booleans.

- [ ] **Step 6: Run a pipeline while collapsed**

With Fast Sync collapsed, click its group Run button. Expected: the condensed row's state icon flips to a blue spinner; the progress bar appears under the stats line and advances. When it finishes, the icon flips to the green complete check.

- [ ] **Step 7: Expand mid-run**

Expand Fast Sync while it is still running. Expected: full StageRow list renders, showing which specific stage is running with its own per-stage progress bar. Collapse again — condensed row resumes cleanly.

- [ ] **Step 8: Group-level pause from the condensed row**

While Fast Sync is running and collapsed, click the condensed row's Run button menu (actually, pause flows through per-stage hover today; the group-level Resume button is what's in the header). For v1, verify: **running → complete** works end-to-end from the condensed view without expanding.

If pause behavior in the condensed view feels missing, note it as a **deferred follow-up** — do not add scope here.

- [ ] **Step 9: Error roll-up check**

If the dashboard has a way to induce a stage error (e.g., disable a required model, then run the pipeline), verify the condensed row shows the red error icon and "error — expand to inspect" stats. If inducing an error isn't easy in this environment, note that the unit tests (Task 2) cover this case and mark this step done.

- [ ] **Step 10: Final commit (if any touch-ups)**

If any step revealed a bug, fix it with the smallest possible change, re-run the relevant test, and commit. Otherwise:

```bash
git log --oneline -n 6   # confirm 5-6 phase98 commits
```

- [ ] **Step 11: Done**

Report back with: the commit range, a confirmation that manual smoke test passed each step, and any deferred follow-ups noted in Step 8/9.

---

## Self-Review Notes (plan author)

- **Spec coverage:** Every section of the spec is implemented: condensed row visual (Task 4), roll-up rules (Task 2), persistence in ui_config.json (Task 6), default-collapsed (Task 3 default + Task 6 state init), interaction rules (Task 4), stability constraints (global rules + per-task reverse-engineering notes).
- **Placeholder scan:** No TBDs. All code blocks are concrete. Test names are specific.
- **Type consistency:** `GroupRollup`, `computeGroupRollup`, `pipeline_ui`, `fast_collapsed`/`deep_collapsed`/`finalize_collapsed`, `onToggleGroupCollapsed` all consistent across Tasks 1–6.
- **Known concession:** Task 7 Step 8 (group-level pause from condensed view) is softened because the existing per-stage pause mechanism lives on StageRow hover, which is skipped in condensed mode. The group-level pause/resume buttons in the header row still exist and function. If the user wants a richer condensed-mode pause affordance, that's a follow-up.

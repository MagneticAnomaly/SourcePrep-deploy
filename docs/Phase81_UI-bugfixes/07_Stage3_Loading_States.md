# Phase 81 Stage 3 — Loading States

**Date:** 2026-04-07
**Commit:** `545a1035` on `phase81/ui-bugfixes`
**Status:** Complete

---

## Problem

Panels with async state loading rendered full components with empty/no-op props during the loading phase. Users saw:
- GoalpostsPanel with `missing: ['Loading...']` text but no spinner
- AdvisorPanel with `ready: false` and empty proposals
- RoadmapPanel with empty node list and `ready: false`

These looked broken, not loading.

## Changes

### 1. PanelLoading component

**New file:** `packages/ui/src/components/primitives/PanelLoading.tsx`

```tsx
export function PanelLoading({ className, message = 'Loading...' }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 py-12 px-4", className)}>
      <Loader2 className="w-6 h-6 text-text-muted/40 animate-spin" />
      <p className="text-xs text-text-muted">{message}</p>
    </div>
  );
}
```

Matches the existing loading pattern used by GraphEnrichmentPipeline's `projectLoading` gate.

Exported from:
- `packages/ui/src/components/primitives/index.ts`
- `packages/ui/src/index.ts`

### 2. Null-state fallback replacements

**File:** `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`

| Panel | Before (lines removed) | After |
|-------|----------------------|-------|
| goalposts | 17-line GoalpostsPanel with empty props + `missing: ['Loading...']` | `<PanelLoading message="Loading goalposts..." />` |
| advisor | 17-line AdvisorPanel with empty props + `missing: ['Loading...']` | `<PanelLoading message="Loading advisor..." />` |
| roadmap | 22-line RoadmapPanel with empty props + `ready: false` | `<PanelLoading message="Loading roadmap..." />` |

Net: **-56 lines of no-op component rendering**, replaced with 3 clean loading indicators.

---

## Future Work (not in this stage)

- Add loading prop to AtlasStatusCard and ActivityHeatmap
- Wire `projectLoading` through to more panels
- Consider a panel-level Suspense boundary pattern

---

## Verification

- TypeScript: clean (only pre-existing errors)

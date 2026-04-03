# Dashboard Project-Switch Performance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate UI freezing and lag when switching between projects in the CoDRAG dashboard.

**Architecture:** Incremental fixes applied in priority order. Each task is independently shippable and delivers measurable improvement. Tasks 1-2 are quick wins (~5 min each). Task 3 is the core structural fix. Tasks 4-5 are polish that come partly free from Task 3.

**Tech Stack:** React 18, TypeScript, Vite

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `src/codrag/dashboard/src/hooks/useHydrationController.ts` | Central hydration coordinator: AbortController, debounce, tiered queue, `isHydrating` flag | **Create** |
| `src/codrag/dashboard/src/hooks/useProjectManager.ts` | Consume hydration signal, remove independent hydration effects | **Modify** |
| `src/codrag/dashboard/src/hooks/useFileSystem.ts` | Consume hydration signal | **Modify** |
| `src/codrag/dashboard/src/hooks/useTraceSystem.ts` | Consume hydration signal, guard polls | **Modify** |
| `src/codrag/dashboard/src/hooks/useEnrichment.ts` | Consume hydration signal, guard polls | **Modify** |
| `src/codrag/dashboard/src/hooks/useAuditSystem.ts` | Consume hydration signal, guard polls | **Modify** |
| `src/codrag/dashboard/src/hooks/useSpaghettiSystem.ts` | Consume hydration signal | **Modify** |
| `src/codrag/dashboard/src/hooks/useGoalpostsSystem.ts` | Consume hydration signal, guard polls | **Modify** |
| `src/codrag/dashboard/src/hooks/useRoadmapSystem.ts` | Consume hydration signal, guard polls | **Modify** |
| `src/codrag/dashboard/src/hooks/useOpportunitiesSystem.ts` | Consume hydration signal, guard polls | **Modify** |
| `src/codrag/dashboard/src/hooks/useAgentOps.ts` | Consume hydration signal | **Modify** |
| `src/codrag/dashboard/src/App.tsx` | Wire useHydrationController, pass signal to hooks, replace direct hydration effects | **Modify** |

---

### Task 1: Create `useHydrationController` hook — AbortController + debounce

The foundation. This hook manages a single AbortController that gets replaced on every project switch, and debounces the "hydrated" project ID so rapid clicks don't trigger cascading fetches.

**Files:**
- Create: `src/codrag/dashboard/src/hooks/useHydrationController.ts`

- [ ] **Step 1: Create the hook file with AbortController lifecycle**

```typescript
import { useState, useEffect, useRef, useCallback } from 'react'

export interface HydrationController {
  /** The debounced project ID — hooks should hydrate against this, not the raw selection */
  hydratedProjectId: string | null
  /** AbortSignal that gets aborted on every project switch. Pass to fetch calls. */
  signal: AbortSignal
  /** True while hydration is in progress (critical + secondary tiers). Polls should wait. */
  isHydrating: boolean
  /** Call when your hook's hydration fetch completes (success or fail). */
  markHydrated: (hookId: string) => void
  /** Register a hook as needing hydration for the current switch. */
  registerHook: (hookId: string) => void
}

const DEBOUNCE_MS = 100

export function useHydrationController(rawProjectId: string | null): HydrationController {
  const [hydratedProjectId, setHydratedProjectId] = useState<string | null>(rawProjectId)
  const [isHydrating, setIsHydrating] = useState(false)
  const abortRef = useRef<AbortController>(new AbortController())
  const debounceRef = useRef<NodeJS.Timeout | null>(null)
  const pendingHooksRef = useRef<Set<string>>(new Set())

  // On rawProjectId change: abort previous, debounce new
  useEffect(() => {
    // Abort all in-flight requests from previous project
    abortRef.current.abort()
    abortRef.current = new AbortController()

    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (!rawProjectId) {
      setHydratedProjectId(null)
      setIsHydrating(false)
      pendingHooksRef.current.clear()
      return
    }

    // Start hydrating immediately (even during debounce window)
    setIsHydrating(true)
    pendingHooksRef.current.clear()

    // Debounce the actual project ID propagation
    debounceRef.current = setTimeout(() => {
      setHydratedProjectId(rawProjectId)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [rawProjectId])

  const registerHook = useCallback((hookId: string) => {
    pendingHooksRef.current.add(hookId)
  }, [])

  const markHydrated = useCallback((hookId: string) => {
    pendingHooksRef.current.delete(hookId)
    if (pendingHooksRef.current.size === 0) {
      setIsHydrating(false)
    }
  }, [])

  return {
    hydratedProjectId,
    signal: abortRef.current.signal,
    isHydrating,
    markHydrated,
    registerHook,
  }
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd src/codrag/dashboard && npx tsc --noEmit src/hooks/useHydrationController.ts 2>&1 | head -20`

Expected: No errors (or only errors about missing module resolution, not type errors in the hook itself).

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useHydrationController.ts
git commit -m "feat(dashboard): add useHydrationController hook for project-switch coordination"
```

---

### Task 2: Wire `useHydrationController` into App.tsx

Connect the controller to the existing project selection flow. At this stage, hooks still hydrate themselves — we're just making the controller and its `signal` available.

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Import and instantiate the controller**

In `App.tsx`, after the `useProjectManager` destructuring block (~line 208), add:

```typescript
import { useHydrationController } from './hooks/useHydrationController'

// Inside App():
// After: const { selectedProjectId, ... } = project

const hydration = useHydrationController(selectedProjectId)
```

- [ ] **Step 2: Verify the app still compiles**

Run: `cd src/codrag/dashboard && npx tsc --noEmit 2>&1 | head -30`

Expected: No new errors. The controller is instantiated but not consumed by hooks yet.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): wire useHydrationController into App"
```

---

### Task 3: Thread AbortSignal into simple hooks (useAuditSystem, useSpaghettiSystem, useGoalpostsSystem)

These three hooks are the simplest — they have straightforward hydration effects with no complex dependencies. We'll modify them to accept and use the AbortSignal, and switch from reacting to `selectedProjectId` to reacting to `hydratedProjectId`.

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useAuditSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useSpaghettiSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useGoalpostsSystem.ts`
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Update useAuditSystem to accept signal and hydratedProjectId**

Change the hook signature and hydration effect:

```typescript
// useAuditSystem.ts — change signature
export function useAuditSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal }
): UseAuditSystemReturn {
```

In the hydration `useEffect` (line 25), wrap the `.then()` callbacks to check `signal.aborted`:

```typescript
  useEffect(() => {
    setAuditStatus(null)
    setAuditFindings([])
    setAuditReports([])
    setAuditReportContent(null)
    setViewingAuditReport(null)

    if (!selectedProjectId) return

    const signal = options?.signal

    api.getAuditStatus(selectedProjectId)
      .then((s) => {
        if (signal?.aborted) return
        setAuditStatus(s)
        if (s.has_results) {
          api.getAuditFindings(selectedProjectId, { limit: 200 })
            .then((r) => { if (!signal?.aborted) setAuditFindings(r.findings || []) })
            .catch(() => {})
          api.getAuditReports(selectedProjectId)
            .then((r) => { if (!signal?.aborted) setAuditReports(r.reports || []) })
            .catch(() => {})
        }
      })
      .catch(() => {})
  }, [selectedProjectId, api])
```

Note: We keep `selectedProjectId` in the dep array (not `options.signal`) because the signal object changes on every switch — the abort check inside is sufficient.

- [ ] **Step 2: Update useSpaghettiSystem similarly**

```typescript
// useSpaghettiSystem.ts — change signature
export function useSpaghettiSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal }
): UseSpaghettiSystemReturn {
```

In `fetchScores`, check signal before setting state:

```typescript
  const fetchScores = useCallback((projectId: string, refresh = false, signal?: AbortSignal) => {
    setLoading(true)
    api.getSpaghettiScores(projectId, { limit: 100, refresh })
      .then((r) => {
        if (signal?.aborted) return
        setFiles(r.files || [])
        setFileCount(r.file_count || 0)
        setScoredCount(r.scored_count || 0)
        setSeverityCounts(r.severity_counts || {})
      })
      .catch(() => {
        if (signal?.aborted) return
        setFiles([])
        setFileCount(0)
        setScoredCount(0)
        setSeverityCounts({})
      })
      .finally(() => { if (!signal?.aborted) setLoading(false) })
  }, [api])
```

Update the hydration effect:

```typescript
  useEffect(() => {
    setFiles([])
    setFileCount(0)
    setScoredCount(0)
    setSeverityCounts({})
    if (!selectedProjectId) return
    fetchScores(selectedProjectId, false, options?.signal)
  }, [selectedProjectId, fetchScores])
```

- [ ] **Step 3: Update useGoalpostsSystem similarly**

```typescript
// useGoalpostsSystem.ts — change signature
export function useGoalpostsSystem(
  selectedProjectId: string | null,
  options?: { signal?: AbortSignal }
): UseGoalpostsSystemReturn {
```

Update hydration effect:

```typescript
  useEffect(() => {
    setState(null)
    if (!selectedProjectId) return
    const signal = options?.signal
    api.getGoalposts(selectedProjectId)
      .then((s) => { if (!signal?.aborted) setState(s) })
      .catch(() => {})
  }, [selectedProjectId, api])
```

- [ ] **Step 4: Update App.tsx to pass the signal**

Where these hooks are instantiated in App.tsx:

```typescript
  const audit = useAuditSystem(hydration.hydratedProjectId, { signal: hydration.signal })
  const spaghetti = useSpaghettiSystem(hydration.hydratedProjectId, { signal: hydration.signal })
  const goalposts = useGoalpostsSystem(hydration.hydratedProjectId, { signal: hydration.signal })
```

Note: We pass `hydration.hydratedProjectId` (the debounced ID) instead of `selectedProjectId` so these hooks benefit from the debounce.

- [ ] **Step 5: Verify the app compiles**

Run: `cd src/codrag/dashboard && npx tsc --noEmit 2>&1 | head -30`

- [ ] **Step 6: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useAuditSystem.ts \
        src/codrag/dashboard/src/hooks/useSpaghettiSystem.ts \
        src/codrag/dashboard/src/hooks/useGoalpostsSystem.ts \
        src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): thread AbortSignal into audit, spaghetti, goalposts hooks"
```

---

### Task 4: Thread AbortSignal into remaining secondary hooks (roadmap, opportunities, agentOps)

Same pattern as Task 3, applied to the remaining secondary-tier hooks.

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useRoadmapSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useOpportunitiesSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useAgentOps.ts`
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Update useRoadmapSystem**

Add `options?: { signal?: AbortSignal }` to the signature. In the hydration effect, check `signal?.aborted` before every `setState` call in `.then()` handlers.

- [ ] **Step 2: Update useOpportunitiesSystem**

Same pattern. Add signal option, guard all hydration setState calls.

- [ ] **Step 3: Update useAgentOps**

Same pattern. Add signal option, guard all hydration setState calls.

- [ ] **Step 4: Update App.tsx call sites**

```typescript
  const roadmap = useRoadmapSystem(hydration.hydratedProjectId, { signal: hydration.signal })
  const opportunities = useOpportunitiesSystem(hydration.hydratedProjectId, { signal: hydration.signal })
  // useAgentOps — check its current signature and add signal similarly
```

- [ ] **Step 5: Verify compilation**

Run: `cd src/codrag/dashboard && npx tsc --noEmit 2>&1 | head -30`

- [ ] **Step 6: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useRoadmapSystem.ts \
        src/codrag/dashboard/src/hooks/useOpportunitiesSystem.ts \
        src/codrag/dashboard/src/hooks/useAgentOps.ts \
        src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): thread AbortSignal into roadmap, opportunities, agentOps hooks"
```

---

### Task 5: Thread AbortSignal into critical hooks (useProjectManager, useFileSystem, useTraceSystem, useEnrichment)

These are the most complex hooks. They have polling, cross-hook dependencies, and richer state management. The approach is the same — add signal, guard setState — but more care is needed.

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useProjectManager.ts`
- Modify: `src/codrag/dashboard/src/hooks/useFileSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useTraceSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useEnrichment.ts`
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Update useProjectManager**

Add `signal?: AbortSignal` to the `UseProjectManagerDeps` interface. In the self-hydration `useEffect` (line 132), guard the `.then()` callbacks:

```typescript
  useEffect(() => {
    if (!selectedProjectId) return
    void refreshStatus(selectedProjectId)
    const signal = deps.signal
    api.getProject(selectedProjectId).then((data) => {
      if (signal?.aborted) return
      const cfg = data.project.config
      if (cfg) {
        setProjectConfig((prev) => ({
          include_globs: cfg.include_globs ?? prev.include_globs,
          // ... rest unchanged
        }))
        setConfigDirty(false)
      }
    }).catch(() => {})
  }, [api, selectedProjectId, refreshStatus])
```

- [ ] **Step 2: Update useFileSystem**

Add `signal?: AbortSignal` to the deps interface. Guard the hydration effect's setState calls with `signal?.aborted` checks. The file tree fetch, path weights fetch, and included paths fetch should all check before setting state.

- [ ] **Step 3: Update useTraceSystem**

Add `signal?: AbortSignal` to `UseTraceSystemDeps`. Guard the hydration effect (which fetches trace status, coverage, and pipeline status). This hook already has a `cancelled` flag pattern — replace it with the shared AbortSignal.

- [ ] **Step 4: Update useEnrichment**

Add `signal?: AbortSignal` to `UseEnrichmentDeps`. The hydration effect (which fetches 6 statuses) already uses a `cancelled` flag — replace it with `signal?.aborted`. Guard the polling interval's setState calls too.

- [ ] **Step 5: Update App.tsx**

Pass signal through to all four hooks via their deps:

```typescript
  const project = useProjectManager({
    onError: (msg, variant) => showToast(msg, variant),
    signal: hydration.signal,
    // ... other deps unchanged
  })

  // useFileSystem, useTraceSystem, useEnrichment — add signal to their options
```

Note: `useProjectManager` uses the raw `selectedProjectId` internally (not the debounced one), because the sidebar selection must respond immediately. The signal still protects against stale responses.

- [ ] **Step 6: Verify compilation**

Run: `cd src/codrag/dashboard && npx tsc --noEmit 2>&1 | head -30`

- [ ] **Step 7: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useProjectManager.ts \
        src/codrag/dashboard/src/hooks/useFileSystem.ts \
        src/codrag/dashboard/src/hooks/useTraceSystem.ts \
        src/codrag/dashboard/src/hooks/useEnrichment.ts \
        src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): thread AbortSignal into critical hooks (project, files, trace, enrichment)"
```

---

### Task 6: Guard polls with `isHydrating`

All hooks that start polling intervals should skip starting polls while hydration is in progress. This prevents poll requests from piling up during the initial fetch burst.

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useProjectManager.ts`
- Modify: `src/codrag/dashboard/src/hooks/useTraceSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useEnrichment.ts`
- Modify: `src/codrag/dashboard/src/hooks/useAuditSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useGoalpostsSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useRoadmapSystem.ts`
- Modify: `src/codrag/dashboard/src/hooks/useOpportunitiesSystem.ts`
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Add `isHydrating` to the options interface of each hook**

Each hook that polls gets `isHydrating?: boolean` added to its options/deps.

- [ ] **Step 2: Guard polling effects**

In each hook that creates a `setInterval` for polling, add an early return:

```typescript
// Example in useProjectManager's auto-poll effect (line 160):
useEffect(() => {
  if (!selectedProjectId) return
  if (deps.isHydrating) return  // <-- new guard
  const ps = projectStatuses[selectedProjectId]
  if (!ps?.building || buildingProjects.has(selectedProjectId)) return
  // ... rest of polling logic unchanged
}, [api, selectedProjectId, projectStatuses, buildingProjects, deps.isHydrating])
```

Apply the same pattern to:
- `useTraceSystem`: trace coverage poll (~line 673)
- `useEnrichment`: progress poll (~line 438)
- `useAuditSystem`: audit poll inside `handleRunAudit` (line 56) — this one only polls after user action, so it's lower priority, but still guard it
- `useGoalpostsSystem`: generation poll (line 50) — same, user-initiated, but guard
- `useRoadmapSystem`: generation poll
- `useOpportunitiesSystem`: agent status poll

- [ ] **Step 3: Pass `isHydrating` from App.tsx**

```typescript
  const audit = useAuditSystem(hydration.hydratedProjectId, {
    signal: hydration.signal,
    isHydrating: hydration.isHydrating,
  })
  // ... same for all hooks with polling
```

- [ ] **Step 4: Guard App.tsx's own polling effects**

The provenance refresh interval (line 637-641) should also check:

```typescript
  useEffect(() => {
    if (!selectedProjectId || !anyPipelineRunning || hydration.isHydrating) return
    const interval = setInterval(() => { void fetchProvenance() }, 10_000)
    return () => clearInterval(interval)
  }, [selectedProjectId, anyPipelineRunning, fetchProvenance, hydration.isHydrating])
```

- [ ] **Step 5: Verify compilation**

Run: `cd src/codrag/dashboard && npx tsc --noEmit 2>&1 | head -30`

- [ ] **Step 6: Commit**

```bash
git add src/codrag/dashboard/src/hooks/*.ts src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): guard all polling effects with isHydrating flag"
```

---

### Task 7: Move App.tsx direct hydration effects behind the controller

App.tsx has its own hydration effect (line 620-629) that fires 5 calls on project change. Move these behind the hydration controller too.

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx`

- [ ] **Step 1: Switch the hydration effect to use `hydratedProjectId`**

```typescript
  // Before (line 620):
  useEffect(() => {
    if (!selectedProjectId) return
    void refreshWatchStatus(selectedProjectId)
    void fetchDeepAnalysisStatus()
    void fetchAtlas()
    void fetchProvenance()
    api.getProjectActivity(selectedProjectId, 12).then(setActivityData).catch(() => { })
  }, [selectedProjectId])

  // After:
  useEffect(() => {
    if (!hydration.hydratedProjectId) return
    if (hydration.signal.aborted) return
    const signal = hydration.signal
    void refreshWatchStatus(hydration.hydratedProjectId)
    void fetchDeepAnalysisStatus()
    void fetchAtlas()
    void fetchProvenance()
    api.getProjectActivity(hydration.hydratedProjectId, 12)
      .then((data) => { if (!signal.aborted) setActivityData(data) })
      .catch(() => { })
  }, [hydration.hydratedProjectId])
```

- [ ] **Step 2: Similarly guard the scope events effect (line 612)**

```typescript
  useEffect(() => {
    if (!hydration.hydratedProjectId) return
    const se = scopeEvents[hydration.hydratedProjectId]
    if (se?.state === 'building' || se?.state === 'idle') {
      void refreshStatus(hydration.hydratedProjectId)
    }
  }, [scopeEvents, hydration.hydratedProjectId, refreshStatus])
```

- [ ] **Step 3: Verify compilation**

Run: `cd src/codrag/dashboard && npx tsc --noEmit 2>&1 | head -30`

- [ ] **Step 4: Manual test — switch projects, verify no freeze**

Start the dev environment with `scripts/dev.sh`. Open the dashboard. Add or select multiple projects. Rapidly click between them. Verify:
- Sidebar highlights immediately (no debounce on visual selection)
- Dashboard content updates within ~200ms of settling on a project
- No UI freeze
- Browser dev tools Network tab shows requests being cancelled (red/cancelled status)
- No error toasts from aborted requests

- [ ] **Step 5: Commit**

```bash
git add src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): move App.tsx hydration effects behind hydration controller"
```

---

## Re-evaluation Point

After completing Tasks 1-7, manually test project switching performance. If the fix is sufficient, stop here. If there's still measurable lag:

**Potential next steps (not yet planned in detail):**
- **Tiered concurrency cap**: Add a request queue to `useHydrationController` that limits concurrent fetches to 4 for critical hooks, 3 for secondary. This requires hooks to register their hydration functions with the controller instead of running them independently.
- **Full state machine**: Introduce explicit `idle -> switching -> hydrating:critical -> hydrating:secondary -> ready` states if the phased loading UX is desired.
- **Server-side batched endpoint**: Single `/api/projects/{id}/context` that returns all dashboard data in one response.

These are more invasive and should only be pursued if the AbortController + debounce + poll suppression combo doesn't solve the problem.

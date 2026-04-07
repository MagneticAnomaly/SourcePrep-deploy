# Pipeline Rebuild Button — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Rebuild Pipeline" button to the Settings Danger Zone that triggers a full from-scratch pipeline rebuild using the existing atomic-write infrastructure — no data loss during rebuild.

**Architecture:** A new `POST /projects/{id}/pipeline/rebuild` endpoint calls `pipeline_orchestrator.run_all(project_id, force_from_start=True)`. The UI adds a new card to the existing Danger Zone section in `SettingsDrawer`. Every core engine already writes to temp files and atomically swaps via `os.rename`, so live data stays intact until each stage completes. No shadow DB or new infrastructure needed.

**Tech Stack:** Python (FastAPI), TypeScript (React), existing pipeline orchestrator

---

### Task 1: Backend — Add rebuild endpoint

**Files:**
- Modify: `src/codrag/api/routers/pipeline.py:147-163` (add new endpoint after `pipeline_run_all`)

- [ ] **Step 1: Add the rebuild endpoint**

Add this endpoint after the existing `pipeline_run_all` function (after line 163):

```python
@router.post("/projects/{project_id}/pipeline/rebuild")
def pipeline_rebuild(project_id: str) -> Dict[str, Any]:
    """Rebuild all pipeline stages from scratch (zero-downtime).

    Each stage rebuilds its output completely, writing to a temp file
    and atomically swapping it into the live index directory.  The
    existing data remains available until the new data is ready.

    Phase 76: This is the non-destructive alternative to Reset Graph +
    re-run.  It does NOT delete anything first — it overwrites in place.
    """
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_all(project_id, force_from_start=True)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Pipeline is already running for this project",
        )

    return ok({"started": True, "group": "all", "mode": "rebuild"})
```

- [ ] **Step 2: Update the module docstring**

Update the docstring at line 7 to include the new endpoint:

```python
"""
CoDRAG Pipeline Router — Phase 24 (SM-6) + Phase 25 (Crash Protection) + Phase 76 (Rebuild)
=======================================================================

Exposes the 8-stage pipeline orchestrator via HTTP endpoints.

**Endpoints:**
  - POST /projects/{id}/pipeline/fast     — run Fast Sync (stages 1-4)
  - POST /projects/{id}/pipeline/deep     — run Deep Enrichment (stages 5-8)
  - POST /projects/{id}/pipeline/all      — run all stages (fast → deep)
  - POST /projects/{id}/pipeline/rebuild  — rebuild all stages from scratch (Phase 76)
  - GET  /projects/{id}/pipeline/status   — pipeline status (8-stage, two-group)
  - POST /projects/{id}/pipeline/cancel   — cancel a running group
  - GET  /pipeline/crashed                — all crashed runs (Phase 25)
  - POST /pipeline/resume                 — resume a crashed run (Phase 25)
  - POST /pipeline/discard                — discard a crashed run (Phase 25)
"""
```

- [ ] **Step 3: Verify the backend starts**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && .venv/bin/python -c "from codrag.api.routers.pipeline import router; print('OK:', [r.path for r in router.routes])"`

Expected: Output includes `/projects/{project_id}/pipeline/rebuild`

- [ ] **Step 4: Commit**

```bash
git add src/codrag/api/routers/pipeline.py
git commit -m "feat(pipeline): add POST /pipeline/rebuild endpoint (Phase 76)"
```

---

### Task 2: Frontend — Add `rebuildPipeline` to API client

**Files:**
- Modify: `packages/ui/src/api/client.ts:150-157` (add method to interface)
- Modify: `packages/ui/src/api/client.ts:1040-1044` (add implementation)
- Modify: `packages/ui/src/api/mock.ts:463-465` (add mock)

- [ ] **Step 1: Add to the CodragApiClient interface**

In `packages/ui/src/api/client.ts`, after `runPipelineAll` (line 152), add:

```typescript
  rebuildPipeline(projectId: string): Promise<{ started: boolean; group: string; mode: string }>;
```

- [ ] **Step 2: Add the implementation**

In the `CodragHttpClient` class, after the `runPipelineAll` implementation (after line 1044), add:

```typescript
  async rebuildPipeline(projectId: string): Promise<{ started: boolean; group: string; mode: string }> {
    return this.requestEnvelope<{ started: boolean; group: string; mode: string }>(`/projects/${projectId}/pipeline/rebuild`, {
      method: 'POST',
    });
  }
```

- [ ] **Step 3: Add the mock**

In `packages/ui/src/api/mock.ts`, after `runPipelineAll` (after line 465), add:

```typescript
  async rebuildPipeline(): Promise<any> {
    return { started: true, group: 'all', mode: 'rebuild' };
  }
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npx tsc --noEmit -p packages/ui/tsconfig.json 2>&1 | head -20`

Expected: No errors related to `rebuildPipeline`

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/api/client.ts packages/ui/src/api/mock.ts
git commit -m "feat(ui): add rebuildPipeline API client method"
```

---

### Task 3: Frontend — Add rebuild handler to useTraceSystem

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useTraceSystem.ts:484-502` (add handler near destroy handlers)

- [ ] **Step 1: Add the handleRebuildPipeline callback**

In `useTraceSystem.ts`, after `handleDestroyGraph` (around line 502), add:

```typescript
  const handleRebuildPipeline = useCallback(async () => {
    if (!selectedProjectId) return
    try {
      await api.rebuildPipeline(selectedProjectId)
    } catch (err) {
      console.error('Failed to trigger pipeline rebuild:', err)
    }
  }, [api, selectedProjectId])
```

- [ ] **Step 2: Include it in the return object**

Find the return object (around line 741) and add `handleRebuildPipeline` alongside `handleDestroyGraph, handleDestroyIndex`:

```typescript
    handleDestroyGraph, handleDestroyIndex, handleRebuildPipeline,
```

- [ ] **Step 3: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useTraceSystem.ts
git commit -m "feat(dashboard): add handleRebuildPipeline to useTraceSystem"
```

---

### Task 4: Frontend — Wire rebuild button into SettingsDrawer

**Files:**
- Modify: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx:94-97` (add prop)
- Modify: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx:173` (add to confirm union)
- Modify: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx:260-289` (add card to danger zone)
- Modify: `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx:646-675` (add to confirm dialog)

- [ ] **Step 1: Add the prop to SettingsDrawerProps**

After `onDestroyIndex` (line 97), add:

```typescript
  onRebuildPipeline: () => void
```

- [ ] **Step 2: Destructure the new prop**

In the function parameters (around line 143), add `onRebuildPipeline` after `onDestroyIndex`:

```typescript
  onDestroyGraph,
  onDestroyIndex,
  onRebuildPipeline,
```

- [ ] **Step 3: Add 'rebuild' to the confirmAction union type**

Change the `confirmAction` state (line 173) from:

```typescript
  const [confirmAction, setConfirmAction] = useState<'graph' | 'index' | 'atlas' | 'group_reasoning' | 'deep_enrichment' | null>(null)
```

to:

```typescript
  const [confirmAction, setConfirmAction] = useState<'graph' | 'index' | 'rebuild' | 'atlas' | 'group_reasoning' | 'deep_enrichment' | null>(null)
```

- [ ] **Step 4: Handle the confirmed action**

In `handleConfirmedAction` (line 175-181), add after the `onDestroyIndex` line:

```typescript
    if (confirmAction === 'rebuild') onRebuildPipeline()
```

Update the dependency array to include `onRebuildPipeline`.

- [ ] **Step 5: Add the rebuild card to the Danger Zone section**

In the Danger Zone section (around line 269), change the grid from `grid-cols-2` to `grid-cols-3` and add a new card before the two existing ones:

```tsx
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 rounded border border-warning/30 bg-warning/5 flex flex-col justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-text">Rebuild Pipeline</p>
                      <p className="text-xs text-text-muted mt-1">Re-runs all 11 stages from scratch. Data stays live during rebuild.</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => setConfirmAction('rebuild')} className="w-full border-warning/40 text-warning hover:bg-warning/10">
                      Rebuild
                    </Button>
                  </div>
                  <div className="p-3 rounded border border-border bg-surface-raised flex flex-col justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-text">Reset Graph</p>
                      <p className="text-xs text-text-muted mt-1">Deletes trace graph and all enrichment data.</p>
                    </div>
                    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('graph')} className="w-full">
                      Reset
                    </Button>
                  </div>
                  <div className="p-3 rounded border border-error/30 bg-error/5 flex flex-col justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-text">Full Reset</p>
                      <p className="text-xs text-text-muted mt-1">Deletes everything including search index.</p>
                    </div>
                    <Button variant="destructive" size="sm" onClick={() => setConfirmAction('index')} className="w-full">
                      Reset All
                    </Button>
                  </div>
                </div>
```

- [ ] **Step 6: Add rebuild to the ConfirmDialog**

Update the `title` and `description` props of the `ConfirmDialog` (around line 646-675) to handle the `'rebuild'` case. The title should be:

```typescript
        title={
          confirmAction === 'rebuild' ? `Rebuild Pipeline for ${projectName || 'Project'}?`
            : confirmAction === 'graph' ? `Reset Graph for ${projectName || 'Project'}?`
            // ... rest unchanged
        }
```

The description:

```typescript
        description={
          confirmAction === 'rebuild'
            ? 'This will re-run all 11 pipeline stages from scratch. Your existing data remains available throughout the rebuild — each stage atomically replaces its output when the new version is ready. This can take a long time for large codebases.'
            : confirmAction === 'graph'
            // ... rest unchanged
        }
```

The confirmLabel:

```typescript
        confirmLabel={
          confirmAction === 'rebuild' ? 'Start Rebuild'
            : confirmAction === 'graph' ? 'Reset Graph'
            // ... rest unchanged
        }
```

- [ ] **Step 7: Commit**

```bash
git add src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx
git commit -m "feat(settings): add Rebuild Pipeline button to danger zone"
```

---

### Task 5: Frontend — Wire the prop through App.tsx

**Files:**
- Modify: `src/codrag/dashboard/src/App.tsx:866-867` (pass new prop to SettingsDrawer)

- [ ] **Step 1: Destructure handleRebuildPipeline from useTraceSystem**

At line 372, where `handleDestroyGraph` and `handleDestroyIndex` are destructured, add `handleRebuildPipeline`:

```typescript
    handleDestroyGraph, handleDestroyIndex, handleRebuildPipeline,
```

- [ ] **Step 2: Pass the prop to SettingsDrawer**

At line 866-867, after `onDestroyIndex`, add:

```tsx
        onRebuildPipeline={handleRebuildPipeline}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npx tsc --noEmit -p src/codrag/dashboard/tsconfig.json 2>&1 | head -20`

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/codrag/dashboard/src/App.tsx
git commit -m "feat(dashboard): wire rebuild pipeline prop through App"
```

---

### Task 6: Verify end-to-end

- [ ] **Step 1: Build the UI packages**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run build 2>&1 | tail -20`

Expected: Build succeeds

- [ ] **Step 2: Verify the backend endpoint works**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && .venv/bin/python -c "from codrag.api.routers.pipeline import router; routes = [r.path for r in router.routes]; assert '/projects/{project_id}/pipeline/rebuild' in routes; print('Rebuild endpoint registered')"`

Expected: `Rebuild endpoint registered`

- [ ] **Step 3: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "feat(phase76): pipeline rebuild button — end-to-end wiring"
```

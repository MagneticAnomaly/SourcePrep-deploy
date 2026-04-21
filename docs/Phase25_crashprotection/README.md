# Phase 25: Crash Protection & Resumability

**Status:** ✅ Implemented
**Owner:** @Cascade
**Related:** Phase 24 (State Machine), Phase 04 (Trace Index)

## 1. Problem Statement

Prep pipelines (Fast Sync, Deep Enrichment) are multi-stage, long-running processes (minutes to hours). Currently, all pipeline state is tracked **in-memory** within `PipelineOrchestrator` and `BuildOrchestrator`.

**The Risks:**
1.  **App Crash / Quit:** If the user quits the app (or it crashes via OOM/bug) during Stage 5 (Enrichment), the entire progress is lost. Upon restart, the app forgets it was doing anything.
2.  **Page Refresh:** If the user refreshes the browser/WebView, the React state is reset. While the backend continues running, the frontend may lose "connection" to the progress if not properly synchronized on mount.
3.  **Data Corruption:** While `CodeIndex` uses atomic swaps, the *incremental* Trace Graph updates might leave the graph in a valid but "incomplete" state relative to the pipeline's intent.
4.  **Zombie Locks:** If a process dies while holding a "Running" state in a persistent store (if we had one), a new instance might refuse to run, thinking another is active.

## 2. Solution Architecture: The "Black Box" Recorder

We need a persistent "Flight Recorder" or **Journal** that tracks the intent and progress of pipelines independently of the process memory.

### 2.1. The Pipeline Journal

A file-based store (likely `prep_settings.db` or a dedicated `pipeline_journal.json`) that records:

```json
{
  "project_id": "proj-123",
  "run_id": "run-abc-789",
  "group": "deep_enrichment",
  "status": "running",
  "current_stage": "enrichment",
  "stage_index": 4,
  "started_at": 1700000000,
  "last_heartbeat": 1700000050,
  "stages": {
    "structural": "completed",
    "catalogue": "completed",
    "enrichment": "running"
  }
}
```

### 2.2. Recovery Protocol (On Startup)

When `PipelineOrchestrator` initializes:
1.  **Read Journal:** Check for any runs marked `running`.
2.  **Liveness Check:** Since we just started, *any* run marked `running` is by definition a **crash** (the previous process is gone).
3.  **Resolution Strategy:**
    *   **Auto-Resume:** If the stage is "safe" (idempotent), restart that stage.
    *   **Rollback:** If the stage is risky, revert to the start of the group.
    *   **Mark Failed:** Update status to `crashed` and let the user decide.

### 2.3. UI Synchronization (Cosmetic Protection)

To handle page refreshes:
1.  **Source of Truth:** The UI must *never* rely solely on local state for pipeline status.
2.  **Hydration:** On mount, `useTraceSystem` must call `GET /projects/{id}/pipeline/status`.
3.  **Backend Response:** The backend returns the state from the **Journal** (or active memory).
4.  **Visual Continuity:** The UI reconstructs the progress bar and active stage from this response.

## 3. Implementation Strategy

### Phase 1: The Journal (Persistence)
*   Create `PipelineJournal` class backed by `prep_settings.db` (Table: `pipeline_runs`).
*   Update `PipelineOrchestrator` to write state transitions to the Journal.
    *   `run_start` -> INSERT
    *   `stage_start` -> UPDATE
    *   `stage_complete` -> UPDATE
    *   `run_complete` -> UPDATE status='completed'
    *   `run_fail` -> UPDATE status='failed'

### Phase 2: Heartbeating & Zombie Detection
*   While running, the worker thread updates a `last_heartbeat` timestamp every 10s.
*   On startup, or periodically, we check `now() - last_heartbeat > Threshold`.
*   If timed out, mark as `crashed`.

### Phase 3: Resume Logic
*   Implement `resume_pipeline(project_id)`:
    *   Loads last crashed run.
    *   Determines restart point (e.g., if crashed in Stage 3, restart Stage 3).
    *   Re-initializes the in-memory `PipelineRun` object.

### Phase 4: Data Safety (Checkpoints)
*   **Trace Graph:** Ensure `prep-graph` flushes to disk between stages.
*   **Backup:** Before starting a destructive stage (e.g., Deepening), copy `trace_nodes.jsonl` to `trace_nodes.bak`.
*   **Restore:** On crash recovery, if data looks corrupt, restore from `.bak`.

## 4. Specific Scenarios

### Scenario A: Browser Refresh
*   **Event:** User hits Cmd+R during "Enrichment".
*   **Impact:** React app reloads. Backend continues unaffected.
*   **Fix:** `useTraceSystem` mounts -> `useEffect` calls `status` -> Backend returns "Enrichment: Running" -> UI sets state to match -> Progress bar jumps to correct position.

### Scenario B: Power Loss during Write
*   **Event:** Computer shuts down while writing `trace_nodes.jsonl`.
*   **Impact:** JSONL file is half-written or empty.
*   **Fix:**
    1.  `TraceIndex` load fails (JSON parse error).
    2.  Crash Recovery detects "Crashed in Enrichment".
    3.  Because `TraceIndex` load failed, we look for `trace_nodes.jsonl.bak` (created at start of stage).
    4.  Restore backup -> Resume stage.

### Scenario C: OOM Kill
*   **Event:** OS kills Prep process during "Clustering" (RAM spike).
*   **Impact:** Process vanishes. Journal says "Running".
*   **Fix:**
    1.  App restarts.
    2.  `PipelineOrchestrator` sees "Running" in DB.
    3.  Marks it as "Crashed (Unexpected Exit)".
    4.  UI shows "Pipeline crashed. Resume?" button.
    5.  User clicks Resume -> Restart Clustering stage.

## 5. Implementation Status

All items completed. **31 tests passing.**

### Files Created
| File | Purpose |
|------|---------|
| `src/prep/services/pipeline_journal.py` | SQLite-backed journal: CRUD ops, heartbeat thread, crash recovery |
| `src/prep/services/pipeline_checkpoint.py` | Backup/restore/verify trace files, auto-heal corrupt data |
| `tests/test_pipeline_journal.py` | 31 tests: journal CRUD, checkpoint, recovery, orchestrator integration |

### Files Modified
| File | Changes |
|------|---------|
| `src/prep/services/pipeline_orchestrator.py` | Journal writes on every state transition, checkpoint before destructive stages, `resume_crashed_run()`, `discard_crashed_run()`, `startup_recovery()` |
| `src/prep/api/routers/pipeline.py` | `GET /pipeline/crashed`, `POST /pipeline/resume`, `POST /pipeline/discard` endpoints; `crashed_runs` in status response |
| `src/prep/server.py` | Journal init + startup crash recovery in `configure()` |
| `packages/ui/src/types.ts` | `CrashedPipelineRun` type, `crashed_runs` field on `PipelineStatus` |
| `packages/ui/src/api/client.ts` | `getCrashedRuns()`, `resumeCrashedRun()`, `discardCrashedRun()` API methods |
| `packages/ui/src/index.ts` | Barrel export for `CrashedPipelineRun` |
| `src/prep/dashboard/src/hooks/useTraceSystem.ts` | `crashedRuns` state, `handleResumeCrashedRun()`, `handleDiscardCrashedRun()`, crash detection on hydration |

### Action Items (all done)
1.  [x] **Schema Design:** `pipeline_runs` table in `prep_settings.db`
2.  [x] **Journal Class:** `PipelineJournal` with heartbeat thread + zombie detection
3.  [x] **Checkpoint System:** Backup trace files before destructive stages, auto-heal on recovery
4.  [x] **Orchestrator Integration:** Every transition writes to journal before work begins
5.  [x] **Startup Recovery:** `server.py configure()` → `journal.init()` → `startup_recovery()`
6.  [x] **API Endpoints:** Resume, Discard, Crashed Runs
7.  [x] **Frontend Wiring:** `useTraceSystem` crash detection + resume/discard handlers
8.  [x] **Tests:** 31 tests covering journal, checkpoint, and orchestrator integration

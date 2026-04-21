# Pipeline Selfheal Integration Design

**Date:** 2026-04-13
**Status:** Approved
**Scope:** Integrate backup resurrection and resume-awareness into the pipeline orchestrator so incomplete pipeline states are automatically recovered.

---

## Problem

The pipeline can end up in a "swiss cheese" state — stages scattered incomplete across the 3 groups (Fast Sync, Deep Enrichment, Finalize). This happens when:

- A pipeline run is paused and never resumed
- The daemon crashes or restarts mid-build
- A stage fails and downstream stages never trigger

The current system has no automatic mechanism to detect this state and recover. Incremental mode only activates when all stages are complete. A "priority inversion guard" in the orchestrator actively blocks incremental runs when deep enrichment is incomplete, making the problem worse.

Meanwhile, the backup system (golden checkpoints, run checkpoints, branch snapshots) holds recoverable data that could fill the gaps — but nothing invokes it for this scenario.

## Goals

1. Automatically detect incomplete stages and resurrect data from backups before pipeline runs
2. Remove the priority inversion guard so chain-forward works through incomplete states
3. Run selfheal at daemon startup for all active projects
4. Run selfheal as pre-flight before each group run (trigger-time safety net)
5. Keep the 3 pipeline modes (initial, incremental, rebuild) unchanged
6. Provide a dev-only flag to disable selfheal for testing raw pipeline behavior

## Non-Goals

- No new UI elements (no banners, no "incomplete" indicators)
- No new pipeline states or state machine transitions
- Selfheal does not re-run stages — it only resurrects data from backups
- No changes to the Rust selfheal CLI (Phase 61A) — that remains a separate diagnostic tool

## Design

### New method: `_selfheal_group(project_id, stages)`

**Location:** Core logic in `recovery.py` as `RecoveryManager.selfheal_group()`, called from orchestrator wrapper `_selfheal_group()`.

**Dev flag:** `CODRAG_SELFHEAL=0` environment variable disables selfheal. Checked at the top of `_selfheal_group()` — if set, log that selfheal is disabled and return immediately. Default is enabled.

**Algorithm:**

For each stage in the group:

1. Check if manifest exists and is non-stub → skip (stage already complete)
2. If manifest missing, attempt resurrection in priority order:
   a. **Golden checkpoint** (`.prep/.checkpoints/_golden/`) — known-good state from last successful deep enrichment
   b. **Run checkpoints** (`.prep/.checkpoints/<run_id>/`) — most recent with data for this stage's output file
   c. **Branch snapshot** (`.prep/.branch_snapshots/<current_branch>/`) — current branch data
3. For each source: check if the stage's output file exists in the backup AND is >1KB (not empty/stub)
4. If found: copy output file to `.prep/`, write stub manifest:
   ```json
   {
     "restored": true,
     "source": "selfheal",
     "backup_path": "<path to backup>",
     "backup_type": "golden|run_checkpoint|branch_snapshot",
     "restored_at": "<ISO timestamp>"
   }
   ```
5. If no backup data found: leave stage missing — `detect_resume_point()` will catch it and the stage runs from scratch
6. Log every decision to pipeline file logger

**Safety rules:**
- Never resurrect if manifest already exists (don't overwrite good data)
- `force_from_start` runs skip selfheal entirely (user wants fresh rebuild)
- Only copy if backup file >1KB (reject empty/corrupt backups)

### Call sites

#### 1. Daemon startup

In `startup_recovery()`, after existing hydration and auto-recovery:

```python
# NEW: selfheal all active projects
for project in get_active_projects():
    for stages in [FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES]:
        self._selfheal_group(project.id, stages)
```

By the time anything interacts with the daemon, pipelines are in the best possible state.

#### 2. Trigger-time pre-flight

In each `run_fast_sync()`, `run_deep_enrichment()`, `run_finalize()`, before `_detect_resume_point()`:

```python
# NEW: selfheal pre-flight (catches anything that went wrong mid-session)
if not force_from_start:
    self._selfheal_group(project_id, stages)
```

### Priority inversion guard removal

**Remove lines 483-498 of orchestrator.py** — the guard that checks if deep enrichment is incomplete and returns False.

With selfheal + resume in place, the chain-forward handles this naturally:

1. Fast sync completes (incrementally processes new/stale files)
2. Chain-forward fires → `run_deep_enrichment()`
3. Selfheal pre-flight resurrects what it can for stages 6-10
4. `detect_resume_point()` finds first still-missing stage
5. Workers run from there, skipping already-processed items
6. Same chain to finalize

### Chain-forward flow (unchanged, just unblocked)

```
Fast Sync triggers (file change or Run click)
  → selfheal: resurrect stages 1-5 from backups
  → detect_resume_point: first missing stage
  → run (workers skip processed items)
  → fast sync completes
  → chain-forward: is deep enrichment Auto?
     → YES:
        → selfheal: resurrect stages 6-10
        → detect_resume_point: first missing stage
        → run
        → chain to finalize (same pattern)
     → NO (Manual): stop, user triggers when ready
```

### Resurrection priority

| Priority | Source | Location | Rationale |
|----------|--------|----------|-----------|
| 1 | Golden checkpoint | `.prep/.checkpoints/_golden/` | Known-good from last successful deep enrichment |
| 2 | Run checkpoints | `.prep/.checkpoints/<run_id>/` | Recent, but may be mid-stage |
| 3 | Branch snapshot | `.prep/.branch_snapshots/<branch>/` | Current branch, may be from different code state |

### What selfheal does NOT do

- Does not re-run stages (resurrection only, orchestrator handles re-runs via normal resume)
- Does not touch the state machine (no new states or transitions)
- Does not add UI (dashboard shows same indicators — after resurrection, stages show checkmarks)
- Does not change the 3 modes (initial, incremental, rebuild unchanged)
- Does not replace Phase 61A Rust selfheal CLI (that remains a separate deep diagnostic tool)

## Files Changed

| File | Change |
|------|--------|
| `src/codrag/services/pipeline/orchestrator.py` | Add `_selfheal_group()` wrapper method. Remove priority inversion guard (lines 483-498). Call selfheal pre-flight in `run_fast_sync()`, `run_deep_enrichment()`, `run_finalize()`. Call selfheal in `startup_recovery()` for all active projects. |
| `src/codrag/services/pipeline/recovery.py` | Add `selfheal_group()` static method with resurrection logic: manifest scan, backup lookup (golden → run checkpoints → branch snapshots), file copy, stub manifest write. |
| `src/codrag/services/pipeline/resume.py` | No changes expected — `detect_resume_point()` already handles stub manifests correctly. |
| `src/codrag/services/pipeline/stages.py` | No changes — `STAGE_OUTPUT_FILE` and `STAGE_MANIFEST_FILE` mappings already exist. |

## Testing

- **Unit test:** `selfheal_group()` with mocked checkpoint directories — verify resurrection priority, safety rules, stub manifest format
- **Unit test:** Verify selfheal skipped when `CODRAG_SELFHEAL=0`
- **Unit test:** Verify selfheal skipped when `force_from_start=True`
- **Integration test:** Swiss cheese state (stages 5, 9, 10, 12-15 missing) with golden checkpoint containing data for some stages — verify partial resurrection + correct resume point
- **Integration test:** Priority inversion guard removed — verify chain-forward works through incomplete deep enrichment
- **Dev testing:** Run pipeline with `CODRAG_SELFHEAL=0`, pause mid-build, restart daemon, verify raw resume behavior without backup resurrection

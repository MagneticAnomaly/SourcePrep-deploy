# Phase 60D — Pipeline Incrementalism: "Assume Data Exists"

> **Date**: 2026-04-03  
> **Status**: Implemented  
> **Affects**: `orchestrator.py`, `GraphStructurePanel.tsx`

## Problem Statement

The CoDRAG pipeline was operating under a backwards assumption: it assumed it needed to rebuild from scratch unless it found data to resume from. This meant:

1. **Every server restart** triggered a full structural scan via the Rust engine
2. The Rust engine produces **6,185 file-level nodes**, overwriting the Python engine's **51,072 file + symbol nodes**
3. Downstream stages detected "stale" manifests (mtime mismatches) and cascade-restarted
4. **Hours of LLM reasoning work** (6,796 epistemic entries, 50,697 augmented entries) were destroyed
5. The dashboard showed misleading "Mapping full codebase..." text even when updating

Root cause chain:
```
Server restart → Watcher detects changed files → check_coverage_gap() → 
resume=0 (start from structural) → Rust engine replaces rich Python data → 
STALE_MTIME cascade → Deep enrichment restarts from 0%
```

## Design Philosophy

> **ASSUME data exists and USE it.**  
> Only rebuild from scratch as an absolute last resort — when NO data AND NO backup can be found.

### Decision Tree

| Condition | Action |
|-----------|--------|
| `force_from_start=True` (explicit UI "Destroy Graph") | Full rebuild from scratch |
| All stages complete + stale/untraced files | Skip structural, start from inferred_edges (stage 1). Workers handle delta internally |
| All stages complete + no stale files | Do nothing — up to date |
| Coverage check fails (exception) | Skip structural (safety), start from inferred_edges |
| Some stages missing + resume > 0 | Resume from first missing stage (earlier stages preserved) |
| No data on disk + resume = 0 | **Try restore from backup first** → then re-detect resume |
| No data on disk + no backup | Initial full run (ABSOLUTE LAST RESORT) |

### Key Principles

1. **Structural stage is NEVER re-run automatically** — The Rust engine's full scan (6K file-level nodes) destroys the Python engine's rich output (51K symbol-level nodes)
2. **Mtime cascade permanently disabled** — `skip_mtime_cascade=True` on every `_detect_resume_point()` call. Content-aware staleness: if output file > 1KB, stage is COMPLETE
3. **Workers own incrementality** — `EpistemicEnricher`, `TraceAugmenter`, `InferredEdgesAnalyzer` all load existing data and only process new/changed items
4. **Backup auto-recovery** — Before allowing a full rebuild, `_try_restore_from_backup()` scans `.checkpoints/` and restores the largest checkpoint

## Implementation Details

### 1. `run_fast_sync()` — Lines 416-555

- `skip_mtime_cascade=True` always passed to `_detect_resume_point()`
- When all stages complete and coverage gap exists: `resume = 1` (skip structural)
- Safety fallback (coverage check exception): `resume = 1`
- Before initial_full_run: call `_try_restore_from_backup()` first

### 2. `run_deep_enrichment()` — Lines 569-617

- `skip_mtime_cascade=True` always (not just when `is_incremental`)
- When all stages complete: call `_touch_stale_deep_manifests()` then start workers
- Workers load existing `trace_epistemic.jsonl` and only process new/changed nodes

### 3. `_detect_resume_point()` — Content-Aware Staleness

- If a stage's manifest has a stale mtime but output file exists (> 1KB):
  - Touch manifest to match structural mtime
  - Treat as COMPLETE
  - Log decision with `note = "workers handle incrementality"`

### 4. New Helper Methods

- `_try_restore_from_backup(project_id, stages, pfl)` — Scans `.checkpoints/`, finds largest checkpoint, restores files that are missing or smaller than backup
- `_touch_stale_deep_manifests(project_id)` — Touches deep enrichment manifests to match catalogue mtime
- `_sync_downstream_manifest_mtimes()` — Proactively syncs ALL downstream manifests after structural completion

### 5. UI Fix — `GraphStructurePanel.tsx`

Changed condition from `summary && summary.traced > 0` to `(summary && summary.traced > 0) || traceExists` so the dashboard shows "Updating..." instead of "Mapping full codebase..." when trace data exists but coverage hasn't loaded yet.

## Verification Checklist

- [x] Pipeline logs show `resume_point: 1` (structural skipped)
- [x] All stages detected as COMPLETE
- [x] Incremental mode activated for 181 changed files
- [x] Structural data preserved: 51,072 nodes, 64,985 edges
- [x] Epistemic data preserved: 6,796 entries
- [x] Augmented data preserved: 50,697 entries
- [x] Python syntax validation: OK
- [x] `force_from_start=True` never called automatically (only via explicit UI)

## Known Remaining Issues

1. ~~**Inferred Edges stage manifest conflict**~~ — **FIXED (Phase 60D-4):** The orchestrator's stage manifest (`trace_inferred_manifest.json`) was clobbering the `InferredEdgesAnalyzer`'s per-file hash manifest with its own provenance metadata (`{"format_version": "2.0", "stage_id": "inferred_edges", ...}`). The analyzer's `_load_manifest()` would load this metadata dict and find no matching file paths, causing ALL 4000+ files to be re-analyzed from scratch on every run. Fix: renamed the analyzer's hash manifest to `trace_inferred_hashes.json`, added migration logic for old hash data, and added a guard in `_load_manifest()` to reject orchestrator metadata.

2. ~~**API I/O contention**~~ — **FIXED (Phase 60D-2 + 60D-3):** Default API timeout increased from 8s to 30s. Dashboard now preserves last-known `traceStatus.exists` state during API timeouts instead of resetting to "no data". **Phase 60D-3:** Additionally, the `pipeline/status` endpoint and `trace/coverage` endpoint now run in a **dedicated 4-thread pool** (`_status_executor = ThreadPoolExecutor(4)`) to prevent LLM workers from starving the API. Previously, these endpoints competed with LLM workers for the default thread pool, causing total API blockage during heavy inference.

3. ~~**Per-stage freshness gate skipping incremental stages**~~ — **FIXED (Phase 60D-3):** The `_should_skip_stage_freshness()` check was comparing output file mtimes vs input file mtimes. During incremental runs, outputs from a previous full build are newer than inputs, causing the freshness check to skip stages that actually have new/stale files to process. Fix: bypass freshness check entirely when `project_id in self._incremental_runs`. Workers handle incrementality internally — they skip already-processed items and only do new ones.

## Files Modified

| File | Key Changes |
|------|-------------|
| `src/codrag/services/pipeline/orchestrator.py` | resume=1 in incremental, backup auto-recovery, skip_mtime_cascade everywhere, _touch_stale_deep_manifests, _try_restore_from_backup, **bypass freshness check in incremental mode** |
| `src/codrag/core/inferred_edges.py` | **Renamed hash manifest to `trace_inferred_hashes.json`**, added `_migrate_old_manifest()`, improved `_load_manifest()` to reject orchestrator metadata, added concurrency logging |
| `src/codrag/api/routers/pipeline.py` | **Dedicated thread pool (`_status_executor`)** for `pipeline_status` endpoint — async with `run_in_executor` |
| `src/codrag/api/routers/trace_routes/query.py` | **Dedicated thread pool (`_status_executor`)** for `trace_coverage_project` endpoint |
| `packages/ui/src/components/trace/GraphStructurePanel.tsx` | Fixed "Mapping full codebase" text condition with traceExists fallback |
| `packages/ui/src/api/client.ts` | Increased default requestEnvelope timeout from 8s to 30s |
| `src/codrag/dashboard/src/hooks/useTraceSystem.ts` | Preserve last-known trace state during API retry failures; don't reset `exists=false` when daemon is just slow |

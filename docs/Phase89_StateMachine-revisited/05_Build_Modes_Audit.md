# Phase 89: Build Modes Audit — Initial / Incremental / Rebuild

> Date: 2026-04-08
> Context: Verifying all three pipeline modes are properly connected

## Three Modes — How They Work

### 1. Initial Build (first run)
- **Trigger**: No pipeline data on disk, no backups
- **`force_from_start`**: False (default)
- **`_detect_resume_point()`** returns 0 (no manifests found)
- **Behavior**: Runs all stages from scratch. Each worker writes output for the first time.

### 2. Incremental Update (watcher-triggered or manual re-run)
- **Trigger**: All stages previously completed, but files changed/added since last run
- **Detection**: `orchestrator.py:414-495` — compares filesystem against trace, finds stale/untraced files
- **`incremental=True`** flag set on the run
- **Behavior**:
  - Freshness checks BYPASSED (workers handle incrementality themselves)
  - Workers read existing output, skip already-processed items, process only new/changed files
  - Progress shows `progress_baseline` (already-done) + new items = two-toned progress bar
  - Example: Catalogue has 1000 files done, 50 new → progress shows `[1000 baseline | 50 new]`

### 3. Rebuild (zero-downtime full rebuild)
- **Trigger**: User clicks "Rebuild Pipeline" in Settings → Danger Zone
- **API**: `POST /projects/{id}/pipeline/rebuild` → `run_all(force_from_start=True)`
- **`force_from_start=True`** → `resume=0` (ignore existing manifests)
- **Behavior**:
  - All stages run from scratch (like initial build)
  - BUT existing data stays live — MCP server keeps serving queries from old data
  - Workers write to temp files, then atomically rename (e.g., `augmenter.py:1899-1908`)
  - Integrity guard prevents output from shrinking vs pre-flight snapshot
  - Each stage's output replaces the old one atomically — search/MCP sees new data immediately after swap

## What's Connected ✅

| Aspect | Status | Evidence |
|--------|--------|----------|
| `force_from_start` flows through all groups | ✅ | `run_all()` passes to both `run_fast_sync()` and `run_deep_enrichment()` |
| Resume detection respects `force_from_start` | ✅ | `resume = 0 if force_from_start else _detect_resume_point()` |
| Incremental flag propagated | ✅ | `_persist_incremental_flag()` stores it, workers read it |
| Freshness bypass in incremental | ✅ | `ResumeStrategy.should_skip_stage_freshness()` returns False when `is_incremental=True` |
| Two-toned progress bar | ✅ | `progress_baseline` flows from `BuildSlot` → API → `enrichmentReducer` → UI |
| Atomic writes in workers | ✅ | Augmenter, epistemic enrichment, clustering use temp+rename |
| Integrity guard | ✅ | Pre-flight snapshot → post-flight comparison → blocks if output shrinks |
| MCP stays live during rebuild | ✅ | CodeIndex serves from live files; workers write to temp then swap |
| Fast→Deep chaining in auto mode | ✅ | `_advance_pipeline()` calls `run_deep_enrichment()` after fast_sync completes when auto=True |
| Phase 89 lock lifecycle | ✅ | Release-after-advance, cancel/pause release, ghost guard — all work for all three modes |

## Gap Found: Rebuild Doesn't Invalidate Deep Enrichment Manifests

When `force_from_start=True` runs fast_sync, the structural/catalogue/etc stages rebuild completely. But when deep enrichment auto-chains, the `_detect_resume_point()` for deep enrichment checks manifests — which still exist from the previous run. If the manifests are "fresh" (output mtime > input mtime), deep enrichment stages get SKIPPED even though the underlying data was completely rebuilt.

**Current mitigation**: `orchestrator.py:1347-1356` — when fast_sync chains to deep enrichment after an incremental run, it explicitly invalidates deep enrichment manifests:

```python
# If fast_sync ran incrementally, force deep to re-run from scratch
# because the enrichment stages depend on structural data that changed.
if project_id in self._incremental_runs:
    self._invalidate_deep_manifests(project_id, pfl)
```

**But for rebuild (`force_from_start=True`)**: The project is NOT in `_incremental_runs` (it's a full rebuild, not incremental). So the manifest invalidation is SKIPPED. Deep enrichment resumes from where it left off instead of rebuilding from scratch.

**Impact**: "Rebuild Pipeline" rebuilds fast_sync from scratch but deep enrichment may skip stages if they look fresh. This defeats the purpose of a full rebuild.

**Fix needed**: Also invalidate deep manifests when `force_from_start=True`. Either:
1. Check `force_from_start` in addition to `_incremental_runs` at the chaining point
2. Store the `force_from_start` flag on the run and check it at chain time

## Gap Found: No `progress_baseline` for Rebuild

When running in rebuild mode (`force_from_start=True`), workers process ALL items from scratch. But the progress bar may still show `progress_baseline > 0` if the build slot was initialized with existing counts. This is a minor UI inconsistency — the baseline should be 0 for rebuilds since nothing is being reused.

## Summary

The three modes are well-connected. The Phase 89 stage handoff fixes (release-after-advance, cancel/pause lock release, ghost guard) work correctly for all three modes because they operate at the scheduler/state-machine level, below the mode decision.

**One actionable gap**: Deep enrichment manifest invalidation during rebuild. This should be a quick fix — add `force_from_start` to the invalidation condition at the chaining point.

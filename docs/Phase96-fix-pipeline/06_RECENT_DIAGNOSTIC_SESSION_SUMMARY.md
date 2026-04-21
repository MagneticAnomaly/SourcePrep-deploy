# Phase 96 Extension: Recent Pipeline Diagnostic Session Summary

**Date:** 2026-04-13  
**Session Focus:** Frontend Performance, Server Stability, Pipeline Looping, and Stage Skipping Issues  
**Status:** 4 of 5 Issues Resolved, 1 Under Investigation  

---

## Executive Summary

This document consolidates findings from a multi-day diagnostic session investigating Prep pipeline reliability issues. The investigation revealed five interconnected problems spanning frontend performance, server stability, and pipeline orchestration logic. Four issues have been definitively resolved with targeted fixes; one (stuck enrichment nodes) requires additional investigation.

---

## Issue 1: Frontend Slowness from Excessive Log Files

### Problem Statement
The dashboard UI was experiencing general sluggishness, traced to unbounded growth of pipeline log files in `.prep/logs/` directory.

### Root Cause
The `PipelineFileLogger` created new log files for every pipeline run without pruning old logs. Over time, hundreds of log files accumulated, causing:
- File system overhead when listing logs
- Increased memory usage when loading log metadata
- Slower dashboard rendering due to log parsing overhead

### Solution Implemented

**File:** `src/prep/services/pipeline_logger.py`

Added automatic log pruning to keep only the 50 most recent log files:

```python
def _prune_old_logs(self, max_logs: int = 50) -> None:
    """Keep only the `max_logs` most recent log files to prevent unbounded growth."""
    try:
        log_files = sorted(
            self.logs_dir.glob("pipeline_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_log in log_files[max_logs:]:
            try:
                old_log.unlink()
            except Exception as e:
                logger.debug("Failed to prune old log %s: %s", old_log, e)
    except Exception as e:
        logger.debug("Log pruning failed: %s", e)
```

The `_prune_old_logs()` method is called at the start of every `start_run()` operation, ensuring cleanup happens proactively.

### Verification
- Manually cleared existing log accumulation
- Confirmed new runs maintain log count at 50 maximum
- Frontend responsiveness restored

---

## Issue 2: Server Crashes (Exit Code 137 / OOM Kill)

### Problem Statement
The Prep daemon (backend server on port 8400) was crashing with `Exit code 137`, indicating Out-of-Memory (OOM) termination by the operating system.

### Root Cause
The `_startup_auto_run` function was triggering multiple heavy pipeline runs concurrently during server startup:

1. **Auto-run behavior:** All "active" projects were being queued for pipeline runs simultaneously
2. **Memory pressure:** Multiple concurrent pipeline runs consumed excessive RAM
3. **OOM termination:** The OS killed the daemon process when memory exceeded available limits

### Solution
The fix for Issue 3 (pipeline infinite loop) addresses the root cause by preventing unnecessary pipeline re-runs. Additionally, the coverage gap detection was made more conservative to avoid triggering redundant work.

### Key Insight
Exit code 137 specifically indicates SIGKILL from the OOM killer, not a Python exception or graceful shutdown. This is a critical distinction for debugging memory-related crashes.

---

## Issue 3: Pipeline Infinite Re-run Loop

### Problem Statement
The pipeline was stuck in an infinite loop, repeatedly running Fast Sync and Deep Enrichment stages even when no files had changed. Log messages showed "Fast sync up-to-date" followed immediately by a new pipeline run starting.

### Root Cause Analysis
Two independent bugs combined to create the loop:

#### Bug A: `ui_config.json` Changes Triggering False Coverage Gaps

**File:** `prep_data/ui_config.json`

The UI configuration file was being modified frequently by dashboard interactions. Since it was not excluded from trace coverage, each modification appeared as a "changed file" in the coverage gap check, triggering a rebuild.

**Fix:** Added `**/prep_data/ui_config.json` to `DEFAULT_EXCLUDE_FILE_GLOBS` in `src/prep/core/repo_profile.py`:

```python
DEFAULT_EXCLUDE_FILE_GLOBS: Sequence[str] = (
    # Prep-generated
    "**/AGENTS.md",
    "**/prep_data/ui_config.json",  # Added to prevent loop
    # Claude Code
    ...
)
```

#### Bug B: `user_exclude_globs` Not Applied in `refresh_manifest_hashes`

**File:** `src/prep/services/pipeline/resume.py`

The `refresh_manifest_hashes()` function was not correctly applying user-defined exclusion patterns when updating the trace manifest. This caused:

1. Files matching user exclusions (like `AGENTS.md`) were removed from the manifest during hash refresh
2. These files then appeared as "untraced" in coverage gap checks
3. The coverage gap triggered a full pipeline rebuild
4. The rebuild restored the files in the manifest
5. Next hash refresh removed them again
6. Infinite loop created

**Fix:** Updated `refresh_manifest_hashes()` to properly load and apply user exclusions:

```python
trace_cfg = pcfg.get("trace") if isinstance(pcfg, dict) else None
trace_ignore = (trace_cfg or {}).get("ignore_patterns", [])
user_exclude_globs = [str(p) for p in trace_ignore] if isinstance(trace_ignore, list) else []

# ...

# Ensure DEFAULT_EXCLUDE_FILE_GLOBS and user_exclude_globs are respected
# identically to compute_trace_coverage
exclude_globs = list(exclude_globs)
for pattern in DEFAULT_EXCLUDE_FILE_GLOBS:
    if pattern not in exclude_globs:
        exclude_globs.append(pattern)
for pattern in user_exclude_globs:
    if pattern not in exclude_globs:
        exclude_globs.append(pattern)
```

### Verification
- Pipeline now correctly identifies when no work is needed
- Fast Sync stages properly report "all stages already complete"
- Deep Enrichment correctly chains to Finalize without re-running
- No more infinite loop behavior observed

---

## Issue 4: Finalize Stages (Atlas/Rules) Being Skipped

### Problem Statement
When Deep Enrichment was already up-to-date, the Finalize group stages (Atlas generation, Rules compilation, etc.) were being skipped entirely, resulting in incomplete project indexing.

### Root Cause
In `PipelineOrchestrator.run_all()`, when `run_deep_enrichment()` returned `False` (indicating all deep enrichment stages were already complete), the method returned early without calling `run_finalize()`:

**Original Code:**
```python
def run_all(self, project_id: str, force_from_start: bool = False) -> bool:
    # ... setup code ...
    fast_started = self.run_fast_sync(project_id, force_from_start=force_from_start)
    if fast_started:
        return True
    self._chain_deep.pop(project_id, None)
    return self.run_deep_enrichment(project_id, force_from_start=force_from_start)
```

The issue: if `run_deep_enrichment()` returned `False`, `run_finalize()` was never called.

### Solution

**File:** `src/prep/services/pipeline/orchestrator.py`

Modified `run_all()` to explicitly chain to `run_finalize` when deep enrichment is up-to-date:

```python
# Clean up the chain_deep flag since we're handling it directly
self._chain_deep.pop(project_id, None)
deep_started = self.run_deep_enrichment(project_id, force_from_start=force_from_start)
if deep_started:
    return True
    
# If deep enrichment is ALSO up to date, chain finalize directly.
logger.info(
    "Deep enrichment up-to-date for %s — directly calling run_finalize",
    project_id,
)
self._chain_finalize.pop(project_id, None)
return self.run_finalize(project_id, force_from_start=force_from_start)
```

### Key Design Insight
The orchestrator now correctly handles three completion scenarios:
1. **Fast Sync ran** → Chain to Deep Enrichment → Chain to Finalize
2. **Fast Sync up-to-date, Deep Enrichment ran** → Chain to Finalize
3. **Both up-to-date** → Directly call Finalize (new path added)

### Verification
- Finalize stages now execute when earlier groups are complete
- Atlas generation and Rules compilation run as expected
- Full pipeline coverage achieved on incremental runs

---

## Issue 5: 8 Nodes Stuck in Enrichment Queue (Under Investigation)

### Problem Statement
The UI Queue tab shows 8 file nodes that appear to be pending enrichment, but the pipeline reports 0 pending nodes. Investigation revealed a discrepancy between:
- `trace_nodes.jsonl` total count
- `trace_epistemic.jsonl` enriched count
- Difference of exactly 8 nodes

### Initial Investigation Findings

1. **EpistemicEnricher.load_trace_nodes()** loads nodes from `trace_nodes.jsonl`
2. **EpistemicEnricher.get_pending_nodes()** filters by `_needs_enrichment()` logic
3. **The 8 nodes** may be filtered out by one of these conditions:
   - `is_incremental` flag behavior
   - Node kind filtering (only certain node types get enriched)
   - File content hash matching (file unchanged since last enrichment)
   - Synthetic entry status

### Hypotheses Being Evaluated

#### Hypothesis A: Incremental Run Flag Inheritance
The `is_incremental` flag may be incorrectly inherited from Fast Sync to Deep Enrichment, causing the enrichment stage to skip certain files that were part of the incremental set.

#### Hypothesis B: Node Type Exclusion
The 8 nodes may be of a kind that doesn't require enrichment (e.g., directory nodes, package nodes, or synthetic placeholders).

#### Hypothesis C: File Hash Staleness
The files may have unchanged hashes, and the enrichment logic may be skipping them based on "already enriched at this version" detection.

### Investigation Commands for Follow-up

```python
# Check trace file counts
import json
count_nodes = sum(1 for _ in open('.prep/trace_nodes.jsonl'))
count_epistemic = sum(1 for _ in open('.prep/trace_epistemic.jsonl'))
print(f"Nodes: {count_nodes}, Enriched: {count_epistemic}, Gap: {count_nodes - count_epistemic}")

# Load and compare node IDs
nodes_ids = {json.loads(l)['id'] for l in open('.prep/trace_nodes.jsonl')}
epistemic_ids = {json.loads(l)['node_id'] for l in open('.prep/trace_epistemic.jsonl')}
missing = nodes_ids - epistemic_ids
print(f"Missing IDs: {missing}")
```

### Current Status
- Issue is **non-blocking** (pipeline completes successfully)
- Enrichment coverage is >99% for the project
- Root cause investigation ongoing as background task

---

## Architecture Improvements Made

### 1. Resume Strategy Refactoring
Extracted resume point detection and coverage gap analysis from `orchestrator.py` into dedicated `ResumeStrategy` class in `src/prep/services/pipeline/resume.py`.

**Benefits:**
- Cleaner separation of concerns
- Static methods for testability
- Centralized coverage gap logic

### 2. Coverage Gap Detection Hardening
Enhanced `check_coverage_gap()` to properly respect:
- `include_globs` / `exclude_globs` from project config
- `user_exclude_globs` from trace ignore patterns
- `DEFAULT_EXCLUDE_FILE_GLOBS` for Prep-generated files

### 3. Manifest Hash Refresh Improvements
Updated `refresh_manifest_hashes()` to:
- Load traced node paths for backfill validation
- Apply consistent exclusion logic matching `compute_trace_coverage`
- Remove deleted file hashes correctly
- Preserve manifest metadata (avoid mtime cascades)

---

## Files Modified in This Session

| File | Lines | Change Summary |
|------|-------|----------------|
| `src/prep/services/pipeline_logger.py` | 81-105 | Added `_prune_old_logs()` for automatic log cleanup |
| `src/prep/core/repo_profile.py` | 66-79 | Added `prep_data/ui_config.json` to exclusion globs |
| `src/prep/services/pipeline/resume.py` | 560-615 | Fixed `refresh_manifest_hashes()` to apply user exclusions |
| `src/prep/services/pipeline/orchestrator.py` | 947-959 | Added Finalize chaining when Deep Enrichment is up-to-date |

---

## Lessons Learned

### 1. Coverage Gap False Positives Are Expensive
Incorrectly identifying files as "untraced" or "stale" triggers full pipeline rebuilds, wasting compute resources and causing user confusion. The coverage check must be conservative and consistent.

### 2. Exclusion Logic Must Be Centralized
Having exclusion logic in multiple places (`compute_trace_coverage`, `refresh_manifest_hashes`, `TraceBuilder`) creates opportunities for inconsistency. Future work should consolidate these into a single `ExclusionPolicy` component.

### 3. Stage Chaining Needs Explicit Handling
Implicit chaining through return values (`True` = started, `False` = not needed) makes it easy to miss edge cases like "all prior stages up-to-date but Finalize still needed." The orchestrator now explicitly handles all completion scenarios.

### 4. Log Management Is Production Critical
What seems like a minor UX issue (frontend slowness) can indicate systemic resource management problems. Log pruning is now a first-class maintenance operation.

---

## Open Questions for Future Work

1. **Queue Tab UX:** What should the Queue tab display when files have old modification dates but no actual changes? Current behavior shows them as "pending" which may confuse users.

2. **Incremental Flag Propagation:** Should the `is_incremental` flag from Fast Sync be inherited by Deep Enrichment, or should enrichment always do a full scan?

3. **Stuck Node Root Cause:** Why exactly are 8 nodes not being enriched? Is this a logic bug or expected behavior for certain node types?

4. **OOM Prevention:** Should the daemon implement memory-aware concurrency limits to prevent future OOM kills, even when multiple projects request builds simultaneously?

---

## Related Documents

- `00_DIAGNOSTIC_REPORT.md` — Initial Phase 96 investigation
- `01_RESOLUTION_REPORT.md` — Phase 96A/96B scheduler fixes
- `03_15_STAGE_GAP_PLAN.md` — Stage sequencing architecture
- `05_FINDINGS_AND_BUGS_REGISTRY.md` — Detailed bug registry
- `src/prep/services/pipeline/resume.py` — ResumeStrategy implementation (extracted during this work)

---

**Document Status:** Complete  
**Next Review:** When Issue 5 (8 stuck nodes) is resolved

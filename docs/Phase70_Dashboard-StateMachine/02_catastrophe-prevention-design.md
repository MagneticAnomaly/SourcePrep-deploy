# Phase 70B: Catastrophe Prevention Design Notes

## Context

Phase 60 (IntegrityGuard) and Phase 61 (SelfHeal) already built the backend safety net:
- **IntegrityGuard**: pre/post-flight data comparison for every pipeline stage
- **SelfHeal**: startup recovery, heartbeat watchdog, zombie detection
- **Diagnostic CLI**: Rust binary for fast coverage gap analysis

What's missing is the **frontend/state-machine layer** that prevents the dashboard from:
1. Triggering unnecessary re-runs that cascade-invalidate downstream stages
2. Showing stale data that causes users to think stages need re-running
3. Losing track of where the 11-stage pipeline actually is

## Failure Modes We've Already Hit

### 1. Manifest-data mismatch (just fixed)
- **What**: Rust engine builds 16K nodes but manifest `counts` field is null
- **Effect**: Dashboard shows "0 nodes · 0 edges", user thinks graph is empty
- **User action**: Clicks "Rebuild" → destroys hours of LLM work
- **Fix applied**: Fallback to loaded data when manifest lacks counts

### 2. Status endpoint blocking (just fixed)
- **What**: Synchronous filesystem walk in status endpoint blocks event loop
- **Effect**: All API requests time out, dashboard freezes
- **User action**: Thinks daemon crashed, kills process mid-pipeline
- **Fix applied**: Async endpoints + 30s staleness cache

### 3. Hydration cascade (just fixed)
- **What**: 25 concurrent API calls on project switch overwhelm daemon
- **Effect**: Dashboard freezes, stale data from wrong project appears
- **User action**: Clicks destructive buttons while seeing wrong project's data
- **Fix applied**: AbortController + debounce + signal guarding

### 4. Stale ghost data (from Phase 61 post-mortem)
- **What**: Pipeline skips a stage, leaves old JSONL on disk
- **Effect**: Dashboard shows stale data as if it's current
- **Root cause**: Early-return optimization doesn't truncate old artifacts

### 5. Telemetry payload bloat (from Phase 61 post-mortem)
- **What**: 1.9 MB telemetry in pipeline status response
- **Effect**: Browser spends 80% CPU on JSON.parse, UI freezes
- **Fix applied**: Scrub telemetry before wire

## What Intelligent Catastrophe Prevention Looks Like

### Principle: The dashboard should never let you destroy data you can't rebuild

Three layers:

### Layer 1: Read-only safety (frontend)
- **Pipeline stage awareness**: The dashboard knows which stages have completed and their timestamps
- **Rebuild cost estimation**: Before any destructive action, show "This will invalidate X hours of LLM work across Y stages"
- **Confirmation gates**: "Destroy Graph" requires explicit confirmation with impact summary
- **Stale detection**: Compare manifest timestamps to show which stages are current vs. stale

### Layer 2: Pre-flight validation (backend, mostly exists in Phase 60)
- **IntegrityGuard**: Already compares pre/post file sizes
- **Cascade analysis**: Before running a stage, check if it would invalidate downstream work
- **Size guards**: Refuse to overwrite a 22 MB file with a 0-byte result

### Layer 3: Recovery (backend, mostly exists in Phase 61)
- **Auto-recovery on startup**: Detects interrupted runs, resumes from last checkpoint
- **Heartbeat watchdog**: Detects stalled pipelines
- **Manifest age tracking**: Shows exactly when each stage last completed

## What to Build Next

### Frontend state machine enhancements (Phase 70B)

1. **Pipeline stage timeline**: Show the 11 stages with last-completed timestamps.
   Compare each stage's manifest mtime to detect "stage X ran after stage Y was
   invalidated". This prevents the "stale ghost data" problem.

2. **Destructive action guards**: Before Destroy Graph, Destroy Index, or full rebuild:
   - Query IntegrityGuard for current data sizes
   - Show estimated rebuild time based on historical run durations
   - Require explicit confirmation: "This will destroy 16,711 nodes built over 3.2 seconds.
     Downstream stages (epistemic, modules, atlas) will need to re-run (~55 minutes)."

3. **Pipeline health indicator**: Single badge showing whether the pipeline is
   internally consistent (all stages' data is newer than their inputs) or has
   stale segments. This replaces the current "Overall Health 64% (7/11)" which
   doesn't tell you *why* stages are incomplete.

4. **Auto-refresh after pipeline completion**: When SSE reports a stage completed,
   refresh only the affected panels instead of re-fetching everything.

### Backend guardrails (Phase 70C, future)

5. **Manifest count backfill**: When the Rust engine finishes, write accurate
   `counts` to the manifest. This prevents the "0 nodes" display bug permanently.

6. **Cascade-aware stage runner**: Before starting a stage, check if its inputs
   are newer than its outputs. If outputs are already up-to-date, skip with a
   clear "Already current" message instead of silently re-running.

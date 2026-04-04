# Phase 61 — Self-Heal: Pipeline Integrity & Auto-Recovery

## Overview

Phase 61 provides a comprehensive self-healing system for the CoDRAG pipeline. It ensures the 11-stage enrichment pipeline maintains integrity, recovers from crashes and stalls, and proactively detects broken or stale database states.

The system has two layers:

| Layer | Name | Type | Status |
|-------|------|------|--------|
| **Phase 61A** | `codrag-selfheal` | Read-only Rust diagnostic CLI | ✅ Implemented |
| **Phase 61B** | Active Self-Heal | Python startup recovery + heartbeat watchdog | ✅ Implemented |

---

## Phase 61A: Diagnostic CLI (`codrag-selfheal`)

**Location:** `engine/crates/codrag-selfheal/src/main.rs`

A standalone Rust binary that cross-references the filesystem against pipeline checkpoint files to identify coverage gaps. Designed for fast, read-only analysis.

### Checkpoints Monitored

1. **Traced (`trace_nodes.jsonl`)**: Structural Graph (Stage 1)
2. **Augmented (`trace_augmented.jsonl`)**: Fast Catalogue (Stage 3)
3. **Enriched (`trace_epistemic.jsonl`)**: Deep Enrichment (Stages 6 & 10)
4. **Clustered (`trace_modules.jsonl`)**: Module Synthesis (Stage 8)

### Execution Flow

1. **Policy Loading**: Reads `.codrag/repo_policy.json` for include/exclude globs.
2. **Filesystem Walk**: Uses `codrag-walker` for sub-100ms scanning.
3. **Pipeline Data Loading**: Parses file paths from JSONL checkpoints.
4. **Diff Analysis**: `filesystem_files - pipeline_files` per checkpoint.
5. **Reporting**: JSON output with coverage percentages and missing files.

### Usage

```bash
cargo run -p codrag-selfheal -- /path/to/repo /path/to/repo/.codrag
```

---

## Phase 61B: Active Self-Heal System

Phase 61B transforms passive diagnostics into an active recovery system that operates at three critical points in the pipeline lifecycle:

### 1. Server Startup Recovery

**File:** `src/codrag/services/pipeline/orchestrator.py` → `_auto_recover_stale_pipelines()`

On every server startup, the orchestrator:

1. **Detects zombie metadata**: Scans `pipeline_run_metadata.json` for all projects. If `status == "running"` but the process no longer exists (heartbeat stale or started_at > 1 hour ago), resets to `"interrupted"`.

2. **Logs manifest age summary**: Writes a comprehensive `selfheal.manifest_age` event showing exactly when each of the 11 stages last completed. This is the single most valuable diagnostic for "why is the pipeline stuck?"

3. **Auto-triggers recovery**: If `deep_enrichment` auto mode is enabled and deep manifests are older than the structural trace manifest, auto-queues `run_deep_enrichment()` after a 10s warmup delay.

### 2. Heartbeat System

**File:** `src/codrag/services/pipeline_metadata.py`

Active pipeline stages write a `heartbeat_at` timestamp to `pipeline_run_metadata.json` every 60 seconds. This allows the watchdog to distinguish:

- **Genuinely running**: heartbeat < 5 minutes old
- **Stuck/zombie**: heartbeat > 5 minutes old or absent

Key functions:
- `update_heartbeat(index_dir)` — called by the heartbeat timer
- `check_heartbeat_stale(index_dir)` — returns `None` (healthy) or `{"status": "zombie"|"stale_heartbeat", ...}`
- `reset_stale_metadata(index_dir, reason)` — resets stale metadata to `"interrupted"`

### 3. Heartbeat Watchdog

**File:** `src/codrag/core/watcher.py` → `_on_coverage_check()`

Piggybacks on the existing 5-minute coverage check timer. Every coverage check cycle also:

1. Calls `check_heartbeat_stale()` for the project
2. If stale: logs `selfheal.heartbeat_stale` event, resets metadata, force-resets in-memory state, re-triggers pipeline
3. If healthy: logs `selfheal.heartbeat_ok` at DEBUG level

---

## Diagnostic Logging

Phase 61B introduces `selfheal` events in the pipeline file logger (`pipeline_logger.py`). These are structured JSON events written to `.codrag/logs/pipeline_*.log`:

```json
{"ts": "...", "event": "selfheal", "data": {"action": "stale_detected", "detail": "zombie metadata found", ...}}
{"ts": "...", "event": "selfheal", "data": {"action": "metadata_reset", "detail": "Reset stale metadata", ...}}
{"ts": "...", "event": "selfheal", "data": {"action": "manifest_age", "detail": "...", "manifests": {...}}}
{"ts": "...", "event": "selfheal", "data": {"action": "auto_recover", "detail": "Triggering deep enrichment", ...}}
{"ts": "...", "event": "selfheal", "data": {"action": "heartbeat_stale", "detail": "Watchdog detected zombie", ...}}
```

### Self-Heal Actions

| Action | When | What it means |
|--------|------|---------------|
| `startup_scan` | Server startup | Scanning projects for stale state |
| `stale_detected` | Server startup | Found zombie/stale pipeline_run_metadata.json |
| `metadata_reset` | Startup/watchdog | Reset stale metadata to "interrupted" |
| `auto_recover` | After metadata reset | Auto-triggering pipeline to recover |
| `heartbeat_ok` | Every 5min (watchdog) | Pipeline heartbeat is fresh |
| `heartbeat_stale` | Watchdog detection | Pipeline heartbeat expired |
| `heartbeat_write` | Every 60s (active) | Active stage wrote heartbeat |
| `manifest_age` | Startup | Per-stage manifest age summary |
| `coverage_gap` | Coverage check | Files missing at checkpoints |

---

## Problem This Solves

### The Zombie Pipeline Bug

The CoDRAG pipeline lifecycle depends on `pipeline_run_metadata.json` to track running state. When the dev server crashes or restarts:

1. The in-memory `PipelineGroupStateMachine` instances are lost
2. `pipeline_run_metadata.json` still says `"status": "running"`
3. The watcher triggers fast_sync on file changes, but deep enrichment never chains because the old manifests appear "complete"
4. The pipeline gets stuck with stale data indefinitely

Phase 61B breaks this deadlock by:
- Detecting on startup that the metadata is a zombie
- Resetting it to allow fresh pipeline runs
- Auto-triggering deep enrichment when manifests are stale
- Running a continuous watchdog to prevent future zombies

### The Silent Stall

Even when the server doesn't restart, a pipeline stage can stall silently (LLM timeout, deadlock, OOM). The heartbeat system detects this: if a stage hasn't heartbeated in 5 minutes, the watchdog intervenes.

---

## Phase 61D: Data-First Incrementalism (2026-04-03)

> Cross-ref: See `Phase60_db-backup/60D_Pipeline_Incrementalism.md` for full technical details.

Phase 61D addresses the root cause of the "silent rebuild" issue — the pipeline was operating under the wrong assumption (rebuild unless data found) instead of the correct one (assume data exists, use it).

### Key Changes

1. **Structural stage skip** — `resume=1` in incremental mode prevents Rust engine from overwriting Python's 51K nodes
2. **Backup auto-recovery** — `_try_restore_from_backup()` scans `.checkpoints/` before allowing a full rebuild  
3. **Mtime cascade disabled** — `skip_mtime_cascade=True` everywhere prevents false-positive staleness
4. **Dashboard resilience** — API timeout increased 8s→30s; dashboard preserves known-good state during retries
5. **Deep manifest touching** — `_touch_stale_deep_manifests()` prevents deep stage cascade restarts

---

## Future Enhancements

- [ ] **Dashboard health indicator**: Expose `/api/pipeline/health` with per-stage freshness
- [ ] **Integrate Rust selfheal CLI**: Call from Python after fast_sync completion
- [ ] **Auto-prune old logs**: Rotate `.codrag/logs/` after N days or N MB
- [ ] **Sub-atlas freshness check**: Verify segment/role atlases are complete
- [ ] **Coverage gap autofix**: When codrag-selfheal finds gaps, trigger specific stages
- [ ] **Inferred edges manifest separation**: Split orchestrator stage manifest from InferredEdgesAnalyzer hash manifest to enable true incremental edge discovery

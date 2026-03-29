# Phase 60: Database Backup & Integrity Guard

> **From debugging tool to product feature**: A layered approach to pipeline data integrity that starts as a near-zero-cost data loss detector and evolves into a versioned backup system.

## Problem Statement

The CoDRAG pipeline processes codebases through 11 sequential stages, each writing output files (JSONL, JSON, NPY) to the project's `.codrag/` directory. Several failure modes can silently destroy hours of LLM processing work:

1. **Full rebuild when incremental was intended** — Stage 1 runs fresh, cascade-invalidates all downstream stage manifests, workers start over
2. **Crash mid-write** — Process dies while writing `trace_augmented.jsonl`, leaving a truncated file
3. **Empty re-run** — Worker produces 0 results (LLM timeout, config error), overwrites a valid 22 MB file with a 0-byte file
4. **Embedding model switch** — Model change detected, entire embedding index rebuilt from scratch instead of incrementally extending

### Current Protection

The existing `pipeline_checkpoint.py` (Phase 25) creates file copies before destructive stages:
- ✅ Copies trace files to `.checkpoints/<run_id>/`
- ✅ Can verify JSONL integrity and auto-heal
- ❌ Only runs before specific stages, not every write
- ❌ Checkpoints are deleted after successful runs (no history)
- ❌ No size/count comparison — doesn't detect "valid but empty" overwrites
- ❌ Doesn't cover embeddings (144 MB NPY files)

## Data Volume Analysis

Real-world measurements from active projects:

| Project | Total .codrag | JSONL Data | Embeddings | Knowledge Docs |
|---------|---------------|------------|------------|----------------|
| CoDRAG (1143 files) | 6.0 GB | ~35 MB | 144 MB | 28 MB |
| DebateHaus (857 files) | 968 MB | ~28 MB | 126 MB | 29 MB |

**Key insight**: The JSONL pipeline data is only ~35 MB even for a large project. A full backup of just the JSONL files costs <50 MB. Embeddings are the expensive part (144 MB) but they're deterministic — they can be rebuilt from the JSONL data.

---

## Phase 60A: Integrity Guard + Decision Logging ✅ COMPLETE

### What was built

Two complementary systems that together provide full pipeline diagnostic coverage:

#### 1. IntegrityGuard (`pipeline_integrity.py`)

Non-blocking pre/post-flight data comparison for every pipeline stage.

```
PRE-FLIGHT (before stage runs):
  Snapshot: trace_augmented.jsonl → 47,851 records, 22 MB

POST-FLIGHT (after stage completes):
  Compare:  trace_augmented.jsonl → 47,866 records, 22.1 MB
  Verdict:  OK (GREW by +15 records)
```

**Severity levels:**
| Level | Threshold | Meaning |
|-------|-----------|---------|
| `critical` | New data <10% of existing | Catastrophic data loss |
| `warning` | New data <50% of existing | Suspicious shrinkage |
| `grew` | New data >200% of existing | Possible full rebuild when incremental expected |
| `ok` | Normal | Healthy increment or unchanged |
| `first_run` | File didn't exist before | Initial creation |

#### 2. Decision-Point Logging (orchestrator + watch.py + pipeline_logger.py)

Every pipeline decision is now logged as a structured `decision` event:

| Decision Type | What it captures |
|---------------|------------------|
| `trigger_source` | WHO triggered the run: `watcher_file_change`, `coverage_check`, `manual` |
| `mode_selection` | WHAT mode was chosen: `incremental`, `resume`, `initial_full_run`, `force_from_start`, `skip_up_to_date` |
| `resume_point` | WHERE to start: per-stage audit showing `COMPLETE`, `STALE_MTIME`, `MISSING_MANIFEST`, `CRASH_RECOVERY` |
| `coverage_gap` | WHY a rebuild was triggered: stale count, untraced count, coverage percentage |

#### Example log output (what you'll see in `.codrag/logs/pipeline_*.log`):

```json
{"ts":"...","event":"decision","data":{"decision_type":"trigger_source","choice":"watcher_file_change","changed_paths_count":2}}
{"ts":"...","event":"decision","data":{"decision_type":"resume_point","choice":"all_complete","per_stage":[{"stage":"structural","decision":"COMPLETE"},...]}}
{"ts":"...","event":"decision","data":{"decision_type":"coverage_gap","choice":"checked","needs_rebuild":true,"stale":3,"untraced":1}}
{"ts":"...","event":"decision","data":{"decision_type":"mode_selection","choice":"incremental","reason":"All stages complete, 3 stale + 1 untraced files"}}
```

### Files created/modified

| File | Status | Description |
|------|--------|-------------|
| `src/codrag/services/pipeline_integrity.py` | **NEW** | IntegrityGuard, FileSnapshot, StageSnapshot, IntegrityVerdict |
| `src/codrag/services/pipeline_logger.py` | **MODIFIED** | Added `decision()` event type |
| `src/codrag/services/pipeline/orchestrator.py` | **MODIFIED** | Pre/post-flight hooks + decision logging at all decision points |
| `src/codrag/api/routers/projects/watch.py` | **MODIFIED** | Trigger-source logging |

---

## Roadmap: Future Phases

### Phase 60B: Snapshot Ledger

**Goal**: Keep a backup of each pipeline data file before overwrite, enabling quick assessment and rollback.

**Design**: Most recent backup is kept **uncompressed** for fast assessment and diffing. Older backups (if retained) are gzip-compressed to save space.

```
.codrag/
├── trace_augmented.jsonl              ← live data (22 MB)
├── .snapshots/
│   ├── trace_augmented.jsonl.bak      ← most recent backup (uncompressed, 22 MB)
│   └── trace_augmented.jsonl.2.gz     ← previous backup (compressed, ~3 MB)
```

Free tier: 1 uncompressed backup per file (~35 MB total).
Pro+: configurable 1–10 backups (most recent uncompressed, rest gzip'd).

### Phase 60C: Pipeline Diff & Rollback UI

Simple API + minimal UI for comparing live data against the backup and restoring if needed.

```
GET  /projects/{id}/snapshots              → list backups
POST /projects/{id}/snapshots/{file}/rollback → restore from backup
```

---

## Relationship to Existing Systems

### vs. pipeline_checkpoint.py (Phase 25)

Phase 25 = **crash recovery** (copies before, restores on crash, deletes after success).
Phase 60 = **data integrity** (compares before/after, keeps history, enables rollback).

They complement each other.

### vs. Pipeline Manifests (Phase 49)

Manifests track *metadata* (model used, timing, quality).
Phase 60 tracks *data content* (record counts, file sizes, deltas).

Together they provide full provenance.

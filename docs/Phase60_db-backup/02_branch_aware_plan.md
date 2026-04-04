# Phase 60B: Branch-Aware Backup & Recovery System

> **Status**: ✅ Implemented (Backend Core)

## Problem Statement

When a user switches Git branches in an active CoDRAG project, the filesystem
changes trigger the pipeline's self-healing layer (Phase 61) to detect a massive
coverage gap. The pipeline treats this as "stale" data and overwrites the entire
`.codrag/` pipeline state to align with the new branch. If the user later returns
to their original branch, **hours of expensive LLM reasoning are permanently lost**.

## Solution: Automatic Branch-Aware Snapshots

The system detects Git branch transitions at pipeline startup and automatically:

1. **Snapshots the current state** for the *departing* branch
2. **Restores from a snapshot** if one exists for the *arriving* branch
3. **Prunes old snapshots** based on a per-project limit (default: 3)

All of this happens transparently — no user action required.

## Architecture

### Storage Layout

```
.codrag/
├── trace_nodes.jsonl                   ← live data
├── trace_augmented.jsonl               ← live data
├── ...
└── .branch_snapshots/
    ├── _branch_state.json              ← tracks last-known branch
    ├── main/
    │   ├── trace_nodes.jsonl           ← branch snapshot
    │   ├── trace_augmented.jsonl
    │   ├── trace_epistemic.jsonl
    │   ├── trace_manifest.json
    │   ├── ...manifests...
    │   └── _snapshot_meta.json         ← snapshot metadata
    └── feature--branch-name/
        ├── trace_nodes.jsonl
        └── ...
```

### What Gets Snapshotted

Only **JSONL trace data + JSON manifests** are snapshotted (~35 MB for a large
1000+ file project). **Embeddings (NPY files, ~144 MB) are excluded** — they are
deterministic and can be cheaply regenerated from JSONL data by the Knowledge
embedding stage.

| File Type | Size | Snapshotted? | Reason |
|-----------|------|:---:|--------|
| `trace_*.jsonl` | ~35 MB | ✅ | LLM reasoning output — irreplaceable |
| `*_manifest.json` | ~1 MB | ✅ | Provenance & freshness tracking |
| `pipeline_run_metadata.json` | ~2 KB | ✅ | Run state for crash recovery |
| `atlas_output.json` | ~1 MB | ✅ | Atlas reasoning output |
| `*.npy` (embeddings) | ~144 MB | ❌ | Deterministic, rebuilt from JSONL |
| `logs/` | Variable | ❌ | Diagnostic only, not pipeline state |

### Backup Limit

Each project has a configurable `max_branch_backups` setting (default: **3**).
No tier-based restrictions — all users get the same capability. When the limit
is exceeded, the oldest snapshot is pruned.

## Implementation

### Files

| File | Status | Description |
|------|--------|-------------|
| `src/codrag/services/branch_backup_manager.py` | **NEW** | Core backup manager with git detection, snapshot/restore/prune |
| `src/codrag/services/pipeline/orchestrator.py` | **MODIFIED** | Branch check hook in `_start_group()`, branch info in `status()` |
| `docs/Phase60_db-backup/02_branch_aware_plan.md` | **NEW** | This document |

### Key Functions

```python
# Detect current git branch (handles detached HEAD, worktrees)
detect_current_branch(project_path) → Optional[str]

# Full transition check — snapshot old branch, restore new, prune
check_branch_transition(project_path, index_dir, max_backups=3) → Optional[Dict]

# Manual operations
snapshot_project(index_dir, branch_name) → Dict
restore_project(index_dir, branch_name) → Optional[Dict]
list_snapshots(index_dir) → List[Dict]
prune_backups(index_dir, max_backups=3) → List[str]
delete_snapshot(index_dir, branch_name) → bool
```

### Pipeline Integration

The branch check runs in `_start_group()` — the method called when a pipeline
group (fast_sync or deep_enrichment) begins execution. It runs **only for
fast_sync** to avoid double-snapshotting when `run_all()` chains groups.

```
Pipeline Startup
  └── _start_group(fast_sync)
       ├── State Machine: IDLE → RUNNING
       ├── Journal + Metadata
       ├── Phase 50: Rules regeneration
       ├── ★ Phase 60B: Branch transition check ★  ← NEW
       │    ├── detect_current_branch()
       │    ├── Compare with last-known branch
       │    ├── If changed: snapshot old → restore new → prune
       │    └── Log selfheal("branch_transition", ...)
       └── _advance_pipeline() → Stage 1
```

### Pipeline Status API

The `status()` method now returns branch info:

```json
{
  "fast_sync": { ... },
  "deep_enrichment": { ... },
  "branch": "main",
  "branch_snapshots": [
    {
      "branch": "feature/x",
      "created_at": "2026-04-03T...",
      "size_bytes": 35000000,
      "file_count": 12
    }
  ],
  "branch_state": {
    "branch": "main",
    "switched_at": "2026-04-03T...",
    "transition_from": "feature/x"
  }
}
```

## Relationship to Other Phases

| Phase | Relationship |
|-------|-------------|
| **Phase 60A** (Integrity Guard) | Complementary — integrity guard monitors *within* a branch; branch backup manages *across* branches |
| **Phase 61** (Self-Heal) | Branch transitions are logged as `selfheal("branch_transition", ...)` events |
| **Phase 70** (Dashboard State Machine) | Branch info exposed via pipeline status for future UI rendering |
| **Phase 25** (Crash Recovery) | Branch snapshots survive crashes — snapshot metadata persists on disk |

## Future Enhancements

- [ ] **Dashboard UI**: Show branch badge in pipeline panel header
- [ ] **Manual Snapshot/Restore**: Allow users to manually create/restore from the dashboard
- [ ] **Diff View**: Compare current state against branch snapshot to see what changed
- [ ] **Compressed Older Snapshots**: Gzip older snapshots to save disk space

# Phase 72 — Research Guide for Next AI

> **Purpose**: This file tells the next AI exactly what to investigate before writing any refactoring code.  
> **Rule**: Complete ALL research tasks in a section before starting the code changes for that section.  
> **Output**: For each research task, write your findings directly below the task checkbox in this file.

## Pre-Refactor Research (Do This First, Always)

### 1. Understand the Current Call Graph

The pipeline has a complex chain of dependencies. Before changing anything, map the exact call chain:

```
Watcher detects changes →
  pipeline_orchestrator.run_fast_sync(project_id) →
    _detect_resume_point(project_id, FAST_SYNC_STAGES) →
      reads manifests from disk
    _start_group(project_id, "fast_sync", stages, resume_from) →
      creates PipelineGroupStateMachine
      for each stage:
        WorkerFactory.create_worker(stage) → returns closure
        build_orchestrator.start(project_id, build_type, worker) → runs in thread
        worker completes → build_orchestrator fires completion event →
          PipelineOrchestrator._on_build_transition() →
            state_machine.transition(STAGE_COMPLETED) →
            _advance_pipeline(run) →
              next stage or ALL_STAGES_DONE
```

- [ ] **Research**: Trace the EXACT execution path from `run_fast_sync()` to the first worker starting. Note every lock acquisition, every file read, every thread spawn.
- [ ] **Research**: Trace the EXACT execution path from worker completion to the next worker starting. Note the callback chain through `_on_build_transition()` → `_advance_pipeline()`.
- [ ] **Research**: Identify ALL places where `self._lock` is acquired in `orchestrator.py`. For each one, note what other locks might be held concurrently.

### 2. Map the Full Manifest Ecosystem

There are TWO types of manifests that currently share the same namespace:

**Type A: Worker Hash Manifests** (per-file content hashes for incrementality)
```json
{
  "src/codrag/core/index.py": "sha256:abc123...",
  "src/codrag/api/server.py": "sha256:def456...",
  ...
}
```

**Type B: Orchestrator Provenance Manifests** (model info, timing, quality)
```json
{
  "format_version": "2.0",
  "stage_id": "inferred_edges",
  "started_at": "2026-04-03T...",
  "finished_at": "2026-04-03T...",
  "quality": { "total_items": 4139, "processed": 4139, ... },
  "model": { "name": "qwen3-coder-next:cloud", ... }
}
```

- [ ] **Research**: Run `grep -rn 'manifest' src/codrag/core/ src/codrag/services/pipeline/` and categorize every mention as Type A or Type B
- [ ] **Research**: For EACH stage, fill in this table:

| Stage | Provenance Manifest File | Worker Hash File | Output File | Who Writes Provenance | Who Writes Hash |
|-------|--------------------------|------------------|-------------|----------------------|-----------------|
| STRUCTURAL | trace_manifest.json | (none — Rust engine) | trace_nodes.jsonl | orchestrator | N/A |
| INFERRED_EDGES | trace_inferred_manifest.json | trace_inferred_hashes.json (✅ new) | trace_inferred_edges.jsonl | orchestrator | InferredEdgesAnalyzer |
| CATALOGUE | trace_augment_manifest.json | (none) | trace_augmented.jsonl | orchestrator | (reads JSONL directly) |
| VALIDATION | validation_manifest.json | (none) | (none) | orchestrator | N/A |
| KNOWLEDGE | knowledge_manifest.json | (none) | knowledge_documents.json | orchestrator | N/A |
| ENRICHMENT | trace_epistemic_manifest.json | (none) | trace_epistemic.jsonl | orchestrator | (reads JSONL directly) |
| GROUP_REASONING | group_reasoning_manifest.json | (none) | trace_group_reasoning.jsonl | orchestrator | (reads JSONL directly) |
| CLUSTERING | trace_modules_manifest.json | (none) | trace_modules.jsonl | orchestrator | (reads JSONL directly) |
| ATLAS | atlas_manifest.json | (none) | atlas.json | orchestrator | N/A |
| DEEPENING | deepening_manifest.json | (none) | trace_epistemic.jsonl | orchestrator | (reads JSONL directly) |
| DEEP_KNOWLEDGE | deep_knowledge_manifest.json | (none) | knowledge_documents.json | orchestrator | N/A |

- [ ] **Research**: Verify the above table is accurate by checking each worker's `run()` method for any manifest reads/writes
- [ ] **Research**: Check if `TraceAugmenter` has a hidden manifest — it may use `trace_augment_hashes.json` or similar
- [ ] **Research**: Does `EpistemicEnricher` have a hash cache file, or does it rely entirely on checking existing JSONL entries?

### 3. Understand the Status Data Flow

The dashboard polls GET `/pipeline/status` every 2-5 seconds. Trace exactly what data flows:

```
Dashboard polls → GET /pipeline/status →
  pipeline.py._build_status() →
    reads structural from build_manager
    reads augment from _project_augment_status()
    reads epistemic from disk (trace_epistemic.jsonl line count) ← Phase 60D-5 fix
    reads modules from disk (trace_modules.jsonl line count) ← Phase 60D-5 fix
    reads deepening from disk (trace_deepening_manifest.json) ← Phase 60D-5 fix
    calls pipeline_orchestrator.status(project_id) → acquires _lock → reads _runs dict
    calls pipeline_scheduler.status() → reads scheduler state
    returns massive JSON blob
```

- [ ] **Research**: Print the FULL JSON response from `curl localhost:8400/projects/{id}/pipeline/status` and document every field. This is the API contract the dashboard depends on.
- [ ] **Research**: Check which fields the dashboard reads. Search `packages/ui/src` for `pipeline/status` and trace the data consumption.
- [ ] **Research**: How often does the dashboard poll this endpoint? Is it configurable? See `useTraceSystem.ts` or `usePolling` hooks.
- [ ] **Research**: Does the dashboard also poll individual endpoints like `/epistemic/status` separately? Or only through `/pipeline/status`?

### 4. Understand the Lock Architecture

The orchestrator has a single `self._lock` (threading.Lock) that protects `self._runs`. But other components also have locks:

- [ ] **Research**: List ALL locks in the pipeline subsystem:
  - `PipelineOrchestrator._lock` — protects `_runs` dict
  - `PipelineGroupStateMachine._lock` — per-run state transitions
  - `BuildOrchestrator` — does it have a lock?
  - `pipeline_scheduler` — does it have a lock?
  - Any file-level locks (e.g., SQLite in-process locks)?

- [ ] **Research**: Can any combination of these locks deadlock? Draw the lock acquisition order for:
  1. Worker completing → `_on_build_transition()` → acquires orchestrator._lock → transitions state machine (acquires SM._lock)
  2. Status endpoint → `pipeline_orchestrator.status()` → acquires orchestrator._lock → iterates _runs (each SM has its own lock)
  3. What happens when both happen simultaneously?

### 5. Audit Exception Handling

The orchestrator has **90 try/except blocks** and **85 `except Exception`** catches. Many of these silently swallow errors.

- [ ] **Research**: Find all `except Exception: pass` patterns and categorize:
  - Truly non-fatal (e.g., Pi agent notification) → keep as is
  - Potentially masks bugs (e.g., manifest write failure) → add logging
  - Should be specific exceptions (e.g., `FileNotFoundError`) → narrow the catch

- [ ] **Research**: Are there any bare `except:` (no exception type at all)? These catch even `SystemExit` and `KeyboardInterrupt`.

---

## Stage 1 Research: ManifestStore Extraction

Before writing `manifest_store.py`, answer these:

- [ ] Read orchestrator.py lines 3627-3766 (`_write_stage_manifest_and_update_run`) and document:
  - What data is written?
  - What's the file format?
  - Is there any error handling for write failures?
  - Does it use atomic writes (tmp + rename)?

- [ ] Read orchestrator.py lines 2446-2466 (`_read_graph_stats_from_manifest`) and document:
  - What does it read?
  - What fallbacks exist?
  - Is it called from outside the orchestrator?

- [ ] Search for `manifest_path` and `manifest_file` across ALL Python files to find hidden callers:
  ```bash
  grep -rn 'manifest_path\|manifest_file\|_manifest\.json' src/codrag/ \
    --include='*.py' | grep -v '__pycache__'
  ```

- [ ] Check if the enrichment API endpoints (`enrichment.py`) read manifest files directly:
  ```bash
  grep -n 'manifest' src/codrag/api/routers/trace_routes/enrichment.py
  ```

- [ ] Determine if `PipelineRunMetadata` (line 82 of orchestrator.py) should live in ManifestStore or remain separate.

---

## Stage 2 Research: RecoveryManager Extraction

- [ ] Read `_auto_recover_stale_pipelines()` (lines 3338-3523) completely — it's 185 lines of complex logic. Document:
  - What heuristics does it use to detect "crashed" runs?
  - Does it work reliably? (Are there known false positives or false negatives?)
  - Does it touch the state machine?
  - What file system state does it inspect?

- [ ] Read `_try_restore_from_backup()` (lines 199-278) and document:
  - Where does it look for backups?
  - How does it decide which backup to use?
  - What files does it restore?
  - What happens if the backup is corrupted?

- [ ] Check if `_create_checkpoint_if_needed()` (lines 2797-2817) is actually called consistently or if some code paths skip it.

- [ ] Determine if recovery needs to hold `self._lock`. Currently several recovery methods acquire the orchestrator lock — is this truly necessary, or is it defensive?

---

## Stage 4 Research: State Machine as Status Source

This is the most impactful change. Research thoroughly:

- [ ] **Study `PipelineGroupStateMachine.to_dict()`** (state_machine.py lines 378-396) — this is what the API sees. What fields are missing compared to what `_build_status()` returns?

- [ ] **Bootstrap problem**: When the server starts, the state machine is IDLE, but disk has data from previous runs (e.g., 6,796 epistemic entries). How should the state machine learn about pre-existing data?
  - Option A: On startup, scan disk and populate `_stage_snapshots` with file-based stats
  - Option B: Always read disk for "exists/count" data, only use SM for "running/progress"
  - Option C: Use `ManifestStore` to provide both static (disk) and dynamic (SM) data

- [ ] **What does the dashboard do when `pipeline/status` returns `data: null` for enrichment stages?**
  - Does it show "Not Yet Run" (expected)?
  - Does it flash/reset the UI (bug)?
  - Test this by temporarily removing the epistemic data and watching the dashboard.

- [ ] **How does the state machine handle "stage completed in a previous run" vs "stage never ran"?**
  - Currently this is determined by file existence checks
  - The SM only knows about the CURRENT run's stages
  - For the API to return correct data, it needs BOTH current-run state AND historical completion

---

## Anti-Patterns to Watch For

The next AI should be careful to avoid these patterns that already caused bugs:

1. **DON'T share file paths between orchestrator and workers** — This is the #1 source of bugs. If both the orchestrator and the worker write to the same file, they will clobber each other.

2. **DON'T acquire locks during status reads** — The API endpoint polls every 2-5 seconds. Any lock acquisition in the status path creates a potential deadlock with LLM workers that hold locks for minutes.

3. **DON'T use mtime for semantic comparison** — File modification times are unreliable across filesystems, backup restores, and git operations. Use content hashes.

4. **DON'T swallow exceptions silently** — Every `except Exception: pass` hides a potential bug. At minimum, log at DEBUG level.

5. **DON'T make the orchestrator responsible for "knowing" what's on disk** — The orchestrator should delegate disk reads to ManifestStore and file existence checks to ResumeStrategy. It should only know about state machine events.

6. **DON'T inline business logic in `_on_build_transition()`** — This method is already 200+ lines. Post-flight actions should be registered as callbacks, not coded as inline blocks.

---

## How to Validate Each Stage

### After Stage 1 (ManifestStore):
```bash
# Verify all tests still pass
pytest tests/ -x -q

# Verify manifest files are still written correctly
python3 -c "
from codrag.services.pipeline.manifest_store import ManifestStore
from pathlib import Path
ms = ManifestStore(Path('.codrag'))
print('Provenance:', ms.provenance_exists('inferred_edges'))
print('Hashes:', ms.read_hashes('inferred_edges'))
"

# Verify orchestrator.py line count decreased
wc -l src/codrag/services/pipeline/orchestrator.py
# Expected: ~3,595 (was 3,895)
```

### After Stage 2 (RecoveryManager):
```bash
# Simulate crash: kill server mid-stage, restart, verify recovery
# (Manual test — can't be fully automated)

# Verify recovery detects the crashed run
curl localhost:8400/projects/{id}/pipeline/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Crashed runs:', d.get('crashed_runs', []))
"

# Verify orchestrator line count
wc -l src/codrag/services/pipeline/orchestrator.py
# Expected: ~2,995 (was 3,595)
```

### After Stage 4 (SM as Status Source):
```bash
# Stress test: start a heavy LLM stage, then rapidly poll status
for i in $(seq 1 50); do
  time curl -s --max-time 1 localhost:8400/projects/{id}/pipeline/status | wc -c
  sleep 0.1
done
# ALL 50 requests should return data within 100ms

# Verify no disk I/O in status path (use strace/dtrace)
# On macOS:
sudo dtrace -n 'syscall::open*:entry /execname == "python3"/ { printf("%s", copyinstr(arg0)); }' \
  -c 'curl localhost:8400/projects/{id}/pipeline/status' 2>&1 | grep manifest
# Expected: NO manifest file opens in the status path
```

---

## Key Files to Read (In Order)

If you're a new AI starting this refactor, read these files in this order:

1. **This file** (`Phase72_Pipeline-refactor/README.md`) — overall plan
2. **This research guide** — what to investigate
3. `src/codrag/services/pipeline/state_machine.py` (397 lines) — the foundation
4. `src/codrag/services/pipeline/stages.py` (212 lines) — stage metadata
5. `src/codrag/services/pipeline/workers.py` (795 lines) — worker factory
6. `src/codrag/services/pipeline/orchestrator.py` (3,895 lines) — the god class to decompose
7. `src/codrag/api/routers/pipeline.py` (596 lines) — API layer
8. `src/codrag/core/inferred_edges.py` (1,042 lines) — example of a fixed worker
9. `docs/Phase60_db-backup/60D_Pipeline_Incrementalism.md` — the band-aid fixes
10. `docs/Phase70_Dashboard-StateMachine/02_catastrophe-prevention-design.md` — dashboard state concerns

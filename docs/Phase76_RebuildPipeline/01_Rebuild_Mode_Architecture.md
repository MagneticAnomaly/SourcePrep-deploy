# Phase 76: Zero-Downtime Pipeline Rebuild Architecture

## 1. Problem Space and Objective

CoDRAG currently operates via two fundamental pipeline modes:
1. **Initial Full Sync:** Deletes the existing database (Trace Index) and computes the trace graph entirely from scratch. This guarantees absolute freshness but takes the CoDRAG database offline for the duration of the pipeline run (which can take hours for massive repositories). 
2. **Incremental Fast Sync:** Computes differences and relies on appending localized file changes. This keeps the DB entirely online, but over many mutations, the epistemic reasoning can become disjointed or drift.

**The Objective:** Establish a hybrid **"Rebuild Mode"**. It must compute each stage from scratch (like the initial sync) to cure data drift, but **it must not execute destructively against the live DB**. Instead, the pipeline should compute the new index files transparently in the background. Once an entire stage successfully completes, its specific output file is atomically swapped into the live index directory.

This achieves a completely seamless UI experience where the graph is technically rebuilding from scratch, but the user and API endpoints never experience a split-second of downtime.

---

## 2. Core Constraints

- **Minimal Blast Radius:** To prevent destabilizing millions of nodes or the core Rust/Python execution engines (`TraceBuilder`, `EpistemicEnricher`, `ClusterSynthesizer`, etc.), we will **not** inject complex file-swap or partial-write code directly into the massive core engine classes.
- **Componentized Isolation:** We will treat the problem at the lowest infrastructure layer—by manipulating the `index_dir` targeted by the workers.
- **Storage Profile:** During a rebuild, the storage footprint for the target stage is temporarily doubled (e.g., computing a 500MB `trace_nodes.rebuild.jsonl` beside the active 500MB `trace_nodes.jsonl`).

---

## 3. High-Level Architecture: The "Shadow DB" Pattern

Instead of passing the live `index_dir` to the `WorkerFactory` during a Rebuild request, the Orchestrator will seamlessly reroute pipeline instances into a **Shadow Index**.

### 3.1 The `RebuildManager` Service Component
We will introduce `src/codrag/services/pipeline/rebuild_manager.py`.

This component will be the authoritative subsystem for managing shadow environments. It provides isolated directory contexts for running workers safely decoupled from the active system state.

#### Key Behaviors:
- `create_shadow_context(live_idx_dir)`: 
  - Provisions a `.codrag/index/.rebuild-shadow` directory.
  - Because downstream pipeline stages require upstream inputs (e.g., `TraceAugmenter` needs to read `trace_nodes.jsonl`), this function manages creating hardlinks or read-only symlinks to existing live files within the shadow directory *for any stages that haven't been rebuilt yet*.
- `commit_stage(stage_output_filename)`:
  - Takes a successfully generated file from the shadow index (e.g., `trace_augmented.jsonl`).
  - Calls `os.replace` to overwrite the live index file exactly as the stage concludes safely.
  - Updates the respective `STAGE_MANIFEST_FILE`.
- `cleanup_shadow()`:
  - Obliterates the temporary staging folder on pipeline completion or fatal failure/cancellation.

---

## 4. Integration Specifications

### 4.1 Orchestrator Hooks (`src/codrag/services/pipeline/orchestrator.py`)
- We add `run_rebuild(self, project_id: str)`.
- It registers the project in `self._rebuild_runs`.
- It intentionally skips the standard `_detect_resume_point` check to ensure the starting stage is always `0`.
- Passes an execution context/flag into the workers indicating they are in Rebuild Mode.

### 4.2 Worker Factory Overlay (`src/codrag/services/pipeline/workers.py`)
The `WorkerFactory` currently resolves the index location with a single static command:
```python
idx_dir = project_index_dir(project)
```

In Rebuild Mode, this must be patched to route to the Shadow DB:
```python
if is_rebuild:
    from codrag.services.pipeline.rebuild_manager import rebuild_manager
    idx_dir = rebuild_manager.get_or_create_shadow_dir(project.id)
else:
    idx_dir = project_index_dir(project)
```
The exact same worker engines (`builder = TraceBuilder(...)`) execute unmodified. They execute blindly into `idx_dir`, unaware they are writing to a secure shadow boundary. 

At the end of the `worker()` wrap function (where timing, confidence arrays, and skips are calculated before return), the worker requests the `rebuild_manager` to finalize the specific stage.

**Example:**
```python
if is_rebuild:
    rebuild_manager.commit_stage(project.id, stage=StageId.CATALOGUE)
```

### 4.3 API & Dashboard Triggers
- **Backend:** `POST /projects/{project_id}/pipeline/rebuild` routes internally to `pipeline_orchestrator.run_rebuild()`.
- **Frontend Dashboard:** A dedicated "Zero-Downtime Rebuild" button is exposed in the Graph Management console.

---

## 5. Risk Assessment & Further Research Needed

Before finalizing line-of-code implementations, the following elements require precise testing metrics:

1. **Upstream Read/Write Symlink Integrity:**
   If a worker is executed inside `.rebuild-shadow` and attempts to read its input `trace_nodes.jsonl`, providing a standard OS symlink pointing to the live directory typically works for read modes. However, some JSONL incremental loops might attempt to `a+` or modify input files. We need to audit `TraceAugmenter`, `InferredEdgesAnalyzer`, and `ClusterSynthesizer` to ensure they treat their *input* documents as strictly Read-Only, and only modify their *output* documents.

2. **OS File-Locking Constraints:**
   During the `commit_stage`'s `os.replace(...)` execution, how does the underlying OS (macOS/Linux via Docker) behave if the API server or `codrag` agent commands are actively streaming a contextual read from `trace_nodes.jsonl`? Usually, Unix file descriptor references maintain integrity of active reads on overwritten inodes, but this must be rigorously validated to ensure we don't sever active AI Gateway MCP responses mid-flight.

3. **Manifest State Bleeding:**
   The UI utilizes `*_manifest.json` files to track progress bars and percentage gaps. If the Rebuild Mode takes two hours, the UI should ideally signal "Rebuild in Progress..." rather than freezing. We need to decide if we continuously merge the target percentage tracking from the Shadow DB into the Live DB *without* triggering premature stage skips.

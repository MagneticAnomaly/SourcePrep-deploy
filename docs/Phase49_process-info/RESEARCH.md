# Phase 49: Process Metadata & Data Provenance

## Research Findings: What We Currently Track

### 1. Pipeline Journal System (`pipeline_journal.py`)

**Purpose:** Crash-resilient SQLite-based run tracker

**Current Metadata Captured:**
- `run_id` — unique identifier for each pipeline run
- `project_id` — which project was processed
- `group` — "fast_sync" or "deep_enrichment"
- `status` — running | completed | failed | crashed | cancelled
- `stages` — ordered list of stage IDs
- `current_stage` — which stage is currently executing
- `current_stage_index` — numeric position in stage list
- `started_at` — Unix timestamp when run began
- `finished_at` — Unix timestamp when run ended
- `last_heartbeat` — Unix timestamp of last health check (updated every 10s)
- `error` — error message if failed
- `stage_results` — JSON dict mapping stage_id → "completed"|"failed"|"skipped"
- `checkpoint_path` — path to backup directory for crash recovery
- `chain_deep` — boolean flag for auto-chaining deep enrichment after fast sync

**What's Missing:**
- ❌ **No model information** — which LLM was used for each stage
- ❌ **No quality metrics** — confidence scores, parse success rates, etc.
- ❌ **No version tracking** — CoDRAG version, engine version, model versions
- ❌ **No per-stage timing** — only run-level start/finish timestamps
- ❌ **No input/output file hashes** — can't detect if data changed since last run
- ❌ **No concurrency info** — how many workers, which compute nodes
- ❌ **No batch profile** — which batching strategy was used (for BYOK)

### 2. Pipeline File Logger (`pipeline_logger.py`)

**Purpose:** Verbose structured JSON logs per run

**Current Metadata Captured:**
- Per-run log file: `<index_dir>/logs/pipeline_YYYYMMDD_HHMMSS.log`
- Structured JSON lines with:
  - `ts` — ISO timestamp
  - `elapsed` — seconds since run start
  - `event` — run_start | run_end | stage_start | stage_end | log | progress | llm_call | transition
  - `stage` — which stage (if applicable)
  - `data` — event-specific payload

**Event Types:**
- `run_start` — captures group, stages, project_id, log_file path
- `run_end` — captures result, error, elapsed_seconds
- `stage_start` — captures custom data dict
- `stage_end` — captures result, error, elapsed_seconds, custom data
- `log` — general message within a stage
- `progress` — current/total/detail for progress bars
- `llm_call` — node_id, success, elapsed_ms, model, error, confidence
- `transition` — build_type, old_phase, new_phase, detail

**What's Missing:**
- ❌ **Model info not consistently captured** — `llm_call` has model field, but not always populated
- ❌ **No aggregated metrics** — logs are verbose, no summary stats
- ❌ **No structured quality metrics** — confidence is logged per-call, but not aggregated
- ❌ **No file-level provenance** — which source files were processed, with what hashes
- ❌ **No embedding model info** — only LLM models tracked in llm_call events

### 3. Data Files (JSONL Overlays)

**Current Files:**
- `trace_nodes.jsonl` — structural graph (Rust engine output)
- `trace_edges.jsonl` — structural edges
- `trace_augmented.jsonl` — fast LLM augmentation (Pass 1)
- `trace_epistemic.jsonl` — deep enrichment (Pass 2+)
- `trace_modules.jsonl` — cluster synthesis
- `trace_inferred_edges.jsonl` — relationship validation
- `deepening_history.jsonl` — continuous deepening iterations
- `knowledge_documents.json` — knowledge index

**Metadata in Data Files:**

#### `trace_augmented.jsonl` (AugmentationEntry)
```python
{
    "node_id": str,
    "summary": str,
    "role": str,
    "confidence": float,
    "augmented_at": str,  # ISO timestamp
    "model": str,         # ✅ Model name captured
    "version": int,       # Format version (not CoDRAG version)
    "validated": bool,
    "validated_at": str,
    "validated_by": str,
    "file_hash": str,     # ✅ Source file hash for staleness detection
    "related_files": List[str],
    "doc_type": str,
    "doc_status": str
}
```

#### `trace_epistemic.jsonl` (EpistemicEntry)
```python
{
    "node_id": str,
    "extended_summary": str,
    "domain_tags": List[str],
    "architecture_layer": str,
    "subsystem": str,
    "design_patterns": List[str],
    "cross_references": List[str],
    "tech_debt": List[str],
    "staleness_risk": str,
    "epistemic_confidence": float,  # ✅ Quality metric
    "pass_number": int,             # ✅ Which enrichment pass
    "enriched_at": str,             # ✅ ISO timestamp
    "model": str,                   # ✅ Model name
    "doc_type": str,
    "doc_status": str,
    "decision_chains": List[str]
}
```

#### Manifest Files
- `trace_augment_manifest.json` — metadata about augmentation run
- `trace_epistemic_manifest.json` — metadata about epistemic run
- `trace_modules_manifest.json` — metadata about clustering run
- `trace_inferred_manifest.json` — metadata about validation run

**What's Good:**
- ✅ Per-entry timestamps (`augmented_at`, `enriched_at`)
- ✅ Per-entry model names
- ✅ File hashes for staleness detection
- ✅ Quality metrics (confidence, epistemic_confidence)
- ✅ Pass numbers for multi-pass enrichment

**What's Missing:**
- ❌ **No run-level aggregates** — can't easily answer "what was the average confidence for run X?"
- ❌ **No CoDRAG version** — if we change prompts/logic, can't tell which version produced the data
- ❌ **No embedding model** — knowledge index doesn't track which embedding model was used
- ❌ **No batch profile** — BYOK batching strategy not recorded
- ❌ **No compute node info** — which GPU/node processed which files

### 4. State Machine (`state_machine.py`)

**Current Metadata:**
- `PipelineGroupStateMachine` tracks:
  - `project_id`, `group`, `stages`
  - `state` — IDLE | QUEUED | RUNNING | PAUSING | PAUSED | CANCELLING | CANCELLED | COMPLETED | FAILED | RECOVERING
  - `current_stage_index`
  - `started_at`, `finished_at`
  - `error`
  - `stage_results` — dict of stage_id → result
  - `journal_run_id` — link to journal entry
  - `history` — list of `TransitionRecord` (timestamp, from_state, to_state, event, stage_index, detail)

**What's Good:**
- ✅ Full state transition history
- ✅ Per-transition timestamps
- ✅ Links to journal for persistence

**What's Missing:**
- ❌ **No model info in transition records**
- ❌ **No quality metrics in transition records**
- ❌ **History is bounded (max 100 entries)** — older transitions are lost

---

## Gap Analysis: What We Need to Track

### Critical Gaps (Must Have)

1. **Model Provenance Per Stage**
   - Which LLM model was used for each stage
   - Which embedding model was used for knowledge index
   - Model version/variant (e.g., "qwen3.5-27b-q8" vs "qwen3.5-27b-q4")
   - Provider (ollama, lm-studio, openai, etc.)
   - Endpoint ID (for multi-endpoint setups)

2. **CoDRAG Version Tracking**
   - CoDRAG version that produced the data
   - Rust engine version (if using Rust backend)
   - Prompt template versions (if we version prompts separately)

3. **Quality Metrics Aggregation**
   - Per-stage summary:
     - Total items processed
     - Success rate (parse success for LLM stages)
     - Average confidence score
     - Min/max confidence
     - Error count
   - Per-run summary:
     - Overall quality score
     - Staleness ratio (how much data is stale)
     - Coverage ratio (how much of the codebase was processed)

4. **File-Level Provenance**
   - Which source files were processed in each run
   - File hashes at time of processing
   - Which files were skipped (and why)
   - Which files failed processing (and why)

5. **Per-Stage Timing**
   - Start/end timestamps for each stage
   - Elapsed time per stage
   - Throughput metrics (files/second, items/second)

### Important Gaps (Should Have)

6. **Batch Processing Metadata**
   - Batch profile used (Large/Standard/Compact/Off)
   - Batch sizes per stage
   - Total API calls made
   - Total tokens consumed (if available from provider)

7. **Concurrency Metadata**
   - Number of concurrent workers
   - Compute node assignments (for multi-GPU setups)
   - Queue wait times (if queued)

8. **Input/Output File Metadata**
   - Input file sizes
   - Output file sizes
   - Compression ratios (for LOD)
   - File counts per stage

9. **Dependency Tracking**
   - Which stages depend on which previous stages
   - Which data files were read as input
   - Which data files were written as output

### Nice to Have

10. **Performance Metrics**
    - Peak memory usage
    - CPU/GPU utilization
    - Disk I/O stats
    - Network I/O (for cloud API calls)

11. **Error Details**
    - Stack traces for failures
    - Retry attempts
    - Fallback strategies used

12. **User Actions**
    - Manual pause/resume events
    - Manual cancellations
    - Configuration changes mid-run

---

## What We Already Get (Good News!)

### From Data Files
- ✅ Per-entry model names in `trace_augmented.jsonl` and `trace_epistemic.jsonl`
- ✅ Per-entry timestamps
- ✅ Per-entry confidence scores
- ✅ File hashes for staleness detection
- ✅ Pass numbers for multi-pass enrichment

### From Pipeline Journal
- ✅ Run-level start/end timestamps
- ✅ Run status (completed/failed/crashed)
- ✅ Stage-level results (completed/failed/skipped)
- ✅ Crash detection and recovery metadata

### From Pipeline File Logger
- ✅ Verbose per-event logs with timestamps
- ✅ LLM call-level metrics (success, elapsed_ms, confidence)
- ✅ Progress events

### From State Machine
- ✅ Full state transition history
- ✅ Per-transition timestamps

---

## What We Can Get (Low-Hanging Fruit)

### 1. From Existing Code (Just Need to Capture)

**Model Information:**
- `WorkerFactory._get_llm_client_for_task()` knows which model/endpoint is used
- `STAGE_TASK_ID` dict maps stages to task IDs
- LLM config has full model details (provider, endpoint, model name)
- Can capture at stage start and include in journal/manifest

**CoDRAG Version:**
- `codrag.__version__` is available
- Can capture once per run

**Embedding Model:**
- `NativeEmbedder` or `OllamaEmbedder` knows which model
- Can capture in knowledge index manifest

**Per-Stage Timing:**
- Pipeline file logger already captures `stage_start` and `stage_end` with timestamps
- Just need to aggregate into manifest

**Quality Metrics:**
- `trace_augmented.jsonl` has per-entry confidence
- `trace_epistemic.jsonl` has per-entry epistemic_confidence
- Can aggregate during stage completion

### 2. From Manifest Files (Already Partially There)

Current manifest files exist but are underutilized:
- `trace_augment_manifest.json`
- `trace_epistemic_manifest.json`
- `trace_modules_manifest.json`
- `trace_inferred_manifest.json`

We can enhance these to include:
- Model info
- CoDRAG version
- Timing stats
- Quality metrics
- File counts
- Success rates

### 3. From Pipeline Orchestrator (Easy to Add)

The orchestrator already has access to:
- Project ID
- Stage list
- Current stage
- Build orchestrator (for timing)
- LLM client factory (for model info)

Can easily capture:
- Which model was assigned to each stage
- Start/end timestamps per stage
- Success/failure per stage

---

## Proposed Solution Architecture

### 1. Enhanced Manifest Files (Primary Storage)

Each stage writes an enhanced manifest file with:

```json
{
  "format_version": "2.0",
  "stage_id": "catalogue",
  "run_id": "run-abc123",
  "project_id": "proj-xyz",
  
  // Provenance
  "codrag_version": "0.9.0",
  "engine_version": "0.1.0",
  "engine_backend": "rust",
  
  // Model Info
  "model": {
    "task_id": "fast_catalogue",
    "provider": "ollama",
    "endpoint_id": "local-ollama",
    "model_name": "qwen3:14b",
    "model_variant": "q8_0",
    "batch_profile": "off",
    "concurrency": 4
  },
  
  // Timing
  "started_at": "2026-03-11T23:45:00Z",
  "finished_at": "2026-03-11T23:47:30Z",
  "elapsed_seconds": 150.5,
  
  // Quality Metrics
  "quality": {
    "total_items": 247,
    "processed": 245,
    "skipped": 2,
    "failed": 0,
    "success_rate": 0.992,
    "avg_confidence": 0.87,
    "min_confidence": 0.45,
    "max_confidence": 0.98,
    "parse_errors": 0
  },
  
  // File Provenance
  "input_files": {
    "trace_nodes.jsonl": {
      "size_bytes": 1234567,
      "hash": "blake3:abc...",
      "item_count": 247
    }
  },
  "output_files": {
    "trace_augmented.jsonl": {
      "size_bytes": 2345678,
      "hash": "blake3:def...",
      "item_count": 245
    }
  },
  
  // Performance
  "throughput": {
    "items_per_second": 1.63,
    "bytes_per_second": 15630
  },
  
  // Errors (if any)
  "errors": [
    {
      "node_id": "file:src/broken.py",
      "error": "LLM parse failure",
      "detail": "Invalid JSON response"
    }
  ]
}
```

### 2. Run-Level Metadata (New File)

Create `<index_dir>/pipeline_run_metadata.json` for each run:

```json
{
  "run_id": "run-abc123",
  "project_id": "proj-xyz",
  "group": "fast_sync",
  
  // Provenance
  "codrag_version": "0.9.0",
  "engine_version": "0.1.0",
  "engine_backend": "rust",
  
  // Timing
  "started_at": "2026-03-11T23:45:00Z",
  "finished_at": "2026-03-11T23:52:00Z",
  "elapsed_seconds": 420.0,
  
  // Stages
  "stages": [
    {
      "stage_id": "structural",
      "started_at": "2026-03-11T23:45:00Z",
      "finished_at": "2026-03-11T23:45:30Z",
      "elapsed_seconds": 30.0,
      "status": "completed",
      "manifest_file": "trace_manifest.json"
    },
    {
      "stage_id": "catalogue",
      "started_at": "2026-03-11T23:45:30Z",
      "finished_at": "2026-03-11T23:47:30Z",
      "elapsed_seconds": 120.0,
      "status": "completed",
      "model": "qwen3:14b",
      "manifest_file": "trace_augment_manifest.json"
    }
    // ... more stages
  ],
  
  // Overall Quality
  "quality_summary": {
    "total_files_processed": 247,
    "avg_confidence": 0.85,
    "staleness_ratio": 0.12,
    "coverage_ratio": 0.98
  },
  
  // Models Used
  "models_used": {
    "fast_catalogue": {
      "provider": "ollama",
      "model": "qwen3:14b",
      "endpoint_id": "local-ollama"
    },
    "deep_reasoning": {
      "provider": "ollama",
      "model": "qwen3.5-27b",
      "endpoint_id": "local-ollama"
    },
    "embedding": {
      "provider": "native",
      "model": "nomic-embed-text-v1.5"
    }
  },
  
  // Configuration Snapshot
  "config_snapshot": {
    "batch_mode": "auto",
    "assignment_mode": "structured",
    "max_active_projects": 1
  }
}
```

### 3. Historical Run Registry (New SQLite Table)

Extend `codrag_settings.db` with a new table:

```sql
CREATE TABLE pipeline_run_history (
    run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    group_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    elapsed_seconds REAL,
    codrag_version TEXT,
    engine_backend TEXT,
    
    -- Aggregated quality metrics (JSON)
    quality_summary TEXT,
    
    -- Models used (JSON)
    models_used TEXT,
    
    -- Stage count
    total_stages INTEGER,
    completed_stages INTEGER,
    failed_stages INTEGER,
    
    -- File reference
    metadata_file TEXT,  -- path to pipeline_run_metadata.json
    
    created_at REAL NOT NULL
);

CREATE INDEX idx_run_history_project ON pipeline_run_history (project_id, started_at DESC);
CREATE INDEX idx_run_history_status ON pipeline_run_history (status);
```

This table provides:
- Fast queries for "last 10 runs"
- Fast queries for "all runs using model X"
- Fast queries for "runs with quality < 0.7"
- Links to full metadata files for details

### 4. Data Flow

```
Pipeline Run Starts
    ↓
Create run_id in pipeline_journal (existing)
    ↓
Create pipeline_run_metadata.json (new)
    ↓
For each stage:
    ↓
    Capture model info from LLM config
    ↓
    Run stage worker
    ↓
    Write enhanced manifest file (updated)
    ↓
    Update pipeline_run_metadata.json with stage info
    ↓
Pipeline Run Completes
    ↓
Aggregate quality metrics across all manifests
    ↓
Write final pipeline_run_metadata.json
    ↓
Insert row into pipeline_run_history table (new)
```

---

## Implementation Phases

### Phase 1: Enhance Manifest Files (Minimal Disruption)

**Goal:** Capture model info, timing, and basic quality metrics in existing manifest files

**Changes:**
1. Update `TraceAugmenter.run()` to write enhanced `trace_augment_manifest.json`
2. Update `EpistemicEnrichment.run()` to write enhanced `trace_epistemic_manifest.json`
3. Update `ClusterSynthesizer.run()` to write enhanced `trace_modules_manifest.json`
4. Update `InferredEdgeValidator.run()` to write enhanced `trace_inferred_manifest.json`

**New Fields in Each Manifest:**
- `codrag_version`
- `engine_version` (if using Rust)
- `model` object (provider, endpoint_id, model_name, batch_profile, concurrency)
- `started_at`, `finished_at`, `elapsed_seconds`
- `quality` object (total_items, processed, skipped, failed, success_rate, avg_confidence, etc.)
- `throughput` object (items_per_second)

**Effort:** ~2-3 hours per worker class

### Phase 2: Run-Level Metadata File (Orchestrator Integration)

**Goal:** Create `pipeline_run_metadata.json` with run-level aggregates

**Changes:**
1. Create `PipelineRunMetadata` dataclass
2. Update `PipelineOrchestrator._start_group()` to create metadata file
3. Update `PipelineOrchestrator._on_build_transition()` to update metadata file after each stage
4. Update `PipelineOrchestrator._advance_pipeline()` to finalize metadata file on completion

**Effort:** ~4-6 hours

### Phase 3: Historical Run Registry (SQLite Table)

**Goal:** Enable fast queries across all historical runs

**Changes:**
1. Add `pipeline_run_history` table to `codrag_settings.db`
2. Create `PipelineRunHistory` service class
3. Update orchestrator to insert row on run completion
4. Add API endpoints:
   - `GET /projects/{id}/pipeline/history` — list recent runs
   - `GET /projects/{id}/pipeline/runs/{run_id}` — get full metadata for a run
   - `GET /projects/{id}/pipeline/runs/{run_id}/manifest/{stage}` — get stage manifest

**Effort:** ~6-8 hours

### Phase 4: Frontend UI (Dashboard Panel)

**Goal:** Display process history and data provenance in the dashboard

**New Components:**
1. `ProcessHistoryPanel` — table of recent runs with quality scores
2. `RunDetailView` — detailed view of a single run with per-stage breakdown
3. `DataProvenanceView` — shows which models/versions produced current data

**Effort:** ~8-12 hours

### Phase 5: Data Purging (Future)

**Goal:** Allow users to purge "old" data based on age, quality, or model

**Features:**
- Identify data produced by specific models
- Identify data older than N months
- Identify data with quality below threshold
- Purge selected data and re-run pipeline

**Effort:** ~6-8 hours (deferred to future phase)

---

## Benefits

### For Users

1. **Trust & Transparency**
   - "This summary was generated by qwen3:14b on 2026-01-15"
   - "This data is 4 months old and may be stale"
   - "Average confidence: 0.87 (high quality)"

2. **Debugging**
   - "Why is this file's summary wrong?" → Check which model/version produced it
   - "Why did the pipeline fail?" → Check run history for error details
   - "Is my data up to date?" → Check last run timestamp and file hashes

3. **Quality Control**
   - See which runs had low confidence scores
   - Identify files that consistently fail processing
   - Track quality improvements over time

4. **Model Comparison**
   - Compare quality metrics across different models
   - See which model produces better results for your codebase
   - Justify upgrading to a larger model

### For Development

1. **Regression Testing**
   - Detect when code changes degrade quality
   - Compare metrics before/after prompt changes
   - Verify that new models improve results

2. **Performance Optimization**
   - Identify slow stages
   - Track throughput improvements
   - Optimize batch sizes based on historical data

3. **Support & Debugging**
   - Users can share run metadata for bug reports
   - Reproduce issues with exact model/version info
   - Identify patterns in failures

---

## Open Questions

1. **Storage Location**
   - Should `pipeline_run_metadata.json` be in the index dir or a separate `runs/` directory?
   - Should we keep all historical metadata files or just the latest N?

2. **Retention Policy**
   - How many historical runs should we keep in SQLite?
   - Should we auto-purge runs older than X months?

3. **Backward Compatibility**
   - How do we handle existing data files without provenance metadata?
   - Should we backfill metadata for old runs (if possible)?

4. **Performance Impact**
   - Will writing metadata files slow down the pipeline?
   - Should we write metadata async?

5. **UI Complexity**
   - How much detail should we show in the dashboard?
   - Should we have a separate "Data Provenance" panel or integrate into existing panels?

---

## Next Steps

1. ✅ Research current metadata tracking (DONE)
2. ✅ Identify gaps (DONE)
3. ✅ Design solution architecture (DONE)
4. ⏭️ Document the plan (THIS FILE)
5. ⏭️ Implement Phase 1 (Enhanced Manifest Files)
6. ⏭️ Implement Phase 2 (Run-Level Metadata)
7. ⏭️ Implement Phase 3 (Historical Run Registry)
8. ⏭️ Add API endpoints
9. ⏭️ Build frontend UI (Phase 4)

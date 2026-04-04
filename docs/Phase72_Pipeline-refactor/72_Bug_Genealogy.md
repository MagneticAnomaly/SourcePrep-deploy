# Phase 72 — Bug Genealogy & Current State Snapshot

> **Date**: 2026-04-03  
> **Purpose**: Capture the exact state of all known pipeline bugs, their root causes, and fix status so the next AI has full context.

## Bug Genealogy

Every pipeline bug we've encountered traces to one of three architectural root causes. Understanding this genealogy prevents wasting time on symptoms.

### Root Cause 1: Manifest Namespace Collision

**What**: The orchestrator writes provenance metadata (`{"format_version": "2.0", ...}`) to the same file that workers use for per-file content hashes (`{"src/foo.py": "sha256:abc..."}`). They clobber each other.

**Manifested as**:
- ❌ Edge Discovery re-analyzes ALL 4139 files from scratch every run (~43 min)
- ❌ `_load_manifest()` loads orchestrator metadata, finds no file paths, treats as empty

**Fix status**: ✅ FIXED in Phase 60D-4
- `InferredEdgesAnalyzer` now writes to `trace_inferred_hashes.json` (separate from `trace_inferred_manifest.json`)
- Migration logic rescues old hash data
- Guard in `_load_manifest()` rejects orchestrator metadata

**Remaining risk**: Only ONE worker (`InferredEdgesAnalyzer`) has this fix. Other workers (`TraceAugmenter`, `EpistemicEnricher`) don't use hash manifests at all — they check their JSONL output directly. If we ever add hash caching to those workers, the same collision pattern would recur unless we use ManifestStore.

---

### Root Cause 2: Status Endpoint Lock Contention

**What**: The `pipeline/status` API endpoint calls enrichment status functions, each of which independently calls `pipeline_orchestrator.status()`, which acquires `self._lock`. During heavy LLM work, the lock is held for minutes, causing the status endpoint to time out.

**Manifested as**:
- ❌ Dashboard shows "Waiting for enrichment" despite 6,796 epistemic entries existing on disk
- ❌ API returns empty body (curl times out with 0 bytes)
- ❌ Dashboard believes deep stages "forgot" their data and need to start over

**Fix status**: ✅ PARTIALLY FIXED in Phase 60D-5
- Replaced enrichment endpoint calls with inline file reads in `_build_status()`
- `pipeline_orchestrator.status()` now called only once (down from 5x)
- Dedicated thread pool (`_status_executor = ThreadPoolExecutor(4)`) for status endpoints

**Remaining risk**: The inline file reads still do disk I/O (line counting JSONL files). Under extreme I/O contention (e.g., large checkpoint writes), this could still slow down. The definitive fix is Stage 4 (state machine as status source).

---

### Root Cause 3: No Worker Checkpointing

**What**: Workers write their hash manifest and output data only at the very END of a run. If the server is killed mid-run (e.g., at 47%), all progress is lost.

**Manifested as**:
- ❌ Restarting server after Edge Discovery ran for 20 minutes → starts over from 0%
- ❌ `trace_inferred_hashes.json` doesn't exist because previous run never completed
- ❌ User has to wait ~43 minutes again for the same files

**Fix status**: ✅ FIXED for Edge Discovery in Phase 60D-6
- Added periodic checkpointing every 10 batches (~80 files)
- Both edges and hash manifest flushed to disk during the run
- On restart, picks up from last checkpoint

**Remaining risk**: Only `InferredEdgesAnalyzer` has checkpointing. `TraceAugmenter` (50,000+ nodes) and `EpistemicEnricher` (6,700+ nodes) have NO checkpointing. These are LLM-heavy stages that take 30-120 minutes — if killed mid-run, all progress is lost.

---

## Current Data on Disk

As of 2026-04-03T21:30 EDT:

```
File                           Records    Size     Status
trace_nodes.jsonl              51,072     19 MB    ✅ Complete
trace_edges.jsonl              64,985     27 MB    ✅ Complete
trace_augmented.jsonl          50,697     varies   ✅ Complete
trace_inferred_edges.jsonl     varies     6.9 MB   ⚠️  Partially complete (run was killed)
trace_epistemic.jsonl          6,796      8.4 MB   ✅ Complete
trace_modules.jsonl            602        673 KB   ✅ Complete
trace_group_reasoning.jsonl    16         53 KB    ✅ Complete
trace_inferred_hashes.json     —          MISSING  ❌ Never created (run killed before save)
```

**Implication**: The next Edge Discovery run will re-analyze all 4139 files because there's no hash manifest. After it completes (with the new checkpointing), subsequent runs will be incremental. This is a one-time cost.

## Orchestrator Complexity Metrics

```
Metric                              Value
Total lines                         3,895
Total methods                       74
try/except blocks                   90
except Exception catches            85
bare pass (swallowed exceptions)    7
time.sleep() calls                  4
Lock references (self._lock)        19
Distinct responsibilities           8+
Deepest nesting level               6-7
Longest method (_detect_resume)     226 lines
```

## Current Incrementality Matrix

| Worker | Has Hash Cache | Has Checkpointing | Incremental Strategy |
|--------|---------------|-------------------|---------------------|
| Rust structural engine | N/A | N/A | Always full scan |
| InferredEdgesAnalyzer | ✅ `trace_inferred_hashes.json` | ✅ Every 10 batches | Content hash comparison |
| TraceAugmenter | ❌ None | ❌ None | Reads JSONL, skips existing entries |
| EpistemicEnricher | ❌ None | ❌ None | Reads JSONL, skips existing entries |
| ClusterSynthesizer | ❌ None | ❌ None | Always full run |
| AtlasGenerator | ❌ None | ❌ None | Context-dependent regeneration |
| KnowledgeEmbedder | ❌ None | ❌ None | Checks embedded count vs total |

## API Endpoint Health

| Endpoint | Response Time (during LLM work) | Status |
|----------|--------------------------------|--------|
| GET /health | <10ms | ✅ Always fast |
| GET /trace/status | <3s | ✅ Independent thread pool |
| GET /pipeline/status | <500ms (with fix) | ⚠️ Fixed but still reads disk |
| GET /trace/coverage | <5s | ⚠️ Independent thread pool, but slow I/O |
| GET /epistemic/status | 🔴 Potentially blocked | ⚠️ Still calls pipeline_orchestrator.status() |
| GET /modules/status | 🔴 Potentially blocked | ⚠️ Still calls pipeline_orchestrator.status() |

## Phase 72 Additions: Recently Fixed Architectural Bugs

### Root Cause 4: Startup Hydration vs Auto-Recovery Priority Inversion

**What**: During startup, `_hydrate_paused_runs_from_disk()` blindly creates fake `PAUSED` state machines for any incomplete pipelines BEFORE the auto-recovery system gets a chance to evaluate the data. 

**Manifested as**:
- ❌ Dashboard permanently shows Atlas as "Paused" after a simple server restart.
- ❌ The user has to manually hit "Play" every single time the daemon boots.
- ❌ `_auto_recover_stale_pipelines()` observes the fake "Paused" state, thinks a human paused it, and bails out, entirely defeating the auto-resume system.

**Fix status**: ✅ FIXED in Phase 72
- When a group is configured in `AUTO` mode, we completely skip `_hydrate_paused_runs_from_disk` for that group.
- The `PAUSED` state is reserved for humans who explicitly pause; `_auto_recover_stale_pipelines()` cleanly auto-resumes orphaned pipelines.

---

### Root Cause 5: Backup Sabotage (Restoring Stale Checkpoints over Fresh Data)

**What**: The `_try_restore_from_backup()` logic blindly clobbered the current `trace_manifest.json` with an older checkpoint if the orchestrator decided it needed to run a structural rebuild (i.e., `incremental=False`), effectively wiping its own short-term memory of new files.

**Manifested as**:
- ❌ 209 untraced files are detected by the coverage gap logic.
- ❌ Orchestrator triggers a structural rebuild (`resume=0`, `incremental=False`) to add them to the graph.
- ❌ Backup logic sees `incremental=False`, thinks "we are empty! Let me restore from a checkpoint."
- ❌ An old `trace_manifest.json` is restored, overwriting the new file list. The 209 untraced files disappear from the orchestrator's radar forever.

**Fix status**: ✅ FIXED in Phase 72
- We now set `incremental=True` for untraced files because adding new files to existing valid structural data *is* an incremental operation. This completely bypasses the catastrophic backup restore path.

---

### Root Cause 6: The Infinite Iteration Loop (Reset on Completion)

**What**: When all deep enrichment stages finished successfully, `run_deep_enrichment()` assumed it should stay alive to "process incremental changes" before any existed. It forcibly reset `resume=0` and restarted from stage 1.

**Manifested as**:
- ❌ Deep enrichment ran continuously in an infinite 6-stage loop.
- ❌ Massive LLM token burning immediately after completion on clustering and atlas building.
- ❌ Redundant "structural rebuilds" being endlessly fired by fast sync.

**Fix status**: ✅ FIXED in Phase 72
- When stages are complete on disk, the orchestrator now legitimately returns `False` ("nothing to do"). Future changes enter legally via the `fast_sync` coverage gap detection loop instead of arbitrary restarts.

---

### Root Cause 7: Provenance Namespace/State Silos

**What**: The pipeline successfully runs and saves accurate data on disk, but the API endpoints looking up that data guess filenames or miss derived fields, rendering the UI blind to pipeline execution.

**Manifested as**:
- ❌ "Continuous Deepening" showed as "Not started" because the API hard-coded a check for `trace_deepening_manifest.json` instead of `deepening_manifest.json`.
- ❌ Missing derived UI fields (like `settled_ratio`) missing from the API caused the dashboard frontend reducer (`computeDeepeningState`) to silently fall backwards to `not_built`.

**Fix status**: ✅ FIXED in Phase 72
- Synchronized API endpoints to read actual filenames and correctly re-compute required dashboard telemetry (e.g. `settled_ratio = processed / total`).

---

### Root Cause 8: Cross-Domain UI Fallbacks (Irrelevant Progress Ratios)

**What**: Frontend components blindly apply generic fallback rendering data (e.g., project-level file metrics like `staleCounts`) across stages that operate on completely different abstract boundaries. In other words, file-level ratios are force-rendered on graph-level or epoch-level jobs.

**Manifested as**:
- ❌ The user looks at the `Continuous Deepening` UI and sees the text string explicitely saying `10%`, but the `<StageProgressBar>` component underneath renders a 99% solid green bar. 
- ❌ This occurs because the UI detects `staleCounts.stale > 0` and silently overrides the active epoch/iteration progress with a "fallback" ratio reflecting the percentage of non-stale files out of the whole project codebase.

**Fix status**: 📝 Needs Fix in Phase 72 (UI Refactor / Data Boundary Isolation)

---

### Root Cause 9: Orchestrator-Coupled Telemetry (Blind AI Gateway)

**What**: The `AI Gateway /llm/status` endpoints determine whether an LLM is active exclusively by checking if the `pipeline_orchestrator` asserts that the `fast_sync` or `deep_enrichment` groups are `is_active`. It checks pipeline status, not LLM socket traffic.

**Manifested as**:
- ❌ Paperclip agents, chat completions, ad-hoc rule regeneration, and internal reasoning sidecar operations happen invisibly.
- ❌ The AI Gateway dashboard and sidebar activity indicators show the system as completely "idle" and silent, even if an autonomous agent is slamming the local LLM at max capacity burning thousands of tokens.
- ❌ Telemetry is coupled to pipeline batches instead of actual `LLMClient` token throughput or task queue dispatch locks.

**Fix status**: 📝 Needs Fix in Phase 72 (Architectural decoupling of LLM telemetry from pipeline orchestrator constraints)

### Root Cause 10: Binary UI Building State (Mishandling Incremental Metrics)

**What**: Frontend components (like the `Graph Scope` trace coverage UI) detect a boolean `building` state and forcefully override their visual representation to a binary state. Rather than reflecting the true incremental status (completed vs. active), they collapse the entire graph into a monolithic "in-progress" status for the duration of the pipeline.

**Manifested as**:
- ❌ During an incremental pipeline run focused on 209 specific files out of 1,348 total, the Graph Scope UI drops the 1,139 successfully completed items to `0 traced & embedded` and claims all `1348 in-progress` (painting the bar solid blue).
- ❌ Additionally, the `stale` metric immediately drops to 0 in when the run begins, causing the two-tone rerun `<StageProgressBar>` to break since its fallback logic relies on `staleCounts`. It swaps dynamically from a rerun format to a standard indeterminate blue format, dropping all visibility into the incremental span.

**Fix status**: 📝 Needs Fix in Phase 72 (UI Refactor / Preserve incremental baselines throughout pipeline execution)

### Root Cause 11: Queue Processing Priority Inversion

**What**: When the pipeline is in an incomplete state (e.g., partial runs, crashed states, or skipped stages), the self-healing and queue processors prioritize gathering newly detected or stale items over simply finishing the existing, partially-processed pipeline graph. 

**Manifested as**:
- ❌ The system refuses to continue an incomplete Atlas or Deepening run, instead spinning up the 'Edge Discovery' or 'Fast Sync' loop to chase a handful of new/stale items.
- ❌ The user attempts to manually resume an incomplete pipeline, but the orchestrator spins or fails because it detects 2 stale files and tries to integrate them before making the entire pipeline "complete".
- ❌ Redundant "new/stale" queue processing occurs when the core objective should be to repair and finish what was started.

**Fix status**: 📝 Needs Fix in Phase 72 (Self-heal architecture must prioritize pipeline completion over new queue processing when state is incomplete)

---

## Phase 60D Fixes Applied (Already Deployed)

| Fix ID | Description | File | Lines Changed |
|--------|-------------|------|---------------|
| 60D-1 | Skip structural in incremental mode | orchestrator.py | ~50 |
| 60D-1 | Mtime cascade permanently disabled | orchestrator.py | ~30 |
| 60D-1 | Backup auto-recovery before full rebuild | orchestrator.py | ~80 |
| 60D-2 | API timeout 8s → 30s | client.ts | 1 |
| 60D-2 | Dashboard preserves trace state during timeouts | useTraceSystem.ts | ~10 |
| 60D-3 | Bypass freshness gate in incremental mode | orchestrator.py | ~20 |
| 60D-3 | Dedicated thread pool for status endpoints | pipeline.py, query.py | ~20 |
| 60D-4 | Manifest clobber fix (separate hash manifest) | inferred_edges.py | ~40 |
| 60D-4 | Old manifest migration + metadata guard | inferred_edges.py | ~25 |
| 60D-4 | Concurrency logging | inferred_edges.py | ~5 |
| 60D-5 | Inline status reads (eliminate lock cascade) | pipeline.py | ~80 |
| 60D-6 | Periodic checkpointing every 10 batches | inferred_edges.py | ~10 |

## Phase 72 Immediate Fixes Applied (Already Deployed)

| Fix ID | Description | File | Lines Changed |
|--------|-------------|------|---------------|
| 72-1 | Break infinite looping on deep_enrichment complete | orchestrator.py | ~5 |
| 72-2 | Post-touch freshness guard to prevent false staleness runs | orchestrator.py | ~10 |
| 72-3 | Skip PAUSED hydration for pipelines in AUTO mode | orchestrator.py | ~15 |
| 72-4 | Skip backup restore for untraced file integration (`incremental=True`) | orchestrator.py | ~5 |
| 72-5 | Fix deepening status filename bug and missing `settled_ratio` | pipeline.py | ~10 |

Total: 5 individual fixes across 2 files, ~45 lines changed.
All of these are defensive patches — they work, but they demonstrate why we **urgently** need the structural decomposition detailed in `README.md`.

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

Total: 12 individual fixes across 6 files, ~370 lines changed.
All of these are defensive patches — they work, but they don't address the structural decomposition needed in Phase 72.

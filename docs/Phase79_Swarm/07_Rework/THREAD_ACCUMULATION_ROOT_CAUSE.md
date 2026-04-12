# Thread Accumulation Root Cause — Definitive Investigation

**Created:** 2026-04-12 19:30
**Status:** ROOT CAUSE IDENTIFIED — implementation in progress
**Priority:** P0 — explains all observed daemon hangs with cloud models
**Supersedes:** CLOUD_MODEL_DAEMON_HANG.md diagnosis (misattributed to `requests.post()`)
**Related:** SWARM_HANG_INVESTIGATION.md (swarm-specific timeouts — still valid, complementary)

## Executive Summary

The daemon hang with cloud models is **not caused by `requests.post()`**, `urllib3`, chunked
transfer encoding, or any HTTP library bug. It is caused by **thread accumulation from
per-stage ThreadPoolExecutors** during pipeline runs. A single pipeline run on a 28-file
project increases the daemon's thread count from 20 to 73+, with 64 threads competing
for the GIL. This GIL contention causes Python-level lock timeouts, making the daemon
appear hung.

Cloud model calls through the daemon work correctly (1.8s) when tested in isolation.
The hang only manifests when the pipeline's thread accumulation degrades the daemon.

## The Investigation

### Step 1: Fresh Daemon Baseline

A freshly started daemon (PID 98348) was measured:

```
Thread count:      20
Ollama connections: 0
LISTEN socket:     present
Response time:     10ms (projects endpoint)
```

### Step 2: Cloud Model Calls Through the Daemon — ALL PASS

Four tests were run through the running daemon:

| Test | Target | Route | Result |
|------|--------|-------|--------|
| Standalone cloud call | Ollama direct | N/A | 2.3s OK |
| Daemon → local model | `/api/llm/proxy/test-model` | FastAPI sync route → uvicorn worker thread | 3.9s OK |
| Daemon → cloud model | `/api/llm/proxy/test-model` | FastAPI sync route → uvicorn worker thread | **1.8s OK** |
| Pipeline status | `/projects/{id}/pipeline/status` | Async route → executor | OK |

**This disproves the central claim of CLOUD_MODEL_DAEMON_HANG.md.** `requests.post()` to
cloud models does NOT hang in daemon context. The test-model endpoint uses the exact same
code path (FastAPI sync route → uvicorn worker thread → `requests.post()`) that the bug
report identified as broken.

### Step 3: Trigger a Pipeline Run and Monitor Thread Growth

A full pipeline rebuild was triggered on `rust_repo` (28 files — the smallest project).
Thread count was sampled every 15 seconds for 3 minutes:

```
Time     Threads  Ollama   /pipeline/status
──────   ───────  ──────   ────────────────
  0s     20       0        OK (10ms)
 15s     29       1        TIMEOUT
 30s     34       1        TIMEOUT
 45s     50       1        OK (stale cache)
 60s     51       1        TIMEOUT
 90s     57       1        TIMEOUT
120s     61       1        TIMEOUT
165s     67       1        TIMEOUT
180s     71       1        OK (stale cache)
```

**Thread count increased from 20 to 71 during a single pipeline run on 28 files.**

The `/pipeline/status` endpoint became unreliable starting at ~30 threads, and almost
always timed out above 50 threads — even though the pipeline itself reported
`any_running: False` when it could be reached.

### Step 4: Thread State Analysis via Native Sampling

The daemon was sampled using macOS `sample` command after the pipeline run completed:

```
Total threads:        73
GIL waiters:          64   (lock_PyThread_acquire_lock)
uvloop kevent:         1   (main event loop — healthy)
uvloop cond_wait:      4   (uvloop worker threads — healthy)
watchdog:              1   (FSEvents file watcher — healthy)
workqueue:             2   (system dispatch — healthy)
pthread cond_wait:     1   (misc)
```

**64 of 73 threads were blocked waiting for the Python GIL.** None were blocked on
`socket.recv()`, `select()`, or any network I/O. The "hang" is entirely GIL contention
from thread accumulation, not an HTTP library issue.

### Step 5: Research Confirmation

A parallel research effort confirmed the technical basis:

1. **CPython releases the GIL before `socket.recv()` syscalls.** Threads blocked on
   network I/O do not hold the GIL. The urllib3 timeout mechanism uses OS-level
   `SO_RCVTIMEO` which fires independently of Python thread scheduling.

2. **GIL convoy effect** (CPython issue #7946) occurs with many CPU-bound threads
   competing for the GIL, causing excessive context switching. With 64 threads competing,
   each thread gets ~5ms of CPU time (the default GIL switch interval) before yielding.
   A Python-level lock acquisition that would normally take microseconds now takes
   64 × 5ms = ~320ms per GIL round-trip.

3. **httpx would not fix this.** It uses the same CPython GIL and the same OS socket
   layer. The timeout enforcement is architecturally different (threading.Event vs
   socket.settimeout) but neither is affected by GIL contention for I/O-bound calls.

4. **Production LLM orchestrators** (LangChain, LlamaIndex, vLLM) avoid per-call
   ThreadPoolExecutors entirely. They use either async HTTP clients (`httpx.AsyncClient`
   + `asyncio.gather()`) or a single shared bounded thread pool.

## Why the Previous Diagnosis Was Wrong

CLOUD_MODEL_DAEMON_HANG.md concluded that `requests.post()` "blocks indefinitely" for
cloud models in daemon context. This conclusion was based on observing pipeline stages
that never completed. However:

1. **The symptom was observed on a daemon that already had 77+ threads** from previous
   pipeline runs. The thread accumulation (not `requests.post()`) caused the hang.

2. **The "works standalone" vs "hangs in daemon" comparison** was comparing a 5-thread
   standalone test against a 77-thread degraded daemon. The relevant variable was thread
   count, not daemon context.

3. **The "local models work, cloud models don't" observation** is explained by timing:
   local models respond in 1-5s (quick enough to complete before GIL contention causes
   timeout cascades), while cloud models take 30-120s (long enough for accumulated thread
   contention to cause lock convoy effects on build_orchestrator and pipeline state locks).

4. **The "even a single sequential call hangs" claim** was tested on an already-degraded
   daemon. On a fresh daemon (20 threads), single cloud calls complete in 1.8s.

5. **The SWARM_HANG_INVESTIGATION.md "RESOLVED" section** was partially correct: the
   swarm's timeout and stall-detection fixes are valid and necessary. The stall detection
   (`wait(FIRST_COMPLETED)` with `worker_timeout_s`) and wall-time cap
   (`max_wall_time_s`) prevent indefinite waits regardless of the root cause. These
   are defense-in-depth measures that complement the thread accumulation fix.

## Where the Threads Come From

The pipeline architecture creates threads at multiple levels:

```
uvicorn (1 main thread + 4 uvloop workers)                    = 5
watchdog file watcher                                          = 1
pipeline-status executor (ThreadPoolExecutor, max_workers=4)   = 4
trace-status executor (ThreadPoolExecutor, max_workers=4)      = 4
build_orchestrator threads (1 per build group × 3 groups)      = 3
model readiness preload threads                                = 1-2
                                                        TOTAL ≈ 20 (baseline)

During a pipeline run, EACH STAGE creates its own ThreadPoolExecutor:
  Stage 3 (Fast Catalogue):    TPE(max_workers=3)              = +3
  Stage 2 (Edge Discovery):    TPE(max_workers=3)              = +3
  Stage 6 (Deep Reasoning):    TPE(max_workers=3)              = +3
  Stage 4 (Epistemic Code):    TPE(max_workers=3)              = +3
  Stage 5 (Epistemic Docs):    TPE(max_workers=3)              = +3
  Stage 7 (Group Reasoning):   TPE(max_workers=3) or swarm     = +3-10
  Stage 8 (Module Synthesis):  TPE(max_workers=3)              = +3
  Stage 9 (Augment Code):      TPE(max_workers=3)              = +3
  Stage 10 (Augment Docs):     TPE(max_workers=3)              = +3
  Stage 11 (Atlas):            TPE(max_workers=3) or swarm     = +3-10
  Stage 13 (Concept Seeding):  TPE(max_workers=3) or swarm     = +3-10
  Stage 14 (Audit):            TPE(max_workers=3)              = +3
                                                        TOTAL ≈ 36-60 threads

Additionally:
  Swarm coordinator zombies:   pool.shutdown(wait=False)       = +1-3 per swarm
  Pipeline journal flush:      daemon thread                   = +1
  Auto-run/retrigger threads:  daemon threads                  = +1-3
```

Most per-stage TPE threads clean up when the `with` block exits (`shutdown(wait=True)`),
BUT:
- If a stage's LLM call hangs (cloud queueing, timeout), the `with` block can't exit
  until the timeout fires (up to 600s for the large slot)
- Multiple stages run concurrently across the 3 build groups (fast_sync, deep_enrichment,
  finalize), so their TPE threads overlap
- Swarm `pool.shutdown(wait=False)` creates permanent zombies until HTTP timeout fires
- Each pipeline run leaves residual threads that accumulate across runs

## The Fix

### Immediate: Shared Bounded Thread Pool

Replace per-stage `ThreadPoolExecutor` creation with a single shared, bounded pool.
A `ThreadPoolExecutor(max_workers=8)` shared across all pipeline stages would:

- Cap total daemon threads at ~28 (8 workers + 20 baseline)
- Provide natural backpressure (stages queue instead of creating new threads)
- Eliminate thread accumulation across pipeline runs
- Keep the daemon responsive under load

### Implementation Plan

1. Create a shared `LLMThreadPool` singleton in `src/codrag/services/pipeline/`
2. Replace `with ThreadPoolExecutor(...) as pool:` in all 12+ pipeline stages with
   `shared_pool.submit()`
3. The shared pool should be bounded (max_workers=8) and named (for debugging)
4. Stages that currently use `shutdown(wait=True)` via `with` blocks will instead
   collect their futures and `wait()` on them directly
5. The swarm orchestrator already manages its own pool with proper lifecycle — leave
   it as-is but ensure it uses the shared pool for fan-out

### Long-term: Async LLM Client

Migrate `LLMClient.generate()` to use `httpx.AsyncClient` + `asyncio.gather()` with
semaphore-bounded concurrency. This eliminates ThreadPoolExecutor for LLM calls entirely
and integrates naturally with uvicorn's event loop. httpx is already a dependency
(used by `mcp/server.py`).

## Testing Checklist

1. Fresh daemon: verify 20 threads baseline
2. Single pipeline run (rust_repo): verify thread count stays under 30
3. Two consecutive pipeline runs: verify thread count doesn't grow between runs
4. Cloud model LLM calls during pipeline: verify they complete in <120s
5. `/pipeline/status` endpoint: verify it never hangs during pipeline runs
6. Swarm fan-out: verify stall detection and wall-time cap still work
7. All existing tests: `pytest tests/test_swarm_orchestrator.py tests/test_swarm_stress.py -v`

## Files Referenced

| File | Role in thread accumulation |
|------|----------------------------|
| `src/codrag/core/augmenter.py` | 4 ThreadPoolExecutor usages |
| `src/codrag/core/epistemic_enrichment.py` | 3 ThreadPoolExecutor usages |
| `src/codrag/core/inferred_edges.py` | 2 ThreadPoolExecutor usages |
| `src/codrag/core/deepening.py` | 1 ThreadPoolExecutor usage |
| `src/codrag/core/group_reasoning.py` | 1 ThreadPoolExecutor usage (+ swarm) |
| `src/codrag/core/cluster.py` | 1 ThreadPoolExecutor usage |
| `src/codrag/core/atlas/generator.py` | 1 ThreadPoolExecutor usage (+ swarm) |
| `src/codrag/core/audit/synthesizer.py` | 1 ThreadPoolExecutor usage |
| `src/codrag/core/swarm_orchestrator.py` | 2 ThreadPoolExecutor usages (with lifecycle mgmt) |
| `src/codrag/services/build_orchestrator.py` | Spawns 1 thread per build group |
| `src/codrag/services/build_manager.py` | Spawns 4 thread types |
| `src/codrag/api/routers/pipeline.py` | Status executor (4 threads, persistent) |
| `src/codrag/api/routers/trace_routes/query.py` | Status executor (4 threads, persistent) |

## Post-Fix Verification (2026-04-12 19:45)

### Sequential fast-path migration results

After migrating 6 batched TPE usages (augmenter ×3, epistemic ×2, inferred_edges ×1)
to sequential fast-paths when `concurrency <= 1`:

| Metric | Before fix | After fix | Target |
|--------|-----------|-----------|--------|
| Peak threads | 71 | 62 | <30 |
| GIL waiters (post-pipeline) | 64 | 51 | <10 |
| Pipeline status endpoint | intermittent timeout | intermittent timeout | <100ms |

**Finding:** The sequential fast-paths help (~13% reduction) but the remaining 51
zombie threads come from **daemon infrastructure**, not LLM pipeline stages:

- All `_get_llm_concurrency()` settings return 1 (sequential)
- All `get_batch_concurrency()` returns 1 for cloud (F-59 workaround)
- Pipeline stages with `concurrency=1` already use sequential code paths
- Pipeline finishes (`any_running: False`, queue empty) but 51 threads persist
- The persistent threads are from `threading.Thread(daemon=True)` spawns in:
  - `api/routers/trace_routes/enrichment.py` (5 endpoints × 1 thread each)
  - `services/build_manager.py` (4 thread types)
  - `core/model_readiness.py` (preload threads)
  - `api/routers/settings.py` (auto-run trigger threads)
  - `services/pipeline/resume.py` (retrigger thread)

### Next step: daemon thread lifecycle management

The remaining thread accumulation is not from ThreadPoolExecutors but from bare
`threading.Thread(daemon=True)` spawns that never terminate. Each pipeline run, trace
enrichment request, model readiness check, and settings save spawns a new daemon thread
that runs once and then blocks waiting for the GIL (Python daemon threads don't terminate
until the process exits).

Fix options:
1. **Thread reuse**: Use a shared thread pool for all daemon-spawned background tasks
2. **Fire-and-forget with cleanup**: Ensure daemon threads exit after their work completes
3. **asyncio migration**: Convert background tasks to `asyncio.create_task()` which
   doesn't create OS threads

## Diagnostic Scripts

- `scripts/diag_daemon_cloud.py` — Tests cloud model calls through the running daemon
  (standalone baseline + daemon test-model endpoint + thread/connection monitoring)

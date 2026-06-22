# Phase 145 Finding — Daemon stalls and frontend locks up (10-minute gap with uvicorn stall and idle-release trigger)

**Status:** Open. Symptom captured from terminal logs. Root cause under investigation.
**Found:** 2026-06-17, during a developer dogfooding session (captured in bash terminal ProcessId 53781).
**Severity:** High. The frontend tab locks up / freezes, and the backend daemon halts processing of all asyncio events (including polled status endpoints) for an extended period, recovering only after an idle-release event fires.

---

## 1. Symptom

During an active session, the frontend is observed to lock up/freeze, and the daemon stops responding. The terminal log from the running daemon (ProcessID 53781) shows a massive 10-minute (600s) gap where absolutely no API requests (including the highly frequent `/system/pipeline-queue` poll) are handled or logged by uvicorn. 

Crucially, under-the-hood background OS threads continue ticking independently. Exactly 10 minutes (600s) after the last active request, the daemon's background idle-release timer thread (`prep-embedder-idle-release`) detects that the shared embedders have been idle, calls `close_shared_embedders()`, and logs:

```
INFO:prep.services.embedder_factory:Released 1 shared embedder(s)
INFO:prep.services.idle_release:Idle-release: dropped 1 embedder(s) after 600s of inactivity
```

*Immediately* after this background logging occurs, uvicorn unblocks and instantly resumes processing the queued / incoming HTTP requests:

```
INFO:     127.0.0.1:57282 - "GET /system/pipeline-queue HTTP/1.1" 200 OK
INFO:     127.0.0.1:57282 - "GET /system/pipeline-queue HTTP/1.1" 200
INFO:uvicorn.access:127.0.0.1:57282 - "GET /system/pipeline-queue HTTP/1.1" 200
```

## 2. Why this matters

The system becomes completely unresponsive during the stall:
1. **Developer / User Interruption:** Clicks do not register, and the dashboard appears dead.
2. **Asyncio Event Loop Starvation:** Any background async tasks or polling-driven routines are frozen during the blocking period.
3. **Recovery Coincidence:** The fact that the loop unblocks *exactly* when `close_shared_embedders()` is called by a background OS thread strongly hints at a lock contention or resource deadlock between the main asyncio thread and the native embedder/model runtime (CoreML / ONNX Runtime / HuggingFace session) which is only released when dropped.

## 3. Where to look (hypothesis list, unverified)

| # | Hypothesis | First place to instrument |
|---|---|---|
| **H1** | **Lock Contention (`_SHARED_EMBEDDERS_LOCK`):** The asyncio event loop thread is waiting on `_SHARED_EMBEDDERS_LOCK` or a similar lock while some other synchronous operation holds it. When the idle-release thread wakes up, it acquires the lock or modifies the cached embedders, breaking the deadlock or unblocking the waiting thread. | `src/prep/services/embedder_factory.py` lines 46 (`_SHARED_EMBEDDERS_LOCK`), 55, and 95. Monitor lock acquisition duration. |
| **H2** | **Native Model Execution Hang (ONNX / CoreML):** A synchronous model inference or model loading call hung in C++ native code on the main thread, blocking the event loop. When the idle-release background thread calls `close()` on the native embedder, the native cleanup code forcefully interrupts or terminates the hung execution, unblocking the main thread. | `src/prep/core/embedder.py` (specifically how `NativeEmbedder` wraps ONNX / CoreML sessions), and `close_shared_embedders()`. |
| **H3** | **Frontend-driven freeze (Browser Tab Backgrounding):** The browser tab was minimized / hidden by the OS, which paused JS execution. Since F-11 added `document.hidden` check to `SidebarPipelineQueue.tsx`, polling of `/system/pipeline-queue` paused on purpose. After 10 mins, the user brought the tab to focus, triggering an immediate poll, but in the meantime the embedder became genuinely idle and was released. *Note: This would explain the logs but doesn't explain if there was an actual lock-up prior to backgrounding.* | Verify if the browser tab was backgrounded or if there is any React infinite-render loop occurring under specific state rollups. |
| **H4** | **Synchronous Blocking DB / File I/O:** An disk I/O operation (e.g. journal writes or database transaction) is blocking the main thread without yielding control to the asyncio event loop. | Check sqlite/journal writes in `orchestrator.py` or `watcher.py` to ensure they are offloaded to a thread pool via `asyncio.to_thread`. |

## 4. Evidence / Repro to capture next

When a stall occurs or is suspected:
1. **Check Thread Dumps:** Run `kill -USR1 <daemon_pid>` (if a custom signal handler is configured) or use `py-spy dump --pid <daemon_pid>` to see exactly where the main thread and background threads are blocked.
2. **Monitor Browser Responsiveness:** Open Chrome DevTools performance tab and capture a trace to see if there is long task/main thread blockage in the browser or if the browser is simply waiting for a pending HTTP request.
3. **Instrument Embedder Lock:** Add logging to `embedder_factory.py` around the lock context manager to log any acquisition that takes longer than 100ms:
   ```python
   # Example instrumentation
   import time
   start_t = time.monotonic()
   with _SHARED_EMBEDDERS_LOCK:
       elapsed = time.monotonic() - start_t
       if elapsed > 0.1:
           logger.warning("Acquired _SHARED_EMBEDDERS_LOCK after %.3f seconds!", elapsed)
   ```

## 5. Design invariants this bug violates

1. **The main asyncio thread must never block.** All synchronous heavy work, I/O, and model invocations must be executed on a separate thread pool.
2. **Graceful degradation on network stall.** If a network request is pending, the frontend must not lock up; it should have a timeout on all fetch requests so it can reject and show a degraded connection state instead of hanging indefinitely.
3. **No background-lock starvation.** Background housekeeping tasks (like `idle_release`) must never starve or lock out the main thread.

## 6. Recommended path forward

1. **Instrument `SidebarPipelineQueue` Fetch Timeout:** Add an `AbortController` timeout (e.g. 5 seconds) to `fetch` calls in `SidebarPipelineQueue.tsx` and other polling hooks so they never hang indefinitely if the daemon stalls.
2. **Audit Locks in `embedder_factory.py`:** Examine if any main thread route calls `close_shared_embedders` or `create_embedder` in a way that blocks on a thread lock.
3. **Update Phase 145 README:** Catalog this symptom as `2m` to track it.

## 7. Preliminary Live Forensic Investigation (2026-06-17)

A live dogfooding session on project `Applifier` (`7cdea5e4-c94d-4612-be67-81597da3d6ec`) on path `/Volumes/Thunderbolt/AI/ApplicationBrowser` captured a real-time reproduction of this exact stall event.

### A. The Target Run & Active Heartbeat
The pipeline `fast_sync` run was started today at `12:48:15` UTC (`08:48:15` EDT). While in the stalled state, the running daemon continued to write heartbeats to `@/Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/pipeline_run_metadata.json` (e.g., `heartbeat_at: "2026-06-17T13:19:16.454106+00:00"`), indicating that the main scheduler's background management loop was still ticking, but the worker thread and FastAPI/uvicorn request processing were completely frozen.

### B. The Stall Log Timeline
Logs extracted from `@/Volumes/Thunderbolt/AI/ApplicationBrowser/.sourceprep/logs/pipeline_20260617_124815.log` reveal:
- **08:49:16 EDT**: `catalogue` stage completes. `validation` is skipped.
- **08:49:16 EDT**: `knowledge` (Knowledge Embedding) starts running with model `native:nomic-embed-text-v1.5`.
- **08:49:16 to 08:50:38 EDT**: The embedder processes input batches incrementally, logging every few seconds:
  ```
  2026-06-17 08:49:21 INFO  [prep.services.pipeline.workers] [Applifier/Knowledge Embedding] Embedding 96/1544 new (0 reused) (96/1544 — 6%)
  ...
  2026-06-17 08:50:33 INFO  [prep.services.pipeline.workers] [Applifier/Knowledge Embedding] Embedding 1472/1544 new (0 reused) (1472/1544 — 95%)
  2026-06-17 08:50:36 INFO  [prep.services.pipeline.workers] [Applifier/Knowledge Embedding] Embedding 1504/1544 new (0 reused) (1504/1544 — 97%)
  2026-06-17 08:50:38 INFO  [prep.services.pipeline.workers] [Applifier/Knowledge Embedding] Embedding 1536/1544 new (0 reused) (1536/1544 — 99%)
  ```
- **08:50:38 EDT (The Stall Point)**: The embedder stops logging immediately after reaching the 99% mark.
- **08:50:38 to 09:01:09 EDT (The 10m 31s silence)**: Event loop starvation. No API request logs, no progress logs.
- **09:01:09 EDT (The Release)**: Background `prep-embedder-idle-release` wakes up, acquires `_SHARED_EMBEDDERS_LOCK`, drops the native embedder (`Released 1 shared embedder(s)`), and instantly uvicorn unblocks.

### C. Deep Hypothesis Investigation

#### GIL Starvation in C++ Native Code (ONNX Runtime)
Since `_project_knowledge_build_worker` runs inside a background Python daemon thread, and `NativeEmbedder` generates embeddings via `onnxruntime` (`self._session.run`), the execution occurs inside compiled C++ code. Under certain circumstances (such as thread-pool collisions, CPU core affinity locks, or CoreML provider issues on macOS), ONNX Runtime's execution pool can dead-lock or hang. 

Normally, ONNX Runtime releases the Python GIL during `.run()`. However, if the native execution hangs on a path where the GIL was re-acquired or wasn't fully released, or if the deadlock blocks Python's thread-switching interpreter loop, the entire FastAPI process freezes. 

#### Destruction Recovery
When the background `idle_release` thread wakes up after 600 seconds of inactivity, it calls `close_shared_embedders()`. This function executes `self._session = None` in Python, which forces the invocation of the underlying C++ destructors. Tearing down the ONNX session forcefully deallocates the native execution state, collapsing the native deadlock and immediately releasing the GIL. The Python interpreter loop resumes, allowing uvicorn to instantly clear its backlog of requests.

---

**Linked code:**
- `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` — `/system/pipeline-queue` fetch and in-flight ref
- `src/prep/services/idle_release.py` — idle release timer thread loop
- `src/prep/services/embedder_factory.py` — embedder caching, locks, and `close_shared_embedders`

---

## 8. Mitigations applied (2026-06-17)

These changes do **not** fix the underlying CoreML hang. They address the two recommendations from §6 that are actionable without further repro, plus a latent correctness bug uncovered while reviewing the code paths.

### 8.1 Frontend resilience — 5s AbortController timeout on the polling fetch

**File:** `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`.

Before, `fetchQueue` did a raw `fetch()` with no timeout. When the daemon stalled, the `inFlightRef` guard stayed `true` forever, polls stopped silently, and the sidebar appeared frozen.

After, the fetch is wrapped in a 5-second `AbortController` timeout. If it aborts, the in-flight ref clears in the `finally` block, the UI keeps rendering last-known queue state, and the next 10s tick retries.

The server-side `/system/pipeline-queue` endpoint (`queue.py` F-62 fix) already enforces a 3s build timeout, so the 5s client-side timeout gives ~2s of network/scheduling margin before the client gives up.

### 8.2 Embedder idle-touch correctness — touch per inner ONNX call

**File:** `src/prep/core/embedder.py`.

Before, `NativeEmbedder._touch_idle()` was called once at the top of `embed_batch(...)`. A single outer `embed_batch` call dispatches multiple inner `_session.run(...)` calls via `_dispatch_token_budget` (one per token-bucket / token-budget slice). If the outer call ran longer than `PREP_EMBED_IDLE_RELEASE_SEC` (default 600s), the idle-release timer would fire mid-call and `close()` the live session out from under the worker — a real race on legitimate long runs, not just stuck ones.

After, the touch fires *inside* `_embed_token_batch` immediately after `self._session.run(...)` returns (and analogously inside `_embed_texts` for the legacy/single-text path). Each successful inner batch keeps `_last_embed_ts` current; a stuck call (which never returns) still has its timestamp go stale and trips the idle-release recovery path — that recovery is what unblocked the daemon in this incident.

**Note on the recovery path:** the live observation is that `close_shared_embedders()` running on the background timer thread DID collapse the hang and resume uvicorn. We're keeping that pathway intact — the fix above is careful to not refresh the timestamp during a hung call, so the 600s timer still fires.

### 8.3 Regression tests

**File:** `tests/test_phase139_pr2_batching.py::TestPhase145IdleTouchPlacement`.

Two cases pin the new behavior:
- `test_touch_idle_fires_per_inner_onnx_batch` — multi-bucket input → 3 inner `session.run` calls → 3 `_touch_idle` invocations.
- `test_touch_idle_refreshes_timestamp_per_inner_call` — proves the timestamp advances on each inner call (rather than only at entry).

Both fail against the pre-fix code (one touch per outer call) and pass against the fix.

### 8.4 Still open

- **H1 lock-instrumentation** (`embedder_factory.py`) was deferred — it's diagnostic, not a fix. Worth adding if the next stall doesn't reproduce in the same shape.
- **H2 CoreML hang root cause** — needs a py-spy dump captured during the next stall. The trailing 8-item batch at the end of the user's 1544-doc run is a strong shape-specific lead (last bucket likely had a different sequence length than the steady-state batches).
- **H4 synchronous blocking I/O on the asyncio loop** — not yet audited.

## 9. Suspected recurrence 2026-06-18 22:38 — RETRACTED 2026-06-18 23:38

**Original framing (kept for context):** I documented the 2026-06-18 22:38 screenshot as a §2m recurrence and proposed a new sub-symptom ("Loading project…" never resolves) plus reattribution of §2p/§2q to §2m.

**Retraction (2026-06-18 23:38):** Eric verified by browser refresh that the daemon was **running the entire time** at 22:38 — all queued work had completed under the hood. The symptom was a frontend hang (UI lost sync with a healthy backend), NOT a backend stall. §2m's original 2026-06-17 evidence (10-minute uvicorn gap in the terminal log) remains a genuine backend stall; this is a different bug.

**What survives from this section:**

- **H5 — polling layer has no fallback when the UI loses sync with the backend** (was originally "daemon-silence fallback"). Generalizes from "daemon went silent" to "polling missed the update, SSE dropped, tab was backgrounded, or any other desync cause." Still worth a UI defense-in-depth thread.
- **The "Loading project… never resolves" sub-symptom** is real, but its cause is frontend-only — the dashboard didn't refetch when polling stalled. Move it into its own §2x entry (related to §2r and §2l's UI-vs-reality drift family) rather than §2m.
- **The cross-panel inconsistency** (queue widget empty + AI Gateway showing `10× active`) is its own bug too — multiple panels reading different state stores with no reconciliation. Same shape as §2r.

**What's withdrawn:**

- The "§2p / §2q fold into §2m" reattribution. Both stand as independent bugs again.
- The "daemon freeze is the leading root cause for the 22:38 symptoms." It wasn't.
- The H5 framing tied to daemon silence specifically. H5 stays but reframed to UI-desync more broadly.

Lesson for future captures: a UI showing stale data + cross-panel inconsistency is NOT proof the daemon froze. The proof requires terminal-log evidence of a uvicorn gap (the original §2m 2026-06-17 capture). A browser refresh that recovers full state is proof the *frontend* hung; if the refresh shows queued work has progressed, the daemon was healthy.

**Suggested next captures for an actual §2m recurrence** (NOT the 22:38 hang):

- During the next stall: keep the dashboard open AND a terminal running `while true; do curl -s -m 2 http://localhost:8400/health && echo OK || echo SILENT; sleep 1; done`. The SILENT count gives a direct timeline of when the daemon stopped responding vs when the UI started misbehaving. **A daemon stall produces SILENT lines; a frontend hang produces only OK lines.**
- The "Loading project…" sub-symptom is folded out into its own §2x entry — it's a frontend-only bug, not a §2m sub-symptom. See README.

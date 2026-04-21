# Swarm Fan-Out Hang Investigation — Handoff Document

**Created:** 2026-04-12
**Context:** Phase 96 pipeline debugging session (F-59 series)
**Status:** BLOCKED — root cause identified to architectural level, needs rework

## The Problem

Swarm fan-out workers hang indefinitely inside the Prep daemon process. The workers connect to the Ollama cloud endpoint (`kimi-k2.5:cloud`) but `requests.post()` never returns. This blocks ALL swarm-capable pipeline stages (Group Reasoning, Concept Seeding, Atlas Building) from completing on large projects like Prep (1800+ files, 600+ modules, 150+ groups).

**Critical observation:** The exact same LLM calls work perfectly in standalone tests — even concurrent ones. 5 threads, all returning in 5-8 seconds. The hang is specific to calls made from within the running daemon process.

## What Has Been Tried (F-59 Parts 1-5)

### F-59 Part 1: Coordinator timeout zombie thread (FIXED, not the root cause)
- **File:** `src/prep/services/pipeline/swarm_orchestrator.py:183`
- **Problem:** `SwarmOrchestrator._llm_call_with_timeout` used `with ThreadPoolExecutor() as pool:` — the `__exit__` called `pool.shutdown(wait=True)`, blocking until the coordinator LLM call returned (11+ minutes for cloud models). During this wait, the zombie thread held a urllib3 connection pool slot.
- **Fix:** Explicit `pool = ThreadPoolExecutor(...)` + `pool.shutdown(wait=False)` on all exit paths.
- **Commit:** `6462edfb`

### F-59 Part 2: Connection pool exhaustion (FIXED, not sufficient)
- **File:** `src/prep/core/llm_client.py` — Session creation
- **Problem:** Default `pool_maxsize=10` in urllib3. With 10 workers + 1 zombie coordinator = 11 concurrent connections, the 11th blocks waiting for a pool slot.
- **Fix:** `requests.Session()` with `HTTPAdapter(pool_maxsize=20)`.
- **Commit:** `4d31c01a`

### F-59 Part 3: Thread-local Sessions (FIXED, not sufficient)
- **File:** `src/prep/core/llm_client.py:386-396`
- **Problem:** All threads shared one `requests.Session`, causing serialized access through urllib3's connection pool lock.
- **Fix:** `threading.local()` gives each thread its own Session with its own connection pool.
- **Commit:** `10d6ee62`
- **Current code:**
  ```python
  self._thread_local = _threading.local()
  
  @property
  def _session(self):
      s = getattr(self._thread_local, 'session', None)
      if s is None:
          s = _requests.Session()
          self._thread_local.session = s
      return s
  ```

### F-59 Part 4: `stream=False` in requests (FIXED, not sufficient)
- **File:** `src/prep/core/llm_client.py:678`
- **Problem:** `resp.iter_lines()` hung after the cloud model's response was fully received because the chunked transfer decoder waited for more chunks that never arrived.
- **Fix:** `self._session.post(url, json=payload, timeout=(30, self.timeout), stream=False)` — buffers the full response.
- **Commit:** `91626438`

### F-59 Part 5: `stream: false` in Ollama API payload (FIXED, necessary but not sufficient)
- **File:** `src/prep/core/llm_client.py:625`
- **Problem:** The Ollama payload still had `"stream": True`, telling Ollama to send NDJSON tokens. With `stream=False` on the requests side, each arriving token chunk reset the read timeout counter, so the 60s timeout never fired. Workers appeared hung for 20+ minutes.
- **Fix:** Changed payload to `"stream": False` — Ollama returns a single JSON object.
- **Commit:** `d8b04ae8`
- **Also fixed LM Studio path at line 1061.**

### Cloud concurrency cap (FIXED, helps but doesn't solve hang)
- **Files:** `src/prep/core/concept_seeder.py:260-272`, `src/prep/core/group_reasoning.py:458`
- **Problem:** Cloud endpoints (Ollama Cloud free tier) only process 1 request at a time. 10 concurrent workers = 9 queued requests, each waiting up to 10 minutes.
- **Fix:** Cap concurrency at 3 for cloud-proxied models. Also set coordinator timeout to 10s for cloud (vs 90s local).
- **Commits:** `0ee05575`, `e0086815`

## The Remaining Hang — What We Know

### Reproduction
1. Start daemon: `.venv/bin/python -m prep.cli serve --port 8400`
2. Trigger any swarm stage on Prep project (Group Reasoning, Concept Seeding)
3. Swarm coordinator times out at 10s (expected for cloud) → falls back to default assignments
4. Fan-out starts 3 workers → workers call `llm.generate()` → `requests.post()` blocks indefinitely
5. Workers never return — no "Worker done" log messages, no timeouts, no errors

### What Works (standalone, outside daemon)
```python
# This returns in 5-8 seconds, even with 5 concurrent threads
from prep.core.llm_client import LLMClient
import threading

def worker(i):
    llm = LLMClient(endpoint_url='http://localhost:11434', model='kimi-k2.5:cloud', provider='ollama', timeout=60)
    text, tokens = llm.generate(prompt='...', json_mode=True, num_predict=500, think=True)
    # Returns successfully

threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
for t in threads: t.start()
for t in threads: t.join()  # All return in ~8 seconds
```

### What Doesn't Work (inside daemon)
The same `llm.generate()` call, made from:
```
uvicorn event loop 
  → asyncio 
    → build_orchestrator threading.Thread (worker_fn) 
      → SwarmOrchestrator._fan_out ThreadPoolExecutor 
        → worker thread 
          → llm.generate() 
            → self._session.post(url, json=payload, stream=False)  # HANGS HERE
```

### Key Observations
- **Ollama is responsive:** `curl` to `localhost:11434` returns in <2 seconds during the hang
- **TCP connections are ESTABLISHED:** `lsof` shows 3-8 connections from daemon to Ollama port 11434
- **No errors/timeouts logged:** Workers don't throw exceptions — they simply never return
- **`Transfer-Encoding: chunked`** is used by Ollama even with `stream: false` in the payload — no `Content-Length` header
- **74 threads in daemon process:** Many from zombie thread pools (coordinator timeouts)
- **Thread-local Sessions confirmed working:** Each thread gets its own Session (verified in standalone tests)

### Hypotheses Not Yet Tested

1. **GIL + asyncio interaction:** The daemon runs uvicorn's asyncio event loop. Worker threads run synchronous `requests.post()` which holds the GIL during DNS resolution and SSL handshake. With 74 threads, GIL contention might cause the read timeout to never fire because the timeout thread can't acquire the GIL to check elapsed time.

2. **Nested ThreadPoolExecutor deadlock:** The call chain has TWO levels of ThreadPoolExecutor:
   - BuildOrchestrator's `threading.Thread` → runs the pipeline worker
   - SwarmOrchestrator's `ThreadPoolExecutor(max_workers=3)` → runs fan-out workers
   - If the outer Thread somehow blocks the inner ThreadPoolExecutor's thread creation or scheduling...

3. **urllib3 connection reuse issue:** Even with thread-local Sessions, if a zombie coordinator thread's Session gets garbage collected while a connection is in TIME_WAIT, the new Session might try to reuse that socket and get stuck.

4. **Ollama cloud chunked response parsing:** With `Transfer-Encoding: chunked`, `requests` reads chunk by chunk. If Ollama sends the response in a single chunk but doesn't immediately send the terminating zero-length chunk, `requests` blocks waiting for more chunks. The read timeout (60s or 600s depending on slot configuration) should eventually fire — unless the GIL issue prevents it.

5. **`requests` vs `httpx` behavioral difference:** The `requests` library uses `urllib3` which has known issues with chunked transfer encoding and timeouts in threaded environments. `httpx` uses a different HTTP stack that might handle this better.

## Recommended Rework Approaches

### Option A: Replace `requests` with `httpx` (async-native)
- `httpx` supports both sync and async modes
- Better timeout handling with `httpx.Timeout(connect=30, read=60, write=30, pool=30)`
- Built-in connection pooling that works correctly with threading
- Can use `httpx.AsyncClient` in async contexts and `httpx.Client` in sync contexts
- **Risk:** Large diff, many call sites to change

### Option B: Subprocess isolation for swarm workers
- Run swarm fan-out in a separate Python subprocess (not threads)
- Each subprocess has its own GIL, event loop, connection pool
- Communication via `multiprocessing.Queue` or pipes
- **Risk:** More complex IPC, harder to share state

### Option C: `asyncio.to_thread()` instead of ThreadPoolExecutor
- Use `asyncio.to_thread()` for the top-level worker dispatch
- Keeps the event loop aware of the background work
- Better integration with uvicorn's event loop
- **Risk:** Requires restructuring the SwarmOrchestrator to be async-aware

### Option D: Direct `socket` / `http.client` for LLM calls
- Bypass `requests` entirely for Ollama calls
- Use Python's built-in `http.client.HTTPConnection` with explicit timeouts
- Simpler timeout semantics — `settimeout()` on the socket level
- **Risk:** Lose retry/redirect/auth handling from requests

**Recommendation:** Start with Option A (httpx) — it's the most targeted fix with the least architectural disruption. If httpx also hangs, it proves the issue is at a deeper level (GIL/asyncio interaction) and Option B (subprocess) is needed.

## F-59 Rework: Root Cause Found and Fixed (2026-04-12)

**Status: RESOLVED — The hang was not a threading/requests bug.**

### Actual Root Cause

The "hang" was caused by **three compounding factors**, none of which are a bug in `requests` or `urllib3`:

1. **600s HTTP timeout on the large slot.** Group reasoning and concept seeding use the `large` LLM slot, which has `timeout=600.0` (10 minutes). Workers that hit a slow or unresponsive cloud endpoint sit silently for up to 10 minutes before timing out. With no per-worker timeout in `_fan_out`, the only timeout was the HTTP read timeout.

2. **Sequential cloud processing.** Ollama Cloud (free tier) processes 1 request at a time. With 3 concurrent workers, requests queue and process sequentially. Each `kimi-k2.5:cloud` call with `think=True` and `num_predict=8192` (effective 24576 tokens) takes 5-10 minutes. Three workers = 15-30 minutes of silence before any "Worker done" log appears.

3. **Zombie coordinator connections.** When the coordinator futures timeout fires (10s), `pool.shutdown(wait=False)` abandons the thread but its `requests.Session` holds an ESTABLISHED TCP connection to Ollama for up to 600s. This zombie occupies a cloud queue slot, further delaying workers.

**Combined effect:** 155 groups × sequential cloud processing × 600s timeouts = hours of apparent hang with zero progress logging.

### Diagnostic Evidence

A diagnostic script simulating exact daemon threading conditions (asyncio event loop + build thread + nested ThreadPoolExecutor) proved:
- **All workers return successfully** — no threading deadlock or requests/urllib3 bug
- **Cloud processes requests sequentially** for `think=True` workloads (27s, 53s, 101s for 3 workers with `num_predict=2048`)
- **Extrapolated real-world timing:** `num_predict=8192` (effective 24576) × 155 groups = 7-19 hours

### Fixes Applied

| Fix | File | What |
|-----|------|------|
| Per-worker timeout | `swarm_orchestrator.py` | `worker_timeout_s` (120s cloud, 300s local) — workers that exceed this are marked failed |
| Overall wall-time cap | `swarm_orchestrator.py` | `max_wall_time_s` (600s cloud, 1800s local) — fan-out returns partial results when exceeded |
| Zombie session cleanup | `swarm_orchestrator.py` + `llm_client.py` | `close_session()` on coordinator/synthesis timeout — kills zombie TCP connections |
| Caller-side timeouts | `group_reasoning.py`, `concept_seeder.py`, `atlas/generator.py` | All SwarmOrchestrator callers now pass `worker_timeout_s` and `max_wall_time_s` |
| Test fix | `test_swarm_orchestrator.py` | Fixed incorrect test that expected `None` on coordinator failure (fan-out runs with defaults) |

### What Was NOT Needed

- **httpx migration** — `requests` works correctly; the issue was timeout configuration, not HTTP library bugs
- **Subprocess isolation** — no GIL or asyncio interaction bug found
- **asyncio.to_thread()** — the threading model (Thread + ThreadPoolExecutor) works correctly

## Files to Modify (Historical)

| File | What | Why |
|------|------|-----|
| `src/prep/core/llm_client.py` | Replace `requests` with `httpx` | Core LLM HTTP client — all API calls flow through here |
| `src/prep/core/swarm_orchestrator.py` | Review ThreadPoolExecutor usage | Fan-out mechanism that creates the nested thread pools |
| `src/prep/core/group_reasoning.py` | Cloud concurrency cap (already done) | Uses SwarmOrchestrator for group analysis |
| `src/prep/core/concept_seeder.py` | Cloud concurrency cap (already done) | Uses SwarmOrchestrator for concept extraction |
| `src/prep/core/cluster.py` | Check if swarm-capable | Module synthesis — may also hang |
| `src/prep/core/atlas/generator.py` | Check if swarm-capable | Atlas generation — may also hang |
| `pyproject.toml` | Add `httpx` dependency | If using Option A |

## LLM Client Architecture (Current)

```python
class LLMClient:
    def __init__(self, endpoint_url, model, provider, timeout=60):
        self._thread_local = threading.local()
    
    @property
    def _session(self):
        # Thread-local requests.Session
        s = getattr(self._thread_local, 'session', None)
        if s is None:
            s = requests.Session()
            self._thread_local.session = s
        return s
    
    def generate(self, prompt, ...) -> Tuple[str, int]:
        # Provider dispatch
        if self.provider == "ollama":
            payload = {"model": ..., "prompt": ..., "stream": False, ...}
            resp = self._session.post(url, json=payload, timeout=(30, self.timeout), stream=False)
            # Parse single-line JSON response
            for line in resp.text.splitlines():
                chunk = json.loads(line)
                # Extract response, thinking, done, token counts
        elif self.provider == "lm_studio":
            # Similar but different API format
        elif self.provider in ("openai", "anthropic", "google"):
            # SDK-based calls (not affected by this bug)
```

## Testing Checklist

When verifying a fix, test ALL of these:
1. `pytest tests/test_swarm_orchestrator.py -v` — unit tests
2. Standalone concurrent test (5 threads, `llm.generate()` with think=True, num_predict=500)
3. **In-daemon test on Prep:** Trigger finalize → concept seeding swarm (602 modules, 3 workers)
4. **In-daemon test on Prep:** Trigger deep enrichment → group reasoning swarm (155 groups, 3 workers)
5. **In-daemon test on mini-redis-rust:** Trigger finalize → concept seeding swarm (19 modules, 3 workers) — this is the smaller project that previously succeeded

## Context From This Session

- The daemon runs as `uvicorn prep.server:app` with a single worker
- The Thunderbolt3 drive (`/Volumes/4TB-BAD`) is NOT a USB drive — it runs at 3000MB/s
- SQLite stores use DELETE journal mode (not WAL) due to filesystem characteristics
- The cloud model `kimi-k2.5:cloud` is proxied through Ollama Cloud — responses go through Ollama's cloud relay infrastructure
- `qwen3-coder-next:cloud` is the Code Model (used for Edge Discovery, not swarm stages)
- The user has a perpetual dev license (not production)
- All 6 SQLite stores now use dedicated DB files (F-36/F-37/F-54/F-55) to avoid cross-store locking
- The F-57 stale-while-refresh cache on `/pipeline/status` has a 3s TTL and 10s executor timeout
- The F-62 async timeout on `/system/pipeline-queue` has a 3s timeout

## What NOT to Change

- Don't touch the `SwarmOrchestrator` three-phase architecture (coordinator → fan-out → synthesis) — it works correctly once workers actually return
- Don't remove cloud concurrency caps (3 for cloud, auto-detected for local)
- Don't remove coordinator/synthesis timeouts (10s/120s for cloud)
- Don't change `think=False` for coordinator/synthesis calls (F-29)
- Don't change `stream=False` in the Ollama payload — this is correct and necessary
- The thread-local Sessions pattern is correct and should be kept regardless of HTTP library choice

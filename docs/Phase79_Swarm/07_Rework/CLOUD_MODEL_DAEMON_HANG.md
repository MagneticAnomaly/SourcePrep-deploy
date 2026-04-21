# Cloud Model Daemon Thread Hang — Definitive Bug Report

**Created:** 2026-04-12 18:50
**Status:** OPEN — BLOCKING all cloud model LLM stages in the daemon
**Priority:** P0 — prevents pipeline completion on production config
**Supersedes:** The "RESOLVED" section in SWARM_HANG_INVESTIGATION.md (that diagnosis was incomplete)

## The Bug

**`requests.post()` blocks indefinitely when called from a daemon worker thread to any Ollama cloud-proxied model (`kimi-k2.5:cloud`, `qwen3-coder-next:cloud`).** The same call works perfectly in standalone Python scripts, even with identical threading (Thread + ThreadPoolExecutor).

This is NOT just a swarm issue — it affects ALL LLM-calling pipeline stages:
- Fast Catalogue (stage 3)
- Edge Discovery (stage 2) 
- Deep Reasoning (stage 6)
- Group Reasoning (stage 7)
- Module Synthesis (stage 8)
- Concept Seeding (stage 13)
- Atlas Building (stage 11)

**Local models (qwen3:8b, etc.) work fine in daemon threads.** Only cloud-proxied models hang.

## Reproduction

### Hangs (in daemon):
```
1. Start daemon: .venv/bin/python -m prep.cli serve --port 8400
2. Configure models to kimi-k2.5:cloud (default production config)
3. Trigger any pipeline stage that makes LLM calls
4. Worker thread calls llm.generate() → requests.post() → blocks forever
5. lsof shows 1 ESTABLISHED TCP connection to localhost:11434
6. Connection sits indefinitely — no data transfer, no timeout
```

### Works (standalone, same machine, same model):
```python
# Returns in 5-8 seconds, even with 5 concurrent threads
from prep.core.llm_client import LLMClient
import threading

llm = LLMClient(endpoint_url='http://localhost:11434', model='kimi-k2.5:cloud', 
                provider='ollama', timeout=60)
text, tokens = llm.generate(prompt='...', json_mode=True, num_predict=500, think=True)
# Returns successfully in 5-8 seconds
```

### Works (curl, same endpoint):
```bash
# Returns in 1-22 seconds depending on prompt size
curl -s http://localhost:11434/api/generate -d '{
  "model": "kimi-k2.5:cloud",
  "prompt": "...",
  "stream": false,
  "think": true,
  "options": {"num_predict": 4000}
}'
```

## Key Evidence

| Test | Model | Threading | Result |
|------|-------|-----------|--------|
| curl direct | kimi-k2.5:cloud | N/A | 1-22s ✅ |
| Standalone script (1 thread) | kimi-k2.5:cloud | main thread | 1-9s ✅ |
| Standalone script (5 threads) | kimi-k2.5:cloud | threading.Thread | 5-8s ✅ |
| Standalone script (ThreadPoolExecutor) | kimi-k2.5:cloud | TPE in Thread | 5-8s ✅ |
| Daemon worker (1 call, sequential) | kimi-k2.5:cloud | build_orchestrator Thread | **HANGS** ❌ |
| Daemon worker (3 concurrent) | kimi-k2.5:cloud | Thread → TPE | **HANGS** ❌ |
| Daemon worker (any call) | qwen3:8b (local) | same threading | ✅ Works |

## What's Different About the Daemon

The daemon runs under `uvicorn` with an asyncio event loop. The call chain is:
```
uvicorn asyncio event loop
  → FastAPI route handler (async)
    → build_orchestrator threading.Thread (worker_fn)
      → [optional: SwarmOrchestrator ThreadPoolExecutor]
        → LLMClient.generate()
          → self._session.post(url, json=payload, stream=False, timeout=(30, 600))
            → HANGS HERE
```

### Verified NOT the cause:
- **GIL contention** — standalone test with asyncio event loop + Thread + TPE works fine
- **Session sharing** — thread-local Sessions (F-59 part 3) didn't help
- **Connection pool** — pool_maxsize=20 (F-59 part 2) didn't help  
- **Stream mode** — `stream=False` in both requests and Ollama payload (F-59 parts 4+5) didn't help
- **Concurrency** — even with concurrency=1 (single sequential call), hangs
- **Timeout** — 600s read timeout should fire but never does
- **DNS resolution** — localhost resolves instantly in tests

### Still suspected:
- **Ollama chunked transfer encoding** — Ollama uses `Transfer-Encoding: chunked` even with `stream: false`. The `requests` library reads chunks until the zero-length terminator. If Ollama's cloud proxy doesn't send the terminator cleanly in a long-running daemon context, `requests` blocks forever.
- **uvicorn's anyio/asyncio thread pool** — uvicorn may configure the default thread pool in a way that affects `socket.recv()` behavior in spawned threads.
- **Keep-alive connection reuse** — the daemon's long-lived thread-local Session may reuse a connection that Ollama's cloud proxy has silently closed, causing a read on a dead socket.

## Recommended Fix Approach

### Option 1: `httpx` with explicit timeouts (RECOMMENDED)
Replace `requests` with `httpx` in `llm_client.py`. `httpx` has:
- Better timeout granularity (`httpx.Timeout(connect=30, read=60, write=30, pool=30)`)
- Native async support (can use `httpx.AsyncClient` in async contexts)
- Different HTTP/socket stack that may not have the chunked encoding issue
- Active maintenance and modern Python support

**Scope:** Change only `LLMClient` class — the rest of the codebase calls `llm.generate()` which is the abstraction boundary.

### Option 2: `subprocess` isolation for LLM calls
Run each `llm.generate()` call in a subprocess via `multiprocessing.Process`. The subprocess has its own GIL, event loop, and socket state. Communication via pipe.

**Scope:** Wrap `LLMClient.generate()` in a subprocess dispatcher. Higher latency per call (~100ms overhead) but guaranteed isolation.

### Option 3: Raw `http.client` with socket-level timeout
Replace `requests.post()` with Python's built-in `http.client.HTTPConnection` and set `socket.settimeout()` directly. This bypasses urllib3's chunked transfer handling.

**Scope:** Rewrite the Ollama HTTP call path only (lines 620-760 in llm_client.py).

## Files to Change

| File | Lines | What |
|------|-------|------|
| `src/prep/core/llm_client.py` | 356-760 | Replace `requests.Session.post()` with `httpx.Client.post()` |
| `src/prep/core/llm_client.py` | 386-396 | Replace thread-local `requests.Session` with thread-local `httpx.Client` |
| `src/prep/core/llm_client.py` | 1050-1120 | LM Studio path — same replacement |
| `pyproject.toml` | dependencies | Add `httpx>=0.27` |

## Testing Checklist

1. **Unit test:** `pytest tests/test_llm_client.py -v` (if exists)
2. **Standalone concurrent test:** 5 threads × `llm.generate()` with kimi-k2.5:cloud, think=True, num_predict=4000
3. **In-daemon test on rust_repo (28 files):**
   - Trigger rebuild → all 15 stages should complete
   - Watch for "starting stage" → "stage completed" for each stage
   - No stage should take >2 minutes on rust_repo
4. **In-daemon test on mini-redis-rust (19 modules):**
   - Trigger finalize → concept seeding should complete
   - Swarm fan-out with 3 workers should all return
5. **In-daemon test on Prep (1800+ files):**
   - Trigger deep enrichment → group reasoning should complete
   - 150+ groups processed sequentially or via swarm
6. **Verify local models still work:** Switch to qwen3:8b, run same tests

## What NOT to Change

- Don't touch SwarmOrchestrator architecture (coordinator → fan-out → synthesis)
- Don't remove cloud concurrency caps (3 for cloud models)
- Don't remove per-worker/wall-time timeouts in SwarmOrchestrator
- Don't change `think=False` for coordinator/synthesis calls
- Keep thread-local client pattern (each thread gets its own httpx.Client)
- Keep the `stream=false` in Ollama payload — it's correct

## Context From This Session

- The previous "RESOLVED" diagnosis in SWARM_HANG_INVESTIGATION.md tested with `num_predict=2048` — too small to trigger the hang. Real production calls use `num_predict=8192-24576` with `think=True`.
- The hang is NOT specific to concurrent/swarm calls — even a SINGLE sequential `requests.post()` hangs in a daemon thread.
- Local Ollama models (qwen3:8b, qwen3.5:27b, etc.) work fine — only cloud-proxied models hang.
- The `get_batch_concurrency()` workaround (returning 1 for cloud models) does NOT fix the hang — it just reduces concurrency from N to 1, but the single call still hangs.
- Ollama responds with `Transfer-Encoding: chunked` even when the payload has `"stream": false`.
- The daemon has 70+ threads from various ThreadPoolExecutors and zombie coordinator threads.
- Prep project must be deactivated (`active=False`) while this bug exists, otherwise its cloud model calls block the entire daemon's scheduler slots.

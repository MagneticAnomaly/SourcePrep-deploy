"""Shared bounded thread pool for pipeline LLM stages.

Replaces per-stage ThreadPoolExecutor creation to prevent thread
accumulation.  A single pipeline run on a 28-file project was observed
to grow the daemon from 20 to 73 threads, with 64 competing for the
GIL — causing lock convoy effects that made the daemon appear hung.

Usage (in pipeline stages):

    from codrag.services.pipeline.thread_pool import llm_pool

    # Submit work — same API as ThreadPoolExecutor
    futures = [llm_pool.submit(fn, arg) for arg in items]

    # Collect results — use concurrent.futures.wait or as_completed
    from concurrent.futures import wait, FIRST_COMPLETED
    done, pending = wait(futures, timeout=120, return_when=FIRST_COMPLETED)

The pool is bounded (default 6 workers) so at most 6 LLM calls run
concurrently across all stages.  Stages that submit work when the pool
is full will block until a worker becomes available — this is natural
backpressure that prevents thread explosion.

The pool is created lazily on first access and lives for the daemon's
lifetime.  It is NOT shut down between pipeline runs.
"""
from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Max concurrent LLM calls across all pipeline stages.  This caps the
# total thread count contribution from pipeline work at this number.
#
# Sizing rationale:
#   - Local models: GPU can handle 1 request at a time (model loaded
#     once).  Concurrency >1 just queues on the GPU.  But Ollama can
#     handle ~3 concurrent requests with parallel decoding.
#   - Cloud models: Free tier = 1 concurrent, Pro = 3, Max = 10.
#     Most users are on free/pro tier.
#   - System overhead: each thread holds a requests.Session with a TCP
#     connection to Ollama.  6 connections is lightweight.
#   - GIL: with 6 pool threads + ~14 daemon threads = ~20 total.
#     Well under the ~30 thread threshold where GIL contention starts
#     causing observable degradation on Python 3.11.
#
# Can be overridden via CODRAG_LLM_POOL_SIZE environment variable.
_DEFAULT_POOL_SIZE = 6

_pool: Optional[ThreadPoolExecutor] = None
_pool_lock = threading.Lock()


def _get_pool_size() -> int:
    """Read pool size from env or use default."""
    try:
        val = os.environ.get("CODRAG_LLM_POOL_SIZE")
        if val:
            n = int(val)
            if 1 <= n <= 32:
                return n
            logger.warning(
                "CODRAG_LLM_POOL_SIZE=%d out of range [1,32], using default %d",
                n, _DEFAULT_POOL_SIZE,
            )
    except (ValueError, TypeError):
        pass
    return _DEFAULT_POOL_SIZE


def _ensure_pool() -> ThreadPoolExecutor:
    """Lazily create the shared pool on first access."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        size = _get_pool_size()
        _pool = ThreadPoolExecutor(
            max_workers=size,
            thread_name_prefix="llm-pool",
        )
        logger.info("[LLM Pool] Created shared pool with %d workers", size)
        return _pool


class _LLMPoolProxy:
    """Proxy object that lazily initializes the shared ThreadPoolExecutor.

    Exposes ``submit()`` (same as ThreadPoolExecutor) so callers can
    use it as a drop-in replacement.  Also exposes ``max_workers`` for
    stages that need to know the concurrency limit.
    """

    @property
    def max_workers(self) -> int:
        return _ensure_pool()._max_workers

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """Submit a callable to the shared pool.

        Blocks if all workers are busy — this is intentional backpressure.
        """
        return _ensure_pool().submit(fn, *args, **kwargs)


def run_parallel(
    fn: Callable,
    items: list,
    *,
    concurrency: int = 0,
    cancel_token: Any = None,
    progress_fn: Optional[Callable[[int, int], None]] = None,
) -> list:
    """Submit ``fn(item)`` for each item using the shared pool.

    Drop-in replacement for the per-stage ThreadPoolExecutor pattern::

        # OLD (creates a new TPE per call):
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(fn, item): item for item in items}
            for future in as_completed(futures):
                results.append(future.result())

        # NEW (uses shared bounded pool):
        results = run_parallel(fn, items, concurrency=concurrency)

    If ``concurrency`` is 0 or > pool size, uses the full shared pool.
    If ``concurrency`` is 1, runs sequentially (no pool submission).

    Returns results in completion order (not submission order).
    Items whose ``fn`` raises are logged and skipped (not re-raised).
    """
    from concurrent.futures import as_completed as _as_completed

    if not items:
        return []

    # Sequential fast-path: avoids pool overhead when concurrency=1
    if concurrency == 1:
        results = []
        for i, item in enumerate(items):
            if cancel_token and getattr(cancel_token, 'is_cancelled', False):
                break
            try:
                results.append(fn(item))
            except Exception:
                logger.warning("run_parallel: item %d raised", i, exc_info=True)
            if progress_fn:
                progress_fn(i + 1, len(items))
        return results

    pool = _ensure_pool()
    # Limit in-flight submissions to min(concurrency, pool_size, len(items))
    effective = min(
        concurrency if concurrency > 0 else pool._max_workers,
        pool._max_workers,
        len(items),
    )

    # Submit in batches to provide backpressure when items >> effective
    # Without batching, all items queue immediately and the pool's internal
    # queue grows unbounded. With batching, we submit `effective` items at
    # a time and wait for one to complete before submitting the next.
    results = []
    futures_to_idx = {}
    submitted = 0
    done_count = 0

    # Initial batch
    for item in items[:effective]:
        f = pool.submit(fn, item)
        futures_to_idx[f] = submitted
        submitted += 1

    pending = set(futures_to_idx.keys())
    while pending:
        if cancel_token and getattr(cancel_token, 'is_cancelled', False):
            for f in pending:
                f.cancel()
            break

        for future in _as_completed(pending):
            pending.discard(future)
            done_count += 1
            try:
                results.append(future.result())
            except Exception:
                logger.warning(
                    "run_parallel: item %d raised",
                    futures_to_idx[future], exc_info=True,
                )

            if progress_fn:
                progress_fn(done_count, len(items))

            # Submit next item if available
            if submitted < len(items):
                f = pool.submit(fn, items[submitted])
                futures_to_idx[f] = submitted
                pending.add(f)
                submitted += 1

    return results


# Singleton — import and use directly:
#   from codrag.services.pipeline.thread_pool import llm_pool
#   future = llm_pool.submit(llm.generate, prompt=..., ...)
llm_pool = _LLMPoolProxy()

"""Shared bounded thread pool for pipeline LLM stages.

Replaces per-stage ThreadPoolExecutor creation to prevent thread
accumulation.  A single pipeline run on a 28-file project was observed
to grow the daemon from 20 to 73 threads, with 64 competing for the
GIL — causing lock convoy effects that made the daemon appear hung.

Usage (in pipeline stages):

    from prep.services.pipeline.thread_pool import llm_pool

    # Submit work — same API as ThreadPoolExecutor
    futures = [llm_pool.submit(fn, arg) for arg in items]

    # Collect results — use concurrent.futures.wait or as_completed
    from concurrent.futures import wait, FIRST_COMPLETED
    done, pending = wait(futures, timeout=120, return_when=FIRST_COMPLETED)

The pool is bounded (default 32 workers, ``CODRAG_LLM_POOL_SIZE``
env override up to 64) so thread growth is capped. The **actual**
LLM concurrency ceiling is enforced by the AIMD gate inside
``LLMClient.generate`` (``PipelineScheduler.acquire_request``) — the
same mechanism swarm stages use — so both swarm and non-swarm paths
converge on the scheduler's discovered per-provider budget. Stages
that submit work when the pool is full will block until a worker
becomes available.

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

# Thread capacity for LLM fan-out across pipeline stages.
#
# IMPORTANT: this is NOT the concurrency throttle. The AIMD per-request
# gate inside ``LLMClient.generate`` (``PipelineScheduler.acquire_request``)
# is the sole throttle for how many LLM calls actually run in parallel —
# it discovers the real per-provider ceiling dynamically (typically
# 20-40 for cloud Max tier). This pool just needs to provide *enough*
# thread capacity that the gate is the binding constraint, not the pool.
#
# Sizing rationale (Phase 82 follow-up):
#   - Old default was 6, which artificially choked non-swarm fan-out
#     to 2-3 observed concurrent calls even after AIMD had discovered
#     28+ budget.  Swarm paths bypassed this by creating their own
#     per-call ThreadPoolExecutor sized to the scheduler budget, and
#     routinely hit 18-28 concurrent.  The non-swarm fan-out paths
#     (``cluster._synthesize_batched``, ``concept_seeder._seed_concepts_sequential``)
#     now share this pool; it must be large enough that the AIMD gate
#     is what gates them, just like swarm.
#   - 32 comfortably exceeds typical cloud Max-tier AIMD ceilings and
#     leaves headroom for incidental stage work.  Threads blocked in
#     the AIMD gate consume no CPU, so idle headroom is nearly free.
#   - GIL: Python 3.11 thread-count concerns were measured around
#     pipeline runs that spun 60+ *active* threads.  Here most threads
#     are blocked on the gate or on I/O to the LLM endpoint, so the
#     active-thread count stays low.
#
# Can be overridden via ``CODRAG_LLM_POOL_SIZE`` env var, range [1,64].
_DEFAULT_POOL_SIZE = 32
_MAX_POOL_SIZE = 64

_pool: Optional[ThreadPoolExecutor] = None
_pool_size: int = 0  # Cached — avoids accessing ThreadPoolExecutor._max_workers (private)
_pool_lock = threading.Lock()


def _get_pool_size() -> int:
    """Read pool size from env or use default."""
    try:
        val = os.environ.get("CODRAG_LLM_POOL_SIZE")
        if val:
            n = int(val)
            if 1 <= n <= _MAX_POOL_SIZE:
                return n
            logger.warning(
                "CODRAG_LLM_POOL_SIZE=%d out of range [1,%d], using default %d",
                n, _MAX_POOL_SIZE, _DEFAULT_POOL_SIZE,
            )
    except (ValueError, TypeError):
        pass
    return _DEFAULT_POOL_SIZE


def _ensure_pool() -> ThreadPoolExecutor:
    """Lazily create the shared pool on first access."""
    global _pool, _pool_size
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
        _pool_size = size
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
        _ensure_pool()  # force lazy init
        return _pool_size

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
        concurrency if concurrency > 0 else _pool_size,
        _pool_size,
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
#   from prep.services.pipeline.thread_pool import llm_pool
#   future = llm_pool.submit(llm.generate, prompt=..., ...)
llm_pool = _LLMPoolProxy()

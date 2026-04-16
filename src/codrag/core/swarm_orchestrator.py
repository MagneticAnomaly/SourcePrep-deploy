"""Three-phase swarm orchestrator for parallel codebase analysis.

Phase 1 (Coordinate): One LLM call decomposes work into scoped assignments.
Phase 2 (Fan-out):    N parallel worker calls with scoped roles.
Phase 3 (Synthesize): One LLM call aggregates worker results.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import (
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    wait,
)
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from codrag.core.llm_client import LLMClient, _parse_json_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

COORDINATOR_SYSTEM = (
    "You are a senior software architect planning a parallel codebase analysis. "
    "Respond with valid JSON only. No markdown, no explanation outside the JSON."
)

SYNTHESIS_SYSTEM = (
    "You are a senior software architect synthesizing findings from parallel "
    "codebase analyses. Respond with valid JSON only."
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WorkItem:
    id: str
    summary: str
    full_context: str


@dataclass
class WorkerAssignment:
    item_id: str
    analysis_angle: str
    priority_concerns: List[str] = field(default_factory=list)


@dataclass
class CoordinatorPlan:
    assignments: List[WorkerAssignment] = field(default_factory=list)

    def get_assignment(self, item_id: str) -> Optional[WorkerAssignment]:
        for a in self.assignments:
            if a.item_id == item_id:
                return a
        return None


@dataclass
class WorkerResult:
    item_id: str
    raw_output: str
    parsed: Optional[Dict[str, Any]] = None
    success: bool = True


@dataclass
class SwarmStats:
    total_items: int = 0
    workers_succeeded: int = 0
    workers_failed: int = 0
    coordinator_tokens: int = 0
    worker_tokens: int = 0
    synthesis_tokens: int = 0
    wall_clock_seconds: float = 0.0


@dataclass
class SwarmResult:
    worker_results: List[WorkerResult] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    coordinator_plan: Optional[CoordinatorPlan] = None
    stats: SwarmStats = field(default_factory=SwarmStats)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SwarmOrchestrator:
    """Generic three-phase swarm executor.

    Phase 96F: Coordinator and synthesis phases now respect their own
    short timeouts (default 120s and 180s) instead of inheriting the
    LLMClient's "large slot" 600s timeout.  A hung coordinator falls
    back to an empty plan — the fan-out path already handles missing
    assignments by giving each worker a default analysis angle, so the
    workers can still produce output even when the coordinator can't.
    """

    # Phase 96F: timeout defaults — these are shorter than LLMClient
    # large-slot timeout (600s) because coordinator/synthesis prompts
    # are tiny and should respond fast.  A hung coordinator was the
    # root cause of the mini-redis-rust finalize stall during live
    # validation — kimi-k2.5:cloud took 11+ minutes on a ~3KB prompt
    # before being killed.
    DEFAULT_COORDINATOR_TIMEOUT_S: float = 120.0
    DEFAULT_SYNTHESIS_TIMEOUT_S: float = 180.0

    # F-59 rework: per-worker and overall fan-out timeouts.
    # Cloud models process requests sequentially (1 at a time for free tier).
    # With 155 groups × 5-10 min per group, fan-out could run for hours
    # without these caps.  Workers that exceed the per-worker timeout are
    # marked as failed; the fan-out returns partial results when the
    # overall timeout fires.
    DEFAULT_WORKER_TIMEOUT_S: float = 180.0
    DEFAULT_MAX_WALL_TIME_S: float = 900.0  # 15 minutes total

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        concurrency: int = 10,
        *,
        coordinator_llm: Optional[LLMClient] = None,
        worker_llm: Optional[LLMClient] = None,
        coordinator_timeout_s: Optional[float] = None,
        synthesis_timeout_s: Optional[float] = None,
        worker_timeout_s: Optional[float] = None,
        max_wall_time_s: Optional[float] = None,
    ) -> None:
        # Resolve LLMs.  New-style callers pass coordinator_llm + worker_llm.
        # Legacy callers (and tests) still use llm=.  If coordinator_llm is
        # unset, fall back to worker_llm (or legacy llm) — this is the
        # "Inherit from Thinking Model" behavior.
        if worker_llm is None:
            worker_llm = llm
        if coordinator_llm is None:
            coordinator_llm = worker_llm

        if worker_llm is None:
            raise ValueError(
                "SwarmOrchestrator requires either `llm` (legacy) or "
                "`worker_llm` (preferred)."
            )

        self.worker_llm = worker_llm
        self.coordinator_llm = coordinator_llm
        # Keep `self.llm` pointing at the worker LLM for any code path that
        # still references it (migrated incrementally in call-site tasks).
        self.llm = worker_llm

        self.concurrency = max(1, concurrency)
        self.coordinator_timeout_s = (
            coordinator_timeout_s
            if coordinator_timeout_s is not None
            else self.DEFAULT_COORDINATOR_TIMEOUT_S
        )
        self.synthesis_timeout_s = (
            synthesis_timeout_s
            if synthesis_timeout_s is not None
            else self.DEFAULT_SYNTHESIS_TIMEOUT_S
        )
        self.worker_timeout_s = (
            worker_timeout_s
            if worker_timeout_s is not None
            else self.DEFAULT_WORKER_TIMEOUT_S
        )
        self.max_wall_time_s = (
            max_wall_time_s
            if max_wall_time_s is not None
            else self.DEFAULT_MAX_WALL_TIME_S
        )

    def _llm_call_with_timeout(
        self,
        prompt: str,
        system: str,
        temperature: float,
        timeout_s: float,
        phase: str,
        llm: Optional[LLMClient] = None,
    ) -> Tuple[Optional[str], int]:
        """Run an LLM call in a worker thread with a hard timeout.

        Returns (text, tokens) on success, (None, 0) on timeout or
        exception.  The underlying thread is allowed to keep running
        until the LLM call returns naturally — Python provides no way
        to forcibly cancel a thread blocked on a network read.  In
        practice this is fine because the LLMClient itself has a
        request-level timeout, just longer than ours.

        Phase 96F follow-up (F-29): Forces ``think=False`` for swarm
        coordinator and synthesis calls.  Reasoning models like
        kimi-k2.5:cloud consume their ``num_predict`` budget on the
        ``thinking`` field and produce empty ``response`` output when
        the budget is small (≤2048 tokens).  Swarm coordinator and
        synthesis prompts are short structured JSON requests that
        don't benefit from chain-of-thought reasoning, so disabling
        thinking is both faster and avoids the empty-response failure
        mode.  Reasoning-heavy stages (deepening, group_reasoning
        analysis) keep their thinking enabled at the worker level.
        """
        # F-59: DO NOT use `with ThreadPoolExecutor(...) as pool:` here.
        # The `with` block's __exit__ calls pool.shutdown(wait=True), which
        # blocks until the submitted future completes — even after our timeout
        # fires.
        #
        # F-59 rework: on timeout, close the worker thread's HTTP Session
        # to abort the zombie's in-flight request and free the cloud queue
        # slot.  We can't use self.llm.close_session() because that only
        # reaches the *calling* thread's thread-local Session, not the
        # zombie's.  Instead, the wrapper captures the Session reference
        # so we can close it from any thread.
        client = llm if llm is not None else self.worker_llm
        zombie_session_ref: List = []  # mutable container to capture from closure

        def _generate_and_capture(**kwargs):
            """Wrapper that captures the thread-local Session for cleanup."""
            # Force Session creation by touching the property, then capture it.
            _ = client._session
            s = getattr(client._thread_local, 'session', None)
            if s is not None:
                zombie_session_ref.append(s)
            return client.generate(**kwargs)

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"swarm-{phase}")
        future = pool.submit(
            _generate_and_capture,
            prompt=prompt,
            system=system,
            json_mode=True,
            temperature=temperature,
            think=False,
        )
        try:
            result = future.result(timeout=timeout_s)
            return result
        except FuturesTimeoutError:
            logger.warning(
                "[Swarm/%s] LLM call timed out after %.0fs — falling back",
                phase, timeout_s,
            )
            # Close the zombie thread's Session to abort the in-flight HTTP
            # request and free the Ollama cloud queue slot.
            if zombie_session_ref:
                try:
                    zombie_session_ref[0].close()
                    logger.info("[Swarm/%s] Closed zombie HTTP session", phase)
                except Exception:
                    pass
            return None, 0
        except Exception:
            logger.warning(
                "[Swarm/%s] LLM call raised", phase, exc_info=True,
            )
            return None, 0
        finally:
            pool.shutdown(wait=False)

    # -- Phase 1: Coordinate ------------------------------------------------

    def _coordinate(
        self,
        items: List[WorkItem],
        coordinator_prompt: str,
    ) -> Tuple[Optional[CoordinatorPlan], int]:
        """Single LLM call to decompose work into scoped assignments.

        Returns (plan, token_count).  Plan is None on any failure
        (timeout, parse error, empty assignments).  Callers should
        proceed with fan-out anyway — the fan-out path handles missing
        assignments by giving each worker a default analysis angle.
        """
        summaries = "\n".join(
            f"- {item.id}: {item.summary}" for item in items
        )
        prompt = coordinator_prompt.replace("{group_summaries}", summaries)

        text, tokens = self._llm_call_with_timeout(
            prompt=prompt,
            system=COORDINATOR_SYSTEM,
            temperature=0.4,
            timeout_s=self.coordinator_timeout_s,
            phase="coordinator",
            llm=self.coordinator_llm,
        )
        if text is None:
            return None, tokens

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Coordinator returned unparseable JSON")
            return None, tokens

        raw_assignments = parsed.get("assignments", [])
        if not raw_assignments:
            logger.warning("Coordinator returned empty assignments")
            return None, tokens

        assignments = [
            WorkerAssignment(
                item_id=a.get("item_id", ""),
                analysis_angle=a.get("analysis_angle", ""),
                priority_concerns=a.get("priority_concerns", []),
            )
            for a in raw_assignments
        ]

        logger.info(
            "[Swarm] Coordinator planned %d assignments (%d tokens)",
            len(assignments), tokens,
        )
        return CoordinatorPlan(assignments=assignments), tokens

    # -- Phase 2: Fan-out ---------------------------------------------------

    def _fan_out(
        self,
        items: List[WorkItem],
        plan: CoordinatorPlan,
        worker_fn: Callable[[WorkItem, WorkerAssignment], Optional[str]],
        progress_fn: Optional[Callable[[int, int], None]] = None,
        t0: Optional[float] = None,
    ) -> List[WorkerResult]:
        """Run worker_fn in parallel for each item.

        F-59 rework: two timeout layers protect against hangs.

        1. **Stall detection** (``worker_timeout_s``): If no worker
           completes for ``worker_timeout_s`` seconds, the fan-out
           assumes the cloud endpoint is stuck and aborts.  Uses
           ``wait(FIRST_COMPLETED)`` so the timeout is measured between
           completions, not per-worker.  (``as_completed`` + per-future
           timeout doesn't work — it only yields *done* futures, so
           ``future.result(timeout=X)`` returns instantly.)

        2. **Wall-time cap** (``max_wall_time_s``): Absolute elapsed
           time from the start of ``execute()``.  Prevents 155 groups
           on a 1-at-a-time cloud endpoint from running for hours.
        """
        total = len(items)
        results: List[WorkerResult] = []
        fan_start = t0 or time.monotonic()

        def _run_worker(item: WorkItem) -> WorkerResult:
            logger.info("[Swarm] Worker starting: %s", item.id[:40])
            assignment = plan.get_assignment(item.id)
            if assignment is None:
                assignment = WorkerAssignment(
                    item_id=item.id,
                    analysis_angle="Perform standard architectural analysis",
                )
            try:
                raw = worker_fn(item, assignment)
                logger.info("[Swarm] Worker returned: %s len=%d", item.id[:40], len(raw or ""))
                if raw is None:
                    return WorkerResult(
                        item_id=item.id, raw_output="", success=False
                    )
                parsed = _parse_json_response(raw)
                return WorkerResult(
                    item_id=item.id,
                    raw_output=raw,
                    parsed=parsed,
                    success=True,
                )
            except Exception:
                logger.warning(
                    "Worker failed for %s", item.id, exc_info=True
                )
                return WorkerResult(
                    item_id=item.id, raw_output="", success=False
                )

        max_workers = min(self.concurrency, total) if total > 0 else 1
        done_count = 0
        stall_aborted = False

        logger.info(
            "[Swarm] Starting fan-out: %d items, %d workers, "
            "stall_timeout=%.0fs, max_wall=%.0fs",
            total, max_workers, self.worker_timeout_s, self.max_wall_time_s,
        )
        pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="swarm-fanout")
        try:
            futures = {pool.submit(_run_worker, item): item for item in items}
            pending = set(futures.keys())

            while pending:
                # Compute remaining wall time
                elapsed = time.monotonic() - fan_start
                remaining_wall = self.max_wall_time_s - elapsed
                if remaining_wall <= 0:
                    logger.warning(
                        "[Swarm] Wall-time cap (%.0fs) exceeded after %.0fs — "
                        "aborting %d pending workers, returning %d partial results",
                        self.max_wall_time_s, elapsed, len(pending), done_count,
                    )
                    for f in pending:
                        f.cancel()
                    break

                # Wait for the next completion, with stall detection.
                # Timeout is the LESSER of stall timeout and remaining wall time.
                wait_timeout = min(self.worker_timeout_s, remaining_wall)
                done_set, pending = wait(pending, timeout=wait_timeout, return_when=FIRST_COMPLETED)

                if not done_set:
                    # No worker completed in wait_timeout seconds — stall.
                    stall_aborted = True
                    logger.warning(
                        "[Swarm] Stall detected: no worker completed in %.0fs — "
                        "aborting %d pending workers, returning %d partial results",
                        wait_timeout, len(pending), done_count,
                    )
                    for f in pending:
                        f.cancel()
                    break

                # Collect completed results
                for future in done_set:
                    try:
                        result = future.result()  # already done, returns instantly
                    except Exception:
                        item = futures[future]
                        logger.warning(
                            "Worker future raised for %s", item.id, exc_info=True
                        )
                        result = WorkerResult(
                            item_id=item.id, raw_output="", success=False
                        )

                    results.append(result)
                    done_count += 1
                    logger.info(
                        "[Swarm] Worker %d/%d done: %s success=%s (%.0fs elapsed)",
                        done_count, total, result.item_id[:40], result.success,
                        time.monotonic() - fan_start,
                    )
                    if progress_fn is not None:
                        progress_fn(done_count, total)
        finally:
            pool.shutdown(wait=False)

        succeeded = sum(1 for r in results if r.success)
        logger.info(
            "[Swarm] Fan-out complete: %d/%d succeeded, %d pending abandoned%s, "
            "%.0fs elapsed",
            succeeded, total, total - done_count,
            " (stall)" if stall_aborted else "",
            time.monotonic() - fan_start,
        )
        return results

    # -- Phase 3: Synthesize ------------------------------------------------

    def _synthesize(
        self,
        worker_results: List[WorkerResult],
        synthesis_prompt: str,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Single LLM call to aggregate successful worker results.

        Returns (parsed_result, token_count). Result is None on failure,
        timeout, or if no workers succeeded.  Callers (e.g.
        concept_seeder) should fall back to merging raw worker outputs
        when synthesis returns None.
        """
        successful = [r for r in worker_results if r.success and r.parsed]
        if not successful:
            logger.warning("[Swarm] No successful workers with parsed output — skipping synthesis")
            return None, 0

        outputs = "\n\n".join(
            f"### {r.item_id}\n```json\n{json.dumps(r.parsed, indent=2)}\n```"
            for r in successful
        )
        prompt = synthesis_prompt.replace("{worker_outputs}", outputs)

        text, tokens = self._llm_call_with_timeout(
            prompt=prompt,
            system=SYNTHESIS_SYSTEM,
            temperature=0.5,
            timeout_s=self.synthesis_timeout_s,
            phase="synthesis",
            llm=self.coordinator_llm,
        )
        if text is None:
            return None, tokens

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Synthesis returned unparseable JSON")
            return None, tokens

        logger.info("[Swarm] Synthesis complete (%d tokens)", tokens)
        return parsed, tokens

    # -- Full execution -----------------------------------------------------

    def execute(
        self,
        items: List[WorkItem],
        coordinator_prompt: str,
        worker_fn: Callable[[WorkItem, WorkerAssignment], Optional[str]],
        synthesis_prompt: str,
        progress_fn: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[SwarmResult]:
        """Run all three phases.

        Phase 96F: When the coordinator fails or times out, fan-out
        still runs with default per-worker assignments.  Only the
        synthesis phase is allowed to leave a None synthesis on the
        result — callers handle that by merging raw worker outputs.
        Returns None only when there are zero items to process.
        """
        if not items:
            return None

        t0 = time.monotonic()
        stats = SwarmStats(total_items=len(items))

        # Phase 1: Coordinate (with timeout, may return empty plan)
        plan, coordinator_tokens = self._coordinate(items, coordinator_prompt)
        if plan is None:
            logger.info(
                "[Swarm] Coordinator failed/timed out — proceeding with "
                "default assignments for %d items",
                len(items),
            )
            plan = CoordinatorPlan(assignments=[])  # fan-out fills defaults
        stats.coordinator_tokens = coordinator_tokens

        # Phase 2: Fan-out (t0 passed for overall wall-time tracking)
        logger.info("[Swarm] Entering fan-out phase (%d items)", len(items))
        worker_results = self._fan_out(items, plan, worker_fn, progress_fn, t0=t0)
        logger.info("[Swarm] Fan-out returned: %d results", len(worker_results))

        for r in worker_results:
            if r.success:
                stats.workers_succeeded += 1
            else:
                stats.workers_failed += 1

        # Phase 3: Synthesize
        logger.info("[Swarm] Entering synthesis phase (%d/%d succeeded)",
                    stats.workers_succeeded, len(worker_results))
        synthesis, synthesis_tokens = self._synthesize(
            worker_results, synthesis_prompt
        )
        logger.info("[Swarm] Synthesis returned (tokens=%d)", synthesis_tokens)
        stats.synthesis_tokens = synthesis_tokens

        stats.wall_clock_seconds = time.monotonic() - t0

        result = SwarmResult(
            worker_results=worker_results,
            synthesis=synthesis,
            coordinator_plan=plan,
            stats=stats,
        )

        # §9 observability: emit per-run quality + throughput metrics.
        # Uses record_swarm_metrics() if token_telemetry exposes it, otherwise
        # falls back to a structured log line that downstream tooling can grep.
        try:
            from codrag.services import token_telemetry as _tt
            recorder = getattr(_tt, "record_swarm_metrics", None)
            if recorder is not None:
                recorder(
                    phase="swarm_run",
                    coordinator_json_valid=(result.coordinator_plan is not None
                                           and len(result.coordinator_plan.assignments) > 0),
                    synthesis_json_valid=(result.synthesis is not None),
                    workers_succeeded=result.stats.workers_succeeded,
                    workers_failed=result.stats.workers_failed,
                    wall_clock_seconds=result.stats.wall_clock_seconds,
                )
            else:
                logger.info(
                    "[Swarm-Metrics] phase=swarm_run coord_valid=%s synth_valid=%s "
                    "workers_succeeded=%d workers_failed=%d wall_clock_s=%.2f",
                    result.coordinator_plan is not None and len(result.coordinator_plan.assignments) > 0,
                    result.synthesis is not None,
                    result.stats.workers_succeeded,
                    result.stats.workers_failed,
                    result.stats.wall_clock_seconds,
                )
        except Exception:
            logger.debug("swarm metrics emission failed", exc_info=True)

        return result

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
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    as_completed,
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

    def __init__(
        self,
        llm: LLMClient,
        concurrency: int = 10,
        *,
        coordinator_timeout_s: Optional[float] = None,
        synthesis_timeout_s: Optional[float] = None,
    ) -> None:
        self.llm = llm
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

    def _llm_call_with_timeout(
        self,
        prompt: str,
        system: str,
        temperature: float,
        timeout_s: float,
        phase: str,
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
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"swarm-{phase}") as pool:
            future = pool.submit(
                self.llm.generate,
                prompt=prompt,
                system=system,
                json_mode=True,
                temperature=temperature,
                think=False,
            )
            try:
                return future.result(timeout=timeout_s)
            except FuturesTimeoutError:
                logger.warning(
                    "[Swarm/%s] LLM call timed out after %.0fs — falling back",
                    phase, timeout_s,
                )
                return None, 0
            except Exception:
                logger.warning(
                    "[Swarm/%s] LLM call raised", phase, exc_info=True,
                )
                return None, 0

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
    ) -> List[WorkerResult]:
        """Run worker_fn in parallel for each item."""
        total = len(items)
        results: List[WorkerResult] = []

        def _run_worker(item: WorkItem) -> WorkerResult:
            assignment = plan.get_assignment(item.id)
            if assignment is None:
                assignment = WorkerAssignment(
                    item_id=item.id,
                    analysis_angle="Perform standard architectural analysis",
                )
            try:
                raw = worker_fn(item, assignment)
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

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_worker, item): item for item in items}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                done_count += 1
                if progress_fn is not None:
                    progress_fn(done_count, total)

        succeeded = sum(1 for r in results if r.success)
        logger.info(
            "[Swarm] Fan-out complete: %d/%d workers succeeded",
            succeeded, total,
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

        # Phase 2: Fan-out
        worker_results = self._fan_out(items, plan, worker_fn, progress_fn)

        for r in worker_results:
            if r.success:
                stats.workers_succeeded += 1
            else:
                stats.workers_failed += 1

        # Phase 3: Synthesize
        synthesis, synthesis_tokens = self._synthesize(
            worker_results, synthesis_prompt
        )
        stats.synthesis_tokens = synthesis_tokens

        stats.wall_clock_seconds = time.monotonic() - t0

        return SwarmResult(
            worker_results=worker_results,
            synthesis=synthesis,
            coordinator_plan=plan,
            stats=stats,
        )

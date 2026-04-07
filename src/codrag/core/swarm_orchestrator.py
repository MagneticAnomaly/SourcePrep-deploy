"""Three-phase swarm orchestrator for parallel codebase analysis.

Phase 1 (Coordinate): One LLM call decomposes work into scoped assignments.
Phase 2 (Fan-out):    N parallel worker calls with scoped roles.
Phase 3 (Synthesize): One LLM call aggregates worker results.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Generic three-phase swarm executor."""

    def __init__(self, llm: LLMClient, concurrency: int = 10) -> None:
        self.llm = llm
        self.concurrency = max(1, concurrency)

    # -- Phase 1: Coordinate ------------------------------------------------

    def _coordinate(
        self,
        items: List[WorkItem],
        coordinator_prompt: str,
    ) -> Tuple[Optional[CoordinatorPlan], int]:
        """Single LLM call to decompose work into scoped assignments.

        Returns (plan, token_count). Plan is None on any failure.
        """
        summaries = "\n".join(
            f"- {item.id}: {item.summary}" for item in items
        )
        prompt = coordinator_prompt.replace("{group_summaries}", summaries)

        try:
            text, tokens = self.llm.generate(
                prompt=prompt,
                system=COORDINATOR_SYSTEM,
                json_mode=True,
                temperature=0.4,
            )
        except Exception:
            logger.warning("Coordinator LLM call failed", exc_info=True)
            return None, 0

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

        return results

    # -- Phase 3: Synthesize ------------------------------------------------

    def _synthesize(
        self,
        worker_results: List[WorkerResult],
        synthesis_prompt: str,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Single LLM call to aggregate successful worker results.

        Returns (parsed_result, token_count). Result is None on failure
        or if no workers succeeded.
        """
        successful = [r for r in worker_results if r.success]
        if not successful:
            logger.warning("No successful workers — skipping synthesis")
            return None, 0

        outputs = "\n\n".join(
            f"=== {r.item_id} ===\n{r.raw_output}" for r in successful
        )
        prompt = synthesis_prompt.replace("{worker_outputs}", outputs)

        try:
            text, tokens = self.llm.generate(
                prompt=prompt,
                system=SYNTHESIS_SYSTEM,
                json_mode=True,
                temperature=0.5,
            )
        except Exception:
            logger.warning("Synthesis LLM call failed", exc_info=True)
            return None, 0

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Synthesis returned unparseable JSON")
            return None, tokens

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
        """Run all three phases. Returns None if coordinator fails."""
        t0 = time.monotonic()
        stats = SwarmStats(total_items=len(items))

        # Phase 1: Coordinate
        plan, coordinator_tokens = self._coordinate(items, coordinator_prompt)
        if plan is None:
            return None
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

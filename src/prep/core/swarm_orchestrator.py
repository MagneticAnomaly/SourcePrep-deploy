"""Three-phase swarm orchestrator for parallel codebase analysis.

Phase 1 (Coordinate): One LLM call decomposes work into scoped assignments.
Phase 2 (Fan-out):    N parallel worker calls with scoped roles.
Phase 3 (Synthesize): One LLM call aggregates worker results.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import (
    FIRST_COMPLETED,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    wait,
)
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from prep.core.llm_client import LLMClient, _parse_json_response
from prep.core.swarm_event_logger import SwarmEventLogger, default_log_dir
from prep.services.cancellation import PipelinePausedError
from prep.services.pipeline.holds import HoldAwareMixin, HoldPausedError
from prep.services.token_telemetry import set_swarm_role

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
    # Phase 119 verbose-logging: path to the JSONL event log written
    # for this swarm execution.  None when logging was disabled or the
    # logger could not initialize (e.g. read-only data_dir).
    event_log_path: Optional[str] = None

    # Phase 127: soft-hold pause signaling.  When ``paused`` is True the
    # swarm exited at a phase boundary because a soft-hold blocked
    # further LLM dispatch (exclusive priority on another project, or
    # swarm window draining ours).  Callers should treat this as
    # "retry on next run" rather than counting it as a permanent failure.
    paused: bool = False
    pause_info: Optional[Dict[str, str]] = None

    # Phase 136 Part 09: raw LLM synthesis response, captured on every
    # parse path so callers (currently concept_seeder) can include
    # head/tail in the ``concepts_synthesis_failed`` telemetry payload.
    # ``None`` when no LLM call was made (no successful workers) or the
    # call timed out — the call was made if ``synthesis_prompt_chars > 0``.
    # ``synthesis_prompt_chars`` records the consolidation prompt size so
    # the "output-token cap on large prompts" hypothesis can be tested
    # against production telemetry without re-instrumenting later.
    raw_synthesis_text: Optional[str] = None
    synthesis_prompt_chars: int = 0

    # Phase 136 Part 09 Step 2: chunked-synthesis surface.
    # synthesis_chunk_count == 1 means single-call path (or chunking was
    # eligible but only one chunk's worth of workers).  N > 1 means N
    # chunks + 1 meta call.  synthesis_meta_failed is True ONLY when the
    # chunked path ran AND chunks succeeded AND meta failed AND we
    # returned a manually-deduped union of survivors as result.synthesis.
    # The diagnostic classifier reads these to distinguish
    # chunked_meta_failed and chunked_all_failed from the four single-
    # call failure modes (no_workers / no_text / parse_failed /
    # parsed_but_empty).
    synthesis_chunk_count: int = 1
    synthesis_meta_failed: bool = False


# ---------------------------------------------------------------------------
# Wall-time budget helpers
# ---------------------------------------------------------------------------


# Per-worker time estimates used to size the fan-out wall budget.
# Empirical (2026-05-27, kimi-k2.6:cloud): observed 35-110s per worker
# on a 167-group group_reasoning run, average ~70s.  Local workers run
# slower and serialize through ollama's queue, so estimate higher.
_WORKER_AVG_S_CLOUD: float = 80.0
_WORKER_AVG_S_LOCAL: float = 120.0

# Safety multiplier applied to the projected runtime before clamping.
# Workers may have variance, the coordinator and synthesis phases also
# consume the same budget, and we'd rather over-allocate than re-trip
# the silent-data-loss path documented in pipeline_checkpoint.py.
_WALL_SAFETY_FACTOR: float = 1.5

# Lower / upper bounds on the computed budget.  Floor prevents tiny
# workloads from getting unreasonably short caps; ceiling prevents a
# wildly-sized workload from disabling the safety net entirely.
_WALL_FLOOR_CLOUD_S: float = 900.0
_WALL_FLOOR_LOCAL_S: float = 1800.0
_WALL_CEILING_S: float = 5400.0  # 90 min — past this, redesign


def compute_swarm_wall_budget(
    n_items: int,
    concurrency: int,
    is_cloud: bool,
) -> float:
    """Compute a fan-out wall-time budget scaled to the workload.

    Before 2026-05-27 (Phase 141) the swarm wall cap was a fixed 900s
    inherited from the F-59 fix to the mini-redis-rust finalize stall,
    when cloud was assumed to be sequential (free tier).  Phase 82
    enabled AIMD-discovered parallel cloud concurrency (~10x), which
    invalidated the sizing assumption — a legitimate 160-group
    group_reasoning run now needs ~1170-1750s, well over 900s.

    The 2026-05-26 incident: swarm hit the 900s cap at worker 61/160,
    silently cancelled the remaining 99 pending workers (all of which
    had ``success=True`` records), and wrote a 38%-of-expected output
    that the IntegrityGuard's broken recovery path then accepted as
    "completed".  Phase 136 Part 09's risk note —"bigger budget hides
    workload growth"— was reified.

    This helper sizes the budget per-call so the next workload growth
    doesn't silently re-trip the same bug.  Stall detection and
    per-worker timeouts in the orchestrator still catch genuinely
    hung models within their own budgets.
    """
    n = max(1, n_items)
    conc = max(1, concurrency)
    worker_avg = _WORKER_AVG_S_CLOUD if is_cloud else _WORKER_AVG_S_LOCAL
    floor = _WALL_FLOOR_CLOUD_S if is_cloud else _WALL_FLOOR_LOCAL_S

    projected = (n * worker_avg) / conc * _WALL_SAFETY_FACTOR
    return max(floor, min(projected, _WALL_CEILING_S))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SwarmOrchestrator(HoldAwareMixin):
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
    # 2026-05-27 (Phase 141): bumped from 900s -> 1800s.  The original
    # 900s assumed free-tier sequential cloud; Phase 82 enabled AIMD
    # parallel cloud (~10x concurrency) which means legitimate large
    # workloads (160+ groups × ~70s avg / 10 conc) need ~1170-1750s.
    # Use ``compute_swarm_wall_budget`` from caller sites instead of
    # relying on this default — that scales the budget with workload
    # so we don't trip on the next growth episode.
    DEFAULT_MAX_WALL_TIME_S: float = 1800.0  # 30 minutes — defensive default

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
        project_id: Optional[str] = None,
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
        # Phase 136 Part 09 Step 2: threshold above which synthesis
        # splits into chunks of ~chunk_max_workers each.  Read at
        # __init__ so tests can monkeypatch the env before constructing
        # the orchestrator.  Default 200 matches the Part 09 work order.
        # Same value doubles as the per-chunk batch size (`chunk_max_workers`
        # workers per chunk; last chunk may be smaller).
        try:
            self.synthesis_chunk_max_workers = int(
                os.environ.get("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", "200")
            )
        except ValueError:
            self.synthesis_chunk_max_workers = 200
        if self.synthesis_chunk_max_workers < 1:
            self.synthesis_chunk_max_workers = 200
        # Phase 127: project_id lets us check soft-holds at phase
        # boundaries.  None is acceptable (the hold check becomes a no-op
        # because no project-keyed hold can match an empty project id).
        # ``execute()`` accepts a project_id kwarg too — when provided
        # there it overrides this for the duration of that call (e.g.
        # event-log routing).
        self.project_id = project_id

    @property
    def _hold_llm_for_check(self) -> Any:
        """Gate the soft-hold check against the worker LLM.

        Fan-out consumes the bulk of capacity, so the worker endpoint
        is the right blast-radius bound — coord and synth typically
        share the same endpoint family in practice.
        """
        return self.worker_llm

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

        # Phase 119 Swarm Authority: tag the LLM call with its swarm role
        # so token_telemetry stamps the active request.  Uses the phase
        # name verbatim ("coordinator" / "synthesis") for the
        # _llm_call_with_timeout path; fan-out workers set their own
        # role around worker_fn (see _fan_out).
        # We translate "synthesis" → "synthesizer" so the surfaced role
        # matches the noun used in the UI grouping.
        role_tag: Optional[str] = None
        if phase == "coordinator":
            role_tag = "coordinator"
        elif phase == "synthesis":
            role_tag = "synthesizer"

        def _generate_and_capture(**kwargs):
            """Wrapper that captures the thread-local Session for cleanup."""
            # Force Session creation by touching the property, then capture it.
            _ = client._session
            s = getattr(client._thread_local, 'session', None)
            if s is not None:
                zombie_session_ref.append(s)
            with set_swarm_role(role_tag):
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
        event_log: Optional[SwarmEventLogger] = None,
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

        coord_model = getattr(self.coordinator_llm, "model", None)
        if event_log is not None:
            event_log.phase_start("coordinator", model=coord_model,
                                  n_items=len(items))
        coord_t0 = time.monotonic()
        text, tokens = self._llm_call_with_timeout(
            prompt=prompt,
            system=COORDINATOR_SYSTEM,
            temperature=0.4,
            timeout_s=self.coordinator_timeout_s,
            phase="coordinator",
            llm=self.coordinator_llm,
        )
        if text is None:
            if event_log is not None:
                event_log.phase_end("coordinator", success=False,
                                    duration_s=time.monotonic() - coord_t0,
                                    reason="timeout_or_error", tokens=tokens)
            return None, tokens

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Coordinator returned unparseable JSON")
            if event_log is not None:
                event_log.parse_failure(where="coordinator",
                                        raw_chars=len(text),
                                        reason="json_parse_failed")
                event_log.phase_end("coordinator", success=False,
                                    duration_s=time.monotonic() - coord_t0,
                                    reason="parse_failed", tokens=tokens)
            return None, tokens

        raw_assignments = parsed.get("assignments", [])
        if not raw_assignments:
            logger.warning("Coordinator returned empty assignments")
            if event_log is not None:
                event_log.phase_end("coordinator", success=False,
                                    duration_s=time.monotonic() - coord_t0,
                                    reason="empty_assignments", tokens=tokens)
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
        if event_log is not None:
            event_log.phase_end("coordinator", success=True,
                                duration_s=time.monotonic() - coord_t0,
                                tokens=tokens, n_assignments=len(assignments))
        return CoordinatorPlan(assignments=assignments), tokens

    # -- Phase 2: Fan-out ---------------------------------------------------

    def _fan_out(
        self,
        items: List[WorkItem],
        plan: CoordinatorPlan,
        worker_fn: Callable[[WorkItem, WorkerAssignment], Optional[str]],
        progress_fn: Optional[Callable[[int, int], None]] = None,
        t0: Optional[float] = None,
        event_log: Optional[SwarmEventLogger] = None,
        cancel_token: Any | None = None,
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

        worker_model = getattr(self.worker_llm, "model", None)

        def _run_worker(item: WorkItem) -> WorkerResult:
            logger.info("[Swarm] Worker starting: %s", item.id[:40])
            assignment = plan.get_assignment(item.id)
            if assignment is None:
                assignment = WorkerAssignment(
                    item_id=item.id,
                    analysis_angle="Perform standard architectural analysis",
                )
            worker_id = f"w-{item.id[:32]}"
            if event_log is not None:
                # prompt_chars uses the work item's full_context as a
                # proxy — workers compose their own prompts from this
                # plus the assignment, so this is the input size we
                # send into the worker, not the literal LLM prompt.
                event_log.worker_dispatch(
                    worker_id=worker_id,
                    work_item_id=item.id,
                    model=worker_model,
                    prompt_chars=len(item.full_context or ""),
                )
            w_t0 = time.monotonic()
            try:
                # Phase 119 Swarm Authority: tag this worker's LLM calls
                # so token_telemetry stamps swarm_role="worker" on the
                # ActiveLLMRequest entry.  Lives in the thread the
                # ThreadPoolExecutor runs us on.
                with set_swarm_role("worker"):
                    raw = worker_fn(item, assignment)
                logger.info("[Swarm] Worker returned: %s len=%d", item.id[:40], len(raw or ""))
                if raw is None:
                    if event_log is not None:
                        event_log.worker_complete(
                            worker_id=worker_id, success=False,
                            duration_s=time.monotonic() - w_t0,
                            response_chars=0, parse_ok=False,
                            error="worker_returned_none",
                        )
                    return WorkerResult(
                        item_id=item.id, raw_output="", success=False
                    )
                parsed = _parse_json_response(raw)
                parse_ok = parsed is not None
                if event_log is not None:
                    if not parse_ok:
                        event_log.parse_failure(
                            where=f"worker:{item.id}",
                            raw_chars=len(raw),
                            reason="json_parse_failed",
                        )
                    event_log.worker_complete(
                        worker_id=worker_id, success=True,
                        duration_s=time.monotonic() - w_t0,
                        response_chars=len(raw),
                        parse_ok=parse_ok,
                    )
                return WorkerResult(
                    item_id=item.id,
                    raw_output=raw,
                    parsed=parsed,
                    success=True,
                )
            except Exception as exc:
                logger.warning(
                    "Worker failed for %s", item.id, exc_info=True
                )
                if event_log is not None:
                    event_log.worker_complete(
                        worker_id=worker_id, success=False,
                        duration_s=time.monotonic() - w_t0,
                        response_chars=0, parse_ok=False,
                        error=str(exc) or exc.__class__.__name__,
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
            # Phase 127 (P127-F9): when cancel_token is provided we
            # dispatch lazily — keep at most max_workers in flight at any
            # one time and submit a new work item only when an old one
            # completes.  This lets us check the cancel_token between
            # completion and the next submission, so a pause set between
            # batches stops new dispatch immediately.  Already-running
            # workers can't be killed (Python can't safely cancel a
            # thread mid-HTTP-request) — they drain naturally.
            #
            # When cancel_token is None we keep the original behavior of
            # submitting all futures up-front so existing tests and
            # workloads continue to behave the same.
            lazy_dispatch = cancel_token is not None

            if lazy_dispatch:
                items_iter = iter(items)
                futures: Dict[Any, WorkItem] = {}
                pending: set = set()
                # Prime the pool with up to max_workers in-flight.
                for _ in range(max_workers):
                    try:
                        nxt = next(items_iter)
                    except StopIteration:
                        break
                    f = pool.submit(_run_worker, nxt)
                    futures[f] = nxt
                    pending.add(f)
            else:
                futures = {pool.submit(_run_worker, item): item for item in items}
                pending = set(futures.keys())
                items_iter = iter([])  # exhausted

            while pending:
                # Phase 127 (P127-F9): user-pause via cancel_token.  Check
                # before each wait so a pause set between completions
                # stops dispatching new work.  Existing in-flight workers
                # cannot be killed mid-HTTP-request — Python has no safe
                # thread cancel — so they drain naturally.  cancel_futures
                # stops any not-yet-started future from running.
                if cancel_token is not None and cancel_token.is_cancelled:
                    logger.info(
                        "[Swarm] cancel_token set — shutting down fan-out pool "
                        "(%d pending, %d done so far)",
                        len(pending), done_count,
                    )
                    try:
                        pool.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        pass
                    # Re-raise as PipelinePausedError (or PipelineCancelledError);
                    # outer try/except in execute() catches and propagates so
                    # the worker dispatcher transitions the slot inactive.
                    cancel_token.raise_if_cancelled()

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

                # Phase 127 (P127-F9): post-batch cancel check.  When
                # lazy_dispatch is on, also use this point to submit a
                # replacement work item — but ONLY if the cancel_token
                # is not set, otherwise we'd dispatch new work after
                # the user paused.
                if cancel_token is not None and cancel_token.is_cancelled:
                    logger.info(
                        "[Swarm] cancel_token set after batch — shutting down "
                        "fan-out pool (%d pending, %d done)",
                        len(pending), done_count,
                    )
                    try:
                        pool.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        pass
                    cancel_token.raise_if_cancelled()

                if lazy_dispatch:
                    # Refill the pool with one new item per completion so we
                    # keep max_workers in flight.  A future submission AFTER
                    # the cancel check above is still safe because a pause
                    # set during this submission step will be caught at the
                    # top of the next loop iteration before we wait again.
                    for _ in range(len(done_set)):
                        try:
                            nxt = next(items_iter)
                        except StopIteration:
                            break
                        f = pool.submit(_run_worker, nxt)
                        futures[f] = nxt
                        pending.add(f)
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
        event_log: Optional[SwarmEventLogger] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
        """Phase 136 Part 09 Step 2: dispatch to single-call or chunked
        synthesis based on worker count.

        When the number of successful workers exceeds
        ``self.synthesis_chunk_max_workers``, split into chunks and run
        synthesis + meta-synthesis.  Otherwise run the existing single-
        call path unchanged.

        Same return shape as ``_synthesize_single``:
        ``(parsed, tokens, raw_text, prompt_chars, meta_failed)``.
        """
        successful = [r for r in worker_results if r.success and r.parsed]
        if not successful:
            # Identical to _synthesize_single's no-workers branch —
            # return early without inspecting threshold.  Important:
            # avoids dispatching an empty chunked run.
            logger.warning(
                "[Swarm] No successful workers with parsed output — "
                "skipping synthesis"
            )
            if event_log is not None:
                event_log.event("phase_skipped", phase="synthesis",
                                reason="no_successful_workers")
            return None, 0, None, 0, False

        if len(successful) > self.synthesis_chunk_max_workers:
            return self._synthesize_chunked(
                successful, synthesis_prompt, event_log=event_log,
            )
        return self._synthesize_single(
            successful, synthesis_prompt, event_log=event_log,
        )

    def _synthesize_chunked(
        self,
        successful: List[WorkerResult],
        synthesis_prompt: str,
        event_log: Optional[SwarmEventLogger] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
        """Phase 136 Part 09 Step 2: split synthesis into chunks of
        ``self.synthesis_chunk_max_workers`` and run a meta-synthesis
        over the chunk results.

        Path:
          1. Sort ``successful`` by ``item_id`` for reproducibility.
          2. Slice into batches of up to ``chunk_max_workers``.
          3. For each chunk, run ``_synthesize_single`` (drops the
             chunk on parse_failed / timeout / no_text).  Soft-hold
             check fires AFTER each chunk completes.
          4. If 0 chunks succeeded → return (None, ..., None, max_prompt, False).
             The existing concept_seeder fallback runs against raw
             worker outputs.
          5. Otherwise call ``_synthesize_single`` once more with the
             chunk parsed results as the ``{worker_outputs}`` payload
             (each chunk parsed dict serialized as JSON, joined the
             same way the original prompt joins workers).  Item id for
             each chunk is ``chunk-N``.
             - Meta succeeds → return (meta_parsed, sum_tokens + meta_tokens,
               meta_text, max(per_chunk_prompts, meta_prompt), False).
             - Meta fails → return (manually_deduped_union, ...,
               max(per_chunk_prompts, meta_prompt), True).
               Dedup mirrors concept_seeder.py:889-909 (skip empty
               titles, skip questions with empty text, lowercase-strip
               for dedup keys).

        Tokens are summed across chunks + meta.  prompt_chars is the
        MAX single prompt sent so the diagnostic question "was the
        prompt size too large for the model's output cap?" stays
        meaningful.
        """
        # Step 5a-d: chunk splitting + per-chunk dispatch.
        # Sort by item_id for reproducibility — production debugging and
        # test fixtures both rely on chunk boundaries being deterministic.
        sorted_workers = sorted(successful, key=lambda w: w.item_id)
        chunk_size = self.synthesis_chunk_max_workers
        chunks: List[List[WorkerResult]] = [
            sorted_workers[i:i + chunk_size]
            for i in range(0, len(sorted_workers), chunk_size)
        ]

        logger.info(
            "[Swarm/Chunked] Synthesis: %d workers split into %d chunks of "
            "up to %d each",
            len(sorted_workers), len(chunks), chunk_size,
        )

        # Per-chunk results: list of parsed dicts (successes only).
        chunk_parsed_dicts: List[Dict[str, Any]] = []
        sum_chunk_tokens = 0
        max_chunk_prompt_chars = 0

        for chunk_idx, chunk_workers in enumerate(chunks):
            logger.info(
                "[Swarm/Chunked] Chunk %d/%d: synthesizing %d workers",
                chunk_idx + 1, len(chunks), len(chunk_workers),
            )
            chunk_parsed, chunk_tokens, chunk_text, chunk_prompt_chars, _ = (
                self._synthesize_single(
                    chunk_workers, synthesis_prompt, event_log=event_log,
                )
            )
            sum_chunk_tokens += chunk_tokens
            if chunk_prompt_chars > max_chunk_prompt_chars:
                max_chunk_prompt_chars = chunk_prompt_chars

            if chunk_parsed is not None:
                chunk_parsed_dicts.append(chunk_parsed)
                logger.info(
                    "[Swarm/Chunked] Chunk %d/%d: success (%d tokens)",
                    chunk_idx + 1, len(chunks), chunk_tokens,
                )
            else:
                logger.info(
                    "[Swarm/Chunked] Chunk %d/%d: failed (no parsed output)",
                    chunk_idx + 1, len(chunks),
                )

            # Soft-hold check AFTER each chunk completes (= before next).
            # The first chunk doesn't need this because execute() already
            # checked at the fanout→synth boundary; subsequent chunks need
            # the check to honor a hold that landed mid-synthesis.
            if chunk_idx < len(chunks) - 1 and self._hold_paused():
                self._raise_hold_paused()

        # All chunks failed → return None, existing fallback runs.
        if not chunk_parsed_dicts:
            logger.warning(
                "[Swarm/Chunked] All %d chunks failed — returning None",
                len(chunks),
            )
            return None, sum_chunk_tokens, None, max_chunk_prompt_chars, False

        # Phase 136 Part 09 Step 2 follow-up: 1-survivor short-circuit.
        # A degenerate meta call over a single chunk-parsed dict adds
        # wall-time, can silently destroy survivor data if the LLM
        # returns schema-valid-but-empty JSON, and provides no
        # cross-chunk synthesis benefit (there is no other chunk to
        # synthesize against).  Skip meta; treat as recovery-success
        # via dedup union; flag meta_failed=True so operators get
        # the chunked_meta_failed signal.
        if len(chunk_parsed_dicts) == 1:
            logger.info(
                "[Swarm/Chunked] Only 1 chunk succeeded — skipping "
                "meta-synthesis (no cross-chunk benefit); returning "
                "deduped union"
            )
            union = self._dedup_chunk_union(chunk_parsed_dicts)
            return union, sum_chunk_tokens, None, max_chunk_prompt_chars, True

        # Soft-hold check before meta dispatch.
        if self._hold_paused():
            self._raise_hold_paused()

        # Build meta synthesis input — same format as worker output joining.
        meta_workers: List[WorkerResult] = [
            WorkerResult(
                item_id=f"chunk-{i+1}",
                raw_output="",
                parsed=chunk_dict,
                success=True,
            )
            for i, chunk_dict in enumerate(chunk_parsed_dicts)
        ]
        logger.info(
            "[Swarm/Chunked] Meta-synthesis: %d/%d chunks succeeded, "
            "dispatching meta over %d partial syntheses",
            len(chunk_parsed_dicts), len(chunks), len(meta_workers),
        )
        meta_parsed, meta_tokens, meta_text, meta_prompt_chars, _ = (
            self._synthesize_single(
                meta_workers, synthesis_prompt, event_log=event_log,
            )
        )
        total_tokens = sum_chunk_tokens + meta_tokens
        max_prompt = max(max_chunk_prompt_chars, meta_prompt_chars)

        if meta_parsed is not None:
            logger.info(
                "[Swarm/Chunked] Meta-synthesis: success (%d tokens)",
                meta_tokens,
            )
            return meta_parsed, total_tokens, meta_text, max_prompt, False

        # Meta failed but chunks survived → return manually-deduped union.
        logger.warning(
            "[Swarm/Chunked] Meta-synthesis: failed; returning manually-"
            "deduped union of %d chunks",
            len(chunk_parsed_dicts),
        )
        union = self._dedup_chunk_union(chunk_parsed_dicts)
        return union, total_tokens, meta_text, max_prompt, True

    @staticmethod
    def _dedup_chunk_union(
        chunk_parsed_dicts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Union the chunk parsed dicts with the same defensiveness as
        concept_seeder.py:889-909's fallback dedup:

          - Concepts deduped by ``title.lower().strip()``.
          - Questions deduped by ``(text.lower().strip(),
            target_module.lower().strip())``.
          - Empty/missing titles → entry dropped.
          - Empty/missing question text → entry dropped.

        This keeps the chunked_meta_failed shape comparable to the
        single-call empty-synthesis fallback so downstream consumers
        don't need to learn a new path.
        """
        seen_titles: set = set()
        seen_questions: set = set()
        out_concepts: List[Dict[str, Any]] = []
        out_questions: List[Dict[str, Any]] = []

        for chunk_dict in chunk_parsed_dicts:
            for c in chunk_dict.get("concepts", []) or []:
                title = (c.get("title") or "").strip().lower()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    out_concepts.append(c)
            for q in chunk_dict.get("questions", []) or []:
                qtext = (q.get("question") or "").strip().lower()
                qmod = (q.get("target_module") or "").strip().lower()
                key = (qtext, qmod)
                if qtext and key not in seen_questions:
                    seen_questions.add(key)
                    out_questions.append(q)

        return {"concepts": out_concepts, "questions": out_questions}

    def _synthesize_single(
        self,
        worker_results: List[WorkerResult],
        synthesis_prompt: str,
        event_log: Optional[SwarmEventLogger] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str], int, bool]:
        """Single LLM call to aggregate successful worker results.

        This is the existing single-prompt synthesis path.  The chunked path
        (`_synthesize_chunked`) calls this method once per chunk plus once
        for the meta synthesis.

        Returns ``(parsed_result, token_count, raw_text, prompt_chars,
        meta_failed)``.

        - ``parsed_result`` is ``None`` on failure, timeout, or if no
          workers succeeded.
        - ``raw_text`` is the LLM response captured even on parse failure
          so callers (currently concept_seeder) can include head/tail in
          the diagnostic.  ``None`` when no LLM call was made or it timed
          out.
        - ``prompt_chars`` is the consolidation prompt size; ``0`` when no
          LLM call was made.
        - ``meta_failed`` is reserved for the chunked path (Step 2);
          single-call path always returns ``False``.

        Callers should fall back to merging raw worker outputs when
        ``parsed_result`` is ``None``.
        """
        successful = [r for r in worker_results if r.success and r.parsed]
        if not successful:
            logger.warning("[Swarm] No successful workers with parsed output — skipping synthesis")
            if event_log is not None:
                event_log.event("phase_skipped", phase="synthesis",
                                reason="no_successful_workers")
            return None, 0, None, 0, False

        outputs = "\n\n".join(
            f"### {r.item_id}\n```json\n{json.dumps(r.parsed, indent=2)}\n```"
            for r in successful
        )
        prompt = synthesis_prompt.replace("{worker_outputs}", outputs)
        prompt_chars = len(prompt)

        synth_model = getattr(self.coordinator_llm, "model", None)
        if event_log is not None:
            event_log.phase_start("synthesizer", model=synth_model,
                                  n_items=len(successful))
        s_t0 = time.monotonic()
        text, tokens = self._llm_call_with_timeout(
            prompt=prompt,
            system=SYNTHESIS_SYSTEM,
            temperature=0.5,
            timeout_s=self.synthesis_timeout_s,
            phase="synthesis",
            llm=self.coordinator_llm,
        )
        if text is None:
            if event_log is not None:
                event_log.phase_end("synthesizer", success=False,
                                    duration_s=time.monotonic() - s_t0,
                                    reason="timeout_or_error", tokens=tokens)
            return None, tokens, None, prompt_chars, False

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Synthesis returned unparseable JSON")
            if event_log is not None:
                event_log.parse_failure(where="synthesis",
                                        raw_chars=len(text),
                                        reason="json_parse_failed")
                event_log.phase_end("synthesizer", success=False,
                                    duration_s=time.monotonic() - s_t0,
                                    reason="parse_failed", tokens=tokens)
            return None, tokens, text, prompt_chars, False

        logger.info("[Swarm] Synthesis complete (%d tokens)", tokens)
        if event_log is not None:
            event_log.phase_end("synthesizer", success=True,
                                duration_s=time.monotonic() - s_t0,
                                tokens=tokens)
        return parsed, tokens, text, prompt_chars, False

    # -- Full execution -----------------------------------------------------

    def execute(
        self,
        items: List[WorkItem],
        coordinator_prompt: str,
        worker_fn: Callable[[WorkItem, WorkerAssignment], Optional[str]],
        synthesis_prompt: str,
        progress_fn: Optional[Callable[[int, int], None]] = None,
        *,
        run_id: Optional[str] = None,
        stage: Optional[str] = None,
        project_id: Optional[str] = None,
        log_dir: Optional[Any] = None,
        enable_event_log: bool = True,
        cancel_token: Any | None = None,
    ) -> Optional[SwarmResult]:
        """Run all three phases.

        Phase 96F: When the coordinator fails or times out, fan-out
        still runs with default per-worker assignments.  Only the
        synthesis phase is allowed to leave a None synthesis on the
        result — callers handle that by merging raw worker outputs.
        Returns None only when there are zero items to process.

        Phase 119 verbose-logging:
            run_id / stage / project_id are recorded in the per-swarm
            JSONL event log written to ``<data_dir>/logs/swarm/``.  Pass
            ``enable_event_log=False`` to suppress (used by tests that
            don't want side-effects on the data dir).  Callers that
            don't pass these get safe defaults — the file still gets
            written, just with placeholder identifiers.
        """
        if not items:
            return None

        t0 = time.monotonic()
        stats = SwarmStats(total_items=len(items))

        # Phase 127: prefer the per-call ``project_id`` kwarg (used by
        # the event logger) over ``self.project_id`` set in __init__,
        # so callers can override on a per-execute basis.  Save and
        # restore around the call so the helper methods (_hold_paused,
        # _raise_hold_paused) see the right project for the duration.
        _saved_project_id = self.project_id
        if project_id:
            self.project_id = project_id

        # ------------------------------------------------------------------
        # Phase 119: per-swarm-execution event log.  Best-effort — every
        # call site is wrapped in try/except inside the helper, so a
        # broken data_dir cannot fail the swarm.
        # ------------------------------------------------------------------
        event_log: Optional[SwarmEventLogger] = None
        if enable_event_log:
            try:
                resolved_log_dir = Path(log_dir) if log_dir is not None else default_log_dir()
                event_log = SwarmEventLogger(
                    run_id=run_id or f"adhoc-{int(t0 * 1000) & 0xFFFFFFFF:08x}",
                    stage=stage or "swarm",
                    project_id=self.project_id or "unknown",
                    log_dir=resolved_log_dir,
                )
            except Exception:
                logger.debug("swarm event logger init failed", exc_info=True)
                event_log = None

        # Phase 127: if we're already on soft-hold before any work
        # begins, exit immediately with paused=True — don't burn the
        # coordinator LLM call against a held endpoint.
        plan: Optional[CoordinatorPlan] = None
        coordinator_tokens = 0
        worker_results: List[WorkerResult] = []
        synthesis: Optional[Dict[str, Any]] = None
        synthesis_tokens = 0
        raw_synthesis_text: Optional[str] = None
        synthesis_prompt_chars = 0
        synthesis_meta_failed = False
        paused = False
        pause_info: Optional[Dict[str, str]] = None

        try:
            # Phase 127 (P127-F9): user-pause check at pre-coord boundary.
            # Mirrors the soft-hold check below; both must be honored.
            if cancel_token is not None and cancel_token.is_cancelled:
                cancel_token.raise_if_cancelled()
            if self._hold_paused():
                self._raise_hold_paused()

            # Phase 1: Coordinate (with timeout, may return empty plan)
            plan, coordinator_tokens = self._coordinate(
                items, coordinator_prompt, event_log=event_log,
            )
            if plan is None:
                logger.info(
                    "[Swarm] Coordinator failed/timed out — proceeding with "
                    "default assignments for %d items",
                    len(items),
                )
                plan = CoordinatorPlan(assignments=[])  # fan-out fills defaults
            stats.coordinator_tokens = coordinator_tokens

            # Phase 127: phase boundary — coord → fanout.  If a hold
            # took effect during coord, exit cleanly before fanout
            # spends N parallel worker calls against a held endpoint.
            # Phase 127 (P127-F9): also honor user-pause cancel_token here.
            if cancel_token is not None and cancel_token.is_cancelled:
                cancel_token.raise_if_cancelled()
            if self._hold_paused():
                self._raise_hold_paused()

            # Phase 2: Fan-out (t0 passed for overall wall-time tracking)
            logger.info("[Swarm] Entering fan-out phase (%d items)", len(items))
            if event_log is not None:
                event_log.phase_start("fanout",
                                      model=getattr(self.worker_llm, "model", None),
                                      n_items=len(items))
            fan_t0 = time.monotonic()
            worker_results = self._fan_out(
                items, plan, worker_fn, progress_fn, t0=t0, event_log=event_log,
                cancel_token=cancel_token,
            )
            if event_log is not None:
                event_log.phase_end(
                    "fanout",
                    success=any(r.success for r in worker_results),
                    duration_s=time.monotonic() - fan_t0,
                    n_succeeded=sum(1 for r in worker_results if r.success),
                    n_total=len(worker_results),
                )
            logger.info("[Swarm] Fan-out returned: %d results", len(worker_results))

            for r in worker_results:
                if r.success:
                    stats.workers_succeeded += 1
                else:
                    stats.workers_failed += 1

            # Phase 127: phase boundary — fanout → synth.  If a hold
            # took effect during fanout, skip synthesis.  Worker
            # results gathered so far are preserved on the SwarmResult
            # and callers can salvage them on retry.
            # Phase 127 (P127-F9): also honor user-pause cancel_token.
            if cancel_token is not None and cancel_token.is_cancelled:
                cancel_token.raise_if_cancelled()
            if self._hold_paused():
                self._raise_hold_paused()

            # Phase 3: Synthesize
            logger.info("[Swarm] Entering synthesis phase (%d/%d succeeded)",
                        stats.workers_succeeded, len(worker_results))
            (
                synthesis, synthesis_tokens,
                raw_synthesis_text, synthesis_prompt_chars,
                synthesis_meta_failed,
            ) = self._synthesize(
                worker_results, synthesis_prompt, event_log=event_log,
            )
            logger.info("[Swarm] Synthesis returned (tokens=%d)", synthesis_tokens)
            stats.synthesis_tokens = synthesis_tokens
        except HoldPausedError as hpe:
            # Phase 127: a soft-hold paused this swarm at a phase
            # boundary.  Log ONCE at INFO level for operator visibility
            # (per-dispatch checks log at DEBUG to avoid spam).  Salvage
            # whatever worker results we have, signal paused=True, and
            # return cleanly — caller treats this as "retry on next run"
            # rather than counting it as a permanent failure.
            paused = True
            pause_info = {
                "project_id": hpe.project_id,
                "endpoint_id": hpe.endpoint_id,
            }
            n_done = sum(1 for r in worker_results if r.success)
            logger.info(
                "Swarm paused on soft-hold (project=%s endpoint=%s) — "
                "%d/%d workers done at pause, %d remaining will retry next run",
                hpe.project_id, hpe.endpoint_id,
                n_done, len(items), max(len(items) - len(worker_results), 0),
            )
        except PipelinePausedError:
            # Phase 127 (P127-F9): user paused via the pipeline cancel_token.
            # Re-raise so the worker dispatcher (workers.py) propagates
            # PipelinePausedError up to build_orchestrator._run_worker,
            # which transitions the slot to inactive (the existing pattern
            # at build_orchestrator.py:402).  This is the difference from
            # soft-hold (HoldPausedError): a soft-hold returns a
            # ``paused=True`` SwarmResult so the caller retries next run,
            # but a user-pause must propagate so the pipeline state machine
            # flips PAUSING→PAUSED.  ``finally`` below restores project_id.
            n_done = sum(1 for r in worker_results if r.success)
            logger.info(
                "[Swarm] Paused by user cancel_token — "
                "%d/%d workers done at pause; pool shutdown with cancel_futures=True. "
                "In-flight LLM calls drain naturally (Python cannot safely cancel "
                "a thread mid-HTTP-request); no NEW workers will dispatch.",
                n_done, len(items),
            )
            raise
        finally:
            # Restore project_id in case execute() is called again with
            # different kwargs.
            self.project_id = _saved_project_id

        stats.wall_clock_seconds = time.monotonic() - t0

        # Phase 136 Part 09 Step 2: compute chunk_count from the number
        # of successful workers so the diagnostic classifier can
        # distinguish chunked from single-call paths without re-deriving.
        n_successful = sum(1 for r in worker_results if r.success and r.parsed)
        if n_successful > self.synthesis_chunk_max_workers:
            chunk_count = (
                (n_successful + self.synthesis_chunk_max_workers - 1)
                // self.synthesis_chunk_max_workers
            )
        else:
            chunk_count = 1

        result = SwarmResult(
            worker_results=worker_results,
            synthesis=synthesis,
            coordinator_plan=plan,
            stats=stats,
            event_log_path=str(event_log.path) if event_log and event_log.path else None,
            paused=paused,
            pause_info=pause_info,
            raw_synthesis_text=raw_synthesis_text,
            synthesis_prompt_chars=synthesis_prompt_chars,
            synthesis_meta_failed=synthesis_meta_failed,
            synthesis_chunk_count=chunk_count,
        )

        # Per-session summary line — closes out the JSONL file with the
        # high-level outcome the dashboard / agent will surface first.
        if event_log is not None:
            try:
                event_log.session_end(
                    success=(synthesis is not None
                             or stats.workers_succeeded > 0),
                    summary={
                        "total_items": stats.total_items,
                        "workers_succeeded": stats.workers_succeeded,
                        "workers_failed": stats.workers_failed,
                        "coordinator_tokens": stats.coordinator_tokens,
                        "worker_tokens": stats.worker_tokens,
                        "synthesis_tokens": stats.synthesis_tokens,
                        "wall_clock_seconds": round(stats.wall_clock_seconds, 3),
                        "synthesis_present": synthesis is not None,
                    },
                )
            except Exception:
                logger.debug("swarm event logger session_end failed",
                             exc_info=True)

        # §9 observability: emit per-run quality + throughput metrics.
        # Uses record_swarm_metrics() if token_telemetry exposes it, otherwise
        # falls back to a structured log line that downstream tooling can grep.
        try:
            from prep.services import token_telemetry as _tt
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

"""
PipelineOrchestrator — sequences the 11-stage enrichment pipeline.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from codrag.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildSlot,
    BuildType,
    build_orchestrator,
)

from .stages import (
    StageId,
    STAGE_BUILD_TYPE,
    FAST_SYNC_STAGES,
    DEEP_ENRICHMENT_STAGES,
    STAGE_TASK_ID,
    STAGE_MODEL_SLOT,
)
from .workers import PipelineRunPhase, PipelineRun, WorkerFactory

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Sequences the 11-stage pipeline in two groups.

    Uses BuildOrchestrator (SM-4) for individual stage execution and
    listens for completion events to advance the pipeline.

    Usage::

        pipeline.run_fast_sync("proj-1")
        pipeline.run_deep_enrichment("proj-1")
        pipeline.run_all("proj-1")  # fast sync then deep enrichment

        status = pipeline.status("proj-1")
    """

    def __init__(self, orchestrator: Optional[BuildOrchestrator] = None) -> None:
        self._orchestrator = orchestrator or build_orchestrator
        self._lock = threading.Lock()
        # Active pipeline runs: (project_id, group) → PipelineRun
        self._runs: Dict[tuple[str, str], PipelineRun] = {}
        # Per-project pipeline file loggers
        self._file_loggers: Dict[str, Any] = {}
        # Register for build completion events
        self._orchestrator.add_listener(self._on_build_transition)
        # Phase 25: cached crashed runs discovered at startup
        self._crashed_runs: List[Any] = []

    def _get_file_logger(self, project_id: str):
        """Get or create a PipelineFileLogger for a project."""
        if project_id not in self._file_loggers:
            try:
                from codrag.services.project_helpers import require_project
                from codrag.core.project_registry import project_index_dir
                project = require_project(project_id)
                idx_dir = project_index_dir(project)
                from codrag.services.pipeline_logger import PipelineFileLogger
                self._file_loggers[project_id] = PipelineFileLogger(idx_dir)
            except Exception:
                logger.debug("Could not create pipeline file logger for %s", project_id, exc_info=True)
                self._file_loggers[project_id] = None
        return self._file_loggers.get(project_id)

    # ── Public API ─────────────────────────────────────────────

    def run_fast_sync(self, project_id: str) -> bool:
        """Start the Fast Sync group (stages 1-5).  Returns False if already running."""
        return self._start_group(project_id, "fast_sync", FAST_SYNC_STAGES)

    def run_deep_enrichment(self, project_id: str) -> bool:
        """Start the Deep Enrichment group (stages 6-10).  Returns False if already running."""
        return self._start_group(project_id, "deep_enrichment", DEEP_ENRICHMENT_STAGES)

    def run_all(self, project_id: str) -> bool:
        """Start Fast Sync, then chain Deep Enrichment after it completes."""
        # Start fast sync; deep enrichment will be chained via the listener
        with self._lock:
            key = (project_id, "fast_sync")
            run = self._runs.get(key)
            if run and run.is_active:
                return False
            # Mark that deep should chain after fast
            self._chain_deep: Dict[str, bool] = getattr(self, "_chain_deep", {})
            self._chain_deep[project_id] = True
        return self.run_fast_sync(project_id)

    def status(self, project_id: str) -> Dict[str, Any]:
        """Get pipeline status for a project."""
        with self._lock:
            fast_run = self._runs.get((project_id, "fast_sync"))
            deep_run = self._runs.get((project_id, "deep_enrichment"))

        # Also get individual stage statuses from the build orchestrator
        stage_statuses = {}
        for stage_id in list(StageId):
            bt = STAGE_BUILD_TYPE[stage_id]
            slot = self._orchestrator.status(project_id, bt)
            stage_statuses[stage_id.value] = slot.to_dict()

        return {
            "fast_sync": fast_run.to_dict() if fast_run else None,
            "deep_enrichment": deep_run.to_dict() if deep_run else None,
            "stages": stage_statuses,
            "any_running": (
                (fast_run.is_active if fast_run else False) or
                (deep_run.is_active if deep_run else False)
            ),
        }

    def cancel_fast_sync(self, project_id: str) -> bool:
        """Cancel the Fast Sync group."""
        return self._cancel_group(project_id, "fast_sync")

    def cancel_deep_enrichment(self, project_id: str) -> bool:
        """Cancel the Deep Enrichment group."""
        return self._cancel_group(project_id, "deep_enrichment")

    def pause_fast_sync(self, project_id: str) -> bool:
        """Pause the Fast Sync group.  The current stage flushes partial
        results and stops.  Resume with ``resume_paused()``."""
        return self._pause_group(project_id, "fast_sync")

    def pause_deep_enrichment(self, project_id: str) -> bool:
        """Pause the Deep Enrichment group."""
        return self._pause_group(project_id, "deep_enrichment")

    def resume_paused(self, project_id: str, group: str) -> bool:
        """Resume a paused pipeline group from the stage it was paused at.

        Because all LLM-heavy stages write incremental results to disk
        (augmentations, epistemic entries, inferred edges, modules, group
        reasoning), restarting the same stage will skip already-processed
        items.
        """
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run:
                return False
            if run.error != "Paused by user":
                return False
            # Resume from the paused stage
            resume_from = run.current_stage_index

        logger.info(
            "Resuming paused run %s/%s from stage %d",
            project_id, group, resume_from,
        )

        if group == "fast_sync":
            stages = FAST_SYNC_STAGES
        elif group == "deep_enrichment":
            stages = DEEP_ENRICHMENT_STAGES
        else:
            return False

        chain_deep = getattr(run, '_chain_deep', False)
        return self._start_group(
            project_id, group, stages,
            chain_deep=chain_deep, resume_from=resume_from,
        )

    def clear_project(self, project_id: str) -> None:
        """Remove all pipeline state for a project."""
        with self._lock:
            keys = [k for k in self._runs if k[0] == project_id]
            for k in keys:
                del self._runs[k]
        self._orchestrator.clear_project(project_id)
        # Clear cached file logger so it doesn't reference stale paths
        self._file_loggers.pop(project_id, None)

    # ── Internal ───────────────────────────────────────────────

    @staticmethod
    def _is_deep_enrichment_auto(project_id: str) -> bool:
        """Check if deep enrichment should auto-chain after fast sync.

        Returns True if either:
        - deep_enrichment.mode is 'auto', OR
        - fast_sync.auto is True (user expectation: AUTO runs the full pipeline)
        """
        try:
            from codrag.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            deep_mode = (config.get("deep_enrichment") or {}).get("mode", "manual")
            fast_auto = (config.get("fast_sync") or {}).get("auto", False)
            return deep_mode == "auto" or fast_auto
        except Exception:
            return False

    def _start_group(
        self, project_id: str, group: str, stages: List[StageId],
        chain_deep: bool = False, resume_from: int = 0,
    ) -> bool:
        """Start a group of stages sequentially.

        Returns False if this group OR any other group for the same
        project is already active — groups share files and must not
        run concurrently.
        """
        with self._lock:
            # Block if this group is already running
            key = (project_id, group)
            existing = self._runs.get(key)
            if existing and existing.is_active:
                return False

            # Block if ANY other group for the same project is running.
            # Fast Sync and Deep Enrichment share trace files (knowledge,
            # modules, epistemic) and running them concurrently causes
            # data corruption (e.g. knowledge embedding "doubling").
            for run_key, run_obj in self._runs.items():
                if run_key[0] == project_id and run_key[1] != group and run_obj.is_active:
                    logger.warning(
                        "Cannot start %s/%s — %s is already active for this project",
                        project_id, group, run_key[1],
                    )
                    return False

            run = PipelineRun(
                project_id=project_id,
                group=group,
                stages=list(stages),
                phase=PipelineRunPhase.RUNNING,
                started_at=time.time(),
                current_stage_index=resume_from,
            )
            self._runs[key] = run

        # Start pipeline file logger for this run
        pfl = self._get_file_logger(project_id)
        if pfl:
            pfl.start_run(group, [s.value for s in stages], project_id=project_id)

        # Phase 25: persist intent to journal before starting work
        try:
            from codrag.services.pipeline_journal import journal
            run_id = journal.start_run(
                project_id, group,
                [s.value for s in stages],
                chain_deep=chain_deep,
            )
            run.journal_run_id = run_id
            # If resuming, mark already-completed stages
            if resume_from > 0:
                for i in range(resume_from):
                    stage_val = stages[i].value
                    run.stage_results[stage_val] = "completed"
                    journal.stage_completed(run_id, stage_val)
                journal.stage_started(run_id, stages[resume_from].value, resume_from)
        except Exception:
            logger.debug("Journal write failed (non-fatal)", exc_info=True)

        # Start the first (or resumed) stage
        self._advance_pipeline(run)
        return True

    def _advance_pipeline(self, run: PipelineRun) -> None:
        """Advance to the next stage in the pipeline, or finish."""
        pfl = self._get_file_logger(run.project_id)
        if run.current_stage_index >= len(run.stages):
            # All stages complete
            with self._lock:
                run.phase = PipelineRunPhase.COMPLETED
                run.finished_at = time.time()
            logger.info(
                "Pipeline %s/%s completed in %.1fs",
                run.project_id, run.group,
                (run.finished_at or 0) - (run.started_at or 0),
            )
            if pfl:
                pfl.end_run("completed")
            # VRAM lifecycle: release group models via state machine (falls back to legacy)
            self._release_group_models_via_sm(run)
            # Phase 25: journal — mark run completed + cleanup checkpoint
            self._journal_run_completed(run)
            # After any group completes, trigger CodeIndex build so
            # /context search works and file tree status badges update.
            if run.group in ("fast_sync", "deep_enrichment"):
                self._trigger_code_index_build(run.project_id, pfl)
            # Chain deep enrichment after fast sync if configured or explicitly requested
            if run.group == "fast_sync":
                should_chain = False
                chain_reason = "none"
                # 1. Explicit chain from run_all()
                chain_deep = getattr(self, "_chain_deep", {})
                if chain_deep.pop(run.project_id, False):
                    should_chain = True
                    chain_reason = "explicit_run_all"
                # 2. Auto-chain: check persisted pipeline config
                if not should_chain:
                    is_auto = self._is_deep_enrichment_auto(run.project_id)
                    logger.info(
                        "Auto-chain check for %s: _is_deep_enrichment_auto=%s",
                        run.project_id, is_auto,
                    )
                    if is_auto:
                        should_chain = True
                        chain_reason = "auto_config"
                # Phase 26 (S-26.5): Budget throttle — skip auto-chain if budget exhausted
                if should_chain and chain_reason != "explicit_run_all":
                    try:
                        from codrag.services.pipeline_budget import budget as _budget
                        if not _budget.check_allowed(run.project_id):
                            usage = _budget.get_usage(run.project_id)
                            logger.info(
                                "Budget exhausted for %s — skipping auto-chain "
                                "(used %d/%d tokens, resets in %ds)",
                                run.project_id,
                                usage["tokens_used"], usage["max_tokens"],
                                usage["window_resets_in"],
                            )
                            if pfl:
                                pfl.log("fast_sync", f"Auto-chain SKIPPED: budget exhausted ({usage['tokens_used']}/{usage['max_tokens']} tokens)")
                            should_chain = False
                            chain_reason = "budget_exhausted"
                    except Exception:
                        pass  # Budget module unavailable — allow chain

                if should_chain:
                    logger.info(
                        "Chaining deep enrichment after fast sync for %s (reason=%s)",
                        run.project_id, chain_reason,
                    )
                    try:
                        started = self.run_deep_enrichment(run.project_id)
                        logger.info(
                            "Deep enrichment chain result for %s: started=%s",
                            run.project_id, started,
                        )
                        if pfl:
                            pfl.log("fast_sync", f"Auto-chained deep enrichment: started={started}, reason={chain_reason}")
                    except Exception as chain_exc:
                        logger.exception(
                            "Failed to chain deep enrichment for %s: %s",
                            run.project_id, chain_exc,
                        )
                        if pfl:
                            pfl.log("fast_sync", f"Auto-chain FAILED: {chain_exc}")
                else:
                    logger.info(
                        "NOT chaining deep enrichment for %s (reason=%s)",
                        run.project_id, chain_reason,
                    )
            return

        stage = run.stages[run.current_stage_index]
        build_type = STAGE_BUILD_TYPE[stage]

        # VRAM lifecycle: acquire model via state machine (handles unload of previous)
        task_id = STAGE_TASK_ID.get(stage)
        if task_id:
            try:
                from codrag.core.model_awareness import model_awareness
                slot = model_awareness.acquire(task_id)
                if slot is None:
                    logger.warning(
                        "ModelAwareness: no model configured for task %s (stage %s) — "
                        "falling back to legacy VRAM lifecycle",
                        task_id, stage.value,
                    )
                    self._maybe_unload_previous_model(run, stage)
            except Exception as e:
                logger.warning(
                    "ModelAwareness acquire failed for %s: %s — falling back",
                    task_id, e,
                )
                self._maybe_unload_previous_model(run, stage)
        else:
            self._maybe_unload_previous_model(run, stage)

        logger.info(
            "Pipeline %s/%s — starting stage %d/%d: %s",
            run.project_id, run.group,
            run.current_stage_index + 1, len(run.stages),
            stage.value,
        )
        if pfl:
            pfl.stage_start(stage.value, {
                "stage_index": run.current_stage_index,
                "total_stages": len(run.stages),
                "group": run.group,
            })

        # Phase 25: journal — record stage start
        self._journal_stage_started(run, stage)

        # Phase 25: checkpoint — backup trace files before destructive stages
        self._create_checkpoint_if_needed(run, stage)

        worker = WorkerFactory.create_worker(run.project_id, stage)
        started = self._orchestrator.start(run.project_id, build_type, worker)

        if not started:
            # Build slot is stuck in RUNNING/QUEUED from a prior run.
            # Force-reset it and retry once so the pipeline doesn't stall.
            logger.warning(
                "Stage %s slot already active for %s — force-resetting stuck slot",
                stage.value, run.project_id,
            )
            self._orchestrator.cancel(run.project_id, build_type)
            # Small delay to let the slot settle after cancel
            time.sleep(0.1)
            started = self._orchestrator.start(run.project_id, build_type, worker)
            if not started:
                raise RuntimeError(
                    f"Cannot start stage {stage.value}: build slot {build_type.value} "
                    f"is stuck for project {run.project_id}"
                )

    def _on_build_transition(
        self,
        project_id: str,
        build_type: BuildType,
        old_phase: BuildPhase,
        new_phase: BuildPhase,
    ) -> None:
        """Called by BuildOrchestrator when a build slot transitions.

        Advances the pipeline if the completed build matches the current stage.
        """
        if new_phase not in (BuildPhase.COMPLETED, BuildPhase.FAILED):
            return

        with self._lock:
            # Find any active pipeline run for this project where the current
            # stage matches this build type
            matching_run: Optional[PipelineRun] = None
            for key, run in self._runs.items():
                if run.project_id != project_id or not run.is_active:
                    continue
                current = run.current_stage
                if current and STAGE_BUILD_TYPE[current] == build_type:
                    matching_run = run
                    break

            if matching_run is None:
                return

            stage = matching_run.current_stage
            if stage is None:
                return

            if new_phase == BuildPhase.COMPLETED:
                matching_run.stage_results[stage.value] = "completed"
                matching_run.current_stage_index += 1
                logger.info(
                    "Pipeline %s/%s — stage %s completed",
                    project_id, matching_run.group, stage.value,
                )
                # Phase 44C: release model via state machine
                completed_task = STAGE_TASK_ID.get(stage)
                if completed_task:
                    try:
                        from codrag.core.model_awareness import model_awareness
                        # Don't unload yet — next stage might use the same model.
                        # acquire() in _advance_pipeline will handle the swap.
                        model_awareness.release(completed_task, unload=False)
                    except Exception:
                        logger.debug("ModelAwareness release failed for %s", completed_task, exc_info=True)
                # Pipeline file logger
                pfl = self._get_file_logger(project_id)
                if pfl:
                    slot = self._orchestrator.status(project_id, build_type)
                    pfl.stage_end(stage.value, "completed", data={
                        "result": slot.result,
                        "duration": slot.duration_seconds,
                    })
                    pfl.transition(build_type.value, old_phase.value, new_phase.value,
                                   f"Stage {stage.value} completed")
                # Phase 25: journal — record stage completion
                self._journal_stage_completed(matching_run, stage)
            elif new_phase == BuildPhase.FAILED:
                matching_run.stage_results[stage.value] = "failed"
                slot = self._orchestrator.status(project_id, build_type)
                matching_run.phase = PipelineRunPhase.FAILED
                matching_run.finished_at = time.time()
                matching_run.error = f"Stage {stage.value} failed: {slot.error}"
                logger.error(
                    "Pipeline %s/%s — stage %s failed: %s",
                    project_id, matching_run.group, stage.value, slot.error,
                )
                # Pipeline file logger
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.stage_end(stage.value, "failed", error=slot.error, data={
                        "duration": slot.duration_seconds,
                    })
                    pfl.end_run("failed", error=slot.error)
                # Phase 25: journal — record stage failure
                self._journal_stage_failed(matching_run, stage, slot.error or "Unknown error")
                # VRAM lifecycle: release all group models via state machine
                self._release_group_models_via_sm(matching_run)
                return

        # Advance outside the lock — wrapped in try/except so a failure
        # in stage creation marks the run FAILED instead of silently stalling.
        if matching_run and matching_run.is_active:
            try:
                self._advance_pipeline(matching_run)
            except Exception as exc:
                logger.exception(
                    "Pipeline %s/%s — _advance_pipeline failed after stage %s: %s",
                    matching_run.project_id, matching_run.group,
                    stage.value if stage else "?", exc,
                )
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.log(stage.value if stage else "unknown",
                            f"_advance_pipeline failed: {exc}")
                    pfl.end_run("failed", error=str(exc))
                with self._lock:
                    matching_run.phase = PipelineRunPhase.FAILED
                    matching_run.finished_at = time.time()
                    matching_run.error = f"Failed to advance after {stage.value if stage else '?'}: {exc}"

    def _cancel_group(self, project_id: str, group: str) -> bool:
        """Cancel a running group."""
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run or not run.is_active:
                return False

            current = run.current_stage
            run.phase = PipelineRunPhase.FAILED
            run.finished_at = time.time()
            run.error = "Cancelled by user"

        # Cancel the current stage's build
        if current:
            bt = STAGE_BUILD_TYPE[current]
            self._orchestrator.cancel(project_id, bt)

        # Phase 25: journal — record cancellation
        if run.journal_run_id:
            try:
                from codrag.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)
            except Exception:
                logger.debug("Journal cancel write failed", exc_info=True)
        return True

    def _pause_group(self, project_id: str, group: str) -> bool:
        """Pause a running group.  The current stage's worker will
        cooperatively stop after flushing partial results to disk.

        The run is left in FAILED state with error="Paused by user"
        so the orchestrator's _on_build_transition handler won't
        advance to the next stage.  ``resume_paused()`` restarts from
        the paused stage — incremental workers skip already-done items.
        """
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run or not run.is_active:
                return False

            current = run.current_stage

        # Signal the worker to pause (not cancel)
        if current:
            bt = STAGE_BUILD_TYPE[current]
            self._orchestrator.pause(project_id, bt)

        # Create a file-level checkpoint before stopping
        self._create_checkpoint_if_needed(run, current) if current else None

        # Mark the pipeline run as paused
        with self._lock:
            run.phase = PipelineRunPhase.FAILED
            run.finished_at = time.time()
            run.error = "Paused by user"

        # Journal: record pause
        if run.journal_run_id:
            try:
                from codrag.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)  # Reuse cancelled for now
            except Exception:
                logger.debug("Journal pause write failed", exc_info=True)

        logger.info(
            "Pipeline paused: %s/%s at stage %s (index %d)",
            project_id, group,
            current.value if current else "?",
            run.current_stage_index,
        )
        return True

    # ── VRAM Lifecycle ─────────────────────────────────────────────

    def _release_group_models_via_sm(self, run: PipelineRun) -> None:
        """Release all models used by a pipeline group via the state machine.

        Phase 44C: Delegates to ModelAwareness.release_group() which handles
        persistent model preservation and eviction recovery.  Falls back to
        the legacy _unload_group_models() if the state machine fails.
        """
        task_ids = [
            STAGE_TASK_ID[stage]
            for stage in run.stages
            if stage in STAGE_TASK_ID
        ]
        try:
            from codrag.core.model_awareness import model_awareness
            model_awareness.release_group(task_ids, unload=True)
        except Exception as e:
            logger.warning(
                "ModelAwareness release_group failed, falling back to legacy: %s", e
            )
            self._unload_group_models(run)

    def _maybe_unload_previous_model(self, run: PipelineRun, next_stage: StageId) -> None:
        """Unload the previous stage's LLM model if the model identity is changing.

        Phase 44: Tracks by (endpoint_id, model) tuple instead of slot name.
        This works correctly in both structured and mapped assignment modes.

        Prevents two models from occupying VRAM simultaneously.
        Non-fatal: logs warnings on failure but never blocks the pipeline.
        """
        from codrag.server import _get_model_identity_for_task, _get_llm_client_for_task

        next_task = STAGE_TASK_ID.get(next_stage)
        next_identity = _get_model_identity_for_task(next_task) if next_task else None

        # Determine the previous stage's model identity
        prev_task: Optional[str] = None
        prev_identity = None
        if run.current_stage_index > 0:
            prev_stage = run.stages[run.current_stage_index - 1]
            prev_task = STAGE_TASK_ID.get(prev_stage)
            prev_identity = _get_model_identity_for_task(prev_task) if prev_task else None

        # No transition needed if same model or previous had no model
        if prev_identity is None or prev_identity == next_identity:
            return

        # Unload the previous model
        try:
            client = _get_llm_client_for_task(prev_task)
            if client:
                logger.info(
                    "VRAM lifecycle: unloading %s model (%s) before stage %s",
                    prev_task, client.model, next_stage.value,
                )
                client.unload()
        except Exception as e:
            logger.warning("VRAM lifecycle: failed to unload model for task %s: %s", prev_task, e)

    def _unload_group_models(self, run: PipelineRun) -> None:
        """Unload any LLM models used by the completed/failed group.

        Phase 44: Tracks unique (endpoint_id, model) identities across the
        group's stages.  Deduplicates so shared models are only unloaded once.

        Called when a pipeline group finishes to free VRAM for the next
        group or for the user's own work.
        """
        from codrag.server import _get_model_identity_for_task, _get_llm_client_for_task

        # Collect unique model identities used by this group
        identities_seen: dict = {}  # identity → task_id (for client resolution)
        for stage in run.stages:
            task_id = STAGE_TASK_ID.get(stage)
            if not task_id:
                continue
            identity = _get_model_identity_for_task(task_id)
            if identity and identity not in identities_seen:
                identities_seen[identity] = task_id

        for identity, task_id in identities_seen.items():
            try:
                client = _get_llm_client_for_task(task_id)
                if client:
                    logger.info("VRAM lifecycle: unloading %s model (%s) — group %s finished",
                                task_id, client.model, run.group)
                    client.unload()
            except Exception as e:
                logger.warning("VRAM lifecycle: failed to unload model for task %s after group: %s", task_id, e)

    # ── CodeIndex Build (post-pipeline) ─────────────────────────────

    def _trigger_code_index_build(self, project_id: str, pfl: Any = None) -> None:
        """Trigger a CodeIndex build after deep enrichment completes.

        The pipeline builds KnowledgeIndex (knowledge_documents.json) but the
        /context search endpoint requires CodeIndex (documents.json +
        embeddings.npy).  This fires the build in the background so search
        works immediately after the pipeline finishes.
        """
        try:
            from codrag.services.build_manager import build_manager
            from codrag.services.project_helpers import require_project

            project = require_project(project_id)
            cfg = project.config or {}
            include_globs = cfg.get("include_globs") or None
            exclude_globs = cfg.get("exclude_globs") or None
            max_file_bytes = int(cfg.get("max_file_bytes") or 500_000)
            hard_limit_bytes = int(cfg.get("hard_limit_bytes") or 100_000_000)
            included_paths = cfg.get("included_paths") or None

            started = build_manager.start_project_build(
                project, None, include_globs, exclude_globs,
                max_file_bytes, hard_limit_bytes,
                included_paths=included_paths,
            )
            logger.info(
                "CodeIndex build triggered for %s after pipeline: started=%s",
                project_id, started,
            )
            if pfl:
                pfl.log("code_index", f"CodeIndex build triggered: started={started}")
        except Exception as e:
            logger.warning("Failed to trigger CodeIndex build for %s: %s", project_id, e)
            if pfl:
                pfl.log("code_index", f"CodeIndex build FAILED: {e}")

    # ── Phase 25: Journal Helpers ─────────────────────────────────

    def _journal_stage_started(self, run: PipelineRun, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_started(run.journal_run_id, stage.value, run.current_stage_index)
        except Exception:
            logger.debug("Journal stage_started write failed", exc_info=True)

    def _journal_stage_completed(self, run: PipelineRun, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_completed(run.journal_run_id, stage.value)
        except Exception:
            logger.debug("Journal stage_completed write failed", exc_info=True)

    def _journal_stage_failed(self, run: PipelineRun, stage: StageId, error: str) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_failed(run.journal_run_id, stage.value, error)
        except Exception:
            logger.debug("Journal stage_failed write failed", exc_info=True)

    def _journal_run_completed(self, run: PipelineRun) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.run_completed(run.journal_run_id)
        except Exception:
            logger.debug("Journal run_completed write failed", exc_info=True)
        # Cleanup checkpoint
        try:
            from codrag.services.pipeline_journal import journal as j
            entry = j.get_run(run.journal_run_id)
            if entry and entry.checkpoint_path:
                from codrag.services.pipeline_checkpoint import cleanup_checkpoint
                cleanup_checkpoint(entry.checkpoint_path)
        except Exception:
            logger.debug("Checkpoint cleanup failed", exc_info=True)

    def _create_checkpoint_if_needed(self, run: PipelineRun, stage: StageId) -> None:
        """Create a checkpoint before destructive stages."""
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_checkpoint import create_checkpoint, CHECKPOINT_STAGES
            if stage.value not in CHECKPOINT_STAGES:
                return
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            project = require_project(run.project_id)
            idx_dir = project_index_dir(project)
            cp_path = create_checkpoint(idx_dir, run.journal_run_id, stage.value)
            if cp_path:
                from codrag.services.pipeline_journal import journal
                journal.set_checkpoint(run.journal_run_id, cp_path)
        except Exception:
            logger.debug("Checkpoint creation failed (non-fatal)", exc_info=True)

    # ── Phase 25: Crash Recovery ──────────────────────────────────

    def startup_recovery(self) -> List[Any]:
        """Called once on daemon startup.  Detects crashed runs.

        Returns list of JournalEntry dicts for the UI to display.
        """
        try:
            from codrag.services.pipeline_journal import journal
            crashed = journal.recover_crashed_runs()
            self._crashed_runs = crashed
            if crashed:
                logger.warning(
                    "Crash recovery: found %d crashed pipeline run(s)", len(crashed)
                )
                # Auto-heal: verify trace files for each crashed project
                for entry in crashed:
                    try:
                        from codrag.services.pipeline_checkpoint import verify_trace_files, auto_heal
                        from codrag.core.project_registry import project_index_dir
                        from codrag.services.project_helpers import require_project
                        project = require_project(entry.project_id)
                        idx_dir = project_index_dir(project)
                        valid, corrupt = verify_trace_files(idx_dir)
                        if not valid:
                            logger.warning(
                                "Corrupt trace files for %s: %s — attempting auto-heal",
                                entry.project_id, corrupt,
                            )
                            results = auto_heal(idx_dir, entry.checkpoint_path)
                            logger.info("Auto-heal results for %s: %s", entry.project_id, results)
                    except Exception:
                        logger.debug("Auto-heal failed for %s", entry.project_id, exc_info=True)
            return [e.to_dict() for e in crashed]
        except Exception:
            logger.debug("Startup recovery failed", exc_info=True)
            return []

    def get_crashed_runs(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get crashed runs (for UI display)."""
        try:
            from codrag.services.pipeline_journal import journal
            entries = journal.get_crashed_runs(project_id)
            return [e.to_dict() for e in entries]
        except Exception:
            return []

    def resume_crashed_run(self, run_id: str) -> bool:
        """Resume a crashed pipeline run from the stage it was on.

        Creates a new run starting from the crashed stage.
        Returns True if resumed successfully.
        """
        try:
            from codrag.services.pipeline_journal import journal
            entry = journal.get_run(run_id)
            if not entry or entry.status != "crashed":
                return False

            # Resolve the crashed run
            journal.resolve_crashed_run(run_id, "resumed")

            # Determine stages and resume point
            if entry.group == "fast_sync":
                stages = FAST_SYNC_STAGES
            elif entry.group == "deep_enrichment":
                stages = DEEP_ENRICHMENT_STAGES
            else:
                return False

            resume_from = entry.current_stage_index
            chain_deep = entry.chain_deep

            logger.info(
                "Resuming crashed run %s: %s/%s from stage %d (%s)",
                run_id, entry.project_id, entry.group,
                resume_from, entry.current_stage,
            )

            return self._start_group(
                entry.project_id, entry.group, stages,
                chain_deep=chain_deep, resume_from=resume_from,
            )
        except Exception:
            logger.exception("Resume failed for run %s", run_id)
            return False

    def discard_crashed_run(self, run_id: str) -> bool:
        """Discard a crashed pipeline run without resuming."""
        try:
            from codrag.services.pipeline_journal import journal
            return journal.resolve_crashed_run(run_id, "discarded")
        except Exception:
            return False


# ── SSE Event Bridge ─────────────────────────────────────────────

def _create_sse_bridge(pipeline: PipelineOrchestrator) -> None:
    """Register a BuildOrchestrator listener that emits SSE events
    for pipeline stage transitions.  Called once at module init."""

    def _on_transition(
        project_id: str,
        build_type: BuildType,
        old_phase: BuildPhase,
        new_phase: BuildPhase,
    ) -> None:
        try:
            from codrag.core.events import get_event_bus, get_progress_manager

            bus = get_event_bus()
            pm = get_progress_manager()

            # Emit a task-level event for the build type
            task_id = f"pipeline_{build_type.value}_{project_id}"

            if new_phase == BuildPhase.RUNNING:
                bus.emit("task", {
                    "task_id": task_id,
                    "status": "running",
                    "project_id": project_id,
                    "build_type": build_type.value,
                })
            elif new_phase == BuildPhase.COMPLETED:
                bus.emit("task", {
                    "task_id": task_id,
                    "status": "completed",
                    "project_id": project_id,
                    "build_type": build_type.value,
                })
            elif new_phase == BuildPhase.FAILED:
                slot = pipeline._orchestrator.status(project_id, build_type)
                bus.emit("task", {
                    "task_id": task_id,
                    "status": "failed",
                    "project_id": project_id,
                    "build_type": build_type.value,
                    "error": slot.error,
                })

            # Also emit pipeline group-level status
            status = pipeline.status(project_id)
            bus.emit("pipeline_status", {
                "project_id": project_id,
                **status,
            })
        except Exception:
            logger.debug("SSE bridge emit failed (event bus not ready)", exc_info=True)

    pipeline._orchestrator.add_listener(_on_transition)


# ── Module-level singleton ───────────────────────────────────────
pipeline_orchestrator = PipelineOrchestrator()
_create_sse_bridge(pipeline_orchestrator)

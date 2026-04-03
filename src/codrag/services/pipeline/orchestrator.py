"""
PipelineOrchestrator — sequences the 11-stage enrichment pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from codrag.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildSlot,
    BuildType,
    build_orchestrator,
)


class _WriteGuardBlocked(Exception):
    """Raised when the write guard detects data loss and blocks pipeline advancement."""
    pass

from .stages import (
    StageId,
    STAGE_BUILD_TYPE,
    FAST_SYNC_STAGES,
    DEEP_ENRICHMENT_STAGES,
    STAGE_TASK_ID,
    STAGE_MODEL_SLOT,
    QueueType,
    STAGE_QUEUE_TYPE,
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    STAGE_CONFIDENCE_FIELD,
)
from .scheduler import pipeline_scheduler
from .workers import PipelineRunPhase, PipelineRun, WorkerFactory
from .state_machine import (
    PipelineGroupStateMachine,
    PipelineState,
    Event,
    ActiveProjectGuard,
)

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
        # Active pipeline runs: (project_id, group) → state machine
        self._runs: Dict[tuple[str, str], PipelineGroupStateMachine] = {}
        # Default guard: block START for inactive projects
        self._default_guard = ActiveProjectGuard()
        # Per-project pipeline file loggers
        self._file_loggers: Dict[str, Any] = {}
        # Register for build completion events
        self._orchestrator.add_listener(self._on_build_transition)
        # Phase 25: cached crashed runs discovered at startup
        self._crashed_runs: List[Any] = []
        # Phase 49: per-run metadata objects
        self._run_metadata: Dict[tuple[str, str], Any] = {}  # (project_id, group) → PipelineRunMetadata
        # Phase 53: track which projects are in incremental mode
        self._incremental_runs: set[str] = set()
        # Explicit chain flag: run_all() sets this so deep_enrichment chains after fast_sync
        self._chain_deep: Dict[str, bool] = {}

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

    @staticmethod
    def _persist_incremental_flag(project_id: str, is_incremental: bool) -> None:
        """Persist the incremental run flag to disk so it survives daemon restart."""
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            state_path = idx_dir / "pipeline_state.json"
            state: Dict[str, Any] = {}
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text())
                except Exception:
                    state = {}
            state["incremental_pending"] = is_incremental
            state["incremental_set_at"] = time.time()
            state_path.write_text(json.dumps(state, indent=2))
        except Exception:
            logger.debug("Failed to persist incremental flag for %s", project_id, exc_info=True)

    @staticmethod
    def _read_and_clear_incremental_flag(project_id: str) -> bool:
        """Read the persisted incremental flag and clear it atomically."""
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            state_path = idx_dir / "pipeline_state.json"
            if not state_path.exists():
                return False
            state = json.loads(state_path.read_text())
            was_incremental = state.get("incremental_pending", False)
            state["incremental_pending"] = False
            state["incremental_cleared_at"] = time.time()
            state_path.write_text(json.dumps(state, indent=2))
            return was_incremental
        except Exception:
            logger.debug("Failed to read incremental flag for %s", project_id, exc_info=True)
            return False

    @staticmethod
    def _prune_stale_derivative_files(project_id: str, pfl: Any = None) -> None:
        """Prune derivative files that reference nodes no longer in the trace graph.

        Called after the STRUCTURAL stage completes.  Removes edges from
        trace_inferred_edges.jsonl whose source or target file paths are
        not present in the current trace_nodes.jsonl.
        """
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))

            nodes_path = idx_dir / "trace_nodes.jsonl"
            inferred_path = idx_dir / "trace_inferred_edges.jsonl"

            if not inferred_path.exists() or not nodes_path.exists():
                return

            # Build set of valid file paths from current trace graph
            valid_paths: set[str] = set()
            with open(nodes_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        node = json.loads(line)
                        fp = node.get("file_path", "")
                        if fp:
                            valid_paths.add(fp)
                    except json.JSONDecodeError:
                        continue

            if not valid_paths:
                return  # Empty graph — don't prune (safety)

            # Read existing inferred edges and keep only those with valid refs
            kept = []
            pruned = 0
            with open(inferred_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        edge = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    src = edge.get("source", "").replace("file:", "", 1)
                    tgt = edge.get("target", "").replace("file:", "", 1)
                    if src in valid_paths and tgt in valid_paths:
                        kept.append(line)
                    else:
                        pruned += 1

            if pruned == 0:
                logger.debug("No stale inferred edges to prune for %s", project_id)
                return

            # Rewrite the file with only valid edges
            with open(inferred_path, "w") as f:
                for line in kept:
                    f.write(line + "\n")

            logger.info(
                "Pruned %d stale inferred edges for %s (%d kept)",
                pruned, project_id, len(kept),
            )
            if pfl:
                pfl.log("structural", f"Pruned {pruned} stale inferred edges ({len(kept)} kept)")

            # Also prune the inferred manifest's file hash entries
            inferred_manifest = idx_dir / "trace_inferred_manifest.json"
            if inferred_manifest.exists():
                try:
                    manifest = json.loads(inferred_manifest.read_text())
                    file_hashes = manifest.get("file_hashes", {})
                    if file_hashes:
                        pruned_hashes = {
                            k: v for k, v in file_hashes.items()
                            if k in valid_paths
                        }
                        if len(pruned_hashes) < len(file_hashes):
                            manifest["file_hashes"] = pruned_hashes
                            inferred_manifest.write_text(json.dumps(manifest, indent=2))
                except Exception:
                    logger.debug("Failed to prune inferred manifest (non-fatal)", exc_info=True)

        except Exception:
            logger.debug(
                "Failed to prune stale derivative files for %s (non-fatal)",
                project_id, exc_info=True,
            )

    # ── Public API ─────────────────────────────────────────────

    def run_fast_sync(self, project_id: str, force_from_start: bool = False) -> bool:
        """Start the Fast Sync group (stages 1-5).

        By default, detects which stages already have output on disk and
        resumes from the first incomplete stage.  Pass ``force_from_start=True``
        to re-run all stages from scratch (e.g. after file changes that
        invalidate the trace graph).

        Phase 53: When all stages are "complete" on disk, checks for stale
        or untraced files via check_coverage_gap().  If changes are detected,
        re-runs from Stage 1 (structural) so the trace graph picks up the
        new/changed files.  Uses "incremental" mode which prevents
        manifest-timestamp-based cascade invalidation of downstream stages
        — their workers already handle incrementality internally.
        """
        incremental = False
        resume = 0 if force_from_start else self._detect_resume_point(project_id, FAST_SYNC_STAGES)

        # Phase 60A: Log the trigger decision to pipeline file logger
        pfl = self._get_file_logger(project_id)

        if force_from_start and pfl:
            pfl.decision("mode_selection", "force_from_start", {
                "group": "fast_sync",
                "reason": "Caller requested force_from_start=True",
                "resume_point": 0,
            })

        if resume >= len(FAST_SYNC_STAGES):
            # Phase 53: All manifests exist — but are there stale files?
            try:
                gap = self.check_coverage_gap(project_id)

                if pfl:
                    pfl.decision("coverage_gap", "checked", {
                        "group": "fast_sync",
                        "needs_rebuild": gap.get("needs_rebuild", False),
                        "stale": gap.get("stale", 0),
                        "untraced": gap.get("untraced", 0),
                        "coverage_pct": gap.get("coverage_pct", 0),
                        "total_nodes": gap.get("total_nodes", 0),
                    })

                if gap["needs_rebuild"]:
                    stale = gap.get("stale", 0)
                    untraced = gap.get("untraced", 0)
                    logger.info(
                        "All fast_sync stages complete but %d stale + %d untraced "
                        "files for %s — re-running from structural for incremental update",
                        stale, untraced, project_id,
                    )
                    resume = 0  # Start from Stage 1 to rebuild trace graph
                    # Mark as incremental: all stages already have data,
                    # workers will skip already-processed items, we should
                    # NOT cascade-invalidate downstream via manifest mtimes.
                    incremental = True

                    if pfl:
                        pfl.decision("mode_selection", "incremental", {
                            "group": "fast_sync",
                            "reason": f"All stages complete, {stale} stale + {untraced} untraced files",
                            "stale_files": stale,
                            "untraced_files": untraced,
                            "resume_point": 0,
                        })
                else:
                    logger.info(
                        "All fast_sync stages complete and no stale files for %s — up to date",
                        project_id,
                    )
                    if pfl:
                        pfl.decision("mode_selection", "skip_up_to_date", {
                            "group": "fast_sync",
                            "reason": "All stages complete, no stale/untraced files",
                            "coverage_pct": gap.get("coverage_pct", 0),
                        })
                    return False
            except Exception:
                logger.warning(
                    "Coverage gap check failed for %s — triggering rebuild as safety fallback",
                    project_id, exc_info=True,
                )
                # Safe default: rebuild rather than silently skip
                resume = 0
                incremental = True
        if resume > 0:
            logger.info(
                "Resuming fast_sync for %s from stage %d/%d (%s) — stages 0-%d already on disk",
                project_id, resume, len(FAST_SYNC_STAGES),
                FAST_SYNC_STAGES[resume].value, resume - 1,
            )
            if pfl:
                pfl.decision("mode_selection", "resume", {
                    "group": "fast_sync",
                    "reason": f"Stages 0-{resume-1} complete on disk, resuming from {FAST_SYNC_STAGES[resume].value}",
                    "resume_point": resume,
                    "resume_stage": FAST_SYNC_STAGES[resume].value,
                })
        elif not incremental:
            if pfl:
                pfl.decision("mode_selection", "initial_full_run", {
                    "group": "fast_sync",
                    "reason": "No stages complete on disk, starting from scratch",
                    "resume_point": 0,
                })
        if incremental:
            # Track that this is an incremental run so that:
            # 1. _detect_resume_point skips mtime cascade for deep_enrichment
            # 2. run_deep_enrichment doesn't delete deep manifests
            self._incremental_runs.add(project_id)
            self._persist_incremental_flag(project_id, True)
            logger.info(
                "[%s] Running fast_sync in INCREMENTAL mode — downstream stages "
                "will add new/stale files without full rebuild",
                project_id,
            )
        return self._start_group(project_id, "fast_sync", FAST_SYNC_STAGES, resume_from=resume)

    def run_deep_enrichment(self, project_id: str, force_from_start: bool = False) -> bool:
        """Start the Deep Enrichment group (stages 6-11).

        Auto-detects resume point from disk state.

        Phase 53: When all deep stages are complete, checks if the
        catalogue manifest (fast sync output) is newer than any deep
        manifest — meaning fast sync re-ran for stale files and deep
        stages need to re-process the updated data.

        Note: If the preceding fast_sync was incremental (small coverage
        gap), we skip the "delete stale deep manifests" logic.  The deep
        workers already handle incrementality internally — they'll pick
        up new/changed nodes without needing a full restart.
        """
        # Check if the preceding fast_sync was incremental.
        # Try in-memory first (same process), then fall back to disk
        # (survives daemon restart between fast_sync and deep_enrichment).
        is_incremental = project_id in self._incremental_runs
        self._incremental_runs.discard(project_id)
        if not is_incremental:
            is_incremental = self._read_and_clear_incremental_flag(project_id)
            if is_incremental:
                logger.info(
                    "[%s] Recovered incremental flag from disk — "
                    "preceding fast_sync was incremental",
                    project_id,
                )

        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=is_incremental,
        )
        if resume >= len(DEEP_ENRICHMENT_STAGES):
            if is_incremental:
                # After incremental fast_sync, deep stages already have data.
                # Don't cascade-invalidate — workers will pick up the delta.
                logger.info(
                    "All deep_enrichment stages complete and fast_sync was incremental "
                    "for %s — running deep stages in incremental mode",
                    project_id,
                )
                resume = 0  # Run all stages, but workers skip existing data
            else:
                # Phase 53: Check if fast sync output is newer than deep manifests.
                # Instead of deleting stale manifests (which forces a full rebuild),
                # just restart from stage 0 and let workers handle incrementality.
                # Workers internally skip already-processed items.
                try:
                    from codrag.services.project_helpers import require_project
                    from codrag.core.project_registry import project_index_dir
                    project = require_project(project_id)
                    idx_dir = Path(project_index_dir(project))
                    catalogue_manifest = idx_dir / "trace_augment_manifest.json"
                    if catalogue_manifest.exists():
                        cat_mtime = catalogue_manifest.stat().st_mtime
                        # Check if any deep manifest is older than catalogue
                        for stage in DEEP_ENRICHMENT_STAGES:
                            mf = STAGE_MANIFEST_FILE.get(stage)
                            if mf:
                                mp = idx_dir / mf
                                if mp.exists() and mp.stat().st_mtime < cat_mtime:
                                    logger.info(
                                        "Deep stage %s manifest is stale (catalogue was re-run) "
                                        "for %s — re-running deep enrichment incrementally",
                                        stage.value, project_id,
                                    )
                                    resume = 0
                                    break
                except Exception:
                    pass
            if resume >= len(DEEP_ENRICHMENT_STAGES):
                logger.info("All deep_enrichment stages already complete on disk for %s — skipping", project_id)
                return False
        if resume > 0:
            logger.info(
                "Resuming deep_enrichment for %s from stage %d/%d (%s)",
                project_id, resume, len(DEEP_ENRICHMENT_STAGES),
                DEEP_ENRICHMENT_STAGES[resume].value,
            )
        return self._start_group(project_id, "deep_enrichment", DEEP_ENRICHMENT_STAGES, resume_from=resume)

    def run_deepening_only(self, project_id: str) -> bool:
        """Run ONLY the Continuous Deepening and Deep Knowledge stages. Useful for retriggers."""
        from .stages import StageId
        stages = [StageId.DEEPENING, StageId.DEEP_KNOWLEDGE]
        return self._start_group(project_id, "deep_enrichment", stages)

    def swap_model(self, project_id: str, group: str) -> Dict[str, Any]:
        """Pause the running stage, then resume with fresh LLM config.

        Workers call _get_llm_client_for_task() at stage start, so after
        a pause-resume cycle the new model config is automatically picked up.
        Incremental workers skip already-processed items, so no work is lost.

        Returns dict with swap details, or raises if the group isn't running.
        """
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run or not run.is_active:
                return {"swapped": False, "reason": "not_running"}
            paused_stage = run.current_stage

        # Pause → flush partial results
        paused = self._pause_group(project_id, group)
        if not paused:
            return {"swapped": False, "reason": "pause_failed"}

        logger.info(
            "Model swap for %s/%s: paused at stage %s, resuming with new config",
            project_id, group, paused_stage,
        )

        # Resume from the same stage — worker re-reads LLM config at start
        resumed = self.resume_paused(project_id, group)
        return {
            "swapped": resumed,
            "paused_at_stage": paused_stage,
            "resumed": resumed,
        }

    def hot_scope_reload(self, project_id: str) -> Dict[str, Any]:
        """Pause the running pipeline, rebuild the trace graph with current
        include/exclude patterns, then resume.

        Called when the user changes Exclude Tree or Include Patterns while
        a pipeline stage (typically Fast Catalogue) is running.  The flow:

        1. Pause the running stage (checkpoint + flush)
        2. Run Stage 1 (TraceBuilder) synchronously with current globs
           — Rebuilds trace_nodes.jsonl with the new file set
           — Fast: Rust parser, 5-30s even for large repos
        3. Resume the paused stage
           — Augmenter re-reads trace_nodes.jsonl (smaller list)
           — Incremental logic skips already-augmented items
           — Newly-excluded files are absent from the list

        Returns dict with reload details.
        """
        # Find which group is running
        with self._lock:
            active_group = None
            active_run = None
            for key, run in self._runs.items():
                if key[0] == project_id and run.is_active:
                    active_group = key[1]
                    active_run = run
                    break

        if not active_run or not active_group:
            logger.info("hot_scope_reload: no active pipeline for %s — patterns saved for next run", project_id)
            return {"reloaded": False, "reason": "not_running"}

        paused_stage = active_run.current_stage
        logger.info(
            "Hot scope reload for %s: pausing %s at stage %s, rebuilding trace graph",
            project_id, active_group, paused_stage,
        )

        # Step 1: Pause the running stage
        paused = self._pause_group(project_id, active_group)
        if not paused:
            return {"reloaded": False, "reason": "pause_failed"}

        # Step 2: Rebuild Stage 1 (structural trace) synchronously
        # This re-reads the current include/exclude globs from project config
        # and produces a new trace_nodes.jsonl with the updated file set.
        try:
            worker = WorkerFactory.create_worker(project_id, StageId.STRUCTURAL)
            from codrag.services.build_orchestrator import BuildSlot
            # Run the trace worker directly (not via BuildOrchestrator)
            # to keep it synchronous and fast.
            _dummy_slot = BuildSlot()
            _dummy_slot.cancel_token = None
            result = worker(_dummy_slot, lambda msg, cur, tot: logger.info(
                "Hot scope rebuild: %s (%d/%d)", msg, cur, tot,
            ))
            new_nodes = result.get("nodes", 0)
            logger.info(
                "Hot scope reload: trace rebuilt with %d nodes (was processing %s)",
                new_nodes, paused_stage,
            )
        except Exception as e:
            logger.error("Hot scope reload: trace rebuild failed: %s — resuming with old data", e)
            # Resume anyway — better to continue with stale data than stay paused
            self.resume_paused(project_id, active_group)
            return {"reloaded": False, "reason": f"rebuild_failed: {e}"}

        # Step 3: Resume the paused stage
        resumed = self.resume_paused(project_id, active_group)

        return {
            "reloaded": resumed,
            "paused_stage": paused_stage,
            "new_node_count": new_nodes,
            "group": active_group,
        }

    def run_all(self, project_id: str, force_from_start: bool = False) -> bool:
        """Start Fast Sync, then chain Deep Enrichment after it completes.

        Phase 61B: If fast_sync is already up-to-date (returns False),
        directly calls run_deep_enrichment() instead of relying on the
        completion-handler chain — which never fires if fast_sync didn't run.
        """
        # Start fast sync; deep enrichment will be chained via the listener
        with self._lock:
            key = (project_id, "fast_sync")
            run = self._runs.get(key)
            if run and run.is_active:
                return False
            # Mark that deep should chain after fast
            self._chain_deep[project_id] = True
        fast_started = self.run_fast_sync(project_id, force_from_start=force_from_start)
        if fast_started:
            return True  # Deep will chain via completion handler

        # Phase 61B: Fast sync is already up-to-date — chain deep directly.
        # Without this, the completion handler never fires and deep enrichment
        # is orphaned with _chain_deep set but never consumed.
        logger.info(
            "Phase 61B: Fast sync up-to-date for %s — directly calling run_deep_enrichment",
            project_id,
        )
        # Clean up the chain_deep flag since we're handling it directly
        self._chain_deep.pop(project_id, None)
        return self.run_deep_enrichment(project_id, force_from_start=force_from_start)

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
            "run_mode": "incremental" if project_id in self._incremental_runs else None,
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

        Transitions the existing PAUSED state machine to RUNNING via
        Event.RESUME, preserving stage_results and progress.  The
        resumed stage's worker will skip already-processed items
        (incremental).
        """
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run or not run.is_paused:
                return False

            # Transition PAUSED → RUNNING on the existing state machine
            if not run.transition(Event.RESUME):
                logger.warning(
                    "Resume transition rejected for %s/%s (state=%s)",
                    project_id, group, run.state.value,
                )
                return False

        logger.info(
            "Resuming paused run %s/%s from stage %d (%s)",
            project_id, group,
            run.current_stage_index,
            run.current_stage or "?",
        )

        # Re-start the current stage — worker will skip already-done items
        self._advance_pipeline(run)
        return True

    def force_reset_stale_runs(self, project_id: str, max_age_seconds: float = 600) -> List[str]:
        """Force-reset pipeline runs whose current stage worker has crashed.

        Returns list of groups that were reset.  This is a recovery mechanism
        for when a worker finishes but the _on_build_transition callback
        doesn't fire (e.g. due to a crash or race condition).

        IMPORTANT: Only resets if the build slot for the current stage is
        IDLE (worker finished/crashed but callback never fired).  If the
        build slot is actively RUNNING, the pipeline is NOT stuck — the
        worker is just slow.  A 10-hour augmentation pass is normal for
        large repos.
        """
        import time as _time
        reset_groups: List[str] = []
        with self._lock:
            for key, run in list(self._runs.items()):
                if key[0] != project_id:
                    continue
                if not run.is_active:
                    continue

                # Check the ACTUAL build slot for the current stage.
                # If the slot is actively running, the pipeline is NOT stuck.
                current_str = run.current_stage
                if current_str:
                    try:
                        current_stage = StageId(current_str)
                        bt = STAGE_BUILD_TYPE[current_stage]
                        slot = self._orchestrator.status(project_id, bt)
                        if slot.phase in (BuildPhase.RUNNING, BuildPhase.QUEUED):
                            # Worker is actively running — not stuck
                            continue
                    except Exception:
                        pass

                # Build slot is idle/completed/failed but SM thinks we're
                # still running → callback was lost.  Check age.
                elapsed = _time.time() - (run.started_at or 0)
                if elapsed > max_age_seconds:
                    group = key[1]
                    stage = current_str or "?"
                    logger.warning(
                        "Force-resetting stale pipeline %s/%s (stuck at stage %s, "
                        "build slot idle for %.0fs)",
                        project_id, group, stage, elapsed,
                    )
                    # Transition to FAILED so it's a clean terminal state
                    run.transition(Event.STAGE_FAILED,
                                   detail=f"Force-reset: worker crashed (slot idle for {int(elapsed)}s)")
                    reset_groups.append(group)
        return reset_groups

    def clear_project(self, project_id: str) -> None:
        """Remove all pipeline state for a project."""
        with self._lock:
            keys = [k for k in self._runs if k[0] == project_id]
            for k in keys:
                del self._runs[k]
        self._orchestrator.clear_project(project_id)
        # Clear cached file logger so it doesn't reference stale paths
        self._file_loggers.pop(project_id, None)

    # ── Coverage Gap Detection ─────────────────────────────────

    _COVERAGE_RETRIGGER_DELAY = 15.0  # seconds after completion before re-checking

    @staticmethod
    def check_coverage_gap(project_id: str) -> Dict[str, Any]:
        """Check if there are files that should be traced but aren't.

        Uses ``compute_trace_coverage()`` to compare the filesystem against
        the trace manifest.  Returns a lightweight summary — does NOT
        return the full file lists to keep memory usage low.

        Returns dict with:
          - total: total eligible files on disk
          - traced: files already traced and up-to-date
          - untraced: files eligible for trace but not yet traced
          - stale: files that were traced but content has changed
          - needs_rebuild: True if untraced + stale > 0
          - coverage_pct: percentage of files traced
        """
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            from codrag.core.trace.coverage import compute_trace_coverage

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            repo_root = Path(project.path)

            pcfg = project.config or {}
            include_globs = pcfg.get("include_globs") or None
            exclude_globs = pcfg.get("exclude_globs") or None
            max_file_bytes = int(pcfg.get("max_file_bytes") or 500_000)

            coverage = compute_trace_coverage(
                repo_root=repo_root,
                index_dir=idx_dir,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                max_file_bytes=max_file_bytes,
            )
            summary = coverage.get("summary", {})
            untraced = summary.get("untraced", 0)
            stale = summary.get("stale", 0)

            return {
                "total": summary.get("total", 0),
                "traced": summary.get("traced", 0),
                "untraced": untraced,
                "stale": stale,
                "needs_rebuild": (untraced + stale) > 0,
                "coverage_pct": summary.get("coverage_pct", 0.0),
            }
        except Exception:
            logger.warning(
                "Coverage gap check failed for %s — defaulting to needs_rebuild=True",
                project_id, exc_info=True,
            )
            return {
                "total": 0, "traced": 0, "untraced": 0, "stale": 0,
                "needs_rebuild": True, "coverage_pct": 0.0,
            }

    def _maybe_retrigger_for_coverage(
        self, project_id: str, group: str, pfl: Any = None,
    ) -> None:
        """After pipeline completion, check for untraced/stale files and
        auto-retrigger if needed.

        Phase 48-F8: This is the key mechanism that ensures the pipeline
        catches files that exist on disk but were missed by a previous run
        (e.g., Rust engine failure, glob change, new files added between
        watcher events).

        Runs in a delayed background thread to avoid blocking the
        completion callback and to give the filesystem time to settle.
        """
        def _check_and_retrigger():
            try:
                time.sleep(self._COVERAGE_RETRIGGER_DELAY)

                # Respect pipeline mode: don't retrigger if Manual
                try:
                    from codrag.services.settings_store import settings as _ss
                    pc = _ss.get("pipeline_config") or {}
                    fast_auto = (pc.get("fast_sync") or {}).get("auto", False)
                    if not fast_auto:
                        logger.debug(
                            "Coverage retrigger skipped for %s — "
                            "pipeline in manual mode",
                            project_id,
                        )
                        return
                except Exception:
                    pass  # Settings unavailable — proceed

                # Don't retrigger if another run has started in the meantime
                with self._lock:
                    for key, run in self._runs.items():
                        if key[0] == project_id and run.is_active:
                            logger.debug(
                                "Coverage retrigger skipped for %s — "
                                "pipeline already running",
                                project_id,
                            )
                            return

                gap = self.check_coverage_gap(project_id)
                if not gap["needs_rebuild"]:
                    logger.info(
                        "Coverage check for %s: %d/%d files traced (%.1f%%) — "
                        "no retrigger needed",
                        project_id, gap["traced"], gap["total"],
                        gap["coverage_pct"],
                    )
                    return

                logger.info(
                    "Coverage gap detected for %s: %d untraced + %d stale "
                    "out of %d total files (%.1f%% coverage) — retriggering "
                    "fast sync",
                    project_id, gap["untraced"], gap["stale"],
                    gap["total"], gap["coverage_pct"],
                )
                if pfl:
                    pfl.log(
                        "coverage_gap",
                        f"Retriggering: {gap['untraced']} untraced + "
                        f"{gap['stale']} stale files",
                    )

                started = self.run_fast_sync(
                    project_id,
                )
                logger.info(
                    "Coverage retrigger for %s: started=%s",
                    project_id, started,
                )
            except Exception:
                logger.debug(
                    "Coverage retrigger failed for %s",
                    project_id, exc_info=True,
                )

        t = threading.Thread(target=_check_and_retrigger, daemon=True)
        t.start()

    # ── Node resolution (Phase 56) ─────────────────────────────────

    def _resolve_node_for_stage(
        self, project_id: str, stage: StageId,
    ) -> Optional[str]:
        """Resolve which compute node handles this stage's model.

        Walks the chain:  stage → model slot → endpoint → provider + model → node_id.
        Returns None for non-LLM stages (Rust, Embedding).
        """
        slot_name = STAGE_MODEL_SLOT.get(stage)
        if not slot_name:
            return None  # Rust / Embedding — no LLM node

        try:
            from codrag.services.settings_store import settings
            llm_config = settings.get("llm_config") or {}
        except Exception:
            return None

        # Read the slot config (e.g. llm_config["small_model"])
        slot_key = f"{slot_name}_model"
        slot_config = llm_config.get(slot_key, {})
        endpoint_id = slot_config.get("endpoint_id")
        model = slot_config.get("model", "")

        if not endpoint_id:
            return None  # No endpoint configured — fall back to default node

        # Find the provider for this endpoint
        provider = "ollama"
        for ep in llm_config.get("saved_endpoints", []):
            if ep.get("id") == endpoint_id:
                provider = ep.get("provider", "ollama")
                break

        return pipeline_scheduler.resolve_node_for_model(provider, model, endpoint_id)

    def _is_cloud_node(self, node_id: Optional[str]) -> bool:
        """Check if a node ID refers to a cloud compute node."""
        return node_id is not None and node_id.startswith("cloud:")

    # ── Internal ───────────────────────────────────────────────

    def _detect_resume_point(
        self,
        project_id: str,
        stages: List[StageId],
        skip_mtime_cascade: bool = False,
    ) -> int:
        """Detect the first incomplete stage by checking manifest files on disk.

        A stage is considered "complete" if its **manifest file** exists.
        Output files alone are not sufficient — the augmenter writes
        checkpoint data to its output file periodically, but only writes
        the manifest at the end of a successful ``run()``.

        For the structural stage (stage 1), we check if trace_nodes.jsonl
        exists since it doesn't have a separate manifest in the same
        sense — trace_manifest.json is the output.

        Args:
            skip_mtime_cascade: If True, don't invalidate downstream stages
                based on manifest timestamps.  Used for incremental runs
                where the structural trace was rebuilt for a small coverage
                gap — the downstream stages already have data and their
                workers handle incrementality internally.

        Returns the index of the first incomplete stage.  If all stages
        are complete, returns ``len(stages)``.
        """
        from pathlib import Path
        from .stages import STAGE_OUTPUT_FILE, STAGE_MANIFEST_FILE
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
        except Exception:
            return 0  # Can't resolve project — start from scratch

        # Get the structural manifest mtime as the "baseline" — any
        # downstream stage whose manifest is OLDER than this needs to
        # re-run because its input data (the trace graph) changed.
        structural_manifest = idx_dir / "trace_manifest.json"
        baseline_mtime = 0.0
        if not skip_mtime_cascade and structural_manifest.exists():
            baseline_mtime = structural_manifest.stat().st_mtime

        # Phase 60A: Collect per-stage decisions for logging
        stage_decisions: list[dict] = []

        for i, stage in enumerate(stages):
            # The manifest file is the completion signal.
            # Workers write output incrementally (checkpoints) but only
            # write the manifest at the very end of a successful run.
            manifest_file = STAGE_MANIFEST_FILE.get(stage)
            if manifest_file:
                mpath = idx_dir / manifest_file
                if mpath.exists() and mpath.stat().st_size > 0:
                    # Phase 48-F8: For the structural stage, verify the
                    # manifest actually reports nodes.
                    if stage == StageId.STRUCTURAL:
                        nodes_path = idx_dir / "trace_nodes.jsonl"
                        if not nodes_path.exists() or nodes_path.stat().st_size == 0:
                            logger.warning(
                                "Structural manifest exists but "
                                "trace_nodes.jsonl is missing/empty "
                                "— treating as incomplete (needs rebuild)"
                            )
                            stage_decisions.append({
                                "stage": stage.value, "decision": "INCOMPLETE",
                                "reason": "Manifest exists but trace_nodes.jsonl missing/empty",
                            })
                            self._log_resume_decisions(project_id, stages, i, stage_decisions, skip_mtime_cascade)
                            return i

                    # Phase 67: Ensure Sub-Atlas generation is continuous.
                    # If the pipeline crashed generating segment or role atlases, 
                    # the main atlas manifest might exist, but segments are missing.
                    elif stage == StageId.ATLAS:
                        segments_path = idx_dir / "atlas_segments_manifest.json"
                        if not segments_path.exists() or segments_path.stat().st_size == 0:
                            logger.warning(
                                "Atlas manifest exists but atlas_segments_manifest.json "
                                "is missing/empty — treating as incomplete (needs rebuild)"
                            )
                            stage_decisions.append({
                                "stage": stage.value, "decision": "INCOMPLETE",
                                "reason": "Manifest exists but atlas_segments_manifest.json missing",
                            })
                            self._log_resume_decisions(project_id, stages, i, stage_decisions, skip_mtime_cascade)
                            return i

                    # Check staleness: is this manifest older than the
                    # structural trace?
                    if (not skip_mtime_cascade
                            and stage != StageId.STRUCTURAL
                            and baseline_mtime > 0):
                        manifest_mtime = mpath.stat().st_mtime
                        if manifest_mtime < baseline_mtime:
                            logger.info(
                                "Stage %s manifest is stale (%.0f < %.0f) — "
                                "trace was rebuilt after this stage last ran",
                                stage.value, manifest_mtime, baseline_mtime,
                            )
                            stage_decisions.append({
                                "stage": stage.value, "decision": "STALE_MTIME",
                                "reason": f"Manifest mtime {manifest_mtime:.0f} < structural mtime {baseline_mtime:.0f}",
                                "age_gap_seconds": round(baseline_mtime - manifest_mtime, 1),
                            })
                            self._log_resume_decisions(project_id, stages, i, stage_decisions, skip_mtime_cascade)
                            return i

                    stage_decisions.append({
                        "stage": stage.value, "decision": "COMPLETE",
                        "manifest_size": mpath.stat().st_size,
                    })
                    continue  # Stage completed and fresh — skip

                # Manifest missing or empty — stage needs to run.

                # Atlas crash-loop guard
                if stage == StageId.ATLAS:
                    atlas_json = idx_dir / "atlas.json"
                    if atlas_json.exists() and atlas_json.stat().st_size > 10:
                        logger.warning(
                            "Atlas manifest missing but atlas.json exists (%d bytes) "
                            "— treating atlas as complete (crash recovery)",
                            atlas_json.stat().st_size,
                        )
                        stage_decisions.append({
                            "stage": stage.value, "decision": "CRASH_RECOVERY",
                            "reason": f"Atlas manifest missing but atlas.json exists ({atlas_json.stat().st_size} bytes)",
                        })
                        continue

                stage_decisions.append({
                    "stage": stage.value, "decision": "MISSING_MANIFEST",
                    "reason": f"{manifest_file} missing or empty",
                })
                self._log_resume_decisions(project_id, stages, i, stage_decisions, skip_mtime_cascade)
                return i

            # Stage has no manifest mapping — check output file existence
            output_file = STAGE_OUTPUT_FILE.get(stage)
            if output_file:
                opath = idx_dir / output_file
                if opath.exists() and opath.stat().st_size > 0:
                    stage_decisions.append({
                        "stage": stage.value, "decision": "COMPLETE",
                        "output_size": opath.stat().st_size,
                    })
                    continue
                stage_decisions.append({
                    "stage": stage.value, "decision": "MISSING_OUTPUT",
                    "reason": f"{output_file} missing or empty",
                })
                self._log_resume_decisions(project_id, stages, i, stage_decisions, skip_mtime_cascade)
                return i

            # No manifest and no output file — assume needs to run
            stage_decisions.append({
                "stage": stage.value, "decision": "NO_OUTPUT_FILE",
                "reason": "No manifest or output file configured",
            })
            self._log_resume_decisions(project_id, stages, i, stage_decisions, skip_mtime_cascade)
            return i

        # All stages complete
        self._log_resume_decisions(project_id, stages, len(stages), stage_decisions, skip_mtime_cascade)
        return len(stages)

    def _log_resume_decisions(
        self,
        project_id: str,
        stages: list,
        resume_index: int,
        stage_decisions: list[dict],
        skip_mtime_cascade: bool,
    ) -> None:
        """Log the per-stage resume point decision audit trail.

        Called at the end of _detect_resume_point to write a structured
        decision event showing WHY each stage was skipped or selected
        as the resume point.  This is the single most important log
        for diagnosing 'pipeline restarted from scratch' issues.
        """
        try:
            pfl = self._get_file_logger(project_id)
            if not pfl:
                return

            all_complete = resume_index >= len(stages)
            resume_stage = None if all_complete else stages[resume_index].value

            pfl.decision("resume_point", resume_stage or "all_complete", {
                "resume_index": resume_index,
                "total_stages": len(stages),
                "all_complete": all_complete,
                "skip_mtime_cascade": skip_mtime_cascade,
                "per_stage": stage_decisions,
            })
        except Exception:
            logger.debug(
                "Failed to log resume decisions (non-fatal)",
                exc_info=True,
            )

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

        Uses ``PipelineGroupStateMachine`` with ``ActiveProjectGuard``
        to enforce activity checks and formal state transitions.
        """
        with self._lock:
            # Block if this group is already running
            key = (project_id, group)
            existing = self._runs.get(key)
            if existing and existing.is_active:
                return False

            # Block if ANY other group for the same project is running.
            for run_key, run_obj in self._runs.items():
                if run_key[0] == project_id and run_key[1] != group and run_obj.is_active:
                    logger.warning(
                        "Cannot start %s/%s — %s is already active for this project",
                        project_id, group, run_key[1],
                    )
                    return False

            # Create state machine (or reuse existing for resume)
            sm = PipelineGroupStateMachine(
                project_id=project_id,
                group=group,
                stages=[s.value for s in stages],
            )
            sm.add_guard(self._default_guard)
            sm.current_stage_index = resume_from

            # Attempt START transition (ActiveProjectGuard may block)
            if not sm.transition(Event.START):
                return False

            self._runs[key] = sm

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
            sm.journal_run_id = run_id
            # If resuming, mark already-completed stages
            if resume_from > 0:
                for i in range(resume_from):
                    stage_val = stages[i].value
                    sm.stage_results[stage_val] = "completed"
                    journal.stage_completed(run_id, stage_val)
                journal.stage_started(run_id, stages[resume_from].value, resume_from)
        except Exception:
            logger.debug("Journal write failed (non-fatal)", exc_info=True)

        # Phase 49: create run metadata
        try:
            from codrag.services.pipeline_metadata import (
                create_run_metadata, save_run_metadata,
            )
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = project_index_dir(project)
            run_meta = create_run_metadata(
                run_id=sm.journal_run_id or f"run-{int(time.time())}",
                project_id=project_id,
                group=group,
                stage_ids=[s.value for s in stages],
            )
            self._run_metadata[(project_id, group)] = run_meta
            save_run_metadata(run_meta, idx_dir)
        except Exception:
            logger.debug("Run metadata creation failed (non-fatal)", exc_info=True)

        # Phase 50: Detect new AI tools and regenerate missing rules files.
        # Cheap (~1ms detection + ~5ms writes for missing files only).
        # Catches tool switches (user installed Windsurf since last run).
        try:
            from codrag.core.rules_generator import detect_and_regenerate
            from codrag.services.project_helpers import require_project
            project = require_project(project_id)
            detect_and_regenerate(
                project_id=project_id,
                project_path=Path(project.path),
                project_name=project.name or project_id,
            )
        except Exception:
            logger.debug("Phase 50: detect_and_regenerate failed at pipeline start (non-fatal)", exc_info=True)

        # Start the first (or resumed) stage
        self._advance_pipeline(sm)
        return True

    def _advance_pipeline(self, run: PipelineGroupStateMachine) -> None:
        """Advance to the next stage in the pipeline, or finish."""
        pfl = self._get_file_logger(run.project_id)
        if run.current_stage_index >= len(run.stages):
            # All stages complete — formal transition
            run.transition(Event.ALL_STAGES_DONE)
            logger.info(
                "Pipeline %s/%s completed in %.1fs",
                run.project_id, run.group,
                (run.finished_at or 0) - (run.started_at or 0),
            )
            if pfl:
                pfl.end_run("completed")
            # Phase 61B: Stop heartbeat timer — run is complete
            self._stop_heartbeat_timer(run)
            # VRAM lifecycle: release group models via state machine (falls back to legacy)
            self._release_group_models_via_sm(run)
            # Phase 25: journal — mark run completed + cleanup checkpoint
            self._journal_run_completed(run)
            # Phase 49: finalize run metadata + record in history
            self._finalize_run_metadata(run, "completed")
            # Phase 66: Notify Pi agent that a pipeline group completed.
            # Pi decides whether to run Watchdog/Dispatcher based on its
            # own config and cooldown timers.  Runs in a background thread
            # so it never blocks the pipeline.  Non-fatal.
            try:
                from codrag.services.pi_agent import get_pi_agent
                pi = get_pi_agent()
                if pi is not None:
                    pi.on_pipeline_complete(run.group)
            except Exception:
                logger.debug("Pi agent notification failed (non-fatal)", exc_info=True)
            # After deep enrichment completes, trigger CodeIndex build so
            # /context search works and file tree status badges update.
            # Note: fast_sync does NOT trigger CodeIndex — it only builds
            # the trace graph.  CodeIndex rebuilds are heavyweight (re-embed
            # all files) and should only happen after deep enrichment or
            # when the user explicitly clicks Rebuild.
            if run.group == "deep_enrichment":
                self._trigger_code_index_build(run.project_id, pfl)
            # Phase 48 (P48-F5): After deep enrichment completes in auto mode,
            # check if deepening has converged. If not, re-trigger.
            if run.group == "deep_enrichment":
                self._maybe_retrigger_deepening(run.project_id, pfl)

            # Chain deep enrichment after fast sync if configured or explicitly requested
            if run.group == "fast_sync":
                should_chain = False
                chain_reason = "none"
                # 1. Explicit chain from run_all()
                chain_deep = self._chain_deep
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

                # Phase 48-F8: After fast_sync completes, schedule a
                # coverage gap check.  If there are still untraced or
                # stale files (e.g. Rust engine missed them, or new files
                # appeared during the run), auto-retrigger fast_sync.
                self._maybe_retrigger_for_coverage(
                    run.project_id, "fast_sync", pfl,
                )
            return

        stage_str = run.stages[run.current_stage_index]
        stage = StageId(stage_str)
        build_type = STAGE_BUILD_TYPE[stage]
        queue_type = STAGE_QUEUE_TYPE.get(stage, QueueType.LLM)

        # Phase 45D: Check scheduler capacity before starting the stage.
        # If the compute node is full, park the pipeline in QUEUED state.
        # Phase 56: resolve which compute node this stage's model runs on.
        node_id = self._resolve_node_for_stage(run.project_id, stage)

        # Atomic acquire: acquire() checks capacity and grabs the slot
        # in one locked operation, avoiding the TOCTOU race that existed
        # when can_start() and acquire() were called separately.
        if not pipeline_scheduler.acquire(run.project_id, stage, node_id):
            pipeline_scheduler.enqueue(run.project_id, stage, node_id)
            if run.can_transition(Event.ENQUEUE):
                run.transition(Event.ENQUEUE, detail=f"waiting for compute slot ({stage.value})")
            logger.info(
                "Pipeline %s/%s — stage %s queued (compute node %s full)",
                run.project_id, run.group, stage.value, node_id or "__local__",
            )
            if pfl:
                pfl.log(stage.value, f"Queued — waiting for compute capacity on {node_id or '__local__'}")
            return

        # Stash node_id so _on_build_transition can release on the correct node
        run._current_node_id = node_id  # type: ignore[attr-defined]

        # VRAM lifecycle: only LOCAL LLM stages need model acquire/unload.
        # Cloud endpoints are always ready — no VRAM contention.
        # Embedding stages use NativeEmbedder (ONNX/CoreML/CUDA) — independent.
        # Rust stages are CPU-only — no GPU contention.
        if queue_type == QueueType.LLM and not self._is_cloud_node(node_id):
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
        elif queue_type == QueueType.LLM and self._is_cloud_node(node_id):
            logger.debug(
                "Stage %s uses cloud node %s — skipping VRAM lifecycle",
                stage.value, node_id,
            )
        else:
            logger.debug(
                "Stage %s uses %s queue — skipping VRAM lifecycle",
                stage.value, queue_type.value,
            )

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

        # Phase 61B: Start heartbeat timer for this stage.
        # Writes to pipeline_run_metadata.json every 60s so the watchdog
        # can distinguish a genuinely running stage from a dead process.
        self._start_heartbeat_timer(run)

        # Phase 70B: Freshness check — skip if outputs already current
        if self._should_skip_stage_freshness(run, stage, pfl):
            return  # stage is already current, don't run it

        # Phase 25: journal — record stage start
        self._journal_stage_started(run, stage)

        # Phase 25: checkpoint — backup trace files before destructive stages
        self._create_checkpoint_if_needed(run, stage)

        # Phase 60A: integrity guard — snapshot data files before stage runs
        self._integrity_snapshot_before_stage(run, stage)

        worker = WorkerFactory.create_worker(run.project_id, stage)
        started = self._orchestrator.start(run.project_id, build_type, worker)

        if not started:
            logger.warning(
                "Stage %s slot already active for %s — force-resetting stuck slot",
                stage.value, run.project_id,
            )
            self._orchestrator.cancel(run.project_id, build_type)
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
        Uses state machine events for formal state tracking.
        """
        if new_phase not in (BuildPhase.COMPLETED, BuildPhase.FAILED):
            return

        stage: Optional[StageId] = None
        with self._lock:
            # Find any active or paused pipeline run for this project where
            # the current stage matches this build type.  We include PAUSED
            # because a worker's FAILED callback may arrive after
            # _pause_group() already moved the SM to PAUSED (race).
            matching_run: Optional[PipelineGroupStateMachine] = None
            for key, run in self._runs.items():
                if run.project_id != project_id:
                    continue
                if not (run.is_active or run.is_paused):
                    continue
                current_str = run.current_stage
                if current_str:
                    current_stage = StageId(current_str)
                    if STAGE_BUILD_TYPE[current_stage] == build_type:
                        matching_run = run
                        stage = current_stage
                        break

            if matching_run is None or stage is None:
                return

            if new_phase == BuildPhase.COMPLETED:
                # State machine handles stage_results + index increment
                matching_run.transition(Event.STAGE_COMPLETED)
                logger.info(
                    "Pipeline %s/%s — stage %s completed",
                    project_id, matching_run.group, stage.value,
                )

                # --- Post-completion bookkeeping (non-fatal) --------
                # Wrapped in try/except so that failures in logging,
                # metadata, or manifest writing can NEVER prevent
                # _advance_pipeline from being called below.
                try:
                    # Phase 44C: release model via state machine
                    completed_task = STAGE_TASK_ID.get(stage)
                    if completed_task:
                        try:
                            from codrag.core.model_awareness import model_awareness
                            model_awareness.release(completed_task, unload=False)
                        except Exception:
                            logger.debug("ModelAwareness release failed for %s", completed_task, exc_info=True)

                    # Phase 45D / 56: release scheduler slot on the correct node
                    _release_node = getattr(matching_run, '_current_node_id', None)
                    next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
                    if next_entry:
                        self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)

                    # Fetch build slot for file logger + manifest writer
                    slot = self._orchestrator.status(project_id, build_type)

                    # Pipeline file logger
                    pfl = self._get_file_logger(project_id)
                    if pfl:
                        pfl.stage_end(stage.value, "completed", data={
                            "result": slot.result,
                            "duration": slot.duration_seconds,
                        })
                        pfl.transition(build_type.value, old_phase.value, new_phase.value,
                                       f"Stage {stage.value} completed")
                    # Phase 25: journal — record stage completion
                    self._journal_stage_completed(matching_run, stage)
                    # Phase 49: write stage manifest + update run metadata
                    self._write_stage_manifest_and_update_run(
                        matching_run, stage, slot,
                    )
                    # Phase 50: Generate preliminary atlas + rules file after Stage 1,
                    # and regenerate rules with full LLM atlas after Stage 9.
                    if stage == StageId.STRUCTURAL:
                        self._generate_preliminary_atlas_and_rules(project_id)
                        self._prune_stale_derivative_files(project_id, pfl)
                    elif stage == StageId.ATLAS:
                        self._regenerate_rules_with_full_atlas(project_id)

                    # Phase 70B: Write guard — block if data would shrink
                    self._write_guard_check(matching_run, stage, pfl)

                    # Phase 60A: integrity guard — compare post-flight vs pre-flight
                    self._integrity_check_after_stage(matching_run, stage, pfl)
                except _WriteGuardBlocked as wgb:
                    # Write guard blocked advancement — fail this stage
                    logger.critical(
                        "WRITE GUARD BLOCKED stage %s for %s: %s",
                        stage.value, project_id, wgb,
                    )
                    if pfl:
                        pfl.log(stage.value, f"WRITE GUARD BLOCKED: {wgb}")
                    # Transition to FAILED so the pipeline halts
                    matching_run.fail(str(wgb))
                    return  # do NOT advance to next stage
                except Exception:
                    logger.exception(
                        "Post-completion bookkeeping failed for %s/%s stage %s "
                        "(pipeline will still advance)",
                        project_id, matching_run.group, stage.value,
                    )

            elif new_phase == BuildPhase.FAILED:
                slot = self._orchestrator.status(project_id, build_type)
                error_msg = f"Stage {stage.value} failed: {slot.error}"

                # If the state machine is in PAUSING, PAUSED, or QUEUED, this
                # "failure" is actually the worker responding to the pause
                # signal (PipelinePausedError).  Don't transition to FAILED.
                # - PAUSED: race — _pause_group() already moved SM to PAUSED
                # - QUEUED: race — swap_model() paused then resumed, and
                #   _advance_pipeline re-enqueued the stage while the old
                #   worker's PipelinePausedError is still in flight.
                if matching_run.state in (PipelineState.PAUSING, PipelineState.PAUSED, PipelineState.QUEUED):
                    logger.info(
                        "Pipeline %s/%s — ignoring STAGE_FAILED during %s "
                        "(worker stopped for pause/swap, not a real failure)",
                        project_id, matching_run.group, matching_run.state.value,
                    )
                    # Release scheduler slot but don't advance or fail
                    _release_node = getattr(matching_run, '_current_node_id', None)
                    next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
                    if next_entry:
                        self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)
                    return

                # Phase 55 fix: Instead of transitioning to a terminal FAILED state
                # when an error occurs (like an LLM crash), auto-pause the pipeline
                # so the user can see the error and click "Resume" after fixing it.
                if matching_run.state == PipelineState.RUNNING:
                    logger.error(
                        "Pipeline %s/%s — stage %s failed: %s. Auto-pausing for recovery.",
                        project_id, matching_run.group, stage.value, slot.error,
                    )
                    matching_run.transition(Event.PAUSE, detail=error_msg)
                    matching_run.transition(Event.STAGE_FLUSHED, detail=error_msg)
                    matching_run.stage_results[stage.value] = f"failed: {slot.error}"
                else:
                    matching_run.transition(Event.STAGE_FAILED, detail=error_msg)
                    logger.error(
                        "Pipeline %s/%s — stage %s failed: %s",
                        project_id, matching_run.group, stage.value, slot.error,
                    )

                # Phase 45D / 56: release scheduler slot on failure too
                _release_node = getattr(matching_run, '_current_node_id', None)
                next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
                if next_entry:
                    self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)

                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.stage_end(stage.value, "failed", error=slot.error, data={
                        "duration": slot.duration_seconds,
                    })
                    pfl.end_run("failed", error=slot.error)
                # Phase 25: journal — record stage failure
                self._journal_stage_failed(matching_run, stage, slot.error or "Unknown error")
                # Phase 61B: Stop heartbeat timer on failure
                self._stop_heartbeat_timer(matching_run)
                # VRAM lifecycle: release all group models
                self._release_group_models_via_sm(matching_run)
                return

        # Phase 48-F8: Post-structural sanity check.
        # If the structural stage completed but produced 0 nodes, check
        # whether the project actually has files.  If files exist but 0
        # nodes were produced, something is wrong (Rust engine failure,
        # glob misconfiguration, etc.).  Fail the pipeline early instead
        # of wasting time on 10 downstream stages with empty data.
        _abort = False
        if (
            matching_run
            and matching_run.is_active
            and stage == StageId.STRUCTURAL
            and new_phase == BuildPhase.COMPLETED
        ):
            try:
                slot = self._orchestrator.status(project_id, build_type)
                node_count = (slot.result or {}).get("nodes", -1)
                if node_count == 0:
                    # Quick check: does the project directory have relevant files?
                    from codrag.services.project_helpers import require_project
                    from codrag.core.project_registry import project_index_dir
                    _proj = require_project(project_id)
                    _repo = Path(_proj.path)
                    if _repo.is_dir():
                        # Count up to 5 files to confirm the repo isn't empty
                        _found = 0
                        _CODE_EXTS = {
                            ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
                            ".java", ".c", ".cpp", ".h", ".hpp", ".swift",
                            ".md", ".kt", ".cs", ".rb", ".php",
                        }
                        for _r, _ds, _fs in os.walk(_repo):
                            _ds[:] = [
                                d for d in _ds
                                if not d.startswith(".") and d not in (
                                    "node_modules", "__pycache__", ".git",
                                    "target", "build", "dist", "vendor",
                                )
                            ]
                            for _fn in _fs:
                                if any(_fn.endswith(ext) for ext in _CODE_EXTS):
                                    _found += 1
                                    if _found >= 5:
                                        break
                            if _found >= 5:
                                break

                        if _found > 0:
                            _abort = True
                            _detail = (
                                f"Structural stage produced 0 nodes but project "
                                f"has files on disk ({_found}+ code files found). "
                                f"Possible causes: Rust engine failure, glob "
                                f"misconfiguration, or permissions issue."
                            )
                            logger.error(
                                "Pipeline %s/%s — %s",
                                project_id, matching_run.group, _detail,
                            )
                            pfl = self._get_file_logger(project_id)
                            if pfl:
                                pfl.log("structural", _detail)
                                pfl.end_run("failed", error=_detail)
                            matching_run.transition(
                                Event.STAGE_FAILED, detail=_detail,
                            )
            except Exception:
                logger.debug(
                    "Post-structural sanity check failed (non-fatal)",
                    exc_info=True,
                )

        # Advance outside the lock
        if matching_run and matching_run.is_active and not _abort:
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
                matching_run.transition(
                    Event.STAGE_FAILED,
                    detail=f"Failed to advance after {stage.value if stage else '?'}: {exc}",
                )

    def _cancel_group(self, project_id: str, group: str) -> bool:
        """Cancel a running group using state machine events."""
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run:
                return False

            current_str = run.current_stage

            # CANCEL from RUNNING → CANCELLING, from PAUSED → CANCELLED directly
            if not run.transition(Event.CANCEL):
                return False

        # Cancel the current stage's build
        if current_str:
            bt = STAGE_BUILD_TYPE[StageId(current_str)]
            self._orchestrator.cancel(project_id, bt)

        # If still in CANCELLING, complete the transition
        if run.state == PipelineState.CANCELLING:
            run.transition(Event.STAGE_STOPPED)

        # Phase 25: journal — record cancellation
        if run.journal_run_id:
            try:
                from codrag.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)
            except Exception:
                logger.debug("Journal cancel write failed", exc_info=True)
        return True

    def _pause_group(self, project_id: str, group: str) -> bool:
        """Pause a running group using state machine events.

        RUNNING → PAUSING → PAUSED (proper first-class state).
        The current stage's worker cooperatively flushes partial results
        before stopping.  ``resume_paused()`` restarts from the paused
        stage — incremental workers skip already-done items.

        **Important**: We wait for the worker to actually finish flushing
        before transitioning to PAUSED.  Without this, the checkpoint
        captures pre-stage files and the worker's flush never completes.
        """
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run:
                return False

            current_str = run.current_stage

            # RUNNING → PAUSING
            if not run.transition(Event.PAUSE):
                return False

        # Signal the worker to pause (not cancel)
        slot = None
        if current_str:
            stage = StageId(current_str)
            bt = STAGE_BUILD_TYPE[stage]
            self._orchestrator.pause(project_id, bt)

            # Wait for worker to cooperatively stop (bounded).
            # The worker checks cancel_token between batches, flushes
            # partial results, and raises PipelinePausedError which
            # transitions the slot to inactive.
            import time as _time
            slot = self._orchestrator._slots.get((project_id, bt))
            if slot:
                _deadline = _time.monotonic() + 30  # 30s max wait
                while slot.is_active and _time.monotonic() < _deadline:
                    _time.sleep(0.5)
                if slot.is_active:
                    logger.warning(
                        "Pause timeout: worker for %s/%s still active after 30s "
                        "— forcing PAUSED transition (data may be partially flushed)",
                        project_id, group,
                    )

            # Create a file-level checkpoint AFTER worker has flushed
            self._create_checkpoint_if_needed(run, stage)

        # PAUSING → PAUSED
        run.transition(Event.STAGE_FLUSHED)

        # Journal: record pause
        if run.journal_run_id:
            try:
                from codrag.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)
            except Exception:
                logger.debug("Journal pause write failed", exc_info=True)

        logger.info(
            "Pipeline paused: %s/%s at stage %s (index %d)",
            project_id, group,
            current_str or "?",
            run.current_stage_index,
        )
        return True

    # ── VRAM Lifecycle ─────────────────────────────────────────────

    def _release_group_models_via_sm(self, run: PipelineGroupStateMachine) -> None:
        """Release all models used by a pipeline group via the state machine.

        Phase 44C: Delegates to ModelAwareness.release_group() which handles
        persistent model preservation and eviction recovery.  Falls back to
        the legacy _unload_group_models() if the state machine fails.
        """
        task_ids = [
            STAGE_TASK_ID[StageId(stage_str)]
            for stage_str in run.stages
            if StageId(stage_str) in STAGE_TASK_ID
        ]
        try:
            from codrag.core.model_awareness import model_awareness
            model_awareness.release_group(task_ids, unload=True)
        except Exception as e:
            logger.warning(
                "ModelAwareness release_group failed, falling back to legacy: %s", e
            )
            self._unload_group_models(run)

    def _maybe_unload_previous_model(self, run: PipelineGroupStateMachine, next_stage: StageId) -> None:
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
            prev_stage = StageId(run.stages[run.current_stage_index - 1])
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

    def _unload_group_models(self, run: PipelineGroupStateMachine) -> None:
        """Unload any LLM models used by the completed/failed group.

        Phase 44: Tracks unique (endpoint_id, model) identities across the
        group's stages.  Deduplicates so shared models are only unloaded once.

        Called when a pipeline group finishes to free VRAM for the next
        group or for the user's own work.
        """
        from codrag.server import _get_model_identity_for_task, _get_llm_client_for_task

        # Collect unique model identities used by this group
        identities_seen: dict = {}  # identity → task_id (for client resolution)
        for stage_str in run.stages:
            task_id = STAGE_TASK_ID.get(StageId(stage_str))
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

    # ── Phase 61B: Heartbeat Timer ─────────────────────────────────

    _HEARTBEAT_INTERVAL = 60.0  # seconds between heartbeat writes

    def _start_heartbeat_timer(self, run: PipelineGroupStateMachine) -> None:
        """Start a heartbeat timer that writes periodically to metadata.

        Self-cancels when the run is no longer active.  Stashed on the
        state machine so _stop_heartbeat_timer can cancel it.
        """
        # Cancel any existing heartbeat for this run
        self._stop_heartbeat_timer(run)

        import threading

        def _tick():
            if not run.is_active:
                return  # Run completed/failed/paused — stop
            try:
                from codrag.core.project_registry import project_index_dir
                from codrag.services.project_helpers import require_project
                from codrag.services.pipeline_metadata import update_heartbeat
                project = require_project(run.project_id)
                idx_dir = project_index_dir(project)
                update_heartbeat(idx_dir)
                logger.debug(
                    "Phase 61B: heartbeat for %s/%s stage %s",
                    run.project_id, run.group,
                    run.current_stage or "?",
                )
            except Exception:
                logger.debug("Phase 61B: heartbeat write failed", exc_info=True)

            # Schedule next tick if still active
            if run.is_active:
                timer = threading.Timer(self._HEARTBEAT_INTERVAL, _tick)
                timer.daemon = True
                timer.start()
                run._heartbeat_timer = timer  # type: ignore[attr-defined]

        # First heartbeat immediately, then every _HEARTBEAT_INTERVAL
        timer = threading.Timer(self._HEARTBEAT_INTERVAL, _tick)
        timer.daemon = True
        timer.start()
        run._heartbeat_timer = timer  # type: ignore[attr-defined]

    @staticmethod
    def _stop_heartbeat_timer(run: PipelineGroupStateMachine) -> None:
        """Cancel the heartbeat timer for a run."""
        timer = getattr(run, '_heartbeat_timer', None)
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass
            run._heartbeat_timer = None  # type: ignore[attr-defined]

    # ── Phase 48: Continuous Deepening Re-trigger ──────────────────

    _DEEPENING_CONVERGE_TARGET = 0.70
    _DEEPENING_RETRIGGER_DELAY = 30.0

    def _maybe_retrigger_deepening(self, project_id: str, pfl: Any = None) -> None:
        """Re-trigger deep enrichment if auto mode is on and deepening hasn't converged."""
        if not self._is_deep_enrichment_auto(project_id):
            return

        try:
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            from codrag.core import EpistemicEnricher, LLMClient
            from pathlib import Path

            project = require_project(project_id)
            idx_dir = project_index_dir(project)

            modules_path = idx_dir / "trace_modules.jsonl"
            if not modules_path.exists() or modules_path.stat().st_size == 0:
                return

            enricher = EpistemicEnricher(
                llm=LLMClient("http://localhost:11434", "none"),
                repo_root=Path(project.path),
                index_dir=idx_dir,
            )
            scores = enricher.compute_all_scores()
            if not scores:
                return
            composites = [s.composite for s in scores.values()]
            settled_count = sum(1 for c in composites if c >= 0.60)
            settled = settled_count / len(composites) if composites else 0.0
        except Exception:
            logger.debug("Could not compute settled_ratio for %s — skipping retrigger", project_id, exc_info=True)
            return

        if settled >= self._DEEPENING_CONVERGE_TARGET:
            logger.info(
                "Deepening converged for %s (%.1f%% >= %.1f%%) — no retrigger",
                project_id, settled * 100, self._DEEPENING_CONVERGE_TARGET * 100,
            )
            if pfl:
                pfl.log("deepening", f"Converged: {settled*100:.1f}%")
            return

        try:
            from codrag.services.pipeline_budget import budget as _budget
            if not _budget.check_allowed(project_id):
                logger.info("Budget exhausted for %s — deferring retrigger", project_id)
                return
        except Exception:
            pass

        logger.info(
            "Scheduling deepening retrigger for %s in %.0fs (settled=%.1f%%)",
            project_id, self._DEEPENING_RETRIGGER_DELAY, settled * 100,
        )
        if pfl:
            pfl.log("deepening", f"Re-trigger in {self._DEEPENING_RETRIGGER_DELAY:.0f}s (settled={settled*100:.1f}%)")

        import threading
        def _retrigger():
            try:
                started = self.run_deepening_only(project_id)
                logger.info("Deepening retrigger for %s: started=%s", project_id, started)
            except Exception as e:
                logger.warning("Deepening retrigger failed for %s: %s", project_id, e)

        timer = threading.Timer(self._DEEPENING_RETRIGGER_DELAY, _retrigger)
        timer.daemon = True
        timer.start()

    # ── Phase 50: Rules File Generation (post-stage hooks) ──────────

    @staticmethod
    def _read_graph_stats_from_manifest(idx_dir) -> Dict[str, Any]:
        """Read node/edge counts from trace_manifest.json for rules file stats.

        Returns a dict with node_count, edge_count, coverage_pct.
        Non-fatal — returns zeros on any error.
        """
        import json as _json
        stats: Dict[str, Any] = {"node_count": 0, "edge_count": 0, "coverage_pct": None}
        try:
            manifest_path = idx_dir / "trace_manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = _json.load(f)
                counts = manifest.get("counts", {})
                stats["node_count"] = counts.get("nodes_total", 0) or counts.get("files_parsed", 0)
                stats["edge_count"] = counts.get("edges_total", 0)
        except Exception:
            pass
        return stats

    @staticmethod
    def _write_atlas_signal(idx_dir) -> None:
        """D1: Write a timestamp signal file so the MCP server can detect atlas changes.

        The MCP server (separate process) polls this file on each tool_context()
        call. When the mtime is newer than last check, it invalidates its
        _rules_file_cache and sends notifications/resources/updated to the host.
        """
        import time
        from pathlib import Path as _Path
        try:
            signal_path = _Path(str(idx_dir)) / "atlas_updated.signal"
            signal_path.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass  # Non-fatal -- MCP server will still work, just won't get push freshness

    def _generate_preliminary_atlas_and_rules(self, project_id: str) -> None:
        """Generate a structural-only atlas and write/update IDE rules files.

        Called after Stage 1 (STRUCTURAL / Rust trace) completes. Takes ~100ms
        (no LLM). The atlas is replaced by the full LLM-generated version when
        Stage 9 (ATLAS) completes.

        Non-fatal — never blocks the pipeline.
        """
        try:
            from pathlib import Path
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            from codrag.core.atlas import CodebaseAtlas
            from codrag.core.rules_generator import write_rules_file

            project = require_project(project_id)
            idx_dir = project_index_dir(project)

            # Defensive: verify trace files exist before reading
            nodes_path = idx_dir / "trace_nodes.jsonl"
            if not nodes_path.exists() or nodes_path.stat().st_size == 0:
                logger.debug("trace_nodes.jsonl missing after Stage 1 — skipping preliminary atlas")
                return

            atlas = CodebaseAtlas(idx_dir, llm=None, project_root=Path(project.path))

            # ISSUE-I guard: If a full LLM atlas already exists (from a previous
            # pipeline run), do NOT overwrite it with a structural one.  Instead,
            # use the existing atlas content for the rules file and just refresh
            # the focus areas / stats.
            existing_doc = atlas.load()
            if existing_doc and existing_doc.mode == "llm" and existing_doc.content:
                logger.info(
                    "Phase 50: Existing LLM atlas found for %s — reusing for rules file (not downgrading)",
                    project_id,
                )
                doc = existing_doc
            else:
                # No LLM atlas yet — generate structural (no LLM, ~100ms)
                doc = atlas.generate_structural()

            if not doc or not doc.content:
                logger.debug("Structural atlas empty for %s — writing rules without atlas", project_id)

            # Gather stats for the rules file header
            stats = self._read_graph_stats_from_manifest(idx_dir)
            if doc and doc.file_count:
                stats.setdefault("node_count", doc.file_count)

            # Get included_paths from project config
            pcfg = project.config or {}
            included_paths = pcfg.get("included_paths") or []

            # If reusing an existing LLM atlas, this is not preliminary
            is_prelim = not (existing_doc and existing_doc.mode == "llm")

            write_rules_file(
                project_path=Path(project.path),
                project_name=project.name or project_id,
                atlas_content=doc.content if doc else "",
                included_paths=included_paths if included_paths else None,
                is_preliminary=is_prelim,
                stats=stats,
                ide="auto",
                project_id=project_id,
            )
            # D1: Write signal file so MCP server detects atlas change
            self._write_atlas_signal(idx_dir)

            # Phase 64A: Cache rudimentary role sub-atlases from structural data.
            # Uses path-based heuristics (no epistemic yet) — lower fidelity,
            # but agents can immediately get role-filtered context.
            try:
                role_cache = atlas.cache_role_atlases()
                logger.info(
                    "Phase 64A: Preliminary role atlases cached — %d roles",
                    len(role_cache),
                )
            except Exception:
                logger.debug(
                    "Phase 64A: Preliminary role atlas caching failed (non-fatal)",
                    exc_info=True,
                )

            logger.info(
                "Phase 50: Preliminary atlas + rules file written for %s (%d chars)",
                project_id, doc.char_count if doc else 0,
            )
        except Exception:
            logger.debug(
                "Phase 50: Preliminary atlas generation failed for %s (non-fatal)",
                project_id, exc_info=True,
            )

    def _regenerate_rules_with_full_atlas(self, project_id: str) -> None:
        """Regenerate IDE rules files with the full LLM-generated atlas.

        Called after Stage 9 (ATLAS) completes. Reads the atlas.json that the
        atlas worker just wrote and embeds it into the rules files, replacing
        the preliminary structural atlas from Stage 1.

        Non-fatal — never blocks the pipeline.
        """
        try:
            from pathlib import Path
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            from codrag.core.atlas import CodebaseAtlas
            from codrag.core.rules_generator import write_rules_file

            project = require_project(project_id)
            idx_dir = project_index_dir(project)

            # Load the full atlas that Stage 9 just generated
            atlas = CodebaseAtlas(idx_dir)
            doc = atlas.load()

            if not doc or not doc.content:
                logger.debug("No atlas.json found after Stage 9 for %s — skipping rules regen", project_id)
                return

            # Gather stats
            stats = self._read_graph_stats_from_manifest(idx_dir)
            if doc.file_count:
                stats.setdefault("node_count", doc.file_count)

            pcfg = project.config or {}
            included_paths = pcfg.get("included_paths") or []

            write_rules_file(
                project_path=Path(project.path),
                project_name=project.name or project_id,
                atlas_content=doc.content,
                included_paths=included_paths if included_paths else None,
                is_preliminary=False,
                stats=stats,
                ide="auto",
                project_id=project_id,
            )
            # D1: Write signal file so MCP server detects atlas change
            self._write_atlas_signal(idx_dir)

            logger.info(
                "Phase 50: Rules file updated with full LLM atlas for %s (%d chars, mode=%s)",
                project_id, doc.char_count, doc.mode,
            )
        except Exception:
            logger.debug(
                "Phase 50: Rules file regen failed for %s (non-fatal)",
                project_id, exc_info=True,
            )

    # ── CodeIndex Build (post-pipeline) ─────────────────────────────

    def _trigger_code_index_build(self, project_id: str, pfl: Any = None) -> None:
        """Trigger a CodeIndex build after deep enrichment completes.

        The pipeline builds KnowledgeIndex (knowledge_documents.json) but the
        /context search endpoint requires CodeIndex (documents.json +
        embeddings.npy).  This fires the build in the background so search
        works immediately after the pipeline finishes.
        """
        # Don't trigger index builds for inactive projects
        try:
            from codrag.services.project_helpers import get_project_activity_status
            if get_project_activity_status(project_id) != "active":
                logger.info("Skipping CodeIndex build for %s — project not active", project_id)
                return
        except Exception:
            pass

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

    def _journal_stage_started(self, run: PipelineGroupStateMachine, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_started(run.journal_run_id, stage.value, run.current_stage_index)
        except Exception:
            logger.debug("Journal stage_started write failed", exc_info=True)

    def _resume_queued_pipeline(self, project_id: str, stage: StageId) -> None:
        """Resume a pipeline that was waiting for compute capacity.

        Called when a scheduler slot frees up and a queued entry is dequeued.
        Finds the matching state machine, transitions it from QUEUED → RUNNING,
        and advances the pipeline.
        """
        # Find the state machine for this project
        matching_sm = None
        with self._lock:
            for key, sm in self._runs.items():
                if key[0] == project_id and sm.is_queued:
                    matching_sm = sm
                    break

        if matching_sm is None:
            logger.warning(
                "Scheduler: dequeued %s/%s but no QUEUED state machine found",
                project_id, stage.value,
            )
            return

        # Transition QUEUED → RUNNING
        if matching_sm.can_transition(Event.CAPACITY_AVAILABLE):
            matching_sm.transition(
                Event.CAPACITY_AVAILABLE,
                detail=f"compute slot available for {stage.value}",
            )
            logger.info(
                "Scheduler: resumed %s/%s from QUEUED → RUNNING",
                project_id, matching_sm.group,
            )

        # Advance the pipeline (will re-attempt the stage that was queued)
        if matching_sm.is_active:
            try:
                self._advance_pipeline(matching_sm)
            except Exception as exc:
                logger.exception(
                    "Scheduler: _advance_pipeline failed for resumed %s: %s",
                    project_id, exc,
                )

    def _journal_stage_completed(self, run: PipelineGroupStateMachine, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_completed(run.journal_run_id, stage.value)
        except Exception:
            logger.debug("Journal stage_completed write failed", exc_info=True)

    def _journal_stage_failed(self, run: PipelineGroupStateMachine, stage: StageId, error: str) -> None:
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_journal import journal
            journal.stage_failed(run.journal_run_id, stage.value, error)
        except Exception:
            logger.debug("Journal stage_failed write failed", exc_info=True)

    def _journal_run_completed(self, run: PipelineGroupStateMachine) -> None:
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

    def _create_checkpoint_if_needed(self, run: PipelineGroupStateMachine, stage: StageId) -> None:
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

    # ── Phase 70B: Freshness Check + Write Guard ─────────────────

    def _should_skip_stage_freshness(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> bool:
        """Check if a stage's outputs are already newer than its inputs.

        Returns True if the stage should be skipped (already current).
        Marks the stage as 'skipped' in the run and advances to the next.
        """
        try:
            from codrag.services.pipeline_integrity import (
                integrity_guard, STAGE_DATA_FILES,
            )
            from codrag.services.pipeline.stages import STAGE_INPUT_FILES
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))
            input_files = STAGE_INPUT_FILES.get(stage, [])
            output_files = STAGE_DATA_FILES.get(stage.value, [])

            if not input_files:
                return False  # structural has no pipeline inputs

            should_skip, reason = integrity_guard.check_stage_freshness(
                idx_dir, input_files, output_files,
            )

            if should_skip:
                logger.info(
                    "Stage %s skipped for %s: %s",
                    stage.value, run.project_id, reason,
                )
                if pfl:
                    pfl.log(stage.value, f"SKIPPED (freshness): {reason}")
                run.stage_results[stage.value] = "skipped"
                # Advance to next stage
                with self._lock:
                    run.advance()
                return True
        except Exception:
            logger.debug(
                "Freshness check failed (non-fatal) for %s/%s",
                run.project_id, stage.value, exc_info=True,
            )
        return False

    # ── Phase 70B: Write Guard ────────────────────────────────────

    def _write_guard_check(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> None:
        """Block pipeline advancement if a stage's output shrank.

        Compares post-stage file state against the pre-flight snapshot.
        Raises _WriteGuardBlocked if data would be lost. The pipeline
        should only grow the graph, never shrink it.
        """
        try:
            from codrag.services.pipeline_integrity import (
                integrity_guard, STAGE_DATA_FILES,
            )
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))
            data_files = STAGE_DATA_FILES.get(stage.value, [])

            if not data_files:
                return  # stage has no tracked output files

            post_files = {}
            for fname in data_files:
                fpath = idx_dir / fname
                post_files[fname] = integrity_guard._snapshot_file(fpath)

            blocked, reason = integrity_guard.should_block_stage_completion(
                run.project_id, stage.value, post_files,
            )

            if blocked:
                raise _WriteGuardBlocked(reason)

            if pfl:
                pfl.log(stage.value, "Write guard: OK")
        except _WriteGuardBlocked:
            raise  # re-raise to caller
        except Exception:
            logger.debug(
                "Write guard check failed (non-fatal) for %s/%s",
                run.project_id, stage.value, exc_info=True,
            )

    # ── Phase 60A: Integrity Guard ────────────────────────────────

    def _integrity_snapshot_before_stage(
        self, run: PipelineGroupStateMachine, stage: StageId,
    ) -> None:
        """Take a pre-flight snapshot of the stage's output files.

        Non-fatal: logged at DEBUG/INFO, never blocks the pipeline.
        """
        try:
            from codrag.services.pipeline_integrity import integrity_guard
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))

            is_incremental = run.project_id in self._incremental_runs

            snapshot = integrity_guard.snapshot_before_stage(
                run.project_id, stage.value, idx_dir,
                is_incremental=is_incremental,
            )

            # Log to pipeline file logger for verbose telemetry
            pfl = self._get_file_logger(run.project_id)
            if pfl:
                file_info = {}
                for fname, fs in snapshot.files.items():
                    if fs.exists:
                        file_info[fname] = f"{fs.record_count} records, {fs.size_bytes} bytes"
                    else:
                        file_info[fname] = "absent"
                pfl.log(
                    stage.value,
                    f"Integrity PRE-FLIGHT: {file_info}"
                    + (f" [INCREMENTAL]" if is_incremental else " [INITIAL]"),
                )
        except Exception:
            logger.debug(
                "Integrity guard pre-flight failed (non-fatal) for %s/%s",
                run.project_id, stage.value, exc_info=True,
            )

    def _integrity_check_after_stage(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> None:
        """Compare post-flight state against the pre-flight snapshot.

        Non-fatal: logged at INFO/WARNING, never blocks the pipeline.
        Writes detailed verdict to the pipeline file logger for post-hoc
        debugging of data loss issues.
        """
        try:
            from codrag.services.pipeline_integrity import integrity_guard
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project
            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))

            verdict = integrity_guard.check_after_stage(
                run.project_id, stage.value, idx_dir,
            )

            # Always log to pipeline file logger (verbose telemetry)
            if pfl:
                # Build a readable summary of per-file changes
                summaries = []
                for fname, fv in verdict.file_verdicts.items():
                    summary = fv.get("summary", f"{fname}: {fv.get('direction', '?')}")
                    summaries.append(summary)

                level_tag = verdict.level.upper()
                pfl.log(
                    stage.value,
                    f"Integrity POST-FLIGHT [{level_tag}]: "
                    + " | ".join(summaries),
                )

                # Extra detail for critical/warning verdicts
                if verdict.level in ("critical", "warning"):
                    import json
                    pfl.log(
                        stage.value,
                        f"Integrity DETAIL: {json.dumps(verdict.to_log_dict(), indent=2)}",
                    )
        except Exception:
            logger.debug(
                "Integrity guard post-flight failed (non-fatal) for %s/%s",
                run.project_id, stage.value, exc_info=True,
            )

    # ── Phase 25: Crash Recovery ──────────────────────────────────

    def startup_recovery(self) -> List[Any]:
        """Called once on daemon startup.  Detects crashed runs and hydrates
        PAUSED state machines for incomplete pipeline work.

        After a server crash, ``_runs`` is empty (in-memory only).  This
        method scans each project's disk state via ``_detect_resume_point()``
        and creates PAUSED state machines for any group with incomplete
        stages.  The user then sees "Paused" in the UI and can click Resume.

        Returns list of JournalEntry dicts for the UI to display.
        """
        # Phase 1: Journal-based crash detection (existing)
        journal_results: list = []
        try:
            from codrag.services.pipeline_journal import journal
            crashed = journal.recover_crashed_runs()
            self._crashed_runs = crashed
            if crashed:
                logger.warning(
                    "Crash recovery: found %d crashed pipeline run(s)", len(crashed)
                )
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
            journal_results = [e.to_dict() for e in crashed]
        except Exception:
            logger.debug("Journal crash recovery failed", exc_info=True)

        # Phase 2: Disk-state hydration — create PAUSED state machines for
        # projects with incomplete pipeline work so the UI shows the correct
        # state and Resume works after a crash/restart.
        try:
            self._hydrate_paused_runs_from_disk()
        except Exception:
            logger.debug("Disk-state hydration failed", exc_info=True)

        # Phase 61B: Active self-heal — detect stale/zombie metadata and
        # auto-trigger recovery if deep_enrichment auto mode is enabled.
        try:
            self._auto_recover_stale_pipelines()
        except Exception:
            logger.debug("Phase 61B auto-recovery failed", exc_info=True)

        return journal_results

    def _hydrate_paused_runs_from_disk(self) -> None:
        """Scan all projects and create PAUSED state machines for incomplete work.

        Called during startup_recovery.  For each project, checks fast_sync
        and deep_enrichment stage completion via _detect_resume_point().
        If a group has partially completed stages (resume_point > 0 but
        < len(stages)), creates a PAUSED SM at the resume point so the
        user can click Resume.
        """
        try:
            from codrag.services.project_helpers import get_registry
            registry = get_registry()
            projects = registry.list_projects()
        except Exception:
            logger.debug("Cannot list projects for disk-state hydration", exc_info=True)
            return

        for project in projects:
            pid = project.id
            # Skip if we already have an active run for this project
            # (shouldn't happen on fresh startup, but defensive)
            with self._lock:
                has_active = any(
                    run.is_active or run.is_paused
                    for key, run in self._runs.items()
                    if key[0] == pid
                )
            if has_active:
                continue

            for group, stages in [
                ("fast_sync", FAST_SYNC_STAGES),
                ("deep_enrichment", DEEP_ENRICHMENT_STAGES),
            ]:
                resume = self._detect_resume_point(pid, stages)
                if resume <= 0 or resume >= len(stages):
                    continue  # Nothing started, or all complete

                # Create a PAUSED state machine at the resume point
                sm = PipelineGroupStateMachine(
                    project_id=pid,
                    group=group,
                    stages=[s.value for s in stages],
                )
                sm.add_guard(self._default_guard)

                # Transition: IDLE → RUNNING → PAUSING → PAUSED
                sm.transition(Event.START)
                sm.current_stage_index = resume
                # Mark completed stages
                for i in range(resume):
                    sm.stage_results[stages[i].value] = "completed"
                sm.transition(Event.PAUSE)
                sm.transition(Event.STAGE_FLUSHED)

                with self._lock:
                    self._runs[(pid, group)] = sm

                logger.info(
                    "Hydrated PAUSED state for %s/%s at stage %d/%d (%s) "
                    "— user can Resume to continue",
                    pid, group, resume, len(stages), stages[resume].value,
                )

    def _auto_recover_stale_pipelines(self) -> None:
        """Phase 61B: Scan all projects for stale pipeline state and auto-recover.

        Called during startup_recovery AFTER hydrate_paused_runs_from_disk.
        For each project:
        1. Check pipeline_run_metadata.json — reset if zombie/stale
        2. Log manifest age summary for diagnostics
        3. If deep_enrichment auto mode is on and deep manifests are stale,
           auto-trigger run_deep_enrichment after a short delay
        """
        try:
            from codrag.services.project_helpers import get_registry
            registry = get_registry()
            projects = registry.list_projects()
        except Exception:
            logger.debug("Cannot list projects for Phase 61B auto-recovery", exc_info=True)
            return

        for project in projects:
            pid = project.id
            try:
                from codrag.core.project_registry import project_index_dir
                idx_dir = Path(project_index_dir(project))
            except Exception:
                continue

            # Get pipeline file logger for this project
            pfl = self._get_file_logger(pid)

            # Step 1: Check for stale/zombie metadata and reset
            try:
                from codrag.services.pipeline_metadata import (
                    check_heartbeat_stale, reset_stale_metadata,
                    load_run_metadata,
                )
                stale_info = check_heartbeat_stale(idx_dir)
                if stale_info:
                    logger.warning(
                        "Phase 61B: Detected %s pipeline metadata for %s "
                        "(run_id=%s, group=%s, age=%.0fs, heartbeat_age=%.0fs)",
                        stale_info["status"], pid,
                        stale_info.get("run_id"), stale_info.get("group"),
                        stale_info.get("age_seconds", 0),
                        stale_info.get("heartbeat_age_seconds", 0),
                    )
                    if pfl:
                        pfl.selfheal("stale_detected", f"{stale_info['status']} metadata found", stale_info)

                    reset_stale_metadata(idx_dir, reason="startup_recovery")
                    if pfl:
                        pfl.selfheal("metadata_reset", "Reset stale metadata to 'interrupted'", {
                            "project_id": pid,
                            "previous_status": stale_info["status"],
                        })
            except Exception:
                logger.debug("Phase 61B: stale check failed for %s", pid, exc_info=True)

            # Step 2: Log manifest age summary for diagnostics
            try:
                self._log_manifest_age_summary(pid, idx_dir, pfl)
            except Exception:
                logger.debug("Phase 61B: manifest age summary failed for %s", pid, exc_info=True)

            # Step 3: Auto-trigger deep enrichment if manifests are stale
            try:
                if not self._is_deep_enrichment_auto(pid):
                    if pfl:
                        pfl.selfheal("auto_recover", "Skipped — deep_enrichment auto mode is OFF", {
                            "project_id": pid,
                        })
                    continue

                # Check if deep manifests are stale vs structural trace
                structural_manifest = idx_dir / "trace_manifest.json"
                if not structural_manifest.exists():
                    continue

                structural_mtime = structural_manifest.stat().st_mtime
                deep_stale = False

                from .stages import STAGE_MANIFEST_FILE
                for stage in DEEP_ENRICHMENT_STAGES:
                    mf = STAGE_MANIFEST_FILE.get(stage)
                    if mf:
                        mp = idx_dir / mf
                        if not mp.exists():
                            deep_stale = True
                            break
                        if mp.stat().st_mtime < structural_mtime:
                            deep_stale = True
                            break

                if deep_stale:
                    # Skip if we already have an ACTIVE run (actually running)
                    # But if we have a PAUSED run (from hydration), clear it —
                    # auto mode means we should auto-resume, not wait for user.
                    with self._lock:
                        has_active = False
                        paused_keys = []
                        for key, run in self._runs.items():
                            if key[0] != pid:
                                continue
                            if run.is_active:
                                has_active = True
                                break
                            if run.is_paused:
                                paused_keys.append(key)

                    if has_active:
                        logger.info(
                            "Phase 61B: Deep manifests stale for %s but run already "
                            "active — skipping auto-recover",
                            pid,
                        )
                        continue

                    # Clear hydrated PAUSED runs so _start_group doesn't block
                    if paused_keys:
                        with self._lock:
                            for key in paused_keys:
                                del self._runs[key]
                        logger.info(
                            "Phase 61B: Cleared %d PAUSED hydrated runs for %s "
                            "— auto mode replaces manual Resume",
                            len(paused_keys), pid,
                        )
                        if pfl:
                            pfl.selfheal("auto_recover", "Cleared PAUSED runs for auto mode", {
                                "project_id": pid,
                                "cleared_keys": [str(k) for k in paused_keys],
                            })

                    logger.info(
                        "Phase 61B: Auto-recovering deep enrichment for %s "
                        "(deep manifests stale vs structural trace)",
                        pid,
                    )
                    if pfl:
                        pfl.selfheal("auto_recover", "Triggering deep enrichment — manifests stale", {
                            "project_id": pid,
                            "reason": "deep_manifests_stale_vs_structural",
                        })

                    # Delay to let the server fully initialize
                    import threading
                    _orch = self  # Capture reference for thread closure

                    def _delayed_recover(_pid=pid, _pfl=pfl, _orch=_orch):
                        try:
                            time.sleep(10)  # Wait for full server warmup
                            started = _orch.run_deep_enrichment(_pid)
                            logger.info("Phase 61B: Auto-recovery deep enrichment for %s: started=%s", _pid, started)
                            if _pfl:
                                _pfl.selfheal("auto_recover", f"run_deep_enrichment returned {started}", {
                                    "project_id": _pid,
                                    "started": started,
                                })
                            if not started:
                                # If deep enrichment didn't start, try run_all as fallback
                                logger.info("Phase 61B: run_deep_enrichment returned False, trying run_all for %s", _pid)
                                started2 = _orch.run_all(_pid)
                                logger.info("Phase 61B: Fallback run_all for %s: started=%s", _pid, started2)
                                if _pfl:
                                    _pfl.selfheal("auto_recover", f"Fallback run_all returned {started2}", {
                                        "project_id": _pid,
                                        "started": started2,
                                    })
                        except Exception as e:
                            logger.warning("Phase 61B: Auto-recovery failed for %s: %s", _pid, e, exc_info=True)
                            if _pfl:
                                _pfl.selfheal("auto_recover", f"Recovery FAILED: {e}", {
                                    "project_id": _pid,
                                    "error": str(e),
                                })

                    t = threading.Thread(target=_delayed_recover, daemon=True)
                    t.start()
                else:
                    if pfl:
                        pfl.selfheal("auto_recover", "No recovery needed — deep manifests up to date", {
                            "project_id": pid,
                        })

            except Exception:
                logger.debug("Phase 61B: auto-trigger check failed for %s", pid, exc_info=True)

    def _log_manifest_age_summary(self, project_id: str, idx_dir: Path, pfl: Any = None) -> None:
        """Log the age of all stage manifests for diagnostic purposes.

        This creates a comprehensive selfheal event showing exactly when
        each stage last completed — the first thing to check when the
        pipeline seems stuck.
        """
        from .stages import STAGE_MANIFEST_FILE, StageId
        from datetime import datetime, timezone

        now = time.time()
        manifest_ages: Dict[str, Any] = {}

        for stage in list(FAST_SYNC_STAGES) + list(DEEP_ENRICHMENT_STAGES):
            mf = STAGE_MANIFEST_FILE.get(stage)
            if not mf:
                manifest_ages[stage.value] = {"status": "no_manifest_mapping"}
                continue
            mp = idx_dir / mf
            if not mp.exists():
                manifest_ages[stage.value] = {"status": "missing"}
                continue
            mtime = mp.stat().st_mtime
            age_hours = round((now - mtime) / 3600, 1)
            manifest_ages[stage.value] = {
                "status": "present",
                "age_hours": age_hours,
                "last_modified": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            }

        if pfl:
            pfl.selfheal("manifest_age", f"Pipeline checkpoint age summary for {project_id}", {
                "project_id": project_id,
                "manifests": manifest_ages,
            })

        # Also log a one-line summary to the standard logger
        ages_str = ", ".join(
            f"{k}={v.get('age_hours', '?')}h" if v.get("status") == "present" else f"{k}=MISSING"
            for k, v in manifest_ages.items()
        )
        logger.info("Phase 61B manifest ages for %s: %s", project_id, ages_str)

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


    # ── Phase 49: Process Metadata ─────────────────────────────────

    def _write_stage_manifest_and_update_run(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        slot: Any,
    ) -> None:
        """Write an enhanced stage manifest and update the run metadata.

        Called after each stage completes successfully.  Non-fatal — never
        blocks the pipeline if metadata writing fails.
        """
        try:
            from codrag.core.stage_manifest import (
                create_stage_manifest, save_stage_manifest,
            )
            from codrag.core.provenance import (
                aggregate_quality_metrics, get_file_metadata,
                compute_throughput, aggregate_model_breakdown,
            )
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            project = require_project(run.project_id)
            idx_dir = project_index_dir(project)

            # Create manifest with provenance info
            manifest = create_stage_manifest(
                stage_id=stage.value,
                run_id=run.journal_run_id,
                project_id=run.project_id,
            )

            # Extract worker result from the build slot
            worker_result = getattr(slot, "result", None) or {}
            if isinstance(worker_result, dict):
                # Timing from worker
                timing = worker_result.get("_stage_timing", {})
                if timing:
                    from datetime import datetime, timezone
                    started_epoch = timing.get("started_at", 0)
                    if started_epoch:
                        manifest.started_at = datetime.fromtimestamp(
                            started_epoch, tz=timezone.utc
                        ).isoformat()
                    manifest.elapsed_seconds = timing.get("elapsed")
                    from datetime import datetime as dt2
                    manifest.finished_at = datetime.now(timezone.utc).isoformat()

                # Model info from worker
                model_info = worker_result.get("_model_info")
                if model_info:
                    task_id = STAGE_TASK_ID.get(stage)
                    model_info["task_id"] = task_id
                    manifest.model = model_info
                elif stage in (StageId.KNOWLEDGE, StageId.DEEP_KNOWLEDGE):
                    # Phase 55: Inject embedding model info manually
                    # Embeddings don't use the LLM subsystem so they don't produce _model_info.
                    # Use embedding_model (not model) to avoid overwriting KnowledgeIndex's
                    # own manifest.model string that it uses for incremental reuse detection.
                    try:
                        from codrag.server import _load_ui_config
                        cfg = _load_ui_config()
                        llm_cfg = cfg.get("llm_config") or {}
                        embed_cfg = llm_cfg.get("embedding") or {}
                        source = embed_cfg.get("source", "")
                        if source == "huggingface":
                            manifest.embedding_model = {
                                "provider": "native",
                                "model_name": "nomic-embed-text-v1.5",
                                "task_id": "knowledge_embedding",
                            }
                        elif source == "endpoint":
                            manifest.embedding_model = {
                                "provider": "ollama",
                                "model_name": embed_cfg.get("model", "nomic-embed-text"),
                                "task_id": "knowledge_embedding",
                            }
                        else:
                            # Auto-detect: check if NativeEmbedder is available
                            from codrag.core import NativeEmbedder
                            native = NativeEmbedder()
                            if native.is_available():
                                manifest.embedding_model = {
                                    "provider": "native",
                                    "model_name": "nomic-embed-text-v1.5",
                                    "task_id": "knowledge_embedding",
                                }
                            else:
                                manifest.embedding_model = {
                                    "provider": "ollama",
                                    "model_name": "nomic-embed-text",
                                    "task_id": "knowledge_embedding",
                                }
                    except Exception as e:
                        logger.warning("Failed to inject embedding model info: %s", e)

            # Quality metrics from output file
            output_file = STAGE_OUTPUT_FILE.get(stage)
            conf_field = STAGE_CONFIDENCE_FIELD.get(stage)
            if output_file and conf_field:
                output_path = idx_dir / output_file
                if output_path.exists():
                    quality = aggregate_quality_metrics(output_path, conf_field)
                    if quality:
                        manifest.quality = quality

                    # Throughput
                    total = quality.get("total_items", 0)
                    elapsed = manifest.elapsed_seconds or 0
                    if total > 0 and elapsed > 0:
                        manifest.throughput = compute_throughput(total, elapsed)

                    # Model breakdown (detects mid-stage model swaps)
                    breakdown = aggregate_model_breakdown(
                        output_path,
                        model_field="model",
                        confidence_field=conf_field,
                    )
                    if breakdown:
                        quality["model_breakdown"] = breakdown

                    # Output file metadata
                    manifest.output_files = {
                        output_file: get_file_metadata(output_path),
                    }

            # Save manifest
            manifest_filename = STAGE_MANIFEST_FILE.get(stage, f"{stage.value}_manifest.json")
            save_stage_manifest(manifest, idx_dir / manifest_filename)

            # Update run metadata
            self._update_run_metadata_for_stage(
                run, stage, worker_result, manifest_filename,
            )

        except Exception:
            logger.debug(
                "Phase 49: stage manifest write failed for %s/%s (non-fatal)",
                run.project_id, stage.value, exc_info=True,
            )

    def _update_run_metadata_for_stage(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        worker_result: Any,
        manifest_filename: str,
    ) -> None:
        """Update the in-memory run metadata after a stage completes."""
        try:
            from codrag.services.pipeline_metadata import (
                mark_stage_completed, save_run_metadata,
            )
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            key = (run.project_id, run.group)
            run_meta = self._run_metadata.get(key)
            if not run_meta:
                return

            mark_stage_completed(
                run_meta,
                stage.value,
                worker_result=worker_result if isinstance(worker_result, dict) else None,
                manifest_file=manifest_filename,
            )

            project = require_project(run.project_id)
            idx_dir = project_index_dir(project)
            save_run_metadata(run_meta, idx_dir)
        except Exception:
            logger.debug("Phase 49: run metadata update failed (non-fatal)", exc_info=True)

    def _finalize_run_metadata(self, run: PipelineGroupStateMachine, status: str) -> None:
        """Finalize run metadata on completion/failure and record in history."""
        try:
            from codrag.services.pipeline_metadata import (
                finalize_run_metadata, save_run_metadata, METADATA_FILENAME,
            )
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            key = (run.project_id, run.group)
            run_meta = self._run_metadata.get(key)
            if not run_meta:
                return

            project = require_project(run.project_id)
            idx_dir = project_index_dir(project)

            finalize_run_metadata(run_meta, status=status, index_dir=idx_dir)
            save_run_metadata(run_meta, idx_dir)

            # Record in history DB
            try:
                from codrag.services.pipeline_history import history
                metadata_file = str(idx_dir / METADATA_FILENAME)
                history.record_run(run_meta, metadata_file=metadata_file)
            except Exception:
                logger.debug("History record failed (non-fatal)", exc_info=True)

            # Clean up in-memory reference
            self._run_metadata.pop(key, None)

        except Exception:
            logger.debug("Phase 49: run metadata finalize failed (non-fatal)", exc_info=True)


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

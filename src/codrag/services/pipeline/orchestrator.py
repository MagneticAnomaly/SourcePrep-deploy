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
from .manifest_store import ManifestStore
from .recovery import RecoveryManager

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
        # Phase 53+: changed file paths for incremental structural rebuilds
        self._changed_paths: Dict[str, set[str]] = {}
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
    def _sync_downstream_manifest_mtimes(project_id: str, pfl: Any = None) -> None:
        """Touch all downstream manifest files to match structural mtime.

        Delegates to ManifestStore for mtime queries and touch operations.
        """
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            baseline_mtime = store.provenance_mtime(StageId.STRUCTURAL)
            if baseline_mtime == 0.0:
                return

            synced = []
            for stage in list(StageId):
                if stage == StageId.STRUCTURAL:
                    continue
                if store.provenance_exists(stage):
                    if store.provenance_mtime(stage) < baseline_mtime:
                        store.touch_provenance_mtime(stage, baseline_mtime)
                        synced.append(stage.value)

            if synced:
                logger.info(
                    "Phase 60D: Synced %d downstream manifest mtimes to structural "
                    "mtime (%.0f) for %s: %s",
                    len(synced), baseline_mtime, project_id, ", ".join(synced),
                )
                if pfl:
                    pfl.log("structural", f"Synced {len(synced)} downstream manifest mtimes")

        except Exception:
            logger.debug(
                "Failed to sync downstream manifest mtimes for %s (non-fatal)",
                project_id, exc_info=True,
            )

    @staticmethod
    def _try_restore_from_backup(
        project_id: str, stages: list, pfl: Any = None,
    ) -> bool:
        """Delegates to RecoveryManager.try_restore_from_backup."""
        return RecoveryManager.try_restore_from_backup(project_id, stages, pfl)

    @staticmethod
    def _touch_stale_deep_manifests(project_id: str) -> None:
        """Touch deep enrichment manifests so they match the catalogue mtime."""
        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            synced = store.sync_downstream_mtimes(StageId.CATALOGUE, list(DEEP_ENRICHMENT_STAGES))
            if synced:
                logger.debug("Touched %d deep manifests to match catalogue mtime", len(synced))
        except Exception:
            logger.debug(
                "Failed to touch stale deep manifests for %s (non-fatal)",
                project_id, exc_info=True,
            )

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
            # Use ManifestStore for atomic write
            try:
                store = ManifestStore(idx_dir)
                provenance = store.read_provenance(StageId.INFERRED_EDGES)
                if provenance:
                    file_hashes = provenance.get("file_hashes", {})
                    if file_hashes:
                        pruned_hashes = {
                            k: v for k, v in file_hashes.items()
                            if k in valid_paths
                        }
                        if len(pruned_hashes) < len(file_hashes):
                            provenance["file_hashes"] = pruned_hashes
                            store.write_provenance(StageId.INFERRED_EDGES, provenance)
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

        Phase 60D philosophy: ASSUME data exists and USE it.

        1. If all stages are complete and there are stale/untraced files,
           skip structural and start from inferred_edges (stage 1).
           Workers handle incrementality internally.
        2. If no data exists on disk, check backups FIRST.
        3. Only start from scratch if NO data and NO backup found.
        4. ``force_from_start=True`` is the ONLY way to get a true full
           rebuild — this should only be called from the "Destroy Graph"
           UI action, never automatically.
        """
        incremental = False
        # Phase 60D: Always skip mtime cascade — if data exists, USE IT.
        # Content-aware staleness in _detect_resume_point handles edge cases.
        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, FAST_SYNC_STAGES, skip_mtime_cascade=True,
        )

        # Phase 60A: Log the trigger decision to pipeline file logger
        pfl = self._get_file_logger(project_id)

        if force_from_start and pfl:
            pfl.decision("mode_selection", "force_from_start", {
                "group": "fast_sync",
                "reason": "Caller requested force_from_start=True",
                "resume_point": 0,
            })

        if resume >= len(FAST_SYNC_STAGES):
            # [Goal 5] Priority Inversion Check: If deep enrichment is INCOMPLETE,
            # DO NOT trigger new/stale queue processing. We must finish the pipeline first.
            from codrag.services.pipeline.stages import DEEP_ENRICHMENT_STAGES
            deep_resume = self._detect_resume_point(project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True)
            if deep_resume < len(DEEP_ENRICHMENT_STAGES):
                logger.info(
                    "Pipeline incomplete (deep resume=%d/4) for %s — skipping new/stale queue so it can finish",
                    deep_resume, project_id,
                )
                if pfl:
                    pfl.decision("mode_selection", "skip_queue_pipeline_incomplete", {
                        "group": "fast_sync",
                        "reason": f"Deep enrichment is incomplete ({deep_resume}/4) — prioritizing pipeline completion",
                    })
                return False

            # Phase 53: All manifests exist — but are there stale files?
            try:
                # Phase 72: Refresh file_hashes first to clear false
                # "stale" from the Phase 60D structural-skip.
                try:
                    refreshed = self._refresh_manifest_hashes(project_id)
                    if refreshed > 0:
                        logger.info(
                            "Pre-gap refresh: updated %d file hashes for %s",
                            refreshed, project_id,
                        )
                        if pfl:
                            pfl.log("fast_sync", f"Pre-gap: refreshed {refreshed} file hashes")
                except Exception:
                    pass  # Non-fatal

                gap = self.check_coverage_gap(project_id, include_paths=True)

                if pfl:
                    pfl.decision("coverage_gap", "checked", {
                        "group": "fast_sync",
                        "needs_rebuild": gap.get("needs_rebuild", False),
                        "stale": gap.get("stale", 0),
                        "untraced": gap.get("untraced", 0),
                        "coverage_pct": gap.get("coverage_pct", 0),
                        "total_nodes": gap.get("total_nodes", 0),
                    })

                stale = gap.get("stale", 0)
                untraced = gap.get("untraced", 0)

                if stale > 0 or untraced > 0:
                    changed_paths: set[str] = gap.get("changed_paths", set())
                    logger.info(
                        "All fast_sync stages complete but %d stale + %d untraced "
                        "files for %s — running %s update",
                        stale, untraced, project_id,
                        "incremental" if stale > 0 and untraced == 0 else "structural",
                    )
                    if changed_paths:
                        logger.info(
                            "[%s] Changed paths (%d): %s%s",
                            project_id, len(changed_paths),
                            ", ".join(sorted(changed_paths)[:20]),
                            f" ... (+{len(changed_paths) - 20} more)" if len(changed_paths) > 20 else "",
                        )

                    if untraced > 0:
                        # Reverting Phase 72's Root Cause 12 workaround:
                        # Skipping Structural (resume=1) causes new files to NEVER enter
                        # trace_nodes.jsonl, locking them in 'untraced' state forever.
                        # Running structural (resume=0) is safe because it only rebuilds
                        # the base AST cleanly and leaves trace_epistemic data fully intact.
                        resume = 0
                        incremental = True
                        logger.info(
                            "[%s] %d untraced files detected — running structural (resume=0) "
                            "to legally integrate them into trace_nodes.jsonl",
                            project_id, untraced,
                        )
                    else:
                        # Stale-only: skip structural (Phase 60D safety).
                        # Existing structural data is valid — only content changed.
                        # Re-running structural with the Rust engine would replace
                        # the rich Python-engine symbol data with a minimal
                        # file-level-only scan.
                        resume = 1  # Skip structural, start from inferred_edges
                        incremental = True

                    # Store changed paths so downstream workers can use them
                    if changed_paths:
                        self._changed_paths[project_id] = changed_paths

                    if pfl:
                        pfl.decision("mode_selection", "incremental" if incremental else "structural_rebuild", {
                            "group": "fast_sync",
                            "reason": f"All stages complete, {stale} stale + {untraced} untraced files",
                            "stale_files": stale,
                            "untraced_files": untraced,
                            "changed_path_count": len(changed_paths),
                            "resume_point": resume,
                        })
                else:
                    logger.info(
                        "All fast_sync stages complete and no stale/untraced files for %s — up to date",
                        project_id,
                    )
                    if pfl:
                        pfl.decision("mode_selection", "skip_up_to_date", {
                            "group": "fast_sync",
                            "reason": f"All stages complete, 0 stale, 0 untraced",
                            "coverage_pct": gap.get("coverage_pct", 0),
                        })
                    return False
            except Exception:
                logger.warning(
                    "Coverage gap check failed for %s — skipping structural (Phase 60D safety)",
                    project_id, exc_info=True,
                )
                # Safe default: skip structural, start from inferred_edges
                # to avoid Rust engine overwriting Python symbol data.
                resume = 1
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
            # Phase 60D: Before starting from scratch, check for backups.
            # ASSUME data exists somewhere — check backups before rebuilding.
            restored = self._try_restore_from_backup(project_id, FAST_SYNC_STAGES, pfl)
            if restored:
                # Backup restored — re-detect resume point from the restored data
                resume = self._detect_resume_point(project_id, FAST_SYNC_STAGES, skip_mtime_cascade=True)
                logger.info(
                    "[%s] Restored from backup, resuming from stage %d",
                    project_id, resume,
                )
            else:
                if pfl:
                    pfl.decision("mode_selection", "initial_full_run", {
                        "group": "fast_sync",
                        "reason": "No stages complete on disk AND no backup found — starting from scratch",
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

        Phase 60D philosophy: ASSUME data exists and USE it.  Only start
        from scratch if a stage has genuinely never produced output.
        Workers handle incrementality internally — they read existing
        output and only process new/changed nodes.  Restarting a stage
        that has hours of LLM reasoning is destructive and should NEVER
        happen automatically.
        """
        # Check if the preceding fast_sync was incremental.
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

        # Phase 60D: Always skip mtime cascade.  If data exists, it's valid.
        # Workers handle incremental updates internally.
        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
        )
        if resume >= len(DEEP_ENRICHMENT_STAGES):
            # All stages complete on disk.  Touch any stale manifests
            # to prevent future false-positive staleness detection.
            self._touch_stale_deep_manifests(project_id)
            logger.info(
                "All deep_enrichment stages complete for %s — "
                "nothing to do (changes will flow through fast_sync coverage gap)",
                project_id,
            )
            # Phase 72: Return False — do NOT reset resume=0.
            # The old code (resume=0) caused an infinite loop: every startup
            # would restart all 6 stages from scratch, burn LLM tokens on
            # clustering, and never actually complete because the next cycle
            # would restart again.  Changes should flow through fast_sync's
            # coverage gap detection → incremental chain → deep_enrichment.
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
            **self._get_branch_info(project_id),
        }

    def cancel_fast_sync(self, project_id: str) -> bool:
        """Cancel the Fast Sync group."""
        return self._cancel_group(project_id, "fast_sync")

    def _get_branch_info(self, project_id: str) -> Dict[str, Any]:
        """Get branch-aware backup info for a project (Phase 60B).

        Returns keys to merge into the pipeline status dict:
        - ``branch``: current Git branch (or None if not a Git repo)
        - ``branch_snapshots``: list of available branch snapshots
        - ``branch_state``: last-known branch state from disk

        Results are cached for 30s to avoid spawning ``git rev-parse``
        on every SSE event during an active pipeline run.
        """
        # Check cache (keyed by project_id, 30s TTL)
        cache_key = f"_branch_cache_{project_id}"
        cached = getattr(self, cache_key, None)
        if cached:
            ts, data = cached
            if time.time() - ts < 30:
                return data

        try:
            from codrag.services.branch_backup_manager import (
                detect_current_branch,
                list_snapshots,
                read_branch_state,
            )
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
            from datetime import datetime, timezone
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))

            current_branch = detect_current_branch(project.path)
            snapshots = list_snapshots(idx_dir)
            state = read_branch_state(idx_dir)

            # Only include transition_from if the switch was recent (< 5 min)
            # to avoid the "Restored" badge showing permanently in the UI.
            if state and state.get("transition_from") and state.get("switched_at"):
                try:
                    switched = datetime.fromisoformat(state["switched_at"])
                    age_s = (datetime.now(timezone.utc) - switched).total_seconds()
                    if age_s > 300:  # 5 minutes
                        state = {k: v for k, v in state.items() if k != "transition_from"}
                except Exception:
                    pass

            result = {
                "branch": current_branch,
                "branch_snapshots": snapshots,
                "branch_state": state if state else None,
            }
            setattr(self, cache_key, (time.time(), result))
            return result
        except Exception:
            logger.debug(
                "Phase 60B: branch info unavailable for %s",
                project_id, exc_info=True,
            )
            return {"branch": None, "branch_snapshots": [], "branch_state": None}

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
    def _refresh_manifest_hashes(project_id: str) -> int:
        """Refresh ``file_hashes`` in ``trace_manifest.json`` without re-running
        the structural stage.

        This fixes the Phase 60D incrementality gap: when the structural
        stage is skipped to protect rich symbol-level data, ``file_hashes``
        don't get updated.  Downstream stages process the changed files
        but the manifest still has stale hashes, causing
        ``check_coverage_gap()`` to report the same "stale" files forever.

        Algorithm:
          1. Read the current manifest.
          2. Walk eligible files on disk (same globs as coverage).
          3. For each file:
             - If its content hash differs from the manifest → update it.
             - If it's absent from the manifest but present in
               ``trace_nodes.jsonl`` → add it (backfill untraced).
          4. Remove hashes for files that no longer exist on disk.
          5. Atomically write the updated manifest (preserving ``built_at``
             to avoid a false mtime cascade).

        Returns the number of hashes that changed.
        """
        import json as _json
        import os
        import tempfile

        from codrag.core.ids import stable_file_hash
        from codrag.core.trace.utils import _detect_language, _to_posix

        try:
            from codrag.services.project_helpers import require_project
            from codrag.core.project_registry import project_index_dir
        except ImportError:
            return 0

        try:
            project = require_project(project_id)
        except Exception:
            return 0

        idx_dir = Path(project_index_dir(project))
        manifest_path = idx_dir / "trace_manifest.json"

        if not manifest_path.exists():
            return 0

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = _json.load(f)
        except Exception:
            return 0

        old_hashes: Dict[str, str] = manifest.get("file_hashes") or {}
        if not old_hashes:
            # No file_hashes at all — nothing we can incrementally update.
            # The structural stage needs to run first.
            return 0

        repo_root = Path(project.path).resolve()
        pcfg = project.config or {}
        max_file_bytes = int(pcfg.get("max_file_bytes") or 500_000)

        # Collect the set of traced paths from trace_nodes.jsonl
        # so we can add hashes for files that were traced by the
        # structural engine but never had hashes computed (e.g. new
        # files traced by the Rust engine).
        traced_node_paths: set[str] = set()
        nodes_path = idx_dir / "trace_nodes.jsonl"
        if nodes_path.exists():
            try:
                with open(nodes_path, "r", encoding="utf-8") as nf:
                    for line in nf:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            node = _json.loads(line)
                            if node.get("kind") == "file" and node.get("file_path"):
                                traced_node_paths.add(node["file_path"])
                        except _json.JSONDecodeError:
                            continue
            except Exception:
                pass  # Can't read nodes — skip backfill

        # Walk the repo to find current eligible files and their hashes.
        # Use the same globs as the TraceBuilder to stay consistent.
        from codrag.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
        import pathspec

        gitignore_spec = None
        gitignore_path = repo_root / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
            except Exception:
                pass

        # Re-use the builder's include globs (broad set)
        from codrag.core.trace.builder import TraceBuilder
        default_builder = TraceBuilder(
            repo_root=repo_root, index_dir=idx_dir,
            max_file_bytes=max_file_bytes,
        )
        include_globs = default_builder.include_globs
        exclude_globs = default_builder.exclude_globs

        from codrag.core.trace.utils import _is_relevant

        updated = 0
        new_hashes = dict(old_hashes)  # start with existing
        seen_paths: set[str] = set()

        for root_dir, dirs, filenames in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIR_NAMES and not d.startswith(".")]
            root_path = Path(root_dir)
            for fname in filenames:
                file_path = root_path / fname
                if file_path.is_symlink():
                    continue
                rel_path = _to_posix(str(file_path.relative_to(repo_root)))

                if gitignore_spec and gitignore_spec.match_file(rel_path):
                    continue
                if not _is_relevant(rel_path, include_globs, exclude_globs):
                    continue

                try:
                    fsize = file_path.stat().st_size
                    if fsize > max_file_bytes:
                        # Large file — read prefix for hash (same as builder)
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as hf:
                            source = hf.read(50_000)
                    else:
                        source = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                current_hash = stable_file_hash(source)
                seen_paths.add(rel_path)

                prev_hash = old_hashes.get(rel_path)
                if prev_hash is None:
                    # Not in manifest — only add if the structural trace
                    # actually contains this file (don't add truly new files
                    # that need a structural rebuild).
                    if rel_path in traced_node_paths:
                        new_hashes[rel_path] = current_hash
                        updated += 1
                elif prev_hash != current_hash:
                    new_hashes[rel_path] = current_hash
                    updated += 1

        # Remove hashes for files that were deleted from disk
        deleted_paths = set(old_hashes.keys()) - seen_paths
        for dp in deleted_paths:
            del new_hashes[dp]
            updated += 1

        if updated == 0:
            return 0

        # Write atomically — preserve built_at to avoid mtime cascade
        manifest["file_hashes"] = new_hashes
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", dir=str(idx_dir),
                delete=False, encoding="utf-8",
            )
            _json.dump(manifest, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, manifest_path)
            logger.info(
                "Refreshed %d file_hashes in trace_manifest.json for %s "
                "(added/updated: %d, deleted: %d)",
                updated, project_id,
                updated - len(deleted_paths), len(deleted_paths),
            )
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            logger.warning(
                "Failed to write updated file_hashes for %s",
                project_id, exc_info=True,
            )

        return updated

    @staticmethod
    def check_coverage_gap(project_id: str, include_paths: bool = False) -> Dict[str, Any]:
        """Check if there are files that should be traced but aren't.

        Uses ``compute_trace_coverage()`` to compare the filesystem against
        the trace manifest.

        Args:
            project_id: Project to check.
            include_paths: If True, include ``changed_paths`` (set of
                relative paths for untraced + stale files) so the caller
                can forward them to the structural worker for targeted
                rebuilds.

        Returns dict with:
          - total: total eligible files on disk
          - traced: files already traced and up-to-date
          - untraced: files eligible for trace but not yet traced
          - stale: files that were traced but content has changed
          - needs_rebuild: True if untraced + stale > 0
          - coverage_pct: percentage of files traced
          - changed_paths: (only when include_paths=True) set of rel paths
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

            result: Dict[str, Any] = {
                "total": summary.get("total", 0),
                "traced": summary.get("traced", 0),
                "untraced": untraced,
                "stale": stale,
                "needs_rebuild": (untraced + stale) > 0,
                "coverage_pct": summary.get("coverage_pct", 0.0),
            }

            if include_paths and result["needs_rebuild"]:
                changed: set[str] = set()
                for f in coverage.get("untraced", []):
                    changed.add(f["path"])
                for f in coverage.get("stale", []):
                    changed.add(f["path"])
                result["changed_paths"] = changed

            return result
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

                # Phase 72: Refresh file_hashes before checking coverage
                # to avoid false "stale" due to skipped structural stage.
                try:
                    refreshed = self._refresh_manifest_hashes(project_id)
                    if refreshed > 0:
                        logger.info(
                            "Coverage retrigger: refreshed %d file hashes for %s "
                            "before gap check",
                            refreshed, project_id,
                        )
                except Exception:
                    pass  # Non-fatal

                gap = self.check_coverage_gap(project_id)
                if not gap["needs_rebuild"]:
                    logger.info(
                        "Coverage check for %s: %d/%d files traced (%.1f%%) — "
                        "no retrigger needed",
                        project_id, gap["traced"], gap["total"],
                        gap["coverage_pct"],
                    )
                    return

                stale_count = gap.get("stale", 0)
                untraced_count = gap.get("untraced", 0)

                # Phase 72: Only retrigger for STALE files.
                # Untraced files need a structural rebuild — which we
                # deliberately skip (Phase 60D) — so retriggering just
                # creates an infinite loop.
                if stale_count == 0:
                    if untraced_count > 0:
                        logger.info(
                            "Coverage check for %s: 0 stale, %d untraced "
                            "(need structural rebuild) — no retrigger",
                            project_id, untraced_count,
                        )
                    return

                logger.info(
                    "Coverage gap detected for %s: %d untraced + %d stale "
                    "out of %d total files (%.1f%% coverage) — retriggering "
                    "fast sync",
                    project_id, untraced_count, stale_count,
                    gap["total"], gap["coverage_pct"],
                )
                if pfl:
                    pfl.log(
                        "coverage_gap",
                        f"Retriggering: {untraced_count} untraced + "
                        f"{stale_count} stale files",
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

        store = ManifestStore(idx_dir)

        # Get the structural manifest mtime as the "baseline" — any
        # downstream stage whose manifest is OLDER than this needs to
        # re-run because its input data (the trace graph) changed.
        baseline_mtime = 0.0
        if not skip_mtime_cascade:
            baseline_mtime = store.provenance_mtime(StageId.STRUCTURAL)

        # Phase 60A: Collect per-stage decisions for logging
        stage_decisions: list[dict] = []

        for i, stage in enumerate(stages):
            # The manifest file is the completion signal.
            # Workers write output incrementally (checkpoints) but only
            # write the manifest at the very end of a successful run.
            manifest_file = STAGE_MANIFEST_FILE.get(stage)
            if manifest_file:
                mpath = idx_dir / manifest_file  # for logging/size checks
                if store.provenance_exists(stage):
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
                        manifest_mtime = store.provenance_mtime(stage)
                        age_gap = baseline_mtime - manifest_mtime
                        if manifest_mtime < baseline_mtime:
                            # Phase 60C: Tolerance window — sub-second mtime
                            # differences are almost always false positives
                            # caused by the structural rebuild refreshing its
                            # manifest even when nothing changed.  Only treat
                            # as genuinely stale if the gap exceeds 5 seconds.
                            if age_gap <= 5.0:
                                logger.info(
                                    "Stage %s manifest mtime gap is %.1fs "
                                    "(within 5s tolerance) — treating as COMPLETE",
                                    stage.value, age_gap,
                                )
                                stage_decisions.append({
                                    "stage": stage.value, "decision": "COMPLETE",
                                    "note": f"mtime gap {age_gap:.1f}s within tolerance",
                                    "manifest_size": mpath.stat().st_size,
                                })
                                continue  # Within tolerance — not stale

                            # Phase 60D: Content-aware staleness — if the stage
                            # has existing output data, touching the manifest is
                            # sufficient.  Workers handle incrementality internally
                            # (they read existing output and only process new/changed
                            # nodes).  Cascade-restarting a stage with hours of LLM
                            # reasoning is destructive — we only do it when the stage
                            # has NEVER produced output.
                            output_file = STAGE_OUTPUT_FILE.get(stage)
                            has_existing_output = False
                            if output_file:
                                opath = idx_dir / output_file
                                if opath.exists() and opath.stat().st_size > 1024:
                                    has_existing_output = True
                            elif stage == StageId.ATLAS:
                                # Atlas doesn't have a single JSONL output, it produces an atlas.json
                                # plus segment files. If atlas.json exists, we have existing output.
                                opath = idx_dir / "atlas.json"
                                output_file = "atlas.json"  # For logging
                                if opath.exists() and opath.stat().st_size > 1024:
                                    has_existing_output = True

                            if has_existing_output:
                                # Touch manifest to match structural — prevents
                                # re-triggering on next resume check.  The worker
                                # will pick up delta changes when it next runs.
                                store.touch_provenance_mtime(stage, baseline_mtime)
                                logger.info(
                                    "Stage %s manifest is stale (gap=%.0fs) but has "
                                    "existing output (%s, %d bytes) — touching manifest "
                                    "and treating as COMPLETE (workers handle incrementality)",
                                    stage.value, age_gap, output_file,
                                    (idx_dir / output_file).stat().st_size,
                                )
                                stage_decisions.append({
                                    "stage": stage.value, "decision": "COMPLETE",
                                    "note": (
                                        f"mtime gap {age_gap:.0f}s but output exists "
                                        f"({output_file}) — manifest touched, "
                                        f"workers handle incrementality"
                                    ),
                                    "manifest_size": mpath.stat().st_size,
                                })
                                continue  # Treated as complete

                            # No output data — stage has never produced results,
                            # so cascade-restarting is correct.
                            logger.info(
                                "Stage %s manifest is stale (%.0f < %.0f, gap=%.1fs) "
                                "and has NO existing output — restarting stage",
                                stage.value, manifest_mtime, baseline_mtime, age_gap,
                            )
                            stage_decisions.append({
                                "stage": stage.value, "decision": "STALE_MTIME",
                                "reason": f"Manifest mtime {manifest_mtime:.0f} < structural mtime {baseline_mtime:.0f}",
                                "age_gap_seconds": round(age_gap, 1),
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

        # Phase 60B: Branch-aware backup — detect branch transitions and
        # snapshot/restore pipeline data so LLM reasoning survives branch
        # switches.  Only runs for the first group in a pipeline run
        # (fast_sync) to avoid double-snapshotting when run_all() chains.
        if group == "fast_sync":
            try:
                from codrag.services.branch_backup_manager import check_branch_transition
                from codrag.services.project_helpers import require_project
                from codrag.core.project_registry import project_index_dir
                project = require_project(project_id)
                max_backups = (project.config or {}).get("max_branch_backups", 3)
                transition = check_branch_transition(
                    project_path=project.path,
                    index_dir=Path(project_index_dir(project)),
                    max_backups=max_backups,
                )
                if transition:
                    logger.info(
                        "Phase 60B: Branch transition %s → %s for %s "
                        "(snapshot=%s, restored=%s, pruned=%s)",
                        transition["from_branch"], transition["to_branch"],
                        project_id,
                        transition["snapshot_created"],
                        transition["snapshot_restored"],
                        transition.get("pruned_branches", []),
                    )
                    if pfl:
                        pfl.selfheal("branch_transition", (
                            f"Detected branch change: "
                            f"{transition['from_branch']} → {transition['to_branch']}"
                        ), transition)
                    # Invalidate branch info cache so next status()
                    # call reflects the new branch immediately
                    cache_key = f"_branch_cache_{project_id}"
                    if hasattr(self, cache_key):
                        delattr(self, cache_key)
            except Exception:
                logger.debug(
                    "Phase 60B: branch check failed for %s (non-fatal)",
                    project_id, exc_info=True,
                )

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

                # Phase 72: After fast_sync completes, refresh file_hashes
                # in trace_manifest.json so that modified files are no longer
                # reported as "stale" by check_coverage_gap().  This is
                # necessary because the structural stage is skipped during
                # incremental runs (Phase 60D).
                try:
                    refreshed = self._refresh_manifest_hashes(run.project_id)
                    if refreshed > 0 and pfl:
                        pfl.log("fast_sync", f"Refreshed {refreshed} file hashes in manifest")
                except Exception as exc:
                    logger.warning(
                        "Failed to refresh manifest hashes for %s: %s",
                        run.project_id, exc,
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

        # Phase 70B: Freshness check — skip if outputs already current
        # Placed before heartbeat/journal so skipped stages don't start timers.
        if self._should_skip_stage_freshness(run, stage, pfl):
            return  # stage is already current, don't run it

        # Phase 60B: Backup restore — before rebuilding a stage from scratch,
        # check if a backup snapshot has valid data for this stage.  This
        # prevents re-running expensive LLM stages when good data already
        # exists from a previous run (e.g., branch snapshot, prior build).
        if self._try_restore_stage_from_backup(run, stage, pfl):
            return  # stage data restored from backup, skip running it

        # Phase 61B: Start heartbeat timer for this stage.
        # Writes to pipeline_run_metadata.json every 60s so the watchdog
        # can distinguish a genuinely running stage from a dead process.
        self._start_heartbeat_timer(run)

        # Phase 25: journal — record stage start
        self._journal_stage_started(run, stage)

        # Phase 25: checkpoint — backup trace files before destructive stages
        self._create_checkpoint_if_needed(run, stage)

        # Phase 60A: integrity guard — snapshot data files before stage runs
        self._integrity_snapshot_before_stage(run, stage)

        # Pass changed_paths to WorkerFactory for incremental structural rebuilds
        if stage == StageId.STRUCTURAL and run.project_id in self._changed_paths:
            WorkerFactory._changed_paths[run.project_id] = self._changed_paths.pop(run.project_id)

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
                        # Phase 60D: Touch all downstream manifests to match
                        # the new structural manifest mtime.  This prevents
                        # STALE_MTIME cascade — downstream workers handle
                        # incrementality internally.
                        self._sync_downstream_manifest_mtimes(project_id, pfl)
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
                    if matching_run.can_transition(Event.STAGE_FAILED):
                        matching_run.transition(Event.STAGE_FAILED, detail=f"WRITE GUARD BLOCKED: {wgb}")
                    self._unload_group_models(matching_run)
                    self._journal_pipeline_finished(matching_run)
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

        Delegates to ManifestStore. Non-fatal — returns zeros on any error.
        """
        try:
            store = ManifestStore(Path(idx_dir))
            return store.read_graph_stats()
        except Exception:
            return {"node_count": 0, "edge_count": 0, "coverage_pct": None}

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
        from codrag.services.pipeline.scheduler import pipeline_scheduler

        # Find the state machine for this project
        matching_sm = None
        with self._lock:
            for key, sm in self._runs.items():
                if key[0] == project_id and sm.is_queued:
                    matching_sm = sm
                    break

        if matching_sm is None:
            logger.warning(
                "Scheduler: dequeued %s/%s but no QUEUED state machine found — "
                "re-enqueuing to avoid losing the entry",
                project_id, stage.value,
            )
            # Re-enqueue so the entry isn't lost
            try:
                pipeline_scheduler.enqueue(project_id, stage)
            except Exception:
                logger.error(
                    "Scheduler: failed to re-enqueue lost entry %s/%s",
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
                    "Scheduler: _advance_pipeline failed for resumed %s: %s — "
                    "re-enqueuing",
                    project_id, exc,
                )
                # Re-enqueue so it can retry when next slot frees
                try:
                    pipeline_scheduler.enqueue(project_id, stage)
                    if matching_sm.can_transition(Event.ENQUEUE):
                        matching_sm.transition(
                            Event.ENQUEUE,
                            detail=f"re-enqueued after _advance_pipeline failure",
                        )
                except Exception:
                    logger.error(
                        "Scheduler: failed to re-enqueue after advance failure %s/%s",
                        project_id, stage.value,
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
        """Delegates to RecoveryManager.create_checkpoint_if_needed."""
        RecoveryManager.create_checkpoint_if_needed(run, stage)

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
        # Phase 60D: During incremental runs, the coverage gap check in
        # run_fast_sync already determined that stale/new files exist.
        # The freshness check compares output vs input file mtimes,
        # but during incremental runs the output from a PREVIOUS run
        # will be newer than inputs even though it doesn't cover all
        # files.  Workers handle incrementality internally — they skip
        # already-processed items and only do new ones.  Bypassing the
        # freshness gate ensures the worker actually runs.
        if run.project_id in self._incremental_runs:
            logger.debug(
                "Freshness check bypassed for %s/%s (incremental run — "
                "workers handle incrementality internally)",
                run.project_id, stage.value,
            )
            if pfl:
                pfl.log(stage.value, "Freshness check bypassed (incremental mode)")
            return False

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
                # Advance to next stage — no lock needed here since
                # the caller may already hold self._lock (which is not
                # reentrant). run.advance() only updates internal state.
                run.advance()
                return True
        except Exception:
            logger.debug(
                "Freshness check failed (non-fatal) for %s/%s",
                run.project_id, stage.value, exc_info=True,
            )
        return False

    # ── Phase 60B: Pre-Stage Backup Restore ─────────────────────

    def _try_restore_stage_from_backup(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> bool:
        """Delegates to RecoveryManager.try_restore_stage_from_backup."""
        return RecoveryManager.try_restore_stage_from_backup(run, stage, pfl)

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
                # Attempt auto-recovery before giving up
                recovered = self._attempt_write_guard_recovery(
                    run, stage, post_files, reason, pfl,
                )
                if not recovered:
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

    def _attempt_write_guard_recovery(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        post_files: Dict[str, Any],
        reason: str,
        pfl: Any = None,
    ) -> bool:
        """Attempt to recover from a write guard block.

        For deterministic stages (Rust, embedding): log that re-run is safe.
        For LLM stages: try to restore from the Phase 25 checkpoint.

        Returns True if recovery succeeded (pipeline can continue).
        Returns False if recovery failed (pipeline should halt).
        """
        from codrag.services.pipeline.stages import STAGE_IS_DETERMINISTIC

        is_deterministic = STAGE_IS_DETERMINISTIC.get(stage, False)

        if is_deterministic:
            # Deterministic stages (Rust, embedding) are cheap to re-run.
            # The write already happened (temp+rename), so we can't undo it
            # inline.  However, we should NOT blindly allow severe shrinkage
            # — the structural stage producing 10% of its previous output
            # means something went wrong (scope change, glob misconfiguration).
            #
            # Phase 60C: Allow minor shrinkage (<10% loss) as normal churn.
            # For severe shrinkage, try checkpoint restore first.
            import re
            # Extract shrinkage percentage from reason string
            pct_match = re.search(r'(\d+)% of original', reason)
            shrink_pct = int(pct_match.group(1)) if pct_match else 0

            if shrink_pct >= 90:
                # Minor loss (>=90% retained) — allow through
                logger.info(
                    "Write guard: deterministic stage %s lost ~%d%% for %s — "
                    "allowing (normal file churn)",
                    stage.value, 100 - shrink_pct, run.project_id,
                )
                if pfl:
                    pfl.log(stage.value, f"Write guard: allowed (minor deterministic loss): {reason}")
                return True

            # Severe shrinkage — try checkpoint restore
            logger.warning(
                "Write guard: deterministic stage %s produced severe shrinkage "
                "for %s (%s) — attempting checkpoint restore",
                stage.value, run.project_id, reason,
            )

        # LLM stage — try checkpoint restore
        try:
            from codrag.services.pipeline_checkpoint import restore_checkpoint
            from codrag.services.pipeline_journal import journal
            from codrag.core.project_registry import project_index_dir
            from codrag.services.project_helpers import require_project

            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))

            # Find the checkpoint for this run
            if run.journal_run_id:
                entry = journal.get_run(run.journal_run_id)
                if entry and entry.checkpoint_path:
                    restored = restore_checkpoint(entry.checkpoint_path, idx_dir)
                    if restored > 0:
                        logger.warning(
                            "Write guard: RESTORED %d files from checkpoint for "
                            "stage %s/%s (blocked: %s)",
                            restored, stage.value, run.project_id, reason,
                        )
                        if pfl:
                            pfl.log(
                                stage.value,
                                f"Write guard: RESTORED {restored} files from checkpoint ({reason})",
                            )
                        return True

            logger.critical(
                "Write guard: LLM stage %s produced data loss for %s (%s) "
                "and no checkpoint available for recovery",
                stage.value, run.project_id, reason,
            )
            if pfl:
                pfl.log(stage.value, f"Write guard: NO RECOVERY AVAILABLE ({reason})")
            return False
        except Exception as e:
            logger.error(
                "Write guard recovery failed for %s/%s: %s",
                run.project_id, stage.value, e, exc_info=True,
            )
            return False

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
        """Delegates to RecoveryManager.startup_recovery with orchestrator callbacks."""
        return RecoveryManager.startup_recovery(
            hydrate_fn=self._hydrate_paused_runs_from_disk,
            auto_recover_fn=self._auto_recover_stale_pipelines,
            set_crashed_runs=lambda runs: setattr(self, '_crashed_runs', runs),
        )

    def _hydrate_paused_runs_from_disk(self) -> None:
        """Delegates to RecoveryManager.hydrate_paused_runs_from_disk."""

        def _detect_resume(pid, stages, skip_mtime=True):
            return self._detect_resume_point(pid, stages, skip_mtime_cascade=skip_mtime)

        def _register_run(pid, group, sm):
            with self._lock:
                self._runs[(pid, group)] = sm

        def _is_active(pid):
            with self._lock:
                return any(
                    run.is_active or run.is_paused
                    for key, run in self._runs.items()
                    if key[0] == pid
                )

        RecoveryManager.hydrate_paused_runs_from_disk(
            detect_resume_fn=_detect_resume,
            register_run_fn=_register_run,
            is_run_active_fn=_is_active,
            default_guard=self._default_guard,
        )

    def _auto_recover_stale_pipelines(self) -> None:
        """Delegates to RecoveryManager.auto_recover_stale_pipelines."""

        def _is_active(pid):
            with self._lock:
                return any(run.is_active for key, run in self._runs.items() if key[0] == pid)

        def _clear_paused(pid):
            with self._lock:
                paused_keys = [
                    key for key, run in self._runs.items()
                    if key[0] == pid and run.is_paused
                ]
                for key in paused_keys:
                    del self._runs[key]
            return paused_keys

        RecoveryManager.auto_recover_stale_pipelines(
            is_deep_auto_fn=self._is_deep_enrichment_auto,
            get_file_logger_fn=self._get_file_logger,
            is_run_active_fn=_is_active,
            clear_paused_runs_fn=_clear_paused,
            run_deep_enrichment_fn=self.run_deep_enrichment,
        )

    def get_crashed_runs(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Delegates to RecoveryManager.get_crashed_runs."""
        return RecoveryManager.get_crashed_runs(project_id)

    def resume_crashed_run(self, run_id: str) -> bool:
        """Delegates to RecoveryManager.resume_crashed_run."""
        return RecoveryManager.resume_crashed_run(run_id, self._start_group)

    def discard_crashed_run(self, run_id: str) -> bool:
        """Delegates to RecoveryManager.discard_crashed_run."""
        return RecoveryManager.discard_crashed_run(run_id)


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

            # Save manifest — Phase 72: use ManifestStore for atomic writes
            manifest_filename = STAGE_MANIFEST_FILE.get(stage, f"{stage.value}_manifest.json")
            store = ManifestStore(Path(idx_dir))
            store.write_provenance(stage, manifest.to_dict())

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

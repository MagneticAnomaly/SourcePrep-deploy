"""
PipelineOrchestrator — sequences the 11-stage enrichment pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from prep.services.build_orchestrator import (
    BuildOrchestrator,
    BuildPhase,
    BuildType,
    build_orchestrator,
)


class _WriteGuardBlocked(Exception):
    """Raised when the write guard detects data loss and blocks pipeline advancement."""
    pass

from datetime import UTC

from .manifest_store import ManifestStore
from .post_flight import PostFlightActions
from .recovery import RecoveryManager
from .resume import ResumeStrategy
from .scheduler import pipeline_scheduler
from .stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    STAGE_BUILD_TYPE,
    STAGE_CONFIDENCE_FIELD,
    STAGE_MANIFEST_FILE,
    STAGE_MODEL_SLOT,
    STAGE_OUTPUT_FILE,
    STAGE_QUEUE_TYPE,
    STAGE_TASK_ID,
    QueueType,
    StageId,
)
from .state_machine import (
    ActiveProjectGuard,
    Event,
    PipelineGroupStateMachine,
    PipelineState,
)
from .workers import WorkerFactory

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Sequences the 15-stage pipeline in three groups.

    Uses BuildOrchestrator (SM-4) for individual stage execution and
    listens for completion events to advance the pipeline.

    Groups:
    - Fast Sync (stages 1-5): structural, catalogue, embeddings, clustering, topics
    - Deep Enrichment (stages 6-10): augmentation, deep knowledge, deepening, epistemic, cross-ref
    - Finalize (stages 11-15): atlas, rules, concepts, audit, antibodies

    Usage::

        pipeline.run_fast_sync("proj-1")
        pipeline.run_deep_enrichment("proj-1")
        pipeline.run_finalize("proj-1")
        pipeline.run_all("proj-1")  # fast sync → deep enrichment → finalize

        status = pipeline.status("proj-1")
    """

    def __init__(self, orchestrator: BuildOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or build_orchestrator
        self._lock = threading.Lock()
        # Active pipeline runs: (project_id, group) → state machine
        self._runs: dict[tuple[str, str], PipelineGroupStateMachine] = {}
        # Default guard: block START for inactive projects
        self._default_guard = ActiveProjectGuard()
        # Per-project pipeline file loggers
        self._file_loggers: dict[str, Any] = {}
        # Register for build completion events
        self._orchestrator.add_listener(self._on_build_transition)
        # Phase 25: cached crashed runs discovered at startup
        self._crashed_runs: list[Any] = []
        # Phase 49: per-run metadata objects
        self._run_metadata: dict[tuple[str, str], Any] = {}  # (project_id, group) → PipelineRunMetadata
        # Phase 53: track which projects are in incremental mode
        self._incremental_runs: set[str] = set()
        # Phase 53+: changed file paths for incremental structural rebuilds
        self._changed_paths: dict[str, set[str]] = {}
        # Explicit chain flag: run_all() sets this so deep_enrichment chains after fast_sync
        self._chain_deep: dict[str, bool] = {}
        # Explicit chain flag: run_all() sets this so finalize chains after deep_enrichment
        self._chain_finalize: dict[str, bool] = {}
        # Phase 89: Track force_from_start for chain propagation to deep enrichment
        self._force_from_start_runs: set[str] = set()
        # Phase 91: Drain timeout checker (runs every 30s while swarm window is active)
        self._drain_timer: threading.Timer | None = None

    def _start_drain_timer(self) -> None:
        """Start a periodic timer to check for drain timeouts."""
        self._stop_drain_timer()
        # Weak ref to self prevents timer from keeping orchestrator alive
        import weakref
        weak_self = weakref.ref(self)

        def _check():
            strong_self = weak_self()
            if strong_self is None:
                return  # Orchestrator was garbage collected
            try:
                timed_out = pipeline_scheduler.check_drain_timeouts()
                for pid in timed_out:
                    logger.warning(
                        "Phase 91: Drain timeout — force-cancelling %s", pid,
                    )
                    try:
                        strong_self.cancel(pid)
                    except Exception:
                        logger.warning(
                            "Phase 91: Failed to cancel drained project %s",
                            pid, exc_info=True,
                        )
            except Exception:
                logger.debug("Phase 91: Drain timeout check failed", exc_info=True)
            # Reschedule if swarm window is still active
            if pipeline_scheduler.is_swarm_window_active():
                strong_self._drain_timer = threading.Timer(30.0, _check)
                strong_self._drain_timer.daemon = True
                strong_self._drain_timer.start()
            else:
                strong_self._drain_timer = None

        self._drain_timer = threading.Timer(30.0, _check)
        self._drain_timer.daemon = True
        self._drain_timer.start()

    def _stop_drain_timer(self) -> None:
        """Stop the drain timeout checker."""
        if self._drain_timer:
            self._drain_timer.cancel()
            self._drain_timer = None

    def _get_file_logger(self, project_id: str):
        """Get or create a PipelineFileLogger for a project."""
        if project_id not in self._file_loggers:
            try:
                from prep.core.project_registry import project_index_dir
                from prep.services.project_helpers import require_project
                project = require_project(project_id)
                idx_dir = project_index_dir(project)
                from prep.services.pipeline_logger import PipelineFileLogger
                self._file_loggers[project_id] = PipelineFileLogger(idx_dir)
            except Exception:
                logger.debug("Could not create pipeline file logger for %s", project_id, exc_info=True)
                self._file_loggers[project_id] = None
        return self._file_loggers.get(project_id)

    @staticmethod
    def _persist_incremental_flag(project_id: str, is_incremental: bool) -> None:
        """Persist the incremental run flag to disk so it survives daemon restart."""
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            state_path = idx_dir / "pipeline_state.json"
            state: dict[str, Any] = {}
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
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
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
        """Touch all downstream manifest files to match structural mtime."""
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            synced = store.sync_downstream_mtimes(StageId.STRUCTURAL, list(StageId))
            if synced:
                logger.info(
                    "Phase 60D: Synced %d downstream manifest mtimes for %s: %s",
                    len(synced), project_id, ", ".join(synced),
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
    def _invalidate_deep_manifests_for_incremental(
        project_id: str, pfl: Any = None,
    ) -> None:
        """Invalidate deep enrichment manifests after incremental fast_sync.

        When fast_sync runs incrementally and adds new files to the trace graph,
        the deep enrichment stages (6-11) need to re-run to process those files.

        CRITICAL GUARD: Only invalidate if ALL deep stages were previously
        complete.  If any stages are already incomplete (missing manifests),
        they will naturally re-run — deleting manifests for complete stages
        would destroy checkpoint data (e.g. hours of Module Synthesis LLM
        work) for no benefit.  Workers handle incrementality internally by
        reading existing output and only processing new/changed nodes.
        """
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project

        project = require_project(project_id)
        idx_dir = Path(project_index_dir(project))
        store = ManifestStore(idx_dir)

        # Check if ALL deep stages are complete first
        incomplete = [
            stage for stage in DEEP_ENRICHMENT_STAGES
            if not store.provenance_exists(stage)
        ]
        if incomplete:
            # Some stages are already incomplete — they'll naturally re-run.
            # Don't destroy manifests for stages that already completed.
            msg = (
                f"Skipping deep manifest invalidation for {project_id}: "
                f"{len(incomplete)} stages already incomplete "
                f"({', '.join(s.value for s in incomplete)}) — "
                f"workers will handle incremental updates internally"
            )
            logger.info(msg)
            if pfl:
                pfl.log("fast_sync", msg)
            return

        # All stages were complete — mark as needing re-check by setting
        # a stale timestamp. Workers read existing output and only process
        # new/changed nodes, so this just forces them to wake up.
        #
        # IMPORTANT: We do NOT delete manifest files (p.unlink()).
        # Deleting them causes auto-recovery to interpret "missing manifest"
        # as "stage never ran" and triggers needless full re-runs on every
        # daemon restart, destroying hours of LLM synthesis work.
        # Instead, we just let the orchestrator notice that the deep stages
        # need to re-process the incremental additions organically.
        logger.info(
            "Incremental fast_sync for %s: deep stages were all complete. "
            "Workers will handle new files internally (manifests preserved).",
            project_id,
        )
        if pfl:
            pfl.log(
                "fast_sync",
                "Deep enrichment stages all complete — workers will handle "
                "new files internally (manifests preserved, not deleted)",
            )

    @staticmethod
    def _touch_stale_deep_manifests(project_id: str) -> None:
        """Touch deep enrichment manifests so they match the catalogue mtime."""
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project

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
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project

            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))

            nodes_path = idx_dir / "trace_nodes.jsonl"
            inferred_path = idx_dir / "trace_inferred_edges.jsonl"

            if not inferred_path.exists() or not nodes_path.exists():
                return

            # Build set of valid file paths from current trace graph
            valid_paths: set[str] = set()
            with open(nodes_path) as f:
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
            with open(inferred_path) as f:
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

    @staticmethod
    def _is_synthetic_paused(run: "PipelineGroupStateMachine") -> bool:
        """Distinguish a hydration synthetic-paused snapshot from a real user pause.

        Synthetic snapshots are constructed by `recovery.hydrate_paused_runs_from_disk`
        (recovery.py:999-1012) when the daemon starts and finds a partially-built
        group on disk. The construction path drives `START → PAUSE → STAGE_FLUSHED`
        within a single microsecond, producing the diagnostic fingerprint:

            - is_paused = True
            - finished_at - started_at < 0.01s (typically ~0.0001s)
            - journal_run_id is None (orchestrator never opened a real journal row)

        A user-triggered pause has the opposite shape:
            - finished_at - started_at >> 1s (real elapsed work)
            - journal_run_id is a uuid

        This is the F-NEW-0 / Phase 118 G3 diagnostic surfaced during the UI
        smoke phase. The state machine itself cannot distinguish the two; the
        orchestrator must.
        """
        if not run.is_paused:
            return False
        if run.journal_run_id is not None:
            return False
        if run.started_at is None or run.finished_at is None:
            return False
        return (run.finished_at - run.started_at) < 0.01

    def _check_project_active(self, project_id: str) -> bool:
        """F-69: Check if project is active before starting any pipeline.

        Returns False (and logs) if inactive. This is defense-in-depth
        on top of the ActiveProjectGuard — the guard only fires on the
        START transition, but some callers (auto-run, watcher, Phase 61B
        direct-call) bypass _start_group's guard timing.
        """
        try:
            from prep.services.project_helpers import get_project_activity_status
            status = get_project_activity_status(project_id)
            if status != "active":
                logger.info(
                    "Pipeline blocked for %s: project is %s",
                    project_id[:8], status,
                )
                return False
        except Exception:
            pass
        return True

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
        if not self._check_project_active(project_id):
            return False
        incremental = False
        # Phase 98: Selfheal pre-flight — resurrect missing stage data from backups
        if not force_from_start:
            self._selfheal_group(project_id, FAST_SYNC_STAGES)

        # Phase 60D: Always skip mtime cascade — if data exists, USE IT.
        # Content-aware staleness in _detect_resume_point handles edge cases.
        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, FAST_SYNC_STAGES, skip_mtime_cascade=True,
        )

        # Phase 60A: Log the trigger decision to pipeline file logger
        pfl = self._get_file_logger(project_id)

        # Phase 89: Track force_from_start so chain to deep enrichment preserves it
        if force_from_start:
            self._force_from_start_runs.add(project_id)
        else:
            self._force_from_start_runs.discard(project_id)

        if force_from_start and pfl:
            pfl.decision("mode_selection", "force_from_start", {
                "group": "fast_sync",
                "reason": "Caller requested force_from_start=True",
                "resume_point": 0,
            })

        # F-87: Wipe worker-level content-hash caches so individual workers
        # (InferredEdgesAnalyzer, EpistemicEnricher, KnowledgeIndex, etc.)
        # can't silently skip per-file work based on hash match. F-82 stopped
        # the orchestrator from skipping whole stages; this stops the workers
        # from skipping most of their own work. Branch snapshot (taken at
        # _start_group) and _golden checkpoint still hold the pre-rebuild
        # data, so F-84 cancel-revert is unaffected.
        if force_from_start:
            self._wipe_rebuild_caches(project_id, pfl, scope="fast_sync")
            # Phase 118 U16: clear any leftover watcher-derived
            # changed_paths set BEFORE the structural worker pops it.
            # Otherwise a partial set from a recent watcher event acts
            # as an unintended file filter on rebuild — the worker
            # processes only files in that set and silently SKIPS
            # everything else, including new files that the watcher
            # hadn't fired for yet AND stale files in different paths.
            # User-visible symptom: "rebuild seems to skip new and
            # stale files." The fix: a rebuild = full scan, ALWAYS.
            try:
                from prep.services.pipeline.workers import WorkerFactory
                self._changed_paths.pop(project_id, None)
                WorkerFactory._changed_paths.pop(project_id, None)
                if pfl:
                    pfl.decision("rebuild_changed_paths_cleared", "ok", {
                        "reason": "force_from_start: full scan (Phase 118 U16)",
                    })
            except Exception:
                logger.debug("U16 changed_paths clear failed (non-fatal)", exc_info=True)

        if resume >= len(FAST_SYNC_STAGES):
            # Phase 98 removed this guard with the assumption that "selfheal
            # + chain-forward handles incomplete deep enrichment naturally."
            # That assumption fails in two ways:
            #   1. Selfheal is BLOCKED while a reset barrier is active. When
            #      the barrier was set (reset / rebuild) and finalize hasn't
            #      cleared it yet, selfheal can't resurrect anything — deep
            #      enrichment ends up stuck and an incremental fast_sync run
            #      kicks off on top of incomplete state.
            #   2. Resurrecting partial mid-run files via stub manifests
            #      causes downstream stages to consume incomplete data
            #      (the original concern the barrier was added to prevent).
            # The guard is restored with one expansion: it now also blocks
            # when deep enrichment OR finalize is *paused* or *active*,
            # not just when manifests are incomplete. Force_from_start
            # rebuilds bypass the guard (intentional full restart).
            from prep.services.pipeline.stages import FINALIZE_STAGES

            # (a) Manifest completeness for downstream groups.
            deep_resume = self._detect_resume_point(
                project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
            )
            finalize_resume = self._detect_resume_point(
                project_id, FINALIZE_STAGES, skip_mtime_cascade=True,
            )
            downstream_incomplete = (
                deep_resume < len(DEEP_ENRICHMENT_STAGES)
                or finalize_resume < len(FINALIZE_STAGES)
            )

            # (b) Active/paused downstream runs in memory. Hydration on
            # daemon restart should populate self._runs from disk; if a
            # paused deep_enrichment run is sitting there, we MUST not
            # restart fast_sync underneath it.
            blocking_run: Optional[tuple[str, str]] = None
            with self._lock:
                for blocking_group in ("deep_enrichment", "finalize"):
                    other = self._runs.get((project_id, blocking_group))
                    if other and (other.is_active or other.is_paused):
                        blocking_run = (blocking_group, other.state.value)
                        break

            if downstream_incomplete or blocking_run is not None:
                reason_parts = []
                if downstream_incomplete:
                    reason_parts.append(
                        f"deep={deep_resume}/{len(DEEP_ENRICHMENT_STAGES)}, "
                        f"finalize={finalize_resume}/{len(FINALIZE_STAGES)}"
                    )
                if blocking_run is not None:
                    reason_parts.append(
                        f"{blocking_run[0]} is {blocking_run[1]}"
                    )
                reason = "; ".join(reason_parts)
                logger.info(
                    "[%s] Skipping incremental fast_sync — pipeline incomplete or busy: %s. "
                    "Run will be re-attempted after the downstream group settles.",
                    project_id, reason,
                )
                if pfl:
                    pfl.decision("mode_selection", "skip_queue_pipeline_incomplete", {
                        "group": "fast_sync",
                        "reason": reason,
                        "deep_resume": deep_resume,
                        "deep_total": len(DEEP_ENRICHMENT_STAGES),
                        "finalize_resume": finalize_resume,
                        "finalize_total": len(FINALIZE_STAGES),
                        "blocking_run": blocking_run,
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
                            "reason": "All stages complete, 0 stale, 0 untraced",
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
        elif not incremental and not force_from_start:
            # Phase 60D: Before starting from scratch, check for backups.
            # ASSUME data exists somewhere — check backups before rebuilding.
            #
            # F-52: Skip the backup-restore path entirely when the caller
            # passed force_from_start=True (Danger Zone "Rebuild" button).
            # Restoring from backup and re-detecting the resume point silently
            # undoes the user's explicit "throw away the existing data and
            # start over" request — every prior Phase 60D restore-then-resume
            # cycle would land at stage 5/5 (all done) and the rebuild would
            # complete in 0.0s without doing any work.
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
        elif force_from_start:
            # F-52: explicit log so the pipeline file logger captures the
            # decision to skip backup restoration on user-triggered rebuild.
            if pfl:
                pfl.decision("mode_selection", "force_from_start_skip_backup", {
                    "group": "fast_sync",
                    "reason": "Caller requested force_from_start=True — skipping backup restore",
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
        # GS-2/GS-3: prune orphan enrichments before running stages.
        # Only when data exists (resume > 0) and not a full rebuild.
        if resume > 0 and not force_from_start:
            try:
                from prep.core.project_registry import project_index_dir
                from prep.core.trace import prune_orphan_enrichments
                from prep.services.project_helpers import require_project
                proj = require_project(project_id)
                prune_result = prune_orphan_enrichments(project_index_dir(proj))
                if prune_result.get("total_pruned", 0) > 0 and pfl:
                    pfl.log("fast_sync", f"Pruned {prune_result['total_pruned']} orphan enrichments")
            except Exception:
                logger.debug("Pre-build orphan prune failed (non-fatal)", exc_info=True)

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
        if not self._check_project_active(project_id):
            return False
        # Phase 93: Don't start deep enrichment while fast_sync is active.
        # _start_group already has a cross-group guard (line ~1229), but that
        # check can miss timing windows when fast_sync and deep_enrichment
        # are triggered from different threads (e.g., recovery vs auto-run).
        # This early check provides defense-in-depth.
        #
        # Phase 118 G3: hydration synthetic-paused snapshots
        # (recovery.py:999-1012) look identical to user-paused runs — same
        # `is_paused=True`, but with `started_at ≈ finished_at` and
        # `journal_run_id is None` (the diagnostic fingerprint). For a
        # `force_from_start=True` rebuild — a deliberate user action — we
        # MUST NOT let a synthetic snapshot block the run. Detect and
        # discard the synthetic snapshot so the cross-group guard doesn't
        # mistake disk-derived state for an in-flight pause.
        with self._lock:
            fast_run = self._runs.get((project_id, "fast_sync"))
            if fast_run and force_from_start and self._is_synthetic_paused(fast_run):
                logger.info(
                    "[%s] Discarding synthetic-paused fast_sync snapshot for "
                    "deep rebuild (force_from_start=True)", project_id,
                )
                self._runs.pop((project_id, "fast_sync"), None)
                fast_run = None
            # F-64: also block when fast_sync is PAUSED — it will resume
            if fast_run and (fast_run.is_active or fast_run.is_paused):
                logger.info(
                    "[%s] Skipping deep enrichment — fast_sync is %s "
                    "(stage=%s). Deep enrichment will chain after fast_sync completes.",
                    project_id, fast_run.state.value, fast_run.current_stage,
                )
                return False

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

        # Phase 98: Selfheal pre-flight — resurrect missing stage data from backups
        if not force_from_start:
            self._selfheal_group(project_id, DEEP_ENRICHMENT_STAGES)

        # F-87: If Deep Enrichment was started directly with force_from_start=True
        # (not via the fast_sync chain, which already wiped), ensure the rebuild
        # flag + deep-stage cache wipe happen here too.
        # Scope is "deep_enrichment" so trace_augmented.jsonl (Stage 5 output)
        # is preserved — Stage 5 won't run to regenerate it, and Stage 6 reads it.
        if force_from_start:
            self._force_from_start_runs.add(project_id)
            self._wipe_rebuild_caches(
                project_id,
                self._get_file_logger(project_id),
                scope="deep_enrichment",
            )

        # Phase 60D: Always skip mtime cascade.  If data exists, it's valid.
        # Workers handle incremental updates internally.
        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, DEEP_ENRICHMENT_STAGES, skip_mtime_cascade=True,
        )
        if resume >= len(DEEP_ENRICHMENT_STAGES):
            if is_incremental:
                # Phase 89: After incremental fast_sync added new files, deep
                # enrichment must run to process them — even though all manifests
                # show "complete" from the previous run. Workers handle
                # incrementality internally (read existing output, process only
                # new/changed nodes). Resume from stage 0 so all stages get a
                # chance to pick up the new files.
                resume = 0
                logger.info(
                    "All deep_enrichment stages complete for %s, but preceding "
                    "fast_sync was incremental — re-running to process new files "
                    "(workers will skip already-done items)",
                    project_id,
                )
            else:
                # Truly nothing to do. Touch stale manifests to prevent
                # future false-positive staleness detection.
                self._touch_stale_deep_manifests(project_id)
                logger.info(
                    "All deep_enrichment stages complete for %s — "
                    "nothing to do",
                    project_id,
                )
                # Phase 72: Return False — do NOT reset resume=0.
                # The old code (resume=0) caused an infinite loop: every startup
                # would restart all 6 stages from scratch, burn LLM tokens on
                # clustering, and never actually complete because the next cycle
                # would restart again.
                return False

        if resume > 0:
            logger.info(
                "Resuming deep_enrichment for %s from stage %d/%d (%s)",
                project_id, resume, len(DEEP_ENRICHMENT_STAGES),
                DEEP_ENRICHMENT_STAGES[resume].value,
            )
        return self._start_group(project_id, "deep_enrichment", DEEP_ENRICHMENT_STAGES, resume_from=resume)

    def run_finalize(self, project_id: str, force_from_start: bool = False) -> bool:
        """Start the Finalize group (stages 11-15).

        Runs Atlas, Rules, Concepts, Audit, Antibodies.
        Auto-detects resume point from disk state.
        """
        if not self._check_project_active(project_id):
            return False
        from .stages import FINALIZE_STAGES
        # Don't start finalize while enrich is active or paused (F-64)
        with self._lock:
            enrich_run = self._runs.get((project_id, "deep_enrichment"))
            if enrich_run and (enrich_run.is_active or enrich_run.is_paused):
                logger.info(
                    "[%s] Skipping finalize — enrich is %s (stage=%s)",
                    project_id, enrich_run.state.value, enrich_run.current_stage,
                )
                return False

        # Phase 98: Selfheal pre-flight — resurrect missing stage data from backups
        if not force_from_start:
            self._selfheal_group(project_id, FINALIZE_STAGES)

        resume = 0 if force_from_start else self._detect_resume_point(
            project_id, FINALIZE_STAGES, skip_mtime_cascade=True,
        )
        if resume >= len(FINALIZE_STAGES):
            logger.info("All finalize stages complete for %s — nothing to do", project_id)
            return False

        if resume > 0:
            logger.info(
                "Resuming finalize for %s from stage %d/%d (%s)",
                project_id, resume, len(FINALIZE_STAGES),
                FINALIZE_STAGES[resume].value,
            )
        return self._start_group(project_id, "finalize", FINALIZE_STAGES, resume_from=resume)

    def run_single_stage(
        self,
        project_id: str,
        stage_id: StageId,
        *,
        force: bool = False,
    ) -> bool:
        """Queue a single finalize stage through the orchestrator (Phase 105a).

        Routes the same path as run_finalize but with a one-element stage
        list and the stage_id as the group identity. This gives solo runs
        first-class presence in the queue, journal, history, and UI stage
        state.

        Args:
            project_id: Project to run against.
            stage_id: A StageId from FINALIZE_STAGES. Sync/enrich stages
                are rejected — they must run via their group-level methods.
            force: Skip the selfheal pre-flight.

        Returns:
            True when queued; False when rejected (project inactive, another
            group active, or orchestrator otherwise declined).

        Raises:
            ValueError: stage_id is not a finalize stage.
        """
        from .stages import FINALIZE_STAGES
        if stage_id not in FINALIZE_STAGES:
            raise ValueError(
                f"{stage_id!r} is not a finalize stage; use run_fast_sync / "
                "run_deep_enrichment for sync/enrich stages."
            )

        if not self._check_project_active(project_id):
            return False

        # Don't start a solo finalize stage while sync OR enrich is active
        # or paused — solo finalize runs expect a quiescent pipeline. Stricter
        # than run_finalize's enrich-only guard on purpose: solo runs are
        # opportunistic, not part of the mainline pipeline sequence.
        with self._lock:
            for blocking_group in ("fast_sync", "deep_enrichment"):
                other = self._runs.get((project_id, blocking_group))
                if other and (other.is_active or other.is_paused):
                    logger.info(
                        "[%s] Skipping solo %s — %s is %s (stage=%s)",
                        project_id, stage_id.value, blocking_group,
                        other.state.value, other.current_stage,
                    )
                    return False

        if not force:
            self._selfheal_group(project_id, [stage_id])
        else:
            # force=True must also bypass the per-stage freshness check
            # (_should_skip_stage_freshness at line ~2972). Mirrors the
            # Rebuild flow (_start_group F-82 path). The flag is cleared by
            # the orchestrator when the run terminates. Without this,
            # clicking Regenerate when outputs are newer than inputs
            # silently no-ops in <50ms and looks like the button did
            # nothing — exactly the symptom seen on HomeColab.
            self._force_from_start_runs.add(project_id)

        return self._start_group(
            project_id, stage_id.value, [stage_id], resume_from=0,
        )

    def run_deepening_only(self, project_id: str) -> bool:
        """Run ONLY the Continuous Deepening and Deep Knowledge stages. Useful for retriggers."""
        from .stages import StageId
        stages = [StageId.DEEPENING, StageId.DEEP_KNOWLEDGE]
        return self._start_group(project_id, "deep_enrichment", stages)

    def swap_model(self, project_id: str, group: str) -> dict[str, Any]:
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

    def hot_scope_reload(self, project_id: str) -> dict[str, Any]:
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
            from prep.services.build_orchestrator import BuildSlot, BuildType
            # Run the trace worker directly (not via BuildOrchestrator)
            # to keep it synchronous and fast.  BuildSlot requires project_id
            # and build_type; cancel_token auto-inits via default_factory and
            # workers read it via slot.cancel_token.is_cancelled() — leaving
            # it None would crash the worker.
            _inline_slot = BuildSlot(project_id=project_id, build_type=BuildType.TRACE)
            result = worker(_inline_slot, lambda msg, cur, tot: logger.info(
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
        """Start Fast Sync, then chain Deep Enrichment, then Finalize.

        Phase 61B: If fast_sync is already up-to-date (returns False),
        directly calls run_deep_enrichment() instead of relying on the
        completion-handler chain — which never fires if fast_sync didn't run.

        Phase 96: Also chains finalize after deep enrichment completes.
        """
        # Start fast sync; deep enrichment will be chained via the listener
        with self._lock:
            key = (project_id, "fast_sync")
            run = self._runs.get(key)
            if run and run.is_active:
                return False
            # Mark that deep should chain after fast, and finalize after deep
            self._chain_deep[project_id] = True
            self._chain_finalize[project_id] = True
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

    def _emit_pipeline_status(self, project_id: str) -> None:
        """Emit a pipeline_status SSE event for the given project.

        Used after state machine transitions that don't go through the
        build_orchestrator (e.g. PAUSING→PAUSED) and would otherwise be
        invisible to the frontend until the next poll.
        """
        try:
            from prep.core.events import get_event_bus
            bus = get_event_bus()
            bus.emit("pipeline_status", {
                "project_id": project_id,
                **self.status(project_id),
            })
        except Exception:
            logger.debug("Pipeline status SSE emit failed (non-fatal)", exc_info=True)

    def has_active_run(self, project_id: str) -> bool:
        """Check if a project has any active or paused pipeline runs.

        F-67: PAUSED runs are included because they still own the project's
        files and will resume.  Without this, a graceful shutdown during a
        paused pipeline writes a clean-shutdown marker, causing the startup
        auto-run to skip recovery and lose the paused run's progress.
        """
        with self._lock:
            return any(
                run.is_active or run.is_paused
                for key, run in self._runs.items()
                if key[0] == project_id
            )

    def status(self, project_id: str) -> dict[str, Any]:
        """Get pipeline status for a project."""
        from .stages import FINALIZE_STAGES
        finalize_stage_values = {s.value for s in FINALIZE_STAGES}

        with self._lock:
            fast_run = self._runs.get((project_id, "fast_sync"))
            deep_run = self._runs.get((project_id, "deep_enrichment"))
            fin_run = self._runs.get((project_id, "finalize"))

        # Reconcile PAUSED-but-actually-done runs before callers read phase.
        # Done outside our _lock — reconcile_if_settled() takes the run's own
        # lock via transition(). Mirrors the same call in the queue endpoint so
        # both views converge on COMPLETED for settled runs.
        for run in (fast_run, deep_run, fin_run):
            if run is not None:
                run.reconcile_if_settled()

        with self._lock:

            # Phase 105a (C1): Expose solo finalize-stage runs through the
            # `finalize` slot so existing downstream consumers (useEnrichment.ts,
            # SSE pipeline_status events, the Graph Enrichment panel) pick them
            # up unchanged.  run_single_stage() registers runs under the stage
            # value as the group key — e.g. (pid, "atlas") — so they are
            # invisible to the three hardcoded lookups above.
            #
            # Strategy: if the traditional `finalize` group is absent (or
            # inactive), scan all _runs keys for this project that match a
            # finalize-stage value and pick the first active/paused one.
            # Prefer the traditional group run when both coexist (should not
            # happen, but defensive).
            solo_runs: list[Any] = []
            if not (fin_run and (fin_run.is_active or fin_run.is_paused)):
                for (pid, group), run in self._runs.items():
                    if pid == project_id and group in finalize_stage_values:
                        solo_runs.append(run)
                # Use the first active solo run, falling back to paused, then any.
                active_solo = next((r for r in solo_runs if r.is_active), None)
                paused_solo = next((r for r in solo_runs if r.is_paused), None)
                if active_solo or paused_solo:
                    fin_run = active_solo or paused_solo

        # F-41: walk the 15 stages via lock-free snapshots instead of
        # ``BuildOrchestrator.status()``.  The previous implementation
        # acquired ``BuildOrchestrator._lock`` 15 separate times in this
        # loop — and while each acquisition is individually fast, ANY
        # one of them could block while a worker thread held the lock
        # for a state transition.  With the dashboard polling
        # ``/pipeline/status`` every few seconds AND multiple groups
        # running concurrently, contention was essentially guaranteed,
        # leading to /pipeline/status timeouts and (eventually) full
        # daemon wedge as the status executor pool filled with awaiting
        # callers.
        #
        # ``snapshot()`` does not create slots, so for stages that have
        # never run we synthesize a minimal IDLE entry — equivalent to
        # what ``status()`` would have produced via _get_or_create_slot.
        stage_statuses = {}
        for stage_id in list(StageId):
            bt = STAGE_BUILD_TYPE[stage_id]
            slot = self._orchestrator.snapshot(project_id, bt)
            if slot is None:
                stage_statuses[stage_id.value] = {
                    "project_id": project_id,
                    "build_type": bt.value,
                    "phase": "idle",
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "duration_seconds": None,
                }
            else:
                stage_statuses[stage_id.value] = slot.to_dict()

        # Pick the run_id of the currently-active group so consumers
        # (dashboard, CLI, smoke harness) can bind to a single identifier
        # without having to probe each group's journal_run_id individually.
        active_run_id: Optional[str] = None
        for run in (fast_run, deep_run, fin_run):
            if run is not None and run.is_active and getattr(run, "journal_run_id", None):
                active_run_id = run.journal_run_id
                break

        return {
            "run_id": active_run_id,
            "fast_sync": fast_run.to_dict() if fast_run else None,
            "deep_enrichment": deep_run.to_dict() if deep_run else None,
            "finalize": fin_run.to_dict() if fin_run else None,
            "stages": stage_statuses,
            "any_running": (
                (fast_run.is_active if fast_run else False) or
                (deep_run.is_active if deep_run else False) or
                (fin_run.is_active if fin_run else False)
            ),
            "run_mode": "incremental" if project_id in self._incremental_runs else None,
            # Phase 72 Stage 4: Include stage snapshots for lock-free status reads.
            # Combines snapshots from all group runs (fast_sync + deep_enrichment +
            # finalize + any solo finalize-stage runs).
            "stage_snapshots": {
                **({k: v.to_dict() for k, v in fast_run.get_stage_snapshots().items()} if fast_run else {}),
                **({k: v.to_dict() for k, v in deep_run.get_stage_snapshots().items()} if deep_run else {}),
                **({k: v.to_dict() for k, v in fin_run.get_stage_snapshots().items()} if fin_run else {}),
                # Merge snapshots from all solo runs so stage_snapshots["atlas"] etc.
                # are always populated regardless of which finalize variant is in fin_run.
                **({k: v.to_dict() for r in solo_runs for k, v in r.get_stage_snapshots().items()}),
            },
            **self._get_branch_info(project_id),
        }

    def cancel_fast_sync(self, project_id: str) -> bool:
        """Cancel the Fast Sync group."""
        return self._cancel_group(project_id, "fast_sync")

    def _get_branch_info(self, project_id: str) -> dict[str, Any]:
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
            from datetime import datetime

            from prep.core.project_registry import project_index_dir
            from prep.services.branch_backup_manager import (
                detect_current_branch,
                list_snapshots,
                read_branch_state,
            )
            from prep.services.project_helpers import require_project
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
                    age_s = (datetime.now(UTC) - switched).total_seconds()
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

    def cancel_finalize(self, project_id: str) -> bool:
        """Cancel the Finalize group."""
        return self._cancel_group(project_id, "finalize")

    def pause_fast_sync(self, project_id: str) -> bool:
        """Pause the Fast Sync group.  The current stage flushes partial
        results and stops.  Resume with ``resume_paused()``."""
        return self._pause_group(project_id, "fast_sync")

    def pause_deep_enrichment(self, project_id: str) -> bool:
        """Pause the Deep Enrichment group."""
        return self._pause_group(project_id, "deep_enrichment")

    def pause_finalize(self, project_id: str) -> bool:
        """Pause the Finalize group."""
        return self._pause_group(project_id, "finalize")

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

        # User chose to resume — clear the pause-intent marker so a
        # subsequent restart does not re-pause this run.
        try:
            RecoveryManager.clear_user_pause_marker(project_id, group)
        except Exception:
            logger.debug("User pause marker clear failed", exc_info=True)

        # A resumed run is re-processing stages on top of partial data —
        # the rebuild-styled progress bars should fire so the user can
        # tell apart "fresh run" from "continuing prior work" at a
        # glance. The barrier auto-clears via maybe_clear_scoped_barrier
        # when the resumed group's boundary stage completes, so this is
        # self-cleaning. If a barrier is already active (the original
        # run was a force-rebuild), leave it untouched.
        try:
            from prep.services.pipeline.recovery import (
                read_reset_barrier,
                write_reset_barrier,
            )
            if read_reset_barrier(project_id) is None:
                _SCOPE = {
                    "fast_sync": "sync",
                    "deep_enrichment": "enrichment",
                    "finalize": "all",
                }
                write_reset_barrier(
                    project_id,
                    reason="rebuild",
                    scope=_SCOPE.get(group, "all"),
                )
        except Exception:
            logger.debug("Resume barrier write failed (non-fatal)", exc_info=True)

        logger.info(
            "Resuming paused run %s/%s from stage %d (%s)",
            project_id, group,
            run.current_stage_index,
            run.current_stage or "?",
        )

        # Re-start the current stage — worker will skip already-done items
        self._advance_pipeline(run)
        return True

    def force_reset_stale_runs(self, project_id: str, max_age_seconds: float = 600) -> list[str]:
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
        reset_groups: list[str] = []
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
        # Phase 89 WS4: Cancel running builds before clearing state.
        # This ensures scheduler locks are released (via WS2 cancel fix).
        self.cancel_fast_sync(project_id)
        self.cancel_deep_enrichment(project_id)
        with self._lock:
            keys = [k for k in self._runs if k[0] == project_id]
            for k in keys:
                del self._runs[k]
        self._orchestrator.clear_project(project_id)
        # Clear cached file logger so it doesn't reference stale paths
        self._file_loggers.pop(project_id, None)

    # ── Coverage Gap Detection ─────────────────────────────────


    @staticmethod
    def _refresh_manifest_hashes(project_id: str) -> int:
        """Delegates to ResumeStrategy.refresh_manifest_hashes."""
        return ResumeStrategy.refresh_manifest_hashes(project_id)

    @staticmethod
    def check_coverage_gap(project_id: str, include_paths: bool = False) -> dict[str, Any]:
        """Delegates to ResumeStrategy.check_coverage_gap."""
        return ResumeStrategy.check_coverage_gap(project_id, include_paths)
    def _maybe_retrigger_for_coverage(
        self, project_id: str, group: str, pfl: Any = None,
    ) -> None:
        """Delegates to ResumeStrategy.maybe_retrigger_for_coverage."""
        def _is_active(pid):
            with self._lock:
                return any(
                    run.is_active or run.is_paused or run.is_queued
                    for key, run in self._runs.items()
                    if key[0] == pid
                )

        ResumeStrategy.maybe_retrigger_for_coverage(
            project_id,
            run_fast_sync_fn=self.run_fast_sync,
            is_any_active_fn=_is_active,
            refresh_hashes_fn=self._refresh_manifest_hashes,
            pfl=pfl,
        )
    def _resolve_node_for_stage(
        self, project_id: str, stage: StageId,
    ) -> str | None:
        """Resolve which compute node handles this stage's model.

        Walks the chain:  stage → model slot → endpoint → provider + model → node_id.
        Returns None for non-LLM stages (Rust, Embedding).
        """
        slot_name = STAGE_MODEL_SLOT.get(stage)
        if not slot_name:
            return None  # Rust / Embedding — no LLM node

        try:
            from prep.services.settings_store import settings
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

    def _resolve_model_for_stage(
        self, project_id: str, stage: StageId,
    ) -> tuple[str | None, str | None]:
        """Return (provider, model) for a stage's configured LLM.

        Used by Phase 91 swarm window to check if the model supports swarm.
        """
        slot_name = STAGE_MODEL_SLOT.get(stage)
        if not slot_name:
            return None, None
        try:
            from prep.services.settings_store import settings
            llm_config = settings.get("llm_config") or {}
        except Exception:
            return None, None
        slot_key = f"{slot_name}_model"
        slot_config = llm_config.get(slot_key, {})
        model = slot_config.get("model", "")
        endpoint_id = slot_config.get("endpoint_id")
        if not endpoint_id:
            return None, None
        provider = "ollama"
        for ep in llm_config.get("saved_endpoints", []):
            if ep.get("id") == endpoint_id:
                provider = ep.get("provider", "ollama")
                break
        return provider, model

    def _is_cloud_node(self, node_id: str | None) -> bool:
        """Check if a node ID refers to a cloud compute node."""
        return node_id is not None and node_id.startswith("cloud:")

    # ── Internal ───────────────────────────────────────────────

    def _selfheal_group(
        self, project_id: str, stages: list, force_from_start: bool = False,
    ) -> dict:
        """Pre-flight selfheal: resurrect missing stage data from backups."""
        pfl = self._get_file_logger(project_id)
        return RecoveryManager.selfheal_group(
            project_id, stages,
            force_from_start=force_from_start,
            pfl=pfl,
        )

    def _detect_resume_point(
        self,
        project_id: str,
        stages: list[StageId],
        skip_mtime_cascade: bool = False,
    ) -> int:
        """Delegates to ResumeStrategy.detect_resume_point."""
        return ResumeStrategy.detect_resume_point(
            project_id, stages, skip_mtime_cascade,
            pfl_fn=self._get_file_logger,
        )
    @staticmethod
    def _is_deep_enrichment_auto(project_id: str) -> bool:
        """Check if deep enrichment should auto-chain after fast sync.

        Reads per-project auto_config first, falls back to global.
        Independent of the fastSync toggle: users can run fast sync
        automatically (on file change) and still want deep enrichment
        to wait for the Run button.

        Note: 'scheduled' is NOT auto-chain — scheduled runs fire on
        their own cadence, not immediately after fast sync.
        """
        try:
            from prep.services.project_helpers import require_project
            proj = require_project(project_id)
            pcfg = proj.config if isinstance(proj.config, dict) else {}
            auto_cfg = pcfg.get("auto_config")
            if auto_cfg and isinstance(auto_cfg, dict):
                deep = auto_cfg.get("deepEnrichment", auto_cfg.get("deep_enrichment", "manual"))
                return deep == "auto"
        except Exception:
            pass
        # Fallback to global config
        try:
            from prep.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            deep_mode = (config.get("deep_enrichment") or {}).get("mode", "manual")
            return deep_mode == "auto"
        except Exception:
            return False

    @staticmethod
    def _is_finalize_auto(project_id: str) -> bool:
        """Check if finalize should auto-chain after deep enrichment.

        Independent of the deepEnrichment toggle: users can have deep
        enrichment running automatically and still want finalize to
        wait for the Run button (common for manual concept review
        before triggering atlas/audit/antibodies regeneration).
        """
        try:
            from prep.services.project_helpers import require_project
            proj = require_project(project_id)
            pcfg = proj.config if isinstance(proj.config, dict) else {}
            auto_cfg = pcfg.get("auto_config")
            if auto_cfg and isinstance(auto_cfg, dict):
                fin = auto_cfg.get("finalize", "manual")
                return fin == "auto"
        except Exception:
            pass
        # Fallback to global config
        try:
            from prep.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            fin_mode = (config.get("finalize") or {}).get("mode", "manual")
            return fin_mode == "auto"
        except Exception:
            return False

    def _start_group(
        self, project_id: str, group: str, stages: list[StageId],
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
            # Block if this group is already running OR paused. The paused
            # case is critical: hydration on daemon restart rebuilds a
            # PAUSED state machine for whatever the user was working on,
            # and _startup_auto_run runs in parallel with the recovery
            # path. Without including paused here, a fresh state machine
            # would silently overwrite the hydrated pause and the pipeline
            # would auto-resume past the user's stopping point — exactly
            # the "I paused, restarted, and stages got skipped" report.
            # Callers wanting to override (an explicit force-rebuild)
            # must first cancel the paused run; resume_paused() is the
            # supported path for continuing.
            key = (project_id, group)
            existing = self._runs.get(key)
            if existing and (existing.is_active or existing.is_paused):
                if existing.is_paused:
                    logger.info(
                        "[%s] Skipping %s start — group is PAUSED at stage %s. "
                        "User must click Resume (or Cancel and re-run).",
                        project_id, group, existing.current_stage,
                    )
                return False

            # NOTE: the previous Phase 118 G3 logic auto-discarded
            # "synthetic-paused" snapshots from OTHER groups before the
            # cross-group guard runs. After the always-paused-on-restart
            # rule, hydrated paused runs ARE meaningful user/safety state
            # — auto-discarding them would defeat the explicit-Resume
            # contract. Force-rebuild callers (run_deep_enrichment with
            # force_from_start=True) still pop synthetic snapshots
            # themselves before reaching here, so deliberate overrides
            # still work; this guard simply no longer second-guesses
            # the user's intent.

            # Block if ANY other group for the same project is active or paused.
            # F-64: PAUSED groups still own the project's files and will resume.
            # Starting a concurrent group while another is paused causes both
            # to run simultaneously when the paused group resumes, corrupting
            # shared pipeline state (e.g. knowledge embedding + deep reasoning
            # running at the same time).
            for run_key, run_obj in self._runs.items():
                if run_key[0] == project_id and run_key[1] != group and (run_obj.is_active or run_obj.is_paused):
                    logger.warning(
                        "Cannot start %s/%s — %s is %s for this project",
                        project_id, group, run_key[1], run_obj.state.value,
                    )
                    return False

        with self._lock:

            # Determine robust UI mode flag
            mode = "initial"
            if resume_from > 0:
                mode = "incremental"
            else:
                try:
                    from pathlib import Path

                    from prep.core.project_registry import project_index_dir
                    from prep.services.pipeline.stages import STAGE_OUTPUT_FILE
                    from prep.services.project_helpers import require_project

                    if stages:
                        proj_idx = Path(project_index_dir(require_project(project_id)))
                        first_stage = stages[0]
                        out_file = STAGE_OUTPUT_FILE.get(first_stage)
                        if out_file:
                            opath = proj_idx / out_file
                            if opath.exists() and opath.stat().st_size > 100:
                                mode = "incremental"
                except Exception:
                    pass

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
            from prep.services.pipeline_journal import journal
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
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_metadata import (
                create_run_metadata,
                save_run_metadata,
            )
            from prep.services.project_helpers import require_project
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
            from prep.core.rules_generator import detect_and_regenerate
            from prep.services.project_helpers import require_project
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
                from prep.core.project_registry import project_index_dir
                from prep.services.branch_backup_manager import check_branch_transition
                from prep.services.project_helpers import require_project
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

            # Phase 89: Release scheduler lock on pipeline completion.
            # When all stages are done (including via skip/freshness),
            # release any held lock so queued pipelines can proceed.
            # The release-after-advance block in _on_build_transition()
            # only handles the normal stage completion path — this
            # handles the "all stages done" path (skip, restore, chain).
            if pipeline_scheduler.is_held_by(run.project_id):
                _release_node = getattr(run, '_current_node_id', None)
                # Find the last stage to release (current_stage_index points past end)
                _last_stage_idx = len(run.stages) - 1
                if _last_stage_idx >= 0:
                    _last_stage = StageId(run.stages[_last_stage_idx])
                    _deferred = pipeline_scheduler.release(
                        run.project_id, _last_stage, _release_node,
                    )
                    if _deferred:
                        self._resume_queued_pipeline(
                            _deferred.project_id, _deferred.stage,
                        )

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
                from prep.services.pi_agent import get_pi_agent
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
                # Phase 74: Concept seeding now handled by Stage 13 (CONCEPTS) in Finalize group
            # Phase 48 (P48-F5): After deep enrichment completes in auto mode,
            # check if deepening has converged. If not, re-trigger.
            if run.group == "deep_enrichment":
                self._maybe_retrigger_deepening(run.project_id, pfl)

            # Phase 117: Clear barrier if scope="enrichment" (deep_enrichment boundary)
            if run.group == "deep_enrichment":
                try:
                    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
                    maybe_clear_scoped_barrier(run.project_id, completed_group="deep_enrichment")
                except Exception:
                    logger.debug(
                        "maybe_clear_scoped_barrier failed (non-fatal) for %s",
                        run.project_id, exc_info=True,
                    )

            # Chain finalize after enrich if configured or explicitly requested
            if run.group == "deep_enrichment":
                should_chain_fin = False
                if self._chain_finalize.pop(run.project_id, False):
                    should_chain_fin = True
                if not should_chain_fin:
                    is_auto = self._is_finalize_auto(run.project_id)
                    if is_auto:
                        should_chain_fin = True
                if should_chain_fin:
                    logger.info(
                        "Chaining finalize for %s after enrich completed",
                        run.project_id,
                    )
                    try:
                        self.run_finalize(run.project_id)
                    except Exception:
                        logger.debug(
                            "Finalize chain failed for %s (non-fatal)",
                            run.project_id, exc_info=True,
                        )

            # Log finalize group completion
            if run.group == "finalize":
                logger.info("Finalize complete for %s", run.project_id)
                # Clear the reset barrier: every stage now has a genuine
                # manifest, so subsequent selfheal runs can safely consider
                # orphan outputs and backup sources again.
                try:
                    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
                    maybe_clear_scoped_barrier(run.project_id, completed_group="finalize")
                except Exception:
                    logger.debug(
                        "maybe_clear_scoped_barrier failed (non-fatal) for %s",
                        run.project_id, exc_info=True,
                    )

            # Phase 117: Clear barrier if scope="sync" (fast_sync boundary)
            if run.group == "fast_sync":
                try:
                    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
                    maybe_clear_scoped_barrier(run.project_id, completed_group="fast_sync")
                except Exception:
                    logger.debug(
                        "maybe_clear_scoped_barrier failed (non-fatal) for %s",
                        run.project_id, exc_info=True,
                    )

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
                        from prep.services.pipeline_budget import budget as _budget
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
                    # Phase 72 fix: If fast_sync was incremental (new/stale files),
                    # invalidate deep enrichment manifests so run_deep_enrichment()
                    # doesn't see "all_complete" and skip.  Without this, new files
                    # added during incremental fast_sync are never processed by
                    # deep enrichment stages (6-11).
                    # Phase 89: Also invalidate for force_from_start (rebuild) —
                    # deep enrichment must also rebuild from scratch.
                    _should_invalidate = (
                        run.project_id in self._incremental_runs
                        or run.project_id in self._force_from_start_runs
                    )
                    if _should_invalidate:
                        try:
                            self._invalidate_deep_manifests_for_incremental(
                                run.project_id, pfl,
                            )
                        except Exception:
                            logger.debug(
                                "Deep manifest invalidation failed for %s (non-fatal)",
                                run.project_id, exc_info=True,
                            )

                    # Phase 89: Propagate force_from_start to deep enrichment chain
                    _chain_force = run.project_id in self._force_from_start_runs

                    logger.info(
                        "Chaining deep enrichment after fast sync for %s (reason=%s, force=%s)",
                        run.project_id, chain_reason, _chain_force,
                    )
                    try:
                        started = self.run_deep_enrichment(
                            run.project_id, force_from_start=_chain_force,
                        )
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
            # Phase 118 U4: defensive self-resume check. If acquire fails
            # AND nobody else is contending for this node, the pipeline can
            # silently stall in QUEUED state forever (no other release will
            # ever fire to dequeue us). This was the user-reported "stalled
            # at stage 7" symptom: deepening (or any later stage that
            # routes to a different node than its predecessor) would
            # transition to QUEUED with an empty queue and never recover.
            try:
                sched_status = pipeline_scheduler.status() or {}
                target_node = node_id or "__local__"
                node_loads = (sched_status.get("nodes") or {}).get(target_node) or {}
                holders = node_loads.get("holders") or []
                contending_others = [h for h in holders if isinstance(h, dict) and h.get("project_id") != run.project_id]
                if not contending_others:
                    logger.warning(
                        "Pipeline %s/%s — stage %s acquire failed on %s with no other "
                        "contenders; forcing slot reset to break stall",
                        run.project_id, run.group, stage.value, target_node,
                    )
                    # Force-release any phantom hold this project has on the node,
                    # then retry acquire once before falling back to enqueue.
                    try:
                        pipeline_scheduler.release(run.project_id, stage, node_id)
                    except Exception:
                        pass
                    if pipeline_scheduler.acquire(run.project_id, stage, node_id):
                        run._current_node_id = node_id  # type: ignore[attr-defined]
                        # Continue with normal start path below — fall through
                        # by re-entering the next-stage start logic. Use the
                        # journal recovery path to schedule worker dispatch.
                        logger.info(
                            "Pipeline %s/%s — stage %s recovered slot after force-reset",
                            run.project_id, run.group, stage.value,
                        )
                    else:
                        logger.error(
                            "Pipeline %s/%s — stage %s acquire still failing after "
                            "force-reset; node %s may be misconfigured",
                            run.project_id, run.group, stage.value, target_node,
                        )
            except Exception as exc:
                logger.debug("U4 self-resume probe failed: %s", exc, exc_info=True)
            # If the recovery branch above didn't succeed, fall back to the
            # original enqueue-and-wait behavior so we don't double-acquire.
            if not getattr(run, '_current_node_id', None) == node_id:
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

        # Phase 118 U15: per-stage rebuild wipe. ONLY runs if this
        # project is in a force_from_start rebuild — and only wipes
        # THIS stage's files. Downstream stages keep their prior data
        # intact on disk until each one is itself about to re-run.
        # If the user stops mid-rebuild, all not-yet-run stages still
        # have their prior data — exactly the "no stage should be
        # reset until new data is ready to replace it" semantics the
        # user explicitly asked for.
        if run.project_id in self._force_from_start_runs:
            try:
                pfl_for_wipe = self._get_file_logger(run.project_id)
                self._wipe_stage_files_for_rebuild(run.project_id, stage.value, pfl_for_wipe)
            except Exception:
                logger.debug("U15 per-stage wipe failed (non-fatal)", exc_info=True)

        # Phase 91: Open swarm window if this is a swarm-eligible stage.
        # This blocks other projects from acquiring slots on this node,
        # letting running stages drain naturally before swarm takes over.
        from .scheduler import SWARM_CAPABLE_STAGES, is_swarm_active_for_stage
        if stage.value in SWARM_CAPABLE_STAGES:
            try:
                _provider, _model = self._resolve_model_for_stage(run.project_id, stage)
                if _provider and _model and is_swarm_active_for_stage(stage.value, _provider, _model):
                    # Phase 127 T3.2: build endpoint_set from coord+worker LLM
                    # clients so the scheduler holds only conflicting projects.
                    # Single-endpoint swarms still pass a 1-element set;
                    # multi-endpoint swarms (coord on OpenRouter + workers on
                    # Ollama Cloud) pass both.  Resolution is best-effort —
                    # fall back to {node_id} when client lookup fails.
                    endpoint_set: set[str] = set()
                    try:
                        from prep.server import _get_llm_client_for_slot
                        for _slot in ("large", "coordinator"):
                            try:
                                _client = _get_llm_client_for_slot(_slot)
                            except Exception:
                                _client = None
                            if _client is None:
                                continue
                            _resolver = getattr(_client, "_resolve_scheduler_node_id", None)
                            if not callable(_resolver):
                                continue
                            try:
                                _ep = _resolver()
                            except Exception:
                                _ep = None
                            if _ep:
                                endpoint_set.add(str(_ep))
                    except Exception:
                        logger.debug(
                            "Phase 127 T3.2: endpoint_set resolution failed; "
                            "falling back to single-endpoint",
                            exc_info=True,
                        )
                    if not endpoint_set and node_id:
                        endpoint_set = {node_id}
                    opened = pipeline_scheduler.open_swarm_window(
                        run.project_id, stage, node_id,
                        endpoint_set=endpoint_set or None,
                    )
                    if opened:
                        self._start_drain_timer()
                    # If another swarm window is already open, stage runs with
                    # normal (non-swarm) budget — fine
            except Exception:
                logger.debug("Phase 91: swarm window check failed for %s/%s", run.project_id, stage.value, exc_info=True)

        # VRAM lifecycle: only LOCAL LLM stages need model acquire/unload.
        # Cloud endpoints are always ready — no VRAM contention.
        # Embedding stages use NativeEmbedder (ONNX/CoreML/CUDA) — independent.
        # Rust stages are CPU-only — no GPU contention.
        if queue_type == QueueType.LLM and not self._is_cloud_node(node_id):
            task_id = STAGE_TASK_ID.get(stage)
            if task_id:
                try:
                    from prep.core.model_awareness import model_awareness
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

        # Phase 72 Stage 4: Mark stage as running in snapshot
        run.update_stage_snapshot(stage.value, running=True, exists=True)

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

        # F-67: Invalidate old manifest BEFORE worker starts.
        # If the daemon crashes mid-stage, the old manifest from a prior
        # run would still exist.  On restart, detect_resume_point sees it
        # and thinks the stage completed — losing all incremental progress.
        # By removing the manifest at stage START, a crash leaves no manifest,
        # so detect_resume_point correctly detects the stage as incomplete
        # and resumes from it.
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            _proj = require_project(run.project_id)
            _idx_dir = Path(project_index_dir(_proj))
            _manifest_file = STAGE_MANIFEST_FILE.get(stage)
            if _manifest_file:
                _manifest_path = _idx_dir / _manifest_file
                if _manifest_path.exists():
                    _manifest_path.unlink()
                    logger.info(
                        "F-67: Removed stale manifest %s before starting stage %s",
                        _manifest_file, stage.value,
                    )
        except Exception:
            logger.debug("F-67: manifest invalidation failed (non-fatal)", exc_info=True)

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

        # Phase 72: Minimal lock scope — only lookup and state transition
        # inside the lock. All I/O, scheduler release, and callbacks run
        # outside to prevent deadlocks and status endpoint blocking.
        stage: StageId | None = None
        matching_run: PipelineGroupStateMachine | None = None

        with self._lock:
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
            logger.debug(
                "[F-69 DEBUG] _on_build_transition: no matching run for %s/%s (phase=%s). "
                "Active runs: %s",
                project_id, build_type.value, new_phase.value,
                [(k, r.state.value, r.current_stage) for k, r in self._runs.items() if k[0] == project_id],
            )
            return

        if new_phase == BuildPhase.COMPLETED:
            # State transition (SM has its own lock)
            matching_run.transition(Event.STAGE_COMPLETED)
            logger.info(
                "Pipeline %s/%s — stage %s completed",
                project_id, matching_run.group, stage.value,
            )

            # Phase 89: Capture the old node BEFORE advance changes _current_node_id.
            # This is needed for the release-after-advance at the bottom of this method.
            _old_release_node = getattr(matching_run, '_current_node_id', None)

            # --- Post-completion bookkeeping (outside orchestrator lock) ---
            try:
                # Phase 44C: release model via state machine
                completed_task = STAGE_TASK_ID.get(stage)
                if completed_task:
                    try:
                        from prep.core.model_awareness import model_awareness
                        model_awareness.release(completed_task, unload=False)
                    except Exception:
                        logger.debug("ModelAwareness release failed for %s", completed_task, exc_info=True)

                # Fetch build slot for file logger + manifest writer
                slot = self._orchestrator.status(project_id, build_type)

                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.stage_end(stage.value, "completed", data={
                        "result": slot.result,
                        "duration": slot.duration_seconds,
                    })
                    pfl.transition(build_type.value, old_phase.value, new_phase.value,
                                   f"Stage {stage.value} completed")
                # Phase 25: journal
                self._journal_stage_completed(matching_run, stage)
                # Phase 49: write stage manifest + update run metadata
                self._write_stage_manifest_and_update_run(
                    matching_run, stage, slot,
                )
                # Phase 72 Stage 4: Update stage snapshot on completion
                self._update_stage_snapshot_from_slot(matching_run, stage, slot)
                # Phase 50: Atlas/rules generation
                if stage == StageId.STRUCTURAL:
                    self._generate_preliminary_atlas_and_rules(project_id)
                    self._prune_stale_derivative_files(project_id, pfl)
                    # F-67: Skip mtime sync during force_from_start rebuilds.
                    # The sync touches all downstream manifests, making the
                    # freshness check skip them — defeating the rebuild purpose.
                    if project_id not in self._force_from_start_runs:
                        self._sync_downstream_manifest_mtimes(project_id, pfl)
                # Phase 96: Rules regen after ATLAS is now handled by Stage 12 (RULES) in Finalize group
                # elif stage == StageId.ATLAS:
                #     self._regenerate_rules_with_full_atlas(project_id)

                # Phase 70B: Write guard
                self._write_guard_check(matching_run, stage, pfl)
                # Phase 60A: integrity guard
                self._integrity_check_after_stage(matching_run, stage, pfl)
            except _WriteGuardBlocked as wgb:
                logger.critical(
                    "WRITE GUARD BLOCKED stage %s for %s: %s",
                    stage.value, project_id, wgb,
                )
                pfl = self._get_file_logger(project_id)
                if pfl:
                    pfl.log(stage.value, f"WRITE GUARD BLOCKED: {wgb}")
                if matching_run.can_transition(Event.STAGE_FAILED):
                    matching_run.transition(Event.STAGE_FAILED, detail=f"WRITE GUARD BLOCKED: {wgb}")
                self._unload_group_models(matching_run)
                self._journal_run_completed(matching_run)
                # Phase 89: Release scheduler slot on write guard failure
                _release_node = getattr(matching_run, '_current_node_id', None)
                _deferred = pipeline_scheduler.release(project_id, stage, _release_node)
                if _deferred:
                    self._resume_queued_pipeline(_deferred.project_id, _deferred.stage)
                return
            except Exception:
                logger.exception(
                    "Post-completion bookkeeping failed for %s/%s stage %s "
                    "(pipeline will still advance)",
                    project_id, matching_run.group, stage.value,
                )

        elif new_phase == BuildPhase.FAILED:
            slot = self._orchestrator.status(project_id, build_type)
            error_msg = f"Stage {stage.value} failed: {slot.error}"

            if matching_run.state in (PipelineState.PAUSING, PipelineState.PAUSED, PipelineState.QUEUED):
                logger.info(
                    "Pipeline %s/%s — ignoring STAGE_FAILED during %s "
                    "(worker stopped for pause/swap, not a real failure)",
                    project_id, matching_run.group, matching_run.state.value,
                )
                _release_node = getattr(matching_run, '_current_node_id', None)
                next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
                if next_entry:
                    self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)
                return

            # Phase 118 U2: a worker failure should mark the pipeline FAILED,
            # not PAUSED. The original Phase 55 "auto-pause for recovery"
            # pattern conflated three things — transient errors, real errors,
            # and user-initiated cancels — and produced the user-visible
            # symptom of "single project flips to paused while running with
            # nothing else queued." Failures now go straight to FAILED via
            # STAGE_FAILED. Recovery is available via the journal and the
            # explicit /pipeline/resume endpoint when the user wants it.
            #
            # Exception: if the error message indicates user-initiated stop
            # ("Paused by user" / "Cancelled by user"), the slot transitioned
            # to FAILED as part of the cancel/pause flow itself — there's no
            # additional action needed; the state machine has already moved
            # via the explicit endpoint path.
            err_text = (slot.error or "").lower()
            user_initiated = "paused by user" in err_text or "cancelled by user" in err_text
            if user_initiated:
                logger.info(
                    "Pipeline %s/%s — stage %s ended with user-initiated marker %r; "
                    "no additional state transition (already handled by pause/cancel endpoint)",
                    project_id, matching_run.group, stage.value, slot.error,
                )
                matching_run.stage_results[stage.value] = "user_stopped"
            else:
                matching_run.transition(Event.STAGE_FAILED, detail=error_msg)
                logger.error(
                    "Pipeline %s/%s — stage %s failed: %s",
                    project_id, matching_run.group, stage.value, slot.error,
                )
                matching_run.stage_results[stage.value] = f"failed: {slot.error}"

            # Release scheduler slot (outside lock)
            _release_node = getattr(matching_run, '_current_node_id', None)
            next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
            if next_entry:
                self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)

            # Phase 75: ghost guard + queue notification on failure
            try:
                from prep.services.pipeline.ghost_guard import purge_ghost_locks
                purge_ghost_locks()
            except Exception:
                logger.debug("Ghost guard failed during FAILED transition", exc_info=True)
            try:
                from prep.core.events import get_event_bus
                get_event_bus().emit("queue_changed", {
                    "reason": "pipeline_stage_failed",
                    "project_id": project_id,
                })
            except Exception:
                pass

            pfl = self._get_file_logger(project_id)
            if pfl:
                pfl.stage_end(stage.value, "failed", error=slot.error, data={
                    "duration": slot.duration_seconds,
                })
                pfl.end_run("failed", error=slot.error)
            self._journal_stage_failed(matching_run, stage, slot.error or "Unknown error")
            self._stop_heartbeat_timer(matching_run)
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
                    from prep.services.project_helpers import require_project
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

        # Phase 94: Release old stage's scheduler slot BEFORE advancing.
        # The Phase 89 pattern (release AFTER advance) caused a self-deadlock
        # when the next stage uses the same compute node as the completed stage:
        # _advance_pipeline() tries to acquire a slot on the same node that the
        # completed stage still holds, fails, and parks the pipeline in QUEUED
        # state permanently.  Releasing first ensures the slot is available for
        # the same pipeline's next stage.
        _deferred_resume = None
        if new_phase == BuildPhase.COMPLETED:
            _deferred_resume = pipeline_scheduler.release(project_id, stage, _old_release_node)

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

        # Resume any pipeline that was waiting for the slot we just released.
        # Done after advance so the current pipeline gets first crack at the slot.
        if _deferred_resume:
            self._resume_queued_pipeline(_deferred_resume.project_id, _deferred_resume.stage)
            try:
                from prep.core.events import get_event_bus
                get_event_bus().emit("queue_changed", {
                    "reason": "pipeline_stage_completed",
                    "project_id": project_id,
                })
            except Exception:
                pass

    def _cancel_group(self, project_id: str, group: str) -> bool:
        """Cancel a running group using state machine events.

        F-84: If the group being cancelled was a REBUILD (force_from_start),
        restore the project's data files from the most recent pre-rebuild
        backup. Without this, cancelling mid-rebuild leaves the index in a
        torn state (fresh structural + stale deep enrichment). The branch
        snapshot captured at fast_sync start holds the pre-rebuild state.
        """
        was_rebuild = project_id in self._force_from_start_runs
        with self._lock:
            key = (project_id, group)
            run = self._runs.get(key)
            if not run:
                # Still handle rebuild flag cleanup + revert if caller is
                # dismissing a zombie cancelled card.
                if was_rebuild:
                    self._force_from_start_runs.discard(project_id)
                    self._revert_rebuild_to_backup(project_id)
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
                from prep.services.pipeline_journal import journal
                journal.run_cancelled(run.journal_run_id)
            except Exception:
                logger.debug("Journal cancel write failed", exc_info=True)

        # Phase 89 WS2: Release scheduler lock so other projects can proceed.
        # The _on_build_transition FAILED handler may also release, so check
        # is_held_by() to prevent double-release.
        if current_str and pipeline_scheduler.is_held_by(project_id):
            stage = StageId(current_str)
            _release_node = getattr(run, '_current_node_id', None)
            next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
            if next_entry:
                self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)

        # F-84: Rebuild revert — restore pre-rebuild snapshot after cancelling.
        # Runs after scheduler release so the restored data isn't clobbered
        # by a queued worker starting immediately.
        if was_rebuild:
            self._force_from_start_runs.discard(project_id)
            self._revert_rebuild_to_backup(project_id)

        # Cancel discards the run — clear the user-pause marker so a
        # subsequent restart does not resurrect the cancelled run as
        # paused.
        try:
            RecoveryManager.clear_user_pause_marker(project_id, group)
        except Exception:
            logger.debug("User pause marker clear failed on cancel", exc_info=True)

        return True

    # Phase 118 U15: per-stage file wipe map. The previous
    # `_REBUILD_WIPE_FILES_BY_GROUP` deleted ALL files for an entire
    # group at rebuild start, before ANY stage actually re-ran. Result:
    # the user starts a rebuild, looks at the dashboard, and sees every
    # downstream stage immediately flip to "No run data / Waiting for X"
    # — even though the rebuild has only touched stage 1 so far. The
    # user explicitly objected: "no stage should be reset or unset or
    # even prepared to be replaced UNTIL new data has been rebuilt."
    #
    # The fix maps each stage to ONLY the files it produces. The
    # wipe runs per-stage at run-start (in `_advance_pipeline`), so
    # downstream stages keep their prior data on disk until each one
    # is itself about to be re-run. If the user stops mid-rebuild,
    # the un-wiped stages still have their prior data intact —
    # nothing lost.
    _STAGE_WIPE_FILES: dict[Any, list[str]] = {
        # Fast Sync (stages 1-5). Note: structural is intentionally
        # not wiped — `trace_manifest.json` and `trace_nodes.jsonl`
        # are the structural worker's own atomic-rename outputs.
        # If we wiped them here, the dashboard would briefly see
        # `trace.exists=false` even with our U8 guard.
        # Pipeline-run-metadata is a stage-1 wipe target — it
        # carries stale resume decisions across runs.
        # (filled in below by stage_id; lazy-initialised at first use)
    }

    # F-87 (legacy / kept for diff context): grouped wipe map. Now used
    # only as the source-of-truth for what each stage produces — not
    # for upfront mass wiping. See `_STAGE_WIPE_FILES_BY_STAGE` for the
    # active per-stage breakdown derived from this.
    _REBUILD_WIPE_FILES_BY_GROUP = {
        "fast_sync": [
            # Edge Discovery cache
            "trace_inferred_edges.jsonl",
            "trace_inferred_hashes.json",
            "trace_inferred_manifest.json",
            # Fast Catalogue / Validation output
            "trace_augmented.jsonl",
            "trace_augment_manifest.json",
            "validation_manifest.json",
            # Knowledge Embedding (Fast Sync stage 5)
            "knowledge_documents.json",
            "knowledge_embeddings.npy",
            "knowledge_manifest.json",
        ],
        "deep_enrichment": [
            # Deep Reasoning
            "trace_epistemic.jsonl",
            "trace_epistemic_manifest.json",
            # Group Reasoning
            "trace_group_reasoning.jsonl",
            "group_reasoning_manifest.json",
            # Cluster Synthesis
            "trace_modules.jsonl",
            "trace_modules_manifest.json",
            "trace_cluster_swarm_synthesis.json",
            # Deepening + Deep Knowledge manifests
            "deepening_manifest.json",
            "deep_knowledge_manifest.json",
        ],
        "finalize": [
            # Atlas
            "atlas.json",
            "atlas_prev.json",
            "atlas_manifest.json",
            "atlas_segments_manifest.json",
            "atlas_routing.json",
            "atlas_routing_embeddings.npy",
            "atlas_updated.signal",
            # Rules / Concepts / Audit / Antibodies
            "rules_manifest.json",
            "concepts_manifest.json",
            "audit_manifest.json",
            "antibodies_manifest.json",
        ],
        "global": [
            # Pipeline run metadata (stale resume decisions)
            "pipeline_run_metadata.json",
        ],
    }

    # Group chain order: each rebuild scope wipes its own group PLUS any
    # downstream groups that will re-run via auto-chain. "global" is always
    # wiped. A fast_sync rebuild chains through deep + finalize, so all three
    # group lists get wiped. A deep_enrichment rebuild chains into finalize but
    # leaves fast_sync outputs intact (Stage 5 never runs). A finalize rebuild
    # only wipes finalize.
    _REBUILD_WIPE_CHAIN = ["fast_sync", "deep_enrichment", "finalize"]

    # Phase 118 U15: per-stage file map for deferred wipe. Each stage's
    # files are wiped right before that stage runs, NOT upfront.
    # Derived from _REBUILD_WIPE_FILES_BY_GROUP but split by stage.
    _STAGE_WIPE_FILES_BY_STAGE: dict[str, list[str]] = {
        # Fast Sync
        "structural": [],  # NEVER wipe — atomic-overwrite outputs (see U8 / trace.exists guard)
        "inferred_edges": [
            "trace_inferred_edges.jsonl",
            "trace_inferred_hashes.json",
            "trace_inferred_manifest.json",
        ],
        "catalogue": [
            "trace_augmented.jsonl",
            "trace_augment_manifest.json",
            # Wipe pipeline_run_metadata.json on the FIRST stage that touches
            # incremental state (catalogue), so stale resume decisions don't
            # confuse this rebuild. Stage 1 (structural) is left intact.
            "pipeline_run_metadata.json",
        ],
        "validation": ["validation_manifest.json"],
        "knowledge": [
            "knowledge_documents.json",
            "knowledge_embeddings.npy",
            "knowledge_manifest.json",
        ],
        # Deep Enrichment
        "enrichment": [
            "trace_epistemic.jsonl",
            "trace_epistemic_manifest.json",
        ],
        "group_reasoning": [
            "trace_group_reasoning.jsonl",
            "group_reasoning_manifest.json",
        ],
        "clustering": [
            "trace_modules.jsonl",
            "trace_modules_manifest.json",
            "trace_cluster_swarm_synthesis.json",
        ],
        "deepening": ["deepening_manifest.json"],
        "deep_knowledge": ["deep_knowledge_manifest.json"],
        # Finalize
        "atlas": [
            "atlas.json",
            "atlas_prev.json",
            "atlas_manifest.json",
            "atlas_segments_manifest.json",
            "atlas_routing.json",
            "atlas_routing_embeddings.npy",
            "atlas_updated.signal",
        ],
        "rules": ["rules_manifest.json"],
        "concepts": ["concepts_manifest.json"],
        "audit": ["audit_manifest.json"],
        "antibodies": ["antibodies_manifest.json"],
    }

    def _wipe_stage_files_for_rebuild(
        self,
        project_id: str,
        stage_value: str,
        pfl: Any = None,
    ) -> None:
        """Phase 118 U15: per-stage file wipe at rebuild stage-start.

        Replaces the upfront `_wipe_rebuild_caches` group-wide wipe.
        Called right before each stage's worker dispatches when this
        project is in `_force_from_start_runs`. Wipes ONLY the named
        stage's outputs — downstream stages keep their prior data
        intact until each one is itself about to re-run.

        Idempotent: re-wiping a stage that already has no files is a
        no-op.
        """
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
        except Exception:
            return
        files = self._STAGE_WIPE_FILES_BY_STAGE.get(stage_value, [])
        if not files:
            return
        deleted = []
        for fname in files:
            fpath = idx_dir / fname
            if fpath.exists():
                try:
                    fpath.unlink()
                    deleted.append(fname)
                except Exception:
                    pass
        if deleted:
            logger.info(
                "[%s] U15 per-stage wipe (stage=%s): removed %d files",
                project_id, stage_value, len(deleted),
            )
            if pfl:
                pfl.decision("stage_wipe_for_rebuild", "wiped", {
                    "stage": stage_value,
                    "files": deleted,
                })

    def _wipe_files_for_scope(self, scope: str) -> list[str]:
        """Return the list of files to wipe for a rebuild scope.

        Wipes the scope's own group, all downstream groups (which auto-chain
        from it), and global files. Unknown scopes fall back to wiping
        everything for safety.
        """
        chain = self._REBUILD_WIPE_CHAIN
        try:
            idx = chain.index(scope)
        except ValueError:
            idx = 0  # unknown scope — wipe everything
        files: list[str] = list(self._REBUILD_WIPE_FILES_BY_GROUP.get("global", []))
        for g in chain[idx:]:
            files.extend(self._REBUILD_WIPE_FILES_BY_GROUP.get(g, []))
        return files

    def _wipe_rebuild_caches(
        self,
        project_id: str,
        pfl: Any = None,
        scope: str = "fast_sync",
    ) -> None:
        """Remove worker-level caches at rebuild start (F-87).

        Lets each stage's worker re-run end-to-end instead of short-
        circuiting on content-hash matches. Preserves project config
        (project.json, repo_policy.json) and all backup sources
        (_golden, run checkpoints, branch snapshots).

        ``scope`` gates which groups' outputs get wiped — a
        ``deep_enrichment`` rebuild must leave Stage 5's
        ``trace_augmented.jsonl`` alone because Stage 5 won't run to
        regenerate it. See ``_REBUILD_WIPE_FILES_BY_GROUP``.

        Also clears stale in-memory orchestrator state so the UI doesn't
        show ghost spinners from a paused/cancelled run when a fresh
        rebuild starts (F-87 extension): per-project BuildSlot entries
        and non-fast_sync state machine runs that would survive a
        Rebuild button click otherwise.
        """
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))

            # F-87c: Take a "pre_rebuild" checkpoint BEFORE wiping so
            # F-84 cancel-revert always has a safety net — even for
            # first-time rebuilds that have no _golden checkpoint yet.
            # This is cheap (shutil.copy2 of a handful of jsonl files)
            # and only runs for force_from_start rebuilds.
            try:
                from prep.services.pipeline_checkpoint import create_checkpoint
                import time as _time
                pre_cp_id = f"pre_rebuild_{int(_time.time())}"
                cp_path = create_checkpoint(idx_dir, pre_cp_id, "pre_rebuild")
                if cp_path:
                    logger.info(
                        "[%s] F-87c: pre-rebuild checkpoint saved at %s",
                        project_id, cp_path,
                    )
                    if pfl:
                        pfl.decision("pre_rebuild_checkpoint", "saved", {
                            "path": str(cp_path),
                        })
            except Exception:
                logger.debug(
                    "Pre-rebuild checkpoint failed (non-fatal) — "
                    "revert will fall back to _golden/branch_snapshot",
                    exc_info=True,
                )

            # Phase 118 U15: REMOVED the upfront group-wide file wipe.
            # Files are now wiped per-stage at stage-start (see
            # _wipe_stage_files_for_rebuild and the call site in
            # _advance_pipeline). This way, downstream stages keep
            # their prior data on disk until each one is itself about
            # to be re-run — fixing the user-reported "all stages flip
            # to no-data the moment rebuild starts" problem.
            #
            # The pre-rebuild checkpoint above is still saved upfront
            # so F-84 cancel-revert always has a safety net.
            logger.info(
                "[%s] U15 rebuild start: per-stage wipe deferred (scope=%s)",
                project_id, scope,
            )
            if pfl:
                pfl.decision("rebuild_cache_wipe", "deferred", {
                    "scope": scope,
                    "policy": "per_stage_at_run_start (Phase 118 U15)",
                })
        except Exception:
            logger.debug("F-87 cache wipe failed (non-fatal)", exc_info=True)

        # Clear derived finalize-stage SQLite stores so the rebuild
        # doesn't inherit stale concepts/antibodies. The files wiped
        # above are re-generated by the rebuild run, but the SQLite
        # rows (concepts from stage 13, antibodies from stage 15) would
        # otherwise persist from the prior run. Observations are
        # user-authored and deliberately preserved.
        try:
            from prep.services.concept_store import concept_store
            concept_store.clear_project(project_id)
        except Exception:
            logger.debug("concept_store.clear_project failed during rebuild (non-fatal)", exc_info=True)
        try:
            from prep.services.antibody_store import antibody_store
            antibody_store.clear_project(project_id)
        except Exception:
            logger.debug("antibody_store.clear_project failed during rebuild (non-fatal)", exc_info=True)

        # F-87b: Clear stale BuildOrchestrator slots + other-group state
        # machines so the UI doesn't keep showing a paused stage's spinner
        # from a previous run. fast_sync itself gets a fresh state machine
        # inside _start_group.
        try:
            self._orchestrator.clear_project(project_id)
        except Exception:
            logger.debug("clear_project on BuildOrchestrator failed (non-fatal)", exc_info=True)
        try:
            with self._lock:
                # Drop deep_enrichment + finalize runs from a prior paused/cancelled
                # state. fast_sync is about to be overwritten in _start_group so
                # leave it alone — removing here would lose the new run's key.
                doomed = [
                    k for k in self._runs.keys()
                    if k[0] == project_id and k[1] != "fast_sync"
                ]
                for k in doomed:
                    del self._runs[k]
        except Exception:
            logger.debug("Stale run cleanup failed (non-fatal)", exc_info=True)

        # F-87b: Emit pipeline_status so the UI sees the cleared state
        # immediately instead of waiting for the next poll.
        try:
            self._emit_pipeline_status(project_id)
        except Exception:
            pass

    def _revert_rebuild_to_backup(self, project_id: str) -> None:
        """Restore a project's pipeline data from the most recent backup.

        Called when the user cancels a rebuild (force_from_start) before
        it completed. Uses the pre_rebuild_* checkpoint (created by
        F-87c at rebuild start) if available, otherwise falls back to
        _golden / run checkpoints / branch snapshot. Best-effort — logs
        but doesn't raise.

        F-87d: performs an UNCONDITIONAL overlay of the backup files
        onto the index dir. The older `try_restore_from_backup` helper
        was designed for crash recovery and preserves current files
        that are larger than the backup — which is the wrong behavior
        for cancel-revert, where partial rebuild data is exactly what
        we want to discard.
        """
        pfl = self._get_file_logger(project_id)
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))

            # Pick the best backup source for a hard revert.
            # Priority: pre_rebuild_* (most recent) > _golden > run-* > branch_snapshot.
            best = None
            cp_root = idx_dir / ".checkpoints"
            if cp_root.is_dir():
                # pre_rebuild_* first — reverse-sorted by name picks newest timestamp.
                pre_dirs = sorted(
                    (d for d in cp_root.iterdir()
                     if d.is_dir() and d.name.startswith("pre_rebuild_")),
                    reverse=True,
                )
                if pre_dirs:
                    best = pre_dirs[0]
                elif (cp_root / "_golden").is_dir():
                    best = cp_root / "_golden"
                else:
                    runs = sorted(
                        (d for d in cp_root.iterdir()
                         if d.is_dir() and d.name.startswith("run-")),
                        reverse=True,
                    )
                    if runs:
                        best = runs[0]
            if best is None:
                # Fall back to branch snapshot
                try:
                    from prep.services.branch_backup_manager import (
                        read_branch_state, _sanitize_branch_name, SNAPSHOTS_DIR,
                    )
                    state = read_branch_state(idx_dir)
                    branch = state.get("branch")
                    if branch:
                        sd = idx_dir / SNAPSHOTS_DIR / _sanitize_branch_name(branch)
                        if sd.is_dir():
                            best = sd
                except Exception:
                    pass

            if best is None:
                logger.warning(
                    "[%s] Rebuild revert: no backup source available",
                    project_id,
                )
                if pfl:
                    pfl.log("cancel_revert", "No backup source available")
                return

            import shutil
            restored = []
            for src in best.iterdir():
                if not src.is_file():
                    continue
                dst = idx_dir / src.name
                try:
                    shutil.copy2(str(src), str(dst))
                    restored.append(src.name)
                except Exception:
                    logger.debug("Revert copy failed: %s", src.name, exc_info=True)

            logger.info(
                "[%s] Rebuild revert: restored %d files from %s",
                project_id, len(restored), best.name,
            )
            if pfl:
                pfl.log(
                    "cancel_revert",
                    f"Reverted {len(restored)} files from {best.name}",
                )
        except Exception:
            logger.warning(
                "[%s] Rebuild revert failed (non-fatal) — state left as-is",
                project_id, exc_info=True,
            )

        # F-84: Drop stale state-machine entries so the UI's
        # `deep_enrichment.phase=cancelled` / `paused` cards disappear.
        # Without this the SidebarPipelineQueue keeps showing the
        # cancelled run forever and the GraphEnrichmentPipeline panel
        # keeps the per-stage paused styling. The backup data on disk is
        # now authoritative — the stale state machines have nothing to
        # contribute and would confuse resume detection.
        try:
            with self._lock:
                stale_keys = [k for k in self._runs.keys() if k[0] == project_id]
                for k in stale_keys:
                    del self._runs[k]
        except Exception:
            logger.debug("Failed to clear stale runs after revert", exc_info=True)

        # F-84: Emit fresh pipeline_status + queue_changed SSE events so the
        # dashboard re-fetches and clears the paused/cancelled UI state.
        try:
            from prep.core.events import get_event_bus
            bus = get_event_bus()
            self._emit_pipeline_status(project_id)
            bus.emit("queue_changed", {"reason": "rebuild_cancelled", "project_id": project_id})
        except Exception:
            logger.debug("SSE emit after revert failed (non-fatal)", exc_info=True)

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

        # Phase 89 WS3: Release scheduler lock so other projects can run
        # while this pipeline is paused. Resume will re-acquire via
        # _advance_pipeline() → scheduler.acquire().
        if current_str and pipeline_scheduler.is_held_by(project_id):
            stage = StageId(current_str)
            _release_node = getattr(run, '_current_node_id', None)
            next_entry = pipeline_scheduler.release(project_id, stage, _release_node)
            if next_entry:
                self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)

        # Persist the user's pause intent to disk so it survives daemon
        # restart. Without this marker, hydration in auto mode skips
        # creating a PAUSED state machine and the pipeline auto-resumes
        # past the stage the user explicitly stopped on.
        try:
            RecoveryManager.write_user_pause_marker(project_id, group, current_str)
        except Exception:
            logger.debug("User pause marker write failed", exc_info=True)

        # Emit SSE so the frontend sees the PAUSED state immediately
        # (the build_orchestrator's FAILED event only triggers pipeline_status
        # with phase="pausing" — this emits the final "paused" phase).
        self._emit_pipeline_status(project_id)

        # Journal: record pause
        if run.journal_run_id:
            try:
                from prep.services.pipeline_journal import journal
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
            from prep.core.model_awareness import model_awareness
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
        from prep.server import _get_llm_client_for_task, _get_model_identity_for_task

        next_task = STAGE_TASK_ID.get(next_stage)
        next_identity = _get_model_identity_for_task(next_task) if next_task else None

        # Determine the previous stage's model identity
        prev_task: str | None = None
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
        from prep.server import _get_llm_client_for_task, _get_model_identity_for_task

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
                from prep.core.project_registry import project_index_dir
                from prep.services.pipeline_metadata import update_heartbeat
                from prep.services.project_helpers import require_project
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


    def _maybe_retrigger_deepening(self, project_id: str, pfl: Any = None) -> None:
        """Delegates to PostFlightActions.maybe_retrigger_deepening."""
        PostFlightActions.maybe_retrigger_deepening(
            project_id,
            is_deep_auto_fn=self._is_deep_enrichment_auto,
            run_deepening_fn=self.run_deepening_only,
            pfl=pfl,
        )
    @staticmethod
    def _read_graph_stats_from_manifest(idx_dir) -> dict[str, Any]:
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
        """Delegates to PostFlightActions.write_atlas_signal."""
        PostFlightActions.write_atlas_signal(idx_dir)

    def _generate_preliminary_atlas_and_rules(self, project_id: str) -> None:
        """Delegates to PostFlightActions.generate_preliminary_atlas_and_rules."""
        PostFlightActions.generate_preliminary_atlas_and_rules(project_id)
    # Phase 96E: _regenerate_rules_with_full_atlas removed — superseded by
    # the RULES stage (stage 12) in the Finalize group.  The delegate was
    # already commented out at its only call site.
    def _trigger_code_index_build(self, project_id: str, pfl: Any = None) -> None:
        """Delegates to PostFlightActions.trigger_code_index_build."""
        PostFlightActions.trigger_code_index_build(project_id, pfl)
    def _journal_stage_started(self, run: PipelineGroupStateMachine, stage: StageId) -> None:
        if not run.journal_run_id:
            return
        try:
            from prep.services.pipeline_journal import journal
            journal.stage_started(run.journal_run_id, stage.value, run.current_stage_index)
        except Exception:
            logger.debug("Journal stage_started write failed", exc_info=True)

    def _resume_queued_pipeline(self, project_id: str, stage: StageId) -> None:
        """Resume a pipeline that was waiting for compute capacity.

        Called when a scheduler slot frees up and a queued entry is dequeued.
        Finds the matching state machine, transitions it from QUEUED → RUNNING,
        and advances the pipeline.
        """
        from prep.services.pipeline.scheduler import pipeline_scheduler

        # Find the state machine for this project
        matching_sm = None
        with self._lock:
            for key, sm in self._runs.items():
                if key[0] == project_id and sm.is_queued:
                    matching_sm = sm
                    break

        if matching_sm is None:
            # Phase 93: Drop orphaned queue entries instead of re-enqueuing.
            # The old re-enqueue logic created an infinite loop: dequeue →
            # no SM → re-enqueue → dequeue → repeat, blocking all other
            # queued pipelines from ever getting a compute slot.
            # An entry with no state machine is a ghost from a cancelled/
            # completed/recovered run — it will never be resumable.
            logger.warning(
                "Scheduler: dequeued %s/%s but no QUEUED state machine found — "
                "dropping orphaned entry (no state machine to resume)",
                project_id, stage.value,
            )
            try:
                pipeline_scheduler.release(project_id, stage)
            except Exception:
                pass  # Already released or never acquired
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
                            detail="re-enqueued after _advance_pipeline failure",
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
            from prep.services.pipeline_journal import journal
            journal.stage_completed(run.journal_run_id, stage.value)
        except Exception:
            logger.debug("Journal stage_completed write failed", exc_info=True)

    def _journal_stage_failed(self, run: PipelineGroupStateMachine, stage: StageId, error: str) -> None:
        if not run.journal_run_id:
            return
        try:
            from prep.services.pipeline_journal import journal
            journal.stage_failed(run.journal_run_id, stage.value, error)
        except Exception:
            logger.debug("Journal stage_failed write failed", exc_info=True)

    def _journal_run_completed(self, run: PipelineGroupStateMachine) -> None:
        if not run.journal_run_id:
            return
        try:
            from prep.services.pipeline_journal import journal
            journal.run_completed(run.journal_run_id)
        except Exception:
            logger.debug("Journal run_completed write failed", exc_info=True)
        # Cleanup this run's checkpoint
        try:
            from prep.services.pipeline_journal import journal as j
            entry = j.get_run(run.journal_run_id)
            if entry and entry.checkpoint_path:
                from prep.services.pipeline_checkpoint import cleanup_checkpoint
                cleanup_checkpoint(entry.checkpoint_path)
        except Exception:
            logger.debug("Checkpoint cleanup failed", exc_info=True)

        # Phase 72D: Golden checkpoint + pruning
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_checkpoint import (
                create_golden_checkpoint,
                prune_old_checkpoints,
            )
            from prep.services.project_helpers import require_project

            project = require_project(run.project_id)
            idx_dir = Path(project_index_dir(project))

            # Create a golden checkpoint after deep_enrichment completes.
            # This is the "known-good" state — the preferred restore target.
            if run.group == "deep_enrichment":
                gp = create_golden_checkpoint(idx_dir)
                if gp:
                    logger.info(
                        "Phase 72D: Golden checkpoint created for %s at %s",
                        run.project_id, gp,
                    )

            # Prune old run checkpoints (keep 3 most recent + golden)
            pruned = prune_old_checkpoints(idx_dir, keep=3)
            if pruned:
                logger.info(
                    "Phase 72D: Pruned %d old checkpoints for %s",
                    pruned, run.project_id,
                )
        except Exception:
            logger.debug("Phase 72D golden/prune failed (non-fatal)", exc_info=True)

    def _create_checkpoint_if_needed(self, run: PipelineGroupStateMachine, stage: StageId) -> None:
        """Delegates to RecoveryManager.create_checkpoint_if_needed."""
        RecoveryManager.create_checkpoint_if_needed(run, stage)

    # ── Phase 72 Stage 4: Stage Snapshot Updates ─────────────────

    def _update_stage_snapshot_from_slot(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        slot: Any,
    ) -> None:
        """Update the state machine's stage snapshot from a completed build slot.

        Captures progress, quality, and result data so the status endpoint
        can serve this without reading disk.
        """
        try:
            worker_result = getattr(slot, "result", None) or {}
            snapshot_data: dict[str, Any] = {
                "exists": True,
                "running": False,
            }

            # Progress from build slot
            if hasattr(slot, "progress_current"):
                snapshot_data["progress_current"] = slot.progress_current
                snapshot_data["progress_total"] = slot.progress_total
                snapshot_data["progress_baseline"] = getattr(slot, "progress_baseline", 0)

            # Item counts from worker result
            if isinstance(worker_result, dict):
                for key in ("total_items", "processed", "item_count", "nodes", "edges"):
                    if key in worker_result:
                        snapshot_data[key] = worker_result[key]

            # Quality from manifest (just written by _write_stage_manifest)
            try:
                ms = self._get_or_create_manifest_store(run.project_id)
                if ms:
                    quality = ms.read_quality(stage)
                    if quality:
                        snapshot_data["item_count"] = quality.get("processed", quality.get("total_items", 0))
                        snapshot_data["total_items"] = quality.get("total_items", 0)
                        snapshot_data["avg_confidence"] = quality.get("avg_confidence", 0.0)
            except Exception:
                pass

            run.update_stage_snapshot(stage.value, **snapshot_data)
        except Exception:
            logger.debug("Stage snapshot update failed for %s (non-fatal)", stage.value, exc_info=True)

    def _get_or_create_manifest_store(self, project_id: str) -> ManifestStore | None:
        """Get a ManifestStore for a project, creating if needed."""
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            return ManifestStore(Path(project_index_dir(project)))
        except Exception:
            return None

    # ── Phase 70B: Freshness Check + Write Guard ─────────────────

    def _should_skip_stage_freshness(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> bool:
        """Delegates to ResumeStrategy.should_skip_stage_freshness."""
        is_incremental = run.project_id in self._incremental_runs
        # F-82: Rebuild (force_from_start) must never skip a stage on
        # freshness grounds. The Rebuild button is the only place where
        # we deliberately want to overwrite existing data — each stage
        # must re-run end-to-end and swap its output atomically. Previously
        # freshness-skip fired for any stage whose output mtime was newer
        # than its inputs, causing Edge Discovery / Fast Catalogue /
        # Validation to no-op on rebuild when prior data existed.
        is_rebuild = run.project_id in self._force_from_start_runs
        if is_rebuild:
            if pfl:
                pfl.log(stage.value, "Freshness check bypassed (rebuild / force_from_start)")
            return False
        should_skip, reason = ResumeStrategy.should_skip_stage_freshness(
            run.project_id, stage, is_incremental, pfl,
        )
        if should_skip:
            logger.info("Stage %s skipped for %s: %s", stage.value, run.project_id, reason)
            if pfl:
                pfl.log(stage.value, f"SKIPPED (freshness): {reason}")
            run.stage_results[stage.value] = "skipped"

            # Phase 96: Release the scheduler slot acquired for this stage
            # BEFORE advancing.  Without this release, the slot is held
            # forever (no worker was launched, so _on_build_transition will
            # never fire to release it).  This mirrors the release-before-
            # advance pattern from the normal completion path (line ~1967).
            _release_node = getattr(run, '_current_node_id', None)
            if pipeline_scheduler.is_held_by(run.project_id):
                _deferred = pipeline_scheduler.release(
                    run.project_id, stage, _release_node,
                )
                if _deferred:
                    self._resume_queued_pipeline(
                        _deferred.project_id, _deferred.stage,
                    )

            # Manually advance stage index (not via transition, since this
            # isn't a STAGE_COMPLETED event — it's a skip). The caller
            # (_advance_pipeline) will start the next stage.
            run.current_stage_index += 1
            self._advance_pipeline(run)
        return should_skip
    def _try_restore_stage_from_backup(
        self,
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> bool:
        """Delegates to RecoveryManager.try_restore_stage_from_backup."""
        # F-82: Rebuild must never restore from backup. The Rebuild button
        # is the only path where we intentionally overwrite existing data —
        # each stage must re-run end-to-end. Without this guard, Edge
        # Discovery / Fast Catalogue / Validation silently get restored
        # from _golden or branch snapshot and the rebuild is a no-op for
        # those stages.
        if run.project_id in self._force_from_start_runs:
            if pfl:
                pfl.log(stage.value, "Backup restore skipped (rebuild / force_from_start)")
            return False
        restored = RecoveryManager.try_restore_stage_from_backup(run, stage, pfl)
        if restored:
            # Phase 96: Release the scheduler slot acquired for this stage
            # BEFORE advancing.  Same pattern as freshness skip above —
            # no worker was launched, so the slot must be released manually.
            _release_node = getattr(run, '_current_node_id', None)
            if pipeline_scheduler.is_held_by(run.project_id):
                _deferred = pipeline_scheduler.release(
                    run.project_id, stage, _release_node,
                )
                if _deferred:
                    self._resume_queued_pipeline(
                        _deferred.project_id, _deferred.stage,
                    )
            self._advance_pipeline(run)
        return restored

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

        F-33 / F-51: When the user explicitly triggered a force-from-start
        rebuild (e.g. by clicking Rebuild from the Danger Zone), the write
        guard's "shrinkage = data loss" assumption is wrong: the user
        WANTS to throw away the old data and start fresh, including
        accepting fewer nodes if the parser/scope produces them. We
        log the would-be block but allow it through in that mode.
        """
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_integrity import (
                STAGE_DATA_FILES,
                integrity_guard,
            )
            from prep.services.project_helpers import require_project

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
                # F-33 / F-51: explicit user-triggered rebuild bypasses
                # the shrinkage block.  The Danger Zone "Rebuild" button
                # passes force_from_start=True to run_all() which adds
                # the project_id to _force_from_start_runs for the
                # duration of the run.
                if run.project_id in self._force_from_start_runs:
                    logger.warning(
                        "Write guard: BYPASSED for stage %s/%s — "
                        "force-from-start rebuild allows shrinkage (%s)",
                        stage.value, run.project_id, reason,
                    )
                    if pfl:
                        pfl.log(
                            stage.value,
                            f"Write guard: BYPASSED (force rebuild): {reason}",
                        )
                    return

                # Otherwise, attempt auto-recovery before giving up
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
        post_files: dict[str, Any],
        reason: str,
        pfl: Any = None,
    ) -> bool:
        """Attempt to recover from a write guard block.

        For deterministic stages (Rust, embedding): log that re-run is safe.
        For LLM stages: try to restore from the Phase 25 checkpoint.

        Returns True if recovery succeeded (pipeline can continue).
        Returns False if recovery failed (pipeline should halt).
        """
        from prep.services.pipeline.stages import STAGE_IS_DETERMINISTIC

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
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_checkpoint import restore_checkpoint
            from prep.services.pipeline_journal import journal
            from prep.services.project_helpers import require_project

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
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_integrity import integrity_guard
            from prep.services.project_helpers import require_project
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
                    + (" [INCREMENTAL]" if is_incremental else " [INITIAL]"),
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
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_integrity import integrity_guard
            from prep.services.project_helpers import require_project
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

    def startup_recovery(self) -> list[Any]:
        """Delegates to RecoveryManager.startup_recovery with orchestrator callbacks."""
        return RecoveryManager.startup_recovery(
            hydrate_fn=self._hydrate_paused_runs_from_disk,
            auto_recover_fn=self._auto_recover_stale_pipelines,
            set_crashed_runs=lambda runs: setattr(self, '_crashed_runs', runs),
            selfheal_fn=lambda: RecoveryManager.startup_selfheal_all(
                get_file_logger_fn=self._get_file_logger,
            ),
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
            # Paused runs MUST short-circuit auto-recovery. A PAUSED state
            # in `_runs` after hydration represents one of two cases:
            #   (a) the user explicitly paused before shutdown, or
            #   (b) the daemon was killed mid-run and hydration rebuilt the
            #       state from disk artifacts so the user can resume.
            # Either way, auto-recovery must NOT silently clear the pause
            # and start a fresh run on the user's behalf — the user has to
            # click Resume. Without including paused here, the symmetric
            # `is_active` predicate in _hydrate_paused_runs_from_disk
            # (which DOES include paused) was contradicted, and
            # `clear_paused_runs_fn` below would delete the hydrated pause
            # before triggering a fresh deep enrichment — exactly the
            # "I paused, restarted, and it auto-resumed past my stage"
            # bug from real-world reports.
            with self._lock:
                return any(
                    run.is_active or run.is_paused
                    for key, run in self._runs.items()
                    if key[0] == pid
                )

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

    def get_crashed_runs(self, project_id: str | None = None) -> list[dict[str, Any]]:
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
            from prep.core.project_registry import project_index_dir
            from prep.core.provenance import (
                aggregate_model_breakdown,
                aggregate_quality_metrics,
                compute_throughput,
                get_file_metadata,
            )
            from prep.core.stage_manifest import (
                create_stage_manifest,
            )
            from prep.services.project_helpers import require_project

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
                    from datetime import datetime
                    started_epoch = timing.get("started_at", 0)
                    if started_epoch:
                        manifest.started_at = datetime.fromtimestamp(
                            started_epoch, tz=UTC
                        ).isoformat()
                    manifest.elapsed_seconds = timing.get("elapsed")
                    manifest.finished_at = datetime.now(UTC).isoformat()

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
                        from prep.server import _load_ui_config
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
                            from prep.core import NativeEmbedder
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

            # F-66: Persist progress baseline in manifest so 2-tone bars
            # survive page refresh and daemon restart.  The baseline is the
            # count of items that existed before THIS incremental run started.
            if slot and slot.progress_baseline > 0:
                manifest.incremental_baseline = slot.progress_baseline

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
            elif stage in (StageId.KNOWLEDGE, StageId.DEEP_KNOWLEDGE):
                # F-76: KNOWLEDGE stages have no confidence-annotated output
                # file (they produce an embedding index, not a JSONL). Without
                # a quality block the API can't surface historical completion
                # counts and the UI stays grey after a daemon restart even
                # though knowledge_embeddings.npy is on disk. Synthesize
                # quality from the worker result so that
                # deepening_manifest.json parity is achieved.
                try:
                    total = 0
                    if isinstance(worker_result, dict):
                        total = int(worker_result.get("count", 0) or 0)
                    if total > 0:
                        manifest.quality = {
                            "total_items": total,
                            "processed": total,
                            "skipped": 0,
                            "failed": 0,
                            "success_rate": 1.0,
                        }
                        elapsed = manifest.elapsed_seconds or 0
                        if elapsed > 0:
                            manifest.throughput = compute_throughput(total, elapsed)
                except Exception:
                    logger.debug(
                        "F-76: failed to synthesize knowledge quality block for %s (non-fatal)",
                        stage.value, exc_info=True,
                    )

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
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_metadata import (
                mark_stage_completed,
                save_run_metadata,
            )
            from prep.services.project_helpers import require_project

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
            from prep.core.project_registry import project_index_dir
            from prep.services.pipeline_metadata import (
                METADATA_FILENAME,
                finalize_run_metadata,
                save_run_metadata,
            )
            from prep.services.project_helpers import require_project

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
                from prep.services.pipeline_history import history
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
            from prep.core.events import get_event_bus, get_progress_manager

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

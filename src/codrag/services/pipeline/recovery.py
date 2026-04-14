"""
RecoveryManager — Pipeline crash recovery, checkpoint creation, and backup restoration.

Phase 72 Stage 2: Extracted from orchestrator.py to consolidate all
backup, checkpoint, and crash recovery logic into a single module.

Works with ManifestStore for state inspection and
PipelineGroupStateMachine for state transitions.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .manifest_store import ManifestStore
from .stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    FINALIZE_STAGES,
    STAGE_MANIFEST_FILE,
    STAGE_OUTPUT_FILE,
    StageId,
)
from .state_machine import (
    Event,
    PipelineGroupStateMachine,
)

logger = logging.getLogger(__name__)


def _write_selfheal_stub(store: ManifestStore, stage: StageId, source: str) -> None:
    """Write a selfheal stub manifest for a resurrected stage."""
    store.write_provenance(stage, {
        "restored": True,
        "source": "selfheal",
        "backup_type": source,
        "restored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


def _resolve_idx_dir(project_id: str) -> Path | None:
    """Resolve the index directory for a project. Returns None on failure."""
    try:
        from codrag.core.project_registry import project_index_dir
        from codrag.services.project_helpers import require_project

        project = require_project(project_id)
        return Path(project_index_dir(project))
    except Exception:
        logger.debug("Could not resolve idx_dir for %s", project_id, exc_info=True)
        return None


_CLEAN_SHUTDOWN_FILENAME = ".pipeline_clean_shutdown"


class RecoveryManager:
    """Pipeline crash recovery, checkpoint creation, and backup restoration.

    Stateless methods that operate on disk state and ManifestStore.
    The orchestrator owns the lifecycle and passes in state as needed.
    """

    # ── Clean Shutdown Markers ─────────────────────────────────

    @staticmethod
    def write_clean_shutdown_marker(project_id: str) -> bool:
        """Write a marker indicating this project shut down cleanly (no active runs).

        Called during graceful server shutdown for projects that have NO active
        pipeline runs. On next startup, auto_recover_stale_pipelines checks for
        this marker — if present, incomplete deep enrichment manifests are
        steady-state (not interrupted), so recovery is skipped.

        Returns True if the marker was written successfully.
        """
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        try:
            marker_path = idx_dir / _CLEAN_SHUTDOWN_FILENAME
            marker_path.write_text(str(time.time()))
            return True
        except Exception:
            logger.debug(
                "Failed to write clean shutdown marker for %s",
                project_id, exc_info=True,
            )
            return False

    @staticmethod
    def check_clean_shutdown_marker(project_id: str) -> bool:
        """Check if a clean shutdown marker exists (read-only, does NOT remove).

        Use this when multiple code paths need to check the marker. The marker
        is only cleared by read_and_clear_clean_shutdown_marker() in the
        recovery code path.
        """
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        return (idx_dir / _CLEAN_SHUTDOWN_FILENAME).exists()

    @staticmethod
    def read_and_clear_clean_shutdown_marker(project_id: str) -> bool:
        """Check if a clean shutdown marker exists and remove it.

        Returns True if the marker existed (clean shutdown), False otherwise
        (crash or first run). Safe under concurrent calls — the second caller
        gets False from the except branch if the file was already removed.
        """
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        marker_path = idx_dir / _CLEAN_SHUTDOWN_FILENAME
        if not marker_path.exists():
            return False
        try:
            marker_path.unlink()
            return True
        except Exception:
            logger.debug(
                "Failed to clear clean shutdown marker for %s",
                project_id, exc_info=True,
            )
            return False

    # ── Checkpointing ──────────────────────────────────────────

    @staticmethod
    def create_checkpoint_if_needed(
        run: PipelineGroupStateMachine,
        stage: StageId,
    ) -> None:
        """Create a checkpoint before destructive stages."""
        if not run.journal_run_id:
            return
        try:
            from codrag.services.pipeline_checkpoint import CHECKPOINT_STAGES, create_checkpoint

            if stage.value not in CHECKPOINT_STAGES:
                return

            idx_dir = _resolve_idx_dir(run.project_id)
            if idx_dir is None:
                return

            cp_path = create_checkpoint(idx_dir, run.journal_run_id, stage.value)
            if cp_path:
                from codrag.services.pipeline_journal import journal

                journal.set_checkpoint(run.journal_run_id, cp_path)
        except Exception:
            logger.debug("Checkpoint creation failed (non-fatal)", exc_info=True)

    # ── Backup restore (full project) ──────────────────────────

    @staticmethod
    def try_restore_from_backup(
        project_id: str,
        stages: list,
        pfl: Any = None,
    ) -> bool:
        """Try to restore pipeline data from the most recent backup checkpoint.

        Before starting a full rebuild from scratch, check if a backup
        exists. If so, restore the data files and return True. The
        caller should then re-run _detect_resume_point to find where
        to resume from the restored data.

        Returns True if data was restored, False if no backup found.
        """
        try:
            idx_dir = _resolve_idx_dir(project_id)
            if idx_dir is None:
                return False

            checkpoints_dir = idx_dir / ".checkpoints"
            if not checkpoints_dir.exists():
                return False

            # Phase 72D: Prefer the golden checkpoint (known-good state)
            best_checkpoint = None
            best_size = 0

            golden_dir = checkpoints_dir / "_golden"
            if golden_dir.is_dir():
                golden_size = sum(
                    f.stat().st_size
                    for f in golden_dir.iterdir()
                    if f.is_file() and f.suffix in (".jsonl", ".json")
                )
                if golden_size > 1024:
                    best_checkpoint = golden_dir
                    best_size = golden_size
                    logger.info(
                        "Phase 72D: Preferring golden checkpoint for %s "
                        "(%d bytes of data)",
                        project_id, golden_size,
                    )

            # Fallback: find the most recent run checkpoint with the most data
            if best_checkpoint is None:
                for cp_dir in sorted(checkpoints_dir.iterdir(), reverse=True):
                    if not cp_dir.is_dir():
                        continue
                    if cp_dir.name.startswith("_"):
                        continue  # Already checked _golden
                    total_size = sum(
                        f.stat().st_size
                        for f in cp_dir.iterdir()
                        if f.is_file() and f.suffix in (".jsonl", ".json")
                    )
                    if total_size > best_size:
                        best_size = total_size
                        best_checkpoint = cp_dir

            if not best_checkpoint or best_size < 1024:
                return False

            # Restore files from the backup
            restored_files = []
            for src_file in best_checkpoint.iterdir():
                if not src_file.is_file():
                    continue
                dst_file = idx_dir / src_file.name
                if not dst_file.exists() or dst_file.stat().st_size < src_file.stat().st_size:
                    shutil.copy2(str(src_file), str(dst_file))
                    restored_files.append(src_file.name)

            if restored_files:
                logger.info(
                    "Phase 60D: Restored %d files from backup %s for %s: %s",
                    len(restored_files),
                    best_checkpoint.name,
                    project_id,
                    ", ".join(sorted(restored_files)[:10]),
                )
                if pfl:
                    pfl.decision(
                        "mode_selection",
                        "backup_restore",
                        {
                            "group": "fast_sync",
                            "reason": f"Restored {len(restored_files)} files from backup {best_checkpoint.name}",
                            "checkpoint": best_checkpoint.name,
                            "restored_files": sorted(restored_files),
                            "total_backup_size_mb": round(best_size / 1_048_576, 1),
                        },
                    )
                return True

            return False
        except Exception:
            logger.debug(
                "Failed to restore from backup for %s (non-fatal)",
                project_id,
                exc_info=True,
            )
            return False

    # ── Backup restore (per-stage) ─────────────────────────────

    @staticmethod
    def try_restore_stage_from_backup(
        run: PipelineGroupStateMachine,
        stage: StageId,
        pfl: Any = None,
    ) -> bool:
        """Check if a backup has valid data for this stage and restore it.

        Only applies to stages that don't already have output on disk.
        Skips STRUCTURAL stage since the trace graph must always reflect
        current filesystem state.

        Returns True if the stage was restored (caller should skip running it).
        """
        if stage == StageId.STRUCTURAL:
            return False

        try:
            from codrag.services.branch_backup_manager import (
                check_stage_backup,
                restore_stage_from_backup,
            )

            idx_dir = _resolve_idx_dir(run.project_id)
            if idx_dir is None:
                return False

            manifest_file = STAGE_MANIFEST_FILE.get(stage)
            output_file = STAGE_OUTPUT_FILE.get(stage)

            if not manifest_file:
                return False

            # Only restore if the stage's output doesn't already exist on disk
            if output_file and (idx_dir / output_file).is_file():
                return False
            if (idx_dir / manifest_file).is_file():
                return False

            backup = check_stage_backup(idx_dir, manifest_file, output_file)
            if backup is None:
                return False

            logger.info(
                "Phase 60B: Found backup data for stage %s from branch '%s' "
                "(%d records) — restoring instead of rebuilding",
                stage.value,
                backup["branch"],
                backup["record_count"],
            )
            if pfl:
                pfl.log(
                    stage.value,
                    f"RESTORED from backup (branch={backup['branch']}, "
                    f"records={backup['record_count']})",
                )

            restore_stage_from_backup(
                idx_dir,
                backup["snapshot_dir"],
                manifest_file,
                output_file,
            )

            # Mark as restored — the orchestrator wrapper handles advancing
            run.stage_results[stage.value] = "restored_from_backup"
            run.current_stage_index += 1
            return True

        except Exception:
            logger.debug(
                "Backup restore check failed (non-fatal) for %s/%s",
                run.project_id,
                stage.value,
                exc_info=True,
            )
        return False

    # ── Selfheal group scan ───────────────────────────────────

    @staticmethod
    def selfheal_group(
        project_id: str,
        stages: list[StageId],
        force_from_start: bool = False,
        pfl: Any = None,
    ) -> dict[str, Any]:
        """Scan pipeline stages for missing manifests and resurrect from backups.

        Tries backup sources in priority order:
          1. Golden checkpoint
          2. Run checkpoints (most recent first)
          3. Branch snapshot

        Returns a summary dict with resurrected/already_complete/still_missing counts.
        """
        # Dev flag: disable selfheal entirely
        if os.environ.get("CODRAG_SELFHEAL", "1") == "0":
            return {"disabled": True, "resurrected": 0}

        # Force rebuild: skip selfheal
        if force_from_start:
            return {"skipped_force_rebuild": True, "resurrected": 0}

        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return {"resurrected": 0, "already_complete": 0, "still_missing": len(stages), "checked": len(stages), "details": []}

        store = ManifestStore(idx_dir)

        resurrected = 0
        already_complete = 0
        still_missing = 0
        details: list[dict[str, Any]] = []

        # Resolve branch snapshot directory (graceful failure)
        branch_snapshot_dir: Path | None = None
        try:
            from codrag.services.branch_backup_manager import read_branch_state, SNAPSHOTS_DIR
            state = read_branch_state(idx_dir)
            branch = state.get("branch")
            if branch:
                from codrag.services.branch_backup_manager import _sanitize_branch_name
                snap_dir = idx_dir / SNAPSHOTS_DIR / _sanitize_branch_name(branch)
                if snap_dir.is_dir():
                    branch_snapshot_dir = snap_dir
        except Exception:
            pass

        # Build ordered backup source list ONCE (not per-stage)
        backup_sources: list[tuple[str, Path]] = []
        golden_dir = idx_dir / ".checkpoints" / "_golden"
        if golden_dir.is_dir():
            backup_sources.append(("golden", golden_dir))
        cp_root = idx_dir / ".checkpoints"
        if cp_root.is_dir():
            for cp_dir in sorted(cp_root.iterdir(), reverse=True):
                if cp_dir.is_dir() and not cp_dir.name.startswith("_"):
                    backup_sources.append(("run_checkpoint", cp_dir))
        if branch_snapshot_dir is not None:
            backup_sources.append(("branch_snapshot", branch_snapshot_dir))

        # Shared-output stages: orphan detection must be skipped because
        # the output file belongs to an earlier stage, not this one.
        _SHARED_OUTPUT_STAGES = {StageId.DEEPENING, StageId.DEEP_KNOWLEDGE}

        for stage in stages:
            stage_detail: dict[str, Any] = {"stage": stage.value}

            # 1. Already has manifest -> skip
            if store.provenance_exists(stage):
                already_complete += 1
                stage_detail["status"] = "already_complete"
                details.append(stage_detail)
                continue

            output_file = STAGE_OUTPUT_FILE.get(stage)
            manifest_file = STAGE_MANIFEST_FILE.get(stage)

            # 2. Orphan output: file exists on disk but no manifest.
            if output_file and stage not in _SHARED_OUTPUT_STAGES:
                orphan_path = idx_dir / output_file
                if orphan_path.is_file() and orphan_path.stat().st_size > 1024:
                    _write_selfheal_stub(store, stage, "orphan_output")
                    resurrected += 1
                    stage_detail["status"] = "resurrected"
                    stage_detail["source"] = "orphan_output"
                    details.append(stage_detail)
                    if pfl:
                        pfl.selfheal(
                            "resurrect",
                            f"Stage {stage.value}: orphan output found, wrote stub manifest",
                            {"stage": stage.value, "source": "orphan_output"},
                        )
                    continue

            # 3. Try backup sources in priority order
            found = False

            for source_label, source_dir in backup_sources:
                if output_file is not None:
                    # Stage with output file: check for the output file in backup
                    src_path = source_dir / output_file
                    if src_path.is_file() and src_path.stat().st_size > 1024:
                        shutil.copy2(str(src_path), str(idx_dir / output_file))
                        _write_selfheal_stub(store, stage, source_label)
                        resurrected += 1
                        found = True
                        stage_detail["status"] = "resurrected"
                        stage_detail["source"] = source_label
                        if pfl:
                            pfl.selfheal(
                                "resurrect",
                                f"Stage {stage.value}: restored from {source_label}",
                                {"stage": stage.value, "source": source_label, "backup_dir": str(source_dir)},
                            )
                        break
                else:
                    # Stage with no output file (validation, knowledge, etc.):
                    # look for the manifest file itself in the backup.
                    # Write a selfheal stub (not a raw copy) so the manifest
                    # is consistently tagged as restored.
                    if manifest_file:
                        src_manifest = source_dir / manifest_file
                        if src_manifest.is_file() and src_manifest.stat().st_size > 10:
                            _write_selfheal_stub(store, stage, source_label)
                            resurrected += 1
                            found = True
                            stage_detail["status"] = "resurrected"
                            stage_detail["source"] = source_label
                            if pfl:
                                pfl.selfheal(
                                    "resurrect",
                                    f"Stage {stage.value}: manifest restored from {source_label}",
                                    {"stage": stage.value, "source": source_label, "backup_dir": str(source_dir)},
                                )
                            break

            if not found:
                still_missing += 1
                stage_detail["status"] = "still_missing"
                if pfl:
                    pfl.selfheal(
                        "no_backup",
                        f"Stage {stage.value}: no backup found",
                        {"stage": stage.value},
                    )

            details.append(stage_detail)

        result: dict[str, Any] = {
            "resurrected": resurrected,
            "already_complete": already_complete,
            "still_missing": still_missing,
            "checked": len(stages),
            "details": details,
        }

        if pfl:
            pfl.selfheal(
                "selfheal_group_complete",
                f"Selfheal scan: {resurrected} resurrected, {already_complete} complete, {still_missing} missing",
                result,
            )

        return result

    @staticmethod
    def startup_selfheal_all(
        get_file_logger_fn: Callable[[str], Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Run selfheal for all active projects at daemon startup.

        Returns dict of project_id -> selfheal result.
        """
        results: dict[str, dict[str, Any]] = {}
        try:
            from codrag.services.project_helpers import get_registry

            registry = get_registry()
            projects = registry.list_projects()
        except Exception:
            logger.debug("Cannot list projects for startup selfheal", exc_info=True)
            return results

        all_groups = [FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES]

        for project in projects:
            pid = project.id

            # Skip inactive/frozen/locked projects
            try:
                from codrag.services.project_helpers import get_project_activity_status
                activity = get_project_activity_status(pid)
                if activity != "active":
                    continue
            except Exception:
                pass  # Can't determine status — proceed

            pfl = get_file_logger_fn(pid) if get_file_logger_fn else None

            project_result: dict[str, Any] = {}
            for stages in all_groups:
                group_name = (
                    "fast_sync" if stages is FAST_SYNC_STAGES
                    else "deep_enrichment" if stages is DEEP_ENRICHMENT_STAGES
                    else "finalize"
                )
                group_result = RecoveryManager.selfheal_group(pid, stages, pfl=pfl)
                if group_result.get("resurrected", 0) > 0:
                    project_result[group_name] = group_result
                    logger.info(
                        "Startup selfheal for %s/%s: %d resurrected",
                        pid, group_name, group_result["resurrected"],
                    )

            if project_result:
                results[pid] = project_result

        if results:
            total = sum(
                r.get("resurrected", 0)
                for pr in results.values()
                for r in pr.values()
            )
            logger.info(
                "Startup selfheal complete: %d projects healed, %d total stages resurrected",
                len(results), total,
            )
        return results

    # ── Crashed run management ─────────────────────────────────

    @staticmethod
    def get_crashed_runs(project_id: str | None = None) -> list[dict[str, Any]]:
        """Get crashed runs for UI display."""
        try:
            from codrag.services.pipeline_journal import journal

            entries = journal.get_crashed_runs(project_id)
            return [e.to_dict() for e in entries]
        except Exception:
            return []

    @staticmethod
    def resume_crashed_run(
        run_id: str,
        start_group_fn: Callable[..., bool],
    ) -> bool:
        """Resume a crashed pipeline run from the stage it was on.

        Args:
            run_id: The journal run ID to resume.
            start_group_fn: Callback to start a group (project_id, group, stages,
                chain_deep, resume_from) -> bool. Provided by the orchestrator.
        """
        try:
            from codrag.services.pipeline_journal import journal

            entry = journal.get_run(run_id)
            if not entry or entry.status != "crashed":
                return False

            journal.resolve_crashed_run(run_id, "resumed")

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
                run_id,
                entry.project_id,
                entry.group,
                resume_from,
                entry.current_stage,
            )

            return start_group_fn(
                entry.project_id,
                entry.group,
                stages,
                chain_deep=chain_deep,
                resume_from=resume_from,
            )
        except Exception:
            logger.exception("Resume failed for run %s", run_id)
            return False

    @staticmethod
    def discard_crashed_run(run_id: str) -> bool:
        """Discard a crashed pipeline run without resuming."""
        try:
            from codrag.services.pipeline_journal import journal

            return journal.resolve_crashed_run(run_id, "discarded")
        except Exception:
            return False

    # ── Startup recovery orchestration ─────────────────────────

    @staticmethod
    def startup_recovery(
        hydrate_fn: Callable[[], None],
        auto_recover_fn: Callable[[], None],
        set_crashed_runs: Callable[[list], None],
        selfheal_fn: Callable[[], None] | None = None,
    ) -> list[Any]:
        """Called once on daemon startup. Detects crashed runs and
        hydrates PAUSED state machines for incomplete pipeline work.

        Args:
            hydrate_fn: Callback to _hydrate_paused_runs_from_disk
            auto_recover_fn: Callback to _auto_recover_stale_pipelines
            set_crashed_runs: Callback to store crashed runs list

        Returns list of JournalEntry dicts for the UI to display.
        """
        # Phase 1: Journal-based crash detection
        journal_results: list = []
        try:
            from codrag.services.pipeline_journal import journal

            crashed = journal.recover_crashed_runs()
            set_crashed_runs(crashed)
            if crashed:
                logger.warning(
                    "Crash recovery: found %d crashed pipeline run(s)",
                    len(crashed),
                )
                for entry in crashed:
                    try:
                        from codrag.services.pipeline_checkpoint import (
                            auto_heal,
                            verify_trace_files,
                        )

                        idx_dir = _resolve_idx_dir(entry.project_id)
                        if idx_dir is None:
                            continue
                        valid, corrupt = verify_trace_files(idx_dir)
                        if not valid:
                            logger.warning(
                                "Corrupt trace files for %s: %s — attempting auto-heal",
                                entry.project_id,
                                corrupt,
                            )
                            results = auto_heal(idx_dir, entry.checkpoint_path)
                            logger.info(
                                "Auto-heal results for %s: %s",
                                entry.project_id,
                                results,
                            )
                    except Exception:
                        logger.debug(
                            "Auto-heal failed for %s",
                            entry.project_id,
                            exc_info=True,
                        )
            journal_results = [e.to_dict() for e in crashed]
        except Exception:
            logger.debug("Journal crash recovery failed", exc_info=True)

        # Phase 98: Startup selfheal FIRST — resurrect incomplete stages from
        # backups/orphan outputs BEFORE resume detection runs. Without this,
        # hydrate_fn's resume detector sees missing manifests (F-67 deletes
        # them at stage start; if the daemon restarts mid-stage the output
        # file is stranded with no manifest) and pins the PAUSED state machine
        # at the wrong resume point even though the stage's data is on disk.
        if selfheal_fn:
            try:
                selfheal_fn()
            except Exception:
                logger.debug("Startup selfheal failed (non-fatal)", exc_info=True)

        # Phase 2: Disk-state hydration
        try:
            hydrate_fn()
        except Exception:
            logger.debug("Disk-state hydration failed", exc_info=True)

        # Phase 61B: Auto-recovery
        try:
            auto_recover_fn()
        except Exception:
            logger.debug("Phase 61B auto-recovery failed", exc_info=True)

        return journal_results

    # ── Disk-state hydration ───────────────────────────────────

    @staticmethod
    def hydrate_paused_runs_from_disk(
        detect_resume_fn: Callable[[str, list, bool], int],
        register_run_fn: Callable[[str, str, PipelineGroupStateMachine], None],
        is_run_active_fn: Callable[[str], bool],
        default_guard: Any,
    ) -> None:
        """Scan all projects and create PAUSED state machines for incomplete work.

        Args:
            detect_resume_fn: (project_id, stages, skip_mtime) -> resume_index
            register_run_fn: (project_id, group, sm) -> None
            is_run_active_fn: (project_id) -> bool
            default_guard: Guard to add to state machines
        """
        try:
            from codrag.services.project_helpers import get_registry
            from codrag.services.settings_store import settings

            registry = get_registry()
            projects = registry.list_projects()
        except Exception:
            logger.debug("Cannot list projects for disk-state hydration", exc_info=True)
            return

        # Check pipeline config for auto modes
        try:
            config = settings.get("pipeline_config") or {}
            fast_auto = (config.get("fast_sync") or {}).get("auto", False)
            deep_auto = (config.get("deep_enrichment") or {}).get("mode", "manual") == "auto"
        except Exception:
            fast_auto = False
            deep_auto = False

        groups = [
            ("fast_sync", FAST_SYNC_STAGES, fast_auto),
            ("deep_enrichment", DEEP_ENRICHMENT_STAGES, deep_auto),
        ]

        for project in projects:
            pid = project.id

            # F-65/F-69: Skip inactive/frozen/locked projects.
            # Without this, deactivated projects get PAUSED state machines
            # hydrated on every restart, and the auto-recovery path may
            # start them — blocking the scheduler for active projects.
            try:
                from codrag.services.project_helpers import get_project_activity_status
                activity = get_project_activity_status(pid)
                if activity != "active":
                    continue
            except Exception:
                pass

            # Skip if any group is already active
            if is_run_active_fn(pid):
                continue

            for group, stages, is_auto in groups:
                if is_auto:
                    logger.info(
                        "Skipping PAUSED hydration for %s/%s — "
                        "auto mode will handle resumption",
                        pid,
                        group,
                    )
                    continue

                resume = detect_resume_fn(pid, stages, True)
                if resume <= 0 or resume >= len(stages):
                    continue

                # Create a PAUSED state machine at the resume point
                sm = PipelineGroupStateMachine(
                    project_id=pid,
                    group=group,
                    stages=[s.value for s in stages],
                )
                sm.add_guard(default_guard)

                # Transition: IDLE -> RUNNING -> PAUSING -> PAUSED
                sm.transition(Event.START)
                sm.current_stage_index = resume
                for i in range(resume):
                    sm.stage_results[stages[i].value] = "completed"
                sm.transition(Event.PAUSE)
                sm.transition(Event.STAGE_FLUSHED)

                register_run_fn(pid, group, sm)

                logger.info(
                    "Hydrated PAUSED state for %s/%s at stage %d/%d (%s) "
                    "— user can Resume to continue",
                    pid,
                    group,
                    resume,
                    len(stages),
                    stages[resume].value,
                )

    # ── Auto-recovery of stale pipelines ───────────────────────

    @staticmethod
    def auto_recover_stale_pipelines(
        is_deep_auto_fn: Callable[[str], bool],
        get_file_logger_fn: Callable[[str], Any],
        is_run_active_fn: Callable[[str], bool],
        clear_paused_runs_fn: Callable[[str], list],
        run_deep_enrichment_fn: Callable[[str], bool],
    ) -> None:
        """Scan all projects for stale pipeline state and auto-recover.

        Called during startup_recovery AFTER hydrate_paused_runs_from_disk.

        Args:
            is_deep_auto_fn: (project_id) -> bool
            get_file_logger_fn: (project_id) -> pfl or None
            is_run_active_fn: (project_id) -> bool
            clear_paused_runs_fn: (project_id) -> cleared_keys
            run_deep_enrichment_fn: (project_id) -> started
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
            idx_dir = _resolve_idx_dir(pid)
            if idx_dir is None:
                continue

            # Phase 72B: Skip inactive/frozen/locked projects.
            # Auto-recovery should only trigger for active projects.
            # Without this filter, ALL projects get recovery-triggered on
            # every daemon restart, overwhelming the scheduler and starving
            # newly-enabled projects that actually need processing.
            try:
                from codrag.services.project_helpers import get_project_activity_status
                activity = get_project_activity_status(pid)
                if activity != "active":
                    logger.debug(
                        "Phase 61B: skipping auto-recovery for %s (status=%s)",
                        pid, activity,
                    )
                    continue
            except Exception:
                pass  # Can't determine status — proceed with recovery

            pfl = get_file_logger_fn(pid)

            # Step 1: Check for stale/zombie metadata and reset
            try:
                from codrag.services.pipeline_metadata import (
                    check_heartbeat_stale,
                    reset_stale_metadata,
                )

                stale_info = check_heartbeat_stale(idx_dir)
                if stale_info:
                    logger.warning(
                        "Phase 61B: Detected %s pipeline metadata for %s "
                        "(run_id=%s, group=%s, age=%.0fs, heartbeat_age=%.0fs)",
                        stale_info["status"],
                        pid,
                        stale_info.get("run_id"),
                        stale_info.get("group"),
                        stale_info.get("age_seconds", 0),
                        stale_info.get("heartbeat_age_seconds", 0),
                    )
                    if pfl:
                        pfl.selfheal("stale_detected", f"{stale_info['status']} metadata found", stale_info)

                    reset_stale_metadata(idx_dir, reason="startup_recovery")
                    if pfl:
                        pfl.selfheal(
                            "metadata_reset",
                            "Reset stale metadata to 'interrupted'",
                            {"project_id": pid, "previous_status": stale_info["status"]},
                        )
            except Exception:
                logger.debug("Phase 61B: stale check failed for %s", pid, exc_info=True)

            # Step 2: Log manifest age summary
            try:
                store = ManifestStore(idx_dir)
                manifest_ages = store.age_summary()
                if pfl:
                    pfl.selfheal(
                        "manifest_age",
                        f"Pipeline checkpoint age summary for {pid}",
                        {"project_id": pid, "manifests": manifest_ages},
                    )
                ages_str = ", ".join(
                    f"{k}={v.get('age_hours', '?')}h" if v.get("status") == "present" else f"{k}=MISSING"
                    for k, v in manifest_ages.items()
                )
                logger.info("Phase 61B manifest ages for %s: %s", pid, ages_str)
            except Exception:
                logger.debug("Phase 61B: manifest age summary failed for %s", pid, exc_info=True)

            # Step 3: Auto-trigger deep enrichment if manifests are stale
            # Phase 93: Clean shutdown guard — if the daemon shut down
            # gracefully and this project had no active runs, its incomplete
            # deep enrichment manifests are steady-state, not an interruption.
            # Skip the deep enrichment trigger (but Steps 1-2 above still run
            # for diagnostics and stale metadata cleanup).
            was_clean = RecoveryManager.check_clean_shutdown_marker(pid)
            if was_clean:
                logger.info(
                    "Phase 93: Clean shutdown marker found for %s — "
                    "skipping deep enrichment auto-recovery "
                    "(incomplete manifests are steady-state)",
                    pid,
                )
                if pfl:
                    pfl.selfheal(
                        "auto_recover",
                        "Skipped — clean shutdown marker present",
                        {"project_id": pid},
                    )
                continue

            try:
                if not is_deep_auto_fn(pid):
                    if pfl:
                        pfl.selfheal(
                            "auto_recover",
                            "Skipped — deep_enrichment auto mode is OFF",
                            {"project_id": pid},
                        )
                    continue

                store = ManifestStore(idx_dir)
                if not store.provenance_exists(StageId.STRUCTURAL):
                    continue

                structural_mtime = store.provenance_mtime(StageId.STRUCTURAL)
                deep_stale = False

                for stage in DEEP_ENRICHMENT_STAGES:
                    if not store.provenance_exists(stage):
                        # Phase 72C: Before declaring stale, check if the
                        # DATA FILE exists. If so, the stage completed but
                        # the manifest was lost (pre-manifest code, or
                        # deleted by _invalidate_deep_manifests). Create a
                        # stub manifest so we don't needlessly re-run.
                        #
                        # Phase 72D: SKIP stub creation for stages that share
                        # their output file with a prior stage. The data file
                        # belongs to the earlier stage, not this one.
                        _SHARED_OUTPUT_STAGES = {
                            StageId.DEEPENING,       # shares trace_epistemic.jsonl with ENRICHMENT
                            StageId.DEEP_KNOWLEDGE,  # shares knowledge_* with KNOWLEDGE
                        }
                        if stage in _SHARED_OUTPUT_STAGES:
                            # Phase 93: A missing manifest for a shared-output
                            # stage means it hasn't been run yet — that's normal
                            # steady-state, not a crash recovery scenario. Only
                            # declare stale if this was an interrupted run (no
                            # clean shutdown marker, which is checked above).
                            # Without this fix, DEEPENING/DEEP_KNOWLEDGE always
                            # have missing manifests for projects that completed
                            # enrichment but never ran deepening, causing ghost
                            # recovery runs on every daemon restart.
                            logger.info(
                                "Phase 72D/93: Stage %s manifest missing — "
                                "shared-output stage not yet run (steady-state, "
                                "not stale)",
                                stage.value,
                            )
                            continue

                        output_file = STAGE_OUTPUT_FILE.get(stage)
                        data_path = (idx_dir / output_file) if output_file else None
                        if data_path and data_path.exists() and data_path.stat().st_size > 0:
                            logger.info(
                                "Phase 72C: Stage %s manifest missing but data "
                                "file %s exists (%d bytes). Creating stub manifest "
                                "instead of triggering re-run.",
                                stage.value, output_file, data_path.stat().st_size,
                            )
                            store.write_provenance(stage, {
                                "codrag_version": "0.1.0",
                                "format_version": "2.0",
                                "stage_id": stage.value,
                                "restored": True,
                                "restored_reason": "manifest_missing_but_data_exists",
                            })
                            store.touch_provenance_mtime(stage, structural_mtime)
                            if pfl:
                                pfl.selfheal(
                                    "auto_recover",
                                    f"Created stub manifest for {stage.value} "
                                    f"(data file {output_file} exists)",
                                    {"project_id": pid, "stage": stage.value},
                                )
                            continue
                        deep_stale = True
                        break
                    if store.provenance_mtime(stage) < structural_mtime:
                        deep_stale = True
                        break

                if deep_stale:
                    # Phase 72: Touch manifests first and re-check
                    store.sync_downstream_mtimes(StageId.CATALOGUE, list(DEEP_ENRICHMENT_STAGES))

                    # Re-verify after touching
                    deep_stale_after_touch = False
                    for stage in DEEP_ENRICHMENT_STAGES:
                        if not store.provenance_exists(stage):
                            deep_stale_after_touch = True
                            break
                        if store.provenance_mtime(stage) < structural_mtime:
                            deep_stale_after_touch = True
                            break

                    if not deep_stale_after_touch:
                        logger.info(
                            "Phase 61B/72: Deep manifests for %s were stale but "
                            "touch resolved it — no recovery needed",
                            pid,
                        )
                        if pfl:
                            pfl.selfheal(
                                "auto_recover",
                                "Manifests were stale but touch fixed it — skipping recovery",
                                {"project_id": pid},
                            )
                        continue

                    # Still stale — check for active/paused runs
                    if is_run_active_fn(pid):
                        logger.info(
                            "Phase 61B: Deep manifests stale for %s but run already "
                            "active — skipping auto-recover",
                            pid,
                        )
                        continue

                    # Clear hydrated PAUSED runs
                    cleared = clear_paused_runs_fn(pid)
                    if cleared:
                        logger.info(
                            "Phase 61B: Cleared %d PAUSED hydrated runs for %s "
                            "— auto mode replaces manual Resume",
                            len(cleared),
                            pid,
                        )
                        if pfl:
                            pfl.selfheal(
                                "auto_recover",
                                "Cleared PAUSED runs for auto mode",
                                {"project_id": pid, "cleared_keys": [str(k) for k in cleared]},
                            )

                    logger.info(
                        "Phase 61B: Auto-recovering deep enrichment for %s "
                        "(deep manifests genuinely stale vs structural trace)",
                        pid,
                    )
                    if pfl:
                        pfl.selfheal(
                            "auto_recover",
                            "Triggering deep enrichment — manifests genuinely stale",
                            {"project_id": pid, "reason": "deep_manifests_stale_vs_structural_after_touch"},
                        )

                    # Phase 93: Run recovery synchronously instead of in a
                    # delayed thread. The old 10s sleep(10) + daemon thread
                    # caused a race condition: the state machine didn't exist
                    # in _runs yet when the UI polled status, producing
                    # contradictory running/not-running state and missing logs.
                    # Synchronous execution ensures the state machine and file
                    # logger are created before any status query can arrive.
                    # Note: run_deep_enrichment_fn returns quickly — it creates
                    # a state machine and spawns a worker thread, it does NOT
                    # block on the actual enrichment work.
                    try:
                        started = run_deep_enrichment_fn(pid)
                        logger.info(
                            "Phase 61B: Auto-recovery deep enrichment for %s: started=%s",
                            pid,
                            started,
                        )
                        if pfl:
                            pfl.selfheal(
                                "auto_recover",
                                f"run_deep_enrichment returned {started}",
                                {"project_id": pid, "started": started},
                            )
                    except Exception as e:
                        logger.warning(
                            "Phase 61B: Auto-recovery failed for %s: %s",
                            pid,
                            e,
                            exc_info=True,
                        )
                        if pfl:
                            pfl.selfheal(
                                "auto_recover",
                                f"Recovery FAILED: {e}",
                                {"project_id": pid, "error": str(e)},
                            )
                else:
                    if pfl:
                        pfl.selfheal(
                            "auto_recover",
                            "No recovery needed — deep manifests up to date",
                            {"project_id": pid},
                        )

            except Exception:
                logger.debug("Phase 61B: auto-trigger check failed for %s", pid, exc_info=True)

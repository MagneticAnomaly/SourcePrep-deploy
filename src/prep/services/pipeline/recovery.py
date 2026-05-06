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
from typing import Any, Dict, Optional

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
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project

        project = require_project(project_id)
        return Path(project_index_dir(project))
    except Exception:
        logger.debug("Could not resolve idx_dir for %s", project_id, exc_info=True)
        return None


_CLEAN_SHUTDOWN_FILENAME = ".pipeline_clean_shutdown"
_BUILD_SUCCESS_FILENAME = ".pipeline_last_success"  # Phase 128
_RESET_BARRIER_FILENAME = ".reset_barrier"
_USER_PAUSE_FILENAME_TEMPLATE = ".pipeline_user_pause_{group}.json"
_VALID_BARRIER_SCOPES = ("sync", "enrichment", "finalize", "all")

# Phase 128: groups whose successful completion proves "deep_enrichment data
# is healthy" for Phase 61B's staleness check. fast_sync produces structural
# (which is what the staleness check compares AGAINST), but does not produce
# deep enrichment manifests. Writing the marker after fast_sync would falsely
# suppress legitimate deep recovery.
_BUILD_SUCCESS_GROUPS = ("deep_enrichment", "finalize")


def record_group_completion(project_id: str, group: str) -> bool:
    """Phase 128: Refresh the build-success marker for relevant groups.

    Called by the orchestrator after a group finishes successfully. For
    fast_sync the marker is intentionally NOT written — fast_sync alone
    doesn't prove the deep_enrichment data is fresh, and writing it
    would falsely suppress legitimate Phase 61B recovery.

    Returns True if the marker was written, False otherwise.
    """
    if group not in _BUILD_SUCCESS_GROUPS:
        return False
    return RecoveryManager.write_build_success_marker(project_id)


def write_reset_barrier(
    project_id: str,
    reason: str,
    scope: str = "all",
) -> bool:
    """Write a barrier that disables selfheal until the scope's group finishes.

    ``scope`` names which group the rebuild/reset is forcing from start.
    - ``sync``: rebuild fast_sync (stages 1-5); barrier auto-clears when stage 5 finishes.
    - ``enrichment``: rebuild deep_enrichment (stages 6-10); barrier auto-clears when stage 10 finishes.
    - ``finalize``: reset finalize (stages 11-15); barrier auto-clears when stage 15 finishes.
    - ``all``: rebuild the full chain; barrier auto-clears when finalize (stage 15) finishes.

    The file is a 3-line text format for forward/backward compat:
        line 1: written_at (epoch seconds, float)
        line 2: reason
        line 3: scope   (added Phase 117; absent in legacy barriers → treated as "all")
    """
    if scope not in _VALID_BARRIER_SCOPES:
        raise ValueError(f"invalid barrier scope: {scope!r}")

    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return False
    try:
        idx_dir.mkdir(parents=True, exist_ok=True)
        barrier = idx_dir / _RESET_BARRIER_FILENAME
        barrier.write_text(f"{time.time()}\n{reason}\n{scope}\n")
        logger.info(
            "Reset barrier set for %s (reason=%s, scope=%s)",
            project_id, reason, scope,
        )
        return True
    except Exception:
        logger.debug("Failed to write reset barrier for %s", project_id, exc_info=True)
        return False


def clear_reset_barrier(project_id: str) -> bool:
    """Remove the reset barrier. Called on scope-group or finalize completion."""
    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return False
    barrier = idx_dir / _RESET_BARRIER_FILENAME
    if not barrier.is_file():
        return False
    try:
        barrier.unlink()
        logger.info("Reset barrier cleared for %s", project_id)
        return True
    except Exception:
        logger.debug("Failed to clear reset barrier for %s", project_id, exc_info=True)
        return False


def reset_barrier_active(project_id: str) -> bool:
    """True if a reset barrier is in effect for this project."""
    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return False
    return (idx_dir / _RESET_BARRIER_FILENAME).is_file()


def read_reset_barrier(project_id: str) -> dict | None:
    """Read the reset barrier contents. Returns None if inactive.

    Returns {"written_at": float, "reason": str, "scope": str, "age_seconds": float}.
    Legacy 2-line barriers (no scope line) report scope="all".
    """
    idx_dir = _resolve_idx_dir(project_id)
    if idx_dir is None:
        return None
    barrier = idx_dir / _RESET_BARRIER_FILENAME
    if not barrier.is_file():
        return None
    try:
        text = barrier.read_text().strip()
        lines = text.split("\n")
        written_at: float | None = None
        reason = ""
        scope = "all"
        if lines:
            try:
                written_at = float(lines[0])
            except ValueError:
                written_at = None
            if len(lines) >= 2:
                reason = lines[1].strip()
            if len(lines) >= 3:
                candidate = lines[2].strip()
                if candidate in _VALID_BARRIER_SCOPES:
                    scope = candidate
        if written_at is None:
            written_at = barrier.stat().st_mtime
        return {
            "written_at": written_at,
            "reason": reason or "unknown",
            "scope": scope,
            "age_seconds": max(0.0, time.time() - written_at),
        }
    except Exception:
        logger.debug("Failed to read reset barrier for %s", project_id, exc_info=True)
        return None


_SCOPE_BOUNDARY = {
    "sync": "fast_sync",
    "enrichment": "deep_enrichment",
    "finalize": "finalize",
    "all": "finalize",
}

# Subsumption: a barrier scope blocks reuse for the caller's group
# when the caller's group is in this set.
_SCOPE_BLOCKS: dict[str, frozenset[str]] = {
    "sync":       frozenset({"fast_sync"}),
    "enrichment": frozenset({"deep_enrichment", "finalize"}),
    "finalize":   frozenset({"finalize"}),
    "all":        frozenset({"fast_sync", "deep_enrichment", "finalize"}),
}


def is_reuse_blocked(project_id: str, *, stage_group: str) -> bool:
    """Return True if a reset barrier is active and its scope blocks
    incremental-reuse reads for the caller's stage_group.

    Stage-internal reuse paths (cluster fingerprint match, deepening
    drift cache, group_reasoning fingerprint reuse, knowledge incremental
    embed) call this before reading prior outputs. If True, the stage
    must treat existing artifacts as if they don't exist and process
    everything fresh.

    Args:
        project_id: the project being processed
        stage_group: one of "fast_sync", "deep_enrichment", "finalize"

    Returns:
        True if reuse is blocked, False if reuse is permitted.
    """
    info = read_reset_barrier(project_id)
    if info is None:
        return False
    scope = info.get("scope") or "all"  # legacy barriers default to "all"
    blocks = _SCOPE_BLOCKS.get(scope, frozenset())
    return stage_group in blocks


def maybe_clear_scoped_barrier(project_id: str, completed_group: str) -> bool:
    """Clear the reset barrier iff ``completed_group`` is the boundary for its scope.

    Called by the orchestrator after each group finishes. Returns True if the
    barrier was cleared, False otherwise (wrong boundary, or no barrier set).
    """
    info = read_reset_barrier(project_id)
    if info is None:
        return False
    boundary = _SCOPE_BOUNDARY.get(info.get("scope", "all"))
    if boundary != completed_group:
        return False
    return clear_reset_barrier(project_id)


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

    # ── User Pause Markers ─────────────────────────────────────
    #
    # When the user clicks Pause, we drop a per-group marker on disk
    # alongside the pipeline manifests. This marker is the *intent* signal
    # that survives daemon restart: hydration must rebuild a PAUSED state
    # machine for the group regardless of auto-mode policy. Without this,
    # auto-mode bypasses paused-state hydration entirely (the previous
    # Phase 118 U13 design assumed "auto means restart") and the user's
    # explicit pause was silently overridden on every restart.
    #
    # The marker is cleared on:
    #   - Resume (user clicks Resume)
    #   - Cancel (user discards the run)
    #   - Successful completion of the group's final stage
    #
    # The marker payload records *why* and *when* so future debugging can
    # correlate restart timelines without depending on log retention.

    @staticmethod
    def write_user_pause_marker(
        project_id: str,
        group: str,
        stage: Optional[str],
    ) -> bool:
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        try:
            import json
            marker_path = idx_dir / _USER_PAUSE_FILENAME_TEMPLATE.format(group=group)
            marker_path.write_text(json.dumps({
                "group": group,
                "stage": stage,
                "paused_at": time.time(),
                "user_initiated": True,
            }, indent=2))
            return True
        except Exception:
            logger.debug(
                "Failed to write user pause marker for %s/%s",
                project_id, group, exc_info=True,
            )
            return False

    @staticmethod
    def check_user_pause_marker(project_id: str, group: str) -> bool:
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        return (idx_dir / _USER_PAUSE_FILENAME_TEMPLATE.format(group=group)).exists()

    @staticmethod
    def read_user_pause_marker(project_id: str, group: str) -> Optional[Dict[str, Any]]:
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return None
        marker_path = idx_dir / _USER_PAUSE_FILENAME_TEMPLATE.format(group=group)
        if not marker_path.exists():
            return None
        try:
            import json
            return json.loads(marker_path.read_text())
        except Exception:
            return None

    @staticmethod
    def clear_user_pause_marker(project_id: str, group: str) -> bool:
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        marker_path = idx_dir / _USER_PAUSE_FILENAME_TEMPLATE.format(group=group)
        if not marker_path.exists():
            return False
        try:
            marker_path.unlink()
            return True
        except Exception:
            logger.debug(
                "Failed to clear user pause marker for %s/%s",
                project_id, group, exc_info=True,
            )
            return False

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

    # ── Build-Success Markers (Phase 128) ──────────────────────
    #
    # Separate from clean-shutdown markers. The clean-shutdown marker
    # records "the daemon was gracefully stopped while no run was active"
    # and can only be written from the lifespan shutdown handler on
    # SIGTERM. The build-success marker records "a complete pipeline run
    # finished successfully on disk" and is written when finalize ends.
    # It survives any subsequent ungraceful daemon termination, closing
    # the gap where Phase 61B re-triggers a full rebuild after kill -9 /
    # USB eject / sleep — situations where the existing clean-shutdown
    # marker is missing despite healthy data.
    #
    # The marker is NOT cleared on read — it persists until invalidated
    # by an actual destructive reset that wipes outputs.

    @staticmethod
    def write_build_success_marker(project_id: str) -> bool:
        """Write a marker indicating the pipeline last completed successfully."""
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        try:
            marker_path = idx_dir / _BUILD_SUCCESS_FILENAME
            marker_path.write_text(str(time.time()))
            return True
        except Exception:
            logger.debug(
                "Failed to write build success marker for %s",
                project_id, exc_info=True,
            )
            return False

    @staticmethod
    def check_build_success_marker(project_id: str) -> bool:
        """Check if a build-success marker exists (read-only)."""
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        return (idx_dir / _BUILD_SUCCESS_FILENAME).exists()

    @staticmethod
    def build_success_marker_mtime(project_id: str) -> Optional[float]:
        """Return the mtime of the build-success marker, or None if absent.

        Phase 61B compares this against structural mtime: if the marker
        post-dates structural, the existing data is provably fresh.
        """
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return None
        marker_path = idx_dir / _BUILD_SUCCESS_FILENAME
        if not marker_path.exists():
            return None
        try:
            return marker_path.stat().st_mtime
        except OSError:
            return None

    @staticmethod
    def invalidate_build_success_marker(project_id: str) -> bool:
        """Remove the marker (e.g. when a destructive reset wipes outputs)."""
        idx_dir = _resolve_idx_dir(project_id)
        if idx_dir is None:
            return False
        marker_path = idx_dir / _BUILD_SUCCESS_FILENAME
        if not marker_path.exists():
            return False
        try:
            marker_path.unlink()
            return True
        except Exception:
            logger.debug(
                "Failed to invalidate build success marker for %s",
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
            from prep.services.pipeline_checkpoint import CHECKPOINT_STAGES, create_checkpoint

            if stage.value not in CHECKPOINT_STAGES:
                return

            idx_dir = _resolve_idx_dir(run.project_id)
            if idx_dir is None:
                return

            cp_path = create_checkpoint(idx_dir, run.journal_run_id, stage.value)
            if cp_path:
                from prep.services.pipeline_journal import journal

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

        # Reset barrier: block per-stage backup restore during the post-reset
        # window. Matches the selfheal_group check so no resurrection path can
        # bypass the barrier.
        if reset_barrier_active(run.project_id):
            if pfl:
                pfl.log(
                    stage.value,
                    "Backup restore skipped (reset barrier active)",
                )
            return False

        try:
            from prep.services.branch_backup_manager import (
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
        if os.environ.get("PREP_SELFHEAL", "1") == "0":
            return {"disabled": True, "resurrected": 0}

        # Force rebuild: skip selfheal
        if force_from_start:
            return {"skipped_force_rebuild": True, "resurrected": 0}

        # Reset barrier: Reset All / Rebuild set this so selfheal cannot
        # manufacture stub manifests from orphan outputs or backup sources
        # until a genuine finalize run clears it. Without the barrier, a
        # trace_epistemic.jsonl left over from an aborted prior run would
        # be "resurrected" with a fake manifest, and deep reasoning stages
        # would skip enrichment and consume the stale data.
        if reset_barrier_active(project_id):
            if pfl:
                pfl.selfheal(
                    "barrier_active",
                    "Selfheal skipped: reset barrier active — awaiting genuine finalize",
                    {"stages": [s.value for s in stages]},
                )
            return {"skipped_reset_barrier": True, "resurrected": 0}

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
            from prep.services.branch_backup_manager import read_branch_state, SNAPSHOTS_DIR
            state = read_branch_state(idx_dir)
            branch = state.get("branch")
            if branch:
                from prep.services.branch_backup_manager import _sanitize_branch_name
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
                    # Do NOT resurrect when the output file belongs to a
                    # stage that was pending in the most recent interrupted
                    # run — it's the user's paused work, not truly orphan.
                    # Writing a stub here falsely claims the stage is
                    # complete; resume-point detection then skips it and
                    # downstream stages run on partial input.
                    from prep.services.pipeline_metadata import (
                        is_stage_pending_in_interrupted_run,
                    )
                    if is_stage_pending_in_interrupted_run(idx_dir, stage.value):
                        still_missing += 1
                        stage_detail["status"] = "skipped_interrupted_run"
                        stage_detail["reason"] = (
                            "output belongs to pending stage of interrupted run"
                        )
                        details.append(stage_detail)
                        if pfl:
                            pfl.selfheal(
                                "skip_orphan_interrupted",
                                f"Stage {stage.value}: orphan output is pending work "
                                f"from interrupted run — leaving manifest missing",
                                {"stage": stage.value, "source": "orphan_output"},
                            )
                        continue

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
            from prep.services.project_helpers import get_registry

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
                from prep.services.project_helpers import get_project_activity_status
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
            from prep.services.pipeline_journal import journal

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
            from prep.services.pipeline_journal import journal

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
            from prep.services.pipeline_journal import journal

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
            from prep.services.pipeline_journal import journal

            crashed = journal.recover_crashed_runs()
            set_crashed_runs(crashed)
            if crashed:
                logger.warning(
                    "Crash recovery: found %d crashed pipeline run(s)",
                    len(crashed),
                )
                for entry in crashed:
                    try:
                        from prep.services.pipeline_checkpoint import (
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
            from prep.services.project_helpers import get_registry
            from prep.services.settings_store import settings

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
                from prep.services.project_helpers import get_project_activity_status
                activity = get_project_activity_status(pid)
                if activity != "active":
                    continue
            except Exception:
                pass

            # Skip if any group is already active
            if is_run_active_fn(pid):
                continue

            # SIMPLIFIED RULE (per user request): paused is the default
            # state after server restart. Any group with partial state
            # surfaces as PAUSED until the user explicitly clicks Resume.
            # No auto-resume across restart — ever. Auto mode only
            # triggers fresh runs on cleanly-idle projects (no in-flight
            # state to inherit), never on incomplete ones.
            #
            # The user-pause marker is still tracked for diagnostics
            # (the marker payload records the original pause stage and
            # timestamp) and to drive a future "previously paused vs
            # crash-interrupted" UI distinction, but the hydration
            # decision itself is unconditional: partial state → PAUSED.
            for group, stages, _is_auto in groups:
                detected_resume = detect_resume_fn(pid, stages, True)
                user_pause_payload = RecoveryManager.read_user_pause_marker(pid, group)
                user_paused = user_pause_payload is not None

                # If the detector says every stage is complete, trust it —
                # the marker is stale (e.g. resume completed all remaining
                # stages but the marker clear failed). Clear the marker so
                # it doesn't keep producing ghost paused runs forever.
                if detected_resume >= len(stages):
                    if user_paused:
                        logger.info(
                            "Clearing stale user-pause marker for %s/%s — "
                            "resume detector reports group complete",
                            pid, group,
                        )
                        RecoveryManager.clear_user_pause_marker(pid, group)
                    continue

                # No marker, no partial state — fresh project for this group.
                if detected_resume == 0 and not user_paused:
                    continue

                # The user-pause marker is AUTHORITATIVE for the resume
                # index when it points to a stage the detector also
                # considers incomplete-or-earlier. The detector consults
                # manifest `finished_at` timestamps, which a stale
                # previous-run manifest reports as "complete" even when
                # the user paused mid-incremental-rerun of that same
                # stage. Without this, the user's paused stage 6 gets
                # reported as resume=7 by the detector — Resume silently
                # skips the stage they actually stopped on.
                #
                # Heuristic: marker wins when marker_index <= detected_resume
                # (paused at or before the detector's incomplete frontier).
                # If the marker says we got further than the detector
                # thinks, the marker is suspect — fall back to the
                # detector. If the marker is absent or names a stage no
                # longer in this group, fall back to the detector.
                stage_lookup = {s.value: i for i, s in enumerate(stages)}
                marker_index: Optional[int] = None
                if user_pause_payload:
                    marker_stage = user_pause_payload.get("stage")
                    if isinstance(marker_stage, str):
                        marker_index = stage_lookup.get(marker_stage)

                if marker_index is not None and marker_index <= detected_resume:
                    resume = marker_index
                else:
                    resume = detected_resume

                # Clamp to a valid stage index. resume==0 with marker means
                # the user paused before stage 0 wrote any output; pin the
                # paused state machine to stage 0 so Resume picks up there.
                resume = max(0, min(resume, len(stages) - 1))

                shutdown_was_clean = RecoveryManager.check_clean_shutdown_marker(pid)
                if (
                    user_paused
                    and marker_index is not None
                    and marker_index <= detected_resume
                    and marker_index != detected_resume
                ):
                    reason = (
                        f"user pause marker present (stage={stages[marker_index].value}, "
                        f"detector said resume={detected_resume} — marker wins because "
                        f"detector likely tripped on a stale prior-run manifest)"
                    )
                elif user_paused:
                    reason = "user pause marker present"
                elif not shutdown_was_clean:
                    reason = "no clean shutdown marker (interrupted run)"
                else:
                    reason = "partial state on disk (default-paused on restart)"

                sm = PipelineGroupStateMachine(
                    project_id=pid,
                    group=group,
                    stages=[s.value for s in stages],
                )
                sm.add_guard(default_guard)
                if not sm.transition(Event.START):
                    logger.warning(
                        "PAUSED hydration for %s/%s blocked at START — "
                        "guard refused (project may have toggled inactive)",
                        pid, group,
                    )
                    continue
                sm.current_stage_index = resume
                for i in range(resume):
                    sm.stage_results[stages[i].value] = "completed"
                sm.transition(Event.PAUSE)
                sm.transition(Event.STAGE_FLUSHED)
                register_run_fn(pid, group, sm)

                logger.info(
                    "Hydrated PAUSED state for %s/%s at stage %d/%d (%s) "
                    "— %s. User must click Resume to continue.",
                    pid,
                    group,
                    resume,
                    len(stages),
                    stages[resume].value,
                    reason,
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
            from prep.services.project_helpers import get_registry

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
                from prep.services.project_helpers import get_project_activity_status
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
                from prep.services.pipeline_metadata import (
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

            # Step 3: Auto-trigger deep enrichment if manifests are stale.
            #
            # Phase 128: Journal-authority gate (highest precedence). The
            # pipeline_journal records every run with status atomically
            # inside a SQLite transaction. If the journal says a
            # deep_enrichment run completed and its finished_at post-dates
            # the structural manifest mtime, the data is provably healthy
            # — stronger than any disk marker or mtime heuristic. This
            # gate runs BEFORE all marker / mtime paths so the cheapest,
            # strongest signal wins.
            try:
                from prep.services.pipeline_journal import journal as _journal
                store_for_journal_check = ManifestStore(idx_dir)
                if store_for_journal_check.provenance_exists(StageId.STRUCTURAL):
                    struct_mtime_for_journal = store_for_journal_check.provenance_mtime(
                        StageId.STRUCTURAL
                    )
                    if _journal.has_recent_completed_run(
                        pid, "deep_enrichment", since_mtime=struct_mtime_for_journal,
                    ):
                        logger.info(
                            "Phase 128: Journal records completed deep_enrichment "
                            "run for %s post-dating structural — data healthy, "
                            "skipping auto-recovery",
                            pid,
                        )
                        if pfl:
                            pfl.selfheal(
                                "auto_recover",
                                "Skipped — journal proves recent completion",
                                {
                                    "project_id": pid,
                                    "structural_mtime": struct_mtime_for_journal,
                                },
                            )
                        continue
            except Exception:
                logger.debug(
                    "Phase 128: journal-authority check failed for %s",
                    pid, exc_info=True,
                )
                # Fall through to existing recovery logic

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

            # Phase 128: Build-success marker gate. Even without a clean-
            # shutdown marker (which only exists if the daemon got SIGTERM),
            # a build-success marker that post-dates the structural manifest
            # proves the on-disk data is healthy. This closes the
            # kill -9 / USB eject / sleep gap that otherwise leaves Phase 61B
            # spuriously triggering a full rebuild after every ungraceful
            # daemon termination.
            try:
                marker_mtime = RecoveryManager.build_success_marker_mtime(pid)
                if marker_mtime is not None:
                    store_for_marker_check = ManifestStore(idx_dir)
                    if store_for_marker_check.provenance_exists(StageId.STRUCTURAL):
                        struct_mtime = store_for_marker_check.provenance_mtime(
                            StageId.STRUCTURAL
                        )
                        if marker_mtime >= struct_mtime:
                            logger.info(
                                "Phase 128: Build-success marker for %s "
                                "post-dates structural — data healthy, "
                                "skipping deep enrichment auto-recovery",
                                pid,
                            )
                            if pfl:
                                pfl.selfheal(
                                    "auto_recover",
                                    "Skipped — build-success marker proves healthy data",
                                    {
                                        "project_id": pid,
                                        "marker_mtime": marker_mtime,
                                        "structural_mtime": struct_mtime,
                                    },
                                )
                            continue
            except Exception:
                logger.debug(
                    "Phase 128: build-success marker check failed for %s",
                    pid, exc_info=True,
                )
                # Fall through to existing recovery logic

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
                                "prep_version": "0.1.0",
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
                    # Phase 72: Touch manifests first and re-check.
                    #
                    # Phase 128: Touch source corrected from CATALOGUE to
                    # STRUCTURAL. The staleness comparison at line 1426 is
                    # against ``structural_mtime``. After a successful build
                    # STRUCTURAL is the newest manifest (touched at finalize),
                    # so touching deep stages forward to CATALOGUE leaves them
                    # still older than STRUCTURAL — the post-touch re-check
                    # always tripped, defeating the heal-in-place safety net.
                    # Touching to STRUCTURAL allows the re-check to pass when
                    # the data is genuinely fresh and only the ordering looks
                    # stale.
                    store.sync_downstream_mtimes(StageId.STRUCTURAL, list(DEEP_ENRICHMENT_STAGES))

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

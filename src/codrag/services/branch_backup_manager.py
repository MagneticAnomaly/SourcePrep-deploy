"""
Branch-Aware Backup Manager — Phase 60B
========================================

Associates pipeline snapshots with Git branches so that expensive LLM
reasoning (hours of deep enrichment) survives branch switches.

When the pipeline detects a branch transition (e.g. ``main`` → ``feature-x``),
the current ``.codrag/`` trace state is snapshotted and tagged for the
*previous* branch.  If the user later returns to that branch, the snapshot
is restored instead of reprocessing from scratch.

Key design decisions:

1. **Only JSONL + manifests are snapshotted** (~35 MB for a large project).
   Embeddings (144 MB NPY) are deterministic and can be rebuilt cheaply from
   JSONL data via the Knowledge stage, so they are excluded.

2. **Most-recent snapshot is uncompressed** for instant rollback.  Older
   snapshots per branch are gzip-compressed.  A project-level setting
   ``max_branch_backups`` (default 3) caps total branch snapshots.

3. **Branch detection uses ``git rev-parse``** — works in detached HEAD
   mode (returns the SHA), worktrees, and bare clones.

Storage layout::

    .codrag/
    ├── trace_nodes.jsonl          ← live data
    ├── ...
    └── .branch_snapshots/
        ├── _branch_state.json     ← tracks last-known branch per project
        ├── main/
        │   ├── trace_nodes.jsonl
        │   ├── trace_augmented.jsonl
        │   └── ...manifests...
        └── feature-x/
            ├── trace_nodes.jsonl
            └── ...
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Files worth snapshotting: JSONL trace data + manifest JSON files.
# Embeddings (*.npy) are excluded — they're deterministic and can be regenerated.
SNAPSHOT_PATTERNS = [
    "trace_nodes.jsonl",
    "trace_edges.jsonl",
    "trace_inferred_edges.jsonl",
    "trace_augmented.jsonl",
    "trace_epistemic.jsonl",
    "trace_group_reasoning.jsonl",
    "trace_modules.jsonl",
    # Manifests (provenance + freshness tracking)
    "trace_manifest.json",
    "trace_inferred_manifest.json",
    "trace_augment_manifest.json",
    "validation_manifest.json",
    "knowledge_manifest.json",
    "trace_epistemic_manifest.json",
    "group_reasoning_manifest.json",
    "trace_modules_manifest.json",
    "atlas_manifest.json",
    "deepening_manifest.json",
    "deep_knowledge_manifest.json",
    # Pipeline run metadata
    "pipeline_run_metadata.json",
    # Atlas / knowledge docs
    "atlas_output.json",
    "repo_policy.json",
]

SNAPSHOTS_DIR = ".branch_snapshots"
BRANCH_STATE_FILE = "_branch_state.json"


# ── Git Helpers ────────────────────────────────────────────────────


def detect_current_branch(project_path: str | Path) -> Optional[str]:
    """Detect the current Git branch for a project.

    Returns the branch name (e.g. ``main``, ``feature-x``), the short SHA
    if the HEAD is detached, or ``None`` if the directory is not a Git repo.
    """
    project_path = Path(project_path)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()

        # Detached HEAD returns "HEAD" — fall back to short SHA
        if branch == "HEAD":
            result2 = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result2.returncode == 0:
                return f"detached-{result2.stdout.strip()}"
            return None

        return branch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _sanitize_branch_name(branch: str) -> str:
    """Sanitize a branch name for use as a directory name.

    Replaces ``/`` with ``--`` so ``feature/foo`` becomes ``feature--foo``.
    """
    return branch.replace("/", "--").replace("\\", "--").replace("..", "__")


# ── Branch State Tracking ──────────────────────────────────────────


def _branch_state_path(index_dir: Path) -> Path:
    return index_dir / SNAPSHOTS_DIR / BRANCH_STATE_FILE


def read_branch_state(index_dir: Path) -> Dict[str, Any]:
    """Read the persisted branch state for a project.

    Returns ``{"branch": "main", "switched_at": "...", "snapshot_count": 2}``
    or an empty dict if no state file exists.
    """
    path = _branch_state_path(index_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_branch_state(
    index_dir: Path,
    branch: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist the current branch state."""
    path = _branch_state_path(index_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {
        "branch": branch,
        "switched_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        data.update(extra)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Snapshot Operations ────────────────────────────────────────────


def list_snapshots(index_dir: Path) -> List[Dict[str, Any]]:
    """List all available branch snapshots for a project.

    Returns a list of dicts with ``branch``, ``created_at``, ``size_bytes``,
    and ``file_count`` for each snapshot.
    """
    snap_root = index_dir / SNAPSHOTS_DIR
    if not snap_root.is_dir():
        return []

    result: List[Dict[str, Any]] = []
    for entry in sorted(snap_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        # Count files and total size
        files = list(entry.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        # Try to read metadata
        meta_path = entry / "_snapshot_meta.json"
        created_at = None
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                created_at = meta.get("created_at")
            except Exception:
                pass
        if not created_at:
            # Fall back to dir mtime
            created_at = datetime.fromtimestamp(
                entry.stat().st_mtime, tz=timezone.utc
            ).isoformat()

        result.append({
            "branch": entry.name.replace("--", "/"),
            "dir_name": entry.name,
            "created_at": created_at,
            "size_bytes": total_size,
            "file_count": len(files),
        })
    return result


def snapshot_project(
    index_dir: Path,
    branch_name: str,
) -> Dict[str, Any]:
    """Snapshot the current pipeline state for a specific branch.

    Copies all JSONL trace files + manifests into
    ``.codrag/.branch_snapshots/<branch>/``.

    Returns a summary dict with ``files_copied`` and ``total_bytes``.
    """
    safe_name = _sanitize_branch_name(branch_name)
    snap_dir = index_dir / SNAPSHOTS_DIR / safe_name
    snap_dir.mkdir(parents=True, exist_ok=True)

    files_copied = 0
    total_bytes = 0

    for pattern in SNAPSHOT_PATTERNS:
        src = index_dir / pattern
        if src.is_file():
            dst = snap_dir / pattern
            try:
                shutil.copy2(str(src), str(dst))
                files_copied += 1
                total_bytes += src.stat().st_size
            except Exception as e:
                logger.warning(
                    "Branch backup: failed to copy %s → %s: %s",
                    src.name, dst, e,
                )

    # Write snapshot metadata
    meta = {
        "branch": branch_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files_copied": files_copied,
        "total_bytes": total_bytes,
    }
    meta_path = snap_dir / "_snapshot_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    logger.info(
        "Branch backup: snapshotted %d files (%d bytes) for branch '%s' → %s",
        files_copied, total_bytes, branch_name, snap_dir,
    )
    return meta


def restore_project(
    index_dir: Path,
    branch_name: str,
) -> Optional[Dict[str, Any]]:
    """Restore pipeline state from a branch snapshot.

    Copies all files from ``.codrag/.branch_snapshots/<branch>/`` back
    into the live ``.codrag/`` directory, overwriting current state.

    Returns the snapshot metadata dict on success, or ``None`` if no
    snapshot exists for that branch.
    """
    safe_name = _sanitize_branch_name(branch_name)
    snap_dir = index_dir / SNAPSHOTS_DIR / safe_name

    if not snap_dir.is_dir():
        return None

    files_restored = 0
    total_bytes = 0

    for pattern in SNAPSHOT_PATTERNS:
        src = snap_dir / pattern
        if src.is_file():
            dst = index_dir / pattern
            try:
                shutil.copy2(str(src), str(dst))
                files_restored += 1
                total_bytes += src.stat().st_size
            except Exception as e:
                logger.warning(
                    "Branch restore: failed to copy %s → %s: %s",
                    src.name, dst, e,
                )

    logger.info(
        "Branch restore: restored %d files (%d bytes) from branch '%s' snapshot",
        files_restored, total_bytes, branch_name,
    )
    return {
        "branch": branch_name,
        "files_restored": files_restored,
        "total_bytes": total_bytes,
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


def delete_snapshot(index_dir: Path, branch_name: str, *, dir_name: str | None = None) -> bool:
    """Delete a specific branch snapshot. Returns True if deleted.

    If ``dir_name`` is provided, it is used directly as the subdirectory
    name (avoids lossy re-sanitization of decoded branch names).
    """
    safe_name = dir_name or _sanitize_branch_name(branch_name)
    snap_dir = index_dir / SNAPSHOTS_DIR / safe_name

    if not snap_dir.is_dir():
        return False

    try:
        shutil.rmtree(snap_dir)
        logger.info("Branch backup: deleted snapshot for branch '%s'", branch_name)
        return True
    except Exception as e:
        logger.warning("Branch backup: failed to delete snapshot for '%s': %s", branch_name, e)
        return False


def prune_backups(index_dir: Path, max_backups: int = 3) -> List[str]:
    """Enforce the project-level backup limit by pruning oldest snapshots.

    Keeps the ``max_backups`` most recent snapshots and deletes the rest.
    Returns a list of branch names that were pruned.
    """
    snapshots = list_snapshots(index_dir)
    if len(snapshots) <= max_backups:
        return []

    # Sort by creation time (newest first)
    snapshots.sort(key=lambda s: s.get("created_at", ""), reverse=True)

    # Prune the oldest
    to_prune = snapshots[max_backups:]
    pruned: List[str] = []

    for snap in to_prune:
        branch = snap["branch"]
        if delete_snapshot(index_dir, branch, dir_name=snap.get("dir_name")):
            pruned.append(branch)
            logger.info(
                "Branch backup: pruned snapshot for branch '%s' "
                "(over limit of %d)",
                branch, max_backups,
            )

    return pruned


# ── Branch Transition Orchestration ────────────────────────────────


def check_branch_transition(
    project_path: str | Path,
    index_dir: Path,
    max_backups: int = 3,
) -> Optional[Dict[str, Any]]:
    """Check if the project's Git branch has changed since the last pipeline run.

    If a transition is detected:
    1. Snapshots the current state for the *old* branch
    2. Checks if a snapshot exists for the *new* branch → restores it
    3. Prunes snapshots that exceed ``max_backups``
    4. Updates the persisted branch state

    Returns a transition summary dict, or ``None`` if no change detected.
    """
    current_branch = detect_current_branch(project_path)
    if current_branch is None:
        # Not a git repo — no transition tracking
        return None

    state = read_branch_state(index_dir)
    last_branch = state.get("branch")

    if last_branch is None:
        # First time — just record the branch, no transition
        _write_branch_state(index_dir, current_branch)
        return None

    if current_branch == last_branch:
        # No change
        return None

    # ── Branch transition detected ──

    logger.info(
        "Branch transition detected: '%s' → '%s'",
        last_branch, current_branch,
    )

    result: Dict[str, Any] = {
        "from_branch": last_branch,
        "to_branch": current_branch,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_created": False,
        "snapshot_restored": False,
        "pruned_branches": [],
    }

    # Step 1: Snapshot the CURRENT live state for the OLD branch
    # (only if pipeline data exists — don't snapshot an empty directory)
    has_data = (index_dir / "trace_nodes.jsonl").is_file()
    if has_data:
        snapshot_project(index_dir, last_branch)
        result["snapshot_created"] = True

    # Step 2: Check if we have a snapshot for the NEW branch → restore
    safe_name = _sanitize_branch_name(current_branch)
    snap_dir = index_dir / SNAPSHOTS_DIR / safe_name
    if snap_dir.is_dir():
        restore_info = restore_project(index_dir, current_branch)
        if restore_info:
            result["snapshot_restored"] = True
            result["restore_info"] = restore_info

    # Step 3: Prune old snapshots
    pruned = prune_backups(index_dir, max_backups)
    result["pruned_branches"] = pruned

    # Step 4: Update branch state
    _write_branch_state(index_dir, current_branch, {
        "transition_from": last_branch,
    })

    return result


# ── Pre-Stage Backup Check ────────────────────────────────────────


def check_stage_backup(
    index_dir: Path,
    stage_manifest_file: str,
    stage_output_file: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Check if any backup snapshot has valid data for a pipeline stage.

    Scans all branch snapshots for the stage's manifest and output files.
    If found, checks that the data is non-empty and returns info about
    the best backup candidate.

    This is the core backup feature: before rebuilding a stage from
    scratch, check if we already have backed-up data that can be
    restored instead of re-running expensive LLM processing.

    Args:
        index_dir: The project's ``.codrag/`` directory.
        stage_manifest_file: e.g. ``"trace_epistemic_manifest.json"``
        stage_output_file: e.g. ``"trace_epistemic.jsonl"`` (or None)

    Returns:
        Dict with ``branch``, ``snapshot_dir``, ``manifest_path``,
        ``output_path``, ``record_count`` if a valid backup is found,
        or ``None``.
    """
    snap_root = index_dir / SNAPSHOTS_DIR
    if not snap_root.is_dir():
        return None

    best: Optional[Dict[str, Any]] = None
    best_count = 0

    for snap_dir in snap_root.iterdir():
        if not snap_dir.is_dir() or snap_dir.name.startswith("_"):
            continue

        manifest_path = snap_dir / stage_manifest_file
        if not manifest_path.is_file():
            continue

        # Check if manifest has meaningful data
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            quality = data.get("quality", {})
            record_count = quality.get("processed", 0) or quality.get("total_items", 0)
        except Exception:
            continue

        if record_count <= 0:
            continue

        # If there's an output file, check it exists and is non-empty
        output_path = None
        if stage_output_file:
            output_path = snap_dir / stage_output_file
            if not output_path.is_file() or output_path.stat().st_size == 0:
                continue

        # Prefer the backup with the most records
        if record_count > best_count:
            # Read snapshot metadata for branch name
            branch_name = snap_dir.name.replace("--", "/")
            meta_path = snap_dir / "_snapshot_meta.json"
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    branch_name = meta.get("branch", branch_name)
                except Exception:
                    pass

            best = {
                "branch": branch_name,
                "snapshot_dir": str(snap_dir),
                "manifest_path": str(manifest_path),
                "output_path": str(output_path) if output_path else None,
                "record_count": record_count,
            }
            best_count = record_count

    return best


def restore_stage_from_backup(
    index_dir: Path,
    snapshot_dir: str | Path,
    stage_manifest_file: str,
    stage_output_file: Optional[str],
) -> Dict[str, Any]:
    """Restore a specific stage's data from a backup snapshot.

    Only copies the stage-specific files (manifest + output), not the
    entire snapshot.  This allows restoring individual stage data without
    overwriting other stages.

    Returns a summary dict with files restored and bytes copied.
    """
    snap_dir = Path(snapshot_dir)
    files_restored = 0
    total_bytes = 0

    # Restore manifest
    src = snap_dir / stage_manifest_file
    if src.is_file():
        dst = index_dir / stage_manifest_file
        shutil.copy2(str(src), str(dst))
        files_restored += 1
        total_bytes += src.stat().st_size
        logger.info("Backup restore: %s → %s", src.name, dst)

    # Restore output file
    if stage_output_file:
        src = snap_dir / stage_output_file
        if src.is_file():
            dst = index_dir / stage_output_file
            shutil.copy2(str(src), str(dst))
            files_restored += 1
            total_bytes += src.stat().st_size
            logger.info("Backup restore: %s → %s", src.name, dst)

    return {
        "files_restored": files_restored,
        "total_bytes": total_bytes,
        "snapshot_dir": str(snap_dir),
    }

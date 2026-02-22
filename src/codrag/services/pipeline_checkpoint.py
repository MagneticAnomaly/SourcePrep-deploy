"""
CoDRAG Pipeline Checkpoint — Phase 25 (Crash Protection)
=========================================================

Creates and restores backup snapshots of trace data files before
potentially destructive pipeline stages.

**Design:**
  - Before stages that *modify* existing overlay files (e.g. deepening
    re-writes ``trace_epistemic.jsonl``), we copy critical files to a
    timestamped checkpoint directory.
  - On crash recovery, if the live file is corrupt, we restore from
    the checkpoint.
  - Checkpoints are cleaned up after a run completes successfully.

**Checkpoint directory layout:**
  ``<index_dir>/.checkpoints/<run_id>/``
    ├── trace_nodes.jsonl
    ├── trace_edges.jsonl
    ├── trace_augmented.jsonl
    ├── trace_epistemic.jsonl
    ├── trace_modules.jsonl
    └── trace_manifest.json

**Idempotency insight:**
  Most stages only *write* their own output file and read from the
  previous stage.  A crash mid-write leaves the previous stage intact.
  Checkpoints are only *necessary* for stages that modify files from
  earlier stages (deepening modifies epistemic data).

Usage::

    from codrag.services.pipeline_checkpoint import (
        create_checkpoint, restore_checkpoint, cleanup_checkpoint,
        verify_trace_files,
    )
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Files that constitute the trace graph state
TRACE_FILES = [
    "trace_manifest.json",
    "trace_nodes.jsonl",
    "trace_edges.jsonl",
    "trace_augmented.jsonl",
    "trace_augment_manifest.json",
    "trace_inferred_edges.jsonl",
    "trace_epistemic.jsonl",
    "trace_epistemic_manifest.json",
    "trace_modules.jsonl",
]

# Which stages produce which files (used to determine what to checkpoint)
STAGE_OUTPUTS: Dict[str, List[str]] = {
    "structural":     ["trace_nodes.jsonl", "trace_edges.jsonl", "trace_manifest.json"],
    "catalogue":      ["trace_augmented.jsonl", "trace_augment_manifest.json"],
    "validation":     ["trace_inferred_edges.jsonl"],
    "knowledge":      [],  # Knowledge index uses its own atomic swap
    "enrichment":     ["trace_epistemic.jsonl", "trace_epistemic_manifest.json"],
    "clustering":     ["trace_modules.jsonl"],
    "atlas":          [
        "atlas.json",
        "atlas_prev.json",
        "atlas_segments_manifest.json",
        "atlas_routing.json",
        "atlas_routing_embeddings.npy",
    ],
    "deepening":      ["trace_epistemic.jsonl", "trace_epistemic_manifest.json"],  # re-writes epistemic
    "deep_knowledge": [],  # Same atomic swap as knowledge
}

# Stages where a checkpoint is *recommended* because they modify files
# that were produced by an earlier stage
CHECKPOINT_STAGES = {"deepening", "enrichment", "clustering"}


def create_checkpoint(
    index_dir: Path,
    run_id: str,
    stage: str,
) -> Optional[str]:
    """Create a checkpoint of trace files before a stage runs.

    Returns the checkpoint directory path, or None if no checkpoint needed.
    """
    if stage not in CHECKPOINT_STAGES:
        return None

    checkpoint_dir = index_dir / ".checkpoints" / run_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for fname in TRACE_FILES:
        src = index_dir / fname
        if src.exists():
            try:
                shutil.copy2(src, checkpoint_dir / fname)
                copied += 1
            except Exception as e:
                logger.warning("Checkpoint: failed to copy %s: %s", fname, e)

    if copied > 0:
        logger.info(
            "Checkpoint: created %s (%d files) before stage '%s'",
            checkpoint_dir, copied, stage,
        )
        return str(checkpoint_dir)

    # Nothing to checkpoint
    try:
        checkpoint_dir.rmdir()
    except OSError:
        pass
    return None


def restore_checkpoint(checkpoint_path: str, index_dir: Path) -> int:
    """Restore trace files from a checkpoint directory.

    Returns the number of files restored.
    """
    cp = Path(checkpoint_path)
    if not cp.is_dir():
        logger.warning("Checkpoint: restore path does not exist: %s", checkpoint_path)
        return 0

    restored = 0
    for fname in TRACE_FILES:
        src = cp / fname
        if src.exists():
            dst = index_dir / fname
            try:
                shutil.copy2(src, dst)
                restored += 1
                logger.info("Checkpoint: restored %s", fname)
            except Exception as e:
                logger.error("Checkpoint: failed to restore %s: %s", fname, e)

    logger.info("Checkpoint: restored %d files from %s", restored, checkpoint_path)
    return restored


def cleanup_checkpoint(checkpoint_path: Optional[str]) -> bool:
    """Remove a checkpoint directory after a successful run."""
    if not checkpoint_path:
        return False
    cp = Path(checkpoint_path)
    if cp.is_dir():
        try:
            shutil.rmtree(cp)
            logger.debug("Checkpoint: cleaned up %s", checkpoint_path)
            return True
        except Exception as e:
            logger.warning("Checkpoint: cleanup failed for %s: %s", checkpoint_path, e)
    return False


def cleanup_all_checkpoints(index_dir: Path) -> int:
    """Remove all checkpoint directories for a project."""
    cp_root = index_dir / ".checkpoints"
    if not cp_root.is_dir():
        return 0
    count = 0
    try:
        shutil.rmtree(cp_root)
        count = 1
    except Exception as e:
        logger.warning("Checkpoint: cleanup_all failed: %s", e)
    return count


def verify_trace_files(index_dir: Path) -> Tuple[bool, List[str]]:
    """Check trace files for corruption (invalid JSON/JSONL).

    Returns (all_valid, list_of_corrupt_filenames).
    """
    corrupt: List[str] = []

    for fname in TRACE_FILES:
        fpath = index_dir / fname
        if not fpath.exists():
            continue  # Missing files are OK (stage hasn't run yet)

        try:
            if fname.endswith(".jsonl"):
                _verify_jsonl(fpath)
            elif fname.endswith(".json"):
                _verify_json(fpath)
        except Exception as e:
            corrupt.append(fname)
            logger.warning("Corrupt trace file detected: %s — %s", fname, e)

    return (len(corrupt) == 0, corrupt)


def _verify_jsonl(path: Path) -> None:
    """Verify a JSONL file: every line must be valid JSON."""
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            json.loads(line)  # Raises on invalid JSON


def _verify_json(path: Path) -> None:
    """Verify a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        json.load(f)


def auto_heal(
    index_dir: Path,
    checkpoint_path: Optional[str],
) -> Dict[str, str]:
    """Attempt to auto-heal corrupt trace files from a checkpoint.

    Returns a dict of {filename: "healed"|"still_corrupt"|"no_backup"}.
    """
    valid, corrupt = verify_trace_files(index_dir)
    if valid:
        return {}

    results: Dict[str, str] = {}
    cp = Path(checkpoint_path) if checkpoint_path else None

    for fname in corrupt:
        if cp and (cp / fname).exists():
            try:
                shutil.copy2(cp / fname, index_dir / fname)
                # Re-verify
                fpath = index_dir / fname
                if fname.endswith(".jsonl"):
                    _verify_jsonl(fpath)
                else:
                    _verify_json(fpath)
                results[fname] = "healed"
                logger.info("Auto-heal: restored %s from checkpoint", fname)
            except Exception:
                results[fname] = "still_corrupt"
                logger.error("Auto-heal: failed to restore %s", fname)
        else:
            results[fname] = "no_backup"
            logger.warning("Auto-heal: no backup available for %s", fname)

    return results

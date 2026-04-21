"""
Pipeline Integrity Guard — Phase 60A
======================================

Detects and logs data loss during pipeline stage execution.

**How it works:**
  Before a stage runs, we snapshot the current state of its output file
  (record count, file size, last modified).  After the stage completes,
  we compare the new state against the snapshot.  If the new data is
  dramatically smaller — e.g., 47,781 records replaced by 0 — we log
  a WARNING with full details.

**Design principle: observe, don't block.**
  This is a debugging / telemetry tool.  It never blocks pipeline
  execution.  All comparisons are logged to both the standard logger
  (DEBUG/INFO/WARNING level) and the pipeline file logger for post-hoc
  analysis.

**Key metrics logged per stage:**
  - Record count (before vs after)
  - File size in bytes (before vs after)
  - Change ratio (new / old)
  - Change direction: GREW, SHRANK, UNCHANGED, NEW, FIRST_RUN
  - Timestamp of pre-flight snapshot and post-flight check

Usage::

    from prep.services.pipeline_integrity import integrity_guard

    # Before stage runs:
    integrity_guard.snapshot_before_stage(project_id, stage_id, index_dir)

    # After stage completes:
    verdict = integrity_guard.check_after_stage(project_id, stage_id, index_dir)
    # verdict.level is "ok", "grew", "shrank", "warning", "critical"
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Stage ↔ Output file mapping ──────────────────────────────────
# Which files each stage writes.  This is the canonical list of what
# we monitor.  Matches STAGE_OUTPUT_FILE from stages.py but includes
# extra data files (knowledge_documents.json, embedding .npy files).

STAGE_DATA_FILES: Dict[str, list[str]] = {
    "structural":      ["trace_nodes.jsonl", "trace_edges.jsonl", "trace_manifest.json"],
    "inferred_edges":  ["trace_inferred_edges.jsonl"],
    "catalogue":       ["trace_augmented.jsonl"],
    "validation":      [],  # Rust validation modifies edges in-place
    "knowledge":       ["knowledge_documents.json", "knowledge_embeddings.npy"],
    "enrichment":      ["trace_epistemic.jsonl"],
    "group_reasoning": ["trace_group_reasoning.jsonl"],
    "clustering":      ["trace_modules.jsonl"],
    "atlas":           ["atlas.json"],
    "deepening":       ["trace_epistemic.jsonl"],  # overwrites enrichment output
    "deep_knowledge":  ["knowledge_documents.json", "knowledge_embeddings.npy"],
}

# Thresholds for data loss severity classification
_CRITICAL_THRESHOLD = 0.10   # New data is <10% of existing → CRITICAL
_WARNING_THRESHOLD = 0.50    # New data is <50% of existing → WARNING
_GROWTH_THRESHOLD = 2.0      # New data is >200% of existing → unusual growth (INFO)


@dataclass
class FileSnapshot:
    """Snapshot of a single file's state at a point in time."""
    path: str
    exists: bool
    size_bytes: int = 0
    record_count: int = 0  # For JSONL files only
    modified_at: float = 0.0
    taken_at: float = field(default_factory=time.time)


@dataclass
class StageSnapshot:
    """Pre-flight snapshot of all output files for a stage."""
    project_id: str
    stage_id: str
    files: Dict[str, FileSnapshot] = field(default_factory=dict)
    taken_at: float = field(default_factory=time.time)
    is_incremental: bool = False  # Whether this is an incremental run


@dataclass
class IntegrityVerdict:
    """Result of comparing pre-flight vs post-flight state."""
    project_id: str
    stage_id: str
    level: str  # "ok", "grew", "shrank", "warning", "critical", "first_run", "no_output"
    details: Dict[str, Any] = field(default_factory=dict)
    file_verdicts: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_log_dict(self) -> Dict[str, Any]:
        """Flatten to a dict suitable for structured logging."""
        d = {
            "project_id": self.project_id,
            "stage": self.stage_id,
            "level": self.level,
        }
        d.update(self.details)
        if self.file_verdicts:
            d["files"] = self.file_verdicts
        return d


class IntegrityGuard:
    """Observes pipeline data files before/after stage execution.

    Non-blocking: never prevents pipeline execution.  Logs all
    observations for debugging and telemetry.
    """

    def __init__(self) -> None:
        # In-flight snapshots keyed by (project_id, stage_id)
        self._snapshots: Dict[tuple[str, str], StageSnapshot] = {}

    def snapshot_before_stage(
        self,
        project_id: str,
        stage_id: str,
        index_dir: Path,
        *,
        is_incremental: bool = False,
    ) -> StageSnapshot:
        """Take a pre-flight snapshot of the stage's output files.

        Call this BEFORE the stage worker starts.  Records file sizes,
        record counts, and modification times.
        """
        data_files = STAGE_DATA_FILES.get(stage_id, [])
        snapshot = StageSnapshot(
            project_id=project_id,
            stage_id=stage_id,
            is_incremental=is_incremental,
        )

        for fname in data_files:
            fpath = index_dir / fname
            fs = self._snapshot_file(fpath)
            snapshot.files[fname] = fs

        self._snapshots[(project_id, stage_id)] = snapshot

        # Log the pre-flight state at DEBUG level (verbose)
        file_summary = {}
        for fname, fs in snapshot.files.items():
            if fs.exists:
                file_summary[fname] = {
                    "size": _fmt_size(fs.size_bytes),
                    "records": fs.record_count,
                    "modified": time.strftime(
                        "%Y-%m-%dT%H:%M:%S",
                        time.localtime(fs.modified_at),
                    ),
                }
            else:
                file_summary[fname] = {"exists": False}

        logger.info(
            "IntegrityGuard PRE-FLIGHT [%s/%s]%s: %s",
            project_id[:8], stage_id,
            " (incremental)" if is_incremental else "",
            json.dumps(file_summary, separators=(",", ":")),
        )

        return snapshot

    def check_after_stage(
        self,
        project_id: str,
        stage_id: str,
        index_dir: Path,
    ) -> IntegrityVerdict:
        """Compare current state against the pre-flight snapshot.

        Call this AFTER the stage worker completes.  Compares file sizes
        and record counts to detect data loss, suspicious shrinkage, or
        unexpected growth.
        """
        key = (project_id, stage_id)
        pre = self._snapshots.pop(key, None)

        data_files = STAGE_DATA_FILES.get(stage_id, [])
        if not data_files:
            return IntegrityVerdict(
                project_id=project_id,
                stage_id=stage_id,
                level="no_output",
                details={"reason": "stage has no tracked output files"},
            )

        worst_level = "ok"
        file_verdicts: Dict[str, Dict[str, Any]] = {}

        for fname in data_files:
            fpath = index_dir / fname
            post = self._snapshot_file(fpath)

            # Get pre-flight state (or synthesize an "absent" one)
            pre_file = pre.files.get(fname) if pre else None
            if pre_file is None:
                pre_file = FileSnapshot(path=str(fpath), exists=False)

            verdict = self._compare_file(fname, pre_file, post, stage_id)
            file_verdicts[fname] = verdict

            # Track worst severity
            vlevel = verdict.get("level", "ok")
            if _severity(vlevel) > _severity(worst_level):
                worst_level = vlevel

        result = IntegrityVerdict(
            project_id=project_id,
            stage_id=stage_id,
            level=worst_level,
            file_verdicts=file_verdicts,
            details={
                "is_incremental": pre.is_incremental if pre else False,
                "pre_flight_at": pre.taken_at if pre else None,
                "post_flight_at": time.time(),
            },
        )

        # Log at appropriate level based on worst severity
        log_dict = result.to_log_dict()
        if worst_level == "critical":
            logger.warning(
                "IntegrityGuard CRITICAL DATA LOSS [%s/%s]: %s",
                project_id[:8], stage_id,
                json.dumps(log_dict, separators=(",", ":")),
            )
        elif worst_level == "warning":
            logger.warning(
                "IntegrityGuard WARNING [%s/%s]: data shrank significantly — %s",
                project_id[:8], stage_id,
                json.dumps(log_dict, separators=(",", ":")),
            )
        elif worst_level == "grew":
            logger.info(
                "IntegrityGuard POST-FLIGHT [%s/%s]: data grew — %s",
                project_id[:8], stage_id,
                json.dumps(log_dict, separators=(",", ":")),
            )
        else:
            logger.info(
                "IntegrityGuard POST-FLIGHT [%s/%s]: %s — %s",
                project_id[:8], stage_id, worst_level,
                json.dumps(log_dict, separators=(",", ":")),
            )

        return result

    # ── Phase 70B: Write guard (detection + rollback) ──────────────
    #
    # DESIGN NOTE: This guard runs AFTER the stage has written output.
    # It detects data loss and can trigger checkpoint restore (for LLM
    # stages) or allow through (for deterministic stages). True write
    # prevention happens via Phase 25 checkpoints, which back up files
    # BEFORE destructive stages run. This guard catches what checkpoints
    # miss — stages that weren't expected to be destructive but produced
    # fewer records than existed.

    def should_block_stage_completion(
        self,
        project_id: str,
        stage_id: str,
        post_files: Dict[str, "FileSnapshot"],
    ) -> tuple[bool, str]:
        """Check if a stage's output would destroy existing data.

        Compares post-stage file state against the pre-flight snapshot.
        Returns (should_block, reason). If should_block is True, the
        pipeline should NOT advance — the stage's output would reduce
        the data below what already existed.

        The pipeline should only grow the graph, never shrink it.
        """
        key = (project_id, stage_id)
        pre = self._snapshots.get(key)
        if pre is None:
            return False, "no pre-flight snapshot"

        for fname, pre_fs in pre.files.items():
            if not pre_fs.exists or pre_fs.record_count == 0:
                continue  # first run or empty file — nothing to protect

            post_fs = post_files.get(fname)
            if post_fs is None or not post_fs.exists:
                return True, (
                    f"Stage {stage_id} would delete {fname} "
                    f"({pre_fs.record_count} records existed)"
                )

            if post_fs.record_count < pre_fs.record_count:
                return True, (
                    f"Stage {stage_id} would shrink {fname} from "
                    f"{pre_fs.record_count} to {post_fs.record_count} records "
                    f"({post_fs.record_count / pre_fs.record_count:.0%} of original)"
                )

        return False, "ok"

    # ── Phase 70B: Input freshness check ───────────────────────────

    def check_stage_freshness(
        self,
        index_dir: Path,
        input_files: list[str],
        output_files: list[str],
    ) -> tuple[bool, str]:
        """Check if a stage's outputs are already up-to-date.

        Compares modification times of input files vs output files.
        If ALL output files exist and are NEWER than ALL input files,
        the stage is already current and can be skipped.

        Returns (should_skip, reason).
        """
        if not input_files:
            return False, "no pipeline inputs — stage must run"

        newest_input_mtime = 0.0
        for fname in input_files:
            fpath = index_dir / fname
            if not fpath.exists():
                return False, f"input {fname} missing — stage must run"
            newest_input_mtime = max(newest_input_mtime, fpath.stat().st_mtime)

        for fname in output_files:
            fpath = index_dir / fname
            if not fpath.exists():
                return False, f"output {fname} missing — stage must run"
            if fpath.stat().st_mtime < newest_input_mtime:
                return False, f"output {fname} is older than inputs — stage must run"

        return True, "all outputs are newer than inputs — already current"

    # ── Internal helpers ─────────────────────────────────────────

    @staticmethod
    def _snapshot_file(fpath: Path) -> FileSnapshot:
        """Capture the current state of a single file."""
        fs = FileSnapshot(path=str(fpath), exists=fpath.exists())
        if not fs.exists:
            return fs

        try:
            stat = fpath.stat()
            fs.size_bytes = stat.st_size
            fs.modified_at = stat.st_mtime
        except OSError:
            return fs

        # Count records for JSONL files
        if fpath.suffix == ".jsonl" and fs.size_bytes > 0:
            try:
                fs.record_count = _count_jsonl_records(fpath)
            except Exception:
                logger.debug(
                    "IntegrityGuard: failed to count records in %s",
                    fpath.name, exc_info=True,
                )

        # For JSON files that are arrays (like knowledge_documents.json),
        # try to count top-level array items
        elif fpath.suffix == ".json" and fs.size_bytes > 0:
            try:
                fs.record_count = _count_json_items(fpath)
            except Exception:
                pass

        return fs

    @staticmethod
    def _compare_file(
        fname: str,
        pre: FileSnapshot,
        post: FileSnapshot,
        stage_id: str,
    ) -> Dict[str, Any]:
        """Compare before vs after for a single file."""
        verdict: Dict[str, Any] = {
            "pre_exists": pre.exists,
            "post_exists": post.exists,
            "pre_size": pre.size_bytes,
            "post_size": post.size_bytes,
            "pre_records": pre.record_count,
            "post_records": post.record_count,
        }

        # Case 1: File didn't exist before, now it does → first run
        if not pre.exists and post.exists:
            verdict["level"] = "first_run"
            verdict["direction"] = "NEW"
            verdict["summary"] = (
                f"Created {fname}: {post.record_count} records, "
                f"{_fmt_size(post.size_bytes)}"
            )
            return verdict

        # Case 2: File existed before, now it doesn't → deletion!
        if pre.exists and not post.exists:
            verdict["level"] = "critical"
            verdict["direction"] = "DELETED"
            verdict["summary"] = (
                f"DELETED {fname}! Had {pre.record_count} records "
                f"({_fmt_size(pre.size_bytes)})"
            )
            return verdict

        # Case 3: Neither exists → no output (stage has no effect)
        if not pre.exists and not post.exists:
            verdict["level"] = "ok"
            verdict["direction"] = "ABSENT"
            verdict["summary"] = f"{fname} not present (expected for this stage)"
            return verdict

        # Case 4: Both exist — compare sizes and record counts
        size_ratio = post.size_bytes / max(pre.size_bytes, 1)
        record_ratio = post.record_count / max(pre.record_count, 1)

        verdict["size_ratio"] = round(size_ratio, 3)
        verdict["record_ratio"] = round(record_ratio, 3)
        verdict["size_delta"] = post.size_bytes - pre.size_bytes
        verdict["record_delta"] = post.record_count - pre.record_count

        # Use record count if available, otherwise use file size
        ratio = record_ratio if pre.record_count > 0 else size_ratio

        if ratio < _CRITICAL_THRESHOLD:
            verdict["level"] = "critical"
            verdict["direction"] = "CATASTROPHIC_SHRINK"
            verdict["summary"] = (
                f"CRITICAL: {fname} shrank from {pre.record_count} to "
                f"{post.record_count} records ({_fmt_size(pre.size_bytes)} → "
                f"{_fmt_size(post.size_bytes)}). Ratio: {ratio:.2%}"
            )
        elif ratio < _WARNING_THRESHOLD:
            verdict["level"] = "warning"
            verdict["direction"] = "MAJOR_SHRINK"
            verdict["summary"] = (
                f"WARNING: {fname} shrank from {pre.record_count} to "
                f"{post.record_count} records ({ratio:.1%} of original)"
            )
        elif ratio > _GROWTH_THRESHOLD and pre.record_count > 100:
            # Unusual growth — might indicate a full re-run when incremental was expected
            verdict["level"] = "grew"
            verdict["direction"] = "UNEXPECTED_GROWTH"
            verdict["summary"] = (
                f"{fname} grew from {pre.record_count} to "
                f"{post.record_count} records ({ratio:.1%} of original)"
            )
        elif abs(post.record_count - pre.record_count) == 0 and pre.record_count > 0:
            verdict["level"] = "ok"
            verdict["direction"] = "UNCHANGED"
            verdict["summary"] = (
                f"{fname}: {post.record_count} records "
                f"({_fmt_size(post.size_bytes)}) — unchanged"
            )
        else:
            verdict["level"] = "ok"
            verdict["direction"] = "GREW" if record_ratio >= 1.0 else "SHRANK_SMALL"
            added = post.record_count - pre.record_count
            verdict["summary"] = (
                f"{fname}: {pre.record_count} → {post.record_count} records "
                f"({'+' if added >= 0 else ''}{added}), "
                f"{_fmt_size(pre.size_bytes)} → {_fmt_size(post.size_bytes)}"
            )

        return verdict


# ── Singleton ────────────────────────────────────────────────────

integrity_guard = IntegrityGuard()


# ── Utility functions ────────────────────────────────────────────

def _count_jsonl_records(fpath: Path) -> int:
    """Efficiently count non-empty lines in a JSONL file.

    Doesn't parse JSON — just counts lines.  Fast even for large files.
    """
    count = 0
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _count_json_items(fpath: Path) -> int:
    """Count top-level array items in a JSON file (like knowledge_documents.json).

    Uses a fast streaming approach: counts lines starting with '{'
    to avoid parsing the entire 28 MB file into memory.
    Falls back to json.load() for small files (<1 MB).
    Returns 0 if the file isn't a JSON array.
    """
    size = fpath.stat().st_size
    if size == 0:
        return 0

    # Quick check: is this a JSON array?
    with open(fpath, "rb") as f:
        first = f.read(1)
        if first != b"[":
            return 0

    # For small files, just parse
    if size < 1_000_000:  # < 1 MB
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return len(data) if isinstance(data, list) else 0

    # For large files, use fast streaming: count lines starting with '{'
    # This works for both compact JSON ([{...},{...}]) and pretty-printed.
    # In compact format, we count occurrences of '{"' which is the start
    # of each top-level object.
    count = 0
    with open(fpath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            count += chunk.count(b'{"id"')
    # Fallback: if no '{"id"' found, count '{"' patterns
    if count == 0:
        with open(fpath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                count += chunk.count(b'{"')
    return count


def _fmt_size(bytes_count: int) -> str:
    """Format byte count for human-readable logging."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    return f"{bytes_count / (1024 * 1024 * 1024):.1f} GB"


def _severity(level: str) -> int:
    """Severity ordering for comparison."""
    return {
        "no_output": 0,
        "ok": 1,
        "first_run": 1,
        "grew": 2,
        "shrank": 3,
        "warning": 4,
        "critical": 5,
    }.get(level, 1)

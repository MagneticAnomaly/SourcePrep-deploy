"""Tests for the pipeline write guard (Phase 70B)."""
import pytest
from pathlib import Path
from prep.services.pipeline_integrity import IntegrityGuard, FileSnapshot, StageSnapshot


def test_block_when_records_shrank():
    """Stage produced fewer records than existed — must block."""
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre

    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=50_000,
            record_count=50,
        )
    }

    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is True
    assert "800" in reason
    assert "50" in reason


def test_allow_when_records_grew():
    """Stage produced more records — allow."""
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre

    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=1_100_000,
            record_count=850,
        )
    }

    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is False


def test_allow_first_run():
    """No pre-flight data existed — always allow."""
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=False,
    )
    guard._snapshots[("test", "enrichment")] = pre

    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=50_000,
            record_count=50,
        )
    }

    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is False


def test_allow_equal_records():
    """Same record count (re-run with no changes) — allow."""
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre

    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=True,
            size_bytes=1_000_000,
            record_count=800,
        )
    }

    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is False


def test_block_when_output_deleted():
    """Stage deleted its output file — must block."""
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="enrichment")
    pre.files["trace_epistemic.jsonl"] = FileSnapshot(
        path="/tmp/trace_epistemic.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=800,
    )
    guard._snapshots[("test", "enrichment")] = pre

    post_files = {
        "trace_epistemic.jsonl": FileSnapshot(
            path="/tmp/trace_epistemic.jsonl",
            exists=False,
        )
    }

    blocked, reason = guard.should_block_stage_completion(
        "test", "enrichment", post_files
    )
    assert blocked is True
    assert "delete" in reason.lower()


def test_block_when_zero_records():
    """Stage produced 0 records when data existed — must block."""
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="catalogue")
    pre.files["trace_augmented.jsonl"] = FileSnapshot(
        path="/tmp/trace_augmented.jsonl",
        exists=True,
        size_bytes=5_000_000,
        record_count=5000,
    )
    guard._snapshots[("test", "catalogue")] = pre

    post_files = {
        "trace_augmented.jsonl": FileSnapshot(
            path="/tmp/trace_augmented.jsonl",
            exists=True,
            size_bytes=0,
            record_count=0,
        )
    }

    blocked, reason = guard.should_block_stage_completion(
        "test", "catalogue", post_files
    )
    assert blocked is True
    assert "5000" in reason
    assert "0" in reason


def test_phantom_restore_still_blocks_after_no_op_recovery():
    """Regression for the 2026-05-27 phantom-restore incident.

    When ``_attempt_write_guard_recovery`` calls ``restore_checkpoint`` and
    it returns N>0 (e.g. "RESTORED 10 files"), the orchestrator must re-
    snapshot the stage's data files and re-run ``should_block_stage_completion``.
    If the shrunken file was not part of the checkpoint set (a coverage gap
    in TRACE_FILES — exactly the original incident), the file remains
    shrunken on disk and the re-check still returns blocked=True.

    The orchestrator treats this "phantom restore" as a recovery failure and
    refuses to advance the stage, instead of accepting "10 files restored"
    as a misleading success.
    """
    guard = IntegrityGuard()

    # Pre-flight: 166 records in trace_group_reasoning.jsonl
    pre = StageSnapshot(project_id="test", stage_id="group_reasoning")
    pre.files["trace_group_reasoning.jsonl"] = FileSnapshot(
        path="/tmp/trace_group_reasoning.jsonl",
        exists=True,
        size_bytes=540_000,
        record_count=166,
    )
    guard._snapshots[("test", "group_reasoning")] = pre

    # Post-shrink: swarm hit wall-time cap, only 61 of 166 expected workers
    # produced output, file rewritten with 61 records.
    post_shrink = {
        "trace_group_reasoning.jsonl": FileSnapshot(
            path="/tmp/trace_group_reasoning.jsonl",
            exists=True,
            size_bytes=227_000,
            record_count=61,
        ),
    }
    blocked, reason = guard.should_block_stage_completion(
        "test", "group_reasoning", post_shrink,
    )
    assert blocked is True, "initial check must block on 166→61 shrinkage"
    assert "166" in reason and "61" in reason

    # Phantom restore: restore_checkpoint touched 10 other files in TRACE_FILES
    # but did NOT touch trace_group_reasoning.jsonl (the actual incident:
    # the file was not in TRACE_FILES at the time).  The file on disk is
    # still 61 records.  The orchestrator re-snapshots and re-checks.
    post_restore = {
        "trace_group_reasoning.jsonl": FileSnapshot(
            path="/tmp/trace_group_reasoning.jsonl",
            exists=True,
            size_bytes=227_000,
            record_count=61,  # unchanged by the no-op restore
        ),
    }
    still_blocked, post_restore_reason = guard.should_block_stage_completion(
        "test", "group_reasoning", post_restore,
    )
    assert still_blocked is True, (
        "After a phantom restore (target file unchanged), the integrity "
        "check must still return blocked=True so the orchestrator's "
        "recovery-verification step in _attempt_write_guard_recovery "
        "returns False instead of advancing with corrupted data."
    )
    assert "166" in post_restore_reason and "61" in post_restore_reason


def test_real_restore_unblocks_after_recovery():
    """The complement to the phantom-restore test.

    When the checkpoint set DOES include the shrunken file (i.e.
    TRACE_FILES is correctly configured per the 2026-05-27 fix),
    restore_checkpoint copies the pre-flight version back to disk
    and the post-restore record count matches the pre-flight value.
    The re-check returns blocked=False and recovery succeeds.
    """
    guard = IntegrityGuard()

    pre = StageSnapshot(project_id="test", stage_id="group_reasoning")
    pre.files["trace_group_reasoning.jsonl"] = FileSnapshot(
        path="/tmp/trace_group_reasoning.jsonl",
        exists=True,
        size_bytes=540_000,
        record_count=166,
    )
    guard._snapshots[("test", "group_reasoning")] = pre

    # Shrunk briefly during a failed write, then restored to 166 records.
    post_restore = {
        "trace_group_reasoning.jsonl": FileSnapshot(
            path="/tmp/trace_group_reasoning.jsonl",
            exists=True,
            size_bytes=540_000,
            record_count=166,  # matches pre-flight after real restore
        ),
    }
    still_blocked, _ = guard.should_block_stage_completion(
        "test", "group_reasoning", post_restore,
    )
    assert still_blocked is False, (
        "After a true restore (file matches pre-flight record count), the "
        "integrity check must allow the stage to advance."
    )

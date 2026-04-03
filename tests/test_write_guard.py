"""Tests for the pipeline write guard (Phase 70B)."""
import pytest
from pathlib import Path
from codrag.services.pipeline_integrity import IntegrityGuard, FileSnapshot, StageSnapshot


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

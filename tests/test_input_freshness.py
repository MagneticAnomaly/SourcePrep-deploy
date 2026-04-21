"""Tests for pipeline input freshness check (Phase 70B)."""
import pytest
import time
from pathlib import Path
from prep.services.pipeline_integrity import IntegrityGuard


def test_skip_when_outputs_newer_than_inputs(tmp_path):
    """Stage outputs are newer than inputs — should skip."""
    guard = IntegrityGuard()

    input_file = tmp_path / "trace_augmented.jsonl"
    input_file.write_text('{"id": "1"}\n')

    time.sleep(0.05)

    output_file = tmp_path / "trace_epistemic.jsonl"
    output_file.write_text('{"id": "1", "confidence": 0.9}\n')

    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=["trace_augmented.jsonl"],
        output_files=["trace_epistemic.jsonl"],
    )
    assert should_skip is True
    assert "current" in reason.lower()


def test_run_when_inputs_newer_than_outputs(tmp_path):
    """Input was rebuilt after output — stage needs to run."""
    guard = IntegrityGuard()

    output_file = tmp_path / "trace_epistemic.jsonl"
    output_file.write_text('{"id": "1", "confidence": 0.9}\n')

    time.sleep(0.05)

    input_file = tmp_path / "trace_augmented.jsonl"
    input_file.write_text('{"id": "1"}\n{"id": "2"}\n')

    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=["trace_augmented.jsonl"],
        output_files=["trace_epistemic.jsonl"],
    )
    assert should_skip is False


def test_run_when_output_missing(tmp_path):
    """Output doesn't exist — stage must run."""
    guard = IntegrityGuard()

    input_file = tmp_path / "trace_augmented.jsonl"
    input_file.write_text('{"id": "1"}\n')

    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=["trace_augmented.jsonl"],
        output_files=["trace_epistemic.jsonl"],
    )
    assert should_skip is False


def test_run_when_no_inputs(tmp_path):
    """Stage has no pipeline inputs (e.g. structural) — always run."""
    guard = IntegrityGuard()

    should_skip, reason = guard.check_stage_freshness(
        tmp_path,
        input_files=[],
        output_files=["trace_nodes.jsonl"],
    )
    assert should_skip is False

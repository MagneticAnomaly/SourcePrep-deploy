"""Phase 128 Task 7: journal.has_recent_completed_run helper.

Phase 61B (Task 8) will use this as the primary authority for "is this
group's last successful run more recent than this reference time?".
A True answer is conclusive proof of healthy data, demoting mtime
ordering to advisory.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest


@pytest.fixture
def journal(tmp_path: Path):
    from prep.services.pipeline_journal import PipelineJournal

    j = PipelineJournal()
    j.init(tmp_path / "test_journal.db")
    yield j
    j.close()


def test_returns_true_when_completed_run_post_dates_reference(journal) -> None:
    run_id = journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
    journal.run_completed(run_id)
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=time.time() - 3600
    ) is True


def test_returns_false_when_completed_run_pre_dates_reference(journal) -> None:
    """Reference time strictly in the future — completion is "older" than ref."""
    run_id = journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
    journal.run_completed(run_id)
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=time.time() + 3600
    ) is False


def test_returns_false_when_only_failed_runs(journal) -> None:
    run_id = journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
    journal.stage_failed(run_id, "enrichment", "synthetic error")
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=0.0
    ) is False


def test_returns_false_when_only_cancelled_runs(journal) -> None:
    run_id = journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
    journal.run_cancelled(run_id)
    assert journal.has_recent_completed_run(
        "proj-1", "deep_enrichment", since_mtime=0.0
    ) is False


def test_returns_false_when_no_runs_for_project(journal) -> None:
    assert journal.has_recent_completed_run(
        "proj-2", "deep_enrichment", since_mtime=0.0
    ) is False


def test_returns_false_for_different_group(journal) -> None:
    """Completed deep_enrichment must NOT count as a fast_sync completion."""
    run_id = journal.start_run("proj-1", "deep_enrichment", ["enrichment"])
    journal.run_completed(run_id)
    assert journal.has_recent_completed_run(
        "proj-1", "fast_sync", since_mtime=0.0
    ) is False

"""Verify PipelineJournal.delete_runs scopes deletion correctly by group."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from prep.services.pipeline_journal import PipelineJournal


@pytest.fixture()
def journal(tmp_path: Path) -> PipelineJournal:
    j = PipelineJournal()
    j.init(tmp_path / "journal.db")
    return j


def _seed(j: PipelineJournal, run_id: str, project_id: str, group: str) -> None:
    """Insert a minimal pipeline_runs row for testing."""
    conn = j._conn
    assert conn is not None
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, project_id, group_name, status, "
        "stages, current_stage_index, created_at) "
        "VALUES (?, ?, ?, 'completed', '[]', 0, ?)",
        (run_id, project_id, group, time.time()),
    )
    conn.commit()


def test_delete_runs_scoped_to_one_group(journal: PipelineJournal) -> None:
    pid = "proj-A"
    other = "proj-Other"
    _seed(journal, "r1", pid, "fast_sync")
    _seed(journal, "r2", pid, "deep_enrichment")
    _seed(journal, "r3", pid, "finalize")
    _seed(journal, "r4", other, "finalize")  # must NOT be deleted

    deleted = journal.delete_runs(pid, groups={"finalize"})

    assert deleted == 1
    remaining = [
        r["group_name"] for r in journal._conn.execute(
            "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
        ).fetchall()
    ]
    assert sorted(remaining) == ["deep_enrichment", "fast_sync"]
    # Cross-project assertion: other project's finalize row survived
    other_rows = journal._conn.execute(
        "SELECT run_id FROM pipeline_runs WHERE project_id = ?", (other,)
    ).fetchall()
    assert [r["run_id"] for r in other_rows] == ["r4"]


def test_delete_runs_scoped_to_multiple_groups(journal: PipelineJournal) -> None:
    pid = "proj-B"
    _seed(journal, "r1", pid, "fast_sync")
    _seed(journal, "r2", pid, "deep_enrichment")
    _seed(journal, "r3", pid, "finalize")

    deleted = journal.delete_runs(pid, groups={"deep_enrichment", "finalize"})

    assert deleted == 2
    remaining = [
        r["group_name"] for r in journal._conn.execute(
            "SELECT group_name FROM pipeline_runs WHERE project_id = ?", (pid,)
        ).fetchall()
    ]
    assert remaining == ["fast_sync"]


def test_delete_runs_no_groups_means_all_for_project(journal: PipelineJournal) -> None:
    pid = "proj-C"
    other = "proj-D"
    _seed(journal, "r1", pid, "fast_sync")
    _seed(journal, "r2", pid, "deep_enrichment")
    _seed(journal, "r3", other, "fast_sync")

    deleted = journal.delete_runs(pid, groups=None)

    assert deleted == 2
    remaining_pids = [
        r["project_id"] for r in journal._conn.execute(
            "SELECT project_id FROM pipeline_runs"
        ).fetchall()
    ]
    assert remaining_pids == [other]


def test_delete_runs_with_empty_groups_set_is_noop(journal: PipelineJournal) -> None:
    pid = "proj-E"
    _seed(journal, "r1", pid, "fast_sync")

    deleted = journal.delete_runs(pid, groups=set())

    assert deleted == 0
    remaining = journal._conn.execute(
        "SELECT run_id FROM pipeline_runs WHERE project_id = ?", (pid,)
    ).fetchall()
    assert [r["run_id"] for r in remaining] == ["r1"]

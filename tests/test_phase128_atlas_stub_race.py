"""Phase 128 Task 9b: atlas stub-writer must not race with an active run.

The atlas crash-loop guard at resume.py:410-448 reconstructs an atlas
provenance manifest when atlas.json + atlas_segments_manifest.json exist
but atlas_manifest.json is missing. This is the SAME F-67 race pattern
as the downstream-proves-upstream stub writer at resume.py:537:

  1. orchestrator F-67-deletes atlas_manifest.json before atlas worker starts
  2. parallel resume scan sees data files from PRIOR run still on disk
  3. resume scan writes "recovered, finished_at=NOW" stub
  4. atlas worker is still mid-execution

Without a journal-active-run guard, the stub races the worker's real
manifest write and produces inconsistent on-disk state.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import patch

import pytest


@pytest.fixture
def project_with_atlas_data_only(tmp_path: Path) -> Path:
    """Atlas data files from a PRIOR run, atlas_manifest.json missing."""
    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    # atlas.json + atlas_segments_manifest.json from prior run, both
    # > 10 bytes (the size threshold the stub writer uses).
    (idx / "atlas.json").write_text('{"version":"1.0","modules":[]}\n')
    (idx / "atlas_segments_manifest.json").write_text(
        '{"version":"1.0","segments":["a","b"]}\n'
    )
    return idx


def _drive_resume(
    idx_dir: Path,
    journal_active_run: Optional[SimpleNamespace],
):
    from prep.services.pipeline import resume as resume_mod
    from prep.services.pipeline.stages import StageId
    from prep.services.pipeline_journal import journal as _journal

    fake_project = SimpleNamespace(id="proj-1")

    with patch("prep.services.project_helpers.require_project",
               return_value=fake_project), \
         patch("prep.core.project_registry.project_index_dir",
               return_value=idx_dir), \
         patch.object(_journal, "get_active_run",
                      return_value=journal_active_run):
        result = resume_mod.ResumeStrategy.detect_resume_point(
            "proj-1",
            [StageId.ATLAS],
            skip_mtime_cascade=True,
        )
    return result


def test_no_atlas_stub_when_journal_shows_active_finalize(
    project_with_atlas_data_only: Path,
) -> None:
    """An active finalize run in the journal must defer the atlas stub
    write — recovery returns the missing-stage index, not CRASH_RECOVERY."""
    active = SimpleNamespace(
        run_id="run-active", project_id="proj-1",
        group="finalize", status="running",
    )

    result = _drive_resume(project_with_atlas_data_only, journal_active_run=active)

    atlas_manifest = project_with_atlas_data_only / "atlas_manifest.json"
    assert not atlas_manifest.exists(), (
        "Atlas stub written despite active finalize run — race not closed"
    )
    assert result == 0, f"expected resume at ATLAS (0), got {result}"


def test_atlas_stub_written_when_no_active_run(
    project_with_atlas_data_only: Path,
) -> None:
    """No active run → existing crash-loop guard runs and writes a stub."""
    result = _drive_resume(project_with_atlas_data_only, journal_active_run=None)

    atlas_manifest = project_with_atlas_data_only / "atlas_manifest.json"
    assert atlas_manifest.exists(), (
        "Atlas stub should be written when no active run in journal"
    )
    import json
    data = json.loads(atlas_manifest.read_text())
    assert data.get("recovered") is True
    assert "atlas.json" in data.get("recovery_note", "")
    # Resume advances past the now-recovered atlas stage
    assert result == 1, (
        f"expected resume at end (1) after atlas stub recovery, got {result}"
    )

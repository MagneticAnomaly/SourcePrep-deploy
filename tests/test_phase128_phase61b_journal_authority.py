"""Phase 128 Task 8: Phase 61B consults the journal before mtime/marker logic.

A journal entry with status='completed' that post-dates the structural
manifest is conclusive proof of healthy data — the strongest signal we
have. When the journal answers True, Phase 61B short-circuits BEFORE the
build-success marker gate and BEFORE the per-stage mtime check.

The journal-completion check is a self-contained unit test: we patch
``journal.has_recent_completed_run`` to return True/False and verify
that the rest of the recovery pipeline is bypassed accordingly. The
journal helper itself is tested in test_phase128_journal_authority.py.
"""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def project_with_skewed_mtimes(tmp_path: Path) -> Path:
    """All deep manifests present, structural is newest manifest."""
    from prep.services.pipeline.manifest_store import ManifestStore
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
        StageId,
    )

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    store = ManifestStore(idx)
    base = time.time() - 3600
    for offset, stage in enumerate(
        list(FAST_SYNC_STAGES) + list(DEEP_ENRICHMENT_STAGES)
    ):
        store.write_provenance(
            stage, {"format_version": "2.0", "stage_id": stage.value}
        )
        store.touch_provenance_mtime(stage, base + offset * 60)
    store.touch_provenance_mtime(StageId.STRUCTURAL, time.time() - 60)
    return idx


def _drive_phase61b(
    idx_dir: Path,
    journal_says_complete: bool,
):
    """Drive auto_recover_stale_pipelines with a patched journal."""
    from prep.services.pipeline import recovery as rec
    from prep.services.pipeline.manifest_store import ManifestStore
    from prep.services.pipeline.recovery import RecoveryManager
    from prep.services.pipeline_journal import journal as _journal

    fake_projects = [SimpleNamespace(id="proj-1")]
    fake_registry = MagicMock()
    fake_registry.list_projects.return_value = fake_projects

    triggered: List[str] = []
    sync_calls: List[tuple] = []

    real_sync = ManifestStore.sync_downstream_mtimes

    def _spy_sync(self, baseline_stage, target_stages):
        sync_calls.append((baseline_stage, list(target_stages)))
        return real_sync(self, baseline_stage, target_stages)

    with patch.object(rec, "_resolve_idx_dir", return_value=idx_dir), \
         patch("prep.services.project_helpers.get_registry",
               return_value=fake_registry), \
         patch("prep.services.project_helpers.get_project_activity_status",
               return_value="active"), \
         patch.object(ManifestStore, "sync_downstream_mtimes", _spy_sync), \
         patch.object(_journal, "has_recent_completed_run",
                      return_value=journal_says_complete):
        RecoveryManager.auto_recover_stale_pipelines(
            is_deep_auto_fn=lambda pid: True,
            get_file_logger_fn=lambda pid: None,
            is_run_active_fn=lambda pid: False,
            clear_paused_runs_fn=lambda pid: [],
            run_deep_enrichment_fn=lambda pid: triggered.append(pid) or True,
        )

    return triggered, sync_calls


def test_journal_completion_short_circuits_recovery(
    project_with_skewed_mtimes: Path,
) -> None:
    """Journal records a completed deep_enrichment run post-dating
    structural — recovery skipped without ever reaching the marker
    gate or the mtime-touch path."""
    triggered, sync_calls = _drive_phase61b(
        project_with_skewed_mtimes, journal_says_complete=True,
    )
    assert triggered == [], (
        f"Journal authority should suppress recovery, triggered={triggered}"
    )
    assert sync_calls == [], (
        f"Journal gate must short-circuit BEFORE per-stage path; "
        f"sync_calls={sync_calls}"
    )


def test_no_journal_completion_falls_through(
    project_with_skewed_mtimes: Path,
) -> None:
    """No completed-run record → fall through to existing logic. With
    Task 3's touch fix, the mtime-touch path resolves the staleness
    and recovery still doesn't trigger, but sync_downstream_mtimes
    IS called (per-stage path executed)."""
    triggered, sync_calls = _drive_phase61b(
        project_with_skewed_mtimes, journal_says_complete=False,
    )
    assert len(sync_calls) == 1, (
        f"No journal completion should fall through to per-stage path; "
        f"sync_calls={sync_calls}"
    )
    assert triggered == [], (
        "Task 3 fix should resolve mtime staleness via touch — recovery "
        "should not trigger"
    )

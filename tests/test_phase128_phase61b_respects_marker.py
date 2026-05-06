"""Phase 128 Task 6: Phase 61B skips recovery when build-success marker
post-dates structural mtime — even without a clean-shutdown marker.

Note: Task 3's sync_downstream_mtimes fix means that for the common
all-deep-manifests-present-but-structural-newest case, Phase 72's
heal-in-place touch already resolves the staleness without triggering
recovery. The build-success marker gate is therefore tested by spying
on sync_downstream_mtimes — if the marker gate fires, sync_downstream_
mtimes is NOT called (we skip the entire mtime/touch dance). If the
marker is absent or stale, sync_downstream_mtimes IS called.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def project_with_skewed_mtimes(tmp_path: Path):
    """All deep manifests present, structural is the newest manifest."""
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
    # Touch STRUCTURAL last so it is the newest manifest
    store.touch_provenance_mtime(StageId.STRUCTURAL, time.time() - 60)
    return idx


def _drive_phase61b(idx_dir: Path):
    """Drive auto_recover_stale_pipelines and return both the list of
    triggered project_ids and a flag indicating whether sync_downstream_
    mtimes was called (proxy for "did we reach the per-stage check?")."""
    from prep.services.pipeline import recovery as rec
    from prep.services.pipeline.manifest_store import ManifestStore
    from prep.services.pipeline.recovery import RecoveryManager

    fake_projects = [SimpleNamespace(id="proj-1")]
    fake_registry = MagicMock()
    fake_registry.list_projects.return_value = fake_projects

    triggered: List[str] = []
    sync_calls: List[tuple] = []

    def _run_deep(pid: str) -> bool:
        triggered.append(pid)
        return True

    def _fake_status(pid: str) -> str:
        return "active"

    real_sync = ManifestStore.sync_downstream_mtimes

    def _spy_sync(self, baseline_stage, target_stages):
        sync_calls.append((baseline_stage, list(target_stages)))
        return real_sync(self, baseline_stage, target_stages)

    with patch.object(rec, "_resolve_idx_dir", return_value=idx_dir), \
         patch("prep.services.project_helpers.get_registry",
               return_value=fake_registry), \
         patch("prep.services.project_helpers.get_project_activity_status",
               side_effect=_fake_status), \
         patch.object(ManifestStore, "sync_downstream_mtimes", _spy_sync):
        RecoveryManager.auto_recover_stale_pipelines(
            is_deep_auto_fn=lambda pid: True,
            get_file_logger_fn=lambda pid: None,
            is_run_active_fn=lambda pid: False,
            clear_paused_runs_fn=lambda pid: [],
            run_deep_enrichment_fn=_run_deep,
        )

    return triggered, sync_calls


def test_marker_post_dates_structural_short_circuits_recovery(
    project_with_skewed_mtimes: Path,
) -> None:
    """Build-success marker post-dating structural must skip recovery
    BEFORE the per-stage mtime check runs (sync_downstream_mtimes never
    called)."""
    marker = project_with_skewed_mtimes / ".pipeline_last_success"
    marker.write_text(str(time.time()))
    os.utime(marker, (time.time(), time.time()))

    triggered, sync_calls = _drive_phase61b(project_with_skewed_mtimes)

    assert triggered == [], f"recovery triggered despite marker: {triggered}"
    assert sync_calls == [], (
        f"marker gate did NOT fire — sync_downstream_mtimes was called "
        f"{len(sync_calls)} time(s); the per-stage path executed"
    )


def test_stale_marker_falls_through_to_existing_logic(
    project_with_skewed_mtimes: Path,
) -> None:
    """A marker that PRE-DATES structural is stale (e.g. structural was
    rebuilt afterward). Marker gate must fall through; the existing
    Phase 72 touch path then runs and resolves the staleness."""
    marker = project_with_skewed_mtimes / ".pipeline_last_success"
    marker.write_text("stale")
    os.utime(marker, (1.0, 1.0))

    triggered, sync_calls = _drive_phase61b(project_with_skewed_mtimes)

    # Existing logic should run (sync_downstream_mtimes called), and
    # post-Task-3, it should resolve the staleness so recovery still
    # does NOT trigger.
    assert len(sync_calls) == 1, (
        f"stale marker should fall through to per-stage path; "
        f"sync_calls={sync_calls}"
    )
    assert triggered == [], (
        "Task 3 fix should resolve mtime staleness via touch — "
        "recovery should not trigger"
    )


def test_no_marker_falls_through_to_existing_logic(
    project_with_skewed_mtimes: Path,
) -> None:
    """No marker at all → marker gate doesn't fire → existing per-stage
    logic runs."""
    triggered, sync_calls = _drive_phase61b(project_with_skewed_mtimes)

    assert len(sync_calls) == 1, (
        f"no marker should fall through to per-stage path; "
        f"sync_calls={sync_calls}"
    )
    assert triggered == [], (
        "Task 3 fix should resolve mtime staleness via touch — "
        "recovery should not trigger"
    )

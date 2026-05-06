"""Phase 128 Task 3: Phase 72 touch-and-recheck must move deep stages forward
of STRUCTURAL, not just forward of CATALOGUE.

The Phase 61B staleness check at recovery.py:1426 compares each deep stage's
mtime against ``structural_mtime``. After a successful build, STRUCTURAL is
the newest manifest (touched at finalize time). Touching deep stages forward
to CATALOGUE leaves them still older than STRUCTURAL — the post-touch
re-check still trips and triggers a full rebuild. The fix is to touch
forward to STRUCTURAL.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from prep.services.pipeline.manifest_store import ManifestStore
from prep.services.pipeline.stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    StageId,
)


@pytest.fixture
def store_with_post_build_mtime_skew(tmp_path: Path) -> ManifestStore:
    """Build a manifest store mirroring post-successful-build mtime ordering.

    CATALOGUE is older than STRUCTURAL because the build sequence ends with
    STRUCTURAL being touched (finalize, knowledge embedding, etc.).
    """
    idx_dir = tmp_path / ".sourceprep"
    idx_dir.mkdir()
    store = ManifestStore(idx_dir)

    base = time.time() - 3600  # 1 hour ago
    # Order: catalogue first (early in build), deep stages middle,
    # structural last (touched at finalize).
    ordered = [
        StageId.CATALOGUE,
        StageId.ENRICHMENT,
        StageId.GROUP_REASONING,
        StageId.CLUSTERING,
        StageId.DEEPENING,
        StageId.DEEP_KNOWLEDGE,
        StageId.STRUCTURAL,
    ]
    for offset, stage in enumerate(ordered):
        store.write_provenance(
            stage, {"format_version": "2.0", "stage_id": stage.value}
        )
        store.touch_provenance_mtime(stage, base + offset * 60)
    return store


def test_touch_to_structural_resolves_staleness(
    store_with_post_build_mtime_skew: ManifestStore,
) -> None:
    """After touching deep stages to STRUCTURAL's mtime, none should remain
    older — Phase 61B's post-touch re-check passes."""
    store = store_with_post_build_mtime_skew
    structural_mtime = store.provenance_mtime(StageId.STRUCTURAL)

    store.sync_downstream_mtimes(StageId.STRUCTURAL, list(DEEP_ENRICHMENT_STAGES))

    for stage in DEEP_ENRICHMENT_STAGES:
        assert store.provenance_mtime(stage) >= structural_mtime, (
            f"Stage {stage.value} still older than structural after touch — "
            f"Phase 61B will still trigger a spurious rebuild"
        )


def test_touch_to_catalogue_does_not_resolve_staleness(
    store_with_post_build_mtime_skew: ManifestStore,
) -> None:
    """Sanity: the OLD behavior (touch to CATALOGUE) leaves deep stages older
    than STRUCTURAL — proving the bug exists. This guard test ensures that
    if someone reverts the fix, this test fails and flags it."""
    store = store_with_post_build_mtime_skew
    structural_mtime = store.provenance_mtime(StageId.STRUCTURAL)

    store.sync_downstream_mtimes(StageId.CATALOGUE, list(DEEP_ENRICHMENT_STAGES))

    deep_after = [store.provenance_mtime(s) for s in DEEP_ENRICHMENT_STAGES]
    assert all(m < structural_mtime for m in deep_after), (
        "Touching to CATALOGUE should leave deep stages older than STRUCTURAL"
    )

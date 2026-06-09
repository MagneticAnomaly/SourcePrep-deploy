"""Regression test: .guard_rejections.json must be in RECOVERY_MARKERS
so that POST /index/destroy wipes it. Without this, a full reset
leaves stale Write-Guard rejection markers behind that silently defer
selfheal on the freshly-rebuilt index for up to 30 minutes (the P5
TTL).

Scrutiny finding from the cross-cutting review of the 2026-06-08
pipeline reliability fixes.
"""
from __future__ import annotations

from prep.api.routers.trace_routes.shared import (
    ALL_DATA_FILES,
    RECOVERY_MARKERS,
)


def test_guard_rejections_marker_in_recovery_markers():
    """The Write-Guard rejection marker must be in RECOVERY_MARKERS
    so /index/destroy clears it."""
    assert ".guard_rejections.json" in RECOVERY_MARKERS, (
        "Add .guard_rejections.json to RECOVERY_MARKERS in "
        "src/prep/api/routers/trace_routes/shared.py so full reset "
        "wipes Write-Guard markers and prevents stale 30-min defers "
        "on the post-destroy fresh index."
    )


def test_guard_rejections_marker_in_all_data_files():
    """ALL_DATA_FILES is the union the destroy endpoint iterates;
    the marker must transitively appear there."""
    assert ".guard_rejections.json" in ALL_DATA_FILES, (
        "Marker not in ALL_DATA_FILES — destroy will leave it on disk."
    )

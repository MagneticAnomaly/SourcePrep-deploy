"""Deepening drift treats every node as stale when reset barrier is active."""
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_drift_marks_all_nodes_stale_when_barrier_active() -> None:
    from prep.core.deepening import DriftDetector

    detector = DriftDetector(project_id="proj-X")

    # Minimal inputs — when the barrier is active, the body short-circuits
    # and never inspects most of these.
    scores = {f"n{i}": object() for i in range(5)}
    augmentations: dict = {}
    file_hashes: dict = {}
    edges: list = []
    nodes_by_id: dict = {}

    with patch("prep.core.deepening.is_reuse_blocked", return_value=True):
        report = detector.detect(scores, augmentations, file_hashes, edges, nodes_by_id)

    assert sorted(report.stale_nodes) == sorted(scores.keys())
    assert report.total_checked == 5


def test_drift_runs_normally_when_barrier_clear() -> None:
    """With no barrier, no fake-stale marking — real drift detection runs.
    All inputs empty so no nodes mismatch hashes; result has no stale nodes."""
    from prep.core.deepening import DriftDetector

    detector = DriftDetector(project_id="proj-Y")

    scores = {f"n{i}": object() for i in range(3)}
    augmentations: dict = {}
    file_hashes: dict = {}
    edges: list = []
    nodes_by_id: dict = {}

    with patch("prep.core.deepening.is_reuse_blocked", return_value=False):
        report = detector.detect(scores, augmentations, file_hashes, edges, nodes_by_id)

    # Real detect path: no augmentations means nothing to compare hashes
    # against, so no nodes get marked stale. total_checked still reflects
    # the input size.
    assert report.stale_nodes == []
    assert report.total_checked == 3


def test_constructor_default_project_id_is_empty_string() -> None:
    from prep.core.deepening import DriftDetector
    detector = DriftDetector()
    assert detector.project_id == ""


def test_no_check_when_project_id_empty() -> None:
    """When project_id is empty (e.g. headless runs), the barrier is never
    consulted — detect() runs its real logic regardless of patch."""
    from prep.core.deepening import DriftDetector

    detector = DriftDetector()  # project_id == ""

    with patch("prep.core.deepening.is_reuse_blocked", return_value=True) as mock:
        scores = {"n1": object()}
        report = detector.detect(scores, {}, {}, [], {})

    # is_reuse_blocked should NOT have been called because project_id is empty
    mock.assert_not_called()
    # And the early-return path was NOT taken — real detect ran (no stale).
    assert report.stale_nodes == []

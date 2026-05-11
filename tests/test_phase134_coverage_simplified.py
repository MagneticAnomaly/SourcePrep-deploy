"""Phase 134 — compute_trace_coverage reads the changeset, performs
no hashing, has no Path A self-heal, has no backfill carve-out."""
from __future__ import annotations

import inspect

from prep.core.trace import coverage


def test_coverage_does_not_hash():
    src = inspect.getsource(coverage)
    assert "prep_engine.hash_content" not in src, (
        "compute_trace_coverage must not hash files — staleness comes "
        "from the changeset, not from hash comparison"
    )
    assert "hash_algo_mismatch" not in src, (
        "Path A self-heal removed in Phase 134"
    )
    assert "stable_file_hash" not in src
    assert "_backfill_lock" not in src, (
        "backfill carve-out removed; changeset is the truth"
    )


def test_coverage_reads_changeset():
    src = inspect.getsource(coverage)
    assert "read_changeset" in src or "Changeset" in src, (
        "compute_trace_coverage must read the changeset"
    )

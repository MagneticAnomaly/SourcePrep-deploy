"""Phase 133 — assert the preserve+merge defensive logic produces
zero additions on a real fixture. If this test fires, the Rust walker
and Python side disagree on a file (which Phase 133 was supposed to
make impossible)."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_rust_path_merge_has_zero_additions_on_fixture(tmp_path: Path, monkeypatch):
    """Build via the Rust path twice. The second build's saved_file_hashes
    must equal new_hashes — the merge adds nothing. Skip if Rust engine
    isn't available in the test environment (PyO3 wheel not built)."""
    pytest.importorskip("prep_engine")
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "rust")

    from prep.core.trace.builder import TraceBuilder

    fixture = Path(__file__).parent / "fixtures" / "walker_parity_repo"
    idx = tmp_path / "index"
    idx.mkdir()

    builder = TraceBuilder(
        repo_root=fixture,
        index_dir=idx,
        include_globs=["**/*.py", "**/*.md", "**/*.yml"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )

    # First build populates the manifest.
    builder.build()

    # Second build: the assertion installed in builder.py fires under
    # PYTEST_CURRENT_TEST if saved - new is non-empty. Reaching this
    # line without AssertionError is the contract.
    builder.build()

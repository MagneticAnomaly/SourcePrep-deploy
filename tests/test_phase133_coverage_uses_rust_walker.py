"""Phase 133 — coverage discovery routes through prep_engine.walk_repo.

Mock-based contract test. Locks in the cutover at the Python/Rust seam
so subsequent refactors can't accidentally regress to os.walk + fnmatch.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.trace.coverage import compute_trace_coverage


@pytest.fixture
def empty_index(tmp_path: Path):
    """Minimal index_dir with an empty trace_manifest.json."""
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "file_hashes": {},
    }))
    return idx


def test_compute_trace_coverage_calls_prep_engine_walk_repo(tmp_path, empty_index):
    """The cutover. compute_trace_coverage must delegate file discovery
    to the Rust walker; it must not call os.walk for the eligibility
    set anymore."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    with patch("prep_engine.walk_repo") as mock_walk:
        # Return a single FileEntry-shaped object. The real binding
        # returns a list of objects with .path / .abs_path / .size /
        # .modified_secs attributes; coverage iterates them.
        class _StubEntry:
            def __init__(self, path, abs_path, size, modified_secs):
                self.path = path
                self.abs_path = abs_path
                self.size = size
                self.modified_secs = modified_secs

        mock_walk.return_value = [
            _StubEntry(
                path="main.py",
                abs_path=str(repo / "main.py"),
                size=18,
                modified_secs=0.0,
            ),
        ]

        compute_trace_coverage(
            repo_root=repo,
            index_dir=empty_index,
            include_globs=["**/*.py"],
            exclude_globs=[],
            user_exclude_globs=[],
            max_file_bytes=500_000,
        )

    assert mock_walk.called, "compute_trace_coverage must call prep_engine.walk_repo"
    # First positional arg must be the repo root as a string.
    args, kwargs = mock_walk.call_args
    walk_root = args[0] if args else kwargs.get("root")
    assert str(walk_root) == str(repo)

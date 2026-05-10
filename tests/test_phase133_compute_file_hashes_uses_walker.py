"""Phase 133 — _compute_file_hashes walks via prep_engine.walk_repo.

Locks the cutover at the seam: this method previously walked via
self._enumerate_files() (Python os.walk), which could disagree with
the Rust walker that build_trace already uses. After Phase 133 both
walks share a primitive."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prep.core.trace.builder import TraceBuilder


def test_compute_file_hashes_calls_prep_engine_walk_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()

    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )

    with patch("prep_engine.walk_repo") as mock_walk:
        class _StubEntry:
            def __init__(self, path, abs_path, size, modified_secs):
                self.path = path
                self.abs_path = abs_path
                self.size = size
                self.modified_secs = modified_secs

        mock_walk.return_value = [
            _StubEntry("main.py", str(repo / "main.py"), 18, 0.0),
        ]

        builder._compute_file_hashes()

    assert mock_walk.called, "_compute_file_hashes must walk via prep_engine.walk_repo"

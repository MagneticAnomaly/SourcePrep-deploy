"""Phase 133 divergence #5 surface — coverage response carries a
warning when the walker hits its max_files cap, so operators see
truncation instead of silently losing files."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from prep.core.trace.coverage import compute_trace_coverage


def test_coverage_emits_max_files_warning_when_cap_hit(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))

    # Stub walk_repo to return exactly 100_000 entries (Rust default cap).
    class _StubEntry:
        def __init__(self, i):
            self.path = f"f{i}.py"
            self.abs_path = str(repo / f"f{i}.py")
            self.size = 1
            self.modified_secs = 0.0

    with patch("prep_engine.walk_repo") as mock_walk:
        mock_walk.return_value = [_StubEntry(i) for i in range(100_000)]
        result = compute_trace_coverage(
            repo_root=repo,
            index_dir=idx,
            include_globs=["**/*.py"],
            exclude_globs=[],
            user_exclude_globs=[],
            max_file_bytes=500_000,
        )

    warnings = result.get("warnings") or []
    cap_warnings = [w for w in warnings if "max_files" in str(w).lower() or "cap" in str(w).lower()]
    assert cap_warnings, (
        f"expected a max_files cap warning when walker returned exactly 100k entries; "
        f"got warnings={warnings}"
    )


def test_coverage_no_warning_below_cap(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    warnings = result.get("warnings") or []
    assert not warnings, f"expected no warnings on tiny repo; got {warnings}"

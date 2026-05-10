"""Phase 133 divergence #2 — hidden directories not in default
exclude_globs must appear in coverage output. Pre-cutover Python
coverage silently pruned all `.foo` directories via the
`not d.startswith('.')` filter; the Rust walker doesn't, and after
the cutover Python doesn't either."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.trace.coverage import compute_trace_coverage


def test_github_workflows_directory_visible_in_coverage(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py", "**/*.yml"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    paths = set()
    for key in ("traced", "untraced", "stale", "excluded", "pending_embedding"):
        for entry in result.get(key, []):
            paths.add(entry["path"])

    assert ".github/workflows/ci.yml" in paths, (
        "Phase 133 divergence #2 regression: hidden-dir contents must "
        "appear in coverage. The previous `not d.startswith('.')` prune "
        "is gone; only the exclude_globs determine inclusion."
    )
    assert "src/main.py" in paths, "control file should also appear"

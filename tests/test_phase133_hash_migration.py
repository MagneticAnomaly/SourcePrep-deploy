"""Phase 133 — Migration Path A self-heal test.

Pre-cutover manifest has hash_algo="sha256-64" (or absent → defaulted
to that). On first coverage call after the cutover, all hashed files
must be marked stale without computing the current hash. After a
structural rebuild rewrites the manifest with hash_algo="blake3-128",
the next coverage call must categorize files normally.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.trace.coverage import compute_trace_coverage


@pytest.fixture
def repo_with_pre_cutover_manifest(tmp_path: Path):
    """A repo with one .py file and a manifest carrying SHA-256 hashes
    and explicitly hash_algo='sha256-64'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()
    # Compute the SHA-256-64 hash the pre-cutover code would have written.
    import hashlib
    sha = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "hash_algo": "sha256-64",
        "file_hashes": {"main.py": sha},
        "built_at": "2026-05-01T00:00:00Z",
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )
    return repo, idx


def test_pre_cutover_manifest_marks_all_files_stale(repo_with_pre_cutover_manifest):
    repo, idx = repo_with_pre_cutover_manifest

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    stale = {f["path"] for f in result.get("stale", [])}
    traced = {f["path"] for f in result.get("traced", [])}
    untraced = {f["path"] for f in result.get("untraced", [])}

    # The single file must be stale (algo mismatch, no hash computed,
    # marked stale to trigger rebuild).
    assert stale == {"main.py"}, f"expected main.py stale; got stale={stale} traced={traced} untraced={untraced}"


def test_post_cutover_manifest_categorizes_normally(tmp_path):
    """After a hypothetical rebuild has written hash_algo='blake3-128',
    coverage must categorize files via the normal hash-compare path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()

    # Compute the BLAKE3-128 hash that prep_engine.hash_content would write.
    import prep_engine
    blake = prep_engine.hash_content("def main(): pass\n")

    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        "hash_algo": "blake3-128",
        "file_hashes": {"main.py": blake},
        "built_at": "2030-01-01T00:00:00Z",  # future to defeat mtime fast-path
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    traced_or_pending = (
        {f["path"] for f in result.get("traced", [])}
        | {f["path"] for f in result.get("pending_embedding", [])}
    )
    stale = {f["path"] for f in result.get("stale", [])}

    assert "main.py" in traced_or_pending, f"expected main.py traced; got traced/pending={traced_or_pending} stale={stale}"


def test_absent_hash_algo_defaults_to_sha256_64(tmp_path):
    """A manifest from before this phase had no hash_algo field. It
    must be treated as sha256-64 → mismatch with current → self-heal."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx = tmp_path / "index"
    idx.mkdir()
    import hashlib
    sha = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1",
        # no hash_algo field — defaults to sha256-64
        "file_hashes": {"main.py": sha},
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )

    stale = {f["path"] for f in result.get("stale", [])}
    assert stale == {"main.py"}

"""Phase 133 — TraceBuilder writes hash_algo + BLAKE3 hashes into the
trace manifest. Targets the *trace* manifest specifically (the one
compute_trace_coverage reads) — the embedding manifest is covered by
test_phase133_manifest_hash_algo.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.manifest import CURRENT_HASH_ALGO
from prep.core.trace.builder import TraceBuilder


@pytest.fixture
def small_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    idx = tmp_path / "index"
    idx.mkdir()
    return repo, idx


def test_python_builder_emits_hash_algo_blake3_128(small_repo, monkeypatch):
    """Force the Python build path via the _ENGINE module global so we
    test the Python hashing site directly (not the Rust path's
    post-build re-hash). Engine selection in this codebase is via
    PREP_ENGINE env var → prep.core._ENGINE global; we monkeypatch
    the in-builder copy so the test doesn't depend on env var ordering."""
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")

    repo, idx = small_repo
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build()

    manifest = json.loads((idx / "trace_manifest.json").read_text())
    assert manifest.get("hash_algo") == CURRENT_HASH_ALGO
    # Hashes are 32-hex-char BLAKE3, not 16-hex-char SHA-256.
    for rel_path, h in (manifest.get("file_hashes") or {}).items():
        assert len(h) == 32, f"{rel_path}: expected 32-char BLAKE3, got {len(h)}-char {h!r}"


def test_build_manifest_method_emits_hash_algo_unconditionally():
    """`_build_manifest` is the trace manifest factory. After Phase 133
    it always tags the manifest with CURRENT_HASH_ALGO, regardless of
    whether file_hashes is supplied — so even error-fallback manifests
    carry the algo tag."""
    import tempfile
    repo = Path(tempfile.mkdtemp())
    idx = Path(tempfile.mkdtemp())
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    # Direct invocation of the instance method — minimal args.
    m = builder._build_manifest(
        nodes_count=0,
        edges_count=0,
        files_parsed=0,
        files_failed=0,
        file_errors=[],
        last_error=None,
    )
    assert m.get("hash_algo") == CURRENT_HASH_ALGO

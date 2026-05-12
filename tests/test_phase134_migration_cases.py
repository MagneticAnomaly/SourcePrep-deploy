"""Phase 134 — Stage 1 emits the Changeset for all three migration cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from prep.services.pipeline.changeset import read_changeset
from prep.core.trace.builder import TraceBuilder


def _has_prep_engine() -> bool:
    try:
        import prep_engine  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_prep_engine(),
    reason="prep_engine PyO3 binding not built; stage 1 cannot run without it",
)


@pytest.fixture
def small_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    (repo / "util.py").write_text("def util(): return 1\n")
    idx = tmp_path / "index"
    idx.mkdir()
    return repo, idx


def _build_via_python(repo: Path, idx: Path, monkeypatch):
    """Force the Python build path for deterministic test behavior."""
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build()
    return builder


def test_case1_never_built_emits_added_everything(small_repo, monkeypatch):
    """Case 1: project has no prior manifest. Changeset added=everything,
    modified/deleted/unchanged all empty. base_run_id is None."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)

    cs = read_changeset(idx)
    assert cs is not None, "stage 1 must emit a changeset on every build"
    assert cs.added == frozenset({"main.py", "util.py"}), (
        f"Case 1 added must include every walked file; got {cs.added}"
    )
    assert cs.modified == frozenset()
    assert cs.deleted == frozenset()
    assert cs.unchanged == frozenset()
    assert cs.base_run_id is None


def test_case2_blake3_manifest_real_diff(small_repo, monkeypatch):
    """Case 2: prior manifest has hash_algo='blake3-128'. Stage 1
    does a real hash diff. Files unchanged stay in unchanged; one
    file modified moves to modified."""
    repo, idx = small_repo
    # First build: establishes a Phase-133+ manifest
    _build_via_python(repo, idx, monkeypatch)
    cs1 = read_changeset(idx)
    assert cs1 is not None

    # Modify one file
    (repo / "main.py").write_text("def main(): return 'changed'\n")

    # Second build: real diff
    _build_via_python(repo, idx, monkeypatch)
    cs2 = read_changeset(idx)
    assert cs2 is not None
    assert "main.py" in cs2.modified
    assert "util.py" in cs2.unchanged
    assert cs2.added == frozenset()
    assert cs2.deleted == frozenset()
    assert cs2.base_run_id == cs1.run_id


def test_case2_added_and_deleted(small_repo, monkeypatch):
    """Case 2 with file additions/deletions in addition to modifications."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)

    # Add a file, delete a file
    (repo / "new.py").write_text("def new(): pass\n")
    (repo / "util.py").unlink()

    _build_via_python(repo, idx, monkeypatch)
    cs2 = read_changeset(idx)
    assert "new.py" in cs2.added
    assert "util.py" in cs2.deleted
    assert "main.py" in cs2.unchanged


def test_case3_pre_phase133_manifest_trusts_prior_work(small_repo, monkeypatch):
    """Case 3: prior manifest has hash_algo absent or 'sha256-64'
    (pre-Phase-133). Stage 1 cannot meaningfully diff SHA-256 vs
    BLAKE3, so it emits the migration changeset:
        unchanged = {everything in prior manifest still on disk}
        added = {files on disk NOT in prior manifest}
        modified = {} (we cannot tell)
        deleted = {files in prior manifest no longer on disk}
    This UNCONDITIONALLY trusts the prior augmentation work — the
    cache invalidation cascade Phase 133's hot-fix patched is dead
    by construction."""
    repo, idx = small_repo

    # Hand-craft a pre-Phase-133 manifest: SHA-256-64 hashes, no hash_algo.
    sha_main = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    sha_util = hashlib.sha256(b"def util(): return 1\n").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1.0",
        "built_at": "2026-04-01T00:00:00Z",
        # NO hash_algo field — this is the legacy state
        "file_hashes": {"main.py": sha_main, "util.py": sha_util},
    }))
    # Also seed a trace_nodes file so the build doesn't think this is
    # a never-built project.
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n" +
        json.dumps({"kind": "file", "file_path": "util.py", "id": "file:util.py"}) + "\n"
    )

    # Add one new file, delete nothing — to make the migration's
    # add/delete handling distinguishable from "everything unchanged."
    (repo / "new_after_phase133.py").write_text("def new(): pass\n")

    _build_via_python(repo, idx, monkeypatch)

    cs = read_changeset(idx)
    assert cs is not None

    # The headline assertion: existing manifest entries enter
    # `unchanged`, NOT `modified`. This preserves the user's hours
    # of LLM work.
    assert "main.py" in cs.unchanged, (
        "Case 3 must put pre-Phase-133 manifest entries in `unchanged` "
        "to preserve prior augmentation work; got modified={}, unchanged={}"
        .format(cs.modified, cs.unchanged)
    )
    assert "util.py" in cs.unchanged
    # New files enter `added` normally.
    assert "new_after_phase133.py" in cs.added
    # `modified` is intentionally empty in Case 3 (we cannot tell
    # which files actually changed without comparable hashes).
    assert cs.modified == frozenset()


def test_case3_deletes_files_no_longer_on_disk(small_repo, monkeypatch):
    """Case 3 still detects deletes — files in the prior manifest
    that are gone from disk go into `deleted`, not `unchanged`."""
    repo, idx = small_repo

    sha_main = hashlib.sha256(b"def main(): pass\n").hexdigest()[:16]
    sha_util = hashlib.sha256(b"def util(): return 1\n").hexdigest()[:16]
    sha_gone = hashlib.sha256(b"deleted").hexdigest()[:16]
    (idx / "trace_manifest.json").write_text(json.dumps({
        "version": "1.0",
        "file_hashes": {
            "main.py": sha_main,
            "util.py": sha_util,
            "removed_long_ago.py": sha_gone,
        },
    }))
    (idx / "trace_nodes.jsonl").write_text(
        json.dumps({"kind": "file", "file_path": "main.py", "id": "file:main.py"}) + "\n"
    )

    _build_via_python(repo, idx, monkeypatch)
    cs = read_changeset(idx)
    assert "removed_long_ago.py" in cs.deleted
    assert "removed_long_ago.py" not in cs.unchanged

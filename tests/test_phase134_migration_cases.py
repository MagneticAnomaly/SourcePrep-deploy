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


def _build_via_python(repo: Path, idx: Path, monkeypatch, force_from_start: bool = False):
    """Force the Python build path for deterministic test behavior."""
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build(force_from_start=force_from_start)
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


def test_force_from_start_routes_files_to_added_not_modified(small_repo, monkeypatch):
    """2026-05-17 regression fix (two-stage). When the user clicks
    Rebuild (force_from_start=True), the structural stage must emit a
    Changeset that triggers worker re-processing WITHOUT painting the
    coverage dashboard as "everything stale" the moment the rebuild
    finishes.

    Two competing consumers of the Changeset:
      - Workers (inferred_edges.py:230, augmenter.py:513, etc.) gate via
        should_process which checks `added | modified` → both work.
      - compute_trace_coverage at coverage.py:101 maps `cs.modified` →
        the "stale" count shown in Graph Scope. Putting force-everything
        files in `modified` makes the post-rebuild UI display
        "74 stale" — the exact regression hit at SkyPath.

    Therefore force-everything files go in `added`. Workers re-process;
    coverage display correctly shows 0 stale."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)
    cs1 = read_changeset(idx)
    assert cs1 is not None

    _build_via_python(repo, idx, monkeypatch, force_from_start=True)
    cs2 = read_changeset(idx)
    assert cs2 is not None
    assert cs2.added == frozenset({"main.py", "util.py"}), (
        "Rebuild must mark every file as added so downstream workers "
        "re-process them. Got added=%s" % (cs2.added,)
    )
    assert cs2.modified == frozenset(), (
        "Force-from-start changeset must NOT use `modified` — "
        "compute_trace_coverage interprets cs.modified as stale_set, "
        "so a post-rebuild UI would falsely show every file as stale."
    )
    assert cs2.unchanged == frozenset()
    assert cs2.base_run_id == cs1.run_id


def test_force_from_start_workers_will_actually_process(small_repo, monkeypatch):
    """Behavioral guard: after a force-from-start build, calling
    should_process on the resulting Changeset must return True for
    every file. This is the exact API the Phase-135 workers consult
    (inferred_edges.py:230, augmenter.py:513, etc.) — if any of them
    skips, Rebuild is broken."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)
    _build_via_python(repo, idx, monkeypatch, force_from_start=True)
    cs = read_changeset(idx)
    assert cs is not None
    for path in ("main.py", "util.py"):
        assert cs.should_process(path), (
            f"force-from-start changeset must say should_process({path!r}) "
            "is True so workers re-do their work"
        )


def test_force_from_start_coverage_does_not_show_files_as_stale(small_repo, monkeypatch):
    """End-to-end guard against the SkyPath regression: after a
    force-from-start rebuild, the coverage check that drives the
    'Stale (N)' badge in the Graph Scope panel must NOT classify any
    files as stale. Coverage at coverage.py:101 reads stale_set from
    cs.modified."""
    from prep.core.trace.coverage import compute_trace_coverage

    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)
    _build_via_python(repo, idx, monkeypatch, force_from_start=True)

    result = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    summary = result.get("summary", {})
    assert summary.get("stale", -1) == 0, (
        "force_from_start must not paint the dashboard as 'everything "
        "stale' after the rebuild finishes. Got "
        f"summary={summary}"
    )


def test_case1b_manifest_wiped_uses_prior_changeset_for_unchanged(small_repo, monkeypatch):
    """2026-05-17 regression fix. When the structural manifest is wiped
    or written without file_hashes, the old Case 1 code threw away every
    downstream cache by marking every file as `added`. The new fallback
    consults the prior changeset.json (which survives a manifest wipe
    because it lives in a different file) and treats the files it knew
    about as `unchanged`, only new-on-disk files as `added`. Without
    this, the augmenter, knowledge index, and atlas all silently
    re-process the entire repo on every daemon restart after a crash."""
    repo, idx = small_repo
    # First build: establishes manifest + good changeset.
    _build_via_python(repo, idx, monkeypatch)
    cs1 = read_changeset(idx)
    assert cs1 is not None
    prior_run_id = cs1.run_id

    # Simulate the regression trigger: manifest gone, changeset survives.
    (idx / "trace_manifest.json").unlink()

    # Add one new file; existing two files unchanged on disk.
    (repo / "new_file.py").write_text("def new(): pass\n")

    _build_via_python(repo, idx, monkeypatch)
    cs2 = read_changeset(idx)
    assert cs2 is not None, "rebuild must emit a changeset"
    assert cs2.unchanged == frozenset({"main.py", "util.py"}), (
        f"prior-known files must be carried forward as unchanged so the "
        f"augmenter does not re-process them; got unchanged={cs2.unchanged}"
    )
    assert cs2.added == frozenset({"new_file.py"}), (
        f"only the actually-new file must be in added; got added={cs2.added}"
    )
    assert cs2.modified == frozenset()
    assert cs2.base_run_id == prior_run_id, (
        "base_run_id must point at the prior changeset so the pipeline "
        "journal can chain through the wipe"
    )


def test_case1b_manifest_wiped_detects_deleted_files(small_repo, monkeypatch):
    """Belt: when the manifest is wiped, the Case 1b fallback must still
    detect files that were deleted on disk since the prior changeset.
    Otherwise downstream cleanup (cluster/group_reasoning/deepening/audit)
    leaves orphan augmentation entries forever — same regression class
    Phase 134 was designed to prevent."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)
    cs1 = read_changeset(idx)
    assert cs1 is not None

    # Simulate: manifest wiped, file deleted on disk
    (idx / "trace_manifest.json").unlink()
    (repo / "util.py").unlink()

    _build_via_python(repo, idx, monkeypatch)
    cs2 = read_changeset(idx)
    assert cs2 is not None
    assert "util.py" in cs2.deleted, (
        f"Case 1b must mark the deleted file in `deleted` so downstream "
        f"cleanup runs; got deleted={cs2.deleted}"
    )
    assert "util.py" not in cs2.unchanged


def test_case1b_manifest_wiped_falls_back_to_trace_augmented(small_repo, monkeypatch):
    """Belt-and-suspenders fallback: if both the manifest AND the prior
    changeset are gone but trace_augmented.jsonl survives (the augmenter
    writes a separate file from the structural stage), still recover
    the prior file set by parsing node_ids out of the augmenter output."""
    repo, idx = small_repo
    _build_via_python(repo, idx, monkeypatch)

    # Simulate a deeper wipe: manifest AND changeset gone, but augmenter
    # output survives (it's written by a different stage).
    (idx / "trace_manifest.json").unlink()
    (idx / "changeset.json").unlink()
    (idx / "trace_augmented.jsonl").write_text(
        json.dumps({"node_id": "file:main.py", "summary": "x"}) + "\n"
        + json.dumps({"node_id": "file:util.py", "summary": "y"}) + "\n"
    )

    _build_via_python(repo, idx, monkeypatch)
    cs = read_changeset(idx)
    assert cs is not None
    assert cs.unchanged == frozenset({"main.py", "util.py"}), (
        f"trace_augmented should rescue the prior file set; "
        f"got unchanged={cs.unchanged}"
    )
    assert cs.added == frozenset()
    assert cs.base_run_id is None, "no prior changeset → no base_run_id"


def test_case1a_truly_first_build_still_marks_everything_added(small_repo, monkeypatch):
    """Guard: the new fallback must not regress the genuine first-build
    case. If there is no manifest, no prior changeset, AND no augmenter
    output, every file is genuinely new and must land in `added`."""
    repo, idx = small_repo
    # Sanity: idx is empty.
    assert not (idx / "trace_manifest.json").exists()
    assert not (idx / "changeset.json").exists()
    assert not (idx / "trace_augmented.jsonl").exists()

    _build_via_python(repo, idx, monkeypatch)
    cs = read_changeset(idx)
    assert cs is not None
    assert cs.added == frozenset({"main.py", "util.py"})
    assert cs.unchanged == frozenset()
    assert cs.base_run_id is None


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

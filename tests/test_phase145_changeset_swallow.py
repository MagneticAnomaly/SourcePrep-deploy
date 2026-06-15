"""Phase 145 — changeset "swallowed edit" regression: documentation + guards.

Discovered dogfooding SkyPath-Restart (2026-06-15): files with genuine
content edits (confirmed via `git diff`: ARViewController.swift +37 lines)
were classified `changeset.unchanged` and never re-enriched or finalized.

ROOT CAUSE (daemon-wide): every project's trace_manifest.json on disk had
`hash_algo: None`, because the structural stage's provenance write dropped
the builder's `hash_algo` tag. With the prior manifest untagged,
`TraceBuilder._emit_changeset` saw `prior_algo != CURRENT` and took its
"can't compare → trust prior" path (Case 3): every surviving file →
`unchanged`, `modified = {}`. So no content edit was ever reported as
modified, for any project (all 13 local changesets had `modified == []`).

THE FIX is at the writer, not here:
  * manifest_store.py — stop dropping `hash_algo` (+ `built_at`) on the
    STRUCTURAL provenance merge, so new manifests stay tagged and Case 2
    (the real diff) runs again. See
    test_phase145_provenance_preserves_hash_algo.py.

Why _emit_changeset is deliberately NOT changed to treat untagged-as-current:
  1. Unsafe — a genuine pre-Phase-133 manifest is ALSO untagged but its
     hashes are a different algo; diffing it flags every file modified (the
     LLM-recall storm guarded by test_phase134_migration_cases.py).
  2. Useless for the backlog — once a file is swallowed, the manifest
     baseline already holds the *edited* hash, so a re-diff sees no change.
     Recovery of already-swallowed edits is a one-time force-rebuild
     (routes through `added`, no "everything stale" flash).

These tests pin the Case 2 happy path (now reachable post-fix) and document
the two residual trust-prior limitations.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from prep.core.manifest import CURRENT_HASH_ALGO
from prep.core.trace.builder import TraceBuilder
from prep.services.pipeline.changeset import Changeset, read_changeset, write_changeset


def _builder(tmp_path: Path) -> TraceBuilder:
    repo = tmp_path / "repo"
    repo.mkdir()
    idx = tmp_path / "idx"
    idx.mkdir()
    # Explicit globs so the constructor skips ensure_repo_policy /
    # effective_excludes filesystem work — we only exercise _emit_changeset.
    return TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.swift"],
        exclude_globs=["**/.git/**"],
    )


def test_case2_tagged_manifest_detects_real_edit(tmp_path: Path):
    """The path the manifest_store fix restores: with a properly-tagged
    prior manifest, a real content change surfaces as `modified` and an
    untouched file stays `unchanged`. This is what every project SHOULD
    have been doing all along."""
    b = _builder(tmp_path)

    prior_manifest = {
        "run_id": "run-old",
        "hash_algo": CURRENT_HASH_ALGO,
        "file_hashes": {"A.swift": "OLD", "B.swift": "SAME"},
    }
    new_hashes = {"A.swift": "NEW", "B.swift": "SAME"}  # A edited, B not

    b._emit_changeset(new_hashes, prior_manifest, run_id="run-new")

    cs = read_changeset(b.index_dir)
    assert cs is not None
    assert "A.swift" in cs.modified
    assert "B.swift" in cs.unchanged
    assert cs.should_process("A.swift") is True
    assert cs.should_process("B.swift") is False


def test_untagged_prior_trusts_prior_work_by_design(tmp_path: Path):
    """Documents the deliberate limitation: an untagged prior manifest is
    ambiguous (dropped-tag vs genuine pre-Phase-133), so _emit_changeset
    trusts prior work (Case 3) rather than risk an everything-modified
    storm. The manifest_store fix prevents NEW manifests from being
    untagged; existing untagged backlogs are cleared by a force-rebuild."""
    b = _builder(tmp_path)

    prior_manifest = {
        "run_id": "run-old",
        "file_hashes": {"A.swift": "OLD", "B.swift": "SAME"},
        # NO hash_algo — untagged
    }
    new_hashes = {"A.swift": "NEW", "B.swift": "SAME"}

    b._emit_changeset(new_hashes, prior_manifest, run_id="run-new")

    cs = read_changeset(b.index_dir)
    assert cs is not None
    # Trust-prior: both go to unchanged, modified stays empty.
    assert cs.modified == frozenset()
    assert "A.swift" in cs.unchanged
    assert "B.swift" in cs.unchanged


@pytest.mark.xfail(
    strict=True,
    reason="Case 1b (prior manifest lost its file_hashes but a prior "
    "changeset survives) carries surviving files forward as unchanged, so a "
    "real edit during a manifest wipe is missed. Lower priority now that "
    "manifest_store preserves file_hashes; documented in "
    "FINDING_changeset-swallowed-edits.md.",
)
def test_case1b_hashless_manifest_does_not_swallow_real_edit(tmp_path: Path):
    b = _builder(tmp_path)
    write_changeset(
        b.index_dir,
        Changeset(
            added=frozenset(),
            modified=frozenset(),
            deleted=frozenset(),
            unchanged=frozenset({"A.swift"}),
            run_id="run-old",
            base_run_id=None,
        ),
    )
    prior_manifest = {"run_id": "run-old", "file_hashes": {}}  # hashes wiped
    new_hashes = {"A.swift": "NEW"}
    b._emit_changeset(new_hashes, prior_manifest, run_id="run-new")
    cs = read_changeset(b.index_dir)
    assert cs is not None
    assert cs.should_process("A.swift") is True

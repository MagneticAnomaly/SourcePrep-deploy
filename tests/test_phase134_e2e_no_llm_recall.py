"""Phase 134 — end-to-end migration smoke. The headline regression
test for Important #3 (cache invalidation cascade).

Setup: a project with a pre-Phase-133 manifest (SHA-256 hashes, no
hash_algo) and stub augmentations also carrying SHA-256 hashes (or
no file_hash field, since Phase 134 Task 4 deleted that). This is
the state the SourcePrep project was in on 2026-05-10 when clicking
deep_enrichment Auto re-ran every LLM call.

Phase 134 expectation: stage 1 emits a Case-3 changeset (everything
in `unchanged`), the augmenter sees should_process(path) → False
for every existing entry, ZERO LLM call sites are invoked.

If this test ever fails post-Phase-134, the cascade is back."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _has_prep_engine() -> bool:
    try:
        import prep_engine  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_prep_engine(),
    reason="prep_engine PyO3 binding not built",
)


@pytest.fixture
def pre_phase133_project(tmp_path: Path):
    """A project with a SHA-256 manifest and stub augmentations."""
    repo = tmp_path / "repo"
    repo.mkdir()
    files = {"main.py": "def main(): pass\n", "util.py": "def util(): return 1\n"}
    for name, body in files.items():
        (repo / name).write_text(body)

    idx = tmp_path / "index"
    idx.mkdir()

    # Pre-Phase-133 manifest (SHA-256-64, no hash_algo)
    manifest = {
        "version": "1.0",
        "built_at": "2026-04-01T00:00:00Z",
        "file_hashes": {
            name: hashlib.sha256(body.encode()).hexdigest()[:16]
            for name, body in files.items()
        },
    }
    (idx / "trace_manifest.json").write_text(json.dumps(manifest))

    # trace_nodes.jsonl seed
    nodes = "\n".join(
        json.dumps({"kind": "file", "file_path": name, "id": f"file:{name}"})
        for name in files
    )
    (idx / "trace_nodes.jsonl").write_text(nodes + "\n")

    # Stub augmentations — without file_hash field (Phase 134 Task 4
    # deleted the field). Legacy entries on disk may have it; load
    # path silently ignores unknown keys.
    augs = [
        {"node_id": f"file:{name}", "summary": f"summary for {name}"}
        for name in files
    ]
    (idx / "trace_augmented.jsonl").write_text(
        "\n".join(json.dumps(a) for a in augs) + "\n"
    )

    return repo, idx, files


def test_no_llm_recall_on_phase133_to_134_migration(pre_phase133_project, monkeypatch):
    """Build via stage 1, then check the augmenter's per-node skip
    decision. Assert that for every file in the prior manifest,
    _should_skip returns True (skip — trust the cached entry).
    No LLM call is needed because should_process returns False for
    all unchanged files."""
    repo, idx, files = pre_phase133_project

    # Force Python build path for deterministic test
    monkeypatch.setattr("prep.core.trace.builder._ENGINE", "python")

    # Stage 1: build, emit changeset
    from prep.core.trace.builder import TraceBuilder
    builder = TraceBuilder(
        repo_root=repo,
        index_dir=idx,
        include_globs=["**/*.py"],
        exclude_globs=[],
        max_file_bytes=500_000,
    )
    builder.build()

    # Verify the changeset is the migration shape (Case 3)
    from prep.services.pipeline.changeset import read_changeset
    cs = read_changeset(idx)
    assert cs is not None
    assert "main.py" in cs.unchanged, (
        f"Case 3 migration: main.py should be unchanged; got {cs.unchanged}"
    )
    assert cs.modified == frozenset(), (
        f"Case 3 migration: modified must be empty; got {cs.modified}"
    )

    # Verify the augmenter's _should_skip returns True for every
    # pre-existing entry — i.e., NO LLM would be invoked for them.
    from prep.core.augmenter import TraceAugmenter, AugmentationEntry
    augmenter = TraceAugmenter.__new__(TraceAugmenter)
    augmenter.changeset = cs

    # AugmentationEntry requires: node_id, summary, role, confidence,
    # augmented_at, model (the per-entry file_hash was removed in Task 4)
    existing = {
        f"file:{name}": AugmentationEntry(
            node_id=f"file:{name}",
            summary=f"summary for {name}",
            role="utility",
            confidence=0.85,
            augmented_at="2026-04-01T00:00:00Z",
            model="stub",
        )
        for name in files
    }

    for name in files:
        node = {"id": f"file:{name}", "file_path": name}
        skip = augmenter._should_skip(node, existing)
        assert skip is True, (
            f"Phase 134 contract violation: _should_skip returned False "
            f"for {name} which is in changeset.unchanged. The cache "
            f"invalidation cascade is back. Investigate before merging."
        )

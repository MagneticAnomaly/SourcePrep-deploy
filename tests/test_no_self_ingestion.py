"""Phase 115 Step 11 — regression guard for the self-ingestion leak.

Scenario that motivated this phase: an overnight Deep Reasoning run
processed 24 `storybook-static/index.html` fragments, `codrag_data/`
SQLite-dump chunks, and TypeScript `.d.ts` files. Those paths were in
the code defaults as dir-names but the policy writer only unioned
**dir globs** — file globs like `**/*.d.ts` never back-filled.

This test scaffolds a repo that contains the exact culprit paths and
asserts that:
- `effective_excludes()` returns a set that filters them all out.
- The resulting `exclude_globs` in `repo_policy.json` match every culprit.
- `TraceBuilder._enumerate_files()` returns zero of them.

Adding a new leak culprit to the fixture is how we pin a regression
against future policy rewrites.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pathspec

from prep.core.repo_policy import effective_excludes, ensure_repo_policy
from prep.core.trace.builder import TraceBuilder


# Exact paths from the overnight Deep Reasoning leak report
# (docs/Phase115_filter-universality/00_PROBLEM.md §E1).
LEAK_CULPRITS = [
    # Prep self-ingestion
    ".prep/trace_nodes.jsonl",
    "codrag_data/prep_antibodies.db",
    "codrag_data/ui_config.json",
    # AI-tool output
    "AGENTS.md",
    "CLAUDE.md",
    ".cursor/rules/prep.mdc",
    ".windsurf/rules/prep.md",
    ".github/copilot-instructions.md",
    # Frontend build artifacts
    "packages/ui/storybook-static/index.html",
    "packages/ui/storybook-static/iframe.html",
    "packages/ui/storybook-static/assets/chunk-abc123.js",
    "src/types/generated.d.ts",
    "node_modules/some-pkg/dist/index.d.ts",
    "dist/bundle.min.js",
    "dist/bundle.min.css",
    "dist/bundle.js.map",
    # Legit files that MUST still pass the filter.
    # (control group — surfaces false positives.)
]

LEGIT_FILES = [
    "src/prep/core/trace/builder.py",
    "packages/ui/src/index.ts",
    "docs/README.md",
    "engine/crates/prep-walker/src/lib.rs",
]


def _scaffold_leaky_repo(tmpdir: Path) -> tuple[Path, Path]:
    """Create a repo containing every leak culprit and every legit file."""
    # macOS tempfile returns /var/... but resolve() canonicalises to
    # /private/var/... — TraceBuilder does the same internally, so use
    # the resolved form up front to keep relative_to() happy below.
    repo_root = tmpdir.resolve()
    index_dir = repo_root / ".prep"
    index_dir.mkdir(parents=True, exist_ok=True)

    for rel in LEAK_CULPRITS + LEGIT_FILES:
        f = repo_root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"/* fixture: {rel} */\n")

    return repo_root, index_dir


def test_effective_excludes_blocks_every_leak_culprit() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo_root, index_dir = _scaffold_leaky_repo(Path(td))

        excludes = effective_excludes(index_dir=index_dir, repo_root=repo_root)
        spec = pathspec.PathSpec.from_lines("gitwildmatch", excludes)

        for culprit in LEAK_CULPRITS:
            assert spec.match_file(culprit), (
                f"Leak culprit NOT blocked by effective_excludes: {culprit}\n"
                f"This is a Phase 115 regression — the filter has a hole."
            )


def test_policy_excludes_persist_every_leak_culprit_glob() -> None:
    """`repo_policy.json` written by ensure_repo_policy() must carry
    each leak culprit's matching glob, so downstream tools (Rust
    walker, selfheal, watcher) that read the file directly also block.
    """
    with tempfile.TemporaryDirectory() as td:
        repo_root, index_dir = _scaffold_leaky_repo(Path(td))

        policy = ensure_repo_policy(index_dir, repo_root)
        excludes = set(policy.get("exclude_globs") or [])
        spec = pathspec.PathSpec.from_lines("gitwildmatch", excludes)

        for culprit in LEAK_CULPRITS:
            assert spec.match_file(culprit), (
                f"repo_policy.json exclude_globs does not cover: {culprit}"
            )


def test_trace_builder_does_not_enumerate_leak_culprits() -> None:
    """End-to-end: the file walker used by the trace pipeline must
    not surface any culprit, and must still return the legit files.
    """
    with tempfile.TemporaryDirectory() as td:
        repo_root, index_dir = _scaffold_leaky_repo(Path(td))

        # Force policy generation first so TraceBuilder falls through to
        # the effective_excludes() path (not its safety-net include list).
        ensure_repo_policy(index_dir, repo_root)

        builder = TraceBuilder(repo_root=repo_root, index_dir=index_dir)
        files = [str(p.relative_to(repo_root).as_posix()) for p in builder._enumerate_files()]

        for culprit in LEAK_CULPRITS:
            assert culprit not in files, (
                f"TraceBuilder enumerated leak culprit: {culprit}\n"
                f"Filter leak detected — Phase 115 regression."
            )

        # Control: legit .py / .ts / .md / .rs files must still appear.
        for legit in LEGIT_FILES:
            # profile_repo may drop .md or .rs depending on detected lang,
            # so only hard-assert the always-included Python file.
            if legit.endswith(".py"):
                assert legit in files, (
                    f"False positive: legit file filtered out by Phase 115 defaults: {legit}"
                )

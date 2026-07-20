"""Phase 115 Step 9 — Python/Rust walker default-exclude parity.

The Rust `prep-walker` crate carries its own `WalkConfig::default()`
with hardcoded exclude globs. It exists as a safety net when Rust is
invoked without Python-resolved config, so drift is silent but real:
Python gains a new default exclude, the Rust walker keeps ingesting
the excluded files, and selfheal / trace-builder behaviour diverges.

This test parses the `exclude_globs` literal out of
`engine/crates/prep-walker/src/lib.rs` and compares against the
Python-side L1 set (`DEFAULT_EXCLUDE_DIR_NAMES` ∪ `DEFAULT_EXCLUDE_FILE_GLOBS`
∪ the `**/.*` dotfile glob).

Parity contract: **every Python L1 glob must appear in Rust**. Rust is
allowed to carry extra entries (e.g. ecosystem-specific globs Python
hasn't needed yet) — the failure mode we care about is Python adding
an entry that Rust misses.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from prep.core.repo_profile import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_GLOBS,
)
from prep.core.trace.coverage import compute_trace_coverage

REPO_ROOT = Path(__file__).resolve().parent.parent
RUST_WALKER_SRC = REPO_ROOT / "engine" / "crates" / "prep-walker" / "src" / "lib.rs"


def _parse_rust_exclude_globs(text: str) -> set[str]:
    """Extract the `exclude_globs: vec![...]` literal from WalkConfig::default()."""
    match = re.search(
        r"exclude_globs:\s*vec!\[(.*?)\],\s*max_file_bytes",
        text,
        re.DOTALL,
    )
    assert match, "could not locate exclude_globs vec! in prep-walker/src/lib.rs"

    body = match.group(1)
    # Match "..." literals (strip the .into() suffix on each entry).
    globs = re.findall(r'"([^"]+)"', body)
    return set(globs)


def test_rust_walker_mirrors_python_l1_excludes() -> None:
    rust_excludes = _parse_rust_exclude_globs(RUST_WALKER_SRC.read_text())

    python_l1 = set()
    python_l1.update(f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES)
    python_l1.update(DEFAULT_EXCLUDE_FILE_GLOBS)

    missing = python_l1 - rust_excludes
    assert not missing, (
        "Rust walker exclude_globs missing Python L1 entries — drift detected.\n"
        f"Missing {len(missing)}: {sorted(missing)}\n"
        f"Fix: add these literals to the `exclude_globs: vec![...]` block in "
        f"engine/crates/prep-walker/src/lib.rs."
    )


def test_rust_walker_covers_self_ingestion_guards() -> None:
    """Hard invariant: self-ingestion guards MUST be in Rust.

    The live state-dir guards (`**/.sourceprep/**` and `**/prep_data/**`)
    must be present so Prep does not ingest its own outputs. Legacy
    dead-name patterns are no longer carried.
    """
    rust_excludes = _parse_rust_exclude_globs(RUST_WALKER_SRC.read_text())
    for required in ("**/.sourceprep/**", "**/prep_data/**"):
        assert required in rust_excludes, (
            f"Self-ingestion guard '{required}' missing from Rust walker defaults. "
            f"This is a phase-115 regression — Prep will ingest its own outputs."
        )


def test_rust_walker_covers_leak_culprits() -> None:
    """Regression: the leaks that motivated Phase 115.

    The legacy CWD-relative daemon-dir glob was dropped long ago; the
    live `prep_data` guard must remain.
    """
    rust_excludes = _parse_rust_exclude_globs(RUST_WALKER_SRC.read_text())
    for required in (
        "**/storybook-static/**",
        "**/prep_data/**",
        "**/*.d.ts",
        "**/*.map",
    ):
        assert required in rust_excludes, (
            f"Leak culprit '{required}' missing from Rust walker defaults."
        )


# ── Phase 133: behavior parity over the divergence-trigger fixture ──

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "walker_parity_repo"


def _coverage_paths(*, include_globs, exclude_globs):
    """Run compute_trace_coverage on the fixture, return the union of
    traced+untraced+stale+excluded paths. (We don't care about the
    categorization here — only the discovery set.)"""
    # Fresh index dir per call so the cached manifest doesn't leak.
    idx = Path(tempfile.mkdtemp())
    (idx / "trace_manifest.json").write_text(json.dumps({"version": "1", "file_hashes": {}}))
    result = compute_trace_coverage(
        repo_root=FIXTURE,
        index_dir=idx,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        user_exclude_globs=[],
        max_file_bytes=500_000,
    )
    paths = set()
    for key in ("traced", "untraced", "stale", "excluded", "pending_embedding"):
        for entry in result.get(key, []):
            paths.add(entry["path"])
    return paths


def test_recursive_py_glob_picks_up_deep_files() -> None:
    """Divergence #1: stdlib fnmatch fails on `**/*.py` against
    `deep/nested/path/leaf.py`. Rust globset succeeds."""
    paths = _coverage_paths(include_globs=["**/*.py"], exclude_globs=[])
    assert "deep/nested/path/leaf.py" in paths


def test_hidden_github_workflow_visible() -> None:
    """Divergence #2: Python's `not d.startswith('.')` prune drops
    `.github/workflows/ci.yml`. Rust walker doesn't prune hidden dirs."""
    paths = _coverage_paths(include_globs=["**/*.yml", "**/*.py"], exclude_globs=[])
    assert ".github/workflows/ci.yml" in paths


def test_nested_gitignore_honored() -> None:
    """Divergence #6: nested .gitignore must apply. visible.py appears,
    secret.tmp does not.

    Note: The Rust walker's OverrideBuilder takes precedence over gitignore
    when a file explicitly matches an include glob. We therefore test the
    common case: include_globs that do NOT contain '**/*.tmp'. In this
    configuration, the nested .gitignore correctly hides secret.tmp while
    visible.py is reachable. This is still better than the prior Python
    implementation which only read the ROOT .gitignore.
    """
    paths = _coverage_paths(include_globs=["**/*.py"], exclude_globs=[])
    assert "sub/with_gitignore/visible.py" in paths
    assert "sub/with_gitignore/secret.tmp" not in paths


def test_max_files_cap_respected() -> None:
    """Divergence #5: walker caps at 100k. Fixture is small, so just
    confirm the response shape doesn't error when called normally.
    The cap-WARNING surface is tested in test_phase133_max_files_warning.py."""
    paths = _coverage_paths(include_globs=["**/*.py"], exclude_globs=[])
    assert len(paths) > 0, "expected at least one .py file from the fixture"

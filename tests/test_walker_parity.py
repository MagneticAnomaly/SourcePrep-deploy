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

import re
from pathlib import Path

from prep.core.repo_profile import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_GLOBS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUST_WALKER_SRC = REPO_ROOT / "engine" / "crates" / "codrag-walker" / "src" / "lib.rs"


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


def test_rust_walker_covers_codrag_output_dirs() -> None:
    """Hard invariant: self-ingestion guard MUST be in Rust."""
    rust_excludes = _parse_rust_exclude_globs(RUST_WALKER_SRC.read_text())
    for required in ("**/.prep/**", "**/codrag_data/**"):
        assert required in rust_excludes, (
            f"Self-ingestion guard '{required}' missing from Rust walker defaults. "
            f"This is a phase-115 regression — Prep will ingest its own outputs."
        )


def test_rust_walker_covers_leak_culprits() -> None:
    """Regression: the four leaks that motivated Phase 115."""
    rust_excludes = _parse_rust_exclude_globs(RUST_WALKER_SRC.read_text())
    for required in (
        "**/storybook-static/**",
        "**/codrag_data/**",
        "**/*.d.ts",
        "**/*.map",
    ):
        assert required in rust_excludes, (
            f"Leak culprit '{required}' missing from Rust walker defaults."
        )

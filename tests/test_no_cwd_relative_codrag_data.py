"""Phase 113 — regression guard against CWD-relative `codrag_data/` literals.

Pre-fix: several modules hardcoded `./codrag_data` as the daemon's
default data dir, so the daemon's on-disk state followed its CWD. The
fix introduced `prep.core.paths.data_dir()` as the single source of
truth. The legacy migration has since been gutted (dead codename, zero
users), so NO src file may reference the literal — this test fails on
any reintroduction.

If this test fails, the path you're tempted to reach for is:
`from prep.core.paths import data_dir` (daemon-wide) or
`from prep.core.project_registry import project_index_dir` (per-project).
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "prep"

# The Phase-113 legacy `./codrag_data` migration was gutted (dead
# codename, zero users) — no src file legitimately references the
# literal anymore. This allowlist is intentionally empty: any
# reintroduction of `codrag_data` in src is a bug.
_ALLOWLIST_RELATIVE: frozenset[str] = frozenset()

# Regex: "./codrag_data" or "codrag_data/" as a STRING LITERAL (we
# allow docstrings/comments — they're caught manually above via the
# allowlist). We hit both quoted forms (single/double) and the bare
# form that might appear in path expressions.
_LITERAL_RE = re.compile(r"""['"]\.?/?codrag_data/?['"]|['"]\.?/codrag_data""")


def _iter_py_files() -> list[Path]:
    return [p for p in SRC_ROOT.rglob("*.py") if p.is_file()]


def test_no_cwd_relative_codrag_data_in_src() -> None:
    """No source file may reintroduce `./codrag_data` as a default path."""
    offenders: list[str] = []
    for py in _iter_py_files():
        rel = py.relative_to(SRC_ROOT).as_posix()
        if rel in _ALLOWLIST_RELATIVE:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _LITERAL_RE.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "The following src files contain a CWD-relative `codrag_data` "
        "literal. Route through `prep.core.paths.data_dir()` instead:\n  "
        + "\n  ".join(offenders)
    )


def test_allowlist_files_still_exist() -> None:
    """If an allowlisted file is removed the allowlist should be trimmed."""
    missing = [f for f in _ALLOWLIST_RELATIVE if not (SRC_ROOT / f).is_file()]
    assert not missing, (
        "Allowlist references missing files — remove them from "
        "_ALLOWLIST_RELATIVE: " + ", ".join(sorted(missing))
    )

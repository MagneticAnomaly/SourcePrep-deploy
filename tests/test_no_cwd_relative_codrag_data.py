"""Phase 113 — regression guard against CWD-relative `codrag_data/` literals.

Pre-fix: several modules hardcoded `./codrag_data` as the daemon's
default data dir, so the daemon's on-disk state followed its CWD. The
fix introduced `prep.core.paths.data_dir()` as the single source of
truth. This test fails if any new src file reintroduces the legacy
literal outside a narrow, documented allowlist (the migration helper,
self-ingestion guard strings, and CLI docstrings).

If this test fails, the path you're tempted to reach for is:
`from prep.core.paths import data_dir` (daemon-wide) or
`from prep.core.project_registry import project_index_dir` (per-project).
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "prep"

# Files allowed to reference the legacy literal because their job IS
# to deal with the legacy layout.
_ALLOWLIST_RELATIVE = frozenset({
    # The migration helper literally moves files OUT of ./codrag_data/.
    "core/data_dir_migration.py",
    # The paths module documents the legacy name in its module docstring
    # and in `legacy_cwd_data_dir()`.
    "core/paths.py",
    # repo_profile's self-ingestion guard uses "codrag_data" as a
    # directory basename in the L1 exclude set. Keeping it there
    # protects legacy-layout users during the transition.
    "core/repo_profile.py",
    # watcher.py's module docstring / comments reference the legacy
    # layout; the code path is through data_dir() now.
    "core/watcher.py",
    # config_manager's shim accepts both the new and legacy values
    # on `index_dir` for backwards compat.
    "services/config_manager.py",
})

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

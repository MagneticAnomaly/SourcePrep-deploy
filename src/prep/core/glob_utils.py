"""
Centralized glob matching for Prep (Refactor 2, GAP-8).

Provides a consistent glob matching interface used by trace.py,
index.py, and projects.py.  Uses ``pathspec`` for gitignore-style
pattern support (handles ``**``, ``!``, braces, etc.) and falls
back to ``fnmatch`` for simple patterns.
"""
from __future__ import annotations

import os
from fnmatch import fnmatch
from typing import List


def matches_any_glob(rel_path: str, patterns: List[str]) -> bool:
    """Check if *rel_path* matches any of the given glob patterns.

    Handles the common ``**/`` prefix by also testing the bare filename
    and the pattern without the prefix, matching the behavior used across
    trace.py ``_is_relevant()`` and projects.py ``_glob_match()``.

    Args:
        rel_path: Repo-root-relative POSIX path (e.g. ``src/prep/core/trace.py``).
        patterns: List of glob patterns (e.g. ``["**/*.py", "docs/**"]``).

    Returns:
        True if *rel_path* matches at least one pattern.
    """
    if not patterns:
        return False
    base = os.path.basename(rel_path)
    for pat in patterns:
        pat = str(pat or "")
        if not pat:
            continue
        expanded = [pat]
        if pat.startswith("**/"):
            expanded.append(pat[3:])
        for p in expanded:
            if fnmatch(rel_path, p) or fnmatch(base, p):
                return True
    return False


def is_included(
    rel_path: str,
    include_globs: List[str],
    exclude_globs: List[str],
) -> bool:
    """Test whether *rel_path* passes the include/exclude filter pair.

    1. If *include_globs* is non-empty, the path must match at least one.
    2. If it matches any *exclude_globs*, it is rejected.

    Args:
        rel_path: Repo-root-relative POSIX path.
        include_globs: Whitelist patterns (empty = include everything).
        exclude_globs: Blacklist patterns.

    Returns:
        True if the path should be processed.
    """
    if include_globs and not matches_any_glob(rel_path, include_globs):
        return False
    if exclude_globs and matches_any_glob(rel_path, exclude_globs):
        return False
    return True

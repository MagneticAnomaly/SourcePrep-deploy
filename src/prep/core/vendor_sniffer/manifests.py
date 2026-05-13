from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_GITMODULES_PATH_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")


def parse_gitmodules(root: Path) -> set[str]:
    """Extract submodule paths from <root>/.gitmodules. Returns empty set on missing/malformed."""
    gm = root / ".gitmodules"
    if not gm.is_file():
        return set()
    paths: set[str] = set()
    try:
        for line in gm.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _GITMODULES_PATH_RE.match(line)
            if m:
                paths.add(m.group(1).strip())
    except OSError as e:
        logger.warning("failed to read .gitmodules: %s", e)
    return paths


def parse_root_gitignore_toplevel_dirs(root: Path) -> set[str]:
    """
    Extract top-level directory names from <root>/.gitignore.

    Limited semantics: handles direct dir patterns ("vcpkg", "vcpkg/", "/vcpkg")
    and ignores deep paths, file patterns, negations, and comments. Full gitignore
    semantics are handled elsewhere by the Rust walker; this parser only answers
    'is this exact top-level dir name listed in root .gitignore?'.
    """
    gi = root / ".gitignore"
    if not gi.is_file():
        return set()
    names: set[str] = set()
    try:
        for raw in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Strip negation
            if line.startswith("!"):
                line = line[1:]
            # Strip leading slash
            if line.startswith("/"):
                line = line[1:]
            # Strip trailing slash
            if line.endswith("/"):
                line = line[:-1]
            # Skip deep paths and glob patterns
            if "/" in line or "*" in line or "?" in line or "[" in line:
                continue
            if line:
                names.add(line)
    except OSError as e:
        logger.warning("failed to read .gitignore: %s", e)
    return names

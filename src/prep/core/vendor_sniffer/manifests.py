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

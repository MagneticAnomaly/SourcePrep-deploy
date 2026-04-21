"""Atomic file-write helpers.

Stage workers write output files that are consumed live by other
pipelines, the MCP server, and the dashboard. A mid-write crash (or
cancel) using the naive `open(path, 'w')` pattern leaves the file
truncated or half-populated — downstream readers then see garbled
data instead of the prior valid file.

The helpers in this module write to a sibling temp path, fsync, then
rename over the final path. On the same filesystem (always true for
files under the project's `.codrag/` directory), `os.replace` is an
atomic rename — either the reader sees the old file or the new one,
never a half-file.
"""
from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically replace `path` with `content`.

    Writes to `path + '.tmp.<pid>'`, fsyncs, then `os.replace()`s over
    the destination. Safe against mid-write crashes — the old file is
    either intact or completely replaced by the new one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        raise


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically replace `path` with `content` (binary). See atomic_write_text."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    try:
        with open(tmp, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        raise

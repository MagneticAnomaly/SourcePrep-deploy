"""Canonical filesystem paths for CoDRAG daemon-wide state.

Phase 113 — single source of truth for "where does the CoDRAG
installation on this machine keep its state". Before this module, the
answer was split: `project_registry.codrag_data_dir()` returned
`~/.local/share/codrag/` while `server.py`, `config_manager.py`, and
`build_manager.py` hardcoded `./codrag_data` (CWD-relative). The two
worlds never got unified, leading to fragmented on-disk layout.

Every caller that needs the daemon-wide data directory — CLI, server,
config_manager, build_manager, SQLite store modules, the UI config
loader — must go through `data_dir()`. Callers that need the per-project
index dir still go through `project_registry.project_index_dir(proj)`.

Resolution precedence for `data_dir()`:
  1. `$CODRAG_DATA_DIR` if set. Must be an absolute path — a relative
     value raises at startup, because a CWD-relative "canonical" data
     dir is exactly the bug this module exists to prevent.
  2. `~/.local/share/codrag/` (XDG-style default on Linux/macOS).

The returned path is guaranteed to exist (parents are created).
"""
from __future__ import annotations

import os
from pathlib import Path

_ENV_VAR = "CODRAG_DATA_DIR"
_XDG_DEFAULT = Path.home() / ".local" / "share" / "codrag"


def data_dir() -> Path:
    """Return the canonical daemon-wide data directory, creating it if absent.

    See module docstring for resolution precedence.

    Raises:
        ValueError: if `$CODRAG_DATA_DIR` is set to a non-absolute path.
    """
    env_value = os.environ.get(_ENV_VAR, "").strip()
    if env_value:
        env_path = Path(env_value).expanduser()
        if not env_path.is_absolute():
            raise ValueError(
                f"{_ENV_VAR} must be an absolute path (got {env_value!r}). "
                "A relative data-dir defeats the purpose of having one — the "
                "daemon's on-disk state would follow its CWD."
            )
        env_path.mkdir(parents=True, exist_ok=True)
        return env_path

    _XDG_DEFAULT.mkdir(parents=True, exist_ok=True)
    return _XDG_DEFAULT


def legacy_cwd_data_dir(cwd: Path | None = None) -> Path:
    """Return the legacy `./codrag_data` path (relative to `cwd`).

    Used only by the one-time migration helper. Not for new call sites.
    """
    base = Path(cwd) if cwd is not None else Path.cwd()
    return base / "codrag_data"

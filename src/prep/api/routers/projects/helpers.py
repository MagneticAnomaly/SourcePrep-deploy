"""
Shared helpers for the projects router subpackage.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _srv():
    """Lazy import of server module to avoid circular imports."""
    import prep.server as _s
    return _s


def _get_project_globs(proj, *, use_defaults: bool = True) -> Tuple[List[str], List[str]]:
    """Extract include/exclude globs from project config (Refactor 2, GAP-9).

    Eliminates repeated 6-line boilerplate across watch, coverage, file,
    and search endpoints.

    Args:
        proj: Project object with ``.config`` and ``.mode`` attributes.
        use_defaults: If True, fall back to ``_DEFAULT_UI_CONFIG`` when the
            project has no globs configured.  Set False when callers handle
            their own defaults (e.g. build/search which merge with policy).

    Returns:
        (include_globs, exclude_globs) — both guaranteed to be lists.
    """
    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None

    if use_defaults:
        defaults = _srv()._DEFAULT_UI_CONFIG
        include_globs = list(include_raw) if isinstance(include_raw, list) else list(defaults.get("include_globs") or [])
        exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(defaults.get("exclude_globs") or [])
    else:
        include_globs = list(include_raw) if isinstance(include_raw, list) else []
        exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else []

    # Embedded-mode projects must always exclude their own data directory
    if getattr(proj, "mode", None) == "embedded":
        if "**/.runprep/**" not in exclude_globs:
            exclude_globs.append("**/.runprep/**")

    return include_globs, exclude_globs

"""Phase 135.5 — the single sanctioned walker module.

Every file walk in prep MUST go through one of these two APIs.
Direct imports of `prep_engine.walk_repo` outside this module are
banned by `tests/test_phase135_5_walker_lockdown.py` (Task 7).

Two purpose-driven APIs:

- walk_for_source        — trace pipeline / build / coverage / atlas scans.
                           Always applies the L1 catalog baseline so user
                           config CANNOT bypass system-level excludes.
- walk_for_planning_docs — concept-synthesis grounding. INCLUDES agent
                           dirs (.claude/, .cursor/, etc.) by default —
                           the opposite of walk_for_source.

The L1 catalog is owned by `prep.core.repo_profile.DEFAULT_EXCLUDE_DIR_NAMES`
and `DEFAULT_EXCLUDE_FILE_GLOBS`. To add a new exclude across the project,
update that catalog — the wrapper picks it up unconditionally.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List

import prep_engine

from prep.core.repo_profile import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_GLOBS,
)

# Agent-output dirs that planning docs explicitly INCLUDE
# (the opposite of source walks, which exclude these).
_AGENT_DIRS = frozenset({".claude", ".cursor", ".agents", ".windsurf", ".copilot"})


def _baseline_excludes_for_source(
    user_exclude_globs: List[str] | None,
) -> List[str]:
    """Union the L1 catalog with user-supplied excludes.

    User extends; never replaces. Order is stable: user globs first
    (so they appear first in any diagnostic logging), then catalog
    dirs in sorted order, then catalog file globs.
    """
    merged = list(user_exclude_globs or [])
    for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES):
        pattern = f"**/{d}/**"
        if pattern not in merged:
            merged.append(pattern)
    for pattern in DEFAULT_EXCLUDE_FILE_GLOBS:
        if pattern not in merged:
            merged.append(pattern)
    return merged


def walk_for_source(
    repo_root: Path | str,
    *,
    include_globs: List[str] | None = None,
    user_exclude_globs: List[str] | None = None,
    use_gitignore: bool = False,
    max_file_bytes: int | None = None,
) -> List[Any]:
    """The single sanctioned walker for source-code-style scans.

    Always applies L1 (DEFAULT_EXCLUDE_DIR_NAMES + DEFAULT_EXCLUDE_FILE_GLOBS).
    Caller-supplied `user_exclude_globs` EXTEND the catalog; they never replace it.

    Args:
        repo_root: path to walk (str or Path).
        include_globs: glob patterns to include. None or empty means no
            include filter (engine walks everything not excluded). Callers
            that want only Python should pass `["**/*.py"]`.
        user_exclude_globs: additional excludes from the caller's config.
            Will be unioned with the L1 catalog.
        use_gitignore: reserved for future use (prep_engine does not yet
            expose this as a kwarg; kept in signature for API stability).
        max_file_bytes: skip files larger than this. None = engine default.

    Returns:
        Whatever `prep_engine.walk_repo` returns — typically a list of
        entries with `.path`, `.size`, etc. attributes. Walker is the
        thin shim; consumers handle the entry shape.
    """
    exclude_globs = _baseline_excludes_for_source(user_exclude_globs)
    kwargs: dict = {
        "include_globs": include_globs or [],
        "exclude_globs": exclude_globs,
    }
    if max_file_bytes is not None:
        kwargs["max_file_bytes"] = max_file_bytes
    return prep_engine.walk_repo(str(repo_root), **kwargs)


def walk_for_planning_docs(
    repo_root: Path | str,
    *,
    include_globs: List[str] | None = None,
    include_agent_dirs: bool = True,
    extra_exclude_dir_names: Iterable[str] | None = None,
) -> List[Any]:
    """Walker for concept-synthesis grounding / planning-doc collection.

    By default INCLUDES agent-output dirs (`.claude/`, `.cursor/`, etc.) —
    the opposite of `walk_for_source`. Set `include_agent_dirs=False` to
    behave identically to `walk_for_source` w.r.t. agent dirs.

    Args:
        repo_root: path to walk.
        include_globs: glob patterns; defaults to `["**/*.md", "**/*.markdown"]`
            since this API is for planning-doc collection.
        include_agent_dirs: when True (default), agent-output dirs are NOT
            excluded — they're the whole point of this scan.
        extra_exclude_dir_names: caller-specific dir names to exclude on
            top of the L1 catalog. Used by concept-synthesis grounding to
            drop tests/, worktrees/, etc. (Phase 125c noise reduction).
            These are merged into the exclude pattern set as `**/{name}/**`.
    """
    base_excludes: List[str] = []
    for d in sorted(DEFAULT_EXCLUDE_DIR_NAMES):
        if include_agent_dirs and d in _AGENT_DIRS:
            continue  # explicitly DON'T exclude agent dirs in this mode
        base_excludes.append(f"**/{d}/**")
    base_excludes.extend(DEFAULT_EXCLUDE_FILE_GLOBS)
    if extra_exclude_dir_names:
        for d in sorted(set(extra_exclude_dir_names)):
            pattern = f"**/{d}/**"
            if pattern not in base_excludes:
                base_excludes.append(pattern)
    return prep_engine.walk_repo(
        str(repo_root),
        include_globs=include_globs or ["**/*.md", "**/*.markdown"],
        exclude_globs=base_excludes,
    )

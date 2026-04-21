"""
Per-project singleton wrapper around GitEvidence.

Resolves a GitEvidence instance for a given project root, caches it
in a module-level dict, and gates the whole thing behind the
`git_evidence.enabled` setting. Returns None (not raises) when evidence
is unavailable — all consumers must fail open.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from prep.core.git_evidence import GitEvidence, is_enabled

logger = logging.getLogger(__name__)

_INSTANCES: dict[str, GitEvidence] = {}
_LOCK = threading.Lock()


def _is_git_repo(root: Path) -> bool:
    """Cheap check: does `root` have a .git dir (file for worktrees)?"""
    try:
        return (root / ".git").exists()
    except OSError:
        return False


def _cache_dir_for(repo_root: Path) -> Path:
    """Resolve the evidence cache dir.

    Prefers the embedded `.runprep/` dir if present (tracks with the repo);
    otherwise falls back to the standalone project index dir via
    `project_registry.project_index_dir`; final fallback is `.runprep/` at
    the repo root even if not present.
    """
    embedded = repo_root / ".runprep"
    if embedded.exists():
        return embedded / "git_evidence"

    # Try project_registry.project_index_dir
    try:
        from prep.core.project_registry import ProjectRegistry, project_index_dir
        reg = ProjectRegistry()
        for proj in reg.list_projects():
            if Path(proj.path).resolve() == repo_root.resolve():
                return project_index_dir(proj) / "git_evidence"
    except Exception:
        pass

    return embedded / "git_evidence"


def get_git_evidence(project_root: str | Path) -> GitEvidence | None:
    """Return a GitEvidence instance for the project, or None.

    None is returned when:
    - `git_evidence.enabled` setting is False
    - `project_root` is not a git repo (no `.git/` dir)
    - git is not installed (indirectly — we don't check, but the evidence
      module returns empty results in that case)
    """
    if not is_enabled():
        return None

    root = Path(project_root).resolve()
    if not _is_git_repo(root):
        return None

    key = str(root)
    with _LOCK:
        inst = _INSTANCES.get(key)
        if inst is not None:
            return inst
        cache_dir = _cache_dir_for(root)
        inst = GitEvidence(repo_root=root, cache_dir=cache_dir)
        _INSTANCES[key] = inst
        return inst


def reset_cache() -> None:
    """Drop all cached instances. For tests and full-reset paths."""
    with _LOCK:
        _INSTANCES.clear()

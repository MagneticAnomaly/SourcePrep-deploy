"""
CoDRAG Project Helpers Service — Phase 23 Sprint 16c
=====================================================

**Origin:** Extracted from ``server.py`` (lines ~192–480).

**What this encapsulates:**
  - ``get_registry()``            — ProjectRegistry singleton
  - ``project_to_dict()``         — project serialization
  - ``project_id_for_root()``     — deterministic ID from path
  - ``current_project()``         — legacy singleton project dict
  - ``require_project()``         — project lookup with 404
  - ``project_index_status()``    — index status dict
  - ``project_trace_status()``    — trace status dict
  - ``get_project_watcher()``     — file watcher lookup
  - ``get_project_watcher_status()`` — watcher status dict
  - ``read_json_file()``          — safe JSON file reader
  - ``parse_iso_datetime()``      — ISO datetime parser
  - ``project_activity_payload()``— activity data for dashboard
  - ``build_coverage_tree()``     — coverage tree builder

**Consumers:** projects router, system router, trace router.

**Phase 24 note:**
  ``get_registry()`` will be owned by SM-3 (ProjectLifecycle).
  ``project_index_status`` / ``project_trace_status`` will read from
  SM-4 (Build) and SM-6 (Pipeline) state machines respectively.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prep.api.envelope import ApiException
from prep.core import CodeIndex
from prep.core.project_registry import (
    Project,
    ProjectRegistry,
    project_index_dir,
)
from prep.core.watcher import AutoRebuildWatcher

logger = logging.getLogger(__name__)

# ── Mtime-based staleness cache ────────────────────────────────
# Lightweight filesystem check that works without the watcher.
# Cached per project to avoid scanning on every status poll.
_STALE_CACHE_TTL = 30.0  # seconds — filesystem walk is expensive on large repos
_stale_cache_lock = threading.Lock()
_stale_cache: Dict[str, Tuple[float, bool, Optional[str], int]] = {}  # project_id -> (expires_at, is_stale, stale_since_iso, stale_count)

# ── Registry singleton ──────────────────────────────────────────

_registry: Optional[ProjectRegistry] = None


def get_registry() -> ProjectRegistry:
    global _registry
    if _registry is None:
        _registry = ProjectRegistry()
    return _registry


# ── Project serialization ───────────────────────────────────────

def project_to_dict(proj: Project) -> Dict[str, Any]:
    d = {
        "id": proj.id,
        "name": proj.name,
        "path": proj.path,
        "mode": proj.mode,
        "config": proj.config,
        "created_at": proj.created_at,
        "updated_at": proj.updated_at,
    }
    # Include activity status so the frontend knows if this project
    # is active/inactive/frozen/locked without a separate API call.
    try:
        d["activity_status"] = get_project_activity_status(proj.id)
    except Exception:
        d["activity_status"] = "active"  # safe default
    return d


def project_id_for_root(root: str) -> str:
    h = hashlib.sha256(root.encode("utf-8")).hexdigest()[:8]
    return f"proj_{h}"


def current_project(config: Dict[str, Any], watcher: Optional[Any], server_started_at: str) -> Dict[str, Any] | None:
    """Build a legacy project dict from CLI/global config.
    
    Args:
        config: The server ``_config`` dict.
        watcher: The legacy ``_watcher`` instance (or None).
        server_started_at: ISO timestamp of server start.
    """
    from prep.services.config_manager import load_ui_config
    ui_cfg = load_ui_config(config)
    root = str(ui_cfg.get("repo_root") or "") or str(config.get("repo_root") or "")
    root = root.strip()
    if not root:
        return None

    abs_root = str(Path(root).resolve())
    pid = project_id_for_root(abs_root)
    watch = watcher.status() if watcher is not None else None

    proj_config: Dict[str, Any] = {
        "include_globs": list(ui_cfg.get("include_globs") or []),
        "exclude_globs": list(ui_cfg.get("exclude_globs") or []),
        "max_file_bytes": int(ui_cfg.get("max_file_bytes") or 500_000),
        "hard_limit_bytes": int(ui_cfg.get("hard_limit_bytes") or 100_000_000),
        "trace": {"enabled": False},
        "auto_rebuild": {"enabled": bool((watch or {}).get("enabled", False))},
    }
    if watch is not None and watch.get("debounce_ms") is not None:
        proj_config["auto_rebuild"]["debounce_ms"] = watch.get("debounce_ms")

    return {
        "id": pid,
        "name": Path(abs_root).name or pid,
        "path": abs_root,
        "mode": "standalone",
        "config": proj_config,
        "created_at": server_started_at,
        "updated_at": server_started_at,
    }


def require_project(project_id: str) -> Project:
    reg = get_registry()
    proj = reg.get_project(project_id)
    if proj is None:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )
    return proj


def is_over_project_limit() -> bool:
    """Check if the user has more active projects than their current tier allows."""
    from prep.core.feature_gate import get_feature_limit
    limit = get_feature_limit("projects_max")
    if limit >= 999:
        return False
    reg = get_registry()
    count = sum(1 for p in reg.list_projects() if get_project_activity_status(p.id) == "active")
    return count > limit


# ── Project Activity Status ────────────────────────────────────
# Pro tier: projects have an explicit active/inactive toggle in config.
# Free tier: unlimited projects, but max 3 active. Others must be "archived" (locked).
# Paid tiers (Monthly/Perpetual/Team/Enterprise): all projects are writable
# if config.active is True (default).

# Activity status values:
#   "active"   — full functionality (build, pipeline, watcher, MCP)
#   "inactive" — Pro explicit toggle: no auto-sync, manual-only
#   "archived" — Free tier explicit toggle: locked, requires Pro to unlock

_FREE_ACTIVE_SLOTS = 3

def is_project_archived(project: Project) -> bool:
    """Check if a project is archived."""
    cfg = project.config if isinstance(project.config, dict) else {}
    return cfg.get("archived", False)

def is_project_active(project: Project) -> bool:
    """Check if a project is marked active in its config (Pro tier toggle).

    Defaults to True for backward compatibility — all existing projects
    are active unless explicitly deactivated or archived.
    """
    if is_project_archived(project):
        return False
    cfg = project.config if isinstance(project.config, dict) else {}
    return cfg.get("active", True)


def get_free_tier_slots(
    projects: List[Project],
) -> Dict[str, str]:
    """Determine activity status for each project on the Free tier.

    Projects explicitly marked as 'archived' in config are 'locked'.
    Up to 3 unarchived projects (sorted by updated_at descending) are 'active'.
    Any unarchived projects beyond the limit are forced to 'locked' (must be archived/deleted).

    Returns: { project_id: "active" | "locked" }
    """
    result: Dict[str, str] = {}
    
    # First pass: explicitly archived projects are locked
    unarchived = []
    for proj in projects:
        if is_project_archived(proj):
            result[proj.id] = "locked"
        else:
            unarchived.append(proj)

    # Sort unarchived by updated_at descending (most recent first)
    sorted_unarchived = sorted(
        unarchived,
        key=lambda p: p.updated_at or "",
        reverse=True,
    )

    for i, proj in enumerate(sorted_unarchived):
        if i < _FREE_ACTIVE_SLOTS:
            result[proj.id] = "active"
        else:
            # Over the limit but not explicitly archived - treat as locked
            result[proj.id] = "locked"
            
    return result


def get_project_activity_status(project_id: str) -> str:
    """Get the activity status of a project, respecting the current tier.

    Returns: "active" | "inactive" | "locked"

    - Paid tiers (Pro/Team/Enterprise): checks config.active (default True).
      Returns "active" or "inactive". If a project was archived on Free tier,
      it remains "locked" until explicitly unarchived.
    - Free tier: checks limit and archive status.
      Returns "active" or "locked".
    """
    from prep.core.feature_gate import get_license, Tier

    lic = get_license()
    proj = get_registry().get_project(project_id)
    
    if proj is None:
        return "locked"

    if is_project_archived(proj):
        return "locked"

    if lic.tier >= Tier.MONTHLY:
        # Paid tier: explicit active/inactive toggle
        return "active" if is_project_active(proj) else "inactive"

    # Free tier: slot-based and archive-aware
    projects = get_registry().list_projects()
    slots = get_free_tier_slots(projects)
    return slots.get(project_id, "locked")


def require_project_writable(project_id: str) -> Project:
    """Like require_project(), but also checks that the project is writable.

    Raises 403 for locked projects on Free tier, or inactive projects
    when the operation requires active status.

    Returns the Project if writable.
    """
    proj = require_project(project_id)
    status = get_project_activity_status(project_id)

    if status == "locked":
        raise ApiException(
            status_code=403,
            code="PROJECT_LOCKED",
            message=f"Project '{proj.name}' is locked or archived.",
            hint="Upgrade to Pro to unlock this project, or delete another active project to free up a slot.",
        )
    if status == "inactive":
        raise ApiException(
            status_code=403,
            code="PROJECT_INACTIVE",
            message=f"Project '{proj.name}' is marked as inactive.",
            hint="Activate this project to resume builds and syncing.",
        )

    return proj


# ── Status helpers ──────────────────────────────────────────────

def project_index_status(
    idx: CodeIndex,
    last_build_error: Optional[str] = None,
    project: Optional["Project"] = None,
) -> Dict[str, Any]:
    st = idx.stats()
    last_error = None
    if last_build_error:
        last_error = {"code": "BUILD_FAILED", "message": str(last_build_error)}

    # If CodeIndex is loaded, return its stats directly
    if st.get("loaded"):
        return {
            "exists": True,
            "total_chunks": int(st.get("total_documents") or 0),
            "embedding_dim": int(st.get("embedding_dim") or 0) if st.get("embedding_dim") is not None else None,
            "embedding_model": st.get("model"),
            "last_build_at": st.get("built_at"),
            "build": st.get("build"),
            "last_error": last_error,
            "source": "code_index",
        }

    # CodeIndex not loaded — fall back to KnowledgeIndex (pipeline output).
    # The KnowledgeIndex covers ALL files with enriched descriptions and is
    # built by the crash-resilient pipeline. For projects with no Knowledge
    # Scope files selected, this is the only index available.
    if project is not None:
        try:
            from prep.services.build_manager import build_manager as bm
            know_idx = bm.get_project_knowledge_index(project)
            if know_idx.is_loaded():
                know_st = know_idx.status()
                return {
                    "exists": True,
                    "total_chunks": int(know_st.get("count") or 0),
                    "embedding_dim": None,  # KnowledgeIndex doesn't expose dim in status
                    "embedding_model": know_st.get("model"),
                    "last_build_at": know_st.get("last_build_at"),
                    "build": None,
                    "last_error": last_error,
                    "source": "knowledge",
                }
        except Exception:
            pass

    # Neither index loaded
    return {
        "exists": False,
        "total_chunks": int(st.get("total_documents") or 0),
        "embedding_dim": int(st.get("embedding_dim") or 0) if st.get("embedding_dim") is not None else None,
        "embedding_model": st.get("model"),
        "last_build_at": st.get("built_at"),
        "build": st.get("build"),
        "last_error": last_error,
    }


def project_trace_status(project: Project) -> Dict[str, Any]:
    """Return trace status for a project.

    F-39: previously short-circuited to an empty stub when
    ``config.trace.enabled`` was False, even if the trace files
    existed on disk.  That left the dashboard showing "Initialize
    Trace Graph" for projects that already had a fully-built graph
    (e.g. CoDRAG itself: 21k nodes, 31k edges in trace_nodes.jsonl
    but ``trace.enabled`` was never flipped to True).

    Now we always probe the on-disk index via ``trace_idx.status()``
    and treat the config flag purely as the auto-build preference.
    Existing data is reported regardless of the flag; ``enabled``
    is the config value so the dashboard can still show whether
    auto-rebuilds are on.
    """
    from prep.services.build_manager import build_manager as bm
    cfg = project.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    enabled = bool((trace_cfg or {}).get("enabled", False))

    try:
        trace_idx = bm.get_project_trace_index(project)
        status = trace_idx.status()
    except Exception as e:
        return {
            "enabled": enabled,
            "exists": False,
            "building": False,
            "counts": {"nodes": 0, "edges": 0},
            "last_build_at": None,
            "last_error": str(e),
        }

    status["enabled"] = enabled
    status["building"] = bm.is_project_trace_building(project.id)
    return status


def get_project_watcher(project: Project, watchers: Dict[str, AutoRebuildWatcher]) -> Optional[AutoRebuildWatcher]:
    """Get existing watcher for a project (does not create one)."""
    return watchers.get(project.id)


def get_project_watcher_status(project: Project, watchers: Dict[str, AutoRebuildWatcher]) -> Dict[str, Any]:
    """Get watcher status for a project."""
    watcher = get_project_watcher(project, watchers)
    if watcher is None:
        return {
            "enabled": False,
            "state": "disabled",
            "stale": False,
            "stale_since": None,
            "pending": False,
            "pending_paths_count": 0,
        }
    return watcher.status()


def get_project_syncer(project: Project, syncers: Dict[str, Any]) -> Any:
    """Get or create RemoteSyncService for a project."""
    from prep.services.remote_sync import RemoteSyncService
    if project.id not in syncers:
        syncers[project.id] = RemoteSyncService(Path(project.path))
    return syncers[project.id]


def get_project_sync_status(project: Project, syncers: Dict[str, Any]) -> Dict[str, Any]:
    """Get remote sync status for a project."""
    syncer = get_project_syncer(project, syncers)
    # Ensure config is loaded so enabled state is accurate
    if syncer._config is None:
        syncer.load_config()
        
    # Start polling if enabled and not already polling
    if syncer._config and syncer._config.enabled and syncer._poll_thread is None:
        syncer.start_polling()
        
    return syncer.status_dict()


def check_index_staleness(project: Project, idx: CodeIndex) -> Dict[str, Any]:
    """Lightweight mtime-based staleness check (works without watcher).

    Compares file modification times against the index's ``built_at``
    timestamp.  Results are cached per project for ``_STALE_CACHE_TTL``
    seconds to avoid scanning the filesystem on every status poll.

    Returns dict with ``is_stale``, ``stale_since``, ``stale_count``.
    """
    now = time.monotonic()

    # Check cache first
    with _stale_cache_lock:
        cached = _stale_cache.get(project.id)
        if cached is not None:
            expires_at, is_stale, stale_since, stale_count = cached
            if now < expires_at:
                return {"is_stale": is_stale, "stale_since": stale_since, "stale_count": stale_count}

    # Get built_at based on whether trace pipeline is enabled
    cfg = project.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg.get("trace"), dict) else {}
    trace_enabled = bool(trace_cfg.get("enabled", False))

    built_at_str = None
    if trace_enabled:
        from prep.core.project_registry import project_index_dir
        idx_dir = project_index_dir(project)
        mani = idx_dir / "trace_manifest.json"
        
        if mani.exists():
            try:
                import json
                with open(mani, "r", encoding="utf-8") as f:
                    built_at_str = json.load(f).get("built_at")
            except Exception:
                pass
                
        if not built_at_str:
            result = {"is_stale": False, "stale_since": None, "stale_count": 0}
            with _stale_cache_lock:
                _stale_cache[project.id] = (now + _STALE_CACHE_TTL, False, None, 0)
            return result
    else:
        # Get built_at from legacy index stats
        st = idx.stats()
        built_at_str = st.get("built_at")
        if not built_at_str or not st.get("loaded"):
            result = {"is_stale": False, "stale_since": None, "stale_count": 0}
            with _stale_cache_lock:
                _stale_cache[project.id] = (now + _STALE_CACHE_TTL, False, None, 0)
            return result

    # Parse built_at to epoch
    try:
        ba = str(built_at_str).strip()
        if ba.endswith("Z"):
            ba = ba[:-1] + "+00:00"
        built_dt = datetime.fromisoformat(ba)
        built_epoch = built_dt.timestamp()
    except Exception:
        result = {"is_stale": False, "stale_since": None, "stale_count": 0}
        with _stale_cache_lock:
            _stale_cache[project.id] = (now + _STALE_CACHE_TTL, False, None, 0)
        return result

    # Load include/exclude globs from project config
    cfg = project.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else []
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else []

    repo_root = Path(project.path).resolve()
    if not repo_root.is_dir():
        result = {"is_stale": False, "stale_since": None, "stale_count": 0}
        with _stale_cache_lock:
            _stale_cache[project.id] = (now + _STALE_CACHE_TTL, False, None, 0)
        return result

    # Build pathspec matchers for include/exclude
    try:
        import pathspec
        inc_spec = pathspec.PathSpec.from_lines("gitignore", include_globs) if include_globs else None
        exc_spec = pathspec.PathSpec.from_lines("gitignore", exclude_globs) if exclude_globs else None
    except Exception:
        inc_spec = None
        exc_spec = None

    # Quick dir-prune set
    from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
    prune_dirs = DEFAULT_EXCLUDE_DIR_NAMES

    # Respect included_paths: only check files within the user's selected
    # scope.  Without this, files matching include_globs but outside the
    # selected Knowledge Sources would trigger a false "Stale" badge.
    included_paths_raw = cfg.get("included_paths") if isinstance(cfg, dict) else None
    included_set: Optional[set] = None
    if isinstance(included_paths_raw, list) and included_paths_raw:
        included_set = set(str(p) for p in included_paths_raw if p)

    def _is_in_scope(rel: str) -> bool:
        if included_set is None:
            return True  # No scope restriction — all files are in scope
        if rel in included_set:
            return True
        parts = rel.split("/")
        for i in range(1, len(parts)):
            if "/".join(parts[:i]) in included_set:
                return True
        return False

    stale_count = 0
    earliest_stale_mtime: Optional[float] = None

    for root_dir, dirs, filenames in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in prune_dirs and not d.startswith(".")]
        root_path = Path(root_dir)

        for fname in filenames:
            fpath = root_path / fname
            try:
                rel = fpath.relative_to(repo_root).as_posix()
            except Exception:
                continue

            # Apply include filter
            if inc_spec is not None:
                if not inc_spec.match_file(rel):
                    continue
            # Apply exclude filter
            if exc_spec is not None:
                if exc_spec.match_file(rel):
                    continue

            # Apply included_paths scope filter
            if not _is_in_scope(rel):
                continue

            # Check mtime
            try:
                mtime = fpath.stat().st_mtime
            except OSError:
                continue

            if mtime > built_epoch:
                stale_count += 1
                if earliest_stale_mtime is None or mtime < earliest_stale_mtime:
                    earliest_stale_mtime = mtime

    is_stale = stale_count > 0
    stale_since: Optional[str] = None
    if earliest_stale_mtime is not None:
        stale_since = datetime.fromtimestamp(earliest_stale_mtime, tz=timezone.utc).isoformat()

    with _stale_cache_lock:
        _stale_cache[project.id] = (now + _STALE_CACHE_TTL, is_stale, stale_since, stale_count)

    return {"is_stale": is_stale, "stale_since": stale_since, "stale_count": stale_count}


def invalidate_stale_cache(project_id: str) -> None:
    """Clear cached staleness result for a project (e.g. after a build)."""
    with _stale_cache_lock:
        _stale_cache.pop(project_id, None)


# ── Utility helpers ─────────────────────────────────────────────

def read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


# ── Activity & coverage helpers ─────────────────────────────────

def project_activity_payload(project: Project, weeks: int) -> Dict[str, Any]:
    from prep.services.build_manager import build_manager as bm
    idx = bm.get_project_index(project)
    idx_status = project_index_status(idx, bm.last_build_error.get(project.id), project=project)
    trace_status = project_trace_status(project)

    idx_dir = project_index_dir(project)
    idx_manifest = read_json_file(idx_dir / "manifest.json")
    trace_manifest = read_json_file(idx_dir / "trace_manifest.json")

    start_date = (datetime.now(timezone.utc) - timedelta(days=int(weeks) * 7)).date()
    by_date: Dict[str, Dict[str, Any]] = {}

    def _add(date_str: str, *, embeddings: int = 0, trace: int = 0, builds: int = 0) -> None:
        cur = by_date.get(date_str)
        if cur is None:
            cur = {"date": date_str, "embeddings": 0, "trace": 0, "builds": 0}
            by_date[date_str] = cur
        cur["embeddings"] = int(cur.get("embeddings", 0)) + int(embeddings)
        cur["trace"] = int(cur.get("trace", 0)) + int(trace)
        cur["builds"] = int(cur.get("builds", 0)) + int(builds)

    idx_built_at = (idx_manifest or {}).get("built_at") or idx_status.get("last_build_at")
    idx_dt = parse_iso_datetime(str(idx_built_at) if idx_built_at else None)
    if idx_dt is not None and idx_dt.date() >= start_date and bool(idx_status.get("exists", False)):
        b = (idx_manifest or {}).get("build")
        embedded_files = 0
        if isinstance(b, dict):
            embedded_files = int(b.get("files_embedded") or 0)
        if embedded_files <= 0:
            embedded_files = int(idx_status.get("total_chunks") or 0)
        _add(idx_dt.date().isoformat(), embeddings=embedded_files, builds=1)

    trace_built_at = None
    if isinstance(trace_manifest, dict):
        trace_built_at = trace_manifest.get("built_at")
    if trace_built_at is None and isinstance(trace_status, dict):
        trace_built_at = trace_status.get("last_build_at")
    trace_dt = parse_iso_datetime(str(trace_built_at) if trace_built_at else None)
    if trace_dt is not None and trace_dt.date() >= start_date and bool(trace_status.get("exists", False)):
        counts = (trace_manifest or {}).get("counts") if isinstance(trace_manifest, dict) else None
        nodes = 0
        if isinstance(counts, dict):
            nodes = int(counts.get("nodes") or 0)
        if nodes <= 0:
            nodes = int((trace_status.get("counts") or {}).get("nodes") or 0)
        _add(trace_dt.date().isoformat(), trace=nodes, builds=1)

    days = [by_date[k] for k in sorted(by_date.keys())]
    totals = {
        "embeddings": sum(int(d.get("embeddings", 0)) for d in days),
        "trace": sum(int(d.get("trace", 0)) for d in days),
        "builds": sum(int(d.get("builds", 0)) for d in days),
    }
    return {"days": days, "totals": totals}


def build_coverage_tree(repo_root: Path, include_globs: List[str], exclude_globs: List[str]) -> Dict[str, Any]:
    repo_root = Path(repo_root).expanduser().resolve()
    include_globs = list(include_globs or [])
    exclude_globs = list(exclude_globs or [])

    files = set()
    for pat in include_globs:
        try:
            for p in repo_root.glob(pat):
                files.add(p)
        except Exception:
            continue

    root: Dict[str, Any] = {"name": repo_root.name or "root", "type": "dir", "children": []}

    def _ensure_dir(parent: Dict[str, Any], name: str) -> Dict[str, Any]:
        children = parent.get("children")
        if not isinstance(children, list):
            children = []
            parent["children"] = children
        for c in children:
            if isinstance(c, dict) and c.get("type") == "dir" and c.get("name") == name:
                return c
        node: Dict[str, Any] = {"name": name, "type": "dir", "children": []}
        children.append(node)
        return node

    for p in sorted(files, key=lambda x: str(x)):
        try:
            if not p.is_file():
                continue
            rel_path = str(p.relative_to(repo_root))
        except Exception:
            continue

        parts = list(Path(rel_path).parts)
        if not parts:
            continue

        parent = root
        for part in parts[:-1]:
            parent = _ensure_dir(parent, part)

        status = "excluded" if any(Path(rel_path).match(pat) for pat in exclude_globs) else "indexed"
        children = parent.get("children")
        if not isinstance(children, list):
            children = []
            parent["children"] = children
        children.append({"name": parts[-1], "type": "file", "status": status})

    def _compute(node: Dict[str, Any]) -> tuple[int, int]:
        if node.get("type") != "dir":
            return (1, 1) if node.get("status") == "indexed" else (0, 1)

        indexed = 0
        total = 0
        for child in node.get("children", []) or []:
            if not isinstance(child, dict):
                continue
            i, t = _compute(child)
            indexed += i
            total += t
        node["coverage"] = (indexed / total) if total else 0.0
        return indexed, total

    def _sort(node: Dict[str, Any]) -> None:
        children = node.get("children")
        if not isinstance(children, list):
            return
        children.sort(key=lambda c: (0 if isinstance(c, dict) and c.get("type") == "dir" else 1, str(c.get("name") or "")))
        for child in children:
            if isinstance(child, dict) and child.get("type") == "dir":
                _sort(child)

    _compute(root)
    _sort(root)
    return root

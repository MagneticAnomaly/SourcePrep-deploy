"""
CoDRAG Projects Router — Phase 23 Sprint 15
=============================================

**Origin:** Extracted from ``server.py`` (lines ~694–1916 in the pre-extraction file).

**Endpoints moved here:**
  Project CRUD:
    - GET    /projects
    - POST   /projects
    - GET    /projects/{id}
    - PUT    /projects/{id}
    - DELETE /projects/{id}

  Project Config:
    - PUT  /projects/{id}/path_weights
    - GET  /projects/{id}/path_weights

  Project Status & Activity:
    - GET  /projects/{id}/status
    - GET  /projects/{id}/activity
    - GET  /projects/{id}/coverage

  File Operations:
    - GET  /projects/{id}/file
    - GET  /projects/{id}/files
    - GET  /projects/{id}/roots
    - GET  /projects/{id}/detect-stack

  Watch:
    - POST /projects/{id}/watch/start
    - POST /projects/{id}/watch/stop
    - GET  /projects/{id}/watch/status

  Build & Search:
    - POST /projects/{id}/build
    - POST /projects/{id}/search
    - POST /projects/{id}/context

  Deprecated Legacy:
    - POST /api/code-index/context
    - POST /api/code-index/chunk

**Shared state accessed (from server.py):**
  - ``_require_project``          — project lookup
  - ``_get_registry``             — project registry singleton
  - ``_project_to_dict``          — project serialization
  - ``_project_index_status``     — index status dict
  - ``_project_trace_status``     — trace status dict
  - ``_get_project_index``        — per-project CodeIndex (via BuildManager)
  - ``_get_project_trace_index``  — per-project TraceIndex (via BuildManager)
  - ``_is_project_building``      — build thread check (via BuildManager)
  - ``_start_project_build``      — launch build (via BuildManager)
  - ``_start_project_trace_build``— launch trace build (via BuildManager)
  - ``_get_project_watcher``      — file watcher lookup
  - ``_get_project_watcher_status``— watcher status dict
  - ``_project_activity_payload`` — activity data
  - ``_build_coverage_tree``      — coverage tree builder
  - ``_DEFAULT_UI_CONFIG``        — config defaults
  - ``_config``                   — CLI config
  - ``_project_watchers``         — watcher dict
  - ``_project_indexes``          — index cache (via BuildManager)
  - ``_project_trace_indexes``    — trace cache (via BuildManager)
  - ``_project_build_lock``       — build lock (via BuildManager)
  - ``_project_build_threads``    — build threads (via BuildManager)
  - ``_project_last_build_result``— build results (via BuildManager)
  - ``_project_last_build_error`` — build errors (via BuildManager)
  - ``_project_trace_build_lock`` — trace lock (via BuildManager)
  - ``_project_trace_build_threads``— trace threads (via BuildManager)

**Phase 24 note (State Machines SM-1, SM-4, SM-5):**
  SM-4 (Build Orchestrator) will own the ``/build`` endpoint — it becomes
  a transition request (IDLE → QUEUED → BUILDING) rather than a direct
  thread launch.  SM-5 (AutoRebuildWatcher) will formalize the watch
  start/stop into explicit WatcherPhase transitions.  The ``/status``
  endpoint will read directly from SM-4 and SM-5 state rather than
  querying locks and threads.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok
from codrag.core.feature_gate import (
    get_license, get_feature_limit, require_feature, FeatureGateError,
)
from codrag.core.project_registry import (
    ProjectAlreadyExists, ProjectNotFound, project_index_dir,
)
from codrag.core.repo_policy import (
    load_repo_policy, policy_path_for_index, write_repo_policy,
    _normalize_path_weights,
)

from codrag.core.watcher import AutoRebuildWatcher
from codrag.core import ClaraCompressor, NoopCompressor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _srv():
    """Lazy import of server module to avoid circular imports."""
    import codrag.server as _s
    return _s


# ── Pydantic models ─────────────────────────────────────────────

class BuildRequest(BaseModel):
    project_root: Optional[str] = None
    repo_root: Optional[str] = None
    roots: Optional[List[str]] = None
    include_globs: Optional[List[str]] = None
    exclude_globs: Optional[List[str]] = None
    max_file_bytes: Optional[int] = None
    hard_limit_bytes: Optional[int] = None
    use_gitignore: bool = False


class PolicyRequest(BaseModel):
    repo_root: Optional[str] = None
    force: bool = False


class WatchRequest(BaseModel):
    repo_root: Optional[str] = None
    debounce_ms: Optional[int] = None
    min_rebuild_gap_ms: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    k: int = 8
    min_score: float = 0.15


class ContextRequest(BaseModel):
    query: str
    k: int = 5
    max_chars: int = 6000
    include_sources: bool = True
    include_scores: bool = False
    min_score: float = 0.15
    structured: bool = False
    trace_expand: bool = False  # Follow trace edges to include structurally related code
    trace_max_chars: int = 2000  # Budget for trace-expanded chunks
    compression: str = "none"  # "none" | "clara"
    compression_level: str = "standard"  # "light" | "standard" | "aggressive"
    compression_target_chars: Optional[int] = None
    compression_timeout_s: float = 30.0


class ChunkRequest(BaseModel):
    chunk_id: str


class AddProjectRequest(BaseModel):
    path: str
    name: Optional[str] = None
    mode: str = "standalone"
    index_path: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    path_weights: Optional[Dict[str, float]] = None


class PathWeightsRequest(BaseModel):
    path_weights: Dict[str, float]



class DetectStackResponse(BaseModel):
    recommended_globs: List[str]
    detected_presets: List[str]
    all_presets: Dict[str, List[str]]


# ── Stack detection helpers ───────────────────────────────────────

_STACK_PRESETS = {
    "Web (JS/TS)": ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.html", "**/*.css", "**/*.json"],
    "Python": ["**/*.py", "**/*.ipynb"],
    "iOS (Swift/ObjC)": ["**/*.swift", "**/*.h", "**/*.m", "**/*.mm"],
    "Rust": ["**/*.rs", "**/*.toml"],
    "Go": ["**/*.go", "**/*.mod"],
    "Java/Kotlin": ["**/*.java", "**/*.kt", "**/*.kts", "**/*.gradle"],
    "C/C++": ["**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp", "**/*.cc"],
    "C#": ["**/*.cs"],
    "Ruby": ["**/*.rb"],
    "PHP": ["**/*.php"],
    "Shell": ["**/*.sh", "**/*.bash", "**/*.zsh"],
    "Configuration": ["**/*.yaml", "**/*.yml", "**/*.json", "**/*.toml", "**/*.xml", "**/*.ini", "**/*.env"],
    "Documentation": ["**/*.md", "**/*.markdown", "**/*.txt"],
}

# Map extension to preset keys
_EXT_TO_PRESET = {
    ".js": "Web (JS/TS)", ".jsx": "Web (JS/TS)", ".ts": "Web (JS/TS)", ".tsx": "Web (JS/TS)", ".html": "Web (JS/TS)", ".css": "Web (JS/TS)",
    ".py": "Python", ".ipynb": "Python",
    ".swift": "iOS (Swift/ObjC)", ".m": "iOS (Swift/ObjC)", ".mm": "iOS (Swift/ObjC)",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java/Kotlin", ".kt": "Java/Kotlin",
    ".c": "C/C++", ".cpp": "C/C++", ".h": "C/C++", ".hpp": "C/C++", ".cc": "C/C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sh": "Shell", ".bash": "Shell",
    ".yaml": "Configuration", ".yml": "Configuration", ".json": "Configuration", ".xml": "Configuration", ".toml": "Configuration",
    ".md": "Documentation",
}

def _scan_for_presets(root: Path) -> List[str]:
    """
    Quickly scan the project root for file extensions to determine active presets.
    Skips common heavy directories to be fast.
    """
    detected_presets = set()
    # Limit depth and directories to avoid slow scans in huge monorepos
    ignore_dirs = {
        ".git", "node_modules", ".venv", "venv", "env", "__pycache__", 
        "dist", "build", "target", ".next", ".idea", ".vscode", "vendor"
    }
    
    try:
        # We'll just walk up to 3 levels deep for speed, or until we find enough evidence
        # Actually, os.walk is fine if we prune
        import os
        for dirpath, dirnames, filenames in os.walk(str(root)):
            # Prune ignored dirs
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]
            
            for f in filenames:
                ext = Path(f).suffix.lower()
                if ext in _EXT_TO_PRESET:
                    detected_presets.add(_EXT_TO_PRESET[ext])
            
            # Heuristic: stop early if we have found a lot? 
            # No, keep going to find mixed stacks (e.g. Rust + React)
            pass
    except Exception:
        pass
        
    return list(detected_presets)


# ── Endpoints ────────────────────────────────────────────────────

# =============================================================================
# Project Endpoints
# =============================================================================

@router.get("/projects")
def list_projects() -> Dict[str, Any]:
    reg = _srv()._get_registry()
    projects: List[Dict[str, Any]] = []
    for p in reg.list_projects():
        projects.append(
            {
                "id": p.id,
                "name": p.name,
                "path": p.path,
                "mode": p.mode,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "config": p.config,
            }
        )
    return ok({"projects": projects, "total": len(projects)})


@router.post("/projects")
def add_project(req: AddProjectRequest) -> Dict[str, Any]:
    if req.mode not in ("standalone", "embedded", "custom"):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=f"Invalid mode: {req.mode}")

    # Check project count limit for current tier
    reg = _srv()._get_registry()
    existing_count = len(reg.list_projects())
    max_projects = get_feature_limit("projects_max")
    if existing_count >= max_projects:
        lic = get_license()
        raise FeatureGateError(
            feature="projects_max",
            current_tier=lic.tier.name.lower(),
            required_tier="starter" if max_projects <= 1 else "pro",
        )

    p = Path(str(req.path)).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ApiException(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"Path does not exist: {p}",
        )

    # Validate index_path for custom mode
    custom_index_path: Optional[str] = None
    if req.mode == "custom":
        if not req.index_path:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message="index_path is required for custom mode",
            )
        try:
            ip = Path(req.index_path).expanduser().resolve()
            # We don't necessarily require it to exist yet (we can create it), 
            # but maybe we should ensure parent exists or it's a valid path.
            # For now just resolving it is enough check for basic validity.
            custom_index_path = str(ip)
        except Exception as e:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message=f"Invalid index_path: {e}",
            )

    # Determine defaults based on tier
    lic = get_license()
    # Auto-rebuild is enabled by default for Starter tier and above
    auto_rebuild_default = lic.tier >= 1  # Tier.STARTER = 1

    reg = _srv()._get_registry()
    default_cfg: Dict[str, Any] = {
        "include_globs": list(_srv()._DEFAULT_UI_CONFIG.get("include_globs") or []),
        "exclude_globs": list(_srv()._DEFAULT_UI_CONFIG.get("exclude_globs") or []),
        "max_file_bytes": int(_srv()._DEFAULT_UI_CONFIG.get("max_file_bytes") or 500_000),
        "hard_limit_bytes": int(_srv()._DEFAULT_UI_CONFIG.get("hard_limit_bytes") or 100_000_000),
        "trace": {"enabled": True},  # Cross-reference on by default for all tiers
        "auto_rebuild": {
            "enabled": auto_rebuild_default,
            "debounce_ms": 5000,
        },
    }
    
    if req.mode == "embedded":
        if "**/.codrag/**" not in default_cfg["exclude_globs"]:
            default_cfg["exclude_globs"].append("**/.codrag/**")
    
    # Store custom index path in config if applicable
    if custom_index_path:
        default_cfg["index_path"] = custom_index_path

    if (_srv()._DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms") is not None:
        default_cfg["auto_rebuild"]["debounce_ms"] = int(
            (_srv()._DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms")
        )

    try:
        proj = reg.add_project(path=str(p), name=req.name, mode=req.mode, config=default_cfg)
    except ProjectAlreadyExists:
        raise ApiException(
            status_code=409,
            code="PROJECT_ALREADY_EXISTS",
            message=f"A project already exists at '{p}'",
            hint="Use a different path or remove the existing project first.",
        )

    return ok({"project": _srv()._project_to_dict(proj)})


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    return ok({"project": _srv()._project_to_dict(proj)})


@router.put("/projects/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest) -> Dict[str, Any]:
    reg = _srv()._get_registry()
    try:
        updated = reg.update_project(project_id, name=req.name, config=req.config)
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    if req.path_weights is not None:
        updated = _persist_path_weights(updated, req.path_weights)

    return ok({"project": _srv()._project_to_dict(updated)})


@router.put("/projects/{project_id}/path_weights")
def update_path_weights(project_id: str, req: PathWeightsRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    updated = _persist_path_weights(proj, req.path_weights)
    return ok({"project": _srv()._project_to_dict(updated), "path_weights": updated.config.get("path_weights", {})})


@router.get("/projects/{project_id}/path_weights")
def get_path_weights(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    pw = proj.config.get("path_weights", {})
    return ok({"path_weights": pw})


def _persist_path_weights(proj: Project, raw_weights: Dict[str, float]) -> Project:
    """Normalize and persist path_weights to project config AND repo_policy.json."""
    normalized = _normalize_path_weights(raw_weights)

    # Update project config in SQLite
    reg = _srv()._get_registry()
    new_config = dict(proj.config)
    new_config["path_weights"] = normalized
    updated = reg.update_project(proj.id, config=new_config)

    # Also persist to repo_policy.json on disk so next build picks it up
    idx_dir = project_index_dir(proj)
    pp = policy_path_for_index(idx_dir)
    policy = load_repo_policy(pp)
    if policy is not None:
        policy["path_weights"] = normalized
        write_repo_policy(pp, policy)

    # Hot-update the in-memory manifest so searches use new weights immediately
    idx = _srv()._project_indexes.get(proj.id)
    if idx is not None and idx._manifest:
        cfg = idx._manifest.get("config")
        if isinstance(cfg, dict):
            cfg["path_weights"] = normalized

    return updated


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, purge: bool = False) -> Dict[str, Any]:
    reg = _srv()._get_registry()
    try:
        reg.remove_project(project_id, purge=bool(purge))
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    _srv()._project_indexes.pop(project_id, None)
    _srv()._project_srv()._trace_indexes.pop(project_id, None)
    with _srv()._project_build_lock:
        _srv()._project_build_threads.pop(project_id, None)
        _srv()._project_last_build_result.pop(project_id, None)
        _srv()._project_last_build_error.pop(project_id, None)
    with _srv()._project_trace_build_lock:
        _srv()._project_trace_build_threads.pop(project_id, None)

    return ok({"removed": True, "purged": bool(purge)})


@router.get("/projects/{project_id}/status")
def get_project_status(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    idx = _srv()._get_project_index(proj)

    watch = _srv()._get_project_watcher_status(proj)
    data = {
        "building": _srv()._is_project_building(proj.id),
        "stale": bool(watch.get("stale", False)),
        "stale_since": watch.get("stale_since"),
        "index": _srv()._project_index_status(idx, _srv()._project_last_build_error.get(proj.id)),
        "trace": _srv()._project_trace_status(proj),
        "watch": watch,
    }
    return ok(data)


@router.post("/projects/{project_id}/watch/start")
def start_project_watch(
    project_id: str,
    debounce_ms: int = Query(5000, ge=500, le=60000),
    min_gap_ms: int = Query(2000, ge=500, le=30000),
) -> Dict[str, Any]:
    """Enable auto-rebuild watcher for a project."""
    require_feature("auto_rebuild")
    proj = _srv()._require_project(project_id)
    idx = _srv()._get_project_index(proj)
    
    # Stop existing watcher if any
    existing = _srv()._project_watchers.get(proj.id)
    if existing is not None:
        existing.stop()
    
    def trigger_build(paths: List[str]) -> bool:
        cfg = proj.config or {}
        include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
        exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
        include_globs = list(include_raw) if isinstance(include_raw, list) else None
        exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else None
        max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
        hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)

        started = _srv()._start_project_build(proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes)

        # Also trigger trace rebuild if trace is enabled
        trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
        if bool((trace_cfg or {}).get("enabled", False)):
            _srv()._start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)

        return started
    
    def is_building() -> bool:
        return _srv()._is_project_building(proj.id) or _srv()._is_project_trace_building(proj.id)
    
    watcher = AutoRebuildWatcher(
        repo_root=Path(proj.path),
        index_dir=idx.index_dir,
        on_trigger_build=trigger_build,
        is_building=is_building,
        debounce_ms=debounce_ms,
        min_rebuild_gap_ms=min_gap_ms,
    )
    watcher.start()
    _srv()._project_watchers[proj.id] = watcher
    
    return ok({"enabled": True, "status": watcher.status()})


@router.post("/projects/{project_id}/watch/stop")
def stop_project_watch(project_id: str) -> Dict[str, Any]:
    """Disable auto-rebuild watcher for a project."""
    proj = _srv()._require_project(project_id)
    
    watcher = _srv()._project_watchers.pop(proj.id, None)
    if watcher is not None:
        watcher.stop()
    
    return ok({"enabled": False})


@router.get("/projects/{project_id}/watch/status")
def get_project_watch_status(project_id: str) -> Dict[str, Any]:
    """Get watcher status for a project."""
    proj = _srv()._require_project(project_id)
    return ok(_srv()._get_project_watcher_status(proj))


@router.get("/projects/{project_id}/activity")
def get_project_activity(project_id: str, weeks: int = Query(12, ge=1, le=52)) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    data = _srv()._project_activity_payload(proj, int(weeks))
    return ok(data)


@router.get("/projects/{project_id}/coverage")
def get_project_coverage(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)

    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else list(_srv()._DEFAULT_UI_CONFIG.get("include_globs") or [])
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(_srv()._DEFAULT_UI_CONFIG.get("exclude_globs") or [])

    if proj.mode == "embedded":
        if "**/.codrag/**" not in exclude_globs:
            exclude_globs.append("**/.codrag/**")

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    tree = _srv()._build_coverage_tree(repo_root, include_globs, exclude_globs)
    return ok({"tree": tree})


@router.get("/projects/{project_id}/file")
def get_project_file_content(project_id: str, path: str = Query(..., min_length=1)) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)

    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else list(_srv()._DEFAULT_UI_CONFIG.get("include_globs") or [])
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(_srv()._DEFAULT_UI_CONFIG.get("exclude_globs") or [])
    max_file_bytes = int((cfg.get("max_file_bytes") or 400_000) if isinstance(cfg, dict) else 400_000)

    if proj.mode == "embedded":
        if "**/.codrag/**" not in exclude_globs:
            exclude_globs.append("**/.codrag/**")

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    rel_path = Path(str(path).strip().lstrip("/"))
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path without '..' segments.",
        )

    rel_str = str(rel_path)

    def _glob_match(rel: str, pat: str) -> bool:
        rel = rel.replace("\\", "/")
        pat = str(pat or "")
        if not pat:
            return False
        if fnmatch.fnmatch(rel, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:]):
            return True
        return False

    def _matches_any(rel: str, patterns: List[str]) -> bool:
        for pat in patterns:
            try:
                if _glob_match(rel, str(pat)):
                    return True
            except Exception:
                continue
        return False

    if not _matches_any(rel_str, include_globs):
        raise ApiException(
            status_code=403,
            code="FILE_NOT_INCLUDED",
            message="File is not included by project policy",
            hint="Update include_globs to allow this file.",
        )

    if _matches_any(rel_str, exclude_globs):
        raise ApiException(
            status_code=403,
            code="FILE_EXCLUDED",
            message="File is excluded by project policy",
            hint="Update exclude_globs to allow this file.",
        )

    abs_path = (repo_root / rel_path).resolve()
    if not abs_path.is_relative_to(repo_root):
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path.",
        )

    if not abs_path.exists() or not abs_path.is_file():
        raise ApiException(status_code=404, code="FILE_NOT_FOUND", message="File not found")

    size = abs_path.stat().st_size
    if size > max_file_bytes:
        raise ApiException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds max_file_bytes ({max_file_bytes} bytes)",
            hint="Increase max_file_bytes in project settings or pin a smaller file.",
            details={"max_file_bytes": max_file_bytes, "bytes": size},
        )

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_file_bytes + 1)
    except Exception:
        raise ApiException(status_code=500, code="FILE_READ_FAILED", message="Failed to read file")

    if len(content.encode("utf-8", errors="ignore")) > max_file_bytes:
        raise ApiException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds max_file_bytes ({max_file_bytes} bytes)",
            hint="Increase max_file_bytes in project settings or pin a smaller file.",
            details={"max_file_bytes": max_file_bytes, "bytes": size},
        )

    return ok(
        {
            "file": {
                "path": rel_str,
                "name": abs_path.name,
                "content": content,
                "bytes": int(size),
                "max_file_bytes": int(max_file_bytes),
            }
        }
    )


@router.get("/projects/{project_id}/detect-stack")
def detect_project_stack(project_id: str) -> Dict[str, Any]:
    """Analyze the project to recommend include patterns."""
    proj = _srv()._require_project(project_id)
    detected_presets = _scan_for_presets(Path(proj.path))
    
    recommended_globs = []
    for preset in detected_presets:
        recommended_globs.extend(_STACK_PRESETS.get(preset, []))
        
    return ok({
        "recommended_globs": sorted(list(set(recommended_globs))),
        "detected_presets": sorted(detected_presets),
        "all_presets": _STACK_PRESETS,
    })


@router.get("/projects/{project_id}/roots")
def get_project_roots(project_id: str) -> Dict[str, Any]:
    """Get available root directories for a project."""
    proj = _srv()._require_project(project_id)
    project_root = Path(proj.path).expanduser().resolve()
    
    if not project_root.exists() or not project_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    roots: List[str] = []
    
    # Generic discovery: list all top-level directories except ignored ones
    ignore = {".git", ".venv", "node_modules", "__pycache__", ".next", "dist", "build", ".codrag", ".idea", ".vscode"}
    try:
        for item in sorted(project_root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name in ignore:
                continue
            roots.append(item.name)
    except Exception:
        pass

    return ok({"roots": roots})


@router.get("/projects/{project_id}/files")
def list_project_files(
    project_id: str,
    path: str = "",
    depth: int = 3,
) -> Dict[str, Any]:
    """List files and directories under a project path.

    Parameters
    ----------
    path : str
        Relative path within the project root (empty = project root).
    depth : int
        Maximum recursion depth (default 3, max 10).
    """
    proj = _srv()._require_project(project_id)
    project_root = Path(proj.path).expanduser().resolve()

    if not project_root.exists() or not project_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    # Resolve target directory safely
    target = (project_root / path).resolve()
    # Security: ensure target is within project root
    try:
        target.relative_to(project_root)
    except ValueError:
        raise ApiException(status_code=400, code="PATH_OUTSIDE_PROJECT", message="Path is outside project root")

    if not target.exists() or not target.is_dir():
        raise ApiException(status_code=400, code="PATH_NOT_FOUND", message=f"Directory not found: {path}")

    ignore = {".git", ".venv", "venv", "node_modules", "__pycache__", ".next", "dist",
              "build", ".codrag", ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
              ".tox", ".eggs", "*.egg-info", ".DS_Store"}
    depth = min(max(depth, 1), 10)

    # Build per-file chunk count from index documents for status annotation
    idx = _srv()._get_project_index(proj)
    chunks_by_file: Dict[str, int] = {}
    if idx.is_loaded() and idx._documents:
        for doc in idx._documents:
            sp = str(doc.get("source_path") or "")
            if sp:
                chunks_by_file[sp] = chunks_by_file.get(sp, 0) + 1

    def _is_ignored(name: str) -> bool:
        if name in ignore or (name.startswith(".") and name != ".env"):
            return True
        if any(name.endswith(suf) for suf in (".egg-info", ".pyc", ".pyo")):
            return True
        return False

    def _has_visible_children(directory: Path) -> bool:
        """Check if a directory has any non-ignored children."""
        try:
            for item in directory.iterdir():
                if not _is_ignored(item.name):
                    return True
        except PermissionError:
            pass
        return False

    def _scan(directory: Path, current_depth: int, rel_prefix: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        try:
            items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return entries

        for item in items:
            name = item.name
            if _is_ignored(name):
                continue

            child_rel = f"{rel_prefix}/{name}" if rel_prefix else name

            if item.is_dir():
                if current_depth < depth:
                    children = _scan(item, current_depth + 1, child_rel)
                    entries.append({
                        "name": name,
                        "type": "folder",
                        "children": children,
                    })
                else:
                    # Depth limit reached — signal whether folder has children
                    entry: Dict[str, Any] = {
                        "name": name,
                        "type": "folder",
                        "children": [],
                    }
                    if _has_visible_children(item):
                        entry["has_children"] = True
                    entries.append(entry)
            elif item.is_file():
                file_entry: Dict[str, Any] = {
                    "name": name,
                    "type": "file",
                }
                chunk_count = chunks_by_file.get(child_rel)
                if chunk_count is not None:
                    file_entry["status"] = "indexed"
                    file_entry["chunks"] = chunk_count
                entries.append(file_entry)
        return entries

    # Build the relative prefix for the scan root
    rel_prefix = path  # empty string for project root, else the subpath
    tree = _scan(target, 1, rel_prefix)
    return ok({"path": path, "tree": tree})


@router.post("/projects/{project_id}/build")
def build_project(project_id: str, full: bool = False) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)

    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else None
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else None
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
    hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)

    if proj.mode == "embedded":
        if exclude_globs is None:
            exclude_globs = []
        if "**/.codrag/**" not in exclude_globs:
            exclude_globs.append("**/.codrag/**")

    started = _srv()._start_project_build(proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes)
    if not started:
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Build already running")

    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if bool((trace_cfg or {}).get("enabled", False)):
        _srv()._start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)
    return ok({"started": True, "building": True, "build_id": None})


@router.post("/projects/{project_id}/search")
def search_project(project_id: str, req: SearchRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _srv()._get_project_index(proj)
    if not idx.is_loaded():
        raise ApiException(
            status_code=409,
            code="INDEX_NOT_BUILT",
            message="Index has not been built yet",
            hint="Run a build first.",
        )

    results = idx.search(req.query, k=req.k, min_score=req.min_score)
    out: List[Dict[str, Any]] = []
    for r in results:
        d = r.doc
        content = str(d.get("content") or "")
        span = d.get("span")
        if not isinstance(span, dict) or "start_line" not in span or "end_line" not in span:
            span = {"start_line": 1, "end_line": 1}
        out.append(
            {
                "chunk_id": str(d.get("id") or ""),
                "source_path": str(d.get("source_path") or ""),
                "span": span,
                "preview": content[:200],
                "score": float(r.score),
            }
        )
    return ok({"results": out})


def _get_compressor(compression: str) -> "ContextCompressor":
    """Get the appropriate compressor based on the compression parameter."""
    if compression == "clara":
        clara_url = str(_srv()._config.get("clara_url", ClaraCompressor.DEFAULT_URL))
        return ClaraCompressor(base_url=clara_url)
    return NoopCompressor()


def _apply_compression(
    context_str: str,
    req: ContextRequest,
) -> Dict[str, Any]:
    """Apply compression to context string and return compression metadata."""
    if req.compression == "none":
        return {"context": context_str, "compression": None}

    if req.compression == "clara":
        require_feature("clara_compression")

    compressor = _get_compressor(req.compression)
    budget = req.compression_target_chars or req.max_chars
    result = compressor.compress(
        context_str,
        query=req.query,
        budget_chars=budget,
        level=req.compression_level,
        timeout_s=req.compression_timeout_s,
    )

    compression_meta = {
        "enabled": True,
        "mode": req.compression,
        "level": req.compression_level,
        "input_chars": result.input_chars,
        "output_chars": result.output_chars,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "compression_ratio": result.compression_ratio,
        "timing_ms": round(result.timing_ms, 1),
        "error": result.error,
    }

    return {"context": result.compressed, "compression": compression_meta}


@router.post("/projects/{project_id}/context")
def context_project(project_id: str, req: ContextRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _srv()._get_project_index(proj)
    if not idx.is_loaded():
        raise ApiException(
            status_code=409,
            code="INDEX_NOT_BUILT",
            message="Index has not been built yet",
            hint="Run a build first.",
        )

    # Resolve trace index for trace expansion
    trace_idx = None
    if req.trace_expand:
        require_feature("mcp_trace_expand")
        cfg = proj.config or {}
        trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
        if bool((trace_cfg or {}).get("enabled", False)):
            try:
                ti = _srv()._get_project_srv()._trace_index(proj)
                if ti.exists():
                    if not ti.is_loaded():
                        ti.load()
                    trace_idx = ti
            except Exception:
                pass  # Graceful: fall back to non-expanded context

    if not req.structured:
        ctx = idx.get_context(
            req.query,
            k=req.k,
            max_chars=req.max_chars,
            include_sources=req.include_sources,
            include_scores=req.include_scores,
            min_score=req.min_score,
        )

        comp = _apply_compression(ctx, req)
        resp: Dict[str, Any] = {"context": comp["context"]}
        if comp["compression"] is not None:
            resp["compression"] = comp["compression"]
        return ok(resp)

    # Structured context: use trace expansion if available
    if trace_idx is not None:
        result = idx.get_context_with_trace_expansion(
            req.query,
            trace_index=trace_idx,
            k=req.k,
            max_chars=req.max_chars,
            min_score=req.min_score,
            max_additional_chars=req.trace_max_chars,
        )
        context_str = str(result.get("context") or "")
        comp = _apply_compression(context_str, req)
        resp_data: Dict[str, Any] = {
            "context": comp["context"],
            "chunks": result.get("chunks", []),
            "total_chars": len(comp["context"]),
            "estimated_tokens": len(comp["context"]) // 4,
            "trace_expanded": result.get("trace_expanded", False),
            "trace_nodes_added": result.get("trace_nodes_added", 0),
        }
        if comp["compression"] is not None:
            resp_data["compression"] = comp["compression"]
        return ok(resp_data)

    results = idx.search(req.query, k=req.k, min_score=req.min_score)
    parts: List[str] = []
    chunks: List[Dict[str, Any]] = []
    total = 0

    for r in results:
        d = r.doc
        chunk_id = str(d.get("id") or "")
        source_path = str(d.get("source_path") or "")
        section = str(d.get("section") or "")
        span = d.get("span")
        if not isinstance(span, dict) or "start_line" not in span or "end_line" not in span:
            span = {"start_line": 1, "end_line": 1}

        header_bits: List[str] = []
        if section:
            header_bits.append(section)
        if source_path:
            header_bits.append(f"@{source_path}")
        header = " | ".join(header_bits) if header_bits else source_path

        sep = "\n\n---\n\n" if parts else ""
        remaining = int(req.max_chars) - total
        if remaining <= 0 or len(sep) >= remaining:
            break

        prefix = f"[{header}]\n" if header else ""
        allowed = remaining - len(sep)
        if len(prefix) >= allowed:
            break

        text = str(d.get("content") or "")
        if len(prefix) + len(text) > allowed:
            text_allowed = allowed - len(prefix)
            if text_allowed > 200:
                text = text[: max(0, text_allowed - 3)] + "..."
            else:
                break

        block = prefix + text
        parts.append(sep + block)
        total += len(sep) + len(block)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_path": source_path,
                "span": span,
                "score": float(r.score),
                "text": text,
            }
        )
        if text.endswith("..."):
            break

    context_str = "".join(parts)

    comp = _apply_compression(context_str, req)
    resp_data: Dict[str, Any] = {
        "context": comp["context"],
        "chunks": chunks,
        "total_chars": len(comp["context"]),
        "estimated_tokens": len(comp["context"]) // 4,
    }
    if comp["compression"] is not None:
        resp_data["compression"] = comp["compression"]
    return ok(resp_data)




@router.post("/api/code-index/context", deprecated=True)
def context(req: ContextRequest, response: Response):
    """Get assembled context for LLM injection.
    
    DEPRECATED: Use POST /projects/{project_id}/context instead.
    This endpoint uses a global singleton index and does not support multi-project.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-06-01"
    response.headers["Link"] = '</projects/{project_id}/context>; rel="successor-version"'
    logger.warning("DEPRECATED: /api/code-index/context called - migrate to /projects/{id}/context")
    
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _srv()._get_index()
    
    # 1. Retrieve Context
    if req.structured:
        # Structured result (chunks list)
        data = idx.get_context_structured(
            req.query,
            k=req.k,
            max_chars=req.max_chars,
            min_score=req.min_score,
        )
        ctx_text = data["context"]
    else:
        # Plain text result
        policy = idx.query_policy(req.query)
        ctx_text = idx.get_context(
            req.query,
            k=req.k,
            max_chars=req.max_chars,
            include_sources=req.include_sources,
            include_scores=req.include_scores,
            min_score=req.min_score,
        )
        data = {"context": ctx_text, "meta": {"query": req.query, "policy": policy}}

    # 2. Trace Expansion (if requested)
    if req.trace_expand and _srv()._trace_index:
        try:
            # Ensure trace index is loaded
            if not _srv()._trace_index.is_loaded():
                _srv()._trace_index.load()
            
            # Use trace expansion for structured results
            result = idx.get_context_with_trace_expansion(
                req.query,
                trace_index=_srv()._trace_index,
                k=req.k,
                max_chars=req.max_chars,
                min_score=req.min_score,
                max_additional_chars=req.trace_max_chars,
            )
            ctx_text = str(result.get("context") or "")
            data = {
                "context": ctx_text,
                "chunks": result.get("chunks", []),
                "trace_expanded": result.get("trace_expanded", False),
                "trace_nodes_added": result.get("trace_nodes_added", 0),
            }
            if "meta" not in data:
                data["meta"] = {"query": req.query}
        except Exception:
            pass  # Graceful fallback: use non-expanded context

    # 3. Compression (CLaRa)
    if req.compression == "clara" and ctx_text:
        ui_cfg = _srv()._load_ui_config()
        clara_cfg = (ui_cfg.get("llm_config") or {}).get("clara") or {}
        clara_url = clara_cfg.get("remote_url") or _srv()._config.get("clara_url") or ClaraCompressor.DEFAULT_URL
        
        compressor = ClaraCompressor(base_url=str(clara_url), timeout_s=req.compression_timeout_s)
        
        # Calculate budget if not explicit
        budget = req.compression_target_chars
        if not budget:
            # Default to 50% of max_chars or length? 
            # Usually we want to fit into LLM context. 
            # If max_chars was high (e.g. 20k) and we want to fit in 4k...
            # For now, let CLaRa decide (budget=0) or use defaults.
            budget = 0
            
        res = compressor.compress(
            ctx_text,
            query=req.query,
            budget_chars=budget or 0,
            level=req.compression_level
        )
        
        data["context"] = res.compressed
        if "meta" not in data:
            data["meta"] = {}
        data["meta"]["compression"] = {
            "provider": "clara",
            "original_chars": res.input_chars,
            "compressed_chars": res.output_chars,
            "ratio": res.compression_ratio,
            "time_ms": res.timing_ms,
            "error": res.error
        }

    return ok(data)


@router.post("/api/code-index/chunk", deprecated=True)
def chunk(req: ChunkRequest, response: Response):
    """Get a specific chunk by ID.
    
    DEPRECATED: Use POST /projects/{project_id}/search instead.
    This endpoint uses a global singleton index and does not support multi-project.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-06-01"
    logger.warning("DEPRECATED: /api/code-index/chunk called - migrate to /projects/{id}/search")
    
    idx = _srv()._get_index()
    doc = idx.get_chunk(req.chunk_id)
    if doc is None:
        raise ApiException(status_code=404, code="CHUNK_NOT_FOUND", message="Chunk not found")
    return ok({"chunk": doc})



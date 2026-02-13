"""
CoDRAG FastAPI server.

Main HTTP API for the CoDRAG daemon.

Usage:
    python -m codrag.server --repo-root /path/to/repo --index-dir ./codrag_data --port 8400
"""

from __future__ import annotations

import base64
import argparse
import fnmatch
import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codrag import __version__
from codrag.api.envelope import ApiException, install_api_exception_handlers, ok
from codrag.core import CodeIndex, OllamaEmbedder, NativeEmbedder, ClaraCompressor, NoopCompressor, KnowledgeIndex
from codrag.core.events import get_event_bus, BroadcastLogHandler, get_progress_manager
from codrag.core.project_registry import (
    Project,
    ProjectAlreadyExists,
    ProjectNotFound,
    ProjectRegistry,
    project_index_dir,
)
from codrag.core.repo_policy import (
    ensure_repo_policy,
    load_repo_policy,
    policy_path_for_index,
    write_repo_policy,
    _normalize_path_weights,
)
from codrag.core.repo_profile import profile_repo
from codrag.core.trace import TraceBuilder, TraceIndex, compute_trace_coverage
from codrag.core.feature_gate import (
    get_license, check_feature, get_feature_limit, require_feature, clear_license_cache, FeatureGateError,
)
from codrag.core.licensing import verify_license_key
from codrag.core.watcher import AutoRebuildWatcher
from codrag.core.model_readiness import (
    ModelStatus,
    get_model_status,
    ensure_model_ready,
    ollama_model_loaded,
    ollama_ensure_ready,
)
from codrag.mcp_config import generate_mcp_configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CoDRAG",
    description="Code Documentation and RAG - Multi-project semantic search platform",
    version=__version__,
)
install_api_exception_handlers(app)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    import asyncio
    
    # Initialize EventBus with running loop for thread-safe dispatch
    bus = get_event_bus()
    loop = asyncio.get_running_loop()
    bus.set_loop(loop)
    
    # Attach log handler to capture root logs and broadcast via SSE.
    # Root logger defaults to WARNING — lower it so INFO messages
    # (build progress, model readiness, etc.) reach the handler.
    root_logger = logging.getLogger()
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    handler = BroadcastLogHandler(bus)
    handler.setLevel(logging.INFO)  # Don't broadcast DEBUG noise
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Initialize ProgressManager (ensure it's created)
    get_progress_manager()
    
    logger.info("CoDRAG EventBus initialized")


@app.exception_handler(FeatureGateError)
async def _feature_gate_handler(request, exc: FeatureGateError):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "FEATURE_GATED",
                "message": str(exc),
                "hint": f"Upgrade to {exc.required_tier} at https://codrag.io/pricing",
                "details": {
                    "feature": exc.feature,
                    "current_tier": exc.current_tier,
                    "required_tier": exc.required_tier,
                },
            },
        },
    )


# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins to rule out CORS issues
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Build Manager (Phase 23 Sprint 14) ────────────────────────────
# All index caches, build threads, and locks live in the BuildManager
# singleton. Module-level aliases below keep backward compatibility
# with routers that do `from codrag.server import _get_project_index`.
from codrag.services.build_manager import build_manager as _bm

# Global state (non-build)
_config: Dict[str, Any] = {}
_watcher: Optional[AutoRebuildWatcher] = None
_SERVER_STARTED_AT = datetime.now(timezone.utc).isoformat()
_registry: Optional[ProjectRegistry] = None
_project_watchers: Dict[str, AutoRebuildWatcher] = {}

# ── BuildManager aliases (backward compat for routers) ───────────
_index = None  # legacy — use _bm.legacy_index
_trace_index = None  # legacy — use _bm.legacy_trace_index
_project_indexes = _bm.project_indexes
_project_trace_indexes = _bm.project_trace_indexes
_project_knowledge_indexes = _bm.project_knowledge_indexes
_project_build_lock = _bm.build_lock
_project_build_threads = _bm.build_threads
_project_last_build_result = _bm.last_build_result
_project_last_build_error = _bm.last_build_error
_project_trace_build_lock = _bm.trace_build_lock
_project_trace_build_threads = _bm.trace_build_threads
_project_knowledge_build_lock = _bm.knowledge_build_lock
_project_knowledge_build_threads = _bm.knowledge_build_threads


_DEFAULT_UI_CONFIG: Dict[str, Any] = {
    "repo_root": "",
    "core_roots": [],
    "working_roots": [],
    "include_globs": [
        # Documentation & Data
        "**/*.md", "**/*.txt", "**/*.json", "**/*.yaml", "**/*.yml", "**/*.toml", "**/*.xml", "**/*.csv", "**/*.tsv",
        "**/*.sql", "**/*.graphql", "**/*.gql", "**/*.proto",
        
        # Web
        "**/*.html", "**/*.css", "**/*.scss", "**/*.less", "**/*.sass",
        "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.mjs", "**/*.cjs", "**/*.vue", "**/*.svelte", "**/*.astro",
        
        # Systems & Low Level
        "**/*.c", "**/*.h", "**/*.cpp", "**/*.hpp", "**/*.cc", "**/*.cxx", "**/*.hh", "**/*.hxx", "**/*.m", "**/*.mm",
        "**/*.rs", "**/*.go", "**/*.swift", "**/*.java", "**/*.kt", "**/*.kts", "**/*.scala", "**/*.sc",
        
        # Scripting & Backend
        "**/*.py", "**/*.pyi", "**/*.rb", "**/*.php", "**/*.pl", "**/*.pm", "**/*.lua", "**/*.tcl",
        "**/*.sh", "**/*.bash", "**/*.zsh", "**/*.fish", "**/*.ps1", "**/*.bat", "**/*.cmd",
        
        # .NET
        "**/*.cs", "**/*.fs", "**/*.vb", "**/*.cshtml", "**/*.aspx",
        
        # Functional
        "**/*.hs", "**/*.lhs", "**/*.ex", "**/*.exs", "**/*.erl", "**/*.hrl", "**/*.clj", "**/*.cljs", "**/*.cljc", "**/*.edn", "**/*.lisp", "**/*.lsp", "**/*.scm", "**/*.ss", "**/*.rkt", "**/*.ml", "**/*.mli", "**/*.elm",
        
        # Mobile
        "**/*.dart",
        
        # Data Science
        "**/*.r", "**/*.R", "**/*.jl", "**/*.ipynb",
        
        # Config & DevOps
        "**/*.cfg", "**/*.ini", "**/*.conf", "**/*.properties", "**/*.env", "**/*.env.*",
        "**/Dockerfile", "**/*.dockerfile", "**/Makefile", "**/*.mk", "**/CMakeLists.txt", "**/*.cmake",
        "**/*.gradle", "**/*.tf", "**/*.tfvars", "**/*.hcl", "**/*.sol"
    ],
    "exclude_globs": [
        "**/.git/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
        "**/.next/**",
        "**/*.map",
        "**/*.lock",
    ],
    "max_file_bytes": 500_000,  # Threshold for full indexing (above this = summary only)
    "hard_limit_bytes": 100_000_000,  # 100MB hard limit (above this = ignored)
    "trace": {"enabled": False},
    "auto_rebuild": {"enabled": False, "debounce_ms": 5000},
    "llm_config": None,  # Will be populated with defaults if missing
    "deep_analysis": {
        "mode": "manual",
        "threshold_percent": 20,
        "frequency": "weekly",
        "day_of_week": 0,
        "hour": 2,
        "budget_max_tokens": 50000,
        "budget_max_minutes": 30,
        "budget_max_items": 100,
        "priority": "lowest_confidence",
    },
}


def _ui_config_path() -> Path:
    index_dir = Path(_config.get("index_dir", "./codrag_data"))
    return index_dir / "ui_config.json"


def _default_ui_config() -> Dict[str, Any]:
    repo_root = str(_config.get("repo_root") or "")

    cfg: Dict[str, Any] = dict(_DEFAULT_UI_CONFIG)
    cfg["repo_root"] = repo_root

    if repo_root:
        cfg["core_roots"] = []
# Default LLM Config
    ollama_url = str(_config.get("ollama_url") or "http://localhost:11434")
    model = str(_config.get("model") or "nomic-embed-text")
    
    cfg["llm_config"] = {
        "saved_endpoints": [
            {
                "id": "default_ollama",
                "name": "Default Ollama",
                "provider": "ollama",
                "url": ollama_url,
            }
        ],
        "embedding": {
            "source": "huggingface",
            "hf_repo_id": "nomic-ai/nomic-embed-text-v1.5",
            "hf_downloaded": NativeEmbedder().is_available(),
            "endpoint_id": "default_ollama",
            "model": model,
        },
        "small_model": {
            "enabled": False,
            "endpoint_id": "",
            "model": "",
        },
        "large_model": {
            "enabled": False,
            "endpoint_id": "",
            "model": "",
        },
        "clara": {
            "enabled": False,
            "source": "huggingface",
            "hf_repo_id": "apple/CLaRa-7B-Instruct",
        }
    }

    
    return cfg


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge update dict into base dict."""
    for k, v in update.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _load_ui_config() -> Dict[str, Any]:
    path = _ui_config_path()
    data: Optional[Dict[str, Any]] = None
    if path.exists():
        try:
            raw = json.loads(path.read_text())
            if isinstance(raw, dict):
                data = raw
        except Exception:
            data = None

    cfg = _default_ui_config()
    if data:
        # Top-level merge
        for key in [
            "repo_root",
            "core_roots",
            "working_roots",
            "include_globs",
            "exclude_globs",
            "max_file_bytes",
            "trace",
            "auto_rebuild",
            "ui_preferences",
            "module_layout",
        ]:
            if key in data:
                cfg[key] = data[key]
        
        # Deep merge for llm_config to preserve defaults for missing fields
        if "llm_config" in data and isinstance(data["llm_config"], dict):
            # Ensure llm_config exists in cfg (it should from default)
            if "llm_config" not in cfg or not isinstance(cfg["llm_config"], dict):
                cfg["llm_config"] = {}
            _deep_merge(cfg["llm_config"], data["llm_config"])

        # Deep merge for deep_analysis schedule config
        if "deep_analysis" in data and isinstance(data["deep_analysis"], dict):
            if "deep_analysis" not in cfg or not isinstance(cfg["deep_analysis"], dict):
                cfg["deep_analysis"] = {}
            _deep_merge(cfg["deep_analysis"], data["deep_analysis"])
            
    return cfg


def _save_ui_config(cfg: Dict[str, Any]) -> None:
    path = _ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))


def _get_registry() -> ProjectRegistry:
    global _registry
    if _registry is None:
        _registry = ProjectRegistry()
    return _registry


def _project_to_dict(proj: Project) -> Dict[str, Any]:
    return {
        "id": proj.id,
        "name": proj.name,
        "path": proj.path,
        "mode": proj.mode,
        "config": proj.config,
        "created_at": proj.created_at,
        "updated_at": proj.updated_at,
    }


def _project_id_for_root(root: str) -> str:
    h = hashlib.sha256(root.encode("utf-8")).hexdigest()[:8]
    return f"proj_{h}"


def _current_project() -> Dict[str, Any] | None:
    ui_cfg = _load_ui_config()
    root = str(ui_cfg.get("repo_root") or "") or str(_config.get("repo_root") or "")
    root = root.strip()
    if not root:
        return None

    abs_root = str(Path(root).resolve())
    project_id = _project_id_for_root(abs_root)
    watch = _watcher.status() if _watcher is not None else None

    config: Dict[str, Any] = {
        "include_globs": list(ui_cfg.get("include_globs") or []),
        "exclude_globs": list(ui_cfg.get("exclude_globs") or []),
        "max_file_bytes": int(ui_cfg.get("max_file_bytes") or 500_000),
        "hard_limit_bytes": int(ui_cfg.get("hard_limit_bytes") or 100_000_000),
        "trace": {"enabled": False},
        "auto_rebuild": {"enabled": bool((watch or {}).get("enabled", False))},
    }
    if watch is not None and watch.get("debounce_ms") is not None:
        config["auto_rebuild"]["debounce_ms"] = watch.get("debounce_ms")

    return {
        "id": project_id,
        "name": Path(abs_root).name or project_id,
        "path": abs_root,
        "mode": "standalone",
        "config": config,
        "created_at": _SERVER_STARTED_AT,
        "updated_at": _SERVER_STARTED_AT,
    }


def _require_project(project_id: str) -> Project:
    reg = _get_registry()
    proj = reg.get_project(project_id)
    if proj is None:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )
    return proj


def _project_index_status(idx: CodeIndex, last_build_error: Optional[str] = None) -> Dict[str, Any]:
    st = idx.stats()
    last_error = None
    if last_build_error:
        last_error = {"code": "BUILD_FAILED", "message": str(last_build_error)}

    return {
        "exists": bool(st.get("loaded", False)),
        "total_chunks": int(st.get("total_documents") or 0),
        "embedding_dim": int(st.get("embedding_dim") or 0) if st.get("embedding_dim") is not None else None,
        "embedding_model": st.get("model"),
        "last_build_at": st.get("built_at"),
        "build": st.get("build"),
        "last_error": last_error,
    }


def _project_trace_status(project: Project) -> Dict[str, Any]:
    cfg = project.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    enabled = bool((trace_cfg or {}).get("enabled", False))

    if not enabled:
        return {
            "enabled": False,
            "exists": False,
            "building": False,
            "counts": {"nodes": 0, "edges": 0},
            "last_build_at": None,
            "last_error": None,
        }

    trace_idx = _get_project_trace_index(project)
    status = trace_idx.status()
    status["enabled"] = True
    status["building"] = _is_project_trace_building(project.id)
    return status


def _get_project_watcher(project: Project) -> Optional[AutoRebuildWatcher]:
    """Get existing watcher for a project (does not create one)."""
    return _project_watchers.get(project.id)


def _get_project_watcher_status(project: Project) -> Dict[str, Any]:
    """Get watcher status for a project."""
    watcher = _get_project_watcher(project)
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


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
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


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
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


def _project_activity_payload(project: Project, weeks: int) -> Dict[str, Any]:
    idx = _get_project_index(project)
    idx_status = _project_index_status(idx, _project_last_build_error.get(project.id))
    trace_status = _project_trace_status(project)

    idx_dir = project_index_dir(project)
    idx_manifest = _read_json_file(idx_dir / "manifest.json")
    trace_manifest = _read_json_file(idx_dir / "trace_manifest.json")

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
    idx_dt = _parse_iso_datetime(str(idx_built_at) if idx_built_at else None)
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
    trace_dt = _parse_iso_datetime(str(trace_built_at) if trace_built_at else None)
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


def _build_coverage_tree(repo_root: Path, include_globs: List[str], exclude_globs: List[str]) -> Dict[str, Any]:
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


def _get_trace_index() -> TraceIndex:
    global _trace_index
    if _trace_index is None:
        index_dir = Path(_config.get("index_dir") or "./codrag_data")
        _trace_index = TraceIndex(index_dir)
    return _trace_index


def _is_trace_building() -> bool:
    global _trace_build_thread
    return _trace_build_thread is not None and _trace_build_thread.is_alive()


def _start_trace_build(repo_root: str, include_globs: Optional[List[str]] = None, exclude_globs: Optional[List[str]] = None) -> bool:
    global _trace_build_thread, _trace_index
    
    if _is_trace_building():
        return False
    
    index_dir = Path(_config.get("index_dir") or "./codrag_data")
    
    def build_task():
        global _trace_index
        pm = get_progress_manager()
        task_id = pm.start_task("trace_build", Path(repo_root).name)

        def progress_callback(msg: str, current: int, total: int):
            pm.update(task_id, msg, current, total)
            logger.info(f"[Trace] {msg} ({current}/{total})")

        try:
            idx_dir = project_index_dir(project)
            logger.info(f"Building trace index for {project.id} in {idx_dir}")
            builder = TraceBuilder(
                repo_root=Path(repo_root),
                index_dir=index_dir,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
            )
            builder.build(progress_callback=progress_callback)
            _trace_index = TraceIndex(index_dir)
            _trace_index.load()
            logger.info("Trace build completed successfully")
            pm.finish_task(task_id, success=True, message="Trace build completed")
        except Exception as e:
            logger.error(f"Trace build failed: {e}")
            pm.finish_task(task_id, success=False, message=str(e))
    
    _trace_build_thread = threading.Thread(target=build_task, daemon=True)
    _trace_build_thread.start()
    return True


# =============================================================================
# Pydantic Models
# =============================================================================

@app.get("/projects")
def list_projects() -> Dict[str, Any]:
    reg = _get_registry()
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


@app.post("/projects")
def add_project(req: AddProjectRequest) -> Dict[str, Any]:
    if req.mode not in ("standalone", "embedded", "custom"):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=f"Invalid mode: {req.mode}")

    # Check project count limit for current tier
    reg = _get_registry()
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

    reg = _get_registry()
    default_cfg: Dict[str, Any] = {
        "include_globs": list(_DEFAULT_UI_CONFIG.get("include_globs") or []),
        "exclude_globs": list(_DEFAULT_UI_CONFIG.get("exclude_globs") or []),
        "max_file_bytes": int(_DEFAULT_UI_CONFIG.get("max_file_bytes") or 500_000),
        "hard_limit_bytes": int(_DEFAULT_UI_CONFIG.get("hard_limit_bytes") or 100_000_000),
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

    if (_DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms") is not None:
        default_cfg["auto_rebuild"]["debounce_ms"] = int(
            (_DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms")
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

    return ok({"project": _project_to_dict(proj)})


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    return ok({"project": _project_to_dict(proj)})


@app.put("/projects/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest) -> Dict[str, Any]:
    reg = _get_registry()
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

    return ok({"project": _project_to_dict(updated)})


@app.put("/projects/{project_id}/path_weights")
def update_path_weights(project_id: str, req: PathWeightsRequest) -> Dict[str, Any]:
    proj = _require_project(project_id)
    updated = _persist_path_weights(proj, req.path_weights)
    return ok({"project": _project_to_dict(updated), "path_weights": updated.config.get("path_weights", {})})


@app.get("/projects/{project_id}/path_weights")
def get_path_weights(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    pw = proj.config.get("path_weights", {})
    return ok({"path_weights": pw})


def _persist_path_weights(proj: Project, raw_weights: Dict[str, float]) -> Project:
    """Normalize and persist path_weights to project config AND repo_policy.json."""
    normalized = _normalize_path_weights(raw_weights)

    # Update project config in SQLite
    reg = _get_registry()
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
    idx = _project_indexes.get(proj.id)
    if idx is not None and idx._manifest:
        cfg = idx._manifest.get("config")
        if isinstance(cfg, dict):
            cfg["path_weights"] = normalized

    return updated


@app.delete("/projects/{project_id}")
def delete_project(project_id: str, purge: bool = False) -> Dict[str, Any]:
    reg = _get_registry()
    try:
        reg.remove_project(project_id, purge=bool(purge))
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    _project_indexes.pop(project_id, None)
    _project_trace_indexes.pop(project_id, None)
    with _project_build_lock:
        _project_build_threads.pop(project_id, None)
        _project_last_build_result.pop(project_id, None)
        _project_last_build_error.pop(project_id, None)
    with _project_trace_build_lock:
        _project_trace_build_threads.pop(project_id, None)

    return ok({"removed": True, "purged": bool(purge)})


@app.get("/projects/{project_id}/status")
def get_project_status(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)
    idx = _get_project_index(proj)

    watch = _get_project_watcher_status(proj)
    data = {
        "building": _is_project_building(proj.id),
        "stale": bool(watch.get("stale", False)),
        "stale_since": watch.get("stale_since"),
        "index": _project_index_status(idx, _project_last_build_error.get(proj.id)),
        "trace": _project_trace_status(proj),
        "watch": watch,
    }
    return ok(data)


@app.post("/projects/{project_id}/watch/start")
def start_project_watch(
    project_id: str,
    debounce_ms: int = Query(5000, ge=500, le=60000),
    min_gap_ms: int = Query(2000, ge=500, le=30000),
) -> Dict[str, Any]:
    """Enable auto-rebuild watcher for a project."""
    require_feature("auto_rebuild")
    proj = _require_project(project_id)
    idx = _get_project_index(proj)
    
    # Stop existing watcher if any
    existing = _project_watchers.get(proj.id)
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

        started = _start_project_build(proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes)

        # Also trigger trace rebuild if trace is enabled
        trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
        if bool((trace_cfg or {}).get("enabled", False)):
            _start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)

        return started
    
    def is_building() -> bool:
        return _is_project_building(proj.id) or _is_project_trace_building(proj.id)
    
    watcher = AutoRebuildWatcher(
        repo_root=Path(proj.path),
        index_dir=idx.index_dir,
        on_trigger_build=trigger_build,
        is_building=is_building,
        debounce_ms=debounce_ms,
        min_rebuild_gap_ms=min_gap_ms,
    )
    watcher.start()
    _project_watchers[proj.id] = watcher
    
    return ok({"enabled": True, "status": watcher.status()})


@app.post("/projects/{project_id}/watch/stop")
def stop_project_watch(project_id: str) -> Dict[str, Any]:
    """Disable auto-rebuild watcher for a project."""
    proj = _require_project(project_id)
    
    watcher = _project_watchers.pop(proj.id, None)
    if watcher is not None:
        watcher.stop()
    
    return ok({"enabled": False})


@app.get("/projects/{project_id}/watch/status")
def get_project_watch_status(project_id: str) -> Dict[str, Any]:
    """Get watcher status for a project."""
    proj = _require_project(project_id)
    return ok(_get_project_watcher_status(proj))


@app.get("/projects/{project_id}/activity")
def get_project_activity(project_id: str, weeks: int = Query(12, ge=1, le=52)) -> Dict[str, Any]:
    proj = _require_project(project_id)
    data = _project_activity_payload(proj, int(weeks))
    return ok(data)


@app.get("/projects/{project_id}/coverage")
def get_project_coverage(project_id: str) -> Dict[str, Any]:
    proj = _require_project(project_id)

    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else list(_DEFAULT_UI_CONFIG.get("include_globs") or [])
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(_DEFAULT_UI_CONFIG.get("exclude_globs") or [])

    if proj.mode == "embedded":
        if "**/.codrag/**" not in exclude_globs:
            exclude_globs.append("**/.codrag/**")

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    tree = _build_coverage_tree(repo_root, include_globs, exclude_globs)
    return ok({"tree": tree})


@app.get("/projects/{project_id}/file")
def get_project_file_content(project_id: str, path: str = Query(..., min_length=1)) -> Dict[str, Any]:
    proj = _require_project(project_id)

    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else list(_DEFAULT_UI_CONFIG.get("include_globs") or [])
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(_DEFAULT_UI_CONFIG.get("exclude_globs") or [])
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


@app.get("/projects/{project_id}/detect-stack")
def detect_project_stack(project_id: str) -> Dict[str, Any]:
    """Analyze the project to recommend include patterns."""
    proj = _require_project(project_id)
    detected_presets = _scan_for_presets(Path(proj.path))
    
    recommended_globs = []
    for preset in detected_presets:
        recommended_globs.extend(_STACK_PRESETS.get(preset, []))
        
    return ok({
        "recommended_globs": sorted(list(set(recommended_globs))),
        "detected_presets": sorted(detected_presets),
        "all_presets": _STACK_PRESETS,
    })


@app.get("/projects/{project_id}/roots")
def get_project_roots(project_id: str) -> Dict[str, Any]:
    """Get available root directories for a project."""
    proj = _require_project(project_id)
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


@app.get("/projects/{project_id}/files")
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
    proj = _require_project(project_id)
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
    idx = _get_project_index(proj)
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


@app.post("/projects/{project_id}/build")
def build_project(project_id: str, full: bool = False) -> Dict[str, Any]:
    proj = _require_project(project_id)

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

    started = _start_project_build(proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes)
    if not started:
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Build already running")

    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if bool((trace_cfg or {}).get("enabled", False)):
        _start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)
    return ok({"started": True, "building": True, "build_id": None})


@app.post("/projects/{project_id}/search")
def search_project(project_id: str, req: SearchRequest) -> Dict[str, Any]:
    proj = _require_project(project_id)
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _get_project_index(proj)
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
        clara_url = str(_config.get("clara_url", ClaraCompressor.DEFAULT_URL))
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


@app.post("/projects/{project_id}/context")
def context_project(project_id: str, req: ContextRequest) -> Dict[str, Any]:
    proj = _require_project(project_id)
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _get_project_index(proj)
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
                ti = _get_project_trace_index(proj)
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




@app.post("/api/code-index/context", deprecated=True)
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

    idx = _get_index()
    
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
    if req.trace_expand and _trace_index:
        try:
            # Ensure trace index is loaded
            if not _trace_index.is_loaded():
                _trace_index.load()
            
            # Use trace expansion for structured results
            result = idx.get_context_with_trace_expansion(
                req.query,
                trace_index=_trace_index,
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
        ui_cfg = _load_ui_config()
        clara_cfg = (ui_cfg.get("llm_config") or {}).get("clara") or {}
        clara_url = clara_cfg.get("remote_url") or _config.get("clara_url") or ClaraCompressor.DEFAULT_URL
        
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


@app.post("/api/code-index/chunk", deprecated=True)
def chunk(req: ChunkRequest, response: Response):
    """Get a specific chunk by ID.
    
    DEPRECATED: Use POST /projects/{project_id}/search instead.
    This endpoint uses a global singleton index and does not support multi-project.
    """
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-06-01"
    logger.warning("DEPRECATED: /api/code-index/chunk called - migrate to /projects/{id}/search")
    
    idx = _get_index()
    doc = idx.get_chunk(req.chunk_id)
    if doc is None:
        raise ApiException(status_code=404, code="CHUNK_NOT_FOUND", message="Chunk not found")
    return ok({"chunk": doc})


# =============================================================================
# Router Registration (Phase 23 — endpoint extraction)
# =============================================================================
# Routers are imported here (after all helpers/globals are defined) to avoid
# circular imports — each router does `from codrag.server import <helper>`.

from codrag.api.routers.system import router as system_router
from codrag.api.routers.license import router as license_router
from codrag.api.routers.trace import router as trace_router
from codrag.api.routers.knowledge import router as knowledge_router
from codrag.api.routers.llm import router as llm_router
from codrag.api.routers.projects import router as projects_router
app.include_router(system_router)
app.include_router(license_router)
app.include_router(trace_router)
app.include_router(knowledge_router)
app.include_router(llm_router)
app.include_router(projects_router)


# =============================================================================
# Server Configuration & Main
# =============================================================================

def configure(
    repo_root: Optional[str] = None,
    index_dir: str = "./codrag_data",
    ollama_url: str = "http://localhost:11434",
    model: str = "nomic-embed-text",
):
    """Configure the server before starting."""
    global _config, _index, _watcher
    if _watcher is not None:
        try:
            _watcher.stop()
        except Exception:
            pass
        _watcher = None
    _config = {
        "repo_root": repo_root,
        "index_dir": index_dir,
        "ollama_url": ollama_url,
        "model": model,
    }
    _index = None


def mount_dashboard():
    """Mount the static dashboard if available."""
    dashboard_dir = Path(__file__).parent / "dashboard" / "dist"
    if dashboard_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
        logger.info(f"Dashboard mounted at /ui from {dashboard_dir}")
    else:
        logger.warning(f"Dashboard not found at {dashboard_dir} - run 'npm run build' in dashboard/")


def main():
    parser = argparse.ArgumentParser(description="CoDRAG Server")
    parser.add_argument("--repo-root", help="Default repository root to index")
    parser.add_argument("--index-dir", default="./codrag_data", help="Directory to store index")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
    parser.add_argument("--model", default="nomic-embed-text", help="Embedding model name")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8400, help="Port to bind to")
    args = parser.parse_args()

    configure(
        repo_root=args.repo_root,
        index_dir=args.index_dir,
        ollama_url=args.ollama_url,
        model=args.model,
    )

    mount_dashboard()

    import uvicorn
    logger.info(f"Starting CoDRAG server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

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

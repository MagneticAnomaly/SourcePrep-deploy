"""
CoDRAG FastAPI server.

Main HTTP API for the CoDRAG daemon.

Usage:
    python -m codrag.server --repo-root /path/to/repo --index-dir ./codrag_data --port 8400
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from codrag import __version__
from codrag.api.envelope import install_api_exception_handlers
from codrag.core import CodeIndex
from codrag.core.events import get_event_bus, BroadcastLogHandler, get_progress_manager
from codrag.core.project_registry import Project, ProjectRegistry
from codrag.core.feature_gate import FeatureGateError
from codrag.core.watcher import AutoRebuildWatcher

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

# IPC Token Auth Middleware
@app.middleware("http")
async def verify_ipc_token(request: Request, call_next):
    # Allow health checks and SSE events to pass without token for simplicity in some contexts
    if request.url.path in ["/health", "/events"]:
        return await call_next(request)
    
    expected_token = os.environ.get("CODRAG_DAEMON_TOKEN")
    if expected_token:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"success": False, "error": {"message": "Missing Authorization header"}})
        
        token = auth_header.split(" ")[1]
        if token != expected_token:
            return JSONResponse(status_code=403, content={"success": False, "error": {"message": "Invalid daemon token"}})
            
    return await call_next(request)

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
_project_syncers: Dict[str, Any] = {}  # Dict[str, RemoteSyncService]

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


# ── Config Manager (Phase 23 Sprint 16b) ─────────────────────────
# Config defaults, load/save, and merge logic live in ConfigManager.
# Thin wrappers below keep backward compatibility for routers.
from codrag.services.config_manager import (
    _DEFAULT_UI_CONFIG,
    ui_config_path as _cm_ui_config_path,
    default_ui_config as _cm_default_ui_config,
    deep_merge as _deep_merge,
    load_ui_config as _cm_load_ui_config,
    save_ui_config as _cm_save_ui_config,
)


def _ui_config_path() -> Path:
    return _cm_ui_config_path(_config)


def _default_ui_config() -> Dict[str, Any]:
    return _cm_default_ui_config(_config)


def _load_ui_config() -> Dict[str, Any]:
    return _cm_load_ui_config(_config)


def _save_ui_config(cfg: Dict[str, Any]) -> None:
    _cm_save_ui_config(_config, cfg)


# ── Project Helpers (Phase 23 Sprint 16c) ────────────────────────
# Project helpers live in services/project_helpers.py.
# Thin wrappers below keep backward compatibility for routers.
from codrag.services.project_helpers import (
    get_registry as _ph_get_registry,
    project_to_dict as _ph_project_to_dict,
    project_id_for_root as _ph_project_id_for_root,
    current_project as _ph_current_project,
    require_project as _ph_require_project,
    project_index_status as _ph_project_index_status,
    project_trace_status as _ph_project_trace_status,
    get_project_watcher as _ph_get_project_watcher,
    get_project_watcher_status as _ph_get_project_watcher_status,
    get_project_sync_status as _ph_get_project_sync_status,
    check_index_staleness as _ph_check_index_staleness,
    invalidate_stale_cache as _ph_invalidate_stale_cache,
    read_json_file as _ph_read_json_file,
    parse_iso_datetime as _ph_parse_iso_datetime,
    project_activity_payload as _ph_project_activity_payload,
    build_coverage_tree as _ph_build_coverage_tree,
)


def _get_registry() -> ProjectRegistry:
    return _ph_get_registry()


def _project_to_dict(proj: Project) -> Dict[str, Any]:
    return _ph_project_to_dict(proj)


def _project_id_for_root(root: str) -> str:
    return _ph_project_id_for_root(root)


def _current_project() -> Dict[str, Any] | None:
    return _ph_current_project(_config, _watcher, _SERVER_STARTED_AT)


def _require_project(project_id: str) -> Project:
    return _ph_require_project(project_id)


def _project_index_status(idx: CodeIndex, last_build_error: Optional[str] = None) -> Dict[str, Any]:
    return _ph_project_index_status(idx, last_build_error)


def _project_trace_status(project: Project) -> Dict[str, Any]:
    return _ph_project_trace_status(project)


def _get_project_watcher(project: Project) -> Optional[AutoRebuildWatcher]:
    return _ph_get_project_watcher(project, _project_watchers)


def _get_project_watcher_status(project: Project) -> Dict[str, Any]:
    return _ph_get_project_watcher_status(project, _project_watchers)


def _get_project_sync_status(project: Project) -> Dict[str, Any]:
    return _ph_get_project_sync_status(project, _project_syncers)


def _check_index_staleness(project: Project, idx: CodeIndex) -> Dict[str, Any]:
    return _ph_check_index_staleness(project, idx)


def _invalidate_stale_cache(project_id: str) -> None:
    _ph_invalidate_stale_cache(project_id)


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    return _ph_read_json_file(path)


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    return _ph_parse_iso_datetime(value)


def _project_activity_payload(project: Project, weeks: int) -> Dict[str, Any]:
    return _ph_project_activity_payload(project, weeks)


def _build_coverage_tree(repo_root: Path, include_globs: List[str], exclude_globs: List[str]) -> Dict[str, Any]:
    return _ph_build_coverage_tree(repo_root, include_globs, exclude_globs)


# ── Build Manager convenience wrappers (backward compat) ─────────
# These delegate to the BuildManager singleton so routers can keep
# doing `from codrag.server import _get_project_index` etc.

def _get_project_index(project: Project) -> CodeIndex:
    return _bm.get_project_index(project)

def _get_project_trace_index(project: Project) -> "TraceIndex":
    return _bm.get_project_trace_index(project)

def _get_project_knowledge_index(project: Project) -> "KnowledgeIndex":
    return _bm.get_project_knowledge_index(project)

def _is_project_building(project_id: str) -> bool:
    return _bm.is_project_building(project_id)

def _is_project_trace_building(project_id: str) -> bool:
    return _bm.is_project_trace_building(project_id)

def _is_project_knowledge_building(project_id: str) -> bool:
    return _bm.is_project_knowledge_building(project_id)

def _start_project_build(project: Project, roots, include_globs, exclude_globs, max_file_bytes: int, hard_limit_bytes: int, use_gitignore: bool = False, included_paths=None) -> bool:
    return _bm.start_project_build(project, roots, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore, included_paths=included_paths)

def _start_project_trace_build(project: Project, include_globs=None, exclude_globs=None, max_file_bytes: int = 500_000, hard_limit_bytes: int = 100_000_000, use_gitignore: bool = False) -> bool:
    return _bm.start_project_trace_build(project, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore)

def _project_augment_status(project: Project) -> Dict[str, Any]:
    """Read augmentation manifest for a project and return status dict."""
    from codrag.core.project_registry import project_index_dir
    from codrag.core import TraceAugmenter
    idx_dir = project_index_dir(project)
    augmenter = TraceAugmenter(index_dir=idx_dir, repo_root=project.path, llm_client=None)
    return augmenter.status()

def _get_llm_client_for_slot(slot: str):
    """Create an LLMClient for the given slot ('small', 'large', or 'code')."""
    # Map slot aliases to config keys
    SLOT_MAP = {"small": "small_model", "large": "large_model", "code": "code_model"}
    slot_key = SLOT_MAP.get(slot, slot)
    
    ui_cfg = _load_ui_config()
    llm_config = ui_cfg.get("llm_config") or {}
    
    # Get slot config (e.g. small_model: { enabled: true, endpoint_id: "...", model: "..." })
    slot_cfg = llm_config.get(slot_key) or {}
    if not slot_cfg.get("enabled"):
        return None
        
    endpoint_id = slot_cfg.get("endpoint_id")
    if not endpoint_id:
        return None
        
    # Resolve endpoint from saved_endpoints list
    endpoints = llm_config.get("saved_endpoints") or []
    endpoint = next((ep for ep in endpoints if ep.get("id") == endpoint_id), None)
    
    if not endpoint:
        return None
        
    url = endpoint.get("url")
    if not url:
        return None

    from codrag.core import LLMClient
    return LLMClient(
        endpoint_url=url,
        model=slot_cfg.get("model", ""),
        api_key=endpoint.get("api_key"),
        provider=endpoint.get("provider", "ollama"),
    )



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
from codrag.api.routers.pipeline import router as pipeline_router
from codrag.api.routers.settings import router as settings_router
from codrag.api.routers.scope import router as scope_router
app.include_router(system_router)
app.include_router(license_router)
app.include_router(trace_router)
app.include_router(knowledge_router)
app.include_router(llm_router)
app.include_router(projects_router)
app.include_router(pipeline_router)
app.include_router(settings_router)
app.include_router(scope_router)


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

    # Initialize SQLite settings store (Phase 24)
    from codrag.services.settings_store import settings as _settings_store
    idx_path = Path(index_dir)
    idx_path.mkdir(parents=True, exist_ok=True)
    db_path = idx_path / "codrag_settings.db"
    _settings_store.init(db_path)

    # Auto-migrate from ui_config.json if this is first run
    json_path = idx_path / "ui_config.json"
    if _settings_store.migrate_from_json(json_path):
        logger.info("Migrated settings from ui_config.json to SQLite")

    # Prune orphan projects (paths that no longer exist on disk)
    try:
        reg = _get_registry()
        pruned = reg.prune_orphans()
        if pruned:
            logger.info("Pruned %d orphan project(s): %s", len(pruned),
                        ", ".join(f"{p.name} ({p.path})" for p in pruned))
    except Exception:
        logger.debug("Orphan pruning failed (non-fatal)", exc_info=True)

    # Initialize pipeline journal + crash recovery (Phase 25)
    from codrag.services.pipeline_journal import journal as _journal
    _journal.init(db_path)
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator as _pipeline
    crashed = _pipeline.startup_recovery()
    if crashed:
        logger.warning("Phase 25: %d crashed pipeline run(s) detected on startup", len(crashed))

    # Phase 26 (S-26.3): Start schedule evaluator for scheduled deep enrichment
    try:
        from codrag.services.pipeline_budget import schedule as _schedule
        _schedule.start(
            run_callback=lambda pid: _pipeline.run_deep_enrichment(pid),
            check_interval=60.0,
        )
    except Exception:
        logger.debug("Schedule evaluator startup failed (non-fatal)", exc_info=True)


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

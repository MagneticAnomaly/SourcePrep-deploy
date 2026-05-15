"""
SourcePrep FastAPI server.

Main HTTP API for the SourcePrep daemon.

Usage:
    python -m prep.server --repo-root /path/to/repo --port 8400

Daemon-wide state defaults to `$PREP_DATA_DIR` or `~/.local/share/runprep/`.
Pass `--index-dir <path>` to override (deprecated).
"""

from __future__ import annotations

import argparse
import hmac
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from prep import __version__

# Phase 113: migrate legacy ./codrag_data/ before any store module gets
# imported. Each service module (concept_store, antibody_store, etc.)
# opens its SQLite connection at import time on a module-level
# singleton — once they've opened the old path, the migration would
# race against live write traffic. Running it here guarantees the
# stores pick up their new XDG location from the first open.
from prep.core.data_dir_migration import (
    migrate_from_legacy_codrag as _migrate_from_codrag,
    migrate_from_legacy_prep as _migrate_from_prep,
    migrate_from_legacy_runprep as _migrate_from_runprep,
    migrate_legacy_data_dir as _migrate_legacy,
)

_migrate_from_codrag()   # codrag -> runprep XDG dirs (rename one-shot, D4)
_migrate_from_prep()     # prep -> runprep XDG dirs (brand-split one-shot)
_migrate_from_runprep()  # runprep -> sourceprep XDG dirs (rename one-shot, S1)
_migrate_legacy()        # CWD codrag_data -> XDG (Phase 113 one-shot)

from prep.api.envelope import install_api_exception_handlers
from prep.core import CodeIndex
from prep.core.events import get_event_bus, BroadcastLogHandler, get_progress_manager
from prep.core.project_registry import Project, ProjectRegistry
from prep.core.feature_gate import FeatureGateError
from prep.core.watcher import AutoRebuildWatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize services on startup, cleanup on shutdown."""
    import asyncio

    # Initialize EventBus with running loop for thread-safe dispatch
    bus = get_event_bus()
    loop = asyncio.get_running_loop()
    bus.set_loop(loop)

    # Attach log handler to capture root logs and broadcast via SSE.
    # Root logger defaults to WARNING — lower it so INFO messages
    # (build progress, model readiness, etc.) reach the handler.
    handler = BroadcastLogHandler(bus)
    handler.setLevel(logging.INFO)  # Don't broadcast DEBUG noise
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Attach to root logger ONLY — named loggers propagate up to root,
    # so we do NOT attach to individual namespaces (that causes duplicates).
    root_logger = logging.getLogger()
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # Ensure key namespaces have propagate=True and correct level
    # so their messages reach the root handler via propagation.
    for logger_name in ["prep", "uvicorn", "uvicorn.error", "uvicorn.access"]:
        ns_logger = logging.getLogger(logger_name)
        ns_logger.propagate = True
        if ns_logger.level > logging.INFO:
            ns_logger.setLevel(logging.INFO)

    # F-70: Increase the default anyio thread pool from 40 to 100.
    # Cloud model calls block threads for minutes. With build workers,
    # recovery, SSE, and dashboard polling all sharing the default pool,
    # 40 threads is not enough — API status endpoints timeout during
    # active LLM calls, causing "Loading project..." to stick.
    try:
        import anyio
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = 100
        logger.info("Increased anyio thread pool to %d", limiter.total_tokens)
    except Exception:
        logger.debug("Could not increase anyio thread pool", exc_info=True)

    # Initialize ProgressManager (ensure it's created)
    get_progress_manager()

    # Phase 139: opt-in daemon-wide RSS sampler. Set PREP_RSS_TELEMETRY=1
    # to enable. No-op when unset.
    try:
        from prep.services import rss_sampler
        rss_sampler.start()
    except Exception:
        logger.debug("RSS sampler failed to start (non-fatal)", exc_info=True)

    logger.info("SourcePrep EventBus initialized")
    yield

    # Phase 139: stop RSS sampler before SQLite shutdown.
    try:
        from prep.services import rss_sampler
        rss_sampler.stop()
    except Exception:
        logger.debug("RSS sampler failed to stop (non-fatal)", exc_info=True)

    # Phase 139: release shared embedders. Drops Python refs; does not
    # deterministically reclaim CoreML/ANE memory (open ORT issues #26831,
    # #22007) — restart is the documented remedy. Logged for visibility.
    try:
        from prep.services.embedder_factory import close_shared_embedders
        close_shared_embedders()
    except Exception:
        logger.debug("close_shared_embedders failed (non-fatal)", exc_info=True)
    # Phase 93: Write clean shutdown markers for projects with no active runs.
    # On next startup, auto_recover_stale_pipelines will see these markers and
    # skip recovery — incomplete deep enrichment manifests are steady-state,
    # not interrupted. Projects WITH active runs get NO marker, so recovery
    # triggers correctly after a graceful stop mid-pipeline.
    try:
        from prep.services.pipeline.recovery import RecoveryManager
        from prep.services.pipeline_orchestrator import pipeline_orchestrator
        from prep.services.project_helpers import get_registry
        registry = get_registry()
        for project in registry.list_projects():
            if not pipeline_orchestrator.has_active_run(project.id):
                RecoveryManager.write_clean_shutdown_marker(project.id)
                logger.debug("Clean shutdown marker written for %s", project.id)
            else:
                # Clear any existing marker for active-run projects so that
                # if the daemon subsequently crashes, recovery will trigger.
                RecoveryManager.read_and_clear_clean_shutdown_marker(project.id)
                logger.debug("Clean shutdown marker cleared for %s (active run)", project.id)
    except Exception:
        logger.debug("Failed to write clean shutdown markers", exc_info=True)
    # Shutdown: close all SQLite stores so WAL can be checkpointed cleanly.
    # Order doesn't matter — each store checkpoints its own connection.
    from prep.services.concept_store import concept_store as _concept_store
    _concept_store.close()
    from prep.services.observation_store import observation_store as _obs_store
    _obs_store.close()
    from prep.services.token_telemetry import telemetry as _telemetry
    _telemetry.close()
    from prep.services.pipeline_history import history as _history
    _history.close()
    from prep.services.pipeline_journal import journal as _journal
    _journal.close()
    from prep.services.settings_store import settings as _settings_store
    _settings_store.close()
    logger.info("All SQLite stores closed")


app = FastAPI(
    title="SourcePrep",
    description="Code Documentation and RAG - Multi-project semantic search platform",
    version=__version__,
    lifespan=lifespan,
)
install_api_exception_handlers(app)


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
                "hint": f"Upgrade to {exc.required_tier} at https://sourceprep.io/pricing",
                "details": {
                    "feature": exc.feature,
                    "current_tier": exc.current_tier,
                    "required_tier": exc.required_tier,
                },
            },
        },
    )


# CORS for dashboard (restricted to known origins).
# Starlette's CORSMiddleware does NOT support wildcard port patterns like
# "http://localhost:*".  Use allow_origin_regex for port-flexible matching.
# In development, set PREP_CORS_ALLOW_ALL=1 to revert to allow_origins=["*"].
if os.environ.get("PREP_CORS_ALLOW_ALL"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # Cannot use credentials with wildcard origin
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_origins=["tauri://localhost", "https://tauri.localhost"],
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
    
    expected_token = os.environ.get("PREP_DAEMON_TOKEN")
    if expected_token:
        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"success": False, "error": {"message": "Missing Authorization header"}})
        
        token = auth_header[7:]  # len("Bearer ") == 7
        if not token or not hmac.compare_digest(token, expected_token):
            return JSONResponse(status_code=403, content={"success": False, "error": {"message": "Invalid daemon token"}})
            
    return await call_next(request)

# ── Build Manager (Phase 23 Sprint 14) ────────────────────────────
# All index caches, build threads, and locks live in the BuildManager
# singleton. Module-level aliases below keep backward compatibility
# with routers that do `from prep.server import _get_project_index`.
from prep.services.build_manager import build_manager as _bm

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
from prep.services.config_manager import (
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
from prep.services.project_helpers import (
    get_registry as _ph_get_registry,
    project_to_dict as _ph_project_to_dict,
    project_id_for_root as _ph_project_id_for_root,
    current_project as _ph_current_project,
    require_project as _ph_require_project,
    require_project_writable as _ph_require_project_writable,
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


def _require_project_writable(project_id: str) -> Project:
    return _ph_require_project_writable(project_id)


def _project_index_status(idx: CodeIndex, last_build_error: Optional[str] = None, project: Optional[Project] = None) -> Dict[str, Any]:
    return _ph_project_index_status(idx, last_build_error, project=project)


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
# doing `from prep.server import _get_project_index` etc.

def _get_project_index(project: Project) -> CodeIndex:
    return _bm.get_project_index(project)

def _get_project_layered_index(project: Project):
    return _bm.get_project_layered_index(project)

def _has_remote_index(project: Project) -> bool:
    return _bm.has_remote_index(project)

def _start_project_delta_build(project: Project, changed_paths, include_globs, exclude_globs, max_file_bytes=500_000, hard_limit_bytes=100_000_000, use_gitignore: bool = True, included_paths=None) -> bool:
    return _bm.start_project_delta_build(project, changed_paths, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore=use_gitignore, included_paths=included_paths)

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

def _start_project_knowledge_build(project: Project) -> bool:
    """F-45: thin wrapper around build_manager.start_project_knowledge_build.

    The /projects/{id}/knowledge/build router (knowledge.py:79) imported this
    name from prep.server but it never existed, so every call to that
    endpoint returned 500 with ImportError. Adding the wrapper restores the
    endpoint without changing the build_manager API.
    """
    return _bm.start_project_knowledge_build(project)

def _start_project_build(project: Project, roots, include_globs, exclude_globs, max_file_bytes: int, hard_limit_bytes: int, use_gitignore: bool = False, included_paths=None) -> bool:
    return _bm.start_project_build(project, roots, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore, included_paths=included_paths)

def _start_project_trace_build(project: Project, include_globs=None, exclude_globs=None, max_file_bytes: int = 500_000, hard_limit_bytes: int = 100_000_000, use_gitignore: bool = False) -> bool:
    return _bm.start_project_trace_build(project, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore)

def _project_augment_status(project: Project) -> Dict[str, Any]:
    """Read augmentation manifest for a project and return status dict."""
    from prep.core.project_registry import project_index_dir
    from prep.core import TraceAugmenter
    idx_dir = project_index_dir(project)
    augmenter = TraceAugmenter(index_dir=idx_dir, repo_root=project.path, llm_client=None)
    return augmenter.status()

def _get_llm_client_for_slot(slot: str):
    """Create an LLMClient for the given slot ('small', 'large', or 'code').

    This is the low-level slot resolver used internally by the structured-mode
    path of ``_get_llm_client_for_task()``.  Direct callers should prefer
    ``_get_llm_client_for_task(task_id)`` instead.
    """
    # Map slot aliases to config keys
    SLOT_MAP = {
        "small": "small_model",
        "large": "large_model",
        "code": "code_model",
        "coordinator": "coordinator_model",
    }
    slot_key = SLOT_MAP.get(slot, slot)

    ui_cfg = _load_ui_config()
    llm_config = ui_cfg.get("llm_config") or {}

    # Get slot config (e.g. small_model: { enabled: true, endpoint_id: "...", model: "..." })
    slot_cfg = llm_config.get(slot_key) or {}

    # Phase 112: Swarm coordinator slot honors `inherit_from_large`.
    # When the flag is True (default) or the coordinator slot is
    # unconfigured, fall back to the large-slot client — preserves the
    # legacy single-model swarm behavior.  See SWARM_UI_PLAN.md §2.
    #
    # Phase 112 fix 2: fail loud when both coordinator AND large are
    # unconfigured so callers see the misconfiguration instead of the
    # swarm silently timing out in the Planning phase.  SwarmOrchestrator
    # still handles ``coordinator_llm=None`` (falls back to worker_llm),
    # but that's for the legacy single-LLM construction path — it must
    # not be reached via a misconfigured coordinator slot.
    if slot in ("coordinator", "coordinator_model"):
        inherit = slot_cfg.get("inherit_from_large", True)
        unconfigured = (
            not slot_cfg
            or not slot_cfg.get("endpoint_id")
            or not slot_cfg.get("model")
        )
        if inherit or unconfigured:
            large_client = _get_llm_client_for_slot("large")
            if large_client is None:
                raise RuntimeError(
                    "Coordinator slot unconfigured (or inherit_from_large=True) "
                    "AND large-model slot is also unconfigured.  Configure the "
                    "large model in Settings → AI Models, or assign an explicit "
                    "coordinator model with inherit_from_large=False."
                )
            return large_client

    # A slot is functional when it has both endpoint_id and model configured.
    # The explicit 'enabled' flag is a UI toggle that may be stale from
    # migration or hydration race conditions — don't gate on it alone.
    endpoint_id = slot_cfg.get("endpoint_id")
    if not endpoint_id or not slot_cfg.get("model"):
        return None
        
    # Resolve endpoint from saved_endpoints list
    endpoints = llm_config.get("saved_endpoints") or []
    endpoint = next((ep for ep in endpoints if ep.get("id") == endpoint_id), None)
    
    if not endpoint:
        return None
        
    url = endpoint.get("url")
    if not url:
        return None

    from prep.core import LLMClient
    # Deep reasoning models (large slot) need very long timeouts because
    # thinking models like qwen3.5:27b generate 2000-5000+ thinking tokens
    # before content on complex files, taking 300-500s+ per call at ~11 tok/s.
    _LARGE_SLOTS = {"large", "large_model", "coordinator", "coordinator_model"}
    timeout = 600.0 if slot in _LARGE_SLOTS else 120.0
    client = LLMClient(
        endpoint_url=url,
        model=slot_cfg.get("model", ""),
        api_key=endpoint.get("api_key"),
        provider=endpoint.get("provider", "ollama"),
        timeout=timeout,
        always_on=bool(slot_cfg.get("always_on", False)),
        debug_mode=bool(ui_cfg.get("developer_debug_mode", False)),
        # Phase 119+ correctness: pin the client to its scheduler slot.
        # Without endpoint_id, _resolve_scheduler_node_id falls back to
        # first-prefix-match and Qwen-on-OpenRouter calls get gated
        # through whichever cloud slot was registered first (typically
        # cloud:default_ollama, the Kimi node), masking real OpenRouter
        # AIMD state and delaying coordinator phases.
        endpoint_id=endpoint_id,
    )
    # Phase 119 swarm slot attribution: tag the resolved slot so
    # token_telemetry.track_active_request can stamp model_slot on every
    # in-flight LLMClient call.  Without this every active request lands
    # with model_slot=None, and the AI Gateway can't split a swarm's
    # coordinator/worker/synthesizer calls across the right slots — the
    # whole swarm shows up under one bucket.
    #
    # Normalize the input slot to one of the four canonical short forms
    # the sidebar buckets render as: ``small`` / ``large`` / ``code`` /
    # ``coordinator``.  Callers pass either the short form ("small")
    # or the full config key ("small_model"); we accept both so a caller
    # rename never silently drops the tag.  The inherit-from-large
    # coordinator path returned ``large_client`` above, so that case
    # carries the recursive call's "large" tag — intentional, not a bug.
    _CANONICAL_SLOT = {
        "small": "small", "small_model": "small",
        "large": "large", "large_model": "large",
        "code": "code", "code_model": "code",
        "coordinator": "coordinator", "coordinator_model": "coordinator",
    }
    client._model_slot = _CANONICAL_SLOT.get(slot, slot_key)
    return client


def get_advanced_llm_settings() -> Dict[str, Any]:
    """Return the Phase 112 advanced LLM settings block with safe defaults.

    Reads from ``ui_cfg["llm_config"]["advanced"]``.  Defaults to the
    conservative values (safety ON, Kimi 24K thinking budget) so
    out-of-the-box behavior matches the documented profile sizes.
    """
    ui_cfg = _load_ui_config()
    llm_config = ui_cfg.get("llm_config") or {}
    defaults = {
        "enforce_cloud_token_safety": True,
        "max_thinking_budget": 24576,
    }
    merged = {**defaults, **(llm_config.get("advanced") or {})}
    # Phase 82 deprecation: legacy plan-tier keys are accepted but ignored.
    # Strip them from stale ui_config payloads so callers never see them.
    merged.pop("ollama_plan_tier", None)
    merged.pop("custom_concurrency", None)
    return merged


# ── Phase 44: Unified Task-Based LLM Resolver ─────────────────────

# Maps PrepTaskId → structured slot name.  Used when assignment_mode == "structured".
TASK_TO_SLOT: Dict[str, str] = {
    "catalogue":       "small",
    "inferred_edges":  "code",
    "enrichment":      "large",
    "group_reasoning": "large",
    "clustering":      "large",
    "atlas":           "large",
    "deepening":       "large",
    "search_intent":   "small",
    "audit":           "large",
    "goalposts":       "large",
    "augmentation":    "small",
    "advisor":         "large",   # Phase 63: opportunity discovery pipeline
    "concepts":        "large",   # Phase 74: concept seeding pipeline
}

# Tasks whose structured slot falls back to "small" when the primary slot is unconfigured.
_SLOT_FALLBACK_TO_SMALL = {"code", "large"}

# Tasks whose mapped-mode blocks should use the long (600s) timeout
_LONG_TIMEOUT_TASKS = {"enrichment", "clustering", "atlas", "deepening", "audit", "goalposts"}


def _get_llm_client_for_task(task_id: str):
    """Resolve an LLM client for a specific pipeline/runtime task.

    Phase 44 unified resolver.  In structured mode, maps task → slot → config
    (identical to the old behaviour).  In mapped mode, maps task → assignment
    block → endpoint+model.

    Returns ``None`` if no model is configured for the task, or if the resolved
    model violates the Enterprise Admin Policy.
    """
    ui_cfg = _load_ui_config()
    llm_cfg = ui_cfg.get("llm_config") or {}
    mode = llm_cfg.get("assignment_mode", "structured")

    if mode == "mapped":
        client = _resolve_mapped_task(task_id, llm_cfg)
    else:
        client = _resolve_structured_task(task_id)
        
    # EA-C8: Enforce Admin Policy at execution time
    if client:
        try:
            from prep.core.team_config import parse_admin_policy, is_model_allowed
            admin_policy_raw = ui_cfg.get("_admin_policy_cache")
            if admin_policy_raw:
                policy = parse_admin_policy({"admin_policy": admin_policy_raw})
                if not is_model_allowed(client.model, policy, slot=TASK_TO_SLOT.get(task_id)):
                    logger.warning("Execution blocked by IT Policy: Model '%s' is not allowed for task '%s'", client.model, task_id)
                    from prep.core.audit_log import audit_log
                    audit_log.record(
                        "policy_violation_blocked",
                        f"Execution blocked by IT Policy: Model '{client.model}' not allowed",
                        task_id=task_id,
                        model=client.model,
                        provider=client.provider,
                    )
                    return None
        except Exception as e:
            logger.debug("Failed to enforce admin policy on task %s: %s", task_id, e)
            
    return client


def _resolve_structured_task(task_id: str):
    """Structured-mode resolver: task → slot → slot config."""
    slot = TASK_TO_SLOT.get(task_id, "small")
    client = _get_llm_client_for_slot(slot)
    if not client and slot in _SLOT_FALLBACK_TO_SMALL:
        client = _get_llm_client_for_slot("small")
    return client


def _resolve_mapped_task(task_id: str, llm_cfg: dict):
    """Mapped-mode resolver: task → assignment block → endpoint+model."""
    blocks = llm_cfg.get("assignment_blocks") or []
    for block in blocks:
        if task_id in (block.get("tasks") or []):
            return _create_client_from_block(block, llm_cfg, task_id)
    return None


def _create_client_from_block(block: dict, llm_cfg: dict, task_id: str):
    """Build an LLMClient from a mapped assignment block."""
    endpoint_id = block.get("endpoint_id")
    model = block.get("model")
    if not endpoint_id or not model:
        return None

    endpoints = llm_cfg.get("saved_endpoints") or []
    endpoint = next((ep for ep in endpoints if ep.get("id") == endpoint_id), None)
    if not endpoint:
        return None

    url = endpoint.get("url")
    if not url:
        return None

    from prep.core import LLMClient
    timeout = 600.0 if task_id in _LONG_TIMEOUT_TASKS else 120.0
    return LLMClient(
        endpoint_url=url,
        model=model,
        api_key=endpoint.get("api_key"),
        provider=endpoint.get("provider", "ollama"),
        timeout=timeout,
        always_on=bool(block.get("always_on", False)),
        endpoint_id=endpoint_id,
    )


def _get_model_identity_for_task(task_id: str) -> Optional[tuple]:
    """Return (endpoint_id, model) for a task, or None.

    Used by the VRAM lifecycle manager to detect whether consecutive pipeline
    stages share the same physical model (no unload needed) or different
    models (unload the previous one).
    """
    ui_cfg = _load_ui_config()
    llm_cfg = ui_cfg.get("llm_config") or {}
    mode = llm_cfg.get("assignment_mode", "structured")

    if mode == "mapped":
        for block in llm_cfg.get("assignment_blocks") or []:
            if task_id in (block.get("tasks") or []):
                eid = block.get("endpoint_id")
                mdl = block.get("model")
                return (eid, mdl) if eid and mdl else None
        return None

    # Structured: resolve to slot, then to endpoint+model
    slot = TASK_TO_SLOT.get(task_id, "small")
    SLOT_MAP = {"small": "small_model", "large": "large_model", "code": "code_model"}
    slot_key = SLOT_MAP.get(slot, slot)
    slot_cfg = llm_cfg.get(slot_key) or {}
    if not slot_cfg.get("enabled"):
        if slot in _SLOT_FALLBACK_TO_SMALL:
            slot_cfg = llm_cfg.get("small_model") or {}
        if not slot_cfg.get("enabled"):
            return None
    return (slot_cfg.get("endpoint_id"), slot_cfg.get("model"))


# =============================================================================
# Router Registration (Phase 23 — endpoint extraction)
# =============================================================================
# Routers are imported here (after all helpers/globals are defined) to avoid
# circular imports — each router does `from prep.server import <helper>`.

from prep.api.routers.system import router as system_router
from prep.api.routers.license import router as license_router
from prep.api.routers.trace_routes import router as trace_router
from prep.api.routers.knowledge import router as knowledge_router
from prep.api.routers.llm import router as llm_router
from prep.api.routers.projects import router as projects_router
from prep.api.routers.pipeline import router as pipeline_router
from prep.api.routers.settings import router as settings_router
from prep.api.routers.scope import router as scope_router
from prep.api.routers.scopes import router as scopes_router
from prep.api.routers.observations import router as observations_router
from prep.api.routers.concepts import router as concepts_router
from prep.api.routers.audit import router as audit_router
from prep.api.routers.compute import router as compute_router
from prep.api.routers.goalposts import router as goalposts_router
from prep.api.routers.roadmap import router as roadmap_router
from prep.api.routers.opportunities import router as opportunities_router
from prep.api.routers.pm_push import router as pm_push_router
from prep.api.routers.agents import router as agents_router
from prep.api.routers.architecture import router as architecture_router
from prep.api.routers.mcp_setup import router as mcp_setup_router
from prep.api.routers.collaboration import router as collaboration_router
from prep.api.routers.queue import router as queue_router
from prep.api.routers.roles_endpoints import router as roles_router
app.include_router(system_router)
app.include_router(roles_router)
app.include_router(license_router)
app.include_router(trace_router)
app.include_router(knowledge_router)
app.include_router(llm_router)
app.include_router(projects_router)
app.include_router(pipeline_router)
app.include_router(settings_router)
app.include_router(scope_router)
app.include_router(scopes_router)
app.include_router(observations_router)
app.include_router(concepts_router)
app.include_router(audit_router)
app.include_router(compute_router)
app.include_router(goalposts_router)
app.include_router(roadmap_router)
app.include_router(opportunities_router)
app.include_router(pm_push_router)
app.include_router(agents_router)
app.include_router(architecture_router)
app.include_router(mcp_setup_router)
app.include_router(collaboration_router)
app.include_router(queue_router)


# =============================================================================
# Server Configuration & Main
# =============================================================================

def configure(
    repo_root: Optional[str] = None,
    index_dir: Optional[str] = None,
    ollama_url: str = "http://localhost:11434",
    model: str = "nomic-embed-text",
):
    """Configure the server before starting.

    Phase 113: `index_dir` default is now `paths.data_dir()` (XDG).
    Pass an explicit path to override (deprecated; prefer
    `$PREP_DATA_DIR`).
    """
    global _config, _index, _watcher
    if _watcher is not None:
        try:
            _watcher.stop()
        except Exception:
            pass
        _watcher = None

    from prep.core.paths import data_dir as _data_dir
    resolved_index_dir = index_dir if index_dir else str(_data_dir())

    _config = {
        "repo_root": repo_root,
        "index_dir": resolved_index_dir,
        "ollama_url": ollama_url,
        "model": model,
    }
    _index = None

    # Initialize SQLite settings store (Phase 24)
    from prep.services.settings_store import settings as _settings_store
    idx_path = Path(resolved_index_dir)
    idx_path.mkdir(parents=True, exist_ok=True)
    db_path = idx_path / "prep_settings.db"
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

    # Phase 55: Validate and heal .sourceprep/project.json pointers
    # Ensures every project has a pointer with the correct ID,
    # preventing MCP routing failures for pre-existing projects.
    try:
        report = reg.validate_and_heal_pointers()
        if report.get("healed"):
            logger.info("Healed %d project pointer(s): %s",
                        len(report["healed"]), ", ".join(report["healed"]))
        if report.get("stale"):
            logger.warning("Stale project path(s) (disk missing): %s",
                           ", ".join(report["stale"]))
    except Exception:
        logger.debug("Pointer validation failed (non-fatal)", exc_info=True)

    # Initialize pipeline journal + crash recovery (Phase 25).
    #
    # F-54: dedicated prep_pipeline_journal.db file (same pattern as
    # F-36 concept_store and F-37 antibody_store).  Without this, the
    # journal shares prep_settings.db with settings_store et al, and
    # journal.start_run() during /pipeline/finalize blocks for 30+s on
    # SQLite "database is locked".  Symptom: clicking the Finalize Run
    # button (or auto-mode triggering finalize) silently never starts
    # the pipeline because the API call hangs and the dashboard times
    # out.  Moving to a dedicated file eliminates the cross-store
    # writer-lock contention exactly the same way F-36 fixed concept
    # saves.
    from prep.services.pipeline_journal import journal as _journal
    _journal_db_path = db_path.parent / "prep_pipeline_journal.db"
    _journal.init(_journal_db_path)

    # Initialize pipeline run history (Phase 49: Process Info).
    # F-55: dedicated prep_pipeline_history.db (was sharing prep_settings.db).
    from prep.services.pipeline_history import history as _history
    _history_db_path = db_path.parent / "prep_pipeline_history.db"
    _history.init(_history_db_path)

    # Initialize token telemetry (Phase 56: AI Gateway Phase 2).
    # F-55: dedicated prep_token_telemetry.db (was sharing prep_settings.db).
    from prep.services.token_telemetry import telemetry as _telemetry
    _telemetry_db_path = db_path.parent / "prep_token_telemetry.db"
    _telemetry.init(_telemetry_db_path)

    # Initialize observation store (Phase 39: Session Continuity).
    # F-55: dedicated prep_observations.db (was sharing prep_settings.db).
    from prep.services.observation_store import observation_store as _obs_store
    _obs_store_db_path = db_path.parent / "prep_observations.db"
    _obs_store.init(_obs_store_db_path)

    # Initialize concept store (Phase 74: Epistemic Concepts)
    # Phase 96 / F-36: Use a dedicated concepts.db file instead of the
    # shared prep_settings.db.  When the swarm path saves 26+ concepts
    # in tight succession during finalize, the writer-lock contention
    # against pipeline_journal, pipeline_history, observation_store, and
    # antibody_store (all sharing settings.db) caused SQLITE_BUSY for
    # >30 seconds straight.  Eliminating cross-store contention removes
    # the entire failure mode — concept_store now has its own writer
    # lock that only contends with itself.
    from prep.services.concept_store import concept_store as _concept_store
    _concept_store_db_path = db_path.parent / "prep_concepts.db"

    # One-shot migration: if the dedicated file doesn't exist yet but
    # the shared settings.db has a concepts table, copy the concepts
    # rows over so existing data isn't lost.  Subsequent boots skip
    # this when the dedicated file already exists.
    if not _concept_store_db_path.exists() and db_path.exists():
        try:
            import sqlite3 as _sqlite_migrate
            _src = _sqlite_migrate.connect(str(db_path), timeout=10)
            _has_concepts = _src.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='concepts'"
            ).fetchone()
            if _has_concepts:
                logger.info(
                    "Phase 96/F-36: migrating concepts from %s to %s",
                    db_path, _concept_store_db_path,
                )
                _concept_store.init(_concept_store_db_path)
                _rows = _src.execute("SELECT * FROM concepts").fetchall()
                _migrated = 0
                for _r in _rows:
                    try:
                        _concept_store._conn.execute(
                            "INSERT OR IGNORE INTO concepts VALUES ("
                            + ",".join("?" * len(_r))
                            + ")",
                            tuple(_r),
                        )
                        _migrated += 1
                    except Exception:
                        pass
                # Migrate questions too
                try:
                    _q_rows = _src.execute("SELECT * FROM concept_questions").fetchall()
                    for _qr in _q_rows:
                        try:
                            _concept_store._conn.execute(
                                "INSERT OR IGNORE INTO concept_questions VALUES ("
                                + ",".join("?" * len(_qr))
                                + ")",
                                tuple(_qr),
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
                _concept_store._conn.commit()
                logger.info(
                    "Phase 96/F-36: migrated %d concept rows", _migrated,
                )
            _src.close()
        except Exception as e:
            logger.warning(
                "Phase 96/F-36: concept migration skipped: %s — "
                "starting with empty concepts.db", e,
            )
            try:
                _concept_store.init(_concept_store_db_path)
            except Exception:
                pass
    else:
        _concept_store.init(_concept_store_db_path)

    # Belt-and-suspenders: the migration branch above skips init() when
    # prep_concepts.db is missing AND prep_settings.db exists AND settings.db
    # has no concepts table (e.g. fresh brand-rename data dirs). init() is
    # idempotent, so this is a no-op when migration already called it.
    _concept_store.init(_concept_store_db_path)

    # Phase 119 Task 16: seed built-in "system" concepts (e.g. the
    # discovered-ceiling lock + reset action) so AI agents calling
    # `prep_search` for "concurrency reset" / "rate limit too high"
    # find them. Idempotent — concept_store.save dedupes by title.
    try:
        from prep.core.system_concept_seeder import (
            seed_system_concepts_for_all_projects,
        )
        seed_system_concepts_for_all_projects()
    except Exception:
        logger.debug(
            "Phase 119: system concept seeding failed (non-fatal)",
            exc_info=True,
        )

    # Initialize antibody store (Phase 80: Immune System)
    # F-37: previously never initialized — antibody saves silently failed
    # because the worker catches RuntimeError at DEBUG level.
    # Uses a dedicated antibodies.db file for the same reason concept_store
    # got one (F-36): per-save commits on the shared settings.db hit
    # writer-lock contention against pipeline_journal et al.
    from prep.services.antibody_store import antibody_store as _antibody_store
    _antibody_store_db_path = db_path.parent / "prep_antibodies.db"
    _antibody_store.init(_antibody_store_db_path)

    from prep.services.pipeline_orchestrator import pipeline_orchestrator as _pipeline
    crashed = _pipeline.startup_recovery()
    if crashed:
        logger.warning("Phase 25: %d crashed pipeline run(s) detected on startup", len(crashed))

    # Phase 114 follow-up: checkpoint GC at daemon startup.
    # The happy-path prune hook (run_completed) only fires on successful runs,
    # so projects stuck in a crash loop grow .checkpoints/run-* forever.
    # Startup prune establishes a ceiling of keep=3 per project + _golden.
    try:
        from prep.services.pipeline_checkpoint import prune_checkpoints_all_projects
        prune_checkpoints_all_projects(keep=3)
    except Exception:
        logger.debug("Startup checkpoint prune failed (non-fatal)", exc_info=True)

    # Initialize pipeline scheduler (Phase 45: Multi-GPU Concurrency)
    from prep.services.pipeline.scheduler import pipeline_scheduler as _scheduler
    _scheduler.load_from_settings()

    # Phase 127 sub-phase 5: restore priority state across daemon restart.
    # Must run AFTER load_from_settings (configure_node populates the slot
    # map that priority operates on) but BEFORE any pipeline tasks resume
    # so the restored holds/queue ordering takes effect on the first
    # post-startup dispatch.
    _scheduler.load_priority_state()

    # Auto-run pipeline on startup if settings are set to Auto mode.
    # Checks persisted pipeline_config and triggers runs for projects with
    # stale or incomplete graphs.  Runs in a background thread with a short
    # delay so the server finishes initialization first.
    import threading

    def _startup_auto_run():
        import time
        time.sleep(3)  # Let server fully initialize
        try:
            # 2026-05 follow-up to F-65: the global pipeline_config is read for
            # diagnostic logging only — it is no longer a source of truth for
            # auto-run gating. Each project must explicitly opt in via
            # `auto_config.fastSync` / `auto_config.deepEnrichment`. A project
            # whose IndexStatusCard reads Manual must never auto-fire on
            # daemon restart, even if a stale global flag is set to auto.
            from prep.services.settings_store import settings as _ss
            pc = _ss.get("pipeline_config") or {}
            global_fast_auto = (pc.get("fast_sync") or {}).get("auto", False)
            global_deep_mode = (pc.get("deep_enrichment") or {}).get("mode", "manual")

            logger.info(
                "Startup auto-run check (diagnostic): fast_sync.auto=%s, deep_enrichment.mode=%s "
                "(global is no longer a fallback — per-project auto_config is authoritative)",
                global_fast_auto, global_deep_mode,
            )

            from prep.services.pipeline_orchestrator import pipeline_orchestrator as _po
            from prep.services.project_helpers import (
                get_registry, is_project_active, get_project_activity_status,
            )
            all_projects = get_registry().list_projects()
            projects = []
            for p in all_projects:
                pcfg = p.config if isinstance(p.config, dict) else {}
                trace_cfg = pcfg.get("trace") if isinstance(pcfg.get("trace"), dict) else {}
                if not trace_cfg.get("enabled"):
                    logger.debug("Startup auto-run: skipping %s (trace not enabled)", p.name)
                    continue
                # Skip inactive (Pro toggle) and frozen/locked (Free tier)
                status = get_project_activity_status(p.id)
                if status not in ("active",):
                    logger.info("Startup auto-run: skipping %s (status=%s, not active)", p.name, status)
                    continue
                projects.append(p)

            logger.info(
                "Startup auto-run: %d active trace-enabled project(s) out of %d total",
                len(projects), len(all_projects),
            )

            # Process projects sequentially but with a max wait per project
            # to prevent the thread from blocking forever on a slow model.
            MAX_WAIT_PER_PROJECT = 120  # seconds to wait before moving to next
            for proj in projects:
                # 2026-05: Per-project auto_config is the only authority.
                # Falling back to the global flag was the regression — it
                # caused projects with their UI on Manual to auto-fire after
                # daemon restart whenever the global default was still auto.
                # Default to manual (False / "manual") when the project has
                # never explicitly set its own auto_config.
                pcfg = proj.config if isinstance(proj.config, dict) else {}
                proj_auto = pcfg.get("auto_config") or {}
                fast_auto = bool(proj_auto.get("fastSync", proj_auto.get("fast_sync", False)))
                deep_mode = proj_auto.get("deepEnrichment", proj_auto.get("deep_enrichment", "manual"))

                # Phase 45 Fix: Check if project is actually stale or incomplete before running
                from prep.services.build_manager import build_manager as _bm
                from prep.services.project_helpers import check_index_staleness

                idx = _bm.get_project_index(proj)
                staleness = check_index_staleness(proj, idx)
                is_stale = staleness.get("is_stale", True)

                trace_idx = _bm.get_project_trace_index(proj)
                has_graph = trace_idx is not None and trace_idx.node_count() > 0

                needs_fast_sync = is_stale or not has_graph

                # Phase 48-F8: Even if we have a graph and it's not "stale"
                # by mtime, check if there are untraced files on disk.
                if not needs_fast_sync and has_graph:
                    try:
                        gap = _po.check_coverage_gap(proj.id)
                        if gap.get("needs_rebuild"):
                            needs_fast_sync = True
                            logger.info(
                                "Startup auto-run: coverage gap for %s — "
                                "%d untraced + %d stale (%.1f%% coverage)",
                                proj.name,
                                gap.get("untraced", 0),
                                gap.get("stale", 0),
                                gap.get("coverage_pct", 0),
                            )
                    except Exception:
                        logger.debug(
                            "Startup coverage gap check failed for %s",
                            proj.name, exc_info=True,
                        )

                # Check if deep enrichment needs to run (has graph but incomplete)
                needs_deep = False
                if has_graph and not is_stale and deep_mode == "auto":
                    from prep.services.pipeline.recovery import RecoveryManager
                    was_clean = RecoveryManager.check_clean_shutdown_marker(proj.id)
                    if was_clean:
                        logger.info(
                            "Startup auto-run: skipping deep enrichment for %s "
                            "(clean shutdown marker — pending nodes are steady-state)",
                            proj.name,
                        )
                    else:
                        from prep.core.epistemic_enrichment import EpistemicEnricher
                        from prep.core.project_registry import project_index_dir
                        llm = _get_llm_client_for_task("enrichment")
                        idx_dir = project_index_dir(proj)
                        enricher = EpistemicEnricher(llm=llm, repo_root=Path(proj.path), index_dir=idx_dir)
                        pending = enricher.get_pending_nodes(trace_idx)
                        if pending:
                            needs_deep = True

                started = False
                if needs_fast_sync and fast_auto and deep_mode == "auto":
                    started = _po.run_all(proj.id)
                    logger.info("Startup auto-run: run_all for %s — started=%s", proj.name, started)
                elif needs_fast_sync and fast_auto:
                    started = _po.run_fast_sync(proj.id)
                    logger.info("Startup auto-run: fast_sync for %s — started=%s", proj.name, started)
                elif needs_deep and deep_mode == "auto":
                    started = _po.run_deep_enrichment(proj.id)
                    logger.info("Startup auto-run: deep_enrichment for %s — started=%s", proj.name, started)
                else:
                    logger.info("Startup auto-run: skipping %s (already up to date)", proj.name)
                    continue

                if started:
                    # Wait up to MAX_WAIT before moving to the next project.
                    # The pipeline will continue running in the background.
                    waited = 0
                    while waited < MAX_WAIT_PER_PROJECT:
                        time.sleep(2)
                        waited += 2
                        st = _po.status(proj.id)
                        if not st.get("any_running"):
                            break
                    if waited >= MAX_WAIT_PER_PROJECT:
                        logger.info(
                            "Startup auto-run: %s still running after %ds, moving to next project",
                            proj.name, MAX_WAIT_PER_PROJECT,
                        )

            logger.info("Startup auto-run: all projects triggered")
        except Exception:
            logger.warning("Startup auto-run failed", exc_info=True)

    threading.Thread(target=_startup_auto_run, daemon=True).start()

    # Phase 26 (S-26.3): Start schedule evaluator for scheduled deep enrichment
    try:
        from prep.services.pipeline_budget import schedule as _schedule
        _schedule.start(
            run_callback=lambda pid: _pipeline.run_deep_enrichment(pid),
            check_interval=60.0,
        )
    except Exception:
        logger.debug("Schedule evaluator startup failed (non-fatal)", exc_info=True)

    # Note: Pipeline scheduler already initialized above (line ~597).

    # Team Sync: auto-start RemoteSyncService polling for projects with sync enabled
    try:
        from prep.core.feature_gate import check_feature
        if check_feature("team_config"):
            for proj in reg.list_projects():
                try:
                    sync_status = _get_project_sync_status(proj)
                    if sync_status.get("enabled"):
                        logger.info("Team sync polling started for project %s", proj.name)
                except Exception:
                    logger.debug("Team sync init failed for %s (non-fatal)", proj.name, exc_info=True)
    except Exception:
        logger.debug("Team sync startup failed (non-fatal)", exc_info=True)


def mount_dashboard():
    """Mount the static dashboard if available."""
    dashboard_dir = Path(__file__).parent / "dashboard" / "dist"
    if dashboard_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
        logger.info("Dashboard mounted at /ui from %s", dashboard_dir)
    else:
        logger.warning("Dashboard not found at %s - run 'npm run build' in dashboard/", dashboard_dir)


def main():
    parser = argparse.ArgumentParser(description="SourcePrep Server")
    parser.add_argument("--repo-root", help="Default repository root to index")
    parser.add_argument(
        "--index-dir",
        default=None,
        help="Directory to store index (deprecated; default is $PREP_DATA_DIR or ~/.local/share/runprep/)",
    )
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
    logger.info("Starting SourcePrep server on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

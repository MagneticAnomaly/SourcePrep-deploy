"""
CoDRAG System Router — Phase 23 Sprint 9
=========================================

**Origin:** Extracted from ``server.py`` (lines ~103–157, 1453–1470, 4161–4286).

**Endpoints moved here:**
  - GET  /health          — daemon health check
  - GET  /                — root API info
  - GET  /events          — SSE stream (logs + progress)
  - GET  /api/code-index/mcp-config — MCP IDE integration config
  - GET  /global/config   — read global UI/LLM config
  - PUT  /global/config   — merge-update global config
  - GET  /api/code-index/config  (deprecated alias)
  - PUT  /api/code-index/config  (deprecated alias)

**Shared state accessed (from server.py):**
  - ``_config``           — CLI launch config (repo_root, index_dir, etc.)
  - ``_index``            — legacy singleton CodeIndex (cleared on embedding change)
  - ``_project_indexes``  — per-project CodeIndex cache (cleared on embedding change)
  - ``_load_ui_config``   — reads ``codrag_data/ui_config.json`` with defaults
  - ``_save_ui_config``   — writes merged config back
  - ``_deep_merge``       — recursive dict merge helper

**Phase 24 note (State Machine):**
  The ``/events`` SSE endpoint is the backbone of SM-8 (Daemon Lifecycle).
  When we introduce proper state machine transitions, the event bus should
  emit typed ``state_transition`` events so the frontend can subscribe to
  machine-level changes rather than polling individual status endpoints.
  The ``/global/config`` endpoints will eventually be gated by SM-7
  (License & Feature Gate) at transition time.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from codrag import __version__
from codrag.api.envelope import ApiException, ok
from codrag.core.events import get_event_bus
from codrag.mcp_config import generate_mcp_configs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


# ── Pydantic models ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str


# ── Health & root ────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/")
def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": "CoDRAG",
        "version": __version__,
        "description": "Code Documentation and RAG",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/code-index/status",
    }


# ── SSE event stream ────────────────────────────────────────────

@router.get("/events")
async def events_endpoint(request: Request):
    """
    Server-Sent Events (SSE) endpoint for real-time logs and progress.
    Uses stdlib queue.Queue (thread-safe) polled via asyncio.sleep.
    """
    import queue as _queue
    import asyncio as _asyncio
    import time as _time

    bus = get_event_bus()
    q = bus.subscribe()

    async def event_generator():
        try:
            # Send an initial comment so the client sees an open stream
            yield ": connected\n\n"

            heartbeat_interval = 15  # seconds between heartbeats
            last_heartbeat = _time.time()

            while True:
                # Drain all available events (non-blocking)
                had_events = False
                try:
                    while True:
                        payload = q.get_nowait()
                        yield f"data: {json.dumps(payload)}\n\n"
                        had_events = True
                except _queue.Empty:
                    pass

                if not had_events:
                    # Send heartbeat comment to keep connection alive
                    now = _time.time()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    await _asyncio.sleep(0.2)
        except _asyncio.CancelledError:
            pass
        except GeneratorExit:
            pass
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── MCP config ───────────────────────────────────────────────────

@router.get("/api/code-index/mcp-config")
def get_mcp_config(
    request: Request,
    ide: str = Query("all"),
    mode: str = Query("auto"),
    daemon_url: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
) -> Dict[str, Any]:
    effective_daemon_url = str(daemon_url).strip() if daemon_url else str(request.base_url).rstrip("/")
    effective_project_id = project_id or project

    try:
        configs = generate_mcp_configs(
            ide=str(ide).strip().lower(),
            daemon_url=effective_daemon_url,
            mode=str(mode).strip().lower(),
            project_id=effective_project_id,
        )
    except ValueError as e:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=str(e))

    norm_ide = str(ide).strip().lower() if ide else "all"
    if norm_ide == "all":
        return ok({"daemon_url": effective_daemon_url, "configs": configs})

    entry = configs.get(norm_ide)
    if entry is None:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=f"Unknown IDE: {ide}")

    payload = {"daemon_url": effective_daemon_url, **entry}
    return ok(payload)


# ── Global config ────────────────────────────────────────────────

@router.get("/global/config")
def get_global_config_v2() -> Dict[str, Any]:
    """Get global UI configuration."""
    from codrag.server import _load_ui_config
    return ok(_load_ui_config())


@router.put("/global/config")
async def update_global_config_v2(req: Request) -> Dict[str, Any]:
    """Update global UI configuration (merge update)."""
    from codrag.server import (
        _load_ui_config, _save_ui_config, _deep_merge,
        _index, _project_indexes,
    )

    try:
        data = await req.json()
    except Exception:
        raise ApiException(status_code=400, code="INVALID_JSON", message="Invalid JSON body")

    if not isinstance(data, dict):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="Config must be a JSON object")

    current = _load_ui_config()

    old_emb = (current.get("llm_config") or {}).get("embedding") or {}
    new_emb = (data.get("llm_config") or {}).get("embedding") or {}
    embedding_changed = new_emb and (
        new_emb.get("source") != old_emb.get("source")
        or new_emb.get("endpoint_id") != old_emb.get("endpoint_id")
        or new_emb.get("model") != old_emb.get("model")
    )

    _deep_merge(current, data)
    _save_ui_config(current)

    if embedding_changed:
        import codrag.server as _srv
        _srv._index = None
        _srv._project_indexes.clear()
        logger.info("Embedding config changed — cleared cached indexes")

    return ok(current)


# ── Deprecated config aliases ────────────────────────────────────

@router.get("/api/code-index/config", deprecated=True)
def get_global_config(response: Response) -> Dict[str, Any]:
    """Get global UI configuration.

    DEPRECATED: Use GET /global/config instead.
    """
    from codrag.server import _load_ui_config
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-06-01"
    logger.warning("DEPRECATED: GET /api/code-index/config called — migrate to /global/config")
    return ok(_load_ui_config())


@router.put("/api/code-index/config", deprecated=True)
async def update_global_config(req: Request, response: Response) -> Dict[str, Any]:
    """Update global UI configuration (merge update).

    DEPRECATED: Use PUT /global/config instead.
    """
    from codrag.server import (
        _load_ui_config, _save_ui_config, _deep_merge,
    )
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-06-01"
    logger.warning("DEPRECATED: PUT /api/code-index/config called — migrate to /global/config")

    try:
        data = await req.json()
    except Exception:
        raise ApiException(status_code=400, code="INVALID_JSON", message="Invalid JSON body")

    if not isinstance(data, dict):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="Config must be a JSON object")

    current = _load_ui_config()

    # Detect if embedding config changed — if so, invalidate cached indexes
    # so the next build/search creates a fresh embedder from new settings.
    old_emb = (current.get("llm_config") or {}).get("embedding") or {}
    new_emb = (data.get("llm_config") or {}).get("embedding") or {}
    embedding_changed = new_emb and (
        new_emb.get("source") != old_emb.get("source")
        or new_emb.get("endpoint_id") != old_emb.get("endpoint_id")
        or new_emb.get("model") != old_emb.get("model")
    )

    # Use deep merge to prevent overwriting nested keys with partial updates
    _deep_merge(current, data)
    _save_ui_config(current)

    if embedding_changed:
        import codrag.server as _srv
        _srv._index = None
        _srv._project_indexes.clear()
        logger.info("Embedding config changed — cleared cached indexes")

    return ok(current)

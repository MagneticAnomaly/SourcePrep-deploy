"""
Prep System Router — Phase 23 Sprint 9
=========================================

**Origin:** Extracted from ``server.py`` (lines ~103–157, 1453–1470, 4161–4286).

**Endpoints moved here:**
  - GET  /health          — daemon health check
  - GET  /                — root API info
  - GET  /events          — SSE stream (logs + progress)
  - GET  /mcp/config      — MCP IDE integration config
  - GET  /global/config   — read global UI/LLM config
  - PUT  /global/config   — merge-update global config

**Shared state accessed (from server.py):**
  - ``_config``           — CLI launch config (repo_root, index_dir, etc.)
  - ``_index``            — legacy singleton CodeIndex (cleared on embedding change)
  - ``_project_indexes``  — per-project CodeIndex cache (cleared on embedding change)
  - ``_load_ui_config``   — reads ``<data_dir>/ui_config.json`` with defaults
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

import functools
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from prep import __version__
from prep.api.envelope import ApiException, ok
from prep.core.events import get_event_bus
from prep.mcp_config import generate_mcp_configs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


# ── Pydantic models ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str


# ── Health & root ────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint.

    F-70: Made async so it runs directly on the event loop without
    needing a thread pool slot. When cloud model calls block all
    thread pool slots, sync endpoints timeout — but the dashboard
    polls /health to detect if the daemon is alive.
    """
    return HealthResponse(status="ok", version=__version__)


@router.get("/system/threads")
def thread_dump() -> dict:
    """Dump all Python threads with their stack traces.

    Diagnostic endpoint for debugging thread accumulation and GIL
    contention.  Returns thread count, per-thread stacks, and a
    summary of thread name prefixes.
    """
    import sys
    import threading
    import traceback

    threads = threading.enumerate()
    stacks = sys._current_frames()

    thread_list = []
    name_counts: dict = {}
    for t in threads:
        # Count by name prefix (e.g. "llm-pool_0" → "llm-pool")
        prefix = t.name.rsplit("_", 1)[0] if "_" in t.name else t.name
        # Also strip trailing digits for "build-xxx-trace" → "build"
        if prefix.startswith("build-"):
            prefix = "build-*"
        name_counts[prefix] = name_counts.get(prefix, 0) + 1

        frame = stacks.get(t.ident)
        stack_lines = []
        if frame:
            stack_lines = traceback.format_stack(frame)
            # Truncate to last 8 frames for readability
            if len(stack_lines) > 8:
                stack_lines = ["  ... (truncated)\n"] + stack_lines[-8:]

        thread_list.append({
            "name": t.name,
            "ident": t.ident,
            "daemon": t.daemon,
            "alive": t.is_alive(),
            "stack": "".join(stack_lines).rstrip(),
        })

    return {
        "thread_count": len(threads),
        "summary": dict(sorted(name_counts.items(), key=lambda x: -x[1])),
        "threads": thread_list,
    }


@router.get("/")
def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": "Prep",
        "version": __version__,
        "description": "Code Documentation and RAG",
        "docs": "/docs",
        "health": "/health",
        "api": "/projects",
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


# ── Swarm events log (Phase 119 verbose logging) ─────────────────


@router.get("/system/swarm-events")
def swarm_events(
    file: Optional[str] = Query(None, description="Specific JSONL filename (basename only)"),
    run_id: Optional[str] = Query(None, description="Match run_id substring (first 8 chars in filename)"),
    stage: Optional[str] = Query(None, description="Match stage substring in filename"),
    limit: int = Query(50, ge=1, le=500, description="Max log files to list"),
) -> Dict[str, Any]:
    """List or read per-swarm-execution JSONL event logs.

    With no parameters, returns a directory listing of recent swarm log
    files (newest first).  Pass ``file=<basename>`` to read one log's
    full event sequence.  ``run_id`` / ``stage`` filter the listing by
    filename substring (filenames embed both fields).

    Phase 119: this is the back-end for the developer-popover footer
    that points users to the verbose swarm log directory, and for
    agents that want to reconstruct a swarm post-hoc.
    """
    from prep.core.paths import data_dir

    log_root = data_dir() / "logs" / "swarm"

    # ── Read a specific file ─────────────────────────────────────
    if file:
        # Reject path traversal — only allow plain basenames.  The check
        # runs before the log_root.exists() short-circuit so a hostile
        # path is always rejected with 400, regardless of whether the
        # logs directory has been materialised yet.
        if "/" in file or "\\" in file or ".." in file:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message="invalid file name",
            )
        if not log_root.exists():
            raise ApiException(
                status_code=404,
                code="NOT_FOUND",
                message=f"swarm log not found: {file}",
            )
        target = log_root / file
        if not target.exists() or not target.is_file():
            raise ApiException(
                status_code=404,
                code="NOT_FOUND",
                message=f"swarm log not found: {file}",
            )
        events: List[Dict[str, Any]] = []
        try:
            for line in target.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    # Tolerate truncated last line on a still-running swarm
                    pass
        except Exception as exc:
            raise ApiException(
                status_code=500,
                code="INTERNAL_ERROR",
                message=f"read failed: {exc}",
            ) from exc
        return {
            "ok": True,
            "log_dir": str(log_root),
            "file": file,
            "events": events,
            "n_events": len(events),
        }

    # ── List files ───────────────────────────────────────────────
    if not log_root.exists():
        return {"ok": True, "log_dir": str(log_root), "files": [], "events": None}

    candidates = sorted(
        log_root.glob("swarm_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    files: List[Dict[str, Any]] = []
    for p in candidates:
        name = p.name
        if run_id and run_id not in name:
            continue
        if stage and stage not in name:
            continue
        try:
            st = p.stat()
            files.append({
                "name": name,
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
        except Exception:
            continue
        if len(files) >= limit:
            break
    return {
        "ok": True,
        "log_dir": str(log_root),
        "files": files,
        "events": None,
    }


# ── MCP config ───────────────────────────────────────────────────

@router.get("/mcp/config")
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
    from prep.server import _load_ui_config
    return ok(_load_ui_config())


# Phase 119 Phase A: provider key map from SavedEndpoint.provider →
# concurrency_limits.json provider key.  Header-rich providers
# (auto_detect=true) can save with plan_tier='auto'; others must pick a
# tier or supply an explicit cloud_concurrency.
_PROVIDER_TO_LIMITS_KEY: Dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google_gemini",
    # Note: 'ollama' resolves to ollama_local for localhost URLs and
    # ollama_cloud for ollama.com hosts — see _resolve_ollama_provider_key.
    # Note: 'kimi' is intentionally absent — the LLMProvider TS union does
    # not include it.  Restore "kimi": "moonshot_kimi" if/when the provider
    # type is added.
}


@functools.lru_cache(maxsize=1)
def _load_limits_table() -> Dict[str, Any]:
    """Read concurrency_limits.json once.  Returns empty dict on read failure.

    Phase 119 Phase A fix-up: cached so a single PUT /global/config that
    iterates through saved_endpoints does not re-read the file N times.
    """
    path = Path(__file__).resolve().parent.parent.parent / "data" / "concurrency_limits.json"
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.warning("validate-endpoint: cannot read %s: %s", path, exc)
        return {}


def _resolve_ollama_provider_key(url: str) -> str:
    """An 'ollama' provider can be local (auto_detect via /api/ps) or cloud
    (no headers).  Use the URL host to disambiguate."""
    host = ""
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    # ollama.com / *.ollama.com → cloud; everything else (localhost, 127.x,
    # private LAN) is treated as local OSS.
    if host == "ollama.com" or host.endswith(".ollama.com"):
        return "ollama_cloud"
    return "ollama_local"


def _validate_endpoint_concurrency(endpoint: Dict[str, Any]) -> List[str]:
    """Phase 119 Phase A: warn when a no-auto-detect provider has neither an
    explicit ``plan_tier`` nor a positive ``cloud_concurrency``.

    Returns a list of warning strings — empty list means OK.  Pulled from
    src/prep/data/concurrency_limits.json (the GET /llm/plan-limits source).
    """
    if not isinstance(endpoint, dict):
        return []

    provider = str(endpoint.get("provider", "")).lower().strip()
    if not provider:
        return []

    url = str(endpoint.get("url", ""))
    if provider == "ollama":
        table_key = _resolve_ollama_provider_key(url)
    else:
        table_key = _PROVIDER_TO_LIMITS_KEY.get(provider)
    if not table_key:
        return []  # Unknown / OSS-only provider — nothing to validate.

    table = _load_limits_table()
    if not table:
        return []  # If the table is unreadable, don't block saves.

    provider_entry = table.get("providers", {}).get(table_key)
    if not provider_entry:
        return []

    plan_tier = endpoint.get("plan_tier")
    cloud_concurrency = endpoint.get("cloud_concurrency")
    has_explicit_tier = bool(plan_tier) and plan_tier not in ("", "auto")
    has_explicit_concurrency = (
        isinstance(cloud_concurrency, int) and cloud_concurrency > 0
    )

    if not provider_entry.get("auto_detect", True) and not (
        has_explicit_tier or has_explicit_concurrency
    ):
        name = endpoint.get("name") or endpoint.get("id") or table_key
        return [
            f"Endpoint '{name}' ({provider_entry.get('label', table_key)}): "
            f"please pick a Plan tier from the dropdown so concurrency can be "
            f"capped correctly. This provider does not expose rate-limit "
            f"headers, so we cannot auto-detect."
        ]
    return []


@router.put("/global/config")
async def update_global_config_v2(req: Request) -> Dict[str, Any]:
    """Update global UI configuration (merge update).

    Runs the blocking SQLite load/save in a thread pool so the asyncio
    event loop stays responsive during lock contention.

    Phase 119 Phase A: when the patch contains ``llm_config.saved_endpoints``,
    each endpoint is run through ``_validate_endpoint_concurrency``.  Warnings
    are returned in the response envelope under ``warnings`` (the save still
    proceeds — the UI surfaces the warning so the user can pick a tier).
    """
    import asyncio
    from prep.server import (
        _load_ui_config, _save_ui_config,
        _index, _project_indexes,
    )
    # 2026-06-09: _deep_merge was moved out of prep.server into
    # prep.services.config_manager in commit f3dbd219 (Phase 139 PR2)
    # but this import was never updated. The ImportError fires only
    # on PUT /global/config (never at startup), so the latent break
    # surfaced as a hard 500 every time the dashboard tried to save
    # the global config — the root cause of the 2026-06-09 UI hang
    # (dashboard saves theme/layout on load → 500 → bad state).
    from prep.services.config_manager import deep_merge as _deep_merge

    try:
        data = await req.json()
    except Exception:
        raise ApiException(status_code=400, code="INVALID_JSON", message="Invalid JSON body")

    if not isinstance(data, dict):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="Config must be a JSON object")

    # Phase 119 Phase A: collect concurrency warnings before save.
    warnings: List[str] = []
    incoming_endpoints = (
        ((data.get("llm_config") or {}).get("saved_endpoints"))
        if isinstance(data.get("llm_config"), dict)
        else None
    )
    if isinstance(incoming_endpoints, list):
        for ep in incoming_endpoints:
            warnings.extend(_validate_endpoint_concurrency(ep))

    def _do_save() -> Dict[str, Any]:
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

        # Phase 72: Live-sync endpoint concurrency into the scheduler
        try:
            from prep.services.pipeline.scheduler import pipeline_scheduler
            pipeline_scheduler.sync_endpoint_concurrency()
        except Exception:
            pass

        if embedding_changed:
            import prep.server as _srv
            _srv._index = None
            _srv._project_indexes.clear()
            logger.info("Embedding config changed — cleared cached indexes")

        return current

    try:
        current = await asyncio.get_event_loop().run_in_executor(None, _do_save)
    except Exception as e:
        logger.exception("Failed to save global config")
        raise ApiException(status_code=500, code="CONFIG_SAVE_ERROR", message=f"Failed to save config: {e}")

    response = ok(current)
    if warnings:
        response["warnings"] = warnings
    return response

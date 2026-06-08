"""Prep LLM Router — Phase 23 Sprint 13 (updated Phase 31)
========================================

**Endpoints:**
  Embedding:
    - GET  /embedding/status    — native embedder availability & cache status
    - POST /embedding/download  — download HF model to local cache

  LLM Slots & Status:
    - GET  /llm/slots/status    — per-slot connectivity check (embedding, small, large)
    - GET  /llm/status          — legacy Ollama connectivity
    - GET  /api/llm/status      — alias for above

  LLM Testing & Proxy:
    - POST /llm/test            — legacy quick connectivity test
    - POST /api/llm/test        — alias for above
    - POST /api/llm/proxy/models     — list models from an endpoint
    - POST /api/llm/proxy/test       — test endpoint connectivity
    - POST /api/llm/model-status     — model readiness / preload
    - POST /api/llm/proxy/test-model — test a specific model with readiness gate

**Shared state accessed (from server.py):**
  - ``_config``           — CLI config (ollama_url, model)
  - ``_load_ui_config``   — read global config for llm_config slots
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import urllib.parse
import ipaddress
import socket

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok
from prep.core import NativeEmbedder
from prep.core.model_readiness import (
    ModelStatus,
    get_model_status,
    ensure_model_ready,
)

# Known local LLM provider ports allowed on loopback
_ALLOWED_LOCAL_PORTS = {11434, 1234, 1235}  # Ollama, LM Studio


def _stage_value(stage: Any) -> str:
    """Coerce a StageId-or-str to its string value for comparison.

    The scheduler's swarm window stores ``stage`` as a StageId enum
    (set by orchestrator.py before calling open_swarm_window) but the
    UI surfaces stages as strings.  This helper normalises so the
    runtime comparison in the running-tasks enrichment is enum-safe.
    """
    if stage is None:
        return ""
    return getattr(stage, "value", stage) if not isinstance(stage, str) else stage


def _summarize_swarm_phases(
    active: List[Dict[str, Any]],
    *,
    project_id: str,
    task_id: str,
) -> Dict[str, Dict[str, Any]]:
    """Group live LLM calls by their swarm role for the AI Gateway UI.

    Returns a dict with keys ``coordinator``, ``workers``, ``synthesizer``.
    Each value is ``{"active": int, "model": str | None}``.  Calls
    without ``swarm_role`` set are omitted — they were not part of a
    real swarm phase, even when the swarm window is open (e.g. a non-
    orchestrator path that happens to fire during the swarm).

    Phase 119 Swarm Authority: this is the data the UI uses to render
    the three-phase breakdown.  When all three buckets are empty the
    UI suppresses the breakdown rather than fabricating empty rows.
    """
    buckets: Dict[str, Dict[str, Any]] = {
        "coordinator": {"active": 0, "model": None},
        "workers": {"active": 0, "model": None},
        "synthesizer": {"active": 0, "model": None},
    }
    role_to_bucket = {
        "coordinator": "coordinator",
        "worker": "workers",
        "synthesizer": "synthesizer",
    }
    for req in active:
        if req.get("project_id") != project_id:
            continue
        if task_id and req.get("task_id") != task_id:
            continue
        role = req.get("swarm_role")
        bucket_key = role_to_bucket.get(role)
        if bucket_key is None:
            continue
        bucket = buckets[bucket_key]
        bucket["active"] = int(bucket["active"]) + 1
        if not bucket["model"]:
            bucket["model"] = req.get("model")
    return buckets


def _running_task_state(
    *,
    project_id: str,
    is_held: bool,
    held_reason: Optional[str],
    is_swarm: bool,
) -> str:
    """Phase 127: classify a running task into one of:
    - "held"           : soft-held by exclusive or swarm window
    - "swarm_active"   : actively in a swarm session
    - "running"        : normal pipeline activity

    The dashboard uses this to render a single per-task badge instead
    of inferring state from a combination of is_held / is_swarm flags.
    """
    if is_held:
        return "held"
    if is_swarm:
        return "swarm_active"
    return "running"


def _count_live_workers(*, project_id: str, task_id: str) -> int:
    """Count in-flight LLM requests matching (project_id, task_id).

    Phase 82 completion: the AI Gateway UI now reflects actual API call
    concurrency, not the scheduler's configured maximum. The scheduler
    has adaptive discovery and can run above or below its configured
    cloud_concurrency, so a static read is misleading. Live telemetry is
    authoritative.

    ``model_slot`` is intentionally not filtered on — this counts the
    total in-flight calls for the gate badge; per-slot bucketing is
    done downstream in the swarm split.  Phase 119 added slot tagging
    via ``server._get_llm_client_for_slot``, so newer telemetry entries
    DO carry ``model_slot``; legacy LLMClient construction paths still
    leave it ``None``.  Either way, the gate-total semantics here want
    the unfiltered count.
    """
    from prep.services.token_telemetry import telemetry

    count = 0
    for req in telemetry.get_active_requests():
        if req.get("project_id") != project_id:
            continue
        # task_id optional-match: if provided, filter on it; otherwise accept all
        if task_id and req.get("task_id") != task_id:
            continue
        count += 1
    return count

def is_safe_url(url: str, provider: str) -> bool:
    """SSRF protection: ensure URL is HTTP/HTTPS and not targeting private networks.

    Local providers (ollama, lm-studio) are allowed on specific ports.
    Cloud metadata endpoints (169.254.x.x) are always blocked.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname or ""
        port = parsed.port

        # Always block cloud metadata endpoint (AWS/GCP/Azure)
        if hostname in ("169.254.169.254", "metadata.google.internal"):
            return False

        # Local providers need loopback access
        if provider in ("ollama", "lm-studio"):
            return True

        # For cloud providers, block private/reserved IP ranges
        try:
            resolved = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
            for _, _, _, _, sockaddr in resolved:
                ip = ipaddress.ip_address(sockaddr[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    if ip.is_loopback and port in _ALLOWED_LOCAL_PORTS:
                        return True
                    return False
        except (socket.gaierror, ValueError, OSError):
            pass  # DNS resolution failed — allow (cloud endpoints may not resolve locally)

        return True
    except Exception:
        return False

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm"])


# ── Gemini free-tier rate limits (Mar 2026) ─────────────────────
# Source: https://ai.google.dev/pricing
_GEMINI_RATE_FALLBACKS: List[tuple] = [
    ("gemini-2.5-flash",  {"rpd": 500,  "rpm": 10}),
    ("gemini-2.5-pro",    {"rpd": 25,   "rpm": 5}),
    ("gemini-2.0-flash",  {"rpd": 1500, "rpm": 15}),
    ("gemini-1.5-flash",  {"rpd": 1500, "rpm": 15}),
    ("gemini-1.5-pro",    {"rpd": 50,   "rpm": 2}),
    ("gemini-3-flash",    {"rpd": 500,  "rpm": 10}),
    ("gemini-3-pro",      {"rpd": 25,   "rpm": 5}),
    ("gemini-3.1-flash",  {"rpd": 500,  "rpm": 10}),
    ("gemini-3.1-pro",    {"rpd": 25,   "rpm": 5}),
    ("gemma",             {"rpd": 1500, "rpm": 15}),
]

def _get_gemini_rate_limits(model_id: str) -> Optional[Dict[str, int]]:
    for prefix, limits in _GEMINI_RATE_FALLBACKS:
        if model_id.startswith(prefix):
            return limits
    return None

_AVG_PROMPT_TOKENS = 3000  # conservative per-file prompt size


# ── Pydantic models ─────────────────────────────────────────────

class ModeSwitchRequest(BaseModel):
    mode: str  # "structured" or "mapped"
    assignment_blocks: Optional[List[Dict[str, Any]]] = None


class LLMProxyRequest(BaseModel):
    provider: str = "ollama"
    url: str
    api_key: Optional[str] = None
    slot: Optional[str] = None  # Model slot context for filtering (e.g. "code_model")


class LLMModelTestRequest(BaseModel):
    provider: str = "ollama"
    url: str
    model: str
    api_key: Optional[str] = None
    kind: str = "completion"
    slot: Optional[str] = None  # small_model, large_model, code_model — for context recommendations


# ── Context Window Recommendations ────────────────────────────────
# Minimum recommended context window per model slot.
# Deep stages (epistemic, group reasoning, deepening) routinely send
# 8K–30K token prompts; the model needs headroom for output too.
_SLOT_MIN_CONTEXT: Dict[str, int] = {
    "small_model": 4096,
    "code_model": 8192,
    "large_model": 32768,
}
_SLOT_LABELS: Dict[str, str] = {
    "small_model": "Catalogue / Fast stages",
    "code_model": "Inferred Edges (code analysis)",
    "large_model": "Deep Reasoning (epistemic, group reasoning, deepening)",
}


def _query_context_window(
    provider: str, url: str, model: str, api_key: Optional[str] = None,
) -> Optional[int]:
    """Try to detect the model's current context window size.

    - Ollama: ``/api/show`` returns model parameters including ``num_ctx``.
    - LM Studio / OpenAI-compatible: no standard API for this; returns None.
    """
    url = url.rstrip("/")
    try:
        if provider == "ollama":
            r = requests.post(
                f"{url}/api/show",
                json={"model": model},
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                # Ollama returns model_info with context length
                model_info = data.get("model_info") or {}
                for key, val in model_info.items():
                    if "context_length" in key and isinstance(val, (int, float)):
                        return int(val)
                # Fallback: check parameters string for num_ctx
                params = data.get("parameters") or ""
                for line in params.split("\n"):
                    if "num_ctx" in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                return int(parts[-1])
                            except ValueError:
                                pass
    except Exception:
        pass
    return None


class ModelStatusRequest(BaseModel):
    provider: str = "ollama"
    url: str
    model: str
    api_key: Optional[str] = None
    ensure_ready: bool = False
    timeout_s: int = 120


# ═════════════════════════════════════════════════════════════════
# Embedding
# ═════════════════════════════════════════════════════════════════

@router.get("/embedding/status")
def embedding_status() -> Dict[str, Any]:
    """Return the current embedding provider status."""
    from prep.server import _config
    # Phase 139: static call — no instance construction for introspection.
    deps_ok = NativeEmbedder.is_available()

    model_cached = False
    model_path = None
    if deps_ok:
        try:
            from huggingface_hub import try_to_load_from_cache  # type: ignore[import-untyped]
            cached = try_to_load_from_cache(
                NativeEmbedder.HF_REPO_ID, NativeEmbedder.ONNX_FILE
            )
            if cached is not None and not isinstance(cached, str):
                model_cached = False
            elif isinstance(cached, str):
                model_cached = True
                model_path = cached
        except Exception:
            pass

    source = _config.get("embedding_source", "native")
    model_name = str(NativeEmbedder.HF_REPO_ID).split("/")[-1]
    return ok({
        "available": deps_ok,
        "model": model_name,
        "dim": NativeEmbedder.DIM,
        "downloaded": model_cached,
        "source": source,
        "native_available": deps_ok,
        "model_cached": model_cached,
        "model_path": model_path,
        "hf_repo_id": NativeEmbedder.HF_REPO_ID,
        "onnx_file": NativeEmbedder.ONNX_FILE,
    })


@router.post("/embedding/download")
def embedding_download() -> Dict[str, Any]:
    """Download the native embedding model from HuggingFace Hub.

    The model is cached in the standard HF cache directory (~/.cache/huggingface/).
    This is a blocking call — the download happens synchronously.
    """
    # Phase 139: download_model() is a real action — go through the
    # factory so we get the cached singleton, but the is_available()
    # gate is checked statically first.
    if not NativeEmbedder.is_available():
        raise ApiException(
            status_code=400,
            code="NATIVE_DEPS_MISSING",
            message="Native embedding dependencies not installed",
            hint="pip install onnxruntime tokenizers huggingface-hub",
        )
    from prep.services.embedder_factory import create_embedder
    native = create_embedder("native")

    try:
        model_path = native.download_model()
    except Exception as e:
        raise ApiException(
            status_code=500,
            code="DOWNLOAD_FAILED",
            message=f"Model download failed: {e}",
            hint="Check your internet connection and try again.",
        )

    return ok({
        "status": "downloaded",
        "model_path": model_path,
        "hf_repo_id": NativeEmbedder.HF_REPO_ID,
    })


# ═════════════════════════════════════════════════════════════════
# Pipeline-Safe Mode Switch (Phase 44C)
# ═════════════════════════════════════════════════════════════════

@router.post("/api/llm/mode-switch")
def mode_switch(req: ModeSwitchRequest) -> Dict[str, Any]:
    """Switch LLM assignment mode (structured ↔ mapped) safely.

    If a pipeline is currently running, this endpoint:
    1. Pauses the active pipeline group(s)
    2. Writes the new config atomically
    3. Verifies the next stage's model is available under the new config
    4. Resumes the paused pipeline group(s)

    This prevents pipeline breaks when the user changes their model
    configuration mid-run.
    """
    from prep.server import _load_ui_config, _save_ui_config
    from prep.services.project_helpers import get_registry

    if req.mode not in ("structured", "mapped"):
        raise ApiException(
            status_code=400,
            code="INVALID_MODE",
            message=f"Invalid mode: {req.mode}. Must be 'structured' or 'mapped'.",
        )

    # 1. Snapshot current config
    ui_cfg = _load_ui_config()
    llm_cfg = ui_cfg.get("llm_config") or {}
    old_mode = llm_cfg.get("assignment_mode", "structured")

    # 2. Find active pipeline runs across all projects
    paused_groups: List[Dict[str, str]] = []
    try:
        from prep.services.pipeline_orchestrator import pipeline_orchestrator

        registry = get_registry()
        for project in registry.list_projects():
            status = pipeline_orchestrator.status(project.id)

            # Pause fast_sync if active
            fast = status.get("fast_sync")
            if fast and fast.get("is_active"):
                pipeline_orchestrator.pause_fast_sync(project.id)
                paused_groups.append({"project_id": project.id, "group": "fast_sync"})
                logger.info("Mode switch: paused fast_sync for %s", project.id)

            # Pause deep_enrichment if active
            deep = status.get("deep_enrichment")
            if deep and deep.get("is_active"):
                pipeline_orchestrator.pause_deep_enrichment(project.id)
                paused_groups.append({"project_id": project.id, "group": "deep_enrichment"})
                logger.info("Mode switch: paused deep_enrichment for %s", project.id)
    except Exception as e:
        logger.warning("Mode switch: pipeline pause check failed: %s", e)

    # 3. Compute model identity diff (old vs new) for graceful VRAM swap
    #    Models shared between old and new configs stay loaded.
    #    Models only in old config get unloaded.
    old_identities: set = set()  # {(endpoint_id, model), ...}
    new_identities: set = set()
    unloaded_models: List[str] = []
    kept_models: List[str] = []

    # Gather old identities from current config
    try:
        from prep.server import _get_model_identity_for_task, TASK_TO_SLOT
        for task_id in TASK_TO_SLOT:
            identity = _get_model_identity_for_task(task_id)
            if identity and identity[0] and identity[1]:
                old_identities.add(identity)
    except Exception as e:
        logger.debug("Mode switch: failed to gather old identities: %s", e)

    # 3b. Write new config atomically
    new_blocks = req.assignment_blocks
    if new_blocks is None:
        new_blocks = llm_cfg.get("assignment_blocks") or []
    if req.mode == "mapped" and not new_blocks:
        import time as _time
        new_blocks = [{"id": f"block-{int(_time.time() * 1000)}", "endpoint_id": "", "model": "", "tasks": []}]

    llm_cfg["assignment_mode"] = req.mode
    llm_cfg["assignment_blocks"] = new_blocks
    ui_cfg["llm_config"] = llm_cfg
    _save_ui_config(ui_cfg)
    logger.info("Mode switch: %s → %s (wrote config)", old_mode, req.mode)

    # 3c. Gather new identities from freshly written config
    try:
        for task_id in TASK_TO_SLOT:
            identity = _get_model_identity_for_task(task_id)
            if identity and identity[0] and identity[1]:
                new_identities.add(identity)
    except Exception as e:
        logger.debug("Mode switch: failed to gather new identities: %s", e)

    # 3d. Unload models that are no longer needed, keep shared ones
    removed = old_identities - new_identities
    shared = old_identities & new_identities
    if shared:
        kept_models = [f"{eid}:{mdl}" for eid, mdl in shared]
        logger.info("Mode switch: keeping %d shared model(s) loaded: %s", len(shared), kept_models)

    for eid, mdl in removed:
        try:
            # Find any endpoint config to create a client for unloading
            endpoints = llm_cfg.get("saved_endpoints") or []
            ep = next((e for e in endpoints if e.get("id") == eid), None)
            if ep and ep.get("url"):
                from prep.core import LLMClient
                client = LLMClient(
                    endpoint_url=ep["url"],
                    model=mdl,
                    api_key=ep.get("api_key"),
                    provider=ep.get("provider", "ollama"),
                    timeout=10.0,
                )
                client.unload()
                unloaded_models.append(f"{eid}:{mdl}")
                logger.info("Mode switch: unloaded removed model %s from %s", mdl, eid)
        except Exception as e:
            logger.warning("Mode switch: failed to unload %s:%s — %s", eid, mdl, e)

    # 4. Verify next stage models and resume paused groups
    resumed: List[Dict[str, str]] = []
    for pg in paused_groups:
        try:
            from prep.services.pipeline_orchestrator import pipeline_orchestrator
            from prep.services.pipeline.stages import STAGE_TASK_ID, StageId

            # Try to acquire the model for the next stage under the new config
            run_status = pipeline_orchestrator.status(pg["project_id"])
            group_status = run_status.get(pg["group"])
            if group_status and group_status.get("current_stage"):
                try:
                    stage_enum = StageId(group_status["current_stage"])
                except ValueError:
                    stage_enum = None
                next_task = STAGE_TASK_ID.get(stage_enum) if stage_enum else None
                if next_task:
                    try:
                        from prep.core.model_awareness import model_awareness
                        model_awareness.acquire(next_task)
                    except Exception as acq_err:
                        logger.warning(
                            "Mode switch: model acquire for %s failed: %s (resuming anyway)",
                            next_task, acq_err,
                        )

            # Resume the paused group
            pipeline_orchestrator.resume_paused(pg["project_id"], pg["group"])
            resumed.append(pg)
            logger.info("Mode switch: resumed %s/%s", pg["project_id"], pg["group"])
        except Exception as e:
            logger.warning(
                "Mode switch: failed to resume %s/%s: %s",
                pg["project_id"], pg["group"], e,
            )

    return ok({
        "success": True,
        "old_mode": old_mode,
        "new_mode": req.mode,
        "paused_groups": paused_groups,
        "resumed_groups": resumed,
        "unloaded_models": unloaded_models,
        "kept_models": kept_models,
    })


# ═════════════════════════════════════════════════════════════════
# LLM Slots & Status
# ═════════════════════════════════════════════════════════════════

@router.get("/llm/slots/status")
async def get_llm_slots_status() -> Dict[str, Any]:
    """Check connectivity for all configured model slots (embedding, small, large, code).

    F-70: Made async with 3s timeout. The sync version made HTTP requests
    to check each slot's connectivity, which blocked during active cloud
    model calls — causing the AI Gateway to show empty in the dashboard.

    Returns per-slot status with endpoint reachability and model availability.
    """
    import asyncio

    def _build_slots_status():
        return _build_llm_slots_sync()

    try:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _build_slots_status),
            timeout=3.0,
        )
    except (asyncio.TimeoutError, Exception):
        # Return cached or minimal status so AI Gateway isn't empty
        return ok({"slots": [], "timeout": True})


def _build_llm_slots_sync() -> Dict[str, Any]:
    """Synchronous slots status builder — extracted for timeout wrapper."""
    from prep.server import _load_ui_config
    ui_cfg = _load_ui_config()
    llm_cfg = ui_cfg.get("llm_config") or {}
    endpoints = llm_cfg.get("saved_endpoints") or []
    ep_map = {e["id"]: e for e in endpoints if isinstance(e, dict) and e.get("id")}

    def _check_slot(slot_key: str) -> Dict[str, Any]:
        slot_cfg = llm_cfg.get(slot_key) or {}
        if not isinstance(slot_cfg, dict):
            return {"configured": False, "status": "not_configured"}

        ep_id = slot_cfg.get("endpoint_id") or ""
        model = slot_cfg.get("model") or ""
        enabled = bool(slot_cfg.get("enabled", False))

        if not ep_id or not model:
            return {"configured": False, "status": "not_configured"}

        ep = ep_map.get(ep_id)
        if not ep:
            return {
                "configured": True, "enabled": enabled, "model": model,
                "endpoint_id": ep_id, "status": "endpoint_missing",
                "error": f"Endpoint '{ep_id}' not found in saved endpoints",
            }

        url = str(ep.get("url", "")).rstrip("/")
        provider = ep.get("provider", "ollama")

        try:
            if provider == "ollama":
                r = requests.get(f"{url}/api/tags", timeout=3)
                reachable = r.status_code == 200
                model_found = False
                if reachable:
                    tags = r.json().get("models", []) if isinstance(r.json(), dict) else []
                    model_found = any(
                        str(m.get("name", "")).startswith(model.split(":")[0])
                        for m in tags if isinstance(m, dict)
                    )
            else:
                headers = {"Authorization": f"Bearer {ep.get('api_key', '')}"}
                target = f"{url}/models" if "v1" in url else f"{url}/v1/models"
                r = requests.get(target, timeout=3, headers=headers)
                reachable = r.status_code in (200, 401)
                model_found = r.status_code == 200
        except Exception as e:
            return {
                "configured": True, "enabled": enabled, "model": model,
                "endpoint_id": ep_id, "endpoint_url": url, "provider": provider,
                "status": "unreachable", "error": str(e),
            }

        if not reachable:
            return {
                "configured": True, "enabled": enabled, "model": model,
                "endpoint_id": ep_id, "endpoint_url": url, "provider": provider,
                "status": "unreachable", "error": "Endpoint did not respond",
            }

        return {
            "configured": True, "enabled": enabled, "model": model,
            "endpoint_id": ep_id, "endpoint_url": url, "provider": provider,
            "status": "connected" if model_found else "connected_no_model",
            "model_available": model_found,
        }

    # Check embedding separately (it has a different config shape)
    emb_cfg = llm_cfg.get("embedding") or {}
    emb_source = emb_cfg.get("source", "")
    if emb_source == "endpoint":
        emb_status = _check_slot("embedding")
        if not emb_status.get("configured"):
            ep_id = emb_cfg.get("endpoint_id", "")
            model = emb_cfg.get("model", "")
            if ep_id and model:
                ep = ep_map.get(ep_id)
                url = str((ep or {}).get("url", "")).rstrip("/") if ep else ""
                try:
                    r = requests.get(f"{url}/api/tags", timeout=3)
                    emb_status = {
                        "configured": True, "enabled": True, "model": model,
                        "endpoint_id": ep_id, "endpoint_url": url,
                        "status": "connected" if r.status_code == 200 else "unreachable",
                    }
                except Exception as e:
                    emb_status = {
                        "configured": True, "enabled": True, "model": model,
                        "endpoint_id": ep_id, "endpoint_url": url,
                        "status": "unreachable", "error": str(e),
                    }
    elif emb_source == "huggingface":
        emb_status = {"configured": True, "enabled": True, "source": "huggingface", "status": "local"}
    else:
        emb_status = {"configured": False, "status": "not_configured"}

    # Determine current assignment mode
    assignment_mode = llm_cfg.get("assignment_mode", "structured")

    # Detect running tasks from active pipeline runs (all projects)
    running_task_id: Optional[str] = None
    running_tasks: List[Dict[str, Any]] = []
    try:
        from prep.services.pipeline_orchestrator import pipeline_orchestrator
        from prep.services.project_helpers import get_registry as _get_reg
        from prep.services.pipeline.stages import STAGE_TASK_ID, STAGE_MODEL_SLOT, STAGE_QUEUE_TYPE, QueueType, StageId

        # Phase 125 follow-up (2026-05-03): defensive ghost-slot check.
        # The in-memory orchestrator state can desync from the on-disk
        # pipeline_run_metadata.json across daemon crashes — leaving
        # ``is_active=True`` for stages that the metadata records as
        # "completed". The dashboard's AI Gateway then shows a stale
        # "concepts running" slot indefinitely. Cross-check each
        # candidate against the manifest before reporting it.
        import json as _json
        from pathlib import Path as _Path
        from prep.core.project_registry import project_index_dir as _project_index_dir

        def _is_run_actually_active(project_obj) -> bool:
            try:
                idx = _Path(_project_index_dir(project_obj))
                meta = idx / "pipeline_run_metadata.json"
                if not meta.is_file():
                    return True  # no manifest → trust orchestrator
                data = _json.loads(meta.read_text())
                status = (data.get("status") or "").lower()
                return status not in ("completed", "failed", "cancelled")
            except Exception:
                return True

        registry = _get_reg()
        for project in registry.list_projects():
            # Skip projects whose on-disk manifest declares the run is
            # already done — defends against orchestrator-state staleness.
            if not _is_run_actually_active(project):
                continue
            ps = pipeline_orchestrator.status(project.id)
            # Phase 105a: "finalize" covers both traditional finalize
            # group runs AND solo runs like atlas/concepts/audit — the
            # orchestrator's status() merges solo runs into the finalize
            # slot so existing consumers (including this loop) pick them
            # up unchanged.
            for group_name in ("fast_sync", "deep_enrichment", "finalize"):
                group_run = ps.get(group_name)
                if group_run and group_run.get("is_active") and group_run.get("current_stage"):
                    stage_str = group_run["current_stage"]
                    try:
                        stage_id = StageId(stage_str)
                        task_id = STAGE_TASK_ID.get(stage_id)
                        model_slot = STAGE_MODEL_SLOT.get(stage_id)
                        queue_type = STAGE_QUEUE_TYPE.get(stage_id)
                        # Include LLM-using stages and embedding stages
                        if model_slot is not None or queue_type == QueueType.EMBEDDING:
                            effective_task_id = task_id or stage_str
                            if running_task_id is None:
                                running_task_id = effective_task_id
                            running_tasks.append({
                                "task_id": effective_task_id,
                                "project_id": project.id,
                                "project_name": project.name,
                                "group": group_name,
                                "stage": stage_str,
                                "model_slot": model_slot or "embedding",
                            })
                        elif task_id:
                            if running_task_id is None:
                                running_task_id = task_id
                    except (ValueError, KeyError):
                        pass

        # Enrich running tasks with concurrent worker count.
        # Phase 82 completion: concurrent_workers is the LIVE in-flight
        # count from token_telemetry, not the scheduler's configured max.
        # The scheduler's value is preserved under scheduler_capacity for
        # debugging / observability.
        try:
            from prep.services.pipeline.scheduler import (
                SWARM_CAPABLE_STAGES,
                pipeline_scheduler,
            )
            from prep.services.token_telemetry import telemetry as _tel

            # Phase 127 (audit fix): build project_id → hold mapping once
            # per response so the per-task held check works for projects
            # routed to ANY scheduler endpoint (cloud:openrouter,
            # local:default_ollama, cloud:default_ollama, …) rather than
            # silently assuming cloud:default_ollama.  list_holds() is
            # already lock-protected; defensive try/except matches the
            # T4.1 pattern (held_projects collection).
            holds_by_project: Dict[str, Dict[str, Any]] = {}
            try:
                for h in pipeline_scheduler.list_holds():
                    # First hold wins; a project held on multiple
                    # endpoints simultaneously is rare and any one is a
                    # valid pause signal for the UI.
                    holds_by_project.setdefault(h["project_id"], h)
            except Exception:
                holds_by_project = {}

            for rt in running_tasks:
                _scheduler_max, node_id = pipeline_scheduler.concurrent_workers_for_project(
                    rt["project_id"], stage=rt.get("stage"),
                )
                live_workers = _count_live_workers(
                    project_id=rt["project_id"],
                    task_id=rt.get("task_id", ""),
                )
                rt["concurrent_workers"] = live_workers
                rt["scheduler_capacity"] = _scheduler_max
                rt["compute_node"] = node_id

                # Phase 119+ Swarm Authority: the "Swarming" badge is
                # tied to runtime evidence in two complementary ways:
                #   (a) the scheduler has an open swarm window matching
                #       this task — bureaucratic but cleanest signal
                #   (b) live LLM calls tagged with swarm_role
                #       (coordinator / worker / synthesizer) — the
                #       SwarmOrchestrator stamps these via ContextVar
                #       during its phase blocks.  THIS is the
                #       runtime truth.
                #
                # The window-only signal can miss the brief gap during
                # SwarmOrchestrator phase transitions, where the
                # scheduler window may not yet be opened or may have
                # been closed but workers are still running.  Without
                # (b) the badge would flicker off during these
                # transitions even though the swarm is genuinely
                # active.  (Phase 127 removed the 45s cooldown that
                # historically caused longer false-off windows.)  The earlier ``live_workers >= 2`` gate
                # was also wrong because coord/synth phases are
                # intrinsically 1-worker-in-flight.
                rt["is_swarm"] = False
                rt["swarm_phases"] = None
                stage = rt.get("stage", "")
                window = pipeline_scheduler.get_swarm_window()
                window_matches = (
                    window is not None
                    and window.get("project_id") == rt["project_id"]
                    and _stage_value(window.get("stage")) == stage
                )
                active_reqs = _tel.get_active_requests()
                role_tagged = sum(
                    1 for r in active_reqs
                    if r.get("project_id") == rt["project_id"]
                    and r.get("swarm_role")
                )
                # Phase 136 Part 15: gate on SWARM_CAPABLE_STAGES.  Stale
                # ``swarm_role`` entries that survived past a swarm
                # stage's drain were mislabeling subsequent plain
                # batched stages (notably ``inferred_edges``) as
                # "Swarming" — a real swarm can only run on a
                # swarm-capable stage, so guard the heuristic on that.
                stage_is_swarm_capable = stage in SWARM_CAPABLE_STAGES
                if stage_is_swarm_capable and (window_matches or role_tagged > 0):
                    rt["is_swarm"] = True
                    # _summarize_swarm_phases always returns a
                    # three-bucket dict; idle phases just show
                    # active=0, model=None.  This lets the sidebar's
                    # Coordinator row stay visible at "[idle]"
                    # instead of vanishing during the synth phase.
                    rt["swarm_phases"] = _summarize_swarm_phases(
                        active_reqs,
                        project_id=rt["project_id"],
                        task_id=rt.get("task_id", ""),
                    )

                # Phase 127 Sub-phase 4 (audit fix): classify hold/swarm
                # state for the UI.  Look up holds by project_id only,
                # using the holds_by_project map built once above — the
                # earlier implementation hardcoded a "cloud:default_ollama"
                # fallback for rt["compute_node"], which silently reported
                # "not held" for projects actually running on other
                # endpoints (cloud:openrouter, local:default_ollama, …).
                # is_held now reflects whether ANY hold targets this
                # project; held_reason carries the same "<reason>_by_<set_by>"
                # string the dashboard already renders.
                pid = rt["project_id"]
                hold_entry = holds_by_project.get(pid)
                is_held = hold_entry is not None
                held_reason: Optional[str] = (
                    f"{hold_entry['reason']}_by_{hold_entry['set_by_project']}"
                    if hold_entry else None
                )
                rt["is_held"] = is_held
                rt["held_reason"] = held_reason
                rt["state"] = _running_task_state(
                    project_id=pid,
                    is_held=is_held,
                    held_reason=held_reason,
                    is_swarm=rt.get("is_swarm", False),
                )
        except Exception:
            logger.debug("running-tasks enrichment failed", exc_info=True)
            pass  # Scheduler not available — leave defaults

        # Phase 119 swarm slot attribution: when a running_task is a real
        # swarm (window_matches AND live_workers>=2), the single entry
        # uses STAGE_MODEL_SLOT[stage] — the stage's primary slot — and
        # collapses the coordinator/worker/synthesizer split into one
        # bucket (e.g., 11×Swarm under Thinking even when the coordinator
        # actually ran on a different slot/model).  Replace the single
        # entry with one per (model_slot, swarm_role) seen in live
        # telemetry, so the AI Gateway sidebar shows the calls under
        # whatever slot they actually hit.
        #
        # Sum preservation: ALL active calls for the (project, task) are
        # bucketed — including untagged ones (legacy LLMClient instances
        # not yet routed through ``_get_llm_client_for_slot``) and calls
        # without a swarm_role.  Untagged calls land under the stage's
        # primary slot with swarm_role=None.  Without this the
        # AI Gateway's "N active" badge would silently drop calls and
        # disagree with the Pipeline Queue totals.
        #
        # Sidebar visibility: the SidebarAIGateway renders five canonical
        # buckets (embedding/small/large/code/coordinator).  When a swarm
        # coordinator is configured to a separate endpoint+model (not
        # inherited from large), its in-flight calls carry
        # ``model_slot="coordinator"`` (tagged by server._get_llm_client_for_slot)
        # and are surfaced as a dedicated sidebar row alongside Thinking.
        # Unknown slots still collapse to the stage's primary slot so any
        # future role tag stays visible without a UI change.
        try:
            from prep.services.token_telemetry import telemetry as _tel2
            _SIDEBAR_SLOTS = {"embedding", "small", "large", "code", "coordinator"}
            expanded: List[Dict[str, Any]] = []
            for rt in running_tasks:
                if not rt.get("is_swarm"):
                    expanded.append(rt)
                    continue
                active = [
                    req for req in _tel2.get_active_requests()
                    if req.get("project_id") == rt["project_id"]
                    and req.get("task_id") == rt.get("task_id", "")
                ]
                fallback_slot = rt.get("model_slot")
                # Group by (sidebar-canonical model_slot, swarm_role).
                # Both unknown slots ("coordinator") and unset ones
                # (legacy untagged calls) collapse to fallback_slot.
                groups: Dict[tuple, Dict[str, Any]] = {}
                for req in active:
                    slot = req.get("model_slot") or fallback_slot
                    if slot not in _SIDEBAR_SLOTS:
                        slot = fallback_slot
                    role = req.get("swarm_role")  # may be None
                    key = (slot, role)
                    g = groups.setdefault(key, {
                        "slot": slot,
                        "role": role,
                        "concurrent_workers": 0,
                        "model": req.get("model"),
                    })
                    g["concurrent_workers"] += 1
                if not groups:
                    # No active calls captured — keep the original entry
                    # so the gate badge stays consistent.
                    expanded.append(rt)
                    continue
                for (slot, role), g in groups.items():
                    expanded.append({
                        **rt,
                        "model_slot": slot,
                        "concurrent_workers": g["concurrent_workers"],
                        "swarm_role": role,
                    })
            running_tasks = expanded
        except Exception:
            logger.debug("swarm slot split failed", exc_info=True)

        # [Goal 3] Merge live telemetry active requests that bypass the orchestrator
        from prep.services.token_telemetry import telemetry
        for req in telemetry.get_active_requests():
            # Skip if already tracked by orchestrator logic
            if any(rt["project_id"] == req["project_id"] and rt.get("task_id") == req["task_id"] for rt in running_tasks):
                continue
            proj_name = req["project_id"]
            try:
                p = registry.get_project(req["project_id"])
                if p:
                    proj_name = p.name
            except Exception:
                pass
            _agent_task_id = req["task_id"] or "agent_call"
            _agent_model_slot = req.get("model_slot") or "agent"
            running_tasks.append({
                "task_id": _agent_task_id,
                "project_id": req["project_id"],
                "project_name": proj_name,
                "group": "agent_ops",
                "stage": req["task_id"],
                "model_slot": _agent_model_slot,
                "concurrent_workers": _count_live_workers(
                    project_id=req["project_id"],
                    task_id=_agent_task_id,
                ),
                "compute_node": "local",
                "is_swarm": False,
            })
    except Exception:
        pass  # Non-critical

    # Build mapped-mode block statuses
    block_statuses: Optional[List[Dict[str, Any]]] = None
    if assignment_mode == "mapped":
        blocks = llm_cfg.get("assignment_blocks") or []
        block_statuses = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            b_eid = block.get("endpoint_id") or ""
            b_model = block.get("model") or ""
            b_tasks = block.get("tasks") or []
            b_id = block.get("id") or ""

            if not b_eid or not b_model:
                block_statuses.append({
                    "id": b_id, "configured": False, "status": "not_configured",
                    "model": b_model, "endpoint_id": b_eid, "tasks": b_tasks,
                })
                continue

            ep = ep_map.get(b_eid)
            if not ep:
                block_statuses.append({
                    "id": b_id, "configured": True, "status": "endpoint_missing",
                    "model": b_model, "endpoint_id": b_eid, "tasks": b_tasks,
                    "error": f"Endpoint '{b_eid}' not found",
                })
                continue

            b_url = str(ep.get("url", "")).rstrip("/")
            b_provider = ep.get("provider", "ollama")
            try:
                if b_provider == "ollama":
                    r = requests.get(f"{b_url}/api/tags", timeout=3)
                    b_reachable = r.status_code == 200
                    b_found = False
                    if b_reachable:
                        tags = r.json().get("models", []) if isinstance(r.json(), dict) else []
                        b_found = any(
                            str(m.get("name", "")).startswith(b_model.split(":")[0])
                            for m in tags if isinstance(m, dict)
                        )
                else:
                    headers = {"Authorization": f"Bearer {ep.get('api_key', '')}"}
                    target = f"{b_url}/models" if "v1" in b_url else f"{b_url}/v1/models"
                    r = requests.get(target, timeout=3, headers=headers)
                    b_reachable = r.status_code in (200, 401)
                    b_found = r.status_code == 200

                block_statuses.append({
                    "id": b_id, "configured": True,
                    "status": "connected" if b_found else ("connected_no_model" if b_reachable else "unreachable"),
                    "model": b_model, "endpoint_id": b_eid, "endpoint_url": b_url,
                    "provider": b_provider, "tasks": b_tasks,
                    "endpoint_name": ep.get("name", ""),
                    "model_available": b_found,
                })
            except Exception as e:
                block_statuses.append({
                    "id": b_id, "configured": True, "status": "unreachable",
                    "model": b_model, "endpoint_id": b_eid, "endpoint_url": b_url,
                    "provider": b_provider, "tasks": b_tasks,
                    "error": str(e),
                })

    result: Dict[str, Any] = {
        "assignment_mode": assignment_mode,
        "running_task_id": running_task_id,
        "running_tasks": running_tasks,
        "embedding": emb_status,
        "small_model": _check_slot("small_model"),
        "large_model": _check_slot("large_model"),
        "code_model": _check_slot("code_model"),
        # Coordinator slot is reported only when explicitly configured
        # with inherit_from_large=False.  The inherit-from-large default
        # routes coordinator calls through the large slot (see
        # server._get_llm_client_for_slot), and reporting a separate row
        # would create a phantom sidebar entry that double-counts the
        # large model.
        "coordinator_model": (
            {"configured": False, "status": "inheriting"}
            if bool((llm_cfg.get("coordinator_model") or {}).get("inherit_from_large", True))
            else _check_slot("coordinator_model")
        ),
    }
    if block_statuses is not None:
        result["assignment_blocks"] = block_statuses

    # Phase 127 Sub-phase 4: surface scheduler hold state to the UI.
    # Each entry: {project_id, endpoint_id, reason, set_by_project, held_since}.
    try:
        from prep.services.pipeline.scheduler import pipeline_scheduler as _sched
        result["held_projects"] = _sched.list_holds()
    except Exception:
        logger.debug("held_projects enrichment failed", exc_info=True)
        result["held_projects"] = []

    return ok(result)


@router.get("/llm/plan-limits")
def get_plan_limits() -> Dict[str, Any]:
    """Phase 119 Phase A: return the per-provider plan-tier table for the UI dropdown."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent.parent / "data" / "concurrency_limits.json"
    try:
        return ok(json.loads(path.read_text()))
    except Exception as exc:
        logger.warning("plan-limits: failed to read %s: %s", path, exc)
        return {"success": False, "data": None, "error": {"code": "plan_limits_read_failed", "message": str(exc)}}


@router.get("/llm/status")
@router.get("/api/llm/status")
def get_llm_status() -> Dict[str, Any]:
    from prep.server import _config, _load_ui_config
    ollama_url = str(_config.get("ollama_url") or "http://localhost:11434").rstrip("/")
    connected = False
    models: List[str] = []
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=2)
        if r.status_code == 200:
            payload = r.json()
            raw_models = payload.get("models") if isinstance(payload, dict) else None
            if isinstance(raw_models, list):
                for m in raw_models:
                    if isinstance(m, dict) and m.get("name"):
                        models.append(str(m.get("name")))
            connected = True
    except Exception:
        connected = False
        models = []

    ui_cfg = _load_ui_config()

    return ok(
        {
            "ollama": {"url": ollama_url, "connected": connected, "models": models},
        }
    )


# ═════════════════════════════════════════════════════════════════
# LLM Testing & Proxy
# ═════════════════════════════════════════════════════════════════

@router.post("/llm/test")
@router.post("/api/llm/test")
def test_llm() -> Dict[str, Any]:
    from prep.server import _config, _load_ui_config
    ollama_url = str(_config.get("ollama_url") or "http://localhost:11434").rstrip("/")
    ollama_connected = False
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=2)
        if r.status_code == 200:
            ollama_connected = True
    except Exception:
        ollama_connected = False

    ui_cfg = _load_ui_config()

    return ok(
        {
            "ollama": {"connected": ollama_connected},
        }
    )


@router.post("/api/llm/proxy/models")
def proxy_models(req: LLMProxyRequest) -> Dict[str, Any]:
    url = req.url.rstrip("/")
    if not is_safe_url(url, req.provider):
        return ok({"models": [], "error": "Invalid or unsafe URL"})
    models: List[str] = []
    model_details: List[Dict[str, Any]] = []
    
    try:
        if req.provider == "ollama":
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        name = m["name"]
                        models.append(name)
                        # Extract metadata from the tags response
                        size_bytes = m.get("size", 0)
                        size_label = f"{size_bytes / 1e9:.1f}GB" if size_bytes > 0 else ""
                        param_size = (m.get("details") or {}).get("parameter_size", "")
                        quant = (m.get("details") or {}).get("quantization_level", "")
                        family = (m.get("details") or {}).get("family", "")
                        parts: list = []
                        if param_size:
                            parts.append(param_size)
                        if quant:
                            parts.append(quant)
                        if size_label:
                            parts.append(size_label)
                        detail: Dict[str, Any] = {
                            "name": name,
                            "cost_tier": " · ".join(parts) if parts else "Local",
                        }
                        if family:
                            detail["family"] = family
                        model_details.append(detail)

                # Fetch context_length for each model via /api/show (batched, max 20)
                for md in model_details[:20]:
                    try:
                        show_r = requests.post(f"{url}/api/show", json={"name": md["name"]}, timeout=3)
                        if show_r.status_code == 200:
                            show_data = show_r.json()
                            # model_info has context_length, or parse from parameters
                            model_info = show_data.get("model_info") or {}
                            ctx = 0
                            for k, v in model_info.items():
                                if "context_length" in k and isinstance(v, (int, float)):
                                    ctx = int(v)
                                    break
                            if ctx > 0:
                                md["context_tokens"] = ctx
                                md["context_window"] = f"{ctx // 1000}k" if ctx >= 1000 else str(ctx)
                    except Exception:
                        pass
        
        elif req.provider in ("openai", "openai-compatible", "lm-studio", "anthropic"):
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            target = f"{url}/models"
            if "v1" not in url and req.provider != "anthropic":
                 target = f"{url}/v1/models"
            
            r = requests.get(target, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("data", []):
                    if isinstance(m, dict) and "id" in m:
                        name = m["id"]
                        models.append(name)
                        # Extract metadata when available (OpenAI, LM Studio)
                        detail: Dict[str, Any] = {"name": name}
                        ctx = m.get("context_window") or m.get("context_length") or 0
                        if isinstance(ctx, (int, float)) and ctx > 0:
                            ctx = int(ctx)
                            detail["context_tokens"] = ctx
                            detail["context_window"] = f"{ctx // 1000}k" if ctx >= 1000 else str(ctx)
                        # LM Studio includes architecture/quantization as strings.
                        # OpenRouter returns architecture as a dict — guard against non-strings.
                        arch = m.get("architecture") or ""
                        quant = m.get("quantization") or ""
                        if not isinstance(arch, str):
                            arch = ""
                        if not isinstance(quant, str):
                            quant = ""
                        if arch or quant:
                            parts = [p for p in [arch, quant] if p]
                            detail["cost_tier"] = " · ".join(parts)
                        elif req.provider == "openai":
                            detail["cost_tier"] = "OpenAI"
                        elif req.provider == "anthropic":
                            detail["cost_tier"] = "Anthropic"
                        model_details.append(detail)

        elif req.provider == "google":
            if not req.api_key:
                raise ApiException(status_code=400, code="MISSING_API_KEY", message="Google Gemini requires an API key. Get one at https://aistudio.google.com/apikey")
            params = {"key": req.api_key}
            target = f"{url}/v1beta/models"
            r = requests.get(target, params=params, timeout=10)
            if r.status_code != 200:
                err_text = r.text[:200] if r.text else f"HTTP {r.status_code}"
                raise ApiException(status_code=r.status_code, code="GOOGLE_API_ERROR", message=f"Google API error: {err_text}")
            data = r.json()
            for m in data.get("models", []):
                if not isinstance(m, dict) or "name" not in m:
                    continue
                # Only include models that support text generation
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" not in methods:
                    continue
                # Filter out non-LLM models (image, audio, video, embedding)
                lower_name = m["name"].lower()
                if any(x in lower_name for x in [
                    "embedding", "imagen", "veo", "audio", "vision",
                    "aqa", "tts", "-image", "image-generation", "computer-use",
                ]):
                    continue
                name = m["name"].replace("models/", "") if m["name"].startswith("models/") else m["name"]
                models.append(name)

                # Rich metadata for UI
                ctx = m.get("inputTokenLimit", 0)
                ctx_label = f"{ctx // 1000}k" if ctx >= 1000 else str(ctx)
                output_limit = m.get("outputTokenLimit", 0)

                # Free-tier heuristic (API doesn't expose this directly)
                free_patterns = ["gemma", "nano-banana", "flash-lite", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3-flash"]
                paid_patterns = ["pro", "ultra", "robotics"]
                is_free_tier = any(p in lower_name for p in free_patterns) and not any(p in lower_name for p in paid_patterns)
                cost_label = "Free Tier Available" if is_free_tier else "Paid/Quota"

                # Rate limits + batch estimation
                rl = _get_gemini_rate_limits(name)
                batch_est: Optional[Dict[str, Any]] = None
                if ctx > 0:
                    fpr = max(1, ctx // _AVG_PROMPT_TOKENS)
                    batch_est = {"files_per_request": fpr}
                    if rl and rl.get("rpd"):
                        batch_est["daily_file_capacity"] = fpr * rl["rpd"]

                detail: Dict[str, Any] = {
                    "name": name,
                    "context_window": ctx_label,
                    "context_tokens": ctx,
                    "output_limit": output_limit,
                    "cost_tier": cost_label,
                }
                if rl:
                    detail["rate_limits"] = rl
                if batch_est:
                    detail["batch_estimate"] = batch_est
                model_details.append(detail)

    except Exception as e:
        raise ApiException(status_code=500, code="CONNECTION_FAILED", message=str(e))

    # Inject batch profile tier based on context window
    try:
        from prep.core.batch_profiles import detect_profile_from_context, _LOCAL_PROVIDERS
        is_local = req.provider.lower().strip() in _LOCAL_PROVIDERS
        for detail in model_details:
            ctx = detail.get("context_tokens", 0)
            if ctx and ctx > 0 and not is_local:
                bp = detect_profile_from_context(ctx, req.provider)
                detail["batch_profile"] = bp.name.value
            else:
                detail["batch_profile"] = "off"
    except Exception:
        pass

    # GW-3: Filter models through admin policy if applicable
    try:
        from prep.server import _load_ui_config
        from prep.core.team_config import parse_admin_policy, filter_models_by_policy
        ui_cfg = _load_ui_config()
        admin_policy_raw = ui_cfg.get("_admin_policy_cache")
        if admin_policy_raw:
            policy = parse_admin_policy({"admin_policy": admin_policy_raw})
            if models:
                allowed = set(filter_models_by_policy(models, policy, slot=req.slot))
                for detail in model_details:
                    if detail["name"] not in allowed:
                        detail["blocked_by_policy"] = True
                        detail["cost_tier"] = "Blocked by IT Policy"
    except Exception as e:
        logger.warning("Failed to apply model policy filtering: %s", e)

    return ok({"models": models, "model_details": model_details})


@router.post("/api/llm/proxy/test")
def proxy_test(req: LLMProxyRequest) -> Dict[str, Any]:
    url = req.url.rstrip("/")
    if not is_safe_url(url, req.provider):
        return ok({"success": False, "message": "Invalid or unsafe URL scheme", "models": []})

    success = False
    message = ""
    models: List[str] = []

    try:
        if req.provider == "ollama":
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                success = True
                data = r.json()
                models = [m["name"] for m in data.get("models", []) if "name" in m]
                message = f"Connected to Ollama v{r.headers.get('version', 'unknown')}"
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"

        elif req.provider == "google":
            params = {"key": req.api_key} if req.api_key else {}
            target = f"{url}/v1beta/models"
            r = requests.get(target, params=params, timeout=5)
            if r.status_code == 200:
                success = True
                data = r.json()
                models = [
                    m["name"].replace("models/", "") if m["name"].startswith("models/") else m["name"]
                    for m in data.get("models", [])
                    if isinstance(m, dict) and "name" in m
                    and "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                message = "Connected successfully to Google Gemini"
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"

        else:
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            target = f"{url}/models"
            if "v1" not in url and req.provider != "anthropic":
                 target = f"{url}/v1/models"

            r = requests.get(target, headers=headers, timeout=5)
            if r.status_code == 200:
                success = True
                data = r.json()
                models = [m.get("id") for m in data.get("data", []) if "id" in m]
                message = "Connected successfully"
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"

    except Exception as e:
        message = str(e)

    return ok({"success": success, "message": message, "models": models})


@router.post("/api/llm/model-status")
def model_status_endpoint(req: ModelStatusRequest) -> Dict[str, Any]:
    """Check model readiness status, optionally triggering preload.

    When ``ensure_ready`` is True the server will attempt to preload
    the model and block until it is ready (up to ``timeout_s``).
    """
    url = req.url.rstrip("/")
    if req.ensure_ready:
        result = ensure_model_ready(
            provider=req.provider,
            url=url,
            model=req.model,
            api_key=req.api_key,
            timeout_s=req.timeout_s,
        )
    else:
        result = get_model_status(
            provider=req.provider,
            url=url,
            model=req.model,
            api_key=req.api_key,
        )
    return ok(result.to_dict())


@router.post("/api/llm/proxy/test-model")
def proxy_test_model(req: LLMModelTestRequest) -> Dict[str, Any]:
    """Test a specific model with readiness-aware logic.

    For Ollama models: checks if model is loaded via ``/api/ps`` first.
    If not loaded, preloads it (up to 120 s) before sending the actual
    test request.  This prevents false "timed out" errors caused by
    cold-start model loading.
    """
    url = req.url.rstrip("/")
    if not is_safe_url(url, req.provider):
        return ok({"success": False, "message": "Invalid or unsafe URL scheme", "model_status": "unknown"})

    success = False
    message = ""
    model_status_str = "unknown"
    
    try:
        if req.provider == "ollama":
            if req.kind == "embedding":
                readiness = get_model_status(
                    provider="ollama", url=url, model=req.model,
                )
                model_status_str = readiness.status.value

                if readiness.status in (ModelStatus.NOT_FOUND, ModelStatus.ERROR):
                    message = readiness.message
                    return ok({
                        "success": False,
                        "message": message,
                        "model_status": model_status_str,
                    })

                try:
                    r = requests.post(
                        f"{url}/api/embeddings",
                        json={"model": req.model, "prompt": "Test embedding"},
                        timeout=120,
                    )
                    if r.status_code == 200:
                        success = True
                        load_info = ""
                        try:
                            resp_data = r.json()
                            load_ns = resp_data.get("load_duration", 0)
                            if load_ns > 0:
                                load_info = f" (load: {load_ns / 1e9:.1f}s)"
                        except Exception:
                            pass
                        message = f"Model responded successfully{load_info}"
                        model_status_str = ModelStatus.READY.value
                    else:
                        message = f"HTTP {r.status_code}: {r.text[:100]}"
                except requests.Timeout:
                    message = f"Model '{req.model}' timed out (may still be loading)"
                    model_status_str = ModelStatus.LOADING.value
            else:
                readiness = ensure_model_ready(
                    provider="ollama",
                    url=url,
                    model=req.model,
                    timeout_s=120,
                )
                model_status_str = readiness.status.value

                if readiness.status == ModelStatus.NOT_FOUND:
                    message = readiness.message
                    return ok({
                        "success": False,
                        "message": message,
                        "model_status": model_status_str,
                    })

                if readiness.status == ModelStatus.LOADING:
                    message = readiness.message
                    return ok({
                        "success": False,
                        "message": message,
                        "model_status": model_status_str,
                    })

                try:
                    r = requests.post(
                        f"{url}/api/generate",
                        json={"model": req.model, "prompt": "Hi", "stream": False},
                        timeout=30,
                    )

                    if r.status_code == 200:
                        success = True
                        load_info = ""
                        try:
                            resp_data = r.json()
                            load_ns = resp_data.get("load_duration", 0)
                            if load_ns > 0:
                                load_info = f" (load: {load_ns / 1e9:.1f}s)"
                        except Exception:
                            pass
                        message = f"Model responded successfully{load_info}"
                        model_status_str = ModelStatus.READY.value
                    else:
                        try:
                            err_data = r.json()
                            ollama_err = err_data.get("error", "")
                        except Exception:
                            ollama_err = ""
                        if ollama_err:
                            message = f"Ollama error: {ollama_err}"
                        else:
                            message = f"HTTP {r.status_code}: {r.text[:200]}"
                except requests.Timeout:
                    message = f"Model '{req.model}' timed out (may still be loading)"
                    model_status_str = ModelStatus.LOADING.value

        elif req.provider == "google":
            params = {"key": req.api_key} if req.api_key else {}
            target = f"{url}/v1beta/models/{req.model}:generateContent"
            try:
                r = requests.post(
                    target,
                    params=params,
                    json={
                        "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
                        "generationConfig": {"maxOutputTokens": 5}
                    },
                    timeout=30,
                )
                if r.status_code == 200:
                    success = True
                    message = "Model responded successfully"
                    model_status_str = "ready"
                else:
                    message = f"HTTP {r.status_code}: {r.text[:200]}"
            except requests.Timeout:
                message = f"Model '{req.model}' timed out"

        elif req.provider in ("openai", "openai-compatible", "lm-studio"):
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            base = url if "v1" in url else f"{url}/v1"
            
            if req.kind == "embedding":
                r = requests.post(
                    f"{base}/embeddings",
                    headers=headers,
                    json={"model": req.model, "input": "Test"},
                    timeout=30,
                )
            else:
                r = requests.post(
                    f"{base}/chat/completions",
                    headers=headers,
                    json={
                        "model": req.model, 
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 5
                    },
                    timeout=30,
                )
                
            if r.status_code == 200:
                success = True
                message = "Model responded successfully"
                model_status_str = ModelStatus.READY.value
            else:
                message = f"HTTP {r.status_code}: {r.text[:100]}"

    except requests.Timeout:
        message = "Request timed out — model may still be loading. Try again in a moment."
        model_status_str = ModelStatus.LOADING.value
    except Exception as e:
        message = str(e)

    # ── Context window check ────────────────────────────────────
    warnings: List[str] = []
    recommendations: Dict[str, Any] = {}

    if success and req.slot:
        detected_ctx = _query_context_window(req.provider, url, req.model, req.api_key)
        min_ctx = _SLOT_MIN_CONTEXT.get(req.slot)
        slot_label = _SLOT_LABELS.get(req.slot, req.slot)

        if detected_ctx is not None:
            recommendations["detected_context_window"] = detected_ctx
            if min_ctx and detected_ctx < min_ctx:
                warnings.append(
                    f"Context window is {detected_ctx:,} tokens but {slot_label} "
                    f"needs at least {min_ctx:,}. Increase the context length in "
                    f"your model server settings to avoid truncated results."
                )
        elif min_ctx and req.provider in ("openai-compatible", "lm-studio"):
            recommendations["note"] = (
                f"{slot_label} sends prompts up to ~{min_ctx:,} tokens. "
                f"Ensure your model's context window is set to at least {min_ctx:,} "
                f"in your server settings (e.g. LM Studio → Load → Context Length)."
            )

        if min_ctx:
            recommendations["min_context_window"] = min_ctx
            recommendations["slot_label"] = slot_label

    result: Dict[str, Any] = {
        "success": success,
        "message": message,
        "model_status": model_status_str,
    }
    if warnings:
        result["warnings"] = warnings
    if recommendations:
        result["recommendations"] = recommendations

    return ok(result)

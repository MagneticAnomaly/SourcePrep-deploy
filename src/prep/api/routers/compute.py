"""
Prep Compute Node Router — Phase 45D
========================================

CRUD for compute nodes + scheduler status.  These endpoints manage the
multi-GPU / multi-node configuration that the pipeline scheduler uses
to allocate LLM stages across hardware.

**Endpoints:**
  - GET    /compute/nodes              — List all compute nodes
  - POST   /compute/nodes              — Create a compute node
  - PUT    /compute/nodes/{id}         — Update a compute node
  - DELETE /compute/nodes/{id}         — Delete a compute node
  - GET    /compute/nodes/{id}/status  — Node health + current load
  - GET    /compute/scheduler          — Full scheduler status (diagnostics)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compute"])


# ── Request / Response Models ────────────────────────────────────

class CreateNodeRequest(BaseModel):
    name: str = Field(..., description="Human-readable node name")
    type: str = Field("local", description="'local', 'remote', or 'cloud'")
    hardware_profile: Optional[str] = Field(
        None, description="'apple_silicon', 'nvidia', 'amd', 'intel', or 'cloud'"
    )
    max_concurrent: int = Field(1, ge=1, le=64, description="Max parallel LLM requests")
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    endpoint_ids: List[str] = Field(default_factory=list)


class UpdateNodeRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    hardware_profile: Optional[str] = None
    max_concurrent: Optional[int] = Field(None, ge=1, le=64)
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    endpoint_ids: Optional[List[str]] = None


# ── Helpers ──────────────────────────────────────────────────────

def _load_nodes() -> List[Dict[str, Any]]:
    """Load compute nodes from the settings store."""
    try:
        from prep.services.settings_store import settings
        llm_config = settings.get("llm_config") or {}
        return llm_config.get("compute_nodes", [])
    except Exception:
        return []


def _save_nodes(nodes: List[Dict[str, Any]]) -> None:
    """Persist compute nodes to the settings store and sync scheduler."""
    from prep.services.settings_store import settings
    llm_config = settings.get("llm_config") or {}
    llm_config["compute_nodes"] = nodes
    settings.set("llm_config", llm_config)

    # Sync scheduler with new config
    _sync_scheduler(nodes)


def _sync_scheduler(nodes: List[Dict[str, Any]]) -> None:
    """Push node config into the live pipeline scheduler."""
    from prep.services.pipeline.scheduler import pipeline_scheduler

    # Remove nodes that no longer exist
    existing_ids = {n["id"] for n in nodes}
    status = pipeline_scheduler.status()
    for nid in list(status.get("nodes", {}).keys()):
        if nid not in existing_ids and nid != "__local__":
            pipeline_scheduler.remove_node(nid)

    # Configure all current nodes
    for node in nodes:
        pipeline_scheduler.configure_node(
            node_id=node["id"],
            max_concurrent=node.get("max_concurrent", 1),
        )


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/compute/nodes")
def list_nodes() -> Dict[str, Any]:
    """List all compute nodes."""
    nodes = _load_nodes()
    return ok({"nodes": nodes, "count": len(nodes)})


@router.post("/compute/nodes")
def create_node(req: CreateNodeRequest) -> Dict[str, Any]:
    """Create a new compute node."""
    nodes = _load_nodes()

    node = {
        "id": f"node_{uuid.uuid4().hex[:8]}",
        "name": req.name,
        "type": req.type,
        "hardware_profile": req.hardware_profile,
        "max_concurrent": req.max_concurrent,
        "gpu_name": req.gpu_name,
        "gpu_vram_gb": req.gpu_vram_gb,
        "endpoint_ids": req.endpoint_ids,
    }
    nodes.append(node)
    _save_nodes(nodes)

    logger.info("Created compute node: %s (%s)", node["name"], node["id"])
    return ok(node)


@router.put("/compute/nodes/{node_id}")
def update_node(node_id: str, req: UpdateNodeRequest) -> Dict[str, Any]:
    """Update an existing compute node."""
    nodes = _load_nodes()

    target = None
    for n in nodes:
        if n["id"] == node_id:
            target = n
            break

    if target is None:
        raise ApiException(
            status_code=404,
            code="NODE_NOT_FOUND",
            message=f"Compute node '{node_id}' not found.",
        )

    if req.name is not None:
        target["name"] = req.name
    if req.type is not None:
        target["type"] = req.type
    if req.hardware_profile is not None:
        target["hardware_profile"] = req.hardware_profile
    if req.max_concurrent is not None:
        target["max_concurrent"] = req.max_concurrent
    if req.gpu_name is not None:
        target["gpu_name"] = req.gpu_name
    if req.gpu_vram_gb is not None:
        target["gpu_vram_gb"] = req.gpu_vram_gb
    if req.endpoint_ids is not None:
        target["endpoint_ids"] = req.endpoint_ids

    _save_nodes(nodes)
    logger.info("Updated compute node: %s (%s)", target["name"], node_id)
    return ok(target)


@router.delete("/compute/nodes/{node_id}")
def delete_node(node_id: str) -> Dict[str, Any]:
    """Delete a compute node.

    Endpoints previously assigned to this node will have their
    compute_node_id cleared (they fall back to the default local node).
    """
    nodes = _load_nodes()
    before = len(nodes)
    nodes = [n for n in nodes if n["id"] != node_id]

    if len(nodes) == before:
        raise ApiException(
            status_code=404,
            code="NODE_NOT_FOUND",
            message=f"Compute node '{node_id}' not found.",
        )

    # Clear endpoint associations
    from prep.services.settings_store import settings
    llm_config = settings.get("llm_config") or {}
    for ep in llm_config.get("saved_endpoints", []):
        if ep.get("compute_node_id") == node_id:
            ep["compute_node_id"] = None

    _save_nodes(nodes)
    logger.info("Deleted compute node: %s", node_id)
    return ok({"deleted": node_id})


@router.get("/compute/nodes/{node_id}/status")
def node_status(node_id: str) -> Dict[str, Any]:
    """Get live status for a compute node (current load, queued jobs)."""
    from prep.services.pipeline.scheduler import pipeline_scheduler

    sched_status = pipeline_scheduler.status()
    node_info = sched_status.get("nodes", {}).get(node_id)

    if node_info is None:
        # Node exists in config but not yet registered with scheduler
        nodes = _load_nodes()
        target = next((n for n in nodes if n["id"] == node_id), None)
        if target is None:
            raise ApiException(
                status_code=404,
                code="NODE_NOT_FOUND",
                message=f"Compute node '{node_id}' not found.",
            )
        return ok({
            "node_id": node_id,
            "name": target.get("name"),
            "max_concurrent": target.get("max_concurrent", 1),
            "current_load": 0,
            "active": {},
            "queued": [],
        })

    # Enrich with node config
    nodes = _load_nodes()
    target = next((n for n in nodes if n["id"] == node_id), {})
    return ok({
        "node_id": node_id,
        "name": target.get("name", node_id),
        "hardware_profile": target.get("hardware_profile"),
        "gpu_name": target.get("gpu_name"),
        **node_info,
    })


@router.get("/compute/scheduler")
def scheduler_status() -> Dict[str, Any]:
    """Full scheduler diagnostic status — all nodes, loads, and queues."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    return ok(pipeline_scheduler.status())


@router.post("/compute/sync")
def sync_scheduler() -> Dict[str, Any]:
    """Re-sync scheduler from saved endpoint concurrency settings.

    Phase 72: Call this after changing endpoint concurrency to apply
    changes to the live scheduler without a daemon restart.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.load_from_settings()
    status = pipeline_scheduler.status()
    nodes_summary = {
        nid: v["max_concurrent"]
        for nid, v in status.get("nodes", {}).items()
    }
    logger.info("Scheduler synced: %s", nodes_summary)
    return ok({"synced": True, "nodes": nodes_summary})


@router.post("/compute/clear_locks")
def clear_locks(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Forcefully purge ghost tasks from the scheduler.

    If pipeline threads crash, they can leave active locks in the scheduler
    that prevent any other jobs from running. This self-healing endpoint
    clears them safely without needing to bounce the daemon.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    pipeline_scheduler.clean_locks(project_id)
    return ok({"cleared": True})


@router.get("/compute/concurrency/history")
def concurrency_history(
    node_id: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Phase 119 Task 15: recent AIMD events per slot, for the dashboard
    "Concurrency Health" weather-report panel.

    Each event has fields: ``ts`` (unix seconds), ``node_id``, ``before``,
    ``after``, ``reason`` (one of ``demand_recovery`` / ``additive_increase``
    / ``jumpstart`` / ``backoff`` / ``hydrate`` / ``edge_lock``),
    ``in_flight``, and ``mode``.

    The ring buffer lives in memory and does NOT survive daemon restart.
    Returns an envelope-shaped ``{"history": {node_id: [events...]}}``.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler

    out: Dict[str, list[dict]] = {}
    safe_limit = max(1, min(limit, 500))
    with pipeline_scheduler._lock:
        for nid, slot in pipeline_scheduler._slots.items():
            if node_id and nid != node_id:
                continue
            events = list(getattr(slot, "_history", []) or [])
            out[nid] = events[-safe_limit:]
    return {"history": out}


@router.post("/compute/concurrency/clear")
def clear_concurrency_lock(node_id: str) -> dict[str, Any]:
    """Phase 119 Task 16: full reset of a discovered-concurrency slot.

    Clears the persisted record AND re-seeds ``current_limit`` so the
    in-memory state actually drops back to a fresh starting point.
    Pre-Task-16 this only nulled out ``discovered_ceiling`` /
    ``ceiling_locked_until`` — leaving ``current_limit`` stuck at whatever
    AIMD had grown it to (e.g. 53 inherited from the pre-Phase-119 random
    walk).

    Behavior by node type:
      * ``cloud:default_ollama`` — re-probe via
        :func:`prep.services.pipeline.ollama_probe.probe_ollama_concurrency`,
        using the saved-endpoint base_url; falls back to 5 on any error.
      * Other ``cloud:*`` slots — reset to the Phase 82 jumpstart seed
        (5) and switch ``mode`` back to ``"jumpstart"``.
      * Local slots — leave ``current_limit`` at ``max_concurrent`` (the
        VRAM ceiling is a real hardware constraint, not something to
        rediscover).

    Also resets the per-slot streak / backoff timestamps and appends a
    ``reset`` event to the history ring buffer so the
    "Concurrency Health" weather report reflects the user action.
    Returns ``{status, node_id, old_limit, new_limit, new_mode}`` so
    the UI can confirm what actually changed.
    """
    from prep.services.pipeline import ollama_probe
    from prep.services.pipeline.concurrency_store import concurrency_store
    from prep.services.pipeline.scheduler import pipeline_scheduler

    try:
        concurrency_store().clear(node_id, "__default__")
    except Exception:
        pass

    slot = pipeline_scheduler._slots.get(node_id)
    if slot is None:
        return {
            "status": "ok",
            "node_id": node_id,
            "old_limit": None,
            "new_limit": None,
            "new_mode": None,
        }

    is_cloud = node_id.startswith("cloud:")
    old_limit = int(slot.current_limit)

    if is_cloud:
        if node_id == "cloud:default_ollama":
            try:
                from prep.services.settings_store import settings as _settings
                llm_config = _settings.get("llm_config") or {}
                host = "http://localhost:11434"
                for ep in llm_config.get("saved_endpoints", []):
                    if ep.get("id") == "default_ollama":
                        host = ep.get("base_url") or host
                        break
                new_seed = ollama_probe.probe_ollama_concurrency(host)
            except Exception as exc:
                logger.debug("Ollama probe in reset failed: %s", exc)
                new_seed = 5
        else:
            new_seed = 5
        new_mode: str = "jumpstart"
    else:
        # Local nodes: VRAM ceiling is a real hardware constraint —
        # don't fake-rediscover it. Just normalize current_limit back
        # to max_concurrent and clear AIMD scratch state.
        new_seed = max(1, slot.max_concurrent)
        new_mode = "congestion_avoidance"

    with pipeline_scheduler._lock:
        slot.discovered_ceiling = None
        slot.ceiling_locked_until = 0.0
        slot.current_limit = max(1, int(new_seed))
        # Cloud slots track AIMD mode; local slots stay in congestion_avoidance.
        slot.mode = new_mode  # type: ignore[assignment]
        slot.success_streak = 0
        slot._last_backoff_time = 0.0
        slot._last_recovery_time = 0.0
        slot._gate_binding_until = 0.0
        # Append a "reset" event so the weather-report panel shows
        # this user action alongside AIMD edges.
        try:
            pipeline_scheduler._record_history(
                slot, old_limit, slot.current_limit, "reset",
            )
        except Exception:
            pass
        # Wake any waiters so they observe the new (possibly smaller)
        # limit immediately rather than at the next acquire timeout.
        try:
            pipeline_scheduler._wake_slot_waiters(slot)
        except Exception:
            pass

    logger.info(
        "Concurrency reset: %s old_limit=%d → new_limit=%d mode=%s",
        node_id, old_limit, slot.current_limit, slot.mode,
    )
    return {
        "status": "ok",
        "node_id": node_id,
        "old_limit": old_limit,
        "new_limit": int(slot.current_limit),
        "new_mode": slot.mode,
    }

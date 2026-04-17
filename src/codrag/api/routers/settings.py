"""
CoDRAG Settings Router — Phase 24 (Phase 3: Settings Persistence)
==================================================================

Exposes the SQLite settings store via HTTP endpoints.

**Endpoints:**
  - GET  /settings                          — all global settings
  - GET  /settings/{key}                    — single global setting
  - PUT  /settings/{key}                    — set a global setting
  - DELETE /settings/{key}                  — delete a global setting
  - GET  /projects/{id}/settings            — all project settings
  - GET  /projects/{id}/settings/{key}      — single project setting
  - PUT  /projects/{id}/settings/{key}      — set a project setting
  - DELETE /projects/{id}/settings/{key}    — delete a project setting
  - POST /settings/pipeline-config          — update pipeline config (convenience)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)


def _get_store():
    from codrag.services.settings_store import settings
    return settings


router = APIRouter(tags=["settings"])


# ── Request models ───────────────────────────────────────────────

class SettingValue(BaseModel):
    value: Any


class PipelineConfigUpdate(BaseModel):
    fast_sync_auto: Optional[bool] = None
    deep_enrichment_mode: Optional[str] = None  # 'manual' | 'auto' | 'scheduled'
    schedule_frequency: Optional[str] = None
    schedule_day_of_week: Optional[int] = None
    schedule_hour: Optional[int] = None
    schedule_threshold_enabled: Optional[bool] = None
    schedule_time_enabled: Optional[bool] = None
    threshold_percent: Optional[int] = None
    budget_enabled: Optional[bool] = None
    budget_max_tokens: Optional[int] = None
    budget_max_minutes: Optional[int] = None
    budget_max_items: Optional[int] = None
    priority: Optional[str] = None
    llm_concurrency: Optional[int] = None  # Legacy: sets all three concurrency values
    llm_concurrency_fast: Optional[int] = None  # Catalogue stage (small/instruct model, stage 3)
    llm_concurrency_code: Optional[int] = None  # Inferred edges stage (coder model, stage 2)
    llm_concurrency_deep: Optional[int] = None  # Deep-enrichment stages (thinking model, stages 6-9)


# ── Global settings ──────────────────────────────────────────────

@router.get("/settings")
def get_all_settings() -> Dict[str, Any]:
    """Get all global settings."""
    from codrag.services.settings_store import settings
    return ok(settings.get_all())


@router.get("/settings/{key}")
def get_setting(key: str) -> Dict[str, Any]:
    """Get a single global setting by key."""
    from codrag.services.settings_store import settings
    value = settings.get(key)
    if value is None:
        raise ApiException(
            status_code=404,
            code="SETTING_NOT_FOUND",
            message=f"Setting '{key}' not found",
        )
    return ok({"key": key, "value": value})


@router.put("/settings/{key}")
def set_setting(key: str, body: SettingValue) -> Dict[str, Any]:
    """Set a global setting."""
    from codrag.services.settings_store import settings
    settings.set(key, body.value)
    return ok({"key": key, "value": body.value})


@router.delete("/settings/{key}")
def delete_setting(key: str) -> Dict[str, Any]:
    """Delete a global setting."""
    from codrag.services.settings_store import settings
    deleted = settings.delete(key)
    if not deleted:
        raise ApiException(
            status_code=404,
            code="SETTING_NOT_FOUND",
            message=f"Setting '{key}' not found",
        )
    return ok({"key": key, "deleted": True})


# ── Per-project settings ────────────────────────────────────────

@router.get("/projects/{project_id}/settings")
def get_project_settings(project_id: str) -> Dict[str, Any]:
    """Get all settings for a project."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.settings_store import settings
    return ok(settings.project_get_all(project_id))


@router.get("/projects/{project_id}/settings/{key}")
def get_project_setting(project_id: str, key: str) -> Dict[str, Any]:
    """Get a single project setting by key."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.settings_store import settings
    value = settings.project_get(project_id, key)
    if value is None:
        raise ApiException(
            status_code=404,
            code="SETTING_NOT_FOUND",
            message=f"Project setting '{key}' not found",
        )
    return ok({"key": key, "value": value})


@router.put("/projects/{project_id}/settings/{key}")
def set_project_setting(project_id: str, key: str, body: SettingValue) -> Dict[str, Any]:
    """Set a project setting."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.settings_store import settings
    settings.project_set(project_id, key, body.value)
    return ok({"key": key, "value": body.value})


@router.delete("/projects/{project_id}/settings/{key}")
def delete_project_setting(project_id: str, key: str) -> Dict[str, Any]:
    """Delete a project setting."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.settings_store import settings
    deleted = settings.project_delete(project_id, key)
    if not deleted:
        raise ApiException(
            status_code=404,
            code="SETTING_NOT_FOUND",
            message=f"Project setting '{key}' not found",
        )
    return ok({"key": key, "deleted": True})


# ── Pipeline config convenience endpoints ────────────────────────

@router.get("/settings/pipeline-config")
def get_pipeline_config() -> Dict[str, Any]:
    """Get the current pipeline configuration including llm_concurrency."""
    from codrag.services.settings_store import settings
    config = settings.get("pipeline_config") or {}
    return ok(config)


@router.get("/settings/llm-concurrency-guidelines")
def get_llm_concurrency_guidelines() -> Dict[str, Any]:
    """Return structured LLM concurrency guidelines for the dashboard info icon.

    Concurrency applies to all LLM pipeline stages:
    - Inferred edges, Catalogue: all items processed independently
    - Epistemic enrichment: concurrent within each dependency tier
    - Cluster synthesis: all clusters processed independently
    """
    from codrag.services.settings_store import settings
    config = settings.get("pipeline_config") or {}
    current = max(1, min(8, int(config.get("llm_concurrency", 1))))

    guidelines = {
        "current": current,
        "applies_to": "All LLM pipeline stages",
        "stages": [
            "Inferred Edges — all files analyzed independently",
            "Catalogue — all symbols and files augmented independently",
            "Epistemic Enrichment — concurrent within each dependency tier",
            "Cluster Synthesis — all clusters synthesized independently",
        ],
        "platforms": [
            {
                "name": "Discrete GPU (CUDA / ROCm)",
                "tiers": [
                    {"value": 1, "label": "Safe default — any hardware"},
                    {"value": 2, "label": "16 GB+ VRAM (RTX 4060, 3b/8b models)"},
                    {"value": 4, "label": "32 GB+ VRAM (RTX 5090, 8b/14b models)"},
                    {"value": 6, "label": "48 GB+ VRAM (2x RTX 4090, 35b models)"},
                    {"value": 8, "label": "64 GB+ VRAM (multi-GPU, 35b+ models)"},
                ],
            },
            {
                "name": "Apple Silicon (Metal, unified memory)",
                "tiers": [
                    {"value": 1, "label": "M1/M2 8GB — tight with 8b model loaded"},
                    {"value": 2, "label": "M1/M2 16GB, M3/M4 8GB+"},
                    {"value": 3, "label": "M1 Pro/Max (16–32GB)"},
                    {"value": 4, "label": "M2 Ultra / M3 Max / M4 Max (48–96GB)"},
                    {"value": 6, "label": "M2/M3/M4 Ultra (96–128GB)"},
                    {"value": 8, "label": "128 GB+ (Mac Studio / Mac Pro)"},
                ],
            },
            {
                "name": "Intel Mac",
                "tiers": [
                    {"value": 1, "label": "Always — no Metal acceleration"},
                ],
            },
        ],
    }
    return ok(guidelines)


@router.post("/settings/pipeline-config")
def update_pipeline_config(body: PipelineConfigUpdate) -> Dict[str, Any]:
    """Update pipeline configuration (convenience endpoint).

    Merges provided fields into the existing pipeline_config.
    Only non-None fields are applied.
    """
    from codrag.services.settings_store import settings

    config = settings.get("pipeline_config") or {
        "fast_sync": {"auto": True},
        "deep_enrichment": {"mode": "manual", "schedule": {}},
        "budgets": {},
    }

    # Detect mode transitions for triggering immediate runs
    prev_fast_auto = (config.get("fast_sync") or {}).get("auto", False)
    prev_deep_mode = (config.get("deep_enrichment") or {}).get("mode", "manual")

    if body.fast_sync_auto is not None:
        config.setdefault("fast_sync", {})["auto"] = body.fast_sync_auto

    if body.deep_enrichment_mode is not None:
        config.setdefault("deep_enrichment", {})["mode"] = body.deep_enrichment_mode

    sched = config.setdefault("deep_enrichment", {}).setdefault("schedule", {})
    if body.schedule_frequency is not None:
        sched["frequency"] = body.schedule_frequency
    if body.schedule_day_of_week is not None:
        sched["day_of_week"] = body.schedule_day_of_week
    if body.schedule_hour is not None:
        sched["hour"] = body.schedule_hour

    if body.schedule_threshold_enabled is not None:
        sched["threshold_enabled"] = body.schedule_threshold_enabled
    if body.schedule_time_enabled is not None:
        sched["time_enabled"] = body.schedule_time_enabled
    if body.threshold_percent is not None:
        sched["threshold_percent"] = body.threshold_percent
    if body.priority is not None:
        sched["priority"] = body.priority

    budgets = config.setdefault("budgets", {})
    if body.budget_enabled is not None:
        budgets["enabled"] = body.budget_enabled
    if body.budget_max_tokens is not None:
        budgets["max_tokens_per_run"] = body.budget_max_tokens
    if body.budget_max_minutes is not None:
        budgets["max_minutes_per_run"] = body.budget_max_minutes
    if body.budget_max_items is not None:
        budgets["max_items_per_stage"] = body.budget_max_items

    if body.llm_concurrency is not None:
        # Legacy single key — sets all three
        val = max(1, min(8, body.llm_concurrency))
        config["llm_concurrency"] = val
        config["llm_concurrency_fast"] = val
        config["llm_concurrency_code"] = val
        config["llm_concurrency_deep"] = val
    if body.llm_concurrency_fast is not None:
        config["llm_concurrency_fast"] = max(1, min(8, body.llm_concurrency_fast))
    if body.llm_concurrency_code is not None:
        config["llm_concurrency_code"] = max(1, min(8, body.llm_concurrency_code))
    if body.llm_concurrency_deep is not None:
        config["llm_concurrency_deep"] = max(1, min(8, body.llm_concurrency_deep))

    settings.set("pipeline_config", config)

    # When fast_sync_auto transitions to true, trigger fast_sync for all
    # trace-enabled projects so the existing backlog is processed immediately
    # rather than waiting for new file-system events.
    if body.fast_sync_auto and not prev_fast_auto:
        import threading

        def _trigger_auto_runs():
            try:
                from codrag.services.pipeline_orchestrator import pipeline_orchestrator
                from codrag.services.project_helpers import get_registry, get_project_activity_status
                for proj in get_registry().list_projects():
                    pcfg = proj.config if isinstance(proj.config, dict) else {}
                    trace_cfg = pcfg.get("trace") if isinstance(pcfg.get("trace"), dict) else {}
                    if not trace_cfg.get("enabled"):
                        continue
                    if get_project_activity_status(proj.id) != "active":
                        continue
                    started = pipeline_orchestrator.run_fast_sync(proj.id)
                    if started:
                        logger.info("Auto-mode activated: triggered fast_sync for %s", proj.id)
            except Exception:
                logger.debug("Auto-mode trigger failed (non-fatal)", exc_info=True)

        threading.Thread(target=_trigger_auto_runs, daemon=True).start()

    # When deep_enrichment_mode transitions to 'auto', trigger deep enrichment
    # for all trace-enabled projects so incomplete deep stages start immediately.
    if body.deep_enrichment_mode == "auto" and prev_deep_mode != "auto":
        import threading

        def _trigger_deep_runs():
            try:
                from codrag.services.pipeline_orchestrator import pipeline_orchestrator
                from codrag.services.project_helpers import get_registry, get_project_activity_status
                for proj in get_registry().list_projects():
                    pcfg = proj.config if isinstance(proj.config, dict) else {}
                    trace_cfg = pcfg.get("trace") if isinstance(pcfg.get("trace"), dict) else {}
                    if not trace_cfg.get("enabled"):
                        continue
                    if get_project_activity_status(proj.id) != "active":
                        continue
                    started = pipeline_orchestrator.run_deep_enrichment(proj.id)
                    if started:
                        logger.info("Deep auto-mode activated: triggered deep_enrichment for %s", proj.id)
            except Exception:
                logger.debug("Deep auto-mode trigger failed (non-fatal)", exc_info=True)

        threading.Thread(target=_trigger_deep_runs, daemon=True).start()

    return ok(config)


# ── Advanced config convenience endpoints ─────────────────────

class AdvancedConfigUpdate(BaseModel):
    # Pipeline
    checkpoint_interval: Optional[int] = None       # Augmentation checkpoint frequency (default 500)
    min_edge_confidence: Optional[float] = None     # Inferred edge confidence threshold (default 0.5)
    # Chunking
    chunk_max_chars: Optional[int] = None           # Code chunk size (default 2000)
    chunk_overlap_chars: Optional[int] = None       # Code chunk overlap (default 200)
    md_chunk_max_chars: Optional[int] = None        # Markdown chunk size (default 1800)
    md_chunk_min_chars: Optional[int] = None        # Markdown chunk min size (default 350)


_ADVANCED_DEFAULTS = {
    "checkpoint_interval": 500,
    "min_edge_confidence": 0.5,
    "chunk_max_chars": 2000,
    "chunk_overlap_chars": 200,
    "md_chunk_max_chars": 1800,
    "md_chunk_min_chars": 350,
}


@router.get("/settings/advanced-config")
def get_advanced_config() -> Dict[str, Any]:
    """Get global advanced configuration with defaults."""
    from codrag.services.settings_store import settings
    saved = settings.get("advanced_config") or {}
    merged = {**_ADVANCED_DEFAULTS, **saved}
    return ok(merged)


@router.post("/settings/advanced-config")
def update_advanced_config(body: AdvancedConfigUpdate) -> Dict[str, Any]:
    """Update global advanced configuration (merges with existing)."""
    from codrag.services.settings_store import settings

    config = settings.get("advanced_config") or dict(_ADVANCED_DEFAULTS)

    if body.checkpoint_interval is not None:
        config["checkpoint_interval"] = max(50, min(5000, body.checkpoint_interval))
    if body.min_edge_confidence is not None:
        config["min_edge_confidence"] = max(0.0, min(1.0, body.min_edge_confidence))
    if body.chunk_max_chars is not None:
        config["chunk_max_chars"] = max(500, min(10000, body.chunk_max_chars))
    if body.chunk_overlap_chars is not None:
        config["chunk_overlap_chars"] = max(0, min(2000, body.chunk_overlap_chars))
    if body.md_chunk_max_chars is not None:
        config["md_chunk_max_chars"] = max(500, min(10000, body.md_chunk_max_chars))
    if body.md_chunk_min_chars is not None:
        config["md_chunk_min_chars"] = max(50, min(2000, body.md_chunk_min_chars))

    settings.set("advanced_config", config)
    return ok(config)


# ── Compute node CRUD (Phase 45) ─────────────────────────────

class ComputeNodeCreate(BaseModel):
    name: str
    type: str = "local"  # 'local' | 'remote' | 'cloud'
    max_concurrent: int = 1
    hardware_profile: Optional[str] = None
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    endpoint_ids: list = []


class ComputeNodeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    max_concurrent: Optional[int] = None
    hardware_profile: Optional[str] = None
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    endpoint_ids: Optional[list] = None


def _get_llm_config() -> dict:
    from codrag.services.settings_store import settings
    return settings.get("llm_config") or {}


def _save_llm_config(cfg: dict, change_source: str = "user") -> None:
    """Save LLM config and log the change to the audit trail (GW-7)."""
    from codrag.services.settings_store import settings
    settings.set("llm_config", cfg)

    # Phase 72: Live-sync endpoint concurrency into the scheduler
    # so changes take effect immediately without daemon restart.
    try:
        from codrag.services.pipeline.scheduler import pipeline_scheduler
        pipeline_scheduler.sync_endpoint_concurrency()
    except Exception:
        pass

    # GW-7: Policy change audit trail
    try:
        from codrag.core.audit_log import get_audit_log
        audit = get_audit_log()
        audit.record(
            event_type="llm_config_changed",
            severity="info",
            message=f"LLM configuration updated by {change_source}",
            metadata={
                "source": change_source,
                "endpoints_count": len(cfg.get("saved_endpoints", [])),
            },
        )
    except Exception:
        pass


@router.get("/compute/nodes")
def list_compute_nodes() -> Dict[str, Any]:
    """List all compute nodes."""
    cfg = _get_llm_config()
    nodes = cfg.get("compute_nodes", [])
    return ok({"nodes": nodes})


@router.post("/compute/nodes")
def create_compute_node(body: ComputeNodeCreate) -> Dict[str, Any]:
    """Create a new compute node."""
    import uuid

    cfg = _get_llm_config()
    nodes = cfg.setdefault("compute_nodes", [])

    node = {
        "id": f"node_{uuid.uuid4().hex[:8]}",
        "name": body.name,
        "type": body.type,
        "max_concurrent": max(1, min(100, body.max_concurrent)),
        "endpoint_ids": body.endpoint_ids,
    }
    if body.hardware_profile:
        node["hardware_profile"] = body.hardware_profile
    if body.gpu_name:
        node["gpu_name"] = body.gpu_name
    if body.gpu_vram_gb is not None:
        node["gpu_vram_gb"] = body.gpu_vram_gb

    nodes.append(node)
    _save_llm_config(cfg)
    return ok({"node": node})


@router.put("/compute/nodes/{node_id}")
def update_compute_node(node_id: str, body: ComputeNodeUpdate) -> Dict[str, Any]:
    """Update a compute node."""
    cfg = _get_llm_config()
    nodes = cfg.get("compute_nodes", [])

    node = next((n for n in nodes if n["id"] == node_id), None)
    if not node:
        raise ApiException(
            status_code=404,
            code="COMPUTE_NODE_NOT_FOUND",
            message=f"Compute node '{node_id}' not found",
        )

    if body.name is not None:
        node["name"] = body.name
    if body.type is not None:
        node["type"] = body.type
    if body.max_concurrent is not None:
        node["max_concurrent"] = max(1, min(100, body.max_concurrent))
    if body.hardware_profile is not None:
        node["hardware_profile"] = body.hardware_profile
    if body.gpu_name is not None:
        node["gpu_name"] = body.gpu_name
    if body.gpu_vram_gb is not None:
        node["gpu_vram_gb"] = body.gpu_vram_gb
    if body.endpoint_ids is not None:
        node["endpoint_ids"] = body.endpoint_ids

    _save_llm_config(cfg)
    return ok({"node": node})


@router.delete("/compute/nodes/{node_id}")
def delete_compute_node(node_id: str) -> Dict[str, Any]:
    """Delete a compute node. Unlinks any associated endpoints."""
    cfg = _get_llm_config()
    nodes = cfg.get("compute_nodes", [])

    original_len = len(nodes)
    cfg["compute_nodes"] = [n for n in nodes if n["id"] != node_id]

    if len(cfg["compute_nodes"]) == original_len:
        raise ApiException(
            status_code=404,
            code="COMPUTE_NODE_NOT_FOUND",
            message=f"Compute node '{node_id}' not found",
        )

    # Unlink endpoints that referenced this node
    for ep in cfg.get("saved_endpoints", []):
        if ep.get("compute_node_id") == node_id:
            ep["compute_node_id"] = None

    _save_llm_config(cfg)
    return ok({"deleted": node_id})


@router.get("/compute/scheduler-status")
def get_scheduler_status() -> Dict[str, Any]:
    """Return current scheduler status: active slots, queued pipelines per node."""
    from codrag.services.pipeline.scheduler import pipeline_scheduler
    return ok(pipeline_scheduler.status())


# ── EA-C2: Admin Policy Endpoint ──────────────────────────────────────


@router.get("/settings/admin-policy")
def get_admin_policy() -> Dict[str, Any]:
    """Return the parsed admin policy from the active project's team_config.

    Returns a default permissive policy if no team_config or admin_policy exists.
    """
    from codrag.core.team_config import AdminPolicy, parse_admin_policy

    try:
        store = _get_store()
        active_id = store.get("active_project")
        if active_id:
            proj_root = store.project_get(active_id, "root_path")
            if proj_root:
                from pathlib import Path
                from codrag.core.team_config import load_admin_policy
                policy = load_admin_policy(Path(proj_root))
                return ok(policy.to_dict())
    except Exception as e:
        logger.warning("Failed to load admin policy: %s", e)

    return ok(AdminPolicy().to_dict())


# ── EA-H2: Audit Log Query Endpoint ──────────────────────────────────


class AuditLogQuery(BaseModel):
    event_type: Optional[str] = None
    severity: Optional[str] = None
    since: Optional[float] = None
    until: Optional[float] = None
    limit: int = 100
    offset: int = 0


@router.post("/admin/audit-log")
def query_audit_log(q: AuditLogQuery) -> Dict[str, Any]:
    """Query the audit log with optional filters."""
    from codrag.core.audit_log import get_audit_log

    audit = get_audit_log()
    events = audit.query(
        event_type=q.event_type,
        severity=q.severity,
        since=q.since,
        until=q.until,
        limit=q.limit,
        offset=q.offset,
    )
    total = audit.count(
        event_type=q.event_type,
        severity=q.severity,
        since=q.since,
        until=q.until,
    )
    return ok({"events": events, "total": total, "limit": q.limit, "offset": q.offset})


# ── EA-H8: Audit Log Export ───────────────────────────────────────────


@router.get("/admin/audit-log/export")
def export_audit_log(format: str = "json") -> Dict[str, Any]:
    """Export the full audit log as JSON or CSV."""
    from codrag.core.audit_log import get_audit_log

    audit = get_audit_log()
    if format.lower() == "csv":
        content = audit.export_csv()
        return ok({"format": "csv", "content": content})
    else:
        events = audit.query(limit=10000)
        return ok({"format": "json", "events": events, "count": len(events)})


# ── EA-I1: Security Health Check ──────────────────────────────────────


@router.get("/admin/security-health")
def get_security_health() -> Dict[str, Any]:
    """Run all security health checks and return aggregate results."""
    from codrag.core.security_health import run_security_checks

    try:
        store = _get_store()
        active_id = store.get("active_project")
        project_root = None
        if active_id:
            root = store.project_get(active_id, "root_path")
            if root:
                from pathlib import Path
                project_root = Path(root)

        results = run_security_checks(project_root=project_root)
        return ok(results)
    except Exception as e:
        logger.error("Security health check failed: %s", e)
        return ok({"score": 0, "total": 16, "status": "error", "checks": [], "error": str(e)})


# ── EA-I12: Security Report Export ────────────────────────────────────


@router.get("/admin/security-report")
def export_security_report() -> Dict[str, Any]:
    """Export a comprehensive security report combining health checks and recent events."""
    from codrag.core.audit_log import get_audit_log
    from codrag.core.security_health import run_security_checks

    try:
        store = _get_store()
        active_id = store.get("active_project")
        project_root = None
        if active_id:
            root = store.project_get(active_id, "root_path")
            if root:
                from pathlib import Path
                project_root = Path(root)

        health = run_security_checks(project_root=project_root)
        audit = get_audit_log()
        recent_events = audit.query(limit=50)

        import time
        return ok({
            "generated_at": time.time(),
            "health": health,
            "recent_events": recent_events,
            "event_count": audit.count(),
        })
    except Exception as e:
        logger.error("Security report export failed: %s", e)
        raise ApiException(status_code=500, code="REPORT_FAILED", message=str(e))


# ── EA-I11: Admin Actions ─────────────────────────────────────────────


class AdminActionRequest(BaseModel):
    project_id: Optional[str] = None
    endpoint_id: Optional[str] = None
    reason: str = ""


@router.post("/admin/actions/quarantine-project")
def quarantine_project(req: AdminActionRequest) -> Dict[str, Any]:
    """Quarantine a project — mark it inactive and stop pipelines."""
    from codrag.core.audit_log import get_audit_log

    if not req.project_id:
        raise ApiException(status_code=400, code="MISSING_PROJECT_ID", message="project_id is required")

    store = _get_store()
    store.set_project(req.project_id, "quarantined", "true")

    audit = get_audit_log()
    audit.record(
        event_type="admin_quarantine",
        severity="warning",
        message=f"Project {req.project_id} quarantined: {req.reason}",
        metadata={"project_id": req.project_id, "reason": req.reason},
    )
    return ok({"quarantined": req.project_id})


@router.post("/admin/actions/block-endpoint")
def block_endpoint(req: AdminActionRequest) -> Dict[str, Any]:
    """Block an LLM endpoint from being used."""
    from codrag.core.audit_log import get_audit_log

    if not req.endpoint_id:
        raise ApiException(status_code=400, code="MISSING_ENDPOINT_ID", message="endpoint_id is required")

    cfg = _get_llm_config()
    for ep in cfg.get("saved_endpoints", []):
        if ep.get("id") == req.endpoint_id:
            ep["blocked"] = True
            ep["blocked_reason"] = req.reason
            break
    _save_llm_config(cfg)

    audit = get_audit_log()
    audit.record(
        event_type="admin_block_endpoint",
        severity="warning",
        message=f"Endpoint {req.endpoint_id} blocked: {req.reason}",
        metadata={"endpoint_id": req.endpoint_id, "reason": req.reason},
    )
    return ok({"blocked": req.endpoint_id})


@router.post("/admin/actions/approve-config")
def approve_config_change(req: AdminActionRequest) -> Dict[str, Any]:
    """Log approval of a configuration change."""
    from codrag.core.audit_log import get_audit_log

    audit = get_audit_log()
    audit.record(
        event_type="admin_config_approval",
        severity="info",
        message=f"Config change approved: {req.reason}",
        metadata={"project_id": req.project_id, "reason": req.reason},
    )
    return ok({"approved": True})


# ── Batch Estimate Endpoint ───────────────────────────────────────────


@router.get("/settings/batch-estimate")
def get_batch_estimate() -> Dict[str, Any]:
    """Return the auto-detected batch profile for the current LLM config.

    Resolves the batch profile for each configured model slot (small, large, code)
    and returns per-stage batch sizes + estimated API calls based on file count.
    """
    from codrag.core.batch_profiles import (
        BatchStage,
        resolve_profile,
        PROFILE_OFF,
    )

    cfg = _get_llm_config()
    context_cache = cfg.get("model_context_cache") or {}
    endpoints = {ep["id"]: ep for ep in cfg.get("saved_endpoints", [])}

    def _resolve_slot(slot_cfg: dict) -> Optional[Dict[str, Any]]:
        ep_id = slot_cfg.get("endpoint_id", "")
        model = slot_cfg.get("model", "")
        if not ep_id or not model:
            return None
        ep = endpoints.get(ep_id)
        if not ep:
            return None
        provider = ep.get("provider", "ollama")
        ctx = context_cache.get(model)
        context_tokens = int(ctx) if isinstance(ctx, (int, float)) and ctx > 0 else None
        profile = resolve_profile(provider, model, context_tokens=context_tokens)
        is_local = profile.name.value == "off"
        return {
            "provider": provider,
            "model": model,
            "profile_name": profile.name.value,
            "output_class": profile.output_class,
            "is_local": is_local,
            "per_stage": {
                stage.value: profile.batch_size(stage)
                for stage in BatchStage
            },
        }

    # Resolve each slot
    slots = {}
    for slot_name in ("small_model", "large_model", "code_model"):
        slot_cfg = cfg.get(slot_name, {})
        resolved = _resolve_slot(slot_cfg)
        if resolved:
            slots[slot_name] = resolved

    # Get file count for the active project to estimate API calls
    file_count = 0
    try:
        store = _get_store()
        active_id = store.get("active_project")
        if active_id:
            from codrag.core.project_registry import get_project, project_index_dir
            from codrag.core.trace import TraceIndex
            proj = get_project(active_id)
            if proj:
                idx_dir = project_index_dir(proj)
                ti = TraceIndex(idx_dir)
                if ti.exists():
                    ti.load()
                    file_count = ti.node_count()
    except Exception:
        pass

    # Compute estimated API calls per stage for the primary model
    estimates = {}
    primary = slots.get("small_model") or next(iter(slots.values()), None)
    if primary and not primary["is_local"] and file_count > 0:
        for stage_key, batch_size in primary["per_stage"].items():
            if batch_size > 0:
                calls = max(1, -(-file_count // batch_size))  # ceil division
                estimates[stage_key] = {
                    "batch_size": batch_size,
                    "estimated_calls": calls,
                    "file_count": file_count,
                }

    return ok({
        "slots": slots,
        "file_count": file_count,
        "estimated_calls": estimates,
    })

"""
CoDRAG PM Push Router — Phase 65
==================================

REST endpoints for pushing CoDRAG opportunities to external PM tools.
Paperclip-first, universal interface.

Endpoints:
  POST /projects/{id}/pm/push           — Push opportunities to PM tool
  POST /projects/{id}/pm/push/dry-run   — Preview what would be pushed
  GET  /projects/{id}/pm/config         — Get PM push configuration
  PUT  /projects/{id}/pm/config         — Update PM push configuration
  GET  /projects/{id}/pm/health         — Check PM connection health
  GET  /projects/{id}/pm/history        — Push history
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pm_push"])


def _srv():
    import prep.server as _s
    return _s


# ── Request models ──────────────────────────────────────────────────

class PushRequest(BaseModel):
    strategy: Optional[str] = None          # Override consolidation strategy
    min_priority: Optional[str] = None      # Override priority filter
    exclude_categories: Optional[List[str]] = None  # Override exclusions


class PMConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    paperclip_url: Optional[str] = None
    paperclip_company_id: Optional[str] = None
    paperclip_api_key: Optional[str] = None
    auto_push: Optional[bool] = None
    push_cadence: Optional[str] = None
    consolidation_strategy: Optional[str] = None
    min_priority: Optional[str] = None
    exclude_categories: Optional[List[str]] = None


# ── Helpers ─────────────────────────────────────────────────────────

def _load_config() -> Dict[str, Any]:
    """Load PM push config from settings store."""
    from prep.services.settings_store import settings
    return settings.get("pm_push", {
        "enabled": False,
        "provider": "paperclip",
        "paperclip": {
            "url": "http://localhost:3100",
            "company_id": "",
            "api_key": "",
        },
        "auto_push": False,
        "push_cadence": "manual",
        "consolidation_strategy": "category",
        "min_priority": "P2",
        "exclude_categories": [],
    })


def _save_config(config: Dict[str, Any]) -> None:
    """Save PM push config to settings store."""
    from prep.services.settings_store import settings
    settings.set("pm_push", config)


def _get_items(project_id: str):
    """Load current ActionItems for a project."""
    proj = _srv()._require_project(project_id)

    from prep.core.audit.opportunity_manager import OpportunityManager
    from prep.core.project_registry import project_index_dir

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)
    return mgr.get_opportunities(), proj, index_dir


# ── Push endpoints ──────────────────────────────────────────────────

@router.post("/projects/{project_id}/pm/push")
def push_to_pm(
    project_id: str,
    req: Optional[PushRequest] = None,
) -> Dict[str, Any]:
    """Push consolidated opportunities to the configured PM tool.

    Loads ActionItems from OpportunityManager, consolidates them
    using the configured strategy, then pushes to Paperclip (or
    other configured PM tool).
    """
    config = _load_config()
    if not config.get("enabled"):
        raise ApiException(
            status_code=400,
            code="PM_PUSH_DISABLED",
            message="PM push is not enabled. Configure it in settings.",
        )

    items, proj, index_dir = _get_items(project_id)
    if not items:
        return ok({
            "status": "no_items",
            "message": "No active opportunities to push.",
        })

    from prep.adapters.pm_models import PMPushConfig
    from prep.adapters.push_engine import PushEngine, create_push_engine

    pm_config = PMPushConfig.from_dict(config)
    engine = create_push_engine(pm_config)

    # Apply overrides from request
    strategy = (req.strategy if req and req.strategy else pm_config.consolidation_strategy)
    min_priority = (req.min_priority if req and req.min_priority else pm_config.min_priority)
    exclude_cats = (req.exclude_categories if req and req.exclude_categories else pm_config.exclude_categories)

    result = engine.push(
        items,
        codrag_project_id=project_id,
        strategy=strategy,
        min_priority=min_priority,
        exclude_categories=exclude_cats,
        project_root=str(proj.path),
    )

    # Record history
    PushEngine.record_push(index_dir, result, provider=pm_config.provider)

    return ok(result.to_dict())


@router.post("/projects/{project_id}/pm/push/dry-run")
def push_dry_run(
    project_id: str,
    req: Optional[PushRequest] = None,
) -> Dict[str, Any]:
    """Preview what would be pushed without actually pushing.

    Returns consolidated groups with item counts, priorities,
    and category breakdowns.
    """
    config = _load_config()
    items, proj, index_dir = _get_items(project_id)

    if not items:
        return ok({
            "status": "no_items",
            "groups": [],
            "total_items": 0,
        })

    from prep.adapters.pm_models import PMPushConfig
    from prep.adapters.push_engine import PushEngine, create_push_engine

    pm_config = PMPushConfig.from_dict(config)

    # For dry-run, we don't need a real adapter — just the consolidator
    from prep.core.audit.consolidator import Consolidator
    consolidator = Consolidator()

    strategy = (req.strategy if req and req.strategy else pm_config.consolidation_strategy)
    min_priority = (req.min_priority if req and req.min_priority else pm_config.min_priority)
    exclude_cats = set(req.exclude_categories if req and req.exclude_categories else pm_config.exclude_categories)

    # Filter
    from prep.adapters.push_engine import _PRIO_ORDER
    max_prio = _PRIO_ORDER.get(min_priority, 9)
    filtered = [
        i for i in items
        if i.state != "dismissed"
        and _PRIO_ORDER.get(i.priority, 9) <= max_prio
        and i.category not in exclude_cats
    ]

    groups = consolidator.consolidate(filtered, strategy=strategy)

    return ok({
        "status": "preview",
        "total_items": len(filtered),
        "consolidated_groups": len(groups),
        "provider": pm_config.provider,
        "strategy": strategy,
        "groups": [g.to_dict() for g in groups],
    })


# ── Config endpoints ────────────────────────────────────────────────

@router.get("/projects/{project_id}/pm/config")
def get_pm_config(project_id: str) -> Dict[str, Any]:
    """Get PM push configuration."""
    _srv()._require_project(project_id)
    config = _load_config()
    # Redact API key in response
    safe = dict(config)
    if "paperclip" in safe and isinstance(safe["paperclip"], dict):
        pc = dict(safe["paperclip"])
        if pc.get("api_key"):
            pc["api_key"] = "***" + pc["api_key"][-4:] if len(pc["api_key"]) > 4 else "***"
        safe["paperclip"] = pc
    return ok(safe)


@router.put("/projects/{project_id}/pm/config")
def update_pm_config(
    project_id: str,
    req: PMConfigUpdate,
) -> Dict[str, Any]:
    """Update PM push configuration."""
    from prep.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    config = _load_config()

    # Apply updates
    if req.enabled is not None:
        config["enabled"] = req.enabled
    if req.provider is not None:
        config["provider"] = req.provider
    if req.auto_push is not None:
        config["auto_push"] = req.auto_push
    if req.push_cadence is not None:
        config["push_cadence"] = req.push_cadence
    if req.consolidation_strategy is not None:
        config["consolidation_strategy"] = req.consolidation_strategy
    if req.min_priority is not None:
        config["min_priority"] = req.min_priority
    if req.exclude_categories is not None:
        config["exclude_categories"] = req.exclude_categories

    # Paperclip-specific
    if not isinstance(config.get("paperclip"), dict):
        config["paperclip"] = {}
    if req.paperclip_url is not None:
        config["paperclip"]["url"] = req.paperclip_url
    if req.paperclip_company_id is not None:
        config["paperclip"]["company_id"] = req.paperclip_company_id
    if req.paperclip_api_key is not None:
        config["paperclip"]["api_key"] = req.paperclip_api_key

    _save_config(config)
    return ok({"status": "updated"})


# ── Health check ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/pm/health")
def pm_health(project_id: str) -> Dict[str, Any]:
    """Check PM tool connection health."""
    _srv()._require_project(project_id)
    config = _load_config()

    from prep.adapters.pm_models import PMPushConfig
    from prep.adapters.push_engine import create_push_engine

    try:
        pm_config = PMPushConfig.from_dict(config)
        engine = create_push_engine(pm_config)
        healthy = engine.adapter.health_check()
        return ok({
            "provider": pm_config.provider,
            "healthy": healthy,
            "url": pm_config.paperclip_url if pm_config.provider == "paperclip" else "",
        })
    except Exception as e:
        return ok({
            "provider": config.get("provider", "unknown"),
            "healthy": False,
            "error": str(e),
        })


# ── History ─────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/pm/history")
def push_history(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Get push history for this project."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir

    index_dir = project_index_dir(proj)
    history_path = index_dir / "audit" / "push_history.json"

    if not history_path.exists():
        return ok({"entries": [], "total": 0})

    try:
        entries = json.loads(history_path.read_text(encoding="utf-8"))
        # Most recent first
        entries = list(reversed(entries))[:limit]
        return ok({"entries": entries, "total": len(entries)})
    except (json.JSONDecodeError, OSError):
        return ok({"entries": [], "total": 0})

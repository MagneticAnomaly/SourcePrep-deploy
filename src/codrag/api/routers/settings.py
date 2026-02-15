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
    budget_max_tokens: Optional[int] = None
    budget_max_minutes: Optional[int] = None
    budget_max_items: Optional[int] = None


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


# ── Pipeline config convenience endpoint ─────────────────────────

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

    budgets = config.setdefault("budgets", {})
    if body.budget_max_tokens is not None:
        budgets["max_tokens_per_run"] = body.budget_max_tokens
    if body.budget_max_minutes is not None:
        budgets["max_minutes_per_run"] = body.budget_max_minutes
    if body.budget_max_items is not None:
        budgets["max_items_per_stage"] = body.budget_max_items

    settings.set("pipeline_config", config)
    return ok(config)

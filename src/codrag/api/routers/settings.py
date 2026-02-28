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
    schedule_threshold_enabled: Optional[bool] = None
    schedule_time_enabled: Optional[bool] = None
    threshold_percent: Optional[int] = None
    budget_max_tokens: Optional[int] = None
    budget_max_minutes: Optional[int] = None
    budget_max_items: Optional[int] = None
    llm_concurrency: Optional[int] = None  # Concurrent LLM requests (1=sequential, 2-4 for GPU with ≥12GB VRAM)


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

    budgets = config.setdefault("budgets", {})
    if body.budget_max_tokens is not None:
        budgets["max_tokens_per_run"] = body.budget_max_tokens
    if body.budget_max_minutes is not None:
        budgets["max_minutes_per_run"] = body.budget_max_minutes
    if body.budget_max_items is not None:
        budgets["max_items_per_stage"] = body.budget_max_items

    if body.llm_concurrency is not None:
        config["llm_concurrency"] = max(1, min(8, body.llm_concurrency))

    settings.set("pipeline_config", config)
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

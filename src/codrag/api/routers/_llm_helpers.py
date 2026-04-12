"""Shared helpers for LLM-related API routers.

Phase 82: Provides model resolution so queue.py and llm.py can
determine provider/model for a project's current pipeline stage
without duplicating the slot -> endpoint -> provider resolution chain.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Make patchable for tests
try:
    from codrag.services.settings_store import settings
except ImportError:
    settings = None  # type: ignore[assignment]


def resolve_model_for_stage(
    project_id: str,
    stage: str,
) -> Optional[Tuple[str, str]]:
    """Resolve (provider, model) for a project's current pipeline stage.

    Walks: stage -> model_slot -> llm_config["{slot}_model"] -> endpoint -> provider.
    Returns None if resolution fails (no config, non-LLM stage, etc).
    """
    from codrag.services.pipeline.stages import STAGE_MODEL_SLOT, StageId

    try:
        stage_id = StageId(stage)
    except ValueError:
        return None

    slot_name = STAGE_MODEL_SLOT.get(stage_id)
    if not slot_name:
        return None

    try:
        llm_config = settings.get("llm_config") or {}
    except Exception:
        return None

    slot_config = llm_config.get(f"{slot_name}_model", {})
    endpoint_id = slot_config.get("endpoint_id")
    model = slot_config.get("model", "")
    if not endpoint_id or not model:
        return None

    provider = "ollama"
    for ep in llm_config.get("saved_endpoints", []):
        if ep.get("id") == endpoint_id:
            provider = ep.get("provider", "ollama")
            break

    return provider, model

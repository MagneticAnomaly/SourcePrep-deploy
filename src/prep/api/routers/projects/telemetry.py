"""
Telemetry router for project token usage — Phase 56F.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from prep.api.envelope import ok
from prep.api.routers.projects.helpers import _srv
from prep.services.token_telemetry import telemetry

router = APIRouter(tags=["telemetry"])


@router.get("/{project_id}/token-usage")
def get_project_token_usage(project_id: str, since: float = 0.0) -> Dict[str, Any]:
    """Aggregated token usage for a project, grouped by CodragTaskId.

    Used by the AI Gateway dashboard to display physical token consumption
    instead of heuristic estimates.
    """
    _srv()._require_project(project_id)
    usage = telemetry.get_aggregated_usage(project_id, since_timestamp=since)
    return ok({"usage": usage})

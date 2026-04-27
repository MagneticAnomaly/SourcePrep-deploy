from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok
from prep.core.scope_store import GLOBAL_SCOPE_ID, scope_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scopes"])


# ── Request models ───────────────────────────────────────────────


class CreateScopeRequest(BaseModel):
    display_name: str
    paths: list[str] | None = None
    assigned_to_role: str | None = None


class UpdateScopeRequest(BaseModel):
    display_name: str | None = None
    assigned_to_role: str | None = None


class PathsRequest(BaseModel):
    paths: list[str]


# ── Helpers ──────────────────────────────────────────────────────


def _synthesize_global(project_id: str) -> dict[str, Any]:
    from prep.services.project_helpers import require_project

    proj = require_project(project_id)
    paths = sorted((proj.config or {}).get("included_paths", []))
    return {
        "id": GLOBAL_SCOPE_ID,
        "display_name": "Global",
        "paths": paths,
        "weights": {},
        "assigned_to_role": None,
        "created_at": "",
        "updated_at": "",
    }


def _summary(rec_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rec_dict["id"],
        "display_name": rec_dict["display_name"],
        "path_count": len(rec_dict.get("paths", [])),
        "assigned_to_role": rec_dict.get("assigned_to_role"),
    }


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/projects/{project_id}/scopes")
def list_scopes(project_id: str) -> dict[str, Any]:
    from prep.server import _require_project

    _require_project(project_id)
    summaries = [_summary(_synthesize_global(project_id))]
    summaries.extend(_summary(r.to_dict()) for r in scope_store.list(project_id))
    return ok({"scopes": summaries})


@router.get("/projects/{project_id}/scopes/{scope_id}")
def get_scope(project_id: str, scope_id: str) -> dict[str, Any]:
    from prep.server import _require_project

    _require_project(project_id)
    if scope_id == GLOBAL_SCOPE_ID:
        return ok(_synthesize_global(project_id))
    rec = scope_store.get(project_id, scope_id)
    if rec is None:
        raise ApiException(
            status_code=404,
            code="SCOPE_NOT_FOUND",
            message=f"scope '{scope_id}' not found",
        )
    return ok(rec.to_dict())


@router.post("/projects/{project_id}/scopes")
def create_scope(project_id: str, req: CreateScopeRequest) -> dict[str, Any]:
    from prep.server import _require_project

    _require_project(project_id)
    try:
        rec = scope_store.create(
            project_id,
            display_name=req.display_name,
            paths=req.paths,
            assigned_to_role=req.assigned_to_role,
        )
    except ValueError as e:
        raise ApiException(status_code=409, code="SCOPE_INVALID", message=str(e)) from e
    return ok(rec.to_dict())


@router.put("/projects/{project_id}/scopes/{scope_id}")
def update_scope(
    project_id: str,
    scope_id: str,
    req: UpdateScopeRequest,
) -> dict[str, Any]:
    from prep.server import _require_project

    _require_project(project_id)
    if scope_id == GLOBAL_SCOPE_ID:
        raise ApiException(
            status_code=400,
            code="GLOBAL_IMMUTABLE",
            message="global scope metadata is immutable",
        )
    update_kwargs: dict[str, Any] = {}
    if "display_name" in req.model_fields_set:
        update_kwargs["display_name"] = req.display_name
    if "assigned_to_role" in req.model_fields_set:
        update_kwargs["assigned_to_role"] = req.assigned_to_role
    try:
        rec = scope_store.update(project_id, scope_id, **update_kwargs)
    except KeyError as e:
        raise ApiException(
            status_code=404,
            code="SCOPE_NOT_FOUND",
            message=f"scope '{scope_id}' not found",
        ) from e
    except ValueError as e:
        raise ApiException(status_code=409, code="SCOPE_INVALID", message=str(e)) from e
    return ok(rec.to_dict())


@router.delete("/projects/{project_id}/scopes/{scope_id}")
def delete_scope(project_id: str, scope_id: str) -> dict[str, Any]:
    from prep.server import _require_project

    _require_project(project_id)
    if scope_id == GLOBAL_SCOPE_ID:
        raise ApiException(
            status_code=400,
            code="GLOBAL_UNDELETABLE",
            message="global scope cannot be deleted",
        )
    deleted = scope_store.delete(project_id, scope_id)
    return ok({"deleted": deleted})

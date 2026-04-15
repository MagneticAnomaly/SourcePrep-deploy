"""
Role Overrides endpoints — Phase 104.

Exposes per-project, per-role overrides applied when an agent calls
``codrag(role=...)``. Overrides layer on top of built-in ``RoleVector``
defaults; see ``codrag.services.role_overrides_store``.

Endpoints:
  GET    /projects/{id}/role-overrides               — list all overrides
  GET    /projects/{id}/role-overrides/{role_id}     — get one
  PUT    /projects/{id}/role-overrides/{role_id}     — upsert {max_chars}
  DELETE /projects/{id}/role-overrides/{role_id}     — remove override + pins
  POST   /projects/{id}/role-overrides/{role_id}/pin   — body: {concept_id}
  DELETE /projects/{id}/role-overrides/{role_id}/pin/{concept_id} — unpin
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from codrag.api.envelope import ok
from codrag.services.role_overrides_store import role_overrides_store

from .helpers import _srv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects", "role-overrides"])


# ── Request models ──────────────────────────────────────────────────


class RoleOverrideUpsertRequest(BaseModel):
    max_chars: int | None = Field(
        default=None,
        ge=200,
        le=20000,
        description="Override char budget for this role's sub-atlas. "
                    "Must be between 200 and 20000. Omit to leave unchanged.",
    )


class PinConceptRequest(BaseModel):
    concept_id: str = Field(min_length=1, description="Concept ID to pin.")


# ── Helpers ─────────────────────────────────────────────────────────


def _require_project(project_id: str):
    return _srv()._require_project(project_id)


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/projects/{project_id}/role-overrides")
def list_role_overrides(project_id: str) -> dict:
    """List all role overrides configured for a project."""
    _require_project(project_id)
    overrides = role_overrides_store.list(project_id)
    return ok({
        "overrides": [ov.to_dict() for ov in overrides],
        "count": len(overrides),
    })


@router.get("/projects/{project_id}/role-overrides/{role_id}")
def get_role_override(project_id: str, role_id: str) -> dict:
    """Return the override for a specific role, or None if none is set."""
    _require_project(project_id)
    ov = role_overrides_store.get(project_id, role_id)
    return ok({"override": ov.to_dict() if ov else None})


@router.put("/projects/{project_id}/role-overrides/{role_id}")
def upsert_role_override(
    project_id: str,
    role_id: str,
    body: RoleOverrideUpsertRequest,
) -> dict:
    """Upsert override fields for a role.

    Currently supports ``max_chars``. Concept pinning is a separate
    endpoint so the UI can optimistically update pins without rewriting
    the whole override.
    """
    _require_project(project_id)
    ov = role_overrides_store.upsert(
        project_id, role_id, max_chars=body.max_chars
    )
    return ok({"override": ov.to_dict()})


@router.delete("/projects/{project_id}/role-overrides/{role_id}")
def delete_role_override(project_id: str, role_id: str) -> dict:
    """Delete the override AND all pinned concepts for this role."""
    _require_project(project_id)
    deleted = role_overrides_store.delete(project_id, role_id)
    return ok({"deleted": deleted})


@router.post("/projects/{project_id}/role-overrides/{role_id}/pin")
def pin_concept_to_role(
    project_id: str,
    role_id: str,
    body: PinConceptRequest,
) -> dict:
    """Pin a concept to a role. Pinned concepts are prepended to the
    role's sub-atlas projection (bounded by budget)."""
    _require_project(project_id)
    pinned = role_overrides_store.pin_concept(
        project_id, role_id, body.concept_id
    )
    return ok({"pinned_concept_ids": pinned})


@router.delete("/projects/{project_id}/role-overrides/{role_id}/pin/{concept_id}")
def unpin_concept_from_role(
    project_id: str,
    role_id: str,
    concept_id: str,
) -> dict:
    """Remove a concept pin from a role."""
    _require_project(project_id)
    pinned = role_overrides_store.unpin_concept(
        project_id, role_id, concept_id
    )
    return ok({"pinned_concept_ids": pinned})


@router.get("/projects/{project_id}/concepts/{concept_id}/pinned-roles")
def list_roles_pinning_concept(project_id: str, concept_id: str) -> dict:
    """Return role_ids currently pinning this concept.

    Used by the concepts panel to show "pinned to: engineering, security"
    badges without the UI having to list every role individually.
    """
    _require_project(project_id)
    roles = role_overrides_store.list_roles_pinning_concept(
        project_id, concept_id,
    )
    return ok({"role_ids": roles, "count": len(roles)})

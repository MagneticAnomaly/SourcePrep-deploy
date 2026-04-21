"""
Roles endpoint — Phase 104.

Single read-only endpoint that exposes the built-in RoleVectors so the
dashboard can populate its role picker and anchor the budget-slider's
default tick without hardcoding a copy of role_vectors.py in TypeScript.

    GET /roles  →  { roles: [{ role_id, display_name, max_chars, ... }] }
"""
from __future__ import annotations

from fastapi import APIRouter

from prep.api.envelope import ok

router = APIRouter(tags=["roles"])


@router.get("/roles")
def list_builtin_roles() -> dict:
    """Return every built-in RoleVector, sorted by display name.

    The payload matches RoleVector.to_dict so the UI can share the
    `RoleVectorPayload` type used for `applied_role`.
    """
    from prep.core.atlas.role_vectors import BUILT_IN_ROLES

    roles = [rv.to_dict() for rv in BUILT_IN_ROLES.values()]
    roles.sort(key=lambda r: r["display_name"])
    return ok({"roles": roles, "count": len(roles)})

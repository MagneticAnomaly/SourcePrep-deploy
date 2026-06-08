"""
Project build endpoint.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from prep.api.envelope import ApiException, ok
from prep.core.project_registry import project_index_dir

from .helpers import _srv, _get_project_globs
from .models import BuildRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.post("/projects/{project_id}/build")
def build_project(project_id: str, full: bool = False, req: Optional[BuildRequest] = None) -> Dict[str, Any]:
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)
    include_globs, exclude_globs = _get_project_globs(proj, use_defaults=False)
    # Pass None instead of [] so downstream build() applies its own policy defaults
    include_globs = include_globs or None
    exclude_globs = exclude_globs or None
    cfg = proj.config or {}
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
    hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)

    # Phase 24 SM-8 + 2026-05 follow-up + 2026-05-17 regression fix:
    #   request body has paths     → use those (caller-explicit override)
    #   request body absent/None   → derive from project state, but distinguish
    #     "user has never touched scope" (legacy: embed everything) from
    #     "user explicitly cleared scope" (tri-state: embed nothing).
    #
    # Signal: cfg["included_paths"] is only written by mutate_global_scope and
    # scope endpoints — its absence means the user never engaged the panel.
    # Equivalently, named scopes only exist if the user created them. If both
    # signals are absent, fall back to None so a fresh `prep build` indexes
    # the full repo (matching the pre-0251b538 behavior the dual-tier system
    # was built on). The 2026-05 follow-up flipped this default to [], which
    # silently neutered prep_search on every freshly-imported project — the
    # trace graph would index everything while the CodeIndex indexed nothing.
    if req is not None and req.included_paths is not None:
        included_paths = req.included_paths
    else:
        from prep.core.scope_store import scope_store
        from prep.services.project_helpers import compute_index_membership
        cfg_has_global_scope = isinstance(cfg, dict) and "included_paths" in cfg
        has_named_scopes = bool(scope_store.list(project_id))
        if cfg_has_global_scope or has_named_scopes:
            included_paths = sorted(compute_index_membership(project_id))
        else:
            included_paths = None
    logger.info(
        "build_project: req=%s, included_paths=%s",
        req,
        "None (untouched scope → full repo)" if included_paths is None else f"count={len(included_paths)}",
    )

    from prep.core.project_registry import ensure_prep_pointer

    # Self-heal missing pointers on build
    try:
        ensure_prep_pointer(proj)
    except Exception:
        pass

    use_gitignore = bool(cfg.get("use_gitignore", True)) if isinstance(cfg, dict) else True
    started = _srv()._start_project_build(
        proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes,
        use_gitignore=use_gitignore,
        included_paths=included_paths,
    )
    if not started:
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Build already running")

    return ok({"started": True, "building": True, "build_id": None})



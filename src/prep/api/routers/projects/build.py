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

    # Phase 24 SM-8 + 2026-05 follow-up: included_paths is derived from
    # project state, not from a None-default that meant "embed everything".
    #   request body has paths     → use those (caller-explicit override)
    #   request body absent/None   → compute_index_membership(project)
    #     · returns []          → user has not added anything to scope; embed nothing
    #     · returns [paths…]    → embed exactly that union of global + named scopes
    # The legacy "absent key = embed all repo" default was a footgun: a
    # freshly-imported project with no Scope panel interaction would walk
    # the full repo on the first /build call, persist 9k+ chunks_code into
    # the index metadata, and the IndexStatusCard would then display that
    # number forever as "last built". An untouched project should embed
    # nothing until the user explicitly selects something.
    if req is not None and req.included_paths is not None:
        included_paths = req.included_paths
    else:
        from prep.services.project_helpers import compute_index_membership
        included_paths = sorted(compute_index_membership(project_id))
    logger.info("build_project: req=%s, included_paths count=%d", req, len(included_paths))

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



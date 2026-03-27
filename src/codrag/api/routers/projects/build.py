"""
Project build endpoint.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from codrag.api.envelope import ApiException, ok
from codrag.core.project_registry import project_index_dir

from .helpers import _srv, _get_project_globs
from .models import BuildRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.post("/projects/{project_id}/build")
def build_project(project_id: str, full: bool = False, req: Optional[BuildRequest] = None) -> Dict[str, Any]:
    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)
    include_globs, exclude_globs = _get_project_globs(proj, use_defaults=False)
    # Pass None instead of [] so downstream build() applies its own policy defaults
    include_globs = include_globs or None
    exclude_globs = exclude_globs or None
    cfg = proj.config or {}
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
    hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)

    # Extract included_paths from request body, falling back to project config
    included_paths = req.included_paths if req and req.included_paths else None
    if not included_paths:
        included_paths = cfg.get("included_paths") if isinstance(cfg, dict) else None
    logger.info("build_project: req=%s, included_paths count=%s", req, len(included_paths) if included_paths else None)

    from codrag.core.project_registry import ensure_codrag_pointer
    
    # Self-heal missing pointers on build
    try:
        ensure_codrag_pointer(proj)
    except Exception:
        pass

    started = _srv()._start_project_build(
        proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes,
        included_paths=included_paths,
    )
    if not started:
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Build already running")

    return ok({"started": True, "building": True, "build_id": None})



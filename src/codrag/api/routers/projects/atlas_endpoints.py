"""
Atlas-related project endpoints — get atlas, regenerate atlas.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from codrag.api.envelope import ok
from codrag.core.project_registry import project_index_dir

from .helpers import _srv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _serialize_segments(atlas) -> list[dict[str, Any]]:
    """Return segment metadata for the dashboard sub-atlas tree.

    Per-segment staleness inherits atlas-level staleness for v1; segments
    do not carry individual stale flags today. Phase 104 follow-on will
    add per-segment fingerprint drift detection.
    """
    if not atlas.has_segments():
        return []
    atlas_stale = atlas.is_stale()
    segments: list[dict[str, Any]] = []
    for seg in atlas.load_segments():
        segments.append({
            "segment_id": seg.segment_id,
            "segment_name": seg.segment_name,
            "dir_path": seg.dir_path,
            "file_count": seg.file_count,
            "char_count": seg.char_count,
            "mode": seg.mode,
            "generated_at": seg.generated_at,
            "stale": atlas_stale,
        })
    return segments


def _build_atlas_response(
    atlas,
    doc,
    *,
    role: str | None = None,
    stale_override: bool | None = None,
) -> dict[str, Any]:
    """Build a consistent atlas response payload used by GET and regenerate.

    Args:
        atlas:          CodebaseAtlas instance (already loaded).
        doc:            Root AtlasDocument from atlas.load() or generate_segmented()[0].
        role:           If provided, attach role projection under `role_atlas`.
        stale_override: If set, use this for the `stale` field (regenerate just
                        finished, so it's freshly False regardless of is_stale()).
    """
    display_content, display_chars = atlas.get_display_content()
    stale = atlas.is_stale() if stale_override is None else stale_override

    payload: dict[str, Any] = {
        "exists": True,
        "content": display_content or doc.content,
        "mode": doc.mode,
        "model": doc.model,
        "generated_at": doc.generated_at,
        "file_count": doc.file_count,
        "module_count": doc.module_count,
        "char_count": display_chars or doc.char_count,
        "stale": stale,
        "segmented": atlas.has_segments(),
        "segments": _serialize_segments(atlas),
    }

    if role:
        try:
            role_atlas = atlas.get_role_atlas(role)
            payload["role"] = role
            payload["role_atlas"] = role_atlas
            payload["role_atlas_chars"] = len(role_atlas)
        except Exception as e:
            logger.warning("Role projection failed for role=%s: %s", role, e)
            payload["role_atlas_error"] = str(e)

    return payload


@router.get("/projects/{project_id}/atlas")
def get_atlas(
    project_id: str,
    role: str | None = Query(None, description="Role for filtered sub-atlas (e.g. 'ceo', 'design engineer')"),
) -> dict[str, Any]:
    """Get the cached Codebase Atlas for a project."""
    from codrag.core.atlas import CodebaseAtlas

    proj = _srv()._require_project(project_id)
    idx_dir = project_index_dir(proj)
    atlas = CodebaseAtlas(idx_dir)
    doc = atlas.load()

    if doc is None:
        return ok({
            "exists": False,
            "content": None,
            "stale": True,
            "segments": [],
        })

    return ok(_build_atlas_response(atlas, doc, role=role))


@router.post("/projects/{project_id}/atlas/regenerate")
def regenerate_atlas(project_id: str) -> dict[str, Any]:
    """Manually trigger Atlas regeneration."""
    from codrag.core.atlas import CodebaseAtlas

    proj = _srv()._require_project(project_id)
    idx_dir = project_index_dir(proj)

    # Try to use task-assigned LLM; fall back to structural atlas.
    # Atlas synthesis is a heavy task — increase timeout to 180s.
    llm_client = None
    try:
        from codrag.server import _get_llm_client_for_task
        llm_client = _get_llm_client_for_task("atlas")
        if llm_client and not llm_client.is_available():
            llm_client = None
    except Exception:
        llm_client = None

    if llm_client:
        llm_client.timeout = 180.0

    project_root = Path(proj.path) if proj.path else None
    atlas = CodebaseAtlas(idx_dir, llm=llm_client, project_root=project_root)

    # Try segmented generation first; falls back to single atlas internally.
    root_doc, _seg_docs = atlas.generate_segmented()

    if not root_doc.content:
        return ok({
            "exists": False,
            "content": None,
            "stale": False,
            "segments": [],
        })

    return ok(_build_atlas_response(atlas, root_doc, stale_override=False))

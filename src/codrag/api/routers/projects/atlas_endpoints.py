"""
Atlas-related project endpoints — get atlas, regenerate atlas.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

from codrag.api.envelope import ApiException, ok
from codrag.core.project_registry import project_index_dir

from .helpers import _srv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.get("/projects/{project_id}/atlas")
def get_atlas(project_id: str) -> Dict[str, Any]:
    """Get the cached Codebase Atlas for a project."""
    from codrag.core.atlas import CodebaseAtlas
    from codrag.core.project_registry import project_index_dir

    proj = _srv()._require_project(project_id)
    idx_dir = project_index_dir(proj)
    atlas = CodebaseAtlas(idx_dir)
    doc = atlas.load()

    if doc is None:
        return ok({
            "exists": False,
            "content": None,
            "stale": True,
        })

    # For dashboard: concatenate root + all segments into one display string
    display_content, display_chars = atlas.get_display_content()

    return ok({
        "exists": True,
        "content": display_content or doc.content,
        "mode": doc.mode,
        "model": doc.model,
        "generated_at": doc.generated_at,
        "file_count": doc.file_count,
        "module_count": doc.module_count,
        "char_count": display_chars or doc.char_count,
        "stale": atlas.is_stale(),
        "segmented": atlas.has_segments(),
    })


@router.post("/projects/{project_id}/atlas/regenerate")
def regenerate_atlas(project_id: str) -> Dict[str, Any]:
    """Manually trigger Atlas regeneration."""
    from codrag.core.atlas import CodebaseAtlas
    from codrag.core.project_registry import project_index_dir

    proj = _srv()._require_project(project_id)
    idx_dir = project_index_dir(proj)

    # Try to use task-assigned LLM; fall back to structural atlas
    # Atlas synthesis is a heavy task — increase timeout to 180s
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

    # Pass project_root for workspace detection in segmented atlas
    project_root = Path(proj.path) if proj.path else None
    atlas = CodebaseAtlas(idx_dir, llm=llm_client, project_root=project_root)

    # Try segmented generation first; falls back to single atlas internally
    root_doc, seg_docs = atlas.generate_segmented()

    # For dashboard: concatenate root + all segments into one display string
    display_content, display_chars = atlas.get_display_content()

    result: Dict[str, Any] = {
        "exists": bool(root_doc.content),
        "content": display_content or root_doc.content,
        "mode": root_doc.mode,
        "model": root_doc.model,
        "char_count": display_chars or root_doc.char_count,
        "file_count": root_doc.file_count,
        "module_count": root_doc.module_count,
        "generated_at": root_doc.generated_at,
        "stale": False,
        "segmented": bool(seg_docs),
    }
    if seg_docs:
        result["segments"] = [
            {
                "segment_id": sd.segment_id,
                "segment_name": sd.segment_name,
                "dir_path": sd.dir_path,
                "file_count": sd.file_count,
                "char_count": sd.char_count,
            }
            for sd in seg_docs
        ]
    return ok(result)




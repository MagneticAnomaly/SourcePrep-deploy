"""
Atlas-related project endpoints — get atlas.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from prep.api.envelope import ok
from prep.core.project_registry import project_index_dir

from .helpers import _srv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _load_docs_for_segments(idx_dir) -> dict[str, list[dict[str, Any]]]:
    """Phase 124 T3: aggregate atlas_markdown_links.json by segment.

    Returns ``{segment_id: [{path, mention_count}, ...]}``. Returns an
    empty mapping (no error) when ``atlas_markdown_links.json`` or the
    segments manifest is missing — endpoints stay backward-compatible.
    """
    try:
        import json
        from pathlib import Path
        from prep.core.atlas.markdown_links import (
            load as _load_md_links,
            aggregate_for_segments,
        )
        idx = Path(idx_dir)
        md_result = _load_md_links(idx)
        if md_result is None:
            return {}
        manifest_path = idx / "atlas_segments_manifest.json"
        if not manifest_path.is_file():
            return {}
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, list):
            return {}
        return aggregate_for_segments(md_result, manifest, cap=5)
    except Exception as e:
        logger.debug("docs_for_segments aggregation skipped: %s", e)
        return {}


def _serialize_segments(atlas) -> list[dict[str, Any]]:
    """Return segment metadata + content for the dashboard sub-atlas tree.

    Content is included so the SubAtlasTree can render per-segment previews
    without a second round trip. Typical segment is ~1-3 KB, so even a
    many-segment project adds only a few dozen KB to the payload.

    Per-segment staleness inherits atlas-level staleness for v1; segments
    do not carry individual stale flags today. Phase 104 follow-on will
    add per-segment fingerprint drift detection.

    Phase 124 T3: each segment dict gains a ``docs_for_segment`` field
    listing the top-N markdown docs that mention files inside the
    segment. Empty list when no markdown_links data is on disk.
    """
    if not atlas.has_segments():
        return []
    atlas_stale = atlas.is_stale()
    docs_index = _load_docs_for_segments(atlas.index_dir)
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
            "content": seg.content,
            "docs_for_segment": docs_index.get(seg.segment_id, []),
        })
    return segments


def _load_role_extras(
    project_id: str,
    role: str,
) -> tuple[Any, Any, list[dict[str, Any]]]:
    """Resolve the role + load override + pinned concept dicts for projection.

    Returns ``(role_vector, override, pinned_concepts_list)``. The
    ``role_vector`` is the canonical ``RoleVector`` resolved from the
    free-form role argument — callers reuse it to avoid a second
    ``resolve_role`` call. Any of the values may be empty/None when no
    data is available.
    """
    from prep.core.atlas.role_resolver import resolve_role
    from prep.services.role_overrides_store import role_overrides_store

    # Overrides are keyed by canonical role_id; resolve the free-form role
    # argument to its built-in id so the UI and MCP agree.
    try:
        role_vector = resolve_role(role)
    except Exception as e:
        logger.debug("Failed to resolve role '%s': %s", role, e)
        raise

    override = None
    try:
        override = role_overrides_store.get(project_id, role_vector.role_id)
    except Exception as e:
        logger.debug(
            "Failed to load role override for %s/%s: %s",
            project_id, role_vector.role_id, e,
        )

    pinned_concepts: list[dict[str, Any]] = []
    if override and override.pinned_concept_ids:
        try:
            from prep.services.concept_store import concept_store
            for cid in override.pinned_concept_ids:
                c = concept_store.get(cid)
                if c is not None:
                    pinned_concepts.append({"title": c.title, "content": c.content})
        except Exception as e:
            logger.debug(
                "Failed to load pinned concepts for %s/%s: %s",
                project_id, role_vector.role_id, e,
            )

    return role_vector, override, pinned_concepts


def _build_atlas_response(
    atlas,
    doc,
    project_id: str,
    *,
    role: str | None = None,
) -> dict[str, Any]:
    """Build the atlas response payload served by GET /projects/{id}/atlas.

    Args:
        atlas:      CodebaseAtlas instance (already loaded).
        doc:        Root AtlasDocument from atlas.load().
        project_id: Project id — used to look up role overrides when ``role``
                    is set.
        role:       If provided, attach role projection under ``role_atlas``
                    and the applied-lens fields under ``applied_role`` /
                    ``override``.
    """
    display_content, display_chars = atlas.get_display_content()

    payload: dict[str, Any] = {
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
        "segments": _serialize_segments(atlas),
    }

    if role:
        try:
            role_vector, override, pinned = _load_role_extras(project_id, role)

            role_atlas = atlas.get_role_atlas(
                role,
                overrides=override,
                pinned_concepts=pinned or None,
            )
            payload["role"] = role
            payload["role_atlas"] = role_atlas
            payload["role_atlas_chars"] = len(role_atlas)

            # Applied RoleVector = built-in defaults merged with override.
            applied = role_vector
            if override and override.max_chars is not None:
                applied = role_vector.copy()
                applied.max_chars = override.max_chars
            payload["applied_role"] = applied.to_dict()
            payload["override"] = override.to_dict() if override else None
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
    from prep.core.atlas import CodebaseAtlas

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

    return ok(_build_atlas_response(atlas, doc, project_id, role=role))

"""
Project file operations — file content, detect-stack, roots, file listing.
"""
from __future__ import annotations

import fnmatch
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from prep.api.envelope import ApiException, ok
from prep.core.project_registry import project_index_dir
from prep.core.repo_profile import scan_for_presets, STACK_PRESETS, DEFAULT_EXCLUDE_DIR_NAMES

from .helpers import _srv, _get_project_globs
from .models import DetectStackResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.get("/projects/{project_id}/file")
def get_project_file_content(project_id: str, path: str = Query(..., min_length=1)) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    include_globs, exclude_globs = _get_project_globs(proj)
    cfg = proj.config or {}
    max_file_bytes = int((cfg.get("max_file_bytes") or 400_000) if isinstance(cfg, dict) else 400_000)

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    rel_path = Path(str(path).strip().lstrip("/"))
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path without '..' segments.",
        )

    rel_str = str(rel_path)

    def _glob_match(rel: str, pat: str) -> bool:
        rel = rel.replace("\\", "/")
        pat = str(pat or "")
        if not pat:
            return False
        if fnmatch.fnmatch(rel, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:]):
            return True
        return False

    def _matches_any(rel: str, patterns: List[str]) -> bool:
        for pat in patterns:
            try:
                if _glob_match(rel, str(pat)):
                    return True
            except Exception:
                continue
        return False

    if not _matches_any(rel_str, include_globs):
        raise ApiException(
            status_code=403,
            code="FILE_NOT_INCLUDED",
            message="File is not included by project policy",
            hint="Update include_globs to allow this file.",
        )

    if _matches_any(rel_str, exclude_globs):
        raise ApiException(
            status_code=403,
            code="FILE_EXCLUDED",
            message="File is excluded by project policy",
            hint="Update exclude_globs to allow this file.",
        )

    abs_path = (repo_root / rel_path).resolve()
    # SECURITY: Prevent Path Traversal by ensuring the resolved absolute path starts with the resolved repo_root
    try:
        abs_path.relative_to(repo_root)
    except ValueError:
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path.",
        )

    if not abs_path.is_relative_to(repo_root):
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path.",
        )

    if not abs_path.exists() or not abs_path.is_file():
        raise ApiException(status_code=404, code="FILE_NOT_FOUND", message="File not found")

    size = abs_path.stat().st_size
    if size > max_file_bytes:
        raise ApiException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds max_file_bytes ({max_file_bytes} bytes)",
            hint="Increase max_file_bytes in project settings or pin a smaller file.",
            details={"max_file_bytes": max_file_bytes, "bytes": size},
        )

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_file_bytes + 1)
    except Exception:
        raise ApiException(status_code=500, code="FILE_READ_FAILED", message="Failed to read file")

    if len(content.encode("utf-8", errors="ignore")) > max_file_bytes:
        raise ApiException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds max_file_bytes ({max_file_bytes} bytes)",
            hint="Increase max_file_bytes in project settings or pin a smaller file.",
            details={"max_file_bytes": max_file_bytes, "bytes": size},
        )

    return ok(
        {
            "file": {
                "path": rel_str,
                "name": abs_path.name,
                "content": content,
                "bytes": int(size),
                "max_file_bytes": int(max_file_bytes),
            }
        }
    )


@router.get("/projects/{project_id}/detect-stack")
def detect_project_stack(project_id: str) -> Dict[str, Any]:
    """Analyze the project to recommend include patterns."""
    proj = _srv()._require_project(project_id)
    detected_presets = scan_for_presets(Path(proj.path))
    
    recommended_globs = []
    for preset in detected_presets:
        recommended_globs.extend(STACK_PRESETS.get(preset, []))
        
    return ok({
        "recommended_globs": sorted(list(set(recommended_globs))),
        "detected_presets": sorted(detected_presets),
        "all_presets": STACK_PRESETS,
    })


@router.get("/projects/{project_id}/roots")
def get_project_roots(project_id: str) -> Dict[str, Any]:
    """Get available root directories for a project."""
    proj = _srv()._require_project(project_id)
    project_root = Path(proj.path).expanduser().resolve()
    
    if not project_root.exists() or not project_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    roots: List[str] = []
    
    # Generic discovery: list all top-level directories except ignored ones
    ignore = DEFAULT_EXCLUDE_DIR_NAMES | {".idea", ".vscode"}
    try:
        for item in sorted(project_root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name in ignore:
                continue
            roots.append(item.name)
    except Exception:
        pass

    return ok({"roots": roots})


@router.get("/projects/{project_id}/files")
def list_project_files(
    project_id: str,
    path: str = "",
    depth: int = 3,
) -> Dict[str, Any]:
    """List files and directories under a project path.

    Parameters
    ----------
    path : str
        Relative path within the project root (empty = project root).
    depth : int
        Maximum recursion depth (default 3, max 10).
    """
    proj = _srv()._require_project(project_id)
    project_root = Path(proj.path).expanduser().resolve()

    if not project_root.exists() or not project_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    # Resolve target directory safely
    target = (project_root / path).resolve()
    # Security: ensure target is within project root
    try:
        target.relative_to(project_root)
    except ValueError:
        raise ApiException(status_code=400, code="PATH_OUTSIDE_PROJECT", message="Path is outside project root")

    if not target.exists() or not target.is_dir():
        raise ApiException(status_code=400, code="PATH_NOT_FOUND", message=f"Directory not found: {path}")

    ignore = DEFAULT_EXCLUDE_DIR_NAMES | {
              ".idea", ".vscode", ".eggs", "*.egg-info", ".DS_Store"}
    depth = min(max(depth, 1), 10)

    # Build per-file chunk count from index documents for status annotation
    idx = _srv()._get_project_index(proj)
    chunks_by_file: Dict[str, int] = {}
    if idx.is_loaded() and idx._documents:
        for doc in idx._documents:
            sp = str(doc.get("source_path") or "")
            if sp:
                chunks_by_file[sp] = chunks_by_file.get(sp, 0) + 1

    def _is_ignored(name: str) -> bool:
        if name in ignore or (name.startswith(".") and name != ".env"):
            return True
        if any(name.endswith(suf) for suf in (".egg-info", ".pyc", ".pyo")):
            return True
        return False

    def _has_visible_children(directory: Path) -> bool:
        """Check if a directory has any non-ignored children."""
        try:
            for item in directory.iterdir():
                if not _is_ignored(item.name):
                    return True
        except PermissionError:
            pass
        return False

    def _scan(directory: Path, current_depth: int, rel_prefix: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        try:
            items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return entries

        for item in items:
            name = item.name
            if _is_ignored(name):
                continue

            child_rel = f"{rel_prefix}/{name}" if rel_prefix else name

            if item.is_dir():
                if current_depth < depth:
                    children = _scan(item, current_depth + 1, child_rel)
                    entries.append({
                        "name": name,
                        "type": "folder",
                        "children": children,
                    })
                else:
                    # Depth limit reached — signal whether folder has children
                    entry: Dict[str, Any] = {
                        "name": name,
                        "type": "folder",
                        "children": [],
                    }
                    if _has_visible_children(item):
                        entry["has_children"] = True
                    entries.append(entry)
            elif item.is_file():
                file_entry: Dict[str, Any] = {
                    "name": name,
                    "type": "file",
                }
                chunk_count = chunks_by_file.get(child_rel)
                if chunk_count is not None:
                    file_entry["status"] = "indexed"
                    file_entry["chunks"] = chunk_count
                entries.append(file_entry)
        return entries

    # Build the relative prefix for the scan root
    rel_prefix = path  # empty string for project root, else the subpath
    tree = _scan(target, 1, rel_prefix)
    return ok({"path": path, "tree": tree})



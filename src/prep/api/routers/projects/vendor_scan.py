"""Vendor-scan endpoints.

- GET /projects/{id}/vendor_scan — returns cached VendorScanResult.
- POST /projects/{id}/vendor_scan/rescan — synchronous fresh scan + persist.
- POST /projects/{id}/exclude_proposals/apply — confirm user choices from Gate 2 modal.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from prep.api.envelope import ok
from prep.core.vendor_sniffer import scan_for_vendor_dirs
from prep.core.vendor_sniffer.models import VendorScanResult

from .helpers import _srv

logger = logging.getLogger(__name__)

router = APIRouter(tags=["vendor_scan"])


class ApplyProposalsRequest(BaseModel):
    exclude: List[str] = Field(default_factory=list)
    dismiss: List[str] = Field(default_factory=list)
    add_to_gitignore: List[str] = Field(default_factory=list)


def _glob_for(rel_path: str) -> str:
    return f"**/{rel_path}/**"


def _filter_dismissed(result: VendorScanResult, dismissed: List[str]) -> VendorScanResult:
    """Drop any proposed candidate whose rel_path is in `dismissed`."""
    if not dismissed:
        return result
    dropped = set(dismissed)
    return VendorScanResult(
        auto_excluded=result.auto_excluded,
        proposed=[c for c in result.proposed if c.rel_path not in dropped],
        gitignore_gaps=result.gitignore_gaps,
        scanned_at=result.scanned_at,
        status=result.status,
        error=result.error,
    )


def _merge_excludes_into_config(cfg: dict, new_globs: List[str]) -> dict:
    """Phase 115 additive-merge: append new globs not already present."""
    new_cfg = dict(cfg)
    existing = list(new_cfg.get("exclude_globs", []))
    seen = set(existing)
    for g in new_globs:
        if g not in seen:
            existing.append(g)
            seen.add(g)
    new_cfg["exclude_globs"] = existing
    return new_cfg


@router.get("/projects/{project_id}/vendor_scan")
def get_vendor_scan(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    raw = proj.config.get("vendor_scan")
    if raw is None:
        # No scan has ever run — return a pending sentinel rather than 404.
        empty = VendorScanResult(
            auto_excluded=[], proposed=[], gitignore_gaps=[],
            scanned_at=0.0, status="pending", error=None,
        )
        return ok(empty.to_dict())
    return ok(raw)


@router.post("/projects/{project_id}/vendor_scan/rescan")
def rescan_vendor(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    result = scan_for_vendor_dirs(Path(proj.path))
    dismissed = list(proj.config.get("dismissed_proposals") or [])
    filtered = _filter_dismissed(result, dismissed)

    reg = _srv()._get_registry()

    def _merge(cfg: dict) -> dict:
        new_cfg = _merge_excludes_into_config(cfg, filtered.auto_excluded)
        new_cfg["vendor_scan"] = filtered.to_dict()
        return new_cfg

    reg.mutate_config(project_id, _merge)
    return ok(filtered.to_dict())


@router.post("/projects/{project_id}/exclude_proposals/apply")
def apply_proposals(project_id: str, req: ApplyProposalsRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    new_globs = [_glob_for(rel) for rel in req.exclude]

    if req.add_to_gitignore:
        logger.info(
            "add_to_gitignore requested but not yet implemented (v2 stub): %s",
            req.add_to_gitignore,
        )

    reg = _srv()._get_registry()

    def _merge(cfg: dict) -> dict:
        new_cfg = _merge_excludes_into_config(cfg, new_globs)
        existing_dismissed = list(new_cfg.get("dismissed_proposals") or [])
        seen = set(existing_dismissed)
        for rel in req.dismiss:
            if rel not in seen:
                existing_dismissed.append(rel)
                seen.add(rel)
        if existing_dismissed:
            new_cfg["dismissed_proposals"] = existing_dismissed
        return new_cfg

    updated = reg.mutate_config(project_id, _merge)
    return ok({
        "config": updated.config,
        "dismissed_proposals": list(updated.config.get("dismissed_proposals") or []),
    })

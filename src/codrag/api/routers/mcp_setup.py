"""MCP Configuration & Paperclip Skill API.

Provides endpoints for:
  - Generating MCP config snippets for various IDEs (copy-paste flow)
  - Installing/uninstalling the CoDRAG Paperclip skill globally
  - Checking skill installation status
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


# ── Request Models ──────────────────────────────────────────────────


class SkillInstallRequest(BaseModel):
    """Request to install or uninstall the CoDRAG Paperclip skill."""
    mode: str = "symlink"  # "symlink" or "copy"


# ── Config Generation (copy-paste flow) ─────────────────────────────


@router.get("/mcp/config")
def mcp_config_get(
    ide: str = "all",
    mode: str = "auto",
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate MCP config snippets for the requested IDE(s).

    Returns ready-to-paste JSON for each supported runtime.

    Query params:
        ide: Target IDE — "all", "claude-code", "cursor", "vscode", etc.
        mode: MCP mode — "auto" (default), "project", or "direct".
        project_id: Required when mode="project".
    """
    from codrag.mcp_config import generate_mcp_configs

    daemon_url = _get_daemon_url()
    configs = generate_mcp_configs(
        ide=ide,
        daemon_url=daemon_url,
        mode=mode,
        project_id=project_id,
    )
    return ok({
        "configs": configs,
        "daemon_url": daemon_url,
        "mode": mode,
    })


# ── Paperclip Skill Installation ────────────────────────────────────


@router.post("/paperclip/install-skill")
def paperclip_install_skill(req: SkillInstallRequest) -> Dict[str, Any]:
    """Install the CoDRAG skill into ~/.claude/skills/codrag.

    This makes CoDRAG available as a Paperclip skill.  Agents can then
    enable it via the Skills tab in their Paperclip configuration.

    Modes:
        symlink: (default) Symlinks to the CoDRAG repo source.
                 Best for development — stays in sync automatically.
        copy:    Copies files.  Best when the source tree may move.
    """
    from codrag.paperclip_skill import install_skill

    result = install_skill(mode=req.mode)
    return ok(result)


@router.post("/paperclip/uninstall-skill")
def paperclip_uninstall_skill() -> Dict[str, Any]:
    """Remove the CoDRAG skill from ~/.claude/skills/codrag."""
    from codrag.paperclip_skill import uninstall_skill

    result = uninstall_skill()
    return ok(result)


@router.get("/paperclip/skill-status")
def paperclip_skill_status() -> Dict[str, Any]:
    """Check if the CoDRAG Paperclip skill is installed.

    Returns installation status, path, and mode (symlink or copy).
    """
    from codrag.paperclip_skill import get_skill_status

    result = get_skill_status()
    result["daemon_url"] = _get_daemon_url()
    return ok(result)


# ── Helpers ─────────────────────────────────────────────────────────


def _get_daemon_url() -> str:
    """Get the daemon URL from the current server config."""
    return os.environ.get("CODRAG_DAEMON_URL", "http://127.0.0.1:8400")

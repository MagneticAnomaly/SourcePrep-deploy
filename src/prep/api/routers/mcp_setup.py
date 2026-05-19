"""MCP Configuration, Workspace Installation & Paperclip Skill API.

Provides endpoints for:
  - Generating MCP config snippets for various IDEs (copy-paste flow)
  - Installing/uninstalling Prep MCP configs into an arbitrary workspace
    directory (the "Enable Prep for Workspace" one-click action)
  - Installing/uninstalling the Prep Paperclip skill globally
  - Checking skill installation status
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


# ── Request Models ──────────────────────────────────────────────────


class SkillInstallRequest(BaseModel):
    """Request to install or uninstall the Prep Paperclip skill."""
    mode: str = "symlink"  # "symlink" or "copy"


class MCPInstallRequest(BaseModel):
    """Request to install MCP configs into a workspace."""
    workspace_path: str
    mode: str = "auto"
    project_id: Optional[str] = None
    runtimes: Optional[List[str]] = None


class MCPUninstallRequest(BaseModel):
    """Request to remove Prep from workspace MCP configs."""
    workspace_path: str
    runtimes: Optional[List[str]] = None


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
    from prep.mcp_config import generate_mcp_configs

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


# ── Workspace Installation ──────────────────────────────────────────


@router.post("/mcp/install")
def mcp_install(req: MCPInstallRequest) -> Dict[str, Any]:
    """Install Prep MCP configs into a workspace directory.

    This is the "Enable Prep for Workspace" one-click action.  Writes
    MCP config files for all supported runtimes (Claude Code, Cursor,
    VS Code, Windsurf) so any agent running in that workspace
    automatically discovers Prep tools.

    Merges with existing configs — does not clobber other MCP servers.
    """
    from prep.mcp_config import install_mcp_to_workspace

    daemon_url = _get_daemon_url()
    try:
        result = install_mcp_to_workspace(
            req.workspace_path,
            daemon_url=daemon_url,
            mode=req.mode,
            project_id=req.project_id,
            runtimes=req.runtimes,
        )
    except ValueError as exc:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=str(exc))
    return ok(result)


@router.post("/mcp/uninstall")
def mcp_uninstall(req: MCPUninstallRequest) -> Dict[str, Any]:
    """Remove Prep entries from workspace MCP configs.

    Does not delete the config files — only removes the ``prep`` key
    from each runtime's server list.
    """
    from prep.mcp_config import uninstall_mcp_from_workspace

    result = uninstall_mcp_from_workspace(
        req.workspace_path,
        runtimes=req.runtimes,
    )
    return ok(result)


@router.get("/mcp/status")
def mcp_status(workspace_path: Optional[str] = None) -> Dict[str, Any]:
    """Check MCP installation status for a workspace.

    If ``workspace_path`` is provided, checks which runtimes have Prep
    configs installed.  If omitted, returns current MCP server info
    (daemon URL, supported runtimes).
    """
    from prep.mcp_config import _WORKSPACE_TARGETS

    info: Dict[str, Any] = {
        "daemon_url": _get_daemon_url(),
        "mcp_command": "prep mcp",
        "supported_runtimes": list(_WORKSPACE_TARGETS.keys()),
    }

    if workspace_path:
        ws = Path(workspace_path).expanduser().resolve()
        installed: Dict[str, Any] = {}

        for runtime, (subdir, filename, merge_key) in _WORKSPACE_TARGETS.items():
            target_file = ws / subdir / filename
            status: Dict[str, Any] = {"installed": False, "file": str(target_file)}

            if target_file.exists():
                try:
                    data = json.loads(target_file.read_text(encoding="utf-8"))
                    servers = data.get(merge_key, {})
                    if isinstance(servers, dict) and "prep" in servers:
                        status["installed"] = True
                        status["config"] = servers["prep"]
                except (json.JSONDecodeError, OSError):
                    status["error"] = "Could not parse config file"

            installed[runtime] = status

        info["workspace"] = str(ws)
        info["runtimes"] = installed
        info["any_installed"] = any(r["installed"] for r in installed.values())

    return ok(info)


# ── Paperclip Skill Installation ────────────────────────────────────


@router.post("/paperclip/install-skill")
def paperclip_install_skill(req: SkillInstallRequest) -> Dict[str, Any]:
    """Install the Prep skill into ~/.claude/skills/prep.

    This makes Prep available as a Paperclip skill.  Agents can then
    enable it via the Skills tab in their Paperclip configuration.

    Modes:
        symlink: (default) Symlinks to the Prep repo source.
                 Best for development — stays in sync automatically.
        copy:    Copies files.  Best when the source tree may move.
    """
    from prep.paperclip_skill import install_skill

    result = install_skill(mode=req.mode)
    return ok(result)


@router.post("/paperclip/uninstall-skill")
def paperclip_uninstall_skill() -> Dict[str, Any]:
    """Remove the Prep skill from ~/.claude/skills/prep."""
    from prep.paperclip_skill import uninstall_skill

    result = uninstall_skill()
    return ok(result)


@router.get("/paperclip/skill-status")
def paperclip_skill_status() -> Dict[str, Any]:
    """Check if the Prep Paperclip skill is installed.

    Returns installation status, path, and mode (symlink or copy).
    """
    from prep.paperclip_skill import get_skill_status

    result = get_skill_status()
    result["daemon_url"] = _get_daemon_url()
    return ok(result)


# ── Helpers ─────────────────────────────────────────────────────────


def _get_daemon_url() -> str:
    """Get the daemon URL from the current server config."""
    return os.environ.get("PREP_DAEMON_URL", "http://127.0.0.1:8400")

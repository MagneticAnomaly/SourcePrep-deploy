"""MCP Configuration & Installation API.

Provides endpoints for generating MCP config snippets for various IDEs/runtimes,
installing CoDRAG MCP configs into workspaces (the "Enable CoDRAG for Workspace"
one-click action), and checking workspace installation status.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


# ── Request Models ──────────────────────────────────────────────────


class MCPConfigRequest(BaseModel):
    """Request to generate MCP config snippets."""
    ide: str = "all"
    mode: str = "auto"
    project_id: Optional[str] = None


class MCPInstallRequest(BaseModel):
    """Request to install MCP configs into a workspace."""
    workspace_path: str
    mode: str = "auto"
    project_id: Optional[str] = None
    runtimes: Optional[List[str]] = None


class MCPUninstallRequest(BaseModel):
    """Request to remove CoDRAG from workspace MCP configs."""
    workspace_path: str
    runtimes: Optional[List[str]] = None


# ── Config Generation ───────────────────────────────────────────────


@router.get("/mcp/config")
def mcp_config_get(
    ide: str = "all",
    mode: str = "auto",
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate MCP config snippets for the requested IDE(s).

    Returns ready-to-paste JSON for each supported runtime. Use this
    for the "copy to clipboard" flow in the dashboard.

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


# ── Workspace Installation ──────────────────────────────────────────


@router.post("/mcp/install")
def mcp_install(req: MCPInstallRequest) -> Dict[str, Any]:
    """Install CoDRAG MCP configs into a workspace directory.

    This is the "Enable CoDRAG for Workspace" one-click action.
    Writes MCP config files for all supported runtimes (Claude Code,
    Cursor, VS Code, Windsurf) so any agent running in that workspace
    automatically discovers CoDRAG tools.

    Merges with existing configs — won't clobber other MCP servers.
    """
    from codrag.mcp_config import install_mcp_to_workspace

    daemon_url = _get_daemon_url()
    result = install_mcp_to_workspace(
        req.workspace_path,
        daemon_url=daemon_url,
        mode=req.mode,
        project_id=req.project_id,
        runtimes=req.runtimes,
    )
    return ok(result)


@router.post("/mcp/uninstall")
def mcp_uninstall(req: MCPUninstallRequest) -> Dict[str, Any]:
    """Remove CoDRAG entries from workspace MCP configs.

    Does not delete the config files — only removes the "codrag"
    key from each runtime's server list.
    """
    from codrag.mcp_config import uninstall_mcp_from_workspace

    result = uninstall_mcp_from_workspace(
        req.workspace_path,
        runtimes=req.runtimes,
    )
    return ok(result)


# ── Workspace Status ────────────────────────────────────────────────


@router.get("/mcp/status")
def mcp_status(workspace_path: Optional[str] = None) -> Dict[str, Any]:
    """Check MCP installation status for a workspace.

    If workspace_path is provided, checks which runtimes have CoDRAG
    configs installed. If omitted, returns the current MCP server info.
    """
    from codrag.mcp_config import _WORKSPACE_TARGETS

    info: Dict[str, Any] = {
        "daemon_url": _get_daemon_url(),
        "mcp_command": "codrag mcp",
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
                    if isinstance(servers, dict) and "codrag" in servers:
                        status["installed"] = True
                        status["config"] = servers["codrag"]
                except (json.JSONDecodeError, OSError):
                    status["error"] = "Could not parse config file"

            installed[runtime] = status

        info["workspace"] = str(ws)
        info["runtimes"] = installed
        info["any_installed"] = any(
            r["installed"] for r in installed.values()
        )

    return ok(info)


# ── Helpers ─────────────────────────────────────────────────────────


def _get_daemon_url() -> str:
    """Get the daemon URL from the current server config."""
    import os
    # Prefer the environment variable, then fall back to default
    return os.environ.get("CODRAG_DAEMON_URL", "http://127.0.0.1:8400")

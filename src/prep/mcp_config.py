from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _detect_prep_command() -> str:
    """Resolve the absolute path of the ``prep`` CLI for IDE configs.

    Returns an absolute path when possible so generated configs work
    in spawn contexts (Claude Desktop, Cursor) that do not inherit the
    shell PATH. Falls back to the bare ``prep`` name only when no real
    binary can be located.

    Resolution order:
      1. ``shutil.which("prep")`` — picks up any globally-installed copy
         on PATH. Wins when the user has symlinked/installed ``prep``
         into ``/usr/local/bin`` or similar.
      2. The ``prep`` script next to ``sys.executable`` — when the
         daemon is itself running from a venv, the sibling script is
         the binary we are already using.
      3. Bare ``"prep"`` — last-resort fallback. Emits a warning so the
         miss is visible in logs.
    """
    on_path = shutil.which("prep")
    if on_path:
        return on_path

    venv_sibling = Path(sys.executable).resolve().parent / "prep"
    if venv_sibling.is_file():
        return str(venv_sibling)

    logger.warning(
        "prep binary not found via PATH or %s sibling; emitting bare 'prep' "
        "in generated MCP configs — Claude Desktop / Cursor may fail to spawn it",
        sys.executable,
    )
    return "prep"


def generate_mcp_configs(
    *,
    ide: str = "all",
    daemon_url: str = "http://127.0.0.1:8400",
    prep_command: Optional[str] = None,
    mode: str = "auto",
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    norm_mode = str(mode).strip().lower()
    if norm_mode in ("pinned", "project"):
        norm_mode = "project"
    if norm_mode not in ("auto", "project", "direct"):
        raise ValueError("mode must be 'auto', 'project', or 'direct'")
    if norm_mode == "project":
        if project_id is None or not str(project_id).strip():
            raise ValueError("project_id is required when mode='project'")

    prep_path = prep_command or _detect_prep_command()

    args = ["mcp"]
    if norm_mode == "direct":
        args.extend(["--mode", "direct"])
    elif norm_mode == "project":
        args.extend(["--project", str(project_id).strip(), "--daemon", daemon_url])
    else:
        # Auto/Server mode
        args.extend(["--auto", "--daemon", daemon_url])

    base_config: Dict[str, Any] = {
        "command": prep_path,
        "args": args,
    }

    configs: Dict[str, Any] = {}

    if ide in ("all", "claude-code"):
        configs["claude-code"] = {
            "file": ".claude/mcp.json",
            "path_hint": "Project root (project-scoped) or ~/.claude/ (global)",
            "config": {"servers": {"prep": base_config}},
        }

    if ide in ("all", "claude", "claude-desktop"):
        configs["claude"] = {
            "file": "claude_desktop_config.json",
            "path_hint": "~/Library/Application Support/Claude/ (macOS) or %APPDATA%/Claude/ (Windows)",
            "config": {"mcpServers": {"prep": base_config}},
        }

    if ide in ("all", "cursor"):
        configs["cursor"] = {
            "file": ".cursor/mcp.json",
            "path_hint": "Project root or ~/.cursor/",
            "config": {"mcpServers": {"prep": base_config}},
        }

    if ide in ("all", "vscode"):
        configs["vscode"] = {
            "file": ".vscode/mcp.json",
            "path_hint": "Project root",
            "config": {"servers": {"prep": base_config}},
        }

    if ide in ("all", "jetbrains"):
        configs["jetbrains"] = {
            "file": "AI Assistant > MCP Servers (Settings)",
            "path_hint": "Add via IDE Settings > Tools > AI Assistant > MCP Servers",
            "config": {
                "servers": [
                    {
                        "name": "prep",
                        "command": prep_path,
                        "args": args,
                    }
                ]
            },
        }

    if ide in ("all", "windsurf"):
        configs["windsurf"] = {
            "file": ".windsurf/mcp.json",
            "path_hint": "Project root",
            "config": {"mcpServers": {"prep": base_config}},
        }

    if ide in ("all", "gemini"):
        configs["gemini"] = {
            "file": "settings.json",
            "path_hint": "~/.gemini/",
            "config": {"mcpServers": {"prep": {**base_config, "trust": True}}},
        }

    if ide in ("all", "antigravity"):
        configs["antigravity"] = {
            "file": "mcp_config.json",
            "path_hint": "~/.gemini/antigravity/",
            "config": {"mcpServers": {"prep": base_config}},
        }

    if ide in ("all", "zed"):
        configs["zed"] = {
            "file": "settings.json",
            "path_hint": "~/.config/zed/ or project .zed/",
            "config": {"context_servers": {"prep": base_config}},
        }

    if not configs:
        raise ValueError(f"Unknown IDE: {ide}")

    return configs

    return {
        "workspace": str(ws),
        "removed": removed,
        "skipped": skipped,
    }

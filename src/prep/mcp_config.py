from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# ── Workspace Installer ──────────────────────────────────────────────


# Which config files can be safely auto-written into a workspace directory.
# Maps runtime name → (subdirectory, filename, config key path for merging).
_WORKSPACE_TARGETS = {
    "claude-code": (".claude", "mcp.json", "servers"),
    "cursor": (".cursor", "mcp.json", "mcpServers"),
    "vscode": (".vscode", "mcp.json", "servers"),
    "windsurf": (".windsurf", "mcp.json", "mcpServers"),
}


def install_mcp_to_workspace(
    workspace_path: str | Path,
    *,
    daemon_url: str = "http://127.0.0.1:8400",
    prep_command: Optional[str] = None,
    mode: str = "auto",
    project_id: Optional[str] = None,
    runtimes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Write MCP config files into a workspace so all agent runtimes
    running there automatically discover Prep tools.

    This is the "Enable Prep for Workspace" one-click action.

    Args:
        workspace_path: Absolute path to the project workspace (where
            Paperclip agents' ``cwd`` is set).
        daemon_url: Prep daemon base URL.
        prep_command: Override ``prep`` binary path.
        mode: MCP mode (auto, project, direct).
        project_id: Required when mode='project'.
        runtimes: Which runtimes to write configs for.
            Default writes all: claude-code, cursor, vscode, windsurf.

    Returns:
        Dict with ``written`` (list of written file paths),
        ``skipped`` (list of skipped targets with reason),
        and ``workspace`` (resolved workspace path).
    """
    ws = Path(workspace_path).expanduser().resolve()
    if not ws.is_dir():
        raise ValueError(f"Workspace path does not exist or is not a directory: {ws}")

    # Generate raw configs
    all_configs = generate_mcp_configs(
        ide="all",
        daemon_url=daemon_url,
        prep_command=prep_command,
        mode=mode,
        project_id=project_id,
    )

    targets = runtimes or list(_WORKSPACE_TARGETS.keys())
    written: List[str] = []
    skipped: List[Dict[str, str]] = []

    for runtime in targets:
        if runtime not in _WORKSPACE_TARGETS:
            skipped.append({"runtime": runtime, "reason": f"Unknown runtime: {runtime}"})
            continue

        subdir, filename, merge_key = _WORKSPACE_TARGETS[runtime]
        config_data = all_configs.get(runtime, {}).get("config", {})
        if not config_data:
            skipped.append({"runtime": runtime, "reason": "No config generated"})
            continue

        target_dir = ws / subdir
        target_file = target_dir / filename

        # Merge with existing file if present (don't clobber other MCP servers)
        existing: Dict[str, Any] = {}
        if target_file.exists():
            try:
                existing = json.loads(target_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}

        # Deep merge: add our "prep" key under the merge_key without removing
        # any other servers the user may have configured.
        if merge_key in config_data:
            if merge_key not in existing:
                existing[merge_key] = {}
            if isinstance(existing[merge_key], dict) and isinstance(config_data[merge_key], dict):
                existing[merge_key].update(config_data[merge_key])
            else:
                existing[merge_key] = config_data[merge_key]
        else:
            existing.update(config_data)

        # Write
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file.write_text(
                json.dumps(existing, indent=2) + "\n",
                encoding="utf-8",
            )
            written.append(str(target_file))
            logger.info("Wrote MCP config for %s: %s", runtime, target_file)
        except OSError as exc:
            skipped.append({"runtime": runtime, "reason": f"Write failed: {exc}"})

    # Claude Code: also write settings.json with auto-approve
    if "claude-code" in targets:
        settings_path = _ensure_claude_settings(ws)
        if settings_path:
            written.append(settings_path)

    return {
        "workspace": str(ws),
        "written": written,
        "skipped": skipped,
        "runtimes_installed": len(written),
    }


def _ensure_claude_settings(workspace_path: Path) -> Optional[str]:
    """Ensure .claude/settings.json has mcp__prep auto-approve.

    Merges into existing file if present. Returns the file path if
    written, None if skipped (already configured).
    """
    settings_dir = workspace_path / ".claude"
    settings_file = settings_dir / "settings.json"

    existing: Dict[str, Any] = {}
    if settings_file.exists():
        try:
            existing = json.loads(settings_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    perms = existing.setdefault("permissions", {})
    allow_list = perms.setdefault("allow", [])

    if "mcp__prep" in allow_list:
        return None  # Already configured

    allow_list.append("mcp__prep")

    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(existing, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote Claude Code auto-approve: %s", settings_file)
    return str(settings_file)


def uninstall_mcp_from_workspace(
    workspace_path: str | Path,
    *,
    runtimes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Remove Prep entries from MCP config files in a workspace.

    Does not delete the files — only removes the ``prep`` key from
    each config's server list.
    """
    ws = Path(workspace_path).expanduser().resolve()
    targets = runtimes or list(_WORKSPACE_TARGETS.keys())
    removed: List[str] = []
    skipped: List[Dict[str, str]] = []

    for runtime in targets:
        if runtime not in _WORKSPACE_TARGETS:
            continue

        subdir, filename, merge_key = _WORKSPACE_TARGETS[runtime]
        target_file = ws / subdir / filename

        if not target_file.exists():
            skipped.append({"runtime": runtime, "reason": "Config file not found"})
            continue

        try:
            data = json.loads(target_file.read_text(encoding="utf-8"))
            if merge_key in data and isinstance(data[merge_key], dict):
                if "prep" in data[merge_key]:
                    del data[merge_key]["prep"]
                    target_file.write_text(
                        json.dumps(data, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    removed.append(str(target_file))
                    logger.info("Removed Prep from %s: %s", runtime, target_file)
                else:
                    skipped.append({"runtime": runtime, "reason": "Prep not found in config"})
            else:
                skipped.append({"runtime": runtime, "reason": "Prep not found in config"})
        except (json.JSONDecodeError, OSError) as exc:
            skipped.append({"runtime": runtime, "reason": str(exc)})

    return {
        "workspace": str(ws),
        "removed": removed,
        "skipped": skipped,
    }

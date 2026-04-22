"""
Paperclip Skill installer for SourcePrep.

Installs the SourcePrep skill into ``~/.claude/skills/prep`` so that
Paperclip agents can discover and use SourcePrep's MCP tools.  The skill
directory shipped with SourcePrep lives at ``packages/paperclip-skill/``
and is symlinked into the global skills home.

Two installation modes:
  1. **Symlink** (default): Creates a symlink from the global skills
     directory to the SourcePrep source tree.  Best for development — the
     skill stays in sync with the repo.
  2. **Copy**: Copies the skill files into the global skills directory.
     Best for distribution when the SourcePrep source tree may not be
     available.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────

# Where the skill source lives in the SourcePrep repo
_SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent / "packages" / "paperclip-skill"

# Default global skills home (Claude / OpenCode convention)
_DEFAULT_SKILLS_HOME = Path.home() / ".claude" / "skills"

SKILL_NAME = "prep"


# ── Public API ───────────────────────────────────────────────────────


def install_skill(
    *,
    skills_home: Optional[Path] = None,
    mode: str = "symlink",
    source_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Install the SourcePrep skill into the global skills directory.

    Args:
        skills_home: Override the global skills directory.
            Default: ``~/.claude/skills``.
        mode: ``"symlink"`` (default) or ``"copy"``.
        source_dir: Override the skill source directory.
            Default: ``packages/paperclip-skill/`` relative to the repo.

    Returns:
        Dict with ``installed`` (bool), ``path`` (str), ``mode`` (str),
        and ``message`` (str).
    """
    home = (skills_home or _DEFAULT_SKILLS_HOME).expanduser().resolve()
    source = (source_dir or _SKILL_SOURCE_DIR).expanduser().resolve()
    target = home / SKILL_NAME

    # Validate source
    skill_md = source / "SKILL.md"
    if not skill_md.is_file():
        return {
            "installed": False,
            "path": str(target),
            "mode": mode,
            "message": f"Skill source not found: {skill_md}",
        }

    # Create skills home if it doesn't exist
    home.mkdir(parents=True, exist_ok=True)

    # Remove existing link/directory (idempotent reinstall)
    if target.is_symlink():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)

    if mode == "symlink":
        try:
            target.symlink_to(source)
            logger.info("Symlinked SourcePrep skill: %s → %s", target, source)
        except OSError as exc:
            return {
                "installed": False,
                "path": str(target),
                "mode": mode,
                "message": f"Symlink failed: {exc}",
            }
    elif mode == "copy":
        try:
            shutil.copytree(source, target)
            logger.info("Copied SourcePrep skill to %s", target)
        except OSError as exc:
            return {
                "installed": False,
                "path": str(target),
                "mode": mode,
                "message": f"Copy failed: {exc}",
            }
    else:
        return {
            "installed": False,
            "path": str(target),
            "mode": mode,
            "message": f"Unknown mode: {mode}",
        }

    return {
        "installed": True,
        "path": str(target),
        "mode": mode,
        "message": "SourcePrep skill installed. Agents can now enable it in Paperclip.",
    }


def uninstall_skill(
    *,
    skills_home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Remove the SourcePrep skill from the global skills directory."""
    home = (skills_home or _DEFAULT_SKILLS_HOME).expanduser().resolve()
    target = home / SKILL_NAME

    if target.is_symlink():
        target.unlink()
        return {"removed": True, "path": str(target)}
    elif target.is_dir():
        shutil.rmtree(target)
        return {"removed": True, "path": str(target)}
    else:
        return {"removed": False, "path": str(target), "message": "Not installed"}


def get_skill_status(
    *,
    skills_home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Check if the SourcePrep skill is installed in the global skills directory."""
    home = (skills_home or _DEFAULT_SKILLS_HOME).expanduser().resolve()
    target = home / SKILL_NAME
    skill_md = target / "SKILL.md"

    installed = skill_md.is_file() or (target.is_symlink() and (target / "SKILL.md").exists())

    result: Dict[str, Any] = {
        "installed": installed,
        "path": str(target),
        "skills_home": str(home),
    }

    if installed:
        # Check if it's a symlink (dev mode) or copy
        if target.is_symlink():
            result["mode"] = "symlink"
            result["source"] = str(os.readlink(target))
        else:
            result["mode"] = "copy"

    return result

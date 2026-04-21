"""
AGENTS.md auto-writer for Prep — Phase 63 (Headless Mode).

Writes the current opportunity findings into the project's
.agents/AGENTS.md file so any AI agent that reads project files
(Claude Code, Cursor, Antigravity, etc.) automatically gets
Prep's latest intelligence without configuration.

This is the "zero-config" integration path:
  1. Prep discovers opportunities via Health Scanner + Spaghetti
  2. This writer serializes top findings into AGENTS.md
  3. Any agent opening the project reads AGENTS.md automatically

The AGENTS.md convention is widely adopted (Cursor, Claude Code,
Windsurf, etc.) so this works with any tool that reads project
context files.
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from prep.core.audit.action_item import ActionItem

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# Markers for the Prep-managed section
_SECTION_START = "<!-- prep-opportunities-start -->"
_SECTION_END = "<!-- prep-opportunities-end -->"

# Max items to include in AGENTS.md (keep it focused)
_MAX_ITEMS = 15


# ── Writer ───────────────────────────────────────────────────────────

def write_agents_md(
    project_root: Path,
    items: List[ActionItem],
    max_items: int = _MAX_ITEMS,
) -> Optional[Path]:
    """Write or update the Prep section in .agents/AGENTS.md.

    If AGENTS.md already exists, only the Prep-managed section
    (between the start/end markers) is updated. Other content is
    preserved. If AGENTS.md doesn't exist, a new one is created.

    Args:
        project_root: Path to the project root directory.
        items: Active opportunities to include.
        max_items: Maximum number of items to write.

    Returns:
        Path to the written AGENTS.md, or None on failure.
    """
    agents_dir = project_root / ".agents"
    agents_path = agents_dir / "AGENTS.md"

    # Filter to active only, sorted by priority
    active = [i for i in items if i.state != "dismissed"]
    active.sort(key=lambda i: (
        {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(i.priority, 9),
        {"critical": 0, "warning": 1, "info": 2, "suggestion": 3}.get(i.severity, 9),
    ))
    active = active[:max_items]

    # Build the Prep section content
    section = _build_section(active)

    try:
        agents_dir.mkdir(parents=True, exist_ok=True)

        if agents_path.exists():
            # Update existing file — splice in the Prep section
            existing = agents_path.read_text(encoding="utf-8")
            new_content = _splice_section(existing, section)
        else:
            # Create new file with the section
            new_content = section

        _atomic_write(agents_path, new_content)
        logger.info(
            "Updated AGENTS.md: %d opportunities written to %s",
            len(active), agents_path,
        )
        return agents_path

    except Exception as e:
        logger.warning("Failed to write AGENTS.md: %s", e)
        return None


def _build_section(items: List[ActionItem]) -> str:
    """Build the Markdown content for the Prep-managed section."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        _SECTION_START,
        "## Prep Codebase Intelligence",
        "",
        f"*Auto-generated at {now} — {len(items)} active opportunity findings.*",
        "",
    ]

    if not items:
        lines.append("No active opportunities. Run `prep opportunities --refresh` to scan.")
        lines.append("")
        lines.append(_SECTION_END)
        return "\n".join(lines)

    # Group by priority
    current_prio = None
    for item in items:
        if item.priority != current_prio:
            current_prio = item.priority
            prio_labels = {
                "P0": "### 🔴 Critical (P0)",
                "P1": "### 🟡 Warning (P1)",
                "P2": "### 🔵 Info (P2)",
                "P3": "### ⚪ Suggestion (P3)",
            }
            lines.append(prio_labels.get(current_prio, f"### {current_prio}"))
            lines.append("")

        # Item entry
        files_str = f" ({len(item.affected_files)} files)" if item.affected_files else ""
        lines.append(f"- **{item.id}**: {item.title}{files_str} [{item.effort}]")
        if item.suggested_action:
            lines.append(f"  - {item.suggested_action}")

    lines.append("")
    lines.append(
        "*Address these with:* `prep opportunities --format ai_prompt` "
        "*or use the MCP tool:* `prep_audit`"
    )
    lines.append("")
    lines.append(_SECTION_END)

    return "\n".join(lines)


def _splice_section(existing: str, section: str) -> str:
    """Replace the Prep-managed section in existing content.

    If the markers aren't found, append the section at the end.
    """
    start_idx = existing.find(_SECTION_START)
    end_idx = existing.find(_SECTION_END)

    if start_idx != -1 and end_idx != -1:
        # Replace between markers (inclusive of markers)
        end_idx += len(_SECTION_END)
        return existing[:start_idx] + section + existing[end_idx:]
    else:
        # Append at the end
        separator = "\n\n" if existing and not existing.endswith("\n\n") else "\n" if existing and not existing.endswith("\n") else ""
        return existing + separator + section + "\n"


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically via temp file + rename."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", dir=str(path.parent),
        delete=False, encoding="utf-8",
    )
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

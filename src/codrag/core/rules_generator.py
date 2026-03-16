"""
Rules file generator for AI coding tools (Cursor, Windsurf, Claude Code).

Generates project-level instruction files that tell AI assistants to use
CoDRAG's MCP tools for structural codebase context. Embeds the atlas
(when available) for always-on priming.

Phase 50: MCP Interfacing.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Markers for managed sections ────────────────────────────────────
# Used to identify CoDRAG-managed content in rules files that may also
# contain user-written rules. Everything between START and END markers
# is replaced on regeneration; content outside is preserved.

_CURSOR_MARKER_START = "# --- CoDRAG-managed (auto-generated, do not edit above USER ADDITIONS) ---"
_CURSOR_MARKER_END = "# --- USER ADDITIONS BELOW (preserved across updates) ---"

_MANAGED_MARKER_START = "<!-- codrag-managed-start -->"
_MANAGED_MARKER_END = "<!-- codrag-managed-end -->"

# Backward compat aliases (used in detection of existing markers)
_WINDSURF_MARKER_START = _MANAGED_MARKER_START
_WINDSURF_MARKER_END = _MANAGED_MARKER_END
_CLAUDE_MARKER_START = _MANAGED_MARKER_START
_CLAUDE_MARKER_END = _MANAGED_MARKER_END

# Debounce timer for rules file regeneration triggered by included_paths changes
_regen_timers: Dict[str, threading.Timer] = {}
_REGEN_DEBOUNCE_S = 2.0


# ── Public API ──────────────────────────────────────────────────────


def write_rules_file(
    project_path: Path,
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
    ide: str = "auto",
) -> Dict[str, bool]:
    """Write rules files for detected IDEs.

    Generates rules for all detected IDEs (or the specified one).
    Preserves user content outside of CoDRAG-managed markers.

    Args:
        project_path: Root path of the project.
        project_name: Human-readable project name.
        atlas_content: Atlas text to embed. Empty string = no atlas section.
        included_paths: User-selected focus areas from the dashboard.
        is_preliminary: If True, adds "Full analysis in progress" note.
        stats: Optional dict with node_count, edge_count, coverage_pct, last_indexed.
        ide: "auto" (detect all), "cursor", "windsurf", "claude", or "all".

    Returns:
        Dict mapping IDE name to whether the file was written.
    """
    project_path = Path(project_path)
    results: Dict[str, bool] = {}

    targets = _detect_targets(project_path, ide)

    _args = (project_path, project_name, atlas_content,
             included_paths, is_preliminary, stats)

    _writers = {
        "agents_md": _write_agents_md,
        "cursor": _write_cursor_rules,
        "windsurf": _write_windsurf_rules,
        "claude": _write_claude_rules,
        "gemini": _write_generic_md,     # GEMINI.md
        "copilot": _write_copilot_rules,  # .github/copilot-instructions.md
        "cline": _write_cline_rules,      # .clinerules
        "roo_code": _write_roo_rules,     # .roo/rules/codrag.md
    }

    for target_ide in targets:
        writer = _writers.get(target_ide)
        if not writer:
            continue
        try:
            if target_ide == "gemini":
                results["gemini"] = writer(
                    project_path, project_name, atlas_content,
                    included_paths, is_preliminary, stats,
                    filename="GEMINI.md", heading="# CoDRAG Integration",
                )
            else:
                results[target_ide] = writer(*_args)
        except Exception as e:
            logger.warning("Failed to write %s rules: %s", target_ide, e)
            results[target_ide] = False

    written = [k for k, v in results.items() if v]
    if written:
        logger.info("Rules files written for %s: %s", project_name, ", ".join(written))

    return results


def detect_and_regenerate(
    project_id: str,
    project_path: Path,
    project_name: str,
    force: bool = False,
) -> Dict[str, bool]:
    """Detect new AI tools and regenerate missing rules files.

    Cheap (~1ms for detection, ~5ms for file writes). Call at:
    - Pipeline start (fast_sync or deep_enrichment)
    - Stale file rebuild
    - Project config change (included_paths, exclude patterns)
    - MCP server initialize (new IDE session detected)
    - Dashboard "Generate Rules" button

    Skips regeneration if all detected files already exist and haven't
    changed since last write, unless force=True.

    Returns dict of {tool_name: was_written} for any files that were
    created or updated.
    """
    project_path = Path(project_path)
    targets = _detect_targets(project_path, "auto")

    # Check which targets already have CoDRAG content
    _target_paths = {
        "agents_md": project_path / "AGENTS.md",
        "cursor": project_path / ".cursor" / "rules" / "codrag.mdc",
        "windsurf": project_path / ".windsurf" / "rules" / "codrag.md",
        "claude": project_path / "CLAUDE.md",
        "gemini": project_path / "GEMINI.md",
        "copilot": project_path / ".github" / "copilot-instructions.md",
        "cline": project_path / ".clinerules",
        "roo_code": project_path / ".roo" / "rules" / "codrag.md",
    }

    if not force:
        # Only regenerate targets that are missing CoDRAG content
        needs_write: List[str] = []
        for target in targets:
            path = _target_paths.get(target)
            if path is None:
                needs_write.append(target)
                continue
            if not path.exists():
                needs_write.append(target)
                continue
            # File exists -- check if it has our markers
            try:
                content = path.read_text(encoding="utf-8")
                if _CLAUDE_MARKER_START not in content and _CURSOR_MARKER_START not in content:
                    needs_write.append(target)
            except Exception:
                needs_write.append(target)

        if not needs_write:
            return {}  # Everything up to date
        # Only write the missing ones
        targets = needs_write

    # Load current atlas and project config for regeneration
    atlas_content = _get_current_atlas_content(project_id)
    included_paths = _get_current_included_paths(project_id)
    stats = _get_current_stats(project_id)

    results: Dict[str, bool] = {}
    for target in targets:
        try:
            # Write just this one target
            sub_results = write_rules_file(
                project_path=project_path,
                project_name=project_name,
                atlas_content=atlas_content,
                included_paths=included_paths,
                stats=stats,
                ide=target,
            )
            results.update(sub_results)
        except Exception as e:
            logger.debug("detect_and_regenerate: failed for %s: %s", target, e)
            results[target] = False

    if results:
        written = [k for k, v in results.items() if v]
        if written:
            logger.info(
                "detect_and_regenerate: wrote %d rules files for %s: %s",
                len(written), project_name, ", ".join(written),
            )

    return results


def _get_current_atlas_content(project_id: str) -> str:
    """Load the current atlas text from disk. Returns empty string if unavailable."""
    try:
        from codrag.services.project_helpers import require_project
        from codrag.core.project_registry import project_index_dir
        from pathlib import Path as _Path
        import json as _json

        project = require_project(project_id)
        idx_dir = _Path(project_index_dir(project))
        atlas_path = idx_dir / "atlas.json"
        if atlas_path.exists():
            with open(atlas_path, "r", encoding="utf-8") as f:
                doc = _json.load(f)
            return doc.get("content", "")
    except Exception:
        pass
    return ""


def _get_current_included_paths(project_id: str) -> Optional[List[str]]:
    """Load current included_paths from project config."""
    try:
        from codrag.services.project_helpers import require_project
        project = require_project(project_id)
        paths = (project.config or {}).get("included_paths") or []
        return paths if paths else None
    except Exception:
        return None


def _get_current_stats(project_id: str) -> Optional[Dict[str, Any]]:
    """Load current graph stats from trace manifest."""
    try:
        from codrag.services.project_helpers import require_project
        from codrag.core.project_registry import project_index_dir
        from pathlib import Path as _Path
        import json as _json

        project = require_project(project_id)
        idx_dir = _Path(project_index_dir(project))
        manifest_path = idx_dir / "trace_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = _json.load(f)
            counts = manifest.get("counts", {})
            return {
                "node_count": counts.get("nodes_total", 0) or counts.get("files_parsed", 0),
                "edge_count": counts.get("edges_total", 0),
                "coverage_pct": None,
            }
    except Exception:
        pass
    return None


def schedule_rules_regeneration(
    project_id: str,
    project_path: Path,
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> None:
    """Schedule a debounced rules file regeneration.

    Called when included_paths or other config changes. Debounces to
    avoid thrashing the IDE's rules file reload during rapid edits.
    """
    global _regen_timers

    # Cancel any pending timer for this project
    existing = _regen_timers.get(project_id)
    if existing is not None:
        existing.cancel()

    def _do_regen() -> None:
        _regen_timers.pop(project_id, None)
        write_rules_file(
            project_path=project_path,
            project_name=project_name,
            atlas_content=atlas_content,
            included_paths=included_paths,
            is_preliminary=False,
            stats=stats,
            ide="auto",
        )

    timer = threading.Timer(_REGEN_DEBOUNCE_S, _do_regen)
    timer.daemon = True
    _regen_timers[project_id] = timer
    timer.start()


# ── Content Generation ──────────────────────────────────────────────


def _build_managed_content(
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> str:
    """Build the CoDRAG-managed content block shared across all IDEs."""
    parts: List[str] = []

    # Header with freshness info
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stat_parts = [f"Last updated: {now}"]
    if stats:
        if stats.get("node_count"):
            stat_parts.append(f"{stats['node_count']} nodes")
        if stats.get("edge_count"):
            stat_parts.append(f"{stats['edge_count']} edges")
        if stats.get("coverage_pct") is not None:
            stat_parts.append(f"{stats['coverage_pct']}% coverage")
    if is_preliminary:
        stat_parts.append("Full analysis in progress")
    parts.append(" | ".join(stat_parts))
    parts.append("")

    # Tool instructions
    parts.append(
        "You have access to CoDRAG, a structural code intelligence system.\n"
        "ALWAYS call `codrag` (no arguments) at the START of every task.\n"
        "This gives you module structure, hub files, and the user's selected focus areas."
    )
    parts.append("")
    parts.append(
        "For specific code lookups, use `codrag_search` with a natural language query.\n"
        "Before making changes to a file, use `codrag_impact` to understand dependencies.\n"
        "CoDRAG understands structural relationships between files -- use it instead of\n"
        "grep when you need to understand how files connect to each other."
    )
    parts.append("")
    parts.append(
        "For codebase health and tech debt, use `codrag_audit`.\n"
        "For cross-session memory, use `codrag_observe` to save/retrieve notes.\n"
        "All CoDRAG tools are read-only and safe to auto-approve."
    )

    # Atlas section (if available)
    if atlas_content and atlas_content.strip():
        parts.append("")
        parts.append("## Codebase Atlas")
        parts.append("")
        parts.append(atlas_content.strip())

    # Focus areas (pointers only, not file content)
    if included_paths:
        parts.append("")
        parts.append("## Focus Areas")
        for p in included_paths[:15]:
            parts.append(f"- {p}")
        if len(included_paths) > 15:
            parts.append(f"- ... +{len(included_paths) - 15} more")
        parts.append("Call `codrag` for detailed content from these areas.")

    # Stale index / first-run fallback
    parts.append("")
    parts.append(
        "If `codrag` returns 'setup in progress', the index hasn't been built yet.\n"
        "Work normally with read_file/grep_search until the user builds the index."
    )

    # Long-task refresh hint
    parts.append("")
    parts.append(
        "For long tasks (5+ tool calls), call `codrag` again to refresh your\n"
        "structural context."
    )

    return "\n".join(parts)


# ── Cursor (.cursor/rules/codrag.mdc) ──────────────────────────────


def generate_cursor_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate .cursor/rules/codrag.mdc content with YAML frontmatter."""
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )

    return (
        "---\n"
        "description: CoDRAG structural codebase intelligence\n"
        "alwaysApply: true\n"
        "---\n"
        "\n"
        f"{_CURSOR_MARKER_START}\n"
        "\n"
        f"{managed}\n"
        "\n"
        f"{_CURSOR_MARKER_END}\n"
    )


def _write_cursor_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write or update .cursor/rules/codrag.mdc."""
    rules_dir = project_path / ".cursor" / "rules"
    target = rules_dir / "codrag.mdc"

    new_content = generate_cursor_rules(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        # Preserve user content below the end marker
        if _CURSOR_MARKER_END in existing:
            user_section = existing[existing.index(_CURSOR_MARKER_END) + len(_CURSOR_MARKER_END):]
            # Replace managed section, keep user section
            new_content = new_content.rstrip("\n") + user_section
        elif _CURSOR_MARKER_START not in existing:
            # File exists but has no CoDRAG markers -- user created it manually.
            # Don't overwrite. Append our content at the end.
            logger.info("Existing codrag.mdc without markers -- appending CoDRAG section")
            new_content = existing.rstrip("\n") + "\n\n" + new_content

    rules_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    return True


# ── Windsurf (.windsurf/rules/codrag.md) ────────────────────────────
# NOTE: Windsurf moved from .windsurfrules to .windsurf/rules/*.md
# with YAML frontmatter (trigger: always_on). We write to the new
# path but also check for legacy .windsurfrules.


def generate_windsurf_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate .windsurf/rules/codrag.md content with YAML frontmatter."""
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )

    return (
        "---\n"
        "trigger: always_on\n"
        "description: CoDRAG structural codebase intelligence\n"
        "---\n"
        "\n"
        f"{_WINDSURF_MARKER_START}\n"
        f"## CoDRAG Structural Context\n"
        "\n"
        f"{managed}\n"
        f"{_WINDSURF_MARKER_END}"
    )


def _write_windsurf_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write .windsurf/rules/codrag.md (new path) or update legacy .windsurfrules."""
    new_content = generate_windsurf_rules(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )

    # Prefer new path: .windsurf/rules/codrag.md
    new_dir = project_path / ".windsurf" / "rules"
    new_target = new_dir / "codrag.md"
    legacy_target = project_path / ".windsurfrules"

    if new_dir.exists() or (project_path / ".windsurf").exists():
        # Write to new path
        new_dir.mkdir(parents=True, exist_ok=True)
        new_target.write_text(new_content + "\n", encoding="utf-8")
        return True

    # Fallback: legacy .windsurfrules (marker-based append)
    if legacy_target.exists():
        existing = legacy_target.read_text(encoding="utf-8")
        if _WINDSURF_MARKER_START in existing:
            before = existing[:existing.index(_WINDSURF_MARKER_START)]
            end_idx = existing.find(_WINDSURF_MARKER_END)
            after = existing[end_idx + len(_WINDSURF_MARKER_END):] if end_idx >= 0 else ""
            legacy_target.write_text(
                before.rstrip("\n") + "\n\n" + new_content + after,
                encoding="utf-8",
            )
        else:
            legacy_target.write_text(
                existing.rstrip("\n") + "\n\n" + new_content + "\n",
                encoding="utf-8",
            )
        return True

    # No Windsurf directory found -- create new path
    new_dir.mkdir(parents=True, exist_ok=True)
    new_target.write_text(new_content + "\n", encoding="utf-8")
    return True


# ── Claude Code (CLAUDE.md) ────────────────────────────────────────


def generate_claude_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate CoDRAG section for CLAUDE.md."""
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )

    return (
        f"{_CLAUDE_MARKER_START}\n"
        f"# CoDRAG Integration\n"
        "\n"
        f"{managed}\n"
        f"{_CLAUDE_MARKER_END}"
    )


def _write_claude_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write or update CLAUDE.md with marker-based section management."""
    target = project_path / "CLAUDE.md"

    new_section = generate_claude_rules(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            # Replace existing CoDRAG section
            before = existing[:existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END):] if end_idx >= 0 else ""
            target.write_text(
                before.rstrip("\n") + "\n\n" + new_section + after,
                encoding="utf-8",
            )
        else:
            # No CoDRAG section yet -- append
            target.write_text(
                existing.rstrip("\n") + "\n\n" + new_section + "\n",
                encoding="utf-8",
            )
    else:
        target.write_text(new_section + "\n", encoding="utf-8")

    return True


# ── AGENTS.md (universal -- 22+ tools) ──────────────────────────────


def _write_agents_md(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write or update AGENTS.md with CoDRAG section.

    AGENTS.md is the universal standard read by 22+ tools (Cursor, Windsurf,
    Copilot, Claude Code, Gemini CLI, Roo Code, Zed, Aider, Amp, etc.).
    Stewarded by the Agentic AI Foundation under the Linux Foundation.
    """
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n"
        f"## CoDRAG Integration\n"
        "\n"
        f"{managed}\n"
        f"{_CLAUDE_MARKER_END}"
    )

    target = project_path / "AGENTS.md"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[:existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END):] if end_idx >= 0 else ""
            target.write_text(
                before.rstrip("\n") + "\n\n" + new_section + after,
                encoding="utf-8",
            )
        else:
            target.write_text(
                existing.rstrip("\n") + "\n\n" + new_section + "\n",
                encoding="utf-8",
            )
    else:
        target.write_text(new_section + "\n", encoding="utf-8")
    return True


# ── Generic markdown file (GEMINI.md, etc.) ─────────────────────────


def _write_generic_md(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    filename: str = "GEMINI.md",
    heading: str = "# CoDRAG Integration",
) -> bool:
    """Write or update a generic markdown file with CoDRAG section.

    Used for GEMINI.md and similar files that use marker-based sections.
    """
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n"
        f"{heading}\n"
        "\n"
        f"{managed}\n"
        f"{_CLAUDE_MARKER_END}"
    )

    target = project_path / filename
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[:existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END):] if end_idx >= 0 else ""
            target.write_text(
                before.rstrip("\n") + "\n\n" + new_section + after,
                encoding="utf-8",
            )
        else:
            target.write_text(
                existing.rstrip("\n") + "\n\n" + new_section + "\n",
                encoding="utf-8",
            )
    else:
        target.write_text(new_section + "\n", encoding="utf-8")
    return True


# ── GitHub Copilot (.github/copilot-instructions.md) ────────────────


def _write_copilot_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write or update .github/copilot-instructions.md with CoDRAG section."""
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n"
        f"## CoDRAG Integration\n"
        "\n"
        f"{managed}\n"
        f"{_CLAUDE_MARKER_END}"
    )

    github_dir = project_path / ".github"
    target = github_dir / "copilot-instructions.md"

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[:existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END):] if end_idx >= 0 else ""
            target.write_text(
                before.rstrip("\n") + "\n\n" + new_section + after,
                encoding="utf-8",
            )
        else:
            target.write_text(
                existing.rstrip("\n") + "\n\n" + new_section + "\n",
                encoding="utf-8",
            )
    else:
        github_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(new_section + "\n", encoding="utf-8")
    return True


# ── Cline (.clinerules) ──────────────────────────────────────────────


def _write_cline_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write or update .clinerules with CoDRAG keyword triggers.

    Cline uses keyword-based MCP activation: when the AI sees keywords
    matching a .clinerules entry, it activates the corresponding MCP server.
    """
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )
    # Cline-specific: keyword triggers at the top for MCP activation
    trigger_block = (
        "When asked about code structure, architecture, dependencies, modules, "
        "hub files, blast radius, impact analysis, or codebase navigation, "
        "use the CoDRAG MCP tools.\n\n"
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n"
        f"## CoDRAG Integration\n\n"
        f"{trigger_block}"
        f"{managed}\n"
        f"{_CLAUDE_MARKER_END}"
    )

    target = project_path / ".clinerules"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[:existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END):] if end_idx >= 0 else ""
            target.write_text(
                before.rstrip("\n") + "\n\n" + new_section + after,
                encoding="utf-8",
            )
        else:
            target.write_text(
                existing.rstrip("\n") + "\n\n" + new_section + "\n",
                encoding="utf-8",
            )
    else:
        target.write_text(new_section + "\n", encoding="utf-8")
    return True


# ── Roo Code (.roo/rules/codrag.md) ─────────────────────────────────


def _write_roo_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
) -> bool:
    """Write .roo/rules/codrag.md for Roo Code.

    Roo Code reads .roo/rules/*.md files. It also supports mode-specific
    directories (.roo/rules-architect/, .roo/rules-code/, etc.) but the
    base .roo/rules/ applies to all modes.
    """
    managed = _build_managed_content(
        project_name, atlas_content, included_paths, is_preliminary, stats,
    )
    content = (
        f"# CoDRAG Integration\n\n"
        f"{managed}\n"
    )

    rules_dir = project_path / ".roo" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    target = rules_dir / "codrag.md"
    target.write_text(content, encoding="utf-8")
    return True


# ── IDE Detection ───────────────────────────────────────────────────


def _detect_targets(project_path: Path, ide: str) -> List[str]:
    """Detect which IDE rules files to write.

    "auto" writes to all detected IDEs. Detection checks for the presence
    of IDE-specific directories or files.
    """
    all_targets = [
        "agents_md", "cursor", "windsurf", "claude",
        "gemini", "copilot", "cline", "roo_code",
    ]
    if ide == "all":
        return all_targets

    if ide != "auto":
        return [ide]

    # AGENTS.md is ALWAYS generated (22+ tools read it)
    targets: List[str] = ["agents_md"]

    # Cursor: .cursor/ directory exists
    if (project_path / ".cursor").exists():
        targets.append("cursor")

    # Windsurf: .windsurf/ directory OR legacy .windsurfrules exists
    if (project_path / ".windsurf").exists() or (project_path / ".windsurfrules").exists():
        targets.append("windsurf")

    # Claude Code: CLAUDE.md exists
    if (project_path / "CLAUDE.md").exists():
        targets.append("claude")

    # Gemini CLI: GEMINI.md exists
    if (project_path / "GEMINI.md").exists():
        targets.append("gemini")

    # GitHub Copilot: detect by Copilot-specific files, NOT .github/ (too broad)
    if (project_path / ".github" / "copilot-instructions.md").exists() or \
       (project_path / ".vscode" / "mcp.json").exists():
        targets.append("copilot")

    # Cline: .clinerules exists
    if (project_path / ".clinerules").exists():
        targets.append("cline")

    # Roo Code: .roo/ directory exists
    if (project_path / ".roo").exists():
        targets.append("roo_code")

    # Default: if only agents_md, also write Cursor rules (most common IDE)
    if len(targets) == 1:
        targets.append("cursor")

    return targets

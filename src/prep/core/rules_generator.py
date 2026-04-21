"""
Rules file generator for AI coding tools (Cursor, Windsurf, Claude Code).

Generates project-level instruction files that tell AI assistants to use
Prep's MCP tools for structural codebase context. Embeds the atlas
(when available) for always-on priming.

Phase 50: MCP Interfacing.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from prep.core.atomic_io import atomic_write_text

logger = logging.getLogger(__name__)


def _write(path: Path, content: str) -> None:
    """Atomic replacement for `path.write_text(content, encoding='utf-8')`.

    AGENTS.md + per-IDE rule files are user-visible and often git-tracked,
    so mid-write crashes must not leave them half-populated. Uses a
    sibling .tmp file and `os.replace` (atomic rename on the same fs).
    """
    atomic_write_text(path, content)

# ── Markers for managed sections ────────────────────────────────────
# Used to identify Prep-managed content in rules files that may also
# contain user-written rules. Everything between START and END markers
# is replaced on regeneration; content outside is preserved.

_CURSOR_MARKER_START = "# --- Prep-managed (auto-generated, do not edit above USER ADDITIONS) ---"
_CURSOR_MARKER_END = "# --- USER ADDITIONS BELOW (preserved across updates) ---"

_MANAGED_MARKER_START = "<!-- prep-managed-start -->"
_MANAGED_MARKER_END = "<!-- prep-managed-end -->"

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
    project_id: Optional[str] = None,
) -> Dict[str, bool]:
    """Write rules files for detected IDEs.

    Generates rules for all detected IDEs (or the specified one).
    Preserves user content outside of Prep-managed markers.

    Args:
        project_path: Root path of the project.
        project_name: Human-readable project name.
        atlas_content: Atlas text to embed. Empty string = no atlas section.
        included_paths: User-selected focus areas from the dashboard.
        is_preliminary: If True, adds "Full analysis in progress" note.
        stats: Optional dict with node_count, edge_count, coverage_pct, last_indexed.
        ide: "auto" (detect all), "cursor", "windsurf", "claude", or "all".
        project_id: Prep project UUID. Embedded in rules for LLM-based routing.

    Returns:
        Dict mapping IDE name to whether the file was written.
    """
    project_path = Path(project_path)
    results: Dict[str, bool] = {}

    # Auto-detect project_id from .prep/project.json if not provided
    if not project_id:
        from prep.core.project_registry import read_codrag_pointer
        pointer = read_codrag_pointer(project_path)
        if pointer:
            project_id = pointer.get("id")

    targets = _detect_targets(project_path, ide)

    _args = (project_path, project_name, atlas_content, included_paths, is_preliminary, stats, project_id)

    _writers = {
        "agents_md": _write_agents_md,
        "cursor": _write_cursor_rules,
        "windsurf": _write_windsurf_rules,
        "claude": _write_claude_rules,
        "claude_skill": _write_claude_skill,  # .claude/skills/prep.md
        "gemini": _write_generic_md,  # GEMINI.md
        "copilot": _write_copilot_rules,  # .github/copilot-instructions.md
        "cline": _write_cline_rules,  # .clinerules
        "roo_code": _write_roo_rules,  # .roo/rules/prep.md
    }

    for target_ide in targets:
        writer = _writers.get(target_ide)
        if not writer:
            continue
        try:
            if target_ide == "gemini":
                results["gemini"] = writer(
                    project_path,
                    project_name,
                    atlas_content,
                    included_paths,
                    is_preliminary,
                    stats,
                    project_id=project_id,
                    filename="GEMINI.md",
                    heading="# Prep Integration",
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

    # Check which targets already have Prep content
    _target_paths = {
        "agents_md": project_path / "AGENTS.md",
        "cursor": project_path / ".cursor" / "rules" / "prep.mdc",
        "windsurf": project_path / ".windsurf" / "rules" / "prep.md",
        "claude": project_path / "CLAUDE.md",
        "gemini": project_path / "GEMINI.md",
        "copilot": project_path / ".github" / "copilot-instructions.md",
        "cline": project_path / ".clinerules",
        "roo_code": project_path / ".roo" / "rules" / "prep.md",
    }

    if not force:
        # Only regenerate targets that are missing Prep content
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
                project_id=project_id,
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
                len(written),
                project_name,
                ", ".join(written),
            )

    return results


def _get_current_atlas_content(project_id: str) -> str:
    """Load the current atlas text from disk. Returns empty string if unavailable."""
    try:
        import json as _json
        from pathlib import Path as _Path

        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project

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
        from prep.services.project_helpers import require_project

        project = require_project(project_id)
        paths = (project.config or {}).get("included_paths") or []
        return paths if paths else None
    except Exception:
        return None


def _get_current_stats(project_id: str) -> Optional[Dict[str, Any]]:
    """Load current graph stats from trace manifest."""
    try:
        import json as _json
        from pathlib import Path as _Path

        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project

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
            project_id=project_id,
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
    project_id: Optional[str] = None,
    target: str = "universal",
) -> str:
    """Build the Prep-managed content block.

    Args:
        target: Content profile.
            "claude" — compact, Claude Code-specific (~60 lines)
            "cursor" — no Claude-specific hints
            "universal" — verbose, for AGENTS.md (default, backward-compat)
    """
    parts: List[str] = []

    # ── Header (all targets) ──
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

    # ── Project ID routing (all targets) ──
    if project_id:
        parts.append(f"prep_project_id: {project_id}")
        parts.append("")
        parts.append(
            f"**ROUTING: When calling ANY Prep tool, ALWAYS include "
            f"`project_id: \"{project_id}\"` in the arguments.**"
        )
        parts.append("")

    # ── Tool table (all targets — compact reference) ──
    parts.append("## Tools")
    parts.append("| Tool | When to Use |")
    parts.append("|------|-------------|")
    parts.append("| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |")
    parts.append("| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). |")
    parts.append("| `prep_impact` | BEFORE editing — check what depends on a file |")
    parts.append("| `prep_audit` | Structural findings (coupling, cycles, concept violations) OR enrich external lint findings with `findings` param. Use `action=\"antibodies\"` for immune system. |")
    parts.append("| `prep_observe` | Save/retrieve cross-session notes |")
    parts.append("| `prep_concepts` | Record/query business rationale and design decisions |")
    parts.append("")
    parts.append("Call `prep` first. Call `prep_impact` before modifying hub files.")
    parts.append("All read-only tools are safe to auto-approve.")
    parts.append("")
    parts.append("### Audit Enrichment")
    parts.append("Enrich external lint/analysis findings with structural context:")
    parts.append("```")
    parts.append("prep_audit(findings=[{file, line, message, severity, tool}])")
    parts.append("```")
    parts.append("Prep adds: dependent count, hub status, concepts, risk score, recommendation.")
    parts.append("Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.")
    parts.append("")
    parts.append("### Search Intent")
    parts.append("`prep_search` auto-detects query intent: \"where is X\" → symbol lookup,")
    parts.append("\"why X\" → concepts, \"who imports X\" → trace graph. Override with `intent` param if needed.")
    parts.append("")

    # ── Target-specific instructions ──
    if target == "claude":
        parts.append("### Auto-Approve")
        parts.append(
            "Add to `.claude/settings.json`:\n"
            '```json\n'
            '{ "permissions": { "allow": ["mcp__codrag"] } }\n'
            '```'
        )
        parts.append("")
        parts.append(
            "Use `@` to browse Prep resources (atlas, modules, audit). "
            "Use `/mcp__codrag__codrag-onboard` for guided orientation."
        )
    elif target == "cursor":
        parts.append(
            "For specific code lookups, use `prep_search` with a natural language query.\n"
            "Prep understands structural relationships — use it instead of\n"
            "grep when you need to understand how files connect."
        )
    else:
        # Universal (AGENTS.md): verbose, multi-IDE
        parts.append(
            "You have access to Prep, a structural code intelligence system.\n"
            "ALWAYS call `prep` (no arguments) at the START of every task.\n"
            "This gives you module structure, hub files, and the user's selected focus areas."
        )
        parts.append("")
        parts.append(
            "For specific code lookups, use `prep_search` with a natural language query.\n"
            "Before making changes to a file, use `prep_impact` to understand dependencies.\n"
            "Prep understands structural relationships between files -- use it instead of\n"
            "grep when you need to understand how files connect to each other."
        )
        parts.append("")
        parts.append(
            "For codebase health and tech debt, use `prep_audit`.\n"
            "For cross-session memory, use `prep_observe` to save/retrieve notes.\n"
            "All Prep tools are read-only and safe to auto-approve."
        )
        parts.append("")
        parts.append(
            "### Auto-Approve Configuration\n"
            "To skip approval prompts for Prep's read-only tools, add to your settings:\n"
            '```json\n'
            '{ "permissions": { "allow": ["mcp__codrag"] } }\n'
            '```\n'
            "In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings."
        )

    # ── Atlas (all targets) ──
    if atlas_content and atlas_content.strip():
        atlas_hash = hashlib.sha256(atlas_content.strip().encode()).hexdigest()[:12]
        parts.append("")
        parts.append(f"<!-- prep-atlas-hash:{atlas_hash} -->")
        parts.append("## Codebase Atlas")
        parts.append("")
        parts.append(atlas_content.strip())

    # ── Focus areas (all targets) ──
    if included_paths:
        parts.append("")
        parts.append("## Focus Areas")
        for p in included_paths[:15]:
            parts.append(f"- {p}")
        if len(included_paths) > 15:
            parts.append(f"- ... +{len(included_paths) - 15} more")
        parts.append("Call `prep` for detailed content from these areas.")

    # ── Fallback / refresh hints (all targets) ──
    parts.append("")
    parts.append(
        "If `prep` returns 'setup in progress', the index hasn't been built yet.\n"
        "Work normally with read_file/grep_search until the user builds the index."
    )
    parts.append("")
    parts.append(
        "For long tasks (5+ tool calls), call `prep` again to refresh your\nstructural context."
    )

    # ── Universal-only verbose sections ──
    if target == "universal":
        parts.append("")
        parts.append(
            "You can call `prep` and `prep_search` in parallel on your first\n"
            "prompt -- structural overview + targeted code lookup in one round-trip."
        )
        parts.append("")
        parts.append("### Tool Calling Rules")
        parts.append("1. **Never announce** 'I will now call...' - just call the tool")
        parts.append("2. **No permission needed** - simple keywords = immediate invocation")
        parts.append("3. **Single word triggers** - 'prep' alone is enough to call the tool")
        parts.append(
            "4. **Context is cheap** - prefer calling prep to using grep for structural understanding"
        )
        parts.append("")
        parts.append(
            '**Remember: The word "prep" anywhere in user input is a tool invocation signal. '
            'Call immediately without asking permission.**'
        )
        parts.append("")
        parts.append("### MCP Resources (browse with @)")
        parts.append(
            "Prep also exposes browsable resources via MCP. In supported clients,\n"
            "type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.\n"
            "Resources provide on-demand context without a tool call."
        )
        parts.append("")
        parts.append("### MCP Prompts (invoke with /)")
        parts.append(
            "Available workflow prompts: `prep-onboard` (orientation), `prep-review` (file review),\n"
            "`prep-plan` (change planning), `prep-investigate` (deep dive), `prep-health` (audit).\n"
            "In Claude Code: `/mcp__codrag__codrag-onboard`. In other clients: check prompt menu."
        )

    return "\n".join(parts)


# ── Cursor (.cursor/rules/prep.mdc) ──────────────────────────────


def generate_cursor_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> str:
    """Generate .cursor/rules/prep.mdc content with YAML frontmatter."""
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
        target="cursor",
    )

    return (
        "---\n"
        "description: Prep structural codebase intelligence\n"
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
    project_id: Optional[str] = None,
) -> bool:
    """Write or update .cursor/rules/prep.mdc."""
    rules_dir = project_path / ".cursor" / "rules"
    target = rules_dir / "prep.mdc"

    new_content = generate_cursor_rules(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        # Preserve user content below the end marker
        if _CURSOR_MARKER_END in existing:
            user_section = existing[existing.index(_CURSOR_MARKER_END) + len(_CURSOR_MARKER_END) :]
            # Replace managed section, keep user section
            new_content = new_content.rstrip("\n") + user_section
        elif _CURSOR_MARKER_START not in existing:
            # File exists but has no Prep markers -- user created it manually.
            # Don't overwrite. Append our content at the end.
            logger.info("Existing prep.mdc without markers -- appending Prep section")
            new_content = existing.rstrip("\n") + "\n\n" + new_content

    rules_dir.mkdir(parents=True, exist_ok=True)
    _write(target, new_content)
    return True


# ── Windsurf (.windsurf/rules/prep.md) ────────────────────────────
# NOTE: Windsurf moved from .windsurfrules to .windsurf/rules/*.md
# with YAML frontmatter (trigger: always_on). We write to the new
# path but also check for legacy .windsurfrules.


def generate_windsurf_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> str:
    """Generate .windsurf/rules/prep.md content with YAML frontmatter."""
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )

    return (
        "---\n"
        "trigger: always_on\n"
        "description: Prep structural codebase intelligence\n"
        "---\n"
        "\n"
        f"{_WINDSURF_MARKER_START}\n"
        f"## Prep Structural Context\n"
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
    project_id: Optional[str] = None,
) -> bool:
    """Write .windsurf/rules/prep.md (new path) or update legacy .windsurfrules."""
    new_content = generate_windsurf_rules(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )

    # Prefer new path: .windsurf/rules/prep.md
    new_dir = project_path / ".windsurf" / "rules"
    new_target = new_dir / "prep.md"
    legacy_target = project_path / ".windsurfrules"

    if new_dir.exists() or (project_path / ".windsurf").exists():
        # Write to new path
        new_dir.mkdir(parents=True, exist_ok=True)
        _write(new_target, new_content + "\n")
        return True

    # Fallback: legacy .windsurfrules (marker-based append)
    if legacy_target.exists():
        existing = legacy_target.read_text(encoding="utf-8")
        if _WINDSURF_MARKER_START in existing:
            before = existing[: existing.index(_WINDSURF_MARKER_START)]
            end_idx = existing.find(_WINDSURF_MARKER_END)
            after = existing[end_idx + len(_WINDSURF_MARKER_END) :] if end_idx >= 0 else ""
            _write(legacy_target, before.rstrip("\n") + "\n\n" + new_content + after)
        else:
            _write(legacy_target, existing.rstrip("\n") + "\n\n" + new_content + "\n")
        return True

    # No Windsurf directory found -- create new path
    new_dir.mkdir(parents=True, exist_ok=True)
    _write(new_target, new_content + "\n")
    return True


# ── Claude Code (CLAUDE.md) ────────────────────────────────────────


def generate_claude_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> str:
    """Generate Prep section for CLAUDE.md."""
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
        target="claude",
    )

    return f"{_CLAUDE_MARKER_START}\n# Prep Integration\n\n{managed}\n{_CLAUDE_MARKER_END}"


def _write_claude_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
) -> bool:
    """Write or update CLAUDE.md with marker-based section management."""
    target = project_path / "CLAUDE.md"

    new_section = generate_claude_rules(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            # Replace existing Prep section
            before = existing[: existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END) :] if end_idx >= 0 else ""
            _write(target, before.rstrip("\n") + "\n\n" + new_section + after)
        else:
            # No Prep section yet -- append
            _write(target, existing.rstrip("\n") + "\n\n" + new_section + "\n")
    else:
        _write(target, new_section + "\n")

    return True


# ── Claude Code Skills (.claude/skills/prep.md) ────────────────────


def _write_claude_skill(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
) -> bool:
    """Write .claude/skills/prep.md for Claude Code slash command.

    Creates a /prep skill that Claude Code users can trigger as a slash
    command. The skill instructs Claude to call Prep tools in a
    structured workflow. Only written if .claude/ directory already exists.
    """
    skills_dir = project_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / "prep.md"

    content = (
        "---\n"
        "description: Get structural codebase context from Prep\n"
        "tools:\n"
        "  - mcp__codrag__codrag\n"
        "  - mcp__codrag__codrag_search\n"
        "  - mcp__codrag__codrag_impact\n"
        "---\n"
        "\n"
        "Call `prep` to get the structural overview of this codebase -- modules,\n"
        "hub files, and knowledge base content. Use the structural context to\n"
        "inform your approach before reading or editing files.\n"
        "\n"
        "If the user asked a specific question, also call `prep_search` with\n"
        "their question to find relevant code with structural trace expansion.\n"
        "\n"
        "Before making changes, call `prep_impact` on the target file to\n"
        "understand what depends on it.\n"
    )

    # Don't overwrite if user has customized the skill
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if "prep" in existing.lower() and "---" in existing:
            return True  # Already has a Prep skill, don't overwrite

    _write(target, content)
    return True


# ── AGENTS.md (universal -- 22+ tools) ──────────────────────────────


def _write_agents_md(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
) -> bool:
    """Write or update AGENTS.md with Prep section.

    AGENTS.md is the universal standard read by 22+ tools (Cursor, Windsurf,
    Copilot, Claude Code, Gemini CLI, Roo Code, Zed, Aider, Amp, etc.).
    Stewarded by the Agentic AI Foundation under the Linux Foundation.
    """
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
        target="universal",
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n## Prep Integration\n\n{managed}\n{_CLAUDE_MARKER_END}"
    )

    target = project_path / "AGENTS.md"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[: existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END) :] if end_idx >= 0 else ""
            _write(target, before.rstrip("\n") + "\n\n" + new_section + after)
        else:
            _write(target, existing.rstrip("\n") + "\n\n" + new_section + "\n")
    else:
        _write(target, new_section + "\n")
    return True


# ── Generic markdown file (GEMINI.md, etc.) ─────────────────────────


def _write_generic_md(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
    filename: str = "GEMINI.md",
    heading: str = "# Prep Integration",
) -> bool:
    """Write or update a generic markdown file with Prep section.

    Used for GEMINI.md and similar files that use marker-based sections.
    """
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )
    new_section = f"{_CLAUDE_MARKER_START}\n{heading}\n\n{managed}\n{_CLAUDE_MARKER_END}"

    target = project_path / filename
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[: existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END) :] if end_idx >= 0 else ""
            _write(target, before.rstrip("\n") + "\n\n" + new_section + after)
        else:
            _write(target, existing.rstrip("\n") + "\n\n" + new_section + "\n")
    else:
        _write(target, new_section + "\n")
    return True


# ── GitHub Copilot (.github/copilot-instructions.md) ────────────────


def _write_copilot_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
) -> bool:
    """Write or update .github/copilot-instructions.md with Prep section."""
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n## Prep Integration\n\n{managed}\n{_CLAUDE_MARKER_END}"
    )

    github_dir = project_path / ".github"
    target = github_dir / "copilot-instructions.md"

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[: existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END) :] if end_idx >= 0 else ""
            _write(target, before.rstrip("\n") + "\n\n" + new_section + after)
        else:
            _write(target, existing.rstrip("\n") + "\n\n" + new_section + "\n")
    else:
        github_dir.mkdir(parents=True, exist_ok=True)
        _write(target, new_section + "\n")
    return True


# ── Cline (.clinerules) ──────────────────────────────────────────────


def _write_cline_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
) -> bool:
    """Write or update .clinerules with Prep keyword triggers.

    Cline uses keyword-based MCP activation: when the AI sees keywords
    matching a .clinerules entry, it activates the corresponding MCP server.
    """
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )
    # Cline-specific: keyword triggers at the top for MCP activation
    trigger_block = (
        "When asked about code structure, architecture, dependencies, modules, "
        "hub files, blast radius, impact analysis, or codebase navigation, "
        "use the Prep MCP tools.\n\n"
    )
    new_section = (
        f"{_CLAUDE_MARKER_START}\n"
        f"## Prep Integration\n\n"
        f"{trigger_block}"
        f"{managed}\n"
        f"{_CLAUDE_MARKER_END}"
    )

    target = project_path / ".clinerules"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _CLAUDE_MARKER_START in existing:
            before = existing[: existing.index(_CLAUDE_MARKER_START)]
            end_idx = existing.find(_CLAUDE_MARKER_END)
            after = existing[end_idx + len(_CLAUDE_MARKER_END) :] if end_idx >= 0 else ""
            _write(target, before.rstrip("\n") + "\n\n" + new_section + after)
        else:
            _write(target, existing.rstrip("\n") + "\n\n" + new_section + "\n")
    else:
        _write(target, new_section + "\n")
    return True


# ── Roo Code (.roo/rules/prep.md) ─────────────────────────────────


def _write_roo_rules(
    project_path: Path,
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
) -> bool:
    """Write .roo/rules/prep.md + mode-specific rules for Roo Code.

    Roo Code reads .roo/rules/*.md files (all modes) and mode-specific
    directories (.roo/rules-architect/, .roo/rules-code/, etc.).

    We write:
    - .roo/rules/prep.md -- base rules for all modes (full managed content)
    - .roo/rules-architect/prep.md -- architecture focus (prep + prep_audit)
    - .roo/rules-code/prep.md -- change focus (prep_impact before edits)
    """
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
    )
    content = f"# Prep Integration\n\n{managed}\n"

    # Base rules (all modes)
    rules_dir = project_path / ".roo" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    target = rules_dir / "prep.md"
    _write(target, content)

    # Mode-specific: Architect -- emphasize structural overview + audit
    arch_dir = project_path / ".roo" / "rules-architect"
    arch_dir.mkdir(parents=True, exist_ok=True)
    arch_content = (
        "# Prep -- Architect Mode\n\n"
        "In Architect mode, always start with `prep` for the structural overview.\n"
        "Use `prep_audit` to identify architecture issues, tech debt, and refactoring targets.\n"
        "Use `prep_search` to explore how modules and subsystems connect.\n"
    )
    _write(arch_dir / "prep.md", arch_content)

    # Mode-specific: Code -- emphasize impact analysis before changes
    code_dir = project_path / ".roo" / "rules-code"
    code_dir.mkdir(parents=True, exist_ok=True)
    code_content = (
        "# Prep -- Code Mode\n\n"
        "Before editing files, call `prep_impact` to understand the blast radius.\n"
        "Use `prep_search` to find related code that may need updates.\n"
        "After finishing changes, use `prep_observe` to record decisions and patterns.\n"
    )
    _write(code_dir / "prep.md", code_content)

    return True


# ── IDE Detection ───────────────────────────────────────────────────


def _detect_targets(project_path: Path, ide: str) -> List[str]:
    """Detect which IDE rules files to write.

    "auto" writes to all detected IDEs. Detection checks for the presence
    of IDE-specific directories or files.
    """
    all_targets = [
        "agents_md",
        "cursor",
        "windsurf",
        "claude",
        "claude_skill",
        "gemini",
        "copilot",
        "cline",
        "roo_code",
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

    # Claude Code Skills: .claude/ directory exists
    if (project_path / ".claude").exists():
        targets.append("claude_skill")

    # Gemini CLI: GEMINI.md exists
    if (project_path / "GEMINI.md").exists():
        targets.append("gemini")

    # GitHub Copilot: detect by Copilot-specific files, NOT .github/ (too broad)
    if (project_path / ".github" / "copilot-instructions.md").exists() or (
        project_path / ".vscode" / "mcp.json"
    ).exists():
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

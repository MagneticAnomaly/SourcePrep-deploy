"""MCP resource content generators + prompt handlers for collaboration.

All data is fetched from the daemon HTTP API via server._api_get().
This file contains NO direct SQLite access.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Resource Registration ──────────────────────────────────────


def get_collaboration_resources(project_id: str) -> List[Dict[str, Any]]:
    """Return resource descriptors for collaboration resources."""
    pid = project_id
    return [
        {
            "uri": f"codrag://{pid}/memory/{{role}}",
            "name": "Agent Memory",
            "description": (
                "An agent's own prior observations, filtered by role. "
                "Replace {role} with agent name "
                "(e.g. researcher, pi/watchdog)."
            ),
            "mimeType": "text/markdown",
            "annotations": {"audience": ["assistant"]},
        },
        {
            "uri": f"codrag://{pid}/agents/{{role}}/findings",
            "name": "Cross-Agent Findings",
            "description": (
                "Another agent's recent findings. "
                "Replace {role} with agent name."
            ),
            "mimeType": "text/markdown",
            "annotations": {"audience": ["assistant"]},
        },
        {
            "uri": f"codrag://{pid}/delta",
            "name": "Structural Delta",
            "description": (
                "What changed structurally in the codebase graph "
                "in the last 7 days."
            ),
            "mimeType": "text/markdown",
            "annotations": {"audience": ["assistant"]},
        },
    ]


# ── URI Parsing ──────────────────────────────────────────────


def parse_collaboration_uri(
    resource_type: str,
) -> Optional[Tuple[str, Dict[str, str]]]:
    """Parse a collaboration resource URI path.

    Args:
        resource_type: Everything after ``codrag://{pid}/``.

    Returns:
        ``(resource_name, params)`` or ``None`` if not a collab resource.
    """
    if resource_type == "delta":
        return ("delta", {})
    if resource_type.startswith("memory/"):
        role = resource_type[len("memory/"):]
        if role:
            return ("memory", {"role": role})
    if (resource_type.startswith("agents/")
            and resource_type.endswith("/findings")):
        middle = resource_type[len("agents/"):-len("/findings")]
        if middle:
            return ("agent_findings", {"role": middle})
    return None


# ── Content Formatters ──────────────────────────────────────


def format_activity_resource(
    entries: List[Dict[str, Any]],
) -> str:
    """Format activity entries as markdown."""
    if not entries:
        return "## Agent Activity\n\nNo recent activity recorded."

    lines = [f"## Agent Activity ({len(entries)} entries)\n"]
    lines.append("| Time | Agent | Action | Summary |")
    lines.append("|---|---|---|---|")

    for e in entries:
        ts = e.get("created_at", 0)
        time_str = (
            datetime.datetime.fromtimestamp(ts).strftime("%H:%M")
            if ts else "?"
        )
        lines.append(
            f"| {time_str} | {e.get('agent_role', '?')} "
            f"| {e.get('action', '?')} "
            f"| {e.get('summary', '')} |"
        )
    return "\n".join(lines)


def format_memory_resource(
    role: str,
    observations: List[Dict[str, Any]],
) -> str:
    """Format per-role memory as markdown."""
    if not observations:
        return (
            f"## {role.title()} Memory\n\n"
            "No observations from this agent."
        )

    lines = [
        f"## {role.title()} Memory "
        f"({len(observations)} observations)\n",
    ]
    for obs in observations:
        ts = obs.get("created_at", 0)
        date_str = (
            datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            if ts else "?"
        )
        content = obs.get("content", "")
        file_path = obs.get("file_path", "")
        category = obs.get("category", "note")

        lines.append(f"- [{date_str}] {content}")
        if file_path:
            lines.append(
                f"  File: {file_path} | Category: {category}"
            )
    return "\n".join(lines)


def format_delta_resource(delta: Dict[str, Any]) -> str:
    """Format structural delta as markdown."""
    if delta.get("is_empty", True):
        return (
            "## Structural Delta\n\n"
            "No structural changes detected."
        )

    lines = ["## Structural Delta\n"]

    hub_changes = delta.get("hub_changes", [])
    if hub_changes:
        lines.append("### Hub Changes")
        for h in hub_changes:
            change = h.get("change", "?")
            path = h.get("path", "?")
            if change == "new":
                deps = h.get("dependents_count", 0)
                rank = h.get("rank", "?")
                lines.append(
                    f"- **NEW:** {path} "
                    f"({deps} dependents) — rank #{rank}"
                )
            elif change == "removed":
                lines.append(f"- **REMOVED:** {path}")
            elif change == "rank_changed":
                lines.append(
                    f"- **RANK CHANGE:** {path} — "
                    f"#{h.get('old_rank', '?')} -> "
                    f"#{h.get('new_rank', '?')}"
                )
        lines.append("")

    mod_changes = delta.get("module_changes", [])
    if mod_changes:
        lines.append("### Module Changes")
        for m in mod_changes:
            change = m.get("change", "?")
            name = m.get("name", "?")
            if change == "new":
                lines.append(
                    f"- **NEW:** {name} "
                    f"({m.get('file_count', 0)} files)"
                )
            elif change == "removed":
                lines.append(f"- **REMOVED:** {name}")
            elif change == "size_changed":
                lines.append(
                    f"- **SIZE CHANGE:** {name} — "
                    f"{m.get('old_file_count', '?')} -> "
                    f"{m.get('new_file_count', '?')} files"
                )

    return "\n".join(lines)


def format_conflicts_resource(
    conflicts: List[Dict[str, Any]],
) -> str:
    """Format active conflicts as markdown."""
    if not conflicts:
        return "## Agent Conflicts\n\nNo active conflicts."

    lines = [
        f"## Active Agent Conflicts "
        f"({len(conflicts)} unresolved)\n",
    ]
    for i, c in enumerate(conflicts, 1):
        lines.append(f"### {i}. {c.get('file_path', '?')}")
        lines.append(
            f"- **{c.get('agent_a', '?')}**: "
            f"\"{c.get('agent_a_assessment', '')}\""
        )
        lines.append(
            f"- **{c.get('agent_b', '?')}**: "
            f"\"{c.get('agent_b_assessment', '')}\""
        )
        lines.append(
            f"- **Type:** {c.get('conflict_type', '?')} "
            f"| **Status:** {c.get('resolution', '?')}"
        )
        lines.append("")

    return "\n".join(lines)


# ── Prompt Definitions ──────────────────────────────────────


def get_collaboration_prompts() -> List[Dict[str, Any]]:
    """Return prompt descriptors for collaboration prompts."""
    return [
        {
            "name": "codrag-handoff",
            "description": (
                "Transfer context from one agent to another — "
                "packages prior work, findings, and structural data"
            ),
            "arguments": [
                {
                    "name": "from_role",
                    "description": "Agent role handing off",
                    "required": True,
                },
                {
                    "name": "to_role",
                    "description": "Agent role receiving",
                    "required": True,
                },
                {
                    "name": "task",
                    "description": "Optional task context",
                    "required": False,
                },
            ],
        },
        {
            "name": "codrag-scope",
            "description": (
                "Show what an agent role owns — modules, "
                "recent changes, open findings"
            ),
            "arguments": [
                {
                    "name": "role",
                    "description": "Agent role to scope",
                    "required": True,
                },
            ],
        },
        {
            "name": "codrag-enrich",
            "description": (
                "Enrich findings with structural intelligence — "
                "blast radius, hub involvement, cross-module analysis"
            ),
            "arguments": [
                {
                    "name": "scope",
                    "description": "Optional area to focus on",
                    "required": False,
                },
            ],
        },
    ]


def get_collaboration_prompt_messages(
    name: str,
    arguments: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Return prompt messages, or None if not a collab prompt."""
    if name == "codrag-handoff":
        from_role = arguments.get("from_role", "previous agent")
        to_role = arguments.get("to_role", "you")
        task = arguments.get("task", "")
        task_line = f"\nTask context: {task}\n" if task else ""
        return {
            "description": f"Handoff from {from_role} to {to_role}",
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "You are taking over a task from the "
                        f"{from_role} agent.{task_line}\n"
                        f"1. Review what {from_role} found — check "
                        f"@codrag://memory/{from_role} for their "
                        f"observations and "
                        f"@codrag://agents/{from_role}/findings "
                        f"for findings.\n"
                        "2. Check @codrag://delta for any structural "
                        "changes since their last session.\n"
                        "3. Call `codrag_search` to deepen your "
                        "understanding of relevant code.\n"
                        "4. Summarize what you're picking up and "
                        "your next steps."
                    ),
                },
            }],
        }

    if name == "codrag-scope":
        role = arguments.get("role", "agent")
        return {
            "description": f"Scope overview for {role}",
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Show me what the {role} agent owns.\n\n"
                        "1. Call `codrag` for the structural "
                        f"overview relevant to {role}.\n"
                        f"2. Check @codrag://memory/{role} for "
                        "recent observations.\n"
                        "3. Check @codrag://delta for structural "
                        "changes in their scope.\n"
                        f"4. Summarize: what does {role} own, "
                        "what changed, what needs attention."
                    ),
                },
            }],
        }

    if name == "codrag-enrich":
        scope = arguments.get("scope", "")
        scope_text = f" Focus on: {scope}." if scope else ""
        return {
            "description": "Enrich findings with structural intelligence",
            "messages": [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        "Enrich the current findings with structural "
                        "intelligence from CoDRAG."
                        f"{scope_text}\n\n"
                        "1. Call `codrag_audit` to get current "
                        "findings.\n"
                        "2. For the top findings, call "
                        "`codrag_impact` to assess blast radius.\n"
                        "3. Identify which findings touch hub files "
                        "vs leaf files.\n"
                        "4. Note which findings span multiple "
                        "modules vs are contained to one.\n"
                        "5. Summarize each finding with: scope "
                        "size, hub involvement, blast radius, "
                        "and whether it overlaps with areas other "
                        "agents have flagged."
                    ),
                },
            }],
        }

    return None

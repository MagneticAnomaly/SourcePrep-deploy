"""LLM prompt templates and KNOWLEDGE.md template for Staffing Agent.

AGENTS.md and SOUL.md generation require LLM calls — these functions
produce the system+user prompts. KNOWLEDGE.md is pure template rendering.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple


def render_agents_md_prompt(
    role_name: str,
    role_slug: str,
    atlas_excerpt: str,
    modules_summary: str,
    recommended_files: List[str],
    previous_content: str = "",
) -> str:
    """Render the LLM prompt for generating an AGENTS.md file.

    If ``previous_content`` is provided (from an existing AGENTS.md on disk),
    the prompt instructs the LLM to preserve and expand upon human edits
    rather than generating from scratch.
    """
    files_block = "\n".join(f"- `{f}`" for f in recommended_files) if recommended_files else "(none)"

    # Edit-aware section: if the user has manually edited the file, tell
    # the LLM to treat those edits as authoritative additions.
    edit_aware = ""
    if previous_content:
        edit_aware = f"""\n## Previous Version (IMPORTANT — PRESERVE EDITS)

The following is the current AGENTS.md for this role. The user may have
manually added responsibilities, priorities, or behavioral guidelines.
**You MUST preserve and incorporate ALL existing content.** Treat any
human-authored additions as authoritative. Expand and refine them with
updated codebase context, but NEVER remove or ignore user additions.

```markdown
{previous_content}
```
"""
    return f"""Generate an AGENTS.md instruction file for the **{role_name}** role (slug: `{role_slug}`).

## Codebase Context

{atlas_excerpt}

## Module Structure

{modules_summary}

## Key Files for This Role

{files_block}
{edit_aware}
## Requirements

Write a markdown document (~1500 tokens) that includes:
1. **Role Summary** — One paragraph defining this role's primary responsibility
2. **Priorities** — Numbered list of what this role focuses on, grounded in the codebase modules above
3. **Behavioral Guidelines** — How this role should approach tasks (e.g., "always check impact radius before modifying hub files")
4. **Knowledge Sources** — Which CoDRAG tools to use and when:
   - `codrag(role="{role_slug}")` for scoped structural overview
   - `codrag_search(query, role="{role_slug}")` for code search
   - `codrag_impact(file)` before modifying files
5. **Boundaries** — What this role should NOT do (stay in lane)

Ground every instruction in specific modules, files, or architectural patterns from the context above. Do not use generic advice."""


AGENTS_MD_SYSTEM = """You are an expert at writing AI agent instruction files (AGENTS.md).
You produce clear, specific, actionable markdown instructions grounded in codebase evidence.
When given a previous version, you PRESERVE all user-authored additions and integrate them
with updated codebase context. Never discard human edits.
Output ONLY the markdown content — no preamble, no code fences wrapping the whole output."""


def render_soul_md_prompt(
    role_name: str,
    role_slug: str,
    atlas_excerpt: str,
    previous_content: str = "",
) -> str:
    """Render the LLM prompt for generating a SOUL.md identity file.

    If ``previous_content`` is provided, the LLM preserves user edits.
    """
    edit_aware = ""
    if previous_content:
        edit_aware = f"""\n## Previous Version (IMPORTANT — PRESERVE EDITS)

The following is the current SOUL.md for this role. The user may have
customized the identity, values, or guardrails. **You MUST preserve and
incorporate ALL existing content.** Refine with updated codebase context
but NEVER remove user additions.

```markdown
{previous_content}
```
"""
    return f"""Generate a SOUL.md identity file for the **{role_name}** role (slug: `{role_slug}`).

## Codebase Context

{atlas_excerpt}
{edit_aware}
## Requirements

Write a markdown document (~600 tokens) that includes:
1. **Identity Statement** — "I am the {role_name}. My purpose is..." (one sentence)
2. **Core Values** — 3-5 values derived from what this role protects/optimizes in this codebase
3. **Communication Style** — How this role communicates (e.g., concise for operators, detailed for architects)
4. **Guardrails** — 2-3 things this role must never do
5. **Collaboration** — How this role relates to other roles on the team

Derive everything from the codebase context. A CTO of a React dashboard app has different values than a CTO of an embedded systems project."""


SOUL_MD_SYSTEM = """You are an expert at writing AI agent identity files (SOUL.md).
You produce concise, personality-defining markdown that gives an AI agent a coherent identity.
When given a previous version, you PRESERVE all user-authored identity traits and integrate them
with updated codebase context. Never discard human customizations.
Output ONLY the markdown content — no preamble, no code fences wrapping the whole output."""


def render_knowledge_md(
    role_name: str,
    role_slug: str,
    atlas_snapshot: str,
    recommended_files: List[Tuple[str, float]],
    domain_focus: List[str],
    project_id: str,
) -> str:
    """Render KNOWLEDGE.md from template (no LLM needed)."""
    files_table = ""
    if recommended_files:
        files_table = "| File | Relevance |\n|------|----------|\n"
        for path, score in recommended_files:
            files_table += f"| `{path}` | {score:.2f} |\n"
    else:
        files_table = "(No files scored yet — run auto-populate to generate.)"

    domains = ", ".join(domain_focus) if domain_focus else "(general)"

    return f"""# Knowledge Base — {role_name}

> Auto-generated by CoDRAG Staffing Agent. Do not edit manually.

## CoDRAG Tools

Use these tools to get live, role-scoped context:

| Tool | Usage |
|------|-------|
| `codrag(role="{role_slug}")` | Structural overview filtered for your role |
| `codrag_search(query, role="{role_slug}")` | Semantic code search scoped to your files |
| `codrag_impact(file)` | Check blast radius before modifying files |
| `codrag_audit()` | Review codebase health findings |
| `codrag_observe(content)` | Save observations for cross-session memory |

**Project ID:** `{project_id}`

## Architecture Snapshot

{atlas_snapshot}

## Key Files

{files_table}

## Domain Focus

{domains}

## Usage Notes

- Call `codrag(role="{role_slug}")` at the start of every task for scoped context
- Use `codrag_impact()` before modifying any file in the Key Files table
- Files with relevance ≥0.8 are your primary responsibility
- Files with relevance 0.4–0.8 are shared with other roles
"""


def render_auto_roles_prompt(
    file_count: int,
    module_count: int,
    modules_summary: str,
    atlas_excerpt: str,
    domain_tags: List[str],
    layer_distribution: Dict[str, int],
    audit_findings: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Render the LLM prompt for auto-inferring roles from codebase analysis.

    Args:
        audit_findings: Optional list of structural audit findings, each with
            'title', 'category', 'severity', 'affected_files', 'description'.
            When provided, the LLM uses these to justify roles that address
            specific structural problems (coupling hotspots, hub concentration,
            concept violations, architectural drift).
    """
    tags_str = ", ".join(domain_tags) if domain_tags else "(none)"
    layers_str = ", ".join(f"{k}: {v} files" for k, v in layer_distribution.items()) if layer_distribution else "(none)"

    audit_section = ""
    if audit_findings:
        finding_lines = []
        for f in audit_findings[:20]:  # Cap at 20 to stay within prompt budget
            files = f.get("affected_files", "")
            finding_lines.append(
                f"- [{f.get('severity', 'info').upper()}] {f.get('title', '')} "
                f"({f.get('category', '')}): {f.get('description', '')[:150]}"
                + (f" — files: {files}" if files else "")
            )
        audit_section = f"""

## Structural Audit Findings

These are CoDRAG-detected structural issues in the codebase. Use them to justify
roles that address specific problems — a role should exist because it resolves
real structural failures, not just because a domain exists.

{chr(10).join(finding_lines)}
"""

    return f"""Analyze this codebase and recommend an optimal team of AI agent roles.

## Codebase Statistics

- **Total files:** {file_count}
- **Module clusters:** {module_count}
- **Domain tags:** {tags_str}
- **Architecture layers:** {layers_str}

## Module Structure

{modules_summary}

## Codebase Overview

{atlas_excerpt}
{audit_section}
## Instructions

Based on the codebase structure above, recommend 2-6 agent roles. For each role provide:

1. **slug** — lowercase_underscore identifier
2. **display_name** — Human-readable role title
3. **justification** — Why this role is needed (cite specific modules/domains and any audit findings that this role would address)
4. **primary_modules** — Which modules this role owns
5. **domain_focus** — Which domain tags this role covers

Respond as a JSON array of objects with these 5 fields. Do not include generic roles unless the codebase evidence supports them. Fewer focused roles are better than many overlapping ones.

Guidelines:
- Small codebases (<30 files): 2-3 generalist roles
- Medium codebases (30-100 files): 3-4 roles
- Large codebases (>100 files): 4-6 specialized roles
- Monorepos: Consider domain-owner roles per workspace
- If audit findings show coupling hotspots or hub concentration in a module, that module needs a dedicated steward role
- If audit findings show concept violations or architectural drift, propose a role responsible for maintaining architectural intent"""


AUTO_ROLES_SYSTEM = """You are an expert at analyzing codebases and designing optimal AI agent team structures.
You output ONLY valid JSON — a JSON array of role objects. No markdown, no explanations outside the JSON."""

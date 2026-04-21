"""LLM prompt templates for Researcher Agent.

Three-stage pipeline: topic selection -> research synthesis -> plan formulation.
"""
from __future__ import annotations

from typing import Any, Dict, List


def render_topic_selection_prompt(
    findings: List[Dict[str, Any]],
    max_topics: int,
    atlas_excerpt: str,
) -> str:
    """Render the LLM prompt for selecting high-impact topics from audit findings."""
    findings_block = ""
    for i, f in enumerate(findings, 1):
        findings_block += (
            f"\n{i}. **[{f.get('priority', 'P2')}] {f.get('title', 'Untitled')}**\n"
            f"   ID: {f.get('id', '')}\n"
            f"   Description: {f.get('description', '')}\n"
            f"   Files: {', '.join(f.get('affected_files', []))}\n"
        )

    return f"""You are a technical PM reviewing codebase audit findings.

## Codebase Context

{atlas_excerpt}

## Audit Findings

{findings_block}

## Task

Select the top {max_topics} findings that would most benefit from deeper research
and a structured implementation plan. Prioritize by:
1. Impact — how many files/modules are affected
2. Severity — P0 > P1 > P2 > P3
3. Actionability — can a clear fix plan be formulated?

Return a JSON array of objects, each with:
- "finding_id": the ID from the list above
- "rationale": one sentence explaining why this topic is worth researching

Select exactly {max_topics} topics (or fewer if fewer findings exist)."""


TOPIC_SELECTION_SYSTEM = """You are an expert technical PM who triages codebase issues.
You output ONLY valid JSON — a JSON array of objects. No markdown, no explanations outside the JSON."""


def render_research_prompt(
    topic_title: str,
    topic_description: str,
    affected_files: List[str],
    code_context: str,
    impact_summary: str,
) -> str:
    """Render the LLM prompt for researching a solution to a specific topic."""
    files_block = "\n".join(f"- `{f}`" for f in affected_files) if affected_files else "(none)"

    return f"""Research a solution for this codebase issue:

## Issue

**Title:** {topic_title}
**Description:** {topic_description}

## Affected Files

{files_block}

## Impact

{impact_summary if impact_summary else "(not analyzed)"}

## Code Context

```
{code_context if code_context else "(no code context available)"}
```

## Task

Produce a detailed analysis covering:
1. **Root cause** — Why does this issue exist? What design decision or oversight led to it?
2. **Solution approach** — What is the best fix? Describe the concrete changes needed.
3. **Step-by-step procedure** — Ordered list of specific code changes to make.
4. **Risks** — What could go wrong? What should be tested carefully?
5. **Effort estimate** — small (< 1 hour), medium (1-4 hours), or large (> 4 hours)

Be specific. Reference actual files and code patterns from the context above."""


RESEARCH_SYSTEM = """You are an expert software engineer analyzing codebase issues.
You produce detailed, actionable technical analysis grounded in the provided code context.
Output clear markdown prose — no JSON wrapping."""


def render_plan_formulation_prompt(
    topic_title: str,
    research_output: str,
    affected_files: List[str],
) -> str:
    """Render the LLM prompt for structuring research into a formal plan."""
    files_block = "\n".join(f"- `{f}`" for f in affected_files) if affected_files else "(none)"

    return f"""Convert this research analysis into a structured implementation plan.

## Research: {topic_title}

{research_output}

## Affected Files

{files_block}

## Task

Output a JSON object with exactly these fields:
- "root_cause": string — one paragraph explaining the root cause
- "fix_steps": array of strings — ordered list of concrete implementation steps
- "effort": "small" | "medium" | "large"
- "risk": "low" | "medium" | "high"
- "testing_strategy": string — how to verify the fix works

Be specific in fix_steps. Each step should be a concrete action like
"Extract shared types from core/models.py into core/shared_types.py"."""


PLAN_FORMULATION_SYSTEM = """You are an expert at converting technical analysis into structured implementation plans.
You output ONLY valid JSON — a single JSON object. No markdown, no explanations outside the JSON."""

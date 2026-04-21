"""CrewAI adapter for the Digital Custodian.

Wraps CustodianEngine as a 2-agent CrewAI Crew: Analyzer + Janitor.

Requires: pip install prep[crewai]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from prep.agents.custodian.engine import CustodianEngine


def build_custodian_crew(
    engine: CustodianEngine,
    findings: List[Dict[str, Any]],
    llm: Optional[Any] = None,
    dry_run: bool = True,
    max_files: int = 20,
) -> Any:
    """Build a CrewAI Crew for the Digital Custodian.

    Args:
        engine: CustodianEngine instance.
        findings: Audit findings to scan for dead code.
        llm: LangChain-compatible LLM. If None, uses build_llm_from_settings().
        dry_run: Whether to skip execution (default True).
        max_files: Max files per cleanup.

    Returns:
        A CrewAI Crew instance ready to kick off.
    """
    try:
        from crewai import Agent, Task, Crew, Process
    except ImportError:
        raise ImportError(
            "crewai is required for CrewAI adapters. "
            "Install with: pip install prep[crewai]"
        )

    if llm is None:
        from prep.agents.shared.llm_bridge import build_llm_from_settings
        llm = build_llm_from_settings()

    analyzer = Agent(
        role="Dead Code Analyzer",
        goal="Identify files with zero dependents that are safe to delete",
        backstory=(
            f"You are scanning {len(findings)} audit findings for dead code. "
            "You filter to dead_code, orphan, and deprecated categories, "
            "then verify each candidate via Prep impact analysis."
        ),
        llm=llm,
        verbose=False,
    )

    janitor = Agent(
        role="Codebase Janitor",
        goal="Plan safe cleanup of verified dead code with archive-first strategy",
        backstory=(
            "You plan file deletions conservatively. Every file is archived "
            "before deletion. You never auto-merge to main. "
            f"Mode: {'dry-run (preview only)' if dry_run else 'LIVE'}. "
            f"Max files: {max_files}."
        ),
        llm=llm,
        verbose=False,
    )

    dead_code_summary = "\n".join(
        f"- {f.get('title', '?')}: {', '.join(f.get('affected_files', []))}"
        for f in findings[:10]
        if f.get("category", "").lower() in {"dead_code", "orphan", "deprecated"}
    )

    scan_task = Task(
        description=(
            f"Scan findings for dead code candidates:\n{dead_code_summary or '(none found)'}"
        ),
        expected_output="List of dead code candidates with file paths and finding IDs",
        agent=analyzer,
    )

    plan_task = Task(
        description=(
            "For each verified candidate, create a cleanup plan. "
            f"{'This is a DRY RUN — no files will be modified.' if dry_run else 'LIVE MODE — files will be archived and deleted.'} "
            f"Cap at {max_files} files."
        ),
        expected_output="Cleanup plan with branch name and candidate list",
        agent=janitor,
    )

    return Crew(
        agents=[analyzer, janitor],
        tasks=[scan_task, plan_task],
        process=Process.sequential,
        verbose=False,
    )

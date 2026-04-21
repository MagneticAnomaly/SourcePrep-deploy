"""CrewAI adapter for the Researcher Agent.

Wraps ResearcherEngine as a 3-agent CrewAI Crew: Analyst + Architect + PM.

Requires: pip install codrag[crewai]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from prep.agents.researcher.engine import ResearcherEngine


def build_researcher_crew(
    engine: ResearcherEngine,
    findings: List[Dict[str, Any]],
    llm: Optional[Any] = None,
    max_topics: int = 3,
) -> Any:
    """Build a CrewAI Crew for the Researcher Agent.

    Args:
        engine: ResearcherEngine instance.
        findings: Audit findings to research.
        llm: LangChain-compatible LLM. If None, uses build_llm_from_settings().
        max_topics: Maximum topics to research.

    Returns:
        A CrewAI Crew instance ready to kick off.
    """
    try:
        from crewai import Agent, Task, Crew, Process
    except ImportError:
        raise ImportError(
            "crewai is required for CrewAI adapters. "
            "Install with: pip install codrag[crewai]"
        )

    if llm is None:
        from prep.agents.shared.llm_bridge import build_llm_from_settings
        llm = build_llm_from_settings()

    analyst = Agent(
        role="Codebase Health Analyst",
        goal=f"Identify the top {max_topics} most impactful codebase issues worth fixing",
        backstory=(
            f"You have deep knowledge of this codebase. "
            f"There are {len(findings)} audit findings to review. "
            "You use CoDRAG's epistemic analysis to find issues that matter."
        ),
        llm=llm,
        verbose=False,
    )

    architect = Agent(
        role="Solutions Architect",
        goal="Research solutions for selected codebase issues",
        backstory=(
            "You are an expert at analyzing technical problems and proposing "
            "concrete implementation plans with root cause analysis, fix steps, "
            "effort estimates, and risk assessments."
        ),
        llm=llm,
        verbose=False,
    )

    pm = Agent(
        role="Technical PM",
        goal="Package research into structured project plans for Paperclip",
        backstory=(
            "You convert technical analysis into structured implementation plans "
            "with clear deliverables, priorities, and testing strategies."
        ),
        llm=llm,
        verbose=False,
    )

    findings_summary = "\n".join(
        f"- [{f.get('priority', 'P2')}] {f.get('title', 'Untitled')}"
        for f in findings[:10]
    )

    select_task = Task(
        description=(
            f"Review these {len(findings)} audit findings and select the top "
            f"{max_topics} worth researching:\n{findings_summary}"
        ),
        expected_output="List of selected topic IDs with rationale",
        agent=analyst,
    )

    research_task = Task(
        description=(
            "For each selected topic, research the root cause and propose "
            "a concrete solution with step-by-step fix procedure."
        ),
        expected_output="Detailed research analysis per topic",
        agent=architect,
    )

    formulate_task = Task(
        description=(
            "Convert each research analysis into a structured plan with: "
            "root_cause, fix_steps, effort, risk, testing_strategy."
        ),
        expected_output="Structured implementation plans",
        agent=pm,
    )

    return Crew(
        agents=[analyst, architect, pm],
        tasks=[select_task, research_task, formulate_task],
        process=Process.sequential,
        verbose=False,
    )

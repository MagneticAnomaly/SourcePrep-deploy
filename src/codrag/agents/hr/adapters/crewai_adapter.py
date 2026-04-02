"""CrewAI adapter for the Staffing Agent.

Wraps StaffingEngine as a 2-agent CrewAI Crew: Analyst + Generator.

Requires: pip install codrag[crewai]
"""
from __future__ import annotations

from typing import Any, List, Optional

from codrag.agents.hr.engine import StaffingEngine


def build_staffing_crew(
    engine: StaffingEngine,
    llm: Optional[Any] = None,
    mode: str = "list",
    role_names: Optional[List[str]] = None,
) -> Any:
    """Build a CrewAI Crew for the Staffing Agent.

    Args:
        engine: StaffingEngine instance.
        llm: LangChain-compatible LLM. If None, uses build_llm_from_settings().
        mode: Generation mode ("list", "auto", "hybrid").
        role_names: Role names for list/hybrid mode.

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
        from codrag.agents.shared.llm_bridge import build_llm_from_settings
        llm = build_llm_from_settings()

    readiness = engine.check_readiness()

    analyst = Agent(
        role="Codebase Analyst",
        goal="Analyze codebase readiness for agent role generation",
        backstory=(
            f"You are analyzing a codebase with readiness score {readiness.score:.2f}. "
            f"Modules available: {len(engine._load_modules())}. "
            f"Mode: {mode}."
        ),
        llm=llm,
        verbose=False,
    )

    generator = Agent(
        role="Role Generator",
        goal="Generate AGENTS.md, SOUL.md, and KNOWLEDGE.md for each agent role",
        backstory=(
            "You create role definitions grounded in codebase structure. "
            "Each role gets three files: behavioral instructions, identity, and knowledge."
        ),
        llm=llm,
        verbose=False,
    )

    analyze_task = Task(
        description=(
            f"Evaluate codebase readiness. Score: {readiness.score:.2f}. "
            f"Ready for list: {readiness.ready_for_list}. "
            f"Ready for auto: {readiness.ready_for_auto}. "
            f"Missing: {', '.join(readiness.missing[:3]) if readiness.missing else 'nothing'}."
        ),
        expected_output="Readiness assessment summary",
        agent=analyst,
    )

    def _llm_fn(prompt: str, system: str | None = None, **kwargs):
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))
        resp = llm.invoke(msgs)
        return resp.content, 0

    generate_task = Task(
        description=(
            f"Generate role definitions in {mode} mode. "
            f"Role names: {role_names or '(auto-inferred)'}. "
            "Use the StaffingEngine to produce AGENTS.md, SOUL.md, KNOWLEDGE.md per role."
        ),
        expected_output="List of generated role slugs",
        agent=generator,
    )

    return Crew(
        agents=[analyst, generator],
        tasks=[analyze_task, generate_task],
        process=Process.sequential,
        verbose=False,
    )

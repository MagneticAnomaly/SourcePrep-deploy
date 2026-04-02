"""LangGraph adapter for the Researcher Agent.

Wraps ResearcherEngine operations as a LangGraph StateGraph:
Ingest → Select → Research → Formulate → Push.

Requires: pip install codrag[langgraph]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from codrag.agents.researcher.engine import ResearcherEngine
from codrag.agents.shared.models import ResearchPlan


class ResearchState(TypedDict, total=False):
    """State flowing through the Researcher LangGraph."""
    findings: List[Dict[str, Any]]
    selected_topics: list
    research_results: List[str]
    plans: List[Dict[str, Any]]
    push_result: Dict[str, Any]
    error: str


def build_researcher_graph(
    engine: ResearcherEngine,
    llm: Optional[Any] = None,
    max_topics: int = 3,
):
    """Build a LangGraph StateGraph for the Researcher Agent.

    Args:
        engine: ResearcherEngine instance.
        llm: LangChain LLM instance. If None, uses build_llm_from_settings().
        max_topics: Maximum topics to research.

    Returns:
        Compiled LangGraph graph.
    """
    from langgraph.graph import StateGraph, END

    if llm is None:
        from codrag.agents.shared.llm_bridge import build_llm_from_settings
        llm = build_llm_from_settings()

    def _llm_fn(prompt: str, system: str | None = None, **kwargs):
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))
        resp = llm.invoke(msgs)
        return resp.content, 0

    def ingest(state: ResearchState) -> ResearchState:
        # Findings should be provided in the initial state
        if not state.get("findings"):
            state["error"] = "No findings provided in initial state"
        return state

    def select_topics(state: ResearchState) -> ResearchState:
        if state.get("error"):
            return state
        findings = state.get("findings", [])
        topics = engine.select_topics(findings, _llm_fn, max_topics=max_topics)
        state["selected_topics"] = topics
        return state

    def research(state: ResearchState) -> ResearchState:
        if state.get("error"):
            return state
        topics = state.get("selected_topics", [])
        results = []
        for topic in topics:
            output = engine.research_topic(topic, _llm_fn)
            results.append(output)
        state["research_results"] = results
        return state

    def formulate(state: ResearchState) -> ResearchState:
        if state.get("error"):
            return state
        topics = state.get("selected_topics", [])
        results = state.get("research_results", [])
        plans = []
        for topic, research_output in zip(topics, results):
            plan = engine.formulate_plan(topic, research_output, _llm_fn)
            plans.append(plan.to_dict())
        state["plans"] = plans
        return state

    graph = StateGraph(ResearchState)
    graph.add_node("ingest", ingest)
    graph.add_node("select_topics", select_topics)
    graph.add_node("research", research)
    graph.add_node("formulate", formulate)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "select_topics")
    graph.add_edge("select_topics", "research")
    graph.add_edge("research", "formulate")
    graph.add_edge("formulate", END)

    return graph.compile()

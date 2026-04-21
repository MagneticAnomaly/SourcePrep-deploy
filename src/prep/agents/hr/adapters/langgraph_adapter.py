"""LangGraph adapter for the Staffing Agent.

Wraps StaffingEngine operations as a LangGraph StateGraph:
Analyze → Generate → Push.

Requires: pip install prep[langgraph]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from prep.agents.hr.engine import StaffingEngine


class StaffingState(TypedDict, total=False):
    """State flowing through the Staffing LangGraph."""
    readiness_score: float
    ready_for_mode: str  # "list" | "auto" | "none"
    role_names: List[str]
    mode: str
    generated_slugs: List[str]
    error: str


def build_staffing_graph(
    engine: StaffingEngine,
    llm: Optional[Any] = None,
):
    """Build a LangGraph StateGraph for the Staffing Agent.

    Args:
        engine: StaffingEngine instance.
        llm: LangChain LLM instance. If None, uses build_llm_from_settings().

    Returns:
        Compiled LangGraph graph.
    """
    from langgraph.graph import StateGraph, END

    if llm is None:
        from prep.agents.shared.llm_bridge import build_llm_from_settings
        llm = build_llm_from_settings()

    def _llm_fn(prompt: str, system: str | None = None, **kwargs):
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))
        resp = llm.invoke(msgs)
        return resp.content, 0

    def analyze(state: StaffingState) -> StaffingState:
        report = engine.check_readiness()
        mode = "none"
        if report.ready_for_auto:
            mode = "auto"
        elif report.ready_for_list:
            mode = "list"
        state["readiness_score"] = report.score
        state["ready_for_mode"] = mode
        return state

    def generate(state: StaffingState) -> StaffingState:
        mode = state.get("mode", "list")
        role_names = state.get("role_names", [])
        try:
            if mode == "auto":
                roles = engine.auto_generate_roles(llm_fn=_llm_fn)
            elif mode == "hybrid":
                roles = engine.hybrid_generate_roles(role_names, llm_fn=_llm_fn)
            else:
                roles = engine.generate_roles(role_names, llm_fn=_llm_fn)
            state["generated_slugs"] = [r.slug for r in roles]
        except ValueError as e:
            state["error"] = str(e)
        return state

    graph = StateGraph(StaffingState)
    graph.add_node("analyze", analyze)
    graph.add_node("generate", generate)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "generate")
    graph.add_edge("generate", END)

    return graph.compile()

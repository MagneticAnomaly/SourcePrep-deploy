"""LangGraph adapter for the Digital Custodian.

Wraps CustodianEngine operations as a LangGraph StateGraph:
Scan → Verify → Plan → (optionally Execute).

Requires: pip install codrag[langgraph]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from codrag.agents.custodian.engine import CustodianEngine
from codrag.agents.shared.models import CleanupPlan


class CustodianState(TypedDict, total=False):
    """State flowing through the Custodian LangGraph."""
    findings: List[Dict[str, Any]]
    candidates: list
    verified: list
    plan: Dict[str, Any]
    dry_run: bool
    error: str


def build_custodian_graph(
    engine: CustodianEngine,
    llm: Optional[Any] = None,
    dry_run: bool = True,
    max_files: int = 20,
):
    """Build a LangGraph StateGraph for the Digital Custodian.

    Args:
        engine: CustodianEngine instance.
        llm: LangChain LLM instance. If None, uses build_llm_from_settings().
        dry_run: Whether to skip execution (default True).
        max_files: Max files in cleanup plan.

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

    def scan(state: CustodianState) -> CustodianState:
        findings = state.get("findings", [])
        if not findings:
            state["error"] = "No findings provided in initial state"
            return state
        candidates = engine.discover(findings)
        state["candidates"] = candidates
        return state

    def verify(state: CustodianState) -> CustodianState:
        if state.get("error"):
            return state
        candidates = state.get("candidates", [])
        verified = engine.verify_candidates(candidates, _llm_fn)
        state["verified"] = verified
        return state

    def plan(state: CustodianState) -> CustodianState:
        if state.get("error"):
            return state
        verified = state.get("verified", [])
        cleanup_plan = engine.plan_cleanup(verified, dry_run=dry_run, max_files=max_files)
        state["plan"] = cleanup_plan.to_dict()
        state["dry_run"] = cleanup_plan.dry_run
        return state

    graph = StateGraph(CustodianState)
    graph.add_node("scan", scan)
    graph.add_node("verify", verify)
    graph.add_node("plan", plan)

    graph.set_entry_point("scan")
    graph.add_edge("scan", "verify")
    graph.add_edge("verify", "plan")
    graph.add_edge("plan", END)

    return graph.compile()

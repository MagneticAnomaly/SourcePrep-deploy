"""Circular dependency analyzer — detects import cycles using Tarjan's algorithm."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Tuple

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class CircularDependencyAnalyzer(BaseAnalyzer):
    name = "circular_deps"
    category = "architecture"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Build file-level import adjacency (file_path → set of imported file_paths)
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in ctx.edges:
            if edge.get("kind") != "imports":
                continue
            src_node = ctx.nodes.get(edge.get("source", ""), {})
            tgt_node = ctx.nodes.get(edge.get("target", ""), {})
            src_path = src_node.get("file_path", "")
            tgt_path = tgt_node.get("file_path", "")
            if src_path and tgt_path and src_path != tgt_path:
                # Skip external modules (no file_path)
                if tgt_node.get("kind") == "external_module":
                    continue
                adj[src_path].add(tgt_path)

        if not adj:
            return findings

        # Tarjan's SCC algorithm
        cycles = _find_sccs(adj)

        for cycle in cycles:
            if len(cycle) < 2:
                continue  # Single-node SCCs aren't cycles

            severity = "critical" if len(cycle) >= 4 else "warning" if len(cycle) >= 2 else "info"

            cycle_display = " → ".join(cycle[:8])
            if len(cycle) > 8:
                cycle_display += f" → ... ({len(cycle)} total)"

            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"Circular dependency: {len(cycle)} files",
                description=(
                    f"Import cycle detected: {cycle_display}. "
                    f"Circular dependencies make the codebase harder to reason about, "
                    f"test in isolation, and can cause runtime import errors."
                ),
                file_paths=list(cycle)[:20],
                evidence={
                    "cycle_length": len(cycle),
                    "cycle": list(cycle)[:20],
                },
                suggested_action=(
                    "Break the cycle by extracting shared interfaces or using "
                    "dependency injection. Identify the lowest-cost edge to remove."
                ),
            ))

        findings.sort(key=lambda f: -f.evidence.get("cycle_length", 0))
        return findings


def _find_sccs(adj: Dict[str, Set[str]]) -> List[List[str]]:
    """Find all strongly connected components using Tarjan's algorithm.

    Returns only SCCs with size >= 2 (actual cycles).
    """
    index_counter = [0]
    stack: List[str] = []
    lowlink: Dict[str, int] = {}
    index: Dict[str, int] = {}
    on_stack: Set[str] = set()
    sccs: List[List[str]] = []

    all_nodes = set(adj.keys())
    for targets in adj.values():
        all_nodes |= targets

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj.get(v, set()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) >= 2:
                sccs.append(scc)

    # Use iterative approach for large graphs to avoid stack overflow
    import sys
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, len(all_nodes) + 1000))
    try:
        for node in all_nodes:
            if node not in index:
                strongconnect(node)
    finally:
        sys.setrecursionlimit(old_limit)

    return sccs

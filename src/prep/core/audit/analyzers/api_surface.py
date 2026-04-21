"""API surface analyzer — finds exported symbols lacking documentation coverage."""
from __future__ import annotations

from typing import Dict, List, Set

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class ApiSurfaceAnalyzer(BaseAnalyzer):
    name = "api_surface"
    category = "coverage"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Identify public symbols (is_public=True or high in-degree)
        public_symbols: List[Dict] = []
        undocumented: List[Dict] = []

        for nid, node in ctx.symbol_nodes.items():
            meta = node.get("metadata", {})
            is_public = meta.get("is_public", True)
            if not is_public:
                continue

            sym_type = meta.get("symbol_type", "")
            if sym_type in ("method",):
                continue  # Only flag top-level classes/functions

            file_path = node.get("file_path", "")
            name = node.get("name", "")
            docstring = meta.get("docstring", "")

            public_symbols.append({
                "node_id": nid,
                "name": name,
                "file_path": file_path,
                "type": sym_type,
                "has_docstring": bool(docstring),
            })

            if not docstring:
                undocumented.append({
                    "name": name,
                    "file_path": file_path,
                    "type": sym_type,
                })

        if not public_symbols:
            return findings

        total = len(public_symbols)
        documented = total - len(undocumented)
        doc_pct = round(100 * documented / total, 1) if total > 0 else 0.0

        if len(undocumented) == 0:
            return findings

        severity = "warning" if doc_pct < 50 else "info"

        findings.append(Finding(
            analyzer=self.name,
            severity=severity,
            category=self.category,
            title=f"API documentation: {doc_pct}% of public symbols have docstrings",
            description=(
                f"{len(undocumented)} public symbols lack docstrings out of "
                f"{total} total. Documentation coverage is {doc_pct}%."
            ),
            file_paths=list(set(u["file_path"] for u in undocumented))[:15],
            evidence={
                "total_public": total,
                "documented": documented,
                "undocumented": len(undocumented),
                "coverage_pct": doc_pct,
                "top_undocumented": [
                    {"name": u["name"], "file": u["file_path"], "type": u["type"]}
                    for u in undocumented[:20]
                ],
            },
            suggested_action="Add docstrings to public classes and functions, prioritizing API-facing code.",
        ))

        return findings

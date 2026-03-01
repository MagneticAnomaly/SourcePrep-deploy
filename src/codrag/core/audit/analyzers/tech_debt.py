"""Tech debt aggregator — surfaces tech_debt fields from epistemic enrichment."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class TechDebtAnalyzer(BaseAnalyzer):
    name = "tech_debt"
    category = "quality"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Collect per-file tech debt from epistemic entries
        file_debts: List[Dict] = []
        for nid, entry in ctx.epistemic.items():
            debts = entry.get("tech_debt") or []
            if not debts:
                continue
            node = ctx.nodes.get(nid, {})
            file_path = node.get("file_path", "")
            if not file_path:
                continue
            file_debts.append({
                "file_path": file_path,
                "items": debts if isinstance(debts, list) else [str(debts)],
                "node_id": nid,
            })

        if not file_debts:
            return findings

        # Aggregate by module
        module_debts: Dict[str, List[Dict]] = defaultdict(list)
        for fd in file_debts:
            mod = ctx.module_for_file(fd["file_path"])
            mod_name = mod.get("name", "unassigned") if mod else "unassigned"
            module_debts[mod_name].append(fd)

        # Per-module finding
        for mod_name, debts in sorted(module_debts.items(), key=lambda kv: -len(kv[1])):
            all_items = []
            all_files = []
            for d in debts:
                all_items.extend(d["items"])
                all_files.append(d["file_path"])

            severity = "warning" if len(all_items) >= 5 else "info"

            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"Tech debt in module '{mod_name}': {len(all_items)} items across {len(all_files)} files",
                description=(
                    f"Module '{mod_name}' has {len(all_items)} tech debt items "
                    f"identified during deep enrichment:\n"
                    + "\n".join(f"  - {item}" for item in all_items[:10])
                    + (f"\n  ... and {len(all_items) - 10} more" if len(all_items) > 10 else "")
                ),
                file_paths=all_files[:10],
                evidence={
                    "module": mod_name,
                    "item_count": len(all_items),
                    "file_count": len(all_files),
                    "items": all_items[:20],
                },
                suggested_action="Review and prioritize tech debt items for remediation.",
            ))

        # Also surface module-level tech_debt_summary from cluster synthesis
        for mod in ctx.modules:
            tds = mod.get("tech_debt_summary")
            if not tds:
                continue
            mod_name = mod.get("name", mod.get("module_id", ""))
            findings.append(Finding(
                analyzer=self.name,
                severity="info",
                category=self.category,
                title=f"Module-level debt: {mod_name}",
                description=f"Cluster synthesis identified: {tds}",
                file_paths=mod.get("member_files", [])[:5],
                evidence={"module": mod_name, "synthesis_summary": tds},
                suggested_action="Review module-level tech debt assessment.",
            ))

        return findings

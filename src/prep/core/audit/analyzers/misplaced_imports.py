"""Misplaced import analyzer — detects cross-module imports that violate boundaries."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Set

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class MisplacedImportAnalyzer(BaseAnalyzer):
    name = "misplaced_imports"
    category = "architecture"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        if not ctx.modules:
            return findings

        # Build file → module mapping
        file_to_module: Dict[str, str] = {}
        for mod in ctx.modules:
            mod_id = mod.get("module_id", "")
            for fp in mod.get("member_files", []):
                file_to_module[fp] = mod_id

        # Build module → module dependency counts via import edges
        cross_module_imports: Dict[str, List[Dict]] = defaultdict(list)

        for edge in ctx.edges:
            if edge.get("kind") != "imports":
                continue

            src_id = edge.get("source", "")
            tgt_id = edge.get("target", "")

            # Resolve to file paths
            src_node = ctx.nodes.get(src_id, {})
            tgt_node = ctx.nodes.get(tgt_id, {})
            src_path = src_node.get("file_path", "")
            tgt_path = tgt_node.get("file_path", "")

            if not src_path or not tgt_path:
                continue

            src_mod = file_to_module.get(src_path)
            tgt_mod = file_to_module.get(tgt_path)

            if src_mod and tgt_mod and src_mod != tgt_mod:
                cross_module_imports[f"{src_mod}->{tgt_mod}"].append({
                    "source_file": src_path,
                    "target_file": tgt_path,
                    "import": edge.get("metadata", {}).get("import", ""),
                })

        # Flag module pairs with many cross-boundary imports
        for pair_key, imports in sorted(
            cross_module_imports.items(), key=lambda kv: -len(kv[1])
        ):
            src_mod, tgt_mod = pair_key.split("->", 1)
            count = len(imports)

            if count >= 10:
                severity = "warning"
            elif count >= 5:
                severity = "info"
            else:
                continue

            # Check for single-file bottleneck (like the LLMClient case)
            target_files = [i["target_file"] for i in imports]
            target_counts: Dict[str, int] = {}
            for tf in target_files:
                target_counts[tf] = target_counts.get(tf, 0) + 1

            bottleneck = max(target_counts, key=target_counts.get) if target_counts else ""
            bottleneck_count = target_counts.get(bottleneck, 0)

            # If >60% of imports target one file, it's a misplaced dependency
            if bottleneck_count > count * 0.6 and bottleneck_count >= 3:
                severity = "critical" if bottleneck_count >= 5 else "warning"
                findings.append(Finding(
                    analyzer=self.name,
                    severity=severity,
                    category=self.category,
                    title=f"Dependency bottleneck: {bottleneck} imported by {src_mod}",
                    description=(
                        f"{bottleneck_count} files in module '{src_mod}' import from "
                        f"'{bottleneck}' (module '{tgt_mod}'). This file may contain "
                        f"shared utilities that should be extracted into their own module."
                    ),
                    file_paths=[bottleneck] + list(set(i["source_file"] for i in imports if i["target_file"] == bottleneck))[:5],
                    evidence={
                        "source_module": src_mod,
                        "target_module": tgt_mod,
                        "bottleneck_file": bottleneck,
                        "bottleneck_import_count": bottleneck_count,
                        "total_cross_imports": count,
                    },
                    suggested_action=(
                        f"Extract shared code from {bottleneck} into a dedicated module "
                        f"that both '{src_mod}' and '{tgt_mod}' can depend on cleanly."
                    ),
                ))
            else:
                all_files = list(set(
                    i["source_file"] for i in imports
                ) | set(
                    i["target_file"] for i in imports
                ))
                findings.append(Finding(
                    analyzer=self.name,
                    severity=severity,
                    category=self.category,
                    title=f"High cross-module coupling: {src_mod} → {tgt_mod} ({count} imports)",
                    description=(
                        f"Module '{src_mod}' has {count} import edges into module '{tgt_mod}'. "
                        f"This may indicate tight coupling or a missing abstraction boundary."
                    ),
                    file_paths=all_files[:10],
                    evidence={
                        "source_module": src_mod,
                        "target_module": tgt_mod,
                        "import_count": count,
                        "top_targets": dict(sorted(target_counts.items(), key=lambda kv: -kv[1])[:5]),
                    },
                    suggested_action="Review module boundaries. Consider extracting shared interfaces.",
                ))

        return findings

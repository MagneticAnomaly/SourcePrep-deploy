"""Naming consistency analyzer — checks symbol names against domain vocabulary."""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Set

from ..models import AuditContext, Finding
from . import BaseAnalyzer


class NamingConsistencyAnalyzer(BaseAnalyzer):
    name = "naming_consistency"
    category = "naming"

    def analyze(self, ctx: AuditContext) -> List[Finding]:
        findings: List[Finding] = []

        # Collect naming conventions per language
        conventions: Dict[str, Counter] = {}  # language → Counter of (pattern_type)
        violations: List[Dict] = []

        for nid, node in ctx.symbol_nodes.items():
            sym_name = node.get("name", "")
            sym_type = node.get("metadata", {}).get("symbol_type", "")
            lang = node.get("language", "")
            file_path = node.get("file_path", "")

            if not sym_name or not lang:
                continue

            pattern = _classify_naming(sym_name)

            if lang not in conventions:
                conventions[lang] = Counter()
            conventions[lang][f"{sym_type}:{pattern}"] += 1

            # Check language-specific conventions
            violation = _check_convention(sym_name, sym_type, lang)
            if violation:
                violations.append({
                    "name": sym_name,
                    "type": sym_type,
                    "language": lang,
                    "file_path": file_path,
                    "violation": violation,
                })

        # Group violations by type
        by_violation: Dict[str, List[Dict]] = {}
        for v in violations:
            by_violation.setdefault(v["violation"], []).append(v)

        for violation_type, items in sorted(by_violation.items(), key=lambda kv: -len(kv[1])):
            if len(items) < 3:
                continue  # Only flag patterns, not individual cases

            severity = "info"
            sample_names = [i["name"] for i in items[:5]]

            findings.append(Finding(
                analyzer=self.name,
                severity=severity,
                category=self.category,
                title=f"Naming convention: {violation_type} ({len(items)} occurrences)",
                description=(
                    f"{len(items)} symbols violate the expected naming convention: "
                    f"{violation_type}. Examples: {', '.join(sample_names)}"
                ),
                file_paths=list(set(i["file_path"] for i in items))[:10],
                evidence={
                    "violation_type": violation_type,
                    "count": len(items),
                    "examples": [{"name": i["name"], "file": i["file_path"]} for i in items[:10]],
                },
                suggested_action="Review naming conventions for consistency.",
            ))

        return findings


def _classify_naming(name: str) -> str:
    """Classify a name's casing pattern."""
    if "_" in name and name == name.lower():
        return "snake_case"
    if "_" in name and name == name.upper():
        return "UPPER_SNAKE"
    if name[0].isupper() and "_" not in name:
        return "PascalCase"
    if name[0].islower() and "_" not in name and any(c.isupper() for c in name):
        return "camelCase"
    if name == name.lower():
        return "lowercase"
    return "mixed"


def _check_convention(name: str, sym_type: str, language: str) -> str:
    """Check if a symbol name follows language conventions. Returns violation string or empty."""
    if language == "python":
        if sym_type == "class" and not name[0].isupper():
            return "Python classes should be PascalCase"
        if sym_type in ("function", "method") and name[0].isupper() and not name.startswith("_"):
            return "Python functions should be snake_case"
    elif language in ("typescript", "javascript"):
        if sym_type == "class" and not name[0].isupper():
            return "JS/TS classes should be PascalCase"
    elif language == "rust":
        if sym_type in ("function",) and name[0].isupper():
            return "Rust functions should be snake_case"
        if sym_type == "class" and name[0].islower():
            return "Rust structs/enums should be PascalCase"
    elif language == "go":
        # Go uses PascalCase for exported, camelCase for unexported
        pass
    return ""

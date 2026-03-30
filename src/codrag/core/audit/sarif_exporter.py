"""
SARIF 2.1.0 exporter for CoDRAG ActionItems (Phase 63).

Converts ActionItems to OASIS SARIF format for consumption by:
- GitHub Code Scanning (upload via github/codeql-action/upload-sarif)
- VS Code SARIF Viewer extension
- IntelliJ SARIF support
- Azure DevOps code analysis

SARIF spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from codrag.core.audit.action_item import ActionItem

# ── Constants ────────────────────────────────────────────────────────

SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
    "main/sarif-2.1/schema/sarif-schema-2.1.0.json"
)
SARIF_VERSION = "2.1.0"
CODRAG_INFO_URI = "https://codrag.dev"


# ── Rule catalog ─────────────────────────────────────────────────────

def _build_rules(items: List[ActionItem]) -> List[Dict[str, Any]]:
    """Build SARIF rule descriptors from ActionItems.

    Each unique (source, analyzer) pair becomes a SARIF rule.
    """
    seen_rules: Set[str] = set()
    rules: List[Dict[str, Any]] = []

    for item in items:
        rule_id = item.id.split("-")[0] + "-" + (item.analyzer or "unknown")
        if rule_id in seen_rules:
            continue
        seen_rules.add(rule_id)

        rule: Dict[str, Any] = {
            "id": rule_id,
            "name": _to_pascal_case(item.analyzer or item.source),
            "shortDescription": {"text": f"CoDRAG {item.source} finding ({item.analyzer})"},
            "properties": {
                "tags": [item.category, item.source],
            },
        }
        rules.append(rule)

    return rules


def _to_pascal_case(s: str) -> str:
    """Convert snake_case to PascalCase for SARIF rule names."""
    return "".join(word.capitalize() for word in s.split("_"))


# ── Main export ──────────────────────────────────────────────────────

def action_items_to_sarif(
    items: List[ActionItem],
    tool_version: str = "2026.1",
    tool_name: str = "CoDRAG",
) -> Dict[str, Any]:
    """Convert a list of ActionItems to a SARIF 2.1.0 JSON document.

    Args:
        items: ActionItems to export (only active items recommended).
        tool_version: Version string for the CoDRAG tool driver.
        tool_name: Name of the tool (default: CoDRAG).

    Returns:
        SARIF JSON as a Python dict.
    """
    # Filter to active items only
    active_items = [i for i in items if i.state != "dismissed"]

    sarif: Dict[str, Any] = {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "version": tool_version,
                        "informationUri": CODRAG_INFO_URI,
                        "rules": _build_rules(active_items),
                    }
                },
                "results": [item.to_sarif_result() for item in active_items],
            }
        ],
    }

    return sarif


def write_sarif_file(
    items: List[ActionItem],
    output_path: Path,
    tool_version: str = "2026.1",
) -> Path:
    """Write ActionItems to a SARIF 2.1.0 JSON file.

    Args:
        items: ActionItems to export.
        output_path: Where to write the SARIF file.
        tool_version: Version string for the CoDRAG tool driver.

    Returns:
        The output path (for chaining).
    """
    sarif = action_items_to_sarif(items, tool_version)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(sarif, indent=2), encoding="utf-8")
    return output_path


def sarif_to_json_string(
    items: List[ActionItem],
    tool_version: str = "2026.1",
    indent: int = 2,
) -> str:
    """Convert ActionItems to a SARIF JSON string.

    Convenience function for HTTP API responses.
    """
    sarif = action_items_to_sarif(items, tool_version)
    return json.dumps(sarif, indent=indent)
"""
Description: SARIF exporter for CoDRAG ActionItems (Phase 63).
"""

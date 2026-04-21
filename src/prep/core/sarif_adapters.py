"""Tool-specific enrichment adapters for SARIF sources.

Different SARIF-emitting tools have different characteristics. Adapters
customize the emphasis of Prep enrichment based on the source tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolAdapter:
    """Configuration for how to emphasize enrichment for a specific tool."""
    tool_name: str
    focus: str              # What Prep signal to emphasize in recommendations
    severity_note: str      # Context about the tool's severity scale


# Known tool adapters
_ADAPTERS = {
    "semgrep": ToolAdapter(
        tool_name="semgrep",
        focus="blast_radius",
        severity_note="Security-focused, high-confidence rules. Dependent count indicates blast radius of a vulnerability.",
    ),
    "codeql": ToolAdapter(
        tool_name="codeql",
        focus="import_chain",
        severity_note="Deep dataflow analysis. Import chain context shows how tainted data flows through modules.",
    ),
    "ruff": ToolAdapter(
        tool_name="ruff",
        focus="hub_status",
        severity_note="Style and complexity checks. Complexity in a hub file matters more than in a leaf.",
    ),
    "eslint": ToolAdapter(
        tool_name="eslint",
        focus="hub_status",
        severity_note="Frontend convention checks. Hub status shows component importance.",
    ),
    "sonarqube": ToolAdapter(
        tool_name="sonarqube",
        focus="composite",
        severity_note="Broad coverage tool. Prep risk score composites structural + epistemological signals.",
    ),
    "pylint": ToolAdapter(
        tool_name="pylint",
        focus="hub_status",
        severity_note="Python linter. Hub status prioritizes findings in structurally important files.",
    ),
}

_DEFAULT_ADAPTER = ToolAdapter(
    tool_name="unknown",
    focus="composite",
    severity_note="Unknown tool. Prep provides standard structural enrichment.",
)


def get_adapter(tool_name: str) -> ToolAdapter:
    """Get the adapter for a tool, falling back to default for unknown tools."""
    if not tool_name:
        return _DEFAULT_ADAPTER
    normalized = tool_name.lower().strip()
    # Try exact match first, then prefix match
    if normalized in _ADAPTERS:
        return _ADAPTERS[normalized]
    for key, adapter in _ADAPTERS.items():
        if normalized.startswith(key):
            return adapter
    return _DEFAULT_ADAPTER


def get_tool_context(tool_name: str) -> str:
    """Get a context note about the source tool for inclusion in enrichment."""
    adapter = get_adapter(tool_name)
    return adapter.severity_note

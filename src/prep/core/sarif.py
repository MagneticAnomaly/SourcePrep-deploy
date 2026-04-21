"""SARIF parser, converter, and auto-detection for CoDRAG enrichment.

Supports SARIF v2.0.0 and v2.1.0.  Converts SARIF results into the simple
finding schema used by :func:`codrag.core.enrichment.enrich_findings`, and
converts enriched results back into valid SARIF with CoDRAG property bags.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from prep.core.enrichment import EnrichmentResult

# Hard limits to prevent resource exhaustion.
_MAX_RESULTS = 1000
_MAX_SERIALIZED_BYTES = 5 * 1024 * 1024  # 5 MB

# SARIF level → simple severity mapping.
_LEVEL_MAP: Dict[str, str] = {
    "error": "error",
    "warning": "warning",
    "note": "info",
    "none": "info",
}


@dataclass
class SarifRun:
    """Parsed representation of a single SARIF run."""

    tool_name: str
    results: List[Dict[str, Any]]  # Simple schema findings
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SarifInput:
    """Parsed representation of a SARIF document."""

    version: str
    runs: List[SarifRun]
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def is_sarif(data: Any) -> bool:
    """Detect if *data* looks like SARIF input (dict with version/runs or $schema)."""
    if not isinstance(data, dict):
        return False
    if "$schema" in data and "sarif" in str(data.get("$schema", "")).lower():
        return True
    if "version" in data and "runs" in data and isinstance(data.get("runs"), list):
        return True
    return False


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _normalize_uri(uri: str) -> str:
    """Strip ``file:///`` prefix from artifact URIs."""
    if uri.startswith("file:///"):
        return uri[len("file:///"):]
    return uri


def parse_sarif(data: Dict[str, Any]) -> SarifInput:
    """Parse a SARIF dict into a :class:`SarifInput`.

    Raises:
        ValueError: If the input exceeds size limits.
    """
    # Size guard (serialized bytes).
    serialized = json.dumps(data, default=str)
    if len(serialized.encode()) > _MAX_SERIALIZED_BYTES:
        raise ValueError(
            f"SARIF input exceeds the {_MAX_SERIALIZED_BYTES // (1024 * 1024)} MB size limit."
        )

    version = data.get("version", "2.1.0")
    raw_runs: List[Dict[str, Any]] = data.get("runs", [])

    # Count total results for the limit check.
    total_results = sum(len(run.get("results", [])) for run in raw_runs)
    if total_results > _MAX_RESULTS:
        raise ValueError(
            f"SARIF input contains {total_results} results, exceeding the limit of {_MAX_RESULTS}."
        )

    parsed_runs: List[SarifRun] = []
    for raw_run in raw_runs:
        tool_name = raw_run.get("tool", {}).get("driver", {}).get("name", "unknown")
        simple_results: List[Dict[str, Any]] = []

        for result in raw_run.get("results", []):
            locations = result.get("locations")
            if not locations:
                continue

            phys = locations[0].get("physicalLocation", {})
            artifact = phys.get("artifactLocation", {})
            region = phys.get("region", {})
            uri = artifact.get("uri", "")
            if not uri:
                continue

            file_path = _normalize_uri(uri)
            line = region.get("startLine", 0)
            message = result.get("message", {}).get("text", "")
            level = result.get("level", "warning")
            severity = _LEVEL_MAP.get(level, "warning")

            simple_results.append(
                {
                    "file": file_path,
                    "line": line,
                    "message": message,
                    "severity": severity,
                    "tool": tool_name,
                }
            )

        parsed_runs.append(SarifRun(tool_name=tool_name, results=simple_results, raw=raw_run))

    return SarifInput(version=version, runs=parsed_runs, raw=data)


# ---------------------------------------------------------------------------
# Flatten to simple schema
# ---------------------------------------------------------------------------


def sarif_to_simple(sarif_input: SarifInput) -> List[Dict[str, Any]]:
    """Flatten all runs' results into a single list of simple finding dicts."""
    findings: List[Dict[str, Any]] = []
    for run in sarif_input.runs:
        findings.extend(run.results)
    return findings


# ---------------------------------------------------------------------------
# Enriched → SARIF conversion
# ---------------------------------------------------------------------------


def enriched_to_sarif(
    sarif_input: SarifInput,
    enrichment_result: EnrichmentResult,
) -> Dict[str, Any]:
    """Inject CoDRAG enrichment data back into a SARIF structure.

    Returns a new SARIF dict (does not mutate the original).  Each result that
    was enriched gets a ``properties.codrag`` dict.  Each run gets a summary
    in ``properties.codrag.summary``.
    """
    output = copy.deepcopy(sarif_input.raw)
    output["version"] = "2.1.0"

    # Build a lookup from the enriched findings (order-preserving by run).
    enriched_iter = iter(enrichment_result.findings)

    for run_idx, run in enumerate(sarif_input.runs):
        out_run = output["runs"][run_idx]

        # Track per-run stats for the summary.
        run_enriched = 0
        run_total = 0
        run_high_risk = 0

        # Walk only the results that were *not* skipped during parsing (i.e.
        # those that had valid locations).  The parsed run.results list and the
        # enriched findings are in the same order.
        kept_result_indices = _kept_result_indices(run.raw)
        for kept_idx in kept_result_indices:
            enriched_finding = next(enriched_iter)
            out_result = out_run["results"][kept_idx]
            run_total += 1

            if enriched_finding.codrag is not None:
                # Inject tool context from adapter
                from prep.core.sarif_adapters import get_tool_context
                tool_ctx = get_tool_context(run.tool_name)
                enriched_finding.codrag["tool_context"] = tool_ctx

                out_result.setdefault("properties", {})
                out_result["properties"]["codrag"] = enriched_finding.codrag
                run_enriched += 1
                if enriched_finding.codrag.get("risk_score", 0) >= 0.5:
                    run_high_risk += 1

        # Per-run summary with per-run high_risk count.
        key_insight = enrichment_result.summary.get("key_insight", "")
        out_run.setdefault("properties", {})
        out_run["properties"]["codrag"] = {
            "summary": {
                "total": run_total,
                "enriched": run_enriched,
                "unenriched": run_total - run_enriched,
                "high_risk": run_high_risk,
                "key_insights": [key_insight] if key_insight else [],
            }
        }

    return output


def _kept_result_indices(raw_run: Dict[str, Any]) -> List[int]:
    """Return indices of results in *raw_run* that have valid locations."""
    indices: List[int] = []
    for idx, result in enumerate(raw_run.get("results", [])):
        locations = result.get("locations")
        if not locations:
            continue
        phys = locations[0].get("physicalLocation", {})
        uri = phys.get("artifactLocation", {}).get("uri", "")
        if uri:
            indices.append(idx)
    return indices

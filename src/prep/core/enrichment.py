"""Enrichment engine — annotates external findings with Prep structural context.

Each incoming finding (file, line, message, severity, tool) is looked up in the
provided context dict (keyed by file path).  When found, structural signals
(dependents, hub_status, concepts, observations) are used to compute a risk
score and generate a human-readable recommendation via the existing
recommendations module.  Missing files trigger a stale_data_warning on the
result so callers know to re-run indexing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from prep.core.audit.recommendations import compute_risk_score, generate_recommendation

# Files with risk_score at or above this threshold count as "high risk".
_HIGH_RISK_THRESHOLD = 0.5

# Mapping of hub_status label to approximate hub_percentile used for risk score.
_HUB_PERCENTILE = {
    "critical": 1.0,
    "high": 0.75,
    "moderate": 0.50,
    "low": 0.10,
}


@dataclass
class EnrichedFinding:
    """An external lint/analysis finding annotated with optional Prep context."""

    file: str
    line: int
    message: str
    severity: str
    tool: str
    prep: Optional[Dict] = field(default=None)

    def to_dict(self) -> Dict:
        d: Dict = {
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "severity": self.severity,
            "tool": self.tool,
        }
        if self.prep is not None:
            d["prep"] = self.prep
        return d


@dataclass
class EnrichmentResult:
    """Wraps a list of enriched findings together with a summary."""

    findings: List[EnrichedFinding]
    summary: Dict
    stale_data_warning: bool = False

    def to_dict(self) -> Dict:
        d: Dict = {
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "stale_data_warning": self.stale_data_warning,
        }
        if self.stale_data_warning:
            d["message"] = (
                "Looks like you have stale data, Prep recommends running enrichment again."
            )
        return d


def enrich_findings(
    findings: List[Dict],
    context: Dict[str, Dict],
    max_findings: int = 200,
) -> EnrichmentResult:
    """Annotate external findings with Prep structural context.

    Args:
        findings: List of dicts with keys: file, line, message, severity, tool.
        context: Mapping of file_path → structural data dict with keys:
                 dependents, hub_status, module, concepts, observations.
        max_findings: Maximum number of findings to process (excess are dropped).

    Returns:
        EnrichmentResult containing enriched findings and a summary dict.
    """
    capped = findings[:max_findings]

    enriched_findings: List[EnrichedFinding] = []
    stale_data_warning = False
    high_risk_count = 0

    for raw in capped:
        file_path: str = raw.get("file", "")
        ctx = context.get(file_path)

        prep_annotation: Optional[Dict] = None
        if ctx is not None:
            hub_status: str = ctx.get("hub_status", "low")
            dependents: int = ctx.get("dependents", 0)
            concepts: List[str] = ctx.get("concepts", [])
            observations: List[str] = ctx.get("observations", [])
            module: str = ctx.get("module", "")

            hub_percentile = _HUB_PERCENTILE.get(hub_status, 0.0)
            has_constraint = any("constraint" in c.lower() for c in concepts)
            has_architecture = any(
                any(kw in c.lower() for kw in ("architect", "refactor", "plan", "design"))
                for c in concepts
            )
            observation_score = min(1.0, len(observations) / 5.0) if observations else 0.0

            risk_score = compute_risk_score(
                hub_percentile=hub_percentile,
                has_constraint_concept=has_constraint,
                has_architecture_concept=has_architecture,
                observation_score=observation_score,
            )

            recommendation = generate_recommendation(
                hub_status=hub_status,
                dependents=dependents,
                concepts=concepts,
                observations=observations,
            )

            prep_annotation = {
                "dependents": dependents,
                "hub_status": hub_status,
                "module": module,
                "concepts": concepts,
                "observations": observations,
                "risk_score": risk_score,
                "recommendation": recommendation,
            }

            if risk_score >= _HIGH_RISK_THRESHOLD:
                high_risk_count += 1
        else:
            stale_data_warning = True

        enriched_findings.append(
            EnrichedFinding(
                file=file_path,
                line=raw.get("line", 0),
                message=raw.get("message", ""),
                severity=raw.get("severity", ""),
                tool=raw.get("tool", ""),
                prep=prep_annotation,
            )
        )

    enriched_count = sum(1 for f in enriched_findings if f.prep is not None)
    unenriched_count = len(enriched_findings) - enriched_count

    # Generate key_insight from highest-risk finding
    key_insight = ""
    enriched_with_scores = [f for f in enriched_findings if f.prep is not None]
    if enriched_with_scores:
        top = max(enriched_with_scores, key=lambda f: f.prep["risk_score"])
        tc = top.prep
        if tc["risk_score"] >= _HIGH_RISK_THRESHOLD:
            key_insight = (
                f"{top.file} is the highest-risk finding "
                f"({tc['hub_status']} hub, {tc['dependents']} dependents"
                + (f", {len(tc['concepts'])} related concepts" if tc["concepts"] else "")
                + ")."
            )

    summary: Dict = {
        "total": len(enriched_findings),
        "enriched": enriched_count,
        "unenriched": unenriched_count,
        "high_risk": high_risk_count,
        "key_insight": key_insight,
    }

    return EnrichmentResult(
        findings=enriched_findings,
        summary=summary,
        stale_data_warning=stale_data_warning,
    )


def enrich_sarif(
    sarif_data: Dict,
    context: Dict[str, Dict],
    max_findings: int = 200,
) -> Dict:
    """Enrich SARIF input with Prep structural context.

    Orchestrates: parse SARIF → convert to simple → enrich → convert back to SARIF.

    Args:
        sarif_data: Raw SARIF dict (version 2.0 or 2.1.0)
        context: File path → structural context mapping (same as enrich_findings)
        max_findings: Maximum findings to process

    Returns:
        Enriched SARIF dict with Prep property bags injected.
    """
    from prep.core.sarif import parse_sarif, sarif_to_simple, enriched_to_sarif

    sarif_input = parse_sarif(sarif_data)
    simple_findings = sarif_to_simple(sarif_input)

    # Enrich using the standard pipeline
    result = enrich_findings(simple_findings, context, max_findings=max_findings)

    # Convert enriched results back to SARIF
    return enriched_to_sarif(sarif_input, result)

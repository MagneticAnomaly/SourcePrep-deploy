"""Template-based recommendation generator for audit findings.

Composes fragments based on structural signals (hub status, concepts, observations).
LLM recommendations are gated behind the experimental toggle.
"""
from __future__ import annotations

from typing import Dict, List, Optional


# Default weights — configurable via settings
_WEIGHTS = {
    "hub": 0.40,
    "concept": 0.30,
    "observation": 0.20,
    "churn": 0.10,
}


def compute_risk_score(
    hub_percentile: float,
    has_constraint_concept: bool = False,
    has_architecture_concept: bool = False,
    observation_score: float = 0.0,
    churn_score: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute composite risk score for a file.

    Args:
        hub_percentile: 0-1, where the file sits in the dependent count distribution
        has_constraint_concept: True if an active constraint concept is anchored here
        has_architecture_concept: True if an active architecture concept is anchored here
        observation_score: 0-1, based on recency and frequency of observations
        churn_score: 0-1, based on git change frequency
        weights: Optional override for weight dict

    Returns:
        Float 0-1 risk score.
    """
    w = weights or _WEIGHTS
    concept_score = 1.0 if has_constraint_concept else (0.5 if has_architecture_concept else 0.0)
    raw = (
        w["hub"] * hub_percentile
        + w["concept"] * concept_score
        + w["observation"] * observation_score
        + w["churn"] * churn_score
    )
    return max(0.0, min(1.0, raw))


def generate_recommendation(
    hub_status: str,
    dependents: int,
    concepts: List[str],
    observations: List[str],
    experimental_llm: bool = False,
) -> str:
    """Generate a context-aware recommendation from structural signals.

    Args:
        hub_status: "critical" | "high" | "moderate" | "low"
        dependents: Number of files that depend on this file
        concepts: Related concept titles/assertions
        observations: Related observation summaries
        experimental_llm: If True, also generate LLM recommendation (future)

    Returns:
        Human-readable recommendation string.
    """
    parts: List[str] = []

    # Hub status fragment
    if hub_status == "critical":
        parts.append(f"Critical hub file \u2014 changes here ripple to {dependents} dependents.")
    elif hub_status == "high":
        parts.append(f"High-impact file with {dependents} dependents.")
    elif hub_status == "moderate":
        parts.append(f"Moderate coupling ({dependents} dependents).")
    else:
        parts.append(f"Low coupling ({dependents} dependents). Minimal blast radius.")

    # Concept fragment
    if concepts:
        parts.append(f"Existing concept: {concepts[0]}")
        if len(concepts) > 1:
            parts.append(f"({len(concepts) - 1} more related concepts.)")
    elif hub_status in ("critical", "high"):
        parts.append("No architectural plan documented. Consider creating a concept before modifying.")

    # Observation fragment
    if observations:
        parts.append(f"Flagged {len(observations)} times in observations.")

    # Composite advice
    if concepts and hub_status in ("critical", "high"):
        parts.append("Prioritize \u2014 high structural impact with planned work already documented.")
    elif not concepts and hub_status in ("critical", "high"):
        parts.append("High impact but undocumented. Proceed with caution.")

    return " ".join(parts)

"""Observation → Concept promotion for RunPrep.

Suggests promoting durable observations (decisions, patterns, assumptions)
into structured concepts. The human confirms and fills in the assertion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


_PROMOTABLE_CATEGORIES = frozenset({"decision", "pattern", "assumption"})

_CATEGORY_MAP = {
    "decision": "architecture",
    "pattern": "pattern",
    "assumption": "domain",
}


@dataclass
class PromotionSuggestion:
    observation_id: str
    reason: str
    suggested_category: str


def suggest_promotion(observation: Dict[str, Any]) -> Optional[PromotionSuggestion]:
    category = observation.get("category", "note")
    if category not in _PROMOTABLE_CATEGORIES:
        return None

    obs_id = observation.get("id", "")
    suggested = _CATEGORY_MAP.get(category, "technical")

    reasons = {
        "decision": "This decision may encode a durable architectural choice worth enforcing.",
        "pattern": "This observed pattern may be an established convention worth documenting.",
        "assumption": "This assumption may encode domain knowledge worth making explicit.",
    }

    return PromotionSuggestion(
        observation_id=obs_id,
        reason=reasons.get(category, "This observation may be worth promoting to a concept."),
        suggested_category=suggested,
    )


def build_concept_from_observation(observation: Dict[str, Any]) -> Dict[str, Any]:
    content = observation.get("content", "")
    category = observation.get("category", "note")
    file_path = observation.get("file_path", "")

    title = content.split(".")[0].strip()
    if len(title) > 80:
        title = title[:77] + "..."
    if not title:
        title = content[:80]

    concept_category = _CATEGORY_MAP.get(category, "technical")
    anchors = [file_path] if file_path else []

    return {
        "title": title,
        "content": content,
        "assertion": "",
        "category": concept_category,
        "status": "proposed",
        "anchors": anchors,
        "doc_links": [],
        "source": observation.get("id", ""),
    }

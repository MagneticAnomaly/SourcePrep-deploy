"""Concept conflict detection for CoDRAG.

Detects contradictory active concepts that share anchors.
Only constraint and architecture concepts can conflict.
Oldest concept wins for code enforcement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set


_CONFLICTING_CATEGORIES = frozenset({"constraint", "architecture"})


@dataclass
class ConceptConflict:
    concept_a_id: str
    concept_a_title: str
    concept_b_id: str
    concept_b_title: str
    shared_anchors: List[str]
    winner_id: str


def detect_conflicts(concepts: List[Dict[str, Any]]) -> List[ConceptConflict]:
    active = [
        c for c in concepts
        if c.get("status") == "active"
        and c.get("category", "") in _CONFLICTING_CATEGORIES
    ]

    conflicts: List[ConceptConflict] = []
    seen_pairs: Set[frozenset] = set()

    for i, a in enumerate(active):
        anchors_a = set(a.get("anchors", []))
        if not anchors_a:
            continue

        for b in active[i + 1:]:
            anchors_b = set(b.get("anchors", []))
            shared = anchors_a & anchors_b
            if not shared:
                continue

            pair_key = frozenset({a["id"], b["id"]})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            a_time = a.get("created_at", 0)
            b_time = b.get("created_at", 0)
            winner_id = a["id"] if a_time <= b_time else b["id"]

            conflicts.append(ConceptConflict(
                concept_a_id=a["id"],
                concept_a_title=a.get("title", ""),
                concept_b_id=b["id"],
                concept_b_title=b.get("title", ""),
                shared_anchors=sorted(shared),
                winner_id=winner_id,
            ))

    return conflicts

"""Derive antibody suggestions from concepts.

Constraint and architecture concepts can be auto-derived into antibodies.
All derived antibodies start in 'testing' status.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from codrag.core.antibodies import (
    Antibody, Trigger, TriggerType, Response, ResponseType, Severity,
)


def suggest_antibody(concept: Dict[str, Any]) -> Optional[Antibody]:
    """Suggest an antibody from a concept, if derivable.

    Only constraint and architecture concepts with anchors are candidates.
    Returns None if the concept can't produce a useful antibody.
    """
    category = concept.get("category", "")
    if category not in ("constraint", "architecture"):
        return None

    anchors = concept.get("anchors", [])
    if not anchors:
        return None

    title = concept.get("title", "")
    assertion = concept.get("assertion", "")
    content = concept.get("content", "")
    concept_id = concept.get("id", "")

    # Try to derive trigger from assertion or content
    text = assertion or content
    if not text:
        return None

    # Detect import restriction patterns
    import_pattern = _extract_import_pattern(text)
    if import_pattern:
        severity = Severity.REVIEW if category == "constraint" else Severity.WARN
        return Antibody(
            id=str(uuid.uuid4())[:12],
            name=f"Guard: {title}",
            source_concept_id=concept_id,
            trigger=Trigger(
                type=TriggerType.IMPORT_ADDED,
                target=anchors[0],
                pattern=import_pattern,
            ),
            response=Response(
                type=ResponseType.AMBIENT_INJECT,
                message=f"Potential violation of '{title}': {assertion or content[:100]}",
            ),
            severity=severity,
            status="testing",
        )

    # Default: watch for any modification to anchored files
    severity = Severity.INFORM if category == "architecture" else Severity.WARN
    return Antibody(
        id=str(uuid.uuid4())[:12],
        name=f"Watch: {title}",
        source_concept_id=concept_id,
        trigger=Trigger(
            type=TriggerType.FILE_MODIFIED,
            target=anchors[0],
        ),
        response=Response(
            type=ResponseType.AMBIENT_INJECT,
            message=f"File modified — concept '{title}' applies here: {assertion or content[:100]}",
        ),
        severity=severity,
        status="testing",
    )


def _extract_import_pattern(text: str) -> Optional[str]:
    """Try to extract an import restriction regex from concept text.

    Looks for phrases like 'never import X', 'must not import X',
    'should not depend on X', 'no X imports'.
    """
    text_lower = text.lower()

    # "never/must not/should not import X, Y, Z"
    m = re.search(
        r"(?:never|must not|should not|cannot|don'?t)\s+"
        r"(?:import|depend on|use)\s+"
        r"([a-zA-Z0-9_,\s]+)",
        text_lower,
    )
    if m:
        modules = [mod.strip() for mod in m.group(1).split(",") if mod.strip()]
        if modules:
            # Build a regex that matches any of the modules in import lines
            return "|".join(re.escape(mod) for mod in modules[:5])

    # "no X imports" or "zero X dependencies"
    m = re.search(
        r"(?:no|zero)\s+([a-zA-Z0-9_]+)\s+(?:imports|dependencies|deps)",
        text_lower,
    )
    if m:
        return re.escape(m.group(1))

    return None


def derive_antibodies_for_project(concepts: List[Dict[str, Any]]) -> List[Antibody]:
    """Derive antibody suggestions for all derivable concepts in a project."""
    antibodies = []
    for c in concepts:
        ab = suggest_antibody(c)
        if ab is not None:
            antibodies.append(ab)
    return antibodies

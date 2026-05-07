"""Derive antibody suggestions from concepts.

Constraint and architecture concepts can be auto-derived into antibodies.

Status inheritance: a derived antibody adopts the status of its source
concept. An ``active`` (curated, vetted) concept produces an ``active``
antibody that fires on file changes via ``immune_watcher``. Any other
concept status (``seed``, ``proposed``, ``triage_pending``, etc.)
produces a ``testing`` antibody that requires manual promotion through
``prep_audit(antibody_id, status='active')`` before it fires. Archived
and superseded concepts do not derive antibodies at all.

This propagates the existing concept-promotion gate to the antibody
layer rather than introducing a second gate. Before this change, every
derived antibody started in ``testing`` and required a separate manual
promotion step that nobody performed in practice — leaving the immune
system functionally inactive even when concepts had been curated.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from prep.core.antibodies import (
    Antibody, Trigger, TriggerType, Response, ResponseType, Severity,
)

# Concept statuses that should not derive antibodies at all.
_SKIP_DERIVATION_STATUSES: frozenset[str] = frozenset({
    "archived", "superseded", "deprecated",
})


def _antibody_status_for_concept(concept_status: str) -> str:
    """Map a concept status to the antibody status it should inherit.

    Only ``active`` concepts produce ``active`` antibodies. Everything
    else stays in ``testing`` — the existing safety valve for unvetted
    concepts continues to apply at the antibody layer too.
    """
    return "active" if concept_status == "active" else "testing"


def suggest_antibody(concept: Dict[str, Any]) -> Optional[Antibody]:
    """Suggest an antibody from a concept, if derivable.

    Only constraint and architecture concepts with anchors are candidates.
    Archived/superseded/deprecated concepts skip derivation. The derived
    antibody inherits the concept's status (active concepts produce
    firing antibodies; seed/testing/proposed concepts produce testing
    antibodies that still require manual promotion).
    Returns None if the concept can't produce a useful antibody.
    """
    category = concept.get("category", "")
    if category not in ("constraint", "architecture"):
        return None

    concept_status = concept.get("status", "seed")
    if concept_status in _SKIP_DERIVATION_STATUSES:
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

    antibody_status = _antibody_status_for_concept(concept_status)

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
            status=antibody_status,
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
        status=antibody_status,
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
        r"([a-zA-Z0-9_][a-zA-Z0-9_,\s]*[a-zA-Z0-9_])",
        text_lower,
    )
    if m:
        # Split on commas and 'or'/'and', keep only identifier-like tokens
        raw = re.split(r"[,]|\bor\b|\band\b", m.group(1))
        modules = [tok.strip() for tok in raw
                   if tok.strip() and re.match(r"^[a-zA-Z0-9_]+$", tok.strip())]
        if modules:
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

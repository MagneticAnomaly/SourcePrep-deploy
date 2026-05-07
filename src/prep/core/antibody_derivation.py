"""Derive antibody suggestions from concepts.

Constraint and architecture concepts can be auto-derived into antibodies.

Status inheritance: a derived antibody adopts the status of its source
concept. An ``active`` (curated, vetted) concept produces an ``active``
antibody that fires on file changes via ``immune_watcher``. Any other
concept status (``seed``, ``proposed``, ``triage_pending``, etc.)
produces a ``testing`` antibody that requires manual promotion through
``prep_audit(antibody_id, status='active')`` before it fires. Archived
and superseded concepts do not derive antibodies at all.

Layer filter: only the small ``kind='concept'`` layer (cross-cutting
architectural axioms, ~30-100 per project) derives antibodies. The
dense ``kind='module_rationale'`` layer (~thousands per project, raw
per-module observations) does not — those are too noisy to fire
runtime alerts from, even when categorized as constraint/architecture.

Stable IDs: a derived antibody's ID is a deterministic hash of
``(source_concept_id, trigger_type, target, pattern)`` so re-runs of
the same concept produce the same antibody ID and the underlying
``INSERT OR REPLACE`` upserts in place rather than accumulating
duplicates across pipeline runs.

This propagates the existing concept-promotion gate to the antibody
layer rather than introducing a second gate. Before this change, every
derived antibody started in ``testing`` and required a separate manual
promotion step that nobody performed in practice — leaving the immune
system functionally inactive even when concepts had been curated.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from prep.core.antibodies import (
    Antibody, Trigger, TriggerType, Response, ResponseType, Severity,
)

# Concept statuses that should not derive antibodies at all.
_SKIP_DERIVATION_STATUSES: frozenset[str] = frozenset({
    "archived", "superseded", "deprecated",
})

# Only the curated cross-cutting concept layer derives antibodies.
# ``module_rationale`` (per-module observations, ~thousands per project)
# is too noisy a substrate for runtime immune-system alerts.
_DERIVABLE_KIND = "concept"


def _antibody_status_for_concept(concept_status: str) -> str:
    """Map a concept status to the antibody status it should inherit.

    Only ``active`` concepts produce ``active`` antibodies. Everything
    else stays in ``testing`` — the existing safety valve for unvetted
    concepts continues to apply at the antibody layer too.
    """
    return "active" if concept_status == "active" else "testing"


def _stable_antibody_id(
    source_concept_id: str,
    trigger_type: TriggerType,
    target: str,
    pattern: str = "",
) -> str:
    """Generate a deterministic 12-char antibody ID from its identity.

    Re-running derivation on the same concept must produce the same ID
    so ``INSERT OR REPLACE`` in the antibody store upserts in place
    instead of accumulating duplicates. uuid4 was the previous choice
    and turned every pipeline run into N new rows.
    """
    key = f"{source_concept_id}|{trigger_type.value}|{target}|{pattern}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def suggest_antibody(concept: Dict[str, Any]) -> Optional[Antibody]:
    """Suggest an antibody from a concept, if derivable.

    Only ``kind='concept'`` constraint/architecture rows with anchors
    are candidates. ``module_rationale`` rows are skipped to keep the
    immune system tied to curated cross-cutting axioms, not bulk
    per-module observations. Archived/superseded/deprecated concepts
    skip derivation. The derived antibody inherits the concept's status
    (active concepts produce firing antibodies; seed/testing/proposed
    concepts produce testing antibodies that still require manual
    promotion). The antibody ID is a stable hash so re-derivation
    upserts the existing row instead of creating duplicates.
    Returns None if the concept can't produce a useful antibody.
    """
    # Phase 125b layer filter — only the small curated layer derives.
    # Default to the derivable kind so legacy concept dicts without an
    # explicit kind field still produce antibodies.
    kind = concept.get("kind", _DERIVABLE_KIND)
    if kind != _DERIVABLE_KIND:
        return None

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
            id=_stable_antibody_id(
                concept_id, TriggerType.IMPORT_ADDED, anchors[0], import_pattern,
            ),
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
        id=_stable_antibody_id(
            concept_id, TriggerType.FILE_MODIFIED, anchors[0],
        ),
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

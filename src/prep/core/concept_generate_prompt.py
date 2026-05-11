"""Phase 125c T2b — per-worker prompt assembly for the Generate swarm.

Composes T2a's deterministic helpers (scope, doc-tier, rationale filter)
with the existing ``concept_synthesizer.load_grounding`` output and the
Phase 125c T1 ``docs_grounding.json`` to produce per-worker payloads
and the ``(system, user)`` prompt strings that SwarmOrchestrator's
worker_fn will hand to the LLM.

This module is **pure** — no LLM, no I/O. T2c will plug it into
SwarmOrchestrator and replace the current single-call synthesizer.

See ``docs/Phase125c_QualityCheckedConceptSwarm/README.md`` §3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prep.core.concept_synthesizer import SYNTH_SYSTEM_PROMPT, Grounding

from .concept_generate_grounding import (
    WorkerScope,
    filter_rationale_by_scope,
    tier_docs_grounding,
)
from .docs_grounding import DiscoveredDoc, DocsGrounding


# ── Per-worker payload ──────────────────────────────────────────────


@dataclass
class WorkerPayload:
    """Everything one Generate worker receives in its prompt.

    Composed from the shared ``Grounding`` (atlas/audit/spaghetti/
    antibodies) plus per-scope filtering of rationale and tiered
    inclusion of planning docs.
    """
    scope: WorkerScope
    project_name: str
    atlas_summary: str = ""
    atlas_segments: list[dict] = field(default_factory=list)
    # Phase 125c post-scrutiny: audit_findings deliberately NOT passed
    # to Generate (it was producing bug-description-shaped "concepts"
    # like "X causes Y desync"). Validate still consults audit per-anchor
    # for counter-evidence. See `build_worker_payload`.
    spaghetti_hotspots: list[dict] = field(default_factory=list)
    antibody_patterns: list[dict] = field(default_factory=list)
    full_doc_excerpts: list[DiscoveredDoc] = field(default_factory=list)
    doc_headings_only: list[DiscoveredDoc] = field(default_factory=list)
    rationale_in_scope: list[dict] = field(default_factory=list)


def build_worker_payload(
    scope: WorkerScope,
    *,
    grounding: Grounding,
    docs: DocsGrounding,
    full_threshold: float = 0.5,
    headings_threshold: float = 0.3,
) -> WorkerPayload:
    """Compose a per-worker payload from shared grounding + per-scope filter.

    The shared grounding (atlas, audit, spaghetti, antibodies) is passed
    through unchanged — every worker sees the full picture there because
    it's small and high-signal. Rationale is filtered to the worker's
    scope categories; docs are split into full-text vs headings-only
    tiers by score threshold.
    """
    full_docs, headings_docs = tier_docs_grounding(
        docs.docs,
        full_threshold=full_threshold,
        headings_threshold=headings_threshold,
    )
    rationale = filter_rationale_by_scope(
        grounding.rationale_clusters, scope,
    )
    return WorkerPayload(
        scope=scope,
        project_name=grounding.project_name,
        atlas_summary=grounding.atlas_summary,
        atlas_segments=list(grounding.segments),
        # audit_findings DELIBERATELY OMITTED — see WorkerPayload docstring.
        spaghetti_hotspots=list(grounding.spaghetti_hotspots),
        antibody_patterns=list(grounding.antibody_patterns),
        full_doc_excerpts=full_docs,
        doc_headings_only=headings_docs,
        rationale_in_scope=rationale,
    )


# ── Prompt builders ─────────────────────────────────────────────────


_GENERATE_SYSTEM_HEADER = """You are one worker in a parallel concept-extraction
swarm. Other workers cover different category dimensions of the same codebase.
Emit ONLY concepts whose `category` falls within your assigned dimension —
the synthesizer downstream will merge cross-dimension findings.

"""


def build_generate_system_prompt(scope: WorkerScope) -> str:
    """Return the system prompt for one Generate worker.

    Reuses the Phase 125b ``SYNTH_SYSTEM_PROMPT`` (T3 rubric, banned
    outputs, hostile-reviewer pass — all the calibration research
    from Phase 125 T3) and prefixes a short scope orientation.
    """
    cats = ", ".join(scope.categories)
    scope_block = (
        _GENERATE_SYSTEM_HEADER
        + f"YOUR ASSIGNED DIMENSION: {scope.label}\n"
        + f"CATEGORIES IN SCOPE: {cats}\n\n"
    )
    return scope_block + SYNTH_SYSTEM_PROMPT


def _format_doc_excerpt(d: DiscoveredDoc) -> str:
    headings = ", ".join(d.headings[:6])
    head_line = f"  headings: {headings}\n" if headings else ""
    return (
        f"## {d.path}  (score={d.score:.2f}, in_links={d.in_link_count})\n"
        f"{head_line}"
        f"  excerpt:\n{d.excerpt}\n"
    )


def _format_doc_headings_only(d: DiscoveredDoc) -> str:
    headings = ", ".join(d.headings[:8]) if d.headings else "(no headings)"
    return f"  - {d.path}  ({headings})"


def _format_rationale_row(r: dict) -> str:
    title = (r.get("title") or "")[:90]
    category = r.get("category", "?")
    anchors = (r.get("anchors") or [])[:3]
    content = (r.get("content") or "")[:200]
    a_str = ", ".join(anchors)
    if content:
        return f"  - [{category}] {title}\n    anchors: {a_str}\n    {content}"
    return f"  - [{category}] {title}  ({a_str})"


def build_generate_user_prompt(payload: WorkerPayload) -> str:
    """Return the user prompt for one Generate worker."""
    parts: list[str] = []
    parts.append(f"PROJECT: {payload.project_name or '(unnamed)'}")
    parts.append(
        f"YOUR DIMENSION: {payload.scope.label}  "
        f"(emit ONLY categories: {', '.join(payload.scope.categories)})"
    )
    parts.append("")

    if payload.atlas_summary:
        parts.append("ATLAS SUMMARY (first 3K chars):")
        parts.append(payload.atlas_summary)
        parts.append("")

    if payload.atlas_segments:
        parts.append(f"ATLAS SEGMENTS ({len(payload.atlas_segments)}):")
        for s in payload.atlas_segments:
            tags = ", ".join(s.get("domain_tags") or [])
            parts.append(
                f"  - {s.get('name')} ({s.get('file_count')} files) [{tags}]"
            )
        parts.append("")

    if payload.full_doc_excerpts:
        parts.append(
            f"PLANNING DOCS — FULL EXCERPTS ({len(payload.full_doc_excerpts)} "
            f"top by score):"
        )
        for d in payload.full_doc_excerpts:
            parts.append(_format_doc_excerpt(d))
        parts.append("")

    if payload.doc_headings_only:
        parts.append(
            f"PLANNING DOCS — HEADINGS ONLY ({len(payload.doc_headings_only)} "
            f"borderline; ask follow-up if relevant):"
        )
        for d in payload.doc_headings_only:
            parts.append(_format_doc_headings_only(d))
        parts.append("")

    if payload.rationale_in_scope:
        parts.append(
            f"MODULE RATIONALE IN YOUR DIMENSION "
            f"({len(payload.rationale_in_scope)} cluster reps):"
        )
        for r in payload.rationale_in_scope:
            parts.append(_format_rationale_row(r))
        parts.append("")

    # NOTE: audit_findings are deliberately omitted from Generate's
    # user prompt (see WorkerPayload docstring). They live in the audit
    # surface; including them here caused Generate to emit bug-description
    # -shaped "concepts" instead of cross-cutting design intent.

    if payload.spaghetti_hotspots:
        parts.append(
            f"SPAGHETTI HOTSPOTS (top {len(payload.spaghetti_hotspots)}):"
        )
        for h in payload.spaghetti_hotspots:
            extra = " [circular]" if h.get("in_circular") else ""
            parts.append(
                f"  - {h.get('file_path')}  score={h.get('score')} "
                f"({h.get('severity')}){extra}"
            )
        parts.append("")

    if payload.antibody_patterns:
        parts.append(
            f"ANTIBODY-ELIGIBLE PATTERNS ({len(payload.antibody_patterns)}):"
        )
        for a in payload.antibody_patterns:
            parts.append(
                f"  - [{a.get('severity','?')}] {a.get('name')}"
            )
        parts.append("")

    parts.append(
        "EMIT JSON ARRAY ONLY. 0-15 concepts. Each MUST have category in "
        f"your scope ({', '.join(payload.scope.categories)}). Empty "
        "array [] is acceptable — padding is failure."
    )
    return "\n".join(parts)


def build_worker_prompt(payload: WorkerPayload) -> tuple[str, str]:
    """Return ``(system, user)`` prompts for one Generate worker."""
    return (
        build_generate_system_prompt(payload.scope),
        build_generate_user_prompt(payload),
    )

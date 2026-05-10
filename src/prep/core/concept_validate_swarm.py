"""Phase 125c T3b — the Validate swarm runner.

Takes the deduped candidate-concept list from Generate (or a fresh
load from concept_store) and runs one Validate worker per concept in
parallel, each fact-checking the candidate against the grounding rows
whose anchors overlap with the candidate's anchors.

Output: per-candidate (final_tier, final_status) via the
``reconcile_tier`` rule from T3a. Concepts are saved via
``concept_store.save_many`` with the reconciled status, so:

    T3 / T2 → status='active'        (auto-accept)
    T1      → status='triage_pending' (queue for human review)
    REJECT  → status='archived'        (hallucination / unsupported)

REJECT and the Validate-wins-on-downgrade rule together replace 125b's
synthesizer-self-tier-mapping behavior with an actual quality check.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .concept_synthesizer import (
    Grounding,
    SynthesizedConcept,
    TIER_TO_CONFIDENCE,
)
from .concept_validate_prompt import (
    ValidationVerdict,
    build_validate_prompt,
    parse_verdict_response,
    reconcile_tier,
)
from .docs_grounding import DocsGrounding

logger = logging.getLogger(__name__)


DEFAULT_PER_WORKER_TIMEOUT_S = 180.0
DEFAULT_TOTAL_TIMEOUT_S = 900.0
DEFAULT_MAX_PARALLEL_WORKERS = 5


@dataclass
class ValidateSwarmReport:
    """Aggregate output of one Validate swarm run."""
    project_id: str = ""
    input_count: int = 0
    verdict_distribution: dict[str, int] = field(default_factory=dict)
    activated: int = 0
    triaged: int = 0
    archived: int = 0
    parse_failures: int = 0
    failed_workers: int = 0
    saved: int = 0
    elapsed_seconds: float = 0.0


def validate_concepts_swarm(
    project_id: str,
    candidates: list[SynthesizedConcept],
    *,
    llm: Any,
    grounding: Grounding,
    docs: DocsGrounding,
    idx_dir: Optional[Path] = None,
    per_worker_timeout_s: float = DEFAULT_PER_WORKER_TIMEOUT_S,
    total_timeout_s: float = DEFAULT_TOTAL_TIMEOUT_S,
    max_workers: int = DEFAULT_MAX_PARALLEL_WORKERS,
    dry_run: bool = False,
) -> ValidateSwarmReport:
    """Run the Validate swarm over Generate's candidates and persist verdicts."""
    t0 = time.time()
    report = ValidateSwarmReport(project_id=project_id, input_count=len(candidates))

    if not candidates:
        report.elapsed_seconds = time.time() - t0
        return report

    # Build per-candidate (related_rationale, related_docs, related_audit) tuples
    # by anchor overlap. Anchors stay strings here — comparison is by-set.
    pre_built: list[tuple[SynthesizedConcept, list[dict], list[dict], list[dict]]] = []
    for cand in candidates:
        cand_anchors = set(cand.anchors)
        related_rationale = [
            r for r in grounding.rationale_clusters
            if cand_anchors.intersection(set(r.get("anchors") or []))
        ]
        related_docs = [
            {"path": d.path, "excerpt": d.excerpt}
            for d in docs.docs
            if d.path in cand_anchors
        ]
        related_audit = [
            f for f in grounding.audit_findings
            if cand_anchors.intersection(set(f.get("file_paths") or []))
        ]
        pre_built.append((cand, related_rationale, related_docs, related_audit))

    if dry_run:
        for cand, rr, rd, ra in pre_built:
            logger.info(
                "[ValSwarm/dry-run] candidate=%r related_rationale=%d "
                "related_docs=%d related_audit=%d",
                cand.title[:60], len(rr), len(rd), len(ra),
            )
        report.elapsed_seconds = time.time() - t0
        return report

    # Fan out — bounded parallelism since Validate per-candidate cost is small
    # and we may be processing many candidates.
    verdicts: dict[int, Optional[ValidationVerdict]] = {}
    pool_size = min(max_workers, len(pre_built))
    with ThreadPoolExecutor(max_workers=pool_size) as pool:
        future_to_idx = {
            pool.submit(
                _validate_one,
                llm=llm, candidate=cand,
                related_rationale=rr,
                related_doc_excerpts=rd,
                related_audit_findings=ra,
                timeout_s=per_worker_timeout_s,
            ): i
            for i, (cand, rr, rd, ra) in enumerate(pre_built)
        }
        for fut in as_completed(future_to_idx, timeout=total_timeout_s):
            i = future_to_idx[fut]
            try:
                verdicts[i] = fut.result()
            except Exception as e:
                logger.warning(
                    "[ValSwarm] worker %d failed: %s",
                    i, e,
                )
                verdicts[i] = None
                report.failed_workers += 1

    # Reconcile + assemble save_dicts.
    save_dicts: list[dict] = []
    for i, (cand, _rr, _rd, _ra) in enumerate(pre_built):
        v = verdicts.get(i)
        if v is None:
            # Validation failed for this candidate. Default conservative:
            # archive — better to drop than auto-promote unverified output.
            report.parse_failures += 1
            final_tier, final_status = "REJECT", "archived"
            verdict_label = "PARSE_FAILED"
        else:
            final_tier, final_status = reconcile_tier(cand.tier, v.verdict)
            verdict_label = v.verdict
        report.verdict_distribution[verdict_label] = (
            report.verdict_distribution.get(verdict_label, 0) + 1
        )
        if final_status == "active":
            report.activated += 1
        elif final_status == "triage_pending":
            report.triaged += 1
        elif final_status == "archived":
            report.archived += 1
        save_dicts.append(_to_save_dict(cand, final_tier, final_status, v))

    # Persist via the existing concept_store.save_many path.
    if save_dicts:
        try:
            from prep.services.concept_store import concept_store
            saved, _skipped = concept_store.save_many(project_id, save_dicts)
            report.saved = saved
        except Exception as e:
            logger.warning("[ValSwarm] save_many failed: %s", e, exc_info=True)

    # Telemetry.
    try:
        from prep.services.pipeline_telemetry import record_event
        record_event(
            idx_dir,
            "validate_swarm_complete",
            {
                "input_count": report.input_count,
                "verdict_distribution": dict(report.verdict_distribution),
                "activated": report.activated,
                "triaged": report.triaged,
                "archived": report.archived,
                "parse_failures": report.parse_failures,
                "failed_workers": report.failed_workers,
                "elapsed_seconds": time.time() - t0,
            },
            stage="concepts", project_id=project_id,
        )
    except Exception:
        logger.debug("[ValSwarm] telemetry record failed", exc_info=True)

    report.elapsed_seconds = time.time() - t0
    return report


def _validate_one(
    *,
    llm: Any,
    candidate: SynthesizedConcept,
    related_rationale: Iterable[dict],
    related_doc_excerpts: Iterable[dict],
    related_audit_findings: Iterable[dict],
    timeout_s: float,  # noqa: ARG001 — caller-side timeout via as_completed
) -> Optional[ValidationVerdict]:
    """One LLM call → one ValidationVerdict (or None on parse failure)."""
    system, user = build_validate_prompt(
        candidate=candidate,
        related_rationale=related_rationale,
        related_doc_excerpts=related_doc_excerpts,
        related_audit_findings=related_audit_findings,
    )
    text, _tokens = llm.generate(
        prompt=user,
        system=system,
        json_mode=True,
        temperature=0.1,
        num_predict=1500,   # verdict output is small
        think=False,
    )
    return parse_verdict_response(text or "")


def _to_save_dict(
    candidate: SynthesizedConcept,
    final_tier: str,
    final_status: str,
    verdict: Optional[ValidationVerdict],
) -> dict:
    """Build the dict shape concept_store.save_many expects.

    `final_tier` may be "T1" / "T2" / "T3" / "REJECT". For REJECT we
    map confidence to 0.0 (archive); otherwise reuse TIER_TO_CONFIDENCE.
    `verdict` is the parsed Validate output (None when parsing failed).
    Validate's counter_evidence/falsification override Generate's when
    present — Validate is the strict reviewer, so we keep its evidence.
    """
    if final_tier == "REJECT":
        confidence = 0.0
    else:
        confidence = TIER_TO_CONFIDENCE.get(final_tier, 0.0)
    counter = (verdict.counter_evidence if verdict else "") or candidate.counter_evidence
    falsification = (verdict.falsification if verdict else "") or candidate.falsification
    content = candidate.refined_content or candidate.content
    return {
        "title": candidate.title[:200],
        "content": content[:4000],
        "category": candidate.category,
        "status": final_status,
        "confidence": confidence,
        "anchors": list(candidate.anchors),
        "kind": "concept",
        "assertion": falsification or "",
    }

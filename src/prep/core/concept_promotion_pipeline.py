"""Phase 125 — multi-pass concept promotion pipeline.

Implements the four-pass refinement architecture documented in
``docs/Phase125_ConceptPromotionPipeline/README.md``. This module
hosts the **non-LLM** passes (Pass 2 deterministic triage and Pass 4
deterministic gate). Pass 3 (scoped LLM critique) lives in
``concept_seeder.py`` because it reuses the ``SwarmOrchestrator``.

Public API:

    run_pass2_triage(project_id) → Pass2Report
        Apply anchor-overlap clustering to ``status='seed'`` concepts.
        Set shadows to ``status='shadow'`` with a ``cluster_rep:<id>``
        tag back-reference. Auto-archive low-confidence anchorless
        concepts.

    run_pass4_gate(project_id) → Pass4Report
        After Pass 3 has refined cluster representatives, apply
        deterministic confidence thresholds:
            confidence ≥ 0.90 → status='active'
            0.65 ≤ confidence < 0.90 → status='triage_pending'
            confidence < 0.65 → status='archived'

Pure-function helpers (testable without a DB):

    decide_pass2_actions(concepts, cluster_report, ...) → list[Pass2Action]
    decide_pass4_actions(concepts, ...) → list[Pass4Action]

Both passes emit ``pipeline_telemetry`` events under phase='125'.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Optional

from prep.core.concept_clustering import (
    ClusterReport,
    ConceptInput,
    cluster_concepts,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Phase 125 thresholds (configurable via run-time args; defaults are
# the values calibrated on SourcePrep — see Phase 125 README §4.4)
# ──────────────────────────────────────────────────────────────────────

DEFAULT_AUTO_ARCHIVE_CONFIDENCE = 0.65
DEFAULT_GATE_HIGH_CONFIDENCE = 0.90
DEFAULT_GATE_LOW_CONFIDENCE = 0.65

CLUSTER_REP_TAG_PREFIX = "cluster_rep:"


# ──────────────────────────────────────────────────────────────────────
# Action records (pure data, no DB dependency)
# ──────────────────────────────────────────────────────────────────────

Pass2ActionKind = Literal["shadow", "auto_archive", "no_change"]


@dataclass
class Pass2Action:
    """One status decision for a single concept after clustering."""
    concept_id: str
    kind: Pass2ActionKind
    new_status: Optional[str] = None        # None when kind == 'no_change'
    cluster_rep_id: Optional[str] = None     # only set when kind == 'shadow'
    reason: str = ""                          # human-readable diagnostic


@dataclass
class Pass2Report:
    """Aggregate result of one Pass-2 run."""
    project_id: str = ""
    input_count: int = 0
    cluster_count: int = 0
    shadowed_count: int = 0
    auto_archived_count: int = 0
    no_change_count: int = 0
    largest_cluster_size: int = 0
    cluster_size_distribution: dict[str, int] = field(default_factory=dict)
    actions: list[Pass2Action] = field(default_factory=list)
    dry_run: bool = False


Pass4ActionKind = Literal["activate", "triage", "archive", "no_change"]


@dataclass
class Pass4Action:
    """One gate decision for a refined concept."""
    concept_id: str
    kind: Pass4ActionKind
    new_status: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""


@dataclass
class Pass4Report:
    """Aggregate result of one Pass-4 gate run."""
    project_id: str = ""
    input_count: int = 0
    activated: int = 0
    triaged: int = 0
    archived: int = 0
    no_change: int = 0
    actions: list[Pass4Action] = field(default_factory=list)
    dry_run: bool = False


# ──────────────────────────────────────────────────────────────────────
# Pure-function decision logic (testable without a DB)
# ──────────────────────────────────────────────────────────────────────

def decide_pass2_actions(
    concepts: Iterable[ConceptInput],
    cluster_report: ClusterReport,
    *,
    auto_archive_confidence: float = DEFAULT_AUTO_ARCHIVE_CONFIDENCE,
) -> list[Pass2Action]:
    """Pure decision: given concepts and cluster report, what actions to take.

    Rules:
    1. Concepts in clusters with ≥2 members:
        - representative_id → no_change (stays seed for Pass 3)
        - shadow_ids → shadow (status='shadow', cluster_rep tag added)
    2. Singletons (cluster size 1):
        - if confidence < auto_archive_confidence AND zero anchors →
          auto_archive (status='archived')
        - otherwise → no_change (stays seed for Pass 3)
    """
    by_id = {c.id: c for c in concepts}
    actions: list[Pass2Action] = []
    handled: set[str] = set()

    # First: handle multi-member clusters.
    for cluster in cluster_report.clusters:
        if cluster.member_count <= 1:
            continue
        rep_id = cluster.representative_id
        actions.append(Pass2Action(
            concept_id=rep_id,
            kind="no_change",
            reason=f"cluster representative ({cluster.member_count} members)",
        ))
        handled.add(rep_id)
        for shadow_id in cluster.shadow_ids:
            actions.append(Pass2Action(
                concept_id=shadow_id,
                kind="shadow",
                new_status="shadow",
                cluster_rep_id=rep_id,
                reason=f"shadow of {rep_id} (reason={cluster.reason})",
            ))
            handled.add(shadow_id)

    # Second: handle singletons + any concepts not in a cluster.
    for c in concepts:
        if c.id in handled:
            continue
        if c.confidence < auto_archive_confidence and not c.anchors:
            actions.append(Pass2Action(
                concept_id=c.id,
                kind="auto_archive",
                new_status="archived",
                reason=(
                    f"low-confidence ({c.confidence:.2f}) and zero anchors — "
                    f"speculative noise"
                ),
            ))
        else:
            actions.append(Pass2Action(
                concept_id=c.id,
                kind="no_change",
                reason="singleton — kept for Pass 3",
            ))

    return actions


def decide_pass4_actions(
    concepts: Iterable[ConceptInput],
    *,
    high: float = DEFAULT_GATE_HIGH_CONFIDENCE,
    low: float = DEFAULT_GATE_LOW_CONFIDENCE,
) -> list[Pass4Action]:
    """Pure decision: given refined concepts, gate them by confidence.

    Rules:
    - confidence ≥ high → activate (status='active')
    - low ≤ confidence < high → triage (status='triage_pending')
    - confidence < low → archive (status='archived')
    """
    if low > high:
        raise ValueError(
            f"low ({low}) must be ≤ high ({high}) for gate to be sane",
        )
    actions: list[Pass4Action] = []
    for c in concepts:
        conf = c.confidence
        if conf >= high:
            actions.append(Pass4Action(
                concept_id=c.id, kind="activate", new_status="active",
                confidence=conf, reason=f"confidence {conf:.2f} ≥ {high}",
            ))
        elif conf >= low:
            actions.append(Pass4Action(
                concept_id=c.id, kind="triage", new_status="triage_pending",
                confidence=conf,
                reason=f"confidence {conf:.2f} in triage band [{low}, {high})",
            ))
        else:
            actions.append(Pass4Action(
                concept_id=c.id, kind="archive", new_status="archived",
                confidence=conf, reason=f"confidence {conf:.2f} < {low}",
            ))
    return actions


# ──────────────────────────────────────────────────────────────────────
# DB-applying wrappers (call into concept_store)
# ──────────────────────────────────────────────────────────────────────

def _apply_pass2_action(action: Pass2Action) -> bool:
    """Apply one Pass-2 action to the concept store. Return True if updated."""
    from prep.services.concept_store import concept_store

    if action.kind == "no_change":
        return False
    if action.kind == "shadow":
        # Tag-decoration (adding the cluster_rep back-ref to tags)
        # happens in run_pass2_triage which has the existing tags
        # pre-loaded via list_concepts(kind='module_rationale').
        # Here we only flip the status — the caller has already
        # written the tags update via concept_store.update().
        return concept_store.update(
            action.concept_id,
            status=action.new_status,
        )
    if action.kind == "auto_archive":
        return concept_store.update(
            action.concept_id,
            status=action.new_status,
        )
    return False


def run_pass2_triage(
    project_id: str,
    *,
    idx_dir: Optional[Path] = None,
    auto_archive_confidence: float = DEFAULT_AUTO_ARCHIVE_CONFIDENCE,
    cluster_kwargs: Optional[dict] = None,
    dry_run: bool = False,
) -> Pass2Report:
    """Apply T1 clustering + status updates to the live concept store.

    Args:
        project_id: project to operate on.
        idx_dir: if provided, telemetry events written to
            ``<idx_dir>/pipeline_telemetry.jsonl``. If None, attempt
            best-effort lookup via ``project_index_dir(require_project(...))``.
        auto_archive_confidence: confidence threshold below which a
            singleton anchorless concept becomes auto-archived. Default 0.65.
        cluster_kwargs: kwargs forwarded to ``cluster_concepts`` (e.g.,
            ``min_shared_anchors``, ``hub_anchor_threshold``).
        dry_run: if True, decide actions but do NOT write to the DB.
            Useful for previewing what Pass 2 would do.

    Returns:
        Pass2Report with action breakdown + cluster stats.
    """
    from prep.core.concept_clustering import load_concepts_for_clustering
    from prep.services.concept_store import concept_store

    # Resolve telemetry index dir if not provided.
    if idx_dir is None:
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
        except Exception:
            idx_dir = None

    # Locate the concept DB.
    from prep.core.project_registry import prep_data_dir
    db_path = Path(prep_data_dir()) / "prep_concepts.db"
    if not db_path.is_file():
        raise RuntimeError(
            f"concept DB not found at {db_path}; ensure the daemon has run at least once",
        )
    db_path_str = str(db_path)

    seeds = load_concepts_for_clustering(db_path_str, project_id, status="seed")

    cluster_report = cluster_concepts(seeds, **(cluster_kwargs or {}))
    actions = decide_pass2_actions(
        seeds, cluster_report,
        auto_archive_confidence=auto_archive_confidence,
    )

    report = Pass2Report(
        project_id=project_id,
        input_count=len(seeds),
        cluster_count=cluster_report.cluster_count,
        largest_cluster_size=cluster_report.largest_cluster_size,
        cluster_size_distribution=cluster_report.cluster_size_distribution(),
        actions=actions,
        dry_run=dry_run,
    )

    # Aggregate counts up front (for telemetry payload).
    report.shadowed_count = sum(1 for a in actions if a.kind == "shadow")
    report.auto_archived_count = sum(1 for a in actions if a.kind == "auto_archive")
    report.no_change_count = sum(1 for a in actions if a.kind == "no_change")

    if dry_run:
        logger.info(
            "[Pass2/dry-run] %d seeds → %d clusters; would shadow %d, archive %d, keep %d",
            report.input_count, report.cluster_count,
            report.shadowed_count, report.auto_archived_count, report.no_change_count,
        )
    else:
        # Apply actions to DB. Fetch tags for shadows so we can preserve
        # existing tags + add the cluster_rep back-ref.
        # Build a lookup: id → existing tags
        # Phase 125b: Pass 2 operates on the rationale layer; pass
        # kind='module_rationale' explicitly (the default changed to
        # kind='concept' in Phase 125b — without this we'd skip every
        # actual cluster-shadow target).
        existing_tags: dict[str, list[str]] = {}
        for c_row in concept_store.list_concepts(
            project_id, kind="module_rationale",
        ):
            try:
                existing_tags[c_row.id] = list(c_row.tags or [])
            except Exception:
                existing_tags[c_row.id] = []

        applied_shadow = 0
        applied_archive = 0
        for a in actions:
            if a.kind == "shadow":
                tags = existing_tags.get(a.concept_id, [])
                rep_tag = f"{CLUSTER_REP_TAG_PREFIX}{a.cluster_rep_id}"
                if rep_tag not in tags:
                    tags = [*tags, rep_tag]
                ok = concept_store.update(
                    a.concept_id, status="shadow", tags=tags,
                )
                if ok:
                    applied_shadow += 1
            elif a.kind == "auto_archive":
                ok = concept_store.update(a.concept_id, status="archived")
                if ok:
                    applied_archive += 1
            # 'no_change' → noop

        logger.info(
            "[Pass2] %d seeds → %d clusters; applied: shadow=%d, archive=%d, kept=%d",
            report.input_count, report.cluster_count,
            applied_shadow, applied_archive, report.no_change_count,
        )

    # Emit telemetry.
    if idx_dir is not None:
        try:
            from prep.services.pipeline_telemetry import record_event
            record_event(
                idx_dir,
                "pass2_clustering_complete" if not dry_run else "pass2_dry_run",
                {
                    "input_count": report.input_count,
                    "cluster_count": report.cluster_count,
                    "shadowed": report.shadowed_count,
                    "auto_archived": report.auto_archived_count,
                    "no_change": report.no_change_count,
                    "largest_cluster": report.largest_cluster_size,
                    "size_distribution": report.cluster_size_distribution,
                    "compression_pct": round(
                        100 * (1 - cluster_report.reduction_ratio), 1,
                    ),
                    "dry_run": dry_run,
                },
                stage="concepts", project_id=project_id,
            )
        except Exception:
            pass

    return report


def run_pass4_gate(
    project_id: str,
    *,
    idx_dir: Optional[Path] = None,
    high: float = DEFAULT_GATE_HIGH_CONFIDENCE,
    low: float = DEFAULT_GATE_LOW_CONFIDENCE,
    status_filter: str = "seed",
    kind: str = "concept",
    dry_run: bool = False,
) -> Pass4Report:
    """Apply confidence-based gate to refined concepts.

    Default reads ``status='seed' AND kind='concept'`` — the curated
    cross-cutting layer left at seed by the synthesizer (T1 tier),
    or by Validate (Phase 125c) when a candidate doesn't auto-promote.
    The synthesizer's tier mapping is T1=0.30 / T2=0.65 / T3=0.92, so
    with default thresholds T1 archives, mid-band stays at triage,
    and T3 promotes to active. T2/T3 already at status='active' from
    the synthesizer's own pass are skipped (status filter).

    Pass ``kind='module_rationale'`` to gate the rationale layer
    (rare — rationale rows are seeded at status='seed' by design and
    gating would archive most). Pass ``kind=None`` to bypass.

    Args:
        project_id: project scope.
        idx_dir: telemetry log location; resolved if None.
        high / low: confidence thresholds. high=0.90 → active,
            low=0.65 → triage_pending; below low → archived.
        status_filter: which status to pull for gating. Default 'seed'.
        kind: which layer to gate. Default 'concept' (the curated layer
            Phase 125c/b emits). Pass 'module_rationale' for rationale
            or None for both.
        dry_run: if True, decide but don't write.
    """
    from prep.core.concept_clustering import load_concepts_for_clustering
    from prep.services.concept_store import concept_store

    if idx_dir is None:
        try:
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project
            project = require_project(project_id)
            idx_dir = Path(project_index_dir(project))
        except Exception:
            idx_dir = None

    from prep.core.project_registry import prep_data_dir
    db_path = Path(prep_data_dir()) / "prep_concepts.db"
    if not db_path.is_file():
        raise RuntimeError(
            f"concept DB not found at {db_path}; ensure the daemon has run at least once",
        )
    refined = load_concepts_for_clustering(
        str(db_path), project_id, status=status_filter, kind=kind,
    )

    actions = decide_pass4_actions(refined, high=high, low=low)

    report = Pass4Report(
        project_id=project_id,
        input_count=len(refined),
        actions=actions,
        dry_run=dry_run,
    )
    report.activated = sum(1 for a in actions if a.kind == "activate")
    report.triaged = sum(1 for a in actions if a.kind == "triage")
    report.archived = sum(1 for a in actions if a.kind == "archive")
    report.no_change = sum(1 for a in actions if a.kind == "no_change")

    if not dry_run:
        for a in actions:
            if a.kind == "no_change":
                continue
            try:
                concept_store.update(a.concept_id, status=a.new_status)
            except Exception as e:
                logger.warning(
                    "Pass4 update failed for concept %s: %s", a.concept_id, e,
                )

    logger.info(
        "[Pass4%s] %d concepts gated: active=%d, triage=%d, archive=%d",
        "/dry-run" if dry_run else "",
        report.input_count, report.activated, report.triaged, report.archived,
    )

    if idx_dir is not None:
        try:
            from prep.services.pipeline_telemetry import record_event
            record_event(
                idx_dir,
                "pass4_gate_complete" if not dry_run else "pass4_dry_run",
                {
                    "input_count": report.input_count,
                    "activated": report.activated,
                    "triaged": report.triaged,
                    "archived": report.archived,
                    "no_change": report.no_change,
                    "thresholds": {"high": high, "low": low},
                    "dry_run": dry_run,
                },
                stage="concepts", project_id=project_id,
            )
        except Exception:
            pass

    return report

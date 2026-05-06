"""Tests for prep.core.concept_promotion_pipeline (Phase 125 T2 + T4).

Covers the pure-function decision logic. The DB-applying wrappers
(run_pass2_triage / run_pass4_gate) are exercised by the live
verification step in the phase deliverables, not unit tests, because
they depend on a configured concept_store singleton.
"""
from __future__ import annotations

import pytest

from prep.core.concept_clustering import (
    ClusterReport,
    ConceptCluster,
    ConceptInput,
    cluster_concepts,
)
from prep.core.concept_promotion_pipeline import (
    DEFAULT_AUTO_ARCHIVE_CONFIDENCE,
    DEFAULT_GATE_HIGH_CONFIDENCE,
    DEFAULT_GATE_LOW_CONFIDENCE,
    Pass2Action,
    Pass4Action,
    decide_pass2_actions,
    decide_pass4_actions,
)


def _c(cid: str, title: str, conf: float, anchors: tuple[str, ...] = ()) -> ConceptInput:
    return ConceptInput(id=cid, title=title, confidence=conf, anchors=anchors)


# ──────────────────────────────────────────────────────────────────────
# Pass 2 — decide_pass2_actions
# ──────────────────────────────────────────────────────────────────────

def test_pass2_singleton_with_anchors_no_change():
    """Singleton with anchors stays at seed for Pass 3."""
    concepts = [_c("a", "Lone Idea", 0.85, ("src/x.py",))]
    report = cluster_concepts(concepts)
    actions = decide_pass2_actions(concepts, report)
    assert len(actions) == 1
    assert actions[0].kind == "no_change"


def test_pass2_low_confidence_anchorless_singleton_auto_archives():
    """Anchorless concept with low confidence is speculative noise → archive."""
    concepts = [_c("a", "Vague Speculation", 0.50, ())]
    report = cluster_concepts(concepts)
    actions = decide_pass2_actions(concepts, report)
    assert actions[0].kind == "auto_archive"
    assert actions[0].new_status == "archived"


def test_pass2_high_confidence_anchorless_kept():
    """Anchorless concept with high confidence stays — could be a global invariant."""
    concepts = [_c("a", "Global Invariant", 0.95, ())]
    report = cluster_concepts(concepts)
    actions = decide_pass2_actions(concepts, report)
    assert actions[0].kind == "no_change"


def test_pass2_low_confidence_with_anchors_kept():
    """Anchored concepts are not auto-archived even if low-confidence."""
    concepts = [_c("a", "Specific But Speculative", 0.50, ("src/x.py",))]
    report = cluster_concepts(concepts)
    actions = decide_pass2_actions(concepts, report)
    assert actions[0].kind == "no_change"


def test_pass2_cluster_marks_shadows_keeps_representative():
    """Multi-member cluster: representative no_change, shadows shadow."""
    concepts = [
        _c("a", "Anchored A", 0.95, ("src/x.py", "src/y.py")),
        _c("b", "Anchored B", 0.80, ("src/x.py", "src/y.py")),
        _c("c", "Anchored C", 0.70, ("src/x.py", "src/y.py")),
    ]
    report = cluster_concepts(concepts)
    assert report.cluster_count == 1
    actions = decide_pass2_actions(concepts, report)
    by_id = {a.concept_id: a for a in actions}
    assert by_id["a"].kind == "no_change"  # rep (highest conf)
    assert by_id["b"].kind == "shadow"
    assert by_id["c"].kind == "shadow"
    assert by_id["b"].cluster_rep_id == "a"
    assert by_id["c"].cluster_rep_id == "a"


def test_pass2_threshold_is_configurable():
    """Auto-archive threshold can be raised to discard more."""
    concepts = [_c("a", "Mid Confidence", 0.70, ())]
    report = cluster_concepts(concepts)
    # Default: 0.65 → 0.70 stays
    keep = decide_pass2_actions(concepts, report)
    assert keep[0].kind == "no_change"
    # Raised: 0.75 → 0.70 archives
    archive = decide_pass2_actions(
        concepts, report, auto_archive_confidence=0.75,
    )
    assert archive[0].kind == "auto_archive"


def test_pass2_handles_empty_input():
    actions = decide_pass2_actions([], cluster_concepts([]))
    assert actions == []


def test_pass2_handles_concepts_not_in_cluster_report():
    """If cluster_report doesn't mention a concept, it gets singleton handling."""
    concepts = [
        _c("a", "Anchored A", 0.95, ("src/x.py", "src/y.py")),
        _c("b", "Anchored B", 0.90, ("src/x.py", "src/y.py")),
        _c("c", "Lonely C",   0.50, ()),
    ]
    report = cluster_concepts(concepts)  # finds {a,b}; c is singleton
    actions = decide_pass2_actions(concepts, report)
    by_id = {a.concept_id: a for a in actions}
    assert by_id["a"].kind == "no_change"
    assert by_id["b"].kind == "shadow"
    assert by_id["c"].kind == "auto_archive"  # low conf + no anchors


def test_pass2_action_reasons_are_diagnostic():
    """Reason strings are non-empty and stage-specific."""
    concepts = [
        _c("a", "Rep",    0.95, ("x.py", "y.py")),
        _c("b", "Shadow", 0.80, ("x.py", "y.py")),
        _c("c", "Lonely", 0.40, ()),
        _c("d", "Single", 0.95, ("z.py",)),
    ]
    report = cluster_concepts(concepts)
    actions = decide_pass2_actions(concepts, report)
    for a in actions:
        assert a.reason  # non-empty
    by_id = {a.concept_id: a for a in actions}
    assert "representative" in by_id["a"].reason
    assert "shadow" in by_id["b"].reason.lower()
    assert "speculative" in by_id["c"].reason.lower() or "low" in by_id["c"].reason.lower()
    assert "singleton" in by_id["d"].reason.lower()


# ──────────────────────────────────────────────────────────────────────
# Pass 4 — decide_pass4_actions
# ──────────────────────────────────────────────────────────────────────

def test_pass4_high_confidence_activates():
    actions = decide_pass4_actions([_c("a", "X", 0.95, ("a.py",))])
    assert actions[0].kind == "activate"
    assert actions[0].new_status == "active"


def test_pass4_mid_confidence_triages():
    actions = decide_pass4_actions([_c("a", "X", 0.75, ("a.py",))])
    assert actions[0].kind == "triage"
    assert actions[0].new_status == "triage_pending"


def test_pass4_low_confidence_archives():
    actions = decide_pass4_actions([_c("a", "X", 0.40, ("a.py",))])
    assert actions[0].kind == "archive"
    assert actions[0].new_status == "archived"


def test_pass4_at_high_threshold_activates():
    """Confidence exactly at high threshold should activate (≥, not >)."""
    actions = decide_pass4_actions(
        [_c("a", "X", 0.90, ("a.py",))],
        high=0.90, low=0.65,
    )
    assert actions[0].kind == "activate"


def test_pass4_at_low_threshold_triages():
    """Confidence exactly at low threshold should triage (≥, not >)."""
    actions = decide_pass4_actions(
        [_c("a", "X", 0.65, ("a.py",))],
        high=0.90, low=0.65,
    )
    assert actions[0].kind == "triage"


def test_pass4_just_below_low_archives():
    actions = decide_pass4_actions(
        [_c("a", "X", 0.6499, ("a.py",))],
        high=0.90, low=0.65,
    )
    assert actions[0].kind == "archive"


def test_pass4_distribution_across_band():
    """Verify a small cohort gets split correctly across bands."""
    concepts = [
        _c(f"a{i}", f"Concept {i}", c, ("x.py",))
        for i, c in enumerate([0.95, 0.92, 0.85, 0.75, 0.65, 0.50, 0.30])
    ]
    actions = decide_pass4_actions(concepts)
    kinds = [a.kind for a in actions]
    assert kinds.count("activate") == 2  # 0.95, 0.92
    assert kinds.count("triage") == 3    # 0.85, 0.75, 0.65
    assert kinds.count("archive") == 2   # 0.50, 0.30


def test_pass4_invalid_thresholds_raise():
    with pytest.raises(ValueError):
        decide_pass4_actions(
            [_c("a", "X", 0.5)], high=0.5, low=0.9,
        )


def test_pass4_handles_empty():
    assert decide_pass4_actions([]) == []

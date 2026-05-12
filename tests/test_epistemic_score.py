"""Tests for epistemic scoring system."""
import pytest

from prep.core.epistemic_score import (
    EpistemicEntry,
    EpistemicScore,
    apply_decay,
    compute_epistemic_score,
    DECAY_SOURCE_CHANGED,
    DECAY_NEIGHBOR_ENRICHED,
    DECAY_DOC_UPDATED,
    DECAY_TRACE_REBUILT,
)


class TestComputeEpistemicScore:
    def test_fully_enriched_node(self):
        """A fully enriched, validated, well-connected node should score high."""
        score = compute_epistemic_score(
            node_id="file:src/main.py",
            augmentation={
                "confidence": 0.95,
                "validated": True,
                "validated_by": "qwen2.5:14b",
            },
            epistemic=EpistemicEntry(
                node_id="file:src/main.py",
                extended_summary="Main entry point",
                domain_tags=["core"],
                architecture_layer="business_logic",
                pass_number=4,
            ),
            neighbor_ids={"file:src/utils.py", "file:src/config.py"},
            enriched_node_ids={"file:src/utils.py", "file:src/config.py", "file:src/main.py"},
            cross_ref_count=3,
        )
        assert score.composite > 0.9
        assert score.summary_confidence == 0.95
        assert score.validation_status == 1.0
        assert score.neighbor_coverage == 1.0
        assert score.enrichment_depth == 1.0

    def test_unenriched_node(self):
        """A node with only Pass 1 augmentation should score low."""
        score = compute_epistemic_score(
            node_id="file:src/new.py",
            augmentation={
                "confidence": 0.8,
                "validated": False,
            },
            epistemic=None,
            neighbor_ids={"file:src/a.py", "file:src/b.py"},
            enriched_node_ids=set(),
            cross_ref_count=0,
        )
        assert score.composite < 0.5
        assert score.enrichment_depth == 0.0
        assert score.validation_status == 0.0
        assert score.neighbor_coverage == 0.0

    def test_no_staleness_check_field(self):
        """Phase 134: EpistemicScore has no staleness_check field.
        The c6 component is deleted — stale entries don't exist because
        the changeset prevents them at the augmenter level."""
        score = compute_epistemic_score(
            node_id="file:src/changed.py",
            augmentation={
                "confidence": 0.9,
                "validated": True,
                "validated_by": "14b",
            },
            epistemic=EpistemicEntry(
                node_id="file:src/changed.py",
                extended_summary="Was accurate",
                domain_tags=["core"],
                architecture_layer="business_logic",
                pass_number=3,
            ),
            neighbor_ids=set(),
            enriched_node_ids=set(),
            cross_ref_count=0,
        )
        assert not hasattr(score, "staleness_check"), (
            "EpistemicScore.staleness_check was deleted in Phase 134"
        )

    def test_isolated_node_neutral_coverage(self):
        """Isolated nodes (0 neighbors) get neutral 0.5 coverage."""
        score = compute_epistemic_score(
            node_id="file:standalone.py",
            augmentation={"confidence": 0.7, "validated": False},
            epistemic=None,
            neighbor_ids=set(),
            enriched_node_ids=set(),
            cross_ref_count=0,
        )
        assert score.neighbor_coverage == 0.5

    def test_cross_ref_saturation(self):
        """Cross-ref density saturates at 4 references."""
        score_3 = compute_epistemic_score(
            node_id="file:a.py",
            augmentation={"confidence": 0.8, "validated": False},
            epistemic=None,
            neighbor_ids=set(),
            enriched_node_ids=set(),
            cross_ref_count=3,
        )
        score_10 = compute_epistemic_score(
            node_id="file:a.py",
            augmentation={"confidence": 0.8, "validated": False},
            epistemic=None,
            neighbor_ids=set(),
            enriched_node_ids=set(),
            cross_ref_count=10,
        )
        assert score_3.cross_reference_density == 0.75
        assert score_10.cross_reference_density == 1.0

    def test_no_augmentation(self):
        """A node with no augmentation at all should score 0."""
        score = compute_epistemic_score(
            node_id="file:unknown.py",
            augmentation=None,
            epistemic=None,
            neighbor_ids=set(),
            enriched_node_ids=set(),
            cross_ref_count=0,
        )
        assert score.summary_confidence == 0.0
        assert score.composite < 0.2

    def test_to_dict(self):
        """Score should serialize to dict with components."""
        score = compute_epistemic_score(
            node_id="file:test.py",
            augmentation={"confidence": 0.8, "validated": False},
            epistemic=None,
            neighbor_ids=set(),
            enriched_node_ids=set(),
            cross_ref_count=0,
        )
        d = score.to_dict()
        assert "composite" in d
        assert "components" in d
        assert "summary_confidence" in d["components"]
        assert "staleness_check" not in d["components"], (
            "staleness_check was deleted from EpistemicScore in Phase 134"
        )


class TestApplyDecay:
    def test_source_changed_resets(self):
        assert apply_decay(0.95, "source_changed") == 0.0

    def test_neighbor_enriched_mild(self):
        assert apply_decay(1.0, "neighbor_enriched") == 0.95

    def test_doc_updated(self):
        assert apply_decay(1.0, "doc_updated") == 0.9

    def test_trace_rebuilt(self):
        assert apply_decay(1.0, "trace_rebuilt") == 0.8

    def test_unknown_event_no_change(self):
        assert apply_decay(0.85, "unknown_event") == 0.85


class TestEpistemicEntry:
    def test_roundtrip(self):
        entry = EpistemicEntry(
            node_id="file:src/main.py",
            extended_summary="Main entry point for the application",
            domain_tags=["core", "entry"],
            architecture_layer="business_logic",
            subsystem="app-core",
            design_patterns=["singleton"],
            cross_references=["docs/README.md"],
            tech_debt=["TODO: refactor startup"],
            staleness_risk="low",
            epistemic_confidence=0.92,
            pass_number=2,
            enriched_at="2026-02-13T00:00:00Z",
            model="qwen2.5:14b",
        )
        d = entry.to_dict()
        restored = EpistemicEntry.from_dict(d)
        assert restored.node_id == entry.node_id
        assert restored.extended_summary == entry.extended_summary
        assert restored.domain_tags == entry.domain_tags
        assert restored.architecture_layer == entry.architecture_layer
        assert restored.subsystem == entry.subsystem
        assert restored.epistemic_confidence == entry.epistemic_confidence
        assert restored.pass_number == 2

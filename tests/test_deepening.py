"""Tests for continuous deepening loop (Pass 4+)."""
import pytest

from prep.core.deepening import (
    ConvergenceTracker,
    DriftDetector,
    DriftReport,
    EnrichmentQueue,
    DeepeningResult,
)
from prep.core.epistemic_score import EpistemicEntry, EpistemicScore
from prep.services.pipeline.changeset import Changeset


# ── EnrichmentQueue ──────────────────────────────────────────────────

class TestEnrichmentQueue:
    def test_lowest_score_first(self):
        q = EnrichmentQueue()
        q.add("high", 0.9, reason="test")
        q.add("low", 0.1, reason="test")
        q.add("mid", 0.5, reason="test")
        batch = q.next_batch(3)
        ids = [b[0] for b in batch]
        assert ids == ["low", "mid", "high"]

    def test_max_nodes_limit(self):
        q = EnrichmentQueue()
        for i in range(10):
            q.add(f"node:{i}", float(i) / 10, reason="test")
        batch = q.next_batch(3)
        assert len(batch) == 3

    def test_no_duplicates(self):
        q = EnrichmentQueue()
        q.add("a", 0.5)
        q.add("a", 0.3)  # duplicate, should be ignored
        assert len(q) == 1

    def test_empty_queue(self):
        q = EnrichmentQueue()
        assert q.is_empty
        batch = q.next_batch(5)
        assert batch == []

    def test_batch_removes_items(self):
        q = EnrichmentQueue()
        q.add("a", 0.1)
        q.add("b", 0.2)
        batch = q.next_batch(1)
        assert len(batch) == 1
        assert len(q) == 1


# ── DriftDetector ────────────────────────────────────────────────────

def _make_score(node_id: str, composite: float) -> EpistemicScore:
    return EpistemicScore(
        node_id=node_id,
        composite=composite,
        summary_confidence=0.8,
        validation_status=0.0,
        neighbor_coverage=0.5,
        cross_reference_density=0.0,
        enrichment_depth=0.5,
        staleness_check=1.0,
    )


class TestDriftDetector:
    def test_detects_stale_node(self):
        # Phase 134: staleness driven by changeset (modified), not hash compare.
        detector = DriftDetector()
        detector.changeset = Changeset(
            added=frozenset(), modified=frozenset({"a.py"}),
            deleted=frozenset(), unchanged=frozenset(),
            run_id="r1", base_run_id=None,
        )
        scores = {"file:a.py": _make_score("file:a.py", 0.8)}
        augmentations = {"file:a.py": {"node_id": "file:a.py"}}
        edges = []
        nodes_by_id = {"file:a.py": {"id": "file:a.py", "kind": "file"}}

        report = detector.detect(scores, augmentations, edges, nodes_by_id)
        assert "file:a.py" in report.stale_nodes
        assert report.decayed_nodes["file:a.py"] == 0.0

    def test_propagates_decay_to_neighbor(self):
        # Phase 134: a.py is modified → stale; b.py is unchanged → only decayed
        # because it's a neighbor of the stale node.
        detector = DriftDetector(max_propagation_hops=1)
        detector.changeset = Changeset(
            added=frozenset(), modified=frozenset({"a.py"}),
            deleted=frozenset(), unchanged=frozenset({"b.py"}),
            run_id="r1", base_run_id=None,
        )
        scores = {
            "file:a.py": _make_score("file:a.py", 0.8),
            "file:b.py": _make_score("file:b.py", 0.9),
        }
        augmentations = {
            "file:a.py": {"node_id": "file:a.py"},
            "file:b.py": {"node_id": "file:b.py"},
        }
        edges = [{"source": "file:a.py", "target": "file:b.py", "kind": "imports"}]
        nodes_by_id = {
            "file:a.py": {"id": "file:a.py", "kind": "file"},
            "file:b.py": {"id": "file:b.py", "kind": "file"},
        }

        report = detector.detect(scores, augmentations, edges, nodes_by_id)
        assert "file:a.py" in report.stale_nodes
        assert "file:b.py" in report.decayed_nodes
        assert report.decayed_nodes["file:b.py"] == pytest.approx(0.855)  # 0.9 * 0.95

    def test_no_drift_when_unchanged(self):
        # Phase 134: a.py is unchanged → not stale.
        detector = DriftDetector()
        detector.changeset = Changeset(
            added=frozenset(), modified=frozenset(),
            deleted=frozenset(), unchanged=frozenset({"a.py"}),
            run_id="r1", base_run_id=None,
        )
        scores = {"file:a.py": _make_score("file:a.py", 0.9)}
        augmentations = {"file:a.py": {"node_id": "file:a.py"}}

        report = detector.detect(scores, augmentations, [], {})
        assert report.stale_nodes == []

    def test_missing_references_detected(self):
        detector = DriftDetector()
        scores = {"file:doc.md": _make_score("file:doc.md", 0.8)}
        augmentations = {}
        edges = [
            {"source": "file:doc.md", "target": "file:deleted.py", "kind": "references"},
        ]
        nodes_by_id = {"file:doc.md": {"id": "file:doc.md", "kind": "file"}}

        report = detector.detect(scores, augmentations, edges, nodes_by_id)
        assert len(report.missing_references) == 1
        assert report.missing_references[0] == ("file:doc.md", "deleted.py")


# ── ConvergenceTracker ───────────────────────────────────────────────

class TestConvergenceTracker:
    def test_converges_all_settled(self):
        tracker = ConvergenceTracker(settled_threshold=0.95)
        scores = {
            "a": _make_score("a", 0.96),
            "b": _make_score("b", 0.97),
            "c": _make_score("c", 0.99),
        }
        state = tracker.check(scores)
        assert state.converged
        assert state.reason == "all_settled"

    def test_converges_no_change(self):
        tracker = ConvergenceTracker(settled_threshold=0.95, residual_threshold=0.01)
        scores1 = {"a": _make_score("a", 0.80), "b": _make_score("b", 0.70)}
        scores2 = {"a": _make_score("a", 0.805), "b": _make_score("b", 0.703)}

        state1 = tracker.check(scores1)
        assert not state1.converged  # first iteration, no previous

        state2 = tracker.check(scores2)
        assert state2.converged
        assert state2.reason == "no_change"

    def test_budget_exhausted(self):
        tracker = ConvergenceTracker(max_iterations=2, settled_threshold=0.99, residual_threshold=0.001)
        scores1 = {"a": _make_score("a", 0.50)}
        scores2 = {"a": _make_score("a", 0.52)}  # changed enough to avoid no_change
        tracker.check(scores1)
        state = tracker.check(scores2)
        assert state.converged
        assert state.reason == "budget_exhausted"

    def test_not_converged_yet(self):
        tracker = ConvergenceTracker(settled_threshold=0.95, max_iterations=10)
        scores = {"a": _make_score("a", 0.50), "b": _make_score("b", 0.60)}
        state = tracker.check(scores)
        assert not state.converged

    def test_reset(self):
        tracker = ConvergenceTracker()
        scores = {"a": _make_score("a", 0.80)}
        tracker.check(scores)
        assert tracker._iteration == 1
        tracker.reset()
        assert tracker._iteration == 0
        assert tracker._previous_scores == {}

    def test_empty_scores_converges(self):
        tracker = ConvergenceTracker()
        state = tracker.check({})
        assert state.converged
        assert state.reason == "no_nodes"


# ── DeepeningResult ─────────────────────────────────────────────────

class TestDeepeningResult:
    def test_to_dict(self):
        r = DeepeningResult(
            iterations=3,
            total_enriched=15,
            total_re_enriched=5,
            drift_stale=2,
            drift_missing_refs=1,
            convergence={"converged": True, "reason": "no_change"},
            duration_ms=1234.5,
        )
        d = r.to_dict()
        assert d["iterations"] == 3
        assert d["total_enriched"] == 15
        assert d["convergence"]["converged"] is True

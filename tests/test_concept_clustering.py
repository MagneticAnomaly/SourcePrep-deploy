"""Tests for prep.core.concept_clustering — Phase 125 T1."""
from __future__ import annotations

import pytest

from prep.core.concept_clustering import (
    ClusterReport,
    ConceptCluster,
    ConceptInput,
    _jaccard,
    _tokenize,
    cluster_concepts,
)


def _c(cid: str, title: str, conf: float, anchors: tuple[str, ...]) -> ConceptInput:
    return ConceptInput(id=cid, title=title, confidence=conf, anchors=anchors)


# ──────────────────────────────────────────────────────────────────────
# Tokenizer + Jaccard
# ──────────────────────────────────────────────────────────────────────

def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = _tokenize("The Audit Pipeline must verify the State")
    assert "audit" in tokens
    assert "pipeline" in tokens
    assert "verify" in tokens
    assert "state" in tokens
    assert "the" not in tokens  # stopword
    assert "must" not in tokens  # stopword


def test_tokenize_empty_string_returns_empty():
    assert _tokenize("") == frozenset()


def test_jaccard_identical_returns_1():
    a = frozenset({"x", "y"})
    assert _jaccard(a, a) == 1.0


def test_jaccard_disjoint_returns_0():
    assert _jaccard(frozenset({"x"}), frozenset({"y"})) == 0.0


def test_jaccard_partial_overlap():
    a = frozenset({"x", "y", "z"})
    b = frozenset({"y", "z", "w"})
    assert _jaccard(a, b) == 2 / 4  # intersect=2, union=4


# ──────────────────────────────────────────────────────────────────────
# Empty / singleton inputs
# ──────────────────────────────────────────────────────────────────────

def test_empty_input_returns_empty_report():
    report = cluster_concepts([])
    assert report.input_count == 0
    assert report.cluster_count == 0
    assert report.clusters == []


def test_single_concept_is_singleton_cluster():
    report = cluster_concepts([_c("a", "First", 0.8, ("src/a.py",))])
    assert report.cluster_count == 1
    assert report.singleton_count == 1
    assert report.clusters[0].member_count == 1
    assert report.clusters[0].reason == "singleton"


def test_two_concepts_no_shared_anchors_are_separate():
    report = cluster_concepts([
        _c("a", "Concept A", 0.8, ("src/a.py",)),
        _c("b", "Concept B", 0.8, ("src/b.py",)),
    ])
    assert report.cluster_count == 2
    assert report.singleton_count == 2


# ──────────────────────────────────────────────────────────────────────
# 2 shared anchors → cluster
# ──────────────────────────────────────────────────────────────────────

def test_two_shared_anchors_cluster_regardless_of_title():
    report = cluster_concepts([
        _c("a", "Totally Different Title One",     0.8, ("src/x.py", "src/y.py")),
        _c("b", "Completely Unrelated Words Here", 0.7, ("src/x.py", "src/y.py")),
    ])
    assert report.cluster_count == 1
    cl = report.clusters[0]
    assert cl.member_count == 2
    assert cl.representative_id == "a"  # higher confidence
    assert cl.shadow_ids == ("b",)
    assert cl.reason == "anchor"


# ──────────────────────────────────────────────────────────────────────
# 1 shared anchor + similar titles → cluster
# ──────────────────────────────────────────────────────────────────────

def test_one_shared_anchor_with_high_jaccard_clusters():
    """Title-jaccard pathway test — exercises min_shared_anchors=2 fallback."""
    report = cluster_concepts(
        [
            _c("a", "Pipeline Recovery State Machine", 0.9, ("src/x.py",)),
            _c("b", "Pipeline Recovery State Tracker", 0.6, ("src/x.py",)),
        ],
        min_shared_anchors=2,  # forces fallback to title-jaccard branch
    )
    assert report.cluster_count == 1
    assert report.clusters[0].reason == "anchor+title"


def test_one_shared_anchor_with_low_jaccard_does_not_cluster():
    """Title-jaccard pathway test — single shared anchor + dissimilar titles."""
    report = cluster_concepts(
        [
            _c("a", "Audit Spaghetti Severity Tiering",   0.9, ("src/x.py",)),
            _c("b", "Background Worker Cleanup Strategy", 0.6, ("src/x.py",)),
        ],
        min_shared_anchors=2,  # forces fallback to title-jaccard branch
    )
    assert report.cluster_count == 2


def test_one_shared_anchor_at_jaccard_boundary_clusters():
    """At exactly the threshold (0.6 default), should cluster."""
    a_title = "Audit Verifier Spaghetti Score"
    b_title = "Audit Verifier Spaghetti Tier"
    # Tokens after stopword filter: {audit, verifier, spaghetti, score}
    #                                {audit, verifier, spaghetti, tier}
    # intersect=3, union=5, jaccard=0.6 — at threshold
    report = cluster_concepts(
        [
            _c("a", a_title, 0.8, ("src/x.py",)),
            _c("b", b_title, 0.7, ("src/x.py",)),
        ],
        min_shared_anchors=2,  # forces fallback to title-jaccard branch
    )
    assert report.cluster_count == 1
    assert report.clusters[0].reason == "anchor+title"


def test_default_min_2_anchors_keeps_unrelated_concepts_separate():
    """Default min_shared_anchors=2 keeps single-anchor pairs apart unless titles agree.

    Phase 125 T1 calibration concluded that min=1 produces too many
    transitive false positives (e.g., 35-member clusters merged via
    shared phase-doc anchors). The default is intentionally
    high-precision.
    """
    # Single shared anchor + dissimilar titles → 2 separate clusters.
    report = cluster_concepts([
        _c("a", "Audit Pipeline State Machine",   0.9, ("src/x.py",)),
        _c("b", "Background Worker Cleanup Plan", 0.7, ("src/x.py",)),
    ])
    assert report.cluster_count == 2


def test_hub_anchor_filter_strips_generic_anchors():
    """When enabled, hub_anchor_threshold strips anchors used by ≥ N concepts.

    Without filter: 4 concepts sharing a 'master_todo.md' anchor would
    transitively cluster. With filter, only the topical anchor matters.
    """
    # Use 2-anchor pairs so the default min_shared_anchors=2 path fires;
    # the test's job is to verify that the HUB anchor doesn't bridge
    # otherwise-unrelated topic groups.
    concepts = [
        _c("a", "Authentication primary path", 0.9, ("docs/MASTER_TODO.md", "src/auth_a.py", "src/auth_a_helper.py")),
        _c("b", "Authentication primary path", 0.8, ("docs/MASTER_TODO.md", "src/auth_a.py", "src/auth_a_helper.py")),
        _c("c", "Database query optimizer", 0.9, ("docs/MASTER_TODO.md", "src/db_q.py", "src/db_q_helper.py")),
        _c("d", "Database query optimizer", 0.8, ("docs/MASTER_TODO.md", "src/db_q.py", "src/db_q_helper.py")),
    ]
    # With filter on (hub_threshold=3): MASTER_TODO is treated as hub.
    # A↔B share 2 topical anchors → cluster via min=2 pathway.
    # C↔D same.
    # A↔C share only MASTER_TODO (filtered) → 0 topical → no cluster.
    report = cluster_concepts(concepts, hub_anchor_threshold=3)
    assert report.cluster_count == 2
    assert report.hub_anchors_filtered == 1  # MASTER_TODO got filtered

    # Without filter (default): same input would also cluster {a,b}+{c,d}
    # but A↔C now share an extra anchor (MASTER_TODO) — still only 1 shared,
    # below min=2, so still 2 clusters. (The test confirms hub_filter is
    # *needed* to surface false positives only when min=1 is in play —
    # see the next test.)
    no_filter = cluster_concepts(concepts)
    assert no_filter.cluster_count == 2  # default min=2 prevents transitive merge


def test_hub_anchor_filter_with_min1_prevents_pile_up():
    """At min_shared_anchors=1, hub filter is the only thing keeping
    transitive union-find from merging unrelated topic buckets via a
    shared MASTER_TODO anchor."""
    concepts = [
        _c("a", "Topic A first",  0.9, ("docs/MASTER_TODO.md", "src/a.py")),
        _c("b", "Topic A second", 0.8, ("docs/MASTER_TODO.md", "src/a.py")),
        _c("c", "Topic B first",  0.9, ("docs/MASTER_TODO.md", "src/b.py")),
        _c("d", "Topic B second", 0.8, ("docs/MASTER_TODO.md", "src/b.py")),
    ]
    # min=1 + no filter: all 4 cluster transitively via MASTER_TODO.
    permissive = cluster_concepts(concepts, min_shared_anchors=1)
    assert permissive.cluster_count == 1  # the false-positive mega-cluster

    # min=1 + hub filter: MASTER_TODO stripped → 2 clean clusters.
    filtered = cluster_concepts(
        concepts, min_shared_anchors=1, hub_anchor_threshold=3,
    )
    assert filtered.cluster_count == 2
    assert filtered.hub_anchors_filtered == 1


# ──────────────────────────────────────────────────────────────────────
# Transitive components
# ──────────────────────────────────────────────────────────────────────

def test_transitive_clustering_merges_three_way_chain():
    """A↔B share x.py+y.py; B↔C share y.py+z.py; A↔C don't share — transitive merge."""
    report = cluster_concepts([
        _c("a", "Concept A", 0.9, ("src/x.py", "src/y.py")),
        _c("b", "Concept B", 0.7, ("src/y.py", "src/z.py", "src/x.py")),
        _c("c", "Concept C", 0.8, ("src/z.py", "src/y.py")),
    ])
    assert report.cluster_count == 1
    cl = report.clusters[0]
    assert cl.member_count == 3
    assert cl.representative_id == "a"  # highest conf
    assert set(cl.shadow_ids) == {"b", "c"}


# ──────────────────────────────────────────────────────────────────────
# Confidence-driven representative picking
# ──────────────────────────────────────────────────────────────────────

def test_representative_is_highest_confidence_in_cluster():
    report = cluster_concepts([
        _c("a", "X mentions /foo /bar", 0.50, ("src/foo.py", "src/bar.py")),
        _c("b", "X mentions /foo /bar", 0.95, ("src/foo.py", "src/bar.py")),
        _c("c", "X mentions /foo /bar", 0.70, ("src/foo.py", "src/bar.py")),
    ])
    assert report.cluster_count == 1
    assert report.clusters[0].representative_id == "b"
    assert set(report.clusters[0].shadow_ids) == {"a", "c"}


def test_tied_confidence_breaks_by_id_for_stability():
    report = cluster_concepts([
        _c("zzz", "Tied A", 0.8, ("src/x.py", "src/y.py")),
        _c("aaa", "Tied B", 0.8, ("src/x.py", "src/y.py")),
    ])
    assert report.cluster_count == 1
    # Stable sort: lower id wins in tie
    assert report.clusters[0].representative_id == "aaa"


# ──────────────────────────────────────────────────────────────────────
# No anchors / robustness
# ──────────────────────────────────────────────────────────────────────

def test_concepts_with_zero_anchors_are_separate_singletons():
    report = cluster_concepts([
        _c("a", "Anchorless A", 0.8, ()),
        _c("b", "Anchorless B", 0.8, ()),
    ])
    assert report.cluster_count == 2
    assert report.singleton_count == 2


def test_dedup_by_id_keeps_last():
    report = cluster_concepts([
        _c("a", "First version",  0.5, ("src/x.py",)),
        _c("a", "Second version", 0.9, ("src/x.py",)),  # same id, different content
    ])
    # by_id dedup means we end up with the second concept only
    assert report.input_count == 2
    assert report.cluster_count == 1
    assert report.clusters[0].representative_id == "a"


def test_non_string_anchors_skipped_silently():
    """Non-string anchor entries are dropped without raising — strict mode."""
    report = cluster_concepts(
        [
            ConceptInput(id="a", title="A", confidence=0.8, anchors=("src/x.py", None, 42, "")),  # type: ignore[arg-type]
            ConceptInput(id="b", title="B", confidence=0.7, anchors=("src/y.py",)),  # disjoint anchors
        ],
        min_shared_anchors=2,  # require 2 shared so the disjoint pair stays separate
    )
    # No shared anchors at all → 2 separate clusters, code didn't raise.
    assert report.cluster_count == 2


# ──────────────────────────────────────────────────────────────────────
# Aggregate stats
# ──────────────────────────────────────────────────────────────────────

def test_size_distribution_buckets_correctly():
    # Build a synthetic input with known cluster sizes
    concepts = []
    # 1 singleton
    concepts.append(_c("s1", "Solo", 0.8, ("solo.py",)))
    # 1 pair (shared 2 anchors)
    concepts.append(_c("p1", "Pair A", 0.8, ("p1.py", "p2.py")))
    concepts.append(_c("p2", "Pair B", 0.7, ("p1.py", "p2.py")))
    # 1 triple
    for i, n in enumerate(["t1", "t2", "t3"]):
        concepts.append(_c(n, f"Triple {i}", 0.8, ("t1.py", "t2.py")))
    report = cluster_concepts(concepts)
    dist = report.cluster_size_distribution()
    assert dist["1"] == 1
    assert dist["2"] == 1
    assert dist["3-5"] == 1


def test_reduction_ratio_drops_with_clustering():
    # 6 concepts, all sharing 2 anchors → 1 cluster, ratio = 1/6
    concepts = [
        _c(f"x{i}", f"Concept {i}", 0.8, ("a.py", "b.py")) for i in range(6)
    ]
    report = cluster_concepts(concepts)
    assert report.cluster_count == 1
    assert report.reduction_ratio == pytest.approx(1 / 6)

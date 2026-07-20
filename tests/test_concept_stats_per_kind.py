"""
Regression coverage for the Phase 125b two-layer concept stats format.

Pins the trailer disambiguation that resolved the 2026-05-02 dogfood
finding (item #1 of the 2026-05-05 epistemic-audit pass). The original
ambiguity was that ``stats['seeds']`` aggregated
seed-status entries across both layers (concept + module_rationale),
and ``by_category`` summed across both — so a reader couldn't tell
"X active concepts of Y total" from the trailer alone.

Phase 125b split this into per-kind × per-status fields and scoped the
category breakdown to ``kind='concept'`` only. These tests lock that in.
"""
from __future__ import annotations

import pytest

from prep.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path):
    s = ConceptStore()
    s.init(tmp_path / "concepts.db")
    yield s
    s.close()


def test_stats_split_concepts_from_module_rationale(store):
    """get_stats must report per-kind counts so the MCP trailer can
    disambiguate the small concept layer from the dense rationale layer."""
    # Save 2 concepts (one active, one seed) and 5 module_rationale (all seed)
    store.save(
        project_id="p1", title="Concept A",
        content="Cross-cutting axiom about how the daemon mediates IO.",
        category="architecture", status="active", kind="concept",
    )
    store.save(
        project_id="p1", title="Concept B",
        content="Constraint: no direct filesystem from UI.",
        category="constraint", status="seed", kind="concept",
    )
    for i in range(5):
        store.save(
            project_id="p1", title=f"Rationale module {i}",
            content=f"Per-module rationale for module {i}.",
            category="technical", status="seed", kind="module_rationale",
        )

    stats = store.get_stats("p1")

    # Per-kind totals
    assert stats["concepts_count"] == 2
    assert stats["module_rationale_count"] == 5

    # Per-kind × per-status
    assert stats["concepts_active"] == 1
    assert stats["concepts_seeds"] == 1
    assert stats["module_rationale_active"] == 0
    assert stats["module_rationale_seeds"] == 5

    # Aggregate fields kept for backward compat
    assert stats["total"] == 7
    assert stats["active"] == 1  # only the one concept-kind active
    assert stats["seeds"] == 6   # 1 concept seed + 5 rationale seeds


def test_by_category_scoped_to_concept_kind_only(store):
    """The ``by_category`` breakdown must reflect ONLY ``kind='concept'``
    rows. Otherwise a reader summing categories sees the rationale layer
    and gets a misleading category profile (the original dogfood failure)."""
    # 2 concepts: one architecture, one constraint
    store.save(
        project_id="p1", title="Architecture concept",
        content="A genuine cross-cutting architecture decision.",
        category="architecture", status="active", kind="concept",
    )
    store.save(
        project_id="p1", title="Constraint concept",
        content="A genuine cross-cutting constraint.",
        category="constraint", status="active", kind="concept",
    )
    # 10 module_rationale, all categorized as 'technical' — should NOT
    # show up in by_category
    for i in range(10):
        store.save(
            project_id="p1", title=f"Rationale {i}",
            content=f"Per-module rationale {i}.",
            category="technical", status="seed", kind="module_rationale",
        )

    stats = store.get_stats("p1")
    cats = stats["by_category"]

    # Only the concept-layer categories should appear
    assert cats == {"architecture": 1, "constraint": 1}
    # Crucially: 'technical' (rationale-only) must NOT leak in
    assert "technical" not in cats


def test_stats_handle_no_concepts_gracefully(store):
    """Empty project must return zeroed per-kind fields, not missing keys
    (the trailer expects them to be present)."""
    stats = store.get_stats("empty-project")
    for key in (
        "concepts_count", "module_rationale_count",
        "concepts_active", "concepts_seeds",
        "module_rationale_active", "module_rationale_seeds",
    ):
        assert key in stats
        assert stats[key] == 0


def test_stats_only_module_rationale_no_concepts(store):
    """Only-rationale projects must not raise and must report zeros for
    the concept layer cleanly."""
    for i in range(3):
        store.save(
            project_id="p1", title=f"Rationale {i}",
            content=f"Per-module rationale {i}.",
            category="technical", status="seed", kind="module_rationale",
        )
    stats = store.get_stats("p1")
    assert stats["concepts_count"] == 0
    assert stats["concepts_active"] == 0
    assert stats["concepts_seeds"] == 0
    assert stats["module_rationale_count"] == 3
    assert stats["module_rationale_seeds"] == 3
    # Categories should be empty (no concept-kind rows exist)
    assert stats["by_category"] == {}

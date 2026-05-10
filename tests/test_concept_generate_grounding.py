"""Tests for Phase 125c T2a — deterministic helpers for the Generate swarm.

These are the pure-function pieces that turn the upstream artifacts
(docs_grounding.json, module rationale, atlas, audit, ...) into
per-worker grounding payloads. No LLM here — when these are right,
T2b plugs them into SwarmOrchestrator.
"""
from __future__ import annotations

import pytest

from prep.core.concept_generate_grounding import (
    AXIS_3_INTENT,
    AXIS_3_RULES,
    AXIS_3_IMPLEMENTATION,
    WorkerScope,
    build_worker_scopes,
    filter_rationale_by_scope,
    tier_docs_grounding,
)
from prep.core.docs_grounding import DiscoveredDoc


# ── build_worker_scopes ─────────────────────────────────────────────


def test_swarm_size_1_yields_one_scope_with_all_categories():
    scopes = build_worker_scopes(1)
    assert len(scopes) == 1
    s = scopes[0]
    assert len(s.categories) == 11   # all VALID_CATEGORIES
    assert s.worker_id == "all"
    assert s.label == "all-categories"


def test_swarm_size_3_yields_three_axis_scopes():
    scopes = build_worker_scopes(3)
    assert len(scopes) == 3
    labels = {s.label for s in scopes}
    assert labels == {"intent", "rules", "implementation"}

    # Categories must be partitioned, no overlap, full coverage
    seen: set[str] = set()
    for s in scopes:
        assert seen.isdisjoint(s.categories), (
            f"category overlap between scopes: {s.label} hit duplicates"
        )
        seen.update(s.categories)
    assert seen == set(AXIS_3_INTENT) | set(AXIS_3_RULES) | set(AXIS_3_IMPLEMENTATION)
    assert len(seen) == 11   # full coverage of VALID_CATEGORIES


def test_swarm_size_10_yields_eleven_per_category_scopes():
    """The 10-bucket means 'one worker per category'. With 11 categories
    the actual worker count is 11. Plan README §3 documents this."""
    scopes = build_worker_scopes(10)
    assert len(scopes) == 11
    # Each scope holds exactly one category
    for s in scopes:
        assert len(s.categories) == 1
        assert s.worker_id == s.categories[0]
    # Together they cover every category exactly once
    all_cats = [c for s in scopes for c in s.categories]
    assert sorted(all_cats) == sorted(set(all_cats))   # no dups
    assert len(all_cats) == 11


def test_invalid_swarm_size_rejected():
    with pytest.raises(ValueError, match="swarm_size"):
        build_worker_scopes(2)
    with pytest.raises(ValueError, match="swarm_size"):
        build_worker_scopes(7)


def test_axis_3_buckets_have_no_overlap():
    """Axis-3 partitions are mutually exclusive at the constant level."""
    assert set(AXIS_3_INTENT).isdisjoint(AXIS_3_RULES)
    assert set(AXIS_3_INTENT).isdisjoint(AXIS_3_IMPLEMENTATION)
    assert set(AXIS_3_RULES).isdisjoint(AXIS_3_IMPLEMENTATION)


# ── tier_docs_grounding ─────────────────────────────────────────────


def _doc(path: str, score: float) -> DiscoveredDoc:
    return DiscoveredDoc(
        path=path, score=score, signals=("convention_match",),
        in_link_count=0, size_bytes=100,
        excerpt="...", headings=("Top",),
    )


def test_tier_splits_docs_by_score_thresholds():
    docs = [
        _doc("a.md", 0.95),
        _doc("b.md", 0.6),
        _doc("c.md", 0.4),
        _doc("d.md", 0.2),
        _doc("e.md", 0.05),
    ]
    full, headings = tier_docs_grounding(
        docs, full_threshold=0.5, headings_threshold=0.3,
    )
    full_paths = {d.path for d in full}
    headings_paths = {d.path for d in headings}
    assert full_paths == {"a.md", "b.md"}      # ≥ 0.5
    assert headings_paths == {"c.md"}           # 0.3-0.5
    # 0.2 and 0.05 dropped


def test_tier_with_empty_input():
    full, headings = tier_docs_grounding([])
    assert full == []
    assert headings == []


def test_tier_default_thresholds():
    """Defaults: full ≥ 0.5, headings 0.3-0.5, drop < 0.3."""
    docs = [_doc("a.md", 0.5), _doc("b.md", 0.3), _doc("c.md", 0.29)]
    full, headings = tier_docs_grounding(docs)
    assert [d.path for d in full] == ["a.md"]
    assert [d.path for d in headings] == ["b.md"]


def test_tier_invalid_threshold_order_rejected():
    with pytest.raises(ValueError, match="threshold"):
        tier_docs_grounding([], full_threshold=0.3, headings_threshold=0.5)


# ── filter_rationale_by_scope ────────────────────────────────────────


def _rationale(title: str, category: str) -> dict:
    return {"title": title, "category": category, "anchors": []}


def test_filter_rationale_keeps_only_in_scope_categories():
    scope = WorkerScope(
        worker_id="rules", label="rules",
        categories=("security", "constraint", "decision"),
    )
    rationale = [
        _rationale("auth flow", "security"),
        _rationale("storage limit", "constraint"),
        _rationale("css system", "brand"),
        _rationale("react usage", "technical"),
        _rationale("ADR-0042", "decision"),
    ]
    filtered = filter_rationale_by_scope(rationale, scope)
    titles = {r["title"] for r in filtered}
    assert titles == {"auth flow", "storage limit", "ADR-0042"}


def test_filter_rationale_handles_missing_category():
    """Rationale rows without a category default to 'technical' bucket;
    they're kept only when the scope includes 'technical'."""
    scope = WorkerScope(
        worker_id="impl", label="implementation",
        categories=("technical", "pattern"),
    )
    rationale = [
        {"title": "no-category row", "anchors": []},  # no 'category' key
        _rationale("t-row", "technical"),
        _rationale("d-row", "decision"),
    ]
    filtered = filter_rationale_by_scope(rationale, scope)
    titles = {r["title"] for r in filtered}
    # default-to-technical means the no-category row passes when
    # 'technical' is in scope.categories
    assert titles == {"no-category row", "t-row"}


def test_filter_rationale_with_all_categories_scope_keeps_everything():
    scopes = build_worker_scopes(1)
    scope = scopes[0]
    rationale = [
        _rationale(f"row-{c}", c) for c in (
            "architecture", "security", "brand", "decision", "pattern",
        )
    ]
    filtered = filter_rationale_by_scope(rationale, scope)
    assert len(filtered) == len(rationale)

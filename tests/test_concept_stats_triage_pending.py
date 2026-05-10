"""Phase 125c T8 — get_stats exposes triage_pending counts per kind.

The MCP trailer reads `concepts_triage` from get_stats() and surfaces
it alongside active/seed when non-zero. This test pins the contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from prep.services.concept_store import ConceptStore


@pytest.fixture
def store(tmp_path: Path):
    s = ConceptStore()
    s.init(tmp_path / "stats_triage.db")
    yield s
    s.close()


def _save(store, title: str, status: str, kind: str = "concept"):
    store.save(
        project_id="p1", title=title, content=f"{title} content",
        category="technical", status=status, confidence=0.7, kind=kind,
    )


def test_stats_includes_triage_pending_for_concept_layer(store):
    _save(store, "active1", "active")
    _save(store, "seed1", "seed")
    _save(store, "triage1", "triage_pending")
    _save(store, "triage2", "triage_pending")

    stats = store.get_stats("p1")
    assert stats["concepts_active"] == 1
    assert stats["concepts_seeds"] == 1
    assert stats["concepts_triage"] == 2


def test_stats_includes_triage_pending_for_rationale_layer(store):
    _save(store, "rat_seed", "seed", kind="module_rationale")
    _save(store, "rat_triage", "triage_pending", kind="module_rationale")

    stats = store.get_stats("p1")
    assert stats["module_rationale_seeds"] == 1
    assert stats["module_rationale_triage"] == 1


def test_stats_triage_pending_top_level_count(store):
    """The top-level `triage_pending` count sums across kinds."""
    _save(store, "c_triage", "triage_pending", kind="concept")
    _save(store, "r_triage", "triage_pending", kind="module_rationale")
    stats = store.get_stats("p1")
    assert stats["triage_pending"] == 2


def test_stats_zero_when_no_triage_pending(store):
    """Backwards compat: project with no triage rows returns 0."""
    _save(store, "active1", "active")
    stats = store.get_stats("p1")
    assert stats["concepts_triage"] == 0
    assert stats["module_rationale_triage"] == 0
    assert stats["triage_pending"] == 0

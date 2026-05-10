"""Phase 125c T5 — Pass 4 gates the concept layer (kind='concept').

Before T5, run_pass4_gate defaulted to kind='module_rationale' (the
clustering-side default of load_concepts_for_clustering). That meant
wiring it into the pipeline would have archived the rationale layer
en masse instead of gating the curated concept layer.

After T5, run_pass4_gate defaults to kind='concept' so a no-args
call from _concepts_worker gates the right layer.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from prep.core.concept_promotion_pipeline import (
    DEFAULT_GATE_HIGH_CONFIDENCE,
    DEFAULT_GATE_LOW_CONFIDENCE,
    decide_pass4_actions,
)
from prep.core.concept_clustering import (
    ConceptInput,
    load_concepts_for_clustering,
)


# ── load_concepts_for_clustering — kind filter ──────────────────────


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Build a SQLite db with the minimal concepts schema + mixed-kind rows."""
    db = tmp_path / "test_concepts.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            title TEXT,
            confidence REAL,
            anchors TEXT,
            status TEXT,
            kind TEXT
        )
    """)
    rows = [
        # (id, project_id, title, confidence, anchors_json, status, kind)
        ("c1", "p1", "Concept T3 active", 0.92, '[]', "active", "concept"),
        ("c2", "p1", "Concept T1 seed", 0.30, '[]', "seed", "concept"),
        ("c3", "p1", "Concept T2 borderline seed", 0.65, '[]', "seed", "concept"),
        ("r1", "p1", "Rationale row seed", 0.70, '[]', "seed", "module_rationale"),
        ("r2", "p1", "Rationale row archived", 0.50, '[]', "archived", "module_rationale"),
    ]
    conn.executemany(
        "INSERT INTO concepts VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def test_load_filters_to_concept_layer_seeds(temp_db):
    """Pass 4's intended scope: kind='concept' AND status='seed'."""
    rows = load_concepts_for_clustering(
        str(temp_db), "p1", status="seed", kind="concept",
    )
    titles = {r.title for r in rows}
    assert titles == {"Concept T1 seed", "Concept T2 borderline seed"}


def test_load_does_not_pull_module_rationale_when_kind_concept(temp_db):
    """Sanity: rationale rows must NOT appear when kind='concept' filter is on."""
    rows = load_concepts_for_clustering(
        str(temp_db), "p1", status="seed", kind="concept",
    )
    assert all(r.title.startswith("Concept") for r in rows)


def test_load_with_kind_none_returns_both_layers(temp_db):
    """Bypass: kind=None returns both kinds (used for debugging / migration)."""
    rows = load_concepts_for_clustering(
        str(temp_db), "p1", status="seed", kind=None,
    )
    titles = {r.title for r in rows}
    assert "Rationale row seed" in titles
    assert "Concept T1 seed" in titles


# ── decide_pass4_actions on synthesizer-shaped tier confidence ──────


def test_pass4_archives_t1_at_default_thresholds():
    """T1 tier (confidence=0.30) falls below 0.65 → archive."""
    inputs = [ConceptInput(id="t1", title="x", confidence=0.30, anchors=[])]
    actions = decide_pass4_actions(inputs)
    assert len(actions) == 1
    assert actions[0].kind == "archive"
    assert actions[0].new_status == "archived"


def test_pass4_triages_t2_at_default_thresholds():
    """T2 tier (confidence=0.65) lands at the low threshold → triage."""
    inputs = [ConceptInput(id="t2", title="x", confidence=0.65, anchors=[])]
    actions = decide_pass4_actions(inputs)
    assert len(actions) == 1
    assert actions[0].kind == "triage"
    assert actions[0].new_status == "triage_pending"


def test_pass4_activates_t3_at_default_thresholds():
    """T3 tier (confidence=0.92) clears 0.90 high → active."""
    inputs = [ConceptInput(id="t3", title="x", confidence=0.92, anchors=[])]
    actions = decide_pass4_actions(inputs)
    assert len(actions) == 1
    assert actions[0].kind == "activate"
    assert actions[0].new_status == "active"


def test_pass4_gates_synthesizer_tier_distribution():
    """End-to-end shape: a typical synthesizer output (T1 + T2 + T3)
    should produce predictable archive/triage/active splits."""
    inputs = [
        ConceptInput(id=f"t1_{i}", title=f"t1 {i}", confidence=0.30, anchors=[])
        for i in range(5)
    ] + [
        ConceptInput(id=f"t2_{i}", title=f"t2 {i}", confidence=0.65, anchors=[])
        for i in range(3)
    ] + [
        ConceptInput(id=f"t3_{i}", title=f"t3 {i}", confidence=0.92, anchors=[])
        for i in range(2)
    ]
    actions = decide_pass4_actions(inputs)
    by_kind = {"archive": 0, "triage": 0, "activate": 0, "no_change": 0}
    for a in actions:
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    assert by_kind["archive"] == 5    # T1
    assert by_kind["triage"] == 3      # T2
    assert by_kind["activate"] == 2    # T3


# ── default thresholds match synthesizer mapping ────────────────────


def test_default_thresholds_match_synthesizer_tier_boundaries():
    """T1=0.30 < low (0.65) < T2=0.65 < high (0.90) ≤ T3=0.92.
    These constants are load-bearing — they're the contract between
    the synthesizer's tier mapping and the gate's default thresholds."""
    from prep.core.concept_synthesizer import TIER_TO_CONFIDENCE
    assert TIER_TO_CONFIDENCE["T1"] < DEFAULT_GATE_LOW_CONFIDENCE
    assert TIER_TO_CONFIDENCE["T2"] >= DEFAULT_GATE_LOW_CONFIDENCE
    assert TIER_TO_CONFIDENCE["T2"] < DEFAULT_GATE_HIGH_CONFIDENCE
    assert TIER_TO_CONFIDENCE["T3"] >= DEFAULT_GATE_HIGH_CONFIDENCE

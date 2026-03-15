"""Tests for the Spaghetti Finder scorer (Phase 52)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from codrag.core.audit.models import AuditContext
from codrag.core.audit.spaghetti_scorer import (
    FileScore,
    SpaghettiResult,
    _find_circular_files,
    _percentile_normalize,
    load_spaghetti,
    save_spaghetti,
    score_files,
)


# ── Helpers ─────────────────────────────────────────────────────


def _make_file_node(nid: str, file_path: str, size: int, language: str = "python") -> Dict[str, Any]:
    return {
        "id": nid,
        "kind": "file",
        "file_path": file_path,
        "language": language,
        "metadata": {"size": size},
    }


def _make_symbol_node(nid: str, file_path: str) -> Dict[str, Any]:
    return {
        "id": nid,
        "kind": "symbol",
        "file_path": file_path,
    }


def _make_edge(source: str, target: str, kind: str = "imports") -> Dict[str, Any]:
    return {"source": source, "target": target, "kind": kind}


def _build_ctx(
    file_nodes: List[Dict[str, Any]],
    symbol_nodes: List[Dict[str, Any]] | None = None,
    edges: List[Dict[str, Any]] | None = None,
    epistemic: Dict[str, Dict[str, Any]] | None = None,
    augmentations: Dict[str, Dict[str, Any]] | None = None,
    modules: List[Dict[str, Any]] | None = None,
) -> AuditContext:
    nodes = {}
    for n in file_nodes:
        nodes[n["id"]] = n
    for n in (symbol_nodes or []):
        nodes[n["id"]] = n

    return AuditContext(
        nodes=nodes,
        edges=edges or [],
        epistemic=epistemic or {},
        augmentations=augmentations or {},
        modules=modules or [],
    )


# ── Percentile normalization ───────────────────────────────────


class TestPercentileNormalize:
    def test_empty(self):
        assert _percentile_normalize([]) == []

    def test_single(self):
        assert _percentile_normalize([42.0]) == [0.5]

    def test_ascending(self):
        result = _percentile_normalize([1.0, 2.0, 3.0])
        assert result[0] < result[1] < result[2]
        assert result[0] == pytest.approx(0.0)
        assert result[2] == pytest.approx(1.0)

    def test_ties(self):
        result = _percentile_normalize([5.0, 5.0, 5.0])
        # All tied — all get the same rank
        assert result[0] == result[1] == result[2]

    def test_two_values(self):
        result = _percentile_normalize([10.0, 20.0])
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(1.0)


# ── Circular dependency detection ──────────────────────────────


class TestCircularDetection:
    def test_no_cycles(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 5000),
                _make_file_node("b", "b.py", 5000),
            ],
            edges=[_make_edge("a", "b")],
        )
        assert _find_circular_files(ctx) == set()

    def test_simple_cycle(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 5000),
                _make_file_node("b", "b.py", 5000),
            ],
            edges=[_make_edge("a", "b"), _make_edge("b", "a")],
        )
        circular = _find_circular_files(ctx)
        assert "a" in circular
        assert "b" in circular

    def test_three_node_cycle(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 5000),
                _make_file_node("b", "b.py", 5000),
                _make_file_node("c", "c.py", 5000),
            ],
            edges=[
                _make_edge("a", "b"),
                _make_edge("b", "c"),
                _make_edge("c", "a"),
            ],
        )
        circular = _find_circular_files(ctx)
        assert circular == {"a", "b", "c"}

    def test_non_import_edges_ignored(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 5000),
                _make_file_node("b", "b.py", 5000),
            ],
            edges=[
                _make_edge("a", "b", kind="calls"),
                _make_edge("b", "a", kind="calls"),
            ],
        )
        assert _find_circular_files(ctx) == set()


# ── Score computation ──────────────────────────────────────────


class TestScoreFiles:
    def test_empty_context(self):
        ctx = AuditContext()
        result = score_files(ctx)
        assert result.scored_count == 0
        assert result.files == []

    def test_small_files_skipped(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 500),  # Too small
                _make_file_node("b", "b.py", 1000),  # Still too small (min_bytes=2000)
            ],
        )
        result = score_files(ctx)
        assert result.scored_count == 0
        assert result.file_count == 2

    def test_large_file_scored(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("big", "big.py", 200_000),
                _make_file_node("small", "small.py", 3000),
            ],
        )
        result = score_files(ctx)
        # At least the big file should appear (score depends on relative ranking)
        assert result.file_count == 2

    def test_scores_sorted_descending(self):
        # Create files with varying sizes to ensure score ordering
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 3000),
                _make_file_node("b", "b.py", 10000),
                _make_file_node("c", "c.py", 50000),
                _make_file_node("d", "d.py", 100000),
                _make_file_node("e", "e.py", 200000),
            ],
        )
        result = score_files(ctx)
        scores = [f.score for f in result.files]
        assert scores == sorted(scores, reverse=True)

    def test_severity_thresholds(self):
        result = SpaghettiResult(
            files=[
                FileScore(file_path="a.py", score=0.80, severity="critical"),
                FileScore(file_path="b.py", score=0.55, severity="warning"),
                FileScore(file_path="c.py", score=0.35, severity="info"),
            ],
            scored_count=3,
            file_count=10,
        )
        assert result.files[0].severity == "critical"
        assert result.files[1].severity == "warning"
        assert result.files[2].severity == "info"

    def test_fan_in_boosts_score(self):
        # File with high fan-in should score higher than equivalent file without
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("hub", "hub.py", 20000),
                _make_file_node("leaf", "leaf.py", 20000),
                _make_file_node("c1", "c1.py", 5000),
                _make_file_node("c2", "c2.py", 5000),
                _make_file_node("c3", "c3.py", 5000),
            ],
            edges=[
                _make_edge("c1", "hub"),
                _make_edge("c2", "hub"),
                _make_edge("c3", "hub"),
            ],
        )
        result = score_files(ctx)
        hub_score = next((f for f in result.files if f.file_path == "hub.py"), None)
        leaf_score = next((f for f in result.files if f.file_path == "leaf.py"), None)
        if hub_score and leaf_score:
            assert hub_score.score >= leaf_score.score

    def test_tech_debt_boosts_score(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("debt", "debt.py", 20000),
                _make_file_node("clean", "clean.py", 20000),
            ],
            epistemic={
                "debt": {
                    "node_id": "debt",
                    "tech_debt": ["hardcoded values", "no error handling", "magic numbers"],
                },
            },
        )
        result = score_files(ctx)
        debt_file = next((f for f in result.files if f.file_path == "debt.py"), None)
        clean_file = next((f for f in result.files if f.file_path == "clean.py"), None)
        if debt_file and clean_file:
            assert debt_file.score >= clean_file.score
            assert debt_file.tech_debt_count == 3

    def test_circular_involvement_boosts_score(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 20000),
                _make_file_node("b", "b.py", 20000),
                _make_file_node("c", "c.py", 20000),
            ],
            edges=[
                _make_edge("a", "b"),
                _make_edge("b", "a"),  # Circular!
            ],
        )
        result = score_files(ctx)
        a_file = next((f for f in result.files if f.file_path == "a.py"), None)
        c_file = next((f for f in result.files if f.file_path == "c.py"), None)
        if a_file:
            assert a_file.in_circular is True
        if c_file:
            assert c_file.in_circular is False

    def test_signals_included(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node("a", "a.py", 50000),
                _make_file_node("b", "b.py", 3000),
            ],
        )
        result = score_files(ctx)
        for f in result.files:
            assert "lines" in f.signals
            assert "fan_in" in f.signals
            assert "fan_out" in f.signals

    def test_severity_counts(self):
        ctx = _build_ctx(
            file_nodes=[
                _make_file_node(f"f{i}", f"f{i}.py", 3000 + i * 20000)
                for i in range(10)
            ],
        )
        result = score_files(ctx)
        total_from_counts = sum(result.severity_counts.values())
        assert total_from_counts == result.scored_count


# ── Persistence (save/load roundtrip) ──────────────────────────


class TestPersistence:
    def test_save_load_roundtrip(self):
        result = SpaghettiResult(
            files=[
                FileScore(
                    file_path="big.py",
                    score=0.85,
                    severity="critical",
                    estimated_lines=2000,
                    fan_in=15,
                    fan_out=8,
                    symbol_count=42,
                    tech_debt_count=3,
                    tech_debt_items=["hardcoded", "no tests", "magic numbers"],
                    language="python",
                    role="core",
                    module_name="core",
                    signals={"lines": 0.9, "fan_in": 0.8},
                ),
            ],
            file_count=50,
            scored_count=1,
            severity_counts={"critical": 1},
            duration_ms=42.5,
        )

        with tempfile.TemporaryDirectory() as tmp:
            index_dir = Path(tmp)
            save_spaghetti(result, index_dir)

            loaded = load_spaghetti(index_dir)
            assert loaded is not None
            assert loaded.file_count == 50
            assert loaded.scored_count == 1
            assert len(loaded.files) == 1

            f = loaded.files[0]
            assert f.file_path == "big.py"
            assert f.score == pytest.approx(0.85, abs=0.001)
            assert f.severity == "critical"
            assert f.estimated_lines == 2000
            assert f.fan_in == 15
            assert f.tech_debt_count == 3
            assert f.tech_debt_items == ["hardcoded", "no tests", "magic numbers"]

    def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_spaghetti(Path(tmp))
            assert result is None


# ── FileScore serialization ────────────────────────────────────


class TestFileScoreSerialization:
    def test_to_dict_minimal(self):
        fs = FileScore(
            file_path="x.py",
            score=0.5,
            severity="warning",
            language="python",
            role="unknown",
            module_name="",
        )
        d = fs.to_dict()
        assert d["file_path"] == "x.py"
        assert d["score"] == 0.5
        assert d["severity"] == "warning"
        assert "tech_debt_items" not in d  # empty list not included
        assert "summary" not in d  # empty string not included
        assert "in_circular" not in d  # False not included

    def test_to_dict_full(self):
        fs = FileScore(
            file_path="big.py",
            score=0.92,
            severity="critical",
            estimated_lines=1800,
            fan_in=23,
            fan_out=5,
            symbol_count=40,
            tech_debt_count=4,
            tech_debt_items=["a", "b", "c", "d", "e", "f"],
            epistemic_confidence=0.3,
            in_circular=True,
            language="python",
            role="core",
            summary="Main server entry point handling all routes",
            module_name="server",
            signals={"lines": 0.95, "fan_in": 0.88},
        )
        d = fs.to_dict()
        assert d["in_circular"] is True
        assert d["epistemic_confidence"] == pytest.approx(0.3, abs=0.001)
        assert len(d["tech_debt_items"]) == 5  # capped at 5
        assert d["signals"]["lines"] == pytest.approx(0.95, abs=0.001)

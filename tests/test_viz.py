"""
Tests for prep.viz — all CLI visualization modules.

These tests verify that each render function runs without error and produces
output to the console. They do NOT assert specific visual formatting (that's
what Storybook is for), but they ensure the data flow doesn't crash.
"""

import io
from datetime import date, timedelta

import pytest
from rich.console import Console

from prep.viz.activity_heatmap import (
    ActivityDay,
    ActivityHeatmapData,
    generate_sample_data,
    get_cell_char,
    render_activity_heatmap,
)
from prep.viz.context import render_relevance_spectrum, render_token_budget
from prep.viz.coverage import render_file_coverage
from prep.viz.drift import render_drift_report
from prep.viz.flow import render_rag_flow
from prep.viz.health import render_index_health
from prep.viz.overview import render_dashboard
from prep.viz.trace import render_trace_stats


# ── Helpers ──────────────────────────────────────────────────────

def _capture_console() -> Console:
    """Create a console that captures output to a string buffer."""
    return Console(file=io.StringIO(), force_terminal=True, width=120)


def _get_output(console: Console) -> str:
    return console.file.getvalue()


# ═══════════════════════════════════════════════════════════════════
# activity_heatmap.py
# ═══════════════════════════════════════════════════════════════════


class TestActivityDay:
    def test_dataclass_fields(self):
        day = ActivityDay(date="2026-01-15", embeddings=10, trace=5, builds=1)
        assert day.date == "2026-01-15"
        assert day.embeddings == 10
        assert day.trace == 5
        assert day.builds == 1


class TestActivityHeatmapData:
    def test_dataclass_fields(self):
        days = [ActivityDay(date="2026-01-15", embeddings=10, trace=5, builds=1)]
        data = ActivityHeatmapData(days=days, totals={"embeddings": 10, "trace": 5, "builds": 1})
        assert len(data.days) == 1
        assert data.totals["embeddings"] == 10


class TestGetCellChar:
    def test_no_activity_returns_dim(self):
        char, color = get_cell_char(0, 0, 100, 100)
        assert char == "░"
        assert color == "dim"

    def test_pure_embedding_returns_cyan(self):
        char, color = get_cell_char(50, 0, 100, 100)
        assert color == "cyan"

    def test_pure_trace_returns_yellow(self):
        char, color = get_cell_char(0, 50, 100, 100)
        assert color == "yellow"

    def test_mixed_returns_green(self):
        char, color = get_cell_char(50, 50, 100, 100)
        assert color == "green"

    def test_high_intensity_returns_full_block(self):
        char, _ = get_cell_char(100, 0, 100, 100)
        assert char == "█"

    def test_low_intensity_returns_light_block(self):
        char, _ = get_cell_char(10, 0, 100, 100)
        assert char == "░"

    def test_zero_max_doesnt_crash(self):
        char, color = get_cell_char(0, 0, 0, 0)
        assert char == "░"


class TestGenerateSampleData:
    def test_returns_activity_heatmap_data(self):
        data = generate_sample_data(4)
        assert isinstance(data, ActivityHeatmapData)
        assert isinstance(data.totals, dict)
        assert "embeddings" in data.totals

    def test_different_weeks(self):
        short = generate_sample_data(2)
        long = generate_sample_data(26)
        # More weeks should generally produce more days (probabilistic)
        assert isinstance(short, ActivityHeatmapData)
        assert isinstance(long, ActivityHeatmapData)


class TestRenderActivityHeatmap:
    def test_renders_without_error(self):
        console = _capture_console()
        data = generate_sample_data(4)
        render_activity_heatmap(data, weeks=4, console=console)
        output = _get_output(console)
        assert "Activity" in output
        assert "Embeddings" in output

    def test_renders_with_no_labels(self):
        console = _capture_console()
        data = generate_sample_data(4)
        render_activity_heatmap(data, weeks=4, show_labels=False, console=console)
        output = _get_output(console)
        assert "Activity" in output

    def test_renders_with_no_legend(self):
        console = _capture_console()
        data = generate_sample_data(4)
        render_activity_heatmap(data, weeks=4, show_legend=False, console=console)
        output = _get_output(console)
        assert "Activity" in output

    def test_renders_empty_data(self):
        console = _capture_console()
        data = ActivityHeatmapData(days=[], totals={"embeddings": 0, "trace": 0, "builds": 0})
        render_activity_heatmap(data, weeks=4, console=console)
        output = _get_output(console)
        assert "Activity" in output


# ═══════════════════════════════════════════════════════════════════
# context.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderTokenBudget:
    def test_basic_render(self):
        console = _capture_console()
        render_token_budget(4000, 8192, console=console)
        output = _get_output(console)
        assert "Token Budget" in output

    def test_with_breakdown(self):
        console = _capture_console()
        render_token_budget(4000, 8192, breakdown={"system": 500, "query": 100, "chunks": 3400}, console=console)
        output = _get_output(console)
        assert "Breakdown" in output

    def test_over_budget(self):
        console = _capture_console()
        render_token_budget(9000, 8192, console=console)
        output = _get_output(console)
        assert "Token Budget" in output

    def test_zero_usage(self):
        console = _capture_console()
        render_token_budget(0, 8192, console=console)
        output = _get_output(console)
        assert "0" in output


class TestRenderRelevanceSpectrum:
    def test_basic_render(self):
        console = _capture_console()
        results = [
            {"score": 0.92, "doc": {"source_path": "src/main.py"}},
            {"score": 0.75, "doc": {"source_path": "src/utils.py"}},
            {"score": 0.50, "doc": {"source_path": "tests/test.py"}},
        ]
        render_relevance_spectrum(results, console=console)
        output = _get_output(console)
        assert "Search Analysis" in output

    def test_empty_results(self):
        console = _capture_console()
        render_relevance_spectrum([], console=console)
        output = _get_output(console)
        # Should not crash; no output expected
        assert output == "" or "Search" not in output

    def test_many_results_truncated(self):
        console = _capture_console()
        results = [{"score": 0.5 + i * 0.05, "doc": {"source_path": f"file{i}.py"}} for i in range(10)]
        render_relevance_spectrum(results, console=console)
        output = _get_output(console)
        assert "more results" in output


# ═══════════════════════════════════════════════════════════════════
# coverage.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderFileCoverage:
    def test_basic_tree(self):
        console = _capture_console()
        tree = {
            "name": "src",
            "type": "dir",
            "coverage": 0.8,
            "children": [
                {"name": "main.py", "type": "file", "status": "indexed"},
                {"name": "old.py", "type": "file", "status": "excluded"},
            ],
        }
        render_file_coverage(tree, console=console)
        output = _get_output(console)
        assert "File Coverage" in output
        assert "main.py" in output

    def test_nested_dirs(self):
        console = _capture_console()
        tree = {
            "name": "root",
            "type": "dir",
            "coverage": 0.5,
            "children": [
                {
                    "name": "api",
                    "type": "dir",
                    "coverage": 1.0,
                    "children": [
                        {"name": "server.py", "type": "file", "status": "indexed"},
                    ],
                },
            ],
        }
        render_file_coverage(tree, console=console)
        output = _get_output(console)
        assert "api" in output

    def test_empty_tree(self):
        console = _capture_console()
        tree = {"name": "empty", "type": "dir", "coverage": 0.0, "children": []}
        render_file_coverage(tree, console=console)
        output = _get_output(console)
        assert "empty" in output

    def test_error_status_file(self):
        console = _capture_console()
        tree = {
            "name": "src",
            "type": "dir",
            "children": [
                {"name": "broken.py", "type": "file", "status": "error"},
            ],
        }
        render_file_coverage(tree, console=console)
        output = _get_output(console)
        assert "broken.py" in output


# ═══════════════════════════════════════════════════════════════════
# drift.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderDriftReport:
    def test_basic_render(self):
        console = _capture_console()
        stats = {
            "freshness_score": 85.0,
            "total_files": 100,
            "fresh_files": 85,
            "stale_files": 10,
            "missing_files": 5,
        }
        render_drift_report(stats, console=console)
        output = _get_output(console)
        assert "Index Drift" in output
        assert "85.0%" in output

    def test_with_rotting_files(self):
        console = _capture_console()
        stats = {"freshness_score": 70.0, "total_files": 50, "fresh_files": 35, "stale_files": 10, "missing_files": 5}
        rotting = [
            {"path": "src/old.py", "age_gap": "2h"},
            {"path": "src/stale.py", "age_gap": "1h"},
        ]
        render_drift_report(stats, rotting_files=rotting, console=console)
        output = _get_output(console)
        assert "Rotting" in output
        assert "src/old.py" in output

    def test_perfect_score(self):
        console = _capture_console()
        stats = {"freshness_score": 100.0, "total_files": 50, "fresh_files": 50, "stale_files": 0, "missing_files": 0}
        render_drift_report(stats, console=console)
        output = _get_output(console)
        assert "100.0%" in output

    def test_zero_score(self):
        console = _capture_console()
        stats = {"freshness_score": 0.0, "total_files": 0, "fresh_files": 0, "stale_files": 0, "missing_files": 0}
        render_drift_report(stats, console=console)
        output = _get_output(console)
        assert "0.0%" in output


# ═══════════════════════════════════════════════════════════════════
# flow.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderRagFlow:
    def test_basic_render(self):
        console = _capture_console()
        trace = {
            "query": "How does auth work?",
            "embedding_model": "nomic-embed-text",
            "embedding_ms": 45,
            "retrieval_count": 50,
            "retrieval_ms": 12,
            "rerank_count": 5,
            "rerank_ms": 8,
            "context_tokens": 4000,
            "context_limit": 8192,
            "llm_model": "gpt-4",
            "llm_ms": 2000,
            "top_chunks": [
                {"path": "src/auth.py", "score": 0.92},
            ],
        }
        render_rag_flow(trace, console=console)
        output = _get_output(console)
        assert "RAG Pipeline" in output
        assert "auth" in output.lower()

    def test_minimal_data(self):
        console = _capture_console()
        render_rag_flow({}, console=console)
        output = _get_output(console)
        assert "RAG Pipeline" in output

    def test_many_chunks(self):
        console = _capture_console()
        trace = {
            "query": "test",
            "top_chunks": [{"path": f"f{i}.py", "score": 0.9 - i * 0.1} for i in range(10)],
            "context_tokens": 4000,
            "context_limit": 8192,
        }
        render_rag_flow(trace, console=console)
        output = _get_output(console)
        assert "more" in output


# ═══════════════════════════════════════════════════════════════════
# health.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderIndexHealth:
    def test_basic_render(self):
        console = _capture_console()
        stats = {
            "total_files": 1000,
            "indexed_files": 800,
            "embeddings_count": 3000,
            "trace_nodes": 500,
            "trace_edges": 1500,
            "last_build": "2026-01-01",
            "disk_usage_mb": 25.0,
        }
        render_index_health(stats, console=console)
        output = _get_output(console)
        assert len(output) > 0

    def test_empty_stats(self):
        console = _capture_console()
        render_index_health({}, console=console)
        output = _get_output(console)
        assert len(output) > 0

    def test_zero_files(self):
        console = _capture_console()
        stats = {"total_files": 0, "indexed_files": 0}
        render_index_health(stats, console=console)
        # Should not divide by zero
        output = _get_output(console)
        assert len(output) > 0


# ═══════════════════════════════════════════════════════════════════
# trace.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderTraceStats:
    def test_basic_render(self):
        console = _capture_console()
        stats = {"node_count": 500, "edge_count": 1200, "avg_degree": 4.8}
        render_trace_stats(stats, console=console)
        output = _get_output(console)
        assert "Trace Index" in output

    def test_with_hubs(self):
        console = _capture_console()
        stats = {"node_count": 500, "edge_count": 1200, "avg_degree": 4.8}
        hubs = [
            {"name": "IndexManager", "kind": "class", "degree": 42},
            {"name": "build_graph", "kind": "function", "degree": 35},
        ]
        render_trace_stats(stats, top_hubs=hubs, console=console)
        output = _get_output(console)
        assert "IndexManager" in output
        assert "Hubs" in output

    def test_empty_stats(self):
        console = _capture_console()
        render_trace_stats({}, console=console)
        output = _get_output(console)
        assert "Trace Index" in output


# ═══════════════════════════════════════════════════════════════════
# overview.py
# ═══════════════════════════════════════════════════════════════════


class TestRenderDashboard:
    def test_basic_render(self):
        console = _capture_console()
        health = {
            "total_files": 100,
            "indexed_files": 80,
            "embeddings_count": 300,
            "trace_nodes": 50,
            "trace_edges": 100,
            "last_build": "2026-01-01",
            "disk_usage_mb": 10.0,
        }
        activity = generate_sample_data(4)
        trace = {"node_count": 50, "edge_count": 100, "avg_degree": 4.0}
        render_dashboard(health, activity, trace, weeks=4, console=console)
        output = _get_output(console)
        assert "Dashboard" in output


# ═══════════════════════════════════════════════════════════════════
# __init__.py exports
# ═══════════════════════════════════════════════════════════════════


class TestVizExports:
    def test_all_exports_importable(self):
        from prep.viz import (
            render_activity_heatmap,
            ActivityDay,
            ActivityHeatmapData,
            render_index_health,
            render_token_budget,
            render_relevance_spectrum,
            render_trace_stats,
            render_file_coverage,
            render_dashboard,
            render_drift_report,
            render_rag_flow,
        )
        # Just verify they're callable
        assert callable(render_activity_heatmap)
        assert callable(render_index_health)
        assert callable(render_token_budget)
        assert callable(render_relevance_spectrum)
        assert callable(render_trace_stats)
        assert callable(render_file_coverage)
        assert callable(render_dashboard)
        assert callable(render_drift_report)
        assert callable(render_rag_flow)

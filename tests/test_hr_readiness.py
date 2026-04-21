"""Tests for HR readiness scoring."""
from prep.agents.hr.readiness import compute_readiness, ReadinessReport


class TestComputeReadiness:
    def test_empty_data_scores_zero(self) -> None:
        report = compute_readiness(modules=[], atlas_content="", file_count=0)
        assert report.score == 0.0
        assert not report.ready_for_auto
        assert not report.ready_for_list

    def test_minimal_data_allows_list_mode(self) -> None:
        modules = [
            {"name": "core", "member_files": ["a.py", "b.py"] * 10, "domain_tags": ["backend"]},
            {"name": "api", "member_files": ["c.py"] * 10, "domain_tags": ["api"]},
        ]
        report = compute_readiness(
            modules=modules,
            atlas_content="# Project Atlas\nSome content here",
            file_count=30,
        )
        assert report.score >= 0.4
        assert report.ready_for_list
        assert not report.ready_for_auto

    def test_rich_data_allows_auto_mode(self) -> None:
        modules = [
            {"name": "core", "member_files": [f"core/{i}.py" for i in range(15)],
             "domain_tags": ["backend", "database"], "architecture_layer": "core"},
            {"name": "api", "member_files": [f"api/{i}.py" for i in range(10)],
             "domain_tags": ["api", "rest"], "architecture_layer": "api"},
            {"name": "ui", "member_files": [f"ui/{i}.tsx" for i in range(10)],
             "domain_tags": ["frontend", "react"], "architecture_layer": "presentation"},
        ]
        report = compute_readiness(
            modules=modules,
            atlas_content="# Atlas\n" + "x" * 200,
            file_count=50,
            has_hub_files=True,
            has_docs=True,
        )
        assert report.score >= 0.7
        assert report.ready_for_auto
        assert report.ready_for_list

    def test_report_has_dimension_breakdown(self) -> None:
        report = compute_readiness(modules=[], atlas_content="", file_count=0)
        assert "pipeline_completion" in report.dimensions
        assert "file_count" in report.dimensions
        assert "module_count" in report.dimensions
        assert "domain_coverage" in report.dimensions
        assert "layer_diversity" in report.dimensions
        assert "documentation" in report.dimensions
        assert "hub_files" in report.dimensions

    def test_missing_checklist_populated(self) -> None:
        report = compute_readiness(modules=[], atlas_content="", file_count=5)
        assert len(report.missing) > 0
        assert any("pipeline" in m.lower() or "file" in m.lower() for m in report.missing)

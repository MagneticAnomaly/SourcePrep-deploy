"""Tests for Researcher prompt template rendering."""
from prep.agents.researcher.prompts import (
    render_topic_selection_prompt,
    render_research_prompt,
    render_plan_formulation_prompt,
)


class TestTopicSelectionPrompt:
    def test_includes_findings(self) -> None:
        findings = [
            {"id": "f1", "title": "Dead imports", "priority": "P1",
             "description": "12 unused imports", "affected_files": ["a.py"]},
            {"id": "f2", "title": "Circular dep", "priority": "P0",
             "description": "core <-> api cycle", "affected_files": ["b.py"]},
        ]
        result = render_topic_selection_prompt(
            findings=findings, max_topics=3,
            atlas_excerpt="Python backend app",
        )
        assert "Dead imports" in result
        assert "Circular dep" in result
        assert "3" in result

    def test_includes_atlas_context(self) -> None:
        result = render_topic_selection_prompt(
            findings=[{"id": "f1", "title": "Bug", "priority": "P2",
                       "description": "desc", "affected_files": []}],
            max_topics=3, atlas_excerpt="React + FastAPI monolith",
        )
        assert "React + FastAPI" in result


class TestResearchPrompt:
    def test_includes_topic_details(self) -> None:
        result = render_research_prompt(
            topic_title="Circular dependency in core",
            topic_description="core imports api which imports core",
            affected_files=["src/core/main.py", "src/api/routes.py"],
            code_context="def main(): from api import routes",
            impact_summary="15 files affected",
        )
        assert "Circular dependency" in result
        assert "src/core/main.py" in result
        assert "15 files affected" in result

    def test_includes_code_context(self) -> None:
        result = render_research_prompt(
            topic_title="Bug", topic_description="desc",
            affected_files=[], code_context="class Foo: pass",
            impact_summary="",
        )
        assert "class Foo" in result


class TestPlanFormulationPrompt:
    def test_includes_research_output(self) -> None:
        result = render_plan_formulation_prompt(
            topic_title="Fix circular deps",
            research_output="Extract shared module to break cycle",
            affected_files=["a.py", "b.py"],
        )
        assert "Fix circular deps" in result
        assert "Extract shared module" in result
        assert "a.py" in result

    def test_requests_structured_output(self) -> None:
        result = render_plan_formulation_prompt(
            topic_title="T", research_output="R", affected_files=[],
        )
        assert "root_cause" in result
        assert "fix_steps" in result
        assert "effort" in result
        assert "risk" in result

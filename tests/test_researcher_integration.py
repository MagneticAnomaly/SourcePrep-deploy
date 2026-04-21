# tests/test_researcher_integration.py
"""Integration tests for the full Researcher Agent pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from prep.agents.researcher import ResearcherEngine, ResearchHistory
from prep.agents.shared.models import ResearchPlan


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "Select the top" in prompt or "select" in prompt.lower()[:50]:
        return json.dumps([
            {"finding_id": "f1", "rationale": "Critical arch issue"},
            {"finding_id": "f2", "rationale": "Security risk"},
        ]), 60
    if "Research a solution" in prompt:
        return "## Analysis\nRoot cause is bad coupling.\n## Fix\nExtract module.", 100
    if "Convert this research" in prompt:
        return json.dumps({
            "root_cause": "Bad coupling between modules",
            "fix_steps": ["Extract shared types", "Update imports", "Add tests"],
            "effort": "medium",
            "risk": "low",
            "testing_strategy": "Run full test suite after refactor",
        }), 80
    return "ok", 10


@pytest.fixture
def rich_index(tmp_path: Path) -> Path:
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(20)],
         "domain_tags": ["backend", "database"], "architecture_layer": "core",
         "summary": "Core logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(15)],
         "domain_tags": ["api", "rest"], "architecture_layer": "api",
         "summary": "REST API"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text(
        "# Atlas\nFull-stack Python app.\n" + "x" * 200
    )
    return tmp_path


def _findings():
    return [
        {"id": "f1", "title": "Circular dependency", "priority": "P0",
         "description": "core <-> api", "severity": "high",
         "affected_files": ["core/main.py"], "category": "architecture"},
        {"id": "f2", "title": "Hardcoded secret", "priority": "P1",
         "description": "API key in source", "severity": "high",
         "affected_files": ["config.py"], "category": "security"},
        {"id": "f3", "title": "Dead code", "priority": "P3",
         "description": "Unused utils", "severity": "low",
         "affected_files": ["utils.py"], "category": "maintenance"},
    ]


class TestResearcherEndToEnd:
    def test_full_pipeline(self, rich_index: Path) -> None:
        engine = ResearcherEngine(index_dir=rich_index, project_id="integ_test")

        plans = engine.run(findings=_findings(), llm_fn=_fake_llm, max_topics=2)

        assert len(plans) == 2
        for plan in plans:
            assert isinstance(plan, ResearchPlan)
            assert plan.root_cause
            assert len(plan.fix_steps) > 0
            assert plan.effort in ("small", "medium", "large")

        latest = engine.history.get_latest()
        assert latest is not None
        assert len(latest["plans"]) == 2

        project, _, issues = engine.package_for_push(plans)
        assert "Research" in project.name
        assert len(issues) == 2

    def test_history_survives_restart(self, rich_index: Path) -> None:
        e1 = ResearcherEngine(index_dir=rich_index, project_id="test")
        e1.run(findings=_findings(), llm_fn=_fake_llm, max_topics=1)

        e2 = ResearcherEngine(index_dir=rich_index, project_id="test")
        assert len(e2.history.list_runs()) == 1

    def test_stage_by_stage_execution(self, rich_index: Path) -> None:
        engine = ResearcherEngine(index_dir=rich_index, project_id="test")

        topics = engine.select_topics(_findings(), _fake_llm, max_topics=1)
        assert len(topics) == 1

        research = engine.research_topic(topics[0], _fake_llm)
        assert len(research) > 0

        plan = engine.formulate_plan(topics[0], research, _fake_llm)
        assert plan.topic_id == topics[0].finding_id

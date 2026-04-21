# tests/test_researcher_engine.py
"""Tests for ResearcherEngine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from prep.agents.researcher.engine import ResearcherEngine
from prep.agents.shared.models import ResearchPlan, ResearchTopic


def _make_findings_jsonl(tmp_path: Path) -> None:
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(15)],
         "domain_tags": ["backend", "database"], "architecture_layer": "core",
         "summary": "Core business logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(10)],
         "domain_tags": ["api", "rest"], "architecture_layer": "api",
         "summary": "REST API layer"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text(
        "# Test Project\nPython backend with REST API"
    )


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "Select the top" in prompt or "select" in prompt.lower()[:50]:
        return json.dumps([
            {"finding_id": "f1", "rationale": "High impact circular dep"},
            {"finding_id": "f2", "rationale": "Security concern"},
        ]), 60
    if "Research a solution" in prompt:
        return (
            "## Root Cause\nBidirectional import between core and api.\n"
            "## Solution\nExtract shared types into a new module.\n"
            "## Steps\n1. Create shared_types.py\n2. Move types\n3. Update imports\n"
        ), 100
    if "Convert this research" in prompt:
        return json.dumps({
            "root_cause": "Bidirectional import between core and api",
            "fix_steps": ["Create shared_types.py", "Move types", "Update imports"],
            "effort": "medium",
            "risk": "low",
            "testing_strategy": "Run import cycle checker",
        }), 80
    return "ok", 10


def _sample_findings() -> List[Dict[str, Any]]:
    return [
        {"id": "f1", "title": "Circular dependency", "priority": "P0",
         "description": "core <-> api import cycle", "severity": "high",
         "affected_files": ["src/core/main.py", "src/api/routes.py"],
         "category": "architecture"},
        {"id": "f2", "title": "Hardcoded secrets", "priority": "P1",
         "description": "API key in config.py", "severity": "high",
         "affected_files": ["src/config.py"],
         "category": "security"},
        {"id": "f3", "title": "Dead code", "priority": "P2",
         "description": "Unused helper functions", "severity": "low",
         "affected_files": ["src/utils.py"],
         "category": "maintenance"},
    ]


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    _make_findings_jsonl(tmp_path)
    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> ResearcherEngine:
    return ResearcherEngine(index_dir=engine_dir, project_id="test_proj")


# -- Task 3: Topic Selection Tests --

class TestTopicSelection:
    def test_select_topics_returns_research_topics(self, engine: ResearcherEngine) -> None:
        topics = engine.select_topics(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=2)
        assert len(topics) == 2
        assert all(isinstance(t, ResearchTopic) for t in topics)

    def test_select_topics_uses_finding_data(self, engine: ResearcherEngine) -> None:
        topics = engine.select_topics(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=2)
        assert topics[0].finding_id == "f1"
        assert topics[0].title == "Circular dependency"

    def test_select_topics_with_no_findings(self, engine: ResearcherEngine) -> None:
        topics = engine.select_topics(findings=[], llm_fn=_fake_llm, max_topics=3)
        assert topics == []

    def test_select_topics_caps_at_max(self, engine: ResearcherEngine) -> None:
        topics = engine.select_topics(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=1)
        assert len(topics) <= 1

    def test_select_topics_raises_on_bad_llm_json(self, engine: ResearcherEngine) -> None:
        def bad_llm(prompt: str, **kw) -> Tuple[str, int]:
            return "not json", 10
        with pytest.raises(ValueError, match="topic selection"):
            engine.select_topics(findings=_sample_findings(), llm_fn=bad_llm, max_topics=2)


# -- Task 4: Research Synthesis + Plan Formulation Tests --

class TestResearchSynthesis:
    def test_research_topic_returns_string(self, engine: ResearcherEngine) -> None:
        topic = ResearchTopic(
            finding_id="f1", title="Circular dependency",
            description="core <-> api cycle",
            affected_files=["src/core/main.py"],
        )
        result = engine.research_topic(topic, llm_fn=_fake_llm)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_research_includes_analysis(self, engine: ResearcherEngine) -> None:
        topic = ResearchTopic(
            finding_id="f1", title="Circular dependency",
            description="core <-> api cycle",
            affected_files=["src/core/main.py"],
        )
        result = engine.research_topic(topic, llm_fn=_fake_llm)
        assert "Root Cause" in result or "Solution" in result


class TestPlanFormulation:
    def test_formulate_returns_research_plan(self, engine: ResearcherEngine) -> None:
        topic = ResearchTopic(finding_id="f1", title="Fix circular deps", description="core <-> api cycle")
        plan = engine.formulate_plan(topic=topic, research_output="Extract shared module", llm_fn=_fake_llm)
        assert isinstance(plan, ResearchPlan)
        assert plan.topic_id == "f1"
        assert plan.title == "Fix circular deps"

    def test_plan_has_fix_steps(self, engine: ResearcherEngine) -> None:
        topic = ResearchTopic(finding_id="f1", title="Fix it", description="desc")
        plan = engine.formulate_plan(topic=topic, research_output="Do this", llm_fn=_fake_llm)
        assert len(plan.fix_steps) > 0

    def test_plan_has_effort_and_risk(self, engine: ResearcherEngine) -> None:
        topic = ResearchTopic(finding_id="f1", title="T", description="D")
        plan = engine.formulate_plan(topic=topic, research_output="Research", llm_fn=_fake_llm)
        assert plan.effort in ("small", "medium", "large")
        assert plan.risk in ("low", "medium", "high")

    def test_formulate_raises_on_bad_json(self, engine: ResearcherEngine) -> None:
        def bad_llm(prompt: str, **kw) -> Tuple[str, int]:
            return "not json", 10
        topic = ResearchTopic(finding_id="f1", title="T", description="D")
        with pytest.raises(ValueError, match="plan formulation"):
            engine.formulate_plan(topic=topic, research_output="R", llm_fn=bad_llm)


# -- Task 5: Full Pipeline + History Tests --

class TestFullPipeline:
    def test_run_produces_plans(self, engine: ResearcherEngine) -> None:
        plans = engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=2)
        assert len(plans) == 2
        assert all(isinstance(p, ResearchPlan) for p in plans)

    def test_run_saves_to_history(self, engine: ResearcherEngine) -> None:
        engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=2)
        latest = engine.history.get_latest()
        assert latest is not None
        assert len(latest["plans"]) == 2

    def test_run_with_empty_findings(self, engine: ResearcherEngine) -> None:
        plans = engine.run(findings=[], llm_fn=_fake_llm)
        assert plans == []

    def test_multiple_runs_accumulate_history(self, engine: ResearcherEngine) -> None:
        engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=1)
        engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=1)
        assert len(engine.history.list_runs()) == 2


from prep.adapters.pm_models import PMProject, PMGoal, PMIssue


class TestPushPackaging:
    def test_package_plans_returns_pm_models(self, engine: ResearcherEngine) -> None:
        plans = engine.run(findings=_sample_findings(), llm_fn=_fake_llm, max_topics=2)
        project, goals, issues = engine.package_for_push(plans)
        assert isinstance(project, PMProject)
        assert len(issues) >= 1

    def test_project_has_research_title(self, engine: ResearcherEngine) -> None:
        plans = [ResearchPlan(
            topic_id="f1", title="Fix circular deps",
            root_cause="Cycle", fix_steps=["Step 1"],
            effort="medium", risk="low",
        )]
        project, _, _ = engine.package_for_push(plans)
        assert "Research" in project.name

    def test_issues_have_plan_details(self, engine: ResearcherEngine) -> None:
        plans = [ResearchPlan(
            topic_id="f1", title="Fix it",
            root_cause="Bad design",
            fix_steps=["Step A", "Step B"],
            effort="large", risk="high",
            testing_strategy="Integration tests",
        )]
        _, _, issues = engine.package_for_push(plans)
        assert len(issues) == 1
        assert "Fix it" in issues[0].title
        assert "Bad design" in issues[0].description

    def test_empty_plans_returns_empty(self, engine: ResearcherEngine) -> None:
        project, goals, issues = engine.package_for_push([])
        assert project.name
        assert issues == []

"""Tests for CustodianEngine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from prep.agents.custodian.engine import CustodianEngine
from prep.agents.shared.models import CleanupCandidate, CleanupPlan


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "safe to delete" in prompt.lower() or "reviewing a code file" in prompt.lower():
        return json.dumps({
            "classification": "SAFE_TO_DELETE",
            "reason": "No dynamic imports, no config refs, no public API usage",
        }), 40
    return "ok", 10


def _fake_llm_needs_review(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "safe to delete" in prompt.lower() or "reviewing a code file" in prompt.lower():
        return json.dumps({
            "classification": "NEEDS_REVIEW",
            "reason": "Possible dynamic import via importlib",
        }), 40
    return "ok", 10


def _sample_findings() -> List[Dict[str, Any]]:
    return [
        {"id": "ARCH-17", "title": "Orphaned test fixture",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["tests/old_fixture.py"],
         "description": "Test fixture with 0 dependents"},
        {"id": "ARCH-22", "title": "Unused utility module",
         "category": "dead_code", "priority": "P2",
         "affected_files": ["src/utils/old_helpers.py"],
         "description": "Helper functions never imported"},
        {"id": "SEC-1", "title": "Hardcoded secret",
         "category": "security", "priority": "P0",
         "affected_files": ["config.py"],
         "description": "Not dead code — should be ignored"},
    ]


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    (tmp_path / "codebase_atlas.md").write_text("# Test Project")
    modules = [{"name": "core", "member_files": ["core/a.py"] * 10,
                "domain_tags": ["backend"], "architecture_layer": "core"}]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules))
    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> CustodianEngine:
    return CustodianEngine(index_dir=engine_dir, project_id="test_proj")


class TestDiscovery:
    def test_discover_filters_dead_code_findings(self, engine: CustodianEngine) -> None:
        candidates = engine.discover(_sample_findings())
        assert all(c.finding_id != "SEC-1" for c in candidates)
        assert len(candidates) == 2

    def test_discover_creates_cleanup_candidates(self, engine: CustodianEngine) -> None:
        candidates = engine.discover(_sample_findings())
        assert all(isinstance(c, CleanupCandidate) for c in candidates)
        assert candidates[0].file_path == "tests/old_fixture.py"

    def test_discover_empty_findings(self, engine: CustodianEngine) -> None:
        assert engine.discover([]) == []

    def test_discover_respects_max_candidates(self, engine: CustodianEngine) -> None:
        candidates = engine.discover(_sample_findings(), max_candidates=1)
        assert len(candidates) <= 1


class TestSafetyVerification:
    def test_verify_classifies_safe(self, engine: CustodianEngine) -> None:
        candidate = CleanupCandidate(file_path="old.py", finding_id="ARCH-1", dependent_count=0)
        verified = engine.verify_candidate(candidate, llm_fn=_fake_llm)
        assert verified.classification == "safe_to_delete"

    def test_verify_classifies_needs_review(self, engine: CustodianEngine) -> None:
        candidate = CleanupCandidate(file_path="old.py", finding_id="ARCH-1", dependent_count=0)
        verified = engine.verify_candidate(candidate, llm_fn=_fake_llm_needs_review)
        assert verified.classification == "needs_review"

    def test_verify_populates_reason(self, engine: CustodianEngine) -> None:
        candidate = CleanupCandidate(file_path="old.py", finding_id="ARCH-1", dependent_count=0)
        verified = engine.verify_candidate(candidate, llm_fn=_fake_llm)
        assert verified.reason

    def test_verify_raises_on_bad_json(self, engine: CustodianEngine) -> None:
        def bad_llm(prompt: str, **kw) -> Tuple[str, int]:
            return "not json", 10
        candidate = CleanupCandidate(file_path="old.py", finding_id="ARCH-1", dependent_count=0)
        with pytest.raises(ValueError, match="safety verification"):
            engine.verify_candidate(candidate, llm_fn=bad_llm)


class TestCleanupPlan:
    def test_plan_includes_only_safe_candidates(self, engine: CustodianEngine) -> None:
        candidates = [
            CleanupCandidate(file_path="a.py", finding_id="A1", dependent_count=0, classification="safe_to_delete"),
            CleanupCandidate(file_path="b.py", finding_id="A2", dependent_count=0, classification="needs_review"),
        ]
        plan = engine.plan_cleanup(candidates)
        assert len(plan.candidates) == 1
        assert plan.candidates[0].file_path == "a.py"

    def test_plan_caps_at_max_files(self, engine: CustodianEngine) -> None:
        candidates = [
            CleanupCandidate(file_path=f"f{i}.py", finding_id=f"A{i}", dependent_count=0, classification="safe_to_delete")
            for i in range(30)
        ]
        plan = engine.plan_cleanup(candidates, max_files=5)
        assert len(plan.candidates) == 5

    def test_plan_has_branch_name(self, engine: CustodianEngine) -> None:
        plan = engine.plan_cleanup([])
        assert plan.branch_name.startswith("custodian/cleanup-")

    def test_plan_defaults_to_dry_run(self, engine: CustodianEngine) -> None:
        plan = engine.plan_cleanup([])
        assert plan.dry_run is True


class TestPushPackaging:
    def test_package_returns_pm_models(self, engine: CustodianEngine) -> None:
        plan = CleanupPlan(
            candidates=[CleanupCandidate(file_path="old.py", finding_id="A1",
                dependent_count=0, classification="safe_to_delete", reason="Dead code")],
            dry_run=True)
        project, goals, issues = engine.package_for_push(plan)
        assert "Cleanup" in project.name
        assert len(issues) == 1
        assert "old.py" in issues[0].title

    def test_empty_plan_returns_empty_issues(self, engine: CustodianEngine) -> None:
        plan = CleanupPlan(candidates=[], dry_run=True)
        _, _, issues = engine.package_for_push(plan)
        assert issues == []


class TestFullPipeline:
    def test_run_produces_cleanup_plan(self, engine: CustodianEngine) -> None:
        plan = engine.run(findings=_sample_findings(), llm_fn=_fake_llm)
        assert isinstance(plan, CleanupPlan)
        assert plan.dry_run is True

    def test_run_filters_and_verifies(self, engine: CustodianEngine) -> None:
        plan = engine.run(findings=_sample_findings(), llm_fn=_fake_llm)
        for c in plan.candidates:
            assert c.classification == "safe_to_delete"

    def test_run_with_empty_findings(self, engine: CustodianEngine) -> None:
        plan = engine.run(findings=[], llm_fn=_fake_llm)
        assert plan.candidates == []

    def test_run_with_needs_review_llm(self, engine: CustodianEngine) -> None:
        plan = engine.run(findings=_sample_findings(), llm_fn=_fake_llm_needs_review)
        assert plan.candidates == []

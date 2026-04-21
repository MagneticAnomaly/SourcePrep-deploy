"""Integration tests for the full Staffing Agent pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from prep.agents.hr import StaffingEngine, ReadinessReport, Roster


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    if "AGENTS.md" in prompt:
        return "# Agent Instructions\n\nYou are the role. Focus on core module.", 50
    if "SOUL.md" in prompt:
        return "# Soul\n\nI am the role. I value code quality.", 30
    if "Analyze this codebase" in prompt:
        return json.dumps([
            {"slug": "backend_dev", "display_name": "Backend Developer",
             "justification": "Core module", "primary_modules": ["core"],
             "domain_focus": ["backend"]},
            {"slug": "api_eng", "display_name": "API Engineer",
             "justification": "API module", "primary_modules": ["api"],
             "domain_focus": ["api"]},
        ]), 80
    return "ok", 10


@pytest.fixture
def rich_index(tmp_path: Path) -> Path:
    """Create a realistic index directory."""
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(20)],
         "domain_tags": ["backend", "database", "business_logic"],
         "architecture_layer": "core", "summary": "Core business logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(15)],
         "domain_tags": ["api", "rest", "http"],
         "architecture_layer": "api", "summary": "REST API layer"},
        {"name": "workers", "member_files": [f"workers/{i}.py" for i in range(10)],
         "domain_tags": ["async", "background", "tasks"],
         "architecture_layer": "services", "summary": "Background workers"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    atlas = "# Project Atlas\n\nFull-stack Python application with REST API and background workers.\n" + "x" * 200
    (tmp_path / "codebase_atlas.md").write_text(atlas)
    return tmp_path


class TestFullPipeline:
    def test_list_mode_end_to_end(self, rich_index: Path) -> None:
        engine = StaffingEngine(index_dir=rich_index, project_id="integ_test")

        # 1. Check readiness
        report = engine.check_readiness()
        assert report.ready_for_list

        # 2. Generate roles
        roles = engine.generate_roles(
            role_names=["Backend Developer", "API Engineer"],
            llm_fn=_fake_llm,
        )
        assert len(roles) == 2

        # 3. Verify all three files populated
        for role in roles:
            assert len(role.agents_md) > 0
            assert len(role.soul_md) > 0
            assert len(role.knowledge_md) > 0
            assert "prep" in role.knowledge_md

        # 4. Verify roster persistence
        roster = Roster(rich_index)
        assert set(roster.list_roles()) == {"backend_developer", "api_engineer"}

        # 5. Audit drift
        drift = engine.audit_roles()
        assert len(drift.role_fitness) == 2

        # 6. Org chart
        chart = engine.generate_org_chart()
        assert len(chart["roles"]) == 2

    def test_auto_mode_end_to_end(self, rich_index: Path) -> None:
        engine = StaffingEngine(index_dir=rich_index, project_id="integ_test")

        report = engine.check_readiness()
        if report.score >= 0.5:
            roles = engine.auto_generate_roles(llm_fn=_fake_llm)
            assert len(roles) >= 1
        else:
            with pytest.raises(ValueError):
                engine.auto_generate_roles(llm_fn=_fake_llm)

    def test_roster_survives_engine_restart(self, rich_index: Path) -> None:
        e1 = StaffingEngine(index_dir=rich_index, project_id="test")
        e1.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)

        e2 = StaffingEngine(index_dir=rich_index, project_id="test")
        assert e2.roster.get_role("dev") is not None

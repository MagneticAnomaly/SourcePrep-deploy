"""Tests for StaffingEngine."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock

import pytest

from prep.agents.hr.engine import StaffingEngine
from prep.agents.hr.readiness import ReadinessReport
from prep.agents.hr.roster import Roster
from prep.agents.shared.models import RoleSpec


def _fake_llm(prompt: str, system: str | None = None, **kwargs) -> Tuple[str, int]:
    """Fake LLM that returns deterministic content based on the prompt."""
    if "AGENTS.md" in prompt:
        return "# Agent Instructions\n\nYou are the role.", 50
    if "SOUL.md" in prompt:
        return "# Soul\n\nI am the role.", 30
    if "Analyze this codebase" in prompt:
        import json
        return json.dumps([
            {"slug": "backend_dev", "display_name": "Backend Developer",
             "justification": "Core module has 30 files",
             "primary_modules": ["core"], "domain_focus": ["backend"]},
        ]), 80
    return "Unknown prompt", 10


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    """Create a minimal index directory with module data."""
    import json
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
    (tmp_path / "codebase_atlas.md").write_text("# Test Project\nPython backend with REST API")
    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> StaffingEngine:
    return StaffingEngine(index_dir=engine_dir, project_id="test_proj")


class TestReadiness:
    def test_check_readiness_returns_report(self, engine: StaffingEngine) -> None:
        report = engine.check_readiness()
        assert isinstance(report, ReadinessReport)
        assert report.score > 0

    def test_readiness_uses_module_data(self, engine: StaffingEngine) -> None:
        report = engine.check_readiness()
        assert report.dimensions["module_count"] > 0


class TestListMode:
    def test_generate_roles_returns_specs(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Backend Developer", "API Specialist"],
            llm_fn=_fake_llm,
        )
        assert len(roles) == 2
        assert all(isinstance(r, RoleSpec) for r in roles)
        assert roles[0].slug == "backend_developer"
        assert roles[1].slug == "api_specialist"

    def test_generate_roles_populates_agents_md(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Dev"],
            llm_fn=_fake_llm,
        )
        assert "Agent Instructions" in roles[0].agents_md

    def test_generate_roles_populates_soul_md(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Dev"],
            llm_fn=_fake_llm,
        )
        assert "Soul" in roles[0].soul_md

    def test_generate_roles_populates_knowledge_md(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Dev"],
            llm_fn=_fake_llm,
        )
        assert "codrag" in roles[0].knowledge_md
        assert "test_proj" in roles[0].knowledge_md

    def test_generate_roles_saves_to_roster(self, engine: StaffingEngine) -> None:
        engine.generate_roles(
            role_names=["Backend Developer"],
            llm_fn=_fake_llm,
        )
        roster = Roster(engine._index_dir)
        assert roster.get_role("backend_developer") is not None

    def test_generate_with_insufficient_readiness_raises(
        self, tmp_path: Path
    ) -> None:
        engine = StaffingEngine(index_dir=tmp_path, project_id="empty")
        with pytest.raises(ValueError, match="readiness"):
            engine.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)


class TestAutoMode:
    def test_auto_generate_returns_roles(self, engine: StaffingEngine) -> None:
        roles = engine.auto_generate_roles(llm_fn=_fake_llm)
        assert len(roles) >= 1
        assert all(isinstance(r, RoleSpec) for r in roles)

    def test_auto_generate_uses_llm_for_role_inference(
        self, engine: StaffingEngine
    ) -> None:
        calls: list = []
        def tracking_llm(prompt: str, system: str | None = None, **kw) -> Tuple[str, int]:
            calls.append(prompt)
            return _fake_llm(prompt, system=system, **kw)

        engine.auto_generate_roles(llm_fn=tracking_llm)
        assert any("Analyze this codebase" in c for c in calls)

    def test_auto_generate_saves_to_roster(self, engine: StaffingEngine) -> None:
        engine.auto_generate_roles(llm_fn=_fake_llm)
        roster = Roster(engine._index_dir)
        assert len(roster.list_roles()) >= 1

    def test_auto_mode_requires_higher_readiness(self, tmp_path: Path) -> None:
        engine = StaffingEngine(index_dir=tmp_path, project_id="empty")
        with pytest.raises(ValueError, match="readiness"):
            engine.auto_generate_roles(llm_fn=_fake_llm)


class TestOrgChart:
    def test_org_chart_returns_dict(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["CTO", "Backend Dev"], llm_fn=_fake_llm)
        chart = engine.generate_org_chart()
        assert isinstance(chart, dict)
        assert "roles" in chart

    def test_org_chart_includes_all_roles(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["CTO", "Backend Dev"], llm_fn=_fake_llm)
        chart = engine.generate_org_chart()
        slugs = {r["slug"] for r in chart["roles"]}
        assert "cto" in slugs
        assert "backend_dev" in slugs

    def test_org_chart_empty_roster(self, engine: StaffingEngine) -> None:
        chart = engine.generate_org_chart()
        assert chart["roles"] == []

    def test_org_chart_as_markdown(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["CTO", "Backend Dev"], llm_fn=_fake_llm)
        md = engine.generate_org_chart_md()
        assert "CTO" in md or "cto" in md.lower()
        assert "Backend Dev" in md or "backend_dev" in md.lower()


class TestHybridMode:
    def test_hybrid_includes_required_and_inferred(self, engine: StaffingEngine) -> None:
        roles = engine.hybrid_generate_roles(
            required_names=["QA Engineer"],
            llm_fn=_fake_llm,
        )
        slugs = {r.slug for r in roles}
        # Required role must be present
        assert "qa_engineer" in slugs
        # Inferred role (from _fake_llm) should also be present
        assert "backend_developer" in slugs

    def test_hybrid_deduplicates_overlap(self, engine: StaffingEngine) -> None:
        roles = engine.hybrid_generate_roles(
            required_names=["Backend Developer"],  # same as what LLM infers
            llm_fn=_fake_llm,
        )
        slugs = [r.slug for r in roles]
        assert slugs.count("backend_developer") == 1

    def test_hybrid_requires_readiness(self, tmp_path: Path) -> None:
        engine = StaffingEngine(index_dir=tmp_path, project_id="empty")
        with pytest.raises(ValueError, match="readiness"):
            engine.hybrid_generate_roles(required_names=["Dev"], llm_fn=_fake_llm)


class TestAutoModeFailure:
    def test_auto_raises_on_bad_llm_json(self, engine: StaffingEngine) -> None:
        def bad_llm(prompt: str, system: str | None = None, **kw) -> Tuple[str, int]:
            if "AGENTS.md" in prompt:
                return "# Agent", 10
            if "SOUL.md" in prompt:
                return "# Soul", 10
            if "Analyze this codebase" in prompt:
                return "not valid json {{{{", 10
            return "ok", 10

        with pytest.raises(ValueError, match="unparseable"):
            engine.auto_generate_roles(llm_fn=bad_llm)


class TestEdgeCases:
    def test_regenerate_overwrites_existing(self, engine: StaffingEngine) -> None:
        engine.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)
        v1 = engine.roster.get_role("dev")
        assert v1 is not None

        # Re-generate same role
        engine.generate_roles(role_names=["Dev"], llm_fn=_fake_llm)
        v2 = engine.roster.get_role("dev")
        assert v2 is not None
        # Should still exist (overwritten, not duplicated)
        assert len(engine.roster.list_roles()) == 1

    def test_duplicate_slugs_in_list(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["Backend Dev", "Backend Dev"],
            llm_fn=_fake_llm,
        )
        # Should deduplicate
        assert len(roles) == 1

    def test_empty_role_names_list(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(role_names=[], llm_fn=_fake_llm)
        assert roles == []

    def test_special_chars_in_role_name(self, engine: StaffingEngine) -> None:
        roles = engine.generate_roles(
            role_names=["C++ Backend (Senior)"],
            llm_fn=_fake_llm,
        )
        assert len(roles) == 1
        assert roles[0].slug == "c_backend_senior"

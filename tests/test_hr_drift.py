"""Tests for HR drift detection / audit."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from codrag.agents.hr.engine import StaffingEngine, DriftReport, RoleFitness
from codrag.agents.hr.roster import Roster
from codrag.agents.shared.models import RoleSpec


@pytest.fixture
def engine_with_roles(tmp_path: Path) -> StaffingEngine:
    modules = [
        {"name": "core", "member_files": [f"core/{i}.py" for i in range(15)],
         "domain_tags": ["backend", "database"], "architecture_layer": "core",
         "summary": "Core logic"},
        {"name": "api", "member_files": [f"api/{i}.py" for i in range(10)],
         "domain_tags": ["api", "rest"], "architecture_layer": "api",
         "summary": "API layer"},
    ]
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text("# Project\nPython backend")
    engine = StaffingEngine(index_dir=tmp_path, project_id="test")

    # Pre-populate roster
    roster = Roster(tmp_path)
    roster.save_role(RoleSpec(
        slug="backend_dev", display_name="Backend Developer",
        agents_md="# Backend Dev\nManages core module",
        soul_md="# Soul", knowledge_md="# Knowledge",
    ))
    roster.save_role(RoleSpec(
        slug="api_specialist", display_name="API Specialist",
        agents_md="# API Specialist\nManages api module",
        soul_md="# Soul", knowledge_md="# Knowledge",
    ))
    # Force reload
    engine._roster = Roster(tmp_path)
    return engine


class TestDriftDetection:
    def test_audit_returns_drift_report(
        self, engine_with_roles: StaffingEngine
    ) -> None:
        report = engine_with_roles.audit_roles()
        assert isinstance(report, DriftReport)
        assert len(report.role_fitness) == 2

    def test_role_fitness_has_score(
        self, engine_with_roles: StaffingEngine
    ) -> None:
        report = engine_with_roles.audit_roles()
        for rf in report.role_fitness:
            assert 0.0 <= rf.fitness_score <= 1.0
            assert rf.slug in ("backend_dev", "api_specialist")

    def test_role_fitness_has_recommendation(
        self, engine_with_roles: StaffingEngine
    ) -> None:
        report = engine_with_roles.audit_roles()
        for rf in report.role_fitness:
            assert rf.recommendation in (
                "healthy", "minor_drift", "significant_drift", "critical"
            )

    def test_empty_roster_returns_empty_report(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "trace_modules.jsonl").write_text("")
        (tmp_path / "codebase_atlas.md").write_text("# Atlas")
        engine = StaffingEngine(index_dir=tmp_path, project_id="test")
        report = engine.audit_roles()
        assert len(report.role_fitness) == 0

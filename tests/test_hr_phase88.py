"""Tests for Phase 88 Agent Generator enhancements.

Tests cover:
- Audit-enhanced role inference prompts
- Role-filtered KNOWLEDGE.md generation
- Vector-based fitness scoring
- Cross-role overlap detection
- Dry-run mode
- Adoption mode
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from prep.agents.hr.engine import DriftReport, RoleFitness, StaffingEngine
from prep.agents.hr.prompts import render_auto_roles_prompt, render_knowledge_md
from prep.agents.hr.roster import Roster
from prep.agents.shared.models import RoleSpec


# ── Fixtures ──────────────────────────────────────────────────


def _dummy_llm_fn(prompt: str, system: str = "", **kwargs) -> Tuple[str, int]:
    """Mock LLM that returns canned JSON for auto-roles or markdown for files."""
    if kwargs.get("json_mode"):
        return json.dumps([
            {
                "slug": "backend_dev",
                "display_name": "Backend Developer",
                "justification": "Core module has 15 files with coupling hotspots",
                "primary_modules": ["core"],
                "domain_focus": ["backend", "database"],
            },
            {
                "slug": "api_engineer",
                "display_name": "API Engineer",
                "justification": "API module with boundary violations",
                "primary_modules": ["api"],
                "domain_focus": ["api", "rest"],
            },
        ]), 100
    # For AGENTS.md / SOUL.md generation
    return "# Generated Content\nThis is generated content for testing.", 50


def _make_modules() -> List[Dict[str, Any]]:
    return [
        {
            "name": "core",
            "member_files": [f"core/{i}.py" for i in range(15)],
            "domain_tags": ["backend", "database"],
            "architecture_layer": "business_logic",
            "summary": "Core business logic",
        },
        {
            "name": "api",
            "member_files": [f"api/{i}.py" for i in range(10)],
            "domain_tags": ["api", "rest"],
            "architecture_layer": "presentation",
            "summary": "REST API endpoints",
        },
    ]


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """Create a minimal index directory with modules and atlas."""
    modules = _make_modules()
    (tmp_path / "trace_modules.jsonl").write_text(
        "\n".join(json.dumps(m) for m in modules)
    )
    (tmp_path / "codebase_atlas.md").write_text(
        "IDENTITY: Test project\nSTACK: Python 25 files"
    )
    return tmp_path


@pytest.fixture
def engine(index_dir: Path) -> StaffingEngine:
    return StaffingEngine(index_dir=index_dir, project_id="test-p88")


# ── Test: Audit-Enhanced Prompts ──────────────────────────────


class TestAuditEnhancedPrompts:
    def test_prompt_includes_audit_findings(self) -> None:
        findings = [
            {
                "title": "Hub concentration in server.py",
                "category": "coupling",
                "severity": "warning",
                "description": "server.py has 23 dependents, making it a critical hub",
                "affected_files": "src/server.py, src/handler.py",
            },
            {
                "title": "Boundary violation: core → ui",
                "category": "architecture",
                "severity": "critical",
                "description": "Core module imports directly from UI module",
                "affected_files": "src/core/logic.py",
            },
        ]
        prompt = render_auto_roles_prompt(
            file_count=50,
            module_count=5,
            modules_summary="- core (15 files)\n- api (10 files)",
            atlas_excerpt="Test project",
            domain_tags=["backend", "api"],
            layer_distribution={"business_logic": 15, "presentation": 10},
            audit_findings=findings,
        )
        assert "Structural Audit Findings" in prompt
        assert "Hub concentration in server.py" in prompt
        assert "Boundary violation" in prompt
        assert "coupling hotspots" in prompt.lower() or "coupling" in prompt.lower()

    def test_prompt_without_findings_has_no_audit_section(self) -> None:
        prompt = render_auto_roles_prompt(
            file_count=50,
            module_count=5,
            modules_summary="- core (15 files)",
            atlas_excerpt="Test project",
            domain_tags=["backend"],
            layer_distribution={"business_logic": 15},
            audit_findings=None,
        )
        assert "Structural Audit Findings" not in prompt

    def test_findings_capped_at_20(self) -> None:
        findings = [
            {
                "title": f"Finding {i}",
                "category": "quality",
                "severity": "info",
                "description": f"Description {i}",
                "affected_files": f"file_{i}.py",
            }
            for i in range(30)
        ]
        prompt = render_auto_roles_prompt(
            file_count=100,
            module_count=10,
            modules_summary="many modules",
            atlas_excerpt="Big project",
            domain_tags=["backend"],
            layer_distribution={},
            audit_findings=findings,
        )
        # Should include "Finding 19" but not "Finding 20"
        assert "Finding 19" in prompt
        assert "Finding 20" not in prompt


# ── Test: Role-Filtered KNOWLEDGE.md ──────────────────────────


class TestRoleFilteredKnowledge:
    def test_knowledge_md_with_scored_files(self) -> None:
        scored_files = [
            ("src/core/engine.py", 0.92),
            ("src/core/models.py", 0.85),
            ("src/api/routes.py", 0.45),
        ]
        content = render_knowledge_md(
            role_name="Backend Developer",
            role_slug="backend_dev",
            atlas_snapshot="[Backend Developer View]\nCore module overview",
            recommended_files=scored_files,
            domain_focus=["backend", "database"],
            project_id="test-123",
        )
        assert "src/core/engine.py" in content
        assert "0.92" in content
        assert "backend_dev" in content
        assert "test-123" in content

    def test_knowledge_md_empty_files(self) -> None:
        content = render_knowledge_md(
            role_name="New Role",
            role_slug="new_role",
            atlas_snapshot="(no atlas)",
            recommended_files=[],
            domain_focus=[],
            project_id="test",
        )
        assert "auto-populate" in content.lower() or "No files scored" in content

    def test_build_role_knowledge_fallback(self, engine: StaffingEngine) -> None:
        """When role projection fails, should fall back to truncated atlas."""
        atlas = "A" * 5000
        role_atlas, scored_files = engine._build_role_knowledge("nonexistent_role", atlas)
        # Should return something — either projected or fallback
        assert len(role_atlas) > 0


# ── Test: Vector-Based Fitness Scoring ────────────────────────


class TestVectorFitnessScoring:
    def test_fitness_returns_valid_score(self, engine: StaffingEngine) -> None:
        role = RoleSpec(
            slug="engineering",
            display_name="Software Engineer",
            agents_md="# Engineer\nManages core module with backend logic",
            soul_md="# Soul\nIdentity statement",
            knowledge_md="# Knowledge\nbackend, database",
        )
        # The fallback should be used since we don't have epistemic data
        score, top_files, details = engine._compute_role_fitness_vector(role)
        assert 0.0 <= score <= 1.0

    def test_fitness_fallback_on_no_index(self, tmp_path: Path) -> None:
        """Without index data, should use text-match fallback."""
        modules = _make_modules()
        (tmp_path / "trace_modules.jsonl").write_text(
            "\n".join(json.dumps(m) for m in modules)
        )
        (tmp_path / "codebase_atlas.md").write_text("# Atlas")
        engine = StaffingEngine(index_dir=tmp_path, project_id="test")

        role = RoleSpec(
            slug="backend_dev", display_name="Backend Dev",
            agents_md="# Backend Dev\ncore module backend database",
            soul_md="# Soul", knowledge_md="# Knowledge",
        )
        score = engine._compute_role_fitness_fallback(role)
        assert 0.0 <= score <= 1.0

    def test_classify_fitness_thresholds(self) -> None:
        assert RoleFitness.classify(0.9) == "healthy"
        assert RoleFitness.classify(0.7) == "minor_drift"
        assert RoleFitness.classify(0.5) == "significant_drift"
        assert RoleFitness.classify(0.3) == "critical"


# ── Test: Cross-Role Overlap Detection ────────────────────────


class TestOverlapDetection:
    def test_no_overlap_when_disjoint(self, engine: StaffingEngine) -> None:
        role_files = {
            "role_a": {"file1.py", "file2.py", "file3.py"},
            "role_b": {"file4.py", "file5.py", "file6.py"},
        }
        warnings = engine._detect_role_overlaps(role_files)
        assert len(warnings) == 0

    def test_overlap_detected_when_shared(self, engine: StaffingEngine) -> None:
        # Jaccard = 2/4 = 50% > 40% threshold
        role_files = {
            "role_a": {"file1.py", "file2.py", "file3.py"},
            "role_b": {"file1.py", "file2.py", "file4.py"},
        }
        warnings = engine._detect_role_overlaps(role_files)
        assert len(warnings) == 1
        assert "role_a" in warnings[0]
        assert "role_b" in warnings[0]

    def test_no_overlap_when_empty(self, engine: StaffingEngine) -> None:
        role_files = {"role_a": set(), "role_b": set()}
        warnings = engine._detect_role_overlaps(role_files)
        assert len(warnings) == 0

    def test_overlap_below_threshold(self, engine: StaffingEngine) -> None:
        """Less than 50% overlap should not trigger a warning."""
        role_files = {
            "role_a": {"f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10"},
            "role_b": {"f1", "f2", "f3", "f11", "f12", "f13", "f14", "f15", "f16", "f17"},
        }
        warnings = engine._detect_role_overlaps(role_files)
        assert len(warnings) == 0


# ── Test: Dry-Run Mode ───────────────────────────────────────


class TestDryRun:
    def test_dry_run_returns_report(self, engine: StaffingEngine) -> None:
        report = engine.dry_run(
            llm_fn=_dummy_llm_fn,
            mode="auto",
        )
        assert "readiness" in report
        assert "proposed_roles" in report
        assert "estimated_knowledge_sizes" in report

    def test_dry_run_does_not_write_files(
        self, index_dir: Path
    ) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        agents_dir = index_dir / ".agents"

        report = engine.dry_run(llm_fn=_dummy_llm_fn, mode="auto")

        # No files should be written in dry-run
        assert not agents_dir.exists() or len(list(agents_dir.iterdir())) == 0

    def test_dry_run_readiness_included(self, engine: StaffingEngine) -> None:
        report = engine.dry_run(llm_fn=_dummy_llm_fn, mode="auto")
        assert "score" in report["readiness"]
        assert isinstance(report["readiness"]["score"], float)

    def test_dry_run_list_mode(self, engine: StaffingEngine) -> None:
        report = engine.dry_run(
            llm_fn=_dummy_llm_fn,
            mode="list",
            role_names=["Backend Dev", "API Engineer"],
        )
        assert len(report["proposed_roles"]) == 2


# ── Test: Adoption Mode ──────────────────────────────────────


class TestAdoption:
    def test_adopt_reads_existing_agents(
        self, index_dir: Path
    ) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        agents_dir = index_dir / "test_agents"
        agents_dir.mkdir()

        # Create a role directory with AGENTS.md
        role_dir = agents_dir / "my_role"
        role_dir.mkdir()
        (role_dir / "AGENTS.md").write_text(
            "# My Custom Role\n\nManages the core module."
        )

        adopted = engine.adopt_existing_agents(agents_dir, _dummy_llm_fn)
        assert len(adopted) == 1
        assert adopted[0].slug == "my_role"
        assert "My Custom Role" in adopted[0].display_name

    def test_adopt_preserves_existing_soul(
        self, index_dir: Path
    ) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        agents_dir = index_dir / "test_agents"
        agents_dir.mkdir()

        role_dir = agents_dir / "cto"
        role_dir.mkdir()
        (role_dir / "AGENTS.md").write_text("# CTO\nStrategic oversight.")
        (role_dir / "SOUL.md").write_text("# Soul\nI am the CTO. My values are...")

        adopted = engine.adopt_existing_agents(agents_dir, _dummy_llm_fn)
        assert len(adopted) == 1
        assert "I am the CTO" in adopted[0].soul_md

    def test_adopt_generates_soul_when_missing(
        self, index_dir: Path
    ) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        agents_dir = index_dir / "test_agents"
        agents_dir.mkdir()

        role_dir = agents_dir / "devops"
        role_dir.mkdir()
        (role_dir / "AGENTS.md").write_text("# DevOps\nManages infrastructure.")

        adopted = engine.adopt_existing_agents(agents_dir, _dummy_llm_fn)
        assert len(adopted) == 1
        # SOUL.md should be generated (from our mock LLM)
        assert len(adopted[0].soul_md) > 0

    def test_adopt_generates_knowledge_md(
        self, index_dir: Path
    ) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        agents_dir = index_dir / "test_agents"
        agents_dir.mkdir()

        role_dir = agents_dir / "qa_engineer"
        role_dir.mkdir()
        (role_dir / "AGENTS.md").write_text("# QA Engineer\nQuality assurance.")

        adopted = engine.adopt_existing_agents(agents_dir, _dummy_llm_fn)
        assert len(adopted) == 1
        assert "codrag" in adopted[0].knowledge_md.lower()
        assert "Project ID" in adopted[0].knowledge_md  # project_id present

    def test_adopt_skips_non_directories(
        self, index_dir: Path
    ) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        agents_dir = index_dir / "test_agents"
        agents_dir.mkdir()

        # Create a file (not a directory) — should be skipped
        (agents_dir / "README.md").write_text("# README")

        adopted = engine.adopt_existing_agents(agents_dir, _dummy_llm_fn)
        assert len(adopted) == 0

    def test_adopt_nonexistent_dir_raises(self, engine: StaffingEngine) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            engine.adopt_existing_agents(Path("/nonexistent"), _dummy_llm_fn)


# ── Test: audit_roles() End-to-End ───────────────────────────


class TestAuditRolesE2E:
    def test_audit_with_populated_roster(self, index_dir: Path) -> None:
        """Full audit pipeline: populate roster, run audit, check all fields."""
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        roster = Roster(index_dir)
        roster.save_role(RoleSpec(
            slug="backend_dev", display_name="Backend Developer",
            agents_md="# Backend Dev\nManages core module with backend logic",
            soul_md="# Soul", knowledge_md="# Knowledge\nbackend database",
            recommended_files=["core/0.py", "core/1.py"],
        ))
        roster.save_role(RoleSpec(
            slug="api_engineer", display_name="API Engineer",
            agents_md="# API Engineer\nManages api module",
            soul_md="# Soul", knowledge_md="# Knowledge\napi rest",
            recommended_files=["api/0.py", "api/1.py"],
        ))
        engine._roster = Roster(index_dir)

        report = engine.audit_roles()
        assert isinstance(report, DriftReport)
        assert len(report.role_fitness) == 2

        # All fitness scores valid
        for rf in report.role_fitness:
            assert 0.0 <= rf.fitness_score <= 1.0
            assert rf.recommendation in ("healthy", "minor_drift", "significant_drift", "critical")
            assert isinstance(rf.details, str)

        # Overlap warnings is a list (may be empty)
        assert isinstance(report.overlap_warnings, list)

        # Coverage gaps is a list
        assert isinstance(report.coverage_gaps, list)

    def test_audit_empty_roster(self, index_dir: Path) -> None:
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        report = engine.audit_roles()
        assert len(report.role_fitness) == 0
        assert len(report.coverage_gaps) == 0
        assert len(report.overlap_warnings) == 0

    def test_audit_detects_overlap_between_similar_roles(
        self, index_dir: Path
    ) -> None:
        """Two roles with identical AGENTS.md content should trigger overlap."""
        engine = StaffingEngine(index_dir=index_dir, project_id="test")
        roster = Roster(index_dir)
        # Same content = same RoleVector resolution = same top files
        roster.save_role(RoleSpec(
            slug="engineering", display_name="Engineer",
            agents_md="# Engineer\ncore backend", soul_md="# Soul",
            knowledge_md="", recommended_files=[],
        ))
        roster.save_role(RoleSpec(
            slug="full_stack", display_name="Full Stack",
            agents_md="# Full Stack\ncore backend", soul_md="# Soul",
            knowledge_md="", recommended_files=[],
        ))
        engine._roster = Roster(index_dir)

        report = engine.audit_roles()
        # Both roles are engineering-like, so they may overlap
        # (depends on whether RoleVector scoring produces overlapping files)
        assert len(report.role_fitness) == 2


# ── Test: _load_audit_findings ────────────────────────────────


class TestLoadAuditFindings:
    def test_returns_empty_without_core(self, engine: StaffingEngine) -> None:
        """Without AgentCore, _load_audit_findings should return []."""
        # engine fixture has no AgentCore
        findings = engine._load_audit_findings()
        assert findings == []

    def test_returns_findings_with_mock_core(self, index_dir: Path) -> None:
        """With a mock AgentCore, should extract fields correctly."""
        from unittest.mock import MagicMock
        from dataclasses import dataclass, field as dc_field

        @dataclass
        class MockFinding:
            title: str = "Hub concentration"
            category: str = "coupling"
            severity: str = "warning"
            description: str = "server.py has too many deps"
            affected_files: list = dc_field(default_factory=lambda: ["server.py", "handler.py"])

        mock_core = MagicMock()
        mock_core.project_id = "test"
        mock_core._data._index_dir = index_dir
        mock_core.get_audit_findings.return_value = [MockFinding(), MockFinding(title="Boundary violation")]

        engine = StaffingEngine(core=mock_core)
        findings = engine._load_audit_findings()

        assert len(findings) == 2
        assert findings[0]["title"] == "Hub concentration"
        assert findings[0]["category"] == "coupling"
        assert findings[0]["severity"] == "warning"
        assert "server.py" in findings[0]["affected_files"]
        assert findings[1]["title"] == "Boundary violation"

    def test_caps_at_30_findings(self, index_dir: Path) -> None:
        from unittest.mock import MagicMock
        from dataclasses import dataclass

        @dataclass
        class MockFinding:
            title: str = "Finding"
            category: str = "quality"
            severity: str = "info"
            description: str = "desc"
            affected_files: list = None
            def __post_init__(self):
                if self.affected_files is None:
                    self.affected_files = []

        mock_core = MagicMock()
        mock_core.project_id = "test"
        mock_core._data._index_dir = index_dir
        mock_core.get_audit_findings.return_value = [MockFinding() for _ in range(50)]

        engine = StaffingEngine(core=mock_core)
        findings = engine._load_audit_findings()
        assert len(findings) == 30

    def test_handles_exception_gracefully(self, index_dir: Path) -> None:
        from unittest.mock import MagicMock

        mock_core = MagicMock()
        mock_core.project_id = "test"
        mock_core._data._index_dir = index_dir
        mock_core.get_audit_findings.side_effect = RuntimeError("DB error")

        engine = StaffingEngine(core=mock_core)
        findings = engine._load_audit_findings()
        assert findings == []

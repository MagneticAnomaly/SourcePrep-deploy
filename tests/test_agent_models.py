"""Tests for src/prep/agents/shared/models.py"""
from __future__ import annotations

import pytest
from prep.agents.shared.models import (
    AgentConfig,
    CleanupCandidate,
    CleanupPlan,
    ResearchPlan,
    ResearchTopic,
    RoleSpec,
    _normalize_slug,
)


class TestNormalizeSlug:
    def test_lowercase(self):
        assert _normalize_slug("Hello") == "hello"

    def test_spaces_become_underscores(self):
        assert _normalize_slug("VP of Engineering") == "vp_of_engineering"

    def test_special_chars(self):
        assert _normalize_slug("C++ / Rust") == "c_rust"

    def test_leading_trailing_stripped(self):
        assert _normalize_slug("__foo__") == "foo"

    def test_collapse_runs(self):
        assert _normalize_slug("a   b") == "a_b"

    def test_already_clean(self):
        assert _normalize_slug("clean_slug") == "clean_slug"


class TestRoleSpec:
    def test_create_minimal(self):
        role = RoleSpec(slug="backend-engineer", display_name="Backend Engineer")
        assert role.slug == "backend_engineer"
        assert role.display_name == "Backend Engineer"
        assert role.agents_md == ""
        assert role.soul_md == ""
        assert role.knowledge_md == ""
        assert role.recommended_files == []
        assert role.paperclip_agent_id == ""

    def test_slug_normalized_on_init(self):
        role = RoleSpec(slug="VP of Engineering", display_name="VP")
        assert role.slug == "vp_of_engineering"

    def test_slug_normalization_special_chars(self):
        role = RoleSpec(slug="DevOps/SRE Lead!", display_name="DevOps")
        assert role.slug == "devops_sre_lead"

    def test_roundtrip_dict(self):
        role = RoleSpec(
            slug="frontend_dev",
            display_name="Frontend Developer",
            agents_md="# Agents",
            soul_md="# Soul",
            knowledge_md="# Knowledge",
            recommended_files=["src/app.ts"],
            paperclip_agent_id="agent-123",
        )
        d = role.to_dict()
        restored = RoleSpec.from_dict(d)
        assert restored.slug == role.slug
        assert restored.display_name == role.display_name
        assert restored.agents_md == role.agents_md
        assert restored.soul_md == role.soul_md
        assert restored.knowledge_md == role.knowledge_md
        assert restored.recommended_files == role.recommended_files
        assert restored.paperclip_agent_id == role.paperclip_agent_id

    def test_from_dict_minimal(self):
        role = RoleSpec.from_dict({"slug": "tester", "display_name": "Tester"})
        assert role.slug == "tester"
        assert role.agents_md == ""
        assert role.recommended_files == []


class TestResearchTopic:
    def test_create(self):
        topic = ResearchTopic(
            finding_id="f-001",
            title="High coupling in auth module",
            description="The auth module has too many dependencies.",
        )
        assert topic.finding_id == "f-001"
        assert topic.priority == "P2"
        assert topic.affected_files == []
        assert topic.impact_summary == ""

    def test_roundtrip_dict(self):
        topic = ResearchTopic(
            finding_id="f-002",
            title="Dead code in utils",
            description="Several utility functions are unused.",
            affected_files=["src/utils.py", "src/helpers.py"],
            priority="P1",
            impact_summary="Reduces bundle size by 10%.",
        )
        d = topic.to_dict()
        restored = ResearchTopic.from_dict(d)
        assert restored.finding_id == topic.finding_id
        assert restored.title == topic.title
        assert restored.description == topic.description
        assert restored.affected_files == topic.affected_files
        assert restored.priority == topic.priority
        assert restored.impact_summary == topic.impact_summary

    def test_from_dict_defaults(self):
        topic = ResearchTopic.from_dict(
            {"finding_id": "f-x", "title": "T", "description": "D"}
        )
        assert topic.priority == "P2"
        assert topic.affected_files == []


class TestResearchPlan:
    def test_create(self):
        plan = ResearchPlan(
            topic_id="f-001",
            title="Refactor auth",
            root_cause="Circular imports",
            fix_steps=["Extract interfaces", "Invert dependencies"],
        )
        assert plan.effort == "medium"
        assert plan.risk == "low"
        assert plan.testing_strategy == ""

    def test_roundtrip_dict(self):
        plan = ResearchPlan(
            topic_id="f-003",
            title="Fix pipeline",
            root_cause="Missing error handling",
            fix_steps=["Add try/except", "Add tests"],
            effort="high",
            risk="medium",
            testing_strategy="Unit + integration tests",
        )
        d = plan.to_dict()
        restored = ResearchPlan.from_dict(d)
        assert restored.topic_id == plan.topic_id
        assert restored.title == plan.title
        assert restored.root_cause == plan.root_cause
        assert restored.fix_steps == plan.fix_steps
        assert restored.effort == plan.effort
        assert restored.risk == plan.risk
        assert restored.testing_strategy == plan.testing_strategy

    def test_fix_steps_preserved(self):
        plan = ResearchPlan.from_dict(
            {
                "topic_id": "t1",
                "title": "T",
                "root_cause": "R",
                "fix_steps": ["step a", "step b", "step c"],
            }
        )
        assert plan.fix_steps == ["step a", "step b", "step c"]


class TestCleanupCandidate:
    def test_create(self):
        c = CleanupCandidate(
            file_path="src/old_module.py",
            finding_id="f-100",
            dependent_count=0,
        )
        assert c.classification == "needs_review"
        assert c.reason == ""

    def test_valid_classifications(self):
        for cls_value in ("safe_to_delete", "needs_review", "keep"):
            c = CleanupCandidate(
                file_path="x.py",
                finding_id="f",
                dependent_count=1,
                classification=cls_value,
            )
            assert c.classification == cls_value

    def test_roundtrip_dict(self):
        c = CleanupCandidate(
            file_path="src/dead.py",
            finding_id="f-200",
            dependent_count=2,
            classification="safe_to_delete",
            reason="No imports found",
        )
        d = c.to_dict()
        restored = CleanupCandidate.from_dict(d)
        assert restored.file_path == c.file_path
        assert restored.finding_id == c.finding_id
        assert restored.dependent_count == c.dependent_count
        assert restored.classification == c.classification
        assert restored.reason == c.reason


class TestCleanupPlan:
    def _make_candidates(self):
        return [
            CleanupCandidate("a.py", "f1", 0, "safe_to_delete", "unused"),
            CleanupCandidate("b.py", "f2", 3, "needs_review", "few deps"),
            CleanupCandidate("c.py", "f3", 0, "safe_to_delete", "orphaned"),
            CleanupCandidate("d.py", "f4", 10, "keep", "core module"),
        ]

    def test_create_defaults(self):
        plan = CleanupPlan()
        assert plan.branch_name == ""
        assert plan.candidates == []
        assert plan.archive_branch == "custodian/archive"
        assert plan.dry_run is True

    def test_safe_candidates_filter(self):
        plan = CleanupPlan(branch_name="custodian/cleanup-1", candidates=self._make_candidates())
        safe = plan.safe_candidates()
        assert len(safe) == 2
        assert all(c.classification == "safe_to_delete" for c in safe)
        assert {c.file_path for c in safe} == {"a.py", "c.py"}

    def test_safe_candidates_empty_when_none(self):
        plan = CleanupPlan(
            candidates=[CleanupCandidate("x.py", "f", 5, "keep", "")]
        )
        assert plan.safe_candidates() == []

    def test_roundtrip_dict(self):
        plan = CleanupPlan(
            branch_name="custodian/run-42",
            candidates=self._make_candidates(),
            archive_branch="custodian/archive",
            dry_run=False,
        )
        d = plan.to_dict()
        restored = CleanupPlan.from_dict(d)
        assert restored.branch_name == plan.branch_name
        assert restored.archive_branch == plan.archive_branch
        assert restored.dry_run == plan.dry_run
        assert len(restored.candidates) == len(plan.candidates)
        assert restored.candidates[0].file_path == plan.candidates[0].file_path
        assert restored.safe_candidates() == [
            c for c in restored.candidates if c.classification == "safe_to_delete"
        ]


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.enabled is False
        assert cfg.adapter == "native"
        assert cfg.dry_run is True
        assert cfg.cooldown_seconds == 3600
        assert cfg.max_topics_per_run == 3
        assert cfg.min_finding_priority == "P2"
        assert cfg.auto_push is False
        assert cfg.max_files_per_run == 20
        assert cfg.exclude_paths == []
        assert cfg.trigger == "manual"

    def test_from_dict_partial(self):
        cfg = AgentConfig.from_dict({"enabled": True, "adapter": "paperclip"})
        assert cfg.enabled is True
        assert cfg.adapter == "paperclip"
        # Unspecified keys get defaults
        assert cfg.dry_run is True
        assert cfg.cooldown_seconds == 3600
        assert cfg.max_files_per_run == 20
        assert cfg.exclude_paths == []

    def test_from_dict_empty(self):
        cfg = AgentConfig.from_dict({})
        assert cfg == AgentConfig()

    def test_roundtrip_dict(self):
        cfg = AgentConfig(
            enabled=True,
            adapter="paperclip",
            dry_run=False,
            cooldown_seconds=7200,
            max_topics_per_run=5,
            min_finding_priority="P1",
            auto_push=True,
            max_files_per_run=50,
            exclude_paths=["node_modules", ".venv"],
            trigger="schedule",
        )
        d = cfg.to_dict()
        restored = AgentConfig.from_dict(d)
        assert restored.enabled == cfg.enabled
        assert restored.adapter == cfg.adapter
        assert restored.dry_run == cfg.dry_run
        assert restored.cooldown_seconds == cfg.cooldown_seconds
        assert restored.max_topics_per_run == cfg.max_topics_per_run
        assert restored.min_finding_priority == cfg.min_finding_priority
        assert restored.auto_push == cfg.auto_push
        assert restored.max_files_per_run == cfg.max_files_per_run
        assert restored.exclude_paths == cfg.exclude_paths
        assert restored.trigger == cfg.trigger

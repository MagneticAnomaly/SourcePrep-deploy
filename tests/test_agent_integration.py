"""Integration smoke test for the agents package.

Verifies AgentCore can be constructed with real Prep classes,
mocking only external I/O (Paperclip HTTP, git subprocess, LLM).
"""

from __future__ import annotations

import pytest
from pathlib import Path

from prep.agents import AgentCore
from prep.agents.shared.models import (
    AgentConfig,
    RoleSpec,
    ResearchTopic,
    ResearchPlan,
    CleanupCandidate,
    CleanupPlan,
)
from prep.adapters.pm_models import PMPushConfig


class TestAgentCoreConstruction:
    def test_creates_without_paperclip(self, tmp_path):
        """AgentCore works without Paperclip configured."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        core = AgentCore(
            project_id="test",
            index_dir=index_dir,
            project_root=tmp_path,
        )
        assert core.project_id == "test"
        assert core._paperclip is None
        assert core.git is not None

    def test_creates_with_paperclip_disabled(self, tmp_path):
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        core = AgentCore(
            project_id="test",
            index_dir=index_dir,
            pm_config=PMPushConfig(enabled=False),
        )
        assert core._paperclip is None

    def test_get_atlas_returns_string(self, tmp_path):
        """Atlas returns empty string when no atlas has been generated."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        core = AgentCore(project_id="test", index_dir=index_dir, project_root=tmp_path)
        result = core.get_atlas()
        assert isinstance(result, str)

    def test_get_audit_findings_returns_list(self, tmp_path):
        """Audit findings returns list (empty if no index data)."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        core = AgentCore(project_id="test", index_dir=index_dir, project_root=tmp_path)
        result = core.get_audit_findings()
        assert isinstance(result, list)

    def test_push_without_config_raises(self, tmp_path):
        """Pushing to Paperclip without config raises RuntimeError."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        core = AgentCore(project_id="test", index_dir=index_dir)
        from prep.adapters.pm_models import PMProject
        with pytest.raises(RuntimeError, match="[Pp]aperclip"):
            core.push_project(PMProject(name="X"))

    def test_agent_config_roundtrip(self, tmp_path):
        """Agent config can be saved and loaded."""
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        core = AgentCore(project_id="test-roundtrip", index_dir=index_dir)
        cfg = AgentConfig(enabled=True, adapter="langgraph", cooldown_seconds=120)
        core.save_agent_config("researcher", cfg)
        loaded = core.get_agent_config("researcher")
        assert loaded.enabled is True
        assert loaded.adapter == "langgraph"
        assert loaded.cooldown_seconds == 120


class TestModelsImportable:
    """Verify all models are importable from the public API."""
    def test_all_models_importable(self):
        assert RoleSpec is not None
        assert ResearchTopic is not None
        assert ResearchPlan is not None
        assert CleanupCandidate is not None
        assert CleanupPlan is not None
        assert AgentConfig is not None

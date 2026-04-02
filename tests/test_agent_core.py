"""Tests for AgentCore facade."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codrag.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from codrag.agents.core import AgentCore
from codrag.agents.shared.models import AgentConfig
from codrag.core.audit.action_item import ActionItem


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_data_access():
    m = MagicMock()
    m.get_audit_findings.return_value = []
    m.refresh_audit.return_value = []
    m.get_atlas.return_value = "# Atlas"
    m.get_impact_radius.return_value = {"target": None, "dependents": []}
    m.save_observation.return_value = "obs-uuid-1"
    m.get_observations.return_value = []
    return m


@pytest.fixture
def mock_paperclip():
    m = MagicMock()
    m.push_project.return_value = "proj-123"
    m.push_goal.return_value = "goal-456"
    m.push_issue.return_value = "issue-789"
    m.bulk_push.return_value = PushResult(pushed=True, issues_created=2)
    return m


@pytest.fixture
def mock_git():
    return MagicMock()


@pytest.fixture
def core(mock_data_access, mock_paperclip, mock_git):
    with patch("codrag.agents.core.CoDRAGDataAccess", return_value=mock_data_access), \
         patch("codrag.agents.core.PaperclipClient", return_value=mock_paperclip), \
         patch("codrag.agents.core.GitClient", return_value=mock_git):
        c = AgentCore(
            project_id="test-proj",
            index_dir=Path("/tmp/index"),
            project_root=Path("/tmp/project"),
            pm_config=PMPushConfig(
                enabled=True,
                paperclip_url="http://localhost:3100",
                paperclip_company_id="comp-1",
            ),
        )
    c._data = mock_data_access
    c._paperclip = mock_paperclip
    c._git = mock_git
    return c


# ── TestCoDRAGReadAccess ───────────────────────────────────────────────────────


class TestCoDRAGReadAccess:
    def test_get_audit_findings_delegates(self, core, mock_data_access):
        findings = [MagicMock(spec=ActionItem)]
        mock_data_access.get_audit_findings.return_value = findings

        result = core.get_audit_findings(min_priority="P1", categories=["quality"])

        mock_data_access.get_audit_findings.assert_called_once_with(
            min_priority="P1", categories=["quality"]
        )
        assert result is findings

    def test_get_audit_findings_defaults(self, core, mock_data_access):
        core.get_audit_findings()
        mock_data_access.get_audit_findings.assert_called_once_with(
            min_priority=None, categories=None
        )

    def test_refresh_audit_delegates(self, core, mock_data_access):
        refreshed = [MagicMock(spec=ActionItem)]
        mock_data_access.refresh_audit.return_value = refreshed

        result = core.refresh_audit(categories=["debt"])

        mock_data_access.refresh_audit.assert_called_once_with(categories=["debt"])
        assert result is refreshed

    def test_get_atlas_delegates(self, core, mock_data_access):
        mock_data_access.get_atlas.return_value = "# My Atlas"
        result = core.get_atlas()
        mock_data_access.get_atlas.assert_called_once()
        assert result == "# My Atlas"

    def test_get_impact_radius_delegates(self, core, mock_data_access):
        mock_data_access.get_impact_radius.return_value = {"target": "foo.py", "dependents": ["bar.py"]}

        result = core.get_impact_radius("foo.py")

        mock_data_access.get_impact_radius.assert_called_once_with("foo.py")
        assert result["target"] == "foo.py"

    def test_save_observation_delegates(self, core, mock_data_access):
        mock_data_access.save_observation.return_value = "obs-abc"

        result = core.save_observation("some note", file_path="src/foo.py", category="decision")

        mock_data_access.save_observation.assert_called_once_with(
            "some note", file_path="src/foo.py", category="decision"
        )
        assert result == "obs-abc"

    def test_get_observations_delegates(self, core, mock_data_access):
        obs = [MagicMock(), MagicMock()]
        mock_data_access.get_observations.return_value = obs

        result = core.get_observations("tech debt", limit=3)

        mock_data_access.get_observations.assert_called_once_with("tech debt", limit=3)
        assert result is obs


# ── TestPaperclipWriteAccess ───────────────────────────────────────────────────


class TestPaperclipWriteAccess:
    def test_push_project_delegates(self, core, mock_paperclip):
        project = PMProject(name="Test Project")
        result = core.push_project(project, goal_ids=["g-1"])
        mock_paperclip.push_project.assert_called_once_with(project, goal_ids=["g-1"])
        assert result == "proj-123"

    def test_push_goal_delegates(self, core, mock_paperclip):
        goal = PMGoal(title="Reduce tech debt")
        result = core.push_goal(goal)
        mock_paperclip.push_goal.assert_called_once_with(goal)
        assert result == "goal-456"

    def test_push_issue_delegates(self, core, mock_paperclip):
        issue = PMIssue(title="Fix complexity", description="Too complex")
        result = core.push_issue(issue)
        mock_paperclip.push_issue.assert_called_once_with(issue)
        assert result == "issue-789"

    def test_bulk_push_delegates(self, core, mock_paperclip):
        items = [MagicMock(spec=ActionItem)]
        result = core.bulk_push(items, strategy="category", min_priority="P1", dry_run=True)
        mock_paperclip.bulk_push.assert_called_once_with(
            items,
            strategy="category",
            min_priority="P1",
            dry_run=True,
        )
        assert result.pushed is True

    def test_push_project_raises_when_paperclip_not_configured(self):
        """AgentCore without pm_config raises RuntimeError on Paperclip calls."""
        with patch("codrag.agents.core.CoDRAGDataAccess"), \
             patch("codrag.agents.core.GitClient"):
            c = AgentCore(
                project_id="no-pm",
                index_dir=Path("/tmp/index"),
                project_root=Path("/tmp/project"),
            )

        with pytest.raises(RuntimeError, match="Paperclip is not configured"):
            c.push_project(PMProject(name="X"))

    def test_push_goal_raises_when_paperclip_not_configured(self):
        with patch("codrag.agents.core.CoDRAGDataAccess"), \
             patch("codrag.agents.core.GitClient"):
            c = AgentCore(
                project_id="no-pm",
                index_dir=Path("/tmp/index"),
                project_root=Path("/tmp/project"),
            )

        with pytest.raises(RuntimeError, match="Paperclip is not configured"):
            c.push_goal(PMGoal(title="X"))

    def test_push_raises_when_pm_config_disabled(self):
        """pm_config.enabled=False → Paperclip not created → raises."""
        with patch("codrag.agents.core.CoDRAGDataAccess"), \
             patch("codrag.agents.core.GitClient"):
            c = AgentCore(
                project_id="disabled-pm",
                index_dir=Path("/tmp/index"),
                project_root=Path("/tmp/project"),
                pm_config=PMPushConfig(enabled=False, paperclip_url="http://localhost:3100"),
            )

        with pytest.raises(RuntimeError, match="Paperclip is not configured"):
            c.push_issue(PMIssue(title="X", description="Y"))


# ── TestAgentConfig ────────────────────────────────────────────────────────────


class TestAgentConfig:
    def test_get_config_returns_defaults_when_not_set(self, core):
        """When no config is stored, returns an AgentConfig with defaults."""
        with patch("codrag.agents.core.settings") as mock_settings:
            mock_settings.project_get.return_value = None
            cfg = core.get_agent_config("researcher")

        mock_settings.project_get.assert_called_once_with("test-proj", "agents_config.researcher")
        assert isinstance(cfg, AgentConfig)
        assert cfg.enabled is False
        assert cfg.dry_run is True

    def test_get_config_from_settings(self, core):
        """Stored dict is converted to AgentConfig."""
        stored = {"enabled": True, "dry_run": False, "max_topics_per_run": 5}

        with patch("codrag.agents.core.settings") as mock_settings:
            mock_settings.project_get.return_value = stored
            cfg = core.get_agent_config("staffing")

        assert cfg.enabled is True
        assert cfg.dry_run is False
        assert cfg.max_topics_per_run == 5

    def test_save_config_roundtrip(self, core):
        """save_agent_config calls project_set with the serialized dict."""
        config = AgentConfig(enabled=True, dry_run=False, max_topics_per_run=7)

        with patch("codrag.agents.core.settings") as mock_settings:
            core.save_agent_config("custodian", config)

        mock_settings.project_set.assert_called_once_with(
            "test-proj",
            "agents_config.custodian",
            config.to_dict(),
        )

    def test_save_and_get_roundtrip(self, core):
        """Full save→get cycle preserves config values."""
        saved_dict: dict = {}

        def fake_set(project_id, key, value):
            saved_dict["value"] = value

        def fake_get(project_id, key, default=None):
            return saved_dict.get("value")

        with patch("codrag.agents.core.settings") as mock_settings:
            mock_settings.project_set.side_effect = fake_set
            mock_settings.project_get.side_effect = fake_get

            original = AgentConfig(enabled=True, adapter="paperclip", max_files_per_run=10)
            core.save_agent_config("custodian", original)
            restored = core.get_agent_config("custodian")

        assert restored.enabled is True
        assert restored.adapter == "paperclip"
        assert restored.max_files_per_run == 10


# ── TestGitAccess ──────────────────────────────────────────────────────────────


class TestGitAccess:
    def test_git_property_returns_mock_git(self, core, mock_git):
        assert core.git is mock_git

    def test_git_is_none_without_project_root(self):
        """When no project_root is given, git property returns None."""
        with patch("codrag.agents.core.CoDRAGDataAccess"):
            c = AgentCore(
                project_id="no-git",
                index_dir=Path("/tmp/index"),
            )
        assert c.git is None

    def test_project_id_stored(self, core):
        assert core.project_id == "test-proj"


# ── TestNewCoDRAGMethods ─────────────────────────────────────────────────────


class TestNewCoDRAGMethods:
    def test_get_module_structure_delegates(self, core, mock_data_access):
        mock_data_access.get_module_structure.return_value = [{"name": "Core"}]
        result = core.get_module_structure()
        assert result == [{"name": "Core"}]

    def test_search_code_delegates(self, core, mock_data_access):
        mock_data_access.search_code.return_value = [{"doc": {}, "score": 0.9}]
        result = core.search_code("auth", k=3)
        assert len(result) == 1
        mock_data_access.search_code.assert_called_once_with("auth", k=3, role=None)

    def test_get_role_vector_delegates(self, core, mock_data_access):
        mock_data_access.get_role_vector.return_value = "mock_vector"
        result = core.get_role_vector("ceo")
        assert result == "mock_vector"

    def test_get_atlas_with_role(self, core, mock_data_access):
        mock_data_access.get_atlas.return_value = "# CEO Atlas"
        result = core.get_atlas(role="ceo")
        mock_data_access.get_atlas.assert_called_once_with(role="ceo")


# ── TestLLMAccess ────────────────────────────────────────────────────────────


class TestLLMAccess:
    def test_get_llm_client_returns_none_when_no_config(self, core):
        with patch("codrag.agents.core.settings") as mock_settings:
            mock_settings.get.return_value = None
            result = core.get_llm_client()
            assert result is None

    def test_get_llm_client_returns_client_when_configured(self, core):
        with patch("codrag.agents.core.settings") as mock_settings, \
             patch("codrag.core.llm_client.LLMClient") as MockLLM:
            mock_settings.get.return_value = {
                "model_thinking": "deepseek-r1:32b",
                "llm_provider": "ollama",
                "ollama_url": "http://localhost:11434",
            }
            result = core.get_llm_client("researcher")
            assert result is not None


# ── TestConcurrencyGate ──────────────────────────────────────────────────────


class TestConcurrencyGate:
    def test_acquire_gate_delegates(self, core):
        with patch("codrag.services.agent_gate.get_agent_gate") as mock_gate_fn:
            mock_gate = MagicMock()
            mock_gate.can_run.return_value = True
            mock_gate_fn.return_value = mock_gate
            assert core.acquire_gate("researcher") is True
            mock_gate.can_run.assert_called_once_with("test-proj", "researcher")

    def test_release_gate_delegates(self, core):
        with patch("codrag.services.agent_gate.get_agent_gate") as mock_gate_fn:
            mock_gate = MagicMock()
            mock_gate_fn.return_value = mock_gate
            core.release_gate()
            mock_gate.release.assert_called_once()


# ── TestAgentCRUD ────────────────────────────────────────────────────────────


class TestAgentCRUD:
    def test_create_agent_delegates_to_paperclip(self, core, mock_paperclip):
        """create_agent calls through to PaperclipClient."""
        mock_paperclip.create_agent.return_value = "agent-123"
        role = MagicMock()
        role.display_name = "Backend Dev"
        role.slug = "backend_dev"
        role.soul_md = "Identity text"
        role.agents_md = "Instructions"
        role.knowledge_md = "Knowledge"
        role.recommended_files = []
        result = core.create_agent(role)
        assert result == "agent-123"
        mock_paperclip.create_agent.assert_called_once()

    def test_update_agent_delegates_to_paperclip(self, core, mock_paperclip):
        """update_agent calls through to PaperclipClient."""
        role = MagicMock()
        role.soul_md = "Soul"
        role.agents_md = "Updated instructions"
        role.knowledge_md = "Knowledge"
        core.update_agent("agent-123", role)
        mock_paperclip.update_agent.assert_called_once()

"""Tests for PaperclipClient agent wrapper."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from prep.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from prep.agents.shared.paperclip_client import PaperclipClient
from prep.core.audit.action_item import ActionItem


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.ensure_project.return_value = "proj-123"
    adapter.ensure_goal.return_value = "goal-456"
    adapter.create_issue.return_value = "issue-789"
    adapter.health_check.return_value = True
    return adapter


@pytest.fixture
def mock_push_engine():
    engine = MagicMock()
    engine.push.return_value = PushResult(pushed=True, issues_created=3)
    return engine


@pytest.fixture
def client(mock_adapter, mock_push_engine):
    with patch(
        "prep.agents.shared.paperclip_client.PaperclipAdapter",
        return_value=mock_adapter,
    ), patch(
        "prep.agents.shared.paperclip_client.create_push_engine",
        return_value=mock_push_engine,
    ):
        c = PaperclipClient(
            config=PMPushConfig(
                enabled=True,
                paperclip_url="http://localhost:3100",
                paperclip_company_id="comp-1",
            )
        )
    # Re-attach mocks so test assertions work after construction
    c._adapter = mock_adapter
    c._push_engine = mock_push_engine
    return c


# ── TestPushProject ───────────────────────────────────────────────────


class TestPushProject:
    def test_creates_project(self, client, mock_adapter):
        project = PMProject(name="My Project", description="Test project")
        result = client.push_project(project)

        mock_adapter.ensure_project.assert_called_once_with(project, goal_ids=None)
        assert result == "proj-123"

    def test_creates_project_with_goal_ids(self, client, mock_adapter):
        project = PMProject(name="My Project")
        goal_ids = ["goal-1", "goal-2"]
        result = client.push_project(project, goal_ids=goal_ids)

        mock_adapter.ensure_project.assert_called_once_with(project, goal_ids=goal_ids)
        assert result == "proj-123"


# ── TestPushGoal ──────────────────────────────────────────────────────


class TestPushGoal:
    def test_creates_goal(self, client, mock_adapter):
        goal = PMGoal(title="Reduce Tech Debt", description="Lower debt score to < 20")
        result = client.push_goal(goal)

        mock_adapter.ensure_goal.assert_called_once_with(goal)
        assert result == "goal-456"


# ── TestPushIssue ─────────────────────────────────────────────────────


class TestPushIssue:
    def test_creates_issue(self, client, mock_adapter):
        issue = PMIssue(
            title="Fix duplicate logic in utils",
            description="Several functions are duplicated.",
            priority="P1",
            category="quality",
        )
        result = client.push_issue(issue)

        mock_adapter.create_issue.assert_called_once_with(issue)
        assert result == "issue-789"


# ── TestBulkPush ──────────────────────────────────────────────────────


class TestBulkPush:
    def test_pushes_action_items(self, client, mock_push_engine):
        items = [
            ActionItem(title="Issue A", priority="P1", category="quality"),
            ActionItem(title="Issue B", priority="P2", category="tech_debt"),
        ]
        result = client.bulk_push(items, prep_project_id="cdr-proj-1")

        mock_push_engine.push.assert_called_once_with(
            items,
            prep_project_id="cdr-proj-1",
            strategy="category",
            min_priority="P2",
            dry_run=False,
        )
        assert result.pushed is True
        assert result.issues_created == 3

    def test_bulk_push_dry_run(self, client, mock_push_engine):
        mock_push_engine.push.return_value = PushResult(pushed=False, dry_run=True, issues_created=5)
        items = [ActionItem(title="Dry run item", priority="P0")]
        result = client.bulk_push(items, dry_run=True)

        call_kwargs = mock_push_engine.push.call_args
        assert call_kwargs.kwargs.get("dry_run") is True or call_kwargs[1].get("dry_run") is True
        assert result.dry_run is True

    def test_bulk_push_custom_strategy(self, client, mock_push_engine):
        items = [ActionItem(title="Root file issue", priority="P1")]
        client.bulk_push(items, strategy="root_file", min_priority="P1")

        mock_push_engine.push.assert_called_once_with(
            items,
            prep_project_id="",
            strategy="root_file",
            min_priority="P1",
            dry_run=False,
        )


# ── TestHealthCheck ───────────────────────────────────────────────────


class TestHealthCheck:
    def test_healthy(self, client, mock_adapter):
        mock_adapter.health_check.return_value = True
        assert client.is_healthy() is True
        mock_adapter.health_check.assert_called_once()

    def test_unhealthy(self, client, mock_adapter):
        mock_adapter.health_check.return_value = False
        assert client.is_healthy() is False

"""
Abstract PM Adapter — Universal interface for all PM tools (Phase 65).

Every PM tool (Paperclip, GitHub Issues, Jira, Linear) implements
this interface. The PushEngine orchestrates through these methods
without knowing which PM tool is behind them.

To add a new PM provider:
1. Subclass PMAdapter
2. Implement all abstract methods
3. Register in the adapter factory (push_engine.py)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from codrag.adapters.pm_models import PMGoal, PMIssue, PMProject


class PMAdapter(ABC):
    """Universal project management adapter interface.

    Paperclip-first, but designed so GitHub Issues, Jira, Linear
    can implement the same interface with a new subclass.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g., 'Paperclip')."""

    # ── Projects ─────────────────────────────────────────────────

    @abstractmethod
    def ensure_project(
        self,
        project: PMProject,
        *,
        goal_ids: Optional[List[str]] = None,
    ) -> str:
        """Create a project if it doesn't exist, or return existing ID.

        Args:
            project: Project to create or find.
            goal_ids: Optional goal IDs to associate with the project.

        Returns:
            The project ID in the target PM system.
        """

    @abstractmethod
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects in the current workspace/company."""

    # ── Goals ────────────────────────────────────────────────────

    @abstractmethod
    def ensure_goal(self, goal: PMGoal) -> str:
        """Create a goal if it doesn't exist, or return existing ID.

        Returns:
            The goal ID in the target PM system.
        """

    # ── Issues ───────────────────────────────────────────────────

    @abstractmethod
    def create_issue(self, issue: PMIssue) -> str:
        """Create a new issue in the target PM system.

        Returns:
            The issue ID in the target PM system.
        """

    @abstractmethod
    def update_issue(self, issue_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing issue.

        Returns:
            True if the update was successful.
        """

    @abstractmethod
    def find_issue_by_codrag_address(self, address: str) -> Optional[str]:
        """Find an existing issue by its CoDRAG address.

        Used for dedup — if an issue with this CoDRAG address already
        exists, we update it instead of creating a duplicate.

        Returns:
            The issue ID if found, None otherwise.
        """

    @abstractmethod
    def list_issues(
        self,
        *,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List issues with optional filters."""

    # ── Health ───────────────────────────────────────────────────

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the PM connection is working.

        Returns:
            True if the connection is healthy.
        """

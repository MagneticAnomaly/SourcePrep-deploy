"""
PaperclipClient — Thin agent-facing wrapper around Phase 65 push infrastructure.

Provides a clean interface for agents to push projects, goals, issues, and
bulk action items to Paperclip without knowing the adapter internals.
"""
from __future__ import annotations

from typing import List, Optional

from codrag.adapters.paperclip_adapter import PaperclipAdapter
from codrag.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from codrag.adapters.push_engine import create_push_engine
from codrag.core.audit.action_item import ActionItem


class PaperclipClient:
    """Agent-facing wrapper around PaperclipAdapter and PushEngine.

    Instantiated with a PMPushConfig and delegates all operations to the
    underlying adapter and push engine. Keeps agents decoupled from adapter
    implementation details.
    """

    def __init__(self, config: PMPushConfig) -> None:
        self._config = config
        self._adapter = PaperclipAdapter(
            base_url=config.paperclip_url,
            company_id=config.paperclip_company_id,
            api_key=config.paperclip_api_key,
        )
        self._push_engine = create_push_engine(config)

    # ── Project ──────────────────────────────────────────────────────

    def push_project(
        self,
        project: PMProject,
        goal_ids: Optional[List[str]] = None,
    ) -> str:
        """Ensure a project exists in Paperclip, creating it if needed.

        Returns the Paperclip project ID.
        """
        return self._adapter.ensure_project(project, goal_ids=goal_ids)

    # ── Goal ─────────────────────────────────────────────────────────

    def push_goal(self, goal: PMGoal) -> str:
        """Ensure a goal exists in Paperclip, creating it if needed.

        Returns the Paperclip goal ID.
        """
        return self._adapter.ensure_goal(goal)

    # ── Issue ────────────────────────────────────────────────────────

    def push_issue(self, issue: PMIssue) -> str:
        """Create a single issue in Paperclip.

        Returns the Paperclip issue ID.
        """
        return self._adapter.create_issue(issue)

    # ── Bulk push ────────────────────────────────────────────────────

    def bulk_push(
        self,
        items: List[ActionItem],
        codrag_project_id: str = "",
        strategy: str = "category",
        min_priority: str = "P2",
        dry_run: bool = False,
    ) -> PushResult:
        """Run the full consolidation → push pipeline for a list of ActionItems.

        Args:
            items: Raw ActionItems from OpportunityManager or audit runner.
            codrag_project_id: CoDRAG project ID used for address generation.
            strategy: Consolidation strategy ("category", "root_file", "severity_band").
            min_priority: Only push items at this priority or higher ("P0"–"P3").
            dry_run: Preview mode — returns result without actually pushing.

        Returns:
            PushResult with counts and error details.
        """
        return self._push_engine.push(
            items,
            codrag_project_id=codrag_project_id,
            strategy=strategy,
            min_priority=min_priority,
            dry_run=dry_run,
        )

    # ── Health ───────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """Return True if the Paperclip server is reachable and healthy."""
        return self._adapter.health_check()

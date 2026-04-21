"""
PaperclipClient — Thin agent-facing wrapper around Phase 65 push infrastructure.

Provides a clean interface for agents to push projects, goals, issues, and
bulk action items to Paperclip without knowing the adapter internals.
"""
from __future__ import annotations

from typing import List, Optional

from prep.adapters.paperclip_adapter import PaperclipAdapter
from prep.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from prep.adapters.push_engine import create_push_engine
from prep.core.audit.action_item import ActionItem


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

    # ── Agent CRUD (Phase 67) ───────────────────────────────────────

    def create_agent(
        self,
        name: str,
        role: str,
        title: str = "",
        adapter_config: Optional[dict] = None,
        capabilities: Optional[List[str]] = None,
        reports_to: Optional[str] = None,
    ) -> str:
        """Create a Paperclip agent. Returns the agent ID."""
        result = self._adapter.create_agent(
            name=name,
            role=role,
            title=title,
            adapter_config=adapter_config,
            capabilities=capabilities,
            reports_to=reports_to,
        )
        return result.get("id", "")

    def update_agent(
        self,
        agent_id: str,
        adapter_config: Optional[dict] = None,
    ) -> None:
        """Update an existing Paperclip agent's config."""
        self._adapter.update_agent(agent_id, adapter_config=adapter_config)

    def list_agents(self) -> list:
        """List all agents in the company."""
        return self._adapter.list_agents()

    def get_agent(self, agent_id: str) -> dict:
        """Get agent details."""
        return self._adapter.get_agent(agent_id)

    def find_agent_by_role(self, role: str) -> Optional[dict]:
        """Find an agent by role slug."""
        return self._adapter.find_agent_by_role(role)

    def pause_agent(self, agent_id: str) -> None:
        """Pause an agent."""
        self._adapter.pause_agent(agent_id)

    def resume_agent(self, agent_id: str) -> None:
        """Resume a paused agent."""
        self._adapter.resume_agent(agent_id)

    # ── Health ───────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """Return True if the Paperclip server is reachable and healthy."""
        return self._adapter.health_check()

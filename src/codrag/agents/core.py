"""AgentCore — single facade combining CoDRAG data access, Paperclip push, git, and config.

All agent engines and orchestration adapters should instantiate AgentCore rather than
reaching into CoDRAGDataAccess, PaperclipClient, or GitClient directly.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.adapters.pm_models import PMGoal, PMIssue, PMProject, PMPushConfig, PushResult
from codrag.agents.shared.codrag_data import CoDRAGDataAccess
from codrag.agents.shared.git_client import GitClient
from codrag.agents.shared.models import AgentConfig
from codrag.agents.shared.paperclip_client import PaperclipClient
from codrag.core.audit.action_item import ActionItem
from codrag.services.settings_store import settings

logger = logging.getLogger(__name__)


class AgentCore:
    """Single entry point for all agent engines.

    Combines CoDRAG read access, Paperclip write access, git operations,
    and per-agent configuration into one cohesive interface.

    Args:
        project_id: CoDRAG project identifier.
        index_dir: Path to the CoDRAG index directory.
        project_root: Optional path to the project source root.
        pm_config: Optional PM push configuration; Paperclip client is only
            created when ``pm_config`` is provided and ``pm_config.enabled``
            is ``True``.
    """

    def __init__(
        self,
        project_id: str,
        index_dir: Path,
        project_root: Optional[Path] = None,
        pm_config: Optional[PMPushConfig] = None,
    ) -> None:
        self.project_id = project_id
        self._data = CoDRAGDataAccess(index_dir, project_root, project_id)
        self._paperclip = PaperclipClient(pm_config) if pm_config and pm_config.enabled else None
        self._git = GitClient(project_root) if project_root else None

    # ── CoDRAG Read Methods ──────────────────────────────────────────────

    def get_audit_findings(
        self,
        min_priority: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Return active (non-dismissed) audit findings.

        Args:
            min_priority: Minimum priority gate, e.g. ``"P1"`` returns P0 + P1.
            categories: Optional list of category strings to filter by.

        Returns:
            List of :class:`~codrag.core.audit.action_item.ActionItem` instances.
        """
        return self._data.get_audit_findings(min_priority=min_priority, categories=categories)

    def refresh_audit(
        self,
        categories: Optional[List[str]] = None,
    ) -> List[ActionItem]:
        """Re-run scanners and return refreshed findings.

        Args:
            categories: Optional list of category strings to limit scanning.

        Returns:
            List of :class:`~codrag.core.audit.action_item.ActionItem` instances.
        """
        return self._data.refresh_audit(categories=categories)

    def get_atlas(self, role: Optional[str] = None) -> str:
        """Get a structural overview, optionally filtered by role."""
        return self._data.get_atlas(role=role)

    def get_impact_radius(self, file_path: str) -> Dict[str, Any]:
        """Return the reverse-dependency impact graph for a file.

        Args:
            file_path: Source-relative or absolute file path.

        Returns:
            Dict with ``"target"`` and ``"dependents"`` keys.
        """
        return self._data.get_impact_radius(file_path)

    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
    ) -> str:
        """Persist an agent observation and return its ID.

        Args:
            content: Observation text.
            file_path: Optional source file this observation relates to.
            category: One of ``note``, ``decision``, ``bug``, ``pattern``,
                ``assumption``.

        Returns:
            Observation UUID string.
        """
        return self._data.save_observation(content, file_path=file_path, category=category)

    def get_observations(self, query: str, limit: int = 5) -> list:
        """Search stored observations and return matches.

        Args:
            query: Free-text query.
            limit: Maximum number of results.

        Returns:
            List of :class:`~codrag.services.observation_store.Observation` instances.
        """
        return self._data.get_observations(query, limit=limit)

    def get_module_structure(self) -> List[Dict[str, Any]]:
        """Get the current module cluster map with domain tags and layers."""
        return self._data.get_module_structure()

    def search_code(self, query: str, k: int = 5, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Semantic code search with optional role scoping."""
        return self._data.search_code(query, k=k, role=role)

    def get_role_vector(self, role_slug: str) -> Any:
        """Get or generate a RoleVector for scoring file relevance."""
        return self._data.get_role_vector(role_slug)

    # ── LLM Access ──────────────────────────────────────────────────────

    def get_llm_client(self, task_id: str = "agent") -> Any:
        """Get an LLM client configured from the AI Gateway settings.

        Reads the model assignment for the given task from pipeline_config.
        Falls back to the 'large' model slot if no agent-specific model is set.

        Returns an LLMClient instance, or None if no LLM is configured.
        """
        from codrag.core.llm_client import LLMClient

        config = settings.get("pipeline_config") or {}

        # Try agent-specific model first, fall back to large model
        model = config.get(f"agent_model_{task_id}", config.get("model_thinking", ""))
        if not model:
            return None

        provider = config.get("llm_provider", "ollama")
        endpoint_url = config.get("ollama_url", "http://localhost:11434")
        api_key = config.get("anthropic_api_key") or config.get("openai_api_key")

        # Cloud providers use different base URLs
        if provider == "anthropic":
            endpoint_url = "https://api.anthropic.com"
        elif provider == "openai":
            endpoint_url = config.get("openai_url", "https://api.openai.com")
        elif provider == "openai-compatible":
            endpoint_url = config.get("openai_url", endpoint_url)

        return LLMClient(
            endpoint_url=endpoint_url,
            model=model,
            provider=provider,
            api_key=api_key,
            timeout=120.0,
        )

    # ── Concurrency Gate ────────────────────────────────────────────────

    def acquire_gate(self, task_name: str = "agent") -> bool:
        """Acquire the agent concurrency gate. Returns True if acquired.

        Must call release_gate() when done (use try/finally).
        Returns False if pipeline is busy or another agent is running.
        """
        from codrag.services.agent_gate import get_agent_gate

        gate = get_agent_gate()
        return gate.can_run(self.project_id, task_name)

    def release_gate(self) -> None:
        """Release the agent concurrency gate."""
        from codrag.services.agent_gate import get_agent_gate

        gate = get_agent_gate()
        gate.release()

    # ── Agent CRUD Placeholders ─────────────────────────────────────────

    def create_agent(self, role_spec: Any) -> str:
        """Create a new Paperclip agent. Not yet implemented in Paperclip adapter."""
        raise NotImplementedError(
            "Paperclip agent creation is not yet supported. "
            "The Staffing Agent will write role files locally until "
            "Paperclip's agent management API is available."
        )

    def update_agent(self, agent_id: str, role_spec: Any) -> None:
        """Update a Paperclip agent. Not yet implemented in Paperclip adapter."""
        raise NotImplementedError(
            "Paperclip agent update is not yet supported."
        )

    # ── Paperclip Write Methods ──────────────────────────────────────────

    def _require_paperclip(self) -> PaperclipClient:
        """Return the Paperclip client or raise RuntimeError if not configured."""
        if self._paperclip is None:
            raise RuntimeError(
                "Paperclip is not configured for this AgentCore instance. "
                "Pass a PMPushConfig with enabled=True to enable push operations."
            )
        return self._paperclip

    def push_project(
        self,
        project: PMProject,
        goal_ids: Optional[List[str]] = None,
    ) -> str:
        """Ensure a project exists in Paperclip, creating it if needed.

        Returns the Paperclip project ID.

        Raises:
            RuntimeError: If Paperclip is not configured.
        """
        return self._require_paperclip().push_project(project, goal_ids=goal_ids)

    def push_goal(self, goal: PMGoal) -> str:
        """Ensure a goal exists in Paperclip, creating it if needed.

        Returns the Paperclip goal ID.

        Raises:
            RuntimeError: If Paperclip is not configured.
        """
        return self._require_paperclip().push_goal(goal)

    def push_issue(self, issue: PMIssue) -> str:
        """Create a single issue in Paperclip.

        Returns the Paperclip issue ID.

        Raises:
            RuntimeError: If Paperclip is not configured.
        """
        return self._require_paperclip().push_issue(issue)

    def bulk_push(
        self,
        items: List[ActionItem],
        strategy: str = "category",
        min_priority: str = "P2",
        dry_run: bool = False,
    ) -> PushResult:
        """Run the full consolidation → push pipeline for a list of ActionItems.

        Args:
            items: Raw ActionItems from OpportunityManager or audit runner.
            strategy: Consolidation strategy ("category", "root_file", "severity_band").
            min_priority: Only push items at this priority or higher ("P0"–"P3").
            dry_run: Preview mode — returns result without actually pushing.

        Returns:
            PushResult with counts and error details.

        Raises:
            RuntimeError: If Paperclip is not configured.
        """
        return self._require_paperclip().bulk_push(
            items,
            strategy=strategy,
            min_priority=min_priority,
            dry_run=dry_run,
        )

    # ── Git Access ───────────────────────────────────────────────────────

    @property
    def git(self) -> Optional[GitClient]:
        """Return the GitClient, or None if no project_root was provided."""
        return self._git

    # ── Agent Config ─────────────────────────────────────────────────────

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Load per-agent configuration from the settings store.

        Args:
            agent_name: Short agent name, e.g. ``"staffing"``.

        Returns:
            :class:`AgentConfig` with defaults for any missing keys.
        """
        raw = settings.project_get(self.project_id, f"agents_config.{agent_name}")
        if raw is None:
            return AgentConfig()
        return AgentConfig.from_dict(raw)

    def save_agent_config(self, agent_name: str, config: AgentConfig) -> None:
        """Persist per-agent configuration to the settings store.

        Args:
            agent_name: Short agent name, e.g. ``"staffing"``.
            config: :class:`AgentConfig` instance to persist.
        """
        settings.project_set(self.project_id, f"agents_config.{agent_name}", config.to_dict())

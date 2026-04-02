"""
Paperclip PM Adapter — REST API integration (Phase 65).

Implements the PMAdapter interface for Paperclip's REST API.
API reference: https://docs.paperclip.ing/api/overview

Paperclip entity hierarchy:
    Company → Goals → Projects → Issues

API base: http://localhost:3100/api
Auth: Bearer token or session cookie

Dedup strategy: CoDRAG addresses are embedded in issue descriptions.
find_issue_by_codrag_address() searches existing issues for the address
string, since Paperclip has no native externalId field.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from codrag.adapters.pm_adapter import PMAdapter
from codrag.adapters.pm_models import (
    CODRAG_TO_PM_PRIORITY,
    PMGoal,
    PMIssue,
    PMProject,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_DEFAULT_TIMEOUT = 15  # seconds per HTTP request


# ── Paperclip Adapter ────────────────────────────────────────────────

class PaperclipAdapter(PMAdapter):
    """Paperclip REST API adapter.

    Uses urllib (stdlib) to avoid adding requests/httpx as a dependency.
    All calls are synchronous — this is fine since push operations are
    infrequent and run in background threads (Pi agent) or on user action.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3100",
        company_id: str = "",
        api_key: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.company_id = company_id
        self.api_key = api_key

        # Cache for project/goal IDs to avoid repeated lookups
        self._project_cache: Dict[str, str] = {}   # name → id
        self._goal_cache: Dict[str, str] = {}       # title → id

    @property
    def provider_name(self) -> str:
        return "Paperclip"

    # ── HTTP helpers ─────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the Paperclip API.

        Returns parsed JSON response.
        Raises RuntimeError on HTTP errors.
        """
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None

        req = Request(url, data=data, headers=self._headers(), method=method)

        try:
            with urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
                resp_body = resp.read().decode("utf-8")
                if resp_body:
                    return json.loads(resp_body)
                return {}
        except HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            logger.error(
                "Paperclip API error %d %s %s: %s",
                e.code, method, path, error_body[:500],
            )
            raise RuntimeError(
                f"Paperclip API {method} {path} returned {e.code}: {error_body[:200]}"
            ) from e
        except URLError as e:
            logger.error("Paperclip connection error: %s", e.reason)
            raise RuntimeError(
                f"Cannot connect to Paperclip at {self.base_url}: {e.reason}"
            ) from e

    def _get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", path, body)

    def _patch(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", path, body)

    # ── Projects ─────────────────────────────────────────────────

    def ensure_project(
        self,
        project: PMProject,
        *,
        goal_ids: Optional[List[str]] = None,
    ) -> str:
        # Check cache first
        if project.name in self._project_cache:
            return self._project_cache[project.name]

        # Search existing projects
        existing = self.list_projects()
        for p in existing:
            if p.get("name", "").lower() == project.name.lower():
                pid = p["id"]
                self._project_cache[project.name] = pid
                logger.debug("Found existing Paperclip project: %s → %s", project.name, pid)
                return pid

        # Create new
        payload: Dict[str, Any] = {
            "name": project.name,
            "description": project.description,
            "status": "planned",
        }
        if goal_ids:
            payload["goalIds"] = goal_ids
        if project.workspace_path:
            payload["workspace"] = {
                "name": project.name.lower().replace(" ", "-"),
                "cwd": project.workspace_path,
                "isPrimary": True,
            }
        if project.repo_url:
            ws = payload.get("workspace", {"name": project.name.lower().replace(" ", "-"), "isPrimary": True})
            ws["repoUrl"] = project.repo_url
            payload["workspace"] = ws

        result = self._post(f"/api/companies/{self.company_id}/projects", payload)
        pid = result.get("id", "")
        self._project_cache[project.name] = pid
        logger.info("Created Paperclip project: %s → %s", project.name, pid)
        return pid

    def list_projects(self) -> List[Dict[str, Any]]:
        result = self._get(f"/api/companies/{self.company_id}/projects")
        # Paperclip may return just the array or wrap it
        if isinstance(result, list):
            return result
        return result.get("projects", result.get("data", []))

    # ── Goals ────────────────────────────────────────────────────

    def ensure_goal(self, goal: PMGoal) -> str:
        # Check cache
        if goal.title in self._goal_cache:
            return self._goal_cache[goal.title]

        # Search existing goals
        try:
            result = self._get(f"/api/companies/{self.company_id}/goals")
            existing = result if isinstance(result, list) else result.get("goals", result.get("data", []))
            for g in existing:
                if g.get("title", "").lower() == goal.title.lower():
                    gid = g["id"]
                    self._goal_cache[goal.title] = gid
                    logger.debug("Found existing Paperclip goal: %s → %s", goal.title, gid)
                    return gid
        except RuntimeError:
            pass  # Goals may not exist yet — that's fine

        # Create new
        payload = {
            "title": goal.title,
            "description": goal.description,
            "level": goal.level,
            "status": goal.status,
        }
        result = self._post(f"/api/companies/{self.company_id}/goals", payload)
        gid = result.get("id", "")
        self._goal_cache[goal.title] = gid
        logger.info("Created Paperclip goal: %s → %s", goal.title, gid)
        return gid

    # ── Issues ───────────────────────────────────────────────────

    def create_issue(self, issue: PMIssue) -> str:
        payload: Dict[str, Any] = {
            "title": issue.title,
            "description": self._build_description(issue),
            "status": "backlog",
            "priority": issue.pm_priority(),
        }
        if issue.project_id:
            payload["projectId"] = issue.project_id
        if issue.goal_id:
            payload["goalId"] = issue.goal_id

        result = self._post(f"/api/companies/{self.company_id}/issues", payload)
        issue_id = result.get("id", "")
        logger.info("Created Paperclip issue: %s → %s", issue.title, issue_id)
        return issue_id

    def update_issue(self, issue_id: str, updates: Dict[str, Any]) -> bool:
        try:
            self._patch(f"/api/issues/{issue_id}", updates)
            return True
        except RuntimeError as e:
            logger.warning("Failed to update Paperclip issue %s: %s", issue_id, e)
            return False

    def find_issue_by_codrag_address(self, address: str) -> Optional[str]:
        """Search existing issues for one containing this CoDRAG address.

        Since Paperclip doesn't have a native externalId field, we embed
        the CoDRAG address in the issue description and search for it.
        """
        try:
            issues = self.list_issues()
            for issue in issues:
                desc = issue.get("description", "")
                if address in desc:
                    return issue.get("id")
        except RuntimeError:
            pass
        return None

    def list_issues(
        self,
        *,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: List[str] = []
        if status:
            params.append(f"status={status}")
        if project_id:
            params.append(f"projectId={project_id}")

        query = f"?{'&'.join(params)}" if params else ""
        result = self._get(f"/api/companies/{self.company_id}/issues{query}")
        if isinstance(result, list):
            return result
        return result.get("issues", result.get("data", []))

    # ── Health ───────────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            result = self._get("/api/health")
            return result.get("status") == "ok"
        except (RuntimeError, Exception):
            return False

    # ── Description Builder ──────────────────────────────────────

    def _build_description(self, issue: PMIssue) -> str:
        """Build rich Markdown description with CoDRAG context hooks.

        The description includes the CoDRAG address and MCP command
        so Paperclip agents can call back to CoDRAG for live context.
        """
        lines: List[str] = [issue.description]

        # Sub-items as checklist
        if issue.sub_items and issue.item_count > 1:
            lines.append("")
            lines.append("### Sub-items")
            for sub in issue.sub_items[:30]:  # Cap at 30
                lines.append(f"- [ ] {sub}")
            if len(issue.sub_items) > 30:
                lines.append(f"- _...and {len(issue.sub_items) - 30} more_")

        # Affected files
        if issue.affected_files:
            lines.append("")
            lines.append(f"### Affected Files ({len(issue.affected_files)})")
            for fp in issue.affected_files[:15]:
                lines.append(f"- `{fp}`")
            if len(issue.affected_files) > 15:
                lines.append(f"- _...and {len(issue.affected_files) - 15} more_")

        # CoDRAG integration block
        lines.append("")
        lines.append("---")
        lines.append("### 🔍 CoDRAG Context")
        lines.append("")
        if issue.codrag_address:
            lines.append(f"**CoDRAG Address:** `{issue.codrag_address}`")
        lines.append(f"**Priority:** {issue.priority} | **Effort:** {issue.effort}")
        lines.append(f"**Category:** {issue.category}")
        if issue.mcp_command:
            lines.append("")
            lines.append("**Get live context:**")
            lines.append(f"```")
            lines.append(issue.mcp_command)
            lines.append(f"```")

        return "\n".join(lines)

    # ── Agent CRUD (Phase 67) ───────────────────────────────────

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents in the company."""
        resp = self._get(f"/api/companies/{self.company_id}/agents")
        return resp.get("agents", resp) if isinstance(resp, dict) else resp

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent details by ID."""
        return self._get(f"/api/agents/{agent_id}")

    def create_agent(
        self,
        name: str,
        role: str,
        title: str = "",
        adapter_type: str = "process",
        adapter_config: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[str]] = None,
        reports_to: Optional[str] = None,
        budget_monthly_cents: int = 0,
    ) -> Dict[str, Any]:
        """Create a new agent in Paperclip.

        Returns the created agent dict (includes 'id').
        """
        payload: Dict[str, Any] = {
            "name": name,
            "role": role,
        }
        if title:
            payload["title"] = title
        if adapter_type:
            payload["adapterType"] = adapter_type
        if adapter_config:
            payload["adapterConfig"] = adapter_config
        if capabilities:
            payload["capabilities"] = capabilities
        if reports_to:
            payload["reportsTo"] = reports_to
        if budget_monthly_cents:
            payload["budgetMonthlyCents"] = budget_monthly_cents

        return self._post(f"/api/companies/{self.company_id}/agents", payload)

    def update_agent(
        self,
        agent_id: str,
        adapter_config: Optional[Dict[str, Any]] = None,
        budget_monthly_cents: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update an existing agent's config or budget."""
        payload: Dict[str, Any] = {}
        if adapter_config is not None:
            payload["adapterConfig"] = adapter_config
        if budget_monthly_cents is not None:
            payload["budgetMonthlyCents"] = budget_monthly_cents
        return self._patch(f"/api/agents/{agent_id}", payload)

    def terminate_agent(self, agent_id: str) -> Dict[str, Any]:
        """Permanently deactivate an agent. Irreversible."""
        return self._post(f"/api/agents/{agent_id}/terminate", {})

    def pause_agent(self, agent_id: str) -> Dict[str, Any]:
        """Pause an agent's heartbeat execution."""
        return self._post(f"/api/agents/{agent_id}/pause", {})

    def resume_agent(self, agent_id: str) -> Dict[str, Any]:
        """Resume a paused agent."""
        return self._post(f"/api/agents/{agent_id}/resume", {})

    def get_org_chart(self) -> Dict[str, Any]:
        """Get the company org chart."""
        return self._get(f"/api/companies/{self.company_id}/org")

    def find_agent_by_role(self, role: str) -> Optional[Dict[str, Any]]:
        """Find an agent by role slug. Returns None if not found."""
        agents = self.list_agents()
        for agent in agents:
            if agent.get("role", "").lower() == role.lower():
                return agent
        return None

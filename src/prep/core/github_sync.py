"""
GitHub sync for CoDRAG Roadmap — Phase 59D.

Provides a lightweight client for GitHub's GraphQL API to import
issues, project items, and milestones as RoadmapNode entries.

Backend-only: all GitHub calls stay on the CoDRAG server. The frontend
never touches GitHub directly (no token exposure).

Usage:
    client = GitHubClient(token="ghp_...", owner="org", repo="project")
    nodes = await client.fetch_issues(state="OPEN", labels=["enhancement"])
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx

from prep.core.goalposts_models import RoadmapNode

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# ── Label → Category Mapping ────────────────────────────────────────

LABEL_CATEGORY_MAP: Dict[str, str] = {
    "bug": "tech_debt",
    "fix": "tech_debt",
    "debt": "tech_debt",
    "enhancement": "feature",
    "feature": "feature",
    "security": "security",
    "architecture": "architecture",
    "refactor": "architecture",
    "documentation": "product",
    "ux": "product",
    "ui": "product",
    "research": "research",
    "market": "market",
    "performance": "architecture",
    "optimization": "architecture",
}

# ── Priority from Labels ────────────────────────────────────────────

LABEL_PRIORITY_MAP: Dict[str, str] = {
    "critical": "P0",
    "urgent": "P0",
    "p0": "P0",
    "high": "P1",
    "p1": "P1",
    "medium": "P2",
    "p2": "P2",
    "low": "P3",
    "p3": "P3",
}


def _label_to_category(labels: List[str]) -> str:
    """Map GitHub labels to a roadmap category."""
    for label in labels:
        key = label.lower().strip()
        if key in LABEL_CATEGORY_MAP:
            return LABEL_CATEGORY_MAP[key]
    return "feature"  # default


def _label_to_priority(labels: List[str]) -> str:
    """Map GitHub labels to a priority level."""
    for label in labels:
        key = label.lower().strip()
        if key in LABEL_PRIORITY_MAP:
            return LABEL_PRIORITY_MAP[key]
    return "P2"  # default


def _make_github_id(url: str) -> str:
    """Deterministic roadmap node ID from a GitHub URL."""
    h = hashlib.sha256(f"github:{url}".encode()).hexdigest()[:8]
    return f"RM-{h}"


# ── GraphQL Queries ──────────────────────────────────────────────────

ISSUES_QUERY = """
query($owner: String!, $repo: String!, $states: [IssueState!], $first: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: $first, after: $after, states: $states, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        url
        state
        createdAt
        closedAt
        labels(first: 20) { nodes { name } }
        milestone { title number }
      }
    }
  }
}
"""

PROJECT_ITEMS_QUERY = """
query($projectId: ID!, $first: Int!, $after: String) {
  node(id: $projectId) {
    ... on ProjectV2 {
      title
      items(first: $first, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue {
              __typename
              number
              title
              body
              url
              state
              createdAt
              closedAt
              labels(first: 20) { nodes { name } }
              milestone { title number }
            }
            ... on PullRequest {
              __typename
              number
              title
              body
              url
              state
              createdAt
              mergedAt
              labels(first: 20) { nodes { name } }
              milestone { title number }
            }
            ... on DraftIssue {
              __typename
              title
              body
              createdAt
            }
          }
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                __typename
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
              ... on ProjectV2ItemFieldIterationValue {
                __typename
                title
                startDate
                duration
                field { ... on ProjectV2IterationField { name } }
              }
            }
          }
        }
      }
    }
  }
}
"""


# ── Sync State ───────────────────────────────────────────────────────

@dataclass
class GitHubSyncState:
    """Tracks last sync metadata."""
    last_synced_at: str = ""
    issues_imported: int = 0
    owner: str = ""
    repo: str = ""
    project_id: str = ""  # ProjectV2 node ID (if configured)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_synced_at": self.last_synced_at,
            "issues_imported": self.issues_imported,
            "owner": self.owner,
            "repo": self.repo,
            "project_id": self.project_id,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GitHubSyncState":
        return cls(
            last_synced_at=d.get("last_synced_at", ""),
            issues_imported=d.get("issues_imported", 0),
            owner=d.get("owner", ""),
            repo=d.get("repo", ""),
            project_id=d.get("project_id", ""),
            error=d.get("error", ""),
        )


# ── Client ───────────────────────────────────────────────────────────

class GitHubClient:
    """Lightweight GitHub GraphQL client for roadmap sync."""

    def __init__(self, token: str, owner: str = "", repo: str = ""):
        self.token = token
        self.owner = owner
        self.repo = repo
        self._client = httpx.Client(
            base_url=GITHUB_GRAPHQL_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def _query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query and return the data dict."""
        response = self._client.post(
            "",
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            errors = result["errors"]
            msg = "; ".join(e.get("message", str(e)) for e in errors)
            logger.error("GitHub GraphQL error: %s", msg)
            raise RuntimeError(f"GitHub GraphQL error: {msg}")

        return result.get("data", {})

    def fetch_issues(
        self,
        *,
        owner: str = "",
        repo: str = "",
        states: Optional[List[str]] = None,
        max_results: int = 50,
        existing_ids: Optional[Set[str]] = None,
    ) -> List[RoadmapNode]:
        """Fetch repository issues and convert to RoadmapNodes.

        Args:
            owner: GitHub owner (org or user). Defaults to self.owner.
            repo: Repository name. Defaults to self.repo.
            states: Issue states to fetch (OPEN, CLOSED). Default: [OPEN].
            max_results: Maximum issues to fetch.
            existing_ids: Set of RoadmapNode IDs to skip (dedup).

        Returns:
            List of RoadmapNodes with source="github".
        """
        owner = owner or self.owner
        repo = repo or self.repo
        existing = existing_ids or set()
        states = states or ["OPEN"]

        if not owner or not repo:
            raise ValueError("GitHub owner and repo are required")

        nodes: List[RoadmapNode] = []
        cursor = None

        while len(nodes) < max_results:
            batch_size = min(50, max_results - len(nodes))
            data = self._query(ISSUES_QUERY, {
                "owner": owner,
                "repo": repo,
                "states": states,
                "first": batch_size,
                "after": cursor,
            })

            repo_data = data.get("repository", {})
            issues_data = repo_data.get("issues", {})
            page_info = issues_data.get("pageInfo", {})

            for issue in issues_data.get("nodes", []):
                node = self._issue_to_node(issue)
                if node.id not in existing:
                    nodes.append(node)
                    existing.add(node.id)

            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.info(
            "GitHub sync: fetched %d issues from %s/%s",
            len(nodes), owner, repo,
        )
        return nodes

    def fetch_project_items(
        self,
        project_id: str,
        *,
        max_results: int = 50,
        existing_ids: Optional[Set[str]] = None,
    ) -> List[RoadmapNode]:
        """Fetch ProjectV2 items and convert to RoadmapNodes.

        ProjectV2 items have custom fields (Status, Iteration) that
        provide richer tier mapping than raw issues.
        """
        existing = existing_ids or set()
        nodes: List[RoadmapNode] = []
        cursor = None

        while len(nodes) < max_results:
            batch_size = min(50, max_results - len(nodes))
            data = self._query(PROJECT_ITEMS_QUERY, {
                "projectId": project_id,
                "first": batch_size,
                "after": cursor,
            })

            project = data.get("node", {})
            items_data = project.get("items", {})
            page_info = items_data.get("pageInfo", {})

            for item in items_data.get("nodes", []):
                node = self._project_item_to_node(item)
                if node and node.id not in existing:
                    nodes.append(node)
                    existing.add(node.id)

            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.info(
            "GitHub sync: fetched %d project items from %s",
            len(nodes), project_id,
        )
        return nodes

    def _issue_to_node(self, issue: Dict[str, Any]) -> RoadmapNode:
        """Convert a GitHub issue to a RoadmapNode."""
        labels = [l["name"] for l in issue.get("labels", {}).get("nodes", [])]
        url = issue.get("url", "")
        is_closed = issue.get("state") == "CLOSED"

        milestone = issue.get("milestone")
        # Closed issues → completed, open with milestone → planned, else → proposed
        if is_closed:
            tier = "completed"
            state = "completed"
        elif milestone:
            tier = "planned"
            state = "accepted"
        else:
            tier = "proposed"
            state = "proposed"

        return RoadmapNode(
            id=_make_github_id(url),
            title=f"#{issue.get('number', '?')} {issue.get('title', 'Untitled')}",
            description=(issue.get("body") or "")[:500],  # Truncate long bodies
            tier=tier,
            position=0,  # Will be assigned by merge logic
            source="github",
            source_ref=url,
            category=_label_to_category(labels),
            priority=_label_to_priority(labels),
            state=state,
            created_at=issue.get("createdAt", ""),
            completed_at=issue.get("closedAt") if is_closed else None,
        )

    def _project_item_to_node(self, item: Dict[str, Any]) -> Optional[RoadmapNode]:
        """Convert a ProjectV2 item to a RoadmapNode.

        Uses custom field values (Status, Iteration) for richer tier mapping.
        """
        content = item.get("content")
        if not content:
            return None

        typename = content.get("__typename", "")

        # Draft issues have minimal fields
        if typename == "DraftIssue":
            title = content.get("title", "Untitled Draft")
            body = content.get("body", "")
            return RoadmapNode(
                id=_make_github_id(f"draft:{title}"),
                title=title,
                description=body[:500],
                tier="proposed",
                source="github",
                source_ref="",
                category="feature",
                priority="P2",
                state="proposed",
                created_at=content.get("createdAt", ""),
            )

        # Issues and PRs
        url = content.get("url", "")
        labels = [l["name"] for l in content.get("labels", {}).get("nodes", [])]

        # Parse custom field values for status/iteration
        status_name = ""
        iteration_title = ""
        for fv in item.get("fieldValues", {}).get("nodes", []):
            fv_type = fv.get("__typename", "")
            if fv_type == "ProjectV2ItemFieldSingleSelectValue":
                field_name = fv.get("field", {}).get("name", "").lower()
                if field_name == "status":
                    status_name = fv.get("name", "").lower()
            elif fv_type == "ProjectV2ItemFieldIterationValue":
                iteration_title = fv.get("title", "")

        # Map ProjectV2 Status → tier
        is_closed = content.get("state") in ("CLOSED", "MERGED")
        if is_closed or status_name in ("done", "completed", "closed"):
            tier, state = "completed", "completed"
        elif status_name in ("in progress", "active", "doing", "in review"):
            tier, state = "active", "active"
        elif status_name in ("todo", "ready", "backlog") or iteration_title:
            tier, state = "planned", "accepted"
        else:
            tier, state = "proposed", "proposed"

        number = content.get("number", "?")
        title = content.get("title", "Untitled")

        return RoadmapNode(
            id=_make_github_id(url or f"project-item:{title}"),
            title=f"#{number} {title}" if url else title,
            description=(content.get("body") or "")[:500],
            tier=tier,
            position=0,
            source="github",
            source_ref=url,
            category=_label_to_category(labels),
            priority=_label_to_priority(labels),
            state=state,
            created_at=content.get("createdAt", ""),
            completed_at=content.get("closedAt") or content.get("mergedAt") if is_closed else None,
        )


# ── Config Helpers ───────────────────────────────────────────────────

def get_github_config(project_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Extract GitHub config from project config dict.

    Expected keys in project config:
        github_token: str   — PAT or app token
        github_owner: str   — org or user
        github_repo: str    — repository name
        github_project_id: str  — optional ProjectV2 node ID (PVT_...)
    """
    token = project_config.get("github_token")
    if not token:
        return None
    return {
        "token": str(token),
        "owner": str(project_config.get("github_owner", "")),
        "repo": str(project_config.get("github_repo", "")),
        "project_id": str(project_config.get("github_project_id", "")),
    }

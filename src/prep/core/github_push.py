"""
GitHub bidirectional push for Prep Roadmap — Phase 59D-3.

Pushes accepted roadmap nodes BACK to GitHub as issues, and updates
ProjectV2 status fields when nodes change tiers.

Operations:
  - create_issue: Push a roadmap node → GitHub issue
  - update_project_status: Sync tier change → ProjectV2 Status field
  - close_issue: Mark a GitHub issue as closed when node is completed

All mutations use GitHub's REST API v3 (simpler for writes than GraphQL).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from prep.core.goalposts_models import RoadmapNode

logger = logging.getLogger(__name__)

GITHUB_REST_URL = "https://api.github.com"

# ── Category → Label Mapping (reverse of sync) ──────────────────────

CATEGORY_LABEL_MAP: Dict[str, str] = {
    "tech_debt": "bug",
    "feature": "enhancement",
    "security": "security",
    "architecture": "architecture",
    "product": "ux",
    "research": "research",
    "market": "market",
}

PRIORITY_LABEL_MAP: Dict[str, str] = {
    "P0": "critical",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
}

# ── Tier → ProjectV2 Status name ────────────────────────────────────

TIER_STATUS_MAP: Dict[str, str] = {
    "completed": "Done",
    "active": "In Progress",
    "planned": "Todo",
    "proposed": "Backlog",
}


# ── GitHub Push Client ───────────────────────────────────────────────

class GitHubPushClient:
    """Creates/updates GitHub issues and ProjectV2 status from roadmap nodes."""

    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self._client = httpx.Client(
            base_url=GITHUB_REST_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    # ── Create Issue ─────────────────────────────────────────────────

    def create_issue(
        self,
        node: RoadmapNode,
        *,
        extra_labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a GitHub issue from a roadmap node.

        Args:
            node: RoadmapNode to push.
            extra_labels: Additional labels to apply.

        Returns:
            Dict with 'issue_number', 'url', 'html_url' on success.

        Raises:
            httpx.HTTPStatusError on API failure.
        """
        # Strip any existing "#N" prefix from title
        title = node.title
        if title.startswith("#"):
            parts = title.split(" ", 1)
            title = parts[1] if len(parts) > 1 else title

        labels: List[str] = []
        cat_label = CATEGORY_LABEL_MAP.get(node.category)
        if cat_label:
            labels.append(cat_label)
        pri_label = PRIORITY_LABEL_MAP.get(node.priority)
        if pri_label:
            labels.append(pri_label)
        if extra_labels:
            labels.extend(extra_labels)

        # Add a "roadmap" label for tracking
        labels.append("roadmap")

        body = self._format_issue_body(node)

        response = self._client.post(
            f"/repos/{self.owner}/{self.repo}/issues",
            json={
                "title": title,
                "body": body,
                "labels": labels,
            },
        )
        response.raise_for_status()
        data = response.json()

        logger.info(
            "Created GitHub issue #%s from roadmap node %s",
            data.get("number"), node.id,
        )

        return {
            "issue_number": data["number"],
            "url": data["url"],
            "html_url": data["html_url"],
        }

    def _format_issue_body(self, node: RoadmapNode) -> str:
        """Format a roadmap node as a GitHub issue body."""
        lines = []

        if node.description:
            lines.append(node.description)
            lines.append("")

        lines.append("---")
        lines.append(f"📋 **Roadmap ID:** `{node.id}`")
        lines.append(f"🏷️ **Category:** {node.category}")
        lines.append(f"⚡ **Priority:** {node.priority}")
        lines.append(f"📍 **Source:** {node.source}")

        if node.ethos_alignment:
            lines.append(f"🎯 **Ethos Alignment:** {node.ethos_alignment}")

        if node.business_impact:
            lines.append(f"💰 **Business Impact:** {node.business_impact}")

        if node.tasks:
            lines.append("")
            lines.append("### Tasks")
            for i, task in enumerate(node.tasks, 1):
                effort_emoji = {"small": "🟢", "medium": "🟡", "large": "🔴"}.get(
                    task.effort, "⚪"
                )
                lines.append(f"- [ ] {effort_emoji} {task.description}")
                if task.file_paths:
                    files = ", ".join(f"`{p}`" for p in task.file_paths[:3])
                    lines.append(f"  Files: {files}")

        lines.append("")
        lines.append("*Created from Prep Roadmap*")

        return "\n".join(lines)

    # ── Close Issue ──────────────────────────────────────────────────

    def close_issue(self, issue_number: int) -> Dict[str, Any]:
        """Close a GitHub issue.

        Args:
            issue_number: GitHub issue number.

        Returns:
            Dict with updated issue data.
        """
        response = self._client.patch(
            f"/repos/{self.owner}/{self.repo}/issues/{issue_number}",
            json={"state": "closed"},
        )
        response.raise_for_status()
        logger.info("Closed GitHub issue #%s", issue_number)
        return response.json()

    # ── Reopen Issue ─────────────────────────────────────────────────

    def reopen_issue(self, issue_number: int) -> Dict[str, Any]:
        """Reopen a previously closed GitHub issue."""
        response = self._client.patch(
            f"/repos/{self.owner}/{self.repo}/issues/{issue_number}",
            json={"state": "open"},
        )
        response.raise_for_status()
        logger.info("Reopened GitHub issue #%s", issue_number)
        return response.json()

    # ── Update Labels ────────────────────────────────────────────────

    def update_labels(
        self, issue_number: int, labels: List[str]
    ) -> Dict[str, Any]:
        """Replace all labels on an issue."""
        response = self._client.put(
            f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels",
            json={"labels": labels},
        )
        response.raise_for_status()
        return response.json()


# ── Batch Push Operations ────────────────────────────────────────────

def push_nodes_to_github(
    nodes: List[RoadmapNode],
    token: str,
    owner: str,
    repo: str,
) -> List[Dict[str, Any]]:
    """Push multiple roadmap nodes to GitHub as issues.

    Only pushes nodes that don't already have a source_ref (GitHub URL).
    After creation, updates node.source_ref with the new issue URL.

    Returns:
        List of creation results [{node_id, issue_number, url}, ...].
    """
    client = GitHubPushClient(token, owner, repo)
    results: List[Dict[str, Any]] = []

    try:
        for node in nodes:
            # Skip nodes already linked to GitHub
            if node.source == "github" and node.source_ref:
                continue

            try:
                result = client.create_issue(node)
                # Update node with GitHub link
                node.source_ref = result["html_url"]
                if node.source == "manual" or node.source == "ai_proposed":
                    # Keep original source but add ref
                    pass
                results.append({
                    "node_id": node.id,
                    **result,
                })
            except Exception as e:
                logger.error(
                    "Failed to push node %s to GitHub: %s", node.id, e
                )
                results.append({
                    "node_id": node.id,
                    "error": str(e),
                })
    finally:
        client.close()

    return results


def sync_tier_change_to_github(
    node: RoadmapNode,
    token: str,
    owner: str,
    repo: str,
) -> Optional[Dict[str, Any]]:
    """Sync a roadmap tier change back to GitHub.

    If completed → close issue.
    If demoted from completed → reopen issue.
    """
    if not node.source_ref or "github.com" not in (node.source_ref or ""):
        return None

    # Extract issue number from URL
    import re
    match = re.search(r'/issues/(\d+)', node.source_ref)
    if not match:
        return None

    issue_number = int(match.group(1))
    client = GitHubPushClient(token, owner, repo)

    try:
        if node.tier == "completed":
            return client.close_issue(issue_number)
        elif node.tier in ("active", "planned"):
            return client.reopen_issue(issue_number)
    except Exception as e:
        logger.error("Failed to sync tier change to GitHub for #%s: %s", issue_number, e)
    finally:
        client.close()

    return None

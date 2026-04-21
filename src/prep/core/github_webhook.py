"""
GitHub Webhook handler for CoDRAG Roadmap — Phase 59D-2.

Receives GitHub webhook events and auto-promotes/demotes roadmap nodes:
  - issues.closed → promote to 'completed'
  - issues.reopened → demote to 'active'
  - pull_request.merged → promote linked issue to 'completed'
  - projects_v2_item.edited → update tier from ProjectV2 Status field

Designed to be mounted as a FastAPI endpoint in the roadmap router.
Verifies webhook signature via HMAC-SHA256.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from prep.core.goalposts_models import (
    RoadmapNode,
    RoadmapState,
    load_roadmap,
    save_roadmap,
)
from prep.core.github_sync import _make_github_id

logger = logging.getLogger(__name__)


# ── Signature Verification ───────────────────────────────────────────

def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    Args:
        payload: Raw request body bytes.
        signature: X-Hub-Signature-256 header value (sha256=...).
        secret: Webhook secret configured in GitHub.

    Returns:
        True if signature is valid.
    """
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


# ── Event Handlers ───────────────────────────────────────────────────

class WebhookResult:
    """Result of processing a webhook event."""
    __slots__ = ("action", "node_id", "old_tier", "new_tier", "created")

    def __init__(
        self,
        action: str = "ignored",
        node_id: str = "",
        old_tier: str = "",
        new_tier: str = "",
        created: bool = False,
    ):
        self.action = action
        self.node_id = node_id
        self.old_tier = old_tier
        self.new_tier = new_tier
        self.created = created

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "node_id": self.node_id,
            "old_tier": self.old_tier,
            "new_tier": self.new_tier,
            "created": self.created,
        }


def process_webhook_event(
    event_type: str,
    payload: Dict[str, Any],
    state: RoadmapState,
) -> WebhookResult:
    """Process a GitHub webhook event and mutate roadmap state.

    Args:
        event_type: GitHub event type (X-GitHub-Event header).
        payload: Parsed JSON payload.
        state: Mutable RoadmapState to update.

    Returns:
        WebhookResult describing what happened.
    """
    if event_type == "issues":
        return _handle_issue_event(payload, state)
    elif event_type == "pull_request":
        return _handle_pr_event(payload, state)
    elif event_type == "projects_v2_item":
        return _handle_project_item_event(payload, state)
    elif event_type == "ping":
        return WebhookResult(action="pong")
    else:
        logger.debug("Ignoring webhook event: %s", event_type)
        return WebhookResult(action="ignored")


def _handle_issue_event(
    payload: Dict[str, Any],
    state: RoadmapState,
) -> WebhookResult:
    """Handle issues.opened, issues.closed, issues.reopened."""
    action = payload.get("action", "")
    issue = payload.get("issue", {})
    url = issue.get("html_url", "")
    node_id = _make_github_id(url)

    node = state.node_by_id(node_id)

    if action == "closed":
        if node:
            old_tier = node.tier
            node.tier = "completed"
            node.state = "completed"
            node.completed_at = datetime.now(timezone.utc).isoformat()
            return WebhookResult(
                action="promoted",
                node_id=node_id,
                old_tier=old_tier,
                new_tier="completed",
            )
        # Issue not tracked — ignore
        return WebhookResult(action="ignored", node_id=node_id)

    elif action == "reopened":
        if node:
            old_tier = node.tier
            node.tier = "active"
            node.state = "active"
            node.completed_at = None
            return WebhookResult(
                action="demoted",
                node_id=node_id,
                old_tier=old_tier,
                new_tier="active",
            )
        return WebhookResult(action="ignored", node_id=node_id)

    elif action == "opened":
        if not node:
            # Auto-import new issues from tracked repo
            labels = [l["name"] for l in issue.get("labels", [])]
            from prep.core.github_sync import _label_to_category, _label_to_priority
            new_node = RoadmapNode(
                id=node_id,
                title=f"#{issue.get('number', '?')} {issue.get('title', 'Untitled')}",
                description=(issue.get("body") or "")[:500],
                tier="proposed",
                position=max((n.position for n in state.proposed_nodes), default=-1) + 1,
                source="github",
                source_ref=url,
                category=_label_to_category(labels),
                priority=_label_to_priority(labels),
                state="proposed",
                created_at=issue.get("created_at", ""),
            )
            state.nodes.append(new_node)
            return WebhookResult(
                action="created",
                node_id=node_id,
                new_tier="proposed",
                created=True,
            )
        return WebhookResult(action="ignored", node_id=node_id)

    return WebhookResult(action="ignored")


def _handle_pr_event(
    payload: Dict[str, Any],
    state: RoadmapState,
) -> WebhookResult:
    """Handle pull_request.closed (merged) → promote linked nodes.

    Looks for issues referenced in the PR body (closes #N, fixes #N patterns).
    """
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})

    if action != "closed" or not pr.get("merged"):
        return WebhookResult(action="ignored")

    # Extract issue references from PR body
    body = pr.get("body") or ""
    repo = payload.get("repository", {})
    base_url = repo.get("html_url", "")

    import re
    # Match: closes #N, fixes #N, resolves #N (case insensitive)
    issue_nums = re.findall(
        r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)',
        body,
        re.IGNORECASE,
    )

    promoted = []
    for num in issue_nums:
        issue_url = f"{base_url}/issues/{num}"
        node_id = _make_github_id(issue_url)
        node = state.node_by_id(node_id)
        if node and node.tier != "completed":
            node.tier = "completed"
            node.state = "completed"
            node.completed_at = datetime.now(timezone.utc).isoformat()
            promoted.append(node_id)

    if promoted:
        return WebhookResult(
            action="promoted",
            node_id=promoted[0],  # Primary
            new_tier="completed",
        )
    return WebhookResult(action="ignored")


def _handle_project_item_event(
    payload: Dict[str, Any],
    state: RoadmapState,
) -> WebhookResult:
    """Handle projects_v2_item.edited → update tier from Status field change."""
    action = payload.get("action", "")
    changes = payload.get("changes", {})

    # Only care about field_value changes
    if action != "edited" or "field_value" not in changes:
        return WebhookResult(action="ignored")

    field_change = changes["field_value"]
    field_name = field_change.get("field_name", "").lower()
    new_value = field_change.get("to", {}).get("name", "").lower()

    if field_name != "status":
        return WebhookResult(action="ignored")

    # Try to find the node by project item content URL
    # ProjectV2 item events include the content node
    item = payload.get("projects_v2_item", {})
    content_node_id = item.get("content_node_id", "")

    # Map status → tier
    if new_value in ("done", "completed", "closed"):
        new_tier, new_state = "completed", "completed"
    elif new_value in ("in progress", "active", "doing", "in review"):
        new_tier, new_state = "active", "active"
    elif new_value in ("todo", "ready", "backlog"):
        new_tier, new_state = "planned", "accepted"
    else:
        new_tier, new_state = "proposed", "proposed"

    # Find matching node by source_ref containing the content URL
    for node in state.nodes:
        if node.source == "github" and content_node_id and content_node_id in (node.source_ref or ""):
            old_tier = node.tier
            node.tier = new_tier
            node.state = new_state
            if new_state == "completed":
                node.completed_at = datetime.now(timezone.utc).isoformat()
            return WebhookResult(
                action="tier_changed",
                node_id=node.id,
                old_tier=old_tier,
                new_tier=new_tier,
            )

    return WebhookResult(action="ignored")

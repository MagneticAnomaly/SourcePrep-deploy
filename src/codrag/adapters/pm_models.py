"""
Universal PM data models — adapter-agnostic (Phase 65).

These models represent the *outgoing* data that CoDRAG pushes to any
project management tool. Each PM adapter maps these to its own API
format (Paperclip issues, GitHub Issues, Jira tickets, etc.).

The models are intentionally simple — they carry CoDRAG intelligence
without assuming anything about the target system's schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Priority mapping helpers ─────────────────────────────────────────

CODRAG_TO_PM_PRIORITY = {
    "P0": "urgent",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
}

PM_STATUS_BACKLOG = "backlog"
PM_STATUS_TODO = "todo"
PM_STATUS_DONE = "done"


# ── Universal PM Issue ───────────────────────────────────────────────

@dataclass
class PMIssue:
    """A single issue to push to a PM tool.

    May represent a consolidated group of ActionItems or a single item.
    The adapter converts this into the target system's format.
    """
    title: str
    description: str
    priority: str = "P2"               # CoDRAG priority (adapter maps to target)
    category: str = "quality"
    effort: str = "small"
    codrag_address: str = ""           # codrag://project_id/HEALTH-a7b9
    mcp_command: str = ""              # Ready-to-paste CoDRAG command
    affected_files: List[str] = field(default_factory=list)
    sub_items: List[str] = field(default_factory=list)  # Descriptions of consolidated items

    # Filled by PushEngine after PM project/goal are resolved
    project_id: str = ""
    goal_id: str = ""

    # Consolidation metadata
    item_count: int = 1                # How many ActionItems were consolidated
    codrag_item_ids: List[str] = field(default_factory=list)  # All original item IDs

    def pm_priority(self) -> str:
        """Map CoDRAG priority to a generic PM priority string."""
        return CODRAG_TO_PM_PRIORITY.get(self.priority, "medium")


@dataclass
class PMProject:
    """A PM project (grouping of related issues)."""
    name: str
    description: str = ""
    workspace_path: str = ""           # CWD for agent workspace
    repo_url: str = ""


@dataclass
class PMGoal:
    """A high-level PM goal that projects/issues roll up to."""
    title: str
    description: str = ""
    level: str = "company"             # Paperclip: "company" | "team"
    status: str = "active"


# ── Push Result ──────────────────────────────────────────────────────

@dataclass
class PushResult:
    """Result of a push operation."""
    pushed: bool = False
    dry_run: bool = False
    projects_created: int = 0
    goals_created: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    issues_skipped: int = 0
    total_action_items: int = 0        # Raw ActionItems before consolidation
    consolidated_groups: int = 0       # Groups after consolidation
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pushed": self.pushed,
            "dry_run": self.dry_run,
            "projects_created": self.projects_created,
            "goals_created": self.goals_created,
            "issues_created": self.issues_created,
            "issues_updated": self.issues_updated,
            "issues_skipped": self.issues_skipped,
            "total_action_items": self.total_action_items,
            "consolidated_groups": self.consolidated_groups,
            "errors": self.errors,
            "details": self.details,
            "conflicts_detected": len(self.conflicts),
        }


# ── Push Config ──────────────────────────────────────────────────────

@dataclass
class PMPushConfig:
    """Configuration for the PM push adapter.

    Loaded from settings_store at runtime.
    """
    enabled: bool = False
    provider: str = "paperclip"        # "paperclip" | "github" | "jira" | "linear"

    # Paperclip-specific
    paperclip_url: str = "http://localhost:3100"
    paperclip_company_id: str = ""
    paperclip_api_key: str = ""

    # Push behavior
    auto_push: bool = False
    push_cadence: str = "manual"       # "on_scan" | "daily" | "manual"
    consolidation_strategy: str = "category"  # "category" | "root_file" | "severity_band"
    min_priority: str = "P2"           # Only push items at this priority or higher
    exclude_categories: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PMPushConfig":
        paperclip = d.get("paperclip", {})
        return cls(
            enabled=d.get("enabled", False),
            provider=d.get("provider", "paperclip"),
            paperclip_url=paperclip.get("url", "http://localhost:3100"),
            paperclip_company_id=paperclip.get("company_id", ""),
            paperclip_api_key=paperclip.get("api_key", ""),
            auto_push=d.get("auto_push", False),
            push_cadence=d.get("push_cadence", "manual"),
            consolidation_strategy=d.get("consolidation_strategy", "category"),
            min_priority=d.get("min_priority", "P2"),
            exclude_categories=d.get("exclude_categories", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "paperclip": {
                "url": self.paperclip_url,
                "company_id": self.paperclip_company_id,
                "api_key": self.paperclip_api_key,
            },
            "auto_push": self.auto_push,
            "push_cadence": self.push_cadence,
            "consolidation_strategy": self.consolidation_strategy,
            "min_priority": self.min_priority,
            "exclude_categories": self.exclude_categories,
        }

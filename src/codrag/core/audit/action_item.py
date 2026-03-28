"""
Unified ActionItem model for CoDRAG analysis tools (Phase 57B).

Provides a single data model for all actionable output from the
Health Scanner (audit analyzers + spaghetti scoring) and the
Advisor (forward-looking LLM proposals). Both dashboard panels
and MCP tools consume this model.

Converters translate legacy Finding, FileScore, and GoalpostProposal
models into ActionItems for backward compatibility during migration.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── Valid enum values ────────────────────────────────────────────────

VALID_SOURCES = frozenset({"health", "advisor"})
VALID_SEVERITIES = frozenset({"critical", "warning", "info", "suggestion"})
VALID_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
VALID_EFFORTS = frozenset({"small", "medium", "large"})
VALID_STATES = frozenset({"proposed", "approved", "dismissed", "completed"})
VALID_CATEGORIES = frozenset({
    "architecture", "security", "feature", "tech_debt",
    "quality", "coverage", "size", "naming", "testing", "research",
})


# ── Sub-task model ───────────────────────────────────────────────────

@dataclass
class SubTask:
    """A concrete sub-step within an ActionItem."""
    description: str
    file_paths: List[str] = field(default_factory=list)
    effort: str = "small"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"description": self.description}
        if self.file_paths:
            d["file_paths"] = self.file_paths
        if self.effort != "small":
            d["effort"] = self.effort
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SubTask":
        return cls(
            description=d.get("description", ""),
            file_paths=d.get("file_paths", []),
            effort=d.get("effort", "small"),
        )


# ── ActionItem model ─────────────────────────────────────────────────

def _make_id(source: str, analyzer: str, title: str, file_paths: List[str]) -> str:
    """Deterministic hash ID for stable handoff references.

    Uses source + analyzer + title + sorted file paths so the same
    finding always gets the same ID across runs.
    """
    key = f"{source}:{analyzer}:{title}:{','.join(sorted(file_paths))}"
    h = hashlib.sha256(key.encode()).hexdigest()[:8]
    prefix = "HEALTH" if source == "health" else "ADV"
    return f"{prefix}-{h}"


@dataclass
class ActionItem:
    """Unified actionable output item.

    Produced by Health Scanner (audit analyzers + spaghetti scoring)
    or the Advisor (LLM planner). Both dashboard panels and MCP tools
    consume this model.
    """
    # Identity
    id: str = ""                       # HEALTH-a7b9 or ADV-c3d4 (deterministic hash)
    title: str = ""
    description: str = ""              # Problem statement or rationale
    category: str = "quality"          # architecture, security, feature, tech_debt, etc.
    severity: str = "info"             # critical, warning, info, suggestion
    priority: str = "P2"               # P0-P3
    effort: str = "small"              # small, medium, large
    source: str = "health"             # "health" or "advisor"

    # Actionable content
    affected_files: List[str] = field(default_factory=list)
    suggested_action: str = ""         # one-sentence concrete action
    tasks: List[SubTask] = field(default_factory=list)

    # User interaction
    state: str = "proposed"            # proposed, approved, dismissed, completed
    user_notes: str = ""               # user context/instructions for AI handoff

    # Provenance
    analyzer: str = ""                 # which analyzer or planner generated this
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: str = ""
    decided_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = _make_id(self.source, self.analyzer, self.title, self.affected_files)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "priority": self.priority,
            "effort": self.effort,
            "source": self.source,
            "affected_files": self.affected_files,
            "suggested_action": self.suggested_action,
            "state": self.state,
            "analyzer": self.analyzer,
            "created_at": self.created_at,
        }
        if self.tasks:
            d["tasks"] = [t.to_dict() for t in self.tasks]
        if self.user_notes:
            d["user_notes"] = self.user_notes
        if self.evidence:
            d["evidence"] = self.evidence
        if self.decided_at:
            d["decided_at"] = self.decided_at
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ActionItem":
        return cls(
            id=d.get("id", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            category=d.get("category", "quality"),
            severity=d.get("severity", "info"),
            priority=d.get("priority", "P2"),
            effort=d.get("effort", "small"),
            source=d.get("source", "health"),
            affected_files=d.get("affected_files", []),
            suggested_action=d.get("suggested_action", ""),
            tasks=[SubTask.from_dict(t) for t in d.get("tasks", [])],
            state=d.get("state", "proposed"),
            user_notes=d.get("user_notes", ""),
            analyzer=d.get("analyzer", ""),
            evidence=d.get("evidence", {}),
            created_at=d.get("created_at", ""),
            decided_at=d.get("decided_at", ""),
        )

    def mcp_command(self, action: str = "refactor") -> str:
        """Generate the MCP command string for AI handoff.

        Returns a ready-to-paste command for Claude Code, Cursor, etc.
        """
        cmd = f'codrag_audit action="{action}" finding_ids=["{self.id}"]'
        if self.user_notes:
            escaped = self.user_notes.replace('"', '\\"')
            cmd += f' instructions="{escaped}"'
        return cmd


# ── Converters ───────────────────────────────────────────────────────

def finding_to_action_item(finding: Any) -> ActionItem:
    """Convert an audit Finding into an ActionItem.

    Accepts either a Finding dataclass or a dict.
    """
    if hasattr(finding, "to_dict"):
        d = finding.to_dict()
    else:
        d = dict(finding)

    return ActionItem(
        id=d.get("finding_id", ""),
        title=d.get("title", ""),
        description=d.get("description", ""),
        category=d.get("category", "quality"),
        severity=d.get("severity", "info"),
        priority=d.get("priority", "P2"),
        effort=d.get("effort", "small"),
        source="health",
        affected_files=d.get("file_paths", []),
        suggested_action=d.get("suggested_action", ""),
        analyzer=d.get("analyzer", ""),
        evidence=d.get("evidence", {}),
    )


def file_score_to_action_item(score: Any) -> ActionItem:
    """Convert a spaghetti FileScore into an ActionItem.

    Accepts either a FileScore dataclass or a dict.
    """
    if hasattr(score, "to_dict"):
        d = score.to_dict()
    else:
        d = dict(score)

    file_path = d.get("file_path", "")
    sev = d.get("severity", "info")
    urgency = d.get("score", 0.0)

    # Build description from available signals
    parts = []
    if d.get("estimated_lines", 0) > 0:
        parts.append(f"{d['estimated_lines']} lines")
    if d.get("fan_in", 0) > 0:
        parts.append(f"{d['fan_in']} dependents")
    if d.get("fan_out", 0) > 0:
        parts.append(f"{d['fan_out']} dependencies")
    if d.get("tech_debt_count", 0) > 0:
        parts.append(f"{d['tech_debt_count']} tech debt items")
    if d.get("in_circular"):
        parts.append("in circular dependency")

    description = f"Refactor urgency {urgency:.2f}: {', '.join(parts)}" if parts else ""
    summary = d.get("summary", "")
    if summary:
        description = f"{summary}\n\n{description}"

    # Map severity to priority
    prio_map = {"critical": "P0", "warning": "P1", "info": "P2"}

    # Build sub-tasks from tech debt items
    tasks = []
    for td in d.get("tech_debt_items", []):
        if isinstance(td, str) and td:
            tasks.append(SubTask(description=td, file_paths=[file_path]))

    return ActionItem(
        title=f"Refactor: {file_path.rsplit('/', 1)[-1] if '/' in file_path else file_path}",
        description=description,
        category="tech_debt",
        severity=sev,
        priority=prio_map.get(sev, "P2"),
        effort="medium" if urgency >= 0.75 else "small",
        source="health",
        affected_files=[file_path] if file_path else [],
        suggested_action=f"Refactor this file to reduce complexity (urgency score: {urgency:.2f})",
        tasks=tasks,
        analyzer="spaghetti_scorer",
        evidence={
            "spaghetti_score": round(urgency, 3),
            "signals": d.get("signals", {}),
            "estimated_lines": d.get("estimated_lines", 0),
            "fan_in": d.get("fan_in", 0),
            "fan_out": d.get("fan_out", 0),
        },
    )


def goalpost_to_action_item(proposal: Any) -> ActionItem:
    """Convert a GoalpostProposal into an ActionItem.

    Accepts either a GoalpostProposal dataclass or a dict.
    """
    if hasattr(proposal, "to_dict"):
        d = proposal.to_dict()
    else:
        d = dict(proposal)

    # Collect file paths from all tasks
    all_files: List[str] = []
    sub_tasks: List[SubTask] = []
    for t in d.get("tasks", []):
        task_files = t.get("file_paths", [])
        all_files.extend(task_files)
        sub_tasks.append(SubTask(
            description=t.get("description", ""),
            file_paths=task_files,
            effort=t.get("effort", "small"),
        ))

    # Deduplicate file paths
    seen: set = set()
    unique_files = []
    for fp in all_files:
        if fp not in seen:
            seen.add(fp)
            unique_files.append(fp)

    # Map Goalposts priority to severity
    prio = d.get("priority", "P2")
    sev_map = {"P0": "critical", "P1": "warning", "P2": "info", "P3": "suggestion"}

    return ActionItem(
        id=d.get("id", ""),
        title=d.get("title", ""),
        description=d.get("rationale", ""),
        category=d.get("category", "feature"),
        severity=sev_map.get(prio, "info"),
        priority=prio,
        effort=sub_tasks[0].effort if sub_tasks else "medium",
        source="advisor",
        affected_files=unique_files,
        suggested_action=d.get("title", ""),
        tasks=sub_tasks,
        state=d.get("state", "proposed"),
        analyzer="advisor_planner",
        created_at=d.get("created_at", ""),
        decided_at=d.get("decided_at", ""),
    )


def roadmap_node_to_action_item(node: Any) -> ActionItem:
    """Convert a RoadmapNode into an ActionItem.

    Accepts either a RoadmapNode dataclass or a dict (Phase 59).
    Preserves tier/position/source in evidence for downstream consumers.
    """
    if hasattr(node, "to_dict"):
        d = node.to_dict()
    else:
        d = dict(node)

    # Collect file paths from tasks
    all_files: List[str] = []
    sub_tasks: List[SubTask] = []
    for t in d.get("tasks", []):
        task_files = t.get("file_paths", [])
        all_files.extend(task_files)
        sub_tasks.append(SubTask(
            description=t.get("description", ""),
            file_paths=task_files,
            effort=t.get("effort", "small"),
        ))

    # Deduplicate file paths
    seen: set = set()
    unique_files = []
    for fp in all_files:
        if fp not in seen:
            seen.add(fp)
            unique_files.append(fp)

    # Map priority to severity
    prio = d.get("priority", "P2")
    sev_map = {"P0": "critical", "P1": "warning", "P2": "info", "P3": "suggestion"}

    return ActionItem(
        id=d.get("id", ""),
        title=d.get("title", ""),
        description=d.get("description", ""),
        category=d.get("category", "feature"),
        severity=sev_map.get(prio, "info"),
        priority=prio,
        effort=sub_tasks[0].effort if sub_tasks else "medium",
        source="roadmap",
        affected_files=unique_files,
        suggested_action=d.get("title", ""),
        tasks=sub_tasks,
        state=d.get("state", "proposed"),
        analyzer="roadmap",
        created_at=d.get("created_at", ""),
        decided_at=d.get("decided_at", ""),
        evidence={
            "tier": d.get("tier", "proposed"),
            "position": d.get("position", 0),
            "source": d.get("source", "manual"),
            "source_ref": d.get("source_ref"),
            "business_impact": d.get("business_impact", ""),
        },
    )


"""Shared data models for Prep agent subsystem.

Pure dataclasses with no Prep internal imports.
These define data contracts between agent engines and shared infrastructure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import List


def _normalize_slug(raw: str) -> str:
    """Normalize a string into a clean slug.

    Lowercases, replaces non-alphanumeric characters with underscores,
    collapses runs of underscores, and strips leading/trailing underscores.
    """
    slug = raw.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug)
    slug = slug.strip("_")
    return slug


@dataclass
class RoleSpec:
    """Paperclip agent role definition."""

    slug: str
    display_name: str
    agents_md: str = ""
    soul_md: str = ""
    knowledge_md: str = ""
    recommended_files: List[str] = field(default_factory=list)
    paperclip_agent_id: str = ""

    def __post_init__(self) -> None:
        self.slug = _normalize_slug(self.slug)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RoleSpec:
        return cls(
            slug=d["slug"],
            display_name=d["display_name"],
            agents_md=d.get("agents_md", ""),
            soul_md=d.get("soul_md", ""),
            knowledge_md=d.get("knowledge_md", ""),
            recommended_files=list(d.get("recommended_files", [])),
            paperclip_agent_id=d.get("paperclip_agent_id", ""),
        )


@dataclass
class ResearchTopic:
    """A topic selected by Researcher Agent."""

    finding_id: str
    title: str
    description: str
    affected_files: List[str] = field(default_factory=list)
    priority: str = "P2"
    impact_summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ResearchTopic:
        return cls(
            finding_id=d["finding_id"],
            title=d["title"],
            description=d["description"],
            affected_files=list(d.get("affected_files", [])),
            priority=d.get("priority", "P2"),
            impact_summary=d.get("impact_summary", ""),
        )


@dataclass
class ResearchPlan:
    """Implementation plan from Researcher Agent."""

    topic_id: str
    title: str
    root_cause: str
    fix_steps: List[str]
    effort: str = "medium"
    risk: str = "low"
    testing_strategy: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ResearchPlan:
        return cls(
            topic_id=d["topic_id"],
            title=d["title"],
            root_cause=d["root_cause"],
            fix_steps=list(d["fix_steps"]),
            effort=d.get("effort", "medium"),
            risk=d.get("risk", "low"),
            testing_strategy=d.get("testing_strategy", ""),
        )


@dataclass
class CleanupCandidate:
    """A file flagged by Digital Custodian for potential cleanup."""

    file_path: str
    finding_id: str
    dependent_count: int
    classification: str = "needs_review"  # safe_to_delete | needs_review | keep
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CleanupCandidate:
        return cls(
            file_path=d["file_path"],
            finding_id=d["finding_id"],
            dependent_count=d["dependent_count"],
            classification=d.get("classification", "needs_review"),
            reason=d.get("reason", ""),
        )


@dataclass
class CleanupPlan:
    """Cleanup plan from Digital Custodian."""

    branch_name: str = ""
    candidates: List[CleanupCandidate] = field(default_factory=list)
    archive_branch: str = "custodian/archive"
    dry_run: bool = True

    def safe_candidates(self) -> List[CleanupCandidate]:
        """Return only candidates classified as safe_to_delete."""
        return [c for c in self.candidates if c.classification == "safe_to_delete"]

    def to_dict(self) -> dict:
        return {
            "branch_name": self.branch_name,
            "candidates": [c.to_dict() for c in self.candidates],
            "archive_branch": self.archive_branch,
            "dry_run": self.dry_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CleanupPlan:
        return cls(
            branch_name=d.get("branch_name", ""),
            candidates=[CleanupCandidate.from_dict(c) for c in d.get("candidates", [])],
            archive_branch=d.get("archive_branch", "custodian/archive"),
            dry_run=d.get("dry_run", True),
        )


@dataclass
class AgentConfig:
    """Per-agent configuration."""

    enabled: bool = False
    adapter: str = "native"
    dry_run: bool = True
    cooldown_seconds: int = 3600
    max_topics_per_run: int = 3
    min_finding_priority: str = "P2"
    auto_push: bool = False
    max_files_per_run: int = 20
    exclude_paths: List[str] = field(default_factory=list)
    trigger: str = "manual"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AgentConfig:
        """Build from a partial dict; missing keys get defaults."""
        defaults = cls()
        return cls(
            enabled=d.get("enabled", defaults.enabled),
            adapter=d.get("adapter", defaults.adapter),
            dry_run=d.get("dry_run", defaults.dry_run),
            cooldown_seconds=d.get("cooldown_seconds", defaults.cooldown_seconds),
            max_topics_per_run=d.get("max_topics_per_run", defaults.max_topics_per_run),
            min_finding_priority=d.get("min_finding_priority", defaults.min_finding_priority),
            auto_push=d.get("auto_push", defaults.auto_push),
            max_files_per_run=d.get("max_files_per_run", defaults.max_files_per_run),
            exclude_paths=list(d.get("exclude_paths", defaults.exclude_paths)),
            trigger=d.get("trigger", defaults.trigger),
        )

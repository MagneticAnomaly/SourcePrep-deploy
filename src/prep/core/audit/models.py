"""
AutoAudit data models for Prep (Phase 43).

Core data structures for the autonomous codebase analysis system.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from prep.services.pipeline.changeset import Changeset


@dataclass
class Finding:
    """A single audit finding produced by an analyzer."""
    analyzer: str          # e.g. "large_files", "circular_deps"
    severity: str          # "critical" | "warning" | "info" | "suggestion"
    category: str          # "size" | "architecture" | "quality" | "coverage"
    title: str             # Human-readable title
    description: str       # Detailed explanation
    file_paths: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_action: str = ""
    finding_id: str = ""   # Stable ID e.g. "GAP-1", "LF-3" — assigned by runner
    priority: str = ""     # "P0" | "P1" | "P2" | "P3" | "P4"
    effort: str = ""       # "small" | "medium" | "large"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analyzer": self.analyzer,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "file_paths": self.file_paths,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action,
            "finding_id": self.finding_id,
            "priority": self.priority,
            "effort": self.effort,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Finding":
        return cls(
            analyzer=d.get("analyzer", ""),
            severity=d.get("severity", "info"),
            category=d.get("category", "quality"),
            title=d.get("title", ""),
            description=d.get("description", ""),
            file_paths=d.get("file_paths", []),
            evidence=d.get("evidence", {}),
            suggested_action=d.get("suggested_action", ""),
            finding_id=d.get("finding_id", ""),
            priority=d.get("priority", ""),
            effort=d.get("effort", ""),
        )


VALID_SEVERITIES = frozenset({"critical", "warning", "info", "suggestion"})
VALID_CATEGORIES = frozenset({"size", "architecture", "quality", "coverage", "naming", "testing"})


@dataclass
class AuditContext:
    """Pre-loaded graph data that analyzers operate on.

    Loaded once by the runner, shared across all analyzers so we don't
    re-parse JSONL files for each analyzer.
    """
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    augmentations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    epistemic: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    modules: List[Dict[str, Any]] = field(default_factory=list)
    atlas: Optional[Dict[str, Any]] = None
    project_root: Optional[Path] = None
    index_dir: Optional[Path] = None
    # Phase 134: changeset-driven staleness — replaces per-stage hash compare.
    # The pre-Phase-134 `file_hashes: Dict[str, str]` field was deleted in
    # the Phase 134 polish pass; no analyzer reads it post-rewrite.
    changeset: Optional[Changeset] = None

    # Exclude globs loaded from repo_policy — applied to file_nodes
    _exclude_globs: Optional[List[str]] = field(
        default=None, repr=False, compare=False
    )

    # Derived indexes built lazily
    _edges_by_source: Optional[Dict[str, List[Dict[str, Any]]]] = field(
        default=None, repr=False, compare=False
    )
    _edges_by_target: Optional[Dict[str, List[Dict[str, Any]]]] = field(
        default=None, repr=False, compare=False
    )
    _file_nodes: Optional[Dict[str, Dict[str, Any]]] = field(
        default=None, repr=False, compare=False
    )
    _symbol_nodes: Optional[Dict[str, Dict[str, Any]]] = field(
        default=None, repr=False, compare=False
    )

    @property
    def edges_by_source(self) -> Dict[str, List[Dict[str, Any]]]:
        if self._edges_by_source is None:
            idx: Dict[str, List[Dict[str, Any]]] = {}
            for e in self.edges:
                idx.setdefault(e.get("source", ""), []).append(e)
            self._edges_by_source = idx
        return self._edges_by_source

    @property
    def edges_by_target(self) -> Dict[str, List[Dict[str, Any]]]:
        if self._edges_by_target is None:
            idx: Dict[str, List[Dict[str, Any]]] = {}
            for e in self.edges:
                idx.setdefault(e.get("target", ""), []).append(e)
            self._edges_by_target = idx
        return self._edges_by_target

    def set_exclude_globs(self, globs: List[str]) -> None:
        """Set exclude globs from repo_policy. Resets cached file_nodes."""
        self._exclude_globs = globs
        self._file_nodes = None  # Reset cache so next access re-filters

    @property
    def file_nodes(self) -> Dict[str, Dict[str, Any]]:
        if self._file_nodes is None:
            from prep.core.glob_utils import matches_any_glob

            raw = {
                nid: n for nid, n in self.nodes.items()
                if n.get("kind") == "file"
            }
            excludes = self._exclude_globs
            if excludes:
                filtered: Dict[str, Dict[str, Any]] = {}
                for nid, n in raw.items():
                    fp = n.get("file_path", "")
                    if fp and matches_any_glob(fp, excludes):
                        continue  # Excluded by repo_policy
                    filtered[nid] = n
                self._file_nodes = filtered
            else:
                self._file_nodes = raw
        return self._file_nodes

    @property
    def symbol_nodes(self) -> Dict[str, Dict[str, Any]]:
        if self._symbol_nodes is None:
            self._symbol_nodes = {
                nid: n for nid, n in self.nodes.items()
                if n.get("kind") == "symbol"
            }
        return self._symbol_nodes

    def in_degree(self, node_id: str) -> int:
        return len(self.edges_by_target.get(node_id, []))

    def out_degree(self, node_id: str) -> int:
        return len(self.edges_by_source.get(node_id, []))

    def module_for_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Find which module a file belongs to."""
        for m in self.modules:
            if file_path in (m.get("member_files") or []):
                return m
        return None


def effective_file_size(node: Dict[str, Any]) -> int:
    """Return a usable byte-size for an audit file node.

    Phase 136 Part 10: the Phase 134/135 Rust-engine cutover stopped
    populating ``metadata.size`` on file nodes (the Python builder set
    it; the Rust builder emits ``Default::default()``).  The markdown-
    link post-process populates ``line_count``, ``section_count`` etc.
    but never ``size``.  Audit analyzers that previously read
    ``meta.get("size", 0)`` silently dropped every file post-cutover.

    Fallback: ``line_count * 40``.  ~40 chars/line is the heuristic the
    spaghetti scorer and large_files thresholds were already calibrated
    against ("~2000 lines" → 80_000 bytes critical threshold).

    Returns 0 only when neither field is present — a genuine signal
    that the file metadata is incomplete (e.g., pre-build node).
    """
    meta = node.get("metadata", {}) or {}
    direct = meta.get("size")
    if direct:
        return int(direct)
    line_count = meta.get("line_count", 0) or 0
    return int(line_count) * 40


@dataclass
class AuditDocument:
    """A generated audit report document."""
    name: str              # e.g. "AUDIT_SUMMARY"
    title: str             # e.g. "Audit Summary"
    content: str           # Markdown content
    generated_at: str = ""
    finding_count: int = 0
    char_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "content": self.content,
            "generated_at": self.generated_at,
            "finding_count": self.finding_count,
            "char_count": self.char_count,
        }


@dataclass
class AuditManifest:
    """Tracks audit run metadata for staleness detection."""
    generated_at: str = ""
    graph_node_count: int = 0
    graph_edge_count: int = 0
    finding_count: int = 0
    document_count: int = 0
    analyzers_run: List[str] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    severity_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "graph_node_count": self.graph_node_count,
            "graph_edge_count": self.graph_edge_count,
            "finding_count": self.finding_count,
            "document_count": self.document_count,
            "analyzers_run": self.analyzers_run,
            "documents": self.documents,
            "severity_counts": self.severity_counts,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditManifest":
        return cls(
            generated_at=d.get("generated_at", ""),
            graph_node_count=d.get("graph_node_count", 0),
            graph_edge_count=d.get("graph_edge_count", 0),
            finding_count=d.get("finding_count", 0),
            document_count=d.get("document_count", 0),
            analyzers_run=d.get("analyzers_run", []),
            documents=d.get("documents", []),
            severity_counts=d.get("severity_counts", {}),
        )


@dataclass
class AuditResult:
    """Complete result of an audit run."""
    findings: List[Finding] = field(default_factory=list)
    documents: List[AuditDocument] = field(default_factory=list)
    manifest: Optional[AuditManifest] = None
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def findings_by_severity(self, severity: str) -> List[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def findings_by_category(self, category: str) -> List[Finding]:
        return [f for f in self.findings if f.category == category]

    def findings_by_analyzer(self, analyzer: str) -> List[Finding]:
        return [f for f in self.findings if f.analyzer == analyzer]

    @property
    def severity_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_count": self.finding_count,
            "severity_counts": self.severity_counts,
            "findings": [f.to_dict() for f in self.findings],
            "documents": [d.to_dict() for d in self.documents],
            "duration_ms": round(self.duration_ms, 1),
            "errors": self.errors,
        }

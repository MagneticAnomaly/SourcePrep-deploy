"""
AutoAudit — Autonomous Codebase Analysis for CoDRAG (Phase 43).

Three tiers:
  Tier 1: Analyzers (pure graph queries, no LLM)
  Tier 2: Synthesizer (LLM-generated markdown reports)
  Tier 3: Continuous monitoring (deepening loop integration)
"""
from .models import (
    AuditContext,
    AuditDocument,
    AuditManifest,
    AuditResult,
    Finding,
)
from .context import load_audit_context
from .runner import (
    run_audit,
    save_findings,
    load_findings,
    run_health_scan,
    save_action_items,
    load_action_items,
)
from .synthesizer import AuditSynthesizer, save_documents
from .spaghetti_scorer import (
    FileScore,
    SpaghettiResult,
    run_spaghetti_scan,
    save_spaghetti,
    load_spaghetti,
    score_files,
)
from .action_item import (
    ActionItem,
    SubTask,
    finding_to_action_item,
    file_score_to_action_item,
    goalpost_to_action_item,
    roadmap_node_to_action_item,
)

__all__ = [
    "ActionItem",
    "AuditContext",
    "AuditDocument",
    "AuditManifest",
    "AuditResult",
    "AuditSynthesizer",
    "FileScore",
    "Finding",
    "SpaghettiResult",
    "SubTask",
    "file_score_to_action_item",
    "finding_to_action_item",
    "goalpost_to_action_item",
    "roadmap_node_to_action_item",
    "load_action_items",
    "load_audit_context",
    "load_findings",
    "load_spaghetti",
    "run_audit",
    "run_health_scan",
    "run_spaghetti_scan",
    "save_action_items",
    "save_documents",
    "save_findings",
    "save_spaghetti",
    "score_files",
]

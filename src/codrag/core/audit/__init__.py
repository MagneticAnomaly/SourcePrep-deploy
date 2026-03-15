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
from .runner import run_audit, save_findings, load_findings
from .synthesizer import AuditSynthesizer, save_documents
from .spaghetti_scorer import (
    FileScore,
    SpaghettiResult,
    run_spaghetti_scan,
    save_spaghetti,
    load_spaghetti,
    score_files,
)

__all__ = [
    "AuditContext",
    "AuditDocument",
    "AuditManifest",
    "AuditResult",
    "AuditSynthesizer",
    "FileScore",
    "Finding",
    "SpaghettiResult",
    "load_audit_context",
    "load_findings",
    "load_spaghetti",
    "run_audit",
    "run_spaghetti_scan",
    "save_documents",
    "save_findings",
    "save_spaghetti",
    "score_files",
]

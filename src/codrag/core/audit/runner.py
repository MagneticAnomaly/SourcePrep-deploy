"""
AutoAudit runner for CoDRAG (Phase 43).

Orchestrates all analyzers, collects findings, writes results to disk.
"""
from __future__ import annotations
import os
import json
import logging
import hashlib
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from .context import load_audit_context
from .models import AuditContext, AuditManifest, AuditResult, Finding

logger = logging.getLogger(__name__)


# ── Built-in analyzer registry ──────────────────────────────────

def _load_audit_config() -> Dict[str, Any]:
    """Load audit_config from the global UI config, with fallbacks."""
    try:
        from codrag.services.settings_store import settings
        ui = settings.get("ui_config") or {}
        return ui.get("audit_config") or {}
    except Exception:
        return {}


def _default_analyzers(audit_cfg: Optional[Dict[str, Any]] = None):
    """Lazily import and instantiate all built-in analyzers.

    Reads thresholds from audit_config so users can tune sensitivity
    via the dashboard Settings panel.
    """
    from .analyzers.large_files import LargeFileAnalyzer
    from .analyzers.misplaced_imports import MisplacedImportAnalyzer
    from .analyzers.dead_code import DeadCodeAnalyzer
    from .analyzers.hub_bottlenecks import HubBottleneckAnalyzer
    from .analyzers.tech_debt import TechDebtAnalyzer
    from .analyzers.staleness import StalenessAnalyzer
    from .analyzers.circular_deps import CircularDependencyAnalyzer
    from .analyzers.duplicate_logic import DuplicateLogicAnalyzer
    from .analyzers.test_coverage import TestCoverageAnalyzer
    from .analyzers.naming import NamingConsistencyAnalyzer
    from .analyzers.api_surface import ApiSurfaceAnalyzer

    cfg = audit_cfg or {}

    return [
        LargeFileAnalyzer(
            critical_bytes=int(cfg.get("large_file_threshold_bytes", 80000)),
            warning_bytes=int(cfg.get("large_file_warning_bytes", 40000)),
        ),
        CircularDependencyAnalyzer(),
        MisplacedImportAnalyzer(),
        DeadCodeAnalyzer(),
        HubBottleneckAnalyzer(
            z_threshold=float(cfg.get("hub_z_threshold", 2.0)),
        ),
        TechDebtAnalyzer(),
        StalenessAnalyzer(),
        DuplicateLogicAnalyzer(
            similarity_threshold=float(cfg.get("similarity_threshold", 0.65)),
        ),
        TestCoverageAnalyzer(),
        NamingConsistencyAnalyzer(),
        ApiSurfaceAnalyzer(),
    ]


# ── Runner ──────────────────────────────────────────────────────

def run_audit(
    index_dir: Path,
    project_root: Optional[Path] = None,
    categories: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> AuditResult:
    """Run all audit analyzers and return findings.

    This is the Tier 1 entry point — pure graph analysis, no LLM.

    Args:
        index_dir: Path to the project's index directory containing trace data.
        project_root: Path to the project root (needed for staleness checks).
        categories: Optional filter — only run analyzers matching these categories.
        progress_callback: Optional (phase, current, total) progress reporter.

    Returns:
        AuditResult with all findings.
    """
    start = time.monotonic()
    result = AuditResult()

    # Load context
    if progress_callback:
        progress_callback("audit_loading", 0, 1)

    ctx = load_audit_context(index_dir, project_root)

    if not ctx.nodes:
        result.errors.append("No trace graph data found. Run the enrichment pipeline first.")
        return result

    logger.info(
        "Audit context loaded: %d nodes, %d edges, %d augmentations, %d epistemic, %d modules",
        len(ctx.nodes), len(ctx.edges), len(ctx.augmentations),
        len(ctx.epistemic), len(ctx.modules),
    )

    # Run analyzers (with user-configured thresholds)
    audit_cfg = _load_audit_config()
    analyzers = _default_analyzers(audit_cfg)
    if categories:
        cat_set = set(categories)
        analyzers = [a for a in analyzers if a.category in cat_set]

    total = len(analyzers)
    for i, analyzer in enumerate(analyzers):
        if progress_callback:
            progress_callback("audit_analyzing", i, total)

        try:
            analyzer_findings = analyzer.analyze(ctx)
            result.findings.extend(analyzer_findings)
            logger.debug(
                "Analyzer %s: %d findings", analyzer.name, len(analyzer_findings)
            )
        except Exception as e:
            error_msg = f"Analyzer {analyzer.name} failed: {e}"
            logger.warning(error_msg)
            result.errors.append(error_msg)

    if progress_callback:
        progress_callback("audit_analyzing", total, total)

    # Assign stable IDs, priority, and effort to each finding
    _assign_ids_and_priority(result.findings)

    # Build manifest
    result.manifest = AuditManifest(
        generated_at=datetime.now(timezone.utc).isoformat(),
        graph_node_count=len(ctx.nodes),
        graph_edge_count=len(ctx.edges),
        finding_count=len(result.findings),
        analyzers_run=[a.name for a in analyzers],
        severity_counts=result.severity_counts,
    )

    result.duration_ms = (time.monotonic() - start) * 1000

    logger.info(
        "Audit complete: %d findings (%s) in %.1fms",
        len(result.findings),
        ", ".join(f"{k}={v}" for k, v in sorted(result.severity_counts.items())),
        result.duration_ms,
    )

    return result


def save_findings(
    result: AuditResult,
    index_dir: Path,
) -> Path:
    """Persist audit findings to disk.

    Writes:
      - {index_dir}/audit/findings.json — raw structured findings
      - {index_dir}/audit/audit_manifest.json — run metadata

    Returns:
        Path to the audit output directory.
    """
    audit_dir = Path(index_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    # Write findings
    findings_data = {
        "generated_at": result.manifest.generated_at if result.manifest else "",
        "finding_count": result.finding_count,
        "severity_counts": result.severity_counts,
        "findings": [f.to_dict() for f in result.findings],
        "errors": result.errors,
        "duration_ms": round(result.duration_ms, 1),
    }
    _atomic_write_json(audit_dir / "findings.json", findings_data)

    # Write manifest
    if result.manifest:
        _atomic_write_json(audit_dir / "audit_manifest.json", result.manifest.to_dict())

    logger.info("Saved %d findings to %s", result.finding_count, audit_dir)
    return audit_dir


def load_findings(index_dir: Path) -> Optional[AuditResult]:
    """Load previously saved audit findings from disk."""
    findings_path = Path(index_dir) / "audit" / "findings.json"
    if not findings_path.exists():
        return None

    try:
        with open(findings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = AuditResult(
            findings=[Finding.from_dict(fd) for fd in data.get("findings", [])],
            errors=data.get("errors", []),
            duration_ms=data.get("duration_ms", 0),
        )

        manifest_path = Path(index_dir) / "audit" / "audit_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                result.manifest = AuditManifest.from_dict(json.load(f))

        return result
    except Exception as e:
        logger.warning("Failed to load audit findings: %s", e)
        return None


_CATEGORY_PREFIXES = {
    "size": "SIZE",
    "architecture": "ARCH",
    "quality": "QUAL",
    "coverage": "COV",
    "naming": "NAME",
    "testing": "TEST",
}

_SEVERITY_TO_PRIORITY = {
    "critical": "P0",
    "warning": "P1",
    "info": "P2",
    "suggestion": "P3",
}

_EFFORT_HEURISTICS = {
    "large_files": "large",
    "circular_deps": "large",
    "misplaced_imports": "medium",
    "hub_bottlenecks": "medium",
    "dead_code": "small",
    "duplicate_logic": "medium",
    "tech_debt": "medium",
    "staleness": "small",
    "test_coverage": "medium",
    "naming_consistency": "small",
    "api_surface": "small",
}


def _assign_ids_and_priority(findings: List[Finding]) -> None:
    """Assign stable IDs, priority, and effort to findings in-place.

    IDs are formatted as ``ARCH-a7b9`` — category prefix + 4-char hash
    of the finding's core identity. This ensures deterministic IDs across
    runs so asynchronous AI handoffs remain valid. Priority is derived
    from severity. Effort is a heuristic based on the analyzer type.
    """
    for f in findings:
        prefix = _CATEGORY_PREFIXES.get(f.category, "MISC")
        
        # Create deterministic hash based on identity
        files_str = ",".join(sorted(f.file_paths))
        identity_str = f"{f.analyzer}:{f.title}:{files_str}"
        h = hashlib.sha256(identity_str.encode('utf-8')).hexdigest()[:4]
        
        f.finding_id = f"{prefix}-{h}"

        if not f.priority:
            f.priority = _SEVERITY_TO_PRIORITY.get(f.severity, "P2")

        if not f.effort:
            f.effort = _EFFORT_HEURISTICS.get(f.analyzer, "medium")


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via temp file + rename."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=str(path.parent),
        delete=False, encoding="utf-8",
    )
    try:
        json.dump(data, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

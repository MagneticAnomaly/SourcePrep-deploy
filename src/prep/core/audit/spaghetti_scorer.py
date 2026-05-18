"""
Spaghetti Finder — per-file refactor urgency scoring (Phase 52).

Computes a composite 0.0-1.0 "refactor urgency" score for every file
in the trace graph by combining static signals (line count, coupling,
symbol density) with LLM-derived signals (tech debt, epistemic confidence).

No LLM calls — uses data already produced by the enrichment pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .context import load_audit_context
from .models import AuditContext

logger = logging.getLogger(__name__)


# ── Score weights ──────────────────────────────────────────────────

W_LINES = 0.25
W_FAN_IN = 0.20
W_FAN_OUT = 0.10
W_SYMBOL_DENSITY = 0.10
W_CIRCULAR = 0.10
W_TECH_DEBT = 0.15
W_LOW_CONFIDENCE = 0.10

# Severity thresholds
CRITICAL_THRESHOLD = 0.75
WARNING_THRESHOLD = 0.50
INFO_THRESHOLD = 0.45

# Minimum file size to even consider (skip tiny files)
MIN_BYTES = 2_000  # ~50 lines


@dataclass
class FileScore:
    """Refactor urgency score for a single file."""
    file_path: str
    score: float
    severity: str  # "critical" | "warning" | "info"
    estimated_lines: int = 0
    fan_in: int = 0
    fan_out: int = 0
    symbol_count: int = 0
    tech_debt_count: int = 0
    tech_debt_items: List[str] = field(default_factory=list)
    epistemic_confidence: float = -1.0  # -1 = no data
    in_circular: bool = False
    language: str = "unknown"
    role: str = "unknown"
    summary: str = ""
    module_name: str = ""
    # Per-signal normalized values (for debugging / UI breakdowns)
    signals: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "file_path": self.file_path,
            "score": round(self.score, 3),
            "severity": self.severity,
            "estimated_lines": self.estimated_lines,
            "fan_in": self.fan_in,
            "fan_out": self.fan_out,
            "symbol_count": self.symbol_count,
            "tech_debt_count": self.tech_debt_count,
            "language": self.language,
            "role": self.role,
            "module_name": self.module_name,
        }
        if self.tech_debt_items:
            d["tech_debt_items"] = self.tech_debt_items[:5]
        if self.summary:
            d["summary"] = self.summary[:200]
        if self.epistemic_confidence >= 0:
            d["epistemic_confidence"] = round(self.epistemic_confidence, 3)
        if self.in_circular:
            d["in_circular"] = True
        if self.signals:
            d["signals"] = {k: round(v, 3) for k, v in self.signals.items()}
        return d


@dataclass
class SpaghettiResult:
    """Complete spaghetti scoring result."""
    files: List[FileScore] = field(default_factory=list)
    file_count: int = 0
    scored_count: int = 0
    severity_counts: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_count": self.file_count,
            "scored_count": self.scored_count,
            "severity_counts": self.severity_counts,
            "duration_ms": round(self.duration_ms, 1),
            "files": [f.to_dict() for f in self.files],
        }


# ── Percentile normalization ──────────────────────────────────────

def _percentile_normalize(values: List[float]) -> List[float]:
    """Normalize values to 0.0-1.0 using percentile ranking.

    Each value's normalized score is its rank / total, so the median
    file gets 0.5 regardless of the raw distribution shape.
    """
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [0.5]

    # Rank by value (average rank for ties)
    indexed = sorted(enumerate(values), key=lambda iv: iv[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j - 1) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank / (n - 1) if n > 1 else 0.5
        i = j
    return ranks


# ── Circular dependency detection ─────────────────────────────────

def _find_circular_files(ctx: AuditContext) -> set:
    """Find files involved in circular import dependencies.

    Uses DFS to detect cycles in the file-level import graph.
    Returns a set of file node IDs that participate in any cycle.
    """
    # Build adjacency for file-level imports only
    import_graph: Dict[str, List[str]] = defaultdict(list)
    file_nids = set(ctx.file_nodes.keys())
    for edge in ctx.edges:
        kind = edge.get("kind", "")
        if kind not in ("imports", "import"):
            continue
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src in file_nids and tgt in file_nids:
            import_graph[src].append(tgt)

    # Tarjan's SCC to find cycles
    circular: set = set()
    index_counter = [0]
    stack: list = []
    lowlink: Dict[str, int] = {}
    index_map: Dict[str, int] = {}
    on_stack: set = set()

    def strongconnect(v: str) -> None:
        index_map[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        for w in import_graph.get(v, []):
            if w not in index_map:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index_map[w])

        if lowlink[v] == index_map[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                circular.update(scc)

    for nid in file_nids:
        if nid not in index_map:
            strongconnect(nid)

    return circular


# ── Scorer ─────────────────────────────────────────────────────────

def score_files(
    ctx: AuditContext,
    min_bytes: int = MIN_BYTES,
) -> SpaghettiResult:
    """Score all files in the trace graph by refactor urgency.

    Args:
        ctx: Pre-loaded audit context (from load_audit_context).
        min_bytes: Minimum file size to include (skip tiny files).

    Returns:
        SpaghettiResult with files sorted by score (highest first).
    """
    start = time.monotonic()

    if not ctx.file_nodes:
        return SpaghettiResult()

    # Pre-compute circular involvement
    circular_nids = _find_circular_files(ctx)

    # Pre-compute symbols per file
    symbols_per_file: Dict[str, int] = defaultdict(int)
    # Phase 65: Use file_nodes (which respects exclude globs) for the
    # parent-file lookup. Iterate all nodes for symbols since symbol
    # nodes don't have a 'kind' == 'file', but only count symbols that
    # belong to non-excluded files.
    file_path_to_nid: Dict[str, str] = {}
    for fnid, fnode in ctx.file_nodes.items():
        fp = fnode.get("file_path", "")
        if fp:
            file_path_to_nid[fp] = fnid

    for nid, node in ctx.nodes.items():
        if node.get("kind") == "symbol":
            fp = node.get("file_path", "")
            if fp and fp in file_path_to_nid:
                symbols_per_file[file_path_to_nid[fp]] += 1

    # Collect raw values for each file
    raw_data: List[Tuple[str, Dict[str, Any]]] = []

    from prep.core.audit.models import effective_file_size
    for nid, node in ctx.file_nodes.items():
        # Phase 136 Part 10: shared helper centralizes the
        # size-or-line-count fallback for the Rust-cutover regression.
        # See `models.effective_file_size` for the rationale.
        size = effective_file_size(node)
        if size < min_bytes:
            continue

        file_path = node.get("file_path", "")
        if not file_path:
            continue

        meta = node.get("metadata", {}) or {}
        est_lines = meta.get("line_count") or (size // 40)
        fan_in = ctx.in_degree(nid)
        fan_out = ctx.out_degree(nid)
        sym_count = symbols_per_file.get(nid, 0)
        in_circ = nid in circular_nids

        # LLM-derived signals
        epi = ctx.epistemic.get(nid, {})
        tech_debt = epi.get("tech_debt") or []
        if isinstance(tech_debt, str):
            tech_debt = [tech_debt] if tech_debt else []
        td_count = len(tech_debt)

        epi_confidence = epi.get("epistemic_confidence", -1.0)
        if epi_confidence is None:
            epi_confidence = -1.0

        # Augmentation data
        aug = ctx.augmentations.get(nid, {})
        role = aug.get("role", "unknown")
        summary = aug.get("summary", "")
        lang = node.get("language", "unknown")

        # Module
        mod = ctx.module_for_file(file_path)
        mod_name = mod.get("name", "") if mod else ""

        raw_data.append((nid, {
            "file_path": file_path,
            "est_lines": est_lines,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "sym_count": sym_count,
            "in_circ": in_circ,
            "td_count": td_count,
            "tech_debt_items": tech_debt[:5],
            "epi_confidence": epi_confidence,
            "language": lang,
            "role": role,
            "summary": summary,
            "module_name": mod_name,
        }))

    if not raw_data:
        return SpaghettiResult(file_count=len(ctx.file_nodes))

    # Extract raw signal arrays for percentile normalization
    lines_raw = [d["est_lines"] for _, d in raw_data]
    fan_in_raw = [d["fan_in"] for _, d in raw_data]
    fan_out_raw = [d["fan_out"] for _, d in raw_data]
    sym_raw = [d["sym_count"] for _, d in raw_data]
    td_raw = [d["td_count"] for _, d in raw_data]

    # For confidence, lower = worse, so invert: norm = 1 - percentile(confidence)
    # Only include files that have epistemic data
    conf_raw = []
    for _, d in raw_data:
        if d["epi_confidence"] >= 0:
            conf_raw.append(d["epi_confidence"])
        else:
            conf_raw.append(0.5)  # neutral default for files without data

    # Normalize
    n_lines = _percentile_normalize(lines_raw)
    n_fan_in = _percentile_normalize(fan_in_raw)
    n_fan_out = _percentile_normalize(fan_out_raw)
    n_sym = _percentile_normalize(sym_raw)
    n_td = _percentile_normalize(td_raw)
    n_conf_pct = _percentile_normalize(conf_raw)
    # Invert confidence: low confidence = high urgency
    n_conf = [1.0 - v for v in n_conf_pct]

    # Compute composite scores
    file_scores: List[FileScore] = []
    for i, (nid, d) in enumerate(raw_data):
        circ_val = 1.0 if d["in_circ"] else 0.0

        score = (
            W_LINES * n_lines[i]
            + W_FAN_IN * n_fan_in[i]
            + W_FAN_OUT * n_fan_out[i]
            + W_SYMBOL_DENSITY * n_sym[i]
            + W_CIRCULAR * circ_val
            + W_TECH_DEBT * n_td[i]
            + W_LOW_CONFIDENCE * n_conf[i]
        )

        # Determine severity
        if score >= CRITICAL_THRESHOLD:
            severity = "critical"
        elif score >= WARNING_THRESHOLD:
            severity = "warning"
        elif score >= INFO_THRESHOLD:
            severity = "info"
        else:
            continue  # Skip healthy files

        fs = FileScore(
            file_path=d["file_path"],
            score=score,
            severity=severity,
            estimated_lines=d["est_lines"],
            fan_in=d["fan_in"],
            fan_out=d["fan_out"],
            symbol_count=d["sym_count"],
            tech_debt_count=d["td_count"],
            tech_debt_items=d["tech_debt_items"],
            epistemic_confidence=d["epi_confidence"],
            in_circular=d["in_circ"],
            language=d["language"],
            role=d["role"],
            summary=d["summary"],
            module_name=d["module_name"],
            signals={
                "lines": n_lines[i],
                "fan_in": n_fan_in[i],
                "fan_out": n_fan_out[i],
                "symbols": n_sym[i],
                "circular": circ_val,
                "tech_debt": n_td[i],
                "low_confidence": n_conf[i],
            },
        )
        file_scores.append(fs)

    # Sort by score descending
    file_scores.sort(key=lambda f: -f.score)

    # Severity counts
    sev_counts: Dict[str, int] = {}
    for fs in file_scores:
        sev_counts[fs.severity] = sev_counts.get(fs.severity, 0) + 1

    result = SpaghettiResult(
        files=file_scores,
        file_count=len(ctx.file_nodes),
        scored_count=len(file_scores),
        severity_counts=sev_counts,
        duration_ms=(time.monotonic() - start) * 1000,
    )

    logger.info(
        "Spaghetti scoring complete: %d/%d files flagged (%s) in %.1fms",
        result.scored_count,
        result.file_count,
        ", ".join(f"{k}={v}" for k, v in sorted(sev_counts.items())),
        result.duration_ms,
    )

    return result


def run_spaghetti_scan(
    index_dir: Path,
    project_root: Optional[Path] = None,
) -> SpaghettiResult:
    """Convenience entry point: load context + score files.

    Args:
        index_dir: Path to the project's index directory.
        project_root: Path to the project root.

    Returns:
        SpaghettiResult with ranked files.
    """
    ctx = load_audit_context(index_dir, project_root)
    if not ctx.nodes:
        return SpaghettiResult()
    result = score_files(ctx)
    # Phase 136 Part 10: guard rail — a non-empty file graph that scores
    # zero hotspots is a silent regression signal (saw it 2026-05-17 when
    # the Rust file-node schema dropped `size`).  Log loudly so future
    # divergences surface before someone notices on the dashboard.
    if (
        result.scored_count == 0
        and len(ctx.file_nodes) > 100
    ):
        logger.warning(
            "[Spaghetti] scored_count=0 against %d file_nodes — "
            "no hotspots emitted.  Likely cause: file-node metadata "
            "schema mismatch (missing size/line_count) or thresholds "
            "miscalibrated.  See docs/Phase136_Dogfood-fixes/Part10_*.",
            len(ctx.file_nodes),
        )
    return result


def save_spaghetti(result: SpaghettiResult, index_dir: Path) -> Path:
    """Persist spaghetti scores to disk.

    Writes {index_dir}/audit/spaghetti.json.
    """
    audit_dir = Path(index_dir) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    out_path = audit_dir / "spaghetti.json"

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=str(audit_dir),
        delete=False, encoding="utf-8",
    )
    try:
        json.dump(result.to_dict(), tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.rename(tmp.name, out_path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise

    logger.info("Saved spaghetti scores to %s", out_path)
    return out_path


def load_spaghetti(index_dir: Path) -> Optional[SpaghettiResult]:
    """Load previously saved spaghetti scores from disk."""
    path = Path(index_dir) / "audit" / "spaghetti.json"
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        files = []
        for fd in data.get("files", []):
            fs = FileScore(
                file_path=fd.get("file_path", ""),
                score=fd.get("score", 0.0),
                severity=fd.get("severity", "info"),
                estimated_lines=fd.get("estimated_lines", 0),
                fan_in=fd.get("fan_in", 0),
                fan_out=fd.get("fan_out", 0),
                symbol_count=fd.get("symbol_count", 0),
                tech_debt_count=fd.get("tech_debt_count", 0),
                tech_debt_items=fd.get("tech_debt_items", []),
                epistemic_confidence=fd.get("epistemic_confidence", -1.0),
                in_circular=fd.get("in_circular", False),
                language=fd.get("language", "unknown"),
                role=fd.get("role", "unknown"),
                summary=fd.get("summary", ""),
                module_name=fd.get("module_name", ""),
                signals=fd.get("signals", {}),
            )
            files.append(fs)

        return SpaghettiResult(
            files=files,
            file_count=data.get("file_count", 0),
            scored_count=data.get("scored_count", 0),
            severity_counts=data.get("severity_counts", {}),
            duration_ms=data.get("duration_ms", 0.0),
        )
    except Exception as e:
        logger.warning("Failed to load spaghetti scores: %s", e)
        return None

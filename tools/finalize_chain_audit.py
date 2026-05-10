#!/usr/bin/env python3
"""Phase 124 T1 — Finalize Chain Epistemic Audit harness.

Grades stages 11–15 (Atlas, Rules, Concepts, Audit, Antibodies)
against a Phase-82-style rubric and flags AP-1..AP-7 anti-patterns
from docs/Phase124_FinalizeChainEpistemicAudit/RESULTS_BASELINE.md.

Read-only. Pure stdlib. Drop into any project with `.sourceprep/`
(embedded mode). XDG mode is a follow-up.

Usage:
    python tools/finalize_chain_audit.py
    python tools/finalize_chain_audit.py --project-dir /path/to/repo
    python tools/finalize_chain_audit.py --json out.json
    python tools/finalize_chain_audit.py --baseline previous.json
    python tools/finalize_chain_audit.py --md scorecard.md

Exit codes:
    0  — harness ran successfully (regardless of scores)
    2  — usage / IO error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

PATH_RE = re.compile(
    r"\b((?:[A-Za-z0-9_./\-]+/)?[A-Za-z0-9_./\-]+\.(?:py|ts|tsx|js|jsx|rs|md))\b"
)

ANTI_PATTERNS = {
    "AP-1": "module has zero linked docs but is referenced by ≥1 .md mention",
    "AP-2": "atlas segment contains zero .md files mentioning its members",
    "AP-3": "doc directory bulk-dropped from segmentation",
    "AP-4": "stale atlas — recent files unsegmented",
    "AP-5a": "concept under-feed (count <30 on a >500-file project — T4 not landing)",
    "AP-5b": "concept over-emit without doc evidence (count >500 with <10% .md anchors — synthesis runaway)",
    "AP-6": "audit/spaghetti.json not produced by pipeline (mtime outside audit-worker window)",
    "AP-7": "antibody count is 0 when constraint-category concepts exist",
}

REQUIRED_AUDIT_MD = (
    "AUDIT_SUMMARY.md",
    "ARCHITECTURE_ANALYSIS.md",
    "COMPONENT_INVENTORY.md",
    "GAP_ANALYSIS.md",
    "TECH_DEBT_REPORT.md",
)


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ProjectPaths:
    project_root: Path
    idx_dir: Path
    project_id: Optional[str] = None
    concepts_db: Optional[Path] = None
    antibodies_db: Optional[Path] = None
    agents_md: Optional[Path] = None


@dataclass
class StageScore:
    stage_id: str          # "11_ATLAS"
    stage_name: str
    score: float           # 0-10
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)  # IDs only
    metrics: dict[str, Any] = field(default_factory=dict)

    def emoji(self) -> str:
        if self.score >= 8.0:
            return "✓"
        if self.score >= 5.0:
            return "~"
        return "✗"


# ──────────────────────────────────────────────────────────────────────
# Path resolution
# ──────────────────────────────────────────────────────────────────────

def resolve_paths(project_dir: Optional[str]) -> ProjectPaths:
    root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    if not (root / ".sourceprep").is_dir():
        raise SystemExit(
            f"error: no .sourceprep/ directory under {root}. "
            "Pass --project-dir explicitly, or run inside an indexed project."
        )
    idx = root / ".sourceprep"
    project_id = None
    proj_json = idx / "project.json"
    if proj_json.is_file():
        try:
            project_id = json.loads(proj_json.read_text()).get("id")
        except Exception:
            pass

    sp_data = Path.home() / ".local" / "share" / "sourceprep"
    concepts_db = sp_data / "prep_concepts.db" if (sp_data / "prep_concepts.db").is_file() else None
    antibodies_db = sp_data / "prep_antibodies.db" if (sp_data / "prep_antibodies.db").is_file() else None
    agents = root / "AGENTS.md" if (root / "AGENTS.md").is_file() else None

    return ProjectPaths(
        project_root=root,
        idx_dir=idx,
        project_id=project_id,
        concepts_db=concepts_db,
        antibodies_db=antibodies_db,
        agents_md=agents,
    )


# ──────────────────────────────────────────────────────────────────────
# Loaders
# ──────────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_md_corpus(root: Path) -> dict[str, set[str]]:
    """For each .md under root/docs, extract candidate file-path mentions."""
    out: dict[str, set[str]] = {}
    docs_root = root / "docs"
    if not docs_root.is_dir():
        return out
    for md in docs_root.rglob("*.md"):
        try:
            text = md.read_text(errors="replace")
        except Exception:
            continue
        rel = str(md.relative_to(root))
        cleaned: set[str] = set()
        for raw in PATH_RE.findall(text):
            r = raw[2:] if raw.startswith("./") else raw
            if "/" not in r and not r.endswith(".md"):
                continue
            if r.startswith(("http", "www.", "//")):
                continue
            cleaned.add(r)
        out[rel] = cleaned
    return out


def query_concepts(db: Optional[Path], project_id: Optional[str]) -> dict:
    """Return {count, status_breakdown, category_breakdown, anchor_pct, questions}."""
    if not db or not project_id:
        return {"available": False}
    try:
        c = sqlite3.connect(str(db))
        rows = c.execute(
            "SELECT category, status, anchors FROM concepts WHERE project_id=?",
            (project_id,),
        ).fetchall()
        questions = c.execute(
            "SELECT COUNT(*) FROM concept_questions WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
        c.close()
    except Exception as e:
        return {"available": False, "error": str(e)}

    cats: dict[str, int] = {}
    statuses: dict[str, int] = {}
    anchored = 0
    for cat, stat, anchors in rows:
        cats[cat or "?"] = cats.get(cat or "?", 0) + 1
        statuses[stat or "?"] = statuses.get(stat or "?", 0) + 1
        if anchors and anchors not in ("[]", "null", ""):
            anchored += 1
    return {
        "available": True,
        "count": len(rows),
        "status_breakdown": statuses,
        "category_breakdown": cats,
        "anchor_pct": (100.0 * anchored / len(rows)) if rows else 0.0,
        "category_diversity": len([k for k, v in cats.items() if v > 0]),
        "questions": questions,
    }


def query_antibodies(db: Optional[Path], project_id: Optional[str]) -> dict:
    if not db or not project_id:
        return {"available": False}
    try:
        c = sqlite3.connect(str(db))
        n = c.execute(
            "SELECT COUNT(*) FROM antibodies WHERE project_id=?",
            (project_id,),
        ).fetchone()[0]
        sevs = c.execute(
            "SELECT severity, COUNT(*) FROM antibodies WHERE project_id=? GROUP BY severity",
            (project_id,),
        ).fetchall()
        c.close()
    except Exception as e:
        return {"available": False, "error": str(e)}
    return {
        "available": True,
        "count": n,
        "severity_breakdown": dict(sevs),
    }


# ──────────────────────────────────────────────────────────────────────
# Stage scorers
# ──────────────────────────────────────────────────────────────────────

def score_atlas(paths: ProjectPaths, mentions: dict[str, set[str]]) -> StageScore:
    s = StageScore(stage_id="11_ATLAS", stage_name="Atlas", score=0.0)
    atlas = load_json(paths.idx_dir / "atlas.json")
    seg_manifest = load_json(paths.idx_dir / "atlas_segments_manifest.json") or []
    routing = load_json(paths.idx_dir / "atlas_routing.json")
    manifest = load_json(paths.idx_dir / "atlas_manifest.json") or {}

    s.metrics["atlas_present"] = atlas is not None
    s.metrics["segment_count"] = len(seg_manifest)
    s.metrics["routing_present"] = routing is not None
    s.metrics["finished_at"] = manifest.get("finished_at")

    if atlas:
        s.score += 2.0
        s.pros.append("atlas.json present")
    else:
        s.cons.append("atlas.json missing")

    if seg_manifest and len(seg_manifest) >= 3:
        s.score += 2.0
        s.pros.append(f"{len(seg_manifest)} atlas segments")
    else:
        s.cons.append("fewer than 3 segments — atlas may not have segmented")

    # Segment file membership accessible (manifest carries file_paths)
    has_files = bool(seg_manifest and isinstance(seg_manifest[0].get("file_paths"), list))
    if has_files:
        s.score += 1.0
        s.pros.append("segments carry file_paths (members enumerable)")
    else:
        s.cons.append("segments_manifest lacks file_paths — downstream tooling can't enumerate members")

    # AP-2: segments with no docs (anywhere in the project) mentioning
    # their members. Phase 124 T3 reframes this from "co-located docs"
    # (the wrong question — docs/ trees naturally live outside their
    # subject's segment) to "any doc in the project mentions this
    # segment's code." Uses the same aggregator the atlas API calls.
    if has_files and mentions:
        try:
            from prep.core.atlas.markdown_links import (
                load as _load_md_links,
                aggregate_for_segments as _agg_segs,
            )
            md_loaded = _load_md_links(paths.idx_dir)
            agg = (
                _agg_segs(md_loaded, seg_manifest, cap=5)
                if md_loaded is not None else {}
            )
        except Exception:
            agg = {}

        empty_segs = [
            (e.get("id") or e.get("segment_id"))
            for e in seg_manifest
            if not agg.get(e.get("id") or e.get("segment_id") or "")
        ]
        total_segs = len(seg_manifest)
        empty_count = len(empty_segs)
        coverage_pct = 100.0 * (total_segs - empty_count) / max(total_segs, 1)
        s.metrics["segments_with_zero_doc_mentions"] = empty_count
        s.metrics["segment_doc_coverage_pct"] = round(coverage_pct, 1)

        if empty_count == 0:
            s.score += 1.0
            s.pros.append(
                "every segment has ≥1 doc referencing its members (T3 aggregator)"
            )
        elif coverage_pct >= 80:
            # Partial credit — strong coverage, AP-2 not flagged
            s.score += 0.5
            s.pros.append(
                f"{total_segs - empty_count}/{total_segs} segments have docs "
                f"({coverage_pct:.0f}% coverage) — minor gap"
            )
        else:
            s.anti_patterns.append("AP-2")
            s.cons.append(
                f"AP-2: {empty_count}/{total_segs} segments have zero docs "
                f"anywhere mentioning their members ({coverage_pct:.0f}% coverage)"
            )

    # AP-3: bulk-dropped doc dirs. Use markdown_links's walker (which
    # respects the same excludes the project applies) so we don't false-
    # positive on node_modules / dist / .venv content nested under docs/.
    in_any = set()
    for e in seg_manifest:
        in_any.update(e.get("file_paths") or [])
    try:
        from prep.core.atlas.markdown_links import _walk_markdown
        all_md_paths = _walk_markdown(paths.project_root)
        all_md = [
            str(p.relative_to(paths.project_root)) for p in all_md_paths
            if str(p.relative_to(paths.project_root)).startswith("docs/")
        ]
    except Exception:
        # Fall back to the naive walk if the import fails (older trees).
        docs_root = paths.project_root / "docs"
        all_md = [
            str(p.relative_to(paths.project_root))
            for p in docs_root.rglob("*.md")
        ] if docs_root.is_dir() else []
    if all_md:
        unsegmented = [m for m in all_md if m not in in_any]
        from collections import Counter
        bulk: Counter = Counter()
        for m in unsegmented:
            parts = m.split("/")
            if len(parts) >= 2:
                bulk[parts[1]] += 1
        bulk_dropped = [(d, c) for d, c in bulk.items() if c > 50]
        s.metrics["unsegmented_md_count"] = len(unsegmented)
        s.metrics["bulk_dropped_dirs"] = bulk_dropped
        if bulk_dropped:
            s.anti_patterns.append("AP-3")
            for d, c in bulk_dropped:
                s.cons.append(f"AP-3: docs/{d}/ — {c} files unsegmented")
        else:
            s.score += 1.0

    # AP-4: stale atlas
    finished = manifest.get("finished_at")
    if finished:
        try:
            t = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - t).total_seconds() / 3600
            s.metrics["atlas_age_hours"] = round(age_h, 1)
            if age_h > 168:  # 1 week
                s.anti_patterns.append("AP-4")
                s.cons.append(f"AP-4: atlas {age_h:.0f} hours old")
            else:
                s.score += 1.0
        except Exception:
            pass

    # H1 reuse: module-doc coverage as a quality bonus
    modules = load_jsonl(paths.idx_dir / "trace_modules.jsonl")
    if modules and mentions:
        from collections import defaultdict
        docs_for_mod: dict[str, set[str]] = defaultdict(set)
        for mod in modules:
            mid = mod.get("module_id") or mod.get("name")
            members = {m for m in (mod.get("member_files") or []) if not m.endswith(".md")}
            if not members:
                continue
            for md_path, ps in mentions.items():
                if ps & members:
                    docs_for_mod[mid].add(md_path)
        code_mods = sum(1 for m in modules if any(not f.endswith(".md") for f in (m.get("member_files") or [])))
        cov = len(docs_for_mod)
        cov_pct = 100.0 * cov / max(code_mods, 1)
        s.metrics["modules_with_relevant_docs_pct"] = round(cov_pct, 1)
        s.metrics["modules_total"] = code_mods
        if cov_pct >= 30:
            s.score += 2.0
            s.pros.append(f"{cov_pct:.0f}% of code modules have ≥1 doc mention")
        else:
            s.cons.append(f"only {cov_pct:.0f}% of code modules have any doc cross-link")

    s.score = min(s.score, 10.0)
    return s


def score_rules(paths: ProjectPaths) -> StageScore:
    s = StageScore(stage_id="12_RULES", stage_name="Rules", score=0.0)
    manifest = load_json(paths.idx_dir / "rules_manifest.json") or {}
    s.metrics["finished_at"] = manifest.get("finished_at")
    s.metrics["elapsed_seconds"] = manifest.get("elapsed_seconds")

    if not paths.agents_md:
        s.cons.append("AGENTS.md missing at project root")
        return s

    text = paths.agents_md.read_text(errors="replace")
    s.metrics["agents_md_lines"] = len(text.splitlines())
    s.metrics["agents_md_chars"] = len(text)

    if paths.agents_md.is_file():
        s.score += 3.0
        s.pros.append(f"AGENTS.md present ({s.metrics['agents_md_lines']} lines)")

    needles = {
        "tool_calling": (("prep(", "prep_search", "prep_impact"), "prep tool-calling instructions"),
        "atlas": (("Atlas", "WORKSPACE MAP", "modules"), "atlas snippet"),
        "concepts": (("Concepts", "concept", "prep_concepts"), "concepts mention"),
        "project_id": (("project_id",), "project_id routing instruction"),
    }
    for key, (terms, label) in needles.items():
        hit = any(t in text for t in terms)
        s.metrics[f"has_{key}"] = hit
        if hit:
            s.score += {"tool_calling": 3.0, "atlas": 2.0, "concepts": 1.0, "project_id": 1.0}[key]
            s.pros.append(f"contains {label}")
        else:
            s.cons.append(f"missing {label}")

    s.score = min(s.score, 10.0)
    return s


def score_concepts(paths: ProjectPaths, project_size: int) -> StageScore:
    s = StageScore(stage_id="13_CONCEPTS", stage_name="Concepts", score=0.0)
    data = query_concepts(paths.concepts_db, paths.project_id)
    manifest = load_json(paths.idx_dir / "concepts_manifest.json") or {}
    s.metrics["finished_at"] = manifest.get("finished_at")
    s.metrics["elapsed_seconds"] = manifest.get("elapsed_seconds")
    s.metrics.update({k: v for k, v in data.items() if k != "available"})

    if not data.get("available"):
        s.cons.append("concepts DB not available — cannot grade")
        return s

    n = data["count"]
    s.metrics["count"] = n
    if n > 0:
        s.score += 2.0
        s.pros.append(f"{n} concepts in store")
    else:
        s.cons.append("zero concepts — concept seeder may not have run")
        return s

    # AP-5: gate by *cause*. Under-feed (T4 not landing) is bad; over-emit
    # with rich .md anchor coverage is the "doc-rich regime" — neutral.
    # Over-emit with poor anchor coverage means synthesis is running away
    # despite weak doc evidence — flag.
    md_anchor_pct = 0.0
    try:
        c = sqlite3.connect(str(paths.concepts_db))
        with_md = c.execute(
            "SELECT COUNT(*) FROM concepts WHERE project_id=? "
            "AND anchors LIKE '%.md%'",
            (paths.project_id,),
        ).fetchone()[0]
        c.close()
        if n > 0:
            md_anchor_pct = 100.0 * with_md / n
    except Exception:
        pass
    s.metrics["md_anchor_pct"] = round(md_anchor_pct, 1)

    if project_size > 500 and n < 30:
        s.anti_patterns.append("AP-5a")
        s.cons.append(
            f"AP-5a: only {n} concepts on a {project_size}-file project — "
            "T4 doc enrichment not landing"
        )
    elif n > 500 and md_anchor_pct < 10:
        s.anti_patterns.append("AP-5b")
        s.cons.append(
            f"AP-5b: {n} concepts but only {md_anchor_pct:.1f}% have .md anchors — "
            "synthesis emitting volume without doc grounding"
        )
    elif 30 <= n <= 80:
        s.score += 3.0
        s.pros.append("concept count in classic 30-80 target band")
    elif n > 80 and md_anchor_pct >= 10:
        s.score += 3.0
        s.pros.append(
            f"doc-rich regime: {n} concepts, {md_anchor_pct:.0f}% .md-anchored"
        )

    # Anchor coverage
    anchor_pct = data["anchor_pct"]
    if anchor_pct >= 50:
        s.score += 2.0
        s.pros.append(f"{anchor_pct:.0f}% of concepts have anchors")
    elif anchor_pct >= 20:
        s.score += 1.0
        s.cons.append(f"only {anchor_pct:.0f}% anchored")
    else:
        s.cons.append(f"only {anchor_pct:.0f}% anchored — concept↔code linkage weak")

    # Category diversity
    div = data["category_diversity"]
    if div >= 6:
        s.score += 2.0
        s.pros.append(f"{div} categories covered")
    elif div >= 3:
        s.score += 1.0
    else:
        s.cons.append(f"only {div} concept categories — diversity low")

    # Questions
    q = data["questions"]
    if q > 0:
        s.score += 1.0
        s.pros.append(f"{q} unanswered concept questions surfaced")

    s.score = min(s.score, 10.0)
    return s


def score_audit(paths: ProjectPaths) -> StageScore:
    s = StageScore(stage_id="14_AUDIT", stage_name="Audit", score=0.0)
    audit_dir = paths.idx_dir / "audit"
    manifest = load_json(paths.idx_dir / "audit_manifest.json") or {}
    s.metrics["finished_at"] = manifest.get("finished_at")
    s.metrics["elapsed_seconds"] = manifest.get("elapsed_seconds")

    if not audit_dir.is_dir():
        s.cons.append("audit/ directory missing")
        return s

    present_md = [m for m in REQUIRED_AUDIT_MD if (audit_dir / m).is_file()]
    s.metrics["markdown_reports_present"] = len(present_md)
    s.metrics["markdown_reports_expected"] = len(REQUIRED_AUDIT_MD)
    if len(present_md) == len(REQUIRED_AUDIT_MD):
        s.score += 3.0
        s.pros.append("all 5 audit markdown reports present")
    elif len(present_md) > 0:
        s.score += 1.0
        s.cons.append(f"{len(REQUIRED_AUDIT_MD) - len(present_md)} markdown reports missing")
    else:
        s.cons.append("no markdown reports written")

    spaghetti = audit_dir / "spaghetti.json"
    s.metrics["spaghetti_present"] = spaghetti.is_file()
    if spaghetti.is_file():
        s.score += 2.0
        s.pros.append("spaghetti.json present")

        # AP-6: provenance check — spaghetti.mtime should fall *inside*
        # the audit_manifest's [started_at, finished_at] window. Manual
        # REST probes drift well outside that window. Phase 124 T5
        # places spaghetti UPSTREAM of the LLM Tier 2 synthesis, so
        # spaghetti is normally earlier than the markdown reports —
        # absolute mtime delta is the wrong test.
        try:
            sp_mtime = spaghetti.stat().st_mtime
            started = manifest.get("started_at")
            finished = manifest.get("finished_at")
            in_window = False
            if started and finished:
                t0 = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
                t1 = datetime.fromisoformat(finished.replace("Z", "+00:00")).timestamp()
                # Allow a small fudge (5 s) for filesystem mtime granularity.
                in_window = (t0 - 5) <= sp_mtime <= (t1 + 5)
                s.metrics["spaghetti_in_audit_window"] = in_window
                s.metrics["spaghetti_offset_from_start_s"] = round(sp_mtime - t0, 1)
            if in_window:
                s.score += 2.0
                s.pros.append("spaghetti.json written inside audit-worker window (pipeline origin)")
            else:
                s.anti_patterns.append("AP-6")
                s.cons.append(
                    "AP-6: spaghetti.json mtime falls outside audit_manifest "
                    "[started_at, finished_at] window — manual REST origin"
                )
        except Exception:
            pass
    else:
        s.anti_patterns.append("AP-6")
        s.cons.append("AP-6: spaghetti.json missing entirely")

    # Markdown report token sprawl (Phase 82 noted this)
    if present_md:
        sizes = [(audit_dir / m).stat().st_size for m in present_md]
        avg_kb = sum(sizes) / len(sizes) / 1024
        s.metrics["avg_md_report_kb"] = round(avg_kb, 1)
        if avg_kb < 12:
            s.score += 1.0
        else:
            s.cons.append(f"average audit report is {avg_kb:.0f} KB — risk of token sprawl")

    s.score = min(s.score, 10.0)
    return s


def score_antibodies(paths: ProjectPaths, concept_data: dict) -> StageScore:
    s = StageScore(stage_id="15_ANTIBODIES", stage_name="Antibodies", score=0.0)
    data = query_antibodies(paths.antibodies_db, paths.project_id)
    manifest = load_json(paths.idx_dir / "antibodies_manifest.json") or {}
    s.metrics["finished_at"] = manifest.get("finished_at")
    s.metrics["elapsed_seconds"] = manifest.get("elapsed_seconds")
    s.metrics.update({k: v for k, v in data.items() if k != "available"})

    if not data.get("available"):
        s.cons.append("antibodies DB not available — cannot grade")
        return s

    n = data["count"]
    s.metrics["count"] = n

    constraint_concepts = (concept_data.get("category_breakdown") or {}).get("constraint", 0)
    arch_concepts = (concept_data.get("category_breakdown") or {}).get("architecture", 0)
    eligible = constraint_concepts + arch_concepts
    s.metrics["eligible_source_concepts"] = eligible

    if n == 0 and eligible > 0:
        s.anti_patterns.append("AP-7")
        s.cons.append(
            f"AP-7: zero antibodies despite {eligible} constraint+architecture concepts available"
        )
        return s

    if n > 0:
        s.score += 4.0
        s.pros.append(f"{n} antibodies derived")

    if eligible > 0:
        ratio = n / eligible
        s.metrics["antibody_to_eligible_ratio"] = round(ratio, 2)
        if ratio >= 0.5:
            s.score += 4.0
            s.pros.append(f"{ratio:.0%} of eligible concepts produced antibodies")
        elif ratio >= 0.2:
            s.score += 2.0
        else:
            s.cons.append(f"only {ratio:.0%} of eligible concepts produced antibodies")

    sevs = data.get("severity_breakdown") or {}
    if len(sevs) >= 2:
        s.score += 1.0
        s.pros.append(f"{len(sevs)} distinct severities")

    elapsed = manifest.get("elapsed_seconds")
    if elapsed is not None and elapsed < 0.1 and n > 0:
        s.cons.append(
            f"derivation reported {elapsed}s for {n} antibodies — "
            "likely served from cache; verify generation actually ran"
        )

    s.score = min(s.score, 10.0)
    return s


# ──────────────────────────────────────────────────────────────────────
# Renderers
# ──────────────────────────────────────────────────────────────────────

def render_text(scores: list[StageScore], paths: ProjectPaths) -> str:
    lines = []
    lines.append("═" * 70)
    lines.append(f"Phase 124 — Finalize Chain Audit  [{paths.project_root.name}]")
    lines.append(f"  idx_dir:    {paths.idx_dir}")
    lines.append(f"  project_id: {paths.project_id or '(unknown)'}")
    lines.append("═" * 70)

    overall = sum(s.score for s in scores) / len(scores)
    lines.append(f"\nOverall: {overall:.1f}/10")
    lines.append("")
    for s in scores:
        head = f"  {s.emoji()}  Stage {s.stage_id:<14}  {s.score:>4.1f}/10"
        lines.append(head)

    lines.append("")
    lines.append("─" * 70)

    for s in scores:
        lines.append("")
        lines.append(f"## Stage {s.stage_id}  ({s.stage_name})    {s.score:.1f}/10  {s.emoji()}")
        if s.pros:
            for p in s.pros:
                lines.append(f"  + {p}")
        if s.cons:
            for c in s.cons:
                lines.append(f"  - {c}")
        if s.anti_patterns:
            ap_summary = ", ".join(f"{ap}: {ANTI_PATTERNS[ap]}" for ap in s.anti_patterns)
            lines.append(f"  ⚠ flagged anti-patterns: {ap_summary}")
        if s.metrics:
            lines.append(f"  metrics: {json.dumps(s.metrics, sort_keys=True)[:300]}")

    lines.append("")
    lines.append("─" * 70)
    all_aps = sorted({ap for s in scores for ap in s.anti_patterns})
    if all_aps:
        lines.append(f"Anti-patterns flagged: {', '.join(all_aps)}")
    else:
        lines.append("Anti-patterns flagged: (none)")
    lines.append("")
    return "\n".join(lines)


def render_json(scores: list[StageScore], paths: ProjectPaths) -> dict:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(paths.project_root),
        "idx_dir": str(paths.idx_dir),
        "project_id": paths.project_id,
        "overall_score": round(sum(s.score for s in scores) / len(scores), 2),
        "stages": [asdict(s) for s in scores],
        "anti_patterns_flagged": sorted({ap for s in scores for ap in s.anti_patterns}),
    }


# Numeric metric keys we want to surface in the diff. Keys not in this
# list are still in the JSON output, just not summarized in stdout.
_METRIC_KEYS_OF_INTEREST = (
    # Atlas
    "segment_count",
    "modules_with_relevant_docs_pct",
    "segment_doc_coverage_pct",
    "unsegmented_md_count",
    "atlas_age_hours",
    # Concepts
    "count",
    "anchor_pct",
    "md_anchor_pct",
    "category_diversity",
    "questions",
    # Audit
    "markdown_reports_present",
    "spaghetti_present",
    "spaghetti_in_audit_window",
    "spaghetti_offset_from_start_s",
    "avg_md_report_kb",
    # Antibodies
    "eligible_source_concepts",
    "antibody_to_eligible_ratio",
)


def _format_metric_delta(key: str, prev_v: Any, cur_v: Any) -> str | None:
    """Format a single metric delta line, or None if the value isn't
    interestingly numeric or didn't change in a quantifiable way."""
    if prev_v is None and cur_v is None:
        return None
    if isinstance(prev_v, bool) or isinstance(cur_v, bool):
        if prev_v != cur_v:
            return f"      {key}: {prev_v} → {cur_v}"
        return None
    if isinstance(prev_v, (int, float)) and isinstance(cur_v, (int, float)):
        if prev_v == cur_v:
            return None
        d = cur_v - prev_v
        sign = "+" if d >= 0 else ""
        marker = "↑" if d > 0 else ("↓" if d < 0 else "·")
        if isinstance(prev_v, float) or isinstance(cur_v, float):
            return f"      {key}: {prev_v:.1f} → {cur_v:.1f} ({sign}{d:.1f}) {marker}"
        return f"      {key}: {prev_v} → {cur_v} ({sign}{d}) {marker}"
    if prev_v != cur_v:
        return f"      {key}: {prev_v!r} → {cur_v!r}"
    return None


def _diff_stage_metrics(prev_stage: dict, cur_stage: dict) -> list[str]:
    """Return a list of metric-delta lines for one stage."""
    prev_m = prev_stage.get("metrics") or {}
    cur_m = cur_stage.get("metrics") or {}
    lines: list[str] = []
    for key in _METRIC_KEYS_OF_INTEREST:
        if key in prev_m or key in cur_m:
            line = _format_metric_delta(key, prev_m.get(key), cur_m.get(key))
            if line:
                lines.append(line)
    return lines


def diff_against_baseline(
    current: dict,
    baseline_path: Path,
    *,
    show_metrics: bool = True,
) -> list[str]:
    if not baseline_path.is_file():
        return [f"baseline not found: {baseline_path}"]
    try:
        prev = json.loads(baseline_path.read_text())
    except Exception as e:
        return [f"baseline unreadable: {e}"]
    out = []
    out.append(f"Δ vs {baseline_path.name}:")
    prev_overall = prev.get("overall_score", 0)
    cur_overall = current["overall_score"]
    delta = cur_overall - prev_overall
    sign = "+" if delta >= 0 else ""
    out.append(f"  overall: {prev_overall:.1f} → {cur_overall:.1f}  ({sign}{delta:.1f})")
    prev_stages = {s["stage_id"]: s for s in prev.get("stages") or []}
    for cs in current["stages"]:
        sid = cs["stage_id"]
        ps = prev_stages.get(sid)
        if ps is None:
            out.append(f"  {sid}: NEW  {cs['score']:.1f}")
            continue
        d = cs["score"] - ps["score"]
        sign = "+" if d >= 0 else ""
        marker = "↑" if d > 0 else ("↓" if d < 0 else "·")
        out.append(f"  {sid}: {ps['score']:.1f} → {cs['score']:.1f}  ({sign}{d:.1f}) {marker}")
        if show_metrics:
            for line in _diff_stage_metrics(ps, cs):
                out.append(line)
    prev_aps = set(prev.get("anti_patterns_flagged") or [])
    cur_aps = set(current["anti_patterns_flagged"])
    cleared = sorted(prev_aps - cur_aps)
    new = sorted(cur_aps - prev_aps)
    if cleared:
        out.append(f"  cleared anti-patterns: {', '.join(cleared)}")
    if new:
        out.append(f"  NEW anti-patterns:     {', '.join(new)}")
    return out


def render_compare(prev: dict, cur: dict, *, show_metrics: bool = True) -> str:
    """Render a side-by-side comparison of two scorecards.

    Used by ``--compare A B`` for ad-hoc comparison without running
    a fresh harness. Inputs are dicts loaded from scorecard JSON.
    """
    lines: list[str] = []
    lines.append("═" * 70)
    lines.append("Phase 124 — scorecard comparison")
    lines.append(f"  prev: generated_at={prev.get('generated_at')}")
    lines.append(f"  cur:  generated_at={cur.get('generated_at')}")
    lines.append("═" * 70)

    overall_delta = cur.get("overall_score", 0) - prev.get("overall_score", 0)
    sign = "+" if overall_delta >= 0 else ""
    lines.append(
        f"\nOverall: {prev.get('overall_score', 0):.1f} → "
        f"{cur.get('overall_score', 0):.1f}  ({sign}{overall_delta:.1f})\n"
    )

    prev_stages = {s["stage_id"]: s for s in prev.get("stages") or []}
    cur_stages = {s["stage_id"]: s for s in cur.get("stages") or []}
    all_ids = sorted(set(prev_stages) | set(cur_stages))

    for sid in all_ids:
        ps = prev_stages.get(sid, {})
        cs = cur_stages.get(sid, {})
        prev_score = ps.get("score", 0.0)
        cur_score = cs.get("score", 0.0)
        d = cur_score - prev_score
        sign = "+" if d >= 0 else ""
        marker = "↑" if d > 0 else ("↓" if d < 0 else "·")
        name = cs.get("stage_name") or ps.get("stage_name") or sid
        lines.append(
            f"  {sid:<14}  {prev_score:>5.1f} → {cur_score:>5.1f}  "
            f"({sign}{d:.1f}) {marker}   {name}"
        )
        prev_aps = set(ps.get("anti_patterns") or [])
        cur_aps = set(cs.get("anti_patterns") or [])
        cleared = sorted(prev_aps - cur_aps)
        new = sorted(cur_aps - prev_aps)
        if cleared:
            lines.append(f"      cleared: {', '.join(cleared)}")
        if new:
            lines.append(f"      NEW:     {', '.join(new)}")
        if show_metrics:
            for line in _diff_stage_metrics(ps, cs):
                lines.append(line)
    return "\n".join(lines)


def render_events_summary(idx_dir: Path) -> str:
    """Phase 124 ``--show-events`` — summarize the latest pipeline run.

    Reads ``pipeline_telemetry.jsonl`` and prints a per-event
    breakdown with key payload fields, so an operator can confirm
    T2/T4/T5/T5b/T9 actually fired and see their effect numerically.
    """
    try:
        from prep.services.pipeline_telemetry import latest_run_events
    except ImportError:
        return "(pipeline_telemetry helper not available — install Phase 124 telemetry)"

    events = latest_run_events(idx_dir, phase="124")
    if not events:
        return (
            "(no Phase 124 telemetry events found — has the pipeline run "
            "since the new code shipped?)"
        )

    lines: list[str] = []
    lines.append("═" * 70)
    lines.append(f"Phase 124 — last-run telemetry  ({len(events)} events)")
    lines.append("═" * 70)

    by_event: dict[str, list[dict]] = {}
    for ev in events:
        by_event.setdefault(ev.get("event", "?"), []).append(ev)

    EXPECTED = (
        "md_links_extracted",  # T2
        "t4_loaded",            # T4 load
        "t4_skipped",           # T4 skipped (negative signal)
        "t4_enrichment_summary",  # T4 fan-out
        "spaghetti_scored",     # T5
        "spaghetti_failed",
        "audit_synth_generator",  # T5b
        "agents_md_docs_section_rendered",  # T9
        "concepts_synthesis_failed",  # negative signal — questions lost (Phase 124 fallback)
        "concept_synthesis_complete",  # Phase 125b Pass 3 — cross-cutting concept synthesis
        "concept_synthesis_failed",    # Phase 125b Pass 3 negative signal
        "concept_synthesis_skipped_fresh",  # Phase 125b — rationale unchanged, no re-synth needed
        "generate_swarm_complete",        # Phase 125c T2c.2 — Generate swarm output
        "generate_swarm_skipped_fresh",   # Phase 125c scrutiny — rationale unchanged short-circuit
        "validate_swarm_complete",        # Phase 125c T3b — Validate swarm verdicts
        "pass4_gate_complete",            # Phase 125 T5 — deterministic gate (now wired in 125c)
    )

    for evname in EXPECTED:
        evs = by_event.get(evname, [])
        if not evs:
            lines.append(f"\n  ✗ {evname}: NOT FIRED")
            continue
        latest = max(evs, key=lambda e: e.get("ts", ""))
        lines.append(f"\n  ✓ {evname}  ({len(evs)} time{'s' if len(evs) != 1 else ''})")
        payload = latest.get("payload") or {}
        # Pretty-print key fields, capped to keep stdout readable
        for k, v in list(payload.items())[:6]:
            if isinstance(v, list) and v and isinstance(v[0], dict):
                lines.append(f"      {k}: {len(v)} items, first: {v[0]}")
            elif isinstance(v, dict):
                lines.append(f"      {k}: {dict(list(v.items())[:5])}")
            elif isinstance(v, str) and len(v) > 80:
                lines.append(f"      {k}: {v[:80]}…")
            else:
                lines.append(f"      {k}: {v}")

    other_events = sorted(set(by_event) - set(EXPECTED))
    if other_events:
        lines.append("\n  Other events:")
        for ev in other_events:
            lines.append(f"    {ev}: {len(by_event[ev])} time(s)")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--project-dir", help="Project root containing .sourceprep/")
    p.add_argument("--baseline", help="Path to a previous JSON output for diff")
    p.add_argument("--json", dest="json_out", help="Write structured output here")
    p.add_argument("--md", dest="md_out", help="Write markdown summary here (Phase 124 RESULTS-style)")
    p.add_argument("--quiet", action="store_true", help="Skip text output")
    p.add_argument(
        "--show-events", action="store_true",
        help="Print Phase 124 telemetry events from the last pipeline run",
    )
    p.add_argument(
        "--no-metric-deltas", action="store_true",
        help="Suppress per-stage metric delta lines in --baseline diff output",
    )
    p.add_argument(
        "--compare", nargs=2, metavar=("PREV", "CUR"),
        help=(
            "Compare two scorecard JSON files side-by-side. Skips running "
            "the harness; just renders the comparison and exits."
        ),
    )
    args = p.parse_args(argv)

    # --compare is a stand-alone mode that doesn't need .sourceprep/.
    if args.compare:
        try:
            prev = json.loads(Path(args.compare[0]).read_text())
            cur = json.loads(Path(args.compare[1]).read_text())
        except Exception as e:
            print(f"error reading compare inputs: {e}", file=sys.stderr)
            return 2
        print(render_compare(prev, cur, show_metrics=not args.no_metric_deltas))
        return 0

    try:
        paths = resolve_paths(args.project_dir)
    except SystemExit:
        raise
    except Exception as e:
        print(f"error resolving paths: {e}", file=sys.stderr)
        return 2

    mentions = load_md_corpus(paths.project_root)

    # Compute project_size for AP-5 gate (count of indexed files via segments)
    seg_manifest = load_json(paths.idx_dir / "atlas_segments_manifest.json") or []
    project_size = sum(len(e.get("file_paths") or []) for e in seg_manifest)

    atlas_score = score_atlas(paths, mentions)
    rules_score = score_rules(paths)
    concepts_data = query_concepts(paths.concepts_db, paths.project_id)
    concepts_score = score_concepts(paths, project_size)
    audit_score = score_audit(paths)
    antibodies_score = score_antibodies(paths, concepts_data)

    scores = [atlas_score, rules_score, concepts_score, audit_score, antibodies_score]

    if not args.quiet:
        print(render_text(scores, paths))

    out = render_json(scores, paths)
    if args.baseline:
        for line in diff_against_baseline(
            out, Path(args.baseline),
            show_metrics=not args.no_metric_deltas,
        ):
            print(line)

    if args.show_events:
        print()
        print(render_events_summary(paths.idx_dir))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2))
        print(f"json written: {args.json_out}")

    if args.md_out:
        md = ["# Finalize Chain Audit Scorecard", ""]
        md.append(f"- Project: `{paths.project_root.name}`")
        md.append(f"- Generated: {out['generated_at']}")
        md.append(f"- Overall: **{out['overall_score']:.1f}/10**")
        md.append("")
        md.append("| Stage | Score | Anti-patterns |")
        md.append("|---|---:|---|")
        for s in scores:
            aps = ", ".join(s.anti_patterns) or "—"
            md.append(f"| {s.stage_id} {s.stage_name} | {s.score:.1f} | {aps} |")
        md.append("")
        for s in scores:
            md.append(f"## {s.stage_id} {s.stage_name} — {s.score:.1f}/10")
            for x in s.pros:
                md.append(f"- ✓ {x}")
            for x in s.cons:
                md.append(f"- ✗ {x}")
            if s.metrics:
                md.append("```json")
                md.append(json.dumps(s.metrics, indent=2, sort_keys=True))
                md.append("```")
            md.append("")
        Path(args.md_out).write_text("\n".join(md))
        print(f"md written: {args.md_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

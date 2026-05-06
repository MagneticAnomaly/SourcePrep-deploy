#!/usr/bin/env python3
"""Phase 125 T3 — score a hand-labeled calibration worksheet.

Reads the markdown produced by ``build_calibration_worksheet.py``,
parses the user-checked tier + truth labels per concept, and reports
distribution + ordinal ECE (Naeini et al. 2015 adjacent-accuracy
variant) against the LLM's current continuous confidence.

ECE here measures **the gap between the LLM's stated confidence
and human-judged truth.** A well-calibrated model emits 0.92 for
concepts that are TRUE 92% of the time. A miscalibrated model
emits 0.92 for concepts that are TRUE 60% of the time → high ECE.

The current Phase 124 LLM prompt asks for a 0.0-1.0 confidence
float and produces 0.7-0.95 clustering. After T3's tier-based
prompt lands, we re-score and expect ECE to drop substantially.

Usage:
    .venv/bin/python tools/score_calibration_worksheet.py \\
        --worksheet docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md
    .venv/bin/python tools/score_calibration_worksheet.py \\
        --worksheet ... --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Tier → mapped float (from T3_RESEARCH.md). Used for ECE expected
# accuracy in the post-T3 measurement; not used pre-T3.
TIER_TO_FLOAT = {"T1": 0.30, "T2": 0.65, "T3": 0.92}

# Truth labels mapped to a "fraction true" for ECE.
TRUTH_TO_FRAC = {"TRUE": 1.0, "PARTIAL": 0.5, "FALSE": 0.0}

CHECKBOX_RE = re.compile(r"^\s*-\s*\[\s*([xX ])\s*\]\s+(.*?)\s*$", re.MULTILINE)
ID_RE = re.compile(r"\*\*ID:\*\*\s*`([^`]+)`")
CATEGORY_RE = re.compile(r"\*\*Category:\*\*\s*`([^`]+)`")
CONFIDENCE_RE = re.compile(r"\*\*LLM confidence \(current, suspect\):\*\*\s*([0-9.]+)")
NOTES_RE = re.compile(r"\*\*Notes:\*\*\s*(.+)$", re.MULTILINE)
SECTION_RE = re.compile(
    r"### Concept #(\d+) — (.+?)\n(.*?)(?=^### Concept #|\Z)",
    re.DOTALL | re.MULTILINE,
)


@dataclass
class LabeledConcept:
    idx: int
    id: str
    title: str
    category: str
    llm_confidence: float
    tier: Optional[str] = None        # "T1" | "T2" | "T3" | None (unfilled)
    truth: Optional[str] = None       # "TRUE" | "PARTIAL" | "FALSE" | None
    notes: str = ""
    parse_warnings: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────

def _checked_label(text: str, candidates: tuple[str, ...]) -> tuple[Optional[str], list[str]]:
    """Find which of the candidate labels is checked. Returns (label, warnings)."""
    found: list[str] = []
    warnings: list[str] = []
    for match in CHECKBOX_RE.finditer(text):
        checked = match.group(1) in ("x", "X")
        label_text = match.group(2)
        for cand in candidates:
            if label_text.startswith(cand):
                if checked:
                    found.append(cand)
                break
    if len(found) > 1:
        warnings.append(f"multiple {candidates[0][:1]}-candidates checked: {found}")
        return found[0], warnings
    if not found:
        return None, warnings
    return found[0], warnings


def parse_worksheet(md_path: Path) -> list[LabeledConcept]:
    text = md_path.read_text()

    out: list[LabeledConcept] = []
    for match in SECTION_RE.finditer(text):
        idx = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3)

        cid_m = ID_RE.search(body)
        cat_m = CATEGORY_RE.search(body)
        conf_m = CONFIDENCE_RE.search(body)
        notes_m = NOTES_RE.search(body)

        cid = cid_m.group(1) if cid_m else f"_unknown_{idx}"
        cat = cat_m.group(1) if cat_m else "?"
        try:
            conf = float(conf_m.group(1)) if conf_m else 0.0
        except Exception:
            conf = 0.0

        tier, tier_warnings = _checked_label(body, ("T1", "T2", "T3"))
        truth, truth_warnings = _checked_label(body, ("TRUE", "PARTIAL", "FALSE"))

        notes_text = ""
        if notes_m:
            raw = notes_m.group(1).strip()
            if raw and not raw.startswith("___"):
                notes_text = raw

        lc = LabeledConcept(
            idx=idx,
            id=cid,
            title=title,
            category=cat,
            llm_confidence=conf,
            tier=tier,
            truth=truth,
            notes=notes_text,
            parse_warnings=tier_warnings + truth_warnings,
        )
        out.append(lc)
    return out


# ──────────────────────────────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CalibrationReport:
    total: int = 0
    fully_labeled: int = 0
    missing_tier: int = 0
    missing_truth: int = 0
    multi_checked: int = 0
    tier_distribution: dict[str, int] = field(default_factory=dict)
    truth_distribution: dict[str, int] = field(default_factory=dict)
    per_tier_truth: dict[str, dict[str, int]] = field(default_factory=dict)
    per_tier_truth_fraction_true: dict[str, float] = field(default_factory=dict)
    per_category_distribution: dict[str, dict[str, int]] = field(default_factory=dict)
    ece_against_llm_confidence: float = 0.0
    review_flags: list[dict] = field(default_factory=list)


def compute_ece_continuous(labeled: list[LabeledConcept], n_buckets: int = 5) -> float:
    """ECE between LLM's continuous confidence and observed truth.

    Uses Naeini et al. 2015 binned calibration error: bucket
    predictions by confidence, compute |avg predicted - observed
    fraction TRUE| per bucket, weight by bucket size.
    """
    fully = [c for c in labeled if c.truth is not None]
    if not fully:
        return float("nan")
    bucket_edges = [i / n_buckets for i in range(n_buckets + 1)]
    bucket_edges[-1] = 1.01  # include 1.0
    n = len(fully)
    ece = 0.0
    for i in range(n_buckets):
        lo, hi = bucket_edges[i], bucket_edges[i + 1]
        in_bucket = [c for c in fully if lo <= c.llm_confidence < hi]
        if not in_bucket:
            continue
        avg_conf = sum(c.llm_confidence for c in in_bucket) / len(in_bucket)
        obs_frac = sum(TRUTH_TO_FRAC[c.truth] for c in in_bucket) / len(in_bucket)
        ece += (len(in_bucket) / n) * abs(avg_conf - obs_frac)
    return ece


def score(labeled: list[LabeledConcept]) -> CalibrationReport:
    r = CalibrationReport(total=len(labeled))

    tier_d: Counter = Counter()
    truth_d: Counter = Counter()
    per_tier_truth: dict[str, Counter] = defaultdict(Counter)
    per_cat: dict[str, Counter] = defaultdict(Counter)

    for c in labeled:
        if c.tier is None:
            r.missing_tier += 1
        else:
            tier_d[c.tier] += 1
        if c.truth is None:
            r.missing_truth += 1
        else:
            truth_d[c.truth] += 1
        if c.tier and c.truth:
            per_tier_truth[c.tier][c.truth] += 1
            per_cat[c.category][c.tier] += 1
        if c.tier and c.truth:
            r.fully_labeled += 1
        if any("multiple" in w for w in c.parse_warnings):
            r.multi_checked += 1

        if c.parse_warnings or (c.tier is None and c.truth is None):
            r.review_flags.append({
                "idx": c.idx,
                "id": c.id,
                "title": c.title[:60],
                "tier": c.tier,
                "truth": c.truth,
                "warnings": c.parse_warnings,
                "notes": c.notes[:80] if c.notes else "",
            })

    r.tier_distribution = dict(tier_d)
    r.truth_distribution = dict(truth_d)
    r.per_tier_truth = {
        tier: dict(cnt) for tier, cnt in per_tier_truth.items()
    }
    for tier, cnt in per_tier_truth.items():
        total = sum(cnt.values())
        if total:
            frac = (cnt.get("TRUE", 0) + 0.5 * cnt.get("PARTIAL", 0)) / total
            r.per_tier_truth_fraction_true[tier] = round(frac, 3)
    r.per_category_distribution = {
        cat: dict(cnt) for cat, cnt in per_cat.items()
    }
    r.ece_against_llm_confidence = compute_ece_continuous(labeled)

    return r


# ──────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────

def render_text(r: CalibrationReport, labeled: list[LabeledConcept]) -> str:
    lines: list[str] = []
    lines.append("═" * 68)
    lines.append("Phase 125 T3 — Calibration worksheet score report")
    lines.append("═" * 68)
    lines.append(f"\nLabel completeness: {r.fully_labeled}/{r.total} fully labeled")
    if r.missing_tier:
        lines.append(f"  ⚠ {r.missing_tier} missing tier")
    if r.missing_truth:
        lines.append(f"  ⚠ {r.missing_truth} missing truth")
    if r.multi_checked:
        lines.append(f"  ⚠ {r.multi_checked} have multiple checkboxes ticked")

    lines.append("\nTier distribution:")
    for t in ("T1", "T2", "T3"):
        n = r.tier_distribution.get(t, 0)
        bar = "#" * n
        lines.append(f"  {t}: {n:>3}  {bar}")

    lines.append("\nTruth distribution:")
    for t in ("TRUE", "PARTIAL", "FALSE"):
        n = r.truth_distribution.get(t, 0)
        bar = "#" * n
        lines.append(f"  {t:<8}: {n:>3}  {bar}")

    if r.per_tier_truth_fraction_true:
        lines.append("\nPer-tier truth (TRUE + 0.5×PARTIAL fraction):")
        lines.append("  Expected: T1 ~0.30, T2 ~0.65-0.75, T3 ~0.95")
        for t in ("T1", "T2", "T3"):
            if t in r.per_tier_truth_fraction_true:
                cnt = r.per_tier_truth.get(t, {})
                frac = r.per_tier_truth_fraction_true[t]
                tot = sum(cnt.values())
                marker = "✓" if (
                    (t == "T1" and frac < 0.50)
                    or (t == "T2" and 0.50 <= frac <= 0.85)
                    or (t == "T3" and frac > 0.85)
                ) else "⚠"
                lines.append(
                    f"  {t}: {frac:.2f}  ({tot} concepts)  {marker}"
                )

    lines.append(f"\nECE against LLM-stated confidence: {r.ece_against_llm_confidence:.3f}")
    lines.append("  Realistic first-attempt: 0.15-0.25")
    lines.append("  <0.10 good · <0.05 suspicious (overfit)")
    if r.ece_against_llm_confidence > 0.20:
        lines.append("  → high ECE expected for the current Phase-124 float prompt;")
        lines.append("    re-score after T3 lands to measure improvement")

    if r.per_category_distribution:
        lines.append("\nPer-category tier distribution:")
        for cat, cnt in sorted(
            r.per_category_distribution.items(),
            key=lambda kv: -sum(kv[1].values()),
        ):
            row = " ".join(f"{t}={cnt.get(t, 0)}" for t in ("T1", "T2", "T3"))
            lines.append(f"  {cat:<14}: {row}")

    if r.review_flags:
        lines.append(f"\n{len(r.review_flags)} concept(s) flagged for review:")
        for f in r.review_flags[:15]:
            warn = "; ".join(f["warnings"]) if f["warnings"] else ""
            tier_truth = f"tier={f['tier'] or '—'}, truth={f['truth'] or '—'}"
            lines.append(f"  #{f['idx']:>2}  {tier_truth:<28}  {warn}")
        if len(r.review_flags) > 15:
            lines.append(f"  … and {len(r.review_flags) - 15} more")

    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--worksheet", required=True,
        help="Path to the filled CALIBRATION_WORKSHEET.md",
    )
    p.add_argument(
        "--json", dest="json_out",
        help="(Optional) write structured report here",
    )
    args = p.parse_args(argv)

    md = Path(args.worksheet).expanduser()
    if not md.is_file():
        print(f"error: worksheet not found at {md}", file=sys.stderr)
        return 2

    labeled = parse_worksheet(md)
    if not labeled:
        print("error: no concept sections detected in worksheet", file=sys.stderr)
        return 2

    report = score(labeled)
    print(render_text(report, labeled))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(asdict(report), indent=2))
        print(f"\njson report written: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

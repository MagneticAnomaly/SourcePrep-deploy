#!/usr/bin/env python3
"""Phase 125 T3 — build a hand-labeled calibration worksheet.

Samples 50 concepts from the live concept store, stratified across
confidence buckets and categories, and renders a markdown worksheet
the user can fill in offline. The companion script
``score_calibration_worksheet.py`` reads the filled worksheet and
computes per-tier accuracy, ordinal ECE, and tier distribution.

Sampling strategy (per T3_RESEARCH.md):
- 10 from confidence ≥0.95   (highest LLM-prior; tests over-rating)
- 15 from 0.85-0.95           (high LLM-prior; mostly should be T2)
- 15 from 0.75-0.85           (medium; mix of T1/T2)
-  8 from 0.65-0.75           (low-medium; likely T1)
-  2 from <0.65               (very low; should be T1 / auto-archive)

Within each bucket we further stratify by category so the labeler
sees diversity across architecture / technical / product / etc.

Usage:
    python tools/build_calibration_worksheet.py \\
        --project f1636374-abc6-410d-99ee-822120379e79 \\
        --out docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md

The output is a single markdown file. Fill in the checkboxes
offline; the scorer reads the same file path.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

WORKSHEET_HEADER = """# Phase 125 — Concept Calibration Worksheet

> **Purpose:** ground truth for the T3 prompt design (see
> `T3_RESEARCH.md`). Hand-label these 50 concepts so we can
> measure ordinal ECE and tier distribution after the new tier-based
> prompt lands. Without this, we're flying blind on calibration.
> **Estimated time:** ~2 hours of focused work (~2 minutes per concept).
> **What to fill:** for each concept, mark ONE of the three tier
> checkboxes AND ONE of the three truth checkboxes. Add optional
> notes if the concept is ambiguous.

## The 3-tier rubric (memorize this — the scorer checks against it)

```
T1 — pattern observed in code; no enforcement.
     Test: a reader could find counter-examples in the same codebase
     that don't follow the pattern, and nothing prevents them.
     Anchor example: "Database access uses connection pools" —
     observed in 3 modules but two other modules use raw connections;
     no test, lint, or type check enforces pooling.

T2 — documented decision with at least one enforcing mechanism (test,
     lint rule, docstring referenced as a contract, ADR with named anchor).
     Test: a developer who violated this pattern would either (a) get
     a test failure, OR (b) be flagged by a linter, OR (c) be pointed
     at a written decision document by a reviewer.
     Anchor example: "API responses use envelope format" —
     enforced by test_api_envelope.py and documented in API.md.

T3 — codified in CI/types/constraint-concept; violations fail the build.
     Test: a developer who violated this pattern CANNOT merge —
     PR-time mypy strict / build / tests will block it.
     Anchor example: "All API responses must be Pydantic BaseModels" —
     mypy strict catches non-BaseModel returns, test_api_schema.py
     validates structure at every PR.
```

## Truth label

Independent of tier — is the concept accurate?

- **TRUE** — accurate description of the codebase (regardless of tier).
- **PARTIAL** — partially accurate but mis-states scope or evidence.
- **FALSE** — concept is wrong or generic boilerplate.

## How to fill

For each concept below, fill in:

- **One tier checkbox** (T1/T2/T3) — your judgment of how well-enforced this concept is.
- **One truth checkbox** (TRUE/PARTIAL/FALSE) — your judgment of whether the concept is accurate.
- **(Optional) Notes** — flag concepts that are ambiguous, near a tier boundary, or whose anchor is wrong/missing.

If you can't decide, mark **PARTIAL** + nearest tier and explain in notes.

## Sampling stratification

This sample is intentionally **not** a random draw. We over-sample
the high-confidence buckets and under-sample the low-confidence
ones because the prompt change is most likely to move concepts
DOWN the tier scale, and we need labels in the upper bands to
detect over-confidence.

"""

WORKSHEET_FOOTER = """

---

## What to do after filling

Save the file. Run:

```bash
.venv/bin/python tools/score_calibration_worksheet.py \\
    --worksheet docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md
```

The scorer reports:
- Tier distribution (your labels)
- Ordinal ECE (against current LLM confidence — should be high)
- Per-category breakdown
- A flagged-for-review list for ambiguous entries

Once T3 runs, we re-score the same worksheet against T3's tier outputs
and compare ECE pre/post.
"""


def stratified_sample(
    db_path: Path,
    project_id: str,
    *,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Return 50 concepts stratified by confidence × category.

    Strategy (see module docstring): 10/15/15/8/2 across confidence
    buckets, balanced within each bucket across categories.
    """
    rng = random.Random(seed)
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT id, title, content, category, confidence, anchors "
        "FROM concepts WHERE project_id=? AND status='seed'",
        (project_id,),
    ).fetchall()
    conn.close()

    pool: list[dict] = []
    for cid, title, content, category, confidence, anchors_json in rows:
        try:
            anchors = json.loads(anchors_json) if anchors_json else []
        except Exception:
            anchors = []
        pool.append({
            "id": cid,
            "title": title or "(untitled)",
            "content": content or "",
            "category": category or "?",
            "confidence": float(confidence) if confidence is not None else 0.0,
            "anchors": anchors if isinstance(anchors, list) else [],
        })

    # Bucket by confidence
    buckets = {
        "≥0.95":     [c for c in pool if c["confidence"] >= 0.95],
        "0.85-0.95": [c for c in pool if 0.85 <= c["confidence"] < 0.95],
        "0.75-0.85": [c for c in pool if 0.75 <= c["confidence"] < 0.85],
        "0.65-0.75": [c for c in pool if 0.65 <= c["confidence"] < 0.75],
        "<0.65":     [c for c in pool if c["confidence"] < 0.65],
    }
    targets = {
        "≥0.95":     10,
        "0.85-0.95": 15,
        "0.75-0.85": 15,
        "0.65-0.75":  8,
        "<0.65":      2,
    }

    sampled: list[dict] = []
    for bucket, target in targets.items():
        bucket_pool = buckets[bucket]
        if len(bucket_pool) <= target:
            sampled.extend(bucket_pool)
            continue
        # Stratify by category within the bucket
        by_cat: dict[str, list] = defaultdict(list)
        for c in bucket_pool:
            by_cat[c["category"]].append(c)
        # Round-robin pick across categories
        for c_list in by_cat.values():
            rng.shuffle(c_list)
        picked: list[dict] = []
        cats = list(by_cat.keys())
        rng.shuffle(cats)
        idx = 0
        while len(picked) < target and any(by_cat[c] for c in cats):
            cat = cats[idx % len(cats)]
            if by_cat[cat]:
                picked.append(by_cat[cat].pop())
            idx += 1
        sampled.extend(picked[:target])

    # Stable sort by bucket then category for the worksheet
    bucket_rank = {k: i for i, k in enumerate(buckets.keys())}

    def _bucket_for(c):
        cf = c["confidence"]
        if cf >= 0.95:
            return "≥0.95"
        if cf >= 0.85:
            return "0.85-0.95"
        if cf >= 0.75:
            return "0.75-0.85"
        if cf >= 0.65:
            return "0.65-0.75"
        return "<0.65"

    sampled.sort(key=lambda c: (bucket_rank[_bucket_for(c)], c["category"], c["id"]))
    return sampled


def render_concept(idx: int, c: dict[str, Any]) -> str:
    """Render one concept as a worksheet section."""
    cid = c["id"]
    title = c["title"]
    content = c["content"]
    category = c["category"]
    confidence = c["confidence"]
    anchors = c["anchors"]
    anchors_str = "\n".join(f"  - `{a}`" for a in anchors[:6])
    if len(anchors) > 6:
        anchors_str += f"\n  - … and {len(anchors) - 6} more"
    if not anchors_str:
        anchors_str = "  - (none)"

    return f"""### Concept #{idx} — {title[:80]}

- **ID:** `{cid}`
- **Category:** `{category}`
- **LLM confidence (current, suspect):** {confidence:.2f}
- **Title:** {title}
- **Content:** {content}
- **Anchors:**
{anchors_str}

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---
"""


def render_worksheet(concepts: list[dict[str, Any]]) -> str:
    parts = [WORKSHEET_HEADER]

    # Stratification summary
    bucket_counts: dict[str, int] = defaultdict(int)
    cat_counts: dict[str, int] = defaultdict(int)
    for c in concepts:
        cf = c["confidence"]
        if cf >= 0.95:
            bucket_counts["≥0.95"] += 1
        elif cf >= 0.85:
            bucket_counts["0.85-0.95"] += 1
        elif cf >= 0.75:
            bucket_counts["0.75-0.85"] += 1
        elif cf >= 0.65:
            bucket_counts["0.65-0.75"] += 1
        else:
            bucket_counts["<0.65"] += 1
        cat_counts[c["category"]] += 1

    parts.append("Confidence bucket distribution in this sample:\n")
    for k in ("≥0.95", "0.85-0.95", "0.75-0.85", "0.65-0.75", "<0.65"):
        parts.append(f"- `{k}`: {bucket_counts.get(k, 0)}")
    parts.append("\nCategory distribution in this sample:\n")
    for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        parts.append(f"- `{cat}`: {n}")
    parts.append("\n---\n\n## Concepts to label\n")

    for i, c in enumerate(concepts, start=1):
        parts.append(render_concept(i, c))

    parts.append(WORKSHEET_FOOTER)
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--project", required=True,
        help="Project ID to sample concepts from",
    )
    p.add_argument(
        "--db",
        default=str(Path.home() / ".local/share/sourceprep/prep_concepts.db"),
        help="Path to prep_concepts.db (default: standard XDG location)",
    )
    p.add_argument(
        "--out", required=True,
        help="Output markdown path (will be overwritten)",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed for reproducibility",
    )
    args = p.parse_args(argv)

    db = Path(args.db).expanduser()
    if not db.is_file():
        print(f"error: concept DB not found at {db}", file=sys.stderr)
        return 2

    sample = stratified_sample(db, args.project, seed=args.seed)
    out = render_worksheet(sample)
    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out)
    print(f"wrote {out_path}")
    print(f"  sampled {len(sample)} concepts across "
          f"{len(set(c['category'] for c in sample))} categories")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

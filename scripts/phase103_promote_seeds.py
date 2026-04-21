#!/usr/bin/env python
"""
Phase 103 R5 — seed → active concept promotion utility.

Reads prep_concepts.db, applies promotion criteria, flips matching
seeds to `active` status. Idempotent; running twice is a no-op.

Promotion criteria (post-R5 audit):
  1. category is set
  2. anchors is non-empty JSON list
  3. confidence >= MIN_CONFIDENCE (default 0.85)
  4. assertion is derivable — currently uses title as a synthetic
     assertion when the assertion column is empty. This is a POC
     shortcut; later phases replace with real assertion generation.
  5. project_id matches (so cross-project seeds don't get
     unintentionally promoted in batch)

Usage:
    python scripts/phase103_promote_seeds.py --db path/to/concepts.db \
        --project-id 1d6f0b35-... --category constraint --limit 10 \
        [--dry-run]

Always prints the list of concepts it plans to promote (or promoted)
and exits non-zero if fewer than --limit candidates existed.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Tuple


def find_candidates(
    db_path: Path,
    project_id: str,
    category: str,
    min_confidence: float,
    limit: int,
) -> List[Tuple[str, str, str, float, str]]:
    """Return (id, title, anchors_json, confidence, tags_json) for up to
    `limit` seeds that meet promotion criteria."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT id, title, anchors, confidence, tags
        FROM concepts
        WHERE status = 'seed'
          AND project_id = ?
          AND category = ?
          AND confidence >= ?
          AND anchors IS NOT NULL AND anchors != '' AND anchors != '[]'
        ORDER BY confidence DESC, title ASC
        LIMIT ?
        """,
        (project_id, category, min_confidence, limit),
    ).fetchall()
    conn.close()
    return rows


def promote(
    db_path: Path,
    concept_ids: List[str],
    dry_run: bool,
) -> int:
    """Flip status=seed → status=active for the given IDs. Sets valid_from
    + updated_at. If concept has no assertion, copies title into it as a
    POC-level synthetic assertion."""
    now = time.time()
    conn = sqlite3.connect(db_path)
    count = 0
    for cid in concept_ids:
        row = conn.execute(
            "SELECT assertion, title FROM concepts WHERE id = ? AND status = 'seed'",
            (cid,),
        ).fetchone()
        if row is None:
            continue
        assertion, title = row
        new_assertion = assertion if (assertion and assertion.strip()) else f"{title} (synthetic POC assertion; replace with human-written)"
        if not dry_run:
            conn.execute(
                """
                UPDATE concepts
                SET status = 'active',
                    assertion = ?,
                    valid_from = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'seed'
                """,
                (new_assertion, now, now, cid),
            )
        count += 1
    if not dry_run:
        conn.commit()
    conn.close()
    return count


def main() -> None:
    p = argparse.ArgumentParser(description="Phase 103 R5 seed promotion utility")
    p.add_argument("--db", type=Path, required=True, help="Path to prep_concepts.db")
    p.add_argument("--project-id", required=True, help="Project UUID to filter seeds")
    p.add_argument("--category", default="constraint", help="Category to promote (default: constraint — best for antibodies)")
    p.add_argument("--min-confidence", type=float, default=0.85)
    p.add_argument("--limit", type=int, default=10, help="Max concepts to promote")
    p.add_argument("--dry-run", action="store_true", help="Only print candidates, do not write")
    args = p.parse_args()

    if not args.db.exists():
        print(f"Error: DB not found: {args.db}", file=sys.stderr)
        sys.exit(2)

    cands = find_candidates(
        args.db, args.project_id, args.category, args.min_confidence, args.limit,
    )

    print(
        f"Promotion plan ({'DRY RUN' if args.dry_run else 'LIVE'}): "
        f"{len(cands)} concept(s) in category='{args.category}' "
        f"(confidence >= {args.min_confidence})"
    )
    for i, (cid, title, anchors, conf, tags) in enumerate(cands, 1):
        try:
            anchor_list = json.loads(anchors)
        except Exception:
            anchor_list = [anchors]
        print(f"  {i:2d}. [{cid}] conf={conf:.2f}  {title}")
        print(f"       anchors: {anchor_list[:3]}")

    ids = [r[0] for r in cands]
    promoted = promote(args.db, ids, args.dry_run)
    action = "Would promote" if args.dry_run else "Promoted"
    print(f"\n{action} {promoted} concept(s) to status=active.")

    if promoted < args.limit:
        print(
            f"WARNING: asked for {args.limit}, only {promoted} matched criteria. "
            "Consider lowering --min-confidence or widening --category.",
            file=sys.stderr,
        )
        sys.exit(1 if not args.dry_run else 0)


if __name__ == "__main__":
    main()

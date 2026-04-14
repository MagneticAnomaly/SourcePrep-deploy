#!/usr/bin/env python
"""
Phase 103 R6 — temporal-validity schema migration for the concept store.

Adds two columns to the `concepts` table:
  - reviewed_at     REAL    (unix timestamp of last human review; null = never)
  - review_status   TEXT    ('current' | 'needs_review' | 'stale' | 'retired')

The pre-existing columns `valid_from`, `valid_to`, `superseded_by`, `stale`,
`stale_reason` already cover most of the R6 design's temporal model. These
two additions complete the four-state lifecycle (current / needs_review /
stale / retired) that R6 specifies and give us an explicit human-review
timestamp independent of valid_from (which tracks "when first promoted").

Idempotent: runs PRAGMA table_info first and only issues ALTER TABLE ADD
COLUMN for columns that don't exist.

Backfill policy:
  - All rows get `review_status = 'current'` by default.
  - `reviewed_at` is set to `valid_from` when status='active' (we treat
    promotion as implicit first review), otherwise left NULL.

Usage:
    python scripts/phase103_temporal_schema.py --db path/to/concepts.db \
        [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import List, Set


R6_NEW_COLUMNS = {
    "reviewed_at": "REAL",
    "review_status": "TEXT",
}


def existing_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate(db_path: Path, dry_run: bool) -> int:
    if not db_path.exists():
        print(f"Error: DB not found: {db_path}", file=sys.stderr)
        sys.exit(2)
    conn = sqlite3.connect(db_path)
    present = existing_columns(conn, "concepts")
    to_add = {c: t for c, t in R6_NEW_COLUMNS.items() if c not in present}

    if not to_add:
        print("All R6 columns already present. Nothing to add.")
    else:
        for col, coltype in to_add.items():
            stmt = f"ALTER TABLE concepts ADD COLUMN {col} {coltype}"
            print(f"  {'[dry-run] ' if dry_run else ''}{stmt}")
            if not dry_run:
                conn.execute(stmt)

    # Backfill review_status
    total = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    unbacked = conn.execute(
        "SELECT COUNT(*) FROM concepts WHERE review_status IS NULL"
    ).fetchone()[0] if "review_status" in present or not dry_run else total

    if not dry_run:
        conn.execute(
            "UPDATE concepts SET review_status = 'current' WHERE review_status IS NULL"
        )
        # For active concepts, treat activation as implicit first review
        conn.execute(
            """
            UPDATE concepts
            SET reviewed_at = valid_from
            WHERE status = 'active'
              AND reviewed_at IS NULL
              AND valid_from IS NOT NULL
            """
        )
        conn.commit()
        print(f"Backfilled review_status='current' on rows with NULL.")
        print(f"Set reviewed_at=valid_from for active concepts with null reviewed_at.")
    else:
        print(f"[dry-run] Would backfill review_status on ~{unbacked} rows.")

    # Summary
    if not dry_run:
        active = conn.execute(
            "SELECT COUNT(*) FROM concepts WHERE status='active'"
        ).fetchone()[0]
        reviewed = conn.execute(
            "SELECT COUNT(*) FROM concepts WHERE reviewed_at IS NOT NULL"
        ).fetchone()[0]
        by_status = dict(conn.execute(
            "SELECT review_status, COUNT(*) FROM concepts GROUP BY review_status"
        ).fetchall())
        print()
        print(f"Final state:")
        print(f"  total:            {total}")
        print(f"  active concepts:  {active}")
        print(f"  reviewed_at set:  {reviewed}")
        print(f"  review_status:    {by_status}")

    conn.close()
    return len(to_add)


def main() -> None:
    p = argparse.ArgumentParser(description="Phase 103 R6 temporal-validity schema migration")
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    migrate(args.db, args.dry_run)


if __name__ == "__main__":
    main()

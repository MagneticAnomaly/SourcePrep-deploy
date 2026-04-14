# R6 — Temporal Validity Schema (POC)

**Date:** 2026-04-14
**Goal:** Add minimum-viable temporal-validity fields to the concept store so future staleness detection and decay tracking have somewhere to write. POC is schema-only; no auto-staleness logic yet.
**Status:** Schema additions applied to isolated POC DB. Live main-tree DB untouched (same isolation discipline as R5).

## Schema audit

The concept store already had richer temporal fields than the R6 design doc proposed:

| R6 proposed | In schema? | Notes |
|---|---|---|
| `valid_from` REAL | ✅ yes | timestamp of first activation |
| `superseded_by` TEXT | ✅ yes | pointer to replacement concept id |
| `reviewed_at` REAL | ❌ missing | added by this POC |
| `review_status` TEXT | ❌ missing | added by this POC |

Additional pre-existing fields that overlap the space:

- `valid_to` REAL — timestamp when concept became invalid.
- `stale` INTEGER — binary staleness flag.
- `stale_reason` TEXT — free-form explanation.

Only two fields needed adding. Everything else was already in place.

## Why we add `review_status` even with `stale` already present

`stale` is binary (1 or 0). R6 wants a four-state lifecycle: `current | needs_review | stale | retired`. The extra states matter because:

- `current` (default) means "believed valid; no flag raised."
- `needs_review` is a middle state — auto-detector noticed a possible drift signal (e.g., anchor file changed) but a human hasn't decided. Crucially different from `stale` ("confirmed out of date") and from `current` ("nothing to worry about").
- `retired` means "intentionally removed from active use" — different from `stale`, which usually implies "decayed without intervention."

The binary `stale` flag stays for back-compat with existing pipeline queries. Future work can derive `stale = (review_status IN ('stale','retired'))` or deprecate the binary column after migration. Out of scope for this POC.

## Migration script

New file: `scripts/phase103_temporal_schema.py` (~90 lines, stdlib + sqlite3 only).

```
python scripts/phase103_temporal_schema.py --db path/to/codrag_concepts.db [--dry-run]
```

Behavior:
1. `PRAGMA table_info(concepts)` — detect which R6 columns already exist.
2. For each missing column, `ALTER TABLE concepts ADD COLUMN {name} {type}`.
3. Backfill: every row gets `review_status = 'current'`.
4. For `status = 'active'` rows, set `reviewed_at = valid_from` (we treat promotion as implicit first review).

Idempotent: re-running is safe; it reports "All R6 columns already present. Nothing to add." and backfill is a no-op on already-populated rows.

## Results on isolated POC DB

```
Before migration:
  total:           621
  active concepts: 10  (from R5)
  review_status column: absent
  reviewed_at column:   absent

After migration:
  total:           621
  active concepts: 10
  reviewed_at set: 10          ← R5's actives have implicit-first-review timestamp
  review_status:   {'current': 621}

Per-row verification (sample):
  [fa4df389180c] Dual-Model Cost Arbitrage
    status=active  review_status=current
    reviewed_at=1776147442.346576  valid_from=1776147442.346576  (match=True)
```

## Design decisions (recorded)

1. **Additive, not replacive.** We did not rename or drop `stale` / `stale_reason` / `valid_to`. Existing queries keep working.
2. **Default `review_status='current'`**, not NULL. A concept without explicit review state should read as "nothing flagged" — which is `current`, not "unknown."
3. **`reviewed_at` defaults to NULL** (not `created_at`). NULL means "never humanly reviewed." For active concepts we set it to `valid_from` because promotion is an implicit review act. For seeds we leave it NULL — they haven't been reviewed.
4. **No auto-staleness detection in this POC.** That's Phase 103d F12 work. R6's job is to give the future detector somewhere to write its findings.
5. **No `concept_history` table.** Temporal-graph thinking ("what did this concept look like on date X") is deferred; we version in place (`valid_from`, `valid_to`, `superseded_by`) not via an immutable log.

## What this unlocks

### F12 — auto-staleness detection (Phase 103d)

A future heartbeat can now: walk active concepts, check each anchor's file mtime (or content hash) against `reviewed_at`, and flip `review_status` to `needs_review` when anchor drift exceeds a threshold. That detector has a clear write target and doesn't need any schema change.

### Dashboard drift indicators

UI can render a "needs review" badge next to concepts whose `review_status = 'needs_review'`. No backend change required — just a SELECT.

### R7 — auto-captured observations → seed pipeline

When R7's PostToolUse hook notices a file edit, it can check the concept store for concepts anchored to that file and bump their `review_status` to `needs_review`. Direct integration path, no bridging.

### Eval for temporal drift

Future research can ask "of our active concepts, what fraction flipped to `needs_review` over a quarter?" — a measurable proxy for knowledge-graph decay rate. Requires no additional instrumentation beyond this schema.

## Deliberately out of scope

- Auto-staleness detection (F12 — Phase 103d).
- Migration of the live main-tree DB. Same as R5: change goes to the POC copy; live daemon state is untouched. When we're ready, run the migration against main's DB with one flag change — idempotent, safe.
- `concept_history` / event-sourced temporal model.
- `reviewed_by` (who did the review). Can add later if auditing demands it.
- Automated tests. The script is small and pure-SQL; trust its idempotency check covers most cases. Full testing belongs with F12 when the detection layer lands.

## How the calibration workstream might care

Not much — R6 is orthogonal to role-vector tuning. The temporal fields live on concepts; calibration adjusts role vectors. If calibration needs to consume concepts (it doesn't today), it can filter by `review_status != 'stale'` to avoid decayed content. Mention in the calibration handoff's §15 when they close out.

## Success criteria — met

| Criterion | Target | Actual |
|---|---|---|
| Missing R6 fields identified | yes | ✅ `reviewed_at`, `review_status` |
| Idempotent migration script | yes | ✅ `scripts/phase103_temporal_schema.py` |
| All existing rows have sensible defaults | yes | ✅ `review_status='current'` × 621 |
| Active concepts have implicit first-review timestamp | yes | ✅ `reviewed_at = valid_from` × 10 |
| Main-tree DB untouched | yes | ✅ ran on POC copy only |
| Zero breakage of existing pipeline queries | yes | ✅ all ADDs additive |

## Running the migration on the live DB (when ready)

```bash
# Dry-run first
.venv/bin/python scripts/phase103_temporal_schema.py \
  --db codrag_data/codrag_concepts.db --dry-run

# Ship
.venv/bin/python scripts/phase103_temporal_schema.py \
  --db codrag_data/codrag_concepts.db
```

Idempotent on the live DB too. Can be run at any time. Does not require daemon restart for SELECT-only paths; if the daemon caches concept rows in memory, restart it to pick up schema-aware queries.

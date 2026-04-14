# R5 — Concept Activation (POC)

**Date:** 2026-04-14
**Goal:** Activate the dormant concept flywheel. Go from **0 active concepts** to **≥10 active** on CoDRAG's own repo. Diagnose the promotion stall and ship the minimum viable pipeline.
**Status:** POC complete on isolated DB. 10 CoDRAG-project constraint concepts promoted. Script is reusable against any concept store.

## 1. Baseline audit findings

```
codrag_data/codrag_concepts.db (live; main tree)
  total concepts: 621
  statuses:       seed=621, active=0
  projects:       CoDRAG=366, PowerMate=133, other=122
```

Completeness breakdown for the 621 existing seeds:

| Criterion | Count | Rate |
|---|---|---|
| `anchors` non-empty | 621 | **100%** ✓ |
| `category` set | 621 | **100%** ✓ |
| `tags` non-empty | 621 | **100%** ✓ |
| `confidence ≥ 0.7` | 605 | 97.4% ✓ |
| `assertion` non-empty | **0** | **0.0%** ✗ |

**The clog is the assertion field.** Every seed has anchors, tags, a category, and strong confidence. None have assertions. The prior pipeline either did not generate them or dropped them during persistence.

My R5 design-doc hypothesis was "missing anchors" — wrong. The real blocker is missing assertions.

### Sample of high-quality CoDRAG constraint seeds

These are all `conf ≥ 0.85`, anchored to real files, with rich 400–600-char content bodies:

- `Dual-Model Cost Arbitrage as Core Architectural Constraint` → `swarm_orchestrator.py`
- `Archive-First as Non-Negotiable Safety Invariant` → `agents/custodian/engine.py`
- `Auto-Detection as Deployment Reality Acknowledgment` → `core/sarif.py`
- `BYOK as Constraint Engineering` → `core/batch_strategy.py`
- `JSON-RPC 2.0 as Intentional Constraint, Not Choice` → Paperclip plugin docs
- `Trust Invariants as Non-Negotiable Architectural Constraint` → `docs/ARCHITECTURE.md`
- `Token Budgeting as Latency-Accuracy Pareto Frontier` → MCP dogfooding docs
- `MCP Protocol as Foundational Constraint` → MCP protocol anchors

Intellectually, these **are** our "constraint concepts." They have everything antibody derivation needs except one field.

## 2. Criteria we are actually using

Revised from the original R5 design doc to reflect the audit:

1. `status = 'seed'` (obviously)
2. `project_id` matches target (avoid cross-project promotion batches)
3. `category` is set
4. `anchors` non-empty JSON list
5. `confidence >= 0.85` (tighter than 0.7; we want high-signal promotions first)
6. **Assertion handling**: if `assertion` is already set, keep it. If empty, use the concept's `title` as a **synthetic POC assertion** with a `(synthetic POC assertion; replace with human-written)` marker so future workflows can find them. This unblocks the flywheel; proper assertion generation is Phase 103d+ work.

Assertion-derivation is deliberately deferred. Building it properly (e.g., extracting testable claims from concept content via a constrained LLM call) is a dedicated workstream, not POC-appropriate.

## 3. Promotion utility

New file: `scripts/phase103_promote_seeds.py` (~110 lines, no external deps beyond stdlib + sqlite3).

```
python scripts/phase103_promote_seeds.py \
  --db path/to/codrag_concepts.db \
  --project-id 1d6f0b35-45cb-427b-ae9d-aac3c6371a4b \
  --category constraint \
  --min-confidence 0.85 \
  --limit 10 \
  [--dry-run]
```

- Idempotent: re-running is a no-op (only matches `status='seed'`).
- Marks each promoted concept's `valid_from` + `updated_at` to current Unix time.
- Fills synthetic POC assertion from `title` if assertion is empty.
- Exits non-zero with a warning if fewer candidates matched than requested.

## 4. What we promoted

Run on isolated `codrag_data_poc/codrag_concepts_poc.db` (a snapshot copy of main's live DB; main untouched):

| # | Confidence | ID | Title |
|---|---|---|---|
| 1 | 0.92 | `fa4df389180c` | Dual-Model Cost Arbitrage as Core Architectural Constraint |
| 2 | 0.92 | `085f8e5e9f56` | Archive-First as Non-Negotiable Safety Invariant |
| 3 | 0.91 | `950eb928ab66` | ISR Caching for GitHub API Rate Limit Survival |
| 4 | 0.90 | `a7012e46e98f` | Headless GitHub Discussions as Zero-Cost CMS |
| 5 | 0.90 | `b37f308f2342` | Layout Wrapper Proliferation as Next.js Constraint |
| 6 | 0.90 | `8220c6de9af0` | Auto-Detection as Deployment Reality Acknowledgment |
| 7 | 0.90 | `5e5a5ddcc8ea` | Semantic Anchoring Prevents Concept Drift |
| 8 | 0.90 | `2c91ec381d1a` | BYOK as Constraint Engineering |
| 9 | 0.88 | `0562ac261e6b` | JSON-RPC 2.0 as Intentional Constraint, Not Choice |
| 10 | 0.88 | `3dd663b66159` | Real Codebase Experiments as Blocking Gate |

Post-promotion state:

```
status distribution:
  active: 10
  seed:   611
```

**R5 POC success metric met.** The flywheel is no longer frozen at 0.

## 5. Isolation story

The live main-tree `codrag_data/codrag_concepts.db` **was not modified**. The POC wrote to a copy at `codrag_data_poc/codrag_concepts_poc.db` (inside the worktree-local data dir). This mirrors the isolation discipline we established in the handoff doc:

- User's running daemon keeps serving the same pre-promotion state from main's DB.
- POC data stays in `codrag_data_poc/` (which is already gitignored under `codrag_data/`'s parent rules; the full copy is not committed).
- When we're ready to ship, the same script runs against main's DB with one flag change. Idempotent, so running twice is fine.

## 6. Implications for the rest of Phase 103

### Unblocks F3 antibody hooks (Phase 103d)

The HANDOFF_CALIBRATION's §6 "Out of scope" notes hooks are gated on "active constraint concepts." We now have 10. That's enough for F3a (PreToolUse blocking) to be prototyped with real content instead of empty containers — the originally-predicted "empty Gotchas" failure mode does not happen.

Each promoted concept has anchors pointing at concrete source files (`custodian/engine.py`, `core/sarif.py`, `core/batch_strategy.py`, `swarm_orchestrator.py`, etc.) — which is exactly the data an antibody hook needs to decide whether an edit to that file violates a constraint.

### Feeds F4 skills-as-folders (Phase 103c)

Gotchas in generated skill folders can now be populated from real concepts:

> **Gotcha — Archive-First Safety Invariant:** The subsystem enforces mandatory archival before any cleanup operation through `ArchiveManifest` persistence. Do not bypass. Anchor: `src/codrag/agents/custodian/engine.py`.

That's a shippable skill Gotcha entry, derived mechanically from an active concept.

### Supports F6 concept promotion UI (Phase 103d)

The CLI script demonstrates the promotion logic. When the dashboard grows a promotion UI, it can reuse the same criteria + same idempotent SQL path — just wrapped in a React form. No new promotion logic needed.

### Unblocks F12 temporal validity auto-detection (Phase 103d)

Concepts now have real `valid_from` timestamps. Auto-staleness detection (anchor files changed since `valid_from`) can run against these 10 as a pilot.

## 7. Deliberately deferred

- **Real assertion generation.** The current synthetic assertion (title text) is functional for status-flip but not semantically useful for antibody derivation. A separate workstream should extract testable claims from `content` via a bounded LLM pass or structured prompt. Estimate: 1–2 days.
- **Assisted promotion UI.** Our R5 design doc proposed "Option B — propose and approve" with dashboard one-click. Not built in this POC. The CLI is the interim.
- **Auto-accept rules.** The design doc proposed auto-promote after 7 days for high-confidence + anchored + non-duplicate concepts. Not implemented; currently manual via CLI.
- **Non-duplicate detection.** Our criteria check anchors/category/confidence but not semantic duplication across seeds. Two seeds with different titles but the same assertion could both promote. Low risk at N=10; address when we scale.
- **Promotion across other projects.** We ran only on the CoDRAG project. PowerMate (133 seeds) and the other 122 cross-project seeds are untouched. Promote-at-a-time-per-project is the right discipline; resist batch promotion.

## 8. How another session runs this on the live DB

When the lead is ready to commit the 10 promotions to the real daemon's concept store:

```bash
# Dry-run against live DB — verify the plan
.venv/bin/python scripts/phase103_promote_seeds.py \
  --db codrag_data/codrag_concepts.db \
  --project-id 1d6f0b35-45cb-427b-ae9d-aac3c6371a4b \
  --category constraint --min-confidence 0.85 --limit 10 --dry-run

# If the plan looks right, commit:
.venv/bin/python scripts/phase103_promote_seeds.py \
  --db codrag_data/codrag_concepts.db \
  --project-id 1d6f0b35-45cb-427b-ae9d-aac3c6371a4b \
  --category constraint --min-confidence 0.85 --limit 10
```

Because the concept store is a SQLite DB, the running daemon should re-read concepts on next request (we should verify this — if the daemon caches, a restart may be needed). Worth a note for whoever runs it.

## 9. Success criteria — met

| Criterion | Target | Actual |
|---|---|---|
| Active concepts on CoDRAG project | ≥10 | ✅ 10 |
| Promotion criteria documented | yes | ✅ §2 |
| Idempotent reusable script | yes | ✅ `scripts/phase103_promote_seeds.py` |
| Main tree's DB untouched | yes | ✅ ran on isolated copy |
| Clog identified and diagnosed | yes | ✅ missing `assertion` field, not anchors |
| Handoff to Phase 103d ready | yes | ✅ all 10 concepts have code anchors, categories, confidence |

## 10. What R5 does NOT prove

This POC shows promotion is unblocked and the 10 concepts are well-structured. It does **not** show:
- That antibodies derived from these concepts actually fire correctly on live edits (that's F3).
- That the synthetic assertion quality is sufficient for automated constraint enforcement (it isn't; it's a placeholder).
- That 10 concepts is enough for any specific downstream feature — some features may need 30+.

Those are all downstream checks for Phase 103c/d work. R5 delivered its one job: break the flywheel's initial stall.

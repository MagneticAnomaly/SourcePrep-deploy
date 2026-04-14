# 08 — POC Execution Plan (Trimmed from R1–R8)

**Purpose:** Architecturally final experiment design, POC-scale. The R1–R8 docs contain the deep rationale; this doc is what we execute next week.

## What we discovered while designing this plan

Before trimming, we verified the ground truth in the repo:

| Thing we were going to build | Already exists |
|---|---|
| `codrag()` with `role` parameter | ✅ `src/codrag/mcp_tools.py` lines 43–50 — `role` already accepted |
| `working_dir` parameter for file-scope hints | ✅ Already accepted; maps to R4's `file` param |
| Role projection engine | ✅ `src/codrag/core/atlas/role_projection.py` — `project_atlas_for_role()` |
| Role vectors | ✅ `src/codrag/core/atlas/role_vectors.py` — `RoleVector` class |
| Gold-query eval harness | ✅ `tests/eval/eval_runner.py` (246 lines) + `gold_queries.json` |
| Model comparison harness | ✅ `tests/eval/model_comparison.py` (472 lines) |
| Overnight eval runner | ✅ `tests/eval/overnight.py` (654 lines) |
| E2E pipeline eval | ✅ `tests/eval/e2e_pipeline.py` (897 lines) |

**Implication:** Phase 103 is mostly *extension + measurement*, not new construction. The POC plan reflects this.

## Guiding principles (carried from 00_CLARIFICATION and 07_RESEARCH_PATH)

1. **We are testing knowledge-honing (graph-weighted sub-atlas), not persona prompting.** The mechanism is built and live; R3 is its first rigorous measurement.
2. **POC-scale.** Small N, fast turnaround, answers the architectural question without massive compute spend.
3. **Architecturally final.** The experiment *design* is the one we'd run at scale later. The *scale* is small because that's sufficient to answer "does the mechanism work directionally."
4. **Every sub-phase has a kill/refine/ship gate.** No lingering "maybe later."
5. **Fail fast.** If R3's POC comes back Pattern 4 (no lift), we calibrate weights and re-run before any larger investment.

## The eight sub-phases at POC scale

### R1 — Context layout (position)
- **POC experiment:** Pick 5 existing gold queries. Run each under 3 layouts: (A) flat, (B) relevance-sorted, (C) sandwich (critical-start + knowledge-middle + critical-end). 2 trials each. 30 runs total.
- **Measure:** eval_runner's existing pass/fail + file-hit-rate metric.
- **Gate:** If C > B by ≥5 percentage points → adopt sandwich template. If flat, keep simpler sorted layout and document the null finding.
- **Time:** 1 day to run, half-day to analyze.
- **Ships:** A `ContextLayout` enum with default + documented template in `codrag()`'s response assembler.

### R2 — Default budget
- **POC experiment:** Same 5 queries × 3 budgets (500, 2000, 8000 tokens) × 2 trials = 30 runs. Use the winning layout from R1.
- **Measure:** success rate, total token cost including any follow-up `codrag_search` calls.
- **Gate:** Pick the smallest budget where success ≥ 90% of max. That becomes the default for `codrag()`.
- **Time:** Half-day run; half-day analyze.
- **Ships:** A default `max_chars` value per role detail-level (already a concept in `role_projection.py`).

### R3 — Knowledge-honing validation (THE sub-phase)
- **POC experiment:** 4 queries tagged per role × 3 roles (architect, security, frontend — roles we already have vectors for) = 12 queries. Run each across the 2×2 cells (uniform atlas × role-weighted; persona-prompt × no-persona). 2 trials. **96 runs total.**
- **Labels:** Pick queries from the existing `gold_queries.json` whose `expected_files` cluster into a role scope (architect: index.py/atlas; security: admin_policy/api_envelope; frontend: dashboard — may need 2–3 new gold queries added).
- **Measure:** File-hit rate, keyword-hit rate, token cost.
- **Primary comparison:** B (role-weighted, no persona) vs A (uniform, no persona). That's the core knowledge-honing test.
- **Gate:**
  - Pattern 1/2/5 (any measurable lift from B or D) → knowledge-honing validated at POC. Continue to tuning and full harness later.
  - Pattern 3 (persona hurts) → document; strip persona from Paperclip default.
  - Pattern 4 (null) → run calibration pass on role vectors before declaring a problem; re-run.
- **Time:** 1 day to run, 1–2 days to analyze.
- **Ships:** A measured answer to the core Phase 103 question + a tuned `role_vectors.py` if calibration is needed.

### R4 — Universal client API
- **POC observation:** `codrag()` already accepts `role` and `working_dir`. The only real addition is a `task` parameter for natural-language intent.
- **POC experiment:** 5 gold queries × run twice — once with explicit `role`, once with only `task` (natural language hint) and server-side role inference. Measure inference accuracy.
- **Gate:** ≥ 70% role inference accuracy → ship `task` param as optional. < 70% → require explicit `role` for scoped responses, keep inference as hint.
- **Time:** Half-day.
- **Ships:** v2 MCP spec — 4 parameters: `task?`, `role?`, `working_dir?`, `max_chars?`. Backward compatible.

### R5 — Concept activation POC
- **POC experiment:** Manual promotion pass. Pick 10 seeds from our 366 that have clear anchors + testable assertions. Promote by hand. Verify they're reachable via `codrag_concepts`.
- **Gate:** 10 successful promotions in one session → the criteria work; automate as assisted-promotion UI later. < 10 achievable → seed generation is the problem, not promotion — route to seed-generator fix.
- **Time:** Half-day.
- **Ships:** 10 active concepts, a diagnosis of the main failure-to-promote bucket, proposed promotion-criteria YAML.

### R6 — Temporal validity POC
- **POC decision, not experiment:** Add four fields (`valid_from`, `superseded_by`, `reviewed_at`, `review_status`) to the concept schema. Backfill `valid_from = created_at` on the 10 R5-promoted concepts. No auto-staleness detection yet — this is a schema-only POC.
- **Gate:** Schema additions merge without breaking existing concept queries → done. Auto-staleness remains a Phase 103 v2 item.
- **Time:** Half-day.
- **Ships:** Schema update + migration.

### R7 — Automatic observation POC
- **POC experiment:** Implement one PostToolUse hook (`codrag hook post-edit <file>`) that writes a minimal JSONL observation. Install on CoDRAG's own repo; developer uses Claude Code for a day.
- **Measure:** Observations captured, storage size, hook p95 latency, noise-vs-signal ratio.
- **Gate:** >10 observations per active hour, <100ms p95 latency, clustering produces ≥1 seed candidate → ship as opt-in feature. Otherwise iterate filters.
- **Time:** 1 day implement, 1 day observe.
- **Ships:** `codrag hook post-edit` subcommand + opt-in install path.

### R8 — Benchmark harness extension
- **POC observation:** Harness exists. R8 extends it with condition-aware runs.
- **POC experiment:** Add a `--condition {A|B|C|D}` flag to `eval_runner.py`. Add per-condition config: uniform atlas, role-weighted, ± persona wrapper. Run R1–R3 through this flag.
- **Gate:** R1/R2/R3 all drive their experiments through the extended `eval_runner` → harness is validated as the shared infra.
- **Time:** 1 day to extend.
- **Ships:** Extended `eval_runner.py` + per-condition report output.

## Total POC scope

| Item | Days |
|---|---|
| R8 harness extension (foundation) | 1 |
| R1 layout POC | 1 |
| R2 budget POC | 1 |
| R3 knowledge-honing POC (primary deliverable) | 2–3 |
| R4 API POC | 0.5 |
| R5 concept activation POC | 0.5 |
| R6 temporal schema POC | 0.5 |
| R7 auto-observation POC | 2 |
| Analysis + writeup | 2 |
| **Total** | **~10–11 working days** |

One developer-week each for two weeks, or two developers parallelizing over one week.

## Execution order

```
Day 1      R8 extend harness (unblocks everything)
Day 2      R1 layout POC         ─┐
Day 2.5    R2 budget POC          │  (R1→R2 sequential, same harness)
Day 3–5    R3 knowledge-honing POC│  ← gate for the whole phase
Day 4      R7 auto-obs impl (parallel)
Day 5      R7 auto-obs observe period
Day 6      R4 universal API POC
Day 6.5    R5 concept activation POC
Day 7      R6 temporal schema
Day 7–8    Analysis + writeup + gate decisions
```

R3 is the only item that could extend — if results are ambiguous, run calibration + re-test adds 1–2 days. Plan for that.

## What the POC settles (architecturally final)

After this 2-week effort, these decisions are locked in:

1. **Layout template** (from R1) — `codrag()` response uses one specific format.
2. **Default budget** (from R2) — one specific char count per detail-level.
3. **Knowledge-honing validated or flagged** (from R3) — either we proceed with confidence, or we know exactly which role vectors need tuning.
4. **v2 MCP spec** (from R4) — 4-parameter API with backward compat.
5. **Concept promotion criteria** (from R5) — formal criteria for seed→active.
6. **Concept temporal schema** (from R6) — four fields, decided.
7. **Auto-capture ship/defer** (from R7) — feature is built or deferred with cause.
8. **Shared harness** (from R8) — one eval_runner drives all future measurements.

**None of these require a second full design pass.** The POC is the design; scale-up experiments only tighten confidence intervals on already-made decisions.

## Explicit out-of-scope for this POC round

To keep scope honest:

- **No new emission targets** (.claude/agents/, OpenClaw SOUL.md, Cursor rules). Those land *after* R3 validates knowledge-honing — we don't emit formats for a mechanism we haven't measured.
- **No antibody hooks** (the PreToolUse blocking kind). R6/R7 establish infrastructure; antibody hooks come after active concepts exist.
- **No public benchmark publication.** Internal numbers first. Publication follows after a second, larger eval round once POC-confirmed.
- **No Cursor/Windsurf integration work.** R4 settles the API; integration comes later.
- **No removal of existing features.** Paperclip's current behavior stays until R3 says otherwise.

## Risks that could force scope change

| Risk | Trigger | Response |
|---|---|---|
| R3 Pattern 4 (null result) | 96-run POC shows A ≈ B | Calibrate role vectors; re-run with tuned weights before concluding |
| Gold queries don't cluster into roles | R3 setup reveals queries are mostly architecture-flavored | Add 3–5 security/frontend gold queries before running R3 |
| Harness latency blows out | Running 96 R3 runs + 30 R1 runs + 30 R2 runs = ~150 runs, Sonnet 4.6 cost | Use Haiku 4.5 for R1/R2 (only directional signals needed); reserve Sonnet for R3 |
| Active concepts impossible to produce in R5 | 10 manual promotions each fail for different reasons | Downgrade concept layer in narrative; revisit after seed-generator fix |
| Hook latency > 100ms in R7 | Observation writes block edits | Make async; batch writes |

## Success declaration

We will call Phase 103 POC a success when all of the following hold:

- R3 has produced a measured answer to the knowledge-honing question (any pattern 1–5 with clean data, not noisy or inconclusive).
- The extended harness runs `make benchmark` end-to-end with the new conditions.
- A decision record exists for each of the 8 sub-phases (ship/defer/kill/refine).
- The docs folder `docs/Phase103_AgentOptimizations/research/R<n>_results.md` exists for each run, each self-contained, each citable.

Anything beyond that is a future phase — which we will plan with fresh context after seeing the POC numbers, not in advance.

## Architectural finality

Note what this POC **does not defer**:

- The MCP API shape (R4).
- The concept schema (R5 + R6 fields).
- The response-layout template (R1).
- The default budget logic (R2).
- The condition taxonomy in the harness (R8).

These are set after the POC and should not churn with scale. Scale-up runs will refine parameters, not redesign the interface.

What this POC **does defer**:

- Any new emission/writer modules.
- Any marketing benchmark publication.
- Any customer-facing API changes (v2 is a drop-in upgrade, not a breaking one).
- Antibody hook enforcement (needs active concepts first).

## Ready-to-start checklist

Before Day 1:

- [ ] Confirm `tests/eval/eval_runner.py` runs clean on main.
- [ ] Confirm `gold_queries.json` ↔ current atlas has meaningful hit rates (baseline).
- [ ] Tag 6–10 existing gold queries by role (architect / security / frontend); add 3–5 new if coverage is thin.
- [ ] Decide: Sonnet 4.6 for R3 runs, Haiku 4.5 for R1/R2 directional runs. Set budget cap.
- [ ] Create `docs/Phase103_AgentOptimizations/research/` dir for results artifacts.

That's it. Everything else is already in the repo.

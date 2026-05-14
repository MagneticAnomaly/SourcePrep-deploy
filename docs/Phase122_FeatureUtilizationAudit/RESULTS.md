# Phase 122 — Feature Utilization Audit — RESULTS

**Date:** 2026-05-14
**Spec:** `docs/superpowers/specs/2026-05-13-phase122-custodian-dogfood-design.md`
**Plan:** `docs/superpowers/plans/2026-05-13-phase122-custodian-dogfood.md`

## What we did

Dogfooded the existing Custodian engine
(`src/prep/agents/custodian/engine.py`) against the 11 candidate
modules listed under "Other modules under audit" in
`docs/INTENTIONALLY_DORMANT.md`. Built a thin driver
(`tools/phase122_custodian_run.py`) that synthesized `dead_code`
findings for each candidate and ran the discover → verify pipeline
in dry-run mode. Captured verdicts to
`custodian_run.json`. Then ran a human confirmation pass on each
verdict (grep for callers including the relative-import form `.X`,
git log of last meaningful change, marketing-page check) and applied
the 5-bucket rubric.

## Bucket distribution (final, human-decided)

| Bucket | Count | Modules |
|---|---|---|
| **WIRED** — false positives from the audit heuristic | **8** (73%) | `roadmap_miner.py`, `lod_extractor.py`, `github_sync.py`, `chunking.py`, `inferred_edges.py`, `batch_profiles.py`, `swarm_registry.py`, `context_config.py` |
| **KEEP-DORMANT** | **3** (27%) | `treatment_registry.py`, `swarm_optimizer.py`, `budget_enforcement.py` |
| **NEEDS-OWNER** | 0 | — |
| **DEPRECATE** | 0 | — |
| **DELETE** | 0 | — |
| **INVESTIGATION_FAILED** | 0 | — |

Custodian classifications were uniform: **all 11 came back
`needs_review`**. The Custodian's 6-question heuristic is by design
biased toward false positives (preserve life over precision), and on
this batch the bias paid off — the human pass found real callers for
8 of 11.

## What changed the bucket vs the Custodian's verdict implied

The Custodian's `needs_review` is the "I can't tell from file
contents alone, you decide" verdict. For every WIRED case the human
grep pass found explicit imports the LLM had no way to see. For
every KEEP-DORMANT case the grep confirmed the Custodian's caution
was warranted — there are no production callers, and the LLM's
docstring-based hesitation was correct.

Notable per-module reasoning:

- **`treatment_registry.py` (KEEP-DORMANT).** Phase 53 designed a
  two-piece system: `ContentClass` (the 3-class taxonomy) and
  `TreatmentRegistry` (per-class batch sizing). `ContentClass`
  shipped wired (`augmenter.py:1336`, `epistemic_enrichment.py:711`).
  `TreatmentRegistry` did not — the augmenter classifies into 3
  buckets and then applies a uniform `batch_size`. Has unit tests
  in isolation; no integration test. Concrete wire site exists.
  Tracked as `P122-T-treatment_registry` in `MASTER_TODO.md`.

- **`swarm_optimizer.py` (KEEP-DORMANT).** Not on the live swarm
  path. Phase 82 explicitly pruned this file's `PLAN_TIER_CONCURRENCY`
  per `Phase82_CloudPipelineConcurrency/05_Completion_Plan.md:24`
  (commit `214f261f`); the remaining 4 batch-cap / attention-ceiling
  constants were never wired. Their **values** are alive — `200_000`
  is inlined at `batch_profiles.py:276,320` and
  `epistemic_enrichment.py:588`. What's at risk if the file is
  deleted is the **calibration rationale comments** explaining
  *why* the values are what they are. Live swarm files
  (`swarm_orchestrator.py`, `swarm_registry.py`,
  `concept_generate_swarm.py`, `concept_validate_swarm.py`,
  `swarm_event_logger.py`, `swarm_models.json`) are all unaffected.
  Tracked as `P122-T-swarm_optimizer`. **High-care file: do not
  delete without owner signoff.**

- **`budget_enforcement.py` (KEEP-DORMANT, post-MVP).** Phase 06
  enterprise admin design (`EA-H5`). Tested in isolation, never
  wired. Enterprise tier is not in MVP scope so the absence of
  pipeline-runner / audit-log / dashboard integrations is
  by-design-deferral, not abandonment. Tracked as
  `P122-T-budget_enforcement`.

- **`inferred_edges.py` (WIRED).** Registered as a pipeline stage
  (`StageId.INFERRED_EDGES`) with full configuration in
  `services/pipeline/stages.py` (queue, output file, manifest,
  batch profile, prompt key). Modified *last week* under
  Phase 135.5 (`474a2b6f feat(phase135.5): stage 2 inferred_edges
  consults Changeset`). The audit heuristic was simply wrong on
  this one — pipeline-stage registration via `StageId` enum +
  Worker subclassing is exactly the kind of integration the
  naive grep heuristic misses.

## prep_impact dogfooding bug confirmed (P122-D1/D2/D3)

`prep_impact(file_path="src/prep/core/<X>.py", direction="dependents")`
returns `0 dependents` for every module in this audit batch that is
consumed via `from prep.core.X import Y` — including
`src/prep/core/__init__.py` itself, which has hundreds of consumers.
Control case `src/prep/services/pipeline/workers.py` correctly
returns 2 dependents.

**Root cause hypothesis:** the trace graph is bimodal — each Python
module has both a `file` node and an `external_module` node, and
incoming `from prep.core.X import Y` edges land on the
`external_module` twin. `prep_impact` with `direction=dependents`
queries only the file-node side and misses them.

**Downstream impact in this audit:** the Custodian's `_get_impact()`
(`engine.py:51`) uses the same code path and silently received
`dependent_count=0` for every Phase 122 candidate. This biases the
LLM safety verifier toward `safe_to_delete` for files that actually
have callers. The verifier compensated in 8 of 8 WIRED cases by
reading file contents and choosing `needs_review` instead of
`safe_to_delete` — but the bug remains real and is filed as
**P122-D1** (fixture reproduction), **P122-D2** (fix edge
aggregation), **P122-D3** (return "not indexed" instead of silent
0) in `MASTER_TODO.md`. Cross-ref: `prep_observe` bug id
`bd79badde4d2` anchored to `src/prep/mcp/server.py`.

## Lessons for future audits like this

1. **The "no external imports" naive grep heuristic from Phase 119
   has a ~73% false-positive rate on this codebase.** Reasons:
   re-exports through `__init__.py`, relative imports
   (`from .X import Y`), pipeline-stage registration via enum,
   string-keyed dynamic dispatch, and the `prep_impact` bimodal-node
   bug. Future runs should at minimum check both the explicit
   (`from prep.core.X`) AND relative (`from .X`) import forms.
2. **`tests/eval/real_repos/<sample-project>/` is heavy noise**
   for any grep over the repo. The sample projects have their own
   independent codebases — exclude them via
   `grep -v "tests/eval/" ...` to avoid false hits like the
   OpenClaw repo's `reply-chunking` matching a `chunking` grep.
3. **The Custodian's LLM safety verifier is conservative by design**
   — it returned `needs_review` for all 11 candidates, providing
   limited signal differentiation. The human grep pass was the
   actual deciding factor. The Custodian was *correct* to be
   cautious; it just doesn't move the needle on its own.
4. **Pipeline-stage registration (`StageId` enum + Worker subclass
   + `stages.py` config) is invisible to import-grep heuristics.**
   A future audit pass focusing on pipeline modules should grep
   for `StageId\.<NAME>` and `Worker)` (subclass marker) before
   classifying anything in `src/prep/core/` as orphaned.

## Phase 122 status

**Closed.** The original Phase 122 README (2026-04-30) scoped nine
tasks. Status now:

| Original task | Status |
|---|---|
| T1 — `tools/feature_audit.py` reproducible script | Superseded — used the Custodian engine directly instead (see spec §1). |
| T2 — fix re-export false-positive heuristic | N/A — the human grep workaround covered this audit. The underlying bug (P122-D1/D2/D3) is filed. |
| T3 — triage candidates | **Done.** All 11 candidates have decisions. |
| T4 — wire `spaghetti_scorer` | **Done by Phase 124 T5** (`workers.py:1397-1515`). |
| T5 — DELETE / DEPRECATE PRs | N/A — no DELETE / DEPRECATE buckets. |
| T6 — KEEP-AND-WIRE backlog issues | **Done.** Three `P122-T-*` entries in `MASTER_TODO.md`. |
| T7 — `INTENTIONALLY_DORMANT.md` | **Done.** 4 full triage entries (concept_promotion pre-existing + 3 new), 8 WIRED summary lines. |
| T8 — FastAPI route audit (279 routes) | **Deferred** — Part C of the original brainstorm. |
| T9 — Storybook story audit (79 stories) | **Deferred** — Part C of the original brainstorm. |

**Follow-ups now live in `MASTER_TODO.md` Phase 122 section:**

- **P122-D1 / D2 / D3** — fix the `prep_impact` bimodal-node bug.
- **P122-T-treatment_registry** — wire `TreatmentRegistry.compute_batch_size`
  into `augmenter.py:1338` and `epistemic_enrichment.py:711-723`.
- **P122-T-swarm_optimizer** — port calibration rationale to inline
  sites OR re-import constants for recentralization; owner decides;
  high-care file.
- **P122-T-budget_enforcement** — wire when enterprise tier becomes
  MVP scope; alternative: deprecate if tier is shelved.

## Cross-reference: lessons for future file-classification work

The Phase 136 Part 01 spec
(`docs/Phase136_Dogfood-fixes/Part01_FileRoleSplitForSearch/README.md`)
defers "legacy/deprecated detection at file level" pending concept
anchors. If that work ever gets built, the methodology validated
here may transfer:

- **LLM verification + human grep is necessary** when static
  heuristics produce >50% false positives. The Custodian's
  6-question heuristic is a working example, available at
  `src/prep/agents/custodian/prompts.py`.
- **A bimodal-graph fix is a prerequisite** — any classifier built
  on top of the current `prep_impact` will inherit the same
  silent-0 problem.
- **Phase 122 itself is internal maintenance**, not file-anchored
  signal that a search ranker would consume directly. The
  *methodology* may transfer; the *data* does not.

# 06 — Dogfooding Plan (The Active Work)

This is the only file in Phase 116 that describes **work we do now**. The
rest is research and options. This file says: here's how we collect enough
real build data to re-rank checkpoints with evidence.

## Core thesis

We have **intuition** that certain checkpoints deserve overseer attention.
We do **not** have evidence. Intuition can be wildly wrong — the swarm
synthesis checkpoint might catch zero errors in practice; the validation-
rejection checkpoint (ranked 6/10 today) might turn out to be gold.

**Before designing, build a pool.** Minimum N = 20 builds across ≥3 real
codebases. For each, capture per-stage outputs, confidence distributions,
and post-hoc error reports. Then manually simulate overseer calls to
generate ground truth.

## What to capture per build

Create `~/prep_research/phase116/runs/<iso_date>-<project_id>/` and save:

1. **Full pipeline manifest** — all stage records with model, tokens,
   timing, confidence.
2. **Per-stage artifacts** — copies of `trace_nodes.jsonl`,
   `trace_inferred_edges.jsonl`, `trace_augmented.jsonl`, `trace_epistemic.jsonl`,
   `trace_group_reasoning.jsonl`, `trace_modules.jsonl`. Small enough to
   keep; critical for re-analysis.
3. **Swarm worker logs** — the full `SwarmResult.worker_results` arrays
   from Stage 7. This is the single most valuable artifact for Checkpoint #1
   dogfooding.
4. **Audit reports** — the 5 markdown files from Stage 14.
5. **Concept promotion log** — every observation that was promoted, with
   its source category and the promoted concept's assertions.
6. **Atlas + role projections** — the final atlas.json and per-role views.
7. **Build metadata** — project name, commit SHA, total runtime, cost.

Automate collection via a small post-run hook or manual tarball. Even
manual tarball at first — we don't need infrastructure to start.

## What to measure per build

For each candidate checkpoint, compute the **gate signal** that would have
fired (without actually invoking Opus):

| Checkpoint | Signal to compute |
|---|---|
| #1 Swarm synthesis | `stddev(worker_confidence)` per group; count of groups with stddev > 0.3 |
| #2 Concept promotion | Count of promotions; distribution of source-observation confidence |
| #3 Audit synthesis | Pairwise contradiction heuristic across the 5 reports (simple keyword overlap) |
| #4 Hub mutations | Count of hub files (dependents > 50) with classification change between runs |
| #5 Role atlas | Per-role layer-coverage count; min-coverage per role |
| #6 Epistemic anomalies | Count of files with `epistemic_confidence < 0.6` |
| #7 Inferred edge | Edge-confidence distribution per file; count with bimodal distribution |
| #8 Cross-cutting | Coverage % for known cross-cutting concerns (logging, auth, metrics) |
| #9 Validation rejection | Per-file edge-rejection rate; count with rate > 30% |
| #10 Antibody grounding | Per-antibody trigger-pattern match count (0 = dead rule) |
| #11 Deepening convergence | Tag edit-distance per file between Stage 6 and Stage 9 |
| #12 Filter universality | Count of excluded-dir paths leaking into trace |

Each of these is cheap pure-data analysis over captured artifacts. Produces
a per-build row: "would-have-fired counts per checkpoint."

## Manual overseer simulation (ground-truth generation)

For a subset of would-have-fired moments (say, top 5 per build), manually:

1. Construct the prompt the overseer would have received.
2. Paste into Claude Code (or the Claude web app) running Opus.
3. Apply the tentative JSON rubric from `05_` Q5.
4. Record: did Opus flag an actual problem? Was its suggestion actionable?
5. Record to `07_DOGFOODING_LOG.md` in the log format below.

This is the **gold standard** data — it tells us the actual catch rate for
each checkpoint, not the theoretical blast radius.

**Target: 50 manual overseer simulations across ≥20 runs.** This is a
weekend of work, not months.

## Dogfooding the product while dogfooding the idea

Every run we capture is also a real Prep build. Treat the build itself as
product-feedback opportunity:

- Does the pipeline run to completion?
- Does the atlas look right to the human reviewer?
- Do the audit reports land?
- Did any stage silently drop work? (Swarm-timeout failures in `02_`.)

Findings that aren't about the overseer idea still go in `08_SURPRISES_AND_FEEDBACK.md`.
Some of those may promote to their own micro-phase independent of 116.

## When dogfooding is "done"

Exit criteria for moving Phase 116 from research → design:

1. **≥ 20 real builds captured** across ≥ 3 distinct codebases (including
   Prep itself, Paperclip, and 1+ external project).
2. **≥ 50 manual overseer simulations** logged in `07_`.
3. **Measured per-checkpoint catch rate** — an actual number
   (e.g. "swarm-synthesis checkpoint caught 7/15 real issues when fired").
4. **Re-ranked checkpoint priority** based on measured, not theoretical,
   ROI.
5. **Rubric validated** — 2+ rubric iterations producing consistent
   overseer output on the same input.
6. **Cost model** — per-checkpoint estimated dollars/run under realistic
   gating.

Only after these six are in hand do we write a spec and move to
implementation. **Without this data, any design we commit to is a guess.**

## What NOT to do during dogfooding

- **Don't build the framework yet.** Tempting to start scaffolding
  `OverseerGate` / `CheckpointRegistry`. Resist. The dogfooding data will
  reshape what abstractions you actually need.
- **Don't call the overseer inside the pipeline.** Keep it manual /
  out-of-band. In-pipeline invocation is a commitment; we're not there.
- **Don't over-collect.** 20 builds is the target, not 200. Data hoarding
  is procrastination dressed up.
- **Don't normalize the confidence fields yet.** They're inconsistent
  (`02_`). Normalizing is a product-improvement task worth doing, but
  doing it for the overseer locks in a schema we may regret.

## First actionable step

Write a small shell / Python script that, given a run directory, produces
a `checkpoint_signals.json` with the 12 per-checkpoint counts. Run it
against past builds we already have. See what we can learn from historical
data before collecting a single new build.

That's the first concrete Phase 116 task. Everything else is reading,
thinking, and collecting.

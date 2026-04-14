# R6 — Temporal Validity: Do Concepts Decay?

**Goal:** Determine whether concepts and observations need explicit temporal validity, and if so, what the minimum model is.
**Time budget:** 1 week
**Decision at end:** add temporal fields (and what kind) or explicitly decide not to.

## Core question

Zep beats Mem0 by 15 points on LongMemEval by tracking **when facts were true and when they were superseded**. Code changes over time: a concept recorded six months ago about auth middleware may not apply after a rewrite. **Do we need temporal validity on concepts, and if so, how little can we get away with?**

## Hypothesis

**H1:** Concepts do decay — a meaningful fraction (10–30%) become stale within a year in an actively developed codebase.

**H2:** A minimum two-field model (`valid_from`, `superseded_by`) is sufficient for 95% of cases. Full temporal graphs (Allen's interval algebra, etc.) are overkill.

**H3:** Auto-detection of concept staleness is possible by watching for anchor file changes; a concept whose anchor was rewritten is at least a candidate for review.

## Literature check

- **Zep temporal knowledge graph** — explicit validity windows; measured 15-point LongMemEval gain.
- **arxiv 2601.03236 MAGMA (multi-graph agentic memory)** — multi-graph architecture with temporal edges.
- **Temporal RDF / OWL** — academic precedent for validity windows on assertions.

The consensus is clear: temporal validity matters for agent memory. The design question is how much of that machinery we need.

## Investigation

This is a small-scale diagnosis + lightweight design exercise.

**Step 1 — Measure decay on our own concepts (2 days):**
- When R5 produces ≥20 active concepts, retrospectively check: of the seeds, how many reference files that have been substantially modified since the seed was created?
- Rough proxy: seed-date vs. anchor-file last-modified date; if anchor changed after seed was made, concept may be stale.
- Output: percentage of potentially-stale concepts.

**Step 2 — Design minimum temporal model (2 days):**
- Propose minimum fields.
- Cross-reference with R5's concept criteria to avoid duplication.

**Step 3 — Implement and backfill (2 days):**
- Add fields to schema.
- Backfill existing concepts with `valid_from = created_at`.
- No `superseded_by` backfill — those come from review or auto-detection.

**Step 4 — Staleness detection experiment (1 day):**
- Run auto-detection: for each concept, check if its anchor files have changed ≥N% since activation.
- Flag as "review" (not auto-demote).
- Measure false-positive rate on a sample.

## Proposed minimum model

Add to concept schema:

```yaml
valid_from: 2026-04-13T21:00:00Z
superseded_by: null | <concept_id>
reviewed_at: 2026-04-13T21:00:00Z
review_status: current | needs_review | stale | retired
```

That's it. Four fields.

- `valid_from` — when the concept was first true (default: activation timestamp).
- `superseded_by` — if another concept replaces it, pointer to the new one.
- `reviewed_at` — when a human last confirmed the concept is still valid.
- `review_status` — lifecycle state.

**What we do NOT add:**
- `valid_until` — concepts don't expire on a schedule; they get superseded by events.
- `confidence_decay_function` — over-engineering. Binary states are fine.
- `temporal_graph_edges` — not a temporal graph, just annotated concepts.

## Staleness signals

Auto-flag a concept as `needs_review` when any hold:
1. Anchor file has changed >30% (line diff) since last review.
2. Concept is older than 180 days with no review.
3. A newer concept has been promoted with overlapping assertion.
4. An antibody derived from this concept has a high false-positive rate.

Flagging is low-cost, informational. Human decides demote/retire/update.

## Simplicity audit

The temptation is to build a temporal reasoning layer. Resist.

- No interval algebra. No time-traveling queries.
- No "what did the codebase look like at time T" — git already does that.
- No automatic demotion — review-flagging only.
- Concepts are timestamped assertions that humans can mark stale. That's all.

If this grows past four fields, we've drifted.

## Decision

**Path 1 — Decay is real, temporal is cheap:** Ship four-field model. Auto-detection flags stale candidates; humans resolve.

**Path 2 — Decay is rare, temporal is premature:** Don't add fields; rely on manual retirement when someone notices. Revisit in six months.

**Path 3 — Decay is moderate, auto-detection is noisy:** Ship four-field model but turn off auto-detection initially; enable it only after tuning the threshold.

Likely Path 1 or 3 based on H1.

## Dependencies

- **R5** must produce active concepts before we can measure decay.
- **R7 (auto-observation)** writes observations that can support re-validation of concepts.

## Success criteria

- ✅ Decay rate measured on our own concepts.
- ✅ Four-field schema added (or explicitly rejected with rationale).
- ✅ Auto-detection flagging, with tuned threshold.
- ✅ Zero-cost for concepts that don't need temporal treatment (default values work).

## Output artifact

`docs/Phase103_AgentOptimizations/research/R6_results.md`:
- Measured decay rate.
- Final schema decision.
- Auto-detection threshold and validation data.
- Comparison to Zep's approach (are we in the same class?).

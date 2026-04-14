# R1 — Context Rot & Positional Sensitivity

**Goal:** Determine the optimal layout and size of context returned by `codrag(role, task, budget)`.
**Time budget:** 1 week
**Decision at end:** template layout standard for all context responses.

## Core question

When CoDRAG returns scoped context to an agent, **where does the agent actually retrieve from?** Chroma's context-rot work and the "Lost in the Haystack" paper both suggest start and end positions have 85–95% recall while the middle drops steeply. If this is true for agent workloads specifically, our template layout matters more than our content selection.

## Hypothesis

**H1:** Context returned by `codrag()` with critical constraints at the start+end and derivable knowledge in the middle produces measurably better task completion than flat layout.

**H2:** There is a sharp cliff in effective context usage well before the advertised token budget — probably at 40–60% of the model's stated limit — where adding more context hurts rather than helps.

**H3:** Very small contexts (under 1K) amplify positional sensitivity rather than eliminating it. The sweet spot is not "as small as possible" but "as small as sufficient, structured deliberately."

## Literature check

- **Chroma Context Rot research** — performance degrades with input growth even when content is relevant.
- **Lost in the Haystack (PMC12478432)** — smaller gold contexts *worse*, not better, due to positional sensitivity amplification.
- **Anthropic context engineering guide** — position-aware placement recommended; critical constraints at start/end.
- **Microsoft agent-skills** — 4-stage progressive loading; 94.7% savings from *staged* delivery, not just smaller payloads.

The literature converges on: **size matters, but structure matters more.** We haven't internalized this yet.

## Experiment

Set up a measurement harness on CoDRAG's own codebase.

**Setup:**
1. Pick 20 representative tasks against CoDRAG repo: 10 modifications (fix bug in file X), 5 investigations (find where Y happens), 5 reviews (is file Z safe to modify).
2. For each task, define an objective success criterion (file path returned, diff that compiles, question answered with correct file citation).

**Conditions (5 variants per task):**
- **A — Flat:** all context concatenated in arbitrary order.
- **B — Sorted by relevance:** highest-scored chunks first, decreasing.
- **C — Start-End sandwich:** critical (antibodies, forbidden tools, task framing) at start AND end; knowledge in middle.
- **D — Minimal:** smallest context that contains the answer (oracle baseline).
- **E — Bloated:** full atlas + all concepts (upper bound on "too much").

**Budget sweep per condition:** 500, 1000, 2000, 4000, 8000, 16000 tokens (where applicable).

**Run:** each task × each condition × each budget, 3 trials for noise. Use Claude Sonnet 4.6 for cost; spot-check with Opus on variance-heavy cases.

**Measure:**
- Task success rate.
- Output quality score (rubric: correctness, specificity, hallucination rate).
- Cost in tokens.
- First-attempt success vs. retried.

## Expected findings (to be falsified)

- Condition C (sandwich) outperforms B (sorted) by ≥10% at medium budgets (2–8K).
- Condition D (minimal) wins on cost but has a cliff — below some threshold, success collapses.
- Condition E (bloated) loses to C at nearly every budget above 4K — context rot confirmed.
- The "knee" where adding context stops helping is between 4K and 8K on Sonnet 4.6.

If any of these fail, the layout standard needs rethinking before we ship.

## Decision framework

After the experiment we pick one of three paths:

**Path 1 — Confirmed:** Sandwich layout is measurably better. Standardize it in the `codrag()` MCP contract. All context responses use the template:
```
[CRITICAL-START] antibodies, forbidden tools, role constraints, task framing
[KNOWLEDGE]       scoped atlas, concepts, code chunks
[CRITICAL-END]    repeat key constraints, next-action hints
```

**Path 2 — Inconclusive:** Sandwich helps in some cases, hurts in others. Expose layout as a parameter on `codrag(layout="sandwich|sorted|flat")` with `sandwich` default; document the trade-offs.

**Path 3 — Falsified:** Position doesn't matter for agent workloads. Keep the simpler sorted-by-relevance layout. Cite the falsification in the research notes so we don't revisit it.

## Simplicity audit

Could we answer the positional-sensitivity question with a smaller experiment? Probably — a 5-task pilot on one condition (C vs B) at one budget (4K) would detect a large effect. If we don't see a signal there, we can defer the full sweep.

**Proposed refinement:** run the 5-task pilot first (1 day). If signal is clear, either ship the layout without the full sweep (saves time) or do the full sweep to quantify (saves credibility). If no signal, the full sweep is waste.

## Success criteria

- ✅ 20-task harness exists and can be re-run against any future CoDRAG version.
- ✅ Position-sensitivity question has a measured answer (yes/no/partial), not an intuition.
- ✅ Layout standard (or deliberate non-standard) is documented in the `codrag()` MCP tool spec.
- ✅ The harness becomes the foundation for R8 (benchmark & eval).

## Dependencies

- Requires a stable `codrag()` response format (already exists).
- Requires `codrag_data/` to have a meaningful atlas (already exists).
- Requires at least 10 active concepts for some test conditions (currently blocked — see R5).

**If R5 hasn't produced active concepts yet**, run R1 without the concepts condition and revisit after R5.

## Output artifact

`docs/Phase103_AgentOptimizations/research/R1_results.md` containing:
- Measurement data (raw + summary stats).
- Per-task outcome matrix.
- Chosen layout standard with rationale.
- Template spec for `codrag()` response formatting.
- Notes on what surprised us; feeds into R2's hypothesis refinement.

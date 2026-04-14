# R5 — Concept Activation: Fixing the Flywheel

**Goal:** Make concept promotion work. Go from 0 active concepts on our own repo to ≥20 active concepts feeding real `codrag()` responses.
**Time budget:** 2 weeks
**Decision at end:** promotion pipeline design (auto, assisted, or manual).

## Core question

We have 366 concept seeds and 0 active concepts. The scrutiny doc (06) called this "the most honest risk in the whole plan." **Why hasn't promotion happened? What's the minimum pipeline that produces active concepts without becoming a human-in-the-loop tax?**

Every downstream feature — antibody hooks, skill gotchas, scoped KNOWLEDGE.md enrichment — depends on active concepts. Without solving R5, Phase 103 ships empty containers.

## Hypothesis

**H1:** Promotion has stalled because the criteria are ambiguous — no one knows when a seed is "ready." Clear criteria will unblock a wave of auto-promotions.

**H2:** Many seeds fail promotion not because they're bad but because they lack anchors (specific file/line references). Fixing the seed-generation pipeline to require anchors would raise promotion yield dramatically.

**H3:** Full automation is probably wrong — the act of promoting is part of how concepts become *trusted*. Semi-automated (auto-propose, human one-click approve) is the sweet spot.

## Literature check

- **Knowledge graph construction research** — most production graphs rely on human validation at key nodes; fully-auto graphs drift quickly.
- **Zep temporal memory architecture** — explicitly separates "raw observation" from "validated fact"; our seed→active split mirrors this.
- **arxiv 2505.18279 Collaborative Memory** — access-controlled promotion chains are a design pattern.
- **CoDRAG's own Phase 67/88 docs** — role-file generation presumes concepts exist; they're the inputs.

## Investigation

This sub-phase is **less experiment, more diagnosis**. We need to understand why our own flywheel stopped before we can fix it.

**Step 1 — Seed audit (2 days):**
- Categorize all 366 seeds by why they are NOT promoted.
- Buckets: (a) lacks anchor, (b) lacks testable assertion, (c) ambiguous scope, (d) duplicate, (e) speculative/low-confidence, (f) blocked on human review, (g) other.
- Output: a percentage breakdown. Reveals where the funnel loses candidates.

**Step 2 — Identify high-yield bucket (1 day):**
- Whichever bucket is biggest → target it.
- Likely hypothesis: (a) "lacks anchor" is dominant. If 200+ seeds lack anchors but are otherwise valid, we've found the flywheel's clog.

**Step 3 — Fix the clog (1 week):**
- If missing anchors: improve seed generation to require anchors, or add an anchor-discovery pass over existing seeds.
- If missing assertions: seeds without testable assertions shouldn't be called concept seeds; they're observations. Reclassify.
- If ambiguous scope: tighten the criterion; reject low-quality seeds earlier.
- If duplicate: cluster and merge.

**Step 4 — Promote what's ready (2 days):**
- With clog fixed, run a promotion pass over all existing seeds.
- Target: ≥20 concepts move to active.
- Measure the human-review burden to see if it's sustainable.

## Criteria for "active concept"

Today the criteria are vague. Propose explicit, minimal criteria:

1. **Anchor present** — at least one file path (and optionally a line range) the concept references.
2. **Assertion present** — at least one falsifiable statement about the codebase ("file X must not import library Y").
3. **Scope clear** — audience tag (architecture, security, etc.) is set.
4. **Non-duplicate** — no existing active concept covers the same assertion.
5. **Confidence** — either LLM-marked as high-confidence or human-approved.

If all 5 hold → auto-promote-ready. Propose to human; default accept.
If 3–4 hold → needs one pass to fix; propose to human; default review.
If <3 hold → reject; fix seed generation or mark as observation instead.

## Promotion pipeline options

**Option A — Fully automatic:**
All seeds meeting criteria auto-promote. Human reviews only those contested or demoted later. *Risk: noise pollutes the graph; false concepts drive false antibodies.*

**Option B — Propose-and-approve:**
Pipeline produces promotion proposals; dashboard shows one-click approve/reject. Default accept after 7 days if nobody reviews. *Risk: if no one reviews, defaults accept everything = Option A.*

**Option C — Human-gated:**
No auto-promotion; human explicitly promotes. *Risk: what we have today — 0 active concepts.*

**Recommended:** Option B with a twist — auto-accept after 7 days **only for high-confidence + anchored + non-duplicate** seeds. Everything else stays pending until human review. This is the "simplest thing that could work."

## Experiment

Run Option B on CoDRAG's own seeds for two weeks. Measure:

- How many seeds auto-accept after 7 days without human touch?
- How many get human one-click approval within 7 days?
- How many are explicitly rejected?
- How many rot (neither accepted nor rejected)?
- Of the auto-accepted, how many turn out to be wrong (retrospective check)?

If auto-accept false-positive rate is >10%, Option B is too loose — tighten criteria or add more human gates.

## Simplicity audit

The whole concept system risks becoming a second codebase inside CoDRAG. Keep it minimal:

- Active concept = 5 criteria above. No more fields.
- Promotion = JSON flip from `status: seed` to `status: active`, plus `activated_at` timestamp. No complex workflows.
- Demotion (the reverse) = flag for review, human decides.
- Every concept has a simple lifecycle: seed → active → (stale | superseded | retired).

If the pipeline requires more than 200 lines of code, it's over-designed.

## Connection to other sub-phases

- **R6 (temporal validity)** — once concepts are active, they need validity windows. R5 sets the stage.
- **R3 (role scoping validation)** — a concept-rich test environment for the 2×2 factorial. Running R3 before R5 produces empty results in the concept condition.
- **R7 (auto-observation)** — observation capture feeds the seed pipeline. Improving R7 improves R5's input rate.

**Sequencing note:** R5 should be run in parallel with R3 if possible. R3 needs active concepts to measure scope value against; R5 produces active concepts.

## Kill criteria

If after two weeks of focused work we cannot produce ≥10 active concepts even with explicit criteria and one-click approval, the flywheel premise is broken and we should:

- Strip "concepts" from the product narrative.
- Keep the data layer (it's low-cost) but stop claiming concepts as a differentiator.
- Rely on antibodies derived from lint rules or explicit user input, not from organic concept promotion.

This is an uncomfortable but honest possibility. We should be prepared.

## Success criteria

- ✅ Seed-bucket analysis done; clog identified.
- ✅ Fix to seed generation shipped.
- ✅ ≥20 active concepts on CoDRAG's own repo.
- ✅ Promotion pipeline producing ≥3 active concepts per week, sustainable.
- ✅ False-positive rate on auto-accept < 10%.

## Output artifact

`docs/Phase103_AgentOptimizations/research/R5_results.md`:
- Seed bucket breakdown with counts and examples.
- Root-cause diagnosis of the promotion stall.
- Chosen promotion pipeline (A/B/C/hybrid).
- Criteria definition.
- Two-week metric data: auto-accept rate, false positives, human review burden.
- Recommendation on ongoing monitoring.

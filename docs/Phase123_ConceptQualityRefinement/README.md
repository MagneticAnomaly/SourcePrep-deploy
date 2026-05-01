# Phase 123 — Concept Quality Refinement

> **Scope:** Investigate why the swarm-synthesizer concept output, while
> high-quality, may be over-compressing. Tune the seeder to produce
> richer, more useful per-codebase concept sets without sacrificing the
> "high-level / not regurgitating code" property the user wants to keep.
> **Status:** Scaffolded — **not started**
> **Date opened:** 2026-05-01

---

## 0. Getting started (next agent, read this first)

This phase is a research-and-tune ticket, not a rewrite. The current
output is **good but suspect** — start by quantifying that suspicion
before changing anything.

### Recommended first session (≤2 hours)

1. **Read §1 and §2** to understand the symptom and the suspected
   cause path.
2. **Reproduce on at least two projects** of different sizes and
   compare raw worker output vs. final synthesized output (§3
   instrumentation). Don't tune until you see the actual compression
   ratio.
3. **Decide whether the issue is in the prompt, the synthesizer
   model choice, or the dedup heuristic** (§4 hypotheses). Most likely
   it's the synthesis prompt + model choice; keep the swarm
   architecture as-is.
4. **Open a small PR with one tuning knob** at a time (§5 backlog).
   Don't bundle.

### What this phase explicitly does NOT do

- Replace the swarm orchestrator or the per-module worker prompts
  (those produce diverse, high-volume raw concepts — that's working).
- Change the concept storage schema.
- Change UI rendering of concepts.
- Touch the antibody derivation pipeline (separate stage).

---

## 1. Problem statement

Running `seed_concepts_swarm` on the SourcePrep codebase
(1848 files, 491 modules) yields **13 concepts** in the final concept
store. The user's reaction:

> "Honestly 13 concepts is good — we only want high quality high-level
> concepts — and even still I think this needs more refinement."

Two readings of "13 is good":

1. **Quality over quantity is correct.** The synthesizer is
   appropriately deduplicating overlapping per-module observations
   into globally-meaningful concepts. The codebase is internally
   consistent, so there genuinely aren't 200 distinct *concepts*
   to extract — there are 13 ideas with many supporting examples.

2. **Compression is too aggressive.** With 491 module workers each
   producing 3–8 concepts (call it ~2,500 raw), collapsing to 13 is
   ~99.5% compression. Even after legitimate dedup we'd expect
   something in the 30–80 range for a codebase of this size and
   architectural variety.

The truth is probably between (1) and (2) — keep some compression
but not this much. The phase ticket is to figure out where.

---

## 2. Suspected cause path

`src/prep/core/concept_seeder.py:494-516` synthesis prompt:

```
"Below are concepts extracted from {N} parallel subsystem analyses…
1. DEDUPLICATE: merge concepts with similar titles or overlapping content.
   Prefer the more specific version.
2. CROSS-MODULE PATTERNS: identify concepts that span multiple
   subsystems and elevate them.
3. GLOBAL INVARIANTS: generate 3-5 high-level concepts about the
   codebase as a whole…
4. CLARIFYING QUESTIONS: generate 5-8 questions about areas where
   the 'why' is still unclear."
```

Three things in this prompt push toward over-compression:

1. **"Merge concepts with similar titles or overlapping content."**
   With Kimi-K2.6-style instruction following, "overlapping" gets
   interpreted broadly. Two concepts that share a topic but diverge
   on the specific *why* get merged into one less-specific concept.

2. **"Generate 3-5 high-level concepts about the codebase as a
   whole."** This caps the global-invariant set explicitly. The model
   takes the cap as a target rather than a floor.

3. **No explicit lower bound on the deduped output.** The prompt
   asks for global invariants to fit a 3-5 range, but doesn't ask
   for a target post-dedup count for module-scoped or cross-module
   concepts.

The synthesizer is also a single LLM call processing the full
worker-output blob. For 491 modules that's a *lot* of input to
compress; the model's natural response is to summarize aggressively.

---

## 3. Instrumentation needed before tuning

Don't tune blind. Before changing the prompt, capture:

1. **Per-run raw vs. final counts.** Add a debug log at the swarm
   synthesis boundary: `raw_workers=491, raw_concepts=N, final=13`.
   The `result.worker_results` already carries the raw outputs;
   `concept_seeder.py:588-601` walks them as a fallback.
2. **Per-category distribution.** `architecture | domain | product |
   epistemic | process | brand | security | technical | pattern |
   constraint | decision`. If the final 13 are 12 architecture and
   1 technical, the synthesizer is collapsing real diversity.
3. **Anchor coverage.** What percentage of files in the codebase
   are referenced by at least one concept's `anchors`? If <5% the
   synthesizer is throwing away the per-module specificity even
   when keeping the concept count low.
4. **Question count.** The user only sees concepts. The 5-8
   clarifying questions should also surface — verify they're being
   generated and stored (check `concept_store.save_question` for
   the test project).

A small `tools/concept_audit.py` script that dumps these metrics for
a given project would be the right starting point. Reuse the existing
swarm event log (`~/.local/share/sourceprep/logs/swarm/`) which
already records per-run worker outputs.

---

## 4. Hypotheses (test these in order)

### H1 — Synthesis prompt is too aggressive on dedup
**Test:** rewrite the dedup instruction to "merge ONLY when titles
are paraphrases of the same idea AND the why behind them is
identical. Keep concepts whose specifics differ even if the topic
overlaps." Also remove the "3-5 global invariants" cap; ask for "all
codebase-wide invariants the workers identified, however many."

**Risk:** swings back to "too many concepts."

### H2 — Synthesis model isn't suited for the volume
**Test:** when worker count is large (>50), shard the synthesis into
two passes — synthesize per architectural cluster (atlas segment),
then synthesize the cluster summaries. The final step has fewer
inputs and produces a richer set.

**Risk:** more LLM cost, longer wall time.

### H3 — Too few concepts per worker, not too few in synthesis
**Test:** check the raw `worker_results`. If workers themselves
return 1-2 concepts per module rather than 3-8, the worker prompt
is the bottleneck. Tweak per-module worker prompt to require
≥3 concepts.

**Risk:** noise; the 3-8 range is currently "as needed."

### H4 — Confidence threshold drops valid concepts silently
**Test:** check whether `concept_store.save_many` filters on a
confidence threshold. If yes, concepts at 0.5-0.7 confidence may be
dropped. Look at `_validate_parsed` in concept_seeder.py.

---

## 5. Backlog (one-tuning-knob-per-PR)

In rough priority order — finish §3 instrumentation first.

| ID  | Change                                                              | Risk |
| --- | ------------------------------------------------------------------- | ---- |
| T1  | Add concept-audit tool + per-run metrics logging                    | low  |
| T2  | Remove "3-5 global invariants" cap; ask for "however many emerge"   | low  |
| T3  | Tighten dedup instruction (paraphrase + same-why test)              | low  |
| T4  | Two-pass synthesis when worker count > 50                           | med  |
| T5  | Surface per-category distribution in the Concepts panel             | low  |
| T6  | Persist raw worker_results to disk for post-hoc analysis            | low  |
| T7  | Validate confidence-threshold filtering isn't silently dropping     | low  |

---

## 6. Out of scope for this phase

- Re-architecting the swarm orchestrator
- Changing storage schema or panel UI
- Antibody derivation tuning
- Concept lifecycle (status transitions: seed → approved → archived)
- Migration plan for projects whose concept set was generated under
  old prompts

---

## 7. Pointers

- Entry point:           `src/prep/core/concept_seeder.py:62 seed_concepts(...)`
- Swarm path:            `src/prep/core/concept_seeder.py:355 seed_concepts_swarm(...)`
- Synthesis prompt:      `src/prep/core/concept_seeder.py:494-516`
- Worker prompt:         `src/prep/core/concept_seeder.py:525-548`
- Storage:               `src/prep/services/concept_store.py`
- Stage worker:          `src/prep/services/pipeline/workers.py _concepts_worker`
- Live concept stats DB: `~/.local/share/sourceprep/prep_concepts.db`
- Swarm event log:       `~/.local/share/sourceprep/logs/swarm/`

## 8. Acceptance for "done"

When this phase ships, the SourcePrep test project should produce
**30-80 concepts** (not 13, not 500) with category diversity ≥6/11
and anchor coverage ≥20% of code files. A second test project
(PowerMate or Halley) should produce a similarly-shaped distribution
without re-tuning. The user should be able to read the final concept
list and feel "yes, that captures what's interesting about this
codebase," without seeing obvious near-duplicates.

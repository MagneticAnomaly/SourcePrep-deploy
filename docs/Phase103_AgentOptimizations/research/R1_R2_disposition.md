# R1 + R2 — Honest Disposition

**Date:** 2026-04-14
**Short answer:** Both R1 (context layout / position) and R2 (default budget) are **null-by-construction in the current atlas-mode harness**. Running them formally would waste compute without producing signal. Their real measurement requires an LLM-based eval layer we haven't built yet. This doc records the finding so a future session doesn't repeat the exercise.

## R1 — Context layout / position

### Claim under test
Sandwich layout (critical-start + knowledge-middle + critical-end) should outperform sorted-by-relevance and flat layouts, because agents have ~85–95% recall at the start and end of a context window but much lower in the middle (Chroma "Context Rot" research, "Lost in the Haystack" paper).

### Why this can't be measured in our current harness
Our scorer (`eval_runner.py::evaluate_query_atlas`) checks whether expected keywords and file paths appear as substrings in the atlas text. Substring matching is **position-invariant**: a keyword at position 0 and the same keyword at position 3000 both score the same. Running sandwich vs sorted vs flat through this scorer produces identical numbers by construction.

### What would make R1 measurable
A proper layout experiment requires measuring **agent recall**, not string presence. Options:

1. **LLM-based eval:** feed the assembled atlas + task to an LLM; ask it to answer; grade the answer. Now layout matters because LLM attention is position-biased.
2. **Needle-in-haystack harness:** plant a unique distinctive token at different positions in the atlas; measure whether the downstream agent recalls it. Standard methodology from the context-rot literature.

Both are substantial — they require LLM spend and adversarial prompt design. Out of scope for Phase 103 POC.

### Current default layout

`project_atlas_for_role` assembles content in score order (highest-score modules first). This is "sorted by relevance" by default. No conscious sandwich arrangement.

### Disposition
- **R1 is deferred to Phase 104** (or whenever an LLM-based eval layer lands).
- No formal Run-NN sweep produced.
- The "sandwich layout" recommendation from 05_RESEARCH_SURVEY is a hypothesis carried forward, not tested data.

### What we did informally observe (Run 02 + beyond)

The atlas output always starts with `[{Role} View]`, then `MODULES (N subsystems):` header, then module entries. That places the role-framing at the start, which aligns with Chroma's "critical constraints at start" guidance without us explicitly designing for it. We left this behavior as-is.

---

## R2 — Default budget

### Claim under test
Agents succeed on most tasks at 500–1500 initial-response tokens, with follow-up `codrag_search` calls for anything missing. Larger budgets (8K+) hurt via context rot.

### Why this can't be cleanly measured in our current harness

Similar issue: our scorer measures substring presence, which **monotonically improves** with more atlas content. More chars → more chances for keywords to appear → higher score. No context rot penalty. So a budget sweep in the current harness will always favor the largest budget.

### What we already know from Run 04 data

Even though we didn't run R2 as a dedicated sweep, the `atlas_chars` field on every Run 04 result already reveals the budget-score relationship:

```
Condition A (neutral): 3,840 chars → 55.6% avg
Condition B/eng:       3,482       → 48.8%
Condition B/fe:        2,968       → 48.7%
Condition B/arch:      2,887       → 45.9%
Condition B/sec:       2,289       → 45.7%
```

The correlation is directionally positive (more chars → more score) but weak. That's important: the role-projection logic already trims to `max_chars` per role (2500–4000 range), and the scores within that range vary more by **what** was included than by **how much**.

### What would make R2 measurable

Same as R1: an LLM-based eval. Budget effects on agent task-completion (not string-presence) require measuring actual agent output quality.

A cheap intermediate experiment: for a single query, project its best role at budgets 500 / 1500 / 3000 / 6000, feed each to a real LLM with the task, grade the answer. 4 LLM calls × 5 queries = 20 calls — affordable but out of this POC's wiring.

### Disposition
- **R2 is also deferred to Phase 104.**
- Budget sweep in the atlas-mode harness would produce monotonically-rising scores — null-by-construction.
- Current `max_chars` defaults (per-role, 1500–4000) are untouched. Calibration workstream may tune these further on a per-role basis.

---

## The shared root cause

Our Phase 103 harness was designed to measure **atlas content adequacy** (does it mention the expected files + keywords?), not **agent performance** (did the agent succeed at the task?). Content-adequacy is:

- order-invariant (layout doesn't matter)
- monotonic in size (bigger = more likely to contain the target substrings)
- cheap (pure SQLite + string ops)

Agent-performance measurement is:

- position-sensitive (where content sits in the context window affects recall)
- non-monotonic (too much content hurts)
- LLM-call-bounded (each eval sample costs real tokens)

These are different instruments. We built the cheaper one first and learned a lot from it (R3 knowledge-honing validation, R5 concept flywheel, R4 inference accuracy). R1 and R2 are the pieces that specifically require the other instrument.

## What stays valid from the research-survey framing

The Phase 103 research survey (`05_RESEARCH_SURVEY.md`) cited Chroma context-rot, Microsoft agent-skills progressive disclosure, and related work. Those findings **still apply** — they just can't be reproduced in our harness. The recommendations survive as design guidance:

- **Position-aware layout** — implement it anyway; measure later.
- **Progressive disclosure** — our per-role `max_chars` already does this implicitly via role-level budget.
- **Budget under the effective-context ceiling** — our 2.5K–4K range is well below any model's degradation knee.

No action item change. Just documented reasoning.

## When to revisit

- When Phase 104's LLM-eval layer lands (the "CodeRAG bench" style harness with real model calls grading real agent outputs), run R1 + R2 as the first experiments against it.
- Until then, R3 knowledge-honing remains the anchor result. Everything else is infrastructure.

---

**Summary of dispositions:**

| Phase 103 item | Status |
|---|---|
| R1 layout / position | **null-by-construction**; defer to Phase 104 LLM-eval harness |
| R2 default budget | **null-by-construction**; defer to Phase 104 LLM-eval harness |
| R3 knowledge-honing | **measured** (Run 04); **handed off** for calibration |
| R4 universal API | **shipped** (task param + IDF role inference, 66% soft precision) |
| R5 concept activation | **shipped** (10 actives, promotion script, clog diagnosed as missing assertions) |
| R6 temporal validity | **shipped** (2 new columns, idempotent migration) |
| R7 auto-observation | **shipped** (PostToolUse hook, 51ms p95, F0 exclusion filter) |
| R8 benchmark harness | **shipped** (the eval_runner extension itself) |

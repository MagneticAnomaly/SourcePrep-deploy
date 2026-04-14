# R2 — Progressive Disclosure Minimum

**Goal:** Determine the minimum context we can return by default that still lets the agent succeed.
**Time budget:** 1 week
**Decision at end:** default budget settings for `codrag()` per task type.

## Core question

Microsoft's agent-skills research reports **94.7% context savings** from staged delivery — but they're measuring *total* token consumption across many tasks in a session. Our case is different: a single `codrag()` call returns a single response. The question is: *what's the smallest initial response that still succeeds, with follow-up calls filling gaps as needed?*

## Hypothesis

**H1:** For most tasks, an initial response of 500–1500 tokens — containing only the task-critical constraints, the narrow file set, and the key concepts — succeeds without follow-up.

**H2:** Tasks that fail at small budgets fail in predictable categories (cross-module investigations, refactors spanning hub files) — those need larger default budgets; most don't.

**H3:** Follow-up `codrag_search()` calls from the agent are cheaper (in total cost) than pre-loading everything. Agentic retrieval > front-loading.

## Literature check

- **Microsoft agent-skills** — 4-stage staged delivery; measured gains on multi-skill sessions.
- **Anthropic building-agents-with-SDK** — "just-in-time" retrieval is the recommended pattern.
- **Codebase-Memory (arxiv 2603.27277)** — 83% answer quality at 10× fewer tokens; implies their scoped-first strategy is near-optimal.
- **Agentic RAG survey (arxiv 2501.09136)** — iterative retrieve-evaluate-re-retrieve pattern; latency trade-off.

Literature supports "serve small, let the agent ask again if needed." No one publishes the exact breakpoint.

## Experiment

Reuse R1's 20-task harness. New conditions focused on *progressive* delivery:

**Conditions:**
- **P1 — Minimal upfront:** 500 tokens, role-scoped; agent must follow up via `codrag_search` for anything else.
- **P2 — Moderate upfront:** 1500 tokens; moderate scope; agent may follow up.
- **P3 — Rich upfront:** 4000 tokens; full role-scoped atlas; follow-ups rare.
- **P4 — All at once:** 8000+ tokens; everything CoDRAG would consider relevant; no follow-up.

For each task, count total tokens across the whole interaction (initial + follow-ups + final answer).

**Measure:**
- Success rate.
- Total token cost (initial + follow-ups).
- Number of follow-up `codrag_search` calls.
- Wall time (follow-ups have latency cost).

## Expected findings

- P1 minimal succeeds on 60–75% of tasks with 1–2 follow-ups; total cost wins over P4.
- P2 moderate succeeds on 85–95%; fewest follow-ups; probably the sweet spot.
- P3 rich succeeds on ≥95% but costs 2–3× P2.
- P4 all-at-once either matches P3 (wasted tokens) or *underperforms* due to context rot (R1 territory).

If P2 clearly wins, our default shifts to "moderate upfront" (~1500 tokens scoped context) with well-documented follow-up encouragement.

## Decision framework

**Path 1 — Sharp sweet spot:** One budget clearly dominates. Make it the default. Expose as `codrag(budget="minimal|moderate|rich")` with moderate as default.

**Path 2 — Task-dependent:** Minimal wins for investigations, moderate for modifications, rich for refactors. Auto-detect task type from intent classification (already in `codrag_search`) and pick budget accordingly.

**Path 3 — Flat curve:** No meaningful difference. Pick the smallest budget that's sufficient (saves cost without hurting quality). Likely P2.

## Simplicity audit

The progressive-disclosure pattern has three sub-questions:
1. How big should the initial response be? (this experiment)
2. How does the agent know it *can* follow up? (belongs to R4 — universal API design)
3. What follow-up tools do they call? (already exists — `codrag_search`, `codrag_impact`)

We only need to solve #1 here. #2 is R4. #3 is shipped.

**If we frame this correctly, R2 is just "what's the right default budget."** Everything else is already there.

## Interaction with R1

R1 tells us *how to arrange* what we return. R2 tells us *how much*. Run R2 *after* R1 so we use the best layout when measuring the budget question; otherwise we conflate layout and budget effects.

**Sequencing note:** R1 pilot (1 day) → R1 full (4 days) → R2 (1 week). Results from R2 inform the final `codrag()` response spec.

## Success criteria

- ✅ Measured default budget(s) backed by the 20-task harness data.
- ✅ `codrag(budget=...)` parameter documented with task-type guidance.
- ✅ Clear statement of when follow-up `codrag_search` is expected vs. avoidable.

## Output artifact

`docs/Phase103_AgentOptimizations/research/R2_results.md`:
- Budget sweep data across all 20 tasks × 4 budgets.
- Cost breakdown: initial vs. follow-up tokens, latency impact.
- Default budget selection with rationale.
- Recommendation on whether to ship auto task-type detection or keep it manual.

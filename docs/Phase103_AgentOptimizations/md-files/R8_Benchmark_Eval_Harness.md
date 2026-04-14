# R8 — Benchmark & Eval Harness

**Goal:** Build a reusable evaluation harness that measures whether CoDRAG-scoped context makes agents better, and publish numbers.
**Time budget:** threads throughout Phase 103; 1 week focused build
**Decision at end:** public benchmark we can cite, replicable by customers.

## Core question

Scrutiny (06) identified "no eval harness" as a critical gap. Every other sub-phase depends on measurement: R1 needs a task harness, R2 needs budget comparisons, R3 needs the 2×2 factorial. **Instead of building these one-off, build the harness once and use it everywhere.** At the end, we have a public number: *"CoDRAG-scoped context achieves X% higher task success at Y× fewer tokens compared to baseline."*

## Hypothesis

**H1:** A 30-task harness against CoDRAG's own repo, rubric-scored, is sufficient to produce credible numbers.

**H2:** Our scoped-context advantage is in the 2–10× token reduction range at comparable quality — consistent with the Codebase-Memory paper (83% quality, 10× tokens) and our own 49×/120× external references.

**H3:** Publishing reproducible numbers is a stronger moat than architectural elegance. A competitor can't easily refute data.

## Literature check

- **Codebase-Memory paper (arxiv 2603.27277)** — directly comparable benchmark. We should replicate their methodology.
- **LongMemEval** — used by Zep/Mem0 for memory comparisons. Could adapt.
- **PersonaGym (ACL 2025)** — benchmark for persona effectiveness. Reference for R3.
- **SWE-Bench** — industry-standard for code-agent evaluation. Probably too heavy for us but worth comparing.

## Harness design

**Components:**

1. **Task catalog** — 30 tasks against CoDRAG's repo:
   - 10 bug fixes (given a failing test, make it pass)
   - 10 investigations (answer a question about the codebase)
   - 10 modifications (implement a small feature)

   Each task has:
   - Objective rubric (test passes / correct file path returned / diff compiles).
   - Optional quality rubric (5-point scale: idiomatic, documented, concise).
   - Expected difficulty (easy/medium/hard).

2. **Condition runner** — executes a task under a specified context condition:
   - Baseline A: no CoDRAG, flat `ls + cat` of relevant dirs.
   - Baseline B: CoDRAG full atlas (legacy behavior).
   - Treatment C: CoDRAG scoped context (v2 API from R4).
   - Oracle D: minimal hand-picked context that contains the answer (upper bound).

3. **Metric collector** — for each run:
   - Success (objective rubric pass/fail).
   - Quality score (0–5, human or LLM-judged).
   - Total tokens (prompt + completion + follow-ups).
   - Latency (wall clock).
   - Tool-call count.
   - Hallucination count (file/symbol references that don't exist).

4. **Reporter** — aggregates runs into a leaderboard:
   ```
   Condition    Success   Quality   Tokens   Latency   Hallucinations
   A baseline   55%       2.8       12000    45s       1.2/task
   B full-atlas 72%       3.4       18000    52s       0.6/task
   C scoped     74%       3.5        4500    38s       0.4/task  ← target
   D oracle     82%       3.9        1200    22s       0.1/task  ← upper bound
   ```

## Build plan

**Week 1 — harness infrastructure:**
- Task catalog YAML schema (30 tasks).
- Condition runner (4 conditions).
- Metric collector.
- Reporter.
- CI hookup — harness runs nightly on main.

**Ongoing — task catalog growth:**
- Every time we find a task where CoDRAG "should" have helped but didn't, add it to the catalog.
- The catalog is a living asset, not a one-time artifact.

## Initial measurements

Run the harness with:
- Model: Sonnet 4.6 (cost), spot-checks with Opus 4.6.
- Trials: 3 per task × condition (90 runs per condition, 360 total per full sweep).
- Frequency: full sweep weekly during Phase 103; daily deltas on the 5-task smoke subset.

Expected initial results:
- **Success:** C ≥ B by 1–3 points (scoping modest improvement at baseline quality).
- **Quality:** C ≈ B (no regression).
- **Tokens:** C significantly lower than B (3–5× reduction likely).
- **Hallucinations:** C lower (less irrelevant context to hallucinate from).

**If C ≤ A:** major red flag. CoDRAG actively hurts. Investigate before shipping anything.

## Public publication

After the harness stabilizes (2–3 weeks of runs), publish:

- Methodology writeup as part of CoDRAG docs / website.
- Numbers table (leaderboard above, with real data).
- Reproducibility: anyone can clone CoDRAG repo, run `pytest tests/benchmark/`, get same numbers.
- Comparison to published works (Codebase-Memory's 83%/10×; our equivalent).

This is the marketing moat — not architectural claims, but *reproducible numbers*.

## Simplicity audit

The eval harness can easily become a second product. Keep it tight:

- No UI — it's a pytest run plus a markdown report.
- No cloud scoring service — local LLM calls, cached.
- No ML-based quality judging (initially) — explicit rubrics + occasional human spot-check.
- 30 tasks is enough. Don't grow to 300 before we have 30 that work.

If the harness takes more than 2 weeks to build initially, we've over-scoped.

## Connection to other sub-phases

- **R1, R2, R3** all run through the harness. The harness is the shared infrastructure.
- **R4** v2 API is tested via the harness (condition C uses v2).
- **R5, R6, R7** feed content *into* the harness's scoped condition.
- **R8 itself** produces the reports cited in every other sub-phase's results.

**R8 is a meta-sub-phase.** It's the measurement layer under everything else.

## Decision

**Path 1 — Harness works, numbers support CoDRAG:** publish. Become the eval reference everyone cites.

**Path 2 — Harness works, numbers are mediocre:** fix CoDRAG until numbers improve. Do not publish until improved. Harness is our internal feedback loop.

**Path 3 — Harness has bugs / tasks poorly designed:** rebuild tasks; smaller is better than bad. Ship 10 good tasks before 30 mediocre ones.

## Success criteria

- ✅ 30 tasks with objective rubrics.
- ✅ 4 conditions runnable end-to-end.
- ✅ Full sweep in under 2 hours (budget constraint).
- ✅ Reproducible: `make benchmark` produces the leaderboard.
- ✅ Public numbers published (after internal validation).
- ✅ Harness is reused by every other sub-phase.

## Output artifact

`docs/Phase103_AgentOptimizations/research/R8_results.md`:
- Harness design document.
- Task catalog (or link).
- Leaderboard from most recent run.
- Trend data over Phase 103.
- Delta report when a sub-phase change lands.

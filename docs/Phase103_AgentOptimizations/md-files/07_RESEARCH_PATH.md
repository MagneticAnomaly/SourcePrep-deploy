# 07 — Research Path: Sub-Phases for Phase 103

## Philosophy shift — the thesis simplifies

Reading the research survey (05) and scrutiny (06) alongside our own instinct: **we are not building agents. We are scoping context.**

The agent already exists — Claude Code, Cursor, Windsurf, Paperclip-dispatched agents, OpenClaw agents. Each one has its own context window, its own reasoning, its own tools. What all of them lack is the ability to ask *"for what I'm about to do, what's the minimum context that makes me good at it?"*

Our existing `codrag(role="rolename")` call, built for Paperclip, is the right shape — it just isn't universal yet. Every other feature we sketched in 02 / 04 is either (a) a different flavor of the same primitive, (b) infrastructure supporting it, or (c) emission theater we should drop.

### What this reframing eliminates

From the original roadmap, these features get **cut or demoted**:

- **F1 role-projected subagents (as file emission):** No more `.claude/agents/*.md` generation. The IDE agent calls `codrag(role="security", task="...")` and receives scoped context inline. No files, no drift, no staleness.
- **Per-target emitters (Paperclip/OpenClaw/Claude Code/Cursor):** Down to one MCP call. The client is the agent; CoDRAG answers.
- **Phase 88's three-file output (AGENTS.md / SOUL.md / KNOWLEDGE.md) as required artifacts:** Still useful as optional legacy output for clients that can't call MCP, but not the primary surface.
- **SOUL.md persona generation:** Research shows persona prompting has mixed-to-negative effects. We don't write "be paranoid, be terse" — the agent decides its own voice. We give it *knowledge scope*, not personality.

### What this reframing keeps and elevates

- **The unified `codrag()` call** (role + task + budget) becomes the primary product surface.
- **Role vectors, concept graph, antibodies** stay — they're the inputs to scoping, not user-facing outputs.
- **Exclusion policy (F0)** stays — even if we don't *emit* agent files, users still have them, and we still mustn't index them.
- **Hooks (F3)** stay — but as enforcement for antibodies, not content delivery.
- **Automatic observation capture (F11)** stays — the only way the graph grows without requiring agent initiative.
- **Eval harness (F13)** stays — we have to measure context-scoping quality.
- **Temporal validity (F12)** stays — old concepts shouldn't pollute current context.

### The new product sentence

> **CoDRAG serves minimal, maximally-relevant context to any agent, indexed by role and task, over MCP. Agents stay in their host; context comes from us.**

That's it. Everything else is infrastructure for that one API.

## The research question stack

Before we commit to *any* new feature in Phase 103, we need empirical answers to a stack of questions. Each sub-phase is a focused investigation ending in a design decision — **not a build plan**.

Structure: 8 sub-phases, ordered by dependency. Each runs 1–2 weeks. Most end with a kill/revise/ship decision. Ship only after the research says ship.

```
R1 Context Rot & Position          ──────┐
R2 Progressive Disclosure Minimum  ──────┤── foundational
R3 Role Scoping vs Generic         ──────┘
                                         │
                                         ▼
R4 Universal Client API  ◄───────────────┤── interface
R5 Concept Activation    ◄───────────────┤── flywheel input
                                         │
                                         ▼
R6 Temporal Validity     ◄───────────────┤── decay
R7 Auto Observation      ◄───────────────┤── growth
R8 Benchmark & Eval      ◄───────────────┴── measurement (threads through all)
```

Each sub-phase has its own detailed doc (R1_*.md through R8_*.md). This document is the map.

## Sub-phase summary table

| Sub-phase | Core question | Time | Gate decision |
|---|---|---|---|
| **R1** Context Rot & Position | Where in our scoped context does an agent actually retrieve from? | 1 wk | Template layout standard |
| **R2** Progressive Disclosure | What's the minimum we can serve and still get the task done? | 1 wk | Budget defaults |
| **R3** Role Scoping vs Generic | Does role-scoped context beat full-atlas context on real tasks? | 2 wk | Keep/kill role projection |
| **R4** Universal Client API | What's the simplest MCP surface that any client can call? | 1 wk | API v2 spec |
| **R5** Concept Activation | Why 0/366 active? What's the minimum viable promotion pipeline? | 2 wk | Auto vs. manual promotion |
| **R6** Temporal Validity | Do concepts decay? How much? What's the minimum temporal model? | 1 wk | Add or don't |
| **R7** Automatic Observation | Can PostToolUse hooks grow the graph without agent help? | 1 wk | Ship or skip |
| **R8** Benchmark & Eval | What does "scoped context makes agents better" measure as? | threads throughout | Benchmark publication |

## Method — how we'll conduct each sub-phase

Every sub-phase follows a five-step template:

1. **Hypothesis** — what we currently believe, stated falsifiably.
2. **Literature check** — 2–4 sources; what does existing work claim?
3. **Experiment** — the smallest test that could change our mind. Usually run against our own CoDRAG codebase (dogfood).
4. **Measurement** — explicit metrics; no hand-waving.
5. **Decision** — ship / revise / kill, with a one-paragraph rationale.

Every sub-phase produces an artifact in `docs/Phase103_AgentOptimizations/research/R<n>_results.md` containing all five steps. That artifact is the durable record, not the feature code.

## Principles guiding every sub-phase

1. **Elegance is the goal, not the constraint.** If a sub-phase's simplest answer is "don't do this feature," that's the right answer.
2. **Measure before you build.** No sub-phase greenlights a feature until a measurement exists that justifies it.
3. **Dogfood the experiments.** CoDRAG has its own repo, its own atlas, its own 366 concept seeds. That's our test bed. If we can't solve the problem on our own code, we won't solve it on customers'.
4. **Reevaluate at the end of each sub-phase.** Conclusions from R1 may change R2's hypothesis. Re-read prior conclusions before starting each new one.
5. **Simplicity audit per sub-phase.** At the end, ask: *"Could we have answered this with less code / fewer concepts / a smaller API?"* If yes, adjust.

## The end state

After all 8 sub-phases:

- We have measured answers, not intuitions, for every assumption in Phase 103.
- We have a single elegant MCP-level contract: `codrag(role, task, budget)` returns context.
- We have a published benchmark showing what scoped context does to agent performance.
- We know which of the original Phase 103 features to ship and which to drop.
- We have a clean, simple story: *"we scope context, we don't build agents."*

## Cross-references

- `R1_Context_Rot_and_Position.md` — detailed plan, R1
- `R2_Progressive_Disclosure_Minimum.md` — detailed plan, R2
- `R3_Role_Scoping_Validation.md` — detailed plan, R3
- `R4_Universal_Client_API.md` — detailed plan, R4
- `R5_Concept_Activation.md` — detailed plan, R5
- `R6_Temporal_Validity.md` — detailed plan, R6
- `R7_Automatic_Observation.md` — detailed plan, R7
- `R8_Benchmark_Eval_Harness.md` — detailed plan, R8

Each sub-phase doc is self-contained. Read in order; reevaluate priors as findings accumulate.

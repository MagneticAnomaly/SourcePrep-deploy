# Researcher — Topic selection

**File:** `src/prep/agents/researcher/prompts.py:10-53` (render at 10, SYSTEM at 50)
**Symbols:** `TOPIC_SELECTION_SYSTEM`, `render_topic_selection_prompt`
**Invoked by:** Researcher Agent — first pass after running an audit
**Pipeline stage:** agent (researcher)
**Output schema:** structured JSON list of selected topics with priority + rationale
**Status:** baseline

## Purpose
Picks high-impact audit findings to research. The triage step that decides "out of 50 findings, these 5 deserve deep investigation."

## Grounding (inputs)
- Full audit-finding list with severities
- Codebase atlas (for context on what's hub vs leaf)
- Optional: user-specified priority hints

## Output schema
JSON list. Each: `{topic, source_findings[], priority, rationale}`.

## Known issues / hypotheses
- **Severity-vs-impact mismatch**: severity (lint scoring) ≠ impact (does fixing this matter?). Hypothesis: the prompt should explicitly distinguish and prioritize by impact, with severity as a tiebreaker.
- **Topic granularity**: a "topic" can be one finding or a cluster. Without a defined granularity, outputs vary call-to-call. Worth specifying.
- **Top-N cap**: without an explicit cap, outputs may pick "top 20" — too many. Hypothesis: add explicit `select_at_most: 5` to the prompt.

## Snapshot 2026-05-17
- Prompt source SHA: `3b0ba9b80202`
- Outputs captured: TBD

## Iterations

### 2026-05-19: A5 — structural review + corrects page stub schema

**Type:** analysis-only (no PowerMate output — Researcher agent has never been run against PowerMate)

**Read materials:**
- `TOPIC_SELECTION_SYSTEM` + `render_topic_selection_prompt` (`agents/researcher/prompts.py:10-51`).

**Correction to page stub (line 19) — output schema is incorrect.** Page says: `{topic, source_findings[], priority, rationale}` (4 fields). Actual prompt (line 43-46) asks for 2 fields per object:

```
- "finding_id": the ID from the list above
- "rationale": one sentence explaining why this topic is worth researching
```

Plus the prompt asks the model to select EXACTLY `max_topics` topics (or fewer if fewer findings exist) — `max_topics` is a parameter, not hardcoded. Page open-question #1 about "Should the prompt accept a quota parameter (top-3, top-5, top-10)?" is already answered — yes, it does (`max_topics`).

Update page schema to: `{finding_id, rationale}` + "exactly N selected, parameterized via `max_topics`".

**Finding #1 — strong points (no iteration needed):**

1. **Output discipline good:** `TOPIC_SELECTION_SYSTEM` says "Output ONLY valid JSON — a JSON array of objects. No markdown, no explanations outside the JSON." This is the right anti-preamble pattern (compare to my A3 audit-prompts fix).
2. **Prioritization criteria are explicit:** "Prioritize by: 1. Impact... 2. Severity... 3. Actionability..." — gives the model concrete criteria to apply, not just "pick the best ones".
3. **Severity ordering codified:** "P0 > P1 > P2 > P3" — explicit total order, no ambiguity.
4. **Parameterized cap:** `max_topics` is a runtime parameter; page hypothesis #3 about needing an explicit cap is already satisfied.

**Finding #2 — minor: `rationale` is unbounded.** The schema says "one sentence" inline, but no character cap. Without enforcement, the model may emit multi-sentence rationales when it has more to say. Low-risk drift; not worth shipping without observed output.

**Finding #3 — `Actionability — can a clear fix plan be formulated?` is a circular criterion.** The downstream stage IS the plan formulation. The model is asked to judge "is this researchable?" before doing the research. In practice this means biasing toward well-bounded findings (single file, clear root cause), away from cross-cutting / architectural ones. May produce systematically narrow topic selection. Page hypothesis #1 about "severity-vs-impact mismatch" is related but not identical — the actionability criterion is the real source of the bias.

Worth recognizing as a design choice (the agent is meant to produce shippable plans, so unactionable topics ARE worth deprioritizing) but flagging that it shapes which findings get research attention.

**Finding #4 — no preamble-leakage risk** because system prompt requires JSON-only output. Unlike RESEARCH_SYSTEM (next sibling) which permits markdown prose and is exposed to the preamble-leakage failure I documented in audit-inventory/tech-debt.

**Verdict:** **analysis (no edit shipped).** Two deferred actions:

1. **Update page stub** to reflect actual 2-field schema with `max_topics` parameter.
2. **Capture PowerMate output** — needs Researcher agent invocation against an audit-completed project. PowerMate has audit findings (from A2 captures); could be the trigger.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (explicit prioritization criteria > vague "pick best").
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §2 (few-shot would help — currently zero examples).

**Cross-references:** [`researcher-research.md`](./researcher-research.md), [`researcher-plan.md`](./researcher-plan.md) (next stages in the 3-step pipeline).

## Open questions
- Should the prompt accept a quota parameter (top-3, top-5, top-10)?
- Does topic-selection use `prep_impact` data implicitly via grounding, or should it call it explicitly?

## Cross-references
- Sibling: [researcher-research](./researcher-research.md), [researcher-plan](./researcher-plan.md)
- Memory: `project_audit_runner_schema.md`

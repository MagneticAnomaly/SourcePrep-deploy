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

_(none yet)_

## Open questions
- Should the prompt accept a quota parameter (top-3, top-5, top-10)?
- Does topic-selection use `prep_impact` data implicitly via grounding, or should it call it explicitly?

## Cross-references
- Sibling: [researcher-research](./researcher-research.md), [researcher-plan](./researcher-plan.md)
- Memory: `project_audit_runner_schema.md`

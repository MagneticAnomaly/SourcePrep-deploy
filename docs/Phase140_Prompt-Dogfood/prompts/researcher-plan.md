# Researcher — Plan formulation

**File:** `src/prep/agents/researcher/prompts.py:102-134` (render at 102, SYSTEM at 133)
**Symbols:** `PLAN_FORMULATION_SYSTEM`, `render_plan_formulation_prompt`
**Invoked by:** Researcher Agent — final pass per topic
**Pipeline stage:** agent (researcher)
**Output schema:** structured JSON plan (steps with file targets, dependencies, verification criteria)
**Status:** baseline

## Purpose
Converts research output (root cause, fix approach) into a structured implementation plan. The actionable handoff to whoever (human or other agent) will execute.

## Grounding (inputs)
- One topic's research output (from `researcher-research`)
- Atlas context for affected segments
- Codebase conventions (if captured)

## Output schema
JSON: `{steps: [{description, files[], dependencies, verification}]}`. Each step is concrete enough to implement directly.

## Known issues / hypotheses
- **Step granularity drift**: "1 step = ?" is undefined. Outputs vary from 3 mega-steps to 20 micro-steps. Hypothesis: specify "each step ends with a runnable verification" to anchor granularity.
- **Verification criteria fabrication**: "verify with tests" is vague. Better: "after this step, `pytest tests/foo.py::test_bar` must pass." Specific verification is the marker of a good plan.
- **Dependency edges**: cross-step dependencies are often missing or wrong. Linear plans get written even when steps could run in parallel.

## Snapshot 2026-05-17
- Prompt source SHA: `3b0ba9b80202`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- Should verification criteria be required to name a specific command (test, script, manual check)?
- Should the prompt output a DAG of step dependencies, not just a linear list?

## Cross-references
- Sibling: [researcher-topic](./researcher-topic.md), [researcher-research](./researcher-research.md)
- Compare with superpowers writing-plans skill (external) for shape inspiration

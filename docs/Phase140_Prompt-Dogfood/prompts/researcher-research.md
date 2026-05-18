# Researcher — Research

**File:** `src/prep/agents/researcher/prompts.py:54-101` (render at 54, SYSTEM at 97)
**Symbols:** `RESEARCH_SYSTEM`, `render_research_prompt`
**Invoked by:** Researcher Agent — once per selected topic
**Pipeline stage:** agent (researcher)
**Output schema:** structured JSON — root cause, fix approach, risks, effort estimate
**Status:** baseline

## Purpose
Researches a solution to one topic. Produces root-cause analysis + proposed fix + risks + effort estimate. The "investigate and recommend" step before plan formulation.

## Grounding (inputs)
- One topic (from `researcher-topic` output)
- Relevant file content (audit-flagged files)
- Trace-graph context
- Optional: prior fix attempts

## Output schema
JSON: `{root_cause, fix_approach, risks[], effort: low|medium|high}`.

## Known issues / hypotheses
- **Effort estimate fabrication**: low/medium/high effort estimates are notoriously unreliable from LLMs. Hypothesis: replacing with concrete signals ("touches N files, requires schema change Y/N") would be more useful than the categorical estimate.
- **Single-fix bias**: prompts asking for "the fix" produce one fix even when multiple are reasonable. Worth A/B testing "propose 2-3 alternatives with tradeoffs."
- **Risk-list inflation**: outputs may produce a long generic risk list ("might break existing tests"). Specific risks (with concrete examples) are more useful than generic ones.

## Snapshot 2026-05-17
- Prompt source SHA: `3b0ba9b80202`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- Should effort be replaced with concrete signals (file count, schema change Y/N, test impact)?
- Should the prompt produce multiple fix alternatives by default?

## Cross-references
- Sibling: [researcher-topic](./researcher-topic.md), [researcher-plan](./researcher-plan.md)

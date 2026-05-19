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

### 2026-05-19: A5 — structural review + corrects page stub schema

**Type:** analysis-only (no PowerMate output)

**Read materials:**
- `PLAN_FORMULATION_SYSTEM` + `render_plan_formulation_prompt` (`agents/researcher/prompts.py:102-134`).

**Correction to page stub (line 19) — output schema is completely different from what's documented.** Page says `{steps: [{description, files[], dependencies, verification}]}` — a steps-array shape with per-step dependency edges. Actual prompt (line 122-128) asks for:

```
- "root_cause": string — one paragraph
- "fix_steps": array of strings — ordered list of concrete implementation steps
- "effort": "small" | "medium" | "large"
- "risk": "low" | "medium" | "high"
- "testing_strategy": string — how to verify the fix works
```

5 flat fields, no per-step structure, no dependencies graph, no per-step verification. The page's "steps array with description/files/dependencies/verification per step" was drafted from imagination, not from reading the prompt. Page schema needs full rewrite.

Open-question #2 (line 36: "Should the prompt output a DAG of step dependencies, not just a linear list?") is asking the right question — currently it's a flat string array with no dependency edges or per-step verification. Adding those would be a substantive enhancement, not a small edit.

**Finding #1 — `fix_steps` is undefined granularity.** Page hypothesis #1 ("Step granularity drift") is correct — schema is "array of strings, ordered" with no constraint on step size. Outputs could be 3 mega-steps ("refactor the controller") or 20 micro-steps ("change line 47 in file X"). Without "each step ends with a runnable verification" anchor, granularity drifts.

The prompt's example ("Extract shared types from core/models.py into core/shared_types.py") is mid-grained — a paragraph-sized intervention with a clear before/after. If this is the intended granularity, the prompt should say so explicitly: "Each step should be a single mid-grained intervention that can be reviewed as one diff (typically modifying 1-3 files, no more than ~50 lines)."

**Finding #2 — `effort` and `risk` enums lack passing-test definitions.** Compare to the named-tier rubric in concept-t3-refine prompt where each tier is defined as a passing test:

> T1 — pattern observed in code; no enforcement. Test: a reader could find counter-examples in the same codebase that don't follow the pattern, and nothing prevents them.

The Researcher plan's effort+risk enums have no equivalent. "small / medium / large" effort is even less anchored than `researcher-research`'s time-range version. Recommend:

```diff
-- "effort": "small" | "medium" | "large"
+- "effort": one of:
+    "small" — single file, < 50 line diff, no schema changes, no test refactor
+    "medium" — 2-3 files, < 200 line diff, may add tests
+    "large" — 4+ files OR schema change OR test refactor needed
-- "risk": "low" | "medium" | "high"
+- "risk": one of:
+    "low" — pure refactor, no behavior change, covered by existing tests
+    "medium" — behavior change in single subsystem; tests need additions
+    "high" — cross-subsystem behavior change OR no test coverage OR public API change
```

**Finding #3 — JSON output discipline is correct.** `PLAN_FORMULATION_SYSTEM`: "Output ONLY valid JSON — a single JSON object. No markdown, no explanations outside the JSON." This is the right anti-preamble pattern for JSON output. No preamble-leakage risk.

**Finding #4 — `testing_strategy` is a single string without structure.** Could be enriched: `{verification_commands: ["pytest tests/foo.py::test_bar", "manual: confirm UI renders X"], regression_targets: [files-to-spot-check]}`. But that's a schema extension, not a small edit.

**Verdict:** **analysis (no edit shipped).** Three deferred actions:

1. **Update page stub** to match actual 5-field flat schema.
2. **Add passing-test definitions to effort + risk enums** — high-value, low-risk edit. Could ship now.
3. **Capture PowerMate output** to validate. Effort/risk distributions across multiple captured runs would show whether the enums are being used distinctly or all defaulting to "medium".

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §7 (named-tier rubrics with passing tests — same pattern from concept-t3-refine applies here).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (concrete examples for each enum value).

**Cross-references:** [`researcher-topic.md`](./researcher-topic.md), [`researcher-research.md`](./researcher-research.md), [`concept-t3-refine.md`](./concept-t3-refine.md) (proven passing-test enum pattern).

## Open questions
- Should verification criteria be required to name a specific command (test, script, manual check)?
- Should the prompt output a DAG of step dependencies, not just a linear list?

## Cross-references
- Sibling: [researcher-topic](./researcher-topic.md), [researcher-research](./researcher-research.md)
- Compare with superpowers writing-plans skill (external) for shape inspiration

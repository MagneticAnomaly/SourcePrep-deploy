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

### 2026-05-19: A5 — structural review + corrects page stub schema + preamble-leakage risk

**Type:** analysis-only (no PowerMate output)

**Read materials:**
- `RESEARCH_SYSTEM` + `render_research_prompt` (`agents/researcher/prompts.py:54-99`).

**Corrections to page stub:**

- **Line 7 (Output schema):** Page says "structured JSON — root cause, fix approach, risks, effort estimate." Actual prompt outputs **Markdown prose** with 5 sections (not JSON):
  1. Root cause
  2. Solution approach
  3. Step-by-step procedure
  4. Risks
  5. Effort estimate
  
  System prompt explicitly: "Output clear markdown prose — no JSON wrapping."

- **Line 20 (effort enum):** Page says `effort: low|medium|high`. Actual prompt asks for `small | medium | large` with explicit ranges: "small (< 1 hour), medium (1-4 hours), or large (> 4 hours)."

- **Field name:** Page says "fix_approach"; actual prompt section is "Solution approach".

Update page schema + open-question #1 (which is moot — effort is already operationalized with time ranges, not bare enums).

**Finding #1 — preamble-leakage risk (HIGH).** System prompt: "Output clear markdown prose — no JSON wrapping." This says what NOT to wrap in, but does NOT say "no preamble before the first section heading." This is the same gap I identified in audit-inventory and audit-tech-debt prompts (A3), which produced 57% and 80% preamble respectively.

**Recommendation if iterating:** add the anti-preamble clause that I shipped for the audit family (commit `76d0b119`):

```diff
 RESEARCH_SYSTEM = """You are an expert software engineer analyzing codebase issues.
 You produce detailed, actionable technical analysis grounded in the provided code context.
-Output clear markdown prose — no JSON wrapping."""
+Output clear markdown prose — no JSON wrapping.
+Output ONLY the Markdown analysis — no preamble, no internal planning notes, no "The user wants..." restatements, no thinking-out-loud paragraphs before the first section heading. Start your output directly with "## Root cause"."""
```

Defensive ship — 90% confidence this is needed because RESEARCH_SYSTEM matches the failure-shape of audit-inventory exactly (markdown output, no anti-preamble clause). The cost is one line; the upside is preventing the same 57-80% preamble waste.

Worth shipping in the same coordinated commit as the rest of the agent prompts after A5 review, OR shipping now and letting the rest follow.

**Finding #2 — effort estimate is well-operationalized.** "(< 1 hour)", "(1-4 hours)", "(> 4 hours)" are concrete time ranges — better than bare low/medium/high. Page hypothesis #1 ("replacing with concrete signals would be more useful") is partly addressed by the time ranges, but doesn't include touched-file count or schema-change-Y/N hints. Worth a small enhancement.

**Finding #3 — "Be specific. Reference actual files and code patterns from the context above." is the right anti-vague clause.** Grounding §9 (Caulfield) — anchoring instructions in provided grounding suppresses fabrication. Good as-is.

**Finding #4 — Step-by-step procedure section asks for "Ordered list of specific code changes" but doesn't constrain step granularity.** Page hypothesis on `researcher-plan` flags this for the next-stage prompt; same risk lives here.

**Verdict:** **analysis (no edit shipped this iteration).** Three deferred actions:

1. **Update page stub** for actual schema (Markdown, 5 sections, effort with time ranges).
2. **Add anti-preamble clause to RESEARCH_SYSTEM** — ship in coordinated agent-prompts commit (after A5 review).
3. **Capture PowerMate output** before further iteration.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (explicit response-shape constraints — A3 commit `76d0b119` proves the anti-preamble clause works on the audit family).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (anti-fabrication via grounding anchor — "Reference actual files... from the context above").

**Cross-references:** [`researcher-topic.md`](./researcher-topic.md), [`researcher-plan.md`](./researcher-plan.md), [`audit-inventory.md`](./audit-inventory.md) (proven anti-preamble pattern to port).

## Open questions
- Should effort be replaced with concrete signals (file count, schema change Y/N, test impact)?
- Should the prompt produce multiple fix alternatives by default?

## Cross-references
- Sibling: [researcher-topic](./researcher-topic.md), [researcher-plan](./researcher-plan.md)

# Audit — Architecture analysis

**File:** `src/prep/core/audit/prompts.py:44-78`
**Symbols:** `ARCHITECTURE_ANALYSIS_SYSTEM`, `ARCHITECTURE_ANALYSIS_PROMPT`
**Invoked by:** `src/prep/core/audit/synthesizer.py:_gen_architecture`
**Pipeline stage:** audit (parallel since Phase 96F)
**Output schema:** structured markdown — module dependency flow, bottlenecks, layering violations
**Status:** baseline

## Purpose
Generates the architecture-analysis page of the audit report: how modules depend on each other, where bottlenecks live, what layering violations exist.

## Grounding (inputs)
- Module / cluster summaries (from `batch-cluster`)
- Import graph (edge list, in/out degrees)
- Identified cycles
- Cross-cutting concerns

## Output schema
Markdown with sections: dependency flow, bottlenecks, violations. Includes a textual dependency description (no visual diagram from the LLM).

## Known issues / hypotheses
- **Cycle hallucination**: LLM may name cycles that don't exist or miss obvious ones. Hypothesis: ground the prompt with the actual cycle list (already done via `prep_audit` upstream?) and instruct it to "explain these cycles only, do not invent new ones."
- **Bottleneck = high in-degree fallacy**: high in-degree (many imports) ≠ bottleneck in many architectures (e.g., a `types.ts` is high-in-degree but desired). Worth verifying outputs distinguish "expected hub" from "accidental bottleneck."
- **Layering vocabulary**: violations are framed in terms of architectural layers. Without a fixed layer vocabulary (see batch-epi-code), outputs invent layer names per call. Hypothesis: share the layer taxonomy across audit + epistemic prompts.

## Snapshot 2026-05-17
- Prompt source SHA: `d129188714f2`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- Should the architecture page link to `prep_impact` for each named bottleneck?
- Is there value in adding ASCII dependency diagrams, or are they noise?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-gaps](./audit-gaps.md), [audit-inventory](./audit-inventory.md), [audit-tech-debt](./audit-tech-debt.md)
- Memory: `project_audit_runner_schema.md`

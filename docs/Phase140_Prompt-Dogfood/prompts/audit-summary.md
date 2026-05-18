# Audit — Summary

**File:** `src/prep/core/audit/prompts.py:9-42`
**Symbols:** `AUDIT_SUMMARY_SYSTEM`, `AUDIT_SUMMARY_PROMPT`
**Invoked by:** `src/prep/core/audit/synthesizer.py:_gen_summary`
**Pipeline stage:** audit (parallel since Phase 96F)
**Output schema:** structured markdown — health score, key findings, recommendations
**Status:** baseline

## Purpose
Generates the top-level audit summary document: health score (0-100), key findings, recommended actions. This is the page users see first when opening an audit report.

## Grounding (inputs)
- Structural metrics (coupling, cycles, dead code, complexity)
- Concept-violation findings
- Tech-debt indicators
- Cross-cutting concerns

## Output schema
Markdown with prescribed sections. Health score is parseable from a labeled line; rest is prose.

## Known issues / hypotheses
- **Schema divergence** (memory: `project_audit_runner_schema.md`). `run_audit` returns `AuditResult`; `run_health_scan` returns `List[ActionItem]`; they're not swappable. The summary prompt assumes which inputs? Verify the grounding format matches the `AuditResult` shape.
- **Health score gaming**: a 0-100 score is a tempting target for "make the number go up" without addressing root causes. Hypothesis: replacing the score with a tier (good/concerning/critical) would reduce gaming and force qualitative reasoning.
- **Recommendation generality**: outputs often produce recommendations that are accurate but generic ("reduce coupling in X"). Worth checking whether the prompt asks for specific next steps with file/line refs.

## Snapshot 2026-05-17
- Prompt source SHA: `d129188714f2`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- Should the health score be replaced with a tier + brief justification?
- Does the prompt explicitly request file/line refs in recommendations? (If not, that's a candidate iteration.)

## Cross-references
- Sibling: [audit-architecture](./audit-architecture.md), [audit-gaps](./audit-gaps.md), [audit-inventory](./audit-inventory.md), [audit-tech-debt](./audit-tech-debt.md)
- Memory: `project_audit_runner_schema.md`, `project_audit_spaghetti_migration.md`
- Phase 122 — Feature Utilization Audit (wired vs dormant audit features)

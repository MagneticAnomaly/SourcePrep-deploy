# Audit — Tech debt report

**File:** `src/prep/core/audit/prompts.py:132-165`
**Symbols:** `TECH_DEBT_REPORT_SYSTEM`, `TECH_DEBT_REPORT_PROMPT`
**Invoked by:** `src/prep/core/audit/synthesizer.py:_gen_tech_debt`
**Pipeline stage:** audit (parallel since Phase 96F)
**Output schema:** structured markdown — debt summary, hotspots, module health, remediation roadmap
**Status:** baseline

## Purpose
Synthesizes a tech-debt report with a remediation roadmap. The action-oriented page of the audit.

## Grounding (inputs)
- TODO/FIXME markers
- Deprecated-call counts
- Test xfails / skips
- Complexity hotspots
- Cycle list

## Output schema
Markdown with sections: summary, hotspots (ranked), module health (per-module 1-line), remediation roadmap (ordered actions).

## Known issues / hypotheses
- **Roadmap fabrication**: "remediation roadmap" tempts the LLM to invent specific tasks. Hypothesis: outputs should ground every roadmap item in a hotspot or finding cited above; verify they do.
- **Module health vocabulary**: "healthy / concerning / unhealthy" — same vocabulary as audit-summary's score? If not, inconsistency.
- **Spaghetti migration** (memory: `project_audit_spaghetti_migration.md`). `run_spaghetti_scan` exists unwired because of panel→pipeline migration. If spaghetti scan results aren't in grounding, tech-debt report misses one of the most useful debt signals.
- **Hotspot ranking criteria**: unclear what makes a hotspot a hotspot. If the prompt doesn't define it, outputs use ad-hoc reasoning.

## Snapshot 2026-05-17
- Prompt source SHA: `d129188714f2`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/audit-tech-debt/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-tech-debt/powermate-reborn.md)

## Iterations

_(none yet)_

## Open questions
- Is spaghetti-scan output wired into grounding for this prompt? (See `project_audit_spaghetti_migration.md`.)
- Should hotspot ranking be deterministic (sort by `(complexity × dependents)`) before the LLM ever sees the list?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-gaps](./audit-gaps.md)
- Memory: `project_audit_runner_schema.md`, `project_audit_spaghetti_migration.md`
- Phase 122 — Feature Utilization Audit

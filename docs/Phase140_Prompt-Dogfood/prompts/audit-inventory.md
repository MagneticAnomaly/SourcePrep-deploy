# Audit — Component inventory

**File:** `src/prep/core/audit/prompts.py:112-130`
**Symbols:** `COMPONENT_INVENTORY_SYSTEM`, `COMPONENT_INVENTORY_PROMPT`
**Invoked by:** `src/prep/core/audit/synthesizer.py:_gen_inventory`
**Pipeline stage:** audit (parallel since Phase 96F)
**Output schema:** structured markdown — component table grouped by module
**Status:** baseline

## Purpose
Builds an inventory table of components / modules / services with one-line descriptions. The "what's in this codebase, at a glance" page of the audit.

## Grounding (inputs)
- Cluster summaries (from `batch-cluster`)
- File-role classifications (from `batch-file`)
- Atlas WORKSPACE MAP

## Output schema
Markdown table(s), grouped by module. Each row: component name, location, one-line role.

## Known issues / hypotheses
- **Inventory vs atlas overlap**: the atlas's WORKSPACE MAP already enumerates modules. Hypothesis: the audit inventory needs to add something the atlas doesn't (e.g., test coverage per component, last-modified, ownership). If it doesn't, drop it.
- **Table formatting drift**: cloud LLMs sometimes mis-render markdown tables (wrong column counts). Verify outputs across repos.
- **Module-grouping consistency**: does each cluster name from `batch-cluster` show up as a heading here? If groupings diverge, the audit reads like a different project from the atlas.

## Snapshot 2026-05-17
- Prompt source SHA: `d129188714f2`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/audit-inventory/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-inventory/powermate-reborn.md) — only 9 lines, very small component count for a small Swift project

## Iterations

_(none yet)_

## Open questions
- Should the inventory cite file counts per component (factual, no LLM judgment needed)?
- Is this prompt redundant with the atlas, and should we kill it?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-architecture](./audit-architecture.md), [batch-cluster](./batch-cluster.md), [atlas-root](./atlas-root.md)
- Memory: `project_audit_runner_schema.md`

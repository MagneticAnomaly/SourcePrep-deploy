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

### 2026-05-19: A3 — preamble leakage + 3× regeneration; anti-preamble clause shipped

**Type:** prompt edit shipped (single iteration; commit pending)

**Read materials:**
- `COMPONENT_INVENTORY_SYSTEM` + `COMPONENT_INVENTORY_PROMPT` (`audit/prompts.py:112-130`).
- PowerMate output: [`../snapshots/2026-05-17_baseline/outputs/audit-inventory/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-inventory/powermate-reborn.md) — 529 lines.

**Correction to page stub (line 30) — output is 529 lines, not "only 9 lines". Stub is wrong.**

**Finding #1 — 57% of output is preamble.** The first `## Component Table` heading does not appear until line 301. Lines 1-300 contain the model's internal planning notes:

> Line 1: "The user wants a Markdown component inventory for the PowerMateReborn codebase."
> Line 3-7: requirements restatement
> Line 9-29: file-by-file mapping table written as bullets (NOT in the requested markdown table format)

The actual requested `## Component Table` finally starts at line 301. But there are **THREE `## Component Table` sections** (lines 301, 321, 519) — the model restarted the table twice, suggesting it wrote a draft, decided it wasn't right, and rewrote. Lines 321-518 are a second draft; lines 519-529 are a third attempt that's truncated.

This is two bad failure modes:
- **Preamble leakage**: the model planning-out-loud before output.
- **Multi-regeneration**: model writing then rewriting in the same response, tripling the output and confusing parsers.

**Finding #2 — root cause is missing output-discipline in the SYSTEM prompt.** The `COMPONENT_INVENTORY_SYSTEM` was the shortest of the audit-family system prompts:

```
You are documenting every major component in the codebase.
Produce a detailed component inventory in Markdown.
```

Two sentences, no output-shape discipline. Compare to `AGENTS_MD_SYSTEM` in `agents/hr/prompts.py:72-76` which has "Output ONLY the markdown content — no preamble, no code fences wrapping the whole output." That clause is what's missing here.

**Edit shipped (commit pending):**

```diff
 COMPONENT_INVENTORY_SYSTEM = """You are documenting every major component in the codebase.
-Produce a detailed component inventory in Markdown."""
+Produce a detailed component inventory in Markdown.
+Output ONLY the Markdown report — no preamble, no internal planning notes, no "The user wants..." restatements, no thinking-out-loud paragraphs before the first section heading. Start your output directly with the first "## " section.
+Do NOT regenerate the report multiple times in one response; emit each section exactly once."""
```

The "Do NOT regenerate the report multiple times" clause is unique to this prompt because the captured output showed the 3× regeneration; the other 4 audit prompts only got the "no preamble" clause.

**Verdict:** **partial** — shipped to `main`; awaiting PowerMate finalize-group rerun for confirmation that:
- The output starts with `## Component Table` on line 1 (no preamble)
- Only ONE `## Component Table` section exists in the output (no regeneration)
- Token count drops dramatically (529 lines → ~50-100 lines expected)

Confidence in shipping without rerun: **95%**. The fix matches a known-working pattern (AGENTS_MD_SYSTEM) and the failure mode is unambiguous. The only risk is the model interpreting "exactly once" too literally and dropping legitimate repeated headings (unlikely — markdown tables don't typically have repeated `## H2` headings within a single inventory).

**Follow-ups:**
1. Rerun PowerMate audit and re-capture; promote to `kept` if findings hold.
2. Re-baseline snapshot.
3. Cross-cutting check: same failure mode may exist in any audit-family prompt under specific model/grounding combinations. Defensive anti-preamble clause shipped on `AUDIT_SUMMARY_SYSTEM`, `ARCHITECTURE_ANALYSIS_SYSTEM`, `GAP_ANALYSIS_SYSTEM`, `TECH_DEBT_REPORT_SYSTEM` in the same commit for consistency.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (Anthropic best practices: explicit response-shape constraints survive better than implicit assumptions).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §3 (CoT can hurt — when the model "thinks step by step" in the output instead of using thinking tokens, it pollutes the visible response).
- Memory: `feedback_test_full_import_chain.md` — verification should include actual rerun, not just prompt-side dry run.

**Cross-references:** [`audit-tech-debt.md`](./audit-tech-debt.md) Iteration #1 (same failure mode, same fix), other audit siblings.

## Open questions
- Should the inventory cite file counts per component (factual, no LLM judgment needed)?
- Is this prompt redundant with the atlas, and should we kill it?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-architecture](./audit-architecture.md), [batch-cluster](./batch-cluster.md), [atlas-root](./atlas-root.md)
- Memory: `project_audit_runner_schema.md`

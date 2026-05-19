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

### 2026-05-19: A3 — 80% preamble leakage; anti-preamble clause shipped

**Type:** prompt edit shipped (single iteration; commit pending)

**Read materials:**
- `TECH_DEBT_REPORT_SYSTEM` + `TECH_DEBT_REPORT_PROMPT` (`audit/prompts.py:132-165`).
- PowerMate output: [`../snapshots/2026-05-17_baseline/outputs/audit-tech-debt/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-tech-debt/powermate-reborn.md) — 580 lines.

**Finding #1 — 80% of output is preamble.** The first `## Debt Summary` heading does not appear until line 465. Lines 1-464 contain the model's internal planning:

> Line 1: "The user wants a tech debt report for the 'PowerMateReborn' project based on the provided findings."
> Lines 8-460: a massive 15-section breakdown of findings by module ("**Findings breakdown by module:**"), each module enumerated with 1-7 debt items, complete with severity tagging, item descriptions, and notes. This is the model writing the report INSIDE its planning before writing the report ITSELF.

The actual requested sections (`## Debt Summary`, `## Spaghetti Hotspots`, `## By Module`, `## Remediation Roadmap`) start at line 465 and continue through 580. So 115 lines of report, 465 lines of preamble.

The preamble is high-quality (it's basically the report in different formatting), but it's not what the user asked for, it's in the wrong format, and it doubles the token cost.

**Finding #2 — same root cause as audit-inventory.** The `TECH_DEBT_REPORT_SYSTEM` is two sentences with no output-discipline clause. Same problem the AGENTS_MD_SYSTEM pattern would solve.

**Edit shipped (commit pending):**

```diff
 TECH_DEBT_REPORT_SYSTEM = """You are producing a tech debt report for engineering leadership.
-Be specific about locations, severity, and estimated remediation effort."""
+Be specific about locations, severity, and estimated remediation effort.
+Output ONLY the Markdown report — no preamble, no internal planning notes, no "The user wants..." restatements, no thinking-out-loud paragraphs before the first section heading. Start your output directly with the first "## " section."""
```

**Verdict:** **partial** — shipped to `main`; awaiting PowerMate rerun for confirmation:
- Output starts with `## Debt Summary` on line 1
- Token count drops dramatically (580 → ~100-120 lines expected — the actual report)
- All 4 requested sections still present

Confidence in shipping without rerun: **95%**. Same as audit-inventory — known-pattern, unambiguous failure mode, low risk of over-application.

**Observation #3 — preamble actually contained good content the report should keep.** The preamble's "Findings breakdown by module" section enumerates each module's debt items with severity, which is essentially what `## By Module` is supposed to show. After the fix, the model should put this content in the `## By Module` section directly, not as preamble.

**Follow-ups:**
1. Rerun PowerMate audit and re-capture.
2. Compare new `## By Module` section to the preamble's "Findings breakdown by module" — verify the report retains the per-module enumeration (it should, since that's what the section asks for).
3. Sibling: same fix applied to `audit-inventory`, `audit-summary`, `audit-architecture`, `audit-gaps` (defensive — they didn't show the failure on this single capture but may on different models).

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (explicit response-shape constraints).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §3 (CoT-in-output is the failure mode — model should think then commit, not think-and-commit in same stream).

**Cross-references:** [`audit-inventory.md`](./audit-inventory.md) Iteration #1 (same failure, same fix). Other audit-family siblings.

## Open questions
- Is spaghetti-scan output wired into grounding for this prompt? (See `project_audit_spaghetti_migration.md`.)
- Should hotspot ranking be deterministic (sort by `(complexity × dependents)`) before the LLM ever sees the list?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-gaps](./audit-gaps.md)
- Memory: `project_audit_runner_schema.md`, `project_audit_spaghetti_migration.md`
- Phase 122 — Feature Utilization Audit

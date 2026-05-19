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
- Outputs captured:
  - Slot A (SourcePrep self): TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/audit-summary/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-summary/powermate-reborn.md) — generated 2026-05-01

## Iterations

### 2026-05-19: A2 — well-engineered prompt; Module Status appears to truncate; corrects page hypothesis #2

**Type:** analysis-only (no edit shipped)

**Read materials:**
- `AUDIT_SUMMARY_SYSTEM` + `AUDIT_SUMMARY_PROMPT` (`audit/prompts.py:9-42`).
- PowerMate output: [`../snapshots/2026-05-17_baseline/outputs/audit-summary/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-summary/powermate-reborn.md) — 32 lines, all 5 required sections present.

**Correction to page hypothesis #2 (line 24) — there is no 0-100 health score.** Page says "Health score gaming: a 0-100 score is a tempting target..." but the actual prompt asks for "an A-F grade" (line 30 of prompts.py). PowerMate output uses `C+`. The hypothesis is moot; A-F grades resist gaming more than 0-100 scores per behavioral-economics literature. Worth updating the page to reflect actual schema.

**Strong points of the prompt (no iteration needed):**

1. **All 5 sections present in output.** Unlike `atlas-single-doc` (which silently drops sections under budget pressure), audit-summary's output is complete.
2. **Anti-hallucination is strong:** "Do NOT invent findings — only summarize what is given." Output respects this — Health Score cites real numbers (9 warnings, 3 spaghetti hotspots, in-degree 13, z-score 3.7).
3. **Cross-stage data integration:** the Health Score and Top Recommendations explicitly reference spaghetti hotspots, honoring the prompt's "When a finding's file appears in the spaghetti hotspots, cite the spaghetti score" instruction.
4. **Top Recommendations are concrete:** each names specific files and lists actionable changes (decouple AppDelegate, fix Sparkle pubDate), not generic prescriptions. Addresses the page open-question about "specific next steps with file/line refs" — the prompt doesn't explicitly require them but the grounding instruction "Use exact file paths and concrete numbers" gets the job done.
5. **"Max 5" + "0 critical findings" graceful handling** — prompt allows zero output gracefully when input has no criticals.

**Observation #1 — Module Status appears to truncate.** PowerMate has 20 modules per pipeline metadata, but the Module Status section lists only 8. Prompt: "One line per module: name, file count, status, key issue if any." Implies all modules. Three reads:

- **(a) Model self-throttled** — even without an explicit char budget, model curated.
- **(b) Model emitted only "interesting" modules** (warnings/criticals + a couple healthy).
- **(c) Model deduplicated against Top Recommendations / Critical Findings** — only listing modules already cited above.

For an agent reading this audit, (c) is reasonable, but the instruction asks for one line *per module*. A future "zero-finding" module would silently disappear. **Recommendation if iterating:** clarify to either "EVERY module, one line, even healthy" OR "up to N most-impactful modules (warnings + top healthy by file count)" — the current ambiguous phrasing produces neither. Confidence: 80% this is a real ambiguity worth tightening.

**Observation #2 — markdown bold/headers used freely.** Different from atlas which forbids markdown. Consistent with this prompt's "in Markdown" requirement. Downstream consumer (audit UI? Dashboard?) renders this as markdown.

**Verdict:** **analysis (no edit shipped).** Confidence in the prompt as-is is high. Two deferred actions:

1. Update page hypothesis #2 (correct the 0-100 score → A-F grade)
2. Tighten Module Status instruction (exhaustive vs bounded — currently ambiguous)

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (concrete contrast in examples — this prompt's numeric anchors work well).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 ("Do NOT invent" + "only summarize what is given" is the correct anti-hallucination pattern).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §7 (calibration — A-F grades are named-tier rubric, exactly the right call vs 0-100 float).

**Cross-references:** [`audit-architecture.md`](./audit-architecture.md), [`audit-gaps.md`](./audit-gaps.md), [`audit-inventory.md`](./audit-inventory.md), [`audit-tech-debt.md`](./audit-tech-debt.md) (siblings — same prompt file).

## Open questions
- Should the health score be replaced with a tier + brief justification?
- Does the prompt explicitly request file/line refs in recommendations? (If not, that's a candidate iteration.)

## Cross-references
- Sibling: [audit-architecture](./audit-architecture.md), [audit-gaps](./audit-gaps.md), [audit-inventory](./audit-inventory.md), [audit-tech-debt](./audit-tech-debt.md)
- Memory: `project_audit_runner_schema.md`, `project_audit_spaghetti_migration.md`
- Phase 122 — Feature Utilization Audit (wired vs dormant audit features)

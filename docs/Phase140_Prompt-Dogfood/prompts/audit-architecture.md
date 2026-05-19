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
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/audit-architecture/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-architecture/powermate-reborn.md)

## Iterations

### 2026-05-19: A2 — well-engineered prompt; module-identifier casing inconsistent

**Type:** analysis-only (no edit shipped)

**Read materials:**
- `ARCHITECTURE_ANALYSIS_SYSTEM` + `ARCHITECTURE_ANALYSIS_PROMPT` (`audit/prompts.py:44-78`).
- PowerMate output: [`../snapshots/2026-05-17_baseline/outputs/audit-architecture/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-architecture/powermate-reborn.md) — 84 lines, all 5 sections present (Architecture Overview, Module Dependency Flow, Structural Bottlenecks, Boundary Violations, Recommendations).

**Strong points (no iteration needed):**

1. **All 5 sections present, well-developed.** Each section has multiple paragraphs/bullets with concrete file paths.
2. **Identifies real architectural patterns.** "Despite this logical layering, the physical dependency graph collapses into a centralized star topology anchored by a single application coordinator." This is a genuine observation, not boilerplate — the actual import graph (`AppDelegate.swift` in-degree 13, z-score 3.7) supports it.
3. **5 named boundary violations** (Runtime→Build, Build→Runtime, Hardware→Policy, Transport→Application Core, Core→Concrete Hardware) — each grounded in the cluster graph.
4. **6 concrete recommendations** with file/protocol names (`LifecycleCoordinating`, `SettingsPersisting`, `HardwareEventRouting`, `DisplayHardwareControlling`, `HardwareEventSink`, `BrightnessStrategy`). Actionable enough that an engineer could start implementing.
5. **Hub-z-score citation** — "in-degree: 13, z-score: 3.7" appears in Primary Hub section. This is the kind of grounded-in-statistics output the prompt's "Reference exact file paths and import relationships from the data provided" enables.

**Observation #1 — module-identifier casing is inconsistent in output.** The cluster identifiers used as module names mix three conventions:

- snake_case: `application_coordination`, `usb-hardware-transport`, `hardware_transport`
- kebab-case: `hardware-event-coordinator`, `custom-mode-controller`, `display-control`
- Title Case prose: "Application Lifecycle & Hardware Input Coordinator", "PowerMate Gesture & LED Coordinator"

The mixing is a downstream effect — the cluster IDs themselves are mixed (likely because batch-cluster outputs use both naming styles depending on input). But the audit-architecture output shows them side-by-side in the same paragraph, which is jarring for the reader. Worth either:

- (a) Normalizing in the prompt: "When listing module identifiers, normalize all to Title Case prose. The kebab-case / snake_case slugs are internal identifiers; the user-facing audit should use the human-readable cluster names."
- (b) Fixing upstream in `batch-cluster` to enforce one ID convention.

For an agent reading the audit, (a) is easier (prompt-only fix) and avoids touching cluster IDs that other consumers may depend on.

**Observation #2 — page hypothesis #2 about bottleneck = high in-degree fallacy is correctly addressed.** Page worries "high in-degree (many imports) ≠ bottleneck in many architectures (e.g., a `types.ts` is high-in-degree but desired)." Actual output handles this nuance — distinguishes "Primary Hub" (god-object pattern) from "Secondary Hubs" (described as nexuses for extensibility logic). The prompt doesn't explicitly say "distinguish desired vs accidental hubs" but the model is doing it via context (the cluster summaries provide enough grounding). Worth recognizing the prompt is doing well here.

**Observation #3 — no ASCII dependency diagrams emitted** (per page open-question). The prompt doesn't request them; the output sticks to prose with bullet-listed edges. Probably correct decision — ASCII art is unreliable from LLMs and the textual format renders cleanly in markdown.

**Verdict:** **analysis (no edit shipped).** The prompt is mature and producing excellent output. Single recommendation worth a follow-up iteration:

1. **Normalize module-identifier casing in output** via one-line clause in the prompt.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (concrete contrast — `Primary Hub` vs `Secondary Hubs` distinction is the kind of two-tier discrimination Anthropic's docs encourage).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (anti-hallucination via grounding — explicit cycle list + degree counts in grounding make the output stay anchored).

**Cross-references:** [`audit-summary.md`](./audit-summary.md), [`audit-gaps.md`](./audit-gaps.md), [`batch-cluster.md`](./batch-cluster.md) (source of the mixed-casing cluster IDs).

## Open questions
- Should the architecture page link to `prep_impact` for each named bottleneck?
- Is there value in adding ASCII dependency diagrams, or are they noise?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-gaps](./audit-gaps.md), [audit-inventory](./audit-inventory.md), [audit-tech-debt](./audit-tech-debt.md)
- Memory: `project_audit_runner_schema.md`

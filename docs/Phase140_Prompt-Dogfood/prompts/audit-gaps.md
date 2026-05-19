# Audit — Gap analysis

**File:** `src/prep/core/audit/prompts.py:80-110`
**Symbols:** `GAP_ANALYSIS_SYSTEM`, `GAP_ANALYSIS_PROMPT`
**Invoked by:** `src/prep/core/audit/synthesizer.py:_gen_gaps`
**Pipeline stage:** audit (parallel since Phase 96F)
**Output schema:** structured markdown — misplaced imports, dead code, tech-debt indicators, dependency diagram
**Status:** baseline

## Purpose
Identifies "gaps" — code that isn't doing what its location suggests, dead branches, or accumulated debt that's signaling.

## Grounding (inputs)
- Dead-code candidates from structural analysis
- Misplaced imports (e.g., business logic imported from `utils/`)
- Tech-debt markers (TODOs, deprecated calls, `xfail` tests)

## Output schema
Markdown sections. Includes a "dependency diagram" — text-rendered, not graphical.

## Known issues / hypotheses
- **False-positive dead code**: structural dead-code detection misses dynamic dispatch and plugin loading. Hypothesis: prompt should be told "treat structural dead-code list as candidates only; explain why each is or isn't actually dead." Without that nudge, outputs are too confident.
- **Diagram quality**: text dependency diagrams are notorious for being wrong (mis-arrowed, mis-grouped). Worth comparing "include diagram" vs "omit diagram" outputs.
- **Tech debt double-counting**: this prompt and `audit-tech-debt` both surface tech debt. Verify they don't say contradictory things on the same items.

## Snapshot 2026-05-17
- Prompt source SHA: `d129188714f2`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/audit-gaps/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-gaps/powermate-reborn.md)

## Iterations

### 2026-05-19: A2 — well-engineered prompt; GAP-1 dead-code finding is high-confidence false-positive risk

**Type:** analysis-only (concrete prompt edit proposed; not shipped this iteration)

**Read materials:**
- `GAP_ANALYSIS_SYSTEM` + `GAP_ANALYSIS_PROMPT` (`audit/prompts.py:80-110`).
- PowerMate output: [`../snapshots/2026-05-17_baseline/outputs/audit-gaps/powermate-reborn.md`](../snapshots/2026-05-17_baseline/outputs/audit-gaps/powermate-reborn.md) — 11 numbered gaps (GAP-1 through GAP-11), structured with severity/files/problem/resolution.

**Strong points (no iteration needed):**

1. **Structured numbered output** (GAP-N format) is parseable + cite-able. 11 gaps emitted, well-bounded.
2. **Each gap has severity / affected files / problem / resolution** — uniform schema honored.
3. **Resolutions are concrete and Swift-aware** — protocol extraction (`HardwareAbstraction`), enum-with-associated-values for `CodableActionConfig`, etc. Not generic advice.
4. **Grounding citations** — many gaps quote tech-debt items by name from the input.

**Finding #1 — GAP-1 ("Orphaned Core Modules / Broken Static Dependency Graph") is a high-confidence false positive that page hypothesis #1 anticipated.** Page hypothesis #1: "False-positive dead code: structural dead-code detection misses dynamic dispatch and plugin loading. Hypothesis: prompt should be told 'treat structural dead-code list as candidates only; explain why each is or isn't actually dead.'"

GAP-1 marks 11 Swift files Critical for having "zero incoming import edges":

> Sources/BrightnessController.swift, Sources/CustomModeEngine.swift, Sources/CustomModeSettingsView.swift, Sources/DDCController.swift, Sources/MIDIController.swift, Sources/MenuBarIcon.swift, Sources/OSCController.swift, Sources/OSDOverlay.swift, Sources/PowerMateBLETransport.swift, Sources/PowerMateUSBTransport.swift, Sources/VolumeController.swift

Cross-checking against the captured `outputs/batch-edges/powermate-reborn.jsonl` (the inferred edges from a sibling prompt): **all 11 files have multiple inferred edges** to/from them. For example: BrightnessController.swift has edges to/from DDCController, OSDOverlay, AppDelegate. CustomModeEngine has edges to OSCController, AppDelegate. PowerMateBLETransport implements PowerMateManager, and so on.

So these files ARE live, just connected via runtime protocol conformance + AppDelegate-mediated instantiation, which the static-import parser does not track. The audit-gaps prompt sees only the static `dead_code_findings` input and infers Critical-severity dead-code. The recommendation "delete or properly wire them up" is dangerous — these files contain real functionality.

**Root cause:** the `dead_code_findings` grounding input is static-import-only; inferred-edges data isn't passed. This is a grounding-shape gap (same family as the [`../findings/concept-pipeline-grounding-gap.md`](../findings/concept-pipeline-grounding-gap.md) finding for concepts).

**Two paths to fix:**

**(A) Upstream — preferred.** Modify the `audit/runner.py` data assembly to pass inferred-edges-aware dead-code candidates: a file is "dead-code candidate" only if it has zero STATIC edges AND zero INFERRED edges. This is structural pipeline work, outside Phase 140's prompt-copy scope.

**(B) Prompt softening — fallback in scope for Phase 140.** Add to `GAP_ANALYSIS_PROMPT` before the schema:

> **dead_code_findings caveat:** items in MISPLACED IMPORT FINDINGS and the dead-code list are derived from STATIC import analysis only. In codebases that use dynamic dispatch (protocol conformance, delegate patterns, plugin registries, IoC containers, runtime instantiation by AppDelegate / main / factory functions), files with zero static incoming edges may still be alive. Before recommending deletion: (a) downgrade severity if the file's name suggests an integration point (Controller, Transport, Handler, Service, Manager, etc.), (b) recommend "audit dynamic instantiation paths" as the first action, not "delete", (c) DO NOT mark as Critical purely on the basis of zero static imports.

- **Pro:** in scope (prompt copy). Avoids dangerous "delete" recommendations downstream.
- **Con:** still treating the symptom. Real fix is grounding-shape.
- **Estimated impact:** GAP-1 would have been downgraded from Critical to Medium with a "audit dynamic instantiation" recommendation instead of "delete or properly wire them up."

**Verdict:** **analysis (no edit shipped).** Path B is in scope; Path A is the right fix but is grounding-pipeline work.

Confidence in Path B if shipped without rerun: 75%. The risk is the model over-applying the caveat (downgrading legitimately-dead code to "needs audit") — should be measured on a rerun against a project with both kinds (real dead code + dynamic-dispatch-alive code).

**Finding #2 — Dependency Diagram section content is well-bounded.** The "Dependency Diagram" section in the prompt schema (line 109-110) asks for "Text-based diagram showing the problematic dependency chains." The PowerMate output handles this reasonably — no obvious diagram, but the GAP entries describe dependency chains in prose. Page open-question "Drop the text dependency diagram entirely?" — based on this single sample, the diagram is implicit in the prose. If A1 atlas captures show the same, the section is probably noise; if other repos render real ASCII diagrams, it's worth keeping.

**Verdict on the diagram question:** defer — need more samples.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield over-abduction: model confidently emits "dead code" from incomplete grounding).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (concrete contrast in example: prompt could include a positive/negative example for dead-code vs dynamically-dispatched).
- See [`../findings/concept-pipeline-grounding-gap.md`](../findings/concept-pipeline-grounding-gap.md) — same pattern (grounding-shape gap → confident-but-wrong output).

**Cross-references:** [`audit-summary.md`](./audit-summary.md), [`audit-architecture.md`](./audit-architecture.md), [`audit-tech-debt.md`](./audit-tech-debt.md), [`batch-edges.md`](./batch-edges.md) (the inferred-edges that would have prevented GAP-1's false positive).

## Open questions
- Should dead-code items in the output link to `prep_search` queries that would let the user verify?
- Drop the text dependency diagram entirely?

## Cross-references
- Sibling: [audit-summary](./audit-summary.md), [audit-architecture](./audit-architecture.md), [audit-tech-debt](./audit-tech-debt.md)
- Memory: `project_audit_runner_schema.md`, `project_audit_spaghetti_migration.md`

# Concept — Validate

**File:** `src/prep/core/concept_validate_prompt.py:49-227`
**Symbols:** `VALIDATE_SYSTEM_PROMPT`, `build_validate_user_prompt`
**Invoked by:** Validate swarm worker — once per candidate concept
**Pipeline stage:** synth (Validate pass)
**Output schema:** strict JSON `{verdict, tier, rationale, counter_evidence, falsification}`
**Status:** baseline

## Purpose
Hostile-reviewer critique of one candidate concept. The prompt asks the LLM to play adversarial reviewer — quote evidence, search for counter-evidence, attempt falsification, then issue a verdict.

## Grounding (inputs)
- One candidate concept (title + draft rationale + anchors)
- The anchor files' content
- Audit context if relevant

## Output schema
Strict JSON. Schema is defined inline in the prompt (lines ~190-220). Verdict ∈ {accept, reject, partial}. Tier follows the T1/T2/T3 rubric.

## Known issues / hypotheses
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). Prompt should produce rationale BEFORE tier — verify this ordering is present in VALIDATE_SYSTEM_PROMPT. If the model is asked for tier first, social-register clumping kicks in and tiers cluster around the middle.
- **Adversarial framing fatigue**: hostile-reviewer prompts can produce performatively negative critiques regardless of input quality. Worth comparing a "fair-witness" framing variant on the same candidates.
- **Few-shot omission**: T3 Refine has few-shot examples; Validate does not. Hypothesis: adding 2-3 worked examples (accept / reject / partial) would tighten the tier distribution.

## Snapshot 2026-05-17 → updated 2026-05-18 with fresh concept-pipeline run
- Prompt source SHA: `f257c13839aa`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): all 66 concept records (status reflects validate verdicts): [`../snapshots/2026-05-17_baseline/outputs/concept-validate/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-validate/powermate-reborn-concepts.json)
  - **Validate-stage breakdown** (from pipeline metadata): of 19 synth concepts seen, validate **activated 6, triaged 3, archived 10**. 0 parse failures. Reject-rate ≈ 53% — within the 5-40% sanity band from grounding §9, slightly hot. Possible iteration target.

## Iterations

### 2026-05-18: analysis of 53% reject rate on PowerMate Slot B baseline

**Type:** analysis-only (no prompt edit, no rerun yet)

**Hypothesis going in:** Reject rate is hot per grounding §9 (5-40% sane band). Maybe the rubric is too aggressive.

**What I actually found after reading all 10 archived candidates + the 6 active + 3 triage_pending:**

The rubric is fine. The bug is **structural in the user prompt, not the system prompt.**

Looking at `build_validate_user_prompt` (`concept_validate_prompt.py:136-208`), Validate gets:
- the candidate concept's title + content + anchors
- `related_rationale` — per-file/module summaries
- `related_doc_excerpts` — planning docs
- `related_audit_findings` — audit results

It does NOT get the actual code file content for the candidate's anchors. So Validate cannot verify claims that require reading source.

Reviewing the 10 archived candidates by the rejection pattern stated in the LLM's own `assertion` field:

| Archived candidate | Failure mode |
|---|---|
| dlopen/dlsym of private DisplayServices | assertion: "Without grounding, neither test can be performed" |
| Per-display gamma state isolation | assertion: "no falsification query can be executed against actual source" |
| Big-endian OSC packet construction | assertion: "the falsification requires inspecting a file that is not in the grounding" |
| Documentation as hardware-owner recruitment | assertion: "but Sources/PowerMateBLETransport.swift is not in grounding" |
| POSIX signal handlers duplicate AppKit | assertion is grep-executable but anchor files weren't surfaced to Validate |
| Timer-based gesture detection on main runloop | same — anchor files not in grounding |
| Sparkle EdDSA signing artifact-order | needs `scripts/build_and_sign.sh` content — not surfaced |
| Native menu-bar form factor (security) | needs entitlements file — not surfaced |
| Manual release pipeline (security) | needs `CODE_SIGNING.md` content — not surfaced |
| Sparkle 2.5.0 pin EdDSA migration | needs `Package.swift` content — not surfaced |

Compare with the 6 **accepted** (T2-tier, confidence 0.65) candidates — they are predominantly **architectural / positioning** claims that can be confirmed from file-level rationale or README excerpts:
- "Manual .app bundle assembly bypasses SPM..."
- "Four-mode taxonomy deliberately masks HID-to-system-control impedance mismatch"
- "Single-file subsystems preserve hardware-state atomicity"
- "Cursor-positioned HUD exploits spatial discoverability"
- "Menu-bar-only activation policy"
- "Runtime dlopen of private IOKit I2C symbols defends against undocumented API churn" (note: this one IS implementation-specific and got accepted — because rationale on `DDCController.swift` probably mentions dlopen, so grounding was sufficient by accident)

**The bias is systematic:** Validate accepts architecture/positioning concepts and rejects implementation-detail concepts, regardless of correctness, because grounding is rationale-shaped, not source-shaped.

**Root cause:** The upstream "T3b runner" job that builds `related_rationale` / `related_doc_excerpts` / `related_audit_findings` doesn't include actual file content. When a concept's anchor is `Sources/BrightnessController.swift`, Validate sees the per-file rationale (a 1-2 sentence summary) instead of the actual source where dlopen calls live.

**Two paths to fix:**

**(A) Upstream — preferred.** Modify the T3b runner that prepares `related_rationale` to *additionally* attach a small slice of the actual file content when the candidate's claim is implementation-specific. Heuristic: if the concept's content mentions a specific API/symbol (dlopen, sigaction, Timer, etc.), pull a ±20-line window around the first match in each anchor file. This is the right fix and it doesn't require touching the Validate prompt.

**(B) Validate prompt softening — fallback.** Add a clause to `VALIDATE_SYSTEM_PROMPT` REJECT criteria:
> EXCEPTION: If the concept's claim is implementation-specific (mentions an API, symbol, byte order, signal name, etc.) and the grounding doesn't include source for the anchor file, downgrade to T1 with rationale "grounding insufficient for falsification but claim is plausible." Do NOT REJECT in this case.

This is a workaround — it preserves recall at the cost of precision. Better than losing the concepts but worse than fixing the grounding.

**Verdict:** **analysis (not a kept/reverted iteration yet).** Path A is the right fix but requires touching the T3b runner code, which is structural pipeline work — outside Phase 140's "prompt copy" scope. Path B is in scope but is a band-aid.

**Recommended next iteration (out of this session):**
1. Verify the T3b runner code lives where I think it does (probably `src/prep/core/concept_validate_swarm.py` or similar).
2. Decide: ship Path B as a stopgap, OR move Path A to a separate phase ticket and leave Phase 140 to wait.
3. If Path B: write a 3-line iteration block proposing the exact prompt change, commit, restart daemon, re-run pipeline on PowerMate, capture, compare reject rate.

**Side observation — the rationale-before-score ordering IS present** (`process` block lines 99-117, output schema field order `counter_evidence, falsification, rationale, verdict`). The grounding §7 calibration finding is already implemented in this prompt. Don't iterate on that.

**Cross-references:** See [`../findings/concept-pipeline-grounding-gap.md`](../findings/concept-pipeline-grounding-gap.md) for the cross-cutting write-up (Validate's reject-rate symptom is a Generate-side opportunity too: Generate is correctly producing implementation-detail claims that downstream can't verify).

## Open questions
- Is the falsification step too aggressive for T1 concepts that genuinely have no counter-evidence? Causes false `partial` verdicts?
- Does per-concept critique scale — or should we batch candidates and let the LLM compare them?

## Cross-references
- Sibling: [concept-synthesize](./concept-synthesize.md), [concept-t3-refine](./concept-t3-refine.md), [concept-generate](./concept-generate.md)
- Memory: `project_llm_confidence_calibration.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)

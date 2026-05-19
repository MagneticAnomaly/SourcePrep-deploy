# Concept — Synthesize

**File:** `src/prep/core/concept_synthesizer.py:292-527`
**Symbols:** `SYNTH_SYSTEM_PROMPT`, `build_synthesis_prompt`
**Invoked by:** `concept_synthesizer.synthesize_concepts()` — called once per project, terminal stage of the concept pipeline (Phase 125c)
**Pipeline stage:** synth
**Output schema:** structured JSON list of concepts with tier (T1/T2/T3), title, rationale, anchors, assertions
**Status:** baseline

## Purpose
Synthesizes cross-cutting concepts from the full grounding (atlas, audit findings, anchor-overlap clusters, doc bodies). This is where Generate-pass candidates get promoted to project-level concepts.

## Grounding (inputs)
- Atlas (root + segments)
- Audit summary
- Anchor-overlap clusters (concept candidates that share file anchors)
- Hub files and cross-cutting domains
- Doc excerpts

## Output schema
JSON list. Each concept: `{title, tier, rationale, anchors[], assertions[]}`. Rubric defines T1 (clear truth) / T2 (true with caveats) / T3 (boundary / aspirational). Banned outputs include vacuous concepts ("this project uses code"), trivial concepts, and concepts that fail the falsification step.

## Known issues / hypotheses
- **Wall-time regression** (memory: `project_synthesizer_wall_time_regression.md`). 900s cloud budget consumed by workers + T4 enrichment, synthesis silently fails, questions lost. Budget bumped to 1500s on 2026-05-02 — verify the prompt is not contributing to runtime by being prolix.
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). The prompt should use the named-tier rubric and ask for rationale BEFORE tier (avoids social-register clumping of floats). Verify SYNTH_SYSTEM_PROMPT does this; if not, that's a likely first iteration.
- **Concept promotion strategy** (memory: `project_concept_promotion_strategy.md`). 1,590 candidates is unacceptable for manual review; anchor-overlap clustering is the lever. Worth inspecting whether the synthesis prompt is producing too many T2/T3 candidates that should be deduped via anchor overlap upstream.

## Snapshot 2026-05-17 → updated 2026-05-18 with fresh concept-pipeline run
- Prompt source SHA: `b35e784e3abd`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): captured 2026-05-18 from a fresh Phase 125c pipeline run (model: `kimi-k2.6:cloud`, 163s elapsed, swarm_size 3, prompt_revision 2)
    - All 66 concept records (status: 6 active / 10 archived / 47 seed / 3 triage_pending): [`../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-concepts.json)
    - 36 concept questions: [`../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-questions.json`](../snapshots/2026-05-17_baseline/outputs/concept-synthesize/powermate-reborn-questions.json)
  - Per pipeline metadata: 19 synth_concepts_emitted, 19 saved, 6 val_activated, 3 val_triaged, 10 val_archived, 0 val_parse_failures, 36 questions_created. See [`_run-metadata/powermate-reborn-pipeline-2026-05-18.json`](../snapshots/2026-05-17_baseline/outputs/_run-metadata/powermate-reborn-pipeline-2026-05-18.json)

## Iterations

### 2026-05-19: B1 — synthesize prompt audit

**Type:** analysis-only (no prompt edit)

**Read materials:**
- `SYNTH_SYSTEM_PROMPT` (`concept_synthesizer.py:292-454`) — the system prompt with banned-outputs list, tier rubric, process steps, output schema.
- `build_synthesis_prompt` (`concept_synthesizer.py:457-527`) — user prompt builder.
- PowerMate Slot B captured concepts: 19 synth records (kind=`concept`) — 6 active (T2, conf 0.65), 10 archived (REJECTED by Validate, conf 0.0), 3 triage_pending (T1, conf 0.3). Plus 47 module-rationale records (kind=`module_rationale`) — separate layer, not synth output.

**Strong points of the current prompt** (no iteration needed on these):
- **Banned-outputs list** is concrete and unambiguous: 5 cliches + 3 layer-violation shapes ("Function X validates inputs" = belongs in module rationale) + 7 audit-shape framings ("X causes Y bug" = belongs in audit surface) + 3 historical/meta framings ("Phase docs encode chronological evolution" = not actionable).
- **GOOD examples** anchor what cross-cutting concepts look like (license-verification, embedded-mode-preserves-git-trackability, headless-engine, Tauri-over-Electron) — 1 T1, 2 T2, 1 T3-ish, well-balanced.
- **Hostile-reviewer downgrade pass** at step 5 of process is the right safeguard against tier inflation.
- **"DO NOT DEFAULT TO T2"** explicit instruction is correctly aimed at the social-register clumping failure mode (grounding §7).
- **`tier_pairwise` commit before tier** — calibration technique consistent with the named-tier rubric.

**Observation #1 — same grounding-gap as concept-validate.** Synthesize gets `atlas_summary` (first 3K chars) + `segments` + `audit_findings` + `spaghetti_hotspots` + `antibody_patterns` + `top_md_docs` + `rationale_clusters` — but **not actual file content**. When it emits a concept like "dlopen/dlsym of private DisplayServices prevents launch failure", it's drawing the claim from rationale clusters' summaries, not from inspecting source. Downstream Validate (which also lacks source) then rejects for "cannot quote grounding span". The synth prompt's instruction to "QUOTE 1-3 verbatim spans from the input grounding" reinforces this — it quotes the rationale summary, which isn't enough for Validate.

This is the same root cause as the Validate finding: the grounding pipeline is rationale-shaped. The fix is Path A from [`../findings/concept-pipeline-grounding-gap.md`](../findings/concept-pipeline-grounding-gap.md).

**Observation #2 — 0 T3 concepts emitted on PowerMate is consistent with prompt guidance.** The prompt says "most projects have 0-5 T3 concepts" — PowerMate is a single-segment Swift app with no CI/build-gate constraints visible from the indexed surface. 0 T3 is expected, not a bug.

**Observation #3 — all 6 active are confidence 0.65 (T2).** Looks like float-clumping, but per memory `project_llm_confidence_calibration.md` the storage maps tier→float (T2 = 0.65). Not a calibration issue; the LLM is emitting named tiers, the storage layer is doing the float mapping. Correct.

**Observation #4 — synth's "synthesize across, do not echo" instruction is doing real work.** Comparing the 47 module-rationale records (per-file claims like "DDCController.swift uses dlopen for IOKit I2C") to the 19 synth concepts (cross-cutting claims like "Runtime dlopen of private IOKit I2C symbols defends against undocumented API churn"), synth is lifting abstraction. Not just echoing. The 19 cover ~3-5 anchors each — within the "≥3 anchors" requirement.

**Verdict:** `analysis (no edit)`. Synthesize is well-engineered for its job. The downstream reject rate is a grounding-pipeline issue, not a synthesize-prompt issue. No edits recommended pending Path A.

**Open question (deferred):** If Path A ships and Synthesize gets source slices in grounding, would the T3 count rise? Worth re-measuring after that change. Until then, can't test.

## Open questions
- Does the rubric's tier definitions need few-shot examples (concept-t3-refine has them — should synth match)? **Iteration #1 deferred this; the prompt has 4 inline GOOD examples plus a banned-examples list. Adding few-shot would help if/when grounding includes source.**
- Are "banned outputs" enforced — i.e., do real outputs ever fall into the banned categories? **Quick check on PowerMate's 19 synth records: 0 fall into the banned shapes. The prompt is doing its job.**

## Cross-references
- Sibling: [concept-validate](./concept-validate.md), [concept-t3-refine](./concept-t3-refine.md), [concept-generate](./concept-generate.md)
- Memory: `project_synthesizer_wall_time_regression.md`, `project_llm_confidence_calibration.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)

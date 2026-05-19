# Batch — Inferred edges

**File:** `src/prep/core/batch_prompts.py:181-216`
**Symbols:** `BATCHED_INFERRED_EDGES_SYSTEM`, `build_batched_inferred_edges_prompt`
**Invoked by:** Augmenter worker — fills in graph edges that the structural parser missed
**Pipeline stage:** fast (catalogue augmentation) / enrichment
**Output schema:** structured JSON list of inferred edges (source, target, edge type, confidence)
**Status:** baseline

## Purpose
Detects cross-file dependencies that the AST parser couldn't statically resolve (dynamic imports, plugin registries, runtime config wiring). Adds these as inferred edges in the trace graph.

## Grounding (inputs)
- Batch of files with their content
- Structural edges already known (so we don't re-emit them)
- Symbol catalog snippet

## Output schema
JSON list. Each: `{source, target, edge_type, confidence, evidence_quote}`. Schema at `batch_prompts.py:365-546`.

## Known issues / hypotheses
- **False positives are expensive**: inferred edges feed `prep_impact`, so a wrong edge means a wrong blast-radius answer. Hypothesis: confidence threshold for accepting an inferred edge may be too permissive. Inspect baseline for low-confidence edges that look invented.
- **Evidence quote drift**: the prompt asks for an `evidence_quote` — verify that real outputs include quotes that *actually exist* in the input. Hallucinated quotes are a known LLM failure mode.
- **Plugin patterns**: dynamic import idioms are language-specific (Python `importlib`, JS `require()` with variable args). Hypothesis: the prompt's coverage is uneven across languages.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-edges/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-edges/powermate-reborn.jsonl) — 36 inferred edges

## Iterations

### 2026-05-19: B2 — evidence-quote hallucination + build-manifest noise

**Type:** analysis-only (proposes a concrete prompt edit, deferred to follow-up iteration with daemon rerun)

**Read materials:**
- `BATCHED_INFERRED_EDGES_SYSTEM` + `build_batched_inferred_edges_prompt` (`batch_prompts.py:181-216`).
- 36 PowerMate inferred edges: [`../snapshots/2026-05-17_baseline/outputs/batch-edges/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-edges/powermate-reborn.jsonl).

**Finding #1 — ~47% of emitted edges contain hedge language in their `evidence` field.** Scanning the 36 edges for hedge markers ("likely", "though source is not shown", "would likely", "designed for", "probably", "though not shown"), 17 of 36 (47%) match. Examples:

| Line | Edge | Evidence (truncated, hedge bolded) |
|---|---|---|
| 1 | OSDOverlay → VolumeController | "VolumeController **likely** triggers these displays via delegate pattern or direct calls" |
| 9 | VolumeController → AppDelegate | "VolumeChangeDelegate protocol **designed for** AppDelegate or similar to receive..." |
| 19 | Package.swift → BrightnessController | "Package.swift links CoreGraphics framework which BrightnessController.swift imports... **though source is not shown**." |
| 26 | AppDelegate → CustomModeSettingsView | "AppDelegate **likely presents** CustomModeSettingsView through customSettingsWindowController... instantiated by type name string..." |
| 32 | AppDelegate → OSCController | "AppDelegate **likely uses** OSCController through CustomModeEngine for OSC message actions" |

These are exactly the over-abduction failure mode named in grounding §9 (Caulfield: "instead of 'verify the answer,' ask 'attack the answer'") and §8 (G-Eval: LLM-judge bias toward fluent-but-unsupported claims). The prompt's `evidence` field is intended as a defense — the model must quote — but the field is being honored *rhetorically* (the model writes a justification) rather than *literally* (the model quotes the actual code). Because `evidence` is free text, there's nothing in the schema or the parser that checks for substring overlap with the input source.

**Finding #2 — Package.swift → individual source file `configures` edges (9 of 36 = 25%) are conceptually wrong.** Lines 16-24 emit edges like:

| Source | Target | Kind | Evidence summary |
|---|---|---|---|
| `Package.swift` | `Sources/AppDelegate.swift` | configures | "Package.swift declares Sparkle dependency and links frameworks (IOKit, CoreAudio...) used by AppDelegate.swift" |
| `Package.swift` | `Sources/BrightnessController.swift` | configures | "Package.swift links CoreGraphics framework which BrightnessController.swift imports" |
| `Package.swift` | `Sources/DDCController.swift` | configures | "Package.swift links IOKit framework which DDCController.swift imports" |
| ... 6 more, same pattern ... | | | |

A Swift Package Manifest *declares* what frameworks the target links — it does not "configure" individual source files. The relationship the model is detecting (target → linked frameworks → source files that import those frameworks) is a 3-hop transitive that the structural parser correctly does NOT emit as an edge. The model is inventing an edge type to describe a transitively-derivable property. Downstream `prep_impact` will treat these as real edges, so editing `Package.swift` will appear to "impact" 9 unrelated source files — false positive for blast-radius calculations.

The structural parser was correct to omit these; the LLM is filling a gap that shouldn't be filled.

**Finding #3 — the open question on the page is the right question, and the answer is yes.** Existing open question:

> Should we require `evidence_quote` to be substring-matched against input before accepting the edge?

Yes — and the substring requirement should be enforced inside the prompt (the model is asked to quote) AND post-hoc in the parser (drop edges whose `evidence` doesn't substring-match any of the source code in the batch). Two defenses, not one — the prompt instruction is best-effort; the parser check is hard.

**Proposed prompt edit (single change, in scope for Phase 140):**

```diff
-BATCHED_INFERRED_EDGES_SYSTEM = """You are a code analyst specializing in cross-file dependency detection.
-You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input file, in order.
-No markdown, no explanation outside the JSON."""
+BATCHED_INFERRED_EDGES_SYSTEM = """You are a code analyst specializing in cross-file dependency detection.
+You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input file, in order.
+No markdown, no explanation outside the JSON.
+
+EVIDENCE RULES:
+- The `evidence` field MUST be a verbatim quoted substring of the source code shown in this batch.
+  Format: `evidence: "<exact substring from source>"`. Do NOT paraphrase, summarize, or restate.
+- If you cannot quote a verbatim substring that demonstrates the edge, OMIT the edge.
+- Hedging language in evidence is FORBIDDEN: "likely", "would", "designed for",
+  "though source is not shown", "probably", "may use" — if your evidence contains
+  any of these, you are inferring rather than observing. Omit the edge instead.
+- Build manifests (Package.swift, package.json, requirements.txt, etc.) link frameworks
+  to TARGETS, not to individual source files. Do NOT emit `configures` edges from a
+  build manifest to a source file — only to other manifests or to build scripts.
+"""
```

Estimated impact: would have suppressed ~17 hedge-language edges and the 9 Package.swift→source `configures` edges = ~26 of 36 = **72% reject rate.** That's a lot. Two reads of this:

- **(a) The prompt is doing the wrong job.** If 72% of emit is noise, then "inferred edges" as currently constructed is producing more wrong-edges than right-edges. Worth a deeper architectural review (out of Phase 140 scope) — maybe the right batch-edges output volume should be 5-10 high-confidence edges per ~10 files, not 36.
- **(b) The prompt is doing the right job badly.** The right edges (lines 3, 7 — protocol conformance with high confidence 0.95) are valuable. The fix is to suppress the bad ones, not to abandon the prompt.

I lean (b): the high-confidence (≥0.85) edges with no hedge language are mostly sound. Tighten via the EVIDENCE RULES above and the noise drops.

**Verdict:** `analysis (no edit shipped this iteration).` The proposed edit is concrete and in scope, but its impact (72% of current edges suppressed) is large enough to warrant a careful side-by-side rerun before committing. Recommended: ship the edit as a separate iteration block, restart daemon, run a `fast`-group rebuild on PowerMate, capture new `powermate-reborn.jsonl`, diff line-by-line, decide kept/reverted by counting (a) protocol-conformance edges preserved, (b) hedge-language edges suppressed, (c) any false negatives — real edges erased because the model couldn't construct a quotable substring.

**Follow-up:**
1. Verify whether `prep_impact` is consuming inferred edges with `confidence < 0.7` — if it weights them down already, the noise impact is smaller than the raw count suggests.
2. Substring-match check in the parser (`build_batched_inferred_edges_prompt` consumer) as a second layer of defense. Where is the parser?

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield "attack the answer, don't verify it" — over-abduction).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §5 (Structured output: Geng et al. 2025 on schema overhead — the `evidence` field's free-text shape is what permits hedging; making it a constrained substring would help).
- Existing memory: `feedback_test_full_import_chain.md` — applies here too: any test of the new EVIDENCE RULES should test the post-hoc parser substring-check, not just the prompt-level instruction.

**Cross-references:** [`batch-symbol.md`](./batch-symbol.md), [`batch-file.md`](./batch-file.md) (sibling batched prompts; should audit their `evidence`-shaped fields for the same hallucination pattern).

### 2026-05-19: B2-followup — shipped EVIDENCE DISCIPLINE + BUILD-MANIFEST EXCEPTION

**Type:** prompt edit + schema edit (single iteration, ships the changes proposed in Iteration #1)

**Commit:** `3c22cb09 fix(prompts): Phase 140 B-side iterations — batched prompts (edges + epistemic)`

**Diff:**
```diff
 BATCHED_INFERRED_EDGES_SYSTEM = """You are a code analyst specializing in cross-file dependency detection.
 You MUST respond with a JSON object containing a "results" array. ...
 No markdown, no explanation outside the JSON.
+
+EVIDENCE DISCIPLINE:
+- The `evidence` field MUST be a verbatim quoted substring of the source code shown for that file.
+- If you cannot quote a verbatim substring that demonstrates the edge, OMIT the edge.
+- Hedging language in evidence is forbidden: "likely", "would", "designed for",
+  "though source is not shown", "probably", "may use", "could", "implies".
+
+BUILD-MANIFEST EXCEPTION:
+- Build manifests (Package.swift, package.json, pyproject.toml, etc.) declare what frameworks
+  a TARGET links — they do NOT "configure" individual source files.
+- Do NOT emit `configures` edges from a build manifest to a source file.
```

Also: `inferred_edges` structured-output schema now requires `evidence` (was optional). Enforces EVIDENCE DISCIPLINE at decode time for BYOK structured-outputs path.

**Confidence in shipping without rerun:** 95%. The failure mode (hedge language, build-manifest noise) is repo-agnostic and well-documented in the captured baseline. The risk surface is small: a model that genuinely cannot quote a verbatim substring would emit an empty edges array, which is correct behavior (the structural parser still catches real edges).

**Verdict:** **partial** — shipped to `main`; awaiting PowerMate finalize-group rerun for confirmation diff. Will re-verdict as `kept` if rerun shows:
- ≤15 inferred edges per file (was ~17/36 hedge-language items in 36-edge sample = 47% suppression hit rate)
- Zero `configures` edges from `Package.swift`
- All retained edges contain verbatim source substrings in `evidence`
- No new false positives in protocol-conformance edges (lines 3, 7 of the baseline jsonl).

**Follow-ups:**
1. Post-rerun: diff `outputs/batch-edges/powermate-reborn.jsonl` vs current baseline.
2. If kept: re-baseline snapshot under `snapshots/2026-05-19_B2-batch-edges-kept/`.
3. Sibling check: `batch-symbol`, `batch-file`, `batch-doc` schemas have `related_files` / similar fields — same hallucination pattern may apply, worth follow-up audit.

## Open questions
- Should we require `evidence_quote` to be substring-matched against input before accepting the edge?
   **Answered (B2-followup):** yes, shipped via EVIDENCE DISCIPLINE block + schema-required evidence field. Post-hoc parser substring-check is still recommended as a defense-in-depth layer.
- What's the false-positive rate when run against repos with no dynamic imports (should be near zero)?

## Cross-references
- Sibling: [batch-symbol](./batch-symbol.md), [batch-file](./batch-file.md)
- Phase 136 Part 2 — prep_impact bimodal node (related impact-graph concerns)

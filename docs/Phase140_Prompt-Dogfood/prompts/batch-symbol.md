# Batch — Symbol summaries

**File:** `src/prep/core/batch_prompts.py:22-54`
**Symbols:** `BATCHED_SYMBOL_SYSTEM`, `build_batched_symbol_prompt`
**Invoked by:** Augmenter worker (`src/prep/core/augmenter.py`)
**Pipeline stage:** fast (catalogue augmentation)
**Output schema:** structured JSON, schema at `batch_prompts.py:365-546`
**Status:** baseline

## Purpose
Generates compact per-symbol summaries (functions, classes, methods) for the trace graph. Outputs flow into the symbol overlays the catalogue serves to `prep_search` and `prep_impact`.

## Grounding (inputs)
- Batch of symbols with: name, file, signature, surrounding context
- Token budget per batch is bounded; batching is for throughput

## Output schema
JSON list, one entry per symbol. Schema enforces fields like `summary` (short), `purpose`, `key_args`. Validated server-side via JSON Schema (see `batch_prompts.py:365-546`).

## Known issues / hypotheses
- **Schema-vs-prompt drift**: schema lives at the bottom of `batch_prompts.py` and prompts up top. Easy for the prompt to ask for fields the schema rejects. Worth confirming round-trip on baseline.
- **Symbol context**: how much surrounding code is fed? Too little and summaries become vacuous; too much and tokens balloon. Hypothesis: there's a sweet spot we haven't measured.
- **Generic-function trap**: utility functions (e.g., `def get_id(self): return self.id`) produce summaries that are longer than the function. Worth seeing if the prompt could detect and produce shorter summaries.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-symbol/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-symbol/powermate-reborn.jsonl) — **mixed jsonl**: filter records by `node_id` starting `symbol:`. Generated 2026-04-29 by `gemini-3-flash-preview:cloud`.

## Iterations

### 2026-05-19: A3 — 64% of records are fallback stubs (not LLM output); role taxonomy too narrow

**Type:** analysis-only (no edit shipped)

**Read materials:**
- `BATCHED_SYMBOL_SYSTEM` + `build_batched_symbol_prompt` (`batch_prompts.py:22-54`).
- PowerMate output: [`../snapshots/2026-05-17_baseline/outputs/batch-symbol/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-symbol/powermate-reborn.jsonl) — 311 entries, model `gemini-3-flash-preview:cloud`.

**Finding #1 — 199 of 311 records (64%) have `confidence: 0.1` and stub-shaped summaries.** Examples:

| node_id | role | summary |
|---|---|---|
| sym:AppDelegate@Sources/AppDelegate.swift:34 | internal | Swift class 'AppDelegate' in Sources/AppDelegate.swift |
| sym:BrightnessController@Sources/BrightnessController.swift:21 | internal | Swift class 'BrightnessController' in Sources/BrightnessController.swift |
| sym:AudioDeviceInfo@Sources/VolumeController.swift:27 | internal | Swift class 'AudioDeviceInfo' in Sources/VolumeController.swift |

These are NOT LLM-augmented — the summary is literally "Swift class 'X' in Y.swift" (parameterized template). The `confidence: 0.1` and `role: "internal"` are the fallback values. So the LLM was either not called for these symbols, or its response was rejected and a fallback applied.

**The captured snapshot represents only the 112 entries (36%) that got real LLM output.** Of those, confidence distribution:
- 0.85: 8
- 0.9: 41
- 0.95: 46
- 1.0: 17

That's a clumping at 0.9-0.95 — the exact float-clumping memory `project_llm_confidence_calibration.md` warns about. Worth porting the named-tier (T1/T2/T3) rubric from concept prompts to this one.

**Finding #2 — `role` taxonomy is too narrow; 208 of 311 fall into "internal" catch-all.** The role values emitted: `internal` (208), `ui` (28), `api` (19), `handler` (19), `core` (15), `utility` (9), `documentation` (7), `config` (2), `script` (2), `model` (2). The prompt's allowed roles (per line 50): `entry_point, handler, utility, model, config, test, internal, script, api, core, ui`.

`internal` is a catch-all for "I don't know what category this fits" — when 67% of symbols fall in catch-all, the taxonomy is too narrow. Notable gaps:
- No `controller` (for things like BrightnessController, MIDIController — the bulk of PowerMate's symbols)
- No `transport` / `driver` (PowerMateUSBTransport, PowerMateBLETransport)
- No `protocol` / `delegate` (Swift protocol definitions)

For Swift codebases specifically, the taxonomy is misfit. For Python it's probably fine.

**Finding #3 — `related_files` field is suspiciously sparse.** Only 16 of 311 entries emit `related_files` (5%). Either:
- The model is being conservative (correct, given grounding §9 — don't invent edges).
- The model doesn't know what to put because the grounding doesn't include neighbor symbols.

Without the prompt source for what's in grounding, hard to say. But 5% suggests the model is correctly NOT hallucinating related files when it doesn't know. Good behavior.

**Finding #4 — schema-vs-prompt page hypothesis #1 is real but bounded.** Prompt asks for fields `summary, role, confidence`. Schema at `batch_prompts.py:405-424` matches. No drift observed in the captured output. ✓

**Verdict:** **analysis (no edit shipped this iteration).** Three deferred actions:

1. **Investigate why 64% of symbols got fallback stubs.** Not a prompt issue — probably an augmenter-batching issue (per-batch failures, skipped symbols, batch-size caps). Out of Phase 140 scope.
2. **Widen role taxonomy for Swift / iOS code** — add `controller`, `transport`, `protocol` to the allowed values. Or make the taxonomy language-aware. In scope as a prompt-copy edit but should ship after observability on the fallback-stub issue.
3. **Port named-tier confidence rubric** from concept prompts (T1/T2/T3 → 0.30/0.65/0.92) instead of free-float confidence. Would close the clumping observation. In scope but coordinates with other batched prompts using the same pattern.

None of these are obviously high-confidence enough to ship now. Better to wait until we have full coverage (not fallback stubs) so the analysis isn't sampling-bias.

**Grounding citations:**
- Memory: `project_llm_confidence_calibration.md` — directly applies to confidence-clumping observation.
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §7 (named tiers > floats).

**Cross-references:** [`batch-file.md`](./batch-file.md), [`batch-doc.md`](./batch-doc.md) (siblings — same batched-augmenter family).

## Open questions
- Should symbol summaries cite their file location (redundant with grounding) or stay name-only?
- Trivial / one-liner symbols — is there value in summarizing them at all?

## Cross-references
- Sibling: [batch-file](./batch-file.md), [batch-doc](./batch-doc.md), [batch-cluster](./batch-cluster.md)
- Phase 136 Part 1 — File role split for search

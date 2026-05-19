# Batch — File roles

**File:** `src/prep/core/batch_prompts.py:59-97`
**Symbols:** `BATCHED_FILE_SYSTEM`, `build_batched_file_prompt`
**Invoked by:** Augmenter worker (`src/prep/core/augmenter.py`)
**Pipeline stage:** fast (catalogue augmentation)
**Output schema:** structured JSON — file role classification (hub / entry / leaf / config / test / etc.) plus summary
**Status:** baseline

## Purpose
Classifies each code file by role and produces a brief summary. Role labels feed the atlas's WORKSPACE MAP and the dashboard's file inventory; summaries feed `prep_search`.

## Grounding (inputs)
- Batch of files with: path, language, leading byte slice (truncated)
- Import / export hints from the structural graph

## Output schema
JSON list. Each: `{path, role, summary, primary_responsibility}`. Schema at `batch_prompts.py:365-546`.

## Known issues / hypotheses
- **Phase 136 Part 1 (File role split for search)**: revealed file-role classification was conflating multiple dimensions. Verify the prompt's role label vocabulary post-fix matches what the search layer expects.
- **Truncation artifacts**: leading byte slice may cut off mid-function. Hypothesis: roles get miscalled when truncation happens to land on imports vs body. Worth inspecting outputs for files known to be truncated.
- **Off-by-language miscalls**: TS files with `.tsx` extension sometimes get classified as React component when they're really utility — possibly because the prompt over-weights extension.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-file/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-file/powermate-reborn.jsonl) — **mixed jsonl**: filter records by `node_id` starting `file:` with `role` set

## Iterations

### 2026-05-19: A4 — well-engineered; related_files moderate hallucination risk; confidence clumping

**Type:** analysis-only (no edit shipped)

**Read materials:**
- `BATCHED_FILE_SYSTEM` + `build_batched_file_prompt` (`batch_prompts.py:59-97`).
- PowerMate output: filtered from [`../snapshots/2026-05-17_baseline/outputs/batch-file/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-file/powermate-reborn.jsonl) — 18 file records (filtering out 6 with doc_type and 287 sym: records that share the same jsonl).

**Snapshot methodology note:** All four `batch-*` snapshot files (`batch-file`, `batch-doc`, `batch-narrative`, `batch-symbol`) are byte-identical (md5 `34ab6e2e9b6ba60741684f5256037626`). The catalogue augmenter produces ONE `trace_augmented.jsonl` with mixed file/symbol/doc records; capture-notes copied it into 4 site directories without filtering. Future re-baselines should either (a) filter at capture time, or (b) acknowledge the shared-source.

**Strong points:**

1. **100% LLM coverage of file records** — all 18 file records have real summaries (confidence 0.9-1.0), unlike batch-symbol which had 64% fallback stubs.
2. **Role taxonomy maps well to Swift** — distribution: 9 core, 3 ui, 2 config, 2 script, 1 utility, 1 documentation. Notably NO `internal` catch-all this time (compare batch-symbol's 67%-internal). The smaller file count (24 vs 287 symbols) plus more-distinguishable file-level signal probably accounts for the difference.
3. **Summary quality is high** — examples:
   - `Sources/AppDelegate.swift`: "Application delegate managing the lifecycle, menu bar interface, user settings persistence, and coordination between different control modes like Volume, Brightness, and MIDI." (factually grounded)
   - `Sources/BrightnessController.swift`: "Manages display brightness adjustments across multiple monitors using native APIs, DDC/CI hardware commands, or software-based gamma and overlay fallbacks." (matches the 5-strategy fallback chain in source)

**Finding #1 — `related_files` quality is mixed (similar to batch-edges pattern).** 16 of 18 records emit related_files. Spot check:

| File | Related files | Quality |
|---|---|---|
| Package.swift | `[Sources/AppDelegate.swift]` | Weak — Package.swift relates to ALL Swift files (target), not just AppDelegate. Same Package.swift→source confused pattern as batch-edges. |
| Sources/AppDelegate.swift | `[BrightnessController, CustomModeEngine, CustomModeSettingsView]` | Correct — these are AppDelegate's instantiated controllers. |
| Sources/BrightnessController.swift | `[AppDelegate]` | Direction-arguable — BrightnessController doesn't import AppDelegate, but is owned by it. Defensible. |
| Sources/CustomModeSettingsView.swift | `[CustomModeEngine]` | Correct — direct dependency. |
| Sources/DDCController.swift | `[OSDOverlay]` | **Questionable** — these are peer hardware/UI files, no direct call relationship. |
| Sources/MIDIController.swift | `[]` | Correct conservatism — no specific related-file. |
| Sources/MenuBarIcon.swift | `[OSDOverlay]` | **Questionable** — MenuBarIcon is a pure CoreGraphics renderer; OSDOverlay is a separate UI surface. No direct relation. |

Estimated 4-6 of 16 emitted related_files (25-40%) are questionable or wrong. Lower stakes than `batch-edges` (related_files don't feed prep_impact), but downstream consumers (`prep_search` related-files surface) get noisy results.

**Recommendation if iterating:** port a softer version of `batch-edges` EVIDENCE DISCIPLINE clause — "Only emit related_files when you can quote a verbatim import statement, function call, type reference, or string-based reference from the source code shown above. If you cannot quote a verbatim grounding, omit the file from related_files." Confidence: 85% this would suppress the questionable cases without losing the correct ones.

**Finding #2 — confidence distribution clumps at 0.9-0.95.** 13 records at 0.95, 3 at 1.0, 2 at 0.9. Zero records below 0.9. This is the float-clumping pattern memory `project_llm_confidence_calibration.md` warns about. The named-tier rubric (T1/T2/T3) used by concept prompts would be a better fit.

**Finding #3 — role taxonomy fits Swift well in this capture.** Page hypothesis #1 about Phase 136 Part 1 role-split: outputs use the post-fix taxonomy (`core`, `ui`, `config`, `script`, `utility`, `documentation`) — no `internal` catch-all on file records. ✓ Good.

**Verdict:** **analysis (no edit shipped).** Two deferred actions:

1. **Port batch-edges-style EVIDENCE DISCIPLINE to related_files** — 85% confidence this would improve quality.
2. **Port named-tier confidence rubric** from concept prompts — coordinates with same fix recommended for `batch-symbol`.

Neither is shipped now because both involve coordinating across siblings (batch-doc, batch-narrative, batch-symbol use the same patterns). Better to do them all in one coordinated commit after we capture each prompt's output separately.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §7 (named tiers > floats for confidence).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield over-abduction — `related_files` is a small attack surface for the same pattern).
- Memory: `project_llm_confidence_calibration.md`.

**Cross-references:** [`batch-symbol.md`](./batch-symbol.md) (sibling — confidence clumping + role taxonomy), [`batch-doc.md`](./batch-doc.md), [`batch-narrative.md`](./batch-narrative.md), [`batch-edges.md`](./batch-edges.md) (proven EVIDENCE DISCIPLINE pattern to port).

## Open questions
- Is the role taxonomy stable, or does it drift as the codebase grows?
- For files <100 bytes, should we skip the LLM call entirely?

## Cross-references
- Sibling: [batch-symbol](./batch-symbol.md), [batch-doc](./batch-doc.md), [batch-narrative](./batch-narrative.md)
- Phase 136 Part 1 — File role split for search

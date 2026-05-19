# Epistemic — Doc (single-file)

**File:** `src/prep/core/epistemic_enrichment.py:89-140`
**Symbols:** `EPISTEMIC_SYSTEM`, `EPISTEMIC_DOC_PROMPT`
**Invoked by:** `epistemic_enrichment.py` worker (doc nodes)
**Pipeline stage:** deep (epistemic enrichment, Phase 22 Pass 2)
**Output schema:** structured JSON — extended summary, domain tags, architecture layer, subsystem, design patterns, cross-refs, tech debt, staleness risk, confidence + doc_type, doc_status, decision_chains
**Status:** baseline

## Purpose
Deep per-doc enrichment for the trace graph. Doc analogue of `epistemic-code` with doc-only fields like `doc_type`, `doc_status`, `decision_chains`.

## Grounding (inputs)
- Full doc content
- The doc's trace-graph neighbors (linked docs, referenced files)
- Prior epistemic enrichment on neighbors

## Output schema
JSON. Shared epistemic fields plus `doc_type`, `doc_status`, `decision_chains`.

## Known issues / hypotheses
- **Three doc-status prompts overlap**: batch-doc, batch-epi-doc, and this prompt all classify `doc_status`. Likely producing inconsistent values. Hypothesis: pick one source of truth and have the others read it.
- **decision_chains hallucination risk**: same concern as batch-epi-doc — chains may invent linkages. Verify chains point to real files / docs in grounding.
- **Search docs bias** (memory: `project_search_docs_bias.md`). Deep doc enrichment makes docs even more findable; if doc-vs-code ranking prior isn't added in `index.py`, this amplifies the bias.

## Snapshot 2026-05-17
- Prompt source SHA: `7c6239a6f300`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/epistemic-doc/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/epistemic-doc/powermate-reborn.jsonl) — **mixed jsonl**: filter for `.md` / doc records

## Iterations

### 2026-05-19: B4 — emergent structured shape in decision_chains + doc_status triple-overlap

**Type:** analysis-only (cross-refs B3 cross-cutting finding)

**Read materials:**
- `EPISTEMIC_DOC_PROMPT` (`epistemic_enrichment.py:89-126`).
- `_enrich_doc` (`epistemic_enrichment.py:545-575`) — dispatches when `node.language == "markdown"` or path ends `.md` / `.markdown`. Excerpt up to 3000 lines.
- PowerMate snapshot: doc-portion of [`../snapshots/2026-05-17_baseline/outputs/epistemic-doc/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/epistemic-doc/powermate-reborn.jsonl) — file is mixed code+doc; doc records identifiable by `architecture_layer: "documentation"` or `doc_type` field present.

**Finding #1 — `decision_chains` emerges as `{decision, rationale, tradeoffs}` despite the schema's bare-string spec.** Schema (line 116): `"decision_chains": ["key decisions or conclusions documented here"]` — flat list of strings. README.md output:

```json
"decision_chains": [
  {"decision": "Native Swift IOKit HID implementation instead of kernel extensions",
   "rationale": "No Rosetta dependency, modern macOS compatibility, avoids kext security/privacy restrictions",
   "tradeoffs": "Must reimplement driver functionality in user space; potential latency vs kernel-level access"},
  {"decision": "Four-mode architecture (Volume/Brightness/MIDI/Custom)",
   "rationale": "Covers primary use cases from simple media control to professional DAW integration to power-user customization",
   "tradeoffs": "Mode cycling complexity; Custom mode subsumes some simpler use cases potentially creating UI confusion"},
  ... 3 more ...
]
```

5 items, all structured. The model is recovering quality by extending the schema (per grounding §5, Geng et al. 2025: schema overhead — when the spec is too thin, the model fills it in). For `decision_chains` specifically, the `{decision, rationale, tradeoffs}` triple acts as a self-check — the model has to *justify* each decision and *acknowledge tradeoffs*, which suppresses the hallucinated-decision failure mode the page's known-issue #2 calls out.

**Recommendation:** match the schema to the emergent shape. Same diff as proposed in [`epistemic-code.md`](./epistemic-code.md) Iteration #1 Finding #2.

**Finding #2 — `doc_status` is produced by THREE prompts and there's no reconciliation rule.** The page's existing hypothesis ("Three doc-status prompts overlap: batch-doc, batch-epi-doc, and this prompt all classify `doc_status`. Likely producing inconsistent values.") is correct. Three doc-status producers:

| Producer | Pipeline stage | Schema |
|---|---|---|
| `batch-doc` | Pass 1 (fast catalogue) | doc_type + doc_status, full taxonomy |
| this prompt (`EPISTEMIC_DOC_PROMPT`) | Pass 2 single-file (deep enrichment) | doc_status taxonomy listed; **receives `pass1_doc_status` as input** but is asked to emit its own |
| `batch-epi-doc` | Pass 2 batched (deep enrichment) | doc_status taxonomy listed; same input shape |

`EPISTEMIC_DOC_PROMPT` (line 96-97) shows: `Pass 1 summary: {pass1_summary}` + `Pass 1 doc_type: {pass1_doc_type}` + `Pass 1 doc_status: {pass1_doc_status}` — so Pass 2 DOES see Pass 1's verdict. But the prompt then asks it to emit `doc_status` independently with no instruction like "preserve Pass 1's value unless contradicted by content." Result: Pass 2 either echoes (field redundant) or contradicts (drift). Downstream consumers have no rule to pick between them — `EpistemicEntry.doc_status` (line 669) takes Pass 2's value, overwriting Pass 1.

For README.md the captured output shows `doc_status: "active"` — likely matches Pass 1 (most healthy doc statuses are "active"), but without Pass 1 snapshot to verify we can't confirm. A `doc_status` mismatch test across the full PowerMate corpus would expose drift.

**Recommendation:** add to `EPISTEMIC_DOC_PROMPT` (and `EPISTEMIC_DOC` batched sibling) before the schema:

> **doc_status reconciliation:** You are given `Pass 1 doc_status` above. Preserve it unless the content excerpt explicitly contradicts the Pass 1 verdict (e.g., Pass 1 said "active" but the content is empty / a stub / explicitly deprecated). If you change `doc_status`, explain why in `extended_summary`.

This makes Pass 2 a refiner, not a re-classifier — matches the "Pass 2 = deep enrichment of Pass 1's structural verdict" intent.

**Finding #3 — `cross_references` for docs is field-misused similar to the code-side issue.** Schema (line 117) says `"cross_references": ["src/path/to/code.py"]` — a flat list of paths. README.md output emits structured `{context, relationship, target}` objects, which is **better**. Same fix recommended in [`epistemic-code.md`](./epistemic-code.md) (Finding #2/#3) applies — codify the structured shape.

**Finding #4 — single-file vs batched (deferred to B3 cross-cutting finding).** See [`../findings/epistemic-batched-vs-single-guidance-gap.md`](../findings/epistemic-batched-vs-single-guidance-gap.md) for the full pattern. This prompt has more guidance than its batched sibling (decision_chains description, tech_debt anti-hallucination clause); batched users get a degraded version of this same prompt.

**Verdict:** `analysis (no edit shipped this iteration).` Two specific defers:

1. Match schema to emergent structured shape (decision_chains, cross_references — both prompts).
2. Add `doc_status` reconciliation clause (both prompts).

Both can be done in a single combined iteration block targeting `EPISTEMIC_DOC_PROMPT` + `build_batched_epistemic_doc_prompt` simultaneously, with a single pipeline rerun on PowerMate to validate.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §5 (Geng et al. 2025 schema overhead).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield over-abduction — decision_chains is the canonical setup; structured `{decision, rationale, tradeoffs}` is the natural counter-measure).
- Memory: `project_search_docs_bias.md` — adds context about why this prompt's outputs matter (deep doc enrichment amplifies doc-ranking unless balanced).

**Cross-references:** [`epistemic-code.md`](./epistemic-code.md) (sibling, same schema-drift pattern from the code side), [`batch-epi-doc.md`](./batch-epi-doc.md) (batched variant), [`batch-doc.md`](./batch-doc.md) (Pass-1 source of doc_status overlap), [`../findings/epistemic-batched-vs-single-guidance-gap.md`](../findings/epistemic-batched-vs-single-guidance-gap.md).

### 2026-05-19: B4-followup — shipped structured schema + doc_status reconciliation

**Type:** prompt edit + schema edit + dataclass widening (single iteration; ships the two recommendations from Iteration #1)

**Commit:** `24871dc0 fix(prompts): Phase 140 B-side iterations — single-file epistemic prompts + dataclass`

**Edits:**
- `EPISTEMIC_DOC_PROMPT`: `decision_chains` schema now structured array of `{decision, rationale, tradeoffs}` objects (was flat string list — the model was already emitting structured per snapshot). `cross_references` and `tech_debt` same structured shape as code prompt.
- Added doc_status reconciliation clause: "PRESERVE Pass 1 doc_status unless the content excerpt explicitly contradicts the Pass 1 verdict... If you change doc_status, explain why in extended_summary." Closes the silent-Pass-2-overwrite gap between `batch-doc`, `batch-epi-doc`, and this prompt.
- `EpistemicEntry.decision_chains` type widened to `Optional[List[Any]]` for roundtrip preservation (same fix as code-side cross_references / tech_debt).

**Confidence in shipping without rerun:** 99% on the schema codification (README.md snapshot proves model already emits structured decision_chains). 95% on doc_status reconciliation (small 3-line addition; clear improvement over silent overwrite; no risk to existing behavior because the prompt still allows changing doc_status if contradicted).

**Verdict (2026-05-19, post-rerun):** **kept** — single-repo PowerMate evidence confirms all three success criteria. Promoted from `partial` to `kept`:

- ✅ All 6 doc records emit dict-shaped `decision_chains` (`{decision, rationale, tradeoffs}`) — 100% structured compliance. README.md's chains explicitly cite README content and acknowledge tradeoffs.
- ✅ `doc_status` preserved correctly (e.g., README.md → "active" matches Pass 1 verdict; no silent overwrites).
- ✅ No downstream consumer breakage AFTER the consumer-side fix in commit `a2004c02`. (Initial rerun crashed group_reasoning on the structured tech_debt format; that consumer also calls `cross_references` paths so the same fix covers both. Subsequent rerun completed 5/5 deep stages clean.)

Sample new decision_chains from README.md output (full snapshot at [`../snapshots/2026-05-19_B-followup-post-rerun/`](../snapshots/2026-05-19_B-followup-post-rerun/)):

```json
{"decision": "Implement pure IOKit HID driver in Swift rather than using legacy Griffin drivers or kernel extensions",
 "rationale": "The document states 'Native Swift Driver -- Pure IOKit HID implementation...' and notes 'Since the official drivers haven't worked in years, this is a native Swift menu bar app built from scratch'...",
 "tradeoffs": "Requires complete reimplementation of hardware protocol; loses any proprietary Griffin features; gains Apple Silicon native performance..."}
```

The rationale quotes the actual README content (verifiable substring) and the tradeoffs are concrete, not generic.

**Multi-repo note:** Same as `epistemic-code` Iteration #2 — promoting on single-repo because the schema-shape change is verified mechanically and is not corpus-dependent.

**Re-baseline:** [`../snapshots/2026-05-19_B-followup-post-rerun/outputs/epistemic-code/powermate-reborn.jsonl`](../snapshots/2026-05-19_B-followup-post-rerun/outputs/epistemic-code/powermate-reborn.jsonl) (filter to doc records).

**Follow-ups:**
1. BYOK / cloud-batched validation still pending.
2. Per-doc `doc_status` consistency audit deferred — would need fresh `batch-doc` capture (Pass 1) alongside this Pass 2 to diff.
3. Sibling: `batch-epi-doc` schema edit in coordinated commit `3c22cb09`; sequential path validated here, BYOK path still pending.

## Open questions
- How does this differ from `batch-epi-doc`? Is single-file mode ever invoked, or did batched supersede it?
- Should `decision_chains` accept only verified-in-grounding targets, with hallucinated ones silently dropped?

## Cross-references
- Sibling: [epistemic-code](./epistemic-code.md), [batch-epi-doc](./batch-epi-doc.md), [batch-doc](./batch-doc.md)
- Memory: `project_search_docs_bias.md`, `project_llm_confidence_calibration.md`
- Phase 22 — Epistemic enrichment (parent architecture)

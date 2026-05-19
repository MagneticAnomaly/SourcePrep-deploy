# Finding — epistemic batched prompts drop field-level guidance carried by their single-file siblings

**Discovered:** 2026-05-19 (during Phase 140 B3 audit of `batch-epi-code` + `batch-epi-doc` + `epistemic-code`)
**Severity:** Quality-affecting, BYOK/cloud profile only; not a correctness bug
**Status:** Documented, awaiting follow-up batched-output capture for direct verdict

## TL;DR

SourcePrep has two parallel epistemic-enrichment prompt families:

- **Sequential / single-file** (`epistemic_enrichment.py`): `EPISTEMIC_CODE_PROMPT` and `EPISTEMIC_DOC_PROMPT` — used for local LLM / sequential pipeline.
- **Batched** (`batch_prompts.py`): `BATCHED_EPISTEMIC_CODE_SYSTEM` + `build_batched_epistemic_code_prompt` and `BATCHED_EPISTEMIC_DOC_SYSTEM` + `build_batched_epistemic_doc_prompt` — used for BYOK / cloud profile pipelines (`_enrich_tier_batched`).

The two families share the **same schema** but the batched prompts have **lost the per-field guidance** the single-file prompts carry. Result: BYOK/cloud users get **less-steered, lower-quality** epistemic enrichment than local-sequential users, on identical input.

This is invisible from inside Phase 140's snapshot (the snapshot is from the sequential path) — but the divergence is in the code and the dispatch logic.

## Affected sites

| Site | File | Path |
|---|---|---|
| `batch-epi-code` | `batch_prompts.py:221-259` | [`../prompts/batch-epi-code.md`](../prompts/batch-epi-code.md) |
| `batch-epi-doc` | `batch_prompts.py:264-308` | [`../prompts/batch-epi-doc.md`](../prompts/batch-epi-doc.md) |
| `epistemic-code` | `epistemic_enrichment.py:53-87` | [`../prompts/epistemic-code.md`](../prompts/epistemic-code.md) |
| `epistemic-doc` | `epistemic_enrichment.py:89-126` | [`../prompts/epistemic-doc.md`](../prompts/epistemic-doc.md) |

## Evidence

### What single-file has and batched lacks

Field-by-field, single-file CODE vs batched CODE:

| Field | Single-file guidance | Batched guidance |
|---|---|---|
| `domain_tags` | "1-4 descriptive tags for the domain this file operates in (e.g. 'monetization', 'auth', 'ui', 'data-persistence')" | `["tag1", "tag2"]` — no count, no examples |
| `subsystem` | "the logical subsystem this file belongs to (e.g. 'ad-framework', 'user-auth', 'trace-engine')" | `"name-of-subsystem"` — no examples |
| `design_patterns` | "any notable patterns used (empty list if none)" | `[]` — no "empty if none" nudge |
| `cross_references` | "documentation files that describe or relate to this code" | `[]` — no description (target type unspecified) |
| `tech_debt` | "list ONLY explicit markers (TODO, FIXME) or severe architectural flaws. Do not list potential improvements or nitpicks." | `[]` — no scope restriction whatsoever |
| `staleness_risk` | "low\|medium\|high — how likely is this file's understanding to become stale" | `"low\|medium\|high"` — taxonomy without description |

Single-file DOC vs batched DOC:

| Field | Single-file guidance | Batched guidance |
|---|---|---|
| `decision_chains` | "key decisions or conclusions documented here" | `[]` — no description (highest-hallucination-risk field per [Caulfield's over-abduction critique][1]) |
| `tech_debt` | "list ONLY explicit issues found in the text. Do not hallucinate or guess." | `[]` — no anti-hallucination clause |
| `cross_references` | (inherits "files this doc references") | `["src/path.py"]` — bare example, no description |

### System prompt divergence

| Aspect | `EPISTEMIC_SYSTEM` (single-file, shared) | `BATCHED_EPISTEMIC_*_SYSTEM` |
|---|---|---|
| Persona | "expert software architect performing deep analysis of a codebase" | "senior software architect performing deep epistemic analysis of source code/doc files" |
| Anchoring | "produce structured, accurate analysis **grounded in the actual code and documentation**" | (dropped) |
| Output discipline | "valid JSON only. No markdown, no explanation outside the JSON." | "JSON object containing a 'results' array. ... No markdown, no explanation outside the JSON." (same plus 'results' wrapper) |

The "grounded in the actual code and documentation" clause is Constitutional-AI-style (grounding §4) explicit intent steering. The batched system prompts drop it entirely.

## Why this happens

Most likely explanation: the batched prompts were added later (the BYOK / cloud-batched profile is a more recent feature) and copied the schema structure from the single-file prompts without copying the inline descriptions. The schema looks "the same," so the divergence is invisible to a reviewer reading the JSON spec — only a side-by-side of the full prompts reveals the gap.

The pipeline picks between sequential and batched based on `use_batching = self._batch_profile is not None and self._batch_profile.name.value != "off"` (`epistemic_enrichment.py:1085-1088`). Local / sequential gets the well-steered prompt. BYOK / cloud-batched gets the under-steered prompt. Both write to the same downstream artifact (`trace_epistemic.jsonl`), so downstream consumers see the divergence as "quality varies by deployment."

## Confidence in the prediction

**Code-structural finding: high confidence.** The prompts are quoted verbatim above; the gap is undeniable.

**Output-divergence prediction: medium-high confidence, pending capture.** We have:
- Single-file snapshot output (captured 2026-04-30) shows specific failure modes — `tech_debt` ignores its scope-restriction in 26/26 sampled items (see [`epistemic-code.md`](../prompts/epistemic-code.md) Iteration #1), schema-drift in `cross_references` / `decision_chains` / `tech_debt`.
- Batched output not separately captured for SourcePrep or PowerMate.

If single-file already ignores its own `tech_debt` instruction, batched-without-that-instruction is at minimum no worse on `tech_debt`. But on `domain_tags` (single-file has 1-4 count + examples; batched has neither), batched is likely to either overflow count or use over-generic tags. On `decision_chains` (single-file has nothing-too-restrictive but emerged into structured `{decision, rationale, tradeoffs}`; batched has nothing too), batched will likely emit bare-string fabrications more often.

The right next step is to capture batched output and diff. A 10-file side-by-side rerun against PowerMate would suffice.

## Recommendation

**Phase 140 scope (prompt-copy fix):**

Port the single-file field-level guidance into the two batched prompts. Concrete diff for `build_batched_epistemic_code_prompt`:

```diff
     parts.append(
         '\nFor each file, respond with: '
         '{"id": <file_number>, "file": "<file_path>", '
-        '"extended_summary": "2-4 sentence detailed description", '
-        '"domain_tags": ["tag1", "tag2"], '
-        '"architecture_layer": "<presentation|business_logic|...>", '
-        '"subsystem": "name-of-subsystem", '
-        '"design_patterns": [], '
-        '"cross_references": [], '
-        '"tech_debt": [], '
-        '"staleness_risk": "low|medium|high", '
+        '"extended_summary": "2-4 sentence detailed description", '
+        '"domain_tags": ["1-4 descriptive tags (e.g. monetization, auth, ui, data-persistence)"], '
+        '"architecture_layer": "<presentation|business_logic|...>", '
+        '"subsystem": "logical subsystem (e.g. ad-framework, user-auth, trace-engine)", '
+        '"design_patterns": ["only notable patterns; empty list if none"], '
+        '"cross_references": ["doc files that describe this code; not source files"], '
+        '"tech_debt": ["ONLY explicit TODO|FIXME|XXX|HACK markers. If none, emit []."], '
+        '"staleness_risk": "low|medium|high — likelihood file changes a lot",  '
         '"epistemic_confidence": 0.85}'
     )
```

Parallel diff for `build_batched_epistemic_doc_prompt` (focus on `decision_chains` anti-hallucination + `tech_debt` anti-hallucination + `doc_status` Pass-1 reconciliation clause).

**Also: restore the dropped anchoring clause** in both `BATCHED_EPISTEMIC_*_SYSTEM` prompts:

```diff
 BATCHED_EPISTEMIC_CODE_SYSTEM = """You are a senior software architect performing deep epistemic analysis of source code files.
+You produce structured, accurate analysis grounded in the actual code shown in each item.
 You MUST respond with a JSON object containing a "results" array. Each element corresponds to one input file, in order.
 No markdown, no explanation outside the JSON."""
```

**Verification plan:**

1. Apply the diffs above.
2. Restart daemon.
3. Run `fast`+`deep` pipeline on PowerMate with BYOK / cloud profile enabled (`PREP_BATCH_PROFILE=cloud` or similar).
4. Capture into `snapshots/<date>_batched-epi-port/outputs/{batch-epi-code,batch-epi-doc}/powermate-reborn.jsonl`.
5. Diff vs (a) the pre-port batched output (capture once before the change to baseline), (b) the sequential single-file output already captured 2026-04-30.
6. Verdict criteria: per-field `domain_tags` count compliance (target: 100% in 1-4 range), `tech_debt` explicit-marker compliance (target: ≥80% items contain `TODO|FIXME|XXX|HACK` substring after the fix; currently 0% in single-file output), `decision_chains` shape compliance (target: 100% structured objects, not bare strings).

**Out of Phase 140 scope but flagged:** the underlying issue — single-file's `tech_debt` instruction being ignored 26/26 times in the captured output — suggests the model's "expert architect" persona overrides negatively-scoped instructions. Both prompt families may need a structural rethink (e.g., split `tech_debt` into `explicit_markers` and `design_concerns` channels) that won't fit in a copy-only edit. That's a Phase 22 successor / Phase 124-equivalent task, not Phase 140.

## What changes downstream when this ships

After the guidance-port:
- BYOK / cloud-batched outputs gain the constraints the sequential outputs already have.
- `domain_tags` distribution narrows (1-4 instead of unbounded).
- `tech_debt` shifts toward empty-or-markers (if the instruction works in batched context — it doesn't work in sequential, but batched's less assertive persona may comply better).
- `decision_chains` doc outputs emit structured objects more reliably.

The single-file path is unchanged; this is a one-way uplift for the BYOK path.

## Cross-references

- [`../prompts/batch-epi-code.md`](../prompts/batch-epi-code.md) Iteration #1
- [`../prompts/batch-epi-doc.md`](../prompts/batch-epi-doc.md) Iteration #1
- [`../prompts/epistemic-code.md`](../prompts/epistemic-code.md) Iteration #1 — provides the output-side evidence that even the well-guided sequential prompt is being ignored on `tech_debt`; expect worse on batched without the instruction.
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §4 (Constitutional AI: explicit principles), §5 (Structured Outputs: schema is orthogonal to content guidance), §6 (Persona alone is weak — need instruction).
- Memory: `feedback_test_full_import_chain.md` — any verification of this finding must exercise the actual BYOK code path, not just call the prompt builder.

[1]: https://mikecaulfield.substack.com/p/is-the-llm-response-wrong-or-have

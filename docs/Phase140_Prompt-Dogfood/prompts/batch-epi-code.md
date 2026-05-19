# Batch — Epistemic code

**File:** `src/prep/core/batch_prompts.py:221-259`
**Symbols:** `BATCHED_EPISTEMIC_CODE_SYSTEM`, `build_batched_epistemic_code_prompt`
**Invoked by:** Epistemic enrichment worker (deep pass)
**Pipeline stage:** deep (epistemic enrichment)
**Output schema:** structured JSON — deep code analysis (architecture layer, subsystem, design patterns, cross-refs, tech debt, staleness, confidence)
**Status:** baseline

## Purpose
Batched version of the single-file epistemic code prompt. Used when throughput matters more than per-file context depth — typically the bulk pass over many files.

## Grounding (inputs)
- Batch of code files with full content (or large slice)
- Their position in the trace graph (in/out degree)

## Output schema
JSON list, fields including: `extended_summary`, `domain_tags`, `architecture_layer`, `subsystem`, `design_patterns`, `cross_refs`, `tech_debt`, `staleness_risk`, `confidence`.

## Known issues / hypotheses
- **Overlap with single-file epistemic-code prompt** (`epistemic_enrichment.py:53-87`). Both produce the same fields — when do we use which? If batched is "fast path" and single-file is "deep path," the prompts should diverge in instruction tightness; verify they do.
- **Layer taxonomy**: architecture_layer values (presentation / domain / infra / etc.) are not standardized in any documented vocabulary I've seen. Hypothesis: outputs drift across batches because the model invents categories.
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). If the prompt asks for a 0-1 float, expect clumping around 0.7-0.85. Switch to named tiers.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured: TBD

## Iterations

### 2026-05-19: B3 — field-level guidance gap vs single-file sibling

**Type:** analysis-only (no prompt edit, snapshot not separately captured for batched path)

**Read materials:**
- `BATCHED_EPISTEMIC_CODE_SYSTEM` + `build_batched_epistemic_code_prompt` (`batch_prompts.py:221-259`).
- Sibling single-file prompt `EPISTEMIC_CODE_PROMPT` (`epistemic_enrichment.py:53-87`).
- Caller: `_enrich_tier_batched._call_code_batch` (`epistemic_enrichment.py:755-791`) — uses `response_schema=code_schema` (structured outputs / strict JSON) and `BATCHED_EPISTEMIC_CODE_SYSTEM`.

**Finding #1 — batched prompt drops the field-level guidance that the single-file sibling carries.** Side-by-side comparison:

| Field | Single-file (`EPISTEMIC_CODE_PROMPT`) | Batched (`build_batched_epistemic_code_prompt`) |
|---|---|---|
| `architecture_layer` | "Where architecture_layer is one of: presentation, business_logic, ..." (full taxonomy listed) | `"architecture_layer": "<presentation\|business_logic\|data\|...>"` (taxonomy in pipe-syntax — equivalent) |
| `domain_tags` | "1-4 descriptive tags for the domain this file operates in (e.g. 'monetization', 'auth', 'ui', 'data-persistence')" | `"domain_tags": ["tag1", "tag2"]` — no count, no examples |
| `subsystem` | "the logical subsystem this file belongs to (e.g. 'ad-framework', 'user-auth', 'trace-engine')" | `"subsystem": "name-of-subsystem"` — no examples |
| `design_patterns` | "any notable patterns used (empty list if none)" | `"design_patterns": []` — empty placeholder, no "if none" nudge |
| `cross_references` | "documentation files that describe or relate to this code" | `"cross_references": []` — no description |
| `tech_debt` | "list ONLY explicit markers (TODO, FIXME) or severe architectural flaws. Do not list potential improvements or nitpicks." | `"tech_debt": []` — no scope restriction |
| `staleness_risk` | (inline taxonomy "low\|medium\|high — how likely is this file's understanding to become stale") | `"staleness_risk": "low\|medium\|high"` — taxonomy without description |

The batched prompt has the **same schema** but **none of the intent-shaped instructions**. Three of the most failure-prone fields lose their guards entirely:
- `tech_debt` loses its "explicit markers only" scope restriction — likely emits the same design-critique drift documented in [`epistemic-code.md`](./epistemic-code.md) Iteration #1, but without the original prompt's (already-ignored) attempt to fence it off.
- `domain_tags` loses its 1-4 count constraint + 4 concrete examples — risk of overflow or over-generic tags.
- `subsystem` loses its example anchors — risk of free-form/redundant subsystem labels that don't match the segment vocabulary used elsewhere.

**Why this matters:** the batched path is the BYOK / cloud profile (controlled by `self._batch_profile is not None and self._batch_profile.name.value != "off"` — `epistemic_enrichment.py:1085-1088`). When the daemon is configured with a remote/cloud LLM that supports structured outputs, this batched prompt fires. **Production users on BYOK get worse epistemic enrichment than local-sequential users**, because the single-file prompt's per-field guidance is lost in translation.

**Finding #2 — `response_schema=code_schema` (structured outputs) does NOT compensate for missing instruction-level guidance.** Grounding §5 (OpenAI Structured Outputs / Anthropic Tool Use): constrained decoding guarantees *shape*, not *content*. It will ensure the model emits a valid JSON object with `tech_debt: [...]` — it will not ensure the items in that array are explicit TODO markers vs design critiques. The schema and the instruction are orthogonal layers, and the batched path is using only the first.

**Finding #3 — snapshot gap.** No separately-captured batched-epi-code output exists. The captured `outputs/epistemic-code/powermate-reborn.jsonl` was produced by the sequential single-file path (one record per file, no batch boundaries visible). To audit batched behavior we'd need either (a) a deliberate run with `_batch_profile.name.value != "off"` and side-by-side capture, or (b) examining a BYOK-configured deployment's output. Without this, finding #1 is a code-structural prediction, not an output-observed verdict.

**Finding #4 — `BATCHED_EPISTEMIC_CODE_SYSTEM` is generic-architect persona.** "You are a senior software architect performing deep epistemic analysis of source code files. You MUST respond with a JSON object containing a 'results' array..." Compare to `EPISTEMIC_SYSTEM`: "You are an expert software architect performing deep analysis of a codebase. You produce structured, accurate analysis grounded in the actual code and documentation. You MUST respond with valid JSON only..." The batched version adds "containing a 'results' array" (necessary for the batched shape) but DROPS the "grounded in the actual code and documentation" anchoring clause. That clause is the kind of intent-shaping instruction grounding §4 (Constitutional AI) recommends — explicit principles that guide critique.

**Verdict:** `analysis (no edit shipped this iteration).` This is the cross-cutting B3 issue — both batched epistemic prompts (`batch-epi-code`, `batch-epi-doc`) suffer the same instruction-level guidance gap relative to their single-file siblings. Recommend writing a cross-cutting finding ([`../findings/epistemic-batched-vs-single-guidance-gap.md`](../findings/epistemic-batched-vs-single-guidance-gap.md)) once the batched output is captured for direct comparison.

**Recommended next iteration:**

1. **Capture batched-epi-code output** for direct comparison — either configure a BYOK profile and rerun, OR run a focused side-by-side on a 10-file subset.
2. **Port single-file field-level guidance into `build_batched_epistemic_code_prompt`:**

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
-        '"epistemic_confidence": 0.85}'
+        '"extended_summary": "2-4 sentence detailed description", '
+        '"domain_tags": ["1-4 descriptive tags (e.g. monetization, auth, ui, data-persistence)"], '
+        '"architecture_layer": "<presentation|business_logic|data|infrastructure|configuration|testing|documentation|build|unknown>", '
+        '"subsystem": "logical subsystem (e.g. ad-framework, user-auth, trace-engine)", '
+        '"design_patterns": ["only notable patterns; empty list if none"], '
+        '"cross_references": ["documentation files that describe or relate to this code; not source files"], '
+        '"tech_debt": ["ONLY explicit TODO/FIXME/XXX/HACK markers. If file has none of these substrings, emit []. Do NOT substitute design critique."], '
+        '"staleness_risk": "low|medium|high — likelihood that understanding goes stale (file changes a lot)", '
+        '"epistemic_confidence": 0.85}'
     )
```

The inline descriptions are unusual JSON shape (descriptions in value slots rather than schema annotations), but they survive token-by-token and the model reads them. Alternative: use a separate INSTRUCTIONS section above the JSON schema.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §5 (Structured Outputs guarantee shape, not content — schema is orthogonal to intent).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §10 (Batched prompts: order/position bias — independent of the guidance gap, but worth measuring per-position quality once batched output is captured).
- Memory: `project_llm_confidence_calibration.md` — `epistemic_confidence: 0.85` placeholder is a clumping anchor; per memory, asking for a 0-1 float gives social-register clumping near 0.85. Should be a named tier in both prompts.

**Cross-references:** [`epistemic-code.md`](./epistemic-code.md) (sibling — same finding from output-observation side), [`batch-epi-doc.md`](./batch-epi-doc.md) (sibling — same guidance-gap pattern for docs), [`epistemic-doc.md`](./epistemic-doc.md) (single-file doc variant).

## Open questions
- Should we publish a fixed taxonomy of layer/subsystem values?
- When is batched-epi-code better than single-file epistemic-code? Should one supersede the other?

## Cross-references
- Sibling: [batch-epi-doc](./batch-epi-doc.md), [epistemic-code](./epistemic-code.md)
- Memory: `project_llm_confidence_calibration.md`
- Phase 22 — Epistemic enrichment (parent architecture)

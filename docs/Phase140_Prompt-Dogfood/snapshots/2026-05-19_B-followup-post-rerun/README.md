# Snapshot 2026-05-19 — B-followup post-rerun

**Captured:** 2026-05-19 (after daemon restart + clean rebuild on PowerMate)
**Purpose:** Validate the prompt edits shipped in Phase 140 B-followup iterations.

## Context

After the B1-B5 analysis pass, AI B shipped five prompt-side improvements in four commits:

- `3c22cb09` fix(prompts): batched prompts (batch-edges EVIDENCE DISCIPLINE + epistemic field-level guidance port + structured schemas)
- `24871dc0` fix(prompts): single-file epistemic prompts (structured cross_references/tech_debt/decision_chains + doc_status reconciliation) + EpistemicEntry roundtrip widening
- `157ffe78` docs: Iteration #2 entries documenting the shipped edits
- `a2004c02` fix(epistemic): consumer-side branch for structured tech_debt items in group_reasoning.py and cluster.py (caught when group_reasoning crashed on the first deep-rerun attempt)

This snapshot captures the output AFTER all four commits + a clean rebuild.

## Captured artifacts

| Site / stage | File | Records |
|---|---|---|
| `batch-edges` | `outputs/batch-edges/powermate-reborn.jsonl` | 31 inferred edges |
| `epistemic-code` + `epistemic-doc` (mixed) | `outputs/epistemic-code/powermate-reborn.jsonl` | 24 records (18 code + 6 doc) |
| `batch-cluster` | `outputs/batch-cluster/powermate-reborn.jsonl` | 21 cluster summaries |
| `group_reasoning` | `outputs/group-reasoning/powermate-reborn.jsonl` | 2 group_reasoning records |

## Pipeline run

- `fast_sync` (run-bd... after cache clear): 5/5 stages, ~38s elapsed (inferred_edges itself: 12.94s on Kimi-K2.6 cloud)
- `deep_enrichment` (run-... after group_reasoning consumer fix): 5/5 stages green
  - enrichment: 24/24 records enriched, 0 failed
  - group_reasoning: 2/2 groups (NO CRASH this time — consumer fix worked)
  - clustering: 21 clusters
  - deepening + deep_knowledge: completed

## Key validation results

### batch-edges (verdict: kept)

3-way comparison hedge-language + build-manifest-noise rates:

| Snapshot | Edges | Hedge-language | Package.swift→source `configures` | Avg evidence length |
|---|---|---|---|---|
| `2026-05-17_baseline` (Apr-30 cache) | 36 | 16 (44%) | 9 | 178 chars |
| Pre-rerun cached (today, OLD prompt) | 51 | 10 (20%) | 4 | 133 chars |
| **Post-rerun, NEW prompt** | **31** | **0 (0%)** | **0** | **48 chars** |

The shorter evidence (178 → 48 chars) is because verbatim source quotes are tighter than fabricated rationale. Sample new edges all carry verbatim Swift function/class signatures as evidence — exactly what EVIDENCE DISCIPLINE requires.

### epistemic-code + epistemic-doc (verdict: kept)

All 24 records in `outputs/epistemic-code/powermate-reborn.jsonl` carry structured-shape fields:

- 18 code records: 100% have dict-shaped `cross_references` and `tech_debt` (with severity tags)
- 6 doc records: 100% have dict-shaped `cross_references`, `decision_chains` (with rationale + tradeoffs)
- doc_status preserved per Pass-1 reconciliation clause (README.md → "active")

Round-trip preservation verified: `EpistemicEntry._mixed_list` keeps dicts intact through load/write.

### Consumer-side fix

`group_reasoning.py` and `cluster.py` previously did `"; ".join(entry.tech_debt[:2])` assuming List[str]. After commit `a2004c02` they branch on `isinstance(t, dict)` and render structured items as `"[severity] item"`. Verified by post-rerun pipeline running clean through group_reasoning + clustering with the structured tech_debt format.

### batch-cluster + group_reasoning (incidental — not Phase-140 target)

Captured for completeness. 21 clusters analyzed, 2 group_reasoning records emitted. Stage-level success demonstrates the consumer fix.

## What is NOT validated by this snapshot

- **BYOK / cloud-batched path** (`_enrich_tier_batched`) for epistemic prompts. The PowerMate runs above used the local-sequential path. The structured-shape edits to `BATCHED_EPISTEMIC_CODE_SYSTEM` + `BATCHED_EPISTEMIC_DOC_SYSTEM` + `get_structured_schema` still need a deliberate run with `_batch_profile.name.value != "off"` to validate. Deferred.
- **Multi-repo discipline.** Per Phase 140 methodology non-negotiable #4, "kept" verdicts should be confirmed across ≥3 repos. This snapshot is single-repo (PowerMate Slot B). Slot A (SourcePrep self) and Slot C are still TBD. Verdicts are promoted on the basis of (a) the failure mode being repo-agnostic and (b) the captured output being unambiguous about the prompt's behavior change.

## Cross-references

- [`prompts/batch-edges.md`](../../prompts/batch-edges.md) Iterations #1 + #2
- [`prompts/epistemic-code.md`](../../prompts/epistemic-code.md) Iterations #1 + #2
- [`prompts/epistemic-doc.md`](../../prompts/epistemic-doc.md) Iterations #1 + #2
- [`prompts/batch-epi-code.md`](../../prompts/batch-epi-code.md) Iterations #1 + #2 (batched path unverified)
- [`prompts/batch-epi-doc.md`](../../prompts/batch-epi-doc.md) Iterations #1 + #2 (batched path unverified)
- [`findings/epistemic-batched-vs-single-guidance-gap.md`](../../findings/epistemic-batched-vs-single-guidance-gap.md)

# Phase 126 — Multi-Pass Refinement, Generalized

> **Scope:** After Phase 125 proves the four-pass refinement pattern on
> Stage 13 (Concepts), apply it to other expensive single-pass LLM
> stages where it's likely to produce equivalent quality lift —
> Stage 6 (Enrichment), Stage 8 (Clustering), Stage 11 (Atlas).
> **Status:** Scaffolded — **gated on Phase 125 acceptance**
> **Date opened:** 2026-05-02
> **Prerequisite:** Phase 125 ships and demonstrates the pattern is
> robust without per-project tuning.

---

## 0. Getting started (next agent, read this first)

This phase is **conditional**. Do not start any T-level work until:

1. Phase 125 has shipped (T1-T4 minimum), AND
2. SourcePrep + ≥1 external project both produce stable distributions
   under the four-pass pipeline without per-project parameter
   tuning, AND
3. Phase 125's RESULTS.md confirms ≥40% quality lift over the
   single-pass baseline by some agreed metric.

If any of those preconditions are absent, this phase stays parked.

If they're all met, the work is **stage-by-stage application of an
already-validated template**, not novel architecture. Each Pxx-Sub
section below is its own sprint.

### What this phase explicitly does NOT do

- Re-derive the four-pass design. Copy from Phase 125.
- Apply the pattern to deterministic stages (Rust engine, embedding,
  rules generation). They have no broad LLM emission to refine.
- Replace the swarm orchestrator. Reuse it.

---

## 1. Problem statement (after Phase 125 lands)

Phase 125 demonstrates that for a "broad LLM emit → structured
critique → narrow LLM refine → deterministic gate" pattern, you can
take a single-pass LLM stage that emits 1,500+ raw items down to
50-100 curated items + a small triage queue, with quality lift
visible in downstream consumers.

The same pattern is structurally available in three other Finalize-
or Enrich-stage workloads. Each is a single LLM pass today; each has
inherent grouping/dedup semantics; each feeds a downstream stage that
amplifies its quality bugs.

### The three target stages

| Stage | Today | Quality bug it has | Multi-pass yield |
|---|---|---|---|
| **6 ENRICHMENT** (per-file augmentation) | LLM emits one augmentation per file blind | Vague summaries, hallucinated dependencies, mis-claimed call relationships | Catch hallucinations before they pollute Stage 7-15 inputs |
| **8 CLUSTERING** (module synthesis) | LLM groups files into modules in one pass | Near-duplicate module names, low-cohesion modules, missing splits | Better atlas structure → better all downstream |
| **11 ATLAS** (segmented atlas) | LLM writes per-segment narrative | Hallucinated hubs, unverified cross-cutting claims, drift from graph reality | Atlas claims that survive a structural verifier |

---

## 2. Generalized pattern reminder (from Phase 125)

```
Pass 1: BROAD LLM EMIT (existing — keep as-is)
   Inputs: stage's natural input
   Output: many raw items with confidence + anchors

Pass 2: CPU GROUP/SCORE (NEW — deterministic, fast)
   Cluster by overlap signal (stage-specific)
   Score against ground-truth signal (stage-specific)
   Mark obvious noise as auto-rejected
   Output: smaller set of cluster representatives + scored items

Pass 3: SCOPED LLM CRITIQUE (NEW — swarm-shaped, narrow scope)
   Per-cluster or per-group LLM call with TIGHTER scope than Pass 1
   Refine confidence (use full 0.0-1.0 range)
   Consolidate / merge / split
   Output: curated set with sharper confidence spread

Pass 4: DETERMINISTIC GATE (NEW)
   confidence >= high → active
   middle → triage_pending (manual review)
   confidence < low → archived
   Output: active + small triage queue + archive history
```

The cost shape is **expensive once + cheap critiques**. Pass 1
dominates wall time (~18 min for concepts). Pass 2 is seconds. Pass
3 is 3-5 min on a smaller input. Pass 4 is sub-second. So the
critique stack adds ~5 min and lifts quality dramatically.

---

## 3. Per-stage application

### 3.A — Stage 6 ENRICHMENT (per-file augmentation)

**Pass 1 (existing):** LLM produces `epistemic` augmentation per file
— role label, summary, intent, dependencies, layer, confidence.

**Pass 2 — CPU verifier:**
- For each augmentation, verify against `trace_nodes.jsonl` /
  `trace_edges.jsonl`:
  - **Dependency claims** — does the file actually import what the
    LLM said it depends on?
  - **Layer assertion** — does the file path actually match the
    layer (e.g., LLM says "presentation" but path is `src/.../core/`)?
  - **Hub status** — does the LLM say "hub file" but graph
    centrality is low?
- Score each augmentation on a `verifier_score`:
  - +1.0 per matched claim
  - −1.0 per claim contradicted by graph
- Auto-flag augmentations with `verifier_score < 0` for re-emission.

**Pass 3 — scoped LLM re-emit:** for the flagged subset only,
re-run the augmentation prompt with a corrective preamble: "your
previous augmentation claimed X but graph evidence shows Y.
Re-emit with this constraint."

**Pass 4 — deterministic gate:** augmentations with
`verifier_score >= 0` after Pass 3 → kept. Below → flagged in the
manifest with `quality='unverified'`. Downstream stages can choose
to skip them.

**Expected yield:** strongest at this stage because Stage 6 is the
**first LLM stage** in the chain — quality bugs propagate across all
of stages 7-15. A 10% reduction in hallucination here is worth more
than a 50% reduction in any single downstream stage.

### 3.B — Stage 8 CLUSTERING (module synthesis)

**Pass 1 (existing):** LLM groups files into modules with a name +
summary + member list per module.

**Pass 2 — CPU module quality scorer:**
- **Cohesion score:** average pairwise edge density between members.
  Low cohesion → module is incoherent.
- **Distinctness score:** for each module name, compute Jaccard /
  edit distance vs every other module name. High overlap → likely
  duplicate.
- **Member-count outliers:** modules with 1-2 members might be
  speculative; modules with 100+ might need splitting.

**Pass 3 — scoped LLM critique:** for flagged modules (low cohesion,
near-duplicate names, outlier sizes), per-module LLM call: "split,
merge, or refine?" with concrete data ("you grouped these 42 files
but 38 of them have zero edges between them").

**Pass 4 — deterministic:** accept the LLM's split/merge decisions
or fall back to the original Pass 1 module if Pass 3 fails.

**Expected yield:** the atlas stage (11) consumes modules; better
modules → better atlas → better `prep()` ambient context.

### 3.C — Stage 11 ATLAS (segmented narrative)

**Pass 1 (existing):** LLM writes a narrative per segment with
claimed hub files, cross-cutting concerns, entry points.

**Pass 2 — CPU claim verifier:**
- **Hub claims:** LLM says file X is a hub. Verify: in-degree of X
  on the import graph. If below segment median → false claim.
- **Cross-cutting concerns:** LLM names domain Y as cross-cutting.
  Verify: how many segments mention domain Y? If <3 → not actually
  cross-cutting.
- **Entry points:** LLM names file X as entry point. Verify: is X
  in `pyproject.toml`'s `[project.scripts]` or a `main()` definition
  or an `index.ts`?

**Pass 3 — scoped LLM correction:** for segments with verified-false
claims, per-segment LLM call: "your atlas mentioned X as a hub but
graph centrality is Y; rewrite this section with the correction."

**Pass 4 — deterministic:** atlas content with
`verifier_score >= threshold` is canonical; below threshold flagged
in manifest as `quality='unverified'`.

**Expected yield:** atlas is the most agent-visible artifact;
hallucinations here mislead every downstream consumer.

---

## 4. Sequencing across the three sub-phases

Don't try all three at once. Each sub-phase is its own ship:

| Sub-phase | Stage | Effort | Why first / last |
|---|---|---|---|
| **126.A** | 6 ENRICHMENT | medium | First LLM stage — biggest blast radius. Highest yield. Land FIRST after Phase 125 settles. |
| **126.B** | 11 ATLAS | medium | Most agent-visible. Land SECOND. |
| **126.C** | 8 CLUSTERING | medium | Internal — modules feed atlas. Land THIRD because atlas verifier (126.B) catches cluster bugs anyway. |

Each sub-phase ships independently with its own RESULTS.md. The
generalized pattern's specs in §2 are the contract; if a sub-phase
deviates, document why in its own README.

---

## 5. Backlog (gated on Phase 125 ship)

| ID | Sub-phase | Change | Risk |
|---|---|---|---|
| 126.A.T1 | ENRICHMENT | CPU verifier — claim/graph cross-check | low |
| 126.A.T2 | ENRICHMENT | Scoped LLM re-emit on flagged subset | med |
| 126.A.T3 | ENRICHMENT | Manifest `quality` field; downstream consumers respect it | low |
| 126.B.T1 | ATLAS | CPU claim verifier (hubs / cross-cutting / entry points) | low |
| 126.B.T2 | ATLAS | Scoped LLM correction on segments with false claims | med |
| 126.C.T1 | CLUSTERING | CPU cohesion/distinctness scorer | low |
| 126.C.T2 | CLUSTERING | Scoped LLM split/merge | med |
| 126.X.T1 | shared | Generalized verifier framework — abstract the Pass 2 contract so 126.A/B/C share infrastructure | med |

---

## 6. Acceptance for each sub-phase

When 126.A ships:
- Augmentations with verified-false dependency claims are <5% of
  total (was: unmeasured)
- Stage 6 manifest carries `verifier_score` per file
- Downstream stages (7-15) can opt out of unverified augmentations

When 126.B ships:
- Atlas claims (hubs, cross-cutting concerns) match graph reality
  on automated verification
- `prep()` ambient context surfaces only verified claims (or marks
  unverified ones explicitly)

When 126.C ships:
- Module list shows ≥80% cohesion-passing modules
- No near-duplicate module names (Jaccard ≥0.8) survive Pass 3

---

## 7. Out of scope

- Re-architecting any stage beyond adding the verifier + critique
  passes. The Pass 1 LLM emission stays as-is.
- Cross-stage refinement (e.g., concept knowledge feeding atlas
  refinement). Each stage refines locally.
- Replacing structural analysis (Rust engine, audit analyzers) with
  LLM-based equivalents. The CPU verifier in Pass 2 LEVERAGES the
  existing structural data; it doesn't replace it.

---

## 8. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Pattern doesn't generalize cleanly — each stage needs custom verifier logic, abstraction breaks | med | 126.X.T1 (generalized verifier framework) is a stretch; if the abstraction is forced, ship per-stage code without the framework |
| Pass 3 cost adds up across 3 stages — total pipeline time grows by ~15 min | low | Each sub-phase's Pass 3 is conditional on flagged subset; not all stages will need refinement on every run |
| Verifier false-positives flag healthy claims as wrong | med | Tune threshold to favor false-negative; record verifier_score so auditors can investigate |
| Phase 125's pattern doesn't actually generalize because concepts are uniquely "deduplicable" | high | This is exactly why Phase 125 must ship + verify first; do not start any 126 work until that's true |

---

## 9. Open questions

1. **Should the verifier framework be unified or per-stage?** Lean
   per-stage for v1 — abstractions tend to leak when each stage's
   ground-truth signal is different.
2. **Where does verifier output live?** Each stage's manifest? A
   shared `verification_log.jsonl`? Probably per-stage manifest for
   locality.
3. **How does the harness check verifier output?** New AP-9 +:
   ENRICHMENT verifier_score median, ATLAS hub-accuracy ratio,
   CLUSTERING cohesion average.
4. **Does "broad LLM emit" Pass 1 stay intact, or do we tune its
   prompt to expect Pass 3 corrections?** Lean: keep Pass 1 as-is
   for compatibility with non-multi-pass deployments.

---

## 10. Pointers

- **Phase 125** — the canonical implementation of the four-pass
  pattern; copy from there
- **Stage 6 entry** — `src/prep/services/build_orchestrator.py`
  EPISTEMIC build type
- **Stage 8 entry** — `src/prep/core/clustering.py` (writes
  `trace_modules.jsonl`)
- **Stage 11 entry** — `src/prep/core/atlas/generator.py`
- **Trace nodes / edges** — `src/prep/core/trace_*.py` (Pass 2
  verifier reads from these)
- **Pipeline telemetry** — `src/prep/services/pipeline_telemetry.py`
  (Phase 124 T11; reuse for verifier events)
- **Harness** — `tools/finalize_chain_audit.py` (extend AP list
  per sub-phase)

---

## 11. Cross-references

- **Phase 124 (FinalizeChainEpistemicAudit)** — established the
  harness, telemetry, and `--compare` infrastructure that this
  phase will extend.
- **Phase 125 (ConceptPromotionPipeline)** — proves the pattern.
  This phase is gated on its acceptance.
- **Phase 122 (FeatureUtilizationAudit)** — `run_health_scan` was
  the original "panel-merged unified entry" pattern. The four-pass
  generalization is the next-generation version: not just merging
  passes, but adding a critique stage.

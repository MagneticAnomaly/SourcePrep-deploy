# 03 — Candidate Checkpoints

12 candidate invocation points for a strategic overseer, ranked by priority.
Each is cited to file:line and includes a cheap uncertainty-gate signal so
the overseer doesn't fire every time.

**These rankings are based on code inspection and intuition.** The Phase 116
dogfooding plan (`06_`) is how we replace intuition with measured error rates.

---

## Tier A — Top-5 (strongest ROI based on current inspection)

### 1. Swarm synthesis consensus — **10/10**
- **Name:** `group-reasoning-worker-synthesis-merge`
- **Stage:** 7 GROUP_REASONING
- **Why Opus:** Kimi workers analyze 50–200 file groups in parallel. The
  synthesis model merges their outputs into a single `GroupReasoningEntry`
  with no visibility into worker *disagreement*. If 3 workers say "safe
  to refactor" and 2 say "high blast radius," synthesis averages confidence
  and the conflict disappears.
- **Blast radius if wrong:** Blast-radius misjudgments feed clustering
  (Stage 8) and concepts (Stage 12). Team relying on "safe" guidance gets
  false positives downstream.
- **Gate signal:** stddev of worker confidence scores; count of workers
  whose claims contradict (same file, opposite coupling verdicts).
- **Frequency if gated:** 5–15 per run (trigger: stddev > 0.3 across ≥3 workers).
- **Source:** `src/codrag/core/swarm_orchestrator.py:186-250`;
  `src/codrag/core/group_reasoning.py:200-350`.

### 2. Concept promotion grounding — **9/10**
- **Name:** `concept-promotion-observation-to-durable-knowledge`
- **Stage:** 12 CONCEPTS
- **Why Opus:** `concept_promotion.suggest_promotion()` promotes
  observations → concepts using a static category rule (decision → architecture,
  pattern → pattern, assumption → domain). No semantic analysis, no
  cross-file evidence check, no assertion extraction.
- **Blast radius if wrong:** Promoted concepts feed antibody derivation.
  Wrong concept → wrong antibodies → false-positive alerts → erode trust
  in the immune system entirely.
- **Gate signal:** observation confidence < 0.7; novelty (first time this
  pattern seen); evidence count (how many files corroborate).
- **Frequency if gated:** 10–30 per run.
- **Source:** `src/codrag/core/concept_promotion.py:28-72`;
  `src/codrag/services/pipeline/workers.py:471-500`;
  `src/codrag/core/audit/synthesizer.py:56-61`.

### 3. Audit report synthesis consistency — **9/10**
- **Name:** `audit-findings-risk-stratification-synthesis`
- **Stage:** 14 AUDIT
- **Why Opus:** `AuditSynthesizer` runs 5 report generators in a ThreadPool
  with no cross-consistency check. ARCHITECTURE_ANALYSIS can claim
  "monolithic" while COMPONENT_INVENTORY says "microservices." User sees
  both, trust collapses.
- **Blast radius if wrong:** These are the primary user-facing outputs.
- **Gate signal:** severity distribution anomalies; hub-file coverage gap
  (hub file with zero findings = blind spot); pairwise contradiction
  detection across the 5 reports.
- **Frequency if gated:** 3–8 per run (one meta-review per audit).
- **Source:** `src/codrag/core/audit/synthesizer.py:96-250`;
  `src/codrag/core/audit/recommendations.py`.

### 4. Hub-file classification mutations — **8/10**
- **Name:** `hub-file-high-blast-radius-validation`
- **Stage:** 6 / 7 / 8 (any stage mutating hub classification)
- **Why Opus:** Files with > ~50 dependents are architectural load-bearers.
  When Stage 7 or 8 changes a hub file's role classification (e.g., "core
  service" → "utility"), downstream module shape shifts. No gate today.
- **Blast radius if wrong:** Module boundaries, atlas shape, concept
  anchors all derive from classifications.
- **Gate signal:** `codrag_impact.dependents > hub_threshold` AND
  (classification changed from prior run OR confidence < 0.75).
- **Frequency if gated:** 2–8 per run.
- **Source:** `src/codrag/services/pipeline/workers.py:100-150`;
  `src/codrag/core/group_reasoning.py:48-93`.

### 5. Role atlas projection coverage — **8/10**
- **Name:** `role-atlas-projection-semantic-consistency`
- **Stage:** 11 ATLAS
- **Why Opus:** Role vectors select subsets per role (CEO, design-engineer,
  infra). No validation that selected subset actually spans the
  architectural layers the role needs. Design-engineer role might see all
  UI files and zero API files.
- **Blast radius if wrong:** Role-scoped atlases ship to IDE plugins and
  dashboards. Wrong scope → wrong context downstream.
- **Gate signal:** selected files span < N of M layers; tag-affinity
  variance > threshold; cross-role contradictions (file X labeled "core"
  by role A, "peripheral" by role B).
- **Frequency if gated:** 1–3 per run (per role).
- **Source:** `src/codrag/core/atlas/role_projection.py:28-250`.

---

## Tier B — Strong candidates (7/10)

### 6. Epistemic confidence anomalies — **7/10**
- **Stage:** 6 ENRICHMENT
- **Why:** Per-file confidence is computed independently. No cross-file
  consistency check. A file with high confidence but tags contradicting
  its neighbors' is invisible.
- **Gate signal:** per-file confidence < 0.6; connected-component average
  confidence < 0.6; high variance within a component.
- **Frequency:** 15–40 per run (1000–3000 files; gate on anomalies).
- **Source:** `src/codrag/core/epistemic_enrichment.py:237-500`.

### 7. Inferred-edge threshold tuning — **7/10**
- **Stage:** 2 INFERRED_EDGES
- **Why:** Static 0.5 threshold globally. Kimi may systematically
  underestimate confidence for some patterns (Go reflection, dynamic
  imports). No per-file / per-language adaptation.
- **Gate signal:** edge-confidence distribution bimodal; file uses
  known-hard-to-infer patterns; edges to/from hub files (lower threshold).
- **Frequency:** 5–20 per run.
- **Source:** `src/codrag/core/inferred_edges.py:94-250`.

### 8. Cross-cutting concern validation — **7/10**
- **Stage:** 6–8 + 14 AUDIT
- **Why:** Cross-cutting detection is bottom-up from name/tag patterns.
  No top-down check that the concern is applied consistently across
  modules.
- **Gate signal:** coverage % < threshold OR coverage bimodal (some
  modules 100%, others 0%).
- **Frequency:** 2–5 per run.
- **Source:** `group_reasoning.py` (architectural_insight field);
  clustering logic.

---

## Tier C — Lower priority (5–6/10)

### 9. Validation edge-rejection analysis — **6/10**
- **Stage:** 4 VALIDATION
- **Why:** Rejected edges are not exposed to later stages. 50% rejection
  rate on a file is a signal its classification is wrong, but it's silent.
- **Gate signal:** per-file rejection rate > 30%.
- **Source:** `workers.py:267-290`; validation manifest.

### 10. Antibody grounding check — **6/10**
- **Stage:** 15 ANTIBODIES (depends on Stage 12 CONCEPTS)
- **Why:** Template-based derivation. No check that trigger patterns
  actually match real files or that assertions are testable.
- **Gate signal:** trigger-pattern file match count = 0; assertion
  ambiguity heuristic.
- **Source:** `src/codrag/core/antibody_derivation.py:17-79`.

### 11. Deepening-stage convergence check — **6/10**
- **Stage:** 9 DEEPENING
- **Why:** Second-pass enrichment should improve confidence. If it drops
  or tags flip significantly, that's model instability. Silent today.
- **Gate signal:** tag edit-distance > 2 between Stage 6 and Stage 9;
  confidence drop > 0.2.
- **Source:** `workers.py:360-380`; compare trace_epistemic across stages.

### 12. Filter universality post-structural — **5/10**
- **Stage:** 1 STRUCTURAL (post-hoc check)
- **Why:** Phase 115 territory. More linter than overseer, but Opus could
  validate filter coverage on edge cases.
- **Gate signal:** `trace_nodes.jsonl` contains paths matching
  `CODRAG_OUTPUT_DIRS`.
- **Source:** `src/codrag/core/repo_policy.py:100-160`.

---

## Summary tables

### By stage
```
Stage 1 — Structural          → #12 (low priority)
Stage 2 — Inferred edges      → #7
Stage 4 — Validation          → #9
Stage 6 — Enrichment          → #6
Stage 6/7/8 — Hub mutations   → #4
Stage 7 — Swarm synthesis     → #1 ★
Stage 9 — Deepening           → #11
Stage 11 — Atlas              → #5
Stage 12 — Concepts           → #2 ★
Stage 14 — Audit              → #3 ★
Stage 15 — Antibodies         → #10
Cross-stage                   → #8
```

### By cheapness of gate (easiest to implement first)
```
Easy:     #12, #9, #11 (pure-data gates, no model calls)
Medium:   #1, #6, #7, #10 (need to compute stats from existing output)
Hard:     #2, #3, #4, #5, #8 (need cross-artifact reasoning)
```

### Recommended first 3 to dogfood
**#1 (swarm synthesis), #2 (concept promotion), #3 (audit synthesis).**

Reasoning: diverse stages, diverse artifact shapes, diverse gating signals.
If we can make a generic overseer abstraction work for all three, it likely
generalizes to the rest. Tier-B candidates come after we've proven the
pattern on these three.

---

## What's missing from this ranking

- **Real error data.** All rankings above are guesses. The dogfooding plan
  (`06_`) collects actual per-run data so we can re-rank by measured
  error-catch rate.
- **Cost estimates.** We don't have per-call Opus cost at each checkpoint
  yet. A 30-file swarm synthesis input may be 10k tokens; a concept
  promotion may be 2k. Cost modeling belongs in the dogfooding phase.
- **User-observable error catalog.** We don't yet have a list of
  "mistakes CoDRAG has made that users noticed." That's the gold standard
  for validating which checkpoints matter.

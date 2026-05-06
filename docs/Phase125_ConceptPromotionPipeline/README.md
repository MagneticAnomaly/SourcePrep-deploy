# Phase 125 — Concept Promotion Pipeline

> **Scope:** Replace the single-pass concept seeder + dormant
> manual-promotion flow with a four-pass pipeline that compresses
> ~1,500 raw seed concepts to ~50–100 active concepts plus a
> tractable triage queue (≤30) for human review. Generalizes the
> "expensive broad LLM pass + cheap deterministic critique pass +
> scoped LLM refinement + deterministic gate" pattern.
> **Status:** Scaffolded — **not started**
> **Date opened:** 2026-05-02
> **Companion phases:** Phase 123 (synthesis prompt tuning),
> Phase 124 (Finalize chain epistemic audit). Both shipped; this
> phase consumes their outputs.

---

## 0. Getting started (next agent, read this first)

This phase is the natural follow-on to Phase 124. The chain is
now **richly seeded** — workers receive doc-anchored prompts, 1,590
concepts emerge with 50.9% `.md`-anchor coverage. But:

- 0 concepts get promoted to `active` (concept_promotion.py is dormant)
- 1,590 manually-reviewable concepts is impossible for any human
- The trailer in `prep()` shows `0 active / 1590 seeds` — to a
  consumer this reads as "broken"
- Antibodies are derived but stuck at `status='testing'`
  (parallel broken promotion path — see §11 for cross-reference)

This phase fixes the curation/promotion architecture without
regressing the seed quality Phase 124 established.

### Recommended first session (≤2 hours)

1. **Read §1 and §2** to internalize the four-pass framing. Without
   it the rest reads as "just write a triage script" and you'll
   underbuild it.
2. **Reproduce the confidence histogram** (§3 instrumentation) on
   SourcePrep + one external project. The histogram **is the
   strategy** — it tells you whether confidence-based thresholds
   are even useful (probably not — see §3).
3. **Open T1 (anchor-overlap clusterer) as the first PR.** It's
   pure CPU, deterministic, runs in seconds, and generates the data
   the rest of the phase needs. Don't tune anything until you can
   see the cluster size distribution.

### What this phase explicitly does NOT do

- Re-architect the swarm worker prompt (Phase 124 owns it).
- Touch synthesis prompt tuning (Phase 123 owns it; the wall-time
  fix already landed 2026-05-02).
- Build a UI workflow for triage review. The backend supports
  triage (`status='triage_pending'`); the dashboard panel for
  reviewing it is a Phase 126 candidate.
- Touch antibody promotion. That's the parallel broken
  flywheel — split into its own phase or a §11 follow-up.
- Add more pipeline stages. The four passes all happen INSIDE
  Stage 13 CONCEPTS — the existing 15-stage shape stays.

---

## 1. Problem statement

After Phase 124, we have:

- 1,590 raw concepts, 50.9% with `.md` anchors, 11/11 categories
- Synthesis runs successfully (post Phase 123 wall-time fix)
- Zero concepts in `status='active'`
- `concept_promotion.py` exists but has zero callers
  (filed in `docs/INTENTIONALLY_DORMANT.md`)
- The MCP `prep()` trailer reads `[Concepts: 0 active, 1590 seeds]`
  which a security-audit agent (see
  `docs/Phase124_FinalizeChainEpistemicAudit/MCP_DOGFOOD_FEEDBACK_2026-05-02.md`)
  flagged as a "stuck pipeline" symptom

The previous mental model assumed concepts move via a
**single-shot manual promotion**: human reviews each seed, marks
active. That model breaks at any reasonable scale:

| Project size | Seeds | Time to review @ 30s each |
|---|---:|---:|
| SourcePrep (1,848 files) | ~1,590 | **13 hours** |
| PowerMate (~600 files) | ~600 (est) | 5 hours |
| Halley (~800 files) | ~800 (est) | 6.5 hours |

No developer, including the platform creator, will ever do that.
The architecture has to do most of the work and present a small
human-decidable set.

---

## 2. The four-pass architecture

```
   ┌────────────────────────────────────────────────────────┐
   │  Stage 13 CONCEPTS (in-stage, ~22 min total)           │
   │                                                          │
   │  Pass 1 ──── Pass 2 ──── Pass 3 ──── Pass 4 ─── (out)   │
   │  LLM swarm   CPU         LLM swarm   CPU                │
   │  ~18 min     ~5 sec      ~3-5 min    ~5 sec             │
   │  1,590       400 cluster 80-120      ≤30 to triage      │
   │  raw seeds   reps + 1k   refined     + ~70 active       │
   │              shadows     concepts                       │
   └────────────────────────────────────────────────────────┘
```

### Pass 1 — Worker swarm (existing — Phase 124 enriched)

- Per-module workers receive linked-doc excerpts (T4)
- Emit `{title, content, category, confidence, anchors, tags}`
- Output: ~1,500-1,800 raw concepts, status=`seed`
- Time: ~18 min on cloud Kimi/Qwen

### Pass 2 — Deterministic triage (NEW)

- **Input:** all `status='seed'` concepts for the project
- **Operations (pure CPU, no LLM):**
  1. Cluster by anchor overlap. Two concepts cluster together if
     they share ≥2 anchors OR share ≥1 anchor AND have ≥0.6
     title-token-overlap (Jaccard).
  2. Within each cluster, the highest-confidence concept becomes
     the **cluster representative**; others get
     `status='shadow'` with a back-reference to the representative.
  3. Auto-archive concepts with `confidence < 0.65 AND zero
     anchors` (likely speculative noise) → `status='archived'`.
- **Output:** ~200-400 cluster representatives still at `seed`
  status, ~1,000-1,300 in `shadow`, ~50-200 in `archived`.
- **Time:** seconds. Pure Python on the concepts table.

### Pass 3 — Scoped LLM refinement (NEW — swarm-shaped, tier-based)

- **Input:** the ~1,272 cluster representatives (post Pass 2)
- **Decomposition:** group by `(category, atlas_segment)` so each
  worker handles a coherent slice (e.g. all "constraint" concepts
  in `packages-ui`).
- **CRITICAL design choice (per `T3_RESEARCH.md`):** the worker
  prompt does **NOT** ask for a 0.0-1.0 confidence float. Asking
  for a continuous self-rated number is the canonical failure mode
  documented in Xiong et al. ICLR 2024 — it produces the exact
  0.7-0.95 clustering Phase 124's data showed. Instead, the prompt
  asks the worker to assign one of **5 named tiers**, each with a
  written passing test the model must cite:

  | Tier | Passing test |
  |---|---|
  | SPECULATIVE | plausible reading of ≤2 files; no falsification test |
  | SUGGESTIVE | pattern in 3-5 files in one module; no enforcement |
  | SUPPORTED | pattern in 5+ files OR explicit anchor (test/ADR/docstring) |
  | LOAD-BEARING | cross-module; removing breaks runtime or named test |
  | AXIOMATIC | codified in CI/types/constraint; violations fail build |

  Tiers map to floats **post-hoc at storage**: 0.20 / 0.40 / 0.65 /
  0.85 / 0.97. The LLM never sees the floats.

- **Per-worker prompt** (full template in `T3_RESEARCH.md`):
  combines Patterns 1+3 from the research — adversarial self-critique
  before tier assignment. Order matters: counter-evidence →
  coincidence hypothesis → falsification test → consolidation
  decision → tier. Rationale before score.

- **Synthesis:** elevate cross-segment cross-cutting concepts to
  the global level.

- **Output:** ~80-120 refined concepts with **real confidence
  spread** across the full 0.20-0.97 range (vs the current 0.70-0.95
  clump). Status still `seed` until Pass 4 gates them.

- **Time:** 3-5 min on cloud (much smaller input than Pass 1).

- **Validation:** see T3_RESEARCH.md §"Validation methodology" —
  three-tier check (distribution histogram → hand-labeled
  calibration sample → cross-LLM agreement via Cohen's κ).
  Target ECE < 0.10 (currently ~0.30+ on the verbalized-float prompt).

### Pass 4 — Deterministic gate (NEW)

- **Input:** the refined ~80-120 concepts
- **Operations:**
  - `confidence ≥ 0.90` → `status='active'`
  - `0.65 ≤ confidence < 0.90` → `status='triage_pending'`
  - `confidence < 0.65` → `status='archived'` (rare — Pass 3 should
    have caught these)
- **Output:** ~70 actives + ≤30 triage + ~20 archived
- **Time:** sub-second.

### Final state

| Status | Visibility | Audience | Count (est) |
|---|---|---|---:|
| `active` | default in `prep_concepts` + ambient trailer | every consumer | 50-100 |
| `triage_pending` | optional surface (`status='triage_pending'`) | platform owner / power user | ≤30 |
| `archived` | hidden by default; `status='archived'` to view | anyone wanting history | ~1,400 |
| `shadow` | hidden by default; reachable via cluster representative back-ref | anyone debugging dedup | ~1,000 |

---

## 3. Hypotheses (test these in order)

### H1 — Confidence alone is not a useful filter

**Test:** dump the confidence histogram on SourcePrep + 1 external.

**Expected (SourcePrep, 2026-05-02 measured):**
- ≥0.95: 38 (2.4%)
- 0.85-0.95: 577 (36%)
- 0.70-0.85: 898 (57%)
- 0.50-0.70: 77 (5%)
- <0.50: 0

**If confirmed:** confidence-only thresholds keep 95% (≥0.70) or
2.4% (≥0.95). Neither is useful. Anchor-overlap clustering is the
real lever — H2.

### H2 — Anchor-overlap clustering recovers most duplicates

**Test:** on the 1,590 SourcePrep concepts, cluster by anchor
overlap (≥2 shared OR ≥1 shared + Jaccard ≥0.6 on title tokens).
Measure: cluster-size distribution + reduction ratio.

**Original expected:** ~70-80% of concepts collapse into clusters
of 2-5; ~20-30% remain as singletons. Net: 1,590 → ~300-500.

**Result (T1 landed 2026-05-02): PARTIALLY REFUTED.**

- Default settings (min_shared_anchors=2): 1,590 → **1,272 clusters**
  (**20% compression**). 159 multi-member clusters; biggest 9 members.
  All 159 inspected as **genuine** near-duplicates (e.g., 9-concept
  cluster all anchored to Phase 104/105 docs about API mock/migration).
- Aggressive settings (min_shared_anchors=1 + hub-anchor filter):
  1,590 → 317 clusters (**80% compression**). Inspection of
  largest clusters (35 members) showed **non-duplicates** merged
  transitively via shared phase-doc anchors. False-positive yield.

**Why H2 was wrong:** the LLM is genuinely producing diverse,
non-overlapping concepts. Most concepts have 1-2 anchors (876/1590
are single-anchor). Two single-anchor concepts can only co-cluster
via title similarity, which is rare for distinct topics. The
"shared anchor" bridge is mostly real — and there aren't that many
of them.

**Implication:** Pass 2 yields **~20% high-precision compression**.
Bulk volume reduction is **Pass 3's job** — scoped LLM critique
on the 1,272 cluster representatives must compress to ~80-100
actives. That's still better than Pass 3 facing all 1,590 raw
concepts (40% LLM cost reduction), but the architecture leans on
Pass 3 more heavily than originally sketched.

### H3 — A scoped LLM critique on cluster representatives produces stronger confidence calibration

**Test:** compare confidence histogram BEFORE Pass 3 (Pass 1
output, currently 0.7-0.95 cluster) vs AFTER Pass 3 (refined
representatives).

**Expected:** post-refinement spread should be wider — clear
high-confidence (≥0.90) for cross-cutting concepts, clear
low-confidence (<0.65) for refined-out merges.

**If false:** the per-worker prompt isn't pushing hard enough on
discrimination → tighten the prompt to require
"justify confidence with evidence: anchors quoted, cross-segment
mentions counted."

### H4 — The triage queue stabilizes at ≤30 across project sizes

**Test:** run the full pipeline on SourcePrep + PowerMate + Halley.
Count concepts in `triage_pending` for each.

**Expected:** ≤30 for all three. The 0.90 threshold is high enough
that most concepts either clear it (active) or fall well below
(archive); few hover at 0.85.

**If false:** the 0.90 gate is too lenient OR too aggressive. Tune
based on observed per-project distributions.

---

## 4. Methodology

### 4.1 Anchor-overlap clusterer (T1)

New module `src/prep/core/concept_clustering.py`:

```python
def cluster_concepts(
    concepts: list[Concept],
    *,
    min_shared_anchors: int = 2,
    title_jaccard_threshold: float = 0.6,
) -> list[ConceptCluster]:
    """Group near-duplicate concepts via anchor overlap + title similarity."""
```

Algorithm:
1. Build a (concept_id → set of anchors) map.
2. Build inverted index (anchor → list of concept_ids).
3. For each concept, find candidates via the inverted index: any
   other concept sharing ≥1 anchor.
4. Apply the `min_shared_anchors=2` gate OR `min_shared_anchors=1
   AND title_jaccard ≥ 0.6`. (Tunable via params for ablation.)
5. Use union-find to compute connected components.
6. Return list of `ConceptCluster(representative_id, shadow_ids,
   shared_anchors)` — representative = highest-confidence member.

Tests:
- empty input
- single concept (singleton cluster)
- two concepts with 0 shared anchors (separate clusters)
- two concepts with 1 shared anchor + similar titles (single cluster)
- two concepts with 1 shared anchor + dissimilar titles (separate)
- three-way transitive cluster

### 4.2 Pass 2 worker (T2)

Add a new Stage-13 sub-step in `concept_seeder.py`:

```python
def triage_seeded_concepts(project_id: str) -> TriageReport:
    """Pass 2: deterministic triage on status='seed' concepts.

    - Cluster by anchor overlap.
    - Mark cluster shadows as status='shadow' with back-ref to rep.
    - Auto-archive low-confidence anchorless concepts.
    """
```

Telemetry events: `pass2_clustering_complete` (cluster_count,
shadow_count, auto_archived_count, time_ms).

### 4.3 Pass 3 — scoped LLM refine (T3)

New function `refine_cluster_representatives(project_id, llm)`:

- Read `status='seed'` concepts (the cluster representatives after
  Pass 2 marked the others as shadow).
- Group by `(category, atlas_segment)`. Atlas segment lookup uses
  `atlas_markdown_links.json` reverse — concepts whose anchors
  mostly fall in segment X belong to that segment's group.
- Fan out via `SwarmOrchestrator` with **scoped per-worker
  prompts**: each worker sees only N cluster reps (N ≤ 20) for one
  (category, segment). Smaller scope → better quality.
- Per-worker output: refined concepts with new confidence values.
- Synthesizer: elevate cross-segment cross-cutting concepts.

Telemetry: `pass3_refine_summary` (input_count, output_count,
confidence_histogram_post).

### 4.4 Pass 4 — deterministic gate (T4)

```python
def gate_refined_concepts(project_id: str) -> GateReport:
    """Pass 4: status='active' / 'triage_pending' / 'archived'."""
```

Thresholds initially:
- `confidence >= 0.90` → `active`
- `0.65 <= confidence < 0.90` → `triage_pending`
- `confidence < 0.65` → `archived`

Make these configurable via `settings_store` so projects can tune.

### 4.5 prep_concepts surface update (T5)

`prep_concepts(action="list")` defaults to `status IN ('active',
'triage_pending')`. Explicit `status='seed'` or `'archived'`
returns the underlying data for debugging.

`prep()` ambient trailer changes from:
```
[Concepts: 0 active, 1590 seeds — architecture: 350, technical: 235, …]
```
to:
```
[Concepts: 73 active, 24 triage_pending — architecture: 18, technical: 12, … | 1,463 archived]
```

### 4.6 Telemetry (T9)

Add Phase 125 events to `pipeline_telemetry.jsonl`:
- `pass2_clustering_complete` — cluster size distribution
- `pass2_auto_archived` — count and reasons
- `pass3_refine_summary` — input/output counts + post-confidence histogram
- `pass4_gate_complete` — final active/triage/archive counts

Update the harness `--show-events` EXPECTED list.

---

## 5. Backlog (one-tuning-knob-per-PR)

| ID | Change | Risk | Est LoC |
|---|---|---|---:|
| T1 | ✅ `concept_clustering.py` + tests for anchor-overlap clusterer (landed 2026-05-02) | low | ~280 + 23 tests |
| T2 | ✅ `concept_promotion_pipeline.py` Pass 2 + Pass 4 decision/runner functions + tests (landed 2026-05-02; live dry-run: 1590 → 318 shadows + 1272 seed reps + 0 auto-archives) | low | ~390 + 18 tests |
| T3 | Pass 3 scoped-LLM refine via `SwarmOrchestrator` — **tier-based prompt per `T3_RESEARCH.md`** | med | ~300 |
| T4 | ✅ Pass 4 deterministic gate (decision logic + `run_pass4_gate`) — landed alongside T2 | low | included in T2 module |
| T5 | `prep_concepts` default-filter to active+triage; trailer update in `mcp/server.py` | low | ~60 |
| T6 | Concept lifecycle migration (move existing 1,590 seeds through the new pipeline once) | low | one-shot script |
| T7 | (stretch) Per-project threshold tuning via `settings_store` | low | ~50 |
| T8 | (stretch) Cluster-shadow visibility — let triage UI walk shadows of a representative | low | ~80 |
| T9 | Telemetry events + harness `EXPECTED` list update | low | ~40 |
| T10 | Acceptance run on SourcePrep + PowerMate + Halley + RESULTS.md | low | ~100 |

---

## 6. Tasks (operational checklist)

| ID | Task | Output / Done When |
|---|---|---|
| T1 | Anchor-overlap clusterer | `cluster_concepts()` returns expected components on test fixtures |
| T2 | Pass 2 deterministic triage | live SourcePrep run reduces 1,590 seeds → ~200-400 representatives + ~1,000 shadows + ~150 archives |
| T3 | Pass 3 scoped LLM refine | live run produces ~80-120 refined with confidence spread covering [0.5, 1.0] |
| T4 | Pass 4 gate | live run produces ≤100 actives + ≤30 triage |
| T5 | prep_concepts + trailer surface update | `prep()` trailer reads "73 active, 24 triage_pending — …" instead of "0 active, 1590 seeds" |
| T6 | Concept migration script | existing seeds move through pipeline without data loss |
| T7 | (stretch) per-project thresholds | settings.db key `concept_promotion.gate.high` configurable |
| T8 | (stretch) cluster shadow walking | `prep_concepts(action="cluster", id=X)` returns rep + shadows |
| T9 | Telemetry + harness updates | new events visible in `--show-events`; harness flags AP-8 if active==0 after gate |
| T10 | Acceptance run + RESULTS.md | three projects each show: ≤30 triage, ≥40 active, anti-pattern AP-8 not fired |

---

## 7. Acceptance for "done"

This phase ships when, simultaneously:

1. SourcePrep produces **50-100 active concepts** + **≤30 triage_pending** after a clean pipeline run.
2. The MCP `prep()` ambient trailer no longer reads "0 active";
   it reads non-zero active + triage counts.
3. `prep_concepts(action="list")` defaults to active+triage;
   underlying seeds/shadows/archives are queryable but not
   defaulted.
4. Two external projects (PowerMate + Halley) each produce
   distributions in the same shape (50-100 active, ≤30 triage)
   without per-project tuning.
5. The harness gains AP-8 ("active concept count is zero on a
   project with >100 seeds — promotion path didn't run") and
   doesn't fire it on a fresh run.
6. RESULTS.md documents before/after numbers and any threshold
   tuning that landed.

A **partial ship** (T1-T4 only, deferring T5-T10) is acceptable if
T5's UI-facing changes need a coordinated dashboard PR. Promote
the gate to `active` server-side; let the dashboard catch up next.

---

## 8. Out of scope for this phase

- Antibody promotion path (parallel issue — antibodies stuck at
  `status='testing'`). Track separately. See §11.
- Triage review UI in the dashboard (Phase 126 candidate).
- Cross-project concept federation (all projects' actives merged
  for an org-wide view). Future phase.
- Re-tuning the worker prompt (Phase 124 owns that).
- Re-tuning the synthesis prompt (Phase 123 owns that).
- Generalizing the multi-pass pattern to ENRICHMENT / CLUSTERING /
  ATLAS stages. Phase 126+ research item — proven on concepts
  first.

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Anchor overlap is too coarse — concepts share `MASTER_TODO.md` but discuss totally different topics | med | require ≥2 shared anchors OR ≥1 + title Jaccard 0.6; tune on real data |
| Pass 3 LLM scoring still clusters at 0.7-0.95 (same as Pass 1) | med | Pass 3 prompt requires evidence-backed confidence ("quote the anchor that justifies a 0.90+"); test on real run |
| Migration of existing 1,590 seeds breaks references | low | T6 script is idempotent; runs once per project; backup the table before running |
| Triage queue grows unbounded across runs (re-runs add new triage_pending entries) | med | Pass 4 reconciles: if a concept previously archived comes back at the same anchors, flip to archived again (don't re-queue) |
| Threshold tuning becomes per-project tribal knowledge | low | T7 settings_store key + harness reports active/triage ratios so anomalies surface |

---

## 10. Open questions

1. **Should `shadow` concepts be queryable via MCP at all?** They're
   useful for debugging dedup, but they pollute the surface. Lean:
   no by default, expose via `status='shadow'` opt-in.
2. **Are anchors comparable across projects?** A concept in project
   A anchored to `src/foo.py` is unrelated to a same-titled concept
   in project B with a different `src/foo.py`. We're scoped per-project
   so this doesn't bite, but worth flagging if cross-project
   federation comes up later.
3. **What about concepts with zero anchors?** Some legitimately
   are global — e.g. "MCP-First Distribution Strategy" doesn't
   anchor to a single file. Pass 2 currently auto-archives
   `<0.65 AND no anchors`. Reconsider if Pass 1 emits enough
   high-confidence anchorless concepts.
4. **Does Pass 3 need its own coordinator, or can the synthesis
   step cover it?** The post-Phase-123 synthesis runs after the
   per-worker fan-out and provides cross-module insight. Pass 3
   COULD just be "run synthesis again on the cluster-rep subset."
   Worth experimenting before building a separate orchestrator.
5. **When does a concept get re-evaluated?** If a project's
   atlas regenerates and `atlas_markdown_links.json` changes,
   should clusters be recomputed? Current answer: yes, on every
   concepts-stage run. Cheap to redo; data freshness matters.

---

## 11. Pointers

| What | Where |
|---|---|
| Concept seeder entry | `src/prep/core/concept_seeder.py:62 seed_concepts(...)` |
| Concept swarm path | `src/prep/core/concept_seeder.py:355 seed_concepts_swarm(...)` |
| Concept worker prompt | `src/prep/core/concept_seeder.py:670` (Phase 124 T4 enriched) |
| Synthesis prompt | `src/prep/core/concept_seeder.py:649-668` (Phase 123 territory) |
| Synth wall-time fix | `src/prep/core/concept_seeder.py:617-627` (Phase 123 follow-up, 2026-05-02) |
| Concept store | `src/prep/services/concept_store.py` |
| Dormant promotion module | `src/prep/core/concept_promotion.py` (still dormant; this phase obsoletes the manual UI plan) |
| MCP ambient trailer | `src/prep/mcp/server.py:1273` |
| Pipeline telemetry | `src/prep/services/pipeline_telemetry.py` (Phase 124 T11) |
| Harness | `tools/finalize_chain_audit.py` |
| Antibody promotion (parallel issue) | `src/prep/core/antibody_derivation.py:59,77` (hardcodes `status='testing'`) and `src/prep/core/immune_watcher.py:50` (queries `status='active'`) |
| Phase 124 results | `docs/Phase124_FinalizeChainEpistemicAudit/RESULTS.md` |
| Dogfood feedback | `docs/Phase124_FinalizeChainEpistemicAudit/MCP_DOGFOOD_FEEDBACK_2026-05-02.md` |
| Confidence histogram methodology | §3 H1 above |

---

## 12. Cross-references

- **Phase 123 (ConceptQualityRefinement)** — synthesis prompt
  tuning. Phase 125 inherits a synthesis stage that now actually
  runs (post wall-time fix); the four-pass design assumes
  synthesis output is reliable.
- **Phase 124 (FinalizeChainEpistemicAudit)** — established
  doc-anchored worker prompts, 50.9% `.md`-anchor coverage,
  pipeline_telemetry infrastructure. Phase 125 builds on all of
  this.
- **Phase 122 (FeatureUtilizationAudit)** — `concept_promotion.py`
  filed as dormant. Phase 125 makes that module obsolete (we
  promote programmatically, not via observation→concept manual
  flow). Update `INTENTIONALLY_DORMANT.md` once T4 ships.
- **Phase 104 (SubAtlas)** — atlas role projection. The dogfood
  feedback issue #2 (role-weighted module list) is a parallel
  Phase 104 follow-up; tracked in `MASTER_TODO.md`'s recent
  follow-ups section.
- **Phase 126 (proposed)** — apply the four-pass pattern to other
  stages. Strongest candidates: ENRICHMENT (Stage 6) and
  CLUSTERING (Stage 8). Track as Phase 126 research item.

---

## 13. Antibody promotion (parallel broken flywheel — split or absorb)

The MCP dogfood feedback flagged "no antibody alerts on a
security-framed `prep` call." Investigation (Phase 124 RESULTS.md
"Regression caught" section) confirmed:

- `antibody_derivation.py:59,77` hardcodes `status='testing'`
- `immune_watcher.py:50` queries `status='active'`
- 517 antibodies exist but are invisible to `prep()` ambient context

**This phase explicitly does NOT fix antibodies** — but the same
multi-pass thinking applies: derived → review → promote. Either:

- **Absorb option:** add a Pass 5 to this phase that promotes
  high-severity antibodies (`severity='warn'` or `'critical'`)
  to `status='active'` automatically, leaves `severity='inform'`
  in testing for opt-in surface.
- **Split option:** open Phase 126 (or 125b) for the antibody
  promotion path independently.

**Recommendation:** split. Antibody semantics are different (they
gate runtime, not retrieval) and conflating them with concepts
will muddy this phase's acceptance. File as MASTER_TODO follow-up.

# Phase 125c — Quality-Checked Concept Swarm

> **Scope:** Replace 125b's single-call concept synthesizer with a
> two-stage swarm: a **Generate swarm** that produces candidate
> concepts using rich grounding (auto-discovered planning/design docs +
> module rationale + atlas + audit + spaghetti + antibodies), and a
> **Validate swarm** that critiques each candidate per-concept and
> classifies it as `active` (auto-accept), `triage_pending` (queue for
> review), or `archived` (hallucination / unsupported).
>
> **Status:** Scaffolded — not started
> **Date opened:** 2026-05-09
> **Companion phases:** Phase 125 (parked T3 swarm — partially revived
> here as the Validate swarm), Phase 125b (current single-call
> synthesizer — superseded by Generate swarm), Phase 124 (anchor
> coverage), Phase 122 (`concept_promotion.py` dormant).

---

## 0. Getting started (next agent, read this first)

Phase 125b shipped the right *abstraction* (two-layer concept/rationale
split, synthesizer self-tags T1/T2/T3) but the wrong *engine*: a single
LLM call with starved grounding (top-50 rationale **titles only**, no
content). That produced ~50% rationale↔concept paraphrase overlap and
**zero T3 emissions** on real projects (HomeColab live runs, 2026-05-03).
No T3 means no antibodies, which means the immune system stays empty.

The original Phase 125 plan had a swarm critique pass (T3 backlog item)
that was **parked** when 125b chose single-call synthesis for cost. The
user's design intent — explicit, 2026-05-09 — overrides that cost
decision: **lean on compute**, then quality-check the output.

### Recommended first session (≤2 hours)

1. **Read §1 (the two-swarm shape) and §2 (auto-discovery of planning
   docs)** to internalize the architecture. The cost shape is now
   "many cheap workers" (Generate) + "many cheap critiques" (Validate),
   not "one big call."
2. **T1 (planning-doc discovery)** is the first PR. It produces
   `docs_grounding.json` — the input every Generate worker reads. No
   LLM cost. Lets you eyeball what each repo actually surfaces as
   "planning material" before tuning prompts.
3. **T2 (Generate swarm)** wires SwarmOrchestrator with rich
   per-worker grounding. Reuses concept_seeder's swarm path.
4. **T3 (Validate swarm)** is the new critique stage.
5. **T4 (gate + telemetry)** wires `run_pass4_gate` as a final CPU
   tiebreaker.

### What this phase explicitly does NOT do

- Re-architect the **rationale layer** (Pass 1 stays — module rationale
  extraction is the substrate that feeds Generate's grounding).
- Re-architect the existing **clusterer** (`concept_clustering.py`) —
  reused as-is for rationale dedup before grounding load.
- Replace 125b's **two-layer abstraction** (`kind='concept'` vs
  `kind='module_rationale'`) — that's load-bearing and stays.
- Build a **dashboard triage UI** for `triage_pending`. The store
  surface is a prerequisite; the UI is a follow-up phase.
- Touch **antibody promotion** — the parallel broken flywheel from
  Phase 124. Out of scope; tracked separately.

---

## 1. The two-swarm architecture

```
Stage 13 CONCEPTS (~20-30 min on cloud, depends on swarm size)

  ┌─ Pass 1 — Per-module rationale extraction (existing, unchanged)
  │  Output: 1,000-3,000 entries, kind='module_rationale'
  │  Time: ~18 min cloud (existing swarm)
  │
  ├─ Pass 2 — Anchor-overlap clustering (existing CPU, NEWLY WIRED)
  │  Dedup the rationale layer. Mark cluster shadows.
  │  Output: 200-400 cluster representatives in rationale layer
  │  Time: seconds
  │
  ├─ Pass 2b — Doc-grounding discovery (NEW, CPU)
  │  Build docs_grounding.json from auto-discovered planning files
  │  + atlas_markdown_links.json in-link signal. (See §2.)
  │  Output: top-N planning doc PATHS + full-text excerpts
  │  Time: seconds
  │
  ├─ Pass 3 — Generate swarm (REPLACES 125b single-call)
  │  Workers: 1 / 3 / 10 (orchestrator picks by capacity).
  │  Each worker has long context, gets:
  │    • atlas summary + segments
  │    • full-text excerpts of top planning docs
  │    • cluster representatives' content (not just titles)
  │    • audit findings (top-N), spaghetti (top-N), antibody patterns
  │    • category/scope assignment for THIS worker
  │  Each worker emits 5-15 candidate concepts in its scope.
  │  Synthesizer pass merges + dedups.
  │  Output: ~30-150 candidate concepts at kind='concept', status='seed'
  │  Time: ~5-10 min cloud (parallel)
  │
  ├─ Pass 4 — Validate swarm (NEW)
  │  Each worker takes 1-3 candidate concepts + the grounding rows
  │  whose anchors overlap, fact-checks against code/docs.
  │  Classifies each: T3 / T2 / T1 / hallucination.
  │  Output: same concepts with refined tier + verdict
  │  Time: ~3-7 min cloud (parallel, smaller per-call payload)
  │
  └─ Pass 5 — Deterministic gate (existing run_pass4_gate, NEWLY WIRED)
     T3 + T2 → status='active'
     T1      → status='triage_pending'
     halluc. → status='archived'
     CPU tiebreaker only — Validate is the source of truth.
     Time: sub-second.
```

### Why two swarms instead of one rich call

125b's "one call with the whole picture" was the right intuition for
*cross-cutting coherence*, but in practice the prompt is too narrow
(cost-driven token caps) and the LLM's self-rated tier is too noisy.
Generate + Validate decouples those:

- **Generate** gets long context but doesn't have to also self-critique
  (which is the calibration failure mode documented in
  T3_RESEARCH.md). It just has to enumerate plausible concepts.
- **Validate** gets a tiny payload per worker (one concept + its
  grounding) so it can verify rigorously, including on a smaller/cheaper
  model if budget matters.

### What stays from 125b

- Two-layer schema (`kind='concept'` vs `'module_rationale'`)
- Synthesizer's parse logic + JSON salvage (`_salvage_truncated_json_array`)
- Tier vocabulary (T1/T2/T3) and tier→confidence mapping
- `concept_synthesis_complete` / `concept_synthesis_skipped_fresh` telemetry
- Freshness check (skip when rationale unchanged)
- Per-kind eviction caps

The synthesizer module name (`concept_synthesizer.py`) stays. The
implementation pivots from one call to a swarm orchestrator.

---

## 2. Auto-discovery of planning/design docs

Per the user's design intent (2026-05-09), **planning location is
per-repo and not configurable upfront**. Tooling must discover it.

### Discovery strategy — layered

Run all four signals; rank by combined score; emit top-N to
`docs_grounding.json`.

| Signal | Method | Weight |
|---|---|---:|
| **In-link rank** (Phase 124) | `atlas_markdown_links.json` reverse: docs with most code-side mentions are de facto authoritative | **0.5** |
| **Convention name match** | Filename matches the catalog (see below) | 0.25 |
| **Folder concentration** | File's folder is ≥60% .md files (excluding generated dirs) | 0.15 |
| **Hidden agent dir** | Path starts with `.cursor/`, `.claude/`, `.github/instructions/`, `.windsurf/`, `.gemini/` | 0.10 |

Combined score = sum of weighted boolean hits. Cap at 1.0.

### Convention-name catalog (constant)

```python
PLANNING_FILENAMES = {
    "ARCHITECTURE", "DESIGN", "ROADMAP", "VISION",
    "RFC", "ADR", "PROPOSAL", "SPEC", "PRD",
    "PLAN", "BACKLOG", "MASTER_TODO",
    "CLAUDE", "AGENTS", "GEMINI", "CURSOR",
}
PLANNING_FOLDERS = {
    "docs/adr", "docs/decisions", "docs/rfcs", "docs/proposals",
    "docs/specs", "docs/sprints", "docs/phases",
    "rfcs", "adr", "specs", "prds", "product",
    ".cursor/rules", ".github/instructions", ".claude",
}
```

Match is case-insensitive against filename stem and against folder
prefix. `Phase\d+_*` and `Sprint\d+_*` patterns also count.

### Output schema (`<idx_dir>/docs_grounding.json`)

```json
{
  "version": 1,
  "generated_at": 1715200000.0,
  "docs": [
    {
      "path": "docs/Phase125b_TwoLayerConceptArchitecture/README.md",
      "score": 0.85,
      "signals": ["in_link_rank", "convention_match", "folder_concentration"],
      "in_link_count": 12,
      "size_bytes": 18234,
      "excerpt": "...",  // first ~3000 chars, truncated on paragraph boundary
      "headings": ["Phase 125b — Two-Layer ...", "0. Getting started", ...]
    },
    ...
  ],
  "total_candidates_considered": 247,
  "selected_count": 30
}
```

### What Generate workers receive

Each worker gets a curated subset of `docs_grounding.json` — full
`excerpt` for the top 5-10 docs by score, `path + headings` only for
the next ~20. This matches each worker's context budget without
duplicating tokens across workers.

### Override hooks

- `<repo>/.sourceprep/docs_overrides.yaml` — explicit allowlist /
  blocklist, supports glob patterns. Allowlist beats discovery.
- Settings store key `docs.planning_paths` for per-project tuning
  via dashboard (future).

---

## 3. Generate swarm

### Worker assignment

Workers operate per **concept dimension**, not per atlas segment. The
dimensions are the categories already in `VALID_CATEGORIES`:

```
architecture, domain, product, epistemic, process,
brand, security, technical, pattern, constraint, decision
```

Plus a synthesizer pass that elevates cross-cutting / multi-dimensional
findings.

| Swarm size | Workers | What runs |
|---|---|---|
| 1 (single) | 1 | All categories handled in one call. Falls back to 125b shape with rich grounding. |
| 3 (small) | 3 | Worker 1: architecture+domain+product (the "intent" axis). Worker 2: security+constraint+decision (the "rules" axis). Worker 3: technical+pattern+process+epistemic+brand (the "implementation" axis). Plus synthesizer. |
| 10 (full) | 11 | One per category, plus synthesizer. |

Fan-out is picked by `SwarmOrchestrator` based on cloud capacity
(reuses Phase 82 unbounded latency-aware discovery — never hardcode
worker counts). Same orchestrator the rationale extractor uses.

### Per-worker prompt shape

System prompt is a tight version of 125b's (banned-output list,
empty-set permission, quote-then-claim, T3 rubric). User prompt assembles:

```
PROJECT IDENTITY
{atlas identity + stack summary}

ASSIGNED DIMENSION
{category list for this worker}

GROUNDING DOCUMENTS (top 5-10 full excerpts)
{full text from docs_grounding.json scored ≥ 0.6}

GROUNDING DOCUMENTS (next 20, headings only)
{path + heading list}

MODULE RATIONALE (cluster representatives in your dimension)
{title + content + anchors[:3], filtered to category match}

AUDIT FINDINGS (top 6 for your dimension)
{title + severity + 1-line description}

SPAGHETTI HOTSPOTS (if security/architecture/technical)
{file_path + score + severity}

ANTIBODY PATTERNS (if constraint/security)
{title + scope}

EMIT
JSON array, 0-15 concepts. Each:
{ title, content, category, tier, anchors[], counter_evidence,
  falsification, refined_content }

Empty array is acceptable. Padding is failure.
```

### Why category-based, not segment-based

Atlas segments are *file-cluster boundaries* — useful for rationale
extraction (each segment IS a module). For high-level concepts, the
boundary is *what kind of claim* (a security constraint cuts across
all segments). Category-based fan-out lets each worker specialize on
the rubric for its claim type.

### Output

Generate emits to a transient table `concept_candidates`:
- `kind='concept'` (always)
- `status='seed'` (always — Validate decides final status)
- `candidate_run_id` foreign-key linking to a Generate run
- All other fields per `to_save_dict`

Synthesizer pass deduplicates within the run (anchor-overlap +
title-Jaccard, reusing `concept_clustering.py`).

### Telemetry

`generate_swarm_complete` event:
```json
{
  "swarm_size": 10,
  "candidates_emitted": 142,
  "candidates_after_dedup": 87,
  "elapsed_seconds": 487.2,
  "per_category_counts": { "architecture": 14, ... }
}
```

---

## 4. Validate swarm

### Per-concept critique

Each Validate worker receives 1-3 candidate concepts plus the
**grounding rows whose anchors overlap with the concept's anchors**
(the rationale rows it ostensibly summarizes, plus the source files
or doc files cited as anchors, content excerpted).

### T3 rubric (carries from Phase 125 T3_RESEARCH.md, lightly adapted)

| Tier | Passing test | Verdict |
|---|---|---|
| **T3** | Codified in CI/types/constraint OR explicit in design doc + ≥1 enforcing mechanism (test/lint/decorator/contract); falsifiable in <5min via grep/test | `active` |
| **T2** | Documented decision (anchor in `.md` planning doc) + observable enforcement pattern in code | `active` |
| **T1** | Pattern observed; no enforcement; speculative reading | `triage_pending` |
| **REJECT** | Anchors don't actually support the claim, or claim is restating a graph fact / file-level observation, or claim is a banned-list cliché | `archived` |

**Anchor-grounding rule (clarification for 125c):** an anchor can be a
source file, a `.md` planning doc, or a marketing doc. What matters is
whether the validator can verify the concept's *claim* against the
anchor's *content*. A business goal anchored to `websites/apps/marketing/`
that's also enforced by a runtime check is T2. The same goal with no
runtime check is T1.

### Worker prompt shape (sketch)

```
SYSTEM:
You are a hostile reviewer. For each candidate concept, decide whether
the concept's claim is supported by its grounding. Use the T3 rubric:
{T3, T2, T1, REJECT}. Field order: counter_evidence FIRST,
falsification SECOND, tier_pairwise THIRD, tier LAST.

USER:
CANDIDATE 1
title: {...}
content: {...}
anchors: {...}
self-rated tier (from Generate): {...}

GROUNDING FOR CANDIDATE 1
- rationale row {...}: title, content, anchors
- source file excerpt {anchor1}: lines L-L+50
- doc excerpt {anchor2}: heading + 500 chars

EMIT
{ "candidate_id": "...", "verdict": "T3|T2|T1|REJECT",
  "counter_evidence": "...", "falsification": "...",
  "tier_pairwise": "closer_to_lower|closer_to_higher",
  "rationale": "..." }
```

### Disagreement reconciliation

If Generate said T3 and Validate said T1, downgrade to T1 (Validate
wins). If Generate said T1 and Validate said T3, upgrade to T2
(meet in the middle when validator is strictly more rigorous than
generator — surfaces the fact for a second look).

### Telemetry

`validate_swarm_complete`:
```json
{
  "input_count": 87,
  "verdict_distribution": {"T3": 8, "T2": 24, "T1": 31, "REJECT": 24},
  "tier_changes": {"upgraded": 4, "downgraded": 18, "rejected": 24},
  "elapsed_seconds": 312.5
}
```

---

## 5. Pass 5 — deterministic gate (wires existing `run_pass4_gate`)

Tiebreaker only. Validate's verdict is the source of truth. Gate
exists for safety (e.g., if Validate fails wholesale, candidates fall
to `seed` and the gate catches them by confidence).

```python
T3, T2 → 'active'
T1     → 'triage_pending'  # NEW status — see §6
REJECT → 'archived'
```

---

## 6. Schema additions

### Add `triage_pending` to `VALID_STATUSES`

```python
VALID_STATUSES = {
    "seed", "active", "archived",
    "proposed", "superseded", "deprecated",
    "triage_pending",   # NEW Phase 125c
}
```

### Add `candidate_run_id` (optional)

For traceability — every concept saved by Generate carries its run id.
Lets us purge a bad run, replay Validate without re-Generate, etc.

```sql
ALTER TABLE concepts ADD COLUMN candidate_run_id TEXT;
```

Idempotent migration.

### `prep_concepts(action='get')` default filter

Already filters to `kind='concept'`. Update to also surface
`triage_pending` alongside `active` by default — both are visible to
consumers; only `archived` is hidden by default.

---

## 7. Backlog (one-knob-per-PR)

| ID | Change | Risk | Est LoC |
|---|---|---|---:|
| T1 | Doc-discovery — `docs_grounding.json` builder + tests | low | ~250 + 15 tests |
| T2 | Generate swarm — replace `synthesize_concepts` with swarm orchestrator + per-worker prompt builder | med | ~400 + 20 tests |
| T3 | Validate swarm — new module + per-concept critique prompt | med | ~350 + 18 tests |
| T4 | Schema: `triage_pending` status + `candidate_run_id` column | low | ~40 + 4 tests |
| T5 | Wire Pass 4 gate (`run_pass4_gate`) into `_concepts_worker` | low | ~30 + 3 tests |
| T6 | Update `_concepts_worker` to chain Pass 1 → Pass 2 → Pass 2b → Pass 3 (Generate) → Pass 4 (Validate) → Pass 5 (gate) | med | ~80 + integration tests |
| T7 | Telemetry: `generate_swarm_complete`, `validate_swarm_complete`, `pass5_gate_complete`. Update audit harness EXPECTED list | low | ~50 |
| T8 | `prep_concepts(action='get')` default surfaces active+triage; trailer wording update | low | ~30 |
| T9 | Migration: existing `kind='concept'` rows from 125b synthesizer treated as Generate output, run Validate over them once on first 125c run | low | one-shot script |
| T10 | Acceptance run on SourcePrep + 1-2 external projects + RESULTS.md | low | manual |

---

## 8. Acceptance for "done"

This phase ships when, simultaneously:

1. SourcePrep produces a curated concept set (≤~50 active +
   ≤~20 triage_pending) with **at least some T3 emissions**
   (vs 125b's zero).
2. The `prep()` ambient trailer reads `[N concepts (X active,
   Y triage) — kind='concept'] + [M module rationale]` cleanly.
3. `prep_concepts(action='get')` returns active+triage by default;
   `archived` is hidden but queryable.
4. Two external projects (HomeColab + one other) each produce a
   shape consistent with their codebase complexity — small repo →
   handful of concepts; large repo → ~50.
5. Validate swarm rejects ≥10% of Generate's output on at least one
   project (proves the critic is actually critiquing, not rubber-stamping).
6. Pipeline telemetry events fire and the harness recognizes them.
7. RESULTS.md documents per-project counts, tier distribution,
   reject rate, wall-time per pass, and 5-10 sample concepts that
   passed and 5-10 that got rejected (with reasons).

---

## 9. Out of scope

- Antibody promotion (parallel broken flywheel from Phase 124)
- Triage review dashboard UI (consumer of `triage_pending`)
- Cross-project concept federation
- Re-tuning Pass 1 worker prompt (Phase 124 owns it)
- Generalizing the two-swarm pattern to ENRICHMENT/ATLAS (Phase 126+)

---

## 10. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Doc auto-discovery surfaces wrong files (e.g., generated `.md` reports) | med | Skip generated dirs (`<idx_dir>/`, `node_modules`, `dist`, `build`); only count `.md` files in tracked git history |
| Generate swarm produces too much (>200 candidates) | low | Per-worker emit cap (10-15); synthesizer dedup before Validate; if still over, top-N by tier_pairwise score |
| Validate swarm rubber-stamps Generate's tier (no critique value) | med | Telemetry reject rate; if <5% across 3 runs, the prompt isn't pushing hard enough — add adversarial examples |
| Worker count over-saturates cloud LLM endpoint | low | Reuse Phase 82 unbounded latency-aware discovery — already proven |
| Validate's smaller model disagrees in unhelpful ways | low | Use SAME model class for Generate and Validate by default; offer cheaper-model as opt-in |
| Existing 125b concepts (in `kind='concept'`) get clobbered | med | T9 migration: treat existing rows as candidates, run Validate over them once before 125c's first true run |

---

## 11. Open questions

1. **Should Generate workers see existing concepts** (from prior runs)
   to avoid re-emitting them? Lean YES — pass active concepts as
   "already-known, do not duplicate" in the prompt. Cheap, prevents
   noise.

2. **Validate disagreement policy** — "downgrade wins" is the safe
   default but might over-archive. Worth instrumenting on first run.

3. **Should `triage_pending` count toward the project's cap?** 125b's
   per-kind cap is 500. If we hit it with triage, eviction order
   needs an update so triage doesn't squeeze out active.

4. **Re-runs and freshness:** today, synthesizer skips when
   rationale hasn't changed. With Validate, "rationale unchanged but
   doc grounding changed" should still re-run (planning docs evolve).
   Update freshness fingerprint to include doc set hash.

5. **Cost ceiling:** what's the wall-time budget? 125b targeted
   ~3-5 min (single call). Two swarms could push to 15-20 min on a
   large repo. Acceptable? If not, what's the cap?

---

## 12. Pointers

| What | Where |
|---|---|
| 125b synthesizer (to be replaced) | `src/prep/core/concept_synthesizer.py` |
| Existing swarm orchestrator | `src/prep/services/swarm_orchestrator.py` (used by concept_seeder) |
| Existing clusterer (Pass 2 reuse) | `src/prep/core/concept_clustering.py` |
| Existing gate (wired in §5) | `src/prep/core/concept_promotion_pipeline.py:run_pass4_gate` |
| Concept store | `src/prep/services/concept_store.py` (`VALID_STATUSES`, `VALID_KINDS`) |
| Pipeline worker (wires the chain) | `src/prep/services/pipeline/workers.py:_concepts_worker` |
| MCP ambient trailer | `src/prep/mcp/server.py` (search `prep_concepts`) |
| Atlas markdown link map (Phase 124) | `<idx_dir>/atlas_markdown_links.json` |
| T3 rubric reference | `docs/Phase125_ConceptPromotionPipeline/T3_RESEARCH.md` |
| 125b README (architectural baseline) | `docs/Phase125b_TwoLayerConceptArchitecture/README.md` |
| Auto-acceptance bug fix (this phase's prerequisite) | commit `ecb9dee0` |

---

## 13. Cross-references

- **Phase 125** — Pass 4 gate logic reused. T3 swarm idea revived as
  Validate. T1 clusterer reused as Pass 2.
- **Phase 125b** — abstraction layer (concept vs module_rationale) and
  store schema preserved. Synthesizer engine replaced.
- **Phase 124** — `atlas_markdown_links.json` is the doc-discovery
  primary signal. Anchor coverage gains carry through.
- **Phase 122** — `concept_promotion.py` finally retires (this phase
  obsoletes the manual promotion path entirely).
- **Phase 82** — SwarmOrchestrator's unbounded latency-aware concurrency
  used by both Generate and Validate.
- **Phase 87 (immune system)** — depends on T3 emissions. 125c is the
  delivery vehicle for actual T3 concepts → the antibody pipeline
  finally gets fuel.

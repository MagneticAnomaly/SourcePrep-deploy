# Phase 125b — Two-Layer Concept Architecture

> **Scope:** Reframe what the project calls "concepts" by splitting the
> current single layer into TWO distinct abstractions: per-module
> **rationale** entries (many, browseable, fine-grained) and true
> **concepts** (few, cross-cutting, agent-actionable). Adds a new
> synthesis step that consumes module rationale + atlas + audit +
> antibody-eligible patterns + T2 doc links and emits 30-100 high-level
> concepts. Repurposes (does not throw away) the existing 2,000+
> per-module entries.
>
> **Status:** Implementation complete — verified live on HomeColab 2026-05-03
> **Date opened:** 2026-05-03
> **Supersedes:** Phase 125 T3 (parked) — the tier-rubric LLM critique
> applies to the NEW concept layer, not the per-module rationale.
> **Companion:** Phase 124 (Finalize chain), Phase 123 (synthesis
> wall-time bumps), Phase 122 (feature audit). All preserved + load-bearing.

---

## 0. Getting started (next agent, read this first)

This phase is an **abstraction-layer redirect**, not a volume-trim.
Phase 125 v1 framed the problem as "compress 2,000 → 50 via multi-pass
LLM critique." That treats the symptom. The actual problem is the
**kind of thing** the swarm produces today: per-module observations
that should never have been called concepts.

After Phase 125b ships:

- The 2,000 per-module entries become **module rationale**:
  searchable annotations, NOT shown as concepts in any UI or MCP tool.
- A NEW synthesis step produces **true concepts**: 30-100
  cross-cutting axioms / decisions / tradeoffs, with rich grounding
  pulled from atlas, audit, antibody patterns, clustered rationale,
  and T2 doc links.
- Phase 125's tier-rubric research (T3) applies to the NEW concept
  layer, where the small set makes manual review tractable.

### Recommended first session (≤2 hours)

1. **Read §1 (the abstraction split) and §2 (the new pipeline shape)**
   to internalize the difference. Without that mental model, every
   downstream change reads as a volume tweak when it's actually
   a layer separation.
2. **Inspect the current 2,000 HomeColab + 3,123 SourcePrep entries**
   to confirm they're per-module rationale (anchor + content shapes),
   not cross-cutting concepts. Spot-check 5-10 randomly.
3. **Review §4 schema migration** carefully — it's an in-place
   rename, not a destructive change. Backfill is idempotent.
4. **Open T1 (schema split + migration) as the first PR.** Without
   this, every subsequent change hits a layer-confusion problem.

### What this phase explicitly does NOT do

- Delete the existing 2,000+ per-module entries. They become rationale.
- Re-architect the swarm orchestrator, atlas, audit, or T2 work.
  All preserved.
- Add a NEW pipeline stage. Synthesis becomes a sub-step inside Stage 13
  (CONCEPTS). Stage count stays 15.
- Build new MCP tools. We update existing `prep_concepts` filter and
  rely on `prep_search` to surface module rationale.
- Wipe and re-run from scratch. Migration is idempotent in-place.

---

## 1. The abstraction split

### What "concepts" should mean (LLM-utility argument)

An LLM agent working on a codebase needs three classes of
non-obvious-from-code knowledge:

| Need | Volume that helps |
|---|---|
| **Constraints — what NOT to do** | 5-20 statements |
| **Decisions — non-obvious why** | 20-50 statements |
| **Tradeoffs — known compromises** | 5-15 statements |

**Total: 30-100 concepts** for any project. This is the working set
an agent ingests on every task. Larger than that breaks the token
budget — 2,000 concepts × 200 chars = 400 KB, well past any
reasonable MCP context budget.

### What the 2,000+ per-module entries actually are

Per-module observations:
- "This file does X because Y"
- "This subsystem owns the interface to Z"
- "Module M centralizes the W concern"

These are **augmentation-level**: same abstraction as
`trace_augmented.jsonl` (per-file summaries), just at module scope.
They duplicate what atlas + augmentations already provide, and they
inflate the concept layer to uselessness.

### The split

| Layer | Count | Storage | Audience | Surface |
|---|---:|---|---|---|
| **Module rationale** (renamed current per-module output) | thousands | `concepts` table with `kind='module_rationale'` | Agents searching for "why does this module exist" | `prep_search` |
| **Concepts** (true cross-cutting) | 30-100 | `concepts` table with `kind='concept'` | Agents on every task — orientation + constraints | `prep_concepts`, AGENTS.md ambient |

Same table; new `kind` discriminator. No data thrown away.

---

## 2. The new pipeline shape (inside Stage 13 CONCEPTS)

```
Stage 13 CONCEPTS (~25 min total on cloud)

  ┌─ Pass 1 — Per-module rationale extraction (existing seeder, RELABELED)
  │  Worker prompt: "Extract module rationale entries"
  │  Output: 1,500-3,000 entries with kind='module_rationale'
  │  Time: ~18 min cloud (unchanged)
  │
  ├─ Pass 2 — Anchor-overlap clustering (Phase 125 T1, applies HERE)
  │  Output: cluster_id stamped on rationale entries; ~300-500 representatives
  │  Time: seconds
  │
  ├─ Pass 3 — Concept synthesis (NEW — single LLM call with rich grounding)
  │  Inputs:
  │    • atlas.json + atlas_segments
  │    • audit findings (top-N)
  │    • spaghetti hotspots (high-severity)
  │    • antibody-eligible constraint patterns
  │    • clustered module rationale (representatives only)
  │    • T2 markdown links (top docs by mention count)
  │    • Phase docs (active phases)
  │  LLM produces: 30-100 concepts with category + tier + anchors
  │  Stored as kind='concept'
  │  Time: ~3-5 min cloud (one rich call, possibly N=3 self-consistency)
  │
  └─ Pass 4 — Deterministic gate (Phase 125 T4, applies to NEW concepts only)
     T3 → status='active'
     T2 → status='triage_pending'
     T1 → status='archived'
```

### Why one LLM call (vs swarm) for synthesis

Per-module fan-out works for rationale extraction (each worker has a
narrow scope = one module). Synthesis is the OPPOSITE — it needs the
WHOLE picture in one prompt. A single LLM call with rich aggregated
input is the right shape. If the prompt + grounding fits the model's
context window (≤128K for Kimi/Qwen3), one call is fastest, cheapest,
and produces the most coherent cross-cutting output.

Optional N=3 self-consistency at synthesis layer is a nice-to-have
once we measure baseline output quality. Not in v1.

---

## 3. Why this leverages every upstream artifact

| Upstream | How synthesis uses it |
|---|---|
| Atlas (modules, hubs, cross-cutting concerns) | The map of WHAT to look for cross-cutting |
| Audit findings (architectural issues) | Pre-flagged candidate constraints / decisions |
| Spaghetti scores (high-severity hotspots) | Where the architecture is straining |
| Antibody-eligible patterns | Constraints already identified by the immune system |
| Module rationale clusters (Pass 1+2) | Per-module evidence used as grounding for concepts |
| T2 markdown links (top docs by mention) | Doc evidence — phase decisions, ADRs |
| Phase 13 docs / superpowers plans | Active in-flight decisions worth elevating |

Nothing in Phase 124 / 123 / earlier is wasted. **Every artifact
becomes input to a single synthesis prompt that lifts abstraction
once.**

---

## 4. Schema migration

### Add `kind` column (idempotent)

```sql
ALTER TABLE concepts ADD COLUMN kind TEXT
  NOT NULL DEFAULT 'module_rationale';
```

Existing rows default to `kind='module_rationale'` (matches what
they actually are).

### `VALID_KINDS` constant

```python
VALID_KINDS = {"concept", "module_rationale"}
DEFAULT_KIND_FOR_LEGACY_ROWS = "module_rationale"
```

### `concept_store.list_concepts` filter

Default behavior: `list_concepts(project_id, kind='concept')` — only
true concepts. Pass `kind='module_rationale'` to browse the rationale
layer; pass `kind=None` to see both.

### Migration script (one-shot)

```python
# tools/migrate_concepts_to_two_layers.py
# - ALTER TABLE if column missing
# - UPDATE concepts SET kind='module_rationale' WHERE kind IS NULL
# - Idempotent — safe to re-run
```

### MCP / API impact

- `prep_concepts(action='list')` defaults to `kind='concept'`
- `prep()` ambient context shows count of `kind='concept'` only
- `prep_search` indexes both, distinguished in result metadata
- AGENTS.md ambient block surfaces top kind='concept' entries

---

## 5. Concept synthesis prompt (sketch — full template in T3_RESEARCH.md)

```
SYSTEM:
You synthesize cross-cutting concepts from a codebase analysis. A
"concept" is a SINGLE statement that:
- spans MULTIPLE modules or files
- captures a constraint, decision, or tradeoff NOT obvious from code
- is action-shaping for an AI agent working on this codebase
- has at most 30-100 across an entire project

GOOD concepts:
- "License verification must precede any cloud LLM call" (constraint, T3 — codified via decorator)
- "Embedded mode preserves git-trackability — never write to ~/.local for indexes" (decision, T2)
- "Tauri over Electron for binary size — 8 MB vs 80 MB" (tradeoff, T1)

BAD concepts (do NOT emit):
- "Function X validates inputs" (file-level, observable)
- "Module Y handles authentication" (file-level, observable)
- "Import dependency between A and B" (graph fact)

TIER classification (per Phase 125 T3 research):
  T1 — observed; no enforcement
  T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
  T3 — codified in CI/types; violations fail build

USER:
[Atlas summary]
[Audit critical findings]
[Spaghetti top hotspots]
[Antibody-eligible candidates]
[Module rationale clusters — top 50 by member count]
[T2 top docs by mention count]
[Phase docs index]

Emit 30-100 concepts as a JSON array. Each:
  { title, content, category, tier, tier_pairwise, anchors,
    counter_evidence, falsification, refined_content }
```

Field order matches Phase 125 T3 research (rationale before tier;
long free-text last).

---

## 6. Backlog (one-knob-per-PR)

| ID | Change | Risk | Est LoC |
|---|---|---|---:|
| T1 | Schema migration: add `kind` column + backfill + `VALID_KINDS` constant | low | ~80 + 10 tests |
| T2 | `concept_store.list_concepts` defaults `kind='concept'`; backward-compat for callers passing kind=None | low | ~30 |
| T3 | Rename concept seeder worker output: set `kind='module_rationale'` on save_many | low | ~10 |
| T4 | NEW `concept_synthesizer.py` — single-LLM-call synthesis with rich grounding | med | ~350 + 20 tests |
| T5 | Wire synthesizer as Pass 3 inside `_concepts_worker` (after Pass 1 rationale + Pass 2 clusterer); keep Pass 4 gate from old Phase 125 | low | ~40 |
| T6 | Migration script `tools/migrate_concepts_to_two_layers.py` — runs once per project | low | ~80 |
| T7 | MCP `prep_concepts` filter — default kind='concept', surface kind in result metadata | low | ~30 |
| T8 | `prep_search` indexes both, distinguishes by kind in metadata | low | ~30 |
| T9 | AGENTS.md ambient surfaces top kind='concept' entries (drops kind='module_rationale' from the trailer) | low | ~30 |
| T10 | Telemetry events: `concept_synthesis_complete`, `concept_synthesis_failed` | low | ~30 |
| T11 | Live verification on HomeColab + SourcePrep — count, quality, ECE | low | manual |

---

## 7. Acceptance for "done"

This phase ships when:

1. `concept_store` has the `kind` column with all existing rows
   migrated to `kind='module_rationale'`.
2. `prep_concepts` returns 30-100 entries by default (kind='concept'
   only). HomeColab and SourcePrep both produce concept counts in
   that range after the next pipeline run.
3. `prep_search` indexes both layers; results carry the kind.
4. AGENTS.md ambient block lists top concepts (the small layer),
   not the rationale layer.
5. `concept_synthesizer.py` runs as Pass 3 inside the concepts stage.
6. Telemetry events fire (`concept_synthesis_complete`).
7. `RESULTS.md` documents before/after counts and a sample of the
   concept output (qualitatively reviewed).
8. Phase 125 T3 implementation is parked OR retargeted at the new
   concept layer (where the tier rubric makes more sense).

---

## 8. Out of scope

- Re-architecting the swarm orchestrator. Pass 1 fan-out stays.
- Replacing audit / atlas / antibody. Synthesizer just consumes them.
- A new MCP tool for module rationale. `prep_search` already covers it.
- Cross-project concept federation.
- Per-tier human-in-the-loop UI. Use existing `triage_pending` status
  surface.

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Synthesizer prompt grows past context budget on large projects | med | Cap each input source (top-N hotspots, top-N modules, etc); test on largest project (SourcePrep ~636 modules) before claiming done |
| Single-LLM-call gives worse output than swarm | low | N=3 self-consistency is a one-flag follow-up; test single-call first |
| Migration breaks existing `concept_store` callers | med | Backward-compat: `list_concepts(kind=None)` returns both |
| Per-module rationale becomes orphan layer (nobody reads it) | low | `prep_search` indexes it; phase doc / AGENTS.md should mention it as searchable |
| Old Phase 125 T3 prompt code (parked) bit-rots | low | Document parked status in T3_RESEARCH.md; revisit when synthesizer ships and we re-evaluate tier-rubric application |

---

## 9b. Completion notes (2026-05-03)

### What landed

| Item | Where | Status |
|---|---|---|
| Schema: `kind` column (idempotent ALTER) | `concept_store.py` | ✅ |
| Kind-aware `save_many`, dedup, list, stats | `concept_store.py` | ✅ |
| Synthesizer module (700 LoC) | `concept_synthesizer.py` | ✅ |
| Pass 3 wiring in `_concepts_worker` | `services/pipeline/workers.py` | ✅ |
| Seeder tags swarm output `kind='module_rationale'` | `concept_seeder.py` | ✅ |
| MCP ambient block kind-aware | `mcp/server.py` | ✅ |
| 23 unit tests | `tests/test_concept_synthesizer.py` | ✅ all passing |
| **T2/T3 → status='active'**, T1 → 'seed' (synth is the gate) | `concept_synthesizer.py` `to_save_dict` | ✅ wrap-up |
| **Kind-aware eviction** (rationale evicted last; concept-seeds first) | `concept_store.py` `_evict_oldest` | ✅ wrap-up |
| **Synthesizer freshness check** (skip when rationale unchanged) | `concept_synthesizer.py` `synthesize_concepts(force=False)` | ✅ wrap-up |
| **Truncated-JSON salvage in parser** (recover entries up to last `}`) | `concept_synthesizer.py` `_salvage_truncated_json_array` | ✅ scrutiny fix |
| **Lower `num_predict` 8000 → 5000** (avoid hitting cap on large codebases) | `concept_synthesizer.py` LLM call | ✅ scrutiny fix |
| **Audit harness recognises `concept_synthesis_skipped_fresh`** | `tools/finalize_chain_audit.py` EXPECTED list | ✅ scrutiny fix |
| Live HomeColab verification | run 1: 31 emitted, run 2: 20 emitted, both T1+T2 | ✅ |
| Live CoDRAG verification (run 1, before fixes) | `parse_failed_or_empty` after 280s — 8000-token cap truncated JSON. | ❌ exposed bug |
| Live CoDRAG verification (run 2, after fixes + restart) | **21 emitted, 21 saved. Tier dist T3=4 / T2=13 / T1=4 — first T3 emissions across any project. 110s elapsed.** Salvage parser not invoked (LLM finished cleanly within 5000 tokens). | ✅ |
| **Eviction priority fix** (rationale-first → concept-active-last) | Original 125b SQL evicted concept-seeds before rationale, inverted from the comment's intent. CoDRAG run worked by accident because concepts didn't exist yet at eviction time. Fixed to evict in order: archived → rationale → concept-seed → concept-active. | ✅ scrutiny fix |
| **Per-kind caps + per-kind eviction** | Replaced single `MAX_CONCEPTS_PER_PROJECT=200` (which silently destroyed the rationale layer when a fresh batch exceeded 200) with `{concept: 500, module_rationale: 2000}`. Eviction is per-kind so a rationale batch can't trim concepts. | ✅ scrutiny fix |
| **Worker prompt: 3-8 → 0-3 rationale per module** | Root cause of the 2,430-row over-production was the worker prompt asking for "3-8 concept seeds" per module. Updated both worker prompt sites (single-pool and swarm paths) to ask for "0-3 load-bearing rationale entries" with explicit permission to emit nothing for ~30% of modules where the WHY is obvious. Quality > volume. | ✅ scrutiny fix |
| **Razor-sharp prompts** (techniques from Xiong/Madaan/Liu/Anthropic 2024-25) | Synthesizer + both worker prompts rewritten to incorporate: (1) **Empty Set Permission** — `[]` is acceptable, padding flagged as failure mode. (2) **BANNED outputs** — junior-reviewer generic concepts ("uses async", "modular architecture") explicitly forbidden. (3) **Quote-then-Claim** — concepts must logically follow quoted grounding spans. (4) **Counter-evidence FIRST** — populated before tier; T3 requires non-empty counter-evidence refuted by anchor. (5) **Falsifiability test** — assertion must be grep-disprovable in <5min. (6) **Named-tier rubric** — labels not floats, "DO NOT DEFAULT TO T2". (7) **Hostile-reviewer downgrade pass** — final self-critique before serialize. (8) **Field order: tier last**, computed from prior fields. | ✅ scrutiny fix |
| **Per-kind status fields in stats API** | `get_stats` now returns `concepts_active`, `concepts_seeds`, `module_rationale_active`, `module_rationale_seeds` so callers don't have to conflate. | ✅ dogfood fix |
| **Trailer wording: per-kind status breakdown** | Old: `[Concepts: 21 (kind=concept; 17 active, 184 seeds)]` — the 184 included rationale-seeds, so the wording implied 184 concept-seeds. New: `[21 concepts (17 active, 4 seed) + 180 module rationale (0 active, 180 seed)]` — unambiguous. | ✅ dogfood fix |
| **Audit's silent "Concepts loaded: 0"** | `tool_audit_structural` accessed in-process `concept_store` singleton. When MCP server runs in proxy mode (separate process from daemon), the singleton is uninitialized → `RuntimeError` swallowed at DEBUG level → audit reports 0 concepts. Fixed: route concept fetch through HTTP API, same as hub_files / cycles. | ✅ dogfood fix |
| **API: `/concepts?kind=...` filter** | Added `kind` query param (default `"concept"`); `kind=` (empty) returns both layers. | ✅ dogfood fix |
| **UI shows per-layer counts** | `ConceptsPanel.tsx` now renders `Concepts: 21 / Rationale: 179` when backend returns per-kind counts (the legacy `total: 200` was conflating both layers). | ✅ scrutiny fix |

### Live results on HomeColab (2026-05-03)

Two pipeline runs against `/Volumes/Thunderbolt/XcodeProjects/HomeColab`
(project_id `ef18334f-8f71-415c-88e0-007e6b90bae1`):

- 51 `kind='concept'` (synthesizer output, 28 T2 + 23 T1)
- 24 `kind='module_rationale'` (seeder output, 15 high-conf + 9 T2)
- Synthesis wall-time: 102s and 114s for the two runs (well within budget)
- After wrap-up status fix: ~28 'active' (T2) + ~23 'seed' (T1) on next run

Sample T2 concepts emitted (all anchored to HomeColab files):
- "Firestore schema is single-source-of-truth across iOS, web, and functions"
- "Compliance review gates all MLS-adjacent features before code merge"
- "Dual-app strategy forces shared component extraction into HomeColabCore"
- "Native ad rendering requires UIViewController containment breaking SwiftUI purity"

### Known gaps (deferred — NOT 125b scope)

1. **No T3 emission observed.** Synthesizer prompt allows T3 (verifiable +
   anchored + falsifiable) but live runs only produced T1 + T2. T3 is the
   antibody-fuel tier; without it Stage 15 yield stays near zero. Investigate
   prompt nudges and few-shot examples in a follow-up.
2. **~50% rationale↔concept overlap.** Pass 3 paraphrases ~half the rationale
   themes with sharper specificity. Acceptable — both layers serve different
   surfaces (LLM ambient vs. browseable detail). Could explore a "skip Pass 3
   for items that already exist as high-conf rationale" heuristic.
3. **Pipeline sequencing regression.** First HomeColab run got stuck between
   concepts → audit transition (preexisting bug, not introduced by 125b).
   Tracked separately in `project_pipeline_sequencing_bug` memory.
4. **Antibody derivation untested.** Until T3 concepts (with assertions +
   anchors) are produced, antibody store stays at 0. Validation deferred
   until T3 prompt work lands.

### Wrap-up follow-ups

- **Antibody-tier prompt work (next phase).** Make T3 a first-class
  output: explicit examples in the prompt of what falsifiable + anchored
  + cross-cutting looks like; possibly a separate Pass 4 that takes T2
  concepts and asks "can you state this as a falsifiable assertion with a
  file anchor?"
- **Migration tool** (`tools/migrate_concepts_to_two_layers.py`) — listed
  in §10 but not built. Existing data is already kind=NULL → defaults to
  module_rationale via SQL fallback; no migration tool needed for current
  installs. Document this and remove the tool from §10.

---

## 10. Pointers

| What | Where |
|---|---|
| Concept store | `src/prep/services/concept_store.py` |
| Per-module seeder (to relabel) | `src/prep/core/concept_seeder.py:62 seed_concepts` |
| NEW synthesizer | `src/prep/core/concept_synthesizer.py` (created) |
| `_concepts_worker` (wire synthesizer) | `src/prep/services/pipeline/workers.py:1047` |
| Phase 125 T1 clusterer (reused) | `src/prep/core/concept_clustering.py` |
| Phase 125 T3 research (apply to NEW concepts) | `docs/Phase125_ConceptPromotionPipeline/T3_RESEARCH.md` |
| MCP `prep_concepts` | `src/prep/mcp/server.py` (search for `prep_concepts`) |
| Synthesis manifest (freshness) | `<idx_dir>/concept_synthesis_manifest.json` |

---

## 11. Cross-references

- **Phase 125 (ConceptPromotionPipeline)** — supersedes T3 implementation; T1 (clusterer) lives on as Pass 2 over module rationale.
- **Phase 124 (FinalizeChainEpistemicAudit)** — atlas T2 markdown_links + spaghetti are direct synthesis inputs.
- **Phase 123 (ConceptQualityRefinement)** — synthesis wall-time fix preserved.
- **Phase 122 (FeatureUtilizationAudit)** — `concept_promotion.py` becomes "promote a module rationale to a concept" once the layer split lands.
- **MASTER_TODO.md** — Phase 125b entry + cross-phase follow-up for "old Phase 125 T3 parked, retargeted at new layer."

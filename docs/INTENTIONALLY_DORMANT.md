# Intentionally dormant features

> Modules that are **built and tested but currently have no production
> callers**. Triaged via Phase 122 §4.2 protocol. We keep them because
> deletion would be lossy and the upstream code path (often a UI flow
> or external trigger) is genuinely planned, just not yet built.
>
> If a module on this list grows a real caller, remove it from here.
> If a module here ages out (>6 months unused, no plan), demote to a
> DELETE PR.

## concept_promotion.py
- **Path:** `src/prep/core/concept_promotion.py` (72 LoC)
- **Public API:** `suggest_promotion(observation)`,
  `build_concept_from_observation(observation)`,
  `PromotionSuggestion`
- **Production callers:** 0 (verified 2026-05-01 via Phase 124 T6)
- **Why we keep it:** Architecturally complementary to the swarm
  concept seeder (`concept_seeder.py`). The seeder generates concepts
  from module *structure*; this module promotes
  `prep_observe`-style human/agent observations into concepts via
  category-similarity heuristics. They serve different inputs and the
  observation→concept lifecycle is a planned UI flow, not a duplicate
  of the seeder.
- **Why it's dormant:** The dashboard and `prep_observe` MCP tool
  do not currently surface a "suggest promotion" affordance. Wiring
  is a separate UI/UX phase.
- **State (2026-05-01):** all 1,779 SourcePrep concepts have
  `status="seed"`. None has been promoted to `active`. Confirms the
  promotion path is not running.
- **Trigger to wire:** when (a) the dashboard adds a Concepts panel
  surface for inspecting unanswered observations, or (b) the
  `prep_observe` MCP tool gains a `suggest_promotion=True` flag.
- **Owner:** unassigned. File follow-up issue if you wire it.

## treatment_registry.py
- **Path:** `src/prep/core/treatment_registry.py` (99 LoC)
- **Public API:** `TreatmentConfig`, `TreatmentRegistry`
  (`get_treatment`, `compute_batch_size`)
- **Production callers:** 0 (verified 2026-05-13 via Phase 122
  Custodian run + grep). Unit tests at
  `tests/test_content_class.py` exercise it in isolation.
- **Custodian classification:** needs_review
- **Custodian reason:** "Defines TreatmentRegistry/TreatmentConfig
  with specific business logic and parameters for 'Phase 53'
  processing. While no static imports were found, registries of this
  nature are frequently accessed via dynamic discovery... Deleting
  core configuration logic for a specific processing phase requires
  manual verification that the phase itself is no longer active."
- **Triage decision:** KEEP-DORMANT
- **Why:** Phase 53 designed a two-piece system —
  `ContentClass` (the 3-class taxonomy) AND `TreatmentRegistry`
  (the per-class batch-size and prompt-routing config). ContentClass
  shipped wired (`augmenter.py:1336`, `epistemic_enrichment.py:711`),
  but the per-class lookup via `TreatmentRegistry.compute_batch_size`
  was never connected. The augmenter and epistemic enrichment
  classify into 3 buckets and then apply a uniform `batch_size`
  from `self._batch_profile.batch_size(...)` instead of the
  per-class value the registry was built to provide.
- **State (2026-05-13):** Module loads, tests pass, unit-tested
  in isolation. Phase 112 Fix 8 lesson applies — isolated unit tests
  without an integration test that actually exercises the seam is the
  symptom that surfaced this in audit. No production data path
  consumes the registry's output.
- **Trigger to wire:** Replace the uniform `batch_size` at
  `augmenter.py:1338` and the equivalent at
  `epistemic_enrichment.py:711-723` with per-ContentClass calls to
  `TreatmentRegistry.compute_batch_size(content_class, base_size)`.
  Tracked as `P122-T-treatment_registry` in MASTER_TODO.
- **Owner:** unassigned.

## Other modules under audit

Phase 122 lists several other "no external imports" candidates that
need triage. Unless added below explicitly, they are still pending
investigation.

- `antibody_derivation.py` — H3 confirmed via Phase 124 harness:
  derivation IS running (5 antibodies → 594 after T4 lifted concept
  count). The "no external imports" flag is a false positive — the
  derivation runs but is invoked via re-exports. **Status: WIRED,
  flag was wrong.** Remove from Phase 122 audit list.
- `swarm_optimizer.py` — pending; distinct from `swarm_orchestrator`
- `lod_extractor.py` — pending; from Phase 95 LOD work
- `github_sync.py` — pending
- `budget_enforcement.py` — pending
- `chunking.py` — Phase 110 semantic chunking; verify
- `inferred_edges.py` — pipeline stage exists, verify wiring
- `batch_profiles.py` — likely wired via `prep.core` re-export
- `swarm_registry.py` — pending
- `rules_generator.py` — wired (writes AGENTS.md every pipeline run)
- `context_config.py` — pending
- `concept_seeder.py` — wired (Phase 124 T4 integration verified)

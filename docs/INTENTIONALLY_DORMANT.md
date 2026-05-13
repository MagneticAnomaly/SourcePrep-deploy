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

## swarm_optimizer.py
- **Path:** `src/prep/core/swarm_optimizer.py` (34 LoC, mostly
  comments)
- **Public API:** Four module-level int constants —
  `KIMI_MAX_BATCH = 10`, `GEMINI_MAX_BATCH_ITEMS = 200`,
  `GEMINI_ATTENTION_QUALITY_CEILING_TOKENS = 200_000`,
  `GEMINI_HARD_CONTEXT_TOKENS = 800_000`.
  No functions, no classes.
- **Production callers:** 0 (verified 2026-05-13 via Phase 122
  Custodian run + direct grep for each constant name across `src/`).
- **Custodian classification:** needs_review
- **Custodian reason:** "Highly specific, calibrated tuning constants
  for LLM batching and attention limits (Kimi and Gemini). These
  values represent domain-specific knowledge that may be referenced
  dynamically by a configuration loader or a pipeline scheduler not
  captured by static analysis."
- **Triage decision:** KEEP-DORMANT — with deletion precondition.
- **Why:** The file is not part of the working swarm path. Phase 82
  intentionally pruned this module (deleted `PLAN_TIER_CONCURRENCY`
  and `PlanTier` literal per `docs/Phase82_CloudPipelineConcurrency/`
  `05_Completion_Plan.md` line 24, commit `214f261f`); concurrency
  moved to AIMD discovery in `pipeline_scheduler` + persistent
  `concurrency_store`. The 4 remaining constants were added by a
  separate earlier commit (`7216d14a` per SWARM_UI_PLAN_v2 §7) and
  never wired to a consumer. The *values* are alive: `200_000` is
  inlined as a literal at `src/prep/core/batch_profiles.py:276,320`
  and `src/prep/core/epistemic_enrichment.py:588`. What is at risk
  if this file is deleted is the *calibration rationale* in the
  comments (the prose explaining WHY 200_000 is the Gemini attention
  ceiling, why 10 is the Kimi per-file attention lever, etc.) —
  that rationale lives nowhere else.
- **State (2026-05-13):** Module loads, no consumers. Live swarm
  files (`swarm_orchestrator.py`, `swarm_registry.py`,
  `concept_generate_swarm.py`, `concept_validate_swarm.py`,
  `swarm_event_logger.py`, `swarm_models.json`) are unaffected.
  Phase 125c's `concept_generate_swarm.py` *bypasses*
  `SwarmOrchestrator` and runs `ThreadPoolExecutor` directly
  (documented at `concept_generate_swarm.py:15`), so the swarm
  subsystem currently has two execution paths.
- **Trigger to wire OR delete:** Before any deletion, port the
  calibration rationale comments to the call sites that actually
  use the values (`batch_profiles.py:276,320`,
  `epistemic_enrichment.py:588`), OR have those callers re-import
  the constants from this file (recentralization). Owner-decision:
  which direction. Tracked as `P122-T-swarm_optimizer` in
  MASTER_TODO.
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
- `budget_enforcement.py` — pending
- `chunking.py` — Phase 110 semantic chunking; verify
- `inferred_edges.py` — pipeline stage exists, verify wiring
- `batch_profiles.py` — likely wired via `prep.core` re-export
- `swarm_registry.py` — pending
- `rules_generator.py` — wired (writes AGENTS.md every pipeline run)
- `context_config.py` — pending
- `concept_seeder.py` — wired (Phase 124 T4 integration verified)

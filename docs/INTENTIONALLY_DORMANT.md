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

## Other modules under audit

Phase 122 lists several other "no external imports" candidates that
need triage. Unless added below explicitly, they are still pending
investigation.

- `roadmap_miner.py` — pending
- `treatment_registry.py` — likely re-exported via `__init__`
  (Phase 122 §0 false-positive note); verify
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

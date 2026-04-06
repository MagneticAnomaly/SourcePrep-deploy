# Concepts Auto-Seeding & Category Expansion — IMPLEMENTED

This plan addresses the two requests: (1) automatically triggering concept seeding after the deep enrichment pipeline completes, and (2) expanding the concept categories to better support diverse projects like CoDRAG, Homecolab, DebateHaus, and Halley.

> **Status: COMPLETE** — All changes implemented 2026-04-05.

## Proposed Changes

### 1. Expanded Knowledge Categories

To cover complex agentic systems (CoDRAG), collaborative/social apps (Homecolab, DebateHaus), and brand/ecommerce platforms (Halley), we will expand the concept categories from 7 to 11:

*   **`architecture`**: System design, pipeline topologies, overarching structural intent.
*   **`domain`**: Core business logic and rules (e.g., debate rules, household tasks).
*   **`product`**: UX goals, user journeys, and feature prioritization logic.
*   **`epistemic`**: Knowledge representation, agentic reasoning models, cognitive pipelines.
*   **`process`**: CI/CD workflows, operational playbooks, agent operations.
*   **`brand`**: Visual identity, typography, UI/UX feel, tone of voice.
*   **`security`**: Authentication flows, privacy boundaries, data isolation.
*   **`technical`**: Specific implementation constraints, library choices, low-level syntax rules.
*   **`pattern`**: Recurrent code structures and design patterns.
*   **`constraint`**: Performance limits, API restrictions, legacy compatibility.
*   **`decision`**: Architecture Decision Records (ADRs), why X was chosen over Y.

#### [MODIFY] src/codrag/core/concept_seeder.py
*   Update the LLM prompt's JSON schema instructions to include the 11 new categories.
*   Add descriptions for the new categories in the prompt text to guide the LLM's classification.

#### [MODIFY] src/codrag/mcp_tools.py
*   Update the `codrag_concepts` tool input schema `category` enum to match the new 11 categories.

#### [MODIFY] packages/ui/src/components/concepts/ConceptsPanel.tsx
*   Add distinct, aesthetically pleasing badge colors for the 4 new categories (`architecture`, `product`, `epistemic`, `security`) in the `CATEGORY_COLORS` record.

### 2. Auto-Seeding Pipeline Hook

We will auto-seed concepts when the knowledge pipeline finishes extracting the deep context that the seeder requires.

#### [MODIFY] src/codrag/services/pipeline/post_flight.py
*   Add `trigger_concept_seeding(project_id: str, pfl: Any = None)` to `PostFlightActions`.
*   This method will run `codrag.core.concept_seeder.seed_concepts()` in a background daemon thread (so it doesn't block the orchestrator).
*   It will output to the pipeline file logger (pfl) so the dashboard user sees "Auto-seeding concepts..." in the console logs.

#### [MODIFY] src/codrag/services/pipeline/orchestrator.py
*   In `_on_build_transition`, when `run.group == "deep_enrichment"` completes successfully, call `PostFlightActions.trigger_concept_seeding(run.project_id, pfl)` right after `trigger_code_index_build()`.

## Open Questions

None at this time. The expansion correctly covers the mentioned project architectures (AI reasoning -> epistemic, Social apps -> security/product/domain, Design apps -> brand).

## Verification Plan

1. Verify `codrag_concepts` schema reflects 11 categories.
2. Verify TypeScript compiles correctly.
3. Review `PostFlightActions` logic to ensure the background thread cleanly invokes the seeder without blocking state machine transitions.

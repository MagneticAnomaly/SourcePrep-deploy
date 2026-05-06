# Phase 125 — Concept Calibration Worksheet

> **Purpose:** ground truth for the T3 prompt design (see
> `T3_RESEARCH.md`). Hand-label these 50 concepts so we can
> measure ordinal ECE and tier distribution after the new tier-based
> prompt lands. Without this, we're flying blind on calibration.
> **Estimated time:** ~2 hours of focused work (~2 minutes per concept).
> **What to fill:** for each concept, mark ONE of the three tier
> checkboxes AND ONE of the three truth checkboxes. Add optional
> notes if the concept is ambiguous.

## The 3-tier rubric (memorize this — the scorer checks against it)

```
T1 — pattern observed in code; no enforcement.
     Test: a reader could find counter-examples in the same codebase
     that don't follow the pattern, and nothing prevents them.
     Anchor example: "Database access uses connection pools" —
     observed in 3 modules but two other modules use raw connections;
     no test, lint, or type check enforces pooling.

T2 — documented decision with at least one enforcing mechanism (test,
     lint rule, docstring referenced as a contract, ADR with named anchor).
     Test: a developer who violated this pattern would either (a) get
     a test failure, OR (b) be flagged by a linter, OR (c) be pointed
     at a written decision document by a reviewer.
     Anchor example: "API responses use envelope format" —
     enforced by test_api_envelope.py and documented in API.md.

T3 — codified in CI/types/constraint-concept; violations fail the build.
     Test: a developer who violated this pattern CANNOT merge —
     PR-time mypy strict / build / tests will block it.
     Anchor example: "All API responses must be Pydantic BaseModels" —
     mypy strict catches non-BaseModel returns, test_api_schema.py
     validates structure at every PR.
```

## Truth label

Independent of tier — is the concept accurate?

- **TRUE** — accurate description of the codebase (regardless of tier).
- **PARTIAL** — partially accurate but mis-states scope or evidence.
- **FALSE** — concept is wrong or generic boilerplate.

## How to fill

For each concept below, fill in:

- **One tier checkbox** (T1/T2/T3) — your judgment of how well-enforced this concept is.
- **One truth checkbox** (TRUE/PARTIAL/FALSE) — your judgment of whether the concept is accurate.
- **(Optional) Notes** — flag concepts that are ambiguous, near a tier boundary, or whose anchor is wrong/missing.

If you can't decide, mark **PARTIAL** + nearest tier and explain in notes.

## Sampling stratification

This sample is intentionally **not** a random draw. We over-sample
the high-confidence buckets and under-sample the low-confidence
ones because the prompt change is most likely to move concepts
DOWN the tier scale, and we need labels in the upper bands to
detect over-confidence.


Confidence bucket distribution in this sample:

- `≥0.95`: 10
- `0.85-0.95`: 15
- `0.75-0.85`: 15
- `0.65-0.75`: 8
- `<0.65`: 2

Category distribution in this sample:

- `architecture`: 6
- `constraint`: 5
- `decision`: 5
- `domain`: 5
- `epistemic`: 5
- `process`: 5
- `security`: 5
- `technical`: 5
- `brand`: 3
- `product`: 3
- `pattern`: 3

---

## Concepts to label

### Concept #1 — Monorepo Boundary Adapter Pattern

- **ID:** `e3c5ccb4b324`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Monorepo Boundary Adapter Pattern
- **Content:** The subsystem exists solely to create a local import surface that re-exports from @prep/ui, deliberately preventing dashboard components from directly importing shared library internals. This thin adapter maintains monorepo boundary separation, allowing the shared library's API to evolve independently while the dashboard consumes a stable local interface. The one-line re-export is architectural infrastructure, not functional code.
- **Anchors:**
  - `src/prep/dashboard/src/hooks/useScopes.ts`
  - `docs/Phase120_NamedScopes/IMPLEMENTATION_PLAN.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:**  think this sounds right but the description is overly technical and hard to follow -- is this a reule for LLM or for a developer to validate? _____________________________________________________

---

### Concept #2 — Brand migration from 'codrag' to 'prep'/'SourcePrep' drives identifier renaming 

- **ID:** `126aa5ed44e6`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Brand migration from 'codrag' to 'prep'/'SourcePrep' drives identifier renaming with user-visible vs code-level split
- **Content:** The rename spec mandates a precise split: code identifiers (function names, tool names, filenames, dict keys) become 'prep' while user-visible prose becomes 'SourcePrep'. The tool alias 'hi_codrag' → 'hi_prep' follows this convention, matching existing CLI/MCP tools like 'prep_search'. This reveals a systematic brand migration where the old name persists only in 'legitimate migration-source markers', implying careful audit requirements to prevent leakage.
- **Anchors:**
  - `docs/superpowers/specs/2026-04-22-sourceprep-rename-design.md`
  - `docs/superpowers/plans/2026-04-22-sourceprep-rename-implementation.md`
  - `src/prep/mcp/tool_hi.py`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [x] PARTIAL — partially accurate or mis-stated scope (generally true, but hi_codrag is long depreiciated and there is no hi_prep -- this likely found old documents and did not compare to later updated and current code)
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #3 — Dependency-Constrained Testing Strategy

- **ID:** `21a3d8e6944d`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Dependency-Constrained Testing Strategy
- **Content:** The subsystem deliberately bypasses DOM rendering and testing-library dependencies as a pragmatic adaptation to monorepo dependency constraints. This is not a philosophical preference for logic-only testing but a forced architectural compromise—tests run fast because they must avoid unavailable dependencies, not because speed was the primary design goal. The 'fake ScopesApi interface' and mocked API responses substitute for integration testing that would normally require React Testing Library.
- **Anchors:**
  - `packages/ui/src/hooks/__tests__/useScopes.test.ts`
  - `packages/ui/src/components/trace/__tests__/RecoverStagePanel.test.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** I have no idea what this is _____________________________________________________

---

### Concept #4 — User-Initiated Calibration Over Automated Continuous Probing

- **ID:** `838c43a23e8e`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.95
- **Title:** User-Initiated Calibration Over Automated Continuous Probing
- **Content:** The subsystem requires explicit user initiation for probes rather than running automated background calibration. This design choice reflects a cost-optimization constraint: even 'minimal-cost' single-token requests accumulate charges across cloud providers, and unbounded automated probing would violate the 'cost-minimized' mandate. The planning document explicitly frames this as 'explicit user-driven calibration' with a dedicated UI button, making the human-in-the-loop a deliberate safety and budget control mechanism.
- **Anchors:**
  - `docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md`
  - `src/prep/services/pipeline/endpoint_probe.py`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** This is a little meta... this it literally what we are trying to dcide now, we want to avoing excessive decision making _____________________________________________________

---

### Concept #5 — AI-First Search Optimization Over Traditional SEO

- **ID:** `663b856bb824`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.95
- **Title:** AI-First Search Optimization Over Traditional SEO
- **Content:** The subsystem explicitly prioritizes 'AIO' (AI Optimization) alongside classical SEO, reflecting a bet that senior technical decision-makers now discover tools through LLM-assisted search and conversational interfaces rather than traditional Google ranking alone. This shifts content strategy toward answerability, structured intent-matching, and semantic completeness rather than keyword density. The planning document treats this as a competitive necessity for developer tools, not an experimental channel.
- **Anchors:**
  - `docs/Phase42_BetaAccess/SEO_AIO_PLAN.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [x] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #6 — Research Deferral Pattern for Instrument Validity Gaps

- **ID:** `372787d1eb56`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Research Deferral Pattern for Instrument Validity Gaps
- **Content:** The subsystem explicitly acknowledges that current evaluation tools cannot measure agent-level performance, forcing a deliberate deferral of critical experiments to Phase 104's LLM-based evaluation layer. This is not a backlog but a principled research stance: the team refuses to draw conclusions from instruments they judge invalid for the target measurement domain.
- **Anchors:**
  - `docs/Phase28_ContextWindowResearch/PROBLEMS_AND_IMPROVEMENTS.md`
  - `docs/Phase46_large-context-window-research-reccommendations-tooling/RESEARCH.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #7 — Explicit Refactoring Mandate Over Organic Growth

- **ID:** `ba88ba479a97`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Explicit Refactoring Mandate Over Organic Growth
- **Content:** The `useWatchSystem` hook was not created to solve a new problem but was extracted from existing `App.tsx` state as a deliberate cleanup task (S5.1-S5.3). This reveals an architectural decision to enforce separation of concerns through planned refactoring rather than allowing dashboard logic to accumulate in top-level components. The implementation plan treats hook extraction as a scheduled maintenance activity with specific state/callback migration targets.
- **Anchors:**
  - `docs/Phase23_Cleanup-refactor/IMPLEMENTATION_PLAN.md`
  - `src/prep/dashboard/src/hooks/useWatchSystem.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #8 — MVP Demonstration Over Production Readiness

- **ID:** `41040a2c0951`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.95
- **Title:** MVP Demonstration Over Production Readiness
- **Content:** The subsystem was explicitly designed as a working prototype for GraphRAG trace index inspection and MVP demonstrations, not as a production-grade dashboard. This explains why each viz module independently prints to stdout rather than composing into a unified layout—the priority was demonstrable functionality over architectural polish. The 'partial' component status and 'technical-debt' tag confirm this was a conscious scope limitation.
- **Anchors:**
  - `docs/Phase18_DataVisualization/README.md`
  - `src/prep/viz/health.py`
  - `src/prep/viz/overview.py`
  - `src/prep/viz/trace.py`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #9 — XDG Compliance as Security Boundary Against Path Leakage

- **ID:** `75ea1c969dad`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.95
- **Title:** XDG Compliance as Security Boundary Against Path Leakage
- **Content:** The migration from legacy ./codrag_data/ to XDG-compliant directories was driven by a security concern: CWD-relative storage leaks project paths into shared environments and creates config drift when users run the tool from different directories. The TARGET_DESIGN document explicitly frames XDG state directories as a guard against 'security foot-guns like path leakage,' making directory resolution a policy enforcement point rather than mere convenience.
- **Anchors:**
  - `docs/Phase113_xdg_state/01_TARGET_DESIGN.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #10 — Route parser extraction enables settings panel testing without browser dependenc

- **ID:** `a74a855c589e`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Route parser extraction enables settings panel testing without browser dependency
- **Content:** The explicit extraction of URL parameter logic into `routeParser.ts` with dedicated Vitest tests represents a deliberate architectural decision to make routing logic testable without Playwright overhead. This separation was planned as 'Task 5' in the settings panel redesign, indicating it was a recognized gap rather than incidental refactoring. The design rationale is that URL parsing bugs are frequent enough and cheap enough to fix that they warrant fast unit tests, while E2E tests should focus on integration concerns that actually require a browser.
- **Anchors:**
  - `docs/superpowers/plans/2026-04-20-settings-panel-redesign.md`
  - `src/prep/dashboard/src/components/settings/v2/__tests__/routeParser.test.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #11 — Dual-Domain State Orchestration as Deliberate Architectural Boundary

- **ID:** `24afde5108b8`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Dual-Domain State Orchestration as Deliberate Architectural Boundary
- **Content:** The subsystem deliberately splits state management into two hooks (useArchitectureSystem.ts and useGoalpostsSystem.ts) rather than a unified store, reflecting a product decision to keep architecture visualization and project intent workflows as separable concerns. This separation allows independent evolution of collaborative annotation features versus AI-assisted approval pipelines, even though both share the same dashboard surface. The planning documents show these were delivered in distinct phases (71a and 71b), confirming this was a phased rollout strategy rather than organic code growth.
- **Anchors:**
  - `src/prep/dashboard/src/hooks/useArchitectureSystem.ts`
  - `src/prep/dashboard/src/hooks/useGoalpostsSystem.ts`
  - `docs/superpowers/plans/2026-04-04-phase71a-architecture-diagram.md`
  - `docs/superpowers/plans/2026-04-04-phase71b-governance-overlays.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #12 — Founder-as-Canonical-Narrator

- **ID:** `e7bccb7b6b17`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Founder-as-Canonical-Narrator
- **Content:** The subsystem deliberately centralizes 'founder narrative' as the single source of truth for all marketing copy, rather than delegating to external agencies or rotating writers. This reflects a constraint that the product's trust architecture (local-first, perpetual license) must be explained by someone with technical credibility, not polished by generic SaaS marketing. The copy deck serves as the founder's voice amplifier across channels.
- **Anchors:**
  - `docs/Phase12_Marketing-Documentation-Website/COPY_DECK.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #13 — Zero-Dependency Isolation for Documentation Portability

- **ID:** `f15c42fbb7b2`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Zero-Dependency Isolation for Documentation Portability
- **Content:** The complete absence of internal and external dependencies suggests a deliberate isolation strategy: this demo system must function reliably regardless of the rest of the codebase's evolution. This makes the demos maximally portable and failure-resistant, ensuring marketing materials never break due to unrelated system changes. However, this also means the demos cannot dynamically reflect actual system state—they are permanently staged performances rather than live integrations.
- **Anchors:**
  - `websites/apps/docs/src/demo-data.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #14 — Planned Component API Evolution: Variant + RebuildPercent as Breaking Change

- **ID:** `6e7b17f49bb3`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Planned Component API Evolution: Variant + RebuildPercent as Breaking Change
- **Content:** The rebuild progress plan explicitly calls for adding `variant` and `rebuildPercent` props to StageProgressBar with a 'stacked-halves render branch with error sub-state.' This is a significant API expansion for a component already in the fixture layer, suggesting the original design did not anticipate incremental rebuild visualization. The fixture module's 'partial' status likely reflects this mid-migration state—stories exist for the old API surface while the new one is being stabilized.
- **Anchors:**
  - `docs/superpowers/plans/2026-04-17-rebuild-progress-bar.md`
  - `packages/ui/src/stories/trace/StageProgressBar.stories.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #15 — Pro-Tier Feature Gating via Trace Index as Revenue Model Enforcement

- **ID:** `b42e56ce8af0`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Pro-Tier Feature Gating via Trace Index as Revenue Model Enforcement
- **Content:** The explicit mention of 'deliberate Pro-tier feature gating (Trace Index)' reveals that trace visualization isn't technically constrained but commercially constrained—a business model decision embedded in architecture. This creates a hard boundary in the user experience where graph-based code tracing becomes a paid upgrade trigger, not a progressive disclosure pattern. The tight coupling to the Prep daemon API enables this gating server-side, preventing local workarounds that might exist with purely client-side implementations.
- **Anchors:**
  - `packages/vscode/CHANGELOG.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #16 — EV Certificate as Reputation Shortcut, Not Just Security

- **ID:** `1f79f966f7af`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.90
- **Title:** EV Certificate as Reputation Shortcut, Not Just Security
- **Content:** The elaborate EV code signing setup via SSL.com eSigner or Azure Key Vault exists primarily to solve the Windows SmartScreen 'unknown publisher' warning problem, not merely to prove binary integrity. The documentation explicitly notes that standard code signing requires 'building reputation over time' while EV certificates grant 'immediate SmartScreen reputation'—revealing that the cryptographic ceremony is a market-trust hack, not just a security control. This explains why Azure Key Vault integration is acceptable despite cloud HSM complexity: the alternative is user-facing friction that kills adoption.
- **Anchors:**
  - `docs/Phase11_Deployment/WINDOWS_DISTRIBUTION.md`
  - `docs/Phase11_Deployment/guides/04-code-signing.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #17 — Semantic color coding as activity type ontology

- **ID:** `3f69d2612541`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Semantic color coding as activity type ontology
- **Content:** The color scheme embeds a tripartite ontology of developer activity: cyan for embeddings-only, yellow for trace-only, green for mixed. This is not aesthetic preference but a domain model decision—activity types are mutually exclusive at the color level but composable in reality (mixed = both). The choice to represent 'both' as a distinct third color rather than blended colors suggests a product need to quickly identify 'healthy' mixed-activity days versus single-mode activity.
- **Anchors:**
  - `docs/Phase18_DataVisualization/README.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #18 — Prompt Templates as Workflow Enforcement Layer

- **ID:** `adc852d6abe8`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Prompt Templates as Workflow Enforcement Layer
- **Content:** The researcher agent's prompt templates (topic selection → deep research → plan formulation) serve as a lightweight workflow orchestration mechanism that substitutes for heavier state machines or explicit control flow in code. This is a deliberate epistemic choice: LLM prompts enforce ordering constraints through natural language rather than programmatic constructs, making the workflow legible to agent builders who think in terms of prompt engineering. The prompts.py file is the critical enforcement point for this sequential thinking inheritance.
- **Anchors:**
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/phase2-researcher-engine-plan.md`
  - `src/prep/agents/researcher/prompts.py`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #19 — Subsystem delegation pattern hides implementation volatility

- **ID:** `55dadb5705ae`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Subsystem delegation pattern hides implementation volatility
- **Content:** The data flow explicitly shows this surface delegates to three distinct subsystems (Goalposts-Advisor, goalposts-dashboard, goalposts-ui) for actual data and state management, suggesting this module's primary value is stability of import contract rather than stability of implementation. Consumers are shielded from subsystem reorganization as long as the barrel file's export surface remains constant.
- **Anchors:**
  - `packages/ui/src/components/goalposts/index.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #20 — Hook Thin-Wrapper Pattern for Test Strategy

- **ID:** `18ea475c26c1`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Hook Thin-Wrapper Pattern for Test Strategy
- **Content:** The planned `useDebouncedAutoSave` hook follows a deliberate thin-wrapper pattern where complex logic resides in tested utilities (`createDebouncedSaver`) while the React hook merely wires them to component lifecycle. This reveals a testing philosophy that avoids hook testing overhead by trusting `tsc` for wiring validation and unit tests for logic, optimizing for maintainability over coverage metrics.
- **Anchors:**
  - `docs/superpowers/plans/2026-04-20-llm-config-autosave-redesign.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #21 — State Consolidation from Scattered Hooks as Technical Debt Response

- **ID:** `d08c2ebc6790`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.90
- **Title:** State Consolidation from Scattered Hooks as Technical Debt Response
- **Content:** The Phase23 implementation plan explicitly lists eleven state variables to be moved into useTraceSystem, indicating this hook was extracted from a prior architecture where trace-related state was fragmented across multiple hooks or components. The consolidation addresses maintenance burden and state synchronization bugs, but the 'partial' status suggests the migration remains incomplete—some consumers may still hold local state that should belong to the orchestrator.
- **Anchors:**
  - `docs/Phase23_Cleanup-refactor/IMPLEMENTATION_PLAN.md`
  - `src/prep/dashboard/src/hooks/useTraceSystem.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #22 — Explicit ecosystem positioning against 'AI-native IDE' category

- **ID:** `21b1b5ae6731`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Explicit ecosystem positioning against 'AI-native IDE' category
- **Content:** The 'Context MVC' framing is a category-creation maneuver: Prep avoids competing as yet another 'AI-native IDE' (Cursor, Windsurf, etc.) and instead claims the 'context infrastructure' layer that all such tools would ideally share. The member files reveal this is aspirational—the 'partial' component status and empty dependency lists suggest the architecture is declared before implementation. The strategy bets that AI tools will commoditize but context quality will differentiate.
- **Anchors:**
  - `docs/Phase19_Alt-Dev-Workflows/SUMMARY.md`
  - `docs/Phase19_Alt-Dev-Workflows/UNIFIED_STRATEGY.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #23 — Self-Referential Documentation as Compliance Artifact

- **ID:** `4f81cdc8e8eb`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Self-Referential Documentation as Compliance Artifact
- **Content:** The 'self-referential-documentation' tag and SECURITY_AUDIT.md file indicate the system documents its own audit process, creating recursively verifiable compliance evidence. This serves dual purposes: operational (ensuring audit coverage of the audit system itself) and legal (demonstrating due diligence to regulators). The documentation is itself a member of the audited file set, making the subsystem's transparency a first-class architectural concern rather than afterthought.
- **Anchors:**
  - `docs/Phase06_Team_And_Enterprise/SECURITY_AUDIT.md`
  - `docs/Phase06_Team_And_Enterprise/TEAM_ENTERPRISE_CODE_AUDIT.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #24 — Zero-dependency SVG rendering for dashboard performance

- **ID:** `3db181c7ee88`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Zero-dependency SVG rendering for dashboard performance
- **Content:** The subsystem deliberately avoids external charting libraries to minimize bundle size and render latency in performance-critical dashboard contexts. Inline SVG with manual path computation trades developer ergonomics for guaranteed render performance and eliminates version compatibility risks with charting dependencies.
- **Anchors:**
  - `packages/ui/src/components/goalposts/BurndownChart.tsx`
  - `packages/ui/src/components/goalposts/VelocityBar.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #25 — Snake_Case/CamelCase Boundary as Acknowledged Friction Point

- **ID:** `739832f79a59`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Snake_Case/CamelCase Boundary as Acknowledged Friction Point
- **Content:** The data flow explicitly notes 'snake_case/camelCase boundary friction' between backend and frontend, indicating this is a known architectural debt rather than an oversight. The architecture.ts types serve as a deliberate transformation layer to absorb this impedance mismatch, suggesting a pragmatic choice to avoid full backend renaming for frontend ergonomics.
- **Anchors:**
  - `packages/ui/src/types/architecture.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #26 — Pipeline Regeneration Hooks as Implicit State Machine Finalization

- **ID:** `c9b751146ddd`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Pipeline Regeneration Hooks as Implicit State Machine Finalization
- **Content:** The integration with pipeline regeneration hooks suggests the subsystem doesn't merely trigger actions but participates in a larger stage-transition protocol—concept initialization and finalization are lifecycle gates that the dashboard must observe but doesn't control. This creates a hidden coupling where the hook-based integration is the contract surface, not direct orchestrator API calls.
- **Anchors:**
  - `src/prep/dashboard/src/hooks/useConceptSystem.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #27 — Path Alias '@' as Isolation Mechanism

- **ID:** `e0cfa18b3da6`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Path Alias '@' as Isolation Mechanism
- **Content:** The '@' path alias resolving to local src enforces that webview UI code remains self-contained and cannot accidentally import from the extension host's Node.js runtime environment. This alias acts as a compile-time barrier preventing cross-contamination between the webview's browser sandbox and the extension's privileged context.
- **Anchors:**
  - `packages/vscode/webview-ui/vite.config.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #28 — Epistemic Limitations as Differentiator

- **ID:** `59eae2f27f1f`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Epistemic Limitations as Differentiator
- **Content:** The philosophical content on 'knowing that vs knowing how' serves a dual purpose: genuine intellectual contribution and sophisticated content marketing that positions Prep as a tool-maker that understands AI's actual limitations rather than overhyping capabilities. This creates trust-based developer relations by demonstrating epistemic humility.
- **Anchors:**
  - `docs/Phase99_Content/blogs/21_knowing_that_vs_knowing_how.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #29 — Wave-Based Parallelism Constrained by Stage Group Boundaries

- **ID:** `4f9809222c88`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Wave-Based Parallelism Constrained by Stage Group Boundaries
- **Content:** Parallel dispatch is intentionally constrained to occur within stage groups (Sync, Enrich, Finalize) rather than across the entire pipeline because cross-group dependencies carry implicit state contracts that are not yet formally verified. The wave mechanism inside Finalize specifically staggers parallel execution to manage resource contention with external LLM APIs—unbounded parallelism was rejected after telemetry showed rate-limit cascades that increased total latency despite higher concurrency.
- **Anchors:**
  - `docs/Phase96-fix-pipeline/UI+tweaks/PLAN.md`
  - `docs/Phase119_ConcurrencyStability/04_Swarm_Audit.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #30 — Messaging Guidelines as Constraint System

- **ID:** `c36e2ff8f70f`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Messaging Guidelines as Constraint System
- **Content:** The data flow describes messaging guidelines that 'constrain public communications,' framing marketing copy as a governed output rather than creative freedom. This architectural pattern—rules before expression—reflects an enterprise-readiness mindset where brand consistency is enforced structurally. The COMPETITOR_COMPARISON_GRID likely functions as a decision boundary: claims not in the grid are not in the messaging.
- **Anchors:**
  - `docs/Phase12_Marketing-Documentation-Website/COMPETITOR_COMPARISON_GRID.md`
  - `docs/Phase10_Business_And_Competitive_Research/README.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #31 — Search as location mutation rather than client-side state

- **ID:** `44d7bf44acf6`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Search as location mutation rather than client-side state
- **Content:** The search implementation deliberately uses window.location mutation instead of Next.js router navigation or client-side search state, suggesting a design choice to offload search entirely to a dedicated search page rather than building search into the shell itself. This keeps the ClientLayout lightweight and avoids importing search logic or state management into every page, at the cost of a full page navigation.
- **Anchors:**
  - `websites/apps/docs/src/app/ClientLayout.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #32 — Temporal Window Display as Trust-Building Mechanism

- **ID:** `81665680d1fb`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Temporal Window Display as Trust-Building Mechanism
- **Content:** The time-window formatting serves not merely informational but trust-restorative purposes—operators can verify that 'exhausted' states reflect genuine recent consumption rather than stale or cached states. This addresses a specific failure mode in resource governance UIs where users disbelieve warnings and attempt to force operations. The temporal anchoring makes the system's memory visible and auditable.
- **Anchors:**
  - `packages/ui/src/components/viz/TokenBudgetPanel.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #33 — Research-First Content Validation Gate Before Distribution

- **ID:** `5402c8a18bd0`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Research-First Content Validation Gate Before Distribution
- **Content:** The data flow terminates in 'content validation against published research before distribution,' establishing an epistemic quality gate unusual for engineering documentation. The blog post '24_more_context_not_more_knowledge.md' functions as both public communication and validated research artifact, suggesting SourcePrep treats prompt engineering claims as falsifiable hypotheses requiring literature review. This implies a brand decision to position the extension as evidence-based rather than hype-driven in a crowded AI tooling market.
- **Anchors:**
  - `docs/Phase99_Content/blogs/24_more_context_not_more_knowledge.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #34 — Tiered Analysis Pipeline as Trust-Building Mechanism

- **ID:** `eeeae6ee2b90`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Tiered Analysis Pipeline as Trust-Building Mechanism
- **Content:** AutoAudit's three-tier pipeline (graph queries → LLM synthesis → continuous monitoring) exists not merely for technical decomposition but to create verifiable audit trails. Each tier produces inspectable artifacts, allowing human reviewers to validate lower-tier structural findings independently before trusting higher-tier synthetic conclusions. This reflects a meta-cognitive commitment to epistemic transparency in automated analysis systems.
- **Anchors:**
  - `docs/Phase43_AutoAudit/README.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #35 — D3.js + React Flow Hybrid as Tiered Visualization Strategy

- **ID:** `92ba6300f4bb`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.75
- **Title:** D3.js + React Flow Hybrid as Tiered Visualization Strategy
- **Content:** The choice to combine D3.js for the Roadmap with React Flow for node rendering represents a deliberate tiered visualization strategy: D3 handles complex timeline and fork semantics while React Flow provides interactive node manipulation. This split avoids forcing either library into uncomfortable patterns rather than selecting a single 'winner'.
- **Anchors:**
  - `docs/Phase59_Roadmap/03_Refined_Architecture.md`
  - `docs/superpowers/plans/2026-04-04-phase71a-architecture-diagram.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #36 — Organic growth as implicit technical debt strategy

- **ID:** `bc57944be2ed`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Organic growth as implicit technical debt strategy
- **Content:** The 'organic growth patterns with implicit c[oupling]' fragment reveals a system that expanded without refactoring boundaries, likely because each new component (roadmap, sprint, burndown, GitHub status) was added incrementally under delivery pressure. The lack of architectural layering separation suggests deferred decisions about where presentational vs. container responsibilities should live, accumulating structural risk.
- **Anchors:**
  - `packages/ui/src/components/goalposts/index.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #37 — LLM Configuration as Critical Path Requiring Debounced Durability

- **ID:** `d49ffa1d4323`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.75
- **Title:** LLM Configuration as Critical Path Requiring Debounced Durability
- **Content:** The dedicated spec document for LLM config auto-save redesign (dated 2026-04-20) signals that this particular async pattern was problematic enough to warrant separate design attention. The debouncing requirement suggests LLM configuration changes are frequent during active editing but must reliably persist—implying a tension between user experience (no save buttons) and operational risk (misconfigured LLM contexts could propagate expensive or incorrect pipeline runs). The 'model-context-protocol' tag hints this connects to emerging MCP standards.
- **Anchors:**
  - `docs/superpowers/specs/2026-04-20-llm-config-autosave-redesign.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #38 — Append-only audit logging as compliance primitive, not debugging convenience

- **ID:** `30b752ab2b86`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Append-only audit logging as compliance primitive, not debugging convenience
- **Content:** The audit_log.py implementation treats immutability as a legal requirement rather than an operational preference, designed to satisfy enterprise compliance frameworks that demand tamper-evident records. This design choice prioritizes regulatory defensibility over storage efficiency—accepting the cost of unbounded growth in audit records to avoid any appearance of record manipulation. The subsystem's scope_store.py and antibodies.py components likely enforce this by restricting write paths and detecting integrity violations.
- **Anchors:**
  - `src/prep/core/audit_log.py`
  - `src/prep/core/scope_store.py`
  - `src/prep/core/antibodies.py`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #39 — Client-Side License Validation Over Server Authority

- **ID:** `4c2ffa119251`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Client-Side License Validation Over Server Authority
- **Content:** The data flow specifies license validation occurring client-side after distribution, suggesting a deliberate trade-off between piracy risk and offline functionality. This implies the product prioritizes user experience in disconnected environments over strict license enforcement, or alternatively that verification is staged with periodic server re-checks.
- **Anchors:**
  - `docs/Phase11_Deployment/README.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #40 — Persistent Dev Server Tasks as Intentional Cache Escape

- **ID:** `c00c67caaba2`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Persistent Dev Server Tasks as Intentional Cache Escape
- **Content:** The explicit 'persistent without caching' configuration for dev server tasks represents a deliberate trade-off: local development velocity requires skipping cache validation for watch-mode processes, but this same escape hatch is what makes dev-only code leakage possible. The security migration's Wave 3 (dead code elimination) exists specifically because this escape cannot be closed without destroying developer experience.
- **Anchors:**
  - `turbo.json`
  - `docs/Phase101_Trim-for-MVP/DEV_ONLY_ARCHITECTURE.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #41 — Empty dependency arrays signal intentional isolation from module system coupling

- **ID:** `46dd60f9d7bd`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.65
- **Title:** Empty dependency arrays signal intentional isolation from module system coupling
- **Content:** The absence of both internal and external dependencies in the module metadata, despite clear runtime dependencies on Tauri APIs and React, indicates a design decision to treat this bootstrap layer as an integration point that dynamically resolves its dependencies rather than statically importing them. This reduces build-time coupling at the cost of losing compile-time verification for critical path dependencies.
- **Anchors:**
  - `src/prep/dashboard/src/main.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #42 — Zero Dependencies as Isolation Strategy

- **ID:** `3408fa274dad`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.65
- **Title:** Zero Dependencies as Isolation Strategy
- **Content:** The complete absence of internal and external dependencies for a loading component is architecturally significant—it suggests either a deliberate lightweighting to prevent cascade failures during async operations, or a constraint imposed by the build system to avoid circular dependencies in the UI package. This isolation may also reflect a 'no surprises' philosophy for core feedback patterns where reliability trumps feature richness.
- **Anchors:**
  - `packages/ui/src/components/patterns/LoadingState.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #43 — Partial Component Status Suggests Deliberate Scope Reduction for Critical Infras

- **ID:** `84d4ed2006c1`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Partial Component Status Suggests Deliberate Scope Reduction for Critical Infrastructure
- **Content:** The 'partial' component status indicates this subsystem was likely scoped down to its essential SSE bridging function rather than expanded into a general event system. This aligns with the planning document's pattern of explicitly marking existing components for reuse-as-is, suggesting architectural discipline to avoid over-engineering infrastructure that serves a specific dashboard need.
- **Anchors:**
  - `src/prep/core/events.py`
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #44 — Configurable Week Ranges as Accommodation for Irregular Review Cycles

- **ID:** `8393cd513474`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Configurable Week Ranges as Accommodation for Irregular Review Cycles
- **Content:** The configurable week ranges feature implies recognition that SourcePrep users operate on non-standard temporal rhythms—sprint cycles, release trains, or incident post-mortem windows that don't align with calendar months. Fixed month/quarter views would force mental translation between organizational time and visualization time. Making week ranges configurable (likely including partial weeks) allows direct mapping to actual work rhythms, suggesting the product serves teams with varied operational cadences rather than imposing a single analytical frame.
- **Anchors:**
  - `packages/ui/src/components/viz/ActivityHeatmap.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #45 — Barrel file pattern as intentional UI encapsulation for multi-package governance

- **ID:** `48a93c72af50`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Barrel file pattern as intentional UI encapsulation for multi-package governance
- **Content:** The enterprise/index.ts barrel file, alongside AdminSection.tsx primitive and explicit 'ui-encapsulation' tag, indicates a deliberate boundary design: enterprise components are exposed through controlled aggregation points rather than direct imports. This supports a versioning and deprecation strategy for enterprise UI contracts, where the governance layer's visual surface can evolve without breaking internal consumers. The pattern is especially important given the 'partial' status and ongoing tier definition changes.
- **Anchors:**
  - `packages/ui/src/components/enterprise/index.ts`
  - `packages/ui/src/components/primitives/AdminSection.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #46 — Changelog as Partial Status Indicator for Rapid Iteration

- **ID:** `6657415a65a9`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Changelog as Partial Status Indicator for Rapid Iteration
- **Content:** The component_status is 'partial' despite having a CHANGELOG.md, suggesting active development with incomplete feature coverage rather than maintenance mode. The presence of a changelog in a 7-file module with partial status implies either recent extraction from a larger package or rapid iteration with documented breaking changes. This creates tension: users expect stability from versioned extensions, but the 'partial' status and roadmap documents indicate the VS Code integration is still evolving toward its declared vision.
- **Anchors:**
  - `packages/vscode/CHANGELOG.md`
  - `docs/ROADMAP.md`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #47 — Agent-to-External-Integration Boundary as Security-Sensitive Configuration Surfa

- **ID:** `e730a4121748`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Agent-to-External-Integration Boundary as Security-Sensitive Configuration Surface
- **Content:** The module's positioning as 'primary UI entry point for agent-to-Paperclip integration settings' places it at a trust boundary where agent-generated findings cross organizational control into an external system. The constrained three-field surface likely reflects security review outcomes: limiting exfiltration control points reduces attack surface, while the project ID field serves as an explicit routing gate preventing accidental or malicious cross-tenant data pushes. The significance threshold further acts as a content filter, ensuring only appropriately vetted findings reach external infrastructure.
- **Anchors:**
  - `packages/ui/src/components/agents/PushSettings.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #48 — Signal Word Stripping as Query Degradation Risk

- **ID:** `1c097e24b3a4`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Signal Word Stripping as Query Degradation Risk
- **Content:** The rewrite_query function removes words that triggered intent classification, which may discard semantically meaningful content. This design assumes signal words are purely pragmatic markers without substantive content, a linguistic simplification that could degrade downstream semantic search quality for certain query types.
- **Anchors:**
  - `src/prep/core/intent.py`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #49 — Zero internal dependencies indicate cross-cutting infrastructure treated as exte

- **ID:** `7a3bd851c4ba`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.60
- **Title:** Zero internal dependencies indicate cross-cutting infrastructure treated as external
- **Content:** The empty internal_dependencies list for a subsystem spanning packages/ui and two websites/apps directories is architecturally anomalous. Either the shared registry and template components are treated as external utilities (despite being in the same monorepo), or dependency tracking is incomplete. If intentional, this suggests a deliberate decoupling strategy—treating the MCP integration layer as a consumer of platform primitives rather than an integrated subsystem, enabling potential extraction or white-labeling.
- **Anchors:**
  - `packages/ui/src/components/dashboard/UsageGuidePanel.tsx`
  - `websites/apps/docs/src/app/mcp/ides/page.tsx`
  - `websites/apps/marketing/src/app/integrations/page.tsx`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---

### Concept #50 — Zero Internal Dependencies Suggests Either Purity or Isolation Risk

- **ID:** `0c4b208f3be5`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.60
- **Title:** Zero Internal Dependencies Suggests Either Purity or Isolation Risk
- **Content:** The empty internal_dependencies array is unusual for a barrel that re-exports multiple components—typically these would depend on sibling files within the layout directory. This could indicate: (a) all implementation files are co-located and considered 'the same' module by the analysis tool, (b) the components are thin wrappers around external libraries, or (c) the subsystem is dangerously isolated from shared utilities (formatters, error boundaries, theming). The ambiguity itself reveals a tooling or modeling decision about what constitutes 'internal' versus 'external' in this codebase.
- **Anchors:**
  - `packages/ui/src/components/layout/index.ts`

**Your tier (pick one):**
- [ ] T1 — observed pattern; no enforcement
- [ ] T2 — documented + ≥1 enforcing mechanism (test/lint/contract)
- [ ] T3 — codified in CI/types; violations fail build

**Truth label (pick one):**
- [ ] TRUE — concept is accurate
- [ ] PARTIAL — partially accurate or mis-stated scope
- [ ] FALSE — wrong or generic boilerplate

**Notes:** _____________________________________________________

---



---

## What to do after filling

Save the file. Run:

```bash
.venv/bin/python tools/score_calibration_worksheet.py \
    --worksheet docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md
```

The scorer reports:
- Tier distribution (your labels)
- Ordinal ECE (against current LLM confidence — should be high)
- Per-category breakdown
- A flagged-for-review list for ambiguous entries

Once T3 runs, we re-score the same worksheet against T3's tier outputs
and compare ECE pre/post.

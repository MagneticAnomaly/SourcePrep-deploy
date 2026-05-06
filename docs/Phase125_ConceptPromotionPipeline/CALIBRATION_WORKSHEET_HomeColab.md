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
- `constraint`: 6
- `decision`: 5
- `domain`: 5
- `process`: 5
- `product`: 4
- `technical`: 4
- `brand`: 4
- `epistemic`: 4
- `pattern`: 4
- `security`: 3

---

## Concepts to label

### Concept #1 — Strangler Fig Pattern as Risk Mitigation for 1,386-Line Singleton

- **ID:** `0c6b8622231e`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Strangler Fig Pattern as Risk Mitigation for 1,386-Line Singleton
- **Content:** The decomposition explicitly adopts the Strangler Fig pattern not merely as an architectural preference, but as a risk-mitigation strategy for a monolithic class that has become too large to safely refactor in a single operation. The phased approach with feature flags allows the team to validate each extracted service in production before committing to full migration, preserving the ability to instantly revert to legacy behavior if a new service fails.
- **Anchors:**
  - `HomeColabApp/Docs/Architectural-Audit/High-Risk-Migrations/02_FIRESTORE_MANAGER_DECOMPOSITION.md`

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

### Concept #2 — Mock-to-Firebase Swap Path as Explicit Migration Strategy

- **ID:** `997ae6cf3cea`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Mock-to-Firebase Swap Path as Explicit Migration Strategy
- **Content:** The subsystem is architected around a deliberate two-phase migration: Phase 1 uses a pluggable MockDataSource with artificial latency to simulate backend behavior, while Phase 2 will swap in FirebaseDataSource once the SDK is integrated. This is not merely testing convenience but a documented business risk-mitigation strategy that allows UI/UX development to proceed in parallel with backend contract negotiation. The explicit 'swap path' in MASTER_TODO.md reveals this was a planned architectural decision, not emergent technical debt.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/MASTER_TODO.md`
  - `HomeColabProWebsite/website/lib/mock-data-source.ts`
  - `HomeColabProWebsite/website/lib/firebase-data-source.ts`

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

### Concept #3 — Deployment Target Lock-In as Business Constraint

- **ID:** `82d533ecc033`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Deployment Target Lock-In as Business Constraint
- **Content:** The bridge exists because HomeColab maintains iOS 15+ as its minimum deployment target, a business decision that prevents direct adoption of iOS 17 MapKit APIs. The subsystem is explicitly designed with a 'complete migration path' documented for when iOS 17 eventually becomes the minimum, treating the bridge as temporary technical debt rather than permanent architecture.
- **Anchors:**
  - `HomeColabApp/Docs/Developer/IOS_15_COMPATIBILITY.md`

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

### Concept #4 — Single Couple/Shared Space as Fundamental Architectural Bottleneck

- **ID:** `e4607be10345`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Single Couple/Shared Space as Fundamental Architectural Bottleneck
- **Content:** The consumer app's core constraint—modeling exactly one couple sharing one space—permeates the data model, Firestore schema, and ViewModel assumptions so deeply that multi-tenancy cannot be grafted on. This is identified as the root cause requiring dedicated AgentFirestoreManager rather than extending existing managers.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase03_ArchitectureStrategy/01_CONSUMER_APP_ARCHITECTURE.md`

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

### Concept #5 — MVP Heuristic Over ML to Ship Faster

- **ID:** `a7b17d7f14b1`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.95
- **Title:** MVP Heuristic Over ML to Ship Faster
- **Content:** The engine deliberately uses keyword-based classification rather than machine learning to enable immediate shipping. The design document explicitly states 'MVP heuristic approach' with 'future ML enhancement' as a deferred upgrade, prioritizing speed-to-market over classification accuracy. This creates a known accuracy ceiling that the team has consciously accepted.
- **Anchors:**
  - `HomeColabApp/Docs/Design/PROS_CONS_CATEGORIZATION.md`

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

### Concept #6 — Verified Listing as Trust Anchor for Agent-Curated Data

- **ID:** `56eaf0a1cd80`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Verified Listing as Trust Anchor for Agent-Curated Data
- **Content:** The VerifiedListing schema was explicitly designed with provenance tracking (`source`, `importedAt`, `verifiedBy`, `verifiedAt`) and audit trails (`editHistory`) because the business model treats agent verification as a trust differentiator. This is not merely data normalization—it is a reputational mechanism where the 'verified' status carries contractual weight between agents and the platform. The required fields (MLS number, status, price, address, city, state, zip) form the minimum viable legal description of a property listing, while optional fields allow flexibility without compromising core integrity.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/MASTER_TODO.md`
  - `HomeColabProWebsite/website/lib/csv-parser.ts`

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

### Concept #7 — Five-Phase Rollout as Risk Mitigation for Revenue-Critical Path

- **ID:** `8e07873267b6`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Five-Phase Rollout as Risk Mitigation for Revenue-Critical Path
- **Content:** The phased rollout (scaffolding → integration → testing → analytics → optimization) exists because ad monetization is a revenue-critical path that must not destabilize the core property management UX. By keeping all ad components as stubs in Phase 1, the team can validate UI layout and frequency capping logic without risking premature SDK initialization that could trigger policy violations or revenue leakage. The document explicitly warns against 'connecting to live ad networks before analytics and consent plumbing are ready.'
- **Anchors:**
  - `HomeColabApp/Docs/2.0/Plans/Pre-Launch/Phase03_ads/IMPLEMENTATION_PLAN.md`

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

### Concept #8 — Unvalidated Strategic Documentation Without Technical Feasibility

- **ID:** `c2cd197628f2`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Unvalidated Strategic Documentation Without Technical Feasibility
- **Content:** The vision document exists in a deliberate epistemic gap: it articulates intended data flows (consumer intent → structured data → Pro workflow orchestration) but explicitly lacks any technical feasibility study or integration roadmap. This reveals a process decision to separate strategic visioning from technical validation, creating risk that the B2B2C network effects may be architecturally infeasible or prohibitively expensive to implement.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase01_Consolidate/03_BUSINESS_APP_VISION.md`

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

### Concept #9 — Portfolio demonstration purpose over production readiness

- **ID:** `4cfd8745b2ed`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.95
- **Title:** Portfolio demonstration purpose over production readiness
- **Content:** The subsystem's hardcoded point sizes and violation of iOS Dynamic Type requirements suggest it was built primarily as a portfolio showcase rather than for production use. The file path containing 'Portfolio/code-samples' confirms this intent, indicating the design system prioritizes visual polish and API elegance over accessibility compliance and real-world adaptability.
- **Anchors:**
  - `HomeColabApp/Docs/Portfolio/code-samples/DesignSystem/Typography.swift`

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

### Concept #10 — High signal-to-noise communication philosophy

- **ID:** `740b849024d7`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.95
- **Title:** High signal-to-noise communication philosophy
- **Content:** The system intentionally rejects open-ended chat in favor of structured, tiered notification categories (favorite, send-to-agent, request-action) with template formats. This design choice prioritizes actionable, categorized communication over conversational flexibility, reflecting a belief that unstructured messaging creates noise that degrades professional collaboration.
- **Anchors:**
  - `HomeColabApp/Docs/Pro_App_Version_Planning/Collaboration_Workflows.md`

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

### Concept #11 — Sidecar Pattern as Firebase Coexistence Strategy

- **ID:** `2fe6ccd619e9`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Sidecar Pattern as Firebase Coexistence Strategy
- **Content:** The subsystem deliberately avoids replacing incumbent Firebase infrastructure, instead adopting a sidecar architecture to add vector/AI capabilities incrementally. This reflects a business constraint: the existing platform has working auth, data, and hosting in Firebase, and migration risk outweighs the benefit of a greenfield rewrite. The sidecar model allows the team to experiment with Supabase/Pinecone and OpenAI without destabilizing production workloads.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase07_Comparison-Matrix/Backend-research.md`

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

### Concept #12 — 'Our List' Nomenclature as Joint Ownership Framing

- **ID:** `db67b9ceb0a9`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.85
- **Title:** 'Our List' Nomenclature as Joint Ownership Framing
- **Content:** The screen naming 'Our List' rather than 'Saved', 'Favorites', or 'Shortlist' deliberately constructs shared identity around the collaborative artifact. This microcopy choice reflects a brand-level positioning of HomeColab as relationship infrastructure rather than functional real estate tooling, potentially influencing downstream feature prioritization toward conflict resolution and mutual discovery over individual efficiency.
- **Anchors:**
  - `HomeColabApp/Docs/Design/UI_SPECIFICATION_V2.md`

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

### Concept #13 — Partial Component Status Reflects Marketing Site as Secondary Priority

- **ID:** `c41d9d2f9b2b`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Partial Component Status Reflects Marketing Site as Secondary Priority
- **Content:** The 'partial' component status for a consumer-facing marketing subsystem, despite being the 'single source of truth,' indicates the broader HomeColab system prioritizes app functionality over web presence. The marketing site's architectural investment is deliberately constrained, treated as a thin presentation layer rather than a core product surface.
- **Anchors:**
  - `HomeColabProWebsite/website/content/copy.ts`

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

### Concept #14 — One-off visual treatment over configurable system

- **ID:** `a9b2eafafe86`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.85
- **Title:** One-off visual treatment over configurable system
- **Content:** The subsystem deliberately prioritizes immediate delivery of a specific glassmorphism aesthetic over building a reusable theming engine. This reflects a pragmatic trade-off: the team needed premium spatial matrix aesthetics quickly without the engineering overhead of dynamic opacity, blur radius, or color temperature controls. The static 'glass-card' CSS class embodies this 'ship now, systematize later' philosophy.
- **Anchors:**
  - `HomeColabProWebsite/website/components/ui/glass-card.tsx`

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

### Concept #15 — Email-Only MVP as Technical Complexity Arbitrage

- **ID:** `f85735bbbefa`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Email-Only MVP as Technical Complexity Arbitrage
- **Content:** The pivot to an email-only delivery mechanism for v1.0 represents a deliberate trade-off: eliminating web dashboard development reduces technical risk and accelerates time-to-market, but introduces product adoption uncertainty since agents may expect a traditional SaaS interface. This scope contraction is framed as deferring dashboard to v1.1, suggesting the team views email delivery as a temporary bridge, not a permanent architecture.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase02_DeepRealEstateApp-Research/08_GO_NO_GO_DECISION.md`

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

### Concept #16 — Legal Documentation Layer as Marketing Website Component

- **ID:** `56010accf8c4`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Legal Documentation Layer as Marketing Website Component
- **Content:** Placing legal compliance documentation under 'Marketing_Website/legal_for_marketing/' rather than a standalone compliance or legal directory reveals that privacy policy and terms of service are treated as conversion infrastructure rather than operational governance. The README.md in this location suggests these documents are designed for public-facing trust signaling (reducing friction in user acquisition) rather than internal legal reference, explaining why the subsystem's 'compliance attestation' flows toward marketing rather than toward operational audit systems.
- **Anchors:**
  - `HomeColabApp/Docs/Marketing_Website/legal_for_marketing/README.md`

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

### Concept #17 — Natural language controls as bridge between domain vocabulary and spatial parame

- **ID:** `7fd6e7ad7b23`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Natural language controls as bridge between domain vocabulary and spatial parameters
- **Content:** The natural language control layer serves as a translation mechanism between how real estate professionals actually speak ('more square footage', 'better school district') and the underlying quantile grid coordinates. This indirection layer is essential because the spatial positions are algorithmically derived from multi-dimensional data, but users reason in comparative qualitative terms. The design must maintain this bidirectional mapping without exposing the binning mechanics.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase07_Comparison-Matrix/SPATIAL_MATRIX_DESIGN.md`

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

### Concept #18 — Stubbed Component Status Reveals Documentation-First Development Anti-Pattern

- **ID:** `eaac2aedd263`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Stubbed Component Status Reveals Documentation-First Development Anti-Pattern
- **Content:** The component_status being explicitly marked 'stubbed' while the changelog documents claimed feature completion indicates a documentation-first or 'paper architecture' anti-pattern where progress is recorded before implementation. This creates epistemic risk where the organization cannot reliably distinguish between planned, in-progress, and actually functional capabilities. The static nature of the document ('no runtime data flow') means there is no automated verification linking changelog claims to build artifacts, enabling the 'significant implementation gaps' to persist undetected.
- **Anchors:**
  - `HomeColabApp/Docs/Development/CHANGELOG.md`

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

### Concept #19 — Single gateway as import discipline enforcement

- **ID:** `5a09e1e17815`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Single gateway as import discipline enforcement
- **Content:** Centralizing eight disparate marketing subsystems through one entry point creates a chokepoint that enforces import discipline across the organization. This prevents direct deep imports that would fragment the section ecosystem and make global changes prohibitively expensive. The pattern reflects an organizational decision to accept indirection costs in exchange for centralized control over a high-visibility surface area.
- **Anchors:**
  - `HomeColabProWebsite/website/components/sections/index.ts`

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

### Concept #20 — Stubbed status as risk indicator for stakeholder dependency chain

- **ID:** `428478a86b72`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.90
- **Title:** Stubbed status as risk indicator for stakeholder dependency chain
- **Content:** The 'stubbed' component status reveals this subsystem sits at a critical dependency junction: marketing copy depends on product positioning, visual design depends on brand identity, and analytics depends on domain finalization. The stubbed state is not technical debt but a visible project management artifact tracking external blockers.
- **Anchors:**
  - `HomeColabApp/Docs/Marketing_Website/README.md`

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

### Concept #21 — Four-Phase Rollout as Risk Mitigation Strategy

- **ID:** `dae4c91e6e17`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Four-Phase Rollout as Risk Mitigation Strategy
- **Content:** The migration deliberately structures deployment into Development → Staging/Canary → Production → Cleanup phases, with each phase having explicit entry/exit criteria. This reflects a business decision that service decomposition carries coordination risk across a distributed team, and that feature flags alone are insufficient without staged organizational adoption. The TRACE tagging convention (Test, Review, Audit, Confirm, Execute) further institutionalizes paranoia about production changes.
- **Anchors:**
  - `HomeColabApp/Docs/Architecture/SERVICE_LAYER.md`

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

### Concept #22 — Partnership Linking as Hard Gate Creates Explicit Couples-Only Product Positioni

- **ID:** `446a39270eac`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Partnership Linking as Hard Gate Creates Explicit Couples-Only Product Positioning
- **Content:** The router's 'needsPartner' state—distinct from 'needsAuth'—represents a deliberate product decision that HomeColab is exclusively for pairs, not individual users. Unlike apps that allow solo exploration with optional sharing, this system blocks all core functionality until a partnership link is established. This constrains the addressable market but ensures the collaborative voting state machine (the differentiated feature) is always exercised, avoiding feature fragmentation.
- **Anchors:**
  - `HomeColabApp/App/RootView.swift`
  - `HomeColabApp/Docs/Design/VOTING_STATE_MACHINE.md`

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

### Concept #23 — Spatial metaphor as cognitive prosthetic for multi-dimensional trade-offs

- **ID:** `b537bae3666b`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Spatial metaphor as cognitive prosthetic for multi-dimensional trade-offs
- **Content:** The system deliberately replaces traditional filter/sort interfaces with a 3D spatial layout because real estate decisions involve 6-12 competing attributes (price, school quality, commute, square footage, etc.) that collapse poorly into linear rankings. The UMAP reduction and scatter plot create an 'approximate gestalt' where users' visual cortex does the heavy lifting of detecting clusters, outliers, and neighborhood structures that would require dozens of explicit comparison operations. This is a bet that spatial intuition outperforms parametric search for high-consideration purchases where the user's utility function is initially fuzzy and co-discovered through exploration.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase07_Comparison-Matrix/Research_Framework.md`

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

### Concept #24 — Legal Compliance Links in Auth Flow Address Regulatory Risk Before Data Collecti

- **ID:** `bc68c7d71d65`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Legal Compliance Links in Auth Flow Address Regulatory Risk Before Data Collection
- **Content:** The explicit integration of terms and privacy policy links within the authentication entry point—rendered via in-app browser rather than deferred to post-signup—indicates a compliance-first design responding to GDPR/CCPA requirements for informed consent prior to identity establishment. This placement reveals a business constraint that legal exposure must be minimized even at the cost of adding friction to the conversion funnel, suggesting either past regulatory scrutiny or proactive legal counsel influence on product design.
- **Anchors:**
  - `HomeColabApp/Views/Onboarding/OnboardingView.swift`
  - `HomeColabApp/Utilities/SafariView.swift`

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

### Concept #25 — Purely Presentational Design Eliminates State Management Complexity

- **ID:** `64d57f31bc00`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.85
- **Title:** Purely Presentational Design Eliminates State Management Complexity
- **Content:** The explicit 'no dynamic data flow; purely presentational with no state management' architecture reveals a deliberate trade-off: the component sacrifices flexibility (cannot self-trigger data reloads, cannot display loading skeletons) in exchange for zero behavioral variance across all five consuming views. This constraint prevents feature teams from embedding business logic inside the empty state, keeping it a true visual pattern rather than a latent feature controller.
- **Anchors:**
  - `HomeColabApp/Components/EmptyStateView.swift`

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

### Concept #26 — Domain Blocklist as Runtime Contract

- **ID:** `e2dcc92d5cd9`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Domain Blocklist as Runtime Contract
- **Content:** The blocked domain filtering happens at runtime rather than build-time or configuration-time, suggesting legal compliance is treated as a living enforcement boundary that can respond to new threats. This implies the team expects ongoing ToS disputes with listing platforms and needs operational agility without app store resubmission. The runtime guard also enables A/B testing or regional variation of compliance boundaries.
- **Anchors:**
  - `HomeColabApp/Docs/Bugfixes/LINKPRESENTATION_IMAGE_SCRAPING_FIX.md`

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

### Concept #27 — Glass-Morphism as Differentiating Visual Brand Signature

- **ID:** `41afbcbc72fc`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Glass-Morphism as Differentiating Visual Brand Signature
- **Content:** The subsystem's glass-morphism design language is not merely aesthetic preference but a deliberate product positioning choice for a real-estate collaboration app competing in a crowded market. The translucent, layered surfaces visually reinforce the 'shared space' metaphor—partners literally seeing through each other's preferences—while requiring non-trivial performance trade-offs in SwiftUI's rendering pipeline, especially for the animated notification cards and rank badges that must maintain 60fps during Firestore-driven state updates.
- **Anchors:**
  - `HomeColabApp/Components/NotificationCardView.swift`
  - `HomeColabApp/Components/RankBadge.swift`
  - `HomeColabApp/Views/Queue/QueueView.swift`

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

### Concept #28 — Glass material as distinctive brand signature

- **ID:** `c6d09e4da415`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Glass material as distinctive brand signature
- **Content:** The dedicated glass effect documentation section indicates that translucent materials are not merely an implementation detail but a core brand differentiator for HomeColab. The mode-specific implementations suggest the glass appearance required non-trivial design iteration to maintain readability and aesthetic coherence. This elevates a visual effect to architectural significance—changes to the glass system must propagate through this documentation as a formal change control step.
- **Anchors:**
  - `HomeColabApp/Views/StyleGuide/BrandGuidelinesView.swift`

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

### Concept #29 — Single-Device FCM Token Model as Intentional Simplicity Constraint

- **ID:** `0d93a7fae0a4`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Single-Device FCM Token Model as Intentional Simplicity Constraint
- **Content:** The decision to store only a single FCM token per user rather than a multi-device registry reflects an early-stage product constraint prioritizing implementation speed over cross-device notification parity. This simplifies token management and reduces Firestore document complexity, but implicitly defers handling of tablet/secondary phone scenarios to a future iteration.
- **Anchors:**
  - `HomeColabApp/Docs/Features/PUSH_NOTIFICATIONS_STRATEGY.md`

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

### Concept #30 — SEO as early-stage constraint on debranded content

- **ID:** `8319ea4901a7`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.80
- **Title:** SEO as early-stage constraint on debranded content
- **Content:** Despite the debranded placeholder state, SEO is explicitly tagged as a domain concern. This implies the content strategy must be structurally search-optimized even with neutral copy—likely requiring semantic HTML, meta tag scaffolding, and keyword architecture that survives brand insertion without URL or structure changes.
- **Anchors:**
  - `HomeColabApp/Docs/Marketing_Website/Marketing_Copy_and_Plan.md`

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

### Concept #31 — Deterministic Deployment as Risk Mitigation for Production Revenue Flows

- **ID:** `0df0dfddc6df`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Deterministic Deployment as Risk Mitigation for Production Revenue Flows
- **Content:** The dependency lock exists primarily to prevent 'works on my machine' failures in a subsystem that directly supports monetization functionality. Because this is the sole artifact representing the Firebase Functions subsystem, any dependency drift would have no other guardrails—there are no internal dependencies or additional configuration files to catch version mismatches. The lockfile therefore serves as the only reproducibility guarantee for revenue-critical serverless code.
- **Anchors:**
  - `HomeColabApp/functions/package-lock.json`

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

### Concept #32 — URL Parsing Over Structured API Integration

- **ID:** `8eeb8a667787`
- **Category:** `decision`
- **LLM confidence (current, suspect):** 0.80
- **Title:** URL Parsing Over Structured API Integration
- **Content:** The subsystem extracts property metadata by parsing raw URLs and text rather than integrating with listing platform APIs, suggesting a business decision to support arbitrary property sources without vendor partnerships or API key management. This creates a universal ingestion path at the cost of parsing fragility when site structures change. The choice prioritizes user convenience and broad source compatibility over data reliability guarantees.
- **Anchors:**
  - `HomeColabApp/HomeColabShare/ShareViewController.swift`

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

### Concept #33 — Smart Briefing Timezone Handling as Ambiguity Risk

- **ID:** `aeeffa8f883f`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Smart Briefing Timezone Handling as Ambiguity Risk
- **Content:** Smart Briefing timezone handling is flagged as an explicit edge case, revealing that temporal intelligence features face fundamental ambiguity when user location, device timezone, and content timezone may all diverge. This represents a product decision to push timezone complexity to Phase 05 rather than defer indefinitely, acknowledging that 'smart' time-based content delivery requires resolved timezone semantics to avoid incorrect scheduling or embarrassing temporal errors.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase05_IMPLEMENTATION/00_EDGE_CASES_AND_OPPORTUNITIES.md`

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

### Concept #34 — Empirical Validation as Explicit Epistemic Humility

- **ID:** `e6a5eb5e9c0f`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Empirical Validation as Explicit Epistemic Humility
- **Content:** The repeated emphasis that 'all figures require post-launch empirical validation' reveals a meta-design decision to treat the framework as a falsifiable hypothesis structure rather than a rigid target-setting exercise. This is unusual in early-stage planning documents and suggests organizational awareness that real estate tech metrics often diverge from SaaS benchmarks due to transaction-based (not subscription-based) agent behavior. The framework is architected to be updated, not defended—implying a learning-loop culture was intentionally designed into the measurement system.
- **Anchors:**
  - `HomeColabApp/Docs/Pro_App_Version_Planning/Pro_App_Research/Success_Metrics.md`

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

### Concept #35 — Singleton Manager as Centralized Coordination Point

- **ID:** `77be50d12921`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Singleton Manager as Centralized Coordination Point
- **Content:** The FeatureFlagsManager singleton serves as the intentional bottleneck ensuring all flag reads see consistent state across the distributed service consumers. This centralization trades testability and potential thread-safety concerns for guaranteed coherence during complex routing decisions involving multiple services. The singleton pattern here likely mirrors FirestoreManager's own architecture, maintaining familiar mental model during the migration it supports.
- **Anchors:**
  - `HomeColabApp/Views/Settings/ServiceFlagsDebugView.swift`

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

### Concept #36 — Consolidation Checkpoint Pattern for Post-Merger or Post-Pivot Integration

- **ID:** `d480d61485f9`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Consolidation Checkpoint Pattern for Post-Merger or Post-Pivot Integration
- **Content:** The 'Phase01_Consolidate' directory and 'consolidation checkpoint' language suggest this subsystem emerged from a prior restructuring—likely merging multiple product lines or architectural visions. The audit results file as a planning input indicates a retrospective-first methodology: document what exists before deciding what to build, implying inherited technical debt or competing stakeholder visions that required reconciliation.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase01_Consolidate/01_AUDIT_RESULTS.md`

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

### Concept #37 — Documentation-First Governance for Distributed Design Decision Authority

- **ID:** `aa24a5a53cd0`
- **Category:** `process`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Documentation-First Governance for Distributed Design Decision Authority
- **Content:** The existence of two separate design documents (COLOR_PALETTE_UPDATE.md for migration rationale, COLOR_SYSTEM.md for current specification) indicates a documentation-first governance model where design decisions are recorded before code implementation to enable asynchronous stakeholder review. This suggests distributed teams or external design agency involvement where written rationale serves as decision record and dispute resolution mechanism.
- **Anchors:**
  - `HomeColabApp/Docs/Design/COLOR_PALETTE_UPDATE.md`
  - `HomeColabApp/Docs/Design/COLOR_SYSTEM.md`

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

### Concept #38 — Temporal Metadata for Decision Timeline Reconstruction

- **ID:** `5b9cfcec8725`
- **Category:** `product`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Temporal Metadata for Decision Timeline Reconstruction
- **Content:** Explicit timestamp capture at item creation (rather than relying on database insertion time) enables faithful reconstruction of evaluation chronology even with offline-first sync patterns where insertion order diverges from actual observation sequence. This reveals an implicit product requirement that the 'story' of a property evaluation—when concerns emerged, when enthusiasm shifted—matters as much as the final categorized tally, supporting narrative-driven decision review rather than purely aggregate scoring.
- **Anchors:**
  - `HomeColabCore/Sources/HomeColabCore/Models/ProsConsCategory.swift`

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

### Concept #39 — Privacy Manifest as Preemptive Regulatory Defense

- **ID:** `14133b4c9c5a`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.80
- **Title:** Privacy Manifest as Preemptive Regulatory Defense
- **Content:** The SHARE_EXTENSION_PRIVACY.md documentation and privacy manifest configuration treat Apple's privacy nutrition labels not as bureaucratic checkbox exercise, but as forward-looking legal insulation. By explicitly documenting data flows for the share extension—a high-risk surface for unintentional data leakage—the team creates auditable evidence that can be cited in future regulatory inquiries or class action defense, particularly given the property/real-estate domain's sensitivity to financial and location data.
- **Anchors:**
  - `HomeColabApp/Docs/Marketing_Website/legal_for_marketing/SHARE_EXTENSION_PRIVACY.md`

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

### Concept #40 — Color Scheme-Aware Styling for Ad Container Border/Background

- **ID:** `58da3dd440ea`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.75
- **Title:** Color Scheme-Aware Styling for Ad Container Border/Background
- **Content:** Dynamic styling based on light/dark mode is applied to the container itself rather than the ad content, revealing that the subsystem treats the ad as a visually integrated module within the workspace rather than an isolated third-party element. This implies a design constraint: the ad must not visually 'break' the property workspace's information hierarchy, and the app's brand coherence takes precedence over raw ad visibility.
- **Anchors:**
  - `HomeColabApp/Components/Ads/Banners/InfoBannerAdContainer.swift`

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

### Concept #41 — Separation of Classification from Reporting as Single Responsibility

- **ID:** `ce3d5246850e`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Separation of Classification from Reporting as Single Responsibility
- **Content:** The architectural split between normalization (handle()) and routing (logError()) enforces that error classification logic remains independent of telemetry backend concerns. This separation anticipates future backend migrations or dual-reporting scenarios, and prevents the common entanglement where changing a logging provider corrupts error domain semantics. The 'partial' component status suggests this separation may be incomplete or recently refactored.
- **Anchors:**
  - `HomeColabApp/Utilities/ErrorHandler.swift`

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

### Concept #42 — Lucide icons as brand consistency infrastructure

- **ID:** `115cee2e5e4f`
- **Category:** `brand`
- **LLM confidence (current, suspect):** 0.65
- **Title:** Lucide icons as brand consistency infrastructure
- **Content:** The themed Lucide icon selection reflects a broader design system constraint rather than per-component choice, ensuring semantic consistency across the marketing site. This standardization reduces decision fatigue for developers and creates subconscious pattern recognition that this section belongs to the same trustworthy product family as other surfaced specifications.
- **Anchors:**
  - `HomeColabProWebsite/website/components/sections/SystemRequirements.tsx`

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

### Concept #43 — Legal Compliance as Latent Constraint on Feature Set

- **ID:** `e64d65d7aed5`
- **Category:** `constraint`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Legal Compliance as Latent Constraint on Feature Set
- **Content:** The domain tag 'legal-compliance' suggests that some deferred features (particularly server-side scraping and dead link monitoring) are constrained not by technical feasibility but by legal risk exposure. The subsystem documents these as strategic questions rather than legal blockers, preserving optionality while signaling that compliance review gates future activation.
- **Anchors:**
  - `HomeColabApp/Docs/Design/Key_Questions.md`

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

### Concept #44 — Jurisdiction-aware rendering as GDPR preparation vs. CCPA active compliance

- **ID:** `0d1d44b2fda0`
- **Category:** `domain`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Jurisdiction-aware rendering as GDPR preparation vs. CCPA active compliance
- **Content:** The domain tags include both 'gdpr' and 'gdpr-preparation,' suggesting asymmetric readiness—CCPA compliance is fully operational while GDPR may still be in staging. The component's 'partial' status reinforces this interpretation, indicating the jurisdiction-aware logic may have been scaffolded for future expansion rather than serving live regional variation. This reflects a business prioritization of California users (likely primary market) over European readiness at the pre-launch phase.
- **Anchors:**
  - `HomeColabProWebsite/website/app/privacy/page.tsx`

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

### Concept #45 — Three-Criteria Scoring as Rhetorical Device for Stakeholder Alignment

- **ID:** `e9a3bc50e401`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Three-Criteria Scoring as Rhetorical Device for Stakeholder Alignment
- **Content:** The explicit feasibility/desirability/viability framework, while structurally conventional, serves a specific political function in this subsystem: it provides an auditable rationale for controversial cuts (chat, queues, task management) by mapping them to objective-looking scores rather than subjective preference. This reveals a hidden constraint that the module author needed defensive documentation to justify scope reduction to stakeholders who might otherwise demand 'standard' collaboration features.
- **Anchors:**
  - `HomeColabApp/Docs/2.0/BusinessAPP/Phase04_DESIGN/04_REALITY_CHECK.md`

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

### Concept #46 — ObservableObject as reactive glue without framework lock-in

- **ID:** `fb8c235d03f9`
- **Category:** `pattern`
- **LLM confidence (current, suspect):** 0.70
- **Title:** ObservableObject as reactive glue without framework lock-in
- **Content:** Both managers expose ObservableObject to SwiftUI views, but the internal implementation uses Firestore's own listener patterns rather than wrapping them in Combine or async/await uniformly. This suggests a migration-aware stance: the reactive surface is standardized for UI consumption while the async boundary to Firebase remains vendor-native, preserving optionality to swap cloud providers without rewriting view-layer contracts.
- **Anchors:**
  - `HomeColabApp/Managers/FirestoreManager.swift`
  - `HomeColabApp/Managers/FirebaseStorageManager.swift`

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

### Concept #47 — Global Ad Configuration Centralizes Privacy Compliance Risk

- **ID:** `400c30e6ad8c`
- **Category:** `security`
- **LLM confidence (current, suspect):** 0.70
- **Title:** Global Ad Configuration Centralizes Privacy Compliance Risk
- **Content:** The data flow shows AdManager.shared as single enablement gate, concentrating ATT consent state and SKAdNetwork compliance decisions in one chokepoint. This architecture implies legal/business requirement to enforce user tracking consent before any ad subsystem activates, but also creates single point of failure where a bug disables all monetization. The 'significant incomplete implementation' warning suggests this coordination logic remains unfinished.
- **Anchors:**
  - `HomeColabApp/Components/Ads/Native/MapNativeAdCard.swift`
  - `HomeColabApp/Components/BannerAdView.swift`

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

### Concept #48 — Deep Linking Tag as Future Navigation Contract Without Implementation

- **ID:** `e07cbe658f86`
- **Category:** `technical`
- **LLM confidence (current, suspect):** 0.65
- **Title:** Deep Linking Tag as Future Navigation Contract Without Implementation
- **Content:** The presence of 'deep_linking' in domain tags despite no visible deep link handling in the client scaffolding indicates a planned navigation contract between notifications and in-app screens that was scoped out of the initial implementation. This suggests the subsystem was designed with awareness that push notifications must carry routing payloads, but the actual URL scheme or path resolution mechanism remains undefined.
- **Anchors:**
  - `HomeColabApp/Docs/Features/PUSH_NOTIFICATIONS_STRATEGY.md`

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

### Concept #49 — Zero Internal Dependencies as Isolation for Extraction

- **ID:** `ac36e5ec2455`
- **Category:** `architecture`
- **LLM confidence (current, suspect):** 0.60
- **Title:** Zero Internal Dependencies as Isolation for Extraction
- **Content:** The empty internal_dependencies array, unusual for a design system component, suggests architectural intent to make this module portable—either for future framework extraction, shared component library migration, or to prevent circular dependency issues common in growing SwiftUI codebases. The component resolves its own design tokens rather than importing a centralized tokens module, indicating either token duplication or a self-contained token resolution strategy that prioritizes independence over DRYness.
- **Anchors:**
  - `HomeColabApp/Components/EmptyStateView.swift`

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

### Concept #50 — Abandonment Signal vs. Deferred Intent Ambiguity

- **ID:** `4d89bfa7fe30`
- **Category:** `epistemic`
- **LLM confidence (current, suspect):** 0.60
- **Title:** Abandonment Signal vs. Deferred Intent Ambiguity
- **Content:** The subsystem's 'dormant' status creates interpretive uncertainty: the formal test target structure implies planned future work, yet the zero coverage and lack of TODO comments suggest possible permanent abandonment. This ambiguity may reflect organizational priority shifts where testing was deprioritized without explicit documentation, leaving the code as archaeological evidence of an unstarted or cancelled initiative.
- **Anchors:**
  - `HomeColabCore/Tests/HomeColabCoreTests/HomeColabCoreTests.swift`

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

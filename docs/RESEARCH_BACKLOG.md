# Prep Research Backlog (Phase Readiness)

This document tracks what remains before each phase can be considered **research complete**.

Reference:
- Research gates: `PHASE_RESEARCH_GATES.md`
- Phase dependencies: `PHASE_DEPENDENCIES.md`
- Workflow backbone (journeys + acceptance criteria + MVP boundaries): `WORKFLOW_RESEARCH.md`

## How to use this document
- Each phase README contains the current **open questions** and **research deliverables**.
- This backlog highlights the highest-leverage remaining work to close those gaps.

---

## Phase 01 — Foundation
**Doc:** `Phase01_Foundation/README.md`

Next research tasks:
- Define the exact `manifest.json` schema (required fields for reproducibility + incremental builds).
- Define the stable chunk/document ID strategy (and what guarantees it provides).
- Define the optional FTS capability detection + reporting (and fallback behavior).
- Define the “interrupted build” behavior and recovery strategy.

## Phase 02 — Dashboard
**Doc:** `Phase02_Dashboard/README.md`

Next research tasks:
- Finalize dashboard information architecture (pages, navigation, empty/error states).
- Define the UI-facing API contract (request/response + error shapes) for:
  - projects list/add/remove
  - build/status
  - search
  - context
- Decide what build progress granularity is required for MVP.

## Phase 03 — Auto-Rebuild
**Doc:** `Phase03_AutoRebuild/README.md`

Next research tasks:
- Decide watcher strategy (OS events vs polling) and the default debounce policy.
- Specify incremental indexing rules (changed detection, hash strategy, stable IDs).
- Specify how to avoid rebuild loops in embedded mode (watch exclusions).

## Phase 04 — Trace Index
**Doc:** `Phase04_TraceIndex/README.md`

Next research tasks:
- Specify node/edge schema + stable IDs.
- Define the python analyzer MVP (symbols + imports + spans) and how errors are handled.
- Specify query-time expansion controls (hops, limits, ranking integration).
- Decide how/if curated inputs (e.g. XREF-style) can be ingested as optional plugins.

## Phase 05 — MCP Integration
**Doc:** `Phase05_MCP_Integration/README.md`

Next research tasks:
- Decide architecture: MCP talks to daemon via HTTP vs in-process engine.
- Finalize tool schemas (payloads + error shapes) and limits policy.
- Specify project selection and conflict resolution rules.

## Phase 06 — Team & Enterprise
**Doc:** `Phase06_Team_And_Enterprise/README.md`

Note:
- Phase06 is **post-MVP implementation** (see ADR-012 and `WORKFLOW_RESEARCH.md`).

Next research tasks:
- Define embedded mode commit policy (default vs opt-in) and merge conflict handling.
- Define network mode security baseline (binding defaults, auth required, TLS expectations).
- Specify onboarding UX for team mode (dashboard and CLI flow).

## Phase 07 — Polish & Testing
**Doc:** `Phase07_Polish_Testing/README.md`

Next research tasks:
- Define the minimum automated test suite for MVP confidence.
- Define performance targets and a repeatable measurement method.
- Decide how to test Ollama-dependent flows (mocking vs local runtime).

## Phase 08 — Tauri MVP
**Doc:** `Phase08_Tauri_MVP/README.md`

Next research tasks:
- Choose packaging approach (PyInstaller vs PyOxidizer) and document the rationale.
- Specify port/binding strategy and single-instance behavior.
- Specify OS-specific data directories and signing/notarization requirements.

## Phase 09 — Post-MVP
**Doc:** `Phase09_Post_MVP/README.md`

Next research tasks:
- Convert the candidate list into a prioritized backlog (each with scope + success metrics).
- Decide which post-MVP items are “enterprise must-haves” vs “power-user wins”.

## Phase 10 — Business & Competitive Research (placeholder)
**Doc:** `Phase10_Business_And_Competitive_Research/README.md`

Next research tasks (later):
- Define research questions + decision outputs (pricing, packaging, ICP, deployment).
- Define a cadence and doc structure for competitive updates.

## Phase 11 — Deployment
**Doc:** `Phase11_Deployment/README.md`

Next research tasks:
- Decide whether macOS distribution is direct-download only for MVP, or whether Mac App Store constraints are worth accommodating.
- Specify signing/notarization requirements and the minimum operational docs required for a credible release.
- Define upgrade guarantees (what persists, what breaks, and how rebuilds are communicated).

## Phase 12 — Marketing Website + Public Documentation
**Doc:** `Phase12_Marketing-Documentation-Website/README.md`

Next research tasks:
- Write a v0 “Getting started” that walks a new user through the first trust loop (A1-J1).
- Decide docs hosting approach and versioning strategy.

## Phase 13 — Design System + Storybook
**Doc:** `Phase13_Storybook/README.md`

Next research tasks:
- Define the initial set of “task-based” component stories that map to trust invariants (freshness indicators, chunk viewer, citation blocks).
- Decide visual direction selection rubric and how it will be validated.

---

## When to “analyze next steps”
Once Phases 01–05 are research complete, we can do a grounded next-step analysis:
- identify the critical path,
- identify which decisions are blocking implementation,
- and decide what to build first with minimal rework.

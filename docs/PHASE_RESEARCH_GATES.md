# Prep Phase Research Gates

This document defines what it means for a Prep phase to be **"research complete"**.

It is meant to prevent the roadmap from being treated as a list of implementation tasks without sufficient clarity. The goal is to make sure each phase has enough definition that implementation can proceed with minimal surprises.

## Terminology

### Research complete (phase)
A phase is **research complete** when:

- the work is clearly scoped,
- the key technical decisions are made (or explicitly deferred), and
- the outputs/exit criteria are explicit enough that implementation is mostly execution.

Research complete does **not** necessarily mean anything is implemented.

### Implementation complete (phase)
Implementation complete means the phase's deliverables are shipped, tested, and integrated (see `ROADMAP.md`).

## Global research gate checklist (applies to every phase)

A phase is research complete when the phase README contains:

1. **Problem statement**
   - What problem this phase solves
   - What user workflow improves

2. **Scope**
   - Explicit in-scope work
   - Explicit out-of-scope work

3. **Success criteria**
   - Observable behaviors or measurable outcomes
   - Performance/UX constraints when relevant

4. **Artifacts produced by the phase**
   - New docs/specs, API schemas, data models, prototypes, benchmarks

5. **Dependencies**
   - Which earlier phases must be complete (research or implementation)
   - Which external services are required (Ollama)

6. **Open questions + decision points**
   - A list of decisions that must be made during implementation
   - Or a statement that no open questions remain

7. **Risks**
   - Failure modes and what will be done about them

8. **Testing / evaluation plan**
   - Smoke tests, integration tests, UX tests
   - For retrieval-related phases: basic retrieval evaluation plan

## Per-phase research gates

The sections below are additional gates beyond the global checklist.

### Phase 01 — Foundation
- Define the canonical on-disk formats (manifest/documents/embeddings + optional FTS)
- Define the minimal multi-project abstraction (project registry, project config)
- Define error behavior for:
  - missing Ollama
  - invalid repo paths
  - build failures
  - partial indexes

### Phase 02 — Dashboard
- Define the UI information architecture (navigation, project list/tabs)
- Define the stable API contract the UI consumes (request/response shapes)
- Define the non-goals for v1 UI (what will not be shown yet)

### Phase 03 — Auto-Rebuild
- Define the file watching scope and the debounce strategy
- Define incremental indexing rules:
  - what counts as "changed"
  - how we avoid re-embedding unchanged chunks
  - how stable IDs are derived

### Phase 04 — Trace Index
- Define the minimal node/edge schema and how it coexists with the embedding index
- Define the MVP analyzers (python first; TS optional)
- Define how trace data will be used at query time (expansion rules)

### Phase 05 — MCP Integration
- Define tool surface (which MCP tools exist, schemas, error behavior)
- Define project selection strategy:
  - explicit project id
  - cwd auto-detection

### Phase 06 — Team & Enterprise
- Define embedded mode behavior (what gets committed, conflict handling)
- Define network mode and security baseline (auth, keys)

### Phase 07 — Polish & Testing
- Define the minimum test suite for MVP confidence
- Define performance targets and how they will be measured

### Phase 08 — Tauri MVP
- Define packaging strategy (python sidecar bundling)
- Define installer targets and constraints

### Phase 09 — Post-MVP
- For each candidate feature, define:
  - why it matters
  - minimal viable scope
  - what it depends on

### Phase 10 — Business & Competitive Research (placeholder)
- Define explicit research questions and the decision outputs they should drive
- Define how/where research results flow back into product roadmap (ADRs and phase updates)

### Phase 11 — Deployment
- Define the deployment targets and constraints (local-only vs network mode assumptions)
- Define the minimum operational guidance required for MVP (install, start/stop, logs, data directories)

### Phase 12 — Marketing Website + Public Documentation
- Define domain decision criteria and canonical domain strategy (including redirects)
- Define domain/subdomain map and hosting assumptions
- Define v0 website + docs information architecture (placeholder launch)

### Phase 13 — Design System + Storybook
- Define the visual direction exploration plan (multiple prototypes before standardization)
- Define the token strategy compatible with Tailwind + Tremor
- Define the initial component inventory and Storybook documentation expectations

# Phase 09 — Post-MVP
 
 ## Problem statement
 After MVP, there’s a risk of becoming directionless or feature-driven without a clear framework. This phase exists to keep expansion disciplined: each candidate feature should have a rationale, scope, and measurable outcome.

 ## Goal
 High-leverage expansion after MVP stability.

 ## Scope
 ### In scope
 - Turning candidate features into scoped proposals (mini-specs)
 - Prioritization based on impact, feasibility, and strategic alignment
 - Defining success metrics and evaluation plans for each feature

 ### Out of scope
 - Treating this phase as a single “implementation bucket”
 
 ## Potential directions
 - Cross-project search (opt-in)
 - context compression toggle
 - AGENTS.md generation
 - More languages for trace analyzers
 - Graph visualization

 ## Functional specification

 ### Purpose of this phase

 This phase is not an “anything goes” bucket.

 It defines the process for converting candidate ideas into:
 - a scoped spec
 - an explicit decision
 - an implementation plan that does not destabilize MVP

 ### Candidate intake

 Sources of candidates:
 - User feedback (qualitative)
 - Internal friction logs (from troubleshooting docs; no telemetry required)
 - Competitive implications (when Phase 10 is active)
 - “Platform gaps” (missing primitives that block multiple features)

 Intake rules:
 - Every candidate must be written up as a mini-spec before it can be scheduled.
 - Every mini-spec must include a de-scope plan (what we cut if time runs out).

 ### Mini-spec template (required fields)

 Each post-MVP proposal must include:
 - **Problem statement** (who is blocked, and how)
 - **User story** (what a user can do after this ships)
 - **Scope** / **non-goals**
 - **UX surface** (dashboard, CLI, MCP, API)
 - **API changes** (endpoints + request/response shapes)
 - **Data model / persistence** changes
 - **Operational impact** (CPU/memory/disk, build time, failure modes)
 - **Security/privacy impact** (especially if network mode is involved)
 - **Backward compatibility** and migration plan
 - **Testing plan** (unit/integration/E2E)
 - **Success metrics** (how we evaluate outcome)

 ### Prioritization rubric

Each candidate should be scored (lightweight, but explicit) across:

- **Impact**
  - improves adoption and trust
  - increases enterprise value
  - reduces time-to-answer for real workflows

- **Feasibility**
  - engineering complexity
  - dependencies on earlier primitives
  - maintainability cost

- **Risk**
  - destabilizes core build/search/context loop
  - increases operational complexity (team/server)
  - increases security surface

- **Strategic alignment**
  - strengthens “local-first, team-ready” thesis
  - extends GraphRAG/trace differentiation

### Decision and documentation flow

When a candidate is accepted:
- Update `docs/ROADMAP.md` (add to timeline/backlog)
- Update the relevant phase README(s) if it changes earlier assumptions
- Add an ADR in `docs/DECISIONS.md` if it changes architecture or contracts

When a candidate is rejected or deferred:
- Record the reason (avoid repeating debates)
- Record what would need to change for it to become viable

### Evaluation harness expectations

For retrieval-related work (search/context/trace), each accepted feature should ship with:
- a small suite of “gold queries” for at least one representative repo
- a repeatable evaluation procedure (manual is acceptable; automated later)

### Backward compatibility and deprecation policy

- Prefer additive changes to API and on-disk formats.
- If a breaking change is required:
  - bump `format_version`
  - provide a deterministic rebuild/migration path
  - ensure UI clearly communicates incompatibility and remediation

 ## Success criteria
 - Each chosen post-MVP item has a problem statement, scope, and success criteria.
 - Roadmap updates are reflected in phase docs and ADRs.

 ## Research deliverables
 - A prioritized post-MVP backlog with clear owners and milestones
 - For each top item: a short spec + dependency analysis

 ## Dependencies
 - MVP baseline is stable (Phases 01–08)

 ## Open questions
 - Which feature(s) most increase enterprise value vs individual value
 - Whether cross-project search should be local-only or include remote/server use cases

 ## Risks
 - Scope creep and loss of focus
 - Adding features that increase operational complexity without clear ROI

 ## Testing / evaluation plan
 - Per-feature evaluation plans (varies)
 - Ensure each feature includes a rollback/de-scope plan

 ## Research completion criteria
 - Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 09 gates)

 ## Reference
 - `docs/ROADMAP.md`
 - `../Phase00_Initial-Concept/AI_INFRASTRUCTURE_RESEARCH.md`
 - `../Phase00_Initial-Concept/TRACE_INDEX_RESEARCH.md`

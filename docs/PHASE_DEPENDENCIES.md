# Prep Phase Dependencies

This document maps phase dependencies so we can:

- keep the roadmap realistic,
- identify the critical path,
- and decide next steps only after phases are research complete.

## Dependency principles
- **Phase 01 (Foundation)** is the base for almost everything.
- UI work (Phase 02) should not outrun API stability.
- Trace (Phase 04) is optional for MVP, but it influences chunking, ranking, and evaluation.
- Team/enterprise (Phase 06) is **post-MVP implementation**, but its constraints should feed back into earlier phases via `WORKFLOW_RESEARCH.md` and ADR-012.

## High-level dependency map

### Research-level dependencies
These are “must decide/define before implementation proceeds safely”.

- **Phase 01 → Phase 02**
  - UI depends on stable API shapes + persistence format.
- **Phase 01 → Phase 03**
  - Auto-rebuild depends on stable IDs/hashes/manifest updates.
- **Phase 01 → Phase 05**
  - MCP depends on stable tool schemas and core build/search/context.
- **Phase 01 (+ optional Phase 03) → Phase 04**
  - Trace can ship without incremental rebuild, but is materially better with it.
- **Phase 02 + Phase 07 → Phase 08**
  - Tauri packaging depends on a stable web UI and known operational requirements.
- **Phase 01–05 → Phase 07**
  - Polish/testing depends on MVP feature surface stability.

### Implementation-level dependencies (typical order)
- **Phase 01 (engine) → Phase 02 (dashboard) → Phase 03 (auto-rebuild)**
- **Phase 04 (trace)** can be started after Phase 01 but will need integration work across Phase 02/03.
- **Phase 05 (MCP)** can be started after Phase 01 and run in parallel with Phase 02.
- **Phase 06 (team/enterprise implementation)** is post-MVP.
- **Phase 07 (polish/testing)** is late-stage stabilization.
- **Phase 08 (tauri)** is MVP packaging.

## Critical path (MVP)
Assuming the target is the MVP described in `ROADMAP.md`:

1. Phase 01 — Foundation
2. Phase 02 — Dashboard
3. Phase 03 — Auto-Rebuild
4. Phase 04 — Trace Index (can be MVP+1 if needed)
5. Phase 05 — MCP Integration
6. Phase 07 — Polish & Testing
7. Phase 08 — Tauri MVP
8. Phase 11 — Deployment

## How this interacts with “research complete”
- A phase should not be considered **ready to execute** until its README meets `PHASE_RESEARCH_GATES.md`.
- Once phases 01–05 are research complete, we can do a structured “what next?” decision, rather than guessing.

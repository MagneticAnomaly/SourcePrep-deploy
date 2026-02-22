<div align="center" style="background-color: #0b0e23; padding: 40px 0; width: 100vw; margin-left: calc(-50vw + 50%);">
  <img src="../assets/header-logo.png" alt="CoDRAG" width="400">
</div>

# Phase 01 — Foundation

## Problem statement
CoDRAG’s later phases (dashboard, auto-rebuild, trace, MCP, team mode) all depend on a correct, stable core index with a documented on-disk format and predictable error behavior.

## Goal
Establish CoDRAG’s core engine and data model end-to-end (single-project first, but designed for multi-project).

## Scope
### In scope
- Core index build/search/context primitives
- On-disk persistence format (manifest/documents/embeddings + optional FTS)
- Multi-project foundations (project config shape and storage layout; registry integration)
- “No Ollama” and “build failed” error behavior

### Out of scope
- Full dashboard UX polish
- Trace index extraction and traversal
- Team/network mode

## Derived from (Phase69 sources)
- `../Phase00_Initial-Concept/IMPLEMENTATION.md`
- `../Phase00_Initial-Concept/AI_INFRASTRUCTURE_RESEARCH.md`

## Deliverables
- Core index build/search/context primitives stabilized in `src/codrag/core/`
- On-disk format verified (manifest/documents/embeddings + optional FTS)
- Clean error handling for missing Ollama / failed builds

## Success criteria
- A single project can be indexed end-to-end (build → status → search → context) using CoDRAG’s core engine.
- The on-disk format is stable enough that other components can depend on it.
- Failure modes are predictable and surfaced as user-actionable errors.

## Deep research notes (Phase01 + Phase02)

### User archetypes (Phase01 perspective)

- **Solo developer (local-first default)**
  - Needs: correctness, fast incremental rebuilds, predictable output.
  - Primary fear: silent corruption or silent staleness.

- **Staff engineer / tech lead**
  - Needs: reproducible builds, stable formats for team adoption.
  - Primary fear: format churn breaks downstream tooling (dashboard/MCP).

- **IDE agent user (MCP consumer)**
  - Needs: stable chunk IDs/citations and bounded outputs.
  - Primary fear: non-determinism causes agent loops to degrade.

### Core workflows

The foundation layer must make these workflows reliable:

- **Workflow A: Build lifecycle**
  - scan files
  - chunk
  - embed
  - write index atomically
  - update `manifest.json`

- **Workflow B: Retrieval lifecycle**
  - embed query
  - vector search
  - return ranked chunks
  - assemble context with citations

- **Workflow C: Failure and recovery**
  - dependency down (Ollama unavailable)
  - partial write / interrupted build
  - permission denied / IO failures

### Scope tightening and invariants

Phase01 should explicitly guarantee:

- **Atomic index updates**
  - Search/context always operate on the last known-good snapshot.

- **Stable, inspectable persistence**
  - `manifest.json`, `documents.json`, `embeddings.npy` remain transparent and rebuildable.

- **Deterministic chunk identity**
  - Chunk IDs must be stable across rebuilds when file path + span + content are unchanged.

- **Bounded resource usage**
  - Enforce `max_file_bytes` and caps on request sizes (k, max_chars).

- **Actionable errors**
  - Every failure has a stable `error.code` and a recommended `hint`.

## Research deliverables
- A minimal “core contract” doc (what the engine guarantees to API/CLI/UI)
- A persistence format spec (what files exist and what they contain)
- A baseline performance envelope (what repo sizes are acceptable for MVP targets)

## Dependencies
- `docs/ARCHITECTURE.md` (storage layout + component boundaries)
- `docs/DECISIONS.md` (MVP constraints and technology choices)

## Open questions
- Which fields are mandatory in `manifest.json` for incremental builds and reproducibility
- How optional FTS should be detected and reported (capabilities and fallbacks)
- How much to optimize for large repos in MVP vs post-MVP

## Risks
- Persistence format churn (breaking downstream UI/MCP compatibility)
- Index corruption or partial writes during interrupted builds

## MCP (Multi-Project Routing)

Phase 01 guarantees that downstream clients (dashboard, CLI, MCP) can reliably target the correct project when multiple CoDRAG projects are registered in the daemon.

### Problem

IDE MCP clients (Windsurf/Cursor/Claude Code/etc.) typically connect to CoDRAG via a single MCP server process. If the daemon has multiple projects configured, the MCP server must deterministically choose which project to query for:

- `codrag_search`
- `codrag` (context assembly)
- trace tools (symbol search / neighbors / coverage)

### Resolution order

The MCP server resolves `project_id` with the following priority order:

1. Tool-call override: `project_id` argument passed directly to the tool call
2. Pinned mode: CLI `codrag mcp --project <id>`
3. Workspace roots: paths provided by the IDE during MCP `initialize` (workspace root URIs)
4. Process CWD: the MCP subprocess working directory (commonly the IDE workspace root)
5. Single-project shortcut: if exactly one project exists, use it

Matching is based on longest-prefix path containment (the most specific registered project path wins).

### Tool schemas

All MCP tools accept an optional `project_id` argument. This enables:

- Deterministic targeting when auto-detection is ambiguous
- AI self-correction: the model can retry the same request with an explicit `project_id`

### Responses

Every tool response includes the resolved `project_id` so that clients (and the model) can confirm which project was queried.

`codrag_status` may additionally include an `available_projects` list (IDs, names, paths) when multiple projects exist, to make project selection discoverable.

### Failure mode: ambiguous selection

If the MCP server cannot confidently determine a project, it returns a stable error that includes the full list of configured projects and a hint to pass `project_id` explicitly.

### Recommended setup patterns

- Per-workspace MCP config (recommended for multi-window IDE usage): each workspace window spawns its own MCP server process and auto-detection routes correctly.
- Global MCP config + auto-detect: relies on workspace roots and/or MCP process CWD.
- Pinned MCP config: for dedicated tool windows or single-project environments.

### Reference

For end-user configuration examples, see the public MCP shim docs:

- `public/codrag-mcp/README.md` → “Multi-Project Setup”

## Testing / evaluation plan
- Integration test: build → search → context on a known repo
- Corruption resilience: interrupted build leaves index in a recoverable state

## Research completion criteria
- Phase README satisfies `../PHASE_RESEARCH_GATES.md` (global checklist + Phase 01 gates)

## Notes
This phase should prioritize correctness + persistence format over UI features.

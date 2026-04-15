# Phase 106: Master Index -- Gap Analysis & New Phase Definitions

> **Date:** 2026-04-15
> **Scope:** Review of Phases 74-105, gap analysis, and creation of 5 new macro phases (107-111)

---

## Summary

Reviewed 32 phase directories spanning Phases 74-105. Found:
- **23 tasks completed** across all phases
- **359 tasks pending** across all phases
- **168 identified gaps, opportunities, and deferred items**

The pending work was concentrated in 5 macro themes. Each theme became a new phase:

## New Phases Created

| Phase | Theme | Key Files | Task Count | Priority |
|---|---|---|---|---|
| **107** | Pipeline & State Machine Stability | `orchestrator.py`, `state_machine.py`, `stages.py` | ~30 tasks | CRITICAL -- blocks all other work |
| **108** | MCP Tool Quality & Agentic Integration | `mcp/server.py`, `mcp_tools.py`, `rules_generator.py` | ~35 tasks | HIGH -- directly impacts users |
| **109** | Knowledge Layer (Concepts, Audit, Immune System) | `concept_store.py`, `concept_seeder.py`, `antibodies.py`, audit analyzers | ~35 tasks | HIGH -- unique differentiator |
| **110** | Retrieval Intelligence (Intent, Chunking, Weights) | `index.py`, `query_analyzer.py`, `repo_profile.py`, `chunking.py` | ~30 tasks | HIGH -- search quality |
| **111** | MVP Readiness & Shipping Surface | Cross-cutting: all API endpoints, dashboard, Tauri, marketing | ~40 tasks | CRITICAL -- gates release |

## Dependency Order

```
Phase 107 (Pipeline Stability)
    |
    +---> Phase 109 (Knowledge Layer) -- needs stable pipeline to validate concepts/audit
    |         |
    |         +---> Phase 108 (MCP Quality) -- needs knowledge layer data for antibody wiring
    |
    +---> Phase 110 (Retrieval Intelligence) -- needs stable pipeline for benchmarking
    |
    +---> Phase 111 (MVP Readiness) -- needs ALL above phases for golden path validation
```

**Recommended execution order:** 107 -> 109 + 110 (parallel) -> 108 -> 111

## Phase-to-Phase Traceability

### Phases 74-105 -> New Phases

| Old Phase | Absorbed Into | What Carries Forward |
|---|---|---|
| 74 (Concepts) | 109 | Quality validation, dashboard panel verification |
| 75 (Queue) | 107 | Ghost guard, queue UI deferred items |
| 76 (Rebuild) | 107 | Zero-downtime rebuild (blocked on stable handoff) |
| 77 (Claude Interop) | 108 | Client-aware delivery (32 pending tasks) |
| 78 (Dev Server) | 111 | MCP server resilience |
| 79 (Swarm) | 108 | Swarm verification on shipped stages |
| 80 (MemPalace) | 109 | L2 scoped context (working_dir filtering) |
| 81 (UI Bugfixes) | 107 | Stage 4 (error visibility) deferred |
| 82 (MCP Dogfooding) | 108 | 9 FIX items from prioritized fix plan |
| 83 (Audit Redesign) | 109 | Severity recalibration |
| 83 (MCP External) | 108 | Antibody wiring gap |
| 84 (Concepts Formal) | 109 | Assertion checking, supersede |
| 85 (SARIF) | 109 | SARIF enrichment for external tools |
| 86 (Intent Classification) | 110 | Multi-strategy intent router |
| 87 (Immune System) | 109 | End-to-end validation |
| 88 (Agent Generator) | 108 | Deferred to role= param |
| 89 (State Machine) | 107 | Atomic stage handoff (root cause) |
| 90 (Fixes/Feedback) | 111 | Haley diagnostic (21 tasks) |
| 91 (Queue Refinement) | 107 | Swarm UI deferred |
| 92 (SQLite WAL) | 107 | WAL recovery |
| 93 (Chunking) | 110 | Scoped MVP (context headers, merge, split) |
| 94 (OpenClaw) | 108 | Smoke test + compound query docs |
| 95 (Weights) | 110 | Explicit path weights (advertised but missing) |
| 96 (Fix Pipeline) | 107 | F-66, F-68 open; test rot |
| 97 (Pricing) | 111 | Free tier enforcement |
| 98 (Dashboard Optimization) | 111 | SSE migration |
| 99 (Content) | 111 | Marketing alignment |
| 100 (NVIDIA Research) | -- | Validated direction (no action) |
| 101 (Trim for MVP) | 111 | Dev/prod separation |
| 102 (Prep/Rename) | 111 | Naming consistency |
| 103 (Agent Optimizations) | 108 | Task-based role inference (shipped) |
| 104 (Sub-Atlas) | 110 | Role lens verification |
| 105 (Independent Finalize) | 107 | Finalize rewire (33 tasks) |
| 105 (GIT) | -- | Deferred -- not MVP-critical |

## Key Risks

1. **Phase 107 is the bottleneck.** Pipeline stability blocks validation of every other phase. If the orchestrator still stalls, we can't trust benchmark results (110), knowledge layer output (109), or MCP responses (108).

2. **Path weights (110) are a marketing liability.** They're advertised but not implemented. Either ship them or remove the marketing claim before MVP.

3. **Concept quality is unvalidated (109).** The entire knowledge layer (concepts, audit, immune system) has never been tested end-to-end on a real project. It might be fantastic or it might produce garbage. We don't know yet.

4. **359 pending tasks is too many.** Even with consolidation, shipping all 5 phases is months of work. The MVP gate (111) should be ruthless about what's required vs. nice-to-have.

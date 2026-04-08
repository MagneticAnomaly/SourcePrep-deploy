# CoDRAG Master Roadmap

**Last updated:** 2026-04-08
**Scope:** Phases 83-87 and all deferred future work items

---

## Active Phases

| Phase | Name | Status | Dependencies | Key Deliverable |
|-------|------|--------|-------------|-----------------|
| **83** | Audit Redesign | Design finalized | None | Dual-mode `codrag_audit`: structural-only + enrichment. Global experimental toggle. P0 quick fixes. |
| **84** | Concepts Formalization | Design finalized | Phase 83 | Structured concept model with assertions, anchors, doc links, conflict resolution, observation promotion. |
| **85** | SARIF Enrichment | Design finalized | Phase 83 | SARIF 2.0/2.1.0 ingestion for enrichment mode. Valid SARIF in → enriched SARIF out. Tool-specific adapters. |
| **86** | Intent Classification | Design finalized | Phase 84 | 7-intent taxonomy with rule-based classifier. Per-intent retrieval pipelines. Query rewriting. |
| **87** | Codebase Immune System | Design finalized | Phases 83, 84 | Antibodies from concepts/observations. Watcher integration. Ambient alerts. Advisory git hooks. |

### Dependency Graph

```
Phase 83 (Audit Redesign)
  ├── Phase 84 (Concepts Formalization)
  │     ├── Phase 86 (Intent Classification — RATIONALE pipeline needs concepts)
  │     └── Phase 87 (Immune System — antibodies derive from concepts)
  └── Phase 85 (SARIF Enrichment — enrichment mode must exist first)
```

Phases 83 and 85 can run in parallel once Phase 83's enrichment mode is functional. Phase 84 can start as soon as Phase 83's structural mode ships (concept violations are consumed there). Phases 86 and 87 can proceed independently of each other once Phase 84 completes.

---

## Global Decisions

These apply across all phases:

| Decision | Detail |
|----------|--------|
| **Experimental toggle** | Single project-level `experimental: true/false` setting controls all experimental features: LLM recommendations, audit dashboard pane, future experimental capabilities. |
| **Stale data message** | When un-indexed files are encountered: "Looks like you have stale data, CoDRAG recommends running enrichment again." Used across audit enrichment and SARIF. |
| **Risk score formula** | `0.40 * hub + 0.30 * concept + 0.20 * observation + 0.10 * churn`. Weights in config, tunable after dogfooding. |
| **Recommendations** | Templates default, LLM experimental. Both shown when experimental is on. |
| **Anchor granularity** | File/module/directory/glob for MVP. Symbol-level deferred. |
| **Concept conflicts** | Oldest wins for code enforcement. Both get red outlines in dashboard. Surfaced as audit finding. |
| **Immune system UX** | Never block. Ambient alerts only. Feels like a helpful colleague, not a CI gate. |

---

## Future Work Roadmap

Items deferred from Phases 83-87, prioritized. These are all explicitly noted in the phase docs as future work.

### High Priority (Recommended Next)

| Item | Origin | Description | Why High |
|------|--------|-------------|----------|
| **Phase 85.1: Cross-run SARIF analysis** | Phase 85 | When multiple tools flag the same file, synthesize convergent signals. "Ruff + semgrep both flagged this critical hub file." | Multiplies enrichment value significantly. Natural extension of Phase 85. |
| **LLM-assisted concept generation** | Phase 84 | LLM helps structure assertions from free-text input. Behind experimental toggle. | High demand — manual assertion writing is friction. Already behind toggle. |
| **Multi-intent query composition** | Phase 86 | Detect compound queries ("Where is X and why does it use Y?"), run multiple pipelines, merge results. | Handles the most common classifier edge case. |
| **Concepts UI: rich visualization** | Phase 84 | Move beyond grid MVP — concept cloud, relationship visualization, Paperclip goal mapping UI. | Eric has specific UI ideas for this. Revisit after MVP ships. |
| **Observation pattern auto-learning** | Phase 87 | Tune observation pattern threshold based on dismiss rates. Auto-disable noisy antibodies. | Reduces manual antibody management overhead. |

### Medium Priority

| Item | Origin | Description |
|------|--------|-------------|
| **Symbol-level anchoring** | Phase 84 | Anchor concepts to specific functions/classes, not just files. Enables finer-grained violation detection. |
| **ML intent classifier** | Phase 86 | Replace/augment rule-based classifier with trained model. Higher accuracy for ambiguous queries. |
| **SARIF export from structural mode** | Phase 85 | `codrag_audit()` exports its own structural findings as SARIF. Makes CoDRAG a SARIF producer. |
| **Cross-file antibody triggers** | Phase 87 | Evaluate violations across batches of related file changes, not just individual files. |
| **Antibody auto-learning** | Phase 87 | Auto-disable antibodies with >50% dismiss rate. Promote testing→active based on catch rate. |
| **Intent override auto-tuning** | Phase 86 | When agents use `intent` override, log as misclassification signal. Periodic rule tuning reports. |
| **Concept → Paperclip goal bridge** | Phase 84 | Partial mapping — some concepts map to Paperclip goals. Not 1:1 but valuable where it fits. |

### Future / Exploratory

| Item | Origin | Description |
|------|--------|-------------|
| **GitHub App integration** | Phase 85 | CoDRAG runs as GitHub App, auto-enriches Code Scanning SARIF on push. |
| **Streaming enrichment** | Phase 85 | Stream results for SARIF files with 1000+ findings instead of batch. |
| **Concept evolution chains** | Phase 84 | Visualize how concepts supersede each other over time. Architectural decision history. |
| **Immune system CI integration** | Phase 87 | Beyond opt-in git hooks — full CI step that runs antibody evaluation and posts results to PR. |
| **Real-time dashboard alerts** | Phase 87 | Push antibody alerts to dashboard via SSE/WebSocket as they trigger, not just on next MCP call. |
| **Concept-aware code generation** | Phase 84 | When an AI agent generates code, concepts inform what patterns to follow and constraints to respect. |
| **Cross-project concept sharing** | Phase 84 | Share concepts between related projects (e.g., monorepo packages that share architectural conventions). |

---

## Phase 82 Backlog (Remaining Items)

Items from Phase 82 MCP-Dogfooding docs not covered by Phases 83-87:

| Item | Source Doc | Status |
|------|-----------|--------|
| P0: Impact markdown formatting | Doc 07 | Bundled with Phase 83 |
| P0: Impact stdlib filtering | Doc 07 | Bundled with Phase 83 |
| P0: Search symbol context | Doc 07 | Bundled with Phase 83 |
| P0: Exclude lock/generated files | Doc 07 | Bundled with Phase 83 |
| P1: Fix intern role projection | Doc 07 | Not yet scheduled — tune TAG_TO_AUDIENCE weights |
| P1: Cross-tool "Next Steps" suggestions | Doc 07 | Partially addressed by intent classification routing |
| P2: Progressive disclosure (`detail` param) | Doc 07 | Not yet scheduled |
| P2: Staleness indicator on all responses | Doc 07 | Partially addressed by stale data message in enrichment |
| P2: Hub file selection prefer code over docs | Doc 07 | Not yet scheduled |
| Observe/concepts boundary clarification | Doc 08 | Addressed by Phase 84 (temporal vs durable distinction formalized) |

---

## Versioning

This roadmap is a living document. Update it when:
- A phase status changes (design → in progress → complete)
- New future work items are identified during implementation
- Priorities shift based on dogfooding feedback
- Items move between priority tiers

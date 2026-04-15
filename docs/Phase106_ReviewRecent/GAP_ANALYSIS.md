# CoDRAG Phases 74-105: Gap Analysis & Completeness Review

This document provides a verbose thematic review of planned work, completed items, and identified gaps/opportunities from Phase 74 to 105.

## Theme: Agentic & MCP Tooling

### Phase77_Claude-Interoperability: Phase 77.2: Client-Aware Content Delivery Strategy

**Completeness:** 0 tasks completed, 32 tasks pending.

**Key Pending Work:**
- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement target-aware `_build_managed_content()`**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Run existing atlas hash tests to verify no regressions**
- ... plus 27 more tasks.

### Phase79_Swarm: Model Swarm Capability Research

**Completeness:** 2 tasks completed, 29 tasks pending.

**Key Pending Work:**
- [ ] **Step 1: Create the data directory and JSON registry**
- [ ] **Step 2: Write the failing tests for swarm_registry**
- [ ] **Step 3: Run tests to verify they fail**
- [ ] **Step 4: Implement swarm_registry.py**
- [ ] **Step 5: Run tests to verify they pass**
- ... plus 24 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- Starts earlier than expected** — detectable quality degradation can begin at 30%–50% fill, depending on task complexity
- | Stage | Swarm Opportunity | Priority |
- > Status: Design approved, pending implementation plan
- Why:** Air‑gapped environments; limited utility.

### Phase83_Audit-Redesign: Phase 83 — Audit Redesign: Structural Intelligence + Enrichment Layer

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase83_MCP-Dogfooding-External: 07 — PowerMateReborn: Honest Assessment of CoDRAG on a Small Real-World Project

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- | **Impact quality** | Mixed | Mixed | Mixed (same graph gaps) |
- | 1 | Antibody store not initialized in MCP | High | Wiring gap — pipeline writes, MCP can't read | **Retrieval** — init store in server startup |
- The antibody gap is a wiring issue, not a generation issue. The data exists but the MCP server can't reach it.

### Phase88_Agent-Generator: Phase 88 — Agent Generator: Universal Two-Pass Role Architect

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- Pass 1: Discovery & Org Design (Gap & Drift Analysis)
- 5. Cross-role analysis: overlap detection, gap detection, specialization balance
- Cross-role analysis detects overlap (merge candidates), gaps (new hire needed), and over/under-specialization.

### Phase94_OpenClawResearch: Phase 94 — CoDRAG as Research Context Provider

**Completeness:** 0 tasks completed, 9 tasks pending.

**Key Pending Work:**
- [ ] CoDRAG daemon running (`codrag serve`)
- [ ] OpenClaw gateway started with `codrag` MCP server in `openclaw.json`
- [ ] Gateway logs show successful MCP handshake and tool discovery (6 tools)
- [ ] Agent can call `codrag` and receive structural overview
- [ ] Agent can call `codrag_search` with a natural language query
- ... plus 4 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- | **Universal Adapter** | Partial | Hexagonal architecture. MCP/CLI/HTTP built. A2A/SARIF pending |
- Gap:** None, if prior observations were saved. The observation store is the memory layer.
- Bottom line:** There is a disciplined, bounded integration opportunity — but it requires careful scoping to avoid the security and complexity traps that have plagued the broader OpenClaw ecosystem.
- 3. The Real Gaps
- Opportunity C: OpenClaw as Researcher Orchestrator (MODERATE EFFORT, HIGH VALUE)
- Inverting the perspective — CoDRAG as context provider rather than agent — reveals that the gaps are smaller and more focused than the previous doc suggested:
- Opportunity D: Bidirectional Agent Coordination (HIGH EFFORT, SPECULATIVE)
- Why:** Until Gap 2 (compound queries) is built, documenting the multi-step pattern lets agents and humans do it manually. Zero CoDRAG code changes.
- ... and 7 additional notes.

---

## Theme: Epistemology, Concepts & Audit

### Phase74_Concepts: Phase 74 — UI Design: Concepts Dashboard Panel

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- 3. Epistemic Gap Analysis — Where Concepts Would Have Helped
- ConceptQuestionList** — List of pending clarifying questions with inline answer capability. Expanding a question shows the context, suggested category, and a text area for the answer.
- ConceptsPanel** — The overview card on the dashboard grid. Shows concept count, cluster summary, coverage bar, and pending question count. "Initialize" button if no concepts exist.
- │                    │  RETRIEVAL      │        │  Identifies gaps  │   │
- 4. The Opportunity
- Gap Detection:
- Pending question count badge
- 5. For each gap, generate a targeted question:
- ... and 19 additional notes.

### Phase80_mempalace: Phase 80: MemPalace Integration — Research Strategy

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- | L2 module-scoped retrieval (Track B) | High — fills a real context gap | Small | Low | 1 | **DO** |
- Verdict: **DO THIS** — High priority, the gap is real and the fix is small

### Phase84_Concepts-Formalization: Phase 84 — Concepts Formalization: From Theoretical to Load-Bearing

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- Symbol-level anchoring deferred — file/module/directory/glob covers all MVP use cases. Can be added later if a concrete need arises.
- 3. **Anchor granularity** — File/module/directory/glob for MVP. Symbol-level deferred — no concrete use case demands it yet.

### Phase85_SARIF-Enrichment: Phase 85 — SARIF Enrichment: Industry-Standard Finding Ingestion

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase87_Codebase-Immune-System: Phase 87 — Codebase Immune System: Proactive Architectural Defense

**Completeness:** 0 tasks completed, 0 tasks pending.

---

## Theme: Pipeline & Architecture Operations

### Phase75_Queue: Phase 75: Global Pipeline Queue & Ghost Lock Remediation

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase76_RebuildPipeline: Phase 76: Zero-Downtime Pipeline Rebuild Architecture

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase81_UI-bugfixes: Phase 81 — Dashboard Panel Inventory & State Audit

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- Status:** Stages 0-3 complete, Stage 4 deferred
- Status:** Stages 0-3 complete, Stage 4 (error visibility) deferred
- | [02_Dashboard_Panel_Inventory.md](02_Dashboard_Panel_Inventory.md) | Full inventory of 18 hooks, 37 panels, hydration gap analysis |
- Stage 2: Hydration Gaps (P1)
- Status:** Analysis complete, fixes pending
- 1. **Backend SSE gap:** `_pause_group()` did not emit SSE after `PAUSING->PAUSED` transition. Frontend had a 3+ second blind spot where pause state was only discoverable via polling.
- 1. `pipeline_run_metadata.json` shows `clustering: { status: "pending" }` — never ran
- <div className={cn("flex flex-col items-center justify-center gap-3 py-12 px-4", className)}>
- ... and 8 additional notes.

### Phase82_CloudPipelineConcurrency: Latency-Aware Discovery (AIMD + BBR) for LLM Concurrency

**Completeness:** 0 tasks completed, 39 tasks pending.

**Key Pending Work:**
- [ ] **Step 1: Write failing tests for `is_swarm_active_for_stage()`**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement `SWARM_CAPABLE_STAGES` and `is_swarm_active_for_stage()`**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**
- ... plus 34 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- git commit -m "chore: Phase 82 — swarm UI accuracy + AIMD provider gaps
- Part 2: AIMD Provider Gaps
- 2. **AIMD provider gaps** — Azure OpenAI and Google Gemini providers lack throughput recording.
- Phase 82: Swarm UI Accuracy + AIMD Gap Fixes
- """Tests for LLM client throughput recording (Phase 82 provider gaps)."""
- Goal:** Make the UI accurately show swarm vs concurrent mode by checking model capability, and fill AIMD throughput reporting gaps in Azure/Gemini providers.
- Phase 82: Swarm UI Accuracy + AIMD Gap Fixes — Implementation Plan

### Phase82_MCP-Dogfooding: 11 — Agent Workflow Patterns

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- OPPORTUNITY 1: "What should I fix first?" action
- OPPORTUNITY 3: "What if I change function X?" — symbol-level impact
- OPPORTUNITY 1: "Find usages" query type
- use here. This appears to be a genuine security gap.
- OPPORTUNITY 3: "What do I need to know?" summary
- (Phase 62). Focus: opportunity discovery, not task management.
- OPPORTUNITY 2: Audit diff between runs
- OPPORTUNITY 3: Surface focus areas more prominently
- ... and 16 additional notes.

### Phase89_StateMachine-revisited: Phase 89: Build Modes Audit — Initial / Incremental / Rebuild

**Completeness:** 0 tasks completed, 27 tasks pending.

**Key Pending Work:**
- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement `is_held_by()`**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**
- ... plus 22 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- One actionable gap**: Deep enrichment manifest invalidation during rebuild. This should be a quick fix — add `force_from_start` to the invalidation condition at the chaining point.
- Edge case: Pipeline completes** (all stages done). `_advance_pipeline()` transitions to COMPLETED, then the old lock is released. No gap.
- Gap Found: No `progress_baseline` for Rebuild
- 3. Deferred Resume Race
- _deferred_resume = None
- if deferred_resume:
- self._resume_queued_pipeline(_deferred_resume.project_id, _deferred_resume.stage)
- deferred_resume.project_id, deferred_resume.stage,
- ... and 7 additional notes.

### Phase91_QueueRefinement: Phase 91: Pipeline Scheduler Resource Allocation Redesign

**Completeness:** 20 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- Fix duplicate display: ensure pipeline state and scheduler queue aren't both shown as separate "pending" items
- | Batch engines (dynamic scaling) | Existing engines handle None from `full_budget_for_swarm()`. Mid-flight scaling deferred. | ⏳ Deferred |
- | Dashboard UI (swarm visuals) | Status API exposes data; UI components not yet built | ⏳ Deferred |

### Phase92_SQLite-WAL-Recovery: Phase 92: SQLite WAL Lock Prevention

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- Three independent gaps:

### Phase96-fix-pipeline: Phase 96D: Dashboard UI State Sync — Diagnostic

**Completeness:** 0 tasks completed, 50 tasks pending.

**Key Pending Work:**
- [ ] `seed_concepts_swarm` works with mocked SwarmOrchestrator
- [ ] `seed_concepts_swarm` falls back to sequential when conditions not met
- [ ] Audit Tier 2 swarm works with mocked SwarmOrchestrator
- [ ] CONCEPTS and AUDIT in SWARM_CAPABLE_STAGES
- [ ] All 202 existing pipeline tests still pass
- ... plus 45 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- Symptom:** Cancelled and failed pipelines lingered in `/system/pipeline-queue` API responses. The dashboard rendered them as "Pending" (label bug) and showed ghost entries.
- Wrong label:** `cancelled` is mapped to "Pending" visually (label bug)
- Deferred until Phase 96E ships and we have a clean spec.**
- 1. Doesn't have a mapping for phase=`cancelled` (falls through to default "Pending"?)
- 2. These files then appeared as "untraced" in coverage gap checks
- Status (FIXED / OPEN / DEFERRED / NOT-A-BUG)
- 3. The coverage gap triggered a full pipeline rebuild
- Extracted resume point detection and coverage gap analysis from `orchestrator.py` into dedicated `ResumeStrategy` class in `src/codrag/services/pipeline/resume.py`.
- ... and 26 additional notes.

### Phase105_IndependentFinalize: Phase 105a — Orchestrator Single-Stage + Atlas Rewire

**Completeness:** 0 tasks completed, 33 tasks pending.

**Key Pending Work:**
- [ ] **Step 1.1: Write the failing unit tests**
- [ ] **Step 1.2: Run the tests to verify they fail**
- [ ] **Step 1.3: Implement `run_single_stage`**
- [ ] **Step 1.4: Run the tests to verify they pass**
- [ ] **Step 1.5: Ruff clean**
- ... plus 28 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- 1. **No queue entry.** The left-panel queue never shows the regenerate as pending/running/done.
- All other finalize stages — unchanged in 105a; deferred to 105b.

### Phase105_GIT: 05 — Risks for Option γ

**Completeness:** 0 tasks completed, 71 tasks pending.

**Key Pending Work:**
- [ ] **Step 1: Add the three methods to `GitClient`**
- [ ] **Step 2: Type-check the new methods**
- [ ] **Step 3: Commit**
- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- ... plus 66 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- Wins considered and deferred
- it is a **performance** framing. The bigger opportunity is **semantic**:
- Deferred to later phases:**
- `opportunity_manager.py`'s coupling signals.
- Deferred primitives (forward-compatible signatures)
- Depending on the constructor signature, this may need adaptation.
- `github_push.py`, `sprint_intelligence.py`, `opportunity_manager.py`,
- `hot_zones`). Everything else deferred. The module is consumer-
- ... and 19 additional notes.

---

## Theme: Product, MVP & Deployment

### Phase78_dev-server-repair: Phase 78 — MCP Server Stability Research & Dev Workflow Optimization

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase90_Fixes-Feedback: 06 — Diagnostic Report: Why Phases 83-88 Show Partial Results on Haley

**Completeness:** 0 tasks completed, 21 tasks pending.

**Key Pending Work:**
- [ ] Verify the API field name: does `/trace/hub_files` return `"path"` or `"file_path"`?
- [ ] Verify the API URL: is it `/trace/hub-files` or `/trace/hub_files`? Does FastAPI normalize the hyphen?
- [ ] Check whether Haley has legacy audit findings at all: `GET /projects/{project_id}/audit/findings`
- [ ] Check whether the atlas cycle data (from `atlas.json`) is accessible via a different API
- [ ] Consider having `run_structural_audit` detect cycles directly from the trace graph instead of relying on legacy findings
- ... plus 16 more tasks.

### Phase97_Pricing-ProductTier-UPDATE: Free Tier Project Limits: "Archive vs Purge" Strategy

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase98_Dashboard-Optimization: Dashboard Polling Architecture — Phase 98

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase100_Research_Nvidia-etc: GTC 2026 S81570 — "From Data to Decisions: Enabling AI Agents With Business Knowledge"

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- The Honest Gap NVIDIA Left Open
- CoDRAG already covers 1 and 2 well. The gaps are #3 (reason-ready surfaces over the graph), and #5 (the data flywheel idea — see below).

### Phase101_Trim-for-MVP: Dev-Only Architecture & Dead Code Elimination Strategy (Phase 101)

**Completeness:** 0 tasks completed, 0 tasks pending.

**Identified Gaps, Opportunities & Deferred Work:**
- | # | Gap | Severity | Previous Doc? |
- Summary of Gaps Found (vs. Previous Document Version)
- This is the **biggest gap** the previous document missed. The Python backend already has a coherent dev-mode flag (`CODRAG_DEV_MODE`), but it's read inconsistently and can be set at runtime.

---

## Theme: Search, Chunking & Retrieval Intelligence

### Phase86_Intent-Classification: Phase 86 — Intent Classification: Making Search Understand What You're Actually Asking

**Completeness:** 0 tasks completed, 0 tasks pending.

### Phase93_ChunkingResearch: Phase 93: Semantic Chunking & Contextual Retrieval Implementation Plan

**Completeness:** 0 tasks completed, 32 tasks pending.

**Key Pending Work:**
- [ ] **Step 1: Write the failing tests for the SG filter**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement the SG filter**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**
- ... plus 27 more tasks.

**Identified Gaps, Opportunities & Deferred Work:**
- merged[-1] = merged[-1] + " " + pending
- pending = chunk_text
- candidate = pending + " " + chunk_text
- pending = candidate
- Opportunity:** Define operations once (schema + handler), auto-generate MCP tool definitions, CLI subcommands, and API routes. Reduces maintenance burden and prevents drift.
- CoDRAG comparison:** CoDRAG has no query expansion. It extracts structural signals (file paths, symbols, keywords) from queries but doesn't rephrase for broader recall. This is a clear gap.
- | Priority | Opportunity | Status |
- if pending:
- ... and 8 additional notes.

### Phase95_weights: Phase 95: Path Weights

**Completeness:** 1 tasks completed, 10 tasks pending.

**Key Pending Work:**
- [ ] Add `path_weights` config to project settings (e.g. `{"docs/": 0.5, "src/core/": 1.5, "vendor/": 0.3}`) >>
- [ ] Apply weights during context assembly in `lod_extractor.py` / search ranking
- [ ] Surface in `codrag_search` and `codrag` tool params or project config
- [ ] Validate weights propagate through Atlas routing and LOD compression
- [ ] Ensure `role` param on `codrag` and `codrag_search` applies weight modifiers derived from role definitions
- ... plus 5 more tasks.

### Phase104_SubAtlas: Phase 104 — Sub-Atlas & Role Lens Dashboard Panel

**Completeness:** 0 tasks completed, 6 tasks pending.

**Key Pending Work:**
- [ ] `ruff check src/` and `mypy src/` pass.
- [ ] `pytest tests/ -v` passes including new tests in Steps 1–4.
- [ ] `npm run typecheck` and `npm run lint` pass across workspaces.
- [ ] Storybook renders all new stories without console errors.
- [ ] Dev-server golden path (Step 6 checkpoint + Step 7 checkpoint) tested manually in browser.
- ... plus 1 more tasks.

---

## Overall Gap Analysis Summary

Based on the detailed extraction above, here are the macro-level gaps and areas needing more work:

1. **Pipeline & State Machine Stability**: Many phases (81, 89, 96, 105) repeatedly address pipeline state, queue lockups, and UI hydration. The introduction of the `IndependentFinalize` (Phase 105) aims to resolve stage bypassing, but pending tasks indicate the orchestrator rewire is still ongoing. The continuous churn here is a major completeness gap.
2. **Agentic Tooling & MCP Integration**: While `codrag` MCP tools were dogfooded heavily (Phase 82), several advanced integrations (OpenClaw, Swarm, Agent-Generator) remain largely in the research or design phase. The gap between 'designed' and 'implemented' is substantial here.
3. **Knowledge Layer (Concepts & Audit)**: Concept formalization and the Codebase Immune System (Antibodies) represent significant opportunities. The research is deep, but UI triggers and full lifecycle integration (e.g., seeding concepts automatically) have pending work.
4. **Retrieval Intelligence**: Intent classification (Phase 86) and Adaptive Chunking/Weights (Phase 93, 95) are identified as high-value opportunities to improve search signal-to-noise ratio, but many implementation tasks are marked pending.
5. **MVP Readiness**: Dev-only architecture trimming (Phase 101) and SQLite WAL recovery (Phase 92) indicate preparations for a stable release, but the sheer volume of pending tasks across these phases suggests the MVP surface area might still be too broad.

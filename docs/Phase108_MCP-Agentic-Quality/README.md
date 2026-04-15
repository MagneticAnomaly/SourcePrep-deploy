# Phase 108 -- MCP Tool Quality & Agentic Integration

> **Scope:** Fix all MCP tool UX issues from dogfooding, complete client-aware delivery, and establish external agent integration paths.
> **Prior art:** Phases 77, 79, 82, 83, 88, 94, 103
> **Status:** Research & TODO (**reality-checked 2026-04-15** — see §1.5; ~55% of fixes shipped)
> **Date:** 2026-04-15

> **⚠️ Reality-check delta (2026-04-15):** The tool count is **6, not 5** — `codrag_concepts` is a real shipped tool. Of the 9 FIX items from Phase 82 dogfooding, **FIX-1/2/3/4/6 are SHIPPED** (markdown formatter + stdlib filter in `7a15df99`; symbol metadata in `621e4b55`; large-file basename filter in place; role projection via Phase 103 R4 `94f1086e`). **FIX-5/7/9 remain**, and **FIX-8 is half-done** (target param wiring exists, but MCP client detection doesn't trigger regeneration). SARIF enrichment (§4.4) is SHIPPED (`980fa9e9`). See §1.5 for full verdict.

---

## 1. Problem Statement

Phase 82 was a brutally honest dogfooding session that graded every MCP tool and produced a prioritized fix plan (07_Prioritized_Fix_Plan.md). Phase 83 tested on an external project (PowerMateReborn) and found the same issues in the wild. The fixes were documented but many remain unimplemented.

Meanwhile, several ambitious agentic features (Swarm model orchestration, Agent Generator, OpenClaw integration) were heavily researched but sit at 0% implementation. The gap between "designed" and "shipped" is the widest in this theme.

**Key metrics from Phase 82 dogfooding:**
- `codrag`: B+ (role projection broken; hub selection favors docs over code)
- `codrag_search`: B (symbol search returns no context; semantic misses on "build pipeline")
- `codrag_impact`: C+ (raw JSON output; stdlib noise; missing internal edges)
- `codrag_audit`: B- (severity inflation; duplicate findings; generic remediation)
- `codrag_observe`: A- (works well)
- `codrag_concepts`: N/A (empty -- not adopted)

## 1.5 Reality Check Against Current Code (2026-04-15)

| Claim (from §1–§3) | Verdict | Evidence |
|---|---|---|
| "5 production tools" | **STALE — 6 tools** | `mcp_tools.py:25-420` `_CORE_TOOLS` list: codrag, codrag_search, codrag_impact, codrag_audit, codrag_observe, codrag_concepts |
| FIX-1 markdown for `codrag_impact` all directions | **FIXED** | `7a15df99` + `mcp/server.py:3879-3922` (all directions call markdown) |
| FIX-2 filter stdlib/external from impact | **FIXED** | `7a15df99` + `mcp/server.py:1448-1453` (neighbors); `tool_impact:1532-1535` |
| FIX-3 symbol search includes qualname/docstring/line | **FIXED** | `621e4b55`; `mcp/server.py:1375-1405` |
| FIX-4 EXPECTED_LARGE_BASENAMES filter | **FIXED** | `audit/analyzers/large_files.py:20-35` — lock/log patterns in place |
| FIX-5 hub file selection favors code over docs | **STILL-OPEN** | `atlas/generator.py:882-890` `_identify_hubs` sorts by in-degree only; no code-vs-docs multiplier |
| FIX-6 role projection works | **FIXED** | `94f1086e` (Phase 103 R4). `mcp/server.py:3724-3753` routes task→role inference; passed to `tool_codrag` |
| FIX-7 audit severity recalibration | **STILL-OPEN** | `audit/analyzers/large_files.py:76-82` still marks 80K+ bytes as "critical"; no severity downgrade |
| FIX-8 client-aware managed content | **PARTIAL** | `rules_generator.py:328-477` `_build_managed_content(target)` exists; IDE writers pass target. **Gap:** MCP server detects clientInfo in `handle_initialize()` (`server.py:2761, 118`) but never flows client name to rules regeneration. Rules are daemon-written, not MCP-driven. |
| FIX-9 antibody store init in MCP | **FIXED** | `mcp/server.py:835` — `_antibody_store.init(_antibody_store_db_path)` called on startup. (*Phase 108 reality-check report initially flagged this as still-open; Phase 109 reality-check found the call on line 835.*) |
| "Client detection logged but content adaptation missing" | **CONFIRMED** | `self._client_name` stored at `mcp/server.py:118`; no downstream flow |
| §2.4 Agent Generator 0/0 | **CONFIRMED** | No `agent_generator.py` found |
| SARIF enrichment (§4.4) | **SHIPPED** | `980fa9e9`; `mcp/server.py:3931-3944` + `:2244` `tool_audit_enrich_sarif`; full SARIF-in/SARIF-out |
| `codrag(role=...)` task-based inference | **SHIPPED** | Phase 103 R4 (`94f1086e`); already production |

## 2. Existing Infrastructure Assessment

### 2.1 MCP Tools (6 production tools)

From `mcp_tools.py`:
- **codrag** -- ambient context with `task`, `role`, `working_dir`, `max_chars` params. Has Phase 103 R4 task-based role inference.
- **codrag_search** -- query-based with `type` (context/symbol), `intent` override, `exclude_paths`, `working_dir`.
- **codrag_impact** -- blast radius analysis with `file_path`, `symbol`, `direction`, `max_hops`.
- **codrag_audit** -- structural findings with `action` (scan/antibodies/refactor/verify/report/advise), `findings` param for external enrichment.
- **codrag_observe** -- cross-session memory with `action` (save/get), file anchoring, staleness.

### 2.2 Client-Aware Delivery (Phase 77)

Phase 77 designed target-aware `_build_managed_content()` for AGENTS.md/rules files that adapts to the IDE client (Cursor, Windsurf, Claude Code, Copilot, etc.). **32 tasks pending, 0 completed.** The `clientInfo.name` detection exists but content adaptation does not.

### 2.3 Swarm (Phase 79)

Model Swarm research is extensive (6 docs, pricing analysis, execution profiles). Phase 96F wired swarm into concept seeding and audit. But the general-purpose swarm registry, pricing-aware routing, and dual-model orchestration remain unimplemented. **29 tasks pending, 2 completed.**

### 2.4 Agent Generator (Phase 88)

Two-pass role architect design: Pass 1 (Discovery & Org Design) uses CoDRAG structural intelligence to analyze a codebase and generate role definitions. Pass 2 (Prompt Engineering) generates agent prompts for each role. **0 tasks completed, 0 pending** (design only, no implementation plan).

### 2.5 OpenClaw (Phase 94)

Research concluded that CoDRAG-as-context-provider is the highest-value integration path. 9 verification tasks pending. Real gaps identified: external dependency view, exposure report for packages, observation provenance.

## 3. Prioritized Fix Plan (from Phase 82 dogfooding)

### Tier 1: Quick Wins (1-2 hours each, high impact)

**FIX-1: Format `codrag_impact` direction="all" as markdown**
The markdown formatter already exists in `tool_impact` -- just needs wiring for all directions.

**FIX-2: Filter stdlib/external nodes from impact results**
Filter on existing `metadata.external` flag. Removes ~75% noise from dependency analysis.

**FIX-3: Add code context to symbol search results**
Data exists in trace node metadata (`qualname`, `docstring`, `line`). Just needs surfacing in the markdown template.

**FIX-4: Exclude lock files and log files from critical audit findings**
Verify/fix existing `EXPECTED_LARGE_BASENAMES` filter. Add patterns for nested lock files and log directories.

### Tier 2: Medium Effort (half-day each)

**FIX-5: Hub file selection should favor code over docs**
Current hub selection ranks by in-degree, which favors `README.md` and `__init__.py`. Add a code-vs-docs multiplier.

**FIX-6: Role projection for `codrag(role="intern")` etc.**
Phase 82 found role projection was broken. The `role` param exists but doesn't actually filter/adapt the context.

**FIX-7: Audit severity calibration**
32 "critical" findings on a healthy repo is severity inflation. Recalibrate thresholds. Large files should be "info" not "critical".

### Tier 3: Significant Effort (1-2 days each)

**FIX-8: Client-aware managed content (Phase 77)**
Implement `_build_managed_content()` that adapts AGENTS.md sections based on detected IDE.

**FIX-9: Antibody store wiring for MCP**
Phase 83 external dogfooding found the antibody store isn't initialized in the MCP server. Data exists (pipeline writes it) but MCP can't read it. Wiring gap only.

## 4. TODO

### 4.1 MCP Tool Quality Fixes (from Phase 82) — **5 of 9 SHIPPED**
- [x] FIX-1: Wire markdown formatter to `codrag_impact` for all directions — **[FIXED: 7a15df99]**
- [x] FIX-2: Add `metadata.external` filter — **[FIXED: 7a15df99]**
- [x] FIX-3: Expand symbol search with qualname/docstring/line — **[FIXED: 621e4b55]**
- [x] FIX-4: Large-file basename filter — **[FIXED]** (`audit/analyzers/large_files.py:20-35`)
- [ ] FIX-5: Code-vs-docs multiplier on hub ranking — **[STILL-OPEN]** (`atlas/generator.py:882-890` still in-degree only)
- [x] FIX-6: Role projection — **[FIXED: 94f1086e]** (Phase 103 R4, task→role inference)
- [ ] FIX-7: Audit severity recalibration — **[STILL-OPEN]** (`large_files.py:76-82` still critical at 80K)
- [x] FIX-9: Antibody store init in MCP startup — **[FIXED]** (`mcp/server.py:835`)
- [ ] Write integration tests for each fix against CoDRAG's own index — **[PARTIAL]** (some FIXes tested via existing harness; dedicated post-fix test pass missing)

### 4.2 Client-Aware Delivery (Phase 77 completion) — **INFRASTRUCTURE PARTIAL**

The `_build_managed_content(target)` signature exists at `rules_generator.py:328-477` and IDE writers pass `target="claude"/"cursor"/"universal"`. Content already adapts per target (lines 400-447). **The missing piece:** MCP server captures `clientInfo.name` at `handle_initialize()` (`server.py:118`) but never flows it to `write_rules_file()`. Rules are daemon/CLI-generated, not MCP-session-driven.

**Decision needed:** (a) have MCP server trigger rules regeneration on initialize with detected client, OR (b) accept that rules files are pre-generated per-target at install time and skip MCP-session reactivity.

- [x] `_build_managed_content(target)` signature — **[FIXED]** (`rules_generator.py:328`)
- [x] `clientInfo.name` detection at initialize — **[FIXED]** (`server.py:118, 2761`)
- [ ] **NEW:** Wire `self._client_name` into rules regeneration path — **[STILL-OPEN, DECISION NEEDED]**
- [x] Cursor: `.cursor/rules/codrag.mdc` — **[FIXED]** (IDE writer exists)
- [x] Windsurf: `.windsurf/rules/codrag.md` — **[FIXED]** (IDE writer exists)
- [x] Claude Code: append to `CLAUDE.md` — **[FIXED]**
- [x] Copilot: `.github/copilot-instructions.md` — **[FIXED]**
- [x] Roo Code / Cline writers — **[FIXED]** (IDE writers exist)
- [ ] Test each generated format against the actual IDE — **[STILL-OPEN]** (human verification)
- [ ] Add `codrag_audit(action="antibodies")` data to generated rules — **[STILL-OPEN]** (blocked only by the decision above)

### 4.3 Swarm Completion (Phase 79 -- scoped to shipped stages)
- [ ] Verify concept seeding swarm (Phase 96F) works end-to-end on test repo — **[NEEDS-VERIFICATION]** (`concept_seeder.py` swarm path + fallback exists; live e2e untested)
- [ ] Verify audit Tier 2 swarm works end-to-end — **[NEEDS-VERIFICATION]**
- [ ] Add swarm status to `/pipeline/status` response — **[STILL-OPEN]**
- [ ] Dashboard UI for swarm status — **[STILL-OPEN]**
- [ ] Defer: swarm registry, pricing-aware routing, dual-model orchestration — **[ACCEPT-DEFERRAL]**

### 4.4 External Agent Integration (scoped)
- [ ] OpenClaw smoke test — **[STILL-OPEN]** (human test)
- [ ] Document multi-step pattern for compound queries — **[STILL-OPEN]**
- [x] Agent Generator deferred to `role=` path — **[ACCEPTED]** (no `agent_generator.py` in tree; `role=` pathway shipped)
- [x] SARIF enrichment (`codrag_audit(findings=[...])`) — **[FIXED: 980fa9e9]** (`mcp/server.py:3931-3944, :2244`; full SARIF-in/SARIF-out)

### 4.5 MCP Resource & Prompt Polish
- [ ] Verify all MCP Resources browsable (atlas, structure, modules, audit findings, concepts, focus areas) — **[NEEDS-VERIFICATION]**
- [ ] Test MCP Prompts (codrag-onboard, codrag-review, codrag-plan, codrag-investigate, codrag-health) — **[NEEDS-VERIFICATION]**
- [ ] Update tool descriptions using arXiv rubric if any have drifted — **[STILL-OPEN]**

## 5. Links to Prior Work

| Phase | What it built | Status | Gap this phase addresses |
|---|---|---|---|
| 77 | Client-Aware Delivery Strategy | **Infrastructure partial** (target param + IDE writers live; MCP→rules flow missing) | §4.2 |
| 79 | Model Swarm Research | Concepts+audit swarm wired; e2e untested | §4.3 |
| 82 | MCP Dogfooding (internal) | **5 of 9 fixes SHIPPED**; 3 open + 1 partial | §4.1 |
| 83 | MCP Dogfooding (external, PowerMateReborn) | Assessment done | FIX-9 now FIXED (`server.py:835`) |
| 85 | SARIF Enrichment | **SHIPPED** (`980fa9e9`) | §4.4 done |
| 88 | Agent Generator | Deferred to `role=` path — `role=` shipped | — |
| 94 | OpenClaw Research | 0/9 verification tasks done | §4.4 |
| 103 | Task-based role inference | **SHIPPED** (`94f1086e`, Phase 103 R4) | Foundation for FIX-6 (also shipped) |

## 6. Success Criteria

1. All 9 FIX items from dogfooding verified against CoDRAG's own index
2. `codrag_impact` returns markdown with zero stdlib noise
3. `codrag_audit` critical findings count < 10 on healthy repos
4. Client-aware rules files generated and tested on Cursor + Windsurf + Claude Code
5. Antibody data accessible via MCP
6. OpenClaw smoke test passes

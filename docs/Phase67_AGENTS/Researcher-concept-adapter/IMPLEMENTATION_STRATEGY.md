# Phase 67 — Implementation Strategy & Progress Tracker

> **Created:** 2026-04-01
> **Purpose:** Prioritized TODO list cross-referenced against the architecture audit. Tracks what exists, what's needed, and the build order.

---

## Infrastructure Audit: What Already Exists

Before building anything, here's what the architecture audit (04_Architecture_Audit.md) identified as reusable — verified against the current codebase:

| Infrastructure | Status | Location | Notes |
|---|---|---|---|
| PaperclipAdapter (REST client) | **EXISTS** | `adapters/paperclip_adapter.py` | Full CRUD: companies, goals, projects, issues. Dedup via CoDRAG address. |
| PushEngine (orchestration) | **EXISTS** | `adapters/push_engine.py` | ActionItem → Filter → Consolidate → Push pipeline. Dry-run, history. |
| PM data models | **EXISTS** | `adapters/pm_models.py` | `PMProject`, `PMGoal`, `PMIssue`, `PMPushConfig`, `PushResult` |
| Pi Agent (7 scenarios) | **EXISTS** | `services/pi_agent.py` | 1170 lines. Watchdog, Doctor, Geologist, Dispatcher, Librarian, Architect, Scholar. |
| AgentConcurrencyGate | **EXISTS** | `services/agent_gate.py` | One-at-a-time serialization. Checks 9 LLM pipeline stages. |
| AgentScopeManager | **EXISTS** | `core/agent_scope_manager.py` | Per-agent file scope, auto-populate via RoleVector, runtime masking. |
| Agent Scope API | **EXISTS** | `api/routers/agent_scope.py` | Full REST: get/set/add/remove/delete/auto-populate per role. |
| Agent Scope UI Panel | **EXISTS** | `packages/ui/.../agents/AgentScopePanel.tsx` | Role presets, file tree, auto-populate button. Registered in panelRegistry. |
| A2A Protocol Handler | **EXISTS** | `a2a/handler.py` | JSON-RPC 2.0, 4 skills, task lifecycle. |
| A2A Agent Card | **EXISTS** | `a2a/agent_card.json` | Discovery endpoint at `/.well-known/agent.json` |
| OpportunityManager | **EXISTS** | `core/audit/opportunity_manager.py` | Aggregates ActionItems from all analyzers. Export: SARIF/JSON/CSV/MD. |
| ActionItem model | **EXISTS** | `core/audit/action_item.py` | Universal model: id, title, priority, severity, effort, files, sub_tasks. |
| Settings Store | **EXISTS** | `services/settings_store.py` | SQLite-backed, namespaced keys, thread-safe. |
| Observation Store | **EXISTS** | `services/observation_store.py` | SQLite + FTS5. Categories, staleness tracking. Max 500/project. |
| Scope Orchestrator | **EXISTS** | `services/scope_orchestrator.py` | Scope rebuild pipeline with debouncing and state machine. |
| LLM Client | **EXISTS** | `core/llm_client.py` | Multi-provider (Ollama, OpenAI, Anthropic, Google). Rate-limit aware. |
| Model Awareness | **EXISTS** | `core/model_awareness.py` | State machine: idle→loading→ready→active. VRAM tracking. |
| Event Bus (SSE) | **EXISTS** | `core/events.py` | Thread-safe queue, progress events, log broadcasting. |
| PM Push API | **EXISTS** | `api/routers/pm_push.py` | POST push, GET/PUT config, GET health. |
| Dashboard ModularDashboard | **EXISTS** | `packages/ui/.../layout/ModularDashboard.tsx` | Panel registry, detail overlay, grid layout. |
| StatusBadge component | **EXISTS** | `packages/ui/.../status/StatusBadge.tsx` | fresh/stale/building/pending/error/disabled states. |
| Panel detail overlay pattern | **EXISTS** | `ModularDashboard` | Full-screen modal with ESC close, backdrop blur. |
| `src/codrag/agents/` directory | **DOES NOT EXIST** | — | Must be created from scratch. |
| LangGraph dependency | **DOES NOT EXIST** | — | Not in pyproject.toml optional-deps. |
| CrewAI dependency | **DOES NOT EXIST** | — | Not in pyproject.toml optional-deps. |

**Bottom line:** ~80% of the infrastructure exists. What's missing is the agent engines themselves, the orchestration adapters, and the Agent Operations dashboard panel.

---

## Build Order

The architecture audit identified dependency direction rules:
```
agents/ → services/ → core/
agents/ → adapters/

FORBIDDEN: services/ → agents/, core/ → agents/, adapters/ → agents/, mcp/ → agents/
```

This means `agents/` is purely additive — nothing in the existing codebase should ever import from it. This gives us freedom to build incrementally without breaking anything.

### Critical Path

```
Phase 0: Package scaffolding + AgentCore
    ↓
Phase 1: Staffing Engine (most docs, highest complexity)
    ↓  ↘
Phase 2: Researcher Engine    Phase 3: Custodian Engine
    ↓  ↗                          (can parallelize)
Phase 4: CLI commands (thin layer over engines)
    ↓
Phase 5: API endpoints (thin layer over engines)
    ↓
Phase 6: LangGraph adapters (all 3 agents)
    ↓
Phase 7: CrewAI adapters (all 3 agents)
    ↓
Phase 8: Dashboard — Agent Ops panel (Level 1)
    ↓
Phase 9: Dashboard — Agent Ops detail overlay (Level 2) + AI Gateway agent model slots
```

**Rationale for this ordering:**
1. **AgentCore first** — everything depends on it
2. **Staffing before Researcher** — Staffing has the most detailed docs (7 HR-concept docs) and is the most novel; Researcher heavily overlaps with existing Pi Agent
3. **Custodian can parallelize** with Researcher — independent functionality
4. **CLI before API** — faster iteration loop for testing engines
5. **Native adapters before LangGraph/CrewAI** — prove the engines work first
6. **Dashboard last** — needs stable API endpoints to wire to

---

## Phase 0: Package Scaffolding + AgentCore

> **Depends on:** Nothing (greenfield)
> **Audit ref:** Opportunity 2 (PushEngine reuse), Opportunity 5 (Settings Store)

| # | Task | File | Status |
|---|------|------|--------|
| 0.1 | Create `agents/` package structure | `src/codrag/agents/__init__.py` | ☑ |
| 0.2 | Create `agents/shared/` subpackage | `agents/shared/__init__.py` | ☑ |
| 0.3 | Implement `AgentCore` class | `agents/core.py` | ☑ |
| | — CoDRAG read: `get_audit_findings()`, `get_module_structure()`, `get_impact_radius()`, `get_atlas()`, `search_code()`, `get_role_vector()`, `save_observation()` | | |
| | — Paperclip write: `push_project()`, `push_goal()`, `push_issue()`, `create_agent()`, `update_agent()` | | |
| 0.4 | Create shared data models | `agents/shared/models.py` | ☑ |
| | — `RoleSpec`, `ResearchTopic`, `ResearchPlan`, `CleanupPlan`, `CleanupCandidate` | | |
| 0.5 | Create CoDRAG data access wrapper | `agents/shared/codrag_data.py` | ☑ |
| | — Clean interface over OpportunityManager, atlas, trace store, impact analysis | | |
| 0.6 | Create Paperclip client wrapper | `agents/shared/paperclip_client.py` | ☑ |
| | — Thin wrapper around existing `adapters/push_engine.py` + `adapters/paperclip_adapter.py` | | |
| 0.7 | Create shared git client | `agents/shared/git_client.py` | ☑ |
| | — Branch create/switch, commit, diff, archive ops (for Custodian + future) | | |
| 0.8 | Add agent config namespace to settings | (settings_store integration) | ☑ |
| | — `agents_config.staffing`, `agents_config.researcher`, `agents_config.custodian` | | |

**Exit criteria:** `AgentCore` can pull audit findings from OpportunityManager and push a dummy project to Paperclip via PushEngine.

**Post-audit additions (gap fixes):**

| # | Gap | Resolution | Status |
|---|-----|-----------|--------|
| 0.9 | `get_module_structure()` missing | Added to CoDRAGDataAccess + AgentCore. Reads `trace_modules.jsonl`. | ☑ |
| 0.10 | `search_code(query, role)` missing | Added to CoDRAGDataAccess + AgentCore. Wraps CodeIndex.search() with role-based filtering. | ☑ |
| 0.11 | `get_role_vector(role_slug)` missing | Added to CoDRAGDataAccess + AgentCore. Wraps `resolve_role()`. | ☑ |
| 0.12 | `get_atlas()` lacked role param | Updated to `get_atlas(role=None)`. Uses `project_atlas_for_role()` when role is set. | ☑ |
| 0.13 | `AgentConcurrencyGate` not accessible | Added `acquire_gate()` / `release_gate()` to AgentCore. Wraps `get_agent_gate()`. | ☑ |
| 0.14 | `LLMClient` not accessible | Added `get_llm_client(task_id)` factory to AgentCore. Reads pipeline_config from settings. | ☑ |
| 0.15 | `create_agent()` / `update_agent()` missing | Added as `NotImplementedError` placeholders — Paperclip adapter lacks agent CRUD API. | ☑ |

---

## Phase 1: Staffing Agent Engine

> **Depends on:** Phase 0
> **Audit ref:** Opportunity 3 (Focus Scope placement), Opportunity 7 (ModelAwareness)
> **Design docs:** HR-concept-adapter/ Docs 01–07

| # | Task | File | Status |
|---|------|------|--------|
| 1.1 | Create `agents/hr/` subpackage | `agents/hr/__init__.py` | ☑ |
| 1.2 | Implement readiness scoring | `agents/hr/readiness.py` | ☑ |
| | — `compute_readiness()`: checks pipeline completion, module count, domain tags | | |
| 1.3 | Implement role generation (list mode) | `agents/hr/engine.py` | ☑ |
| | — `list` mode: user specifies roles | | |
| | — `auto` mode: LLM infers from codebase | | |
| | — `auto+list` mode: hybrid | | |
| 1.4 | Implement AGENTS.md generation | `agents/hr/engine.py` + prompts | ☑ |
| 1.5 | Implement SOUL.md generation | `agents/hr/engine.py` + prompts | ☑ |
| 1.6 | Implement KNOWLEDGE.md generation | `agents/hr/engine.py` + prompts | ☑ |
| | — Template from Doc 06: CoDRAG tools, atlas snapshot, key files, domain focus | | |
| 1.7 | Implement drift detection / audit | `agents/hr/engine.py` | ☐ |
| | — Role fitness scoring, domain drift detection, realignment proposals | | |
| 1.8 | Implement org chart generation | `agents/hr/engine.py` | ☐ |
| | — Reports-to, manages, collaborates-with relationships | | |
| 1.9 | Create LLM prompts | `agents/hr/prompts.py` | ☑ |
| | — `render_agents_md_prompt`, `render_soul_md_prompt`, `render_auto_roles_prompt` | | |
| 1.10 | Native Paperclip adapter | `agents/hr/adapters/paperclip.py` | ☐ |
| | — Daemon thread, direct Python imports, hooks into pipeline completion | | |
| 1.11 | Edge case handling (Doc 05) | `agents/hr/engine.py` | ☐ |
| | — Insufficient data blocking, single-domain, monorepo, re-gen, role elimination | | |

**Exit criteria:** `codrag hr generate --mode auto` produces AGENTS.md + SOUL.md + KNOWLEDGE.md per role.

---

## Phase 2: Researcher Agent Engine

> **Depends on:** Phase 0
> **Audit ref:** Opportunity 1 (Pi Agent convergence — CRITICAL), Opportunity 8 (Observation categories)
> **Design docs:** implementation_plan.md §5, README.md §2

| # | Task | File | Status |
|---|------|------|--------|
| 2.1 | Create `agents/researcher/` subpackage | `agents/researcher/__init__.py` | ☐ |
| 2.2 | Implement topic selection | `agents/researcher/engine.py` | ☐ |
| | — LLM picks top N findings from audit, ranked by impact | | |
| 2.3 | Implement research synthesis | `agents/researcher/engine.py` | ☐ |
| | — LLM researches solutions per topic, optionally with web search | | |
| 2.4 | Implement plan formulation | `agents/researcher/engine.py` | ☐ |
| | — Structures research into PMProject schema (root cause, fix steps, effort, risk) | | |
| 2.5 | Implement push packaging | `agents/researcher/engine.py` | ☐ |
| | — Converts plans to Phase 65 PMProject/PMGoal/PMIssue | | |
| 2.6 | Create LLM prompts | `agents/researcher/prompts/` | ☐ |
| | — `topic_selection.txt`, `research_synthesis.txt`, `plan_formulation.txt` | | |
| 2.7 | Native Paperclip adapter | `agents/researcher/adapters/paperclip.py` | ☐ |
| | — Daemon thread, hooks into Pi Watchdog delta | | |
| 2.8 | Wire to Pi Agent loop | `services/pi_agent.py` | ☐ |
| | — New scenario "I: Researcher" triggered after Watchdog completes | | |
| 2.9 | Add observation categories | observation_store extension | ☐ |
| | — `agent_staffing`, `agent_custodian`, `agent_system` (alongside existing `agent_scan`, `agent_triage`) | | |

**Exit criteria:** `codrag research run` produces 3 structured research plans and can push them to Paperclip.

**Architecture decision (from Audit Opportunity 1):** Pi Agent IS the native Researcher adapter long-term. For Phase 2, we wire Researcher as a new Pi scenario. Future migration: `PiAgent` becomes a backward-compatible shim over `ResearcherEngine`.

---

## Phase 3: Digital Custodian Engine

> **Depends on:** Phase 0 (specifically `agents/shared/git_client.py`)
> **Audit ref:** Opportunity 4 (AgentConcurrencyGate multi-agent)
> **Design docs:** 03_Digital_Custodian.md

| # | Task | File | Status |
|---|------|------|--------|
| 3.1 | Create `agents/custodian/` subpackage | `agents/custodian/__init__.py` | ☐ |
| 3.2 | Implement dead code detection | `agents/custodian/engine.py` | ☐ |
| | — Query trace graph for nodes with 0 dependents | | |
| 3.3 | Implement safety verification | `agents/custodian/engine.py` | ☐ |
| | — LLM reviews each candidate: dynamic imports? reflection? config refs? public API? | | |
| | — Classify: SAFE_TO_DELETE / NEEDS_REVIEW / KEEP | | |
| 3.4 | Implement git branch operations | `agents/custodian/git_ops.py` | ☐ |
| | — Create cleanup branch, create/update archive branch | | |
| | — Archive files before deletion, commit with CoDRAG finding IDs | | |
| 3.5 | Implement archive manifest | `agents/custodian/engine.py` | ☐ |
| | — `.custodian_manifest.json` with restore instructions per entry | | |
| 3.6 | Implement cleanup push to Paperclip | `agents/custodian/engine.py` | ☐ |
| | — "Cleanup Report" project with per-file issues | | |
| 3.7 | Create LLM prompts | `agents/custodian/prompts/` | ☐ |
| | — `dead_code_analysis.txt`, `cleanup_plan.txt`, `archive_summary.txt` | | |
| 3.8 | Native Paperclip adapter | `agents/custodian/adapters/paperclip.py` | ☐ |
| 3.9 | Wire to Pi Agent loop | `services/pi_agent.py` | ☐ |
| | — New scenario "J: Custodian" triggered after Researcher | | |
| 3.10 | Extend AgentConcurrencyGate | `services/agent_gate.py` | ☐ |
| | — Add `agent_name` parameter to `can_run()` and `status()` | | |

**Exit criteria:** `codrag custodian run --dry-run` identifies dead code candidates and produces an archive plan without modifying git.

---

## Phase 4: CLI Commands

> **Depends on:** Phases 1, 2, 3 (engines must exist)
> **Audit ref:** Opportunity 10 (CLI pattern consistency)

| # | Task | File | Status |
|---|------|------|--------|
| 4.1 | `codrag hr` subcommand group | `cli.py` | ☐ |
| | — `generate`, `adopt`, `audit`, `sync` | | |
| 4.2 | `codrag research` subcommand group | `cli.py` | ☐ |
| | — `run`, `topics`, `history` | | |
| 4.3 | `codrag custodian` subcommand group | `cli.py` | ☐ |
| | — `run`, `archive`, `restore` | | |
| 4.4 | `--adapter` flag support | `cli.py` | ☐ |
| | — `native` (default), `langgraph`, `crewai` — with import error if extras not installed | | |
| 4.5 | `--dry-run` flag for all agents | `cli.py` | ☐ |

**Exit criteria:** All CLI commands from §6.1 of the implementation plan work end-to-end.

---

## Phase 5: API Endpoints

> **Depends on:** Phases 1, 2, 3 (engines must exist)

| # | Task | File | Status |
|---|------|------|--------|
| 5.1 | HR Agent endpoints | `api/routers/agents_hr.py` | ☐ |
| | — POST generate, POST audit, POST sync, GET readiness, GET roster | | |
| 5.2 | Researcher Agent endpoints | `api/routers/agents_researcher.py` | ☐ |
| | — POST run, GET topics, GET history | | |
| 5.3 | Custodian Agent endpoints | `api/routers/agents_custodian.py` | ☐ |
| | — POST run, GET archive, POST restore | | |
| 5.4 | Agent status aggregate endpoint | `api/routers/agents.py` | ☐ |
| | — GET /agents/status — returns all 3 agents' status for dashboard | | |
| 5.5 | Register routers in server.py | `server.py` | ☐ |

**Exit criteria:** All endpoints from §6.2 of the implementation plan respond correctly.

---

## Phase 6: LangGraph Adapters

> **Depends on:** Phase 0 (AgentCore), engines (1/2/3)
> **Design docs:** 02_LangGraph_CrewAI.md

| # | Task | File | Status |
|---|------|------|--------|
| 6.1 | Add `langgraph` optional dependency | `pyproject.toml` | ☐ |
| | — `langgraph>=0.2.0`, `langchain-anthropic>=0.3.0`, `langchain-ollama>=0.3.0` | | |
| 6.2 | Implement LLM provider bridge | `agents/shared/llm_bridge.py` | ☐ |
| | — Reads AI Gateway config, constructs LangChain LLM (Anthropic/Ollama/OpenAI) | | |
| 6.3 | Staffing LangGraph adapter | `agents/hr/adapters/langgraph_adapter.py` | ☐ |
| | — StateGraph: Analyze → Generate → Push | | |
| 6.4 | Researcher LangGraph adapter | `agents/researcher/adapters/langgraph_adapter.py` | ☐ |
| | — StateGraph: Ingest → Select → Research → Formulate → Push | | |
| 6.5 | Custodian LangGraph adapter | `agents/custodian/adapters/langgraph_adapter.py` | ☐ |
| | — StateGraph: Scan → Verify → Archive → Push | | |

**Exit criteria:** `codrag research run --adapter langgraph` executes the full pipeline end-to-end.

---

## Phase 7: CrewAI Adapters

> **Depends on:** Phase 0 (AgentCore), engines (1/2/3)
> **Design docs:** 02_LangGraph_CrewAI.md

| # | Task | File | Status |
|---|------|------|--------|
| 7.1 | Add `crewai` optional dependency | `pyproject.toml` | ☐ |
| | — `crewai>=0.80.0`, `crewai-tools>=0.14.0` | | |
| 7.2 | Staffing CrewAI adapter | `agents/hr/adapters/crewai_adapter.py` | ☐ |
| | — 2-agent crew: Analyst + Generator | | |
| 7.3 | Researcher CrewAI adapter | `agents/researcher/adapters/crewai_adapter.py` | ☐ |
| | — 3-agent crew: Analyst + Architect + PM | | |
| 7.4 | Custodian CrewAI adapter | `agents/custodian/adapters/crewai_adapter.py` | ☐ |
| | — 2-agent crew: Analyzer + Janitor | | |

**Exit criteria:** `codrag research run --adapter crewai` executes the full pipeline end-to-end.

---

## Phase 8: Dashboard — Agent Operations Panel (Level 1)

> **Depends on:** Phase 5 (API endpoints)
> **Audit ref:** Opportunity 9 (EventBus for status), Opportunity 11 (panel pattern)

| # | Task | File | Status |
|---|------|------|--------|
| 8.1 | Register "Agent Operations" in panelRegistry | `packages/ui/src/config/panelRegistry.ts` | ☐ |
| 8.2 | Create AgentOpsPanel (modular panel) | `packages/ui/src/components/agents/AgentOpsPanel.tsx` | ☐ |
| | — 3 compact AgentCard components (Staffing, Researcher, Custodian) | | |
| 8.3 | Create AgentCard component | `packages/ui/src/components/agents/AgentCard.tsx` | ☐ |
| | — Status badge, key metric, last run time | | |
| 8.4 | Create EmployeeBadges component | `packages/ui/src/components/agents/EmployeeBadges.tsx` | ☐ |
| | — Compact role badges with health indicators for Paperclip-managed employees | | |
| 8.5 | Create useAgentOps hook | `src/codrag/dashboard/src/hooks/useAgentOps.ts` | ☐ |
| | — Polls /agents/status, provides agent state to components | | |

**Exit criteria:** Dashboard shows Agent Operations panel with 3 compact cards + managed employee badges.

---

## Phase 9: Dashboard — Detail Overlay + AI Gateway Integration

> **Depends on:** Phase 8
> **Audit ref:** Opportunity 7 (ModelAwareness), Opportunity 11 (panel pattern)

| # | Task | File | Status |
|---|------|------|--------|
| 9.1 | Create AgentOpsDetail overlay | `packages/ui/src/components/agents/AgentOpsDetail.tsx` | ☐ |
| | — Reuses DetailOverlay pattern from ModularDashboard | | |
| 9.2 | Create SystemAgentsTab | `packages/ui/src/components/agents/SystemAgentsTab.tsx` | ☐ |
| | — Per-agent config sections, model read-only display + AI Gateway deep-link | | |
| 9.3 | Create ManagedEmployeesTab | `packages/ui/src/components/agents/ManagedEmployeesTab.tsx` | ☐ |
| | — Roster table, per-employee detail drawer (AGENTS.md, SOUL.md, RoleVector bars) | | |
| 9.4 | Add Agent Models to AI Gateway Assigned tab | `AssignedModelsPanel.tsx` (or equivalent) | ☐ |
| | — 3 new ModelSlotRow components: Staffing, Researcher, Custodian | | |
| 9.5 | Create CleanupPreview component | `packages/ui/src/components/agents/CleanupPreview.tsx` | ☐ |
| 9.6 | Create ResearchTopicList component | `packages/ui/src/components/agents/ResearchTopicList.tsx` | ☐ |
| 9.7 | Create GenerateWizard component | `packages/ui/src/components/agents/GenerateWizard.tsx` | ☐ |
| | — 3-mode selector for Staffing Agent (list/auto/auto+list) | | |

**Exit criteria:** Full detail overlay with 2 tabs. AI Gateway Assigned tab shows agent model slots.

---

## Risk Register

From the architecture audit (§6), with mitigations:

| # | Risk | Severity | Mitigation | Phase |
|---|------|----------|-----------|-------|
| R1 | Pi Agent convergence breaks pipeline callback | HIGH | Wrap-then-migrate: add scenario first, refactor later. Both paths have tests. | 2 |
| R2 | Adapter naming collision (`adapters/` vs `agents/*/adapters/`) | LOW | Module paths disambiguate. Clear naming: `codrag.adapters.paperclip_adapter` vs `codrag.agents.hr.adapters.paperclip` | 0 |
| R3 | Orchestrator.py bloat (2643 lines) | MEDIUM | Agent integration uses existing `add_completion_callback()` only. Zero new code in orchestrator. | 2, 3 |
| R4 | LangGraph/CrewAI version churn | LOW | Pin minimum versions, lazy imports, feature-detect at runtime. | 6, 7 |
| R5 | Custodian accidentally deletes live code | HIGH | 5 guardrails: dry-run default, impact verification, LLM review, archive-first, never auto-merge. | 3 |

---

## Estimated Effort

| Phase | Scope | Est. Days | Cumulative |
|-------|-------|-----------|-----------|
| 0 | Scaffolding + AgentCore | 2–3 | 2–3 |
| 1 | Staffing Agent Engine | 4–5 | 6–8 |
| 2 | Researcher Agent Engine | 3–4 | 9–12 |
| 3 | Digital Custodian Engine | 3–4 | 12–16 |
| 4 | CLI Commands | 1–2 | 13–18 |
| 5 | API Endpoints | 1–2 | 14–20 |
| 6 | LangGraph Adapters | 2–3 | 16–23 |
| 7 | CrewAI Adapters | 2–3 | 18–26 |
| 8 | Dashboard — Panel (L1) | 2–3 | 20–29 |
| 9 | Dashboard — Overlay (L2) | 3–4 | 23–33 |
| **Total** | | **23–33 days** | |

---

## Quick Reference: Key File Locations

### Existing (reuse as-is)
| What | Where |
|------|-------|
| PM push pipeline | `src/codrag/adapters/push_engine.py` |
| Paperclip REST client | `src/codrag/adapters/paperclip_adapter.py` |
| PM data models | `src/codrag/adapters/pm_models.py` |
| Pi Agent (daemon) | `src/codrag/services/pi_agent.py` |
| Concurrency gate | `src/codrag/services/agent_gate.py` |
| Agent scope manager | `src/codrag/core/agent_scope_manager.py` |
| Opportunity manager | `src/codrag/core/audit/opportunity_manager.py` |
| ActionItem model | `src/codrag/core/audit/action_item.py` |
| Settings store | `src/codrag/services/settings_store.py` |
| Observation store | `src/codrag/services/observation_store.py` |
| LLM client | `src/codrag/core/llm_client.py` |
| Event bus | `src/codrag/core/events.py` |

### New (to be created)
| What | Where |
|------|-------|
| AgentCore | `src/codrag/agents/core.py` |
| Shared models | `src/codrag/agents/shared/models.py` |
| CoDRAG data wrapper | `src/codrag/agents/shared/codrag_data.py` |
| Paperclip client wrapper | `src/codrag/agents/shared/paperclip_client.py` |
| Git client | `src/codrag/agents/shared/git_client.py` |
| LLM bridge (LangChain) | `src/codrag/agents/shared/llm_bridge.py` |
| Staffing engine | `src/codrag/agents/hr/engine.py` |
| Researcher engine | `src/codrag/agents/researcher/engine.py` |
| Custodian engine | `src/codrag/agents/custodian/engine.py` |
| Custodian git ops | `src/codrag/agents/custodian/git_ops.py` |

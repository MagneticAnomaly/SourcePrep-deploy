# Phase 67 — Architecture Audit: Prep Infrastructure Alignment

> **Phase 67 Research** | Date: 2026-04-01
> Comprehensive audit of Prep's existing codebase to identify reuse opportunities, dependency risks, and the optimal integration strategy for the agent subsystem.

---

## 1. Methodology

This audit was conducted using Prep's own structural intelligence tools:
- `prep()` — Module structure, hub files, focus areas
- `prep_search()` — Semantic search for infrastructure patterns
- `prep_audit()` — Architecture category scan (100 findings)
- `prep_impact()` — Dependency analysis on key integration points
- Direct file inspection of `adapters/`, `services/`, `a2a/`, `core/` packages

---

## 2. Infrastructure Inventory

### 2.1 Existing Packages Relevant to Agent Integration

| Package | Phase | Purpose | Files | Lines |
|---------|-------|---------|-------|-------|
| `adapters/` | 65 | PM push infrastructure (Paperclip REST) | 5 | ~1,650 |
| `a2a/` | 63 | Agent-to-Agent protocol (JSON-RPC 2.0) | 3 | ~410 |
| `services/agent_gate.py` | 66 | Agent concurrency gate | 1 | 153 |
| `services/pi_agent.py` | 66 | Proactive Intelligence daemon (7 scenarios) | 1 | 1,171 |
| `services/scope_orchestrator.py` | 24 | Knowledge Scope rebuild pipeline | 1 | 383 |
| `services/settings_store.py` | core | JSON-backed config singleton | 1 | ~400 |
| `services/observation_store.py` | 39 | Cross-session memory | 1 | ~600 |
| `core/llm_client.py` | core | Universal LLM client | 1 | ~500 |
| `core/model_awareness.py` | 44C | Model lifecycle state machine | 1 | ~400 |
| `core/audit/` | 65 | OpportunityManager, ActionItem, Consolidator | ~5 | ~2,000 |
| `core/events.py` | 24 | SSE EventBus | 1 | ~200 |

### 2.2 Zero-Change Zones (Must NOT Modify)

| Component | Reason |
|-----------|--------|
| `mcp/server.py` (2427 lines) | Primary product surface — 5 MCP tools |
| `core/index.py` (1843 lines) | CodeIndex is the foundation |
| `core/atlas/generator.py` (1729 lines) | Atlas generation pipeline |
| `adapters/paperclip_adapter.py` | Already production-ready, reused as-is |
| `adapters/push_engine.py` | Already production-ready, reused as-is |

---

## 3. Twelve Integration Opportunities

### Opportunity 1: Pi Agent → Researcher Agent Convergence

**Status:** CRITICAL ARCHITECTURAL DECISION

`services/pi_agent.py` (Phase 66) runs 7 scenarios that map directly to the Researcher Agent's planned capabilities:

| Pi Scenario | Researcher Capability |
|------------|----------------------|
| Watchdog (delta scan) | Tech Debt Prospector (change detection) |
| Doctor (index integrity) | Security Analyst (system health) |
| Geologist (drift) | Architecture drift detection |
| Dispatcher (triage) | Issue prioritization |
| Librarian (cleanup) | Observation hygiene |
| Architect (assessment) | Architecture proposals |
| Scholar (quality) | Enrichment monitoring |

**Decision:** Pi Agent IS the native Researcher adapter. `services/pi_agent.py` becomes a backward-compatible shim that delegates to `agents/researcher/engine.py`.

**Migration path:**
1. Create `agents/researcher/engine.py` with `ResearcherEngine` class
2. Move scenario implementations gradually (one at a time)
3. `services/pi_agent.py` becomes: `class PiAgent(ResearcherEngine): pass`
4. Existing pipeline callback `pi.on_pipeline_complete(group)` continues working

---

### Opportunity 2: PushEngine Reuse

**Status:** ZERO NEW PM CODE NEEDED

The existing push pipeline at `adapters/push_engine.py`:
```
ActionItems → PushEngine.push() → Consolidator → PaperclipAdapter → REST API
```

Already supports:
- Priority filtering (`min_priority="P2"`)
- Category exclusion
- Dry-run mode
- Deduplication (Prep addresses embedded in descriptions)
- Push history recording

**Decision:** `AgentCore.push_to_pm()` calls `adapters.push_engine.create_push_engine(config)`. No new Paperclip client code is needed.

---

### Opportunity 3: Focus Scope Engine Placement

**Status:** KEY ARCHITECTURAL FIX

The Focus Scope Engine (`scope_engine.py`) suggests which files are relevant to a natural-language focus description. It benefits:
- **IDE users:** "I'm working on authentication" → get relevant files
- **Agent roles:** Auto-populate knowledge scope for a CTO role

**Wrong placement:** `agents/shared/scope_engine.py`
- This would create a backward dependency: `services/` → `agents/`
- Breaks the rule: agents CONSUME services, services are NOT aware of agents

**Correct placement:** `services/scope_engine.py`
- Adjacent to `services/scope_orchestrator.py` (same domain: scope management)
- Both IDE users and agents call it through the service layer
- No dependency direction violations

---

### Opportunity 4: AgentConcurrencyGate for Multi-Agent

**Current:** Gate tracks one active agent task at a time.
**Needed:** Track which agent (staffing, researcher, custodian) is running.

Extension is minimal — add `agent_name` parameter to `can_run()` and `status()`. The existing `task_name` parameter remains for scenario-level tracking.

---

### Opportunity 5: Settings Store for Agent Config

**Decision:** Agent configuration lives under `agents_config` in the existing `settings_store` JSON blob.

Benefits:
- Dashboard settings API already serves this store
- No new config files or config mechanism
- Type-safe keys with defaults
- Per-agent enable/disable from the dashboard

---

### Opportunity 6: A2A Protocol Extensibility (Future)

The existing A2A handler's `_execute_skill()` method uses a dict of handlers:
```python
handlers = {
    "codebase-context": self._skill_context,
    "opportunity-discovery": self._skill_opportunities,
    ...
}
```

Phase 67 should NOT modify this — but the architecture allows future extension by adding agent skills to this dict.

---

### Opportunity 7: ModelAwareness Integration

Agent model assignments should register as task IDs in the existing `ModelAwareness` system:
- `model_awareness.acquire("agent_staffing")` — uses the assigned model
- Model assignments configured in AI Gateway's Assigned tab
- No separate model management for agents

---

### Opportunity 8: Observation Categories

Extend the observation store with agent-specific categories:
- `agent_scan` (already used by Pi)
- `agent_triage` (already used by Pi)
- `agent_staffing` (NEW)
- `agent_custodian` (NEW)
- `agent_system` (NEW)

---

### Opportunity 9: Event Bus for Agent Status

The existing `core/events.py` EventBus supports SSE push. Agent status changes emit through the same bus for real-time dashboard updates.

---

### Opportunity 10: CLI Pattern Consistency

Agent CLI commands follow the existing Click group pattern. New command groups: `hr`, `research`, `custodian`, `scope`.

---

### Opportunity 11: Dashboard Panel Pattern

Agent Operations is ONE panel with compact cards, consistent with existing panel pattern (Pipeline, AI Gateway).

---

### Opportunity 12: Optional Dependency Isolation

LangGraph and CrewAI are optional extras:
```toml
[project.optional-dependencies]
agents = ["langchain-core>=0.3", "langgraph>=0.3"]
crewai = ["crewai>=0.80"]
```

---

## 4. Dependency Direction Rules

```
agents/  →  services/  →  core/
agents/  →  adapters/

FORBIDDEN:
services/ → agents/
core/     → agents/  
adapters/ → agents/
mcp/      → agents/
```

**Enforcement:** Every module in `agents/` can be deleted without breaking any other package. This is the "additive-only" guarantee.

---

## 5. Scalability Analysis

### 5.1 File Count

| Package | Before Phase 67 | After Phase 67 | Growth |
|---------|-----------------|----------------|--------|
| `agents/` | 0 | ~25 | NEW |
| `services/` | 24 | 25 | +1 (scope_engine) |
| `adapters/` | 5 | 5 | 0 |
| `api/routers/` | existing | +4 | +4 (hr, research, custodian, scope) |
| `cli.py` | 1 | 1 | Modified only |
| **Total** | 1143 | ~1173 | +2.6% |

### 5.2 Import Cost

| Import | Cold Time | Lazy? |
|--------|----------|-------|
| `agents.core.AgentCore` | ~5ms | No (core) |
| `agents.hr.engine.StaffingEngine` | ~10ms | No (core) |
| `agents.hr.adapters.langgraph_adapter` | ~500ms+ | Yes (only on use) |
| `agents.hr.adapters.crewai_adapter` | ~300ms+ | Yes (only on use) |

---

## 6. Three Critical Risks

### Risk 1: Pi Agent Convergence

**Risk:** Refactoring Pi (1171 lines) into ResearcherEngine could break the pipeline completion callback.

**Mitigation:** Wrap-then-migrate. Phase 3 creates a wrapper; scenarios are moved one at a time. Both old and new paths have unit tests during migration.

### Risk 2: Adapter Naming Collision

**Risk:** `adapters/` = PM push, `agents/hr/adapters/` = orchestration. Different meanings.

**Mitigation:** Names are clear in context. Module paths disambiguate: `prep.adapters.paperclip_adapter` vs `prep.agents.hr.adapters.native`.

### Risk 3: Orchestrator Growth

**Risk:** `pipeline/orchestrator.py` is already 2643 lines. Agent hooks could bloat it further.

**Mitigation:** All agent integration uses the existing `add_completion_callback()` — zero new code in orchestrator. Agents are notified, never modify the pipeline.

---

## 7. Summary

The audit confirms that Prep's existing infrastructure provides **80%+ of the infrastructure** the agent subsystem needs. Key reuse points:

- PaperclipAdapter + PushEngine → zero new PM code
- AgentConcurrencyGate → extend, don't rebuild
- PiAgent → refactor into ResearcherEngine
- ScopeOrchestrator → co-locate Focus Scope Engine in `services/`
- SettingsStore → agent config namespace
- EventBus → agent status SSE events
- LLMClient → agent LLM calls

The remaining ~20% is truly new code:
- Agent-specific engines (Staffing, Custodian)
- Orchestrator adapters (LangGraph, CrewAI)
- Dashboard panel + overlays
- CLI command groups

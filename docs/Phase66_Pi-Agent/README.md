# Phase 66 — Pi Agent & OpenCode Integration

> **Build Status:** ✅ Complete  
> **Depends On:** Phase 62 (research), Phase 63 (Opportunities), Phase 64 (A2A protocol), Phase 65 (finding collapse)  
> **Started:** 2026-03-31

---

## Overview

Phase 66 implements CoDRAG's **autonomous agent layer** — background intelligence that runs analysis automatically, without human intervention. Two agent systems work in concert:

| Agent | Type | Scenarios | Trigger |
|-------|------|-----------|---------|
| **Pi** | In-process daemon thread | 7 background intelligence scenarios | Auto (after pipeline) + scheduled |
| **OpenCode** | External CLI agent | 1 code review scenario | On-demand (pre-commit) |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    CoDRAG Daemon (FastAPI)                     │
│                                                                │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────┐  │
│  │ HTTP Server  │   │  Watcher     │   │ Pipeline Orch.    │  │
│  │ (FastAPI)    │   │  (watchdog)  │   │ (11-stage)        │  │
│  └──────┬──────┘   └──────┬───────┘   └────────┬──────────┘  │
│         │                  │                     │              │
│         │           on_watch_start()     on_group_complete()   │
│         │                  │                     │              │
│         │           ┌──────▼─────────────────────▼──────────┐  │
│         │           │           Pi Agent                     │  │
│         │           │  ─────────────────────────────────     │  │
│         │           │  A: Watchdog   — delta scan (~80s)     │  │
│         │           │  B: Doctor     — integrity check (~40s)│  │
│         │           │  C: Geologist  — drift detect (~2min)  │  │
│         │           │  D: Dispatcher — smart triage (~2min)  │  │
│         │           │  E: Librarian  — obs cleanup (~1min)   │  │
│         │           │  G: Architect  — proposals (~9min)     │  │
│         │           │  H: Scholar    — quality audit (~80s)  │  │
│         │           │                                        │  │
│         │           │  ↕ Uses:                               │  │
│         │           │  • AgentConcurrencyGate (defers to     │  │
│         │           │    pipeline during LLM stages)         │  │
│         │           │  • CoDRAG's LLMClient (safety guards)  │  │
│         │           │  • codrag_observe (cross-session mem)  │  │
│         │           │  • run_audit() (pure Python, ~5s)      │  │
│         │           └────────────────────────────────────────┘  │
│         │                                                       │
│         └──── GET /pipeline/status ──→ { "agent": {...} }      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         ▲                                              
         │ MCP (codrag tools)                           
         │                                              
┌────────┴────────────────────────────────────────────┐
│              OpenCode (external CLI)                  │
│                                                       │
│  F: Reviewer — git-aware code review prep             │
│  Uses: codrag_impact, codrag_audit, codrag_search     │
│  Config: .opencode/opencode.json + prompts/           │
└──────────────────────────────────────────────────────┘
```

---

## File Inventory

### New Files (Phase 66)

| File | Lines | Purpose |
|------|-------|---------|
| `src/codrag/services/agent_gate.py` | ~140 | Concurrency gate preventing agent–pipeline GPU contention |
| `src/codrag/services/pi_agent.py` | ~1100 | Pi agent core with all 7 scenarios |
| `.opencode/opencode.json` | ~20 | OpenCode MCP config for reviewer agent |
| `.opencode/prompts/reviewer.txt` | ~30 | Reviewer agent system prompt |
| `docs/Phase66_Pi-Agent/README.md` | this file | Design documentation |

### Modified Files

| File | Change | Phase |
|------|--------|-------|
| `src/codrag/services/pipeline/orchestrator.py` | Added `on_pipeline_complete` Pi callback | Sprint 1 |
| `src/codrag/api/routers/projects/watch.py` | Added `init_pi_agent()` on watcher start | Sprint 1 |
| `src/codrag/api/routers/pipeline.py` | Added `"agent"` key to pipeline status API | Sprint 1 |
| `packages/ui/src/types.ts` | Added `AgentStatus`, `AgentGateStatus`, `agent` on `PipelineStatus` | Sprint 4 |
| `packages/ui/src/index.ts` | Exported `AgentStatus`, `AgentGateStatus`, `AgentStatusData` | Sprint 4 |
| `packages/ui/src/components/audit/index.ts` | Re-exported `AgentStatusData` | Sprint 4 |
| `packages/ui/src/components/audit/OpportunitiesPanel.tsx` | Added `AgentStatusBanner` + `agentStatus` prop | Sprint 4 |
| `src/codrag/dashboard/src/hooks/useOpportunitiesSystem.ts` | Added agent status polling (30s) | Sprint 4 |
| `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` | Wired `agentStatus` prop to panel | Sprint 4 |

---

## Design Decisions

### D1: Daemon Thread, Not Separate Process
Pi runs as a `threading.Thread(daemon=True)` inside the CoDRAG FastAPI server. This means:
- **Direct Python imports** — no MCP serialization overhead for audit/observe
- **Shared LLMClient** — inherits OutputMonitor, CloudRateLimitError handling, JSON repair
- **Automatic token telemetry** — all agent LLM calls tracked in dashboard
- **No process management** — no PID files, no zombie cleanup, no IPC

### D2: Agent Concurrency Gate
The `AgentConcurrencyGate` uses a two-check strategy:
1. **Pipeline check** — scans `pipeline_orchestrator._runs` for active LLM stages (2,3,6-9)
2. **Agent lock** — only one agent task at a time (prevents agent–agent GPU contention)

**Fail-open** — if pipeline status can't be checked (import error, etc.), agents proceed. Better to occasionally run during idle pipeline time than to never run.

### D3: Batch Size Guards
Every scenario has an explicit `MAX_FINDINGS_PER_CALL = 200` guard. Agent scenarios work with pre-aggregated `ActionItem` lists (50-200 items after Phase 65's collapsing pass), never raw graph nodes (5,000+).

### D4: Both Observe AND Opportunities
Per user decision: Pi writes to `codrag_observe` (cross-session memory for agents) AND surfaces findings via the pipeline status API (for the dashboard Opportunities panel).

### D5: No New Model Slot for Now
Per user decision: Pi reuses the existing model infrastructure. In the Assigned Tab of AI Gateway, each of the 8 scenarios can be mapped to any existing model using the same assignment UI already built.

### D6: Cooldown Timers
Every scenario has a cooldown (`agent_cooldown_seconds`, default 300s) to prevent hot-loops:
- Watchdog fires → finds issues → pipeline rebuilds → Watchdog fires again
- With cooldown: Watchdog runs, waits 5 minutes regardless of pipeline activity

---

## Scenarios Reference

### A: Watchdog — Continuous Health Monitor
| Property | Value |
|----------|-------|
| **Trigger** | `on_pipeline_complete()` (automatic) |
| **CoDRAG tools** | `run_audit()` (~5s), `codrag_observe` |
| **LLM calls** | 0 (structured delta, no synthesis needed) |
| **Total time** | ~5-10s |
| **What it does** | Compares current audit scan to baseline, computes delta (new/resolved), saves observation |

### B: Doctor — Index Integrity Check
| Property | Value |
|----------|-------|
| **Trigger** | Scheduled (daily) or on-demand |
| **CoDRAG tools** | `run_audit()`, pipeline status API |
| **LLM calls** | 1 call (~35s local) for integrity assessment |
| **Total time** | ~40s |
| **What it does** | Checks for orphaned nodes, broken edges, stale data. Recommends rebuild if needed |

### C: Geologist — Architecture Drift Detection
| Property | Value |
|----------|-------|
| **Trigger** | Weekly schedule |
| **CoDRAG tools** | `codrag()` (atlas), `codrag_observe` |
| **LLM calls** | 1 call (~120s local) for drift analysis |
| **Total time** | ~2min |
| **What it does** | Compares current atlas to previous snapshot, detects module boundary shifts |

### D: Dispatcher — Smart Triage
| Property | Value |
|----------|-------|
| **Trigger** | When findings exceed threshold (default 50) |
| **CoDRAG tools** | `run_audit()`, `codrag_impact()` × top 10 |
| **LLM calls** | 0 (pure graph analysis for root cause grouping) |
| **Total time** | ~7-10s |
| **What it does** | Groups top findings by shared impacted files, identifies root causes |

### E: Librarian — Observation Cleanup
| Property | Value |
|----------|-------|
| **Trigger** | Weekly schedule |
| **CoDRAG tools** | `codrag_observe` |
| **LLM calls** | 0 (checks file existence, staleness flags) |
| **Total time** | ~1-2s |
| **What it does** | Counts stale and orphaned observations, logs cleanup summary |

### F: Reviewer — Code Review Prep (OpenCode)
| Property | Value |
|----------|-------|
| **Trigger** | Manual: `opencode run --agent reviewer "..."` |
| **CoDRAG tools** | `codrag_impact`, `codrag_audit`, `codrag_search` (via MCP) |
| **LLM calls** | 1 call via OpenCode's own LLM client |
| **Total time** | ~1.5min local / ~20s cloud |
| **What it does** | Runs blast radius analysis on changed files, synthesizes review brief |

### G: Architect — Architecture Proposals
| Property | Value |
|----------|-------|
| **Trigger** | Monthly schedule or on-demand |
| **CoDRAG tools** | `codrag()`, `run_audit()`, `codrag_audit(action="report")` |
| **LLM calls** | 2-3 calls (~500s local total) |
| **Total time** | ~9min local / ~1.5min cloud |
| **What it does** | Analyzes codebase structure, proposes refactoring based on architectural patterns |

### H: Scholar — Enrichment Quality Monitoring
| Property | Value |
|----------|-------|
| **Trigger** | After deep enrichment completes |
| **CoDRAG tools** | `run_audit()`, `codrag_search` |
| **LLM calls** | 1 call (~74s local) |
| **Total time** | ~80s |
| **What it does** | Checks enrichment quality (missing descriptions, low-confidence tags), logs gaps |

---

## Configuration

### Settings Store Keys

```json
{
  "pipeline_config": {
    "agent_enabled": false,
    "agent_auto_scan": true,
    "agent_cooldown_seconds": 300,
    "agent_triage_threshold": 50
  }
}
```

### Enable Pi Agent
1. Open CoDRAG Dashboard → AI Gateway panel
2. Toggle "Agent" → enabled
3. Start the file watcher for your project (or restart if already running)
4. Pi initializes automatically and attaches to pipeline completion events

---

## API

### Pipeline Status (augmented with agent data)

`GET /projects/{project_id}/pipeline/status`

```json
{
  "fast_sync": { ... },
  "deep_enrichment": { ... },
  "stages": { ... },
  "agent": {
    "enabled": true,
    "auto_scan": true,
    "cooldown_seconds": 300,
    "running_task": null,
    "last_scan_at": "2026-03-31T04:30:00Z",
    "last_scan_delta": {
      "new_findings": [...],
      "resolved_findings": [...],
      "unchanged_count": 42
    },
    "gate": {
      "agent_active": false,
      "active_task": null,
      "held_for_s": null
    }
  }
}
```

---

## Sprint Log

### Sprint 1: Foundation ✅ (2026-03-31)
- Created `agent_gate.py` — concurrency gate with pipeline awareness
- Created `pi_agent.py` — Pi agent core with Watchdog, Librarian, Dispatcher
- Wired orchestrator completion callback (`on_pipeline_complete`)
- Wired watcher startup (`init_pi_agent`)
- Added agent status to pipeline API response
- Verified: all imports clean, no circular deps, syntax OK

### Sprint 2: Remaining Scenarios ✅ (2026-03-31)
- Implemented Scenario B: Doctor (index integrity check — manifest, file existence, critical findings)
- Implemented Scenario C: Geologist (architecture drift — atlas module snapshot comparison)
- Implemented Scenario G: Architect (architecture assessment — module count, hub files, findings per module)
- Implemented Scenario H: Scholar (enrichment quality — augmentation/epistemic coverage percentages)
- Fixed Scholar gate.release() lint error (missing `finally` block)
- All 7 scenarios verified: compile OK, methods exist

### Sprint 3: OpenCode + Documentation ✅ (2026-03-31)
- Created `.opencode/opencode.json` — MCP config connecting OpenCode to CoDRAG
- Created `.opencode/prompts/reviewer.txt` — Reviewer agent system prompt
- Created `docs/Phase66_Pi-Agent/README.md` — comprehensive design doc (this file)
- All cross-references validated

### Sprint 4: Dashboard UI ✅ (2026-03-31)
- Added `AgentStatus` + `AgentGateStatus` interfaces to `types.ts`
- Added `agent?: AgentStatus` field to `PipelineStatus` interface
- Exported new types from `@codrag/ui` package barrel
- Created `AgentStatusBanner` component in OpportunitiesPanel (violet Cpu icon, delta badges)
- Added `agentStatus` prop to `OpportunitiesPanelProps`
- Added 30s agent status polling in `useOpportunitiesSystem.ts`
- Wired `agentStatus` prop through `useDashboardPanels.tsx`
- Verified: `tsc --noEmit` passes clean, `py_compile` passes clean

### Sprint 5: Code Audit & Bug Fixes ✅ (2026-03-31)
- 🚨 BUG 1: Fixed `from codrag.mcp.tool_observe import _obs_store` → `from codrag.services.observation_store import observation_store` (module didn't exist, all obs I/O was silently failing)
- 🚨 BUG 2: Fixed `.get()` → `.get_for_query()` / `.get_recent()` (wrong method names for `ObservationStore`)
- 🚨 BUG 3: Fixed `category="agent_scan"` → `category="note"` (invalid category, only `note/decision/bug/pattern/assumption` accepted)
- 🚨 BUG 4: Fixed `from codrag.mcp.tool_impact import _run_impact` → `TraceIndex.get_impact_graph()` (module didn't exist, Dispatcher impact analysis never ran)
- 🚨 BUG 5: Fixed `getattr(f, "id")` → `getattr(f, "finding_id")` and `getattr(f, "files")` → `getattr(f, "file_paths")` (wrong `AuditFinding` field names)
- Also fixed: `_get_previous_scan_summary()` now strips `[pi_scan_baseline]` tag before JSON parse
- Also fixed: `_compute_delta()` previous_keys now uses `.get("analyzer", "")` for safety
- Verified: `py_compile` passes clean, `tsc --noEmit` passes clean

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| [Phase 62 Doc 11: Autonomous Agent Scenarios](../Phase62_Pi-research/11_Autonomous_Agent_Scenarios.md) | Research that led to this implementation |
| [Phase 62 Doc 08: Dual Agent Architecture](../Phase62_Pi-research/08_Dual_Agent_Architecture.md) | Pi + OpenCode coexistence design |
| [Phase 62 Doc 10: Universal Adapter](../Phase62_Pi-research/10_Universal_Adapter_Architecture.md) | A2A protocol that Pi uses |
| [Phase 63: Opportunity Console](../Phase63_Opportunity-Console/README.md) | WHERE agent findings surface |
| [Phase 64: Agent Prep](../Phase64_prep-for-agents+paperclip/02_Role_Composition_Engine.md) | Role composition Pi uses |
| [AGENTIC_INTEGRATION_GUIDE.md](../AGENTIC_INTEGRATION_GUIDE.md) | External-facing agent documentation |

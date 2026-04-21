# 02: Hybrid MCP + Lightweight Plugin Architecture

> **Phase 67 — Prep ↔ Paperclip Integration** | Last updated: 2026-04-05
> **Status**: Source of truth. Supersedes `01_Integration_Research.md`.

This is the definitive architectural specification for how Prep integrates with [Paperclip](https://paperclip.ing). It covers the protocol split, what's already built, the "dummy profile" pattern for system agents, and the forward roadmap.

---

## 1. Core Philosophy

Prep is a **headless intelligence engine**. It does not own UI real estate inside Paperclip. It provides answers when asked (Pull), and pushes data when appropriate (Push).

Three principles govern every integration decision:

1. **MCP is the universal standard for agent capabilities.** Paperclip natively supports MCP servers. We do not proxy our tools through custom plugin RPC — agents connect to our MCP endpoint directly.
2. **Workflow orchestration is push-based REST.** Creating tickets, syncing agent profiles, and reacting to lifecycle events are one-way writes via Paperclip's REST API.
3. **No UI injection.** Prep will never register `ui.dashboardWidget`, `ui.detailTab`, or settings pages inside Paperclip. Users who need the full cluster visualization, trace explorer, or architecture diagram use the Prep dashboard.

---

## 2. The Two Layers of Integration

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Paperclip Instance                           │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ Agent:     │  │ Agent:     │  │ Agent:     │  │ Agent:       │  │
│  │ Frontend   │  │ Backend    │  │ DevOps     │  │ Prep       │  │
│  │ Engineer   │  │ Engineer   │  │            │  │ Researcher   │  │
│  │            │  │            │  │            │  │ (paused)     │  │
│  │ adapter:   │  │ adapter:   │  │ adapter:   │  │ adapter: -   │  │
│  │ claude     │  │ gemini     │  │ codex      │  │ (dummy)      │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └──────────────┘  │
│        │               │               │                            │
│        │  MCP Connection (Pull)        │                            │
│        ▼               ▼               ▼                            │
│  ┌─────────────────────────────────────────┐                        │
│  │   Prep MCP Server (stdio/SSE)        │ ◄── Native connection  │
│  │   5 tools + role-based filtering       │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                     │
│                    REST API (Push)                                   │
│                         ▲                                           │
└─────────────────────────┼───────────────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────────────┐
│                   Prep Daemon                                     │
│                         │                                           │
│  ┌──────────────────────┴──────────────────────────┐                │
│  │           PaperclipAdapter (REST Client)        │                │
│  │   Projects · Goals · Issues · Agent CRUD        │                │
│  └──────────────┬──────────────┬───────────────────┘                │
│                 │              │                                     │
│  ┌──────────────▼──┐  ┌───────▼────────┐  ┌───────────────────┐    │
│  │  PushEngine     │  │ StaffingEngine │  │  ResearcherEngine │    │
│  │  (Phase 65)     │  │ (HR Agent)     │  │  (Researcher)     │    │
│  │  consolidate →  │  │ generate →     │  │  select topics →  │    │
│  │  push issues    │  │ push profiles  │  │  research →       │    │
│  └─────────────────┘  └────────────────┘  │  push plans       │    │
│                                           └───────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              AgentCore (Unified Facade)                     │    │
│  │  Prep data read · LLM access · Paperclip write · Git     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### A. The "Pull" Layer: Prep MCP Server (Primary)

**Protocol**: Model Context Protocol (stdio or SSE transport)
**What Paperclip agents consume**:

| Tool | Purpose |
|------|---------|
| `prep` | Codebase overview — modules, hub files, focus areas |
| `prep_search` | Semantic code search with structural trace expansion |
| `prep_impact` | Dependency/dependent analysis before changes |
| `prep_audit` | Codebase health findings, refactoring context |
| `prep_observe` | Cross-session memory for agent notes |

All tools accept an optional `role` parameter for scoped results. When a Paperclip "Frontend Engineer" agent calls `prep(role="frontend")`, the MCP server filters the atlas to drop backend modules and prioritize UI components.

**No plugin involvement.** This layer is pure MCP — Paperclip connects to the Prep server the same way any MCP-compatible host does.

### B. The "Push" Layer: Python REST Adapter (Secondary)

**Protocol**: HTTP REST via `PaperclipAdapter` (stdlib `urllib`)
**What Prep pushes proactively**:

| Capability | Component | What it does |
|---|---|---|
| **Health Finding Sync** | `PushEngine` + `Consolidator` | Consolidates `ActionItem`s by category/module, maps to Projects/Goals/Issues, deduplicates via `prep_address` |
| **Agent CRUD** | `StaffingEngine.push_to_paperclip()` | Creates/updates Paperclip agent profiles from Prep-generated `RoleSpec`s |
| **Research Plans** | `ResearcherEngine.package_for_push()` | Converts research plans into Paperclip Issues with root cause, fix steps, effort/risk |
| **Cleanup Plans** | `CustodianEngine.package_for_push()` | Converts cleanup candidates into removal Issues |

---

## 3. The "Dummy Profile" Pattern

Prep's three system agents (Staffing, Researcher, Custodian) run **entirely within the Prep daemon**. They use whatever LLM the user configures in the AI Gateway (Ollama/Kimi, Claude, Gemini, etc.). Paperclip never executes them.

But we still want them to appear in Paperclip's UI as "employees" who author tickets. The solution:

### How It Works

1. **Create a Paperclip agent** via `POST /api/companies/{id}/agents` with the Prep Staffing Engine.
2. **Immediately pause it** via `POST /api/agents/{id}/pause`. This freezes Paperclip's heartbeat scheduler so it never tries to invoke the agent.
3. **Set the `authorId`** on all pushed Issues/Projects to this dummy agent's ID. In the Paperclip UI, the "Prep Researcher" employee appears to be authoring brilliant tech-debt tickets.

### Why "Paused" Instead of Null Adapter

A paused agent is a first-class Paperclip concept. It shows up correctly in org charts, has a proper status badge, and can be resumed if the user ever wants Paperclip to take over execution. A null adapter would be a hack that might confuse the Paperclip runtime.

### Agent Profile Details

| Field | Staffing Agent | Researcher Agent | Custodian Agent |
|-------|---------------|-----------------|-----------------|
| `name` | Prep Staffing | Prep Researcher | Prep Custodian |
| `role` | `prep_staffing` | `prep_researcher` | `prep_custodian` |
| `title` | Role Architect | Technical Researcher | Maintenance Lead |
| `status` | paused | paused | paused |
| `adapterType` | `process` | `process` | `process` |

---

## 4. What's Already Built

Every major component exists and is operational:

### Agent Infrastructure

| Component | File | Lines | Status |
|---|---|---|---|
| AgentCore facade | `src/prep/agents/core.py` | 358 | ✅ Complete |
| StaffingEngine | `src/prep/agents/hr/engine.py` | 711 | ✅ Complete |
| ResearcherEngine | `src/prep/agents/researcher/engine.py` | 291 | ✅ Complete |
| CustodianEngine | `src/prep/agents/custodian/engine.py` | 219 | ✅ Complete |
| LLM Bridge (LangChain) | `src/prep/agents/shared/llm_bridge.py` | 114 | ✅ Complete |
| Shared models | `src/prep/agents/shared/models.py` | 190+ | ✅ Complete |

### Paperclip REST Layer

| Component | File | Lines | Status |
|---|---|---|---|
| PaperclipAdapter | `src/prep/adapters/paperclip_adapter.py` | 413 | ✅ Complete |
| PushEngine | `src/prep/adapters/push_engine.py` | 296 | ✅ Complete |
| PM Models | `src/prep/adapters/pm_models.py` | 200+ | ✅ Complete |
| PaperclipClient wrapper | `src/prep/agents/shared/paperclip_client.py` | 150 | ✅ Complete |

### API & MCP

| Component | File | Lines | Status |
|---|---|---|---|
| Agent API Router | `src/prep/api/routers/agents.py` | 632 | ✅ 12 endpoints |
| MCP Server | `src/prep/mcp/server.py` | 105K | ✅ 5 tools + role param |
| MCP Config Generator | `src/prep/mcp_config.py` | 230 | ✅ 8 IDE targets + workspace installer |
| MCP Setup API | `src/prep/api/routers/mcp_setup.py` | 170 | ✅ Install/uninstall/status endpoints |
| Paperclip Discovery Probe | (in agents.py) | ~80 | ✅ Health + company + plugin detection |

---

## 5. What We Explicitly Dropped

1. **Host UI Extensions** — No `ui.dashboardWidget`, `ui.detailTab`, or settings pages injected into Paperclip. Prep's 8,000-file cluster visualization stays in the Prep dashboard.
2. **Tool Proxying via Plugin RPC** — We do not wrap `prep_search` inside Paperclip's `executeTool` plugin SDK. MCP handles this natively and better.
3. **Prep as a Paperclip Adapter** — Prep is not an execution engine for Paperclip's heartbeat scheduler. Our agents run internally and puppet paused profiles instead.

---

## 6. Roadmap: The `@prep/paperclip-plugin` npm Package

The Python REST adapter handles all current push workflows. A future TypeScript npm package will unlock **event hooks** — reacting to things that happen inside Paperclip's UI:

### Planned Event Hooks

| Hook | Trigger | Action |
|------|---------|--------|
| `agent.created` | User creates a new agent in Paperclip | Auto-populate Knowledge Scope from Prep module atlas |
| `issue.assigned` | Issue assigned to a Prep-managed agent | Inject fresh `prep_search` context into the issue description |
| `project.created` | New project created | Auto-link to matching Prep module segment |

### Package Scope (When Built)

```
@prep/paperclip-plugin/
  src/
    index.ts          # createServerAdapter() entry point
    server/
      execute.ts      # Event hook handler (not an LLM adapter)
      test.ts         # Prep daemon connectivity check
    ui/
      build-config.ts # Prep URL + project ID config form
```

**Priority**: Low. The Python adapter covers all proactive push workflows. The npm package adds value only when we need to react to Paperclip-initiated events.

---

## 7. Connection Topology at Runtime

```
User's Machine
├── Prep Daemon (Python, port 45678)
│   ├── FastAPI Server
│   │   ├── /projects/{id}/agents/* (12 endpoints)
│   │   └── /projects/{id}/opportunities/push
│   ├── MCP Server (stdio or SSE transport)
│   │   └── 5 tools: prep, prep_search, prep_impact, prep_audit, prep_observe
│   ├── Agent Engines (background threads)
│   │   ├── StaffingEngine  → runs locally, pushes RoleSpecs to Paperclip REST
│   │   ├── ResearcherEngine → runs locally, pushes ResearchPlans to Paperclip REST
│   │   └── CustodianEngine  → runs locally, pushes CleanupPlans to Paperclip REST
│   └── PaperclipAdapter (HTTP client)
│       └── → Paperclip REST API (localhost:3100)
│
├── Paperclip Instance (Node.js, port 3100)
│   ├── Agent: Frontend Engineer (adapter: claude_local)
│   │   └── MCP connection → Prep MCP Server
│   ├── Agent: Backend Engineer (adapter: gemini_local)
│   │   └── MCP connection → Prep MCP Server
│   ├── Agent: Prep Researcher (adapter: process, status: PAUSED)
│   │   └── (no execution — dummy profile, authored by Prep daemon)
│   └── REST API
│       └── ← PaperclipAdapter writes Projects/Goals/Issues/Agents
│
└── Ollama / Cloud LLM (port 11434 or cloud API)
    └── ← Prep AI Gateway routes LLM calls
```

---

## 8. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent execution model | Prep daemon runs agents internally | Avoids daisy-chaining LLMs through Paperclip's heartbeat scheduler |
| Paperclip presence | Paused dummy profiles | First-class Paperclip concept; shows in org charts; resumable |
| Tool delivery | MCP server | Universal standard; Paperclip supports it natively; no SDK dependency |
| Push delivery | Python REST (`urllib`) | Zero external dependencies; runs in daemon threads; sufficient for all current workflows |
| Plugin package timing | Roadmapped, not immediate | Python adapter covers proactive push; npm package needed only for reactive event hooks |
| UI injection | Dropped entirely | Prep maintains its own dashboard; no benefit to fragmenting the experience |

---

## 9. Related Documents

| Document | Relationship |
|----------|-------------|
| [01_Integration_Research.md](./01_Integration_Research.md) | Historical research (superseded by this document) |
| [Phase 65: Pushing to Paperclip](../../Phase65_PushingTasksToPaperclip/README.md) | PushEngine and PM Adapter that all agents use |
| [Phase 66: Pi Agent](../../Phase66_Pi-Agent/README.md) | Pi daemon thread — Researcher and Custodian hook into the Pi Watchdog |
| [Phase 67 README](../README.md) | Unified agent architecture overview |
| [Researcher-concept-adapter/](../Researcher-concept-adapter/) | Agent engine designs, LangGraph/CrewAI blueprints |
| [HR-concept-adapter/](../HR-concept-adapter/) | Staffing Agent concept docs (01–07) |

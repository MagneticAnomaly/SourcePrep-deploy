# Boundary Analysis: CoDRAG vs. Paperclip — Who Owns What?

*2026-04-06 — Eric's CoDRAG MCP R&D*

## The Question

Where does agent staffing live? CoDRAG has the codebase knowledge. Paperclip has the agent runtime. The agent builder script sits in the middle. Who does what?

---

## What Already Exists (I Read All of This)

### In CoDRAG (`src/codrag/agents/`)

| Component | What It Does | Status |
|-----------|-------------|--------|
| **`hr/engine.py`** (711 lines) | **Full StaffingEngine** — readiness scoring, role generation (list/auto/hybrid modes), drift detection, org chart generation, Paperclip push | Built |
| **`hr/prompts.py`** | LLM prompts for AGENTS.md, SOUL.md, auto role inference | Built |
| **`hr/roster.py`** | JSON-backed persistence of role specs | Built |
| **`hr/readiness.py`** | Codebase readiness scoring before role generation | Built |
| **`core.py`** (AgentCore) | Unified facade: CoDRAG read + Paperclip write + Git + LLM + Agent CRUD | Built |
| **`researcher/engine.py`** | Research agent that analyzes codebase proactively | Built |
| **`custodian/engine.py`** | Maintenance agent with manifests | Built |
| **`shared/paperclip_client.py`** | HTTP client to push agents, issues, goals to Paperclip | Built |

### In CoDRAG (`packages/`)

| Component | What It Does | Status |
|-----------|-------------|--------|
| **`paperclip-plugin-codrag/`** | Full Paperclip plugin manifest with 5 tools, 4 UI slots (dashboard widget, agent knowledge scope tab, issue context tab, settings page), scheduled reindex job | Built |
| **`paperclip-skill/`** | Claude Code skill installer that symlinks CoDRAG tools into `~/.claude/skills/codrag` | Built |

### In Paperclip (this repo)

| Component | What It Does | Status |
|-----------|-------------|--------|
| **Plugin system** | External adapter/plugin loading via `~/.paperclip/adapter-plugins.json` | Built |
| **Agent runtime** | Heartbeat lifecycle, task assignment, approval gates, budget enforcement | Built |
| **Agent builder v3** (`scripts/Eric/`) | Workflow script for manually assembling agent teams | Draft |

---

## The Three Integration Surfaces

```
┌──────────────────────────────────────────────────────┐
│                    CoDRAG Daemon                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Index    │  │ Atlas    │  │ HR StaffingEngine │  │
│  │ Search   │  │ Modules  │  │ - readiness       │  │
│  │ Impact   │  │ Hub Files│  │ - auto_generate   │  │
│  │ Audit    │  │ Roles    │  │ - drift_detect    │  │
│  └──────────┘  └──────────┘  │ - push_to_paperclip│  │
│                              └───────────────────────┘  │
│        ↓ HTTP API (:8400)          ↓ HTTP API           │
└──────────────────────────────────────────────────────┘
         │                            │
    ┌────┴────┐                 ┌─────┴────────┐
    │ Surface │                 │   Surface    │
    │    1    │                 │     2        │
    │  MCP    │                 │  Plugin      │
    │ (tools) │                 │  (worker)    │
    └─────────┘                 └──────────────┘
         │                            │
    ┌────┴────────────────────────────┴────┐
    │        AI Coding Agent               │
    │  (Claude Code / Cursor / Gemini)     │
    │                                      │
    │  Surface 3: Paperclip Heartbeat      │
    │  - agent receives task               │
    │  - calls codrag:* via MCP or plugin  │
    │  - does work                         │
    │  - reports status                    │
    └──────────────────────────────────────┘
```

### Surface 1: MCP (Claude Code, Cursor, etc.)
- **What agents get:** `codrag`, `codrag_search`, `codrag_impact`, `codrag_audit`, `codrag_observe`, `codrag_concepts`
- **Who uses it:** Any AI agent in any IDE. Not Paperclip-specific.
- **Staffing relevance:** The `role=` parameter on `codrag()` and `codrag_search()` filters context per agent. CoDRAG's `AgentScopeManager` handles the masking.

### Surface 2: Paperclip Plugin (`@codrag/paperclip-plugin`)
- **What it adds:** 5 registered tools (`codrag:context`, `codrag:search`, etc.), dashboard widgets, agent knowledge scope tab, issue context tab, settings page, scheduled reindex job
- **Who uses it:** Paperclip agents during heartbeat runs
- **Staffing relevance:** The plugin gives agents **access** to CoDRAG during runs. But it does NOT currently expose the HR system.

### Surface 3: Paperclip Runtime (heartbeat lifecycle)
- **What it controls:** Task assignment, approval gates, budget, agent execution
- **Staffing relevance:** Agents are CREATED and MANAGED here. CoDRAG's `push_to_paperclip()` pushes role specs INTO Paperclip via HTTP.

---

## The Answer: CoDRAG Generates, Paperclip Operates, HR Bridges

The existing code already implements your ideal model:

### 🟢 CoDRAG owns GENERATION (the "hiring")

The `StaffingEngine` in `hr/engine.py` already does exactly what the v3 builder script does:

1. **Readiness check** — Is the codebase indexed enough to generate roles?
2. **Role inference** — LLM analyzes modules, atlas, domain tags → recommends roles
3. **File generation** — AGENTS.md, SOUL.md, KNOWLEDGE.md per role (with edit-aware regeneration!)
4. **Roster persistence** — Roles stored in `hr_roster.json`
5. **Drift detection** — `audit_roles()` computes fitness scores per role when codebase changes
6. **Org chart** — `generate_org_chart()` infers collaboration from shared module references

**This should be a dashboard button.** CoDRAG has the deep structural knowledge (atlas, modules, hub files, domain tags, architecture layers) that makes role generation meaningful. A "Generate Staff" button in the CoDRAG dashboard is the natural home.

### 🟢 Paperclip owns OPERATION (the "managing")

Once roles exist:

1. **`push_to_paperclip()`** creates/updates agents in Paperclip
2. Paperclip manages the heartbeat lifecycle, task assignment, budgets
3. Agents call `codrag:*` tools during their runs via the plugin

### 🟡 The HR Agent bridges ongoing adjustment

An HR agent **running inside Paperclip** but **powered by CoDRAG data** handles:

1. **Periodic drift checks** — "Did the codebase change enough to warrant updating role definitions?"
2. **Re-generation** — Uses the StaffingEngine's edit-aware mode (preserves human modifications)
3. **Org chart updates** — Adjusts collaboration relationships as modules evolve

This is already designed in CoDRAG's `hr/engine.py` — it just needs to be wired up.

---

## The v3 Builder Script: Where Does It Fit?

The `paperclip-agent-builder-v3.md` script is effectively a **manual walkthrough of what `StaffingEngine.auto_generate_roles()` does programmatically**. It's:

- ✅ Useful as a **learning tool** and Claude Code workflow
- ✅ Good for **one-off customization** where you want human oversight at each step
- ❌ **Redundant** with the existing HR engine for automated generation
- ❌ **Missing the drift/audit loop** that the engine provides

**Recommendation:** Keep the script as a Claude Code workflow for manual team design, but invest in exposing the StaffingEngine through the CoDRAG dashboard UI for the "push-button" experience.

---

## The Plugin Question

> "I'm unsure if or how the plugin would even do anything"

The plugin **already** does something substantial — it gives agents CoDRAG tools during Paperclip runs. But it could do more:

### What the plugin CAN'T do (by design)
- The plugin is a **consumer** not a **generator**. It queries the daemon, it doesn't run the StaffingEngine.
- It doesn't have access to LLM inference (that's the daemon's job).

### What the plugin COULD add
1. **Knowledge Scope Tab** — Already in the manifest! Shows per-agent file scopes visually.
2. **"Regenerate Role" button** — Calls the daemon's HR API endpoint to re-run generation for one agent.
3. **Drift notification** — The scheduled `reindex-check` job could also check role drift and surface warnings.

---

## Clear Boundary Map

| Responsibility | Owner | Why |
|---------------|-------|-----|
| **Structural analysis** (index, trace, atlas, modules) | CoDRAG daemon | Has the graph engine |
| **Role generation** (readiness, inference, AGENTS.md) | CoDRAG daemon (StaffingEngine) | Needs atlas + modules + LLM |
| **Role persistence** (roster) | CoDRAG daemon | Lives alongside project index |
| **Drift detection** (fitness scoring) | CoDRAG daemon | Needs current graph vs. stored roles |
| **Dashboard UI** for generation | CoDRAG dashboard | Users push a button, see results |
| **Push to Paperclip** (agent CRUD) | CoDRAG daemon → Paperclip API | `push_to_paperclip()` is already built |
| **Agent execution** (heartbeat, tasks, budget) | Paperclip | Its core job |
| **Tool access during runs** | Paperclip plugin | Routes `codrag:*` calls to daemon |
| **Ongoing role adjustment** | HR agent in Paperclip + CoDRAG data | Bridges the gap |
| **Manual team design** | Agent builder v3 script | Human-in-the-loop workflows |

---

## Next Steps

### Immediate (can do now)
1. **Expose StaffingEngine via CoDRAG API** — Add `/projects/{id}/staff` endpoints for readiness, generate, drift, push
2. **Add dashboard panel** — "Agent Staff" tab in CoDRAG dashboard with Generate/Audit/Push buttons

### Medium-term
3. **Wire HR agent to Paperclip** — The HR agent runs in Paperclip on a schedule, calls CoDRAG's drift detection, and auto-regenerates drifted roles
4. **Extend plugin** — Add a "Regenerate" action on the Agent Knowledge Scope tab

### Research
5. **Test the existing `auto_generate_roles()`** against Paperclip's codebase — Does it produce good roles? What needs tuning?
6. **Evaluate whether the plugin should surface the org chart** — Is that a Paperclip UI concern or a CoDRAG UI concern?

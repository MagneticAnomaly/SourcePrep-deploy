# Paperclip Integration — Research & Design

> [!IMPORTANT]
> **This document is historical reference only.** The definitive architecture specification is [02_Hybrid_MCP_Architecture.md](./02_Hybrid_MCP_Architecture.md). Refer to that document for the current integration strategy, what's built, and the forward roadmap.

> **Phase 67 — Paperclip Hybrid Integration (MCP + Lightweight Plugin)** | Date: 2026-04-04
> This document outlines the original CoDRAG-Paperclip integration research. It has been superseded by the Hybrid MCP Architecture document above.

---

## 1. Integration Layers

CoDRAG integrates with Paperclip through a **Hybrid Architecture** prioritizing MCP for agent capabilities, supported by a lightweight plugin for proactive workflows:

| Layer | What | How | Priority |
|-------|------|-----|----------|
| **L1: MCP Server** | Expose CoDRAG's 5 core tools native to agents | MCP Protocol (`codrag_mcp`) | Primary |
| **L2: Workflow Plugin** | Lifecycle events, task pushing, agent CRUD | Plugin SDK (`@paperclipai/plugin-sdk`) | Secondary (Lightweight) |

### Why this hybrid model matters

- **L1 (MCP Server)** is the core integration: Every Paperclip agent gets codebase intelligence natively without needing custom plugin tooling proxies.
- **L2 (Lightweight Plugin)** solves the orchestration gap: It allows CoDRAG to push health findings as issues, populate agent knowledge scopes automatically, and handle Agent CRUD without bloating into a massive UI application.

---

## 2. Paperclip API Surface (Agent CRUD)

### Authentication
- Bearer tokens: agent API keys, run JWTs, or session cookies
- Mutating requests during heartbeats require `X-Paperclip-Run-Id` header
- Secrets encrypted at rest, injected via `secret_ref` in adapter config

### Agent Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/companies/{id}/agents` | Create agent (name, role, title, capabilities, adapterConfig) |
| `GET` | `/api/companies/{id}/agents` | List all agents |
| `GET` | `/api/agents/{id}` | Get agent details + reporting structure |
| `GET` | `/api/agents/me` | Current authenticated agent |
| `PATCH` | `/api/agents/{id}` | Update adapter config, budget |
| `POST` | `/api/agents/{id}/terminate` | Permanently deactivate (irreversible) |
| `POST` | `/api/agents/{id}/pause` | Pause heartbeat execution |
| `POST` | `/api/agents/{id}/resume` | Resume heartbeat execution |
| `POST` | `/api/agents/{id}/heartbeat/invoke` | Manual heartbeat trigger |
| `POST` | `/api/agents/{id}/keys` | Generate API key |
| `GET` | `/api/agents/{id}/config-revisions` | Config version history |
| `GET` | `/api/companies/{id}/org` | Org chart (hierarchy) |

### Agent Data Model

```
Agent {
  id: string
  name: string
  companyId: string
  role: string
  title: string
  reportsTo: string | null
  chainOfCommand: string[]
  capabilities: string[]
  adapterType: string      // "claude_local" | "codex_local" | etc.
  adapterConfig: object    // Runtime-specific config
  budgetMonthlyCents: number
  spentMonthlyCents: number
  status: "active" | "paused" | "terminated"
}
```

### RoleSpec → Agent Mapping

| CoDRAG RoleSpec | Paperclip Agent | Notes |
|-----------------|-----------------|-------|
| `display_name` | `name` | Direct |
| `slug` | `role` | Lowercase identifier |
| `agents_md` | `adapterConfig.instructions` | Or injected as context |
| `soul_md` | `title` | Identity summary |
| `knowledge_md` | Injected via plugin tool | Best as live context, not static |
| `recommended_files` | `capabilities` | What this agent owns |
| `paperclip_agent_id` | `id` (returned on create) | For updates/sync |

### Issue System (Already Integrated — Phase 65)

| Method | Endpoint | Status |
|--------|----------|--------|
| `POST` | `/api/companies/{id}/issues` | Implemented |
| `GET` | `/api/companies/{id}/issues` | Implemented |
| `PATCH` | `/api/issues/{id}` | Implemented |
| `POST` | `/api/issues/{id}/checkout` | Not used (atomic checkout with 409 conflict) |
| Issue documents | `PUT /api/issues/{id}/documents/{key}` | Not used (versioned artifacts) |
| Issue comments | `POST /api/issues/{id}/comments` | Not used |

---

## 3. Paperclip Plugin System (Alpha)

### Architecture

- Plugins are **globally installed per instance**, capability-gated
- **Out-of-process** workers communicating via JSON-RPC over stdio
- No direct DB access — typed SDK clients only
- Worker failure isolated — doesn't affect other plugins or core

### Plugin Lifecycle Hooks

| Hook | When | CoDRAG Use |
|------|------|-----------|
| `initialize(input)` | Worker startup | Connect to CoDRAG daemon, validate project |
| `health()` | Status check | Report daemon connectivity |
| `shutdown()` | Graceful stop | Cleanup connections |
| `validateConfig(input)` | Config change | Verify daemon URL, project ID |
| `configChanged(input)` | Runtime update | Hot-reload project settings |
| `onEvent(input)` | Domain event | React to issue completion, agent creation |
| `runJob(input)` | Cron execution | Scheduled re-indexing, drift analysis |
| `handleWebhook(input)` | Inbound webhook | Git push → rebuild trigger |
| `getData(input)` | UI data request | Serve atlas, module map, search results |
| `performAction(input)` | UI button click | Trigger research run, custodian scan |
| `executeTool(input)` | Agent tool call | `codrag:search`, `codrag:impact`, etc. |

### Worker SDK (`ctx.*`)

```
ctx.config.get()                    — resolved plugin config
ctx.events.on(name, [filter], fn)   — subscribe to domain events
ctx.events.emit(name, payload)      — emit events
ctx.jobs.register(key, {cron}, fn)  — scheduled jobs
ctx.state.get/set/delete(scopeKey)  — scoped state (instance|company|project|agent|issue|run)
ctx.entities.upsert/list()          — plugin entity management
ctx.data.register(key, handler)     — data providers for UI
ctx.actions.register(key, handler)  — actions callable from UI
ctx.tools.register(name, decl, fn)  — agent tools (namespaced as pluginId:toolName)
ctx.logger.*                        — structured logging
```

### UI Extension Points

**Slot types:** `page`, `detailTab`, `dashboardWidget`, `sidebar`, `settingsPage`, `commentAnnotation` (14 total placement zones)

**Detail tab entity types:** `project`, `issue`, `agent`, `goal`, `run`

**Bridge hooks:**
- `usePluginData(key, params?)` — `{ data, loading, error }`
- `usePluginAction(key)` — async action function
- `usePluginStream()` — streaming data
- `useHostContext()` — `{ companyId?, projectId?, entityId? }`

**Shared components:** `MetricCard`, `StatusBadge`, `DataTable`, `TimeseriesChart`, `MarkdownBlock`, `KeyValueList`, `ActionBar`, `LogView`, `JsonTree`, `Spinner`, `ErrorBoundary`

### Agent Tool Integration

Tools are the most relevant surface for CoDRAG:

- **Declaration:** Manifest declares tools with `name`, `displayName`, `description`, `parametersSchema` (JSON Schema)
- **Namespacing:** Auto-prefixed as `<pluginId>:<toolName>` (e.g., `codrag:search`)
- **Execution:** Host routes `executeTool` RPC to plugin worker with run context (`agentId`, `runId`, `companyId`, `projectId`)
- **Results:** String content, structured data, or error; included in run logs
- **Availability:** All agents by default; operator can restrict per-agent or per-project
- **Capability gate:** Requires `agent.tools.register`

**This is NOT MCP** — it's Paperclip-native. CoDRAG would expose its capabilities as Paperclip tools, not MCP tools. The worker would proxy tool calls to the CoDRAG daemon.

### Packaging

- npm packages with `paperclipPlugin` key in `package.json`
- Scaffold: `npx @paperclipai/create-paperclip-plugin codrag`
- Install: `pnpm paperclipai plugin install @codrag/paperclip-plugin`
- Templates: `default`, `connector`, `workspace`
- SDK: `@paperclipai/plugin-sdk` (worker), `@paperclipai/plugin-sdk/ui` (frontend)

### Trust / Security

25+ named capabilities across categories:
- Data: `companies.read`, `projects.read`, `issues.read/create/update`, `agents.read`, `goals.read`, `activity.read`, `costs.read`
- Runtime: `events.subscribe/emit`, `jobs.schedule`, `webhooks.receive`, `http.outbound`, `secrets.read-ref`
- Agent: `agent.tools.register`
- UI: `ui.sidebar.register`, `ui.page.register`, `ui.detailTab.register`, `ui.dashboardWidget.register`

**Forbidden:** Approval override, budget override, auth bypass, direct DB access.

---

## 4. CoDRAG Hybrid Plugin Design

### 4.1 Plugin Identity

```
Package: @codrag/paperclip-plugin
Plugin ID: codrag
Display Name: CoDRAG Codebase Intelligence
```

### 4.2 Capabilities Required

```
agent.tools.register       — Register codrag:search, codrag:impact, etc.
projects.read              — Read project context for tool routing
issues.read                — Read issues to provide context
agents.read                — Read agent roles for context scoping
(Note: Native UI extensions like DashboardWidgets and DetailTabs have been dropped to keep the plugin lightweight and focused on orchestration.)
events.subscribe            — React to project/issue events
jobs.schedule               — Scheduled re-indexing
http.outbound               — Call CoDRAG daemon API
plugin.state.read/write     — Cache project-index mappings
```

### 4.3 Tools (Handled via MCP)

The plugin **does not** register custom tools. Tools are instead provided directly to Paperclip via CoDRAG's standard **MCP Server**. This eliminates the need for an `executeTool` RPC proxy. Paperclip handles MCP natively.

### 4.4 UI Extensions

*Removed. CoDRAG acts as a headless intelligence engine; Paperclip uses the API and MCP tooling for data interaction.*

### 4.5 Events

| Event | Reaction |
|-------|----------|
| `agent.created` | Auto-populate Knowledge Scope for new agent based on role |
| `issue.created` | If issue has `codrag_address`, attach context snapshot as document |
| `project.created` | Prompt user to map to CoDRAG project |
| `run.completed` | Log observation via `codrag_observe` |

### 4.6 Jobs

| Job | Schedule | What |
|-----|----------|------|
| `reindex-check` | Every 6 hours | Check if CoDRAG index is stale, trigger rebuild |
| `drift-scan` | Weekly | Run HR drift detection, report to activity log |

### 4.7 State Scoping

| Scope | Key | Data |
|-------|-----|------|
| `instance` | `daemon_url` | CoDRAG daemon base URL |
| `company` | `default_project` | Default CoDRAG project ID |
| `project` | `codrag_project_id` | Mapping: Paperclip project → CoDRAG project |
| `agent` | `role_slug` | Mapping: Paperclip agent → CoDRAG role slug |
| `agent` | `knowledge_scope` | Cached file list for this agent's scope |

---

## 5. Implementation Phases

### Phase A: Agent CRUD Integration (Immediate)

Extend the existing `PaperclipAdapter` with agent management methods.
Wire into `AgentCore` to replace `NotImplementedError` stubs.
Wire into `StaffingEngine` for optional push-to-Paperclip after role generation.

**Files:**
- Modify: `src/codrag/adapters/paperclip_adapter.py` — add agent CRUD methods
- Modify: `src/codrag/agents/core.py` — replace stubs with real calls
- Modify: `src/codrag/agents/hr/engine.py` — add `push_to_paperclip()` method
- Add: CLI command `codrag hr-sync` for roster ↔ Paperclip sync

### Phase B: Paperclip Plugin Package (Lightweight Workflow)

Build an npm package `@codrag/paperclip-plugin` that focuses purely on workflow orchestration:
1. Orchestrates the PushEngine to inject CoDRAG health findings as Paperclip issues.
2. Syncs RoleSpecs to Agent profiles.
3. Reacts to agent/issue events for automatic context enrichment.

**Location:** `packages/paperclip-plugin/` (new workspace in the monorepo)

**Tech:** TypeScript, `@paperclipai/plugin-sdk`, handles REST/Push workflows.

### Phase C: Bidirectional Sync (Future)

- Pull agent status from Paperclip to update CoDRAG roster health
- Pull issue completion signals to mark CoDRAG findings as resolved
- Use Paperclip's activity log to track which CoDRAG-originated issues were acted on

---

## 6. Opportunities

### 6.1 Every Paperclip Agent Gets CoDRAG Intelligence

With the plugin's tool registration, **every** agent in a Paperclip company can call `codrag:search`, `codrag:impact`, etc. during their runs. This is the "CoDRAG is the brain" value prop from the original design docs — realized through Paperclip's tool system rather than per-agent instruction injection.

### 6.2 Context-Aware Issue Assignment

When Paperclip creates issues from CoDRAG audit findings (Phase 65 push), the plugin can:
- Auto-attach a `codrag-context` document to each issue with the full impact analysis
- Score which agent is best suited to handle the issue (via RoleVector matching)
- Suggest assignment via comments

### 6.3 Budget-Aware Context Budgeting

Paperclip tracks `budgetMonthlyCents` / `spentMonthlyCents` per agent. The plugin could read this and adjust CoDRAG context window sizes — agents near their budget limit get more concise summaries to minimize token consumption.

### 6.4 Org-Aware Atlas Projection

Paperclip's org chart (`/api/companies/{id}/org`) maps directly to CoDRAG's role-aware atlas projection. The plugin can read an agent's Paperclip role and auto-filter codebase context accordingly — engineers get implementation details, managers get architectural summaries.

### 6.5 Run-Triggered Observations

When a Paperclip agent completes a run, the plugin can log the run summary as a CoDRAG observation via `codrag:observe`. This builds cross-session memory — the next agent working on related code sees what was done before.

### 6.6 Marketing Trifecta (from original design docs)

The plugin itself is a marketing vehicle:
- Listed in Paperclip's Plugin Manager (visible in the screenshot)
- Installable via `pnpm paperclipai plugin install @codrag/paperclip-plugin`
- Every Paperclip user sees CoDRAG as an available enhancement

---

## 7. Open Questions

1. **Plugin API stability** — The spec says "alpha, expect breaking changes." How much should we invest now vs. wait for beta? 
2. **Project mapping** — How does a Paperclip project map to a CoDRAG project? Manual config? Auto-detect from git remote? 
>>> I wasn't envisioning accepting project maps, the plugin woule be mostly to use codrag mcp and send paperclip oricects to be accepted there.
3. **Multi-project** — Paperclip companies can have many projects. CoDRAG can index many projects. How do we map N:M? 
>>> I don't know exacly -- I think we can somehow wxpose the list and enable (disabled by default, projects and we find some way to assicoae them th the other app) research more
4. **Daemon dependency** — The plugin worker needs the CoDRAG daemon running. What's the UX when it's not available? 
>>> Um I dunno figure that out later.
5. **Tool latency** — CoDRAG search/impact calls can take 1-5 seconds. Is that acceptable for agent tool calls in Paperclip's execution loop?
>>> not ideal but it's fine

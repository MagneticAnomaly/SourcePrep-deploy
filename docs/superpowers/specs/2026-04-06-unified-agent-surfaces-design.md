# Unified Agent Surfaces — Design Spec

> Date: 2026-04-06 | Companion to `emergence_and_p3_design.md` and `strategic_direction.md`
> Scope: Frontend surfaces only — CoDRAG Dashboard panels, Paperclip Plugin UI, and the interface boundary between them
> Principle: **CoDRAG configures and computes. Paperclip operates and displays. No redundancy.**

---

## 1. Problem Statement

CoDRAG has a mature agent backend — three engines (HR, Researcher, Custodian), a collaboration infrastructure (4 stores, 7 REST endpoints, 3 MCP resources, 3 MCP prompts), and a Paperclip plugin with 5 tools and 4 data providers. The backend is coherent and well-documented.

The frontend surfaces are not. Two UI surfaces exist — the CoDRAG dashboard (React at :5174) and the Paperclip plugin UI (4 declared slots) — with unclear responsibilities and partial implementations:

- The CoDRAG dashboard has 12 agent components across 2 panels (`agent-ops`, `agent-scope`) that expose both **configuration** (scope editing, role generation) and **operational status** (run counts, research history, employee badges). The operational parts overlap with what Paperclip should show.
- The Paperclip plugin declares 4 UI slots but the implementations are thin — `KnowledgeScopeTab` gets `{ files: [] }` from the data provider, `IssueContextTab` is 42 lines of placeholder, and the dashboard widget shows basic health data.
- No surface shows **what CoDRAG actually pushed** to Paperclip — the enrichment pipeline (consensus scores, structural complexity, delta pushes) exists in the backend plan but has no UI home.
- The three CoDRAG engines run and produce findings, but there's no clear flow for how those findings become visible work in Paperclip.

**Goal:** Define what each surface shows, what it doesn't show, and how recommendations flow from CoDRAG engines through to Paperclip tickets — with the simplest possible frontend.

---

## 2. Design Philosophy

### 2.1 The Bulletin Board Model

CoDRAG agents are **recommendation engines**, not task managers. They analyze the codebase, produce findings, and push them to Paperclip as enriched issues. Paperclip manages the lifecycle (assignment, execution, completion). There is no bidirectional sync — flow is one-directional:

```
CoDRAG engines → enriched issues → Paperclip issue tracker
                                    ↓
                              Paperclip agents → pick up work
                                    ↓
                              call codrag:* tools for structural context during execution
```

### 2.2 Three Pipes

All CoDRAG-to-Paperclip communication uses three pipes:

| Pipe | What flows | Mechanism | Already built? |
|------|-----------|-----------|----------------|
| **Recommendations** | Research topics, cleanup candidates, drift alerts, conflicts | `PaperclipClient.push_issue()` with enrichment | Partially — conflict push done, enrichment planned in emergence doc |
| **Staffing** | Role definitions (agent configs, scopes, capabilities) | `PaperclipClient.create_agent()` / `update_agent()` | Yes — `push_to_paperclip()` in HR engine |
| **Runtime context** | Structural intelligence during agent execution | Plugin tools (`codrag:context`, `codrag:search`, etc.) | Yes — 5 tools in plugin worker |

### 2.3 The Line Between Surfaces

| Responsibility | CoDRAG Dashboard | Paperclip Plugin |
|---------------|------------------|------------------|
| **Configure** agent scopes | Yes — file tree editor | Read-only view of scope |
| **Configure** engine settings (thresholds, schedules) | Yes — settings panel | No |
| **Trigger** engine runs (Generate, Research, Scan) | Yes — action buttons | Yes — via plugin actions |
| **View** what was pushed to Paperclip | Summary counts only | Full issue list (native Paperclip UI) |
| **View** agent runtime status | No — Paperclip owns this | Yes — heartbeats, task assignment |
| **View** structural intelligence (delta, consensus) | Minimal — delta preview | Yes — dashboard widget, agent context |
| **View** collaboration (claims, conflicts) | No | Yes — agent detail tabs, issue tracker |
| **Manage** agent lifecycle (pause, resume, assign) | No | Yes — Paperclip native |

**The rule:** If Paperclip has a native UI for it, CoDRAG doesn't show it. CoDRAG shows only what you need to **configure the intelligence** and **verify it's working**.

---

## 3. CoDRAG Dashboard — Minimal Configuration Surface

### 3.1 What Stays

**Agent Knowledge Scopes panel** (`agent-scope`) — This is pure CoDRAG configuration. No equivalent in Paperclip. The panel lets users:
- Create/delete agent roles
- Select files per role via the FolderTree
- Auto-populate scopes from graph analysis
- See file count per role

This panel is complete and well-implemented (387 lines). **No changes needed.**

### 3.2 What Changes

**Agent Operations panel** (`agent-ops`) — Currently shows operational status (run counts, research history, employee badges) alongside configuration actions. This needs to become **configuration-only**:

#### Current AgentOpsPanel (142 lines):
- 3 AgentCards showing run counts and status badges ← **operational, remove**
- MCPConnectionCard for Paperclip skill install ← **configuration, keep**
- EmployeeBadges showing generated roles ← **operational, remove**
- "Getting Started" onboarding guide ← **configuration, keep**

#### Redesigned AgentOpsPanel:

The panel becomes a **control panel** with two sections:

**Section 1: Engine Controls**

Three compact rows (not cards) — one per engine. Each row has:
- Engine name + one-line description
- Action button (Generate / Research / Scan)
- Last-run timestamp (for user confidence, not monitoring)
- Push summary: "3 issues pushed" or "Not yet run" — a static count of what was last pushed, not a live feed

This replaces the current AgentCards which show cumulative counts (unhelpful for config). The push summary connects the "Run" action to visible Paperclip output without showing the Paperclip issue list.

**Section 2: Paperclip Connection**

The existing MCPConnectionCard, unchanged. Shows whether the CoDRAG skill is installed in Paperclip, with install/uninstall/refresh actions.

**Section 3: Push Settings (new, minimal)**

Configuration for how CoDRAG pushes to Paperclip:
- **Auto-push toggle** — whether engine findings auto-push to Paperclip or require manual "Push" click
- **Significance threshold** — dropdown: "All findings", "Recommended+ only", "Mandatory only"
  - `mandatory`: security issues, breaking changes, HR drift >50%
  - `recommended`: research topics, cleanup candidates, mild drift
  - `informational`: delta rank changes, low-confidence findings
- **Paperclip project** — which Paperclip project receives pushed issues (text field, auto-detected if possible)

This is 3 form fields. No complex UI.

#### What's Removed from Dashboard

These components are **not deleted** from `packages/ui/` (they may be useful in Storybook or future contexts), but they are **no longer rendered** in the dashboard:

- `EmployeeBadges` — role status belongs in Paperclip's agent list
- `SystemAgentsTab` — system agent management belongs in Paperclip
- `ManagedEmployeesTab` — managed employee view belongs in Paperclip
- `ResearchTopicList` — research output belongs in Paperclip's issue tracker
- `CleanupPreview` — cleanup output belongs in Paperclip's issue tracker
- `GenerateWizard` — wizard flow is overkill; the action button + CLI command is sufficient
- `AgentOpsDetail` — the detail overlay showed operational data that belongs in Paperclip

The AgentCards are replaced by the simpler engine control rows described above.

### 3.3 Panel Registry Changes

The two existing panels stay in the registry:

| Panel ID | Title | Changes |
|----------|-------|---------|
| `agent-scope` | Agent Knowledge Scopes | None |
| `agent-ops` | Agent Operations | Simplify to config-only (engine controls + connection + push settings) |

No new panels are added.

---

## 4. Paperclip Plugin — The Rich Agent Surface

### 4.1 Current State

The plugin has 5 tools (working), 4 data providers (working), 2 actions (working), 1 job (working), and 4 UI slots (thin implementations). The plugin worker (`395 lines`) is solid — it proxies all calls to the CoDRAG daemon correctly.

### 4.2 UI Slot: Codebase Health Dashboard Widget (`codebase-health`)

**Current:** Fetches agent status + HR readiness from daemon. Minimal display.

**Enhanced:** The dashboard widget becomes the **primary agent intelligence summary** in Paperclip. It shows:

```
┌─────────────────────────────────────────────┐
│  CoDRAG Codebase Health                     │
├─────────────────────────────────────────────┤
│                                             │
│  Pipeline: ● Healthy (rebuilt 2h ago)       │
│  Index: 323 Python / 334 TypeScript files   │
│                                             │
│  ── Recent Pushes ──────────────────────    │
│  3 issues pushed (2 recommended, 1 mandatory│
│  Last push: 45 min ago                      │
│                                             │
│  ── Consensus Hotspots ─────────────────    │
│  src/auth/session.py  3/5 agents  0.60      │
│  src/core/config.py   2/5 agents  0.40      │
│                                             │
│  ── Structural Delta ───────────────────    │
│  1 new hub: src/gateway.py (#2, 14 deps)    │
│  No module changes since last rebuild       │
│                                             │
└─────────────────────────────────────────────┘
```

**Data source:** The `codebase-health` data provider is extended to also fetch:
- `GET /projects/{pid}/collaboration/delta` — latest structural delta
- `GET /projects/{pid}/observations/consensus` — consensus scores (new endpoint, from emergence doc Feature 1)
- Push history summary (from a new lightweight endpoint or from ActivityStore)

**Implementation:** The widget component (`CodebaseHealthWidget`) reads from `usePluginData('codebase-health')` which returns the combined payload. The worker's `codebase-health` data provider makes 3-4 parallel daemon requests and merges them.

### 4.3 UI Slot: Knowledge Scope Tab (`knowledge-scope`, on agents)

**Current:** Returns `{ files: [] }` — the data provider looks up `role_slug` from plugin state but can't populate files.

**Enhanced:** This tab shows the **read-only view** of an agent's CoDRAG knowledge scope. It needs two things to work:

1. **Role mapping:** When CoDRAG pushes an agent to Paperclip via `create_agent()`, it should store the CoDRAG role slug in the agent's `adapterConfig.codrag_role`. The plugin's data provider reads this instead of looking up state.

2. **File list:** The data provider calls `GET /projects/{pid}/agent-scope/{role}` (already exists) with the mapped role.

The tab shows:
- The role name and how it was resolved (from `adapterConfig.codrag_role`)
- A read-only file list (the configured scope paths)
- Active claims on files within the scope (from `agent-claims` data provider)
- A note: "Configure scopes in the CoDRAG dashboard" with a link/instruction

**This tab does NOT allow scope editing** — that's the CoDRAG dashboard's job. Read-only prevents two editing surfaces for the same data.

### 4.4 UI Slot: Issue Context Tab (`codebase-context`, on issues)

**Current:** 42 lines of placeholder.

**Enhanced:** When viewing a Paperclip issue that was pushed from CoDRAG (identifiable by `<!-- codrag-address:... -->` in the description), this tab shows the **structural context** behind the issue:

- **Structural complexity tier** (lightweight / standard / heavyweight) with explanation
- **Hub files involved** with dependent counts
- **Modules spanned** with cross-module flag
- **Consensus score** if multiple agents flagged the area
- **Related observations** from CoDRAG agents (via `codrag_search` with the file paths mentioned in the issue)
- **Impact analysis** for affected files (via the `codrag:impact` tool)

For issues NOT pushed from CoDRAG, the tab shows a simpler view:
- "No CoDRAG context for this issue. Use the Enrich action to add structural analysis."
- A button that triggers `codrag:context` + `codrag:impact` for files mentioned in the issue description

**Data source:** The tab parses the issue description for `codrag-address` metadata. If found, it calls the daemon for the specific context. If not, it offers on-demand enrichment.

### 4.5 UI Slot: Settings Page (`codrag-settings`)

**Current:** 55 lines of basic config.

**Enhanced:** This is the plugin-side mirror of CoDRAG connection settings:
- Daemon URL (with health check indicator)
- Project ID (auto-detected or manual)
- Auto-context toggle (attach CoDRAG context to new issues automatically)
- Push settings link: "Configure push behavior in the CoDRAG dashboard"

**This page does NOT duplicate the CoDRAG dashboard's push settings.** It only controls plugin-side behavior (what the plugin does with data it receives).

### 4.6 New Data Providers

Two new data providers added to the plugin worker:

**`consensus-hotspots`** — Calls `GET /projects/{pid}/observations/consensus` (new endpoint from emergence doc). Returns file paths with consensus scores for display in the dashboard widget and issue context tab.

**`push-summary`** — Calls `GET /projects/{pid}/collaboration/activity?action_filter=push` (uses existing activity endpoint with a filter). Returns recent push counts and timestamps for the dashboard widget.

### 4.7 New Action

**`enrich-issue`** — Calls `codrag:context` and `codrag:impact` for files mentioned in an issue, then appends structural context to the issue description. Triggered from the Issue Context tab's "Enrich" button. Uses existing daemon endpoints, no new backend work.

### 4.8 Plugin Manifest Changes Summary

```diff
  tools: [5 existing — no changes]

  ui.slots: [4 existing — enhanced implementations, no new slots]

  jobs: [1 existing — no changes]

+ dataProviders: [
+   'codebase-health'        // existing, extended payload
+   'agent-knowledge-scope'  // existing, fix role mapping
+   'structural-delta'       // existing (Phase 73.5)
+   'agent-claims'           // existing (Phase 73.5)
+   'consensus-hotspots'     // new
+   'push-summary'           // new
+ ]

+ actions: [
+   'run-researcher'         // existing
+   'run-custodian'          // existing
+   'enrich-issue'           // new
+ ]
```

---

## 5. The Push Enrichment Pipeline

This section documents how CoDRAG engine findings become enriched Paperclip issues. The backend implementation is specified in `emergence_and_p3_design.md` — this section describes the **flow** and how it connects to the frontend surfaces.

### 5.1 Flow: Engine Run → Enriched Issue → Paperclip

```
Step 1: Engine produces findings
  ├── Researcher: research topics from audit findings
  ├── Custodian: dead code candidates from trace graph
  └── HR: role drift from graph vs. roster comparison

Step 2: PushEngine enriches each finding
  ├── Consensus scoring: "3/5 agents flagged this area"
  ├── Structural complexity: lightweight / standard / heavyweight
  ├── Hub involvement: which hub files, dependent counts
  └── Cross-module analysis: how many modules does this span?

Step 3: Significance filter
  ├── mandatory: auto-push (security, breaking changes, severe drift)
  ├── recommended: push if auto-push enabled, otherwise queue for manual push
  └── informational: include in delta resource only, never auto-push as issue

Step 4: Push to Paperclip
  ├── Issue created with enriched description
  ├── Structural context section appended
  ├── Consensus note appended if score > 0.5
  ├── Complexity tier tagged
  └── codrag-address for dedup

Step 5: Visible in Paperclip
  ├── Dashboard widget shows push summary + consensus hotspots
  ├── Issue list shows enriched issues with structural context
  ├── Issue Context tab shows full CoDRAG analysis
  └── Knowledge Scope tab shows agent file claims
```

### 5.2 Significance Classification

Each finding from each engine gets a significance level:

**HR Engine:**
| Finding | Significance |
|---------|-------------|
| Role drift score > 0.5 (50%+ of scope changed) | mandatory |
| Role drift score 0.2–0.5 | recommended |
| New role suggestion from graph analysis | recommended |
| Minor scope adjustment | informational |

**Researcher Engine:**
| Finding | Significance |
|---------|-------------|
| Security-related finding | mandatory |
| High-consensus topic (3+ agents flagged same area) | mandatory |
| Research topic touching hub files (heavyweight complexity) | recommended |
| Standard research topic | recommended |
| Low-confidence topic (single observation, no structural backing) | informational |

**Custodian Engine:**
| Finding | Significance |
|---------|-------------|
| Dead code in hub file (potentially dangerous if wrong) | mandatory |
| Dead code with 0 dependents, 0 imports (safe to remove) | recommended |
| Candidate with claims from another agent | informational (skip, claimed) |

**Structural Delta (Pi Watchdog):**
| Finding | Significance |
|---------|-------------|
| New hub file detected | recommended |
| Hub file removed | recommended |
| New module appeared | recommended |
| Module removed | recommended |
| Hub rank change | informational |
| Module size change < 20% | informational |

### 5.3 Where Significance Classification Lives

Each engine classifies its own findings. The engine knows the domain context (is this a security finding? is this drift severe?) — PushEngine doesn't. Classification happens inside the engine's `run()` method, attached to each finding as a `significance` field (`"mandatory"`, `"recommended"`, `"informational"`). PushEngine reads the field and applies the push settings filter.

### 5.4 Manual vs. Auto Push

The CoDRAG dashboard's push settings control this:

- **Auto-push ON, threshold = "All findings":** Everything at `recommended` and above auto-pushes after engine runs.
- **Auto-push ON, threshold = "Mandatory only":** Only `mandatory` findings auto-push. `recommended` items accumulate until manual push.
- **Auto-push OFF:** Nothing auto-pushes. User clicks "Push" in the engine controls after reviewing.

The `mandatory` significance level always pushes regardless of settings — these are safety-critical signals.

---

## 6. Backend Endpoints Needed

### 6.1 New Endpoints (from emergence doc, restated for clarity)

| Endpoint | Method | Purpose | Source |
|----------|--------|---------|--------|
| `GET /projects/{pid}/observations/consensus` | GET | Consensus scores for files flagged by 2+ agents | emergence doc Feature 1 |
| `GET /projects/{pid}/push/summary` | GET | Recent push counts and timestamps per engine | New — lightweight query on ActivityStore |
| `GET /projects/{pid}/push/settings` | GET | Current push configuration (auto-push, threshold, target project) | New — settings store |
| `PUT /projects/{pid}/push/settings` | PUT | Update push configuration | New — settings store |

### 6.2 Modified Endpoints

| Endpoint | Change | Source |
|----------|--------|--------|
| `POST /projects/{pid}/agents/hr/generate` | Add `push=true` query param to auto-push after generation | Existing endpoint, new param |
| `POST /projects/{pid}/agents/researcher/run` | Add `push=true` query param | Existing endpoint, new param |
| `POST /projects/{pid}/agents/custodian/run` | Add `push=true` query param | Existing endpoint, new param |
| `POST /projects/{pid}/pipeline/rebuild` | After rebuild completes, trigger delta snapshot + significance check | Existing endpoint, new post-hook |

### 6.3 Existing Endpoints (no changes)

All 7 collaboration endpoints, all agent scope endpoints, all agent status endpoints — unchanged.

---

## 7. What We're NOT Building

| Idea | Why not |
|------|---------|
| **Triage Agent in Paperclip** | The significance filter + auto-push settings provide the same gatekeeping without a dedicated agent. If the user wants more control, they turn off auto-push. A triage agent adds complexity (needs its own template, prompt, budget) for marginal benefit over a threshold slider. |
| **Staging queue / pending recommendations table** | The significance filter IS the staging mechanism. `informational` items don't push. `recommended` items push or don't based on settings. No intermediate queue UI needed. |
| **CoDRAG dashboard monitoring** | Run history, agent heartbeats, task assignment — all belong in Paperclip. CoDRAG shows "last ran 2h ago, pushed 3 issues" and nothing more. |
| **Bidirectional sync** | CoDRAG pushes TO Paperclip. It never pulls back. If we need outcome data later (was the issue accepted?), we poll Paperclip's API — we don't build a sync system. |
| **Duplicate issue views** | CoDRAG dashboard does NOT show a list of pushed issues. That's Paperclip's issue list. CoDRAG shows only the push count summary. |
| **Agent lifecycle management** | Pause/resume/assign agents is Paperclip's job. CoDRAG only creates/updates agents via the staffing pipe. |

---

## 8. Component Inventory — What Changes

### 8.1 CoDRAG Dashboard Components (`packages/ui/src/components/agents/`)

| Component | Current | After |
|-----------|---------|-------|
| `AgentOpsPanel.tsx` | 3 AgentCards + MCPConnection + EmployeeBadges | Engine control rows + MCPConnection + Push Settings |
| `AgentScopePanel.tsx` | File tree scope editor | No changes |
| `AgentCard.tsx` | Card with status badge, metric, action | Replaced by simpler engine control row (inline in AgentOpsPanel) |
| `MCPConnectionCard.tsx` | Paperclip skill install/status | No changes |
| `EmployeeBadges.tsx` | Role completion badges | Removed from dashboard rendering |
| `ManagedEmployeesTab.tsx` | Managed employee list | Removed from dashboard rendering |
| `SystemAgentsTab.tsx` | System agent list | Removed from dashboard rendering |
| `GenerateWizard.tsx` | Multi-mode generation wizard | Removed from dashboard rendering |
| `ResearchTopicList.tsx` | Research run display | Removed from dashboard rendering |
| `CleanupPreview.tsx` | Cleanup candidate display | Removed from dashboard rendering |
| `AgentOpsDetail.tsx` | Full detail overlay | Removed from dashboard rendering |
| `index.ts` | Exports all | Updated exports |

**New component:**
| Component | Purpose |
|-----------|---------|
| `PushSettings.tsx` | 3-field form: auto-push toggle, significance threshold dropdown, Paperclip project field |

### 8.2 Paperclip Plugin UI (`packages/paperclip-plugin-codrag/src/ui/`)

| Component | Current | After |
|-----------|---------|-------|
| `CodebaseHealthWidget.tsx` | Basic status display | Rich widget: pipeline status, push summary, consensus hotspots, delta preview |
| `KnowledgeScopeTab.tsx` | 54 lines, reads empty files array | Read-only scope display with claims overlay, role resolved from adapterConfig |
| `IssueContextTab.tsx` | 42 lines placeholder | Structural context for CoDRAG-pushed issues, on-demand enrichment for others |
| `SettingsPage.tsx` | 55 lines basic config | Add push settings link, verify health check works |

### 8.3 Plugin Worker (`packages/paperclip-plugin-codrag/src/worker/index.ts`)

| Change | Description |
|--------|-------------|
| `codebase-health` data provider | Extend to fetch delta + consensus + push summary in parallel |
| `agent-knowledge-scope` data provider | Fix role mapping: read `adapterConfig.codrag_role` instead of state lookup |
| New `consensus-hotspots` data provider | Calls `/observations/consensus` |
| New `push-summary` data provider | Calls `/collaboration/activity?action_filter=push` |
| New `enrich-issue` action | Calls context + impact for issue files, appends structural context |

### 8.4 Backend (`src/codrag/`)

| File | Change |
|------|--------|
| `services/observation_store.py` | Add `get_consensus_scores()` (emergence doc Feature 1) |
| `adapters/pm_models.py` | Add `StructuralContext` dataclass (emergence doc Feature 2) |
| `adapters/push_engine.py` | Add `_enrich_with_structural_context()`, `push_significant_delta()`, consensus enrichment, significance classification (emergence doc Features 1-3) |
| `api/routers/collaboration.py` | Add consensus endpoint, push summary endpoint, push settings endpoints |
| `api/routers/agents.py` | Add `push=true` query param to generate/run endpoints |
| `mcp/collaboration_handlers.py` | Add consensus hotspots to delta resource, claims steps to prompts (emergence doc Feature 4) |
| `agents/hr/engine.py` | Add significance classification to drift findings |
| `agents/researcher/engine.py` | Add significance classification to research topics |
| `agents/custodian/engine.py` | Add significance classification to cleanup candidates |

---

## 9. Implementation Order

### Phase 1: Backend Push Enrichment (emergence doc implementation)

This is the emergence doc's 4 features, implemented in the order specified there:

1. **Consensus Scoring** — `get_consensus_scores()` on ObservationStore, consensus endpoint
2. **Structural Complexity on Push** — `StructuralContext`, `_enrich_with_structural_context()`, complexity tiers
3. **Delta Push** — `push_significant_delta()`, significance filter, Pi Watchdog integration
4. **Claims in Prompts** — extend `codrag-enrich` and `codrag-handoff` prompts

Plus the new infrastructure:
5. **Significance classification** — add classification logic to each engine
6. **Push settings** — settings store keys, REST endpoints, auto-push toggle
7. **Push summary** — lightweight activity query for push counts

### Phase 2: CoDRAG Dashboard Simplification

8. **Redesign AgentOpsPanel** — replace AgentCards with engine control rows, add PushSettings section
9. **Remove operational components from rendering** — EmployeeBadges, SystemAgentsTab, ManagedEmployeesTab, etc. stay in package but are not imported into the dashboard layout
10. **Update panelRegistry** — revise `agent-ops` description

### Phase 3: Paperclip Plugin UI Enhancement

11. **CodebaseHealthWidget** — implement rich dashboard widget with push summary, consensus, delta
12. **KnowledgeScopeTab** — fix role mapping, add read-only file list + claims overlay
13. **IssueContextTab** — implement structural context display for CoDRAG-pushed issues + on-demand enrichment
14. **Plugin worker extensions** — new data providers (consensus-hotspots, push-summary), new action (enrich-issue), fix agent-knowledge-scope provider

### Phase 4: Wiring

15. **HR Engine push integration** — `push=true` on generate, significance classification
16. **Researcher push integration** — `push=true` on run, significance classification
17. **Custodian push integration** — `push=true` on run, significance classification
18. **Pipeline rebuild hook** — delta snapshot + significance check after rebuild

---

## 10. Success Criteria

1. **CoDRAG dashboard shows config only** — no run history, no employee lists, no operational monitoring. Engine controls, scope editor, push settings, Paperclip connection.
2. **Paperclip plugin shows the full picture** — dashboard widget with consensus hotspots and push summary, per-agent knowledge scope with claims, per-issue structural context.
3. **Push enrichment works end-to-end** — running Researcher produces findings → findings get consensus + structural enrichment → significant findings become Paperclip issues with `Structural Context` section.
4. **Significance filtering prevents noise** — `informational` items never become issues. `mandatory` items always push. `recommended` items respect auto-push settings.
5. **No redundancy** — nothing visible in both CoDRAG dashboard AND Paperclip plugin. Each datum has one home.
6. **Agent scopes editable in CoDRAG only** — Paperclip shows read-only scope view. Configuration happens in one place.
7. **Delta pushes fire** — new hub or removed module after pipeline rebuild → Paperclip issue created (once, deduplicated).

---

## 11. Relationship to Existing Docs

| Document | Role | This spec's relationship |
|----------|------|------------------------|
| `emergence_and_p3_design.md` | Backend: consensus, structural complexity, delta push, claims in prompts | **This spec implements the same backend features** and adds the frontend surfaces |
| `strategic_direction.md` | Architecture: CoDRAG computes, Paperclip acts | **This spec follows the same principle** for all frontend decisions |
| `feature_documentation.md` | Record of what Phase 73.5 built | **This spec builds on top of Phase 73.5** — uses all existing stores, endpoints, MCP resources |
| `plan-boundary-analysis.md` | Boundary analysis: who owns what | **This spec operationalizes those boundaries** into concrete UI decisions |
| `plan_client_aware_delivery.md` | MCP content delivery optimization | **Independent** — client-aware delivery is about MCP payload size, not agent surfaces |

---

## 12. Open Questions

1. **Paperclip SDK data provider granularity** — The current SDK appears to support `ctx.data.register(name, handler)`. Can we return nested objects from data providers, or do they need flat payloads? This affects whether `codebase-health` returns one rich object or we need separate providers.

2. **Role mapping on agent create** — When `push_to_paperclip()` creates an agent, does the current `PaperclipClient.create_agent()` support `adapterConfig.codrag_role`? Need to verify the Paperclip API accepts arbitrary adapter config keys.

3. **Issue description enrichment format** — The structural context section uses markdown. Does Paperclip render markdown in issue descriptions? If not, we need a plain-text format.

4. **Auto-push timing** — Should auto-push happen immediately after engine run (synchronous), or should it be a background task that runs after the engine completes? Synchronous is simpler but blocks the API response.

---

## 13. Implementation Status

> Updated: 2026-04-07 | 19 commits on `feat/phase72-pipeline-refactor` | 27 Python tests passing

### What's Done

| Component | Status | Commits |
|-----------|--------|---------|
| **Consensus scoring** (`get_consensus_scores()` on ObservationStore) | Done | `067f94e2` |
| **StructuralContext** dataclass + `compute_complexity_tier()` | Done | `84191afb` |
| **PushEngine structural enrichment** (`_enrich_with_structural_context()`, `snapshot_store` param) | Done | `d8c553c4` |
| **Delta push** (`push_significant_delta()` on PushEngine) | Done | `4384a62c` |
| **Consensus hotspots in delta MCP resource** + claims steps in prompts | Done | `9a74611d` |
| **Significance classification** (`classify_significance()` with hub_count) | Done | `c89ae6c9`, `7950d28c` |
| **REST endpoints** (`/collaboration/consensus`, `/collaboration/push-summary`) | Done | `5ddf1bd5` |
| **Push enrichment wired into `_push_group()`** (structural + consensus) | Done | `88b708f0` |
| **AgentOpsPanel** rewritten to config-only (engine rows + MCPConnection + PushSettings) | Done | `27858ae8`, `7637d08b` |
| **PushSettings** component (auto-push toggle, significance threshold, Paperclip project) | Done (wired to dashboard state) | `27858ae8`, `7950d28c` |
| **Dashboard hook** maps API response to new EngineStatus shape | Done | `8e10a3e6`, `7637d08b` |
| **Panel registry** updated | Done | `8e10a3e6` |
| **Storybook stories** updated for new interface | Done | `b6a28c32` |
| **CodebaseHealthWidget** (pipeline status, push summary, consensus, delta) | Done | `e4196811` |
| **KnowledgeScopeTab** (read-only scope + claims overlay) | Done | `136c2a35` |
| **IssueContextTab** (structural context parsing + on-demand enrichment) | Done | `2fdd9b19` |
| **Plugin worker** (6 data providers, 3 actions, fixed agent-knowledge-scope) | Done | `d2106869` |
| **Push param on HR endpoint** (actually pushes to Paperclip) | Done | `46f15ee1` |
| **Push param on Researcher/Custodian** (accepted, echoed as `push_requested`) | Stub | `46f15ee1` |

### What's Deferred — Roadmap

These items are explicitly deferred. Each is a small, self-contained task that can be picked up independently.

#### Priority 1: Push Settings Persistence

**What:** `GET/PUT /projects/{pid}/push/settings` endpoints backed by the settings store.
**Why deferred:** Requires wiring `PMPushConfig` (which already has `auto_push`, `min_priority`, `consolidation_strategy` fields) to new REST endpoints and connecting the dashboard's `PushSettings` component to fetch/save from them. Currently push settings live in dashboard React state only (not persisted across refreshes).
**Effort:** Small — 2 endpoints + settings store read/write + dashboard fetch/save wiring.
**Files:** `src/codrag/api/routers/collaboration.py`, `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`

#### Priority 2: Researcher + Custodian Push Execution

**What:** When `push=true` is passed to the researcher/custodian run endpoints, actually push findings to Paperclip via PushEngine (like HR already does).
**Why deferred:** The Researcher and Custodian engines produce different output shapes (research topics, cleanup candidates) than what PushEngine.push() expects (ActionItems). Needs an adapter layer to convert engine output → ActionItems → PushEngine.
**Effort:** Medium — adapter functions for each engine output type, PushEngine integration, tests.
**Files:** `src/codrag/api/routers/agents.py`, possibly new adapter functions in each engine.

#### Priority 3: Push Activity Logging

**What:** Log push events to `ActivityStore` when PushEngine successfully pushes issues. This makes the `/collaboration/push-summary` endpoint return real data instead of always 0.
**Why deferred:** Requires threading the `CollaborationHub` through to PushEngine, or having the API layer log after push completes. The plumbing is straightforward but touches several files.
**Effort:** Small — add `hub.activity.record()` calls after successful pushes in PushEngine or the API layer.
**Files:** `src/codrag/adapters/push_engine.py` or `src/codrag/api/routers/agents.py`

#### Priority 4: Pipeline Rebuild → Delta Push

**What:** After pipeline rebuild completes, automatically capture a graph snapshot, compute delta, and push significant changes to Paperclip.
**Why deferred:** The `POST /pipeline/rebuild` endpoint exists but the post-rebuild hook needs to call `CollaborationHub.snapshots.capture()` then `PushEngine.push_significant_delta()`. Requires both services to be available in the rebuild handler.
**Effort:** Small — post-rebuild hook in the pipeline endpoint or watcher.
**Files:** `src/codrag/api/routers/projects/watch.py` or `src/codrag/core/watcher.py`

#### Priority 5: SettingsPage Enhancement

**What:** Enhance the Paperclip plugin's Settings page with daemon URL field, project ID, auto-context toggle, and push settings link.
**Why deferred:** The current 55-line implementation works for basic config. Enhancement is nice-to-have.
**Effort:** Trivial — UI-only change in `packages/paperclip-plugin-codrag/src/ui/SettingsPage.tsx`.

### Test Coverage

| Test file | Tests | Covers |
|-----------|-------|--------|
| `tests/test_consensus_scoring.py` | 5 | `get_consensus_scores()` edge cases |
| `tests/test_structural_enrichment.py` | 9 | `StructuralContext`, `compute_complexity_tier()`, `_enrich_with_structural_context()` |
| `tests/test_delta_push.py` | 5 | `push_significant_delta()` dedup + filtering |
| `tests/test_significance.py` | 6 | `classify_significance()` including hub_count override |
| `tests/test_push_settings_api.py` | 2 | `/collaboration/consensus` endpoint |
| **Total** | **27** | |

**Not tested (noted for future):**
- `/collaboration/push-summary` endpoint (returns 0 until activity logging is added)
- `enrich-issue` plugin action (requires Paperclip SDK test harness)
- Dashboard rendering (requires browser/Storybook test infrastructure)

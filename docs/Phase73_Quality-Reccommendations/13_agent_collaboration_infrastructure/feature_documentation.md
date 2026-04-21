# Agent Collaboration Infrastructure — Feature Documentation

> Phase 73.5 | Implemented 2026-04-06 | 19 commits, 76 tests | Paperclip-first direction

---

## What This Feature Does

Agent Collaboration Infrastructure turns Prep from a code intelligence library that agents query independently into a **shared awareness layer** where agents can see each other's work, avoid stepping on each other, and coordinate through the codebase graph.

Before this feature, Prep's agents — Pi (7 background scenarios), Researcher, Custodian, and external agents via MCP — operated in complete isolation. Each agent queried the observation store, the trace graph, and audit findings without knowing what any other agent was doing. This created real coordination failures: the Researcher would investigate a file the Custodian was about to delete, two agents would push overlapping findings to Paperclip with no way to trace which agent found what, and the Watchdog would detect critical changes that no other agent would see until its next scheduled run.

This feature fixes those problems with two layers of capabilities:

**Layer 1 — Awareness:** Every observation now carries metadata about which agent created it (`created_by`) and who should see it (`visibility`). Agents can browse each other's recent work through dedicated MCP resources (memory, cross-agent findings). Internal activity tracking records what every agent did and when.

**Layer 2 — Coordination:** Agents can claim files they're actively working on so other agents skip those areas. Prep captures structural snapshots of the codebase graph after every pipeline rebuild and can compute what changed between any two points in time. When agents disagree about the same file, the system detects the conflict and pushes it to Paperclip as an issue.

### Paperclip-First Direction

After the initial build, we reframed the collaboration infrastructure around a key insight: **Prep should provide structural intelligence that enriches Paperclip's existing coordination, not build a parallel PM system.** Paperclip already manages agents, tracks activity, routes tasks, and maintains an audit trail. Prep should tell Paperclip things only Prep can know — what changed in the dependency graph, which files are structurally connected, where agents are about to collide — and let Paperclip act on that intelligence.

This led to removing the `prep://activity` and `prep://conflicts` MCP resources (Paperclip has richer versions of both), replacing the `prep-triage` prompt with `prep-enrich` (Prep provides structural enrichment, Paperclip does triage), and adding conflict push to Paperclip as tagged issues.

---

## What Was Built

### Collaboration Package (`src/prep/services/collaboration/`)

A new Python package with a `CollaborationHub` facade composing four stores:

**ActivityStore** (`activity.py`) — An append-only log of agent actions. Every time an agent completes a scenario (Pi Watchdog runs a delta scan, Researcher selects a topic, Custodian discovers dead code), it writes a one-line entry with its role name, the action taken, and a summary. Entries are queryable by project and time range. Auto-prunes entries older than 30 days when the table exceeds 1000 rows. Used internally by FastAPI routes and the Paperclip plugin's data providers (not exposed as an MCP resource — Paperclip has its own richer activity feed).

**ClaimStore** (`claims.py`) — Soft file claims with auto-expiry. When the Researcher starts investigating a file, it creates a claim on that file with a reason and a TTL (default 24 hours). The Custodian checks claims before marking files for deletion — if another agent has claimed a file, the Custodian skips it. Claims support directory prefixes (claiming `src/auth/` covers all files under that path). Expired claims are cleaned up lazily on the next write or query. Used by Researcher (creates claims) and Custodian (checks claims).

**GraphSnapshotStore** (`snapshots.py`) — Captures hub files and module structure at index rebuild time and computes structural deltas between any two snapshots. After every Pi Watchdog run (triggered by pipeline completion), a snapshot is captured containing the current hub file rankings and module cluster data. The `compute_delta()` method diffs two snapshots and returns a `StructuralDelta` showing which hubs were added, removed, or changed rank, and which modules were added, removed, or changed size by more than 20%. Only the 10 most recent snapshots are kept per project. Used by the `prep://{pid}/delta` MCP resource.

**ConflictStore + ConflictDetector** (`conflicts.py`) — Detects when two agents have observations about the same file (a proximity signal that they may disagree). The `ConflictDetector` groups attributed observations by file path and creates an `AgentConflict` record when two different agents both have observations on the same file. Conflicts are stored with both agents' assessments and default to `deferred` resolution until a human or automation resolves them. The PushEngine runs conflict detection before pushing findings to Paperclip, then pushes detected conflicts to Paperclip as tagged issues (not exposed as an MCP resource — conflicts flow to Paperclip's issue tracker instead).

**CollaborationHub** (`__init__.py`) — Single facade composing all four stores. Initialized once during daemon startup (when the file watcher starts). Agent engines and API routes access collaboration features through this hub. A module-level singleton pattern matches the existing `observation_store` singleton.

### Observation Store Changes (`src/prep/services/observation_store.py`)

Two new columns added to the `observations` table:

- **`created_by`** (`TEXT`, default `NULL`) — Which agent created this observation. Values like `"pi/watchdog"`, `"researcher"`, `"custodian"`, or `"human"` for observations saved via the MCP tool. Existing observations get `NULL` (backward compatible).

- **`visibility`** (`TEXT`, default `'shared'`) — Who should see this observation. `"shared"` (default, visible to all), `"private"` (only the creating agent's role), or `"internal"` (visible to Prep agents but not external MCP clients).

Schema migration runs safely on every startup (ALTER TABLE wrapped in try/except for idempotency).

New query method **`get_by_agent(project_id, created_by, ...)`** returns observations filtered by creator, with options for staleness and visibility filtering.

New query method **`get_all_attributed(project_id, limit)`** returns all observations that have a `created_by` value set (used by PushEngine for conflict detection).

### FastAPI Routes (`src/prep/api/routers/collaboration.py`)

Seven new REST endpoints on the daemon (port 8400):

| Endpoint | Method | Purpose |
|---|---|---|
| `/projects/{pid}/collaboration/activity` | GET | Recent agent activity entries |
| `/projects/{pid}/collaboration/observations` | GET | Observations filtered by `created_by` |
| `/projects/{pid}/collaboration/delta` | GET | Structural delta since timestamp (default 7 days) |
| `/projects/{pid}/collaboration/conflicts` | GET | Active (unresolved) agent conflicts |
| `/projects/{pid}/collaboration/conflicts/{id}/resolve` | POST | Resolve a conflict |
| `/projects/{pid}/collaboration/claims` | GET | Active file claims |
| `/projects/{pid}/collaboration/claims` | POST | Create a new claim |
| `/projects/{pid}/collaboration/claims/{id}` | DELETE | Release a claim |

These endpoints are called by the MCP server via HTTP proxy — the MCP server never accesses SQLite directly.

### MCP Resources (`src/prep/mcp/collaboration_handlers.py`)

Three MCP resources browsable via `@` mention in any MCP client:

**`prep://{pid}/memory/{role}`** — An agent's own prior observations, filtered by `created_by`. When a Researcher starts a new session, it can `@prep://memory/researcher` to see what it found last time — without making a tool call. Formatted as a chronological markdown list with dates, content, file paths, and categories. Returns "No observations from this agent" when empty.

**`prep://{pid}/agents/{role}/findings`** — Another agent's recent findings, filtered to `visibility="shared"`. Lets any agent browse what another agent discovered. The Dispatcher can see what the Researcher found; the Architect can see what the Custodian flagged. Same format as memory, but cross-agent.

**`prep://{pid}/delta`** — What changed structurally in the codebase graph since the last snapshot. Shows new/removed/rank-changed hub files and new/removed/size-changed modules. This is data no other tool can provide — git log shows file changes, but this shows structural shifts (new hubs emerging, modules splitting, dependency rankings changing). Returns "No structural changes detected" if the latest two snapshots are identical. Returns guidance text if no snapshots exist yet.

**Removed resources (Paperclip-first revision):**

- ~~`prep://{pid}/activity`~~ — Removed. Paperclip has a richer activity/audit trail. The `ActivityStore` remains as internal infrastructure and is accessible via FastAPI routes and the Paperclip plugin's `structural-delta` data provider.
- ~~`prep://{pid}/conflicts`~~ — Removed. Conflicts now flow to Paperclip as tagged issues via `PushEngine._push_conflict_to_pm()`. The `ConflictStore` remains for persistent records and is accessible via FastAPI routes.

All resources include `audience` annotations for MCP clients and handle empty state gracefully.

### MCP Prompts

Three MCP prompts available as `/` commands in any MCP client:

**`prep-handoff`** (`from_role`, `to_role`, optional `task`) — Structured context transfer between agent sessions. Returns a 4-step workflow: review the prior agent's memory and findings, check the structural delta for changes, search for relevant code, and summarize the handoff. Designed for multi-agent workflows where one agent finishes and another picks up.

**`prep-scope`** (`role`) — Shows what an agent role owns and what's happening in its domain. Pulls structural overview, memory, and delta filtered to the role. Useful for understanding an agent's current scope and responsibilities.

**`prep-enrich`** (optional `scope`) — Enriches findings with structural intelligence from Prep. Walks through: get audit findings, assess blast radius via `prep_impact`, identify hub vs leaf file involvement, check cross-module scope, and summarize each finding with structural context. This gives Paperclip the *inputs* for triage (blast radius, hub involvement, cross-module flag) without doing the triage itself.

**Replaced prompt:** `prep-triage` was renamed to `prep-enrich` in the Paperclip-first revision. Triage (clustering findings, assigning to agents) is Paperclip's job. Prep provides structural evidence that helps Paperclip make better decisions.

These prompts are distinct from the 5 existing Prep prompts (onboard, review, plan, investigate, health) which are human developer workflows. The collaboration prompts are agent coordination workflows.

### Agent Engine Integration

**Pi Agent** (`services/pi_agent.py`):
- All 9 `_save_observation()` calls now pass `scenario=` for attribution (e.g., `"pi/watchdog"`, `"pi/doctor"`, `"pi/geologist"`).
- All 7 scenarios log activity entries via `_log_activity()` on completion.
- The Watchdog captures a graph snapshot after every delta scan via `_capture_graph_snapshot()`, which reads hub files and module clusters from the trace index.
- `PiAgent.__init__` and `init_pi_agent()` accept an optional `collab_hub` parameter.

**Researcher Engine** (`agents/researcher/engine.py`):
- Claims affected files at the start of `research_topic()` (up to 5 files per topic, 24h TTL).
- Logs activity when starting research on a topic.
- Accesses the hub through `self._core.collab` (via AgentCore).

**Custodian Engine** (`agents/custodian/engine.py`):
- Checks claims before marking files as deletion candidates in `discover()`. If another agent (not the Custodian itself) has claimed a file, it's skipped with a log message.
- Accesses the hub through `self._core.collab`.

**PushEngine** (`adapters/push_engine.py`):
- Runs conflict detection after consolidation (Step 2b), before pushing to Paperclip.
- Queries all attributed observations via `get_all_attributed()`, passes them to `ConflictDetector`, and stores any detected conflicts.
- Pushes detected conflicts to Paperclip as tagged issues (Step 2c) via `_push_conflict_to_pm()`. Each conflict becomes a Paperclip issue with both agents' assessments, deduped via `prep-address` embedded in the description.
- `PushResult` now includes a `conflicts` list and `conflicts_detected` count.
- Accepts optional `conflict_detector` and `conflict_store` in `__init__`.

**AgentCore** (`agents/core.py`):
- Accepts optional `collab_hub` in `__init__`, exposed as `self.collab`.
- `save_observation()` passes `created_by` and `visibility` through to the observation store.
- The `_make_core()` helper in `api/routers/agents.py` automatically injects the hub from the singleton.

### MCP Server Integration (`mcp/server.py`)

Four thin integration points — no new logic in server.py, all delegated to `collaboration_handlers.py`:

1. `handle_resources_list` appends 3 collaboration resources (memory, agent_findings, delta) to the existing 7.
2. `handle_resources_read` tries `parse_collaboration_uri()` before the existing if/elif chain. If it matches, delegates to `_read_collaboration_resource()` which calls the daemon's collaboration API endpoints and formats the response. Routes: `memory/{role}`, `agents/{role}/findings`, `delta`.
3. `handle_prompts_list` appends 3 collaboration prompts (handoff, scope, enrich) to the existing 5.
4. `handle_prompts_get` tries `get_collaboration_prompt_messages()` before the existing branches.

The `prep_observe` tool (save action) now accepts an optional `created_by` parameter, passed through the tool schema, dispatch, API endpoint, and observation store.

### Daemon Integration (`server.py`, `api/routers/projects/watch.py`)

- The collaboration router is registered alongside existing routers in the FastAPI app.
- The CollaborationHub singleton is initialized in `watch.py` when the file watcher starts (before Pi agent init), using the same `prep_settings.db` path from the settings store.
- The hub is passed to `init_pi_agent()` so Pi scenarios can log activity and capture snapshots.

---

## What This Accomplishes

### For Prep's Internal Agents

**Agents know who did what.** Every observation carries attribution. When the Librarian cleans up stale observations, it can see that an observation was created by `pi/watchdog` vs `researcher` and prioritize accordingly. When the Dispatcher triages findings, it can see if the Researcher already investigated the same area.

**Agents don't step on each other.** When the Researcher starts investigating `src/auth/`, it claims those files. If the Custodian runs next and finds dead code in `src/auth/login.py`, it checks the claim store and skips that file — logging "Skipped src/auth/login.py — claimed by another agent." The claim expires after 24 hours, so it's a soft coordination signal, not a hard lock.

**Agents see structural changes.** After every pipeline rebuild, the Watchdog captures a graph snapshot. Any agent (or MCP client) can ask "what changed structurally since my last run?" and get a concrete answer: "src/gateway.py became a new hub with 14 dependents, the auth module merged with auth_legacy, the logging concern expanded to 45 files." This is data only Prep can provide — it requires the dependency graph.

**Disagreements are surfaced and pushed to Paperclip.** When the PushEngine consolidates findings for Paperclip, it checks if two agents have observations about the same file. If the Researcher says "important JWT pattern here" and the Custodian says "dead code, safe to delete," that conflict is stored locally and pushed to Paperclip as a tagged issue (e.g., "Prep Conflict: src/auth.py — researcher vs custodian"). The user sees the disagreement in their normal Paperclip issue tracker before either recommendation is acted on.

### For External Agents (via MCP)

**Session continuity without tool calls.** An agent starting a new session can `@prep://memory/researcher` to get its prior work as reference context in the system prompt — no tool call needed. This is faster and doesn't burn tool-call budget.

**Cross-agent visibility.** A Paperclip-managed agent can `@prep://agents/custodian/findings` to see what the Custodian found without querying the Custodian directly. Agents coordinate through shared state, not direct messaging.

**Structured handoff.** The `prep-handoff` prompt packages everything the receiving agent needs: the prior agent's memory, findings, the activity timeline, and any active conflicts. One prompt replaces what would otherwise be 3-4 tool calls to assemble the same context.

### For Paperclip Users

**Agent traceability.** When a finding appears in Paperclip, the `conflicts_detected` count on the push result tells you if agents disagreed. The activity feed shows the timeline of how the finding was discovered.

**Conflict resolution.** The `/conflicts/{id}/resolve` endpoint lets Paperclip (or a human) mark conflicts as resolved with a resolution strategy (`agent_a_wins`, `agent_b_wins`, `human_review`). This closes the feedback loop.

**Evidence-based task assignment.** The structural delta resource tells you what changed in the codebase — if a new hub file emerged or a module split, that's signal for which agents should be re-scoped.

---

## Architecture: How It Wires Up

### Data Flow: Agent Observation → MCP Resource / Paperclip

```
1. Pi Watchdog completes delta scan
2. Calls _save_observation(content="3 new, 1 resolved", scenario="pi/watchdog")
3. ObservationStore.save() writes to SQLite with created_by="pi/watchdog"
4. Calls _log_activity("watchdog", "delta_scan_complete", "3 new, 1 resolved")
5. ActivityStore.log() writes to agent_activity table
6. Calls _capture_graph_snapshot()
7. GraphSnapshotStore.capture() writes hub + module data to graph_snapshots table

Later, an MCP client reads @prep://memory/pi/watchdog:
8. MCP server calls _read_collaboration_resource("memory", {"role": "pi/watchdog"})
9. Which calls self._api_get("/projects/{pid}/collaboration/observations?created_by=pi/watchdog")
10. Daemon's FastAPI route calls observation_store.get_by_agent()
11. Returns observations → formatted as markdown list → sent to client

Later, Paperclip plugin fetches structural-delta data provider:
12. Plugin calls GET /projects/{pid}/collaboration/delta
13. Daemon's FastAPI route calls hub.snapshots.get_latest_two() + compute_delta()
14. Returns StructuralDelta → plugin renders in Paperclip UI
```

### Data Flow: Researcher Claims → Custodian Skips

```
1. Researcher calls research_topic(topic) on a topic with affected_files=["src/auth/login.py"]
2. self._core.collab.claims.claim("proj-1", "researcher", "src/auth/login.py", "Researching: auth")
3. ClaimStore writes to soft_claims table with 24h TTL

Later, Custodian runs discover():
4. For each dead code finding, calls _is_claimed_by_other(file_path)
5. ClaimStore queries: SELECT path FROM soft_claims WHERE project_id=? AND expires_at>?
6. Finds the researcher's claim, returns True
7. Custodian logs "Skipping src/auth/login.py — claimed by another agent" and continues
```

### Data Flow: Conflict Detection → Push to Paperclip

```
1. PushEngine.push() consolidates ActionItems into groups (Step 1-2)
2. Step 2b: Calls observation_store.get_all_attributed(project_id) → all observations with created_by
3. ConflictDetector.detect_from_observations() groups by file_path
4. Finds src/auth.py has observations from both "researcher" and "custodian"
5. Creates AgentConflict(agent_a="researcher", agent_b="custodian", ...)
6. ConflictStore.save() writes to agent_conflicts table
7. Step 2c: For each conflict, calls _push_conflict_to_pm()
8. Checks dedup: adapter.find_issue_by_prep_address("prep://pid/CONFLICT-abc123")
9. If not exists: adapter.create_issue() → creates Paperclip issue with both assessments
10. PushResult.conflicts populated → Paperclip sees conflicts_detected count
```

### Initialization Chain

```
User clicks "Start Watching" in dashboard
  → POST /projects/{pid}/watch
    → watch.py: init_collaboration(settings.db_path)  ← CollaborationHub singleton created
    → watch.py: init_pi_agent(project_id, index_dir, project_root, collab_hub=hub)
    → PiAgent stores self._collab = hub

Pipeline completes
  → PipelineOrchestrator calls pi.on_pipeline_complete()
    → PiAgent._run_watchdog() uses self._collab for activity + snapshots

Agent API called
  → agents.py: _make_core(pid, idx_dir, root) → AgentCore(collab_hub=get_collaboration_hub())
    → ResearcherEngine uses self._core.collab.claims
    → CustodianEngine uses self._core.collab.claims
```

---

## Paperclip Plugin Integration

The Paperclip plugin (`packages/paperclip-plugin-prep/src/worker/index.ts`) was extended with collaboration capabilities:

**Observation Attribution** — The `prep:observe` tool now includes `created_by: 'paperclip-agent'` in every POST body. When a Paperclip-managed agent saves an observation through the plugin, it's automatically attributed.

**Data Providers** — Two new data providers expose collaboration data in the Paperclip UI:
- `structural-delta` — Calls `GET /projects/{pid}/collaboration/delta` to show recent structural changes (new hubs, removed modules, rank changes) in a Paperclip dashboard widget.
- `agent-claims` — Calls `GET /projects/{pid}/collaboration/claims` to show files currently claimed by agents, displayed in the agent detail tab.

The plugin now has 5 tools, 4 data providers, 2 actions, and 1 job.

---

## What's Not Built Yet

### P3 Items (Deferred for User Feedback)

**Claims Push as Paperclip Agent Metadata** — When an agent creates a claim, update the agent's metadata in Paperclip so routing logic can factor in claims before assigning tasks. Requires Paperclip agent metadata API support.

**Delta Push as Paperclip Issues** — After Pi Watchdog captures a snapshot with significant structural changes (new/removed hubs or modules), proactively create Paperclip issues alerting users. Requires Pi to have Paperclip adapter access (or a "pending push" pattern via PushEngine).

### Layer 3 Roadmap (Emergence)

The design doc (`README.md`) describes a third layer — **Emergence** — where agents get smarter together based on collective outcomes. This layer is roadmapped but not implemented:

**Decision History Tracking** — Record what each agent recommends and track whether it was accepted, rejected, or fixed. Needs real push-to-Paperclip usage data. Estimated: 3-4 days.

**Consensus Scoring** — When 2+ agents independently flag the same area, boost that finding's priority. Needs enough attributed observation volume. Estimated: 2-3 days.

**Evidence-Based Task Routing** — Prep provides structural evidence (scope size, blast radius, hub involvement) to help Paperclip route tasks to the right agent class. Needs decision history to calibrate. Estimated: 3-4 days.

**Capability Attestation** — Agents query Prep to assess whether they can handle a task before accepting it. Needs task routing + stable tier system. Estimated: 2-3 days.

**Adaptive Role Scoping** — Roles drift over time based on decision history. Weekly analysis suggests scope adjustments. Needs months of data. Estimated: 5-7 days.

Additional data sources for snapshots (cycle detection, structured cross-cutting concerns) are also deferred — the trace graph doesn't currently expose these as structured data.

---

## Files Changed

### New Files (11 source + 8 test)

| File | Lines | Purpose |
|---|---|---|
| `src/prep/services/collaboration/__init__.py` | ~40 | CollaborationHub facade + singleton |
| `src/prep/services/collaboration/activity.py` | ~170 | ActivityStore |
| `src/prep/services/collaboration/claims.py` | ~170 | ClaimStore |
| `src/prep/services/collaboration/snapshots.py` | ~230 | GraphSnapshotStore + delta computation |
| `src/prep/services/collaboration/conflicts.py` | ~190 | ConflictStore + ConflictDetector |
| `src/prep/api/routers/collaboration.py` | ~150 | FastAPI routes |
| `src/prep/mcp/collaboration_handlers.py` | ~340 | MCP resource formatters + prompt handlers |
| `tests/test_observation_attribution.py` | ~70 | Observation store attribution tests |
| `tests/test_activity_store.py` | ~70 | ActivityStore tests |
| `tests/test_claim_store.py` | ~75 | ClaimStore tests |
| `tests/test_graph_snapshots.py` | ~90 | GraphSnapshotStore tests |
| `tests/test_conflict_store.py` | ~90 | ConflictStore + detector tests |
| `tests/test_collaboration_hub.py` | ~60 | Integration tests |
| `tests/test_collab_api.py` | ~90 | FastAPI route tests |
| `tests/test_collab_resources.py` | ~120 | MCP handler tests |

### Modified Files (12)

| File | Change |
|---|---|
| `src/prep/services/observation_store.py` | `created_by` + `visibility` columns, `get_by_agent()`, `get_all_attributed()` |
| `src/prep/agents/shared/prep_data.py` | `created_by` + `visibility` passthrough |
| `src/prep/agents/core.py` | `collab_hub` param, `created_by` passthrough |
| `src/prep/services/pi_agent.py` | `collab_hub`, `scenario=` attribution, `_log_activity()`, `_capture_graph_snapshot()` |
| `src/prep/agents/researcher/engine.py` | Claim creation + activity logging |
| `src/prep/agents/custodian/engine.py` | Claim checking + `_is_claimed_by_other()` |
| `src/prep/adapters/push_engine.py` | Conflict detection, `conflict_detector`/`conflict_store` params, `_push_conflict_to_pm()` |
| `src/prep/adapters/pm_models.py` | `conflicts` field on PushResult |
| `src/prep/mcp_tools.py` | `created_by` on `prep_save_observation` schema |
| `src/prep/mcp/server.py` | 4 integration points for resources + prompts, `created_by` on tool handler |
| `src/prep/server.py` | Collaboration router registration |
| `src/prep/api/routers/projects/watch.py` | Hub initialization + pass to Pi |
| `src/prep/api/routers/observations.py` | `created_by` on save endpoint |
| `src/prep/api/routers/agents.py` | `_make_core()` helper with hub injection |
| `packages/paperclip-plugin-prep/src/worker/index.ts` | `created_by` on observe tool, 2 data providers (structural-delta, agent-claims) |

---

## Testing

76 tests across 8 test files, all passing:

- 9 observation attribution tests (save/query with `created_by` + `visibility`)
- 8 activity store tests (log, query, ordering, filtering, pruning)
- 9 claim store tests (claim, release, expiry, prefix matching, exclusion)
- 9 graph snapshot tests (capture, delta computation for hubs + modules, pruning)
- 6 conflict store + detector tests (save, resolve, observation-level detection)
- 4 integration tests (hub init, cross-store workflows)
- 8 API route tests (all 7 endpoints)
- 22 MCP handler tests (URI parsing, 3 resource formatters, 2 internal formatters, 3 prompts, negative tests for removed resources/prompts)

Test updates in the Paperclip-first revision:
- `test_parse_uri_activity` and `test_parse_uri_conflicts` replaced with `test_parse_uri_activity_not_routed` and `test_parse_uri_conflicts_not_routed` (verify removed resources return `None`)
- `test_get_collaboration_resources_returns_5` → `test_get_collaboration_resources_returns_3` (verify activity/conflicts not in list)
- `test_prompt_triage_returns_messages` → `test_prompt_triage_no_longer_exists` + `test_prompt_enrich_returns_messages`
- Prompt tests verify `@prep://activity` and `@prep://conflicts` no longer appear in prompt text

All changes are backward compatible — no existing tests outside collaboration files were modified.

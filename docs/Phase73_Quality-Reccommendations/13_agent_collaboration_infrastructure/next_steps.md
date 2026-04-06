# Agent Collaboration Infrastructure — Session Summary & Next Steps

> Date: 2026-04-06 | Recording everything accomplished and everything remaining

---

## 1. What We Accomplished This Session

### 1.1 Concept Development

We started from the MCP Ecosystem Optimization Design (doc 12) and asked: "Are the planned MCP prompts and resources enough for our agents, or should we think of something new?" This led to the discovery that CoDRAG's agents operate in complete isolation — they share a data store but have zero awareness of each other's work. We identified a new product concept: **Agent Collaboration Infrastructure** — turning CoDRAG from a code intelligence library into the coordination substrate for multi-agent development teams.

### 1.2 Three-Layer Architecture

We designed a three-layer system:

- **Layer 1: Awareness** — Agents can see who did what. Agent-attributed observations, per-role memory resources, cross-agent findings, activity feed.
- **Layer 2: Coordination** — Agents don't step on each other. Structural delta detection, conflict detection, soft claims, handoff workflows.
- **Layer 3: Emergence** — Agents get smarter together. Decision history tracking, consensus scoring, evidence-based task routing, capability attestation, adaptive role scoping.

Decided to **build Layers 1+2** and **roadmap Layer 3**.

### 1.3 Design Doc (README.md)

**File:** `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/README.md`

Comprehensive design document covering:

- Problem statement with 5 concrete failure scenarios from existing agents
- Town square model diagram (library → shared awareness layer)
- Full Layer 1 design: `Observation.created_by` + `visibility` fields, per-role memory resources (`codrag://{pid}/memory/{role}`), cross-agent findings resources (`codrag://{pid}/agents/{role}/findings`), activity feed resource (`codrag://{pid}/activity`)
- Full Layer 2 design: structural delta resource (`codrag://{pid}/delta`), conflict detection (`AgentConflict` model + `ConflictDetector`), soft claims (`SoftClaim` model + `ClaimStore`), dependency declarations on plans, shared computation cache
- Full Layer 3 design (roadmapped): decision history, consensus scoring, task complexity analysis, capability attestation, adaptive role scoping
- Complete MCP primitive mapping: 6 new resources, 4 new prompts, 0 new tools
- Full SQL schema for 4 new tables + 2 column additions
- 4-phase implementation plan with effort estimates
- Relationship mapping to Phases 65, 66, 67, 73.3b, 73.4
- Research references from multi-agent systems literature
- Success criteria

### 1.4 Paperclip Concept Doc

**File:** `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/paperclip_concept.md`

Simpler document aimed at Paperclip users explaining:

- What agent collaboration infrastructure is (plain language)
- Three capabilities: agent memory, structural change detection, conflict detection
- Table of 6 MCP resources and 4 MCP prompts agents get
- Architecture diagram showing CoDRAG intelligence + Paperclip orchestration
- 5 concrete integration points (task assignment, agent startup, handoff, conflict resolution, consensus prioritization)
- What makes observation-mediated collaboration different from message-passing
- Getting started section with zero-config adoption path

### 1.5 Implementation Spec

**File:** `docs/superpowers/specs/2026-04-06-agent-collaboration-infrastructure-design.md`

Detailed implementation specification covering:

- Explicit scope: what's built (Layers 1+2), what's not (Layer 3), what's untouched (existing prompts from doc 14, existing resources, existing tools)
- Package structure: `src/codrag/services/collaboration/` with 5 modules + `src/codrag/mcp/collaboration_handlers.py`
- `CollaborationHub` facade design
- Full data models with Python dataclasses and SQL DDL for every table
- Complete API signatures for every store (ActivityStore, GraphSnapshotStore, ConflictStore + ConflictDetector, ClaimStore)
- All 5 MCP resource content formats with example markdown output
- All 3 MCP prompt templates with argument specs
- Agent engine integration details for Pi, Researcher, Custodian, AgentCore, PushEngine
- MCP tool schema change for `codrag_observe`
- Testing strategy: 5 unit test files + 3 integration test files
- Layer 3 roadmap with effort estimates and dependency chains

### 1.6 Critical Architecture Review (Scrutiny Pass)

We reverse-engineered the spec against the actual codebase and found **9 issues**, ranging from critical to low severity. This is the most important output of the session because it prevents building something that doesn't wire up.

---

## 2. The 9 Issues Found (Detailed)

### Issue 1: No Structured Cycle Data Available

**Severity:** Medium

**Problem:** The spec defines `GraphSnapshot.cycles: List[List[str]]` to capture import cycles for delta detection. However, there is no API endpoint, method, or data structure anywhere in the codebase that returns import cycles as structured data. The "124 import cycles present" text in the atlas is LLM-generated prose, not queryable data.

**Files investigated:**
- Searched for `import_cycles`, `find_cycles`, `detect_cycles` across all of `src/codrag/` — zero matches
- `src/codrag/core/atlas/generator.py:418-434` — cross-cutting section is free-text, not structured
- `src/codrag/core/trace/` — no cycle detection methods found

**Resolution options:**
- **A (recommended): Drop cycles from snapshot for now.** Snapshot captures hubs + modules only. Cycle detection becomes a Layer 3 or separate enhancement. This is honest — we don't have the data source.
- **B: Build cycle detection first.** Add a method to the trace index that walks the import graph and returns strongly connected components. This is real work (probably 2-3 days) and should be a separate task.

**Impact if not fixed:** Snapshot capture would crash or return empty cycles, making the delta resource partially useless.

### Issue 2: No Structured Cross-Cutting Data Available

**Severity:** Medium

**Problem:** Same issue as #1. The spec defines `cross_cutting: Dict[str, int]` (concern name → file count), but `cross_cutting` in the atlas generator (line 434) is a free-text string assembled from hub files and shared domain tags. There's no `{concern: file_count}` map.

**Files investigated:**
- `src/codrag/core/atlas/generator.py:418-434` — `cross_parts` is a list of strings like `"Hub files: config.py (168 edges)"` and `"Shared domains: ui, dashboard, typescript"`, concatenated into prose
- No structured cross-cutting data model exists

**Resolution options:**
- **A (recommended): Replace with structured hub data + shared domain tags.** We DO have structured data for hub files (via `/trace/hub_files`) and domain tags per module (via cluster data). Rename `cross_cutting` to something like `shared_domains` and capture `{domain_tag: [module_names]}` instead.
- **B: Drop from snapshot.** Simplest, but loses a useful dimension.

**Impact if not fixed:** Snapshot would either crash or contain meaningless data for cross-cutting delta.

### Issue 3: Pi Agent Has No CollaborationHub Reference

**Severity:** High

**Problem:** The spec shows Pi calling `self._collab_hub.activity.log(...)` and `self._collab_hub.snapshots.capture(...)`. But `PiAgent.__init__` accepts only `(project_id, index_dir, project_root)`. There's no way to get the hub into Pi.

**Files investigated:**
- `src/codrag/services/pi_agent.py:60-68` — init signature
- `src/codrag/services/pi_agent.py:1157-1170` — `init_pi_agent()` factory function
- `src/codrag/services/pipeline/orchestrator.py:1241-1247` — where Pi is triggered

**Resolution:** Add `collab_hub: Optional[CollaborationHub] = None` to both `PiAgent.__init__` and `init_pi_agent()`. The daemon's startup code creates the hub first, then passes it when initializing Pi. All hub access in Pi is guarded with `if self._collab_hub:` for backward compatibility.

**Init chain:** `server.py startup` → `init_pi_agent(project_id, index_dir, project_root, collab_hub=hub)` → `PiAgent(project_id, index_dir, project_root, collab_hub=hub)`.

**Impact if not fixed:** All activity logging and snapshot capture in Pi would be dead code.

### Issue 4: PushEngine Has No ConflictDetector Reference

**Severity:** High

**Problem:** The spec says `if self._conflict_detector:` in `PushEngine.push()`, but PushEngine is initialized with `(adapter, consolidator)` only. The factory function `create_push_engine(config)` at `push_engine.py:295` creates `PushEngine(adapter, Consolidator())` — no conflict detector.

**Files investigated:**
- `src/codrag/adapters/push_engine.py:44-50` — init signature
- `src/codrag/adapters/push_engine.py:280-295` — factory function

**Resolution:** Add optional `conflict_detector: Optional[ConflictDetector] = None` and `conflict_store: Optional[ConflictStore] = None` to `PushEngine.__init__`. The factory function should accept these from its caller. When running without collaboration infrastructure (e.g., standalone CLI), these are `None` and conflict detection is skipped.

**Impact if not fixed:** Conflict detection during push would be dead code.

### Issue 5: Engine Examples Use `self._collab_hub` Inconsistently

**Severity:** Medium

**Problem:** The spec adds `collab_hub` to `AgentCore` as `self.collab`. But the Researcher and Custodian engine examples use `self._collab_hub` directly, as if they have their own hub reference. They should go through `self._core.collab`.

**Files investigated:**
- Spec section "AgentCore" — adds `self.collab = collab_hub`
- Spec section "Researcher Engine" — uses `self._collab_hub.claims.claim(...)` (wrong)
- Spec section "Custodian Engine" — uses `self._collab_hub.claims.is_claimed(...)` (wrong)

**Resolution:** Standardize all engine access through `self._core.collab`:
- Researcher: `self._core.collab.claims.claim(...)` (guarded with `if self._core and self._core.collab:`)
- Custodian: `self._core.collab.claims.is_claimed(...)` (same guard)

This is correct because engines already have `self._core: AgentCore`. Adding a separate hub reference would create two paths to the same data.

**Impact if not fixed:** Implementation would have to decide which pattern to use, wasting time. Risk of engines bypassing AgentCore.

### Issue 6: MCP Server Is an HTTP Proxy — Cannot Access SQLite Directly (CRITICAL)

**Severity:** Critical

**Problem:** This is the biggest structural issue in the spec. `MCPServer` (server.py:100) is an HTTP proxy to the daemon at :8400. It does NOT have direct access to SQLite databases. It calls `self._api_get()` and `self._api_post()` to reach the daemon's FastAPI endpoints.

But the spec designs `CollaborationHub` with direct SQLite access (`db_path: Path`) and has collaboration_handlers.py calling hub methods directly. This architecture doesn't match the existing pattern.

**Files investigated:**
- `src/codrag/mcp/server.py:100-122` — MCPServer.__init__: stores `daemon_url`, creates `httpx.AsyncClient`, zero SQLite imports
- `src/codrag/mcp/server.py:2092-2184` — handle_resources_read: calls `self._api_get()` for data
- `src/codrag/mcp/server.py:2189-2320` — resource content generators: all use `self._api_get()` to fetch data from daemon

**The existing architecture:**
```
MCP Client (Claude Code, Cursor, etc.)
  ↓ JSON-RPC over stdio
MCPServer (mcp/server.py) — HTTP proxy, no DB
  ↓ httpx async HTTP calls
FastAPI Daemon (server.py :8400) — owns all data
  ↓ direct Python imports
ObservationStore, TraceIndex, CodebaseAtlas, etc. — SQLite
```

**Resolution:** The collaboration infrastructure must follow this same pattern:

1. **CollaborationHub lives in the daemon**, not the MCP server. It's instantiated during daemon startup (`src/codrag/server.py`).

2. **New FastAPI routes** expose collaboration data via REST:
   ```
   GET  /projects/{pid}/collaboration/activity       → ActivityStore.get_recent()
   GET  /projects/{pid}/collaboration/delta?since=    → GraphSnapshotStore.compute_delta()
   GET  /projects/{pid}/collaboration/conflicts       → ConflictStore.get_active()
   POST /projects/{pid}/collaboration/conflicts/{id}/resolve → ConflictStore.resolve()
   GET  /projects/{pid}/collaboration/claims           → ClaimStore.get_active()
   POST /projects/{pid}/collaboration/claims           → ClaimStore.claim()
   DELETE /projects/{pid}/collaboration/claims/{id}    → ClaimStore.release()
   GET  /projects/{pid}/observations?created_by={role} → ObservationStore.get_by_agent()
   ```

3. **`collaboration_handlers.py`** calls these daemon endpoints via `server._api_get()` — same as every other resource handler.

4. **New file needed:** `src/codrag/api/routers/collaboration.py` — FastAPI router for the collaboration endpoints. Registered in the daemon's app.

**Impact if not fixed:** The implementation would fail at runtime. The MCP server process doesn't have a SQLite connection to `codrag_settings.db`. This is the fundamental architecture constraint of the system.

### Issue 7: Resource URI Parsing for Nested Paths

**Severity:** Low

**Problem:** The existing `handle_resources_read` (server.py:2147) parses URIs by splitting `codrag://{project_id}/{resource_type}` with `split("/", 1)`. This means for `codrag://pid/memory/researcher`, `resource_type` would be `"memory/researcher"` — which works fine for routing but the spec doesn't document how the role is extracted.

For `codrag://pid/agents/researcher/findings`, `resource_type` would be `"agents/researcher/findings"` — deeper nesting.

**Files investigated:**
- `src/codrag/mcp/server.py:2143-2151` — URI parsing code

**Resolution:** Document explicitly in the spec that `collaboration_handlers.py` receives the full path after `codrag://{pid}/` and does its own parsing:

```python
def _parse_collab_uri(resource_type: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """Parse collaboration resource URIs.
    
    Returns (resource_name, params) or None if not a collab resource.
    
    Examples:
        "memory/researcher" → ("memory", {"role": "researcher"})
        "agents/custodian/findings" → ("agent_findings", {"role": "custodian"})
        "activity" → ("activity", {})
        "delta" → ("delta", {})
        "conflicts" → ("conflicts", {})
        "structure" → None  (not a collab resource)
    """
```

**Impact if not fixed:** Minor — implementation would figure it out, but documenting it prevents ambiguity.

### Issue 8: Category System Mismatch in Conflict Detection

**Severity:** Medium

**Problem:** The spec defines `CONTRADICTORY_PAIRS` using observation categories (`"pattern"`, `"dead_code"`, etc.). But:

- Observation categories are: `note`, `decision`, `bug`, `pattern`, `assumption` (from `VALID_CATEGORIES` in observation_store.py:47)
- ActionItem categories (used by PushEngine) are a different set: `quality`, `architecture`, `dead_code`, `security`, `tech_debt`, etc.

The spec conflates these two systems. `"dead_code"` is an ActionItem category, not an observation category. An observation about dead code would have `category="note"` with content mentioning dead code.

**Files investigated:**
- `src/codrag/services/observation_store.py:47` — `VALID_CATEGORIES = {"note", "decision", "bug", "pattern", "assumption"}`
- `src/codrag/core/audit/action_item.py` — ActionItem has its own category taxonomy

**Resolution:** Conflict detection needs two separate strategies:

1. **Observation-level conflicts (Layer 1):** Can't use category pairs because observations are mostly `note` or `pattern`. Instead, detect conflicts by looking for two agents with observations about the **same file_path** within a time window. The content determines the conflict, not the category. This is simpler but less precise — it flags potential conflicts for human review.

2. **Push-level conflicts (Layer 2):** Works with `ConsolidatedGroup` objects from the PushEngine. These DO have meaningful categories (`dead_code` vs `quality`). The detector checks if two groups reference the same file with contradictory categories. This is more precise because ActionItem categories carry semantic meaning.

The spec should define both strategies separately and make it clear that observation-level detection is "same file, different agents" (proximity signal) while push-level detection is "same file, contradictory categories" (semantic signal).

**Impact if not fixed:** The `CONTRADICTORY_PAIRS` would reference categories that don't exist in the observation system, causing the detector to never fire.

### Issue 9: Missing `CoDRAGDataAccess.save_observation()` Passthrough

**Severity:** High

**Problem:** The call chain for saving observations goes:

```
AgentCore.save_observation(content, file_path, category, created_by)
  → CoDRAGDataAccess.save_observation(content, file_path, category)  ← MISSING created_by
    → ObservationStore.save(project_id, content, file_path, category)
```

The spec updates `AgentCore` and `ObservationStore` but forgets the intermediate layer `CoDRAGDataAccess` at `agents/shared/codrag_data.py:237-259`.

**Files investigated:**
- `src/codrag/agents/shared/codrag_data.py:237-259` — `save_observation()` method
- `src/codrag/agents/core.py:97-114` — calls `self._data.save_observation()`

**Resolution:** Add `created_by: Optional[str] = None` and `visibility: str = "shared"` to `CoDRAGDataAccess.save_observation()` and pass them through to `self._observation_store.save()`.

**Impact if not fixed:** `created_by` would be silently dropped at the CoDRAGDataAccess layer. All observations saved via AgentCore would have `created_by=NULL` despite the caller passing a value.

---

## 3. What Needs to Happen Next

### 3.1 Fix the Spec (Priority: Do First)

Update `docs/superpowers/specs/2026-04-06-agent-collaboration-infrastructure-design.md` with all 9 fixes. The critical ones that change the architecture:

1. **Issue 6 (critical):** Add a new section "FastAPI Routes" specifying the new `src/codrag/api/routers/collaboration.py` router. Update `collaboration_handlers.py` to use `server._api_get()` instead of direct hub access. Document the daemon-side initialization of `CollaborationHub`.

2. **Issues 1+2 (medium):** Simplify `GraphSnapshot` to only capture hubs + modules (structured data we actually have). Drop cycles and cross-cutting, or replace cross-cutting with `shared_domains: Dict[str, List[str]]` from domain tag data.

3. **Issues 3+4 (high):** Add `collab_hub` param to `PiAgent.__init__`, `init_pi_agent()`, and `PushEngine.__init__` + factory.

4. **Issue 5 (medium):** Standardize all engine access as `self._core.collab.*`.

5. **Issue 8 (medium):** Split conflict detection into observation-level (same file, different agents) and push-level (same file, contradictory ActionItem categories).

6. **Issue 9 (high):** Add `created_by` passthrough to `CoDRAGDataAccess.save_observation()`.

7. **Issue 7 (low):** Document URI parsing strategy.

### 3.2 Updated File Manifest (After Spec Fixes)

**New files to create:**

| File | Purpose |
|---|---|
| `src/codrag/services/collaboration/__init__.py` | CollaborationHub facade |
| `src/codrag/services/collaboration/activity.py` | ActivityStore — append-only agent action log |
| `src/codrag/services/collaboration/snapshots.py` | GraphSnapshotStore — persist + diff graph state (hubs + modules only) |
| `src/codrag/services/collaboration/conflicts.py` | ConflictStore + ConflictDetector (two strategies) |
| `src/codrag/services/collaboration/claims.py` | ClaimStore — soft file claims with auto-expiry |
| `src/codrag/api/routers/collaboration.py` | FastAPI routes for collaboration data (daemon-side) |
| `src/codrag/mcp/collaboration_handlers.py` | MCP resource content generators + prompt handlers (calls daemon via HTTP) |
| `tests/test_activity_store.py` | Unit tests for ActivityStore |
| `tests/test_graph_snapshots.py` | Unit tests for GraphSnapshotStore + delta computation |
| `tests/test_conflict_store.py` | Unit tests for ConflictStore + ConflictDetector |
| `tests/test_claim_store.py` | Unit tests for ClaimStore |
| `tests/test_observation_attribution.py` | Tests for created_by + visibility in ObservationStore |
| `tests/test_collaboration_hub.py` | Integration tests for CollaborationHub |
| `tests/test_collab_resources.py` | Tests for MCP resource content generators |
| `tests/test_collab_prompts.py` | Tests for MCP prompt handlers |
| `tests/test_collab_api.py` | Tests for FastAPI collaboration routes |

**Existing files to modify:**

| File | Changes |
|---|---|
| `src/codrag/services/observation_store.py` | Add `created_by` + `visibility` columns, extend `save()` + `from_row()`, add `get_by_agent()` method, schema migration |
| `src/codrag/agents/shared/codrag_data.py` | Add `created_by` + `visibility` passthrough to `save_observation()` |
| `src/codrag/agents/core.py` | Add `collab_hub` param, add `created_by` to `save_observation()` |
| `src/codrag/services/pi_agent.py` | Add `collab_hub` param, add `scenario` to `_save_observation()`, add activity logging + snapshot capture to scenarios |
| `src/codrag/agents/researcher/engine.py` | Add `created_by="researcher"` to observations, add activity logging, add claim creation |
| `src/codrag/agents/custodian/engine.py` | Add `created_by="custodian"` to observations, add activity logging, add claim checking |
| `src/codrag/adapters/push_engine.py` | Add `conflict_detector` + `conflict_store` params, add conflict detection in `push()`, add `conflicts` field to `PushResult` |
| `src/codrag/adapters/pm_models.py` | Add `conflicts` field to `PushResult` dataclass |
| `src/codrag/mcp/server.py` | 4 thin integration points: init hub proxy, extend resource list, delegate resource read, delegate prompts |
| `src/codrag/mcp_tools.py` | Add `created_by` param to `codrag_save_observation` tool schema |
| `src/codrag/server.py` | Initialize `CollaborationHub` during daemon startup, register collaboration router |

### 3.3 Implementation Order

The work naturally splits into phases based on dependency chains:

**Phase A: Foundation (2-3 days)**

Must be done first — everything else depends on this.

1. Observation store schema migration (`created_by` + `visibility` columns)
2. Observation store `save()` signature update + `get_by_agent()` method
3. `CoDRAGDataAccess.save_observation()` passthrough
4. `AgentCore.save_observation()` passthrough
5. `CollaborationHub` facade (`__init__.py`)
6. `ActivityStore` (new)
7. Unit tests for observation attribution + activity store

**Phase B: Awareness Resources (2-3 days)**

Depends on Phase A.

1. FastAPI collaboration router with observation + activity endpoints
2. `collaboration_handlers.py` — resource generators for `memory/{role}`, `agents/{role}/findings`, `activity`
3. MCP server integration (4 thin touch points)
4. `mcp_tools.py` schema update for `codrag_observe` `created_by` param
5. Wire `created_by` into Pi agent `_save_observation()` (all 7 scenarios)
6. Wire `created_by` into Researcher + Custodian engines
7. Wire activity logging into Pi, Researcher, Custodian
8. Tests for resources + prompts + API routes

**Phase C: Coordination (3-5 days)**

Depends on Phase A. Can partially overlap with Phase B.

1. `GraphSnapshotStore` (hubs + modules only)
2. Delta computation logic
3. `ConflictStore` + `ConflictDetector` (both observation-level and push-level strategies)
4. `ClaimStore`
5. FastAPI routes for delta, conflicts, claims
6. Resource generators for `delta`, `conflicts`
7. Prompt handlers for `codrag-handoff`, `codrag-scope`, `codrag-triage`
8. Wire snapshot capture into Pi Watchdog (post-pipeline)
9. Wire claim creation into Researcher
10. Wire claim checking into Custodian
11. Wire conflict detection into PushEngine
12. Unit + integration tests

**Phase D: Polish (1-2 days)**

After C.

1. Update `CollaborationHub` initialization in daemon startup
2. Pass hub into `init_pi_agent()`
3. Pass hub into `AgentCore` construction (in `api/routers/agents.py`)
4. Pass conflict detector into `PushEngine` construction
5. End-to-end integration test: full workflow from agent observation → conflict detection → MCP resource → prompt
6. Update AGENTS.md generation to document collaboration resources

### 3.4 Deferred Work (Layer 3 Roadmap)

These features build on Layers 1+2 and should be considered after real usage data is available:

| Feature | Prerequisite | Estimated Effort |
|---|---|---|
| Decision history tracking | Layer 1 attribution working | 3-4 days |
| Consensus scoring | Enough observation volume (weeks of usage) | 2-3 days |
| Evidence-based task routing | Decision history data | 3-4 days |
| Capability attestation | Task routing + Phase 73.3b tier stability | 2-3 days |
| Adaptive role scoping | Months of decision history | 5-7 days |
| Cycle detection in trace graph | Trace index SCC algorithm | 2-3 days |
| Structured cross-cutting concerns | Atlas generator refactor | 2-3 days |

### 3.5 Open Questions

1. **Snapshot capture source:** The spec says snapshots are captured after Watchdog runs (post-pipeline). The data comes from the existing daemon APIs (`/trace/hub_files`, `/projects/{pid}/modules`). But Pi Agent uses direct Python imports, not HTTP calls. Do we have Pi call the Python internals directly (faster, tighter coupling) or go through the HTTP API (consistent, slower)? Pi already imports `run_audit()` directly — direct Python is the existing pattern.

2. **Activity feed retention:** The spec says 30-day prune. Is this enough? Too much? For a project with 5 active agents running daily, that's ~150 entries/day × 30 = 4,500 entries. At ~200 bytes each, that's <1MB. Probably fine.

3. **Conflict auto-resolution:** The spec defaults all conflicts to `"deferred"`. Should there be any auto-resolution rules? E.g., "if the file has >5 dependents, researcher wins over custodian" (can't delete a highly-connected file). This is probably Layer 3 territory.

4. **Resource template registration:** MCP spec supports `resources/templates/list` for parameterized resources like `codrag://{pid}/memory/{role}`. Should we register templates so clients can auto-complete role names? This would let users type `@codrag://memory/` and see available roles. Nice-to-have, not blocking.

---

## 4. Documents Produced This Session

| Document | Location | Purpose |
|---|---|---|
| Design doc (README.md) | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/README.md` | Full architectural design — three layers, MCP primitives, SQL schemas, implementation plan |
| Paperclip concept | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/paperclip_concept.md` | Non-technical overview for Paperclip users |
| Implementation spec | `docs/superpowers/specs/2026-04-06-agent-collaboration-infrastructure-design.md` | Detailed build spec — data models, API signatures, testing strategy. **Needs 9 fixes before implementation.** |
| This document | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/next_steps.md` | Session summary, 9 issues documented, implementation order, open questions |

---

## 5. Key Decisions Made

| Decision | Rationale |
|---|---|
| Build Layers 1+2 only, roadmap Layer 3 | Layer 3 needs real usage data; premature optimization risk |
| Approach B: collaboration module package | Keep server.py from growing; clean separation of concerns |
| No new MCP tools | Tools are for autonomous agent decisions; collaboration is resources (shared state) + prompts (workflows) |
| 3 new prompts, not overlapping with doc 14 | Doc 14's 5 prompts are human developer workflows; our 3 are agent collaboration workflows (handoff, scope, triage) |
| Drop cycles + cross-cutting from snapshots | No structured data source exists; hubs + modules are available and sufficient |
| MCP server delegates via HTTP, not direct DB | MCPServer is an HTTP proxy; all data access goes through daemon FastAPI routes |
| Engines access hub via `self._core.collab` | Single path through AgentCore; no separate hub injection into engines |
| Conflict detection: two strategies | Observation-level (proximity signal) + push-level (semantic signal) — different data, different approaches |

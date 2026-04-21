# Agent Collaboration Infrastructure — Session Summary & Completion Record

> Date: 2026-04-06 | Recording everything accomplished
> Status: **COMPLETE** — 19 commits, 76 tests, all P1+P2 items implemented

---

## 1. What We Accomplished This Session

### 1.1 Concept Development

We started from the MCP Ecosystem Optimization Design (doc 12) and asked: "Are the planned MCP prompts and resources enough for our agents, or should we think of something new?" This led to the discovery that Prep's agents operate in complete isolation — they share a data store but have zero awareness of each other's work. We identified a new product concept: **Agent Collaboration Infrastructure** — turning Prep from a code intelligence library into the coordination substrate for multi-agent development teams.

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
- Full Layer 1 design: `Observation.created_by` + `visibility` fields, per-role memory resources (`prep://{pid}/memory/{role}`), cross-agent findings resources (`prep://{pid}/agents/{role}/findings`), activity feed resource (`prep://{pid}/activity`)
- Full Layer 2 design: structural delta resource (`prep://{pid}/delta`), conflict detection (`AgentConflict` model + `ConflictDetector`), soft claims (`SoftClaim` model + `ClaimStore`), dependency declarations on plans, shared computation cache
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
- Architecture diagram showing Prep intelligence + Paperclip orchestration
- 5 concrete integration points (task assignment, agent startup, handoff, conflict resolution, consensus prioritization)
- What makes observation-mediated collaboration different from message-passing
- Getting started section with zero-config adoption path

### 1.5 Implementation Spec

**File:** `docs/superpowers/specs/2026-04-06-agent-collaboration-infrastructure-design.md`

Detailed implementation specification covering:

- Explicit scope: what's built (Layers 1+2), what's not (Layer 3), what's untouched (existing prompts from doc 14, existing resources, existing tools)
- Package structure: `src/prep/services/collaboration/` with 5 modules + `src/prep/mcp/collaboration_handlers.py`
- `CollaborationHub` facade design
- Full data models with Python dataclasses and SQL DDL for every table
- Complete API signatures for every store (ActivityStore, GraphSnapshotStore, ConflictStore + ConflictDetector, ClaimStore)
- All 5 MCP resource content formats with example markdown output
- All 3 MCP prompt templates with argument specs
- Agent engine integration details for Pi, Researcher, Custodian, AgentCore, PushEngine
- MCP tool schema change for `prep_observe`
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
- Searched for `import_cycles`, `find_cycles`, `detect_cycles` across all of `src/prep/` — zero matches
- `src/prep/core/atlas/generator.py:418-434` — cross-cutting section is free-text, not structured
- `src/prep/core/trace/` — no cycle detection methods found

**Resolution options:**
- **A (recommended): Drop cycles from snapshot for now.** Snapshot captures hubs + modules only. Cycle detection becomes a Layer 3 or separate enhancement. This is honest — we don't have the data source.
- **B: Build cycle detection first.** Add a method to the trace index that walks the import graph and returns strongly connected components. This is real work (probably 2-3 days) and should be a separate task.

**Impact if not fixed:** Snapshot capture would crash or return empty cycles, making the delta resource partially useless.

### Issue 2: No Structured Cross-Cutting Data Available

**Severity:** Medium

**Problem:** Same issue as #1. The spec defines `cross_cutting: Dict[str, int]` (concern name → file count), but `cross_cutting` in the atlas generator (line 434) is a free-text string assembled from hub files and shared domain tags. There's no `{concern: file_count}` map.

**Files investigated:**
- `src/prep/core/atlas/generator.py:418-434` — `cross_parts` is a list of strings like `"Hub files: config.py (168 edges)"` and `"Shared domains: ui, dashboard, typescript"`, concatenated into prose
- No structured cross-cutting data model exists

**Resolution options:**
- **A (recommended): Replace with structured hub data + shared domain tags.** We DO have structured data for hub files (via `/trace/hub_files`) and domain tags per module (via cluster data). Rename `cross_cutting` to something like `shared_domains` and capture `{domain_tag: [module_names]}` instead.
- **B: Drop from snapshot.** Simplest, but loses a useful dimension.

**Impact if not fixed:** Snapshot would either crash or contain meaningless data for cross-cutting delta.

### Issue 3: Pi Agent Has No CollaborationHub Reference

**Severity:** High

**Problem:** The spec shows Pi calling `self._collab_hub.activity.log(...)` and `self._collab_hub.snapshots.capture(...)`. But `PiAgent.__init__` accepts only `(project_id, index_dir, project_root)`. There's no way to get the hub into Pi.

**Files investigated:**
- `src/prep/services/pi_agent.py:60-68` — init signature
- `src/prep/services/pi_agent.py:1157-1170` — `init_pi_agent()` factory function
- `src/prep/services/pipeline/orchestrator.py:1241-1247` — where Pi is triggered

**Resolution:** Add `collab_hub: Optional[CollaborationHub] = None` to both `PiAgent.__init__` and `init_pi_agent()`. The daemon's startup code creates the hub first, then passes it when initializing Pi. All hub access in Pi is guarded with `if self._collab_hub:` for backward compatibility.

**Init chain:** `server.py startup` → `init_pi_agent(project_id, index_dir, project_root, collab_hub=hub)` → `PiAgent(project_id, index_dir, project_root, collab_hub=hub)`.

**Impact if not fixed:** All activity logging and snapshot capture in Pi would be dead code.

### Issue 4: PushEngine Has No ConflictDetector Reference

**Severity:** High

**Problem:** The spec says `if self._conflict_detector:` in `PushEngine.push()`, but PushEngine is initialized with `(adapter, consolidator)` only. The factory function `create_push_engine(config)` at `push_engine.py:295` creates `PushEngine(adapter, Consolidator())` — no conflict detector.

**Files investigated:**
- `src/prep/adapters/push_engine.py:44-50` — init signature
- `src/prep/adapters/push_engine.py:280-295` — factory function

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
- `src/prep/mcp/server.py:100-122` — MCPServer.__init__: stores `daemon_url`, creates `httpx.AsyncClient`, zero SQLite imports
- `src/prep/mcp/server.py:2092-2184` — handle_resources_read: calls `self._api_get()` for data
- `src/prep/mcp/server.py:2189-2320` — resource content generators: all use `self._api_get()` to fetch data from daemon

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

1. **CollaborationHub lives in the daemon**, not the MCP server. It's instantiated during daemon startup (`src/prep/server.py`).

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

4. **New file needed:** `src/prep/api/routers/collaboration.py` — FastAPI router for the collaboration endpoints. Registered in the daemon's app.

**Impact if not fixed:** The implementation would fail at runtime. The MCP server process doesn't have a SQLite connection to `prep_settings.db`. This is the fundamental architecture constraint of the system.

### Issue 7: Resource URI Parsing for Nested Paths

**Severity:** Low

**Problem:** The existing `handle_resources_read` (server.py:2147) parses URIs by splitting `prep://{project_id}/{resource_type}` with `split("/", 1)`. This means for `prep://pid/memory/researcher`, `resource_type` would be `"memory/researcher"` — which works fine for routing but the spec doesn't document how the role is extracted.

For `prep://pid/agents/researcher/findings`, `resource_type` would be `"agents/researcher/findings"` — deeper nesting.

**Files investigated:**
- `src/prep/mcp/server.py:2143-2151` — URI parsing code

**Resolution:** Document explicitly in the spec that `collaboration_handlers.py` receives the full path after `prep://{pid}/` and does its own parsing:

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
- `src/prep/services/observation_store.py:47` — `VALID_CATEGORIES = {"note", "decision", "bug", "pattern", "assumption"}`
- `src/prep/core/audit/action_item.py` — ActionItem has its own category taxonomy

**Resolution:** Conflict detection needs two separate strategies:

1. **Observation-level conflicts (Layer 1):** Can't use category pairs because observations are mostly `note` or `pattern`. Instead, detect conflicts by looking for two agents with observations about the **same file_path** within a time window. The content determines the conflict, not the category. This is simpler but less precise — it flags potential conflicts for human review.

2. **Push-level conflicts (Layer 2):** Works with `ConsolidatedGroup` objects from the PushEngine. These DO have meaningful categories (`dead_code` vs `quality`). The detector checks if two groups reference the same file with contradictory categories. This is more precise because ActionItem categories carry semantic meaning.

The spec should define both strategies separately and make it clear that observation-level detection is "same file, different agents" (proximity signal) while push-level detection is "same file, contradictory categories" (semantic signal).

**Impact if not fixed:** The `CONTRADICTORY_PAIRS` would reference categories that don't exist in the observation system, causing the detector to never fire.

### Issue 9: Missing `PrepDataAccess.save_observation()` Passthrough

**Severity:** High

**Problem:** The call chain for saving observations goes:

```
AgentCore.save_observation(content, file_path, category, created_by)
  → PrepDataAccess.save_observation(content, file_path, category)  ← MISSING created_by
    → ObservationStore.save(project_id, content, file_path, category)
```

The spec updates `AgentCore` and `ObservationStore` but forgets the intermediate layer `PrepDataAccess` at `agents/shared/prep_data.py:237-259`.

**Files investigated:**
- `src/prep/agents/shared/prep_data.py:237-259` — `save_observation()` method
- `src/prep/agents/core.py:97-114` — calls `self._data.save_observation()`

**Resolution:** Add `created_by: Optional[str] = None` and `visibility: str = "shared"` to `PrepDataAccess.save_observation()` and pass them through to `self._observation_store.save()`.

**Impact if not fixed:** `created_by` would be silently dropped at the PrepDataAccess layer. All observations saved via AgentCore would have `created_by=NULL` despite the caller passing a value.

---

## 3. Implementation Status

> All 9 issues from the scrutiny pass were resolved during implementation. All P1 and P2 items from the strategic direction were implemented in the Paperclip-first revision.

### 3.1 Issues Resolved

All 9 issues identified in section 2 were fixed during implementation:

1. **Issue 6 (critical):** Resolved — `src/prep/api/routers/collaboration.py` created with 7 FastAPI routes. MCP `collaboration_handlers.py` fetches data via `server._api_get()`. CollaborationHub initialized daemon-side in `watch.py`.

2. **Issues 1+2 (medium):** Resolved — `GraphSnapshot` captures hubs + modules only. Cycles and cross-cutting dropped (no structured data source exists).

3. **Issues 3+4 (high):** Resolved — `collab_hub` param added to `PiAgent.__init__`, `init_pi_agent()`, and `PushEngine.__init__`. Factory passes through.

4. **Issue 5 (medium):** Resolved — All engine access standardized as `self._core.collab.*`.

5. **Issue 8 (medium):** Resolved — Observation-level conflict detection only (same file, different agents). Push-level detection deferred to Layer 3.

6. **Issue 9 (high):** Resolved — `created_by` + `visibility` passthrough added to `PrepDataAccess.save_observation()`.

7. **Issue 7 (low):** Resolved — `parse_collaboration_uri()` documents the URI parsing strategy with clear routing.

### 3.2 File Manifest (All Created/Modified)

All files below were created or modified during implementation. See `feature_documentation.md` for the complete file listing with line counts and change descriptions.

### 3.3 Implementation Phases (All Complete)

All four implementation phases were completed:

**Phase A: Foundation** — DONE
- Observation store schema migration, `get_by_agent()`, `get_all_attributed()`
- `PrepDataAccess` and `AgentCore` passthrough
- `CollaborationHub` facade + singleton
- `ActivityStore`

**Phase B: Awareness Resources** — DONE
- FastAPI collaboration router (7 endpoints)
- `collaboration_handlers.py` (3 MCP resources, 3 prompts)
- MCP server integration (4 touch points)
- Pi agent attribution (all 9 `_save_observation` calls + all 7 scenarios)
- Researcher + Custodian attribution

**Phase C: Coordination** — DONE
- `GraphSnapshotStore` + delta computation
- `ConflictStore` + `ConflictDetector`
- `ClaimStore`
- Researcher claims, Custodian claim-checking
- PushEngine conflict detection + conflict push to Paperclip

**Phase D: Polish + Paperclip-First Revision** — DONE
- CollaborationHub initialization in daemon startup
- Hub injection into Pi, AgentCore, PushEngine
- MCP resource cleanup (5→3, removed activity/conflicts)
- Prompt revision (triage→enrich, updated handoff/scope)
- Paperclip plugin: `created_by` attribution, 2 data providers
- 76 tests passing

### 3.4 Deferred Work

**P3 items (deferred for user feedback):**

| Feature | Status | Notes |
|---|---|---|
| Claims push as Paperclip agent metadata | Deferred | Requires Paperclip agent metadata API |
| Delta push as Paperclip issues | Deferred | Requires Pi → PushEngine integration |

**Layer 3 Roadmap (Emergence):**

| Feature | Prerequisite | Estimated Effort |
|---|---|---|
| Decision history tracking | Layer 1 attribution working | 3-4 days |
| Consensus scoring | Enough observation volume (weeks of usage) | 2-3 days |
| Evidence-based task routing | Decision history data | 3-4 days |
| Capability attestation | Task routing + Phase 73.3b tier stability | 2-3 days |
| Adaptive role scoping | Months of decision history | 5-7 days |
| Cycle detection in trace graph | Trace index SCC algorithm | 2-3 days |
| Structured cross-cutting concerns | Atlas generator refactor | 2-3 days |

### 3.5 Resolved Questions

1. **Snapshot capture source:** Resolved — Pi calls Python internals directly (TraceIndex.hub_files, module clusters). Matches existing pattern (Pi already imports `run_audit()` directly).

2. **Activity feed retention:** Resolved — 30-day prune at 1000 entries. Reasonable for expected volumes.

3. **Conflict auto-resolution:** Deferred to Layer 3. All conflicts default to `"deferred"` resolution.

4. **Resource template registration:** Not implemented. Nice-to-have for future.

---

## 4. Documents Produced

| Document | Location | Purpose | Status |
|---|---|---|---|
| Design doc (README.md) | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/README.md` | Full architectural design — three layers, MCP primitives, SQL schemas | Original design — see strategic_direction.md for Paperclip-first revisions |
| Paperclip concept | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/paperclip_concept.md` | Non-technical overview for Paperclip users | Updated to reflect Paperclip-first direction |
| Implementation spec | `docs/superpowers/specs/2026-04-06-agent-collaboration-infrastructure-design.md` | Detailed build spec — data models, API signatures, testing strategy | All 9 issues resolved during implementation |
| Feature documentation | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/feature_documentation.md` | Comprehensive record of what was built | Updated with Paperclip-first revisions |
| Strategic direction | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/strategic_direction.md` | Paperclip-first reframing, P1/P2/P3 items | P1+P2 items implemented |
| This document | `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/next_steps.md` | Session summary, issues documented, completion record | Updated to reflect completion |

---

## 5. Key Decisions Made

| Decision | Rationale |
|---|---|
| Build Layers 1+2 only, roadmap Layer 3 | Layer 3 needs real usage data; premature optimization risk |
| Approach B: collaboration module package | Keep server.py from growing; clean separation of concerns |
| No new MCP tools | Tools are for autonomous agent decisions; collaboration is resources (shared state) + prompts (workflows) |
| 3 new prompts, not overlapping with doc 14 | Doc 14's 5 prompts are human developer workflows; our 3 are agent collaboration workflows (handoff, scope, enrich) |
| Drop cycles + cross-cutting from snapshots | No structured data source exists; hubs + modules are available and sufficient |
| MCP server delegates via HTTP, not direct DB | MCPServer is an HTTP proxy; all data access goes through daemon FastAPI routes |
| Engines access hub via `self._core.collab` | Single path through AgentCore; no separate hub injection into engines |
| Paperclip-first direction | Prep provides structural intelligence to enrich Paperclip, not a parallel PM system |
| Remove activity + conflicts MCP resources | Paperclip has richer versions; conflicts push to Paperclip as tagged issues instead |
| Replace triage with enrich | Prep provides structural enrichment; Paperclip does the actual triage |
| Observation-level conflict detection only | Same file, different agents = proximity signal; push-level (semantic) deferred to Layer 3 |

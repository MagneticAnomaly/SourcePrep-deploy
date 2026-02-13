# Phase 24 — State Machine Architecture

**Scope:** System-wide identification of state machine opportunities across backend, frontend, and inter-process boundaries.

**Status:** Research & Planning

---

## 1. Thesis

CoDRAG has grown organically across 23 phases. Many subsystems now manage complex lifecycle states through ad-hoc patterns: bare booleans, thread-alive checks, string-typed `_state` fields, and independent `useState` variables that must be manually synchronized. This produces:

- **Impossible states** that nothing prevents (e.g., `building: true` + `exists: false` persisting forever)
- **Scattered transitions** where one user action must update 3–5 variables in the right order across multiple callbacks
- **Duplicated guard logic** — the same "is this stage allowed to run?" check repeated at API layer, UI layer, and CLI
- **Silent failures** — thread dies but no state transition fires, leaving the system in a zombie state

A state machine framework provides **explicit phases**, **guarded transitions**, and **impossible-state elimination** — making the system auditable, testable, and self-documenting.

This document identifies **8 state machine opportunities** across the full stack, grouped into 3 tiers of priority.

---

## 2. Identified State Machines

### Overview Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  SM-1  Dashboard App.tsx (54 useState → domain reducers)        │
│  SM-2  GraphEnrichmentPipeline (8-stage UI state)               │
│  SM-3  VS Code Extension DaemonManager                          │
├─────────────────────────────────────────────────────────────────┤
│                         BACKEND                                 │
│  SM-4  Build Orchestrator (3 parallel build types per project)  │
│  SM-5  AutoRebuildWatcher (file watcher lifecycle)              │
│  SM-6  Graph Enrichment Pipeline (8-stage backend orchestrator) │
│  SM-7  License & Feature Gate (tier transitions + enforcement)  │
├─────────────────────────────────────────────────────────────────┤
│                      INTER-PROCESS                              │
│  SM-8  Daemon Lifecycle (Tauri ↔ sidecar ↔ health polling)     │
└─────────────────────────────────────────────────────────────────┘
```

---

### SM-1: Dashboard App.tsx (Frontend — Highest Priority)

**Location:** `src/codrag/dashboard/src/App.tsx` (~2,430 lines)
**Current pattern:** 54 `useState`, 53 `useCallback`, 12 `useEffect` — all independent, manually synchronized.

**Problem:** Stale-state bugs, impossible states, prop-drilling hell. A single "Build Trace Graph" action must update `traceStatus.building`, `traceCoverage`, and multiple enrichment stage booleans in the right order across multiple callbacks. SSE completion events can arrive while state is mid-transition.

**Proposed approach:** `useReducer` per domain (zero new dependencies).

**Domains (4 reducers):**

| Reducer | State vars consumed | Callbacks consumed | Est. LOC freed |
|---------|--------------------|--------------------|----------------|
| `tracePipelineReducer` | 4 (traceStatus, traceCoverage, indexAutoRebuild, enrichmentAutoConfig) | ~10 (build, destroy, coverage, patterns, auto-config) | ~200 |
| `enrichmentReducer` | 12 (augmentation/epistemic/cluster/deepening/knowledge × status+running) | ~8 (run/cancel per stage) | ~250 |
| `searchContextReducer` | 11 (query, k, results, context, meta) | ~5 (search, get context) | ~100 |
| `projectReducer` | 6 (projects, selected, statuses, building, config, dirty) | ~6 (CRUD, build, config save) | ~150 |

**Key invariants to enforce:**
- `TracePipelineState.phase === 'building'` → `BUILD_STARTED` is a no-op (prevents double-fire)
- `BUILD_COMPLETED` always atomically sets `exists: true` + `phase: 'ready'` (fixes the stale-state bug)
- `DESTROYED` resets entire trace + enrichment state in one action
- Each enrichment stage: `idle → running → completed | failed` — no other transitions

**File structure:**
```
src/codrag/dashboard/src/
├── state/
│   ├── tracePipelineReducer.ts
│   ├── enrichmentReducer.ts
│   ├── searchReducer.ts
│   ├── projectReducer.ts
│   └── index.ts
├── hooks/
│   ├── useTracePipeline.ts      ← reducer + API calls + SSE watcher
│   ├── useEnrichment.ts
│   ├── useSearchContext.ts
│   └── useProjectManager.ts
└── App.tsx                       ← ~500 lines: compose hooks, render shell
```

**Post-refactor App.tsx shape:**
```typescript
function App() {
  const api = useApiClient()
  const { connected, unhealthy } = useConnection(api)
  const { projects, selected, actions: projectActions } = useProjectManager(api)
  const { trace, actions: traceActions } = useTracePipeline(api, selected.id)
  const { enrichment, actions: enrichActions } = useEnrichment(api, selected.id)
  const { search, actions: searchActions } = useSearchContext(api, selected.id)
  const license = useLicenseSystem()
  const llm = useLLMConfig()
  // UI chrome stays as plain useState (too simple for a reducer)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // ...panel content map, render
}
```

---

### SM-2: Graph Enrichment Pipeline (Frontend — High Priority)

**Location:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (649 lines)
**Current pattern:** 8 independent `compute*State()` functions, each re-derived on every render from raw props. The component receives ~20 props representing individual boolean/status fields and reconstructs a `StageState` enum (`'disabled' | 'waiting' | 'running' | 'complete' | 'stale' | 'error' | 'idle' | 'not_built' | 'warning'`) per stage.

**Problem:**
- Stage dependencies are implicit in the `compute*` functions — e.g., `computeEpistemicState` checks `trace.enabled && trace.exists && aug.enabled && aug.augmented_nodes > 0` but this prerequisite chain isn't declared anywhere.
- The component can't answer "what should run next?" without re-computing all 8 stages.
- Auto-pilot sequencing (run stages 1→8 automatically) doesn't exist — would need to be a manual chain of callbacks.

**Proposed approach:** A `PipelineState` object with an explicit dependency DAG:

```typescript
type StagePhase = 'blocked' | 'ready' | 'running' | 'done' | 'stale' | 'error';

interface PipelineStage {
  id: EnrichmentStageId;
  phase: StagePhase;
  requires: EnrichmentStageId[];  // declared prerequisites
  stats: Record<string, number>;
}

interface PipelineState {
  stages: Record<EnrichmentStageId, PipelineStage>;
  globalPhase: 'idle' | 'running' | 'complete';
}
```

**Benefits:**
- **"What can run?"** = all stages where `phase === 'ready'` (prerequisites are `'done'`)
- **Auto-pilot** = simple loop: pick first `'ready'` stage → run → on completion, re-evaluate
- **Visualization** = the pipeline component just maps `stages` → rows, no re-computation
- **Tier gating** = a stage's `requires` can include a virtual `'pro_license'` prerequisite

**Dependency DAG (8 stages, 2 groups):**

```
Fast Sync:
  structural ──→ catalogue ──→ validation ──→ knowledge_embedding

Deep Enrichment:
  catalogue ──→ enrichment ──→ clustering ──→ deepening ──→ deep_knowledge_embedding
```

---

### SM-3: VS Code Extension DaemonManager (Frontend — Medium Priority)

**Location:** `packages/vscode/src/daemon.ts` (204 lines)
**Current pattern:** `DaemonState = 'connected' | 'disconnected' | 'starting'` with manual `setState()` calls.

**Problem:** Currently simple enough, but missing states for real-world scenarios:
- Daemon was connected → crashes → extension should show "reconnecting" not just "disconnected"
- `startDaemon()` spawns a child process but has no timeout/failure state
- No `'stopping'` state for graceful shutdown
- License/tier state is fetched inside `poll()` but not part of the state machine — a failed license fetch silently falls back to `'free'`

**Proposed states:**
```
disconnected → starting → connected → unhealthy → reconnecting → connected
                    ↓                       ↓
                 failed                  disconnected
```

**Additional transitions:**
- `connected` + license fetch failure → `connected_degraded` (show warning, don't block)
- `connected` → `stopping` → `disconnected` (graceful shutdown)

**Benefit:** Enables richer status bar states, better error messages in WebViews, and correct behavior when the daemon crashes mid-operation.

---

### SM-4: Build Orchestrator (Backend — High Priority)

**Location:** `src/codrag/server.py` lines 196–214, 1096–1170 (global dicts + thread management)
**Current pattern:** 3 parallel build systems (code index, trace, knowledge), each managed by:
- A global `threading.Lock` (`_project_build_lock`, `_project_trace_build_lock`, `_project_knowledge_build_lock`)
- A global `Dict[str, threading.Thread]` (`_project_build_threads`, etc.)
- A global `Dict[str, str]` for last error
- Free functions: `_is_project_building()`, `_start_project_build()`, `_project_build_worker()`

**Problem:**
- **10+ module-level globals** managing thread state — fragile and untestable
- `_is_project_building()` just checks `thread.is_alive()` — no distinction between "thread crashed" vs "thread completed" vs "thread was never started"
- No unified "what is the project doing right now?" query — the `/engine/status` endpoint manually aggregates 7 separate status calls
- The watcher's `trigger_build` closure captures stale references; race conditions between simultaneous index + trace builds are possible

**Proposed approach:** A `BuildOrchestrator` class (singleton) with per-project state machines:

```python
class BuildPhase(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"       # waiting for lock
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BuildSlot:
    phase: BuildPhase
    thread: Optional[Thread]
    started_at: Optional[str]
    error: Optional[str]
    result: Optional[dict]

class BuildOrchestrator:
    """Per-project, per-type build state management."""
    # project_id → { 'index': BuildSlot, 'trace': BuildSlot, 'knowledge': BuildSlot }
    _slots: Dict[str, Dict[str, BuildSlot]]
    _lock: threading.Lock

    def status(self, project_id: str) -> Dict[str, BuildSlot]: ...
    def start(self, project_id: str, build_type: str, worker: Callable) -> bool: ...
    def is_any_running(self, project_id: str) -> bool: ...
    def cleanup(self, project_id: str) -> None: ...
```

**Benefits:**
- `/engine/status` becomes a single `orchestrator.status(project_id)` call
- Thread lifecycle transitions are explicit (IDLE → QUEUED → RUNNING → COMPLETED/FAILED)
- Crash detection: if `thread.is_alive() == False` but `phase == RUNNING`, auto-transition to `FAILED`
- Testable in isolation without spinning up FastAPI

---

### SM-5: AutoRebuildWatcher (Backend — Medium Priority)

**Location:** `src/codrag/core/watcher.py` (352 lines)
**Current pattern:** `_state: str` field manually set to `"disabled"`, `"idle"`, `"debouncing"`, `"building"`, `"throttled"` across 6 different code paths with `self._lock` guards.

**Current state diagram (implicit):**
```
disabled → idle → debouncing → building → idle
                      ↓              ↗
                  throttled ─────────
```

**Problem:**
- State transitions are scattered across `start()`, `stop()`, `_queue_path()`, `_on_debounce_fire()`, and `_wait_for_build_complete()` — no single place to see all valid transitions.
- `status()` method overrides `_state` at read time: `if enabled and self._is_building(): state = "building"` — the stored state and the reported state diverge.
- The `_stale_since` field is a separate boolean channel that partially duplicates state info.

**Proposed approach:** A `WatcherPhase` enum with a transition table:

```python
class WatcherPhase(str, Enum):
    DISABLED = "disabled"
    IDLE = "idle"              # watching, no changes detected
    STALE = "stale"            # changes detected, debounce timer hasn't fired
    DEBOUNCING = "debouncing"  # debounce timer running
    THROTTLED = "throttled"    # min-gap timer running
    BUILDING = "building"      # build in progress
    ERROR = "error"            # observer crashed

VALID_TRANSITIONS = {
    WatcherPhase.DISABLED:   {WatcherPhase.IDLE},
    WatcherPhase.IDLE:       {WatcherPhase.STALE, WatcherPhase.DISABLED},
    WatcherPhase.STALE:      {WatcherPhase.DEBOUNCING, WatcherPhase.DISABLED},
    WatcherPhase.DEBOUNCING: {WatcherPhase.BUILDING, WatcherPhase.THROTTLED, WatcherPhase.DISABLED},
    WatcherPhase.THROTTLED:  {WatcherPhase.BUILDING, WatcherPhase.DEBOUNCING, WatcherPhase.DISABLED},
    WatcherPhase.BUILDING:   {WatcherPhase.IDLE, WatcherPhase.STALE, WatcherPhase.ERROR, WatcherPhase.DISABLED},
    WatcherPhase.ERROR:      {WatcherPhase.IDLE, WatcherPhase.DISABLED},
}
```

**Benefits:**
- `_transition(new_phase)` method validates transitions → catches bugs at dev time
- `status()` returns the stored phase directly (no read-time override hack)
- `_stale_since` is derivable from transition timestamps, not a separate field

---

### SM-6: Graph Enrichment Pipeline — Backend Orchestrator (Backend — High Priority)

**Location:** `src/codrag/server.py` lines 3256–3564 (3 global state dicts + per-stage run endpoints)
**Current pattern:** Three `Dict[str, Dict[str, Any]]` globals (`_epistemic_state`, `_cluster_state`, `_deepening_state`) each holding a `{"thread": Thread, "current": int, "total": int}` dict. Each stage has its own `/run` and `/status` endpoints that independently check `thread.is_alive()`.

**Problem:**
- **No dependency enforcement** — the API lets you POST `/epistemic/run` even if augmentation hasn't been done. The only guard is the LLM client check, not pipeline prerequisites.
- **No auto-pilot** — running all 8 stages sequentially requires 8 manual API calls or the frontend chaining them together via SSE events.
- **No cancellation** — once a thread starts, there's no cooperative cancellation mechanism.
- **No unified progress** — the `/engine/status` endpoint manually aggregates 7 separate calls, each re-reading JSONL files from disk.

**Proposed approach:** A `PipelineOrchestrator` that owns the stage dependency graph:

```python
class StagePhase(str, Enum):
    BLOCKED = "blocked"     # prerequisites not met
    READY = "ready"         # can run
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    STALE = "stale"         # done but input changed

STAGE_DEPS = {
    "structural":       [],
    "catalogue":        ["structural"],
    "validation":       ["catalogue"],
    "knowledge":        ["catalogue"],
    "enrichment":       ["catalogue"],
    "clustering":       ["enrichment"],
    "deepening":        ["enrichment"],
    "deep_knowledge":   ["enrichment", "clustering"],
}

class PipelineOrchestrator:
    """Per-project pipeline with dependency-driven stage scheduling."""

    def stage_phase(self, stage_id: str) -> StagePhase: ...
    def run_stage(self, stage_id: str) -> bool: ...
    def run_auto(self, group: str) -> None:
        """Auto-pilot: run all ready stages in topological order."""
    def cancel_stage(self, stage_id: str) -> bool: ...
    def status(self) -> Dict[str, StagePhase]: ...
```

**Benefits:**
- **Single-endpoint auto-pilot**: `POST /projects/{id}/pipeline/run-auto?group=fast` runs stages 1→4 in sequence
- **Dependency enforcement**: `run_stage("enrichment")` rejects if `catalogue` is not `DONE`
- **Staleness propagation**: when `structural` is rebuilt, all downstream stages transition to `STALE`
- **Unified status**: one call returns all 8 stages instead of 7 separate queries

**Tier gating integration:** The orchestrator checks `require_feature()` before transitioning certain stages:
- `auto_rebuild` gate → blocks auto-pilot for FREE tier
- `clara_compression` gate → blocks compression stage for non-PRO
- `mcp_trace_expand` gate → blocks trace-aware context expansion

---

### SM-7: License & Feature Gate (Backend — Medium Priority)

**Location:** `src/codrag/core/feature_gate.py` (184 lines)
**Current pattern:** Stateless `check_feature()` / `require_feature()` functions that read a cached `License` dataclass. License is loaded once from `~/.codrag/license.json` or `CODRAG_TIER` env var.

**Problem:**
- **No lifecycle** — the license is loaded once and cached forever. If the user activates a license, `clear_license_cache()` must be called manually, and any in-flight requests still see the old tier.
- **No expiration handling** — `expires_at` is stored but never checked. A license that expired yesterday still grants PRO.
- **No activation state machine** — the activation flow (enter key → validate with Lemon Squeezy → exchange for signed token → write to disk → reload) is spread across the `POST /license/activate` endpoint with no intermediate states.
- **No degradation** — if the license file is corrupted, it falls back to FREE silently with only a log warning.

**Proposed states for license lifecycle:**

```
UNCHECKED → LOADING → VALID → EXPIRED → GRACE_PERIOD → DEGRADED(free)
                  ↓                                          ↑
               INVALID ──────────────────────────────────────┘
```

**Proposed states for activation flow:**

```
IDLE → VALIDATING_KEY → EXCHANGING_TOKEN → WRITING_FILE → ACTIVATED
           ↓                  ↓                 ↓
        KEY_INVALID     EXCHANGE_FAILED    WRITE_FAILED
```

**Benefits:**
- Expiration checking on every `get_license()` call with configurable grace period
- Activation UI can show granular progress ("Validating key…", "Exchanging token…")
- Feature gate decisions become `license_sm.phase in (VALID, GRACE_PERIOD)`
- Corrupted file → explicit `DEGRADED` state with user-visible warning instead of silent fallback

---

### SM-8: Daemon Lifecycle (Inter-Process — Lower Priority)

**Location:** `src/codrag/dashboard/src-tauri/src/main.rs` (116 lines), `src/codrag/dashboard/src/components/StartupScreen.tsx`
**Current pattern:** Tauri setup hook checks port → checks health → conditionally spawns sidecar → `thread::sleep(1s)`. Frontend `StartupScreen` polls `/health` every 1s with 30s timeout.

**Problem:**
- The 1-second sleep is a race condition — slow machines may not have the daemon ready
- No state communicated from Rust → frontend about what's happening ("checking port", "spawning", "waiting for health")
- If the daemon crashes after startup, the frontend's `isDaemonUnhealthy` state is set by a separate polling `useEffect` — disconnected from the startup flow
- No graceful restart — if health fails, the only option is "Retry" (re-poll) or "Quit"

**Proposed states (Tauri side):**

```
CHECKING_PORT → ATTACHING (port open + healthy)
      ↓
SPAWNING → WAITING_FOR_HEALTH → CONNECTED
      ↓              ↓
  SPAWN_FAILED   HEALTH_TIMEOUT → RETRY
```

**Proposed states (Frontend side):**

```
CONNECTING → CONNECTED → HEALTHY
                ↓
            UNHEALTHY → RECONNECTING → CONNECTED
                ↓
            DISCONNECTED → CONNECTING
```

**Benefits:**
- Startup screen shows specific phase ("Spawning daemon…", "Waiting for health check…")
- Crash recovery: `HEALTHY → UNHEALTHY` triggers automatic reconnection attempts before showing error
- Tauri can communicate `SPAWN_FAILED` reason to frontend (port conflict, binary not found, etc.)

---

## 3. Tier Gating × State Machine Integration

The licensing tier system interacts with multiple state machines. Here's how feature gates map to state machine transitions:

| Feature Gate | Tier | State Machine Affected | Effect |
|---|---|---|---|
| `projects_max` | FREE:1, STARTER:3, PRO:∞ | SM-4 BuildOrchestrator | `start()` rejects if project count exceeds limit |
| `auto_rebuild` | STARTER+ | SM-5 Watcher, SM-6 Pipeline | Watcher `start()` blocked; auto-pilot blocked |
| `auto_trace` | STARTER+ | SM-5 Watcher | `trigger_build` skips trace rebuild |
| `trace_index` | FREE | SM-4 BuildOrchestrator | Manual trace build allowed for all tiers |
| `mcp_trace_expand` | PRO+ | SM-6 Pipeline | Context expansion stage gated |
| `clara_compression` | PRO+ | SM-6 Pipeline | Compression stage blocked |
| `multi_repo_agent` | PRO+ | SM-4 BuildOrchestrator | Multi-project builds blocked |
| `team_config` | TEAM+ | — | Shared config sync blocked |
| `audit_log` | ENTERPRISE | — | Audit event emission blocked |

**Design principle:** Feature gates are checked at **transition time**, not at status-query time. A FREE user can _see_ that auto-rebuild exists (stage shows `'blocked'`) but the transition to `RUNNING` is rejected with an upgrade hint.

---

## 4. The Auto-Ingest Workflow (End-to-End State Flow)

The "auto-ingest" workflow — where a file change in the knowledge tree triggers automatic re-indexing and re-embedding — crosses multiple state machines:

```
File change detected (SM-5: IDLE → STALE → DEBOUNCING)
         ↓
Debounce timer fires (SM-5: DEBOUNCING → BUILDING)
         ↓
SM-5 calls trigger_build() → SM-4 starts code index build
         ↓
SM-4: index IDLE → RUNNING → COMPLETED
         ↓
SM-5 checks: trace enabled? → SM-4 starts trace build
         ↓
SM-4: trace IDLE → RUNNING → COMPLETED
         ↓
SM-6: structural stage → DONE (triggers cascade)
         ↓
If auto-pilot enabled (STARTER+ via SM-7):
  SM-6: catalogue READY → RUNNING → DONE
  SM-6: validation READY → RUNNING → DONE
  SM-6: knowledge_embedding READY → RUNNING → DONE
         ↓
SM-5: BUILDING → IDLE (or STALE if more changes arrived)
```

**Current problems with this flow:**
1. SM-5 calls `trigger_build()` but doesn't know when SM-4 completes — it polls `is_building()` every 250ms
2. SM-6 auto-pilot doesn't exist — stages must be triggered manually or by frontend SSE watcher
3. Tier gating is checked at step 1 (watcher start) but not at step 5 (auto-pilot) — a user who downgrades mid-session keeps auto-pilot running

**With state machines:** Each SM emits transition events. SM-5 subscribes to SM-4's `COMPLETED` event. SM-6 subscribes to SM-4's trace `COMPLETED` event to start its cascade. SM-7 is checked at each transition boundary.

---

## 5. Priority & Sequencing

### Tier 1 — High Value, Fixes Active Bugs

| ID | Machine | Layer | Effort | Impact |
|---|---|---|---|---|
| **SM-1** | Dashboard App.tsx | Frontend | 2–3 days | Fixes stale-state bugs, ~700 LOC removed |
| **SM-4** | Build Orchestrator | Backend | 1 day | Replaces 10+ globals, enables SM-6 |
| **SM-6** | Pipeline Orchestrator | Backend | 2 days | Enables auto-pilot, dependency enforcement |

### Tier 2 — Important, Enables Features

| ID | Machine | Layer | Effort | Impact |
|---|---|---|---|---|
| **SM-2** | Pipeline UI | Frontend | 0.5 day | Clean component, enables auto-pilot UI |
| **SM-5** | Watcher | Backend | 0.5 day | Cleaner lifecycle, better status reporting |
| **SM-7** | License/Feature Gate | Backend | 1 day | Expiration handling, activation UX |

### Tier 3 — Polish, Future-Proofing

| ID | Machine | Layer | Effort | Impact |
|---|---|---|---|---|
| **SM-3** | VS Code Daemon | Frontend | 0.5 day | Better reconnection, richer status bar |
| **SM-8** | Tauri Lifecycle | Inter-process | 1 day | Better startup UX, crash recovery |

### Dependency Graph

```
SM-4 (Build Orchestrator) ──→ SM-6 (Pipeline Orchestrator)
         ↓                              ↓
SM-5 (Watcher)              SM-2 (Pipeline UI)
                                        ↓
SM-7 (License) ←── gates ──→ SM-6, SM-5, SM-4
                                        
SM-1 (Dashboard) ←── consumes ──→ SM-4, SM-6 status APIs

SM-8 (Tauri) and SM-3 (VS Code) are independent
```

**Recommended execution order:**
1. **SM-4** (Build Orchestrator) — backend foundation, everything depends on this
2. **SM-6** (Pipeline Orchestrator) — builds on SM-4, enables auto-pilot
3. **SM-1** (Dashboard reducers) — frontend consumes clean APIs from SM-4/SM-6
4. **SM-5** (Watcher) — small, benefits from SM-4
5. **SM-2** (Pipeline UI) — trivial once SM-6 exists
6. **SM-7** (License) — can be done anytime, independent
7. **SM-3**, **SM-8** — polish, do last

---

## 6. Design Principles

| Principle | Rationale |
|---|---|
| **Explicit phases over boolean flags** | `phase: 'running'` is unambiguous; `building: true, exists: false` is not |
| **Transition validation** | Every `transition(new_phase)` call checks the VALID_TRANSITIONS table |
| **Events on transition** | State machines emit events (SSE, EventBus) when phases change — consumers don't poll |
| **Gates at boundaries** | Feature gates are checked at transition time, not query time |
| **Zero new dependencies (frontend)** | `useReducer` is built-in React — no Zustand, XState, or Redux needed |
| **Class-based (backend)** | Python classes with `@dataclass` state, replacing module-level dicts |
| **Incremental adoption** | Each SM can be implemented independently; no big-bang rewrite |
| **Testable in isolation** | Reducers/orchestrators are pure functions or classes testable without HTTP/UI |

---

## 7. Relationship to Phase 23

Phase 23 (Cleanup/Refactor) focuses on **file organization** — extracting routers, hooks, and components into separate files. Phase 24 focuses on **state correctness** — ensuring that the extracted pieces have well-defined lifecycle semantics.

They are complementary and can be interleaved:
- Phase 23 Sprint 6 (extract `useTraceSystem`) becomes Phase 24 SM-1 Phase 1 (trace pipeline reducer)
- Phase 23 Sprint 14 (extract `BuildManager`) becomes Phase 24 SM-4 (Build Orchestrator)

The difference: Phase 23 moves code; Phase 24 changes how state is structured within that code.

---

## 9. Research Findings & Advanced Patterns

Recent research into "StateFlow" (LLM-driven FSMs) and Hierarchical Multi-Agent Systems suggests two critical architectural refinements for CoDRAG.

### 9.1 Hierarchical State Machines (HSM)

Simple FSMs explode in complexity when handling nested lifecycles. We should adopt **Hierarchical State Machines** for complex domains:

**Where to apply:**
1.  **SM-6 (Pipeline Orchestrator):**
    -   **Parent State:** `Idle` | `Running` | `Paused` | `Error`
    -   **Child State (when Running):** `Structural` → `Catalogue` → `Validation` → ...
    -   *Benefit:* Global actions like "Pause" apply to the Parent state, automatically freezing whatever Child state is active.

2.  **SM-1 (Enrichment Reducer):**
    -   **Parent:** `EnrichmentMode` (`Manual` | `Auto-Pilot`)
    -   **Child:** `StageStatus` (per stage)

### 9.2 The "StateFlow" Pattern for LLMs

Papers like *StateFlow: Enhancing LLM Task-Solving through State-Driven Workflows* (2024) define a pattern where the FSM *is* the prompt engineering strategy.

**Application to CoDRAG (SM-6):**
Instead of just "running" a stage, the state machine defines the **context window** for that stage.
-   **State:** `EnrichingNode`
-   **Context:** `PreviousState` (Catalogue Role) + `Transition` (User Request)
-   **Guard:** If LLM confidence < 0.5, transition to `ReviewNeeded` instead of `Done`.

This moves "prompt logic" out of the Python worker and into the State Machine definition, making the AI behavior deterministic and testable.

### 9.3 Orchestration: "Root vs. Leaf"

Multi-agent systems often fail due to flat peer-to-peer communication. Research recommends a strict **Tree Topology**:

```
Root Orchestrator (SM-4 BuildOrchestrator)
├── Leaf Worker: Code Indexer (Rust)
├── Leaf Worker: Trace Builder (Rust)
└── Sub-Orchestrator: Pipeline (SM-6)
    ├── Leaf Worker: Augmenter (LLM)
    └── Leaf Worker: Enricher (LLM)
```

**Rule:** State flows down (commands), Events flow up (status). Sibling machines (e.g., Watcher and Pipeline) never talk directly; they communicate via the Root (BuildOrchestrator) or a shared Event Bus.

---

## 10. Open Questions

| ID | Question | Impact |
|---|---|---|
| Q-1 | Should SM-6 stages be cancellable? (Requires cooperative threading with `Event` flags) | SM-6 design |
| Q-2 | Should SM-4 support queuing? (Build requested while another runs → queue instead of reject) | SM-4 design |
| Q-3 | Should SM-7 check expiration on every request, or on a timer? | Performance vs. correctness |
| Q-4 | Should SM-8 support dynamic port selection? (Currently hardcoded to 8400) | SM-8 scope |
| Q-5 | Should the frontend subscribe to backend SM transitions via SSE, or continue polling? | **Recommendation: SSE (Event Sourcing)** |
| Q-6 | Should we introduce a shared `StateMachine` base class/utility? | **Yes (for SM-4, SM-5, SM-6)** |

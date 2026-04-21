# Agent Collaboration Infrastructure — Implementation Spec

> Date: 2026-04-06 | Layers 1 (Awareness) + 2 (Coordination), with Layer 3 (Emergence) roadmapped

---

## Scope

Build the collaboration infrastructure described in `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/README.md`, Layers 1 and 2 only. Layer 3 (Emergence) is roadmapped at the end of this document but not implemented.

**What we're building:**
- Agent-attributed observations (who created what)
- Per-role memory resources (agent starts session with its own history)
- Cross-agent findings resources (agents see each other's work)
- Activity feed (what happened recently, across all agents)
- Structural delta (what changed in the graph since timestamp X)
- Conflict detection (catch when agents disagree about the same file)
- Soft claims (agents declare active interest in files)
- 3 new MCP prompts: `prep-handoff`, `prep-scope`, `prep-triage`
- 5 new MCP resources: `memory/{role}`, `agents/{role}/findings`, `activity`, `delta`, `conflicts`

**What we're NOT building (Layer 3 roadmap):**
- Decision history tracking
- Consensus scoring
- Evidence-based task routing / TaskComplexityAnalysis
- Capability attestation
- Adaptive role scoping

**What already exists and is not touched:**
- The 5 MCP prompts from doc 14 (`prep-onboard`, `prep-review`, `prep-plan`, `prep-investigate`, `prep-health`) — already shipped in `server.py`
- The 4 existing MCP resources (`structure`, `atlas`, `files`, `health`) — untouched
- The 5 MCP tools (`prep`, `prep_search`, `prep_impact`, `prep_observe`, `prep_audit`) — untouched except `prep_observe` gains optional `created_by` param

---

## Architecture

### Package Structure

```
src/prep/services/collaboration/
    __init__.py              # CollaborationHub facade + public API
    activity.py              # ActivityStore — append-only agent action log
    snapshots.py             # GraphSnapshotStore — persist + diff graph state
    conflicts.py             # ConflictStore + ConflictDetector
    claims.py                # ClaimStore — soft file claims with auto-expiry

src/prep/mcp/
    collaboration_handlers.py  # Resource content generators + prompt handlers
                               # (keeps logic OUT of server.py)
```

### CollaborationHub Facade

Single entry point composing all sub-stores. Mirrors the `AgentCore` pattern.

```python
class CollaborationHub:
    """Single entry point for all collaboration infrastructure.
    
    Initialized once by the server/daemon. Agent engines, MCP handlers,
    and API routers all access collaboration features through this hub.
    """
    
    def __init__(self, db_path: Path):
        self.activity = ActivityStore(db_path)
        self.snapshots = GraphSnapshotStore(db_path)
        self.conflicts = ConflictStore(db_path)
        self.claims = ClaimStore(db_path)
        # Attribution wraps the existing observation_store singleton
        # (does NOT create a new store — filters on top of existing data)
```

### Integration with server.py — Minimal Touch Points

`server.py` gains exactly 4 small changes:

1. **Init:** Create `CollaborationHub` instance during server init (alongside existing stores). Uses the same `prep_settings.db` path from `settings_store`.
2. **Resources:** In `handle_resources_list`, extend the list with `get_collaboration_resources(project_id)`
3. **Resource read:** In `handle_resources_read`, try `handle_collaboration_resource(uri, hub, project_id)` first — if it returns content, use it; otherwise fall through to existing handlers
4. **Prompts:** Same pattern for `handle_prompts_list` and `handle_prompts_get`

All logic lives in `collaboration_handlers.py`. `server.py` is a thin dispatcher.

---

## Data Models

### Observation Store Changes (modify existing `services/observation_store.py`)

Add two columns to the `Observation` dataclass:

```python
@dataclass
class Observation:
    # ... existing fields unchanged ...
    created_by: Optional[str] = None    # "pi/watchdog" | "researcher" | "custodian" | "human"
    visibility: str = "shared"          # "shared" | "private" | "internal"
```

Schema migration (in `_create_tables`, after existing CREATE TABLE):

```sql
-- Safe to run repeatedly (IF NOT EXISTS pattern for columns via try/except)
ALTER TABLE observations ADD COLUMN created_by TEXT DEFAULT NULL;
ALTER TABLE observations ADD COLUMN visibility TEXT DEFAULT 'shared';
```

Extend `save()` signature:

```python
def save(
    self,
    project_id: str,
    content: str,
    file_path: Optional[str] = None,
    symbol_fqn: Optional[str] = None,
    trace_node_id: Optional[str] = None,
    category: str = "note",
    created_by: Optional[str] = None,      # NEW
    visibility: str = "shared",            # NEW
) -> str:
```

Extend `from_row()` to read new columns (with fallback for existing rows).

Add query method:

```python
def get_by_agent(
    self,
    project_id: str,
    created_by: str,
    include_stale: bool = False,
    visibility_filter: Optional[str] = None,
    limit: int = 50,
) -> List[Observation]:
    """Return observations created by a specific agent role."""
```

**Backward compatibility:** All existing callers pass no `created_by` — gets `NULL`. All existing observations get `visibility="shared"`. Zero behavior change for existing code paths.

### ActivityEntry (new: `services/collaboration/activity.py`)

```python
@dataclass
class ActivityEntry:
    id: str                   # uuid hex[:12]
    project_id: str
    agent_role: str           # "pi/watchdog" | "researcher" | "custodian" | "hr"
    action: str               # "delta_scan" | "topic_selection" | "safety_verify" etc.
    summary: str              # one-line human-readable
    details: Optional[Dict[str, Any]] = None
    created_at: float = 0.0
```

```sql
CREATE TABLE IF NOT EXISTS agent_activity (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    details_json TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_project_time 
    ON agent_activity(project_id, created_at DESC);
```

**ActivityStore API:**

```python
class ActivityStore:
    def __init__(self, db_path: Path): ...
    def log(self, project_id: str, agent_role: str, action: str, summary: str,
            details: Optional[Dict] = None) -> str: ...
    def get_recent(self, project_id: str, limit: int = 50, 
                   since: Optional[float] = None) -> List[ActivityEntry]: ...
    def prune(self, project_id: str, max_age_days: int = 30) -> int: ...
```

Auto-prune: `prune()` called lazily on `log()` when entry count > 1000.

### GraphSnapshot + StructuralDelta (new: `services/collaboration/snapshots.py`)

```python
@dataclass
class GraphSnapshot:
    id: str
    project_id: str
    hubs: List[Dict[str, Any]]           # [{path, dependents_count, rank}]
    modules: List[Dict[str, Any]]        # [{name, file_count, domain_tags}]
    cycles: List[List[str]]              # [[file_a, file_b], ...]
    cross_cutting: Dict[str, int]        # {concern_name: file_count}
    created_at: float

@dataclass
class StructuralDelta:
    since: float
    until: float
    hub_changes: List[Dict[str, Any]]
    module_changes: List[Dict[str, Any]]
    cycle_changes: List[Dict[str, Any]]
    cross_cutting_changes: List[Dict[str, Any]]
    
    @property
    def is_empty(self) -> bool:
        return not any([self.hub_changes, self.module_changes, 
                        self.cycle_changes, self.cross_cutting_changes])
```

```sql
CREATE TABLE IF NOT EXISTS graph_snapshots (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshot_project_time 
    ON graph_snapshots(project_id, created_at DESC);
```

**GraphSnapshotStore API:**

```python
class GraphSnapshotStore:
    def __init__(self, db_path: Path): ...
    def capture(self, project_id: str, hubs: List[Dict], modules: List[Dict],
                cycles: List[List[str]], cross_cutting: Dict[str, int]) -> str: ...
    def get_latest(self, project_id: str) -> Optional[GraphSnapshot]: ...
    def compute_delta(self, project_id: str, since: float) -> StructuralDelta: ...
    def prune(self, project_id: str, keep: int = 10) -> int: ...
```

**Delta computation:** `compute_delta` loads the snapshot closest to `since` and the latest snapshot, then diffs:
- Hubs: compare by path — new, removed, rank_changed (rank differs by >1 position)
- Modules: compare by name — new, removed, size_changed (file_count differs by >20%)
- Cycles: compare as sorted tuples — new, resolved
- Cross-cutting: compare counts — expanded (>20% growth), contracted (>20% shrink)

**Snapshot capture trigger:** Called from the pipeline orchestrator's `on_group_complete` callback — the same place Pi agent is triggered. Takes ~50ms (reads pre-computed data from existing index).

### AgentConflict (new: `services/collaboration/conflicts.py`)

```python
@dataclass
class AgentConflict:
    id: str
    project_id: str
    file_path: str
    agent_a: str
    agent_a_assessment: str
    agent_b: str
    agent_b_assessment: str
    conflict_type: str = "contradictory"   # "contradictory" | "scope_overlap" | "dependency_violation"
    resolution: str = "deferred"           # "deferred" | "agent_a_wins" | "agent_b_wins" | "human_review"
    detected_at: float = 0.0
    resolved_at: Optional[float] = None
```

```sql
CREATE TABLE IF NOT EXISTS agent_conflicts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    agent_a TEXT NOT NULL,
    agent_a_assessment TEXT NOT NULL,
    agent_b TEXT NOT NULL,
    agent_b_assessment TEXT NOT NULL,
    conflict_type TEXT NOT NULL DEFAULT 'contradictory',
    resolution TEXT DEFAULT 'deferred',
    detected_at REAL NOT NULL,
    resolved_at REAL
);
CREATE INDEX IF NOT EXISTS idx_conflicts_project 
    ON agent_conflicts(project_id, resolution);
```

**ConflictDetector API:**

```python
class ConflictDetector:
    """Detects contradictions between agent observations about the same files."""
    
    # Category pairs that indicate contradiction
    CONTRADICTORY_PAIRS = {
        ("pattern", "dead_code"),     # researcher sees value, custodian sees dead code
        ("decision", "dead_code"),    # someone decided to keep it, custodian flags deletion
        ("quality", "dead_code"),     # quality finding vs deletion candidate
    }
    
    def detect(self, project_id: str, observations: List[Observation]) -> List[AgentConflict]: ...
    def detect_from_push(self, project_id: str, groups: List[ConsolidatedGroup]) -> List[AgentConflict]: ...

class ConflictStore:
    def __init__(self, db_path: Path): ...
    def save(self, conflict: AgentConflict) -> str: ...
    def get_active(self, project_id: str) -> List[AgentConflict]: ...
    def resolve(self, conflict_id: str, resolution: str) -> bool: ...
```

**Detection triggers:**
1. After `PushEngine.push()` — compare findings across agent attributions
2. After Pi Watchdog delta scan — check if newly flagged files overlap with claimed files
3. On demand via collaboration hub

### SoftClaim (new: `services/collaboration/claims.py`)

```python
@dataclass
class SoftClaim:
    id: str
    project_id: str
    agent_role: str
    path: str                 # file path or directory
    reason: str
    claimed_at: float
    expires_at: float         # default: claimed_at + 86400 (24h)
```

```sql
CREATE TABLE IF NOT EXISTS soft_claims (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    path TEXT NOT NULL,
    reason TEXT,
    claimed_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_project_path 
    ON soft_claims(project_id, path);
```

**ClaimStore API:**

```python
class ClaimStore:
    DEFAULT_TTL = 86400  # 24 hours
    
    def __init__(self, db_path: Path): ...
    def claim(self, project_id: str, agent_role: str, path: str, 
              reason: str, ttl: float = DEFAULT_TTL) -> str: ...
    def release(self, claim_id: str) -> bool: ...
    def get_claims_for_path(self, project_id: str, path: str) -> List[SoftClaim]: ...
    def is_claimed(self, project_id: str, path: str, exclude_agent: Optional[str] = None) -> bool: ...
    def get_active(self, project_id: str) -> List[SoftClaim]: ...
    def cleanup_expired(self, project_id: str) -> int: ...
```

Expired claims cleaned up lazily on `claim()` and `get_active()`. `is_claimed()` checks both exact path and directory prefix (claiming `src/auth/` covers `src/auth/login.py`).

---

## MCP Resources (5 new)

All resource content generation lives in `src/prep/mcp/collaboration_handlers.py`.

### prep://{pid}/memory/{role}

**Content:** Observations filtered by `created_by={role}`, excluding stale, ordered by recency.

```markdown
## Researcher Memory (12 observations, 3 stale excluded)

### Recent (last 7 days)
- [2026-04-05] **Pattern detected in auth module** — JWT refresh logic
  duplicates session validation in 3 files.
  File: src/auth/refresh.py | Category: pattern

### Older (last 30 days)
- [2026-03-28] **Dead import chain investigated** — False positive.
  Chain is used by test fixtures loaded dynamically.
  File: src/auth/imports.py | Category: note
```

**Data source:** `observation_store.get_by_agent(project_id, role)`

### prep://{pid}/agents/{role}/findings

**Content:** Same query as memory, but `visibility != "private"`. For cross-agent browsing.

**Data source:** `observation_store.get_by_agent(project_id, role, visibility_filter="shared")`

### prep://{pid}/activity

**Content:** Last 50 activity entries as markdown table.

```markdown
## Agent Activity (last 24 hours)

| Time | Agent | Action | Summary |
|---|---|---|---|
| 04:12 | pi/watchdog | delta_scan | 3 new findings, 1 resolved |
| 06:00 | researcher | topic_selection | Selected "auth consolidation" (P1) |
| 08:30 | custodian | discovery | 4 dead code files (2 safe, 2 review) |
```

**Data source:** `hub.activity.get_recent(project_id, limit=50)`

### prep://{pid}/delta

**Content:** Structural delta since default lookback (7 days), or since `?since=` query param if the client supports it (parsed from URI query string).

```markdown
## Structural Delta (since 2026-03-30)

### Hub Changes
- **NEW:** src/api/gateway.py (14 dependents) — rank #4
- **RANK +2:** src/core/config.py — moved from #5 to #3
- **REMOVED:** src/utils/helpers.py — dropped below hub threshold

### Module Changes
- **NEW:** api_gateway (4 files) — split from core_api
- **MERGED:** auth_legacy absorbed into auth

### Cycle Changes
- **RESOLVED:** auth <-> session (extracted shared interface)
- **NEW:** gateway <-> middleware

### Cross-Cutting
- logging: 38 -> 45 files (expanded)
- error_handling: 18 -> 12 files (contracted)
```

**Data source:** `hub.snapshots.compute_delta(project_id, since)`

Returns "No structural changes detected" if delta is empty. Returns "No snapshots available yet — structural delta requires at least one completed index rebuild" if no snapshots exist.

### prep://{pid}/conflicts

**Content:** Active (unresolved) conflicts.

```markdown
## Active Agent Conflicts (2 unresolved)

### 1. src/auth/legacy.py
- **Researcher** (2026-04-05): "Important JWT pattern — consolidate into shared validator"
- **Custodian** (2026-04-05): "No imports found — safe to delete"
- **Type:** contradictory | **Status:** deferred

### 2. src/utils/format.py  
- **Researcher** (2026-04-04): "Used by 3 test fixtures via dynamic import"
- **Custodian** (2026-04-04): "Static analysis shows 0 dependents"
- **Type:** contradictory | **Status:** deferred
```

**Data source:** `hub.conflicts.get_active(project_id)`

Returns "No active conflicts" if empty.

---

## MCP Prompts (3 new)

### prep-handoff

**Arguments:** `from_role` (required), `to_role` (required), `task` (optional)

**Returns:**

```
You are taking over a task from the {from_role} agent.

{if task: "Task context: {task}"}

1. Review what {from_role} found — check @prep://memory/{from_role} for their observations and @prep://agents/{from_role}/findings for their findings.
2. Check @prep://activity for recent agent actions to understand the timeline.
3. Check @prep://conflicts for any disagreements that need resolution.
4. Call `prep_search` to deepen your understanding of the relevant code areas.
5. Continue the work: summarize what you're picking up and what your next steps are.
```

### prep-scope

**Arguments:** `role` (required)

**Returns:**

```
Show me what the {role} agent owns and what's happening in their domain.

1. Call `prep` for the structural overview, focusing on modules relevant to {role}.
2. Check @prep://memory/{role} for the agent's recent observations.
3. Check @prep://delta for structural changes that affect {role}'s scope.
4. Check @prep://conflicts for any disputes involving {role}.
5. Summarize: what modules does {role} own, what changed recently, what needs attention.
```

### prep-triage

**Arguments:** `focus` (optional)

**Returns:**

```
Triage the current agent findings and route them to the right agents.{if focus: " Focus on: {focus}."}

1. Call `prep_audit` to get current findings.
2. Check @prep://activity for what agents have already worked on.
3. Check @prep://conflicts for unresolved disagreements.
4. Cluster findings by root cause — group related issues that share affected files or dependency chains.
5. For each cluster: recommend which agent role should handle it, flag any conflicts, and note if multiple agents have independently flagged the same area (consensus signal).
```

---

## Agent Engine Integration

### Pi Agent (`services/pi_agent.py`)

**`_save_observation` gains `created_by`:**

```python
def _save_observation(
    self,
    content: str,
    category: str = "note",
    query_tag: Optional[str] = None,
    scenario: Optional[str] = None,      # NEW: "pi/watchdog", "pi/doctor", etc.
) -> None:
    # ... existing tag logic ...
    observation_store.save(
        self.project_id,
        tagged,
        category="note",
        created_by=scenario or "pi",     # NEW
    )
```

Each scenario call site passes its identity:
- Watchdog: `self._save_observation(..., scenario="pi/watchdog")`
- Doctor: `scenario="pi/doctor"`
- Geologist: `scenario="pi/geologist"`
- Dispatcher: `scenario="pi/dispatcher"`
- Librarian: `scenario="pi/librarian"`
- Architect: `scenario="pi/architect"`
- Scholar: `scenario="pi/scholar"`

**Activity logging:** Each scenario logs its action at start and end:

```python
# At scenario start:
self._collab_hub.activity.log(
    self.project_id, "pi/watchdog", "delta_scan_start",
    f"Starting delta scan after {group} pipeline completion"
)

# At scenario end:
self._collab_hub.activity.log(
    self.project_id, "pi/watchdog", "delta_scan_complete",
    f"Delta: {new_count} new, {resolved_count} resolved, {unchanged} unchanged",
    details={"new": new_count, "resolved": resolved_count}
)
```

**Snapshot capture:** After Watchdog completes (post-pipeline), capture a graph snapshot:

```python
# In Watchdog scenario, after delta scan:
self._capture_snapshot()

def _capture_snapshot(self) -> None:
    """Capture current graph state for structural delta computation."""
    # Read hub files, modules, cycles from existing index data
    # (same data the prep tool already serves)
    hub.snapshots.capture(self.project_id, hubs=..., modules=..., cycles=..., cross_cutting=...)
```

### Researcher Engine (`agents/researcher/engine.py`)

**Attribution:** Pass `created_by="researcher"` when saving observations via `AgentCore`.

**Activity logging:** Log at `select_topics`, `research_topic`, `formulate_plan` stages.

**Claim on research:** When starting research on a topic, claim affected files:

```python
def research_topic(self, topic: ResearchTopic, ...) -> ...:
    # Claim affected files
    for fp in topic.affected_files:
        self._collab_hub.claims.claim(
            self._project_id, "researcher", fp,
            reason=f"Researching: {topic.title}"
        )
    # ... existing research logic ...
```

### Custodian Engine (`agents/custodian/engine.py`)

**Attribution:** Pass `created_by="custodian"` when saving observations.

**Activity logging:** Log at `discover`, `verify`, `plan` stages.

**Claim checking:** Before marking a file as safe_to_delete, check claims:

```python
def _is_safe_candidate(self, file_path: str) -> bool:
    if self._collab_hub and self._collab_hub.claims.is_claimed(
        self._project_id, file_path, exclude_agent="custodian"
    ):
        logger.info("Skipping %s — claimed by another agent", file_path)
        return False
    return True
```

### AgentCore (`agents/core.py`)

**Extend with optional `CollaborationHub`:**

```python
class AgentCore:
    def __init__(
        self,
        project_id: str,
        index_dir: Path,
        project_root: Optional[Path] = None,
        pm_config: Optional[PMPushConfig] = None,
        collab_hub: Optional[CollaborationHub] = None,   # NEW
    ) -> None:
        # ... existing init ...
        self.collab = collab_hub  # NEW — engines access via core.collab

    def save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,     # NEW
    ) -> str:
        return self._data.save_observation(
            content, file_path=file_path, category=category, created_by=created_by
        )
```

### PushEngine (`adapters/push_engine.py`)

**Conflict detection after consolidation:**

```python
def push(self, items: List[ActionItem], ...) -> PushResult:
    # ... existing filter + consolidate ...
    
    # NEW: Detect conflicts before pushing
    if self._conflict_detector:
        conflicts = self._conflict_detector.detect_from_push(
            prep_project_id, groups
        )
        result.conflicts = conflicts  # NEW field on PushResult
        for c in conflicts:
            self._conflict_store.save(c)
    
    # ... existing push logic ...
```

`PushResult` gains:

```python
@dataclass
class PushResult:
    # ... existing fields ...
    conflicts: List[AgentConflict] = field(default_factory=list)  # NEW
```

### MCP `prep_observe` Tool

Extend the `prep_observe` / `prep_save_observation` tool handler in `server.py` to accept optional `created_by` parameter and pass it through to `observation_store.save()`. This requires:

1. Add `created_by` to the `prep_save_observation` tool schema in `mcp_tools.py`:
   ```python
   {"name": "created_by", "description": "Agent role identifier (e.g. 'researcher', 'pi/watchdog')", "type": "string", "required": False}
   ```
2. Pass `created_by` from tool arguments through to `observation_store.save()` in `server.py:tool_save_observation()`.

---

## Shared DB: `prep_settings.db`

All new tables live in the existing `prep_settings.db` file (same as observations). Each store in the collaboration package opens its own connection to this file using the same `WAL` + `DEFERRED` settings as `ObservationStore`. Table creation uses `IF NOT EXISTS` — safe to run multiple times, no migration framework needed.

---

## Testing Strategy

### Unit Tests (per store)

Each store gets a test file using an in-memory SQLite database:

| File | Tests |
|---|---|
| `tests/test_activity_store.py` | log, get_recent, get_recent_since, prune |
| `tests/test_graph_snapshots.py` | capture, get_latest, compute_delta (hub/module/cycle/cross-cutting changes), prune, empty delta |
| `tests/test_conflict_store.py` | save, get_active, resolve, detect contradictions |
| `tests/test_claim_store.py` | claim, release, is_claimed (exact + prefix), cleanup_expired, exclude_agent |
| `tests/test_observation_attribution.py` | save with created_by, get_by_agent, visibility filtering, backward compat (None created_by) |

### Integration Tests

| File | Tests |
|---|---|
| `tests/test_collaboration_hub.py` | Hub init, cross-store workflows (claim → detect conflict → log activity) |
| `tests/test_collab_resources.py` | Resource content generators produce valid markdown, handle empty state gracefully |
| `tests/test_collab_prompts.py` | Prompt handlers return valid message structures with argument interpolation |

### Existing Test Compatibility

The observation store changes are backward compatible — existing tests that call `save()` without `created_by` continue to work (defaults to `None`). No existing tests need modification.

---

## Layer 3 Roadmap (Not Implemented)

These features build on Layers 1+2 and should be considered after real usage data is available.

### Decision History Tracking

**What:** Record what each agent recommends (push finding, mark dead code, select topic) and track the outcome (accepted, rejected, fixed, expired).

**Why wait:** Need real push-to-Paperclip flow running with attribution to capture outcomes. Layer 1 attribution is a prerequisite.

**Data model:** `agent_decisions` table with `agent_role`, `decision_type`, `target`, `recommendation`, `confidence`, `outcome`, `outcome_at`, `outcome_by`.

**Estimated effort:** 3-4 days (table + recording hooks in all engines + outcome capture from Paperclip webhooks).

### Consensus Scoring

**What:** When 2+ agents independently flag the same file/area within a time window, compute a consensus score and boost that finding's priority.

**Why wait:** Need attributed observations (Layer 1) and enough observation volume to meaningfully detect convergence. Premature scoring on sparse data gives false signals.

**Algorithm:** `consensus_score = (agents_flagging / total_active_agents) * avg_confidence`. Threshold: score >0.5 gets auto-boosted in Paperclip push priority.

**Estimated effort:** 2-3 days (periodic computation + consensus resource + priority boost in PushEngine).

### Evidence-Based Task Routing

**What:** `TaskComplexityAnalysis` dataclass that provides structural evidence for routing decisions: scope_size, blast_radius, hub_involvement, cross_module flag, recommended_agent_class.

**Why wait:** Needs decision history to calibrate routing heuristics. Without outcome data, routing thresholds are guesses.

**Integration:** Fold into `prep_impact` tool as optional `include_routing: true` parameter. Paperclip reads the routing recommendation from Prep before assigning tasks.

**Estimated effort:** 3-4 days (model + heuristic + impact tool extension + Paperclip plugin update).

### Capability Attestation

**What:** Agents query Prep to assess whether they can handle a specific task before accepting it. Returns context budget estimate, required tools, risk factors.

**Why wait:** Needs task routing and real agent workload data to define meaningful capability thresholds. Also depends on Phase 73.3b tier system being stable.

**Estimated effort:** 2-3 days (prompt or tool + attestation logic based on graph metrics).

### Adaptive Role Scoping

**What:** Roles drift over time based on decision history. Weekly analysis correlates agent outcomes with file scopes and suggests scope adjustments.

**Why wait:** Requires months of decision history data. Most speculative feature — may not be needed if manual scope management works well enough.

**Estimated effort:** 5-7 days (analysis pipeline + suggestion UI + drift detection in Pi Geologist).

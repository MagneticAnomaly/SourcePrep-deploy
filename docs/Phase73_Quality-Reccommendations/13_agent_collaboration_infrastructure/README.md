# Phase 73.5 — Agent Collaboration Infrastructure

> Date: 2026-04-06 | Turning Prep from a code intelligence library into the coordination substrate for multi-agent development teams
>
> **Implementation Status:** COMPLETE — 19 commits, 76 tests, Layers 1+2 implemented with Paperclip-first revisions. See `feature_documentation.md` for what was built and `strategic_direction.md` for the Paperclip-first reframing.
>
> **Note:** This document is the original design. Some details were revised during implementation:
> - MCP resources reduced from 6 to 3 (activity + conflicts removed, consensus deferred)
> - `prep-triage` replaced with `prep-enrich`; `prep-attest` deferred to Layer 3
> - Cycles and cross-cutting dropped from snapshots (no structured data source)
> - Conflicts push to Paperclip as issues instead of being served as MCP resource

---

## 1. The Problem

Prep has a mature multi-agent ecosystem:

- **Pi Agent** (`services/pi_agent.py`) — 7 autonomous background scenarios (Watchdog, Doctor, Geologist, Dispatcher, Librarian, Architect, Scholar)
- **Staffing Engine** (`agents/hr/engine.py`) — generates AI agent role definitions from codebase graph analysis
- **Researcher Engine** (`agents/researcher/engine.py`) — mines audit findings, formulates implementation plans
- **Custodian Engine** (`agents/custodian/engine.py`) — detects dead code, verifies safety, plans cleanup
- **External agents** — Claude Code, Cursor, Windsurf, Gemini CLI, and Paperclip-managed agents all connect via MCP

Every one of these agents treats Prep as a **library**: go in, query data, leave. They have no awareness of each other. The Researcher doesn't know the Custodian flagged a file for deletion. The Watchdog can't signal the Dispatcher that something urgent appeared. The Staffing Engine generates role profiles without knowing which agents are actually active or what they've been working on.

This isn't a hypothetical problem. It produces real failures:

| Scenario | What Happens | Root Cause |
|---|---|---|
| Researcher investigates file X | Custodian simultaneously marks X as dead code | No cross-agent visibility |
| Watchdog finds critical delta | Researcher won't see it until next scheduled run | No inter-agent signaling |
| Staffing generates CEO role scope | Includes infrastructure files Custodian would delete | No awareness of pending cleanup |
| Two agents push overlapping findings | PushEngine consolidates silently, user can't trace origin | No agent attribution |
| Dispatcher triages 50 findings | Re-queries same audit data Watchdog already processed | No shared computation cache |

**The core issue:** Agents coordinate through side effects (reading/writing to shared stores) rather than through intentional collaboration primitives. Prep has the data and the position to fix this — it already sits at the center of every agent's data flow.

---

## 2. Vision: The Town Square Model

Today Prep is a **library** — agents visit individually, get what they need, leave.

The vision is Prep as a **town square** — agents leave traces of their work, see what others have done, react to structural changes, and coordinate through the shared medium of the codebase graph.

```
                    ┌──────────────────────────────────────────┐
                    │         Prep Town Square               │
                    │                                          │
                    │  ┌─────────┐  ┌──────────┐  ┌────────┐   │ 
                    │  │ Memory  │  │ Activity │  │ Delta  │   │
                    │  │ per-role│  │   Feed   │  │ Stream │   │
                    │  └────┬────┘  └────┬─────┘  └───┬────┘   │
                    │       │            │            │        │
                    │  ┌────┴────────────┴────────────┴────┐   │
                    │  │      Code Graph + Observations    │   │
                    │  └────┬────────────┬────────────┬────┘   │
                    │       │            │            │        │
                    └───────┼────────────┼────────────┼────────┘
                            │            │            │
              ┌─────────────┤            │            ├─────────────┐
              │             │            │            │             │
        ┌─────▼──┐   ┌──────▼──┐   ┌─────▼───┐  ┌────▼────┐  ┌─────▼────┐
        │Watchdog│   │Researcher│   │Custodian│  │Staffing │  │ External │
        │  (Pi)  │   │         │   │         │  │  (HR)   │  │  Agents  │
        └────────┘   └─────────┘   └─────────┘  └─────────┘  └──────────┘
```

**Design principles:**

1. **Observation-mediated collaboration** — agents don't message each other directly; they leave traces in a shared knowledge layer and react to what others have left. This is more resilient than point-to-point messaging and works across process boundaries.

2. **The graph IS the coordination medium** — structural changes in the codebase graph (new hubs, resolved cycles, changed rankings) are first-class events that agents can subscribe to. Not just "file changed" but "the dependency structure shifted."

3. **Attribution without orchestration** — every piece of agent work carries origin metadata (who created it, when, why) so downstream agents and humans can trace provenance. No central orchestrator needed.

4. **MCP-native** — all collaboration primitives are exposed as MCP resources, prompts, and tools. Any MCP client can participate, not just Prep's internal agents.

---

## 3. Three Layers of Collaboration

### Layer 1: Awareness — "Who did what?"

The foundation. Agents can see each other's recent work without going through an external system.

#### 3.1.1 Agent-Attributed Observations

**Current state:** The `Observation` dataclass (`services/observation_store.py:53`) has no concept of which agent created it. All observations are anonymous.

**Enhancement:** Add `created_by` field to observations.

```python
@dataclass
class Observation:
    id: str
    project_id: str
    content: str
    file_path: Optional[str] = None
    symbol_fqn: Optional[str] = None
    trace_node_id: Optional[str] = None
    category: str = "note"              # note | decision | bug | pattern | assumption
    created_by: Optional[str] = None    # NEW: "pi/watchdog" | "researcher" | "custodian" | "human" | "claude-code"
    created_at: float = 0.0
    updated_at: Optional[float] = None
    stale: bool = False
    stale_reason: Optional[str] = None
    visibility: str = "shared"          # NEW: "shared" | "private" | "internal"
```

**Why `created_by` matters:**
- `prep://memory/researcher` can filter to only researcher-created observations
- The Librarian (Pi scenario E) can make smarter cleanup decisions — agent observations decay differently than human observations
- Paperclip dashboards can show "Prep Researcher found..." vs "Prep Watchdog detected..."
- Conflict detection (Layer 2) needs to know which agents are disagreeing

**Why `visibility` matters:**
- `shared` — any agent or human can see it (default, backward compatible)
- `private` — only the creating agent's role can see it (e.g., researcher's working notes)
- `internal` — visible to Prep agents but not surfaced to external MCP clients (e.g., Pi's internal state tracking)

**Schema migration:** Single `ALTER TABLE observations ADD COLUMN created_by TEXT DEFAULT NULL` + `ADD COLUMN visibility TEXT DEFAULT 'shared'`. Non-breaking — existing observations get `NULL` created_by and `shared` visibility.

#### 3.1.2 Per-Role Memory Resources

**MCP Resource:** `prep://{pid}/memory/{role}`

Returns all non-stale observations created by a specific agent role, ordered by recency. This lets an agent starting a new session get its prior work as **reference context** injected into the conversation, rather than having to make a tool call mid-reasoning.

```json
{
    "uri": "prep://1d6f0b35/memory/researcher",
    "name": "Researcher Memory",
    "description": "Recent observations from the Researcher agent",
    "mimeType": "text/markdown",
    "audience": ["assistant"]
}
```

**Content structure (returned by resource read):**

```markdown
## Researcher Memory (12 observations, 3 stale excluded)

### Recent (last 7 days)
- [2026-04-05] **Pattern detected in auth module** — JWT refresh logic
  duplicates session validation in 3 files. Affects: src/auth/refresh.py,
  src/auth/session.py, src/auth/middleware.py
  
- [2026-04-04] **Research plan: Consolidate auth validators** — Root cause:
  organic growth without shared abstraction. Fix: extract BaseValidator.
  Effort: medium. Risk: low. Status: pushed to Paperclip (ISSUE-42).

### Older (last 30 days)
- [2026-03-28] **Dead import chain investigated** — False positive.
  Chain is used by test fixtures loaded dynamically.
```

**Tier-adaptive:** Tier 1 clients get full observations. Tier 2.5 gets titles + dates only.

**Use case flow:**
```
Agent session starts
  → System prompt includes @prep://memory/researcher
  → Agent already knows its prior findings before reasoning
  → No tool call needed for "what did I do last time?"
```

#### 3.1.3 Cross-Agent Visibility Resources

**MCP Resource:** `prep://{pid}/agents/{role}/findings`

Returns the latest findings from a specific agent, visible to other agents. This enables emergent collaboration — agents don't need a coordinator to tell them what others found, they can browse directly.

```json
{
    "uri": "prep://1d6f0b35/agents/custodian/findings",
    "name": "Custodian Findings",
    "description": "Files the Custodian marked for cleanup or deletion",
    "mimeType": "text/markdown",
    "audience": ["assistant"]
}
```

**Why this is different from Paperclip issues:**
- Paperclip issues are the *output* (processed, consolidated, formatted for humans)
- Agent findings are the *raw intelligence* (what the agent actually discovered, with structural context)
- An agent reading another agent's findings gets the Prep-native data (file paths, dependency counts, confidence scores), not a human-readable issue description

#### 3.1.4 Activity Feed Resource

**MCP Resource:** `prep://{pid}/activity`

A chronological feed of agent actions across all roles. Answers "what happened recently?" without querying each agent individually.

```markdown
## Activity Feed (last 24 hours)

| Time | Agent | Action | Summary |
|---|---|---|---|
| 04:12 | pi/watchdog | delta_scan | 3 new findings, 1 resolved. New hub: src/api/gateway.py |
| 04:15 | pi/dispatcher | triage | Clustered 12 findings into 3 root causes |
| 06:00 | researcher | topic_selection | Selected "auth consolidation" (P1) and "gateway routing" (P2) |
| 06:04 | researcher | plan_formulation | Auth consolidation: 3-step plan, medium effort |
| 08:30 | custodian | discovery | 4 dead code files identified (2 safe, 2 need review) |
```

**Implementation:** Lightweight — append-only log table in `prep_settings.db`. Each agent engine writes a one-line activity entry at key pipeline stages. The resource reads the last N entries.

---

### Layer 2: Coordination — "Don't step on each other"

Beyond awareness, agents need mechanisms to avoid semantic conflicts and share computed results.

#### 3.2.1 Structural Delta Resource

**MCP Resource:** `prep://{pid}/delta?since={timestamp}`

This is the most novel primitive. Git log tells you what *files* changed. This tells you what *structurally* shifted in the codebase graph — new hubs, resolved cycles, changed hub rankings, new modules, drift in cross-cutting concerns.

**Only Prep can answer this question.** No other tool has the graph.

```markdown
## Structural Delta (since 2026-04-04T00:00:00Z)

### Hub Changes
- **NEW HUB:** src/api/gateway.py (14 dependents) — emerged from 3→14 imports after API consolidation
- **RANK CHANGE:** src/core/config.py moved from #5 to #3 (gained 6 dependents)
- **DEMOTED:** src/utils/helpers.py dropped from hub list (lost 4 dependents after refactor)

### Module Changes
- **NEW MODULE:** api_gateway (4 files) — split from core_api module
- **MERGED:** auth_legacy absorbed into auth (3 files moved)

### Cycle Changes
- **RESOLVED:** auth ↔ session cycle (removed by extracting shared interface)
- **NEW CYCLE:** gateway ↔ middleware (introduced in commit abc123)

### Cross-Cutting
- **logging** concern expanded: now touches 45 files (was 38)
- **error_handling** concern contracted: 12 files (was 18) — good, consolidation working
```

**Why agents need this:**
- **Watchdog** — core job is delta detection; currently reimplements this by diff'ing audit runs. A first-class delta primitive eliminates ad-hoc diffing.
- **Geologist** — architecture drift detection becomes "read the delta resource for the last week" instead of a full re-scan.
- **Staffing** — role scopes need updating when modules split or merge. The delta tells HR *what* changed so it can target drift analysis.
- **External agents** — a Paperclip agent starting a task can check "did the structural landscape change since my last session?" in one resource read.

**Implementation:** Requires Prep to persist graph snapshots at rebuild time. On delta request, diff current graph against snapshot at `since` timestamp. Store snapshots as lightweight JSON (hub list + rankings, module list + sizes, cycle list). One snapshot per rebuild, pruned after 30 days.

**Data model:**

```python
@dataclass
class GraphSnapshot:
    """Lightweight graph state for delta computation."""
    timestamp: float
    project_id: str
    hubs: List[Dict[str, Any]]        # [{path, dependents_count, rank}]
    modules: List[Dict[str, Any]]     # [{name, file_count, domain_tags}]
    cycles: List[List[str]]           # [[file_a, file_b], ...]
    cross_cutting: Dict[str, int]     # {concern_name: file_count}
```

#### 3.2.2 Conflict Detection

When the PushEngine consolidates findings from multiple agents, it should detect and surface conflicts rather than merging silently.

**Conflict types:**

| Conflict | Example | Detection |
|---|---|---|
| **Contradictory assessment** | Researcher says "important pattern" vs Custodian says "dead code" on same file | Same `file_path`, opposing categories (quality vs dead_code) |
| **Scope overlap** | Two agents push findings about the same root file | Same `prep_address` prefix from different `created_by` |
| **Dependency violation** | Custodian plans to delete file X; Researcher's plan depends on file X | Cross-reference `affected_files` in cleanup plans vs research plans |

**Surfacing:** Conflicts appear in the activity feed, in `PushResult.conflicts` (new field), and as a dedicated MCP resource `prep://{pid}/conflicts`.

```python
@dataclass
class AgentConflict:
    """A disagreement between two agents about the same file or area."""
    id: str
    file_path: str
    agent_a: str                       # "researcher"
    agent_a_assessment: str            # "important pattern — consolidate"
    agent_b: str                       # "custodian"
    agent_b_assessment: str            # "dead code — safe to delete"
    resolution: Optional[str] = None   # "deferred" | "agent_a_wins" | "agent_b_wins" | "human_review"
    detected_at: float = 0.0
```

**Resolution strategy:** Conflicts default to `deferred` and are surfaced to the user via Paperclip issue or dashboard. If a resolution policy exists (e.g., "researcher outranks custodian on actively-referenced files"), it can be applied automatically.

#### 3.2.3 Soft Claims (File-Level Work Declarations)

An agent actively working on a set of files can declare a **soft claim** so other agents deprioritize that area. Not a lock (agents can still read), but a signal.

```python
@dataclass
class SoftClaim:
    """An agent's declaration of active interest in a file or directory."""
    agent_role: str
    path: str                          # file or directory
    claimed_at: float
    expires_at: float                  # Auto-expire after N hours
    reason: str                        # "researching auth consolidation"
```

**Behavior:**
- Custodian checks claims before marking files as dead code → skips claimed files
- Researcher checks claims before selecting topics → avoids areas another researcher is working on
- Claims auto-expire (default 24h) to prevent stale locks
- Visible in activity feed: "Researcher claimed src/auth/ for 'auth consolidation research'"

#### 3.2.4 Dependency Declarations on Plans

When the Researcher formulates a `ResearchPlan` or the Custodian creates a `CleanupPlan`, they can declare dependencies on other plans.

```python
@dataclass
class ResearchPlan:
    # ... existing fields ...
    depends_on: List[str] = field(default_factory=list)     # Plan IDs this depends on
    blocks: List[str] = field(default_factory=list)         # Plan IDs this blocks
```

**Use case:** "This auth consolidation plan depends on the custodian cleaning up `auth_legacy/` first." Paperclip can use this dependency graph to sequence agent work.

**Surfacing:** When pushing plans to Paperclip, dependency declarations map to issue links (e.g., "blocked by ISSUE-37").

#### 3.2.5 Shared Computation Cache

Agents frequently compute the same derived data:

- Watchdog and Researcher both call `run_audit()` within minutes of each other
- Researcher and Custodian both call `get_impact_radius()` on the same hub files
- Multiple agents query the same atlas projection

**Enhancement:** Add a computation cache to `AgentCore` with TTL-based invalidation.

```python
class AgentCore:
    def __init__(self, ...):
        ...
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl: float = 300.0  # 5 minutes

    def get_audit_findings(self, ...) -> List[ActionItem]:
        cache_key = f"audit:{min_priority}:{categories}"
        if cached := self._check_cache(cache_key):
            return cached
        result = self._data.get_audit_findings(...)
        self._set_cache(cache_key, result)
        return result
```

**Impact:** Eliminates redundant audit scans when Watchdog and Researcher run back-to-back. The second agent gets cached results in milliseconds instead of re-running scanners.

---

### Layer 3: Emergence — "Agents that get smarter together"

The most ambitious layer. Agent behavior improves over time based on collective outcomes.

#### 3.3.1 Decision History Tracking

Record what each agent recommends and what happens to that recommendation.

```python
@dataclass
class AgentDecision:
    """A record of an agent's recommendation and its outcome."""
    id: str
    agent_role: str
    decision_type: str                 # "push_finding" | "mark_dead_code" | "research_topic" | "generate_role"
    target: str                        # file path, finding ID, or role slug
    recommendation: str                # what the agent recommended
    confidence: float                  # 0.0-1.0 (agent's self-assessed confidence)
    timestamp: float
    outcome: Optional[str] = None      # "accepted" | "rejected" | "fixed" | "disputed" | "expired"
    outcome_at: Optional[float] = None
    outcome_by: Optional[str] = None   # "human" | "another_agent" | "auto"
```

**How outcomes are captured:**
- **accepted** — finding pushed to Paperclip and marked "done" by user
- **rejected** — user dismisses the finding or removes the Paperclip issue
- **fixed** — the underlying code issue was resolved (detected by next audit scan)
- **disputed** — another agent's finding contradicts this one (conflict detection)
- **expired** — finding went stale before any action was taken

**Storage:** New `agent_decisions` table in `prep_settings.db`. Lightweight — one row per decision, updated when outcome is known.

#### 3.3.2 Evidence-Based Task Routing

Instead of Paperclip (or the user) guessing whether a task is simple or complex, Prep provides structural evidence for routing decisions.

**New data model:**

```python
@dataclass
class TaskComplexityAnalysis:
    """Prep's structural assessment of how complex a task is."""
    finding_id: str
    scope_size: int                    # number of files directly affected
    blast_radius: int                  # number of files transitively affected
    dependency_depth: int              # max hops in dependency chain
    hub_involvement: int               # how many hub files are touched
    cross_module: bool                 # does this span multiple modules?
    confidence: float                  # 0.0-1.0 — how certain is the analysis?
    recommended_agent_class: str       # "lightweight" | "standard" | "heavyweight" | "human"
    reasoning: str                     # one-line explanation
```

**Routing heuristic:**

| Signal | Lightweight (Pi/Haiku) | Standard (Sonnet) | Heavyweight (Opus) | Human Review |
|---|---|---|---|---|
| scope_size | 1-3 files | 4-10 files | 11+ files | — |
| hub_involvement | 0 hubs | 1 hub | 2+ hubs | 3+ critical hubs |
| cross_module | No | No | Yes | Yes + unknown deps |
| confidence | >0.8 | >0.6 | >0.4 | <0.4 |

**MCP exposure:** This can fold into the existing `prep_impact` tool (add `include_routing: true` parameter) or become a new tool `prep_assess`. The lighter option is better — keep tool count low per Phase 73.4's principle.

#### 3.3.3 Consensus Scoring

When multiple agents independently flag the same area, that's a stronger signal than any single agent. A "consensus score" on findings surfaces these naturally.

**How it works:**

1. Watchdog detects delta in `src/auth/` (observation saved with `created_by: "pi/watchdog"`)
2. Researcher selects `src/auth/` as a research topic (observation saved with `created_by: "researcher"`)
3. Audit scanner flags `src/auth/session.py` as high-complexity (finding in `ActionItem`)

**Consensus detection:** When a file or directory appears in observations from 2+ distinct agents within a time window (7 days), it gets a consensus score:

```python
consensus_score = (num_agents_flagging / total_active_agents) * avg_confidence
```

**Surfacing:** High-consensus findings get priority boost in Paperclip pushes. The activity feed highlights them: "3/4 agents independently flagged src/auth/ — consensus score: 0.82."

#### 3.3.4 Agent Capability Attestation

Agents can query Prep to assess whether they have the capability to handle a task before accepting it.

**MCP prompt:** `prep-attest`

```
Arguments:
  capability: str    # "refactor_hub_file" | "dead_code_cleanup" | "cross_module_migration"
  context: str       # Optional description of the specific task

Returns:
  can_handle: bool
  required_context_budget: int   # estimated chars needed
  required_tools: List[str]      # MCP tools the agent would need
  risk_factors: List[str]        # what could go wrong
  alternative: Optional[str]     # "delegate to heavyweight agent" or similar
```

**Use case:** A Paperclip-managed lightweight agent receives a task. Before starting, it calls `prep-attest(capability="refactor_hub_file")`. Prep responds: "This touches a hub with 23 dependents. You'd need ~40K context chars and impact analysis. Recommend delegating to a heavyweight agent." The agent can then decline the task or request escalation.

#### 3.3.5 Adaptive Role Scoping

The Staffing Engine generates role scopes once. With decision history data, scopes can adapt over time.

**Signal:** If the Researcher consistently produces accepted findings in `src/api/` but rejected findings in `src/core/`, its effective scope should drift toward API work.

**Implementation:** Periodic drift analysis (weekly, via Pi Geologist) compares decision outcomes against role scopes. Generates `DriftReport` with recommended scope adjustments. Human approves adjustments via dashboard or Paperclip.

This is not automatic role mutation — it's evidence-based *suggestions* for scope refinement. The user decides.

---

## 4. MCP Primitive Mapping

Mapping all collaboration primitives to MCP's three control models (from Phase 73.4):

### 4.1 Resources (User-Browsable, `@` Mention)

> **As implemented** (3 resources, revised from original 6):

| Resource URI | Layer | Content | Update Trigger | Status |
|---|---|---|---|---|
| `prep://{pid}/memory/{role}` | Awareness | Agent's own observations | Observation save | **Implemented** |
| `prep://{pid}/agents/{role}/findings` | Awareness | Another agent's recent findings | Observation save | **Implemented** |
| `prep://{pid}/delta` | Coordination | Structural graph diff | Index rebuild | **Implemented** |
| ~~`prep://{pid}/activity`~~ | ~~Awareness~~ | ~~Chronological agent action feed~~ | ~~Any agent action~~ | **Removed** — Paperclip has richer activity feed |
| ~~`prep://{pid}/conflicts`~~ | ~~Coordination~~ | ~~Active inter-agent conflicts~~ | ~~Conflict detection~~ | **Removed** — Conflicts push to Paperclip as issues |
| `prep://{pid}/consensus` | Emergence | High-consensus findings | Periodic computation | **Deferred** to Layer 3 |

### 4.2 Prompts (User-Initiated, `/` Command)

> **As implemented** (3 prompts, revised from original 4):

| Prompt | Layer | Arguments | Returns | Status |
|---|---|---|---|---|
| `prep-handoff` | Coordination | `from_role`, `to_role`, `task` | Structured context transfer: memory + findings + delta | **Implemented** |
| `prep-scope` | Coordination | `role` | Live role scoping: owned modules, structural changes, findings | **Implemented** |
| `prep-enrich` | Coordination | `scope` (optional) | Structural enrichment: blast radius, hub involvement, cross-module analysis | **Implemented** (replaced `prep-triage`) |
| ~~`prep-triage`~~ | ~~Coordination~~ | ~~`finding_ids`~~ | ~~Cluster findings, assign to agent roles~~ | **Replaced** by `prep-enrich` — triage is Paperclip's job |
| `prep-attest` | Emergence | `capability`, `context` | Capability assessment: can the agent handle this? | **Deferred** to Layer 3 |

### 4.3 Tools (Model-Initiated, Agent Decides)

No new tools needed. The existing tool surface is sufficient:

| Tool | Collaboration Role |
|---|---|
| `prep` | Returns structural overview + links to collaboration resources |
| `prep_search` | Unchanged — agents search autonomously |
| `prep_impact` | Unchanged (routing analysis deferred to Layer 3) |
| `prep_observe` | Extended with `created_by` parameter for attribution |

**Why no new tools?** Tools are for autonomous agent decisions. Collaboration is inherently about *shared state* (resources) and *structured workflows* (prompts). Adding collaboration tools would bloat the tool surface and conflict with Phase 73.4's principle of keeping tools lean.

---

## 5. Implementation Plan

> **All phases below are COMPLETE except Phase 5.3 (Layer 3, deferred).**

### Phase 5.1: Awareness Layer (3-5 days) — COMPLETE

Foundation work. Everything else builds on attribution and visibility.

| Task | Files | Details | Effort |
|---|---|---|---|
| Add `created_by` + `visibility` to Observation | `services/observation_store.py` | Schema migration, update save/query methods | Small |
| Update all observation writers | `services/pi_agent.py`, `agents/researcher/engine.py`, `agents/custodian/engine.py` | Pass `created_by` to `save_observation()` calls | Small |
| Update `prep_observe` MCP tool | `mcp_tools.py`, `mcp/server.py` | Accept optional `created_by` param; external agents can self-identify | Small |
| Add per-role memory resource | `mcp/server.py` | New resource URI + content generator filtering by `created_by` | Medium |
| Add cross-agent findings resource | `mcp/server.py` | New resource URI + content generator | Medium |
| Add activity feed table + resource | `services/observation_store.py`, `mcp/server.py` | New `agent_activity` table + append-only writes from engines | Medium |
| Wire `listChanged` notifications | `mcp/server.py` | Emit resource list change on new observations | Small |

**Backward compatibility:** All changes are additive. Existing observations get `created_by=NULL`, `visibility="shared"`. No behavior change for callers that don't pass the new fields.

### Phase 5.2: Coordination Layer (5-7 days) — COMPLETE

Depends on Phase 5.1 (needs attribution for conflict detection).

| Task | Files | Details | Effort |
|---|---|---|---|
| Graph snapshot persistence | `services/` (new: `graph_snapshot.py`) | Save hub/module/cycle state on index rebuild | Medium |
| Delta computation | `services/graph_snapshot.py` | Diff two snapshots, produce `StructuralDelta` | Medium |
| Delta resource | `mcp/server.py` | New resource URI with `since` query parameter | Small |
| Conflict detection in PushEngine | `adapters/push_engine.py` | Cross-reference findings by file path and agent | Medium |
| Conflict resource | `mcp/server.py` | New resource URI exposing active conflicts | Small |
| Soft claims store | `services/` (new: `claim_store.py`) | SQLite table, auto-expiry, check methods | Medium |
| Wire claims into engines | `agents/custodian/engine.py`, `agents/researcher/engine.py` | Check claims before selecting targets | Small |
| `prep-handoff` prompt | `mcp/server.py` | Prompt definition with resource embedding | Medium |
| `prep-scope` prompt | `mcp/server.py` | Prompt definition with role scoping | Small |
| Shared computation cache in AgentCore | `agents/core.py` | TTL-based cache for audit findings + impact results | Small |
| Dependency declarations on plans | `agents/shared/models.py` | Add `depends_on`, `blocks` to ResearchPlan + CleanupPlan | Small |

### Phase 5.3: Emergence Layer (5-8 days) — DEFERRED

Depends on Phase 5.1 (needs attribution for decision tracking). Deferred pending real usage data.

| Task | Files | Details | Effort |
|---|---|---|---|
| Decision history table | `services/` (new: `decision_store.py`) | Schema + CRUD for AgentDecision records | Medium |
| Wire decision recording into engines | All agent engines | Record decisions at key pipeline stages | Medium |
| Outcome capture hooks | `adapters/push_engine.py`, observation store | Update decision outcome when Paperclip issue status changes | Medium |
| TaskComplexityAnalysis model | `agents/shared/models.py` | New dataclass | Small |
| Complexity analysis in impact tool | `mcp/server.py`, `api/routers/` | Add routing heuristic based on graph metrics | Medium |
| Consensus scoring | `services/` (new or extend `observation_store.py`) | Periodic computation: group observations by file, count distinct agents | Medium |
| Consensus resource | `mcp/server.py` | New resource URI | Small |
| `prep-attest` prompt | `mcp/server.py` | Prompt definition with capability matching | Medium |
| `prep-triage` prompt | `mcp/server.py` | Prompt definition with clustering + assignment | Medium |
| Adaptive role scope suggestions | `agents/hr/engine.py` + Pi Geologist | Correlate decision outcomes with role scopes | Large |

### Phase 5.4: Integration & Polish (2-3 days) — PARTIALLY COMPLETE

| Task | Files | Details | Effort | Status |
|---|---|---|---|---|
| Update AGENTS.md generation | `core/rules_generator.py` | Document collaboration resources in generated AGENTS.md | Small | Deferred |
| Update Paperclip plugin | `packages/paperclip-plugin-prep/` | Add data providers for delta + claims, `created_by` attribution | Medium | **DONE** |
| Dashboard collaboration panel | `src/prep/dashboard/` | Activity feed + conflict viewer | Medium | Deferred |
| Documentation | `docs/` | Feature docs, concept doc, strategic direction | Small | **DONE** |

---

## 6. Data Model Summary

### New Tables (in `prep_settings.db`)

```sql
-- Agent activity log (append-only)
CREATE TABLE agent_activity (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,           -- "pi/watchdog" | "researcher" | etc.
    action TEXT NOT NULL,               -- "delta_scan" | "topic_selection" | etc.
    summary TEXT NOT NULL,              -- one-line human-readable
    details_json TEXT,                  -- optional JSON blob
    created_at REAL NOT NULL
);
CREATE INDEX idx_activity_project_time ON agent_activity(project_id, created_at DESC);

-- Graph snapshots for delta computation
CREATE TABLE graph_snapshots (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,         -- GraphSnapshot serialized
    created_at REAL NOT NULL
);
CREATE INDEX idx_snapshot_project_time ON graph_snapshots(project_id, created_at DESC);

-- Soft claims
CREATE TABLE soft_claims (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    path TEXT NOT NULL,
    reason TEXT,
    claimed_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX idx_claims_project_path ON soft_claims(project_id, path);

-- Agent decisions (outcome tracking)
CREATE TABLE agent_decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    target TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    outcome TEXT,                        -- NULL until resolved
    outcome_at REAL,
    outcome_by TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX idx_decisions_project_agent ON agent_decisions(project_id, agent_role);
CREATE INDEX idx_decisions_target ON agent_decisions(project_id, target);

-- Conflicts
CREATE TABLE agent_conflicts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    agent_a TEXT NOT NULL,
    agent_a_assessment TEXT NOT NULL,
    agent_b TEXT NOT NULL,
    agent_b_assessment TEXT NOT NULL,
    resolution TEXT DEFAULT 'deferred',
    detected_at REAL NOT NULL,
    resolved_at REAL
);
CREATE INDEX idx_conflicts_project ON agent_conflicts(project_id, resolution);
```

### Modified Tables

```sql
-- observations table (existing) — add columns
ALTER TABLE observations ADD COLUMN created_by TEXT DEFAULT NULL;
ALTER TABLE observations ADD COLUMN visibility TEXT DEFAULT 'shared';
```

---

## 7. Relationship to Other Phases

| Phase | Relationship |
|---|---|
| **Phase 73.4** (MCP Ecosystem Optimization) | This doc extends 73.4's resource/prompt surface with collaboration-specific primitives. All new resources follow 73.4's tier-adaptive content pattern. All new prompts follow 73.4's resource-embedding pattern. |
| **Phase 66** (Pi Agent) | Pi's 7 scenarios become collaboration-aware: they write attributed observations, check claims, record decisions. The Watchdog scenario benefits most from the delta resource (replaces ad-hoc audit diffing). |
| **Phase 67** (AGENTS.md + Paperclip Plugin) | Generated AGENTS.md includes collaboration resource documentation. Paperclip plugin gets new data providers for activity feed and conflicts. |
| **Phase 65** (Pushing Tasks to Paperclip) | PushEngine enhanced with conflict detection. Decision history tracking closes the feedback loop — Prep learns which pushed findings were actually useful. |
| **Phase 73.3b** (Compression Tiering) | Collaboration resources respect the same tier-adaptive content rules. Memory resources compress at Tier 2.5; delta resources show fewer changes at lower tiers. |

---

## 8. What Makes This Unique

Most multi-agent frameworks (CrewAI, LangGraph, AutoGen, Google ADK) focus on **orchestration** — who calls whom in what order. They provide message buses, task queues, and execution graphs.

Prep's approach is fundamentally different:

| Generic Multi-Agent | Prep's Angle |
|---|---|
| Message passing (agent-to-agent) | **Observation-mediated collaboration** — agents leave traces in a shared knowledge layer, others react |
| Task queues (central dispatcher) | **Structural delta as trigger** — agents wake up because the *graph changed*, not because someone dispatched them |
| Role assignment (static config) | **Evidence-based role scoping** — roles adapt based on what the graph reveals about agent effectiveness |
| Orchestration graphs (DAGs) | **The codebase graph IS the coordination medium** — agents coordinate through structural awareness, not message routing |
| Capability discovery (agent cards) | **Capability attestation** — Prep tells agents what they *can and should* handle based on structural complexity |

**The unique value proposition:** Prep doesn't replace orchestrators like Paperclip. It gives them structural intelligence that makes orchestration better. Paperclip decides *who* works on what; Prep provides the evidence for *why* and warns when agents are about to conflict.

---

## 9. Success Criteria

1. **Attribution coverage** — 100% of observations carry `created_by` metadata within 1 release
2. **Zero silent conflicts** — PushEngine surfaces all cross-agent disagreements before pushing
3. **Delta resource latency** — structural diff computed in <2s for codebases up to 10K files
4. **Memory resource adoption** — agents that use `@prep://memory/{role}` make fewer redundant `prep_observe(action="get")` tool calls
5. **Consensus accuracy** — high-consensus findings (score >0.7) have >80% acceptance rate in Paperclip
6. **No new tools** — all collaboration primitives exposed as resources and prompts, tool count stays at 4-5
7. **Cross-client** — all resources and prompts work in Claude Code, Cursor, Windsurf, Gemini CLI, and Paperclip plugin

---

## 10. Research References

| Source | Key Finding | Relevance |
|---|---|---|
| Multi-Agent Collaboration Mechanisms Survey (arXiv 2501.06322, 2025) | Centralized + decentralized hybrid models preserve most diverse information | Validates our hub (observation store) + distributed (multi-scanner) approach |
| Multi-Agent LLM Systems: Emergent Collaboration (Preprints 2025) | Decentralized networks preserve 40% more diverse information than centralized | Supports observation-mediated collaboration over central message bus |
| A2A Protocol Spec (a2a-protocol.org, 2026) | Agent discovery via well-known endpoints, async task lifecycle | Complements MCP — Prep could expose A2A agent card for external discovery |
| MCP vs A2A Guide (DEV Community, 2026) | MCP = context provision, A2A = agent coordination; complementary protocols | Confirms our approach: MCP for data, observation store for coordination |
| Building Agent2Agent on MCP (Microsoft Developer Blog, 2026) | A2A communication can layer on top of MCP server infrastructure | Future extension path — Prep could serve both MCP and A2A from same backend |
| Phase 73.4 MCP Ecosystem Optimization | Right primitive, right control model; resources for reference data, prompts for workflows | Foundation for all MCP primitive decisions in this doc |
| Phase 66 Pi Agent Architecture | 7 autonomous scenarios, daemon thread, concurrency gate | The agents this infrastructure serves |
| Phase 67 Autonomous Agent Architecture | Hybrid MCP + REST model, role-based filtering, Paperclip integration | The integration surface this infrastructure enhances |

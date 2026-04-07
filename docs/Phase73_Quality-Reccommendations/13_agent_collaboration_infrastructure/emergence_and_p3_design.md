# Agent Collaboration Infrastructure — Emergence Layer & P3 Design

> Date: 2026-04-06 | Phase 73.5 extension
> Principle: **Do the most with the least. Fill gaps Paperclip/Claude Code can't fill. No redundancy.**

---

## 1. Design Philosophy

Layer 3 ("Emergence") was originally roadmapped as 5 features requiring 15-24 days of work and months of accumulated data. After critical review, we reduced it to **3 features + 2 P3 items** — all of which leverage existing infrastructure and provide immediate value.

**What we kept and why:**

| Feature | Why it stays | What it leverages |
|---|---|---|
| Consensus Scoring | Paperclip sees individual issues. Only CoDRAG knows "3 agents independently flagged the same area." | `get_all_attributed()`, `created_by`, `file_path` |
| Structural Complexity on Push | Paperclip assigns tasks but has zero structural awareness. "Is this a 3-file leaf fix or a 40-file hub refactor?" | `codrag_impact` logic, hub file detection, PushEngine |
| Delta Push to Paperclip (P3) | Only CoDRAG knows structural shifts — new hubs, module splits, rank changes | `GraphSnapshotStore`, `StructuralDelta`, PushEngine |
| Claims Push to Paperclip (P3) | Paperclip can't see file-level claims without CoDRAG telling it | `ClaimStore`, Paperclip plugin data provider |

**What we dropped and why:**

| Feature | Why it's out |
|---|---|
| Decision History Tracking | Paperclip already tracks issue outcomes (done/rejected/expired). Building a parallel outcome tracker is redundant. |
| Capability Attestation | Requires a stable tier system and agent self-assessment protocol that don't exist yet. Premature. |
| Adaptive Role Scoping | Requires months of accumulated decision data. Can't produce meaningful results today. |

---

## 2. Feature 1: Consensus Scoring

### 2.1 The Gap

Paperclip receives individual issues from CoDRAG. Each issue stands alone. But when 3 out of 4 agents independently flag the same file or directory, that's a much stronger signal than any single finding. Paperclip can't compute this because agent observations live in CoDRAG's observation store, not in Paperclip's issue tracker.

### 2.2 How It Works

Consensus scoring is a **query, not a system**. It groups attributed observations by file path, counts distinct agents, and produces a score:

```
consensus_score = distinct_agents_flagging / total_active_agents
```

For example:
- `src/auth/session.py` has observations from `pi/watchdog`, `researcher`, and `custodian` (3 agents)
- 5 distinct agents have observations in the project total
- Consensus score: `3/5 = 0.60`

A score above **0.5** (majority of active agents agree) is a high-consensus finding.

### 2.3 What Gets Built

**No new tables. No new stores. One new method on ObservationStore.**

```python
# In observation_store.py

def get_consensus_scores(
    self,
    project_id: str,
    min_agents: int = 2,
    since_days: int = 30,
) -> List[Dict[str, Any]]:
    """Group attributed observations by file_path, count distinct agents.

    Returns a list of:
    {
        "file_path": "src/auth/session.py",
        "agents": ["pi/watchdog", "researcher", "custodian"],
        "agent_count": 3,
        "total_active_agents": 5,
        "consensus_score": 0.60,
        "latest_observation_at": 1712444800.0,
    }

    Only returns files flagged by min_agents or more distinct agents.
    Excludes stale observations. Only counts observations within since_days.
    """
```

This is a single SQL query:

```sql
SELECT file_path,
       GROUP_CONCAT(DISTINCT created_by) AS agents,
       COUNT(DISTINCT created_by) AS agent_count,
       MAX(created_at) AS latest_at
FROM observations
WHERE project_id = ?
  AND created_by IS NOT NULL
  AND file_path IS NOT NULL
  AND stale = 0
  AND created_at > ?
GROUP BY file_path
HAVING COUNT(DISTINCT created_by) >= ?
ORDER BY agent_count DESC, latest_at DESC
```

The `total_active_agents` denominator comes from a second query:

```sql
SELECT COUNT(DISTINCT created_by) FROM observations
WHERE project_id = ? AND created_by IS NOT NULL AND created_at > ?
```

### 2.4 How It Surfaces

**On Push:** PushEngine attaches consensus data to each `PMIssue` before pushing to Paperclip. If a `ConsolidatedGroup`'s `affected_files` overlap with high-consensus files, the issue description includes:

```markdown
**Consensus:** 3/5 agents independently flagged files in this area
(pi/watchdog, researcher, custodian)
```

**On MCP Resource:** The existing `codrag://delta` resource is extended with a "Consensus Hotspots" section when consensus data exists:

```markdown
## Consensus Hotspots (files flagged by 2+ agents)

| File | Agents | Score |
|---|---|---|
| src/auth/session.py | pi/watchdog, researcher, custodian | 0.60 |
| src/core/config.py | pi/geologist, researcher | 0.40 |
```

This avoids creating a new MCP resource — consensus piggybacks on the delta resource since both answer "what should I pay attention to?"

**On codrag-enrich prompt:** The `codrag-enrich` prompt already walks through findings and adds structural intelligence. We add one more step:

```
6. Check for consensus: which findings overlap with files that multiple
   agents have independently flagged? High-consensus areas (score > 0.5)
   should be treated as higher priority.
```

### 2.5 No New MCP Resource

The original design included a `codrag://consensus` resource. We're not building it. Consensus data is simple enough to embed in the delta resource and the push payload. A separate resource would fragment the information and add surface area without proportional value.

### 2.6 Data Flow

```
Observation Store (existing data, no new writes needed)
  ↓ get_consensus_scores(project_id, min_agents=2, since_days=30)
  ↓
ConsensusResult: [{file_path, agents, score}, ...]
  ↓
Two consumers:
  1. PushEngine.push() → enrich PMIssue descriptions
  2. collaboration_handlers.py → append to delta resource content
```

### 2.7 Testing

4-5 tests in a new `tests/test_consensus_scoring.py`:

1. No observations → empty results
2. Single agent per file → empty results (below min_agents threshold)
3. Two agents on same file → returns consensus entry with score
4. Stale observations excluded
5. `since_days` filter works (old observations don't count)

---

## 3. Feature 2: Structural Complexity on Push

### 3.1 The Gap

When CoDRAG pushes a finding to Paperclip as an issue, the issue says "quality problem in src/gateway.py" with a priority (P0-P3) and effort estimate (small/medium/large). But it doesn't say:

- "This file has 23 dependents — changes here affect 40% of the codebase"
- "This spans 3 modules — it's a cross-cutting concern"
- "This touches a hub file ranked #2 — high blast radius"

Paperclip gets the *what* but not the *structural why*. It routes tasks based on category and priority, but it can't distinguish a leaf-file fix from a hub-file refactor. Only CoDRAG has the dependency graph to compute this.

### 3.2 How It Works

When PushEngine builds a `PMIssue` for each `ConsolidatedGroup`, it enriches the issue with structural metadata from the trace index:

1. **For each affected file**, check if it's a known hub file (from the latest graph snapshot)
2. **Count hub involvement**: how many of the group's affected files are hubs?
3. **Cross-module check**: do the affected files span multiple modules?
4. **Blast radius**: sum of all dependents across affected hub files

This data is already computed and cached — hub files are in `GraphSnapshotStore`, module membership is in the trace index. No new computation needed.

### 3.3 What Gets Built

**A new dataclass for structural context:**

```python
# In pm_models.py

@dataclass
class StructuralContext:
    """Structural intelligence attached to a PM issue.

    CoDRAG-only data that helps Paperclip route work.
    """
    hub_files_involved: List[str] = field(default_factory=list)
    hub_count: int = 0
    total_dependents: int = 0          # Sum of dependents across hub files
    modules_spanned: List[str] = field(default_factory=list)
    cross_module: bool = False
    complexity_tier: str = "standard"  # "lightweight" | "standard" | "heavyweight"
```

**Complexity tier heuristic:**

| Signal | Lightweight | Standard | Heavyweight |
|---|---|---|---|
| Hub files involved | 0 | 1 | 2+ |
| Total dependents | <5 | 5-20 | 20+ |
| Cross-module | No | No | Yes |

```python
def compute_complexity_tier(ctx: StructuralContext) -> str:
    if ctx.hub_count >= 2 or ctx.total_dependents > 20 or ctx.cross_module:
        return "heavyweight"
    if ctx.hub_count >= 1 or ctx.total_dependents > 5:
        return "standard"
    return "lightweight"
```

**Integration into PushEngine:**

A new method `_enrich_with_structural_context()` is called in `_push_group()` before building the `PMIssue`:

```python
def _enrich_with_structural_context(
    self,
    group: ConsolidatedGroup,
    project_id: str,
) -> Optional[StructuralContext]:
    """Compute structural context for a consolidated group.

    Uses the latest graph snapshot to check hub involvement
    and module membership of affected files.
    """
```

This reads from the existing `GraphSnapshotStore` (latest snapshot's hub list) and module cluster data. No additional API calls needed.

**PMIssue description enrichment:**

When structural context is available, append to the issue description:

```markdown
---
### Structural Context (CoDRAG)
- **Complexity:** heavyweight
- **Hub files:** src/gateway.py (#2, 23 dependents), src/config.py (#3, 18 dependents)
- **Modules spanned:** api_gateway, core_config, auth
- **Blast radius:** 41 total dependents
```

**PMIssue model change:**

Add an optional `structural_context` field to `PMIssue`:

```python
structural_context: Optional[StructuralContext] = None
```

And include `complexity_tier` in `PushResult.to_dict()`:

```python
"complexity_tiers": {
    "lightweight": count_lightweight,
    "standard": count_standard,
    "heavyweight": count_heavyweight,
}
```

### 3.4 How Paperclip Uses This

The Paperclip plugin already renders issue descriptions. The structural context section appears naturally in the issue body. More importantly:

1. **Routing hint**: A Paperclip orchestrator can parse `complexity_tier` from the issue description (or from the plugin's data provider) to route heavyweight tasks to Opus-class agents and lightweight tasks to Haiku-class agents.

2. **Priority adjustment**: A finding with `hub_count >= 2` and `total_dependents > 30` might warrant priority escalation regardless of its original P2 rating.

3. **Effort estimation**: Cross-module findings spanning 3+ modules are structurally harder than their category suggests.

### 3.5 Where the Data Comes From

The method needs access to the latest graph snapshot. Two options:

**Option A (recommended): Read from CollaborationHub.snapshots**

PushEngine already has optional `conflict_detector` and `conflict_store` params. Add `snapshot_store: Optional[GraphSnapshotStore] = None`. The latest snapshot's hub list provides all the data needed.

```python
def _enrich_with_structural_context(self, group, project_id):
    if not self._snapshot_store:
        return None
    latest = self._snapshot_store.get_latest(project_id)
    if not latest:
        return None

    hub_paths = {h["path"]: h for h in latest.hubs}
    hub_files = [f for f in group.affected_files if f in hub_paths]
    total_deps = sum(hub_paths[f].get("dependents_count", 0) for f in hub_files)

    # Module detection from snapshot
    file_to_module = {}
    for mod in latest.modules:
        for f in mod.get("files", []):
            file_to_module[f] = mod["name"]
    modules = list(set(file_to_module.get(f, "unknown") for f in group.affected_files))

    ctx = StructuralContext(
        hub_files_involved=hub_files,
        hub_count=len(hub_files),
        total_dependents=total_deps,
        modules_spanned=modules,
        cross_module=len(modules) > 1,
    )
    ctx.complexity_tier = compute_complexity_tier(ctx)
    return ctx
```

**Option B: Call codrag_impact per file**

Slower, makes HTTP calls, but uses the full live trace index. Overkill for push enrichment — snapshot data is sufficient.

### 3.6 Testing

5-6 tests in `tests/test_structural_enrichment.py`:

1. No snapshot → returns None (graceful degradation)
2. Leaf files only → lightweight tier
3. One hub file → standard tier
4. Multiple hub files + cross-module → heavyweight tier
5. Verify description enrichment includes structural context section
6. PushResult includes complexity tier counts

---

## 4. Feature 3: Delta Push to Paperclip (P3)

### 4.1 The Gap

Structural deltas are captured in `GraphSnapshotStore` and served via the `codrag://delta` MCP resource. But Paperclip users who don't browse MCP resources never see them. When a new hub file emerges with 14 dependents, or a module splits into two, that's architecturally significant — and the right place for it to appear is as a Paperclip issue that can be assigned, discussed, and tracked.

### 4.2 How It Works

After Pi Watchdog captures a graph snapshot and computes a delta, significant changes are pushed to Paperclip as issues. "Significant" means:

- A **new hub** was detected (a file gained enough dependents to enter the hub list)
- A hub was **removed** (a former hub lost dependents below the threshold)
- A **new module** appeared (code reorganization or growth)
- A module was **removed** (consolidation or cleanup)

Rank changes within the existing hub list are NOT pushed — they're informational noise at the issue level (they still appear in the MCP delta resource).

### 4.3 What Gets Built

**No new stores.** No new tables. A new method on PushEngine:

```python
def push_significant_delta(
    self,
    delta: StructuralDelta,
    project_id: str,
) -> int:
    """Push significant structural changes to Paperclip as issues.

    Returns the number of issues created.
    """
```

**Issue format:**

```markdown
Title: "Structural Change: src/gateway.py is a new hub (14 dependents)"
Description: |
  A new hub file was detected after pipeline rebuild.

  **File:** src/gateway.py
  **Change:** New hub
  **Dependents:** 14
  **Rank:** #2

  Hub files are central dependencies — many other files import from them.
  Changes to hub files have high blast radius. Consider:
  - Adding this file to code review requirements
  - Monitoring for breaking changes
  - Assessing whether the dependency count is intentional

  <!-- codrag-address:codrag://project_id/DELTA-abc123 -->
  <!-- codrag-delta:true -->

Priority: P3 (informational)
Category: "architecture"
```

**Significance filter:**

Only push deltas where `change` is `"new"` or `"removed"`:

```python
def _get_significant_changes(self, delta: StructuralDelta) -> List[Dict]:
    significant = []
    for h in delta.hub_changes:
        if h["change"] in ("new", "removed"):
            significant.append({**h, "type": "hub"})
    for m in delta.module_changes:
        if m["change"] in ("new", "removed"):
            significant.append({**m, "type": "module"})
    return significant
```

### 4.4 Integration Point

**Problem:** Pi agent doesn't have access to PushEngine or PaperclipAdapter. It runs in a background thread and interacts with the collaboration stores, not the PM layer.

**Solution: Indirect push via pending observation.**

Pi Watchdog writes a special observation when it detects a significant delta:

```python
# In pi_agent.py, after _capture_graph_snapshot()
if delta and not delta.is_empty:
    significant = [c for c in delta.hub_changes + delta.module_changes
                   if c.get("change") in ("new", "removed")]
    if significant:
        self._save_observation(
            content=json.dumps({"delta_changes": significant}),
            category="note",
            scenario="pi/watchdog",
            file_path=None,  # No single file — structural change
        )
```

Then PushEngine, during its normal push cycle, checks for recent delta observations and pushes them. This avoids coupling Pi to the PM adapter and follows the existing pattern: **agents produce observations, PushEngine consumes and pushes.**

Alternatively (simpler): the collaboration FastAPI route for delta can have an optional `?push=true` query param that triggers the push directly. This lets the dashboard's "Rebuild Pipeline" button trigger a delta push check.

### 4.5 Dedup

Uses the existing `codrag-address` pattern. Each significant change gets a stable address derived from its content:

```python
# For a new hub:
address = f"codrag://{project_id}/DELTA-hub-{file_path_hash}"

# For a new module:
address = f"codrag://{project_id}/DELTA-module-{module_name_hash}"
```

The same structural change won't create duplicate Paperclip issues across multiple pipeline rebuilds.

### 4.6 Testing

4-5 tests in `tests/test_delta_push.py`:

1. Empty delta → no issues pushed
2. Rank-change only → no issues pushed (not significant enough)
3. New hub → one issue created with correct title/description
4. Dedup: same delta pushed twice → only one issue exists
5. Mixed delta (new hub + removed module) → two issues created

---

## 5. Feature 4: Claims Push to Paperclip (P3)

### 5.1 The Gap

When the Researcher claims `src/auth/` for investigation, the Custodian respects that claim within CoDRAG. But Paperclip doesn't know. If Paperclip assigns a task touching `src/auth/login.py` to another agent, there's no warning that the Researcher is actively working there.

### 5.2 How It Works

The Paperclip plugin already has an `agent-claims` data provider that calls `GET /projects/{pid}/collaboration/claims`. This shows claims in the Paperclip UI. The gap is that Paperclip's routing logic can't programmatically access this.

**Solution: The plugin data provider is sufficient.** We don't need to push claims as issues (they're ephemeral, 24h TTL — issues are persistent). Instead:

1. The `agent-claims` data provider (already built) exposes claims to the Paperclip UI
2. Add a **claim summary** to the `codrag-enrich` prompt output so agents see active claims when reviewing findings
3. Add a **claim check** step to the `codrag-handoff` prompt so receiving agents know what's claimed

### 5.3 What Gets Built

**Minimal: extend two existing prompts.**

In `collaboration_handlers.py`, update the `codrag-enrich` prompt to include:

```
7. Check active file claims: which files are currently claimed by agents?
   Findings on claimed files should note the claim — the claiming agent
   may already be addressing the issue.
```

In `collaboration_handlers.py`, update the `codrag-handoff` prompt to include:

```
5. Check active claims: does the from-agent have any active file claims?
   The receiving agent should be aware of claimed areas and either
   respect or release those claims.
```

**No new API endpoints. No new data providers.** The `agent-claims` data provider and the `/collaboration/claims` endpoint already exist.

### 5.4 Testing

2 tests (extend existing `test_collab_resources.py`):

1. `codrag-enrich` prompt text includes "claims" reference
2. `codrag-handoff` prompt text includes "claims" reference

---

## 6. What We're NOT Building (And Why)

### 6.1 Decision History Tracking

**Original idea:** Record what each agent recommends and track whether it was accepted, rejected, or fixed.

**Why it's redundant:** Paperclip already tracks issue lifecycle — created → assigned → in_progress → done/rejected. When CoDRAG pushes a finding to Paperclip, Paperclip tracks the outcome. Building a parallel outcome tracker in CoDRAG means:
- Two sources of truth for the same data
- Sync problems when Paperclip and CoDRAG disagree about whether something was "accepted"
- Extra complexity for data that's already captured

**If we need this later:** Poll Paperclip's issue status (via the plugin or API) to compute agent accuracy. Don't store outcomes separately — read them from where they naturally live.

### 6.2 Capability Attestation

**Original idea:** Agents query CoDRAG to assess whether they can handle a task before accepting it.

**Why it's premature:**
- No stable tier system exists (agents don't have formal capability profiles)
- The `complexity_tier` from Feature 2 provides the routing signal without the self-assessment protocol
- Attestation requires agents to understand their own capabilities — this is an AI alignment problem, not a database query

**If we need this later:** Start with `complexity_tier` as the routing signal. If Paperclip's routing needs more nuance, build attestation as a Paperclip-side feature that queries CoDRAG's structural context.

### 6.3 Adaptive Role Scoping

**Original idea:** Roles drift over time based on decision history. Weekly analysis suggests scope adjustments.

**Why it's premature:**
- Requires months of accumulated decision data that doesn't exist
- The Staffing Engine (HR) already generates role scopes from graph analysis
- Adaptive scoping without data is just role randomization

**If we need this later:** After 3+ months of attributed observations and Paperclip outcome data, build a periodic analysis that correlates agent success rates with file paths. This is a data science task, not an infrastructure task.

---

## 7. Implementation Summary

### What's New

| Component | Location | Effort | Description |
|---|---|---|---|
| `get_consensus_scores()` | `observation_store.py` | Small | Single SQL query, returns file → agent consensus |
| `StructuralContext` dataclass | `pm_models.py` | Trivial | Hub count, dependents, modules, complexity tier |
| `_enrich_with_structural_context()` | `push_engine.py` | Small | Read latest snapshot, compute context per group |
| `push_significant_delta()` | `push_engine.py` | Small | Filter significant changes, push as PM issues |
| Consensus in delta resource | `collaboration_handlers.py` | Trivial | Append consensus hotspots to delta content |
| Consensus in push description | `push_engine.py` | Trivial | Append consensus note to PMIssue description |
| Claims in prompts | `collaboration_handlers.py` | Trivial | Add claims step to enrich + handoff prompts |

### What's Modified

| File | Change |
|---|---|
| `observation_store.py` | Add `get_consensus_scores()` method |
| `pm_models.py` | Add `StructuralContext` dataclass, `structural_context` on `PMIssue`, complexity tiers on `PushResult.to_dict()` |
| `push_engine.py` | Add `snapshot_store` param, `_enrich_with_structural_context()`, `push_significant_delta()`, consensus enrichment in `_push_group()` |
| `collaboration_handlers.py` | Consensus section in delta resource, claims steps in enrich + handoff prompts |

### Tests

| File | Tests | Description |
|---|---|---|
| `tests/test_consensus_scoring.py` | 5 | Consensus query edge cases |
| `tests/test_structural_enrichment.py` | 6 | Complexity tier computation + description enrichment |
| `tests/test_delta_push.py` | 5 | Delta push significance filter + dedup |
| `tests/test_collab_resources.py` | +2 | Prompt text includes claims references |

**Total: ~18 new tests, ~7 modified files, no new stores, no new tables.**

### Implementation Order

1. **Consensus Scoring** — independent, no dependencies on other features
2. **Structural Complexity on Push** — independent, needs `snapshot_store` param added to PushEngine
3. **Delta Push** — depends on PushEngine having `snapshot_store` (from step 2)
4. **Claims in Prompts** — independent, trivial

Steps 1 and 4 can be done in parallel. Steps 2 and 3 are sequential.

---

## 8. Success Criteria

1. **Consensus is visible:** Paperclip issues for high-consensus areas include "N/M agents flagged this" in the description
2. **Complexity tiers work:** PushResult includes lightweight/standard/heavyweight counts. Heavyweight issues have structural context in their description
3. **Delta push fires:** When a new hub emerges after pipeline rebuild, a Paperclip issue is created (once, not on every rebuild)
4. **Claims in prompts:** Running `/codrag-handoff` or `/codrag-enrich` mentions file claims as a consideration
5. **No new stores:** All features built on existing ObservationStore, GraphSnapshotStore, and PushEngine
6. **Test coverage:** 18+ tests covering all new paths

---

## 9. Relationship to Paperclip-First Direction

Every feature in this design follows the Paperclip-first principle from `strategic_direction.md`:

| Feature | CoDRAG computes | Paperclip consumes |
|---|---|---|
| Consensus Scoring | "3/5 agents flagged src/auth/" | Shows in issue description, informs priority |
| Structural Complexity | "This is a heavyweight task: 2 hubs, 41 dependents, 3 modules" | Routes to appropriate agent class |
| Delta Push | "src/gateway.py is a new hub with 14 dependents" | Creates trackable issue |
| Claims in Prompts | "src/auth/ is claimed by researcher" | Agent sees claim before starting work |

CoDRAG provides structural intelligence. Paperclip acts on it. No parallel systems.

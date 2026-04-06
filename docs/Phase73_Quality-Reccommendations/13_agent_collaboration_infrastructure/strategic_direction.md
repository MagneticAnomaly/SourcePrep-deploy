# Agent Collaboration Infrastructure — Strategic Direction

> Date: 2026-04-06 | Reframing collaboration as Paperclip-first structural intelligence

---

## 1. The Reframe

The initial implementation built collaboration infrastructure as a standalone system inside CoDRAG — its own activity feed, its own conflict resource, its own coordination primitives. After review, we identified a clearer product direction:

**CoDRAG should provide structural intelligence that enriches Paperclip's existing coordination, not build a parallel PM system.**

Paperclip already manages agents, tracks activity, routes tasks, and maintains an audit trail. CoDRAG should not duplicate these capabilities. Instead, CoDRAG should tell Paperclip things only CoDRAG can know — what changed in the dependency graph, which files are structurally connected, where agents are about to collide — and let Paperclip act on that intelligence through its own UI, workflows, and agent orchestration.

**CoDRAG's role:** "I know things about the code graph that no PM tool can know. I'll push those signals to Paperclip."

**Paperclip's role:** "I manage agents, tasks, and workflows. CoDRAG gives me signals I can't compute myself."

For non-Paperclip MCP clients (Claude Code, Cursor, Gemini CLI), CoDRAG still serves collaboration data directly via MCP resources — but these are secondary to the Paperclip integration.

---

## 2. What's Already Built (Phase 73.5 Implementation)

The current implementation (17 commits, 74 tests) includes:

**Foundation (keep as-is):**
- `created_by` + `visibility` columns on observation store
- `get_by_agent()` and `get_all_attributed()` query methods
- `CoDRAGDataAccess` and `AgentCore` passthrough for `created_by`
- Pi agent attribution (`scenario=` on all 9 `_save_observation` calls)
- CollaborationHub facade + singleton initialization

**Stores (keep, extend with push):**
- `ActivityStore` — append-only agent action log (all 7 Pi scenarios + Researcher + Custodian log activity)
- `ClaimStore` — soft file claims with TTL (Researcher creates, Custodian checks)
- `GraphSnapshotStore` — hub + module snapshot capture + structural delta computation
- `ConflictStore` + `ConflictDetector` — observation-level conflict detection

**MCP layer (revise per this doc):**
- 5 MCP resources (some to be removed or rethought)
- 3 MCP prompts (some to be rethought)
- FastAPI collaboration routes (keep)
- MCP server integration points (keep, adjust)

**Agent wiring (keep):**
- Pi: snapshot capture after Watchdog, activity logging on all scenarios
- Researcher: claim creation on research_topic
- Custodian: claim checking before discovery
- PushEngine: conflict detection on push

---

## 3. What Changes

### 3.1 Remove: `codrag://activity` MCP Resource

**Why:** Paperclip has a richer activity/audit trail. Our activity feed is a simpler, weaker version of what Paperclip already shows. Exposing it as an MCP resource invites comparison where we lose.

**What stays:** `ActivityStore` itself stays as internal infrastructure. It's useful for diagnostics, for seeding Paperclip push payloads, and for the delta resource to reference. It just doesn't need to be an MCP resource.

**Impact:** Remove from `get_collaboration_resources()`, remove from `parse_collaboration_uri()`, remove `format_activity_resource()` from MCP content generators. Remove from the MCP prompts that reference `@codrag://activity`. Keep the FastAPI endpoint for internal use and Paperclip plugin consumption.

### 3.2 Remove: `codrag://conflicts` MCP Resource

**Why:** Conflicts should flow to Paperclip as issues, not sit in a separate CoDRAG resource. When CoDRAG detects that the Researcher and Custodian disagree about `src/auth.py`, that should become a Paperclip issue tagged `codrag:conflict` with both assessments in the description — visible in the same issue tracker where all other work lives.

**What stays:** `ConflictStore` stays (need persistent record). `ConflictDetector` stays. The change is in how detected conflicts are surfaced: pushed to Paperclip via `PaperclipAdapter`, not served as an MCP resource.

**New behavior:** After `ConflictDetector.detect_from_observations()` finds conflicts, call `PaperclipAdapter` to create a conflict issue:
```
Title: "CoDRAG Conflict: src/auth.py — Researcher vs Custodian"
Description: |
  Two agents disagree about this file:
  
  **Researcher:** "Important JWT pattern — consolidate into shared validator"
  **Custodian:** "No imports found — safe to delete"
  
  <!-- codrag-address:codrag://project_id/CONFLICT-abc123 -->
  <!-- codrag-conflict:true -->
```
Paperclip users see this in their normal issue list. They can assign it, comment, resolve.

**For non-Paperclip MCP clients:** Conflicts still appear as a note in the `codrag://memory/{role}` resource when an agent's observations overlap with another's. Not as a dedicated resource.

### 3.3 Rethink: `codrag-triage` Prompt → `codrag-enrich`

**Why:** Triage (clustering findings, assigning to agents) is Paperclip's job. CoDRAG shouldn't decide who works on what — it should provide the structural evidence that helps Paperclip make better decisions.

**New prompt: `codrag-enrich`**

Arguments: `finding_ids` (optional), `scope` (optional)

Returns a structural enrichment of findings rather than a triage:
```
Enrich the current findings with structural intelligence from CoDRAG.

1. Call `codrag_audit` to get current findings.
2. For the top findings, call `codrag_impact` to assess blast radius.
3. Identify which findings touch hub files (high-impact) vs leaf files (low-impact).
4. Note which findings span multiple modules (cross-cutting) vs are contained to one.
5. Summarize: for each finding, report scope size, hub involvement, and
   whether multiple agents have flagged the same area.
```

This gives Paperclip the *inputs* for triage (blast radius, hub involvement, cross-module flag) without doing the triage itself.

### 3.4 Extend: Push Collaboration Data to Paperclip

Currently CoDRAG pushes audit findings to Paperclip via the PushEngine. The collaboration extension pushes three additional data types:

**A. Push Conflicts as Issues**

When: After `ConflictDetector` finds new conflicts (during PushEngine.push() or on-demand).

How: Use existing `PaperclipAdapter.create_issue()` with a conflict-tagged description. Deduplicate via `codrag-address` in description (existing pattern).

**B. Push Structural Delta Summaries**

When: After Pi Watchdog captures a snapshot and a significant delta is detected (new hubs, removed modules, etc.).

How: Create or update a Paperclip issue in a "Structural Changes" project. Each significant delta gets an issue:
```
Title: "Structural Change: src/gateway.py is a new hub (14 dependents)"
Description: |
  New hub file detected after pipeline rebuild.
  
  Dependents count: 14
  Rank: #2 (new entry)
  
  This file has become a central dependency. Changes to it will affect
  many other files. Consider reviewing the dependency chain.
  
  <!-- codrag-address:codrag://project_id/DELTA-abc123 -->
```

Only push "significant" deltas — new/removed hubs, new/removed modules, rank changes >2. Don't push noise.

**C. Push Claims as Agent Metadata**

When: After an agent creates a claim.

How: Rather than creating issues, update the agent's metadata in Paperclip with current claims:
```
PATCH /api/agents/{agent_id}
{
  "adapterConfig": {
    "codrag_claims": [
      {"path": "src/auth/login.py", "reason": "Researching: auth consolidation", "expires_at": ...}
    ]
  }
}
```

Paperclip's routing logic can read `codrag_claims` before assigning a task that touches the same files. This is a signal, not a hard block.

### 3.5 Extend: Paperclip Plugin Data Providers

The existing plugin has 2 data providers (`codebase-health`, `agent-knowledge-scope`). Add 2 more:

**`structural-delta` data provider:**
Calls `GET /projects/{pid}/collaboration/delta` on the daemon. Returns the latest structural changes for display in a Paperclip dashboard widget or agent context panel.

**`agent-claims` data provider:**
Calls `GET /projects/{pid}/collaboration/claims` on the daemon. Returns active claims for display in the agent detail tab. Paperclip UI can show "This agent has claimed: src/auth/ (reason: researching auth consolidation, expires in 18h)."

### 3.6 Keep: MCP Resources for Non-Paperclip Clients

Three MCP resources stay for Claude Code / Cursor / Windsurf / Gemini users who don't have Paperclip:

| Resource | Why Keep |
|---|---|
| `codrag://memory/{role}` | Session continuity — agent starts with prior observations pre-loaded. No Paperclip equivalent for non-Paperclip agents. |
| `codrag://agents/{role}/findings` | Cross-agent visibility for non-Paperclip sessions. A developer using Claude Code can see what CoDRAG's Researcher found. |
| `codrag://delta` | Structural changes — only CoDRAG can provide this. Useful for any MCP client. |

### 3.7 Keep: MCP Prompts (Revised)

| Prompt | Status | Reasoning |
|---|---|---|
| `codrag-handoff` | **Keep** | Packages structural context (memory + delta + findings) that Paperclip can't assemble. Works for both Paperclip handoffs and non-Paperclip agent transitions. |
| `codrag-scope` | **Keep** | Structural scoping is CoDRAG-native — shows which modules an agent owns, what changed in those modules, what observations exist. |
| `codrag-triage` | **Replace with `codrag-enrich`** | CoDRAG provides structural enrichment (blast radius, hub involvement, cross-module analysis), Paperclip does the actual triage. |

Update prompts to remove `@codrag://activity` references (removed resource) and `@codrag://conflicts` references (pushed to Paperclip instead).

---

## 4. Remaining Unresolved Work

### 4.1 Conflict Push to Paperclip (New)

**Problem:** Conflicts are currently stored in SQLite and served as an MCP resource. They need to flow to Paperclip as issues instead.

**Solution:** Add a `push_conflict()` method to `PaperclipClient` (or extend PushEngine). When `ConflictDetector` finds conflicts:

1. For each `AgentConflict`, check if a Paperclip issue with the same `codrag-address` already exists (dedup).
2. If not, create a new issue in a "CoDRAG Conflicts" project with both agents' assessments.
3. If yes, update the description (assessments may have changed).
4. When a conflict is resolved (via Paperclip or API), mark it resolved in `ConflictStore` too.

**Integration point:** In `PushEngine.push()`, after the existing conflict detection block, add the push-to-Paperclip step (only if `PaperclipAdapter` is available).

**Effort:** Small — uses existing `PaperclipAdapter.create_issue()` and dedup pattern.

### 4.2 Delta Push to Paperclip (New)

**Problem:** Structural deltas are captured in snapshots but only served as an MCP resource. Significant deltas should proactively alert Paperclip users.

**Solution:** After `_capture_graph_snapshot()` in Pi Watchdog, compute the delta and check significance:

```python
def _push_significant_delta(self, delta: StructuralDelta) -> None:
    """Push significant structural changes to Paperclip."""
    if delta.is_empty:
        return
    # Only push if there are new/removed hubs or modules
    significant = [c for c in delta.hub_changes if c["change"] in ("new", "removed")]
    significant += [c for c in delta.module_changes if c["change"] in ("new", "removed")]
    if not significant:
        return
    # Create Paperclip issue via adapter...
```

**Integration point:** In Pi Watchdog, after `_capture_graph_snapshot()`.

**Dependency:** Requires `PaperclipAdapter` to be available to Pi agent. Currently Pi doesn't have access to the adapter — it would need to be passed through `collab_hub` or `AgentCore`. This is a design decision: does Pi push to Paperclip directly, or does it write a "pending push" record that PushEngine picks up later?

**Recommended approach:** Pi writes the delta to a "pending delta" observation with `category="delta"` and `created_by="pi/watchdog"`. A new Pi scenario (or extension of Watchdog) periodically checks for unpushed deltas and pushes them via PushEngine if Paperclip is configured. This avoids giving Pi direct Paperclip access.

**Effort:** Medium — new Pi sub-scenario + PushEngine extension.

### 4.3 Claims Push to Paperclip (New)

**Problem:** When an agent claims files, Paperclip doesn't know. Its routing logic can't factor claims into task assignment.

**Solution:** The Paperclip plugin adds an `agent-claims` data provider that reads from the daemon's `/collaboration/claims` endpoint. Paperclip's UI shows claims on the agent detail tab. For routing, Paperclip's orchestrator can check claims before assigning tasks that touch the same files.

**Integration point:** Paperclip plugin (`packages/paperclip-plugin-codrag/`). No CoDRAG daemon changes needed — the FastAPI endpoint already exists.

**Plugin changes:**
1. Add `agent-claims` data provider to manifest + worker
2. Worker calls `GET /projects/{pid}/collaboration/claims`
3. UI slot: add claims section to the `knowledge-scope` agent detail tab

**Effort:** Small — plugin-side only, daemon API already exists.

### 4.4 MCP Resource Cleanup (Revision)

**Problem:** 5 resources currently registered. Need to remove 2, keep 3.

**Changes to `collaboration_handlers.py`:**
- Remove `activity` and `conflicts` from `get_collaboration_resources()`
- Remove `"activity"` and `"conflicts"` from `parse_collaboration_uri()`
- Keep `format_activity_resource()` and `format_conflicts_resource()` as internal functions (used by FastAPI routes or plugin data providers)

**Changes to MCP prompts:**
- `codrag-handoff`: Remove `@codrag://activity` reference, remove `@codrag://conflicts` reference. Replace with: "Check Paperclip for recent agent activity and any conflict issues."
- `codrag-scope`: Same — remove activity/conflicts resource references.
- Replace `codrag-triage` with `codrag-enrich` (new prompt text).

**Effort:** Small — string edits in `collaboration_handlers.py`.

### 4.5 `codrag-enrich` Prompt (New)

**Problem:** `codrag-triage` does Paperclip's job. Need a prompt that provides structural enrichment for triage instead.

**Solution:** Replace `codrag-triage` with `codrag-enrich`:

```python
{
    "name": "codrag-enrich",
    "description": "Enrich findings with structural intelligence — blast radius, hub involvement, cross-module analysis",
    "arguments": [
        {"name": "scope", "description": "Optional area to focus on", "required": False},
    ],
}
```

Prompt text:
```
Enrich the current findings with structural intelligence from CoDRAG.{scope_text}

1. Call `codrag_audit` to get current findings.
2. For the top findings, call `codrag_impact` to assess blast radius.
3. Identify which findings touch hub files vs leaf files.
4. Note which findings span multiple modules vs are contained to one.
5. Summarize each finding with: scope size, hub involvement, blast radius,
   and whether it overlaps with areas other agents have flagged.
```

**Effort:** Trivial — replace prompt definition in `collaboration_handlers.py`.

### 4.6 Plugin Data Providers (New)

**Problem:** Paperclip plugin doesn't expose collaboration data yet.

**Changes to plugin manifest (`manifest.ts`):**
```typescript
// Add to dataProviders array
{
  name: 'structural-delta',
  displayName: 'Structural Changes',
  description: 'Recent structural changes in the codebase graph',
},
{
  name: 'agent-claims',
  displayName: 'Agent Claims',
  description: 'Files currently claimed by agents',
},
```

**Changes to plugin worker (`worker/index.ts`):**
```typescript
// Add data provider handlers
case 'structural-delta':
  const delta = await client.request(`/projects/${pid}/collaboration/delta`);
  return { content: delta };

case 'agent-claims':
  const claims = await client.request(`/projects/${pid}/collaboration/claims`);
  return { content: claims };
```

**Effort:** Small — daemon API endpoints already exist.

### 4.7 Observation Tool `created_by` in Plugin (Enhancement)

**Problem:** The Paperclip plugin's `codrag:observe` tool doesn't pass `created_by`. When a Paperclip agent saves an observation through the plugin, it's unattributed.

**Solution:** The plugin should automatically set `created_by` based on the calling agent's role. The `ToolRunContext` in the Paperclip SDK provides the agent ID and role — use it:

```typescript
case 'observe':
  const agentRole = ctx.agent?.role ?? ctx.agent?.name ?? 'paperclip-agent';
  await client.request(`/projects/${pid}/observations`, {
    method: 'POST',
    body: {
      content: params.content,
      file_path: params.file_path,
      category: params.category ?? 'note',
      created_by: agentRole,
    },
  });
```

**Effort:** Trivial — one-line addition to plugin worker.

---

## 5. Implementation Priority

| Priority | Item | Effort | Why |
|---|---|---|---|
| **P1** | 4.4 MCP resource cleanup | Small | Remove confusing duplicates, clean signal |
| **P1** | 4.5 `codrag-enrich` prompt | Trivial | Replace mispositioned triage prompt |
| **P1** | 4.7 Plugin `created_by` | Trivial | Observations from Paperclip agents should be attributed |
| **P2** | 4.6 Plugin data providers | Small | Expose delta + claims in Paperclip UI |
| **P2** | 4.1 Conflict push | Small | Conflicts should be Paperclip issues, not CoDRAG resources |
| **P3** | 4.3 Claims push (UI only) | Small | Paperclip can display claims, no daemon changes |
| **P3** | 4.2 Delta push | Medium | Proactive alerting for structural changes |

P1 items are pure revisions to existing code — no new features, just repositioning. P2 items extend the Paperclip integration. P3 items are enhancements that can wait for user feedback.

---

## 6. What Non-Paperclip MCP Clients Get

For a developer using Claude Code directly (no Paperclip):

- **`@codrag://memory/{role}`** — See what CoDRAG's internal agents found. "What did the Researcher discover about auth?"
- **`@codrag://agents/{role}/findings`** — Cross-agent findings. "What did the Custodian flag for deletion?"
- **`@codrag://delta`** — "What changed structurally in the last week?"
- **`/codrag-handoff`** — "I'm picking up from where the Researcher left off"
- **`/codrag-scope`** — "What does the backend_engineer role own?"
- **`/codrag-enrich`** — "Enrich these audit findings with structural analysis"
- **`codrag_observe` with `created_by`** — Save observations with attribution so future sessions can filter by role

These are useful standalone capabilities that don't require Paperclip. But they're secondary to the Paperclip integration — if you have Paperclip, you get richer coordination through its UI and orchestration.

---

## 7. Summary: CoDRAG's Collaboration Value Proposition

CoDRAG provides three things Paperclip cannot compute:

1. **Structural delta** — what changed in the dependency graph, not just what files changed
2. **File-level claims with structural awareness** — coordination at the code level, not the task level
3. **Pre-push conflict detection** — catch agent disagreements before they become separate Paperclip issues

Everything else (activity tracking, task routing, agent management, audit trail) belongs in Paperclip. CoDRAG enriches Paperclip's coordination with structural intelligence. It doesn't replace it.

The Paperclip plugin is the primary integration surface. MCP resources serve non-Paperclip clients as a secondary path. The collaboration stores (`ActivityStore`, `ClaimStore`, `GraphSnapshotStore`, `ConflictStore`) are internal infrastructure that feeds both paths.

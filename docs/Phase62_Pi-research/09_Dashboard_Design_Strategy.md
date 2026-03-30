# Phase 62 — Dashboard & Backend Design Strategy

> **Research Document 9 of 9** | Phase 62: What the Dashboard Should Become
> Date: 2026-03-30

---

## 1. The Problem Statement

CoDRAG has two categories of dashboard panels pulling in opposite directions:

**Intelligence panels** (Layer 1 — what CoDRAG IS):
- HealthScannerPanel, AuditPanel, SpaghettiFinderPanel
- AtlasStatusCard, GraphStructurePanel, TraceExplorer
- SearchPanel, ContextOptionsPanel

**Project management panels** (Layer 3-4 — what CoDRAG ISN'T):
- GoalpostsPanel (proposals, approve/dismiss, generate plans)
- AdvisorPanel (same data as Goalposts, different view)
- RoadmapPanel (tiered timeline, state machine)

**The question:** If we sunset the PM features, what replaces them? What does the dashboard become?

---

## 2. Answering the Paperclip Question First

> *"Does Paperclip run the Pi agents so we don't need to configure that? We just build the adapter?"*

**Yes, exactly.** This is the simplest part:

```
Paperclip handles:
  ✅ Spawning Pi processes (via the adapter)
  ✅ Scheduling heartbeats (waking Pi up)
  ✅ Assigning tasks to specific agents
  ✅ Budget tracking per agent
  ✅ Concurrency limits
  ✅ Org chart (who reports to whom)
  ✅ Audit trails

CoDRAG handles:
  ✅ Generating opportunities/findings (ActionItems)
  ✅ Providing codebase context to any agent that asks
  ✅ Exporting findings in consumable formats

The adapter handles:
  ✅ Translating Paperclip's "do this task" → Pi's "pi --print" invocation
  ✅ Pre-fetching CoDRAG context and injecting into Pi's prompt
  ✅ Parsing Pi's output back into Paperclip's expected format
  ✅ Creating git branches + PRs (safety gate)
```

**CoDRAG doesn't need to know Paperclip exists.** CoDRAG just exposes its intelligence via MCP, CLI, and HTTP API. The adapter is a separate project that bridges Paperclip → Pi → CoDRAG.

---

## 3. The Dashboard Design: "Opportunity Console"

### 3.1 Design Principle

> CoDRAG's dashboard should show users what it *knows*, not what it thinks they should *do*.

**Old metaphor:** Project management board (plan, track, execute)
**New metaphor:** Intelligence console (discover, inspect, export)

### 3.2 The AI Gateway: Adding a Pi Slot

Your instinct is right. The existing `LLMStatusWidget` in the "AI Gateway" panel shows model cards for 4 slots (embedding, small/fast, large/thinking, code). We add a 5th:

```
Current AI Gateway Layout:
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Embedding  │ │  Fast Model │ │  Thinking   │ │  Code Model │
│  nomic-     │ │  kimi-2.5   │ │  kimi-2.5   │ │  qwen2.5-   │
│  embed-code │ │  k1:cloud   │ │  k1:cloud   │ │  coder      │
│  ● Ready    │ │  ● Ready    │ │  ● Ready    │ │  ○ Not Used │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘

Proposed AI Gateway Layout (with Agent Model):
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Embedding  │ │  Fast Model │ │  Thinking   │ │  Code Model │ │  Agent Model│
│  nomic-     │ │  kimi-2.5   │ │  kimi-2.5   │ │  qwen2.5-   │ │  claude-    │
│  embed-code │ │  k1:cloud   │ │  k1:cloud   │ │  coder      │ │  sonnet-4.5 │
│  ● Ready    │ │  ● Ready    │ │  ● Ready    │ │  ○ Not Used │ │  ○ Optional │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

**The "Agent Model" card is where Pi gets its model.** It uses the existing endpoint selection UI. When CoDRAG runs opportunities through an agent (via Pi or direct LLM call), it uses this model.

But wait — is this even a CoDRAG concern? Let's think carefully:

### 3.3 Should CoDRAG Configure Pi's Model?

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: CoDRAG configures agent model** | 5th slot in AI Gateway, CoDRAG passes model to Pi | Single pane of glass, consistent UX | CoDRAG shouldn't own agent config |
| **B: Paperclip configures Pi's model** | Pi model set in Paperclip org chart per agent | Proper separation of concerns | Users need two UIs |
| **C: Hybrid — CoDRAG suggests, external tool configures** | CoDRAG shows "recommended agent model" but doesn't control it | Clean architecture, helpful UX | Slightly disconnected |

**Recommendation: Option C (Hybrid)**

CoDRAG doesn't run Pi — Paperclip does. But CoDRAG can show a "recommended model" for agent work. In practice, the 5th slot could serve a different purpose...

### 3.4 Reframing the 5th Slot: The "Opportunity" Model

Instead of "Agent Model for Pi," the 5th slot could be:

> **"Advisor Model"** — The model CoDRAG uses for its OWN opportunity analysis (the `codrag_audit action="advise"` pipeline)

This already exists conceptually (the advisor/goalposts planner uses the "large model"). Making it an explicit, named slot makes the AI Gateway's purpose clearer:

```
Slot 1: Embedding        → Indexing & search
Slot 2: Fast Model       → Quick analysis (augmentation, fast sync)
Slot 3: Thinking Model   → Deep reasoning (epistemic, modules, atlas)
Slot 4: Code Model       → Code-aware tasks (inferred edges)
Slot 5: Advisor Model    → Opportunity discovery & proposals    ← NEW
```

**This is much cleaner than "agent model."** CoDRAG owns the advisor pipeline. The advisor model generates the opportunities. External tools (Pi, Claude Code) consume them.

---

## 4. What Replaces Goalposts/Advisor/Roadmap Panels

### 4.1 Current State: Three Overlapping Panels

```
GoalpostsPanel:
  • Product intent text field
  • Generate Proposals button
  • List of proposals with approve/dismiss
  • Design questions with answer input
  • State: generating, ready, error

AdvisorPanel:
  • Same data as GoalpostsPanel (different layout)
  • Emphasizes the "copy for AI" workflow

RoadmapPanel:
  • Tiered timeline view (9 zones)
  • Drag-and-drop reorder
  • North star management
```

### 4.2 New Design: Single "Opportunities" Panel

Replace all three with ONE panel that embodies the "knowledge provider" philosophy:

```
┌──────────────────────────────────────────────────────────────────────┐
│  ★ Opportunities                                     [↻ Refresh]    │
│  ───────────────────────────────────────────────────────────────     │
│                                                                      │
│  Product Intent: [Your product is a codebase intelligence engine___]│
│                                                 [Save] when edited  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  Summary Bar                                                      ││
│  │  23 opportunities │ 3 critical │ 8 warnings │ 12 info            ││
│  │  Last refreshed: 2 hours ago │ Model: kimi-2.5 k1:cloud          ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  Filter: [All ▾] [Architecture ▾] [Security ▾] [P0-P3 ▾]           │
│                                                                      │
│  ┌─ 🔴 P0 ──────────────────────────────────────────────────────────┐│
│  │ Circular dependency in auth module                 HEALTH-a7b9   ││
│  │ 3 files │ architecture │ effort: medium                          ││
│  │ ┌─────────┐ ┌───────────┐ ┌──────────────┐ ┌──────────┐        ││
│  │ │Copy ✨  │ │Export JSON│ │Copy MCP cmd  │ │Dismiss ✕ │        ││
│  │ └─────────┘ └───────────┘ └──────────────┘ └──────────┘        ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ┌─ 🟡 P1 ──────────────────────────────────────────────────────────┐│
│  │ Missing error handling in API routes               ADV-c3d4     ││
│  │ 7 files │ quality │ effort: small                                ││
│  │ [Copy ✨] [Export JSON] [Copy MCP cmd] [Dismiss ✕]              ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ┌─ 🔵 P2 ──────────────────────────────────────────────────────────┐│
│  │ Add TypeScript strict mode to dashboard             ADV-e5f6     ││
│  │ 14 files │ tech_debt │ effort: large                             ││
│  │ [Copy ✨] [Export JSON] [Copy MCP cmd] [Dismiss ✕]              ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ─── Export All ────────────────────────────────────────────────     │
│  [JSON] [CSV] [SARIF] [Markdown] [Copy All for AI]                  │
│                                                                      │
│  ─── Questions from AI ─────────────────────────────────────        │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ 💬 "Should the auth module use JWT or session-based auth?"       ││
│  │ [Type your answer...________________________________] [Submit]   ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 What Each Button Does

| Button | Action | For whom |
|---|---|---|
| **Copy ✨** | Copies a well-formatted prompt including the opportunity description, affected files, sub-tasks, and CoDRAG context command. Ready to paste into Claude Code, Cursor, Antigravity, or Pi. | All users |
| **Export JSON** | Downloads the ActionItem as structured JSON (Paperclip API-compatible). | Automation users |
| **Copy MCP cmd** | Copies `codrag_audit action="refactor" finding_ids=["HEALTH-a7b9"]` — the exact command to have Claude Code focus on this item. | MCP users |
| **Dismiss ✕** | Marks as "not relevant" — hidden from view, excluded from future exports. | All users |
| **Export All** | Bulk export in various formats (JSON, CSV, SARIF, Markdown). | Automation, PM tools |
| **Copy All for AI** | Generates a single paste-ready prompt with all undismissed opportunities. | Power users |

### 4.4 What's Intentionally Missing

| Feature | Why it's absent |
|---|---|
| Approve/Start buttons | CoDRAG doesn't manage execution — the agent does |
| Tier/priority reordering | PM tool territory (Paperclip, Linear, Jira handle ordering) |
| State machine (proposed→active→complete) | CoDRAG tracks only proposed/dismissed |
| Timeline visualization | PM tool visualization (Paperclip dashboard shows this) |
| Assignee management | Paperclip org chart handles this |
| Sprint/iteration grouping | PM tool feature |

### 4.5 The "Under The Hood" Option

For users who want even less UI:

> CoDRAG could run the advisor pipeline automatically in the background (like it already does with the health scanner) and just update the AGENTS.md file with current findings. No dashboard panel needed.

This is the **minimal UI** approach: CoDRAG's intelligence runs silently, and the AGENTS.md file IS the interface. Any agent that opens the project automatically sees the current opportunities.

We should support **both modes**:
1. **Dashboard mode** — Opportunities panel for users who want to review/export
2. **Headless mode** — Auto-refresh AGENTS.md for users who just want their agent to see findings

---

## 5. Backend Design

### 5.1 What Already Exists

The backend has all the pieces:

```python
# Already built:
ActionItem model           # action_item.py — unified output schema
Health Scanner             # audit/runner.py — code health findings
Spaghetti Scorer          # finds refactoring urgency
Advisor/Goalposts Planner # generates LLM-based proposals
codrag_audit MCP tool     # exposes findings via MCP
Product Intent            # anchors analysis to user goals
```

### 5.2 What Needs To Change

#### A. Unify All Output into ActionItems

Currently, Health Scanner and Advisor generate different objects that get *converted* to ActionItems. Instead, generate ActionItems directly:

```python
# Before: converter pattern
finding = audit_runner.scan()           # → Finding object
action_item = finding_to_action_item(finding)  # → ActionItem

# After: native ActionItem output
action_items = audit_runner.scan()      # → List[ActionItem] directly
```

This simplifies the pipeline and removes converter maintenance.

#### B. Add Export Formats to CLI and API

```python
# New CLI command:
# codrag advise --format json|csv|sarif|md [--project PROJECT_ID] [--min-priority P2]

# New API endpoint:
# GET /projects/{id}/opportunities?format=json&min_priority=P2
# GET /projects/{id}/opportunities/export?format=sarif
```

#### C. Add "Advisor Model" Slot to LLM Config

```python
# In LLMConfig:
advisor_model: ModelSlotConfig  # New 5th slot for opportunity analysis

# The advisor pipeline currently reuses large_model. Make it explicit:
# - If advisor_model is configured, use it for opportunity generation
# - If not, fall back to large_model (backward compatible)
```

#### D. Simplify State: Only Two States

```python
# Before: proposed | approved | dismissed | completed | refined
VALID_STATES = frozenset({"proposed", "approved", "dismissed", "completed"})

# After: only two states that matter
VALID_STATES = frozenset({"active", "dismissed"})
# Items start as "active" (visible)
# Users can "dismiss" (hidden from view/export)
# No "approved/completed" — that's the PM tool's job
```

#### E. Auto-Refresh Pipeline

```python
# Background task that runs when idle:
async def refresh_opportunities(project_id: str):
    """Refreshes opportunity list from all sources."""
    items: List[ActionItem] = []
    
    # 1. Health scanner findings
    items.extend(audit_runner.scan_to_action_items(project_id))
    
    # 2. Spaghetti scorer findings
    items.extend(spaghetti_runner.score_to_action_items(project_id))
    
    # 3. LLM advisor proposals (if advisor model configured)
    if advisor_model_configured(project_id):
        items.extend(await advisor.generate_action_items(project_id))
    
    # 4. TODO/FIXME scanner
    items.extend(todo_scanner.scan_to_action_items(project_id))
    
    # Deduplicate by ID (hash-based), preserve dismiss state
    merged = merge_with_existing(project_id, items)
    
    # Persist
    save_opportunities(project_id, merged)
    
    # Update AGENTS.md with summary (headless mode)
    update_agents_md_opportunities(project_id, merged)
```

---

## 6. Panel Map: What Stays, What Goes, What's New

```
CURRENT PANELS                              NEW PANELS
──────────                              ──────────
status          → KEEP (IndexStatusCard)
llm-status      → KEEP + Add "Advisor" slot
search          → KEEP
context-options → KEEP
results         → KEEP
context-output  → KEEP
file-tree       → KEEP
trace           → KEEP
trace-pipeline  → KEEP
graph-structure → KEEP
deep-analysis   → KEEP
index-health    → KEEP
health_scanner  → MERGE into Opportunities
audit/spaghetti → MERGE into Opportunities
goalposts       → REPLACE with Opportunities         ← NEW
advisor         → REPLACE with Opportunities         ← NEW
roadmap         → REMOVE (sunset)                    ← REMOVE
atlas           → KEEP
activity        → KEEP
token-budget    → KEEP
log-console     → KEEP
usage-guide     → KEEP
enterprise      → KEEP
```

### What the user sees:

**Before:** 6 analysis/PM panels (Health Scanner, Audit, Spaghetti Finder, Goalposts, Advisor, Roadmap) — confusing overlap

**After:** 1 Opportunities panel — all findings and proposals in one place, with export buttons for any external tool

---

## 7. Design Decisions Summary

| Question | Decision | Rationale |
|---|---|---|
| Add Pi model card to AI Gateway? | **Reframe as "Advisor Model"** | CoDRAG configures its own analysis model, not Pi's |
| Replace Goalposts/Advisor/Roadmap? | **Yes — single Opportunities panel** | Unified view, export-focused, no PM state machine |
| Build complex visualization? | **No** — sorted card list with filters | Simple, functional, export-centric |
| Keep Health Scanner separate? | **Merge into Opportunities** | Same ActionItem format, one place for all findings |
| Auto-refresh findings? | **Yes** — background pipeline like health scanner | Knowledge stays fresh without user intervention |
| Support headless mode? | **Yes** — auto-update AGENTS.md | Zero-UI option for agent-only workflows |
| Complexify for Paperclip integration? | **No** — just export JSON | Clean separation of concerns |
| Keep Questions/Product Intent? | **Yes** — inside Opportunities panel | Anchors analysis and enables user feedback |

---

## 8. Implementation Priority

### Phase 1: Consolidation (1-2 weeks)
1. Create Opportunities panel (replaces Goalposts + Advisor + Roadmap)
2. Merge Health Scanner findings into Opportunities view
3. Add "Copy for AI" button with well-formatted prompt
4. Add "Export JSON" per-item and bulk
5. Simplify state to active/dismissed

### Phase 2: Export Formats (3-5 days)
6. `codrag advise --format json|csv|sarif|md` CLI
7. `GET /projects/{id}/opportunities?format=...` API endpoint
8. SARIF export for GitHub Code Scanning

### Phase 3: Advisor Model (2-3 days)
9. Add 5th model slot to LLMConfig ("Advisor Model")
10. Update AI Gateway UI to show the slot
11. Wire advisor pipeline to use the new slot

### Phase 4: Headless Mode (2-3 days)
12. Auto-refresh pipeline (background, when idle)
13. Auto-update AGENTS.md with opportunity summary
14. Configuration toggle in settings (auto-refresh: on/off)

---

*This document should be read alongside [07_Strategic_Pivot.md](./07_Strategic_Pivot.md) and [08_Dual_Agent_Architecture.md](./08_Dual_Agent_Architecture.md).*

# Phase 59: Refined Architecture — Two Features, Clean Slate

> Synthesizes the R&D Plan, second-opinion analysis, user clarifications, and GitHub integration research into a definitive build plan.

---

## The Product: 2 Dashboard Features

After consolidation, CoDRAG's analysis tools resolve to exactly **2 features**:

```
┌──────────────────────────────────────────────────────────────────┐
│                    CoDRAG Dashboard                              │
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐  │
│  │  Health Scanner 🩺  │    │  Roadmap (Goalposts) 🗺️         │  │
│  │                     │    │                                 │  │
│  │  "What's wrong?"    │    │  "Where are we going?"          │  │
│  │                     │    │                                 │  │
│  │  Tab 1: Findings    │───►│  Interactive D3 vertical        │  │
│  │  Tab 2: Files       │    │  timeline with goalpost nodes   │  │
│  │                     │    │                                 │  │
│  │  Copy for AI ✓      │    │  Past ▲ Active ★ Future ▼       │  │
│  └─────────────────────┘    └─────────────────────────────────┘  │
│                                                                  │
│  Removed: AuditPanel, SpaghettiFinderPanel, GoalpostsPanel,      │
│           AdvisorPanel (all merged into the above two)           │
└──────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **The old GoalpostsPanel is erased.** The new Roadmap IS the goalposts — actual points on a visual timeline that the AI uses to focus its proposals. The AdvisorPanel's LLM generation becomes the intelligence engine feeding the Roadmap, not a separate panel.

---

## What Gets Retired vs Kept vs Built

| Component | Status | Rationale |
|-----------|--------|-----------|
| `AuditPanel.tsx` | **RETIRE** | Merged into HealthScannerPanel |
| `SpaghettiFinderPanel.tsx` | **RETIRE** | Merged into HealthScannerPanel (Files tab) |
| `GoalpostsPanel.tsx` | **RETIRE** | Replaced by RoadmapPanel |
| `AdvisorPanel.tsx` | **RETIRE** | Intelligence engine moves into Roadmap backend |
| `HealthScannerPanel.tsx` | **KEEP** | Feature 1 — unified diagnostics |
| `RoadmapPanel.tsx` | **BUILD** | Feature 2 — visual timeline with goalposts |
| `GoalpostsPlanner` | **KEEP + EVOLVE** | Backend engine for Roadmap proposals |
| `ActionItem` model | **KEEP** | Shared data model for Health Scanner |
| `GoalpostProposal` model | **EVOLVE** | Becomes `RoadmapNode` with position/tier |

---

## Feature 2: The Roadmap (Deep Design)

### The Timeline Graphic

A bottom-to-top SVG/D3 visualization resembling tree roots:

```
              ═══ COMPLETED ═══
                    │
            ┌───────┼───────┐
            │   Done Node   │ 
            └───────┼───────┘
                    │
              ══ ACTIVE ★ ══         ← viewport anchor
                    │
            ┌───────┼───────┐
            │  Current Work │
            └───────┼───────┘
                    │
              ═══ PLANNED ═══
                    │
            ┌───────┼───────┐
            │  Next Sprint  │
            └───────┼───────┘
                    │
           ┌────────┤────────┐       ← fork point
           │                 │
     ┌─────┴──────┐   ┌─────┴──────┐
     │  Option A  │   │  Option B  │  (incomplete forks)
     └────────────┘   └────────────┘
                    │
              ═══ PROPOSED ═══ // these donnt necessarily need lines connected maybe doted lines
                    │
            ┌───────┼───────┐
            │  AI Suggested │        ← from GoalpostsPlanner
            └───────┼───────┘
                    │
              (more below...)
```

### RoadmapNode Model (evolves from GoalpostProposal)

```python
@dataclass
class RoadmapNode:
    id: str                    # RM-{hash8}
    title: str
    description: str
    
    # Position on timeline
    tier: str                  # "completed" | "active" | "planned" | "proposed"
    position: int              # Order within tier (0 = top)
    
    # Source tracking
    source: str                # "manual" | "ai_proposed" | "todo_scan" | "github"
    source_ref: str | None     # File path, GitHub issue URL, etc.
    
    # Category (from GoalpostProposal)
    category: str              # architecture | product | market | security | research
    priority: str              # P0-P3
    
    # Tasks (from GoalpostProposal)
    tasks: list[RoadmapTask]   # Concrete sub-tasks with file_paths
    
    # User state
    state: str                 # proposed | accepted | dismissed | active | completed
    
    # Fork support (Phase 59C+)
    parent_id: str | None      # If this node is a fork option
    fork_label: str | None     # "Option A: Plugin Architecture"
    
    # Timestamps
    created_at: str
    decided_at: str | None
    completed_at: str | None
    
    # App Ethos link (stub — defaults blank)
    ethos_alignment: str       # Free text, defaults to ""
```

### North Star = Current Goalpost

Per the user's clarification, the "north star" is **not a separate data model**. It's simply the topmost node in the `active` tier — the current goalpost that the AI prompt uses as its anchor. The algorithm:

```python
def get_north_star(nodes: list[RoadmapNode]) -> RoadmapNode | None:
    """The north star is the highest-priority active node."""
    active = [n for n in nodes if n.tier == "active"]
    if not active:
        return None
    return min(active, key=lambda n: (PRIORITY_RANK[n.priority], n.position))
```

The GoalpostsPlanner prompt then references this:
```
# North Star (current primary goalpost)
{north_star.title}: {north_star.description}

# All active roadmap nodes
{active_nodes_summary}
```

---

## Building Blocks Audit: What We Reuse

### From Phase 57 (Goalposts)
| Component | Reuse in Roadmap |
|-----------|-----------------|
| `GoalpostsPlanner.generate()` | Core intelligence engine — feeds `proposed` tier |
| `GOALPOSTS_PROMPT` | Evolve with CoT + north star reference (from prompt research) |
| `GoalpostQuestion` | Keep as-is — questions during roadmap generation |
| `GoalpostsState.product_intent` | Becomes `app_ethos` (simple text field, defaults blank) |
| `goalposts.json` persistence | Evolve to `roadmap.json` |

### From Phase 57B (Tool Consolidation)
| Component | Reuse in Roadmap |
|-----------|-----------------|
| `ActionItem` model | Health Scanner's data model (unchanged) |
| `run_health_scan()` | Diagnostics engine (unchanged) |
| `tool_advise()` MCP | Renamed/evolved: populates Roadmap proposed tier |
| `HealthScannerPanel` | Feature 1 (unchanged) |

### From Phase 57 (Prompt Research)
| Finding | Application |
|---------|------------|
| Chain-of-Thought scaffolding | Add to `GOALPOSTS_PROMPT` for better proposals |
| Three-lens framework | Categories become: architecture, product, market |
| Business impact framing | Add `business_impact` field to `RoadmapNode` |
| Few-shot example | Include in system prompt |

---

## Background Discovery Pipeline

### Phase 59A: TODO/FIXME Scanner

A lightweight background task using existing `codrag_search` patterns:

```python
SCAN_PATTERNS = ["TODO", "FIXME", "HACK", "XXX", "OPTIMIZE"]

def scan_todos(project_root: Path) -> list[RoadmapNode]:
    """Grep codebase for annotations, create proposed roadmap nodes."""
    # Uses ripgrep (already a dependency) for speed
    # Deduplicates against existing roadmap nodes by file+line
    # Classifies: FIXME/HACK → tech_debt, TODO → feature, OPTIMIZE → architecture
```

### Phase 59B: Phase Doc Scanner (deferred)

Read `docs/Phase*/README.md` and extract milestones. Park for later.

### Phase 59D: GitHub Integration (dedicated research phase)

> [!WARNING]
> GitHub integration is essential but complex. Deserves its own research/planning phase.

---

## GitHub Integration Research Summary

### What GitHub Projects v2 Offers

| API | Capability | CoDRAG Use |
|-----|-----------|------------|
| GraphQL `ProjectV2` | Custom fields, iterations, roadmap views | Map tiers to iteration fields |
| `updateProjectV2ItemFieldValue` | Programmatic field updates | Push tier changes to GitHub |
| `project_v2_item` webhook | Real-time event notifications | Sync GitHub → CoDRAG |
| Iteration fields | Sprint periods with start/end dates | Map "planned" tier = current sprint |
| Draft issues | Lightweight planning items | Import as "proposed" tier nodes |

### Rate Limits and Auth

| Method | Rate Limit | Best For |
|--------|-----------|----------|
| PAT (Personal Access Token) | 5,000/hr | Development, single-user |
| GitHub App (installation) | 5,000-15,000/hr | Production, multi-user |
| `GITHUB_TOKEN` (Actions) | 1,000-15,000/hr per repo | CI/CD automation |

### Recommended Integration Architecture

```
Phase 1: Read-Only Polling (Phase 59D-1)
  - Poll GitHub Issues API every 15 min
  - Import open issues as "proposed" tier nodes
  - Labels map to categories: "bug"→tech_debt, "enhancement"→feature
  - Milestones map to sprint groupings

Phase 2: Webhook-Driven Sync (Phase 59D-2)  
  - GitHub App with project_v2_item webhook
  - PR merge → auto-promote to "completed"
  - Issue close → mark roadmap node completed
  - New issue → auto-create "proposed" node

Phase 3: Bidirectional Sync (Phase 59D-3)
  - Push: accepted roadmap items → GitHub Issues
  - Push: tier changes → GitHub Projects custom fields
  - Conflict resolution: "last write wins" with audit trail
  - Bot account for automated changes (Wrike pattern)

Phase 4: Sprint Intelligence (Phase 59D-4)
  - Map CoDRAG tiers to GitHub iteration fields
  - Velocity tracking: how many nodes move per sprint
  - Burndown: active tier items vs capacity
  - AI sprint planning: "given velocity, these 4 items fit next sprint"
```

> [!TIP]
> **Webhook > Polling.** Webhooks don't consume rate limits and are real-time. Use GitHub Apps (not PATs) for production — they get higher rate limits and granular permissions.

---

## Phased Build Plan (Revised)

### Phase 59A: Data Model + Backend (1-2 weeks)
- [ ] `RoadmapNode` dataclass (evolve from GoalpostProposal)
- [ ] `RoadmapState` with persistence (`roadmap.json`)
- [ ] CRUD API endpoints (`routers/roadmap.py`)
- [ ] Migrate existing GoalpostsState → RoadmapState
- [ ] Wire `GoalpostsPlanner.generate()` to output RoadmapNodes
- [ ] TODO/FIXME scanner background task
- [ ] `codrag_audit action="roadmap"` MCP sub-action

### Phase 59B: Timeline UI (2 weeks)
- [ ] D3.js + React vertical timeline component
- [ ] 4-tier layout (completed → active → planned → proposed)
- [ ] Node cards with category badges, source indicators
- [ ] Drag-to-reorder within tiers
- [ ] Click to expand node details
- [ ] "Add Node" button for manual entries
- [ ] Dashboard panel registration replacing GoalpostsPanel
- [ ] App Ethos text field (in panel header, defaults blank)

### Phase 59C: Fork Visualization + Intelligence (2-3 weeks)
- [ ] Fork spine split when nodes share a parent_id
- [ ] Decision comparison: side-by-side fork options
- [ ] Enhanced GoalpostsPlanner prompt (CoT, three-lens, business impact)
- [ ] Auto-propose: run planner in background, surface in proposed tier
- [ ] Stale node detection (visual fade for old unactioned nodes)

### Phase 59D: GitHub Integration (dedicated future phase)
- [ ] Phase 59D-1: Read-only polling (Issues → proposed nodes)
- [ ] Phase 59D-2: Webhook-driven sync (PR merge → completed)
- [ ] Phase 59D-3: Bidirectional sync (push accepted items to GitHub)
- [ ] Phase 59D-4: Sprint intelligence (velocity, burndown, capacity)

### Phase 59E: Panel Cleanup
- [ ] Remove `GoalpostsPanel.tsx` from registry
- [ ] Remove `AdvisorPanel.tsx` from registry
- [ ] Remove `AuditPanel.tsx` from registry
- [ ] Remove `SpaghettiFinderPanel.tsx` from registry
- [ ] Update default dashboard layout: HealthScanner + Roadmap only

---

## MCP Surface (Final)

After all phases, CoDRAG has exactly **6 MCP tools**:

| Tool | Sub-actions | What it does |
|------|------------|-------------|
| `codrag` | — | Structural overview (modules, hubs, focus areas) |
| `codrag_search` | context, symbol | Code search with expansion |
| `codrag_impact` | dependents, dependencies, all | Blast radius analysis |
| `codrag_audit` | scan, refactor, verify, report, advise, **roadmap** | Health diagnostics + advisor + roadmap |
| `codrag_observe` | save, get | Cross-session memory |
| `codrag_build` | — | Trigger index build |

The `roadmap` sub-action:
```
codrag_audit action="roadmap"              → Get current roadmap state
codrag_audit action="roadmap" tier="active" → Get active tier nodes
codrag_audit action="advise"               → Generate new proposals into roadmap
```

# Phase 59: Roadmap Feature — R&D Plan

> A visual, AI-assisted roadmap system that transforms scattered goalposts, TODOs, and design proposals into a living, scrollable timeline of past accomplishments and future opportunities.

---

## 1. Core Concept

### The Problem
CoDRAG's Advisor generates proposals, but they exist as a flat list — no sense of sequence, no "north star" direction, no visual journey from "where we were" to "where we're going." Users need a way to:
- Set **destination goals** (north stars) that anchor the AI's proposals
- See a **visual timeline** of completed → active → planned → proposed work
- **Discover roadmap items automatically** from the codebase (TODOs, FIXMEs, phase docs)
- **Accept or reject** AI-proposed items onto their roadmap

### The Metaphor: Goalposts on a Field
A vertical timeline where items rise from the bottom (future/speculative) toward the top (completed/historical). The "goalposts" are user-set destination markers that the AI uses to focus its proposals. Without goalposts, the AI wanders; with them, every proposal serves a clear direction.

---

## 2. Timeline Tier Model (9 Zones)

Items flow upward through these tiers as they progress:

```
┌─────────────────────────────────────┐
│  ▲ HIDDEN TOP (scrolled past)       │  Archived completed items
├─────────────────────────────────────┤
│  9. PROPOSED                        │  AI-suggested, not yet reviewed
├─────────────────────────────────────┤
│  8. PROPOSED + ACCEPTED             │  User reviewed, added to roadmap
├─────────────────────────────────────┤
│  7. MANUALLY ADDED                  │  User-created roadmap items
├─────────────────────────────────────┤
│  6. PLANNED / STILL PLANNING        │  Design phase, not yet started
├─────────────────────────────────────┤
│  5. PLANNED / BEGINNING WORK        │  About to start implementation
├─────────────────────────────────────┤
│  4. CURRENT / ACTIVE                │  ★ Viewport anchor ★
├─────────────────────────────────────┤
│  3. NEARING COMPLETE / WAITING      │  Done but blocked or in review
├─────────────────────────────────────┤
│  2. COMPLETE / STUBS                │  Finished (may have follow-ups)
├─────────────────────────────────────┤
│  1. HIDDEN BOTTOM (scrolled past)   │  Old completed items
└─────────────────────────────────────┘
```

The viewport naturally sits at tier 4 (CURRENT/ACTIVE), with the user scrolling up to see history or down to see future plans.

---

## 3. Architecture Overview

### 3.1 Data Model: `RoadmapItem`

Extends the existing `GoalpostProposal` pattern:

```python
@dataclass
class RoadmapItem:
    id: str                           # RM-{hash8}
    title: str
    description: str
    tier: int                         # 1-9 (maps to timeline position)
    source: str                       # "ai_proposed" | "manual" | "todo_scan" | "github"
    category: str                     # architecture | product | market | security | research
    priority: str                     # P0-P3
    
    # Goalpost link
    goalpost_id: str | None           # Links to a north-star goalpost
    
    # Discovery metadata
    discovered_at: str                # ISO timestamp
    discovered_from: str | None       # file path / GitHub issue URL / scan source
    
    # Scoring (from background analysis)
    relevance: float                  # 0.0-1.0 how relevant to current goals
    staleness: float                  # 0.0-1.0 how outdated (time + code changes)
    excitement: float                 # 0.0-1.0 novelty / innovation score
    impact: float                     # 0.0-1.0 estimated business impact
    
    # User decisions
    state: str                        # proposed | accepted | active | completed | dismissed
    decided_at: str | None
    
    # Fork support (future)
    parent_id: str | None             # For branching roadmap paths
    fork_label: str | None            # "Option A: Plugin arch" / "Option B: Monolith"
```

### 3.2 North Star Goalposts

```python
@dataclass
class NorthStar:
    id: str                           # NS-{hash8}
    title: str                        # "Ship v2.0 with plugin system"
    description: str
    target_date: str | None           # Optional target date
    priority: int                     # 1 = primary, 2-10 = secondary
    active: bool                      # Whether AI should use this as anchor
    
    # Metrics
    linked_items: int                 # How many roadmap items serve this star
    completion_pct: float             # Derived from linked items' progress
```

### 3.3 Background Discovery Pipeline

A new background service that runs periodically:

```
┌──────────────────────────────────────────────────────┐
│                  Discovery Pipeline                   │
│                                                      │
│  1. TODO Scanner                                     │
│     grep for TODO/FIXME/HACK/XXX → RoadmapItem       │
│     (source="todo_scan")                             │
│                                                      │
│  2. Phase Doc Scanner                                │
│     Read docs/Phase*/README.md → RoadmapItem          │
│     (source="phase_doc")                             │
│                                                      │
│  3. GitHub Issue Sync (future)                        │
│     GitHub API → RoadmapItem (source="github")        │
│                                                      │
│  4. Advisor Proposals                                │
│     From codrag_audit action="advise" → RoadmapItem   │
│     (source="ai_proposed")                           │
│                                                      │
│  5. Relevance Scorer                                 │
│     Score each item against NorthStars                │
│     Update: relevance, staleness, excitement, impact  │
└──────────────────────────────────────────────────────┘
```

---

## 4. Visual Design: Vertical Timeline

### D3.js SVG Component

- **Orientation**: Bottom-to-top (future at bottom, past at top)
- **Center spine**: Vertical line with tier markers
- **Item cards**: Branch left/right alternating from the spine
- **Fork visualization**: Spine splits into 2 paths for unresolved design forks
- **Viewport**: Auto-scrolls to CURRENT/ACTIVE tier
- **Interactions**: Click to expand, drag to reorder within tier, zoom/pan

### Mockup Structure

```
                ┌──────────────┐
     ┌──────────┤  Completed   │
     │          └──────────────┘
     │    
─────●────────────────────────── Tier 2: Complete
     │    
     │          ┌──────────────┐
     ├──────────┤  PR Merged   │
     │          └──────────────┘
     │    
═════★══════════════════════════ Tier 4: ACTIVE (highlighted)
     │    
     │          ┌──────────────┐
     ├──────────┤  In Progress │
     │          └──────────────┘
     │    
─────●────────────────────────── Tier 6: Planned
     │    
     │          ┌──────────────┐
     ├──────────┤  Planned     │
     │          └──────────────┘
     │    
     │    ┌─── Fork A ──────────┐
     ├────┤    Option: Plugin   │
     │    └─────────────────────┘
     │    ┌─── Fork B ──────────┐
     └────┤    Option: Monolith │
          └─────────────────────┘
```

---

## 5. GitHub Integration Research

### What's Available Now
| API | What it provides | How CoDRAG uses it |
|-----|------------------|--------------------|
| GitHub Projects v2 (GraphQL) | Custom fields, iterations, roadmap views | Sync items bidirectionally |
| GitHub Issues API | Labels, milestones, assignees | Import issues as roadmap items |
| GitHub Actions | CI/CD hooks | Trigger roadmap updates on merge |
| VS Code Extension API | Workspace state, tasks | Surface roadmap in editor |

### Integration Phases
1. **Read-only sync**: Import GitHub issues/PRs as roadmap items (source="github")
2. **Write-back**: Push accepted roadmap items to GitHub Projects
3. **Sprint mapping**: Map CoDRAG tiers to GitHub iteration fields
4. **VS Code widget**: Show current roadmap tier in editor status bar

---

## 6. "App Ethos" Concept (Stub)

> [!NOTE]
> This is a future product improvement — stub it now, build later.

An `AppEthos` document that describes:
- What the product is (from Atlas)
- Who it's for (user personas)
- Core values (speed? reliability? developer experience?)
- Non-goals (what we explicitly won't do)

The Relevance Scorer uses AppEthos to score `impact` — "does this roadmap item align with who we are?"

---

## 7. Phased Build Plan

### Phase 59A: Foundation (this sprint)
- [ ] `RoadmapItem` and `NorthStar` data models
- [ ] `RoadmapState` with persistence (JSON, same pattern as GoalpostsState)
- [ ] Basic API endpoints (CRUD for items + north stars)
- [ ] TODO/FIXME scanner (background task, grep-based)
- [ ] Wire into existing `codrag_audit action="advise"` output

### Phase 59B: Timeline UI
- [ ] D3.js vertical timeline component (`RoadmapTimeline.tsx`)
- [ ] 9-tier layout with center spine and branching cards
- [ ] Item cards with tier badges, source indicators, and score bars
- [ ] Drag-to-reorder within tiers
- [ ] Dashboard panel registration (`RoadmapPanel`)

### Phase 59C: Scoring and Intelligence
- [ ] Relevance scorer (items vs north stars)
- [ ] Staleness detector (time since creation + code changes in related files)
- [ ] Excitement heuristic (novelty based on category distribution)
- [ ] Impact estimator (using AppEthos stub)
- [ ] Background refresh pipeline

### Phase 59D: GitHub Integration
- [ ] GitHub Issues import (read-only)
- [ ] GitHub Projects v2 sync
- [ ] Sprint/iteration mapping
- [ ] PR merge → tier promotion automation

### Phase 59E: Forking and Advanced Viz
- [ ] Fork visualization (split spine)
- [ ] Decision points (compare fork options)
- [ ] Historical playback (animate timeline changes over time)
- [ ] VS Code roadmap widget

---

## 8. MCP Surface

No new MCP tools — extend existing ones:

| Tool | Action | What it does |
|------|--------|-------------|
| `codrag_audit` | `action="advise"` | Now also tags proposals with `roadmap_tier` |
| `codrag_audit` | `action="roadmap"` | New sub-action: get/update roadmap state |
| `codrag_observe` | `action="save"` | Can save roadmap items as observations |

---

## 9. Decision Questions

### Q1: Timeline Data Source Priority
Which sources should be active in the first release?

- **A)** Only manual + AI-proposed items (simplest)
- **B)** Manual + AI-proposed + TODO/FIXME scanner (moderate)
- **C)** All sources including GitHub sync (full but complex)

### Q2: Scoring Dimensions
The 4 scoring dimensions (relevance, staleness, excitement, impact) — should they:

- **A)** All be computed automatically in background
- **B)** Relevance + staleness auto, excitement + impact manual
- **C)** All manual (user rates each item)

### Q3: Fork Visualization
Design forks where a roadmap item offers two paths — should this be:

- **A)** Phase 59B (build with initial timeline)
- **B)** Phase 59E (defer to advanced viz)
- **C)** Skip entirely (too complex for the value)

### Q4: GitHub Integration Depth
How deep should GitHub integration go?

- **A)** Read-only import of issues/PRs (simple webhook or polling)
- **B)** Bidirectional sync with GitHub Projects v2
- **C)** Full sprint management (map tiers to iterations, auto-assign)
- **D)** Start with VS Code extension integration first

### Q5: North Star Count
How many north stars should be supported?

- **A)** 1 primary (simplest, most focused)
- **B)** 1 primary + up to 3 secondary
- **C)** Up to 10 (user's "10 stars")
- **D)** Unlimited (but ranked by priority)

### Q6: App Ethos
The "core app ethos" concept that guides impact scoring — should it be:

- **A)** A simple text field (like product intent)
- **B)** A structured document (personas, values, anti-goals)
- **C)** Derived from the Atlas automatically
- **D)** Stub it as a text field now, structure it later

### Q7: Visualization Tech
For the timeline component:

- **A)** Pure D3.js (maximum control, harder to integrate with React)
- **B)** D3.js + React (D3 for calculations, React for rendering)
- **C)** Pure SVG with React (simpler, less powerful animations)
- **D)** Canvas-based (performant for many items, loses SVG accessibility)

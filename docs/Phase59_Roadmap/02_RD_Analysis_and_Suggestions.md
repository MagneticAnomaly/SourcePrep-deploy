CoDRAG/docs/Phase59_Roadmap/02_RD_Analysis_and_Suggestions.md
# Phase 59: Roadmap Feature — Critical Analysis & Suggestions

> An expansion and interrogation of the R&D Plan, grounded in the existing Phase 57 Goalposts implementation.

---

## Executive Summary

The R&D Plan proposes a compelling vision: transform CoDRAG's flat goalpost list into a **living, scrollable timeline** with **north star anchors** and **automatic discovery**. This is a natural evolution.

However, after reviewing the existing `GoalpostsState` (Phase 57) and `ActionItem` (Phase 57B) implementations, there are **architectural risks** around data model fragmentation, migration complexity, and scope creep that deserve scrutiny before implementation begins.

This document:
1. **Questions** key assumptions in the plan
2. **Expands** on technical gaps
3. **Offers concrete suggestions** with migration paths
4. **Provides definitive recommendations** for the decision questions

---

## 1. Architecture Reality Check: What Already Exists

Before building new models, let's inventory what's already shipped:

### 1.1 Phase 57 Goalposts (Already Implemented)

```CoDRAG/src/codrag/core/goalposts_models.py#L1-25
"""
Goalposts data models for CoDRAG (Phase 57).

Core data structures for the forward-looking AI planning system.
"""
```

| Feature | Status | Location |
|---------|--------|----------|
| Proposal generation | ✅ | `GoalpostsPlanner.generate()` |
| Priority levels (P0-P3) | ✅ | `GoalpostProposal.priority` |
| State tracking | ✅ | `proposed\|approved\|dismissed\|refined` |
| Product intent | ✅ | `GoalpostsState.product_intent` |
| Design questions | ✅ | `GoalpostQuestion` |
| Task breakdown | ✅ | `GoalpostTask` with file_paths |
| Persistence | ✅ | `goalposts.json` in index_dir |

### 1.2 Phase 57B ActionItem Unification (Already Implemented)

```CoDRAG/src/codrag/core/audit/action_item.py#L1-11
"""
Unified ActionItem model... Both dashboard panels and MCP tools consume this model.
"""
```

The `ActionItem` already unifies:
- Health scanner findings (`source="health"`)
- Advisor proposals (`source="advisor"`) via `goalpost_to_action_item()`

**Critical Question**: Does Roadmap replace Goalposts, extend it, or sit beside it?

>>> This is an important qustion -- the "Goalposts" that are new here do replcace the Goalposts semantically. conceptually these ARE the goalposts we built the previous "goalposts" to prepare for, we built the forward-thinking perdection systom under that name but we are NOW building the actual goal posts -- which are specifically defined point on this "tree-roots" looking svg or d3 graphic. We can completely erase the old "Goalposts" dashboard panal (not used at all anymore) and replace it with a new goalposts panel with this intractive graphic

---

## 2. Critical Questions & Architectural Concerns

### 2.1 Data Model Fragmentation Risk

**The Problem**: The R&D Plan proposes:
- `RoadmapItem` with 9 tiers, scoring dimensions, fork support
- `NorthStar` with active/priority tracking
- New discovery pipeline (TODO scanner, Phase doc scanner)

**Current State**: We have:
- `GoalpostProposal` with priority, state, tasks
- `ActionItem` with severity, priority, source, state
- `GoalpostQuestion` for design ambiguity

**Risk**: Users will have:
- Goalposts panel with approved/dismissed items
- Roadmap panel with tiered items
- Health panel with findings
- Action Items panel (unified view)

**This is cognitive overload.** Three different mental models for "what should I work on?"

### 2.2 The Tier Model: Elegant but Unproven

The 9-tier system is visually compelling:

```
9. PROPOSED → 8. PROPOSED+ACCEPTED → 7. MANUALLY ADDED → ...
```

**Concerns**:

1. **State × Tier Confusion**: An item can be `state="approved"` at tier 9 or tier 4. Is tier a visual position or a lifecycle stage?

2. **The "Hidden" Tiers**: Tiers 1 and 9 are scroll-past zones. In practice, users will rarely see them, yet they complicate the data model.

3. **Tier Promotion Logic**: The plan says items "flow upward" — but what triggers promotion?
   - Manual drag? (user-controlled)
   - Git commit hooks? (automatic)
   - PR merge detection? (external integration)
   - Time-based? (staleness)

4. **Category × Tier Matrix Explosion**: With 9 tiers × 5 categories × 4 priorities, we have 180 potential "buckets." Will the UI collapse empty tiers? Always show all 9?

### 2.3 Scoring Dimensions: Concrete Implementation Gaps

The 4 scoring dimensions (relevance, staleness, excitement, impact) are appealing but vague:

| Dimension | How to Compute? | Confidence |
|-----------|-----------------|------------|
| **Relevance** | Cosine similarity to NorthStar description? | Medium |
| **Staleness** | Time since creation × code churn in affected files? | High |
| **Excitement** | Novelty detection against historical proposals? | Low |
| **Impact** | Requires `AppEthos` (which doesn't exist yet) | Very Low |

**Concern**: "Excitement" is especially hand-wavy. Is it:
- TF-IDF rarity of proposal category?
- LLM-generated "innovation score"?
- User engagement (clicks, time-spent-reading)?

### 2.4 North Star: Single Point of Failure?

The plan positions North Stars as "goalposts the AI uses to focus its proposals." This is philosophically sound but technically fragile:

- **What if the North Star is wrong?** Users may set "Ship v2.0 with plugin system" but the codebase is monolithic and can't support plugins.
- **What if there are no North Stars?** The plan says "Without goalposts, the AI wanders" — but the current `GoalpostsPlanner` generates good proposals without them.
- **Multiple North Stars**: The scoring section suggests ranking against multiple stars, but doesn't specify how to resolve conflicts.

### 2.5 Fork Visualization: Premature Complexity?

The "split spine" fork visualization is aesthetically compelling:

```
    ┌─── Fork A: Plugin arch ──┐
────┤                          │
    └─── Fork B: Monolith ────┘
```

**Reality Check**:
- How many real-world decisions have exactly 2 mutually exclusive options?
- What happens when one fork is chosen? Does the other disappear? Archive?
- This is essentially a **decision record** with visualization — do we need custom D3 logic for this?

**Alternative**: Use the existing `GoalpostQuestion` ("Should we go with Plugin A or Monolith B?") and surface answered questions as "Decision Log."

---

## 3. Concrete Suggestions

### Suggestion 1: Unified Data Model — RoadmapItem as ActionItem Extension

**Don't create a parallel universe.** Extend `ActionItem` with optional roadmap metadata:

```python
# New: Roadmap metadata (optional extension)
@dataclass
class RoadmapMetadata:
    tier: int | None = None           # 1-9, None = not on roadmap
    goalpost_id: str | None = None    # Link to parent NorthStar
    discovered_from: str | None = None  # File path, GitHub issue, etc.
    discovered_at: str = ""           # ISO timestamp
    
    # Scoring (all optional, computed in background)
    relevance: float | None = None
    staleness: float | None = None
    
    # Fork support (future)
    parent_id: str | None = None
    fork_label: str | None = None

# Extend ActionItem with:
#   roadmap: RoadmapMetadata | None = None
```

**Benefits**:
- Existing Health findings can "graduate" to the Roadmap (just add metadata)
- Advisor proposals flow naturally into the timeline
- Single source of truth for "what should I work on"
- MCP tools already understand `ActionItem`

### Suggestion 2: Simplify to 5 Tiers (Not 9)

The 9-tier model is overfit to the "scrollable timeline" metaphor. Consider:

```
┌─────────────────────────────────────┐
│  5. ARCHIVE (completed, hidden)       │  Scroll up to see
├─────────────────────────────────────┤
│  4. IN PROGRESS (current sprint)      │  ★ Default view ★
├─────────────────────────────────────┤
│  3. PLANNED (next 1-2 sprints)        │
├─────────────────────────────────────┤
│  2. BACKLOG (approved, not scheduled) │
├─────────────────────────────────────┤
│  1. PROPOSED (AI suggestions)         │  Scroll down to see
└─────────────────────────────────────┘
```

**Why 5 works better**:
- Maps directly to agile concepts (backlog → planned → in-progress)
- Eliminates the confusing "hidden top/bottom" zones
- Still supports the "scroll through time" metaphor
- Easier to implement drag-and-drop reordering

**Tier Promotion Triggers**:
| From | To | Trigger |
|------|-----|---------|
| PROPOSED | BACKLOG | User clicks "Accept" |
| BACKLOG | PLANNED | User drags to Planned or sets sprint |
| PLANNED | IN PROGRESS | User drags or commit detected |
| IN PROGRESS | ARCHIVE | User marks complete OR PR merged |

### Suggestion 3: Defer "Excitement" and "Impact" Scores

Replace the 4-dimension scoring with:

1. **Relevance** (auto): TF-IDF/cosine similarity to North Star text
2. **Staleness** (auto): Days since discovery × file churn rate
3. **User Priority Override** (manual): Let users pin/star items

Add excitement/impact later when `AppEthos` is defined and we have user behavior data.

### Suggestion 4: North Star as "Product Intent v2"

The existing `product_intent` field is already doing 80% of North Star work:

```CoDRAG/src/codrag/core/goalposts_models.py#L102-108
@dataclass
class GoalpostsState:
    """Complete persisted state for a project's goalposts."""
    product_intent: str = ""            # User's description of their product direction
```

**Evolution Path**:
```python
@dataclass  
class NorthStar:
    id: str
    title: str           # Extracted from first line of product_intent
    description: str       # Full product_intent text
    active: bool = True  # New: can deactivate without deleting
    priority: int = 1    # New: support 1 primary + N secondary
    
    # Derived metrics (computed from linked items)
    linked_count: int = 0
    completion_pct: float = 0.0
```

**Migration**: 
1. Convert existing `product_intent` → `NorthStar(id="ns-primary", ...)`
2. Add `goalpost.north_star_id` foreign key (nullable)
3. Support multiple stars in future iteration

### Suggestion 5: Discovery Pipeline Priority Order

The R&D Plan lists 5 discovery sources. **Prioritize ruthlessly**:

**Phase 59A (Foundation)**:
1. ✅ **Existing GoalpostProposals** — already implemented, just need tier metadata
2. ✅ **Manual items** — user creates directly in UI
3. ⏳ **TODO/FIXME scanner** — new, but grep-based, straightforward

**Phase 59C (Intelligence)**:
4. ⏳ **Phase doc scanner** — nice-to-have, can wait
5. 🔮 **GitHub sync** — requires auth, rate limits, webhooks — defer to Phase 59D

**What to skip entirely**:
- The "Advisor Proposals as discovery source" is circular — Advisor *creates* proposals, it doesn't discover them

### Suggestion 6: Fork Support via Tags, Not Schema

Instead of:
```python
parent_id: str | None     # For branching roadmap paths
fork_label: str | None    # "Option A: Plugin arch"
```

Use **categorical tags**:
```python
tags: List[str] = field(default_factory=list)
# Examples:
# ["fork:plugin-arch", "fork:active"]
# ["fork:monolith", "fork:rejected"]
```

**Benefits**:
- No schema changes for experimental feature
- Can filter by `tag.startswith("fork:")` in UI
- Supports N-way forks, not just binary
- Easy to migrate to formal schema if successful

---

## 4. Revised Phased Build Plan

### Phase 59A: Foundation (2 weeks)

**Goal**: Roadmap timeline displays existing Goalposts with tier metadata.

| Task | Files |
|------|-------|
| Extend `ActionItem` with `RoadmapMetadata` | `audit/action_item.py` |
| Migration: add tier to existing proposals | `goalposts_models.py` |
| `RoadmapState` persistence (JSON) | New: `roadmap_models.py` |
| Basic API: GET/PUT/PATCH items | `routers/roadmap.py` |
| TODO/FIXME scanner (background task) | `tasks/todo_scanner.py` |

**Definition of Done**: 
- Dashboard shows existing approved proposals in tier 2 (BACKLOG)
- User can drag items between 5 tiers
- New items appear in tier 1 (PROPOSED)

### Phase 59B: Timeline UI (2 weeks)

**Goal**: Visual vertical timeline with D3.

| Task | Notes |
|------|-------|
| D3.js vertical timeline component | `RoadmapTimeline.tsx` |
| 5-tier layout with center spine | Tier 3 (IN PROGRESS) highlighted |
| Item cards with badges | Show source (health/advisor/manual) |
| Drag-to-reorder within tiers | HTML5 drag and drop |
| Dashboard panel registration | `RoadmapPanel` |

**Definition of Done**:
- Scrollable timeline, anchored at IN PROGRESS
- Click item to expand details
- Drag item to change tier (triggers state update)

### Phase 59C: Intelligence (2 weeks)

**Goal**: Automatic scoring and promotion.

| Task | Algorithm |
|------|-----------|
| Relevance scorer | Cosine similarity to North Star |
| Staleness detector | `staleness = days * (1 + churn_rate)` |
| Auto-promotion rules | e.g., "promote to PLANNED if relevance > 0.8" |
| Background refresh | Celery/scheduler task |

**Definition of Done**:
- Each item shows relevance/staleness bars
- Background job updates scores hourly
- User can configure auto-promotion thresholds

### Phase 59D: GitHub Integration (Future)

**Goal**: Sync with external project management.

- Read-only import of issues (as tier 1 items)
- PR merge → auto-promote to ARCHIVE
- Bidirectional sync (push accepted items to GitHub Projects)

**Decision**: Only build this if users request it. Start with Phase 59A-C as standalone value.

---

## 5. Decision Questions: Definitive Recommendations

### Q1: Timeline Data Source Priority

**Recommendation: B (Manual + AI-proposed + TODO/FIXME scanner)**

**Rationale**:
- Option A is too limited — TODOs are high-signal, low-effort to capture
- Option C is premature — GitHub integration requires auth, webhooks, and complex error handling
- The TODO scanner is trivial (grep) and adds immediate value

### Q2: Scoring Dimensions

**Recommendation: B (Relevance + staleness auto, excitement + impact manual/deferred)**

**Rationale**:
- Relevance and staleness have clear computational paths
- Excitement requires behavioral data we don't have yet
- Impact requires `AppEthos` which is undefined
- Start with 2 working dimensions, add 2 later based on user feedback

### Q3: Fork Visualization

**Recommendation: C (Skip entirely)**

**Rationale**:
- Use tags + decision log instead (`GoalpostQuestion.answered`)
- Real fork visualization is complex (merge conflicts, path comparison)
- Binary forks rarely exist in practice (usually N options with tradeoffs)
- Revisit if users explicitly request decision comparison UI

### Q4: GitHub Integration Depth

**Recommendation: A (Read-only import of issues/PRs)**

**Rationale**:
- Bidirectional sync is a maintenance nightmare (conflict resolution, rate limits)
- Read-only import via polling is simple and valuable
- VS Code integration is orthogonal — do it separately

### Q5: North Star Count

**Recommendation: B (1 primary + up to 3 secondary)**

**Rationale**:
- Single star is too limiting (users have parallel initiatives)
- Unlimited stars dilute focus ("everything is a priority")
- 4 stars total (1+3) matches cognitive limits (working memory ~4 items)
- Secondary stars can be "deactivated" without deletion

### Q6: App Ethos

**Recommendation: D (Stub as text field now, structure it later)**

**Rationale**:
- Structured `AppEthos` (personas, values, anti-goals) is valuable but requires design research
- A simple text field enables impact scoring immediately
- Can parse text field into structured format later if needed
- Don't block Phase 59 on philosophical document design

### Q7: Visualization Tech

**Recommendation: B (D3.js + React)**

**Rationale**:
- Pure D3 loses React's component model and state management
- Pure SVG is limiting for animations and complex layouts
- Canvas loses accessibility (screen readers, text selection)
- D3 for layout calculations, React for rendering is the industry standard (e.g., Observable Plot, Victory)

**Specific stack**:
```typescript
// D3 for layout
const layout = d3.tree().size([height, width])(hierarchyData);

// React for rendering
return (
  <svg>
    {layout.descendants().map(node => (
      <RoadmapCard key={node.data.id} node={node} />
    ))}
  </svg>
);
```

---

## 6. Open Questions for Discussion

Before implementation begins, resolve:

1. **Migration strategy**: Do we auto-convert existing `GoalpostProposal` to `RoadmapItem`, or grandfather them in? Suggest: auto-convert approved proposals to tier 2 (BACKLOG).

2. **Tier persistence**: When user drags item from tier 4 → tier 3, do we:
   - Update `roadmap_tier` field (current model)
   - Create a `TierHistory` log entry (audit trail)
   - Both?

3. **Stale item handling**: After 30 days with no activity, should items:
   - Auto-escalate staleness score?
   - Fade in UI?
   - Prompt user to "dismiss or commit"?

4. **Health findings on roadmap**: Should critical health findings (P0) auto-appear in tier 1 (PROPOSED), or only appear in unified view?

---

## 7. Summary: Keep vs. Cut

| R&D Plan Feature | Recommendation | Reason |
|------------------|----------------|--------|
| 9-tier model | **Cut to 5 tiers** | Simpler, clearer, faster to build |
| Fork visualization | **Cut** | Use tags + decision log instead |
| 4 scoring dimensions | **Cut to 2 (relevance, staleness)** | Add excitement/impact later |
| GitHub bidirectional sync | **Cut** | Read-only only; complexity too high |
| New `RoadmapItem` model | **Cut** | Extend `ActionItem` instead |
| `NorthStar` as new concept | **Keep but simplify** | Evolve from `product_intent` |
| D3.js timeline | **Keep** | Core differentiator |
| TODO/FIXME scanner | **Keep** | High value, low effort |
| Phase doc scanner | **Defer** | Nice-to-have, not critical path |

---

## 8. Success Metrics

How do we know Phase 59 succeeded?

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Adoption** | 80% of active projects have ≥3 roadmap items | Count from `roadmap.json` |
| **Engagement** | Avg 2 tier changes per week per project | Log tier transitions |
| **Retention** | 60% of users return to roadmap within 7 days | Analytics |
| **AI Utility** | 40% of accepted items are AI-proposed | Compare `source="advisor"` vs manual |
| **Performance** | Timeline renders in <200ms for 50 items | Lighthouse/Timing API |

---

*Document status: Ready for review. Next step: Technical design meeting to ratify Q1-Q7 decisions.*

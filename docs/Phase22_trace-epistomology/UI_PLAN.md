# Graph Enrichment Pipeline — UI Plan

**For**: Frontend developer  
**Component**: `TracePipelineStatus.tsx` → rename to `GraphEnrichmentPipeline.tsx`  
**Panel registry**: `trace-pipeline` → title changes from "AI Pipeline" to "Graph Enrichment"

---

## Current State

```
  ┌─────────┐  →  ┌────────────┐  →  ┌────────────┐
  │  Graph  │     │ Augmented  │     │ Validated  │
  └─────────┘     └────────────┘     └────────────┘

  Horizontal. Three stages. Manual run buttons.
  No concept of continuous operation.
```

## New Design

Vertical pipeline. Six stages. Continuous operation with pause/play.

```
  ┌──────────────────────────────────────────────────┐
  │  Graph Enrichment Pipeline            ⏸ Pause    │
  │                                                  │
  │  ● Structural Graph (Rust)           ✅ 72ms     │
  │  │  547 nodes · 656 edges · 48 docs connected    │
  │  │                                               │
  │  ▼                                               │
  │  ● Fast Catalogue (3b)               ✅ 98%      │
  │  │  538/547 augmented · 0.82 avg conf            │
  │  │                                               │
  │  ▼                                               │
  │  ● Relationship Validation (Rust)    ✅ 5ms      │
  │  │  142 inferred edges · 89 confirmed            │
  │  │                                               │
  │  ▼                                               │
  │  ● Epistemic Enrichment (14b)        🔄 63%      │
  │  │  Processing: src/core/trace.py                │
  │  │  347/547 enriched · 0.87 avg score            │
  │  │                                               │
  │  ▼                                               │
  │  ● Cluster Synthesis (14b)           ⏳ Waiting   │
  │  │  Needs: enrichment >= 80%                     │
  │  │                                               │
  │  ▼                                               │
  │  ○ Continuous Deepening              ○ Idle       │
  │    Converged: 412/547 nodes ≥ 0.95               │
  │                                                  │
  │  ─────────────────────────────────────           │
  │  Overall: 78% enriched · 0.84 avg epistemic      │
  └──────────────────────────────────────────────────┘
```

---

## Layout Spec

### Header Row
- **Title**: "Graph Enrichment" (not "AI Pipeline")
- **Global control**: Single **Pause / Play** toggle button (top-right)
  - Play = all stages auto-run when prerequisites met
  - Pause = nothing runs (battery saver)
  - Icon: `Pause` / `Play` from lucide
  - Tooltip: "Pause enrichment (saves battery)" / "Resume enrichment"
  - State persisted in project settings

### Stage Rows (vertical stack)

Each stage is a row with:

```
  [StateIcon]  [Label]  [Model tag]          [Status badge]
               [Stats line — muted, small text]
```

**StateIcon**: Vertical connector line between stages (like a timeline/stepper).
- `●` filled circle = complete or running
- `○` empty circle = idle/waiting
- Vertical line connects them

**Status badge** (right-aligned):
| State | Badge | Color |
|-------|-------|-------|
| Complete | `✅ 72ms` or `✅ 98%` | emerald |
| Running | `🔄 63%` with spinner | blue |
| Waiting | `⏳ Waiting` | amber |
| Idle | `○ Idle` | muted |
| Error | `⚠ Failed` | red |
| Stale | `🕐 Stale` | amber |
| Disabled | `— Disabled` | muted |

**Stats line** (below label, small muted text):
- Stage-specific metrics. Examples:
  - Graph: "547 nodes · 656 edges · 48 docs connected"
  - Catalogue: "538/547 augmented · 0.82 avg conf"
  - Validation: "142 inferred edges · 89 confirmed"
  - Enrichment: "Processing: src/core/trace.py" (when running) or "347/547 enriched · 0.87 avg score"
  - Clustering: "12 subsystems identified" or "Needs: enrichment >= 80%"
  - Deepening: "Converged: 412/547 nodes ≥ 0.95" or "Pass 3: 18 nodes re-examining"

### Footer Row
- Thin separator line
- **Overall summary**: "78% enriched · 0.84 avg epistemic score"
- Compact single-line summary of pipeline health

### Recommendations (below footer)
- Keep existing recommendation card pattern
- Update messages for new stages
- Primary action button reflects the next actionable stage

---

## Stage Definitions

```typescript
interface EnrichmentStage {
  id: 'structural' | 'catalogue' | 'validation' | 'enrichment' | 'clustering' | 'deepening';
  label: string;
  modelTag?: string;        // "Rust" | "3b" | "14b" | undefined
  state: StageState;
  progress?: number;        // 0-100, shown when state === 'running'
  currentItem?: string;     // "Processing: src/core/trace.py"
  stats: string;            // "547 nodes · 656 edges"
  lastRunAt?: string;       // ISO timestamp
  duration?: number;        // ms, shown as "72ms" or "12m"
}

type StageState = 'disabled' | 'waiting' | 'running' | 'complete' | 'stale' | 'error' | 'idle';
```

### Stage-to-Backend Mapping

| UI Stage | Backend Endpoint | Status Source |
|----------|-----------------|---------------|
| Structural Graph | `POST /trace/build` | `GET /trace/status` |
| Fast Catalogue | `POST /augment/run` | `GET /augment/status` |
| Relationship Validation | (runs automatically after catalogue) | `GET /trace/inferred-edges/status` |
| Epistemic Enrichment | `POST /trace/enrich` | `GET /trace/epistemic/status` |
| Cluster Synthesis | `POST /trace/cluster` | `GET /trace/clusters/status` |
| Continuous Deepening | (auto when enrichment complete) | `GET /trace/deepening/status` |

> Note: Validation, Enrichment, Clustering, Deepening endpoints don't exist yet.
> The UI should gracefully handle missing endpoints (show stage as "Coming Soon" or disabled).

---

## Pause/Play Behavior

**Play mode** (default for Pro users):
- Pipeline auto-advances: when one stage completes, the next begins
- Continuous Deepening runs in background (1 node/min idle, burst on trigger)
- File watcher detects changes → marks affected nodes stale → re-enrichment queues

**Pause mode** (battery saver):
- No LLM calls. No background processing.
- Structural graph still builds on explicit trigger (Rust-only, fast)
- Badge: small "⏸" icon in panel header
- Tooltip: "Enrichment paused — click ▶ to resume"

**Edge case**: If user pauses mid-enrichment:
- Current LLM call finishes (don't abort mid-generation)
- Queue preserved, resumes from same position on play

---

## Progressive Disclosure

The component needs to work at **multiple zoom levels**:

### Collapsed (panel minimized)
```
  Graph Enrichment  ●●●●○○  78%  ⏸
```
Six dots representing six stages. Filled = complete. Overall percentage. Pause state.

### Default (panel open, compact)
```
  Graph Enrichment Pipeline            ⏸ Pause
  ● Structural     ✅    ● Catalogue   ✅
  ● Validation     ✅    ● Enrichment  🔄 63%
  ● Clustering     ⏳    ○ Deepening   ○
  Overall: 78% enriched · 0.84 avg epistemic
```
2×3 grid for tighter layout if panel is narrow. Stats hidden.

### Expanded (panel open, tall)
Full vertical layout as shown above with stats lines.

---

## Migration from Current Component

1. Rename `TracePipelineStatus.tsx` → `GraphEnrichmentPipeline.tsx`
2. Keep backward compat: the three original stages map to:
   - Graph → Structural Graph
   - Augmented → Fast Catalogue
   - Validated → Relationship Validation (+ Enrichment + Clustering + Deepening are new, show as "Coming Soon")
3. Update `panelRegistry.ts`: title "AI Pipeline" → "Graph Enrichment"
4. Update stories to reflect new stages
5. New stages can render as disabled/coming-soon until backend endpoints exist

### Phase 1 (now)
- Rename + restructure to vertical layout
- Map existing 3 stages into new 6-stage model
- Add pause/play toggle (wired to project settings)
- Stages 4-6 show as "Coming Soon" with muted styling

### Phase 2 (after Sprint 3-4 backend work)
- Wire up new endpoints as they become available
- Live progress tracking for enrichment stage
- Real epistemic scores displayed

### Phase 3 (after Sprint 5-6)
- Clustering and deepening stages go live
- Convergence visualization
- Full continuous operation mode

---

## Visual Reference

Color palette (uses existing design tokens):

| Element | Token |
|---------|-------|
| Stage complete | `emerald-500/10` bg, `emerald-400` text |
| Stage running | `blue-500/10` bg, `blue-400` text |
| Stage waiting | `amber-500/10` bg, `amber-400` text |
| Stage idle/disabled | `surface-raised` bg, `text-subtle` |
| Stage error | `red-500/10` bg, `red-400` text |
| Connector line | `border` (muted vertical line) |
| Pause badge | `amber-400` icon |
| Play badge | `emerald-400` icon |

Font sizes:
- Stage label: `text-xs font-semibold`
- Model tag: `text-[10px] text-text-muted`
- Stats line: `text-[10px] text-text-muted`
- Overall summary: `text-xs text-text-secondary`

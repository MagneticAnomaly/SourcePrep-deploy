# Phase 49 Frontend: Details Toggle on Graph Enrichment Pipeline

## Concept

A simple toggle on the existing GraphEnrichmentPipeline panel switches between:
- **Default view** — exactly how it looks today (stage rows with status icons, stats, progress bars)
- **Details view** — same layout, but each stage row expands to show provenance metadata beneath its stats line

The toggle lives in the panel footer (next to "Overall Health"), keeping the header clean. When a user wants to understand data quality, see which model produced what, or check when something was last run, they flip Details on and it's all right there in the familiar pipeline view.

## UX Design

### Toggle Placement

```
┌─────────────────────────────────────────────────┐
│ FAST SYNC                    [Manual] [Auto]    │
│                                                 │
│  (o) Structural Graph         Rust     [check]  │
│  (o) Edge Discovery           Code     [check]  │
│  (o) Fast Catalogue           Fast     [check]  │
│  (o) Relationship Validation  Rust     [check]  │
│  (o) Knowledge Embedding               [check]  │
│                                                 │
│ ─────────────────────────────────────────────── │
│ DEEP ENRICHMENT           [Manual][Auto][Sched] │
│                                                 │
│  (o) Deep Reasoning         Thinking   [check]  │
│  (o) Group Reasoning        Thinking   [check]  │
│  (o) Module Synthesis       Thinking   [check]  │
│  (o) Atlas Building         Thinking   [check]  │
│  (o) Continuous Deepening              [check]  │
│  (o) Deep Knowledge Embedding          [check]  │
│                                                 │
│ ─────────────────────────────────────────────── │
│ Overall Health          72% (8/11)   [Details]  │  <-- toggle here
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░                │
└─────────────────────────────────────────────────┘
```

The `[Details]` toggle is a small `SlidingSwitch2` or a text button in the footer bar. It persists to localStorage so it stays on if the user prefers it.

### Details View — Per-Stage Expansion

When Details is ON, each `StageRow` gains a second line beneath its stats:

```
Default (Details OFF):
  (o) Fast Catalogue           Fast     [check]
      95% coverage · 87% conf

Details ON:
  (o) Fast Catalogue           Fast     [check]
      95% coverage · 87% conf
      qwen3:14b via ollama · 2m 31s · Mar 11 · v0.9.0
```

The detail line is a single row of concise metadata tokens separated by ` · `. It uses `text-[9px] text-text-subtle` — visually subordinate to the stats line.

### Detail Line Content Per Stage Type

**LLM stages** (catalogue, inferred_edges, enrichment, group_reasoning, clustering, atlas, deepening):
```
{model_name} via {provider} · {elapsed} · {date} · v{codrag_version}
```
Examples:
- `qwen3:14b via ollama · 2m 31s · Mar 11 · v0.9.0`
- `gpt-4.1-mini via openai · 45s · Jan 15 · v0.8.2`
- `qwen3.5-27b via lm-studio · 12m 8s · Feb 20 · v0.9.0`

**Rust/embedding stages** (structural, validation, knowledge, deep_knowledge):
```
{engine_backend} · {elapsed} · {date} · v{codrag_version}
```
Examples:
- `rust engine · 0.4s · Mar 11 · v0.9.0`
- `native embedder · 8s · Mar 11 · v0.9.0`

**Not yet run / no manifest:**
```
No run data available
```

### Staleness Indicator

When Details is ON and a stage's data is older than 30 days, the detail line gets an amber tint:
```
  (o) Deep Reasoning         Thinking   [check]
      42 enriched · 91% conf
      qwen3:14b via ollama · 4m 12s · 4 months ago · v0.7.0   ← amber text
```

The date shows as relative time: "Mar 11", "2 weeks ago", "4 months ago". Anything older than 30 days is amber, older than 90 days is red-ish.

### Quality Expansion (Optional Future Enhancement)

A potential future enhancement: clicking a detail line could expand to show a fuller quality breakdown. But for v1 the single detail line is sufficient — it answers the core questions:
- What model? 
- How long ago?
- Which CoDRAG version?
- How long did it take?

## Data Flow

### 1. API Endpoint (already built)

```
GET /projects/{project_id}/pipeline/provenance
```

Returns:
```json
{
  "success": true,
  "data": {
    "current_data": {
      "trace_augmented.jsonl": {
        "stage_id": "catalogue",
        "model": "qwen3:14b",
        "provider": "ollama",
        "generated_at": "2026-03-11T23:47:30Z",
        "age_days": 3.2,
        "elapsed_seconds": 151.2,
        "quality": {
          "avg_confidence": 0.87,
          "success_rate": 0.992,
          "total_items": 247
        }
      },
      "trace_epistemic.jsonl": { ... },
      ...
    },
    "last_run": { ... },
    "oldest_data_age_days": 120.5,
    "staleness_warning": true
  }
}
```

### 2. New Type (types.ts)

```typescript
export interface StageProvenance {
  stage_id: string
  model?: string
  provider?: string
  generated_at?: string
  age_days?: number
  elapsed_seconds?: number
  codrag_version?: string
  quality?: {
    avg_confidence?: number
    success_rate?: number
    total_items?: number
  }
}

export interface PipelineProvenance {
  current_data: Record<string, StageProvenance>
  last_run?: any
  oldest_data_age_days?: number
  staleness_warning?: boolean
}
```

### 3. API Client Method (client.ts)

```typescript
async getPipelineProvenance(projectId: string): Promise<PipelineProvenance>
```

### 4. Data Fetching

Two options for where to fetch:

**Option A: Fetch in useDashboardPanels (recommended)**
- Add `pipelineProvenance` to `PanelEnrichmentProps`
- Fetch in App.tsx alongside other project data
- Pass down to `GraphEnrichmentPipeline`
- Refetch when pipeline completes (SSE event)

**Option B: Fetch inside the component**
- `GraphEnrichmentPipeline` fetches its own data via `useEffect`
- Simpler prop interface but breaks the unidirectional data pattern

**Decision: Option A** — consistent with how all other data flows through the dashboard.

### 5. Component Changes

#### GraphEnrichmentPipelineProps (additions)

```typescript
export interface GraphEnrichmentPipelineProps {
  // ... existing props unchanged ...
  
  /** Phase 49: per-stage provenance data */
  provenance?: Record<string, StageProvenance>
}
```

#### StageRow Changes

The `EnrichmentStage` interface gains an optional `provenance` field:

```typescript
interface EnrichmentStage {
  // ... existing fields ...
  provenance?: StageProvenance
}
```

`StageRow` receives a `showDetails` boolean and renders the detail line conditionally:

```tsx
function StageRow({ stage, isPaused, onPause, onResume, showDetails }: {
  stage: EnrichmentStage
  showDetails: boolean
  // ... rest
}) {
  // ... existing render ...
  
  {/* Detail line — only when Details toggle is ON and provenance exists */}
  {showDetails && stage.provenance && (
    <p className={cn(
      "text-[9px] truncate leading-tight mt-0.5",
      isStale(stage.provenance.age_days) ? "text-amber-400/70" : "text-text-subtle"
    )}>
      {formatProvenanceLine(stage.provenance)}
    </p>
  )}
}
```

#### Footer Toggle

In the footer section of `GraphEnrichmentPipeline`:

```tsx
const [showDetails, setShowDetails] = useState(() => {
  try { return localStorage.getItem('codrag_pipeline_details') === 'true' } 
  catch { return false }
})

const toggleDetails = () => {
  const next = !showDetails
  setShowDetails(next)
  try { localStorage.setItem('codrag_pipeline_details', String(next)) } catch {}
}

// In the footer:
<div className="flex items-center justify-between text-[10px] text-text-muted">
  <span>Overall Health</span>
  <div className="flex items-center gap-2">
    <span>{roundedProgress}% ({completedStages}/{allStates.length})</span>
    <button
      onClick={toggleDetails}
      className={cn(
        "text-[9px] px-1.5 py-0.5 rounded border transition-colors",
        showDetails
          ? "bg-primary/10 border-primary/30 text-primary"
          : "bg-surface-raised border-border text-text-subtle hover:text-text"
      )}
    >
      Details
    </button>
  </div>
</div>
```

### 6. Provenance-to-Stage Mapping

The provenance API keys data by output file name. We need to map stage IDs to their output file names to join the data. This mapping already exists on the backend in `STAGE_OUTPUT_FILE`. On the frontend, we define a small lookup:

```typescript
const STAGE_OUTPUT_KEY: Record<EnrichmentStageId, string | null> = {
  structural:      'trace_nodes.jsonl',
  inferred_edges:  'trace_inferred_edges.jsonl',
  catalogue:       'trace_augmented.jsonl',
  validation:      null,
  knowledge:       null,
  enrichment:      'trace_epistemic.jsonl',
  group_reasoning: 'trace_group_reasoning.jsonl',
  clustering:      'trace_modules.jsonl',
  atlas:           null,
  deepening:       'trace_epistemic.jsonl',
  deep_knowledge:  null,
}
```

For stages with `null`, we fall back to looking up by `stage_id` in the provenance data.

### 7. Helper Functions

```typescript
function formatProvenanceLine(p: StageProvenance): string {
  const parts: string[] = []
  
  // Model
  if (p.model) {
    parts.push(p.provider ? `${p.model} via ${p.provider}` : p.model)
  } else if (p.codrag_version) {
    // Non-LLM stage
    parts.push('rust engine')
  }
  
  // Elapsed time
  if (p.elapsed_seconds != null) {
    parts.push(formatDuration(p.elapsed_seconds))
  }
  
  // Date
  if (p.generated_at) {
    parts.push(formatRelativeDate(p.generated_at))
  }
  
  // Version
  if (p.codrag_version) {
    parts.push(`v${p.codrag_version}`)
  }
  
  return parts.join(' · ') || 'No run data'
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return '<1s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function formatRelativeDate(iso: string): string {
  const d = new Date(iso)
  const now = Date.now()
  const days = (now - d.getTime()) / 86400000
  if (days < 1) return 'today'
  if (days < 2) return 'yesterday'
  if (days < 7) return `${Math.round(days)}d ago`
  if (days < 30) return `${Math.round(days / 7)}w ago`
  if (days < 365) return `${Math.round(days / 30)}mo ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function isStale(ageDays?: number): boolean {
  return (ageDays ?? 0) > 30
}
```

## Implementation Plan

### Sprint 1: Wiring (2-3 hours)

1. **types.ts** — Add `StageProvenance`, `PipelineProvenance` types
2. **client.ts** — Add `getPipelineProvenance()` method
3. **mock.ts** — Add mock implementation
4. **App.tsx** — Add state + fetch for pipeline provenance (on project change + pipeline completion SSE)
5. **useDashboardPanels.tsx** — Add `provenance` to `PanelEnrichmentProps`, pass through

### Sprint 2: Component Changes (3-4 hours)

1. **GraphEnrichmentPipeline.tsx**:
   - Add `provenance` prop
   - Add `showDetails` state with localStorage persistence
   - Map provenance data to stage arrays
   - Add Details toggle button in footer
2. **StageRow** — Add `showDetails` + `provenance` props, render detail line
3. **New helpers** — `formatProvenanceLine()`, `formatDuration()`, `formatRelativeDate()`, `isStale()`

### Sprint 3: Polish (1-2 hours)

1. Verify data shows correctly for each stage type
2. Test staleness color coding
3. Test localStorage persistence
4. Test with no provenance data (graceful fallback)
5. Test during active pipeline runs (detail line stays stable)

**Total estimate: 6-9 hours**

## Design Decisions

### Why the footer, not the header?

The header already has the group labels (FAST SYNC / DEEP ENRICHMENT) plus the auto/manual toggles. Adding another control would crowd it. The footer is low-traffic — just the progress bar. A small "Details" button there is unobtrusive but discoverable.

### Why a single detail line, not a card/panel?

The pipeline view is already vertically dense (11 stages). Expanding each to a card would double the height and break the at-a-glance utility. A single `text-[9px]` line per stage adds ~12px of height per row when active — minimal visual impact, maximum info density.

### Why not a separate panel?

The provenance data is most useful *in context* — right next to the stage it describes. A separate "Process History" panel would require cross-referencing. Putting it inline means "I see Deep Reasoning is complete, and right below it tells me it was qwen3:14b, 4 minutes ago."

### Why localStorage, not backend config?

This is a pure UI preference (show/hide detail). It doesn't affect pipeline behavior and doesn't need to sync across devices. localStorage is the simplest persistence that survives page refreshes.

### Future: Full History Panel

The Details toggle shows *current* provenance (what model produced the data that exists right now). A future "Process History" panel could show the full run history timeline — but that's a separate UX concern. The toggle is the v1 answer for "what's the health of my data?"

## Files to Create/Modify

### New
- None (all changes are modifications to existing files)

### Modify
- `packages/ui/src/types.ts` — `StageProvenance`, `PipelineProvenance`
- `packages/ui/src/api/client.ts` — `getPipelineProvenance()`
- `packages/ui/src/api/mock.ts` — mock impl
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — toggle + detail lines
- `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` — `PanelEnrichmentProps.provenance`
- `src/codrag/dashboard/src/App.tsx` — fetch provenance + pass to panels

## Success Criteria

- [x] Default view is **pixel-identical** to current
- [ ] Details toggle appears in footer, persists across refreshes
- [ ] Each stage shows model/provider/elapsed/date/version when Details is ON
- [ ] Stages with no provenance data show "No run data" gracefully
- [ ] Stale data (>30 days) gets amber coloring
- [ ] Data refreshes when pipeline completes
- [ ] Zero impact on pipeline performance (read-only UI)

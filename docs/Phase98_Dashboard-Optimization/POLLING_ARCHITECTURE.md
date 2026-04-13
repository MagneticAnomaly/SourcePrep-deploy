# Dashboard Polling Architecture — Phase 98

**Status:** Design document — ready for implementation
**Problem:** 10+ independent pollers compete for daemon threads, causing "Loading project..." during cloud model calls. No caching hierarchy. Inactive projects polled at same rate as active ones.

## Current State (broken)

```
Every 5s:  useEnrichment → /pipeline/status (HEAVY — 1.8MB for CoDRAG)
Every 5s:  useEnrichment → /augment/status, /epistemic/status, /modules/status, /deepening/status, /knowledge/status
Every 5s:  useProjectManager → /projects (project list refresh)
Every 8s:  useTraceSystem → /trace/coverage (full file list)
Every 10s: SidebarPipelineQueue → /system/pipeline-queue
Every 10s: useLLMConfig → /llm/slots/status
Every 30s: useAuditSystem → /audit/status
Every 30s: useGoalpostsSystem → /goalposts
Every 60s: useOpportunitiesSystem → /opportunities
```

**Total during active build:** ~15 requests/second across 8 endpoints
**Problem:** ALL of these use the default thread pool. Cloud model calls block threads for minutes → thread pool exhaustion → all endpoints timeout → dashboard goes blank.

## Proposed Architecture

### Tier 1: SSE-Driven (Real-Time, Zero Polling)

Pipeline state transitions are already emitted via SSE. Expand SSE events to carry stage data:

```
SSE event: pipeline_status
Current:  { project_id, fast_sync: {phase, current_stage}, deep_enrichment: {...} }
Proposed: { project_id, fast_sync: {...}, stages: { structural: {nodes, edges}, catalogue: {progress, baseline} } }
```

**Components that switch to SSE-only:**
- Graph Enrichment panel (stage states, running indicators)
- Pipeline Queue sidebar
- AI Gateway status
- Progress bars (current/total/baseline from SSE events)

**Polling fallback:** Only on SSE disconnect (exponential backoff reconnect).

### Tier 2: Hydration-Once + SSE Refresh

Data loaded once on project switch, then updated only via SSE events:

```
On project select:
  1. /trace/status (once)
  2. /trace/coverage/summary (once — lightweight)
  3. /pipeline/status (once — cached server-side)
  
On SSE pipeline_status event:
  → Update stage data in-memory from event payload
  → NO re-fetch needed
  
On SSE stage_completed event:
  → Fetch ONLY the completed stage's status endpoint
  → e.g., enrichment completed → fetch /epistemic/status (one call)
```

### Tier 3: Lazy Load (On-Demand Only)

Data fetched only when the user explicitly opens a panel or tab:

```
/trace/coverage (full file list)     → only when Queue/Patterns tab is visible
/audit/status + /audit/spaghetti    → only when Audit panel is open
/concepts + /concepts/stats          → only when Concepts panel is open
/atlas                               → only when Atlas panel is open
/goalposts                           → only when Goalposts panel is open
/opportunities                       → only when Opportunities panel is open
```

### Tier 4: Background Refresh (Low Priority)

Data that changes slowly, refreshed in background at long intervals:

```
/projects (project list)             → every 60s OR on SSE project_changed event
/llm/slots/status                   → every 30s (only affects AI Gateway badge)
/trace/coverage (full)              → every 60s when Graph Scope is visible
```

## Per-Project Polling Hierarchy

```
┌─────────────────────────────────────────────┐
│ Selected Project (1)                         │
│   SSE: real-time pipeline events            │
│   Hydration: once on select                 │
│   Polling: stage-specific, 5s when running  │
│            30s when idle                    │
│            OFF when tab hidden              │
├─────────────────────────────────────────────┤
│ Active Unselected Projects (2-3)            │
│   SSE: receive events (update sidebar)      │
│   Polling: NONE                             │
│   Cache: pipeline_status cached 10min       │
│   Refresh: only on SSE event               │
├─────────────────────────────────────────────┤
│ Inactive Projects (N)                       │
│   SSE: ignored                              │
│   Polling: NONE                             │
│   Cache: indefinite until activated         │
│   Refresh: only on explicit user action     │
└─────────────────────────────────────────────┘
```

## Server-Side Caching Strategy

```python
# Pipeline status: cached per-project, invalidated on SSE event
@lru_cache_with_ttl(ttl=30)  # 30s for idle projects
def get_pipeline_status(project_id):
    ...

# Invalidation: when build_orchestrator emits stage_completed
def on_stage_completed(project_id, stage):
    invalidate_cache(project_id)
    emit_sse("pipeline_status", {project_id, ...full_stage_data...})
```

## Panel-Aware Adaptive Polling

The polling interval adapts based on what's visible AND what's happening:

```
┌─────────────────────────────────────────────────────┐
│ Graph Enrichment Panel                               │
│                                                      │
│  OPEN + stage RUNNING  → 1s  (progress bars moving) │
│  OPEN + idle           → 10s (check for new runs)   │
│  COLLAPSED/CLOSED      → 0   (no enrichment polls)  │
├─────────────────────────────────────────────────────┤
│ Project-Level (sidebar status, queue)                │
│                                                      │
│  Selected + any running → 5s                         │
│  Selected + idle        → 30s                        │
│  Unselected active      → SSE-only (0 polling)      │
│  Inactive               → 0                          │
├─────────────────────────────────────────────────────┤
│ Heavy Panels (Audit, Concepts, Atlas, etc.)          │
│                                                      │
│  Panel VISIBLE → hydrate once, then SSE-driven      │
│  Panel HIDDEN  → 0                                   │
├─────────────────────────────────────────────────────┤
│ Tab hidden (document.hidden)                         │
│                                                      │
│  ALL polling → 0                                     │
│  SSE stays connected (reconnect on visibility)      │
└─────────────────────────────────────────────────────┘
```

Implementation: each hook receives a `panelVisible` boolean from the layout system.
The `useEnrichment` hook adjusts its interval:

```typescript
const pollInterval = useMemo(() => {
  if (document.hidden) return null;           // tab hidden → no polling
  if (!enrichmentPanelOpen) return null;       // panel closed → no polling  
  if (anyStageRunning) return 1000;            // running → 1s
  return 10000;                                // idle → 10s
}, [enrichmentPanelOpen, anyStageRunning]);
```

## document.hidden Protocol

ALL pollers must respect `document.hidden`:

```typescript
const tick = () => {
  if (document.hidden) return;  // Skip when tab not visible
  // ... fetch
};
```

**Current status:** Some hooks have this, some don't. Make it universal.

## Implementation Priority

1. **Increase SSE event payload** to include stage data (server change)
2. **Remove polling from useEnrichment** — rely on SSE + hydration-once
3. **Add document.hidden to ALL pollers** (quick sweep)
4. **Lazy-load panels** — defer /audit, /concepts, /atlas, /goalposts until visible
5. **Per-project polling hierarchy** — stop polling unselected projects
6. **Server-side cache invalidation** — tie cache TTL to SSE events

## Expected Impact

| Metric | Current | After |
|--------|---------|-------|
| Requests/sec (active build) | ~15 | ~2 |
| Requests/sec (idle) | ~8 | ~0.5 |
| Requests/sec (tab hidden) | ~8 | 0 |
| Thread pool slots used by polling | 15-30 | 2-4 |
| "Loading project..." during LLM | frequent | never |

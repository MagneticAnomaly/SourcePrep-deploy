# Phase 16: Data Visualization (CLI & GUI)

## Overview

Prep generates rich data about codebases: embeddings, traces, build history, search patterns, and usage metrics. This phase explores **data visualization** opportunities across both **CLI** (terminal) and **GUI** (dashboard/Storybook) surfaces.

The goal: Make invisible index activity **visible** and **beautiful**.

---

## Connection to Phase 14 (MCP-CLI)

Phase 14 established the CLI as a first-class citizen with direct MCP mode. Data visualization extends this by providing:

1. **Instant Feedback**: Show index health without opening a browser
2. **Pipeline Integration**: Visualizations that work in CI/CD logs
3. **Developer Delight**: "Wow" moments that build product affinity

---

## Data Sources

| Source | Description | Update Frequency |
|--------|-------------|------------------|
| **Embeddings** | Vector index of code chunks | On build |
| **Trace** | Symbol/import graph (GraphRAG) | On build |
| **Build History** | Timestamps, durations, chunk counts | Per build |
| **Search Queries** | Query strings, result counts, latencies | Per search |
| **File Activity** | Which files changed, when indexed | Continuous |

---

## Visualization Catalog

### 1. Activity Heatmap (GitHub-style Grid)

**Concept**: A calendar grid showing index activity over time, similar to GitHub's contribution graph.

**Data Dimensions**:
- **Cyan cells**: Embedding activity (files indexed)
- **Yellow cells**: Trace activity (symbols parsed)
- **Green cells**: Mixed activity (both)
- **Intensity**: Activity level (light = few, dark = many)

**CLI Implementation** (using `rich`):
```
Activity (last 12 weeks)
       Jan         Feb         Mar
Mon ░░▓▓░░██░░▓▓░░██░░▓▓░░
Tue ░░░░▓▓░░██░░░░▓▓░░██░░
Wed ▓▓░░░░▓▓░░██▓▓░░░░▓▓░░
Thu ░░▓▓░░░░▓▓░░░░▓▓░░░░▓▓
Fri ██░░▓▓░░░░██░░▓▓░░░░██
Sat ░░░░░░░░░░░░░░░░░░░░░░
Sun ░░░░░░░░░░░░░░░░░░░░░░

Legend: ░ none  ▓ embedding  █ trace  ▓█ mixed
```

**GUI Implementation**: SVG/Canvas grid with tooltips, theme-aware colors.

---

### 2. Index Health Bar

**Concept**: A compact progress-bar style indicator of index completeness.

**CLI Implementation**:
```
Index Health [████████████████░░░░] 80% (1,234 / 1,543 files)
  Embeddings: ████████████████████ 100%
  Trace:      ████████████░░░░░░░░  60%
```

**GUI Implementation**: Stacked horizontal bars with Tremor `ProgressBar`.

---

### 3. Build Timeline (Sparkline)

**Concept**: A mini chart showing build history over time.

**CLI Implementation** (sparkline characters):
```
Builds (30 days): ▁▂▃▂▁▄▅▆▃▂▁▅▇█▆▄▃▂▁▂▃▄▅▆▄▃▂▁▂▃
                  └─ avg: 2.3s, max: 8.1s, total: 47 builds
```

**GUI Implementation**: Tremor `SparkAreaChart` or custom SVG.

---

### 4. File Tree Coverage

**Concept**: Show which directories have index coverage.

**CLI Implementation** (tree with coverage badges):
```
src/
├── api/          [████████] 100%
├── components/   [██████░░]  75%
│   ├── ui/       [████████] 100%
│   └── forms/    [████░░░░]  50%
├── utils/        [████████] 100%
└── __tests__/    [░░░░░░░░]   0% (excluded)
```

**GUI Implementation**: Collapsible tree with inline progress bars.

---

### 5. Symbol Graph Mini-Map

**Concept**: A dot-density visualization of the trace graph.

**CLI Implementation** (ASCII art):
```
Symbol Graph (847 nodes, 2,341 edges)
┌─────────────────────────────────┐
│  ·  · ·  ·   ·    ·   ·  ·  ·  │
│ ·  ○ · ○  ·  ○  ·  ○ ·  ○  · · │
│  · ○──○ · ○──○ · ○──○ · ○──○ · │
│ ·  ○ · ○  ·  ○  ·  ○ ·  ○  · · │
│  ·  · ·  ·   ·    ·   ·  ·  ·  │
└─────────────────────────────────┘
Hot spots: IndexManager (12 refs), build_project (8 refs)
```

**GUI Implementation**: Force-directed graph or matrix view.

---

### 6. Search Latency Histogram

**Concept**: Show distribution of search response times.

**CLI Implementation**:
```
Search Latency (last 100 queries)
  <50ms  ████████████████████████████████  64%
  50-100 ████████████░░░░░░░░░░░░░░░░░░░░  24%
  100-200 ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░   8%
  >200ms  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   4%
  
  p50: 32ms  p95: 112ms  p99: 189ms
```

**GUI Implementation**: Tremor `BarChart` with percentile markers.

---

### 7. Token Budget Gauge

**Concept**: Show how much of the context window is being used.

**CLI Implementation**:
```
Context Budget
┌────────────────────────────────────────┐
│ ██████████████████████░░░░░░░░░░░░░░░░ │  55%
└────────────────────────────────────────┘
  Used: 4,400 tokens  |  Budget: 8,000 tokens
  Sources: 5 chunks from 3 files
```

**GUI Implementation**: Circular gauge or linear progress with breakdown.

---

### 8. Embedding Space Preview (t-SNE/UMAP)

**Concept**: 2D projection of embedding vectors showing code clusters.

**CLI Implementation** (ASCII scatter):
```
Embedding Space (sampled 200 chunks)
     ┌────────────────────────────────┐
  1.0│    ·api·      ·     ·utils·    │
     │  · · · ·    ·   ·  · · · ·     │
  0.5│     ·     ·models·    ·        │
     │  ·    · · · · · ·   ·   ·      │
  0.0│ ·tests· ·   ·   · · ·  ·config·│
     └────────────────────────────────┘
     -1.0                          1.0
```

**GUI Implementation**: Canvas scatter plot with zoom/pan.

---

## CLI Library Options

| Library | Pros | Cons | Use Case |
|---------|------|------|----------|
| **rich** | Already in use, tables/panels/progress | Limited charts | Status, tables, progress |
| **textual** | TUI apps, widgets, mouse support | Heavier, async | Interactive dashboards |
| **plotext** | Real charts in terminal | Extra dependency | Histograms, scatter |
| **asciichartpy** | Simple line/bar charts | Basic | Sparklines |
| **termgraph** | Horizontal bar charts | CLI-only | Distributions |

**Recommendation**: Start with `rich` (already installed), add `plotext` for charts.

---

## Implemented Visualizations (CLI)

The following visualizations are now available in the `prep` CLI. This section documents:
- Where the command is implemented
- Which renderer it uses
- Which API endpoint it depends on (if any)
- What is currently demo/stubbed vs real

**Primary implementation file:** `src/prep/cli.py`

### 1. Activity Heatmap
- **Command:** `prep activity [--weeks 12] [--no-legend] [--no-labels] [--json]`
- **Renderer:** `src/prep/viz/activity_heatmap.py` (`render_activity_heatmap`)
- **Data source:**
  - Attempts: `GET /api/code-index/activity?weeks=<N>`
  - Fallback: generated sample data if the endpoint is unavailable.
- **What it shows:** GitHub-style grid where:
  - **Cyan** = embeddings-only activity
  - **Yellow** = trace-only activity
  - **Green** = mixed activity

### 2. Index Health DNA
- **Command:** `prep health`
- **Renderer:** `src/prep/viz/health.py` (`render_index_health`)
- **Data source:**
  - Uses: `GET /api/code-index/status` (existing)
  - **Current limitation:** Trace and disk usage numbers are not available via `status` yet, so they are defaulted/stubbed.
- **What it shows:** A compact “Index DNA” / coverage visualization + summary stats.

### 3. Relevance Spectrum (Search Viz)
- **Command:** `prep search <query> --viz`
- **Renderer:** `src/prep/viz/context.py` (`render_relevance_spectrum`)
- **Data source:** `POST /api/code-index/search`
- **What it shows:** A score spectrum + a top-results mini breakdown to help tune `--min-score`.

### 4. Token Budget Gauge (Context Viz)
- **Command:** `prep context <query> --viz`
- **Renderer:** `src/prep/viz/context.py` (`render_token_budget`)
- **Data source:** `POST /api/code-index/context`
- **Current limitation:** The “budget” is currently a fixed reference (defaults to `8192`) and the breakdown is simplistic.

### 5. Trace Structural Analysis
- **Command:** `prep trace`
- **Renderer:** `src/prep/viz/trace.py` (`render_trace_stats`)
- **Data source:**
  - Attempts: `GET /api/code-index/trace/stats`
  - Fallback: demo data if endpoint is unavailable.
- **What it shows:** Overall graph metrics + a hub list (most-connected symbols).

### 6. File Tree Coverage
- **Command:** `prep coverage`
- **Renderer:** `src/prep/viz/coverage.py` (`render_file_coverage`)
- **Data source:**
  - **Current limitation:** demo-only (no endpoint wired yet).
  - Planned endpoint: `GET /api/code-index/coverage`

### 7. CLI Overview Dashboard
- **Command:** `prep overview [--weeks 12]`
- **Renderer:** `src/prep/viz/overview.py` (`render_dashboard`)
- **Data source:**
  - Uses: `GET /api/code-index/status`
  - Attempts: `/activity`, `/trace/stats` when present; otherwise uses sample/demo.

## Implemented Renderers (Not Yet Exposed as CLI Commands)

These modules exist and are ready to be wired up to CLI commands + API endpoints:

### 1. Index Drift / Freshness
- **Renderer:** `src/prep/viz/drift.py` (`render_drift_report`)
- **Planned command:** `prep drift`
- **Planned endpoint:** `GET /api/code-index/drift`
- **Purpose:** Show “rotting” files that changed after last index build and quantify freshness.

### 2. RAG Pipeline Trace / Explain
- **Renderer:** `src/prep/viz/flow.py` (`render_rag_flow`)
- **Planned command:** `prep explain` (or `prep rag-trace`)
- **Planned endpoint:** `GET /api/code-index/rag/trace` (or “last query trace”)
- **Purpose:** Make retrieval → rerank → context → generation visible and debuggable.

## Unfinished + Planned Work

- **Add missing commands:**
  - **`prep drift`** to expose `render_drift_report`.
  - **`prep explain`** to expose `render_rag_flow`.
- **Wire real endpoints:**
  - `/activity` (currently optional)
  - `/trace/stats` (currently optional)
  - `/coverage` (missing)
  - `/drift` (missing)
  - `/rag/trace` (missing)
- **Improve data models:**
  - Real token budget from configured LLM context window.
  - Real breakdown of token usage (system/query/chunks/sources).
  - Real trace hub extraction, not demo.

---

## API Design

### New CLI Commands

```bash
# Activity heatmap
prep activity [--weeks 12] [--format ascii|json]

# Index health summary
prep health [--format compact|full|json]

# Build history sparkline
prep builds [--days 30] [--format sparkline|table|json]

# Symbol graph stats
prep trace stats [--format mini|full|json]

# Search latency histogram
prep metrics search [--last 100] [--format histogram|json]
```

### New API Endpoints

```
GET /api/code-index/activity?weeks=12
GET /api/code-index/health
GET /api/code-index/builds?days=30
GET /api/code-index/trace/stats
GET /api/code-index/metrics/search?last=100
```

### Shared Data Model

```typescript
interface ActivityDay {
  date: string;           // ISO date
  embeddings: number;     // Files embedded
  trace: number;          // Symbols traced
  builds: number;         // Build count
}

interface ActivityHeatmapData {
  days: ActivityDay[];
  totals: {
    embeddings: number;
    trace: number;
    builds: number;
  };
}
```

---

## Implementation Priority

| Visualization | CLI | GUI | Priority | Effort |
|---------------|-----|-----|----------|--------|
| Activity Heatmap | ▓▓░░ | ████ | **P0** | Medium |
| Index Health Bar | ████ | ████ | **P0** | Low |
| Build Sparkline | ▓▓░░ | ████ | P1 | Low |
| File Tree Coverage | ████ | ▓▓░░ | P1 | Medium |
| Token Budget Gauge | ████ | ████ | P1 | Low |
| Search Latency | ▓▓░░ | ████ | P2 | Medium |
| Symbol Graph Mini | ░░░░ | ████ | P2 | High |
| Embedding Space | ░░░░ | ▓▓░░ | P3 | High |

---

## Phase 15 (Modular Dashboard) Integration

Per `docs/Phase15_modular-design/README.md`, visualizations should be:

1. **Panel-ized**: Each visualization is a standalone panel
2. **Collapsible**: Can minimize to header-only
3. **Repositionable**: Drag to reorder
4. **Closeable**: Hide if not needed

New panel definitions:
```typescript
const VIZ_PANELS: PanelDefinition[] = [
  { id: 'activity-heatmap', title: 'Activity', icon: Calendar, minHeight: 3, category: 'viz' },
  { id: 'health-bar', title: 'Index Health', icon: HeartPulse, minHeight: 1, category: 'viz' },
  { id: 'build-sparkline', title: 'Builds', icon: Activity, minHeight: 2, category: 'viz' },
  { id: 'token-gauge', title: 'Context Budget', icon: Gauge, minHeight: 2, category: 'viz' },
];
```

---

## Next Steps

1. **Data Collection**: Ensure build/search events are logged with timestamps
2. **API Endpoints**: Implement `/activity`, `/health`, `/metrics/*`
3. **CLI Commands**: Add `prep activity`, `prep health`
4. **GUI Components**: Build `ActivityHeatmap`, `HealthBar`, `BuildSparkline` in `@prep/ui`
5. **Storybook Stories**: Document each visualization with sample data

---

## References

- [GitHub Contribution Graph](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/managing-contribution-settings-on-your-profile)
- [rich library](https://rich.readthedocs.io/)
- [plotext - plots in terminal](https://github.com/piccolomo/plotext)
- [Tremor Charts](https://www.tremor.so/docs/visualizations/chart)

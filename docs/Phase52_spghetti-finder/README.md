# Phase 52: Spaghetti Finder — File-Centric Refactor Urgency Panel

## The Problem

One of the biggest complaints about AI-assisted coding is **unhinged, out-of-control code**. Files balloon to 1200+ lines, coupling increases invisibly, tech debt accumulates in corners nobody looks at. The existing Audit panel (Phase 43) is *finding-centric* — it surfaces issues like "circular dependency detected" or "dead code in utils.py". That's useful, but it doesn't answer the immediate question every developer has:

**"Which files in my codebase desperately need refactoring, and why?"**

## The Solution

A **file-centric** dashboard panel that ranks every file by composite "refactor urgency" — combining static signals (line count, coupling, symbol density) with LLM-derived signals (tech debt items, epistemic confidence) into a single score per file.

```
┌──────────────────────────────────────────────────────────────────┐
│  Spaghetti Finder                              [Refresh] [/|\]  │
├──────────────────────────────────────────────────────────────────┤
│  Worst Overall │ Long Files │ High Coupling │ Tech Debt          │
│  ━━━━━━━━━━━━━━                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ■■■■■■■■■■  server.py          1,847 ln │ 23 imports │ 4 debt  │
│  Score: 0.92  src/codrag/server.py                    CRITICAL   │
│                                                                  │
│  ■■■■■■■■░░  orchestrator.py    1,204 ln │ 18 imports │ 2 debt  │
│  Score: 0.78  src/codrag/services/pipeline/           WARNING    │
│                                                                  │
│  ■■■■■■░░░░  mcp_server.py      987 ln │ 31 imports │ 1 debt   │
│  Score: 0.61  src/codrag/mcp/                         WARNING    │
│                                                                  │
│  ■■■■■░░░░░  index.py            756 ln │ 14 imports │ 3 debt   │
│  Score: 0.54  src/codrag/core/                        INFO       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Scoring Model

Each file gets a **refactor urgency score** from 0.0 (pristine) to 1.0 (spaghetti).

### Static Signals (no LLM, instant, from trace graph)

| Signal | Weight | Source | Rationale |
|--------|--------|--------|-----------|
| **Line count** | 0.25 | `trace_nodes[kind=file].metadata.size` / 40 | Long files are the #1 refactoring signal |
| **In-degree** (fan-in) | 0.20 | `trace_edges` target count | High fan-in = changes break many dependents |
| **Out-degree** (fan-out) | 0.10 | `trace_edges` source count | High fan-out = file does too many things |
| **Symbol density** | 0.10 | symbols-per-file from `trace_nodes[kind=symbol]` | Many classes/functions = God object |
| **Circular involvement** | 0.10 | from `CircularDependencyAnalyzer` findings | Circular deps = structural spaghetti |

### LLM-Derived Signals (from existing pipeline data)

| Signal | Weight | Source | Rationale |
|--------|--------|--------|-----------|
| **Tech debt count** | 0.15 | `trace_epistemic[].tech_debt` | Direct LLM assessment of debt |
| **Low epistemic confidence** | 0.10 | `trace_epistemic[].epistemic_confidence` | Low confidence = hard to understand = spaghetti |

### Score Computation

Each signal is normalized to 0.0-1.0 using percentile ranking within the project, then combined with weights:

```python
score = (
    0.25 * norm_lines +
    0.20 * norm_fan_in +
    0.10 * norm_fan_out +
    0.10 * norm_symbol_density +
    0.10 * norm_circular +
    0.15 * norm_tech_debt +
    0.10 * norm_low_confidence
)
```

### Severity Thresholds

| Score | Severity | Label |
|-------|----------|-------|
| >= 0.75 | `critical` | Needs immediate attention |
| >= 0.50 | `warning` | Should be refactored |
| >= 0.30 | `info` | Minor concerns |
| < 0.30 | — | Not shown (healthy) |

## Tab Structure

| Tab | Sort Key | Description |
|-----|----------|-------------|
| **Worst Overall** | Composite score | Files ranked by total refactor urgency |
| **Long Files** | Line count | Files ranked by raw size |
| **High Coupling** | In-degree + out-degree | Files ranked by structural coupling |
| **Tech Debt** | tech_debt count + low confidence | Files ranked by LLM-identified debt |

## Data Flow

```
trace_nodes.jsonl ─┐
trace_edges.jsonl ──┤
trace_epistemic.jsonl ──┤──> SpaghettiScorer ──> spaghetti.json ──> REST API ──> Panel
trace_augmented.jsonl ──┤                                               │
audit/findings.json ────┘                                    GET /audit/spaghetti
```

The scorer reuses the `AuditContext` loader from Phase 43, so all graph data is loaded once.

## Relationship to Audit Panel

| Aspect | Audit Panel | Spaghetti Finder |
|--------|-------------|------------------|
| **Unit** | Finding (issue) | File |
| **Question** | "What issues exist?" | "Which files need refactoring?" |
| **Grouping** | By category (arch, quality, coverage) | By signal (size, coupling, debt) |
| **Action** | Select findings → send to AI | Click file → opens in trace explorer |
| **Data source** | Analyzer findings | Composite per-file scoring |
| **LLM required** | No (Tier 1) / Yes (Tier 2) | No (uses existing pipeline data) |

The two panels are complementary. The Spaghetti Finder answers "where to look", the Audit panel answers "what's wrong there".

## Implementation

### Backend: `src/codrag/core/audit/spaghetti_scorer.py`

New module that computes per-file scores from AuditContext. Pure function, no LLM calls.

### API: `GET /projects/{id}/audit/spaghetti`

Returns ranked file list with scores, signals, and severity. Optionally accepts `?tab=worst|long|coupling|debt` for pre-sorted results.

### Frontend: `SpaghettiFinderPanel.tsx`

New panel component with tabbed file list. Each row shows:
- Score bar (visual fill proportional to 0.0-1.0)
- File name (basename bold, directory muted)
- Key metrics inline (line count, import count, debt count)
- Severity badge

### Panel Registry

New entry: `id: 'spaghetti'`, icon: `AlertTriangle` (from lucide-react), category: `status`.

## Files Created/Modified

**New:**
- `docs/Phase52_spghetti-finder/README.md` — this doc
- `src/codrag/core/audit/spaghetti_scorer.py` — scoring engine
- `packages/ui/src/components/audit/SpaghettiFinderPanel.tsx` — dashboard panel
- `tests/test_spaghetti_scorer.py` — scorer tests

**Modified:**
- `src/codrag/api/routers/audit.py` — new endpoint
- `packages/ui/src/config/panelRegistry.ts` — new panel entry
- `packages/ui/src/api/client.ts` — new API method
- `src/codrag/dashboard/src/App.tsx` — wire panel content
- `src/codrag/core/audit/__init__.py` — export scorer

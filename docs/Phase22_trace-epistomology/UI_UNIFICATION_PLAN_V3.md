# UI Unification Plan V3: The Two-Pane Architecture
**Status**: In Progress  
**Date**: 2026-02-13  
**Objective**: Unify the workflow into two distinct, purposeful panels: "Scope" (Data Management) and "Engine" (Orchestration).

---

## Core Philosophy
**Separation of Concerns**:
1.  **Scope (User's Job)**: Defining *what* enters the graph (Queue, Excludes, Untraced).
2.  **Engine (AI's Job)**: Processing that data through the 7-stage pipeline.

---

## Panel Audit (2026-02-13)

Before V3, **four overlapping panels** existed:

| Registry ID       | Title             | Component                   | Status      |
|-------------------|-------------------|-----------------------------|-------------|
| `trace-coverage`  | Graph Status      | `TraceCoveragePanel`        | **REMOVE** (duplicate) |
| `graph-structure` | Graph Scope       | `GraphStructurePanel`       | **KEEP** → Panel A |
| `trace-pipeline`  | Graph Enrichment  | `GraphEnrichmentPipeline`   | **KEEP + UPGRADE** → Panel B |
| `graph-engine`    | Graph Engine      | `GraphEnginePanel`          | **REMOVE** (duplicate) |

**Findings**:
- "Graph Status" and "Graph Scope" render identical `traceCoverage` state with Queue/Excluded tabs.
- "Graph Enrichment" has 6 stages (missing Knowledge Embedding), no auto/manual toggles.
- "Graph Engine" has 7 stages + auto/manual toggles but uses a separate `GraphEngineStatus` data model.

**Decision**: Keep `GraphStructurePanel` (Scope) and upgrade `GraphEnrichmentPipeline` (Engine).
Remove the two duplicates from registry and App.tsx panel content map.

---

## Panel A: Graph Scope (`graph-structure`)
*Component: `GraphStructurePanel` — Managing the file lists and scope.*

**Header**: "Graph Scope: 658 Files"
*   **Health Indicator**: "97% Traced" (Green bar).

**Tabs**:
1.  **Queue (28)**:
    *   List of files detected but not yet in the graph.
    *   Columns: `File`, `Age`, `Type`.
    *   **Action**: "Trace Selected" / "Trace All".
2.  **Excluded (15)**:
    *   List of ignored files/patterns.
    *   **Action**: "Un-ignore" / "Add Pattern".

**Footer**:
*   **Status**: "Last Scan: 2 mins ago".
*   **Action**: "Rescan Disk".

---

## Panel B: Graph Enrichment (`trace-pipeline`)
*Component: `GraphEnrichmentPipeline` — Orchestration, Progress, and "Deep Thinking".*

**Header**: "Graph Enrichment"
*   **Pause/Resume Toggle**: Save battery during heavy LLM stages.

**The 7-Stage Pipeline (Vertical List)**:
Each row has: **Icon** | **Stage Name** | **Model Tag** | **Status Text** | **AUTO/MANUAL Toggle** | **State Icon**.

1.  **Structural Graph** (Rust)
    *   *Status*: "Idle" or "Parsing (45 files)..."
    *   *Auto*: Default ON.
2.  **Fast Catalogue** (3b)
    *   *Status*: "Augmented 600/658".
    *   *Auto*: Default ON.
3.  **Relationship Validation** (Rust)
    *   *Status*: "Validated 1,200 edges".
    *   *Auto*: Default ON.
4.  **Epistemic Enrichment** (14b)
    *   *Status*: "Enriching... (Budget: 45k tokens left)".
    *   *Auto*: Default OFF.
5.  **Cluster Synthesis** (14b)
    *   *Status*: "24 Modules Synthesized".
    *   *Auto*: Default OFF.
6.  **Continuous Deepening**
    *   *Status*: "85% settled · avg 72%".
    *   *Auto*: Default OFF.
7.  **Knowledge Embedding**
    *   *Status*: "128 chunks embedded" or "Not built yet".
    *   *Auto*: Default OFF.

**Waterfall Logic**: If any stage is set to MANUAL, all subsequent stages are
automatically forced to MANUAL and their run buttons are disabled.

**Footer**:
*   **Overall Health**: Progress bar showing % of stages complete.
*   **Primary Action**: **"Build Structural Graph"** (contextual, shows next available action).
*   **Destroy Graph**: Confirmation-gated destructive action.

---

## 3. Global Settings (Engine Room)
*   **Model Selection**: 3b/14b.
*   **Budget Limits**: Token/Time caps.
*   **Schedule**: Auto-save triggers.

---

## Implementation TODOs

### Phase 1: Consolidation (remove duplicates)
- [x] Audit all four panels — identify duplicates
- [ ] Remove `trace-coverage` from `panelRegistry.ts`
- [ ] Remove `graph-engine` from `panelRegistry.ts`
- [ ] Remove `trace-coverage` and `graph-engine` panel content entries from `App.tsx`
- [ ] Verify `TraceCoveragePanel` and `GraphEnginePanel` components still exported (may be used by VSCode webview) but not in registry

### Phase 2: Upgrade GraphEnrichmentPipeline
- [ ] Add Stage 7: Knowledge Embedding (icon: `Network`, state from `KnowledgeEmbeddingStatus`)
- [ ] Add `onRunKnowledgeBuild` prop
- [ ] Add `knowledgeStatus` prop (`KnowledgeEmbeddingStatus`)
- [ ] Add `knowledgeBuilding` prop
- [ ] Add AUTO/MANUAL toggle button per stage (right side of each row)
- [ ] Add `autoConfig` prop: `Record<StageId, { auto: boolean }>`
- [ ] Add `onAutoConfigChange` callback prop
- [ ] Implement waterfall logic: toggling a stage to MANUAL forces all subsequent stages to MANUAL
- [ ] Disable run buttons for stages that are forced-MANUAL by a predecessor
- [ ] Wire up in `App.tsx`: pass `knowledgeStatus`, `onRunKnowledgeBuild`, auto config state

### Phase 3: Polish
- [ ] Rename panel title from "Graph Enrichment" to "Knowledge Pipeline" (matches V3 spec)
- [ ] Add contextual primary action at bottom (shows next runnable stage)
- [ ] Consider adding "Run All Auto" button that triggers from Stage 1 down through all AUTO stages

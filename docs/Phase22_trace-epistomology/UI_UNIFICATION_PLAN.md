# UI Unification Plan: Trace Epistemology
**Status**: Draft  
**Date**: 2026-02-13  
**Objective**: Unify the "Structural Trace" (Pass 0) and "Deep Analysis" (Pass 1-4) workflows into a cohesive, single-flow experience while preserving critical utilities like the file queue and exclusion management.

---

## The Problem
Currently, the UI is fragmented into three distinct disconnected components:
1. **Graph Status**: Focuses on "Trace" (Pass 0). Heavy on file management (Queue, Excludes).
2. **Graph Enrichment**: Visualizes the multi-stage pipeline (Pass 0-4).
3. **Deep Analysis**: Focuses on configuration (Budget, Schedule) and execution of the later passes.

Users perceive "two separate workflows" (Trace vs. Deep Thinking), but technically, **Trace is just Step 1** of the Deep Thinking pipeline.

---

## Design Goals
1. **Unify the Flow**: Present a single mental model: `Code on Disk` → `Knowledge Graph`.
2. **Preserve Utility**: The "Queue" and "Exclude" lists are critical for scoping and must remain accessible.
3. **Simplify Configuration**: Budget and Schedule are "Engine Settings," not a separate workflow.

---

## Option 1: The "Stage-Centric" Accordion (Vertical Integration)
*Best for: Power users who want granular control over each step.*

Merge everything into a single tall **"Knowledge Graph Pipeline"** card. The vertical stepper (currently in the middle box) becomes the navigation skeleton.

### Structure
1. **Header**: Overall Health (e.g., "Knowledge Graph: 87% Healthy").
2. **The Stepper (Interactive)**:
   - **Step 1: Structural Trace** (Click to expand)
     - *Expanded Content*: The "Graph Status" view (Queue, Excludes, Untraced list).
     - *Action*: "Map All" / "Map Selected".
   - **Step 2: Fast Catalogue** (Click to expand)
     - *Expanded Content*: Progress bar, Sample of processed files.
   - **Step 3: Validation** (Click to expand)
     - *Expanded Content*: List of flagged contradictions or validation errors.
   - **Step 4: Epistemic Enrichment** (Click to expand)
     - *Expanded Content*: **Budget Settings** (tucked here or at the bottom), Queue of "Needs Deepening".
   - **Step 5: Cluster Synthesis** (Click to expand)
     - *Expanded Content*: List of synthesized modules.
3. **Footer**: Master "Run Auto-Pilot" button (runs all steps in sequence) + Global Settings (Gear icon) for Schedule/Budget.

**Pros**:
- Single "Source of Truth".
- Contextual controls (Queue only appears when looking at Step 1).
- Scalable (can add more steps).

**Cons**:
- Can become very tall.
- Might require too many clicks to see the file queue.

---

## Option 2: The "Input-Process-Control" Flow (Visual Hierarchy)
*Best for: Clarity of data flow.*

A three-section vertical layout representing the factory floor.

### Section A: Scope (The "Hopper")
*Replaces "Graph Status"*
- **Headline**: "658 files in scope" (20 untraced).
- **Compact List**: Shows the queue of untraced files horizontally or in a small scroll area.
- **Controls**: "Manage Excludes" (Modal) + "Add to Graph" (Trace).
- *Insight*: This frames tracing as just "loading the hopper."

### Section B: Enrichment (The "Machine")
*Replaces "Graph Enrichment"*
- **Visual**: The 6-stage pipeline visualization (horizontal or vertical).
- **Live Status**: Animations showing items moving from "Structure" → "Epistemic".
- **Intervention**: Stop/Start buttons for specific stages.

### Section C: Governance (The "Control Panel")
*Replaces "Deep Analysis"*
- **Budget & Schedule**: A compact row of dials/toggles.
- **Master Action**: "Start Deep Analysis" (with a clear "Cost Estimate" if budget enabled).

**Pros**:
- Clear mental model (Input → Process → Settings).
- Keeps the "Queue" always visible (in Section A).
- Separates "Scoping" (User's job) from "Processing" (AI's job).

**Cons**:
- Still feels like 3 boxes, even if visually unified.

---

## Option 3: The "Autopilot" Dashboard (Abstraction)
*Best for: Simplicity and "Set it and forget it".*

Drastically simplify. The system handles the stages; the user manages the **Inventory**.

### Top Half: Inventory & Health
- A list view of the repo, similar to a file explorer, but columns are **"Graph Status"**.
- Columns: `File Name` | `Structural` (Check) | `Enriched` (Score 0.9) | `Cluster` (Ad-Framework).
- **Filter**: "Show Untraced", "Show Low Confidence".
- **Action**: Hover over a file to "Exclude" or "Prioritize".

### Bottom Half: Engine Status
- A single "Activity Bar" at the bottom.
- Left: "Engine Idle" or "Enriching (Stage 4/6)...".
- Right: "Budget: Unlimited" (Click to change).
- **Button**: "Sync Graph" (Smart button that does Tracing -> Deep Analysis automatically).

**Pros**:
- Focuses on the *result* (the enriched files), not the *process*.
- Very clean UI.
- "Sync Graph" matches the user's intent ("Make it up to date").

**Integration in Loop**:
*   The **Continuous Deepening** loop (Pass 4+) updates the *Epistemic Entry*.
*   When an entry stabilizes (score > 0.95), we trigger a **re-embed of the Knowledge Chunk**.
*   This keeps the RAG index "smart" and up-to-date with the model's deepest understanding.

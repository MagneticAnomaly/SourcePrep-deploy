# UI Unification Plan V3: The Two-Pane Architecture
**Status**: Proposal  
**Date**: 2026-02-13  
**Objective**: Unify the workflow into two distinct, purposeful panels: "Scope" (Data Management) and "Engine" (Orchestration).

---

## Core Philosophy
**Separation of Concerns**:
1.  **Scope (User's Job)**: Defining *what* enters the graph (Queue, Excludes, Untraced).
2.  **Engine (AI's Job)**: Processing that data through the 7-stage pipeline.

---

## Panel A: Graph Structure (The Inventory)
*Focus: Managing the file lists and scope.*

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

## Panel B: Graph Engine (The Factory)
*Focus: Orchestration, Progress, and "Deep Thinking".*

**Header**: "Knowledge Pipeline"
*   **Global Toggle**: "Auto-Pilot" (Master switch).

**The 7-Stage Pipeline (Vertical List)**:
Each row has: **Icon** | **Stage Name** | **Status** | **Auto-Toggle**.

1.  **Structural Trace** (Rust)
    *   *Status*: "Idle" or "Parsing (45 files)..."
    *   *Auto*: Default ON.
2.  **Vector Indexing** (Source)
    *   *Status*: "Indexed 658 chunks".
    *   *Auto*: Default ON.
3.  **Fast Catalogue** (3b)
    *   *Status*: "Augmented 600/658".
    *   *Auto*: Default ON.
4.  **Relationship Validation** (Rust)
    *   *Status*: "Validated 1,200 edges".
    *   *Auto*: Default ON.
5.  **Epistemic Enrichment** (14b)
    *   *Status*: "Enriching... (Budget: 45k tokens left)".
    *   *Auto*: Default OFF.
6.  **Cluster Synthesis** (14b)
    *   *Status*: "24 Modules Synthesized".
    *   *Auto*: Default OFF.
7.  **Knowledge Embedding** (Deep)
    *   *Status*: "Embeddings up to date".
    *   *Auto*: Default OFF.

**Footer**:
*   **Budget Info**: "Tokens Used: 12k / 50k".
*   **Primary Action**: **"Run Auto-Pilot"** (Executes enabled stages).
*   **Stop**: Global Halt.

---

## 3. Global Settings (Engine Room)
*   **Model Selection**: 3b/14b.
*   **Budget Limits**: Token/Time caps.
*   **Schedule**: Auto-save triggers.

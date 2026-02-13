# UI Unification Plan V2: The Graph Engine
**Status**: Proposal  
**Date**: 2026-02-13  
**Objective**: Unify the "Structural Trace" (Pass 0) and "Deep Analysis" (Pass 1-4) workflows into a cohesive, single-flow experience.

---

## Core Philosophy
**"Code on Disk" → "Knowledge Graph"**
There is only one workflow. Tracing is just the first step. Deepening is the final step.

---

## 1. Global Settings (The "Engine Room")
*Moved from the dashboard panel to the global Application Settings (Gear Icon).*

The user shouldn't need to fiddle with these constantly.
-   **Budget Strategy**: "Development (Uncapped)" vs "Production (Budgeted)".
-   **Schedule**: "Auto-run on Save" vs "Manual / Daily".
-   **Model Config**: Select 3b (Fast) and 14b (Deep) models.

---

## 2. The Unified "Graph Engine" Panel
*Replaces "Graph Status", "Graph Enrichment", and "Deep Analysis" panels.*

### A. Header: Scope & Health
*   **Left**: "Knowledge Graph" (Health: 87% Verified).
*   **Right**: 
    *   **"658 Files"**: Total scope.
    *   **"[Queue: 28]"**: Click to open the **Trace Queue Drawer** (list of untraced files).
    *   **"[Excluded: 15]"**: Click to open the **Exclusion Manager**.

### B. The Pipeline (Main Body)
A vertical visualization of the factory floor. Each stage has a status, a queue, and an **Auto-Run Toggle**.

**The Waterfall Logic**: 
*   If a stage is set to **Auto**, it runs immediately when the previous stage provides data.
*   If a stage is **Manual**, all subsequent stages automatically switch to Manual (you can't auto-cluster if you haven't auto-enriched).

#### Stage 1: Structural Trace (Rust)
*   *Input*: Raw files.
*   *Output*: AST Nodes, Edges, Hashes.
*   *Auto*: **Default ON** (Runs on file save).

#### Stage 2: Vector Indexing (Source)
*   *Input*: Raw code & docs.
*   *Output*: `embeddings.npy` (Source Embeddings).
*   *Auto*: **Default ON** (Essential for basic search).
*   *Note*: This provides immediate "grep-but-better" capability.

#### Stage 3: Fast Catalogue (3b)
*   *Input*: Nodes + Strategic Snippets.
*   *Output*: `trace_augmented.jsonl` (Summaries, Roles).
*   *Auto*: **Default ON** (Cheap & Fast).

#### Stage 4: Relationship Validation (Rust)
*   *Input*: LLM Hypotheses.
*   *Output*: Validated Edges, Inferred Connections.
*   *Auto*: **Default ON** (Fast).

#### Stage 5: Epistemic Enrichment (14b)
*   *Input*: Validated Graph + Neighbors.
*   *Output*: `trace_epistemic.jsonl` (Deep summaries, Domain tags).
*   *Auto*: **Default OFF** (Cost/Time intensive).
*   *User Action*: "Run Batch" or Toggle Auto.

#### Stage 6: Cluster Synthesis (14b)
*   *Input*: Enriched Nodes.
*   *Output*: `trace_modules.jsonl` (Module concepts).
*   *Auto*: **Default OFF**.

#### Stage 7: Knowledge Embedding (Deep)
*   *Input*: Enriched Metadata + Modules.
*   *Output*: Updated `embeddings.npy` (Knowledge Embeddings).
*   *Auto*: **Default OFF** (Linked to Stage 5/6).
*   *Note*: Enables concept-based search (e.g., "Find the auth retry logic").

### C. Footer: Actions
*   **Status Bar**: "Engine Idle" or "Enriching (Stage 5): 42/100...".
*   **Primary Action**: **"Sync Graph"**.
    *   Smart button: Executes all *Auto-enabled* stages that have pending work.
    *   *Example*: If User adds a file, "Sync" runs Trace -> Vector -> Catalogue -> Validation.
*   **Stop Button**: Global kill switch.

---

## 3. The Embedding Strategy ("Hybrid Indexing")

We perform embedding at **two distinct moments** to balance speed (responsiveness) with depth (intelligence).

### Moment A: Source Embedding (Fast)
*   **Trigger**: After **Stage 1 (Trace)**.
*   **Content**: Raw source code chunks and documentation markdown.
*   **Model**: Fast embedding model (e.g., `nomic-embed-text`).
*   **Value**: Immediate availability. The user adds a file, it's searchable by content within seconds.

### Moment B: Knowledge Embedding (Deep)
*   **Trigger**: After **Stage 5 (Enrichment)** and **Stage 6 (Clustering)**.
*   **Content**: 
    *   The **Epistemic Summaries** (which describe *intent* and *behavior*).
    *   The **Module Descriptions** (high-level architecture).
    *   **Domain Tags** and **Design Patterns**.
*   **Mechanism**: These "Knowledge Chunks" are added to the same vector index but with metadata distinguishing them as `type: knowledge`.
*   **Value**: Enables semantic search over *concepts*.
    *   *Query*: "Where is the payment validation?"
    *   *Source match*: Might fail if the code uses obscure variable names.
    *   *Knowledge match*: Hits the Epistemic Summary "Handles validation of credit card payloads".

### Continuous Deepening Loop
*   When the **Deepening Loop (Pass 4+)** updates an Epistemic Entry (score increases), we **invalidate and re-generate** its Knowledge Embedding.
*   This ensures the RAG retrieval gets smarter over time as the system "understands" the code better.

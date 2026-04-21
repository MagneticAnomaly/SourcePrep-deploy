# Prep Component & Design Audit

This document serves as a comprehensive design audit, mapping CLI capabilities to UI components and analyzing the UX requirements for each. The goal is to define a "canonical list of functional dashboard components" and ensure every UI element is purposeful, usable, and aesthetically sound.

## Audit Framework

For each component, we ask:
1.  **Function**: What distinct task does it perform? (Mapped to CLI/API)
2.  **UI Representation**: How is it visualized?
3.  **Graphic Design & Typography**: How is content placed for meaning? Hierarchy?
4.  **UX Mechanics**:
    *   Is it resizable?
    *   What is its detail view?
    *   Does it need sub-components?
    *   Button placement/size ergonomics?
5.  **Semantics**: Is the language too technical? Does it need info tooltips?

---

## 1. System & Connectivity

### 1.1 Daemon Status (Health Check)
*   **CLI Equivalent**: `prep serve` (health check part), `_is_server_available`
*   **Current UI**: `IndexStatusCard` (partial), `App.tsx` connection logic.
*   **Audit**:
    *   *UI*: Currently a subtle indicator or error screen.
    *   *Design*: Should be a persistent "heartbeat" or connection state in the global shell (footer or header).
    *   *UX*:
        *   **Resizable?**: No, fixed small indicator.
        *   **Detail View**: Click to see version, latency, uptime, bound port.
        *   **Semantics**: "Daemon" might be technical. "Server Status" or "Connection" is better.
    *   *Action*: Needs a dedicated `ConnectionStatus` primitive component in the shell.

---

## 2. Project Management

### 2.1 Project List & Selection
*   **CLI Equivalent**: `prep list`, `prep add`
*   **Current UI**: `Sidebar` project list, `AddProjectModal`.
*   **Audit**:
    *   *UI*: Sidebar list of items.
    *   *Design*: Needs clear differentiation between the *active* project and others. Typography should emphasize the project name, with secondary info (path/mode) dimmed.
    *   *UX*:
        *   **Resizable?**: Sidebar is resizable.
        *   **Detail View**: N/A (Project Home is the detail view).
        *   **Placement**: Sidebar is standard.
        *   **Buttons**: "Add Project" needs to be distinct but not distracting.
    *   *Semantics*: "Path" is technical but necessary for local-first tools.

### 2.2 Project Status Overview
*   **CLI Equivalent**: `prep status`, `prep overview`
*   **Current UI**: `IndexStatusCard`, `TraceStatusCard`.
*   **Audit**:
    *   *UI*: Cards in a grid (Dashboard).
    *   *Design*: Currently fragmented. `IndexStatusCard` mixes simple stats with technical details.
    *   *UX*:
        *   **Resizable?**: Cards should fit grid columns.
        *   **Detail View**: Clicking "Embeddings Index" should lead to a file explorer/coverage view.
        *   **Sub-components**: `StatMetric` (Label + Big Number + Trend).
    *   *Semantics*: "Embeddings Index" vs "Trace Index" is core jargon, keep but explain via tooltips.

### 2.3 File Tree & Coverage
*   **CLI Equivalent**: `prep coverage`
*   **Current UI**: `FolderTree` in Roots panel.
*   **Audit**:
    *   *UI*: Tree view with checkboxes/icons.
    *   *Design*: Tree indentation needs careful tuning for deep hierarchies. File icons are critical for scanning.
    *   *UX*:
        *   **Resizable?**: Yes, vertical and horizontal.
        *   **Detail View**: Selecting a file should show its "Chunk" status or raw content?
        *   **Semantics**: "Core Roots" vs "Working Roots" is a unique Prep concept. Needs "Info" button explaining: "Core = Always indexed, Working = Temporary task context".

---

## 3. Core Operations (The Loop)

### 3.1 Build & Indexing
*   **CLI Equivalent**: `prep build`
*   **Current UI**: `BuildCard`
*   **Audit**:
    *   *UI*: Card with "Rebuild" button and progress.
    *   *Design*: This is a *destructive/heavy* action. Button should be prominent but guarded (maybe not primary color unless "Stale").
    *   *UX*:
        *   **Feedback**: Progress bar needs to be granular (Scanning -> Chunking -> Embedding).
        *   **Detail View**: A "Build Log" modal for errors.
    *   *Semantics*: "Full Rebuild" vs "Incremental".

### 3.2 Semantic Search
*   **CLI Equivalent**: `prep search`
*   **Current UI**: `SearchPanel`, `SearchResultsList`.
*   **Audit**:
    *   *UI*: Input field + List of results.
    *   *Design*: The "Search Bar" is the primary interface. Should it be global (Command+K)? Or page specific?
        *   *Typography*: Results need clear hierarchy: File Path (Mono) > Score (Dim) > Preview text (Serif/Readable).
    *   *UX*:
        *   **Resizable?**: Results pane needs height.
        *   **Detail View**: `ChunkPreview` is essential. Side-by-side or Modal? Side-by-side (Master-Detail) is best for skimming.
        *   **Controls**: "Min Score" and "K" are technical tuners. Hide behind "Advanced" or use sensible presets?
    *   *Semantics*: "Score 0.781" is meaningless to most. Translate to "High/Medium/Low" relevance visual cues?

### 3.3 Context Assembly
*   **CLI Equivalent**: `prep context`
*   **Current UI**: `ContextOptionsPanel`, `ContextOutput`.
*   **Audit**:
    *   *UI*: Configuration form + Large text area.
    *   *Design*: This is the "Export" value proposition. The Output needs to look like code/markdown.
    *   *UX*:
        *   **Resizable?**: Text area MUST be resizable or full-screen capable.
        *   **Actions**: "Copy to Clipboard" is the primary action. "Send to LLM" (future).
    *   *Semantics*: "Token Estimation" is critical. Display "X Tokens" prominently.

---

## 4. Visualizations

### 4.1 Activity Heatmap
*   **CLI Equivalent**: `prep activity`
*   **Current UI**: `ActivityHeatmap` (implemented in viz lib).
*   **Audit**:
    *   *UI*: GitHub-style commit graph.
    *   *Design*: Colors must align with theme (Embeddings=Cyan, Trace=Yellow).
    *   *UX*: Tooltip on hover is required.

---

## 5. Configuration & Integrations

### 5.1 MCP Integration
*   **CLI Equivalent**: `prep mcp`, `prep mcp-config`
*   **Current UI**: `Settings` panel details.
*   **Audit**:
    *   *UI*: Config generator / Status.
    *   *Design*: This is "Set and Forget". Doesn't need prime real estate.
    *   *UX*: Copy-paste experience must be flawless.
    *   *Semantics*: "MCP" is an acronym. "IDE Connection" might be friendlier?

### 5.2 Settings (Globs & Models)
*   **CLI Equivalent**: `prep config`
*   **Current UI**: `ProjectSettingsPanel`, `AIModelsSettings`.
*   **Audit**:
    *   *UI*: Form fields.
    *   *Design*: Density matters here. Group related settings.
    *   *UX*: "Save" button placement? Auto-save?
        *   Validation: invalid globs should error immediately.

---

## 6. Recommendations & Action Items

1.  **Refactor Search**: Move to a "Master-Detail" layout. Left col: List of results. Right col: Full file/chunk preview.
2.  **Unify Status**: Create a "Project Header" component that aggregates Status + Build + Stats into one cohesive top bar, freeing up space for the actual work (Search/Trace).
3.  **Terminology**: Add `InfoTooltip` components to "Min Score", "K", "Core Roots".
4.  **Feedback**: Improve the "Build" feedback loop. It needs to not just spin, but say *what* it is doing (e.g., "Parsing src/foo.py").

# Dashboard UX Revamp: From "Debug Tool" to "Product"

## 1. Problem Statement
The current Prep dashboard exposes the raw underlying API parameters (`k`, `min_score`, `max_chars`, `chunks`) directly to the user. While functional for an engineer debugging the system, it is "abstract and hard to understand" for a user trying to *accomplish a task*. The UI lacks a cohesive narrative; it feels like a collection of disjointed tools rather than a unified workspace.

## 2. Theoretical Re-imagining
We need to shift from **"Parameter-First"** to **"Intent-First"**.

### Core Philosophy
*   **Hide the Math:** Users don't care about `k=5` or `min_score=0.75`. They care about "finding relevant code" or "getting enough context".
*   **Progressive Disclosure:** defaults should work for 90% of cases. "Advanced" settings can hold the knobs.
*   **Unified Context:** The dashboard should feel like a single "Console" where search, context, and trace are views of the same data, not separate isolated panels.

## 3. Critical Analysis & Proposed Changes

### 3.1. The "Search" Experience
**Current:**
- Input: `Query`, `Results (K)`, `Min Score`
- Output: List of results
- **Critique:** "Min Score" is arbitrary. Is 0.7 good? Is 0.9 too strict? Users have no frame of reference. `K` is a mechanical limit, not a user intent.

**Proposed:**
- **Unified Search Bar:** A prominent, central search bar (Spotlight/Command-K style).
- **Natural Language Filters:**
    - Instead of `Min Score` slider: "Sensitivity" (Broad <-> Precise).
    - Instead of `K`: "Density" (Few <-> Many).
    - **Better yet:** Hide these entirely by default. Use smart defaults (e.g., auto-expand K if scores are high).
- **Master-Detail View:** Clicking a result shouldn't just "show content" in a box; it should open a "File Preview" pane that highlights the relevant chunk *in context* of the file.

### 3.2. Context Assembly
**Current:**
- Panel: "Context Options"
- Inputs: `Chunks (k)`, `Max Chars`, Toggles.
- **Critique:** "Max Chars" is mental math. Users think in "Tokens" or "Models" (e.g., "Will this fit in Claude 3.5 Sonnet?").

**Proposed:**
- **"Export to LLM" Workflow:** Rename the panel to "Prompt Builder" or "Context Export".
- **Capacity Meter:** Instead of a number input, show a "Context Budget" bar.
    - [||||||....] 45% of 8k tokens used.
- **Smart Presets:** Buttons for "Small (4k)", "Standard (8k)", "Large (32k)".

### 3.3. Index & Build Status
**Current:**
- "Index Status" card and "Build" card.
- **Critique:** Why is "Repository Root" an input field in the Build card? If I'm in a project, the root is fixed. This invites error. "Stale" vs "Fresh" is good, but hidden in a badge.

**Proposed:**
- **Status Header:** Move status out of cards and into a persistent **Project Header**.
    - Left: Project Name / Branch.
    - Right: "System Health" (Ready, Indexing..., Stale).
- **Action:** A single "Sync" or "Refresh Index" button in the header. No inputs needed.

### 3.4. Trace Coverage
**Current:**
- "Trace Coverage" panel.
- **Critique:** "Queue" and "Ignored" tabs are fine, but "Index Scope" (File tree) and "Trace Coverage" feel like duplicate views of the file system.

**Proposed:**
- **Unified "Codebase Explorer":** Merge "Index Scope" and "Trace Coverage".
    - A single file tree.
    - Files have status indicators (Indexed, Traced, Ignored).
    - Right-click context menu: "Exclude from Index", "Prioritize Trace".

## 4. User Flows

### Flow A: The "Investigation" (Developer)
> "I need to find where `auth_token` is validated."

1.  **Enter Project:** Dashboard loads. Header shows "Ready".
2.  **Search:** user types "auth token validation" in the central bar.
3.  **Review:** Results appear in a list. User presses "Down Arrow".
4.  **Preview:** The right pane instantly previews the file at the relevant line.
5.  **Pivot:** User sees a function call `validate_scope()`. They click it (Trace integration) to jump to that definition.

### Flow B: The "Context Gathering" (Agentic)
> "I need to dump the auth logic into Claude to rewrite it."

1.  **Select Scope:** User selects `src/auth` folder in the Explorer.
2.  **Add to Context:** Clicks "Add to Context Buffer".
3.  **Review Budget:** "Context Meter" shows 2,400 tokens (Green).
4.  **Export:** User clicks "Copy Prompt".

## 5. Renaming Recommendations

| Current Name | Proposed Name | Rationale |
| :--- | :--- | :--- |
| **Index Scope** | **Source Browser** | "Scope" sounds abstract. "Browser" implies navigation. |
| **Context Options** | **Context Assembly** | It's an action, not just options. |
| **Search Results** | **Relevant Chunks** | Be specific about what is being returned. |
| **Min Score** | **Relevance Threshold** | (If kept) More descriptive. |
| **K** | **Max Results** | Standard terminology. |
| **Trace Coverage** | **Graph Status** | "Trace" is the mechanism, "Graph" is the value. |

## 6. Layout Wireframe Suggestion

```
+---------------------------------------------------------------+
|  [Project Name]   [Status: Ready (Green)]      [Sync Button]  |
+---------------------------------------------------------------+
|          [ Unified Search Bar (Cmd+K) ]                       |
+---------------------+-------------------+---------------------+
|  SOURCE BROWSER     |  MAIN WORKSPACE   |  CONTEXT ASSEMBLY   |
|                     |                   |                     |
| > src/              |  [Tabs: Search,   |  [Context Meter]    |
|   > components/     |   Trace, Graph]   |  [================] |
|     BuildCard.tsx   |                   |                     |
|     Search.tsx      |  1. Result A      |  Selected: 3 files  |
|                     |     Preview...    |                     |
|                     |  2. Result B      |  [Copy to Clipboard]|
|                     |     Preview...    |                     |
+---------------------+-------------------+---------------------+
```

## 7. Action Items
1.  **Mockup:** Create a Figma/Excalidraw mockup of the 3-column layout.
2.  **Component Refactor:**
    - Consolidate `IndexStatusCard` and `BuildCard` into `ProjectHeader`.
    - Create `ContextMeter` component.
    - Merge `FolderTreePanel` (Scope) and `TraceCoverage` into `CodebaseExplorer`.
3.  **Simplification:** Move `k`, `min_score`, `max_chars` into an "Advanced Settings" accordion or a modal settings dialog, distinct from the main workflow.

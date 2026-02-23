# UX Analysis: Live Sync vs Pipeline Auto/Manual

## The Core Confusion
Users are confused by two separate mechanisms controlling automation in CoDRAG:
1. **Live Sync (Watcher):** Monitors the filesystem and decides *when* to trigger a build.
2. **Pipeline Auto/Manual:** Decides *how far* the pipeline goes once a build starts.

**Mental Model Mismatch:**
Users expect a single "Automation Level" slider, but we present them with two orthogonal switches. When a user turns on "Auto" in the pipeline, they expect things to happen automatically, but if Live Sync is off, nothing happens. Conversely, "Live Sync" implies automatic updates, which conflicts with the "Manual" pipeline setting.

## What Live Sync Actually Does (Backend Reality)
Looking at `src/codrag/api/routers/projects.py` (line 570, `trigger_build` function):
When the watcher detects a file change, it calls `pipeline_orchestrator.run_fast_sync(proj.id)`. 

This is exactly what the "Auto" toggle on the Fast Sync pipeline *implies* it does. The current architecture separates the "Listen for changes" (Live Sync) from the "What to run when listening" (Pipeline Auto/Manual).

## Strategies to Alleviate Confusion

Here are three strategies ranging from simple UI tweaks to a major conceptual overhaul.

### Strategy 1: The "Tooltip & Label" Tweak (Simple)
*Keep the existing separation, but clarify the terminology and provide contextual hints.*

- **Rename "Live Sync" to "File Watcher" or "Auto-Detect Changes"**: Make it explicitly about the filesystem.
- **Rename Pipeline "Auto" to "Auto-Chain" or "Run Automatically on Change"**.
- **Contextual Warnings:** If Pipeline is set to Auto, but Live Sync is Off, show a small warning icon on the pipeline toggle: *"Watcher is off. Changes won't be detected automatically."*

### Strategy 2: The "Master Automation" Hierarchy (Medium)
*Create a visual and logical hierarchy where Live Sync is the master switch for automation.*

- **Visual Grouping:** Move the "Live Sync" toggle *inside* or directly above the Graph Enrichment pipeline panel.
- **Dependency Enforcement:** 
  - If Live Sync is OFF, the Pipeline Auto/Manual toggles are disabled (grayed out) and locked to Manual.
  - When you click "Enable Sync", the pipeline toggles unlock.
- **Clearer States:**
  - `Live Sync: OFF` → Everything is manual.
  - `Live Sync: ON` + `Pipeline: Manual` → "Detect changes but ask before enriching."
  - `Live Sync: ON` + `Pipeline: Auto` → "Fully autonomous."

### Strategy 3: The "Unified Mode" Overhaul (Major)
*Merge the concepts into a single "Automation Level" setting for the entire project.*

Replace the separate toggles with a single dropdown or segmented control at the top of the Graph Enrichment panel. This perfectly aligns with the backend reality (where the watcher directly triggers Fast Sync).

**Automation Mode:**
1. **Manual:** You must click "Run" to do anything. (Watcher off).
2. **Semi-Auto (Fast Only):** Automatically updates the structural graph on file save, but waits for approval before running Deep Reasoning (LLMs). (Watcher on, Pipeline Fast=Auto, Deep=Manual).
3. **Fully Autonomous:** Automatically runs the entire pipeline (Fast + Deep) when files change. (Watcher on, Pipeline Fast=Auto, Deep=Auto).

*Note: This simplifies the UX immensely but removes the edge case of (Watcher Off + Pipeline Auto) which is useless anyway.*

---

## Decision: Strategy 3 — Unified Mode (Implemented)

The "Live Sync" panel was redundant. The Fast Sync "Auto" toggle already starts/stops the file watcher via `useTraceSystem.handleEnrichmentAutoConfigChange()`. There is no reason for a separate panel.

### Changes Made
1. **Removed** `watch` panel from `panelRegistry.ts` (+ removed unused `Eye` import)
2. **Removed** `PanelWatchProps`, `WatchControlPanel` rendering, and `watch` prop group from `useDashboardPanels.tsx`
3. **Removed** `watch: { ... }` from `App.tsx` → `useDashboardPanels()` call
4. **Removed** `WatchControlPanel` from `FullDashboard.stories.tsx`
5. **Added** inline "Watching" badge in `GraphEnrichmentPipeline.tsx` Fast Sync header (shows when Auto is enabled)

### How It Works Now
- **Fast Sync: Manual** → Watcher OFF. User clicks "Run" to trigger pipeline.
- **Fast Sync: Auto** → Watcher ON. File saves trigger Fast Sync automatically. "Watching" badge appears.
- **Deep Enrichment: Manual/Auto/Sched** → Controls whether Deep Enrichment chains after Fast Sync (unchanged).

### Files NOT Deleted (still exported from @codrag/ui)
- `WatchControlPanel.tsx` and `WatchStatusIndicator.tsx` — kept as library components. They're no longer rendered in the dashboard but may be useful for Storybook or future use. Can be deleted later if desired.

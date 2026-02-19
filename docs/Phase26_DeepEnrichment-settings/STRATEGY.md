# Deep Enrichment Strategy & UI Redesign

## Problem Statement
The current implementation suffers from terminological ambiguity and functional gaps:
1.  **Naming Inconsistency**: "Deep Enrichment" (Pipeline Panel) vs. "Deep Analysis" (Settings).
2.  **Missing "True Auto"**: The settings allow "Manual", "Threshold", and "Scheduled", but lack a "Continuous/Auto" mode that mirrors the Fast Sync behavior.
3.  **UI Disconnect**: The Pipeline Panel controls (Manual/Auto/Sched) are disconnected from the Settings configuration.

## Proposed Strategy

### 1. Unified Terminology
We will standardize on **"Deep Enrichment"** for the entire Stage 5-8 pipeline. 
-   **Deep Analysis** will refer specifically to the *reasoning process* performed by the LLM during enrichment, but the feature set is "Deep Enrichment".

### 2. The Three Modes
We will support three distinct modes of operation for Deep Enrichment (Stages 5-8):

| Mode | Behavior | Trigger | Best For |
| :--- | :--- | :--- | :--- |
| **Manual** | Runs only when explicitly triggered by the user. | User clicks "Run". | Saving costs; Reviewing specific changes. |
| **Auto** | Runs continuously. As soon as Fast Sync (Stages 1-4) finishes a file, it is queued for Deep Enrichment. | Completion of Stage 4 (Knowledge Embedding). | Powerful local machines (Ollama); "Always-on" intelligence. |
| **Scheduled** | Runs in batches based on time or accumulated change volume. | Time (CRON) OR Change Threshold (>20%). | Cloud models (Cost control); Large codebases. |

### 3. UI Redesign Options

We need to bridge the gap between the "Control" (Panel) and "Configuration" (Settings). Here are three approaches:

#### Option A: The "Drawer Link" (Recommended)
Keep the panel lightweight. The panel shows the *state* and *mode*, but detailed configuration lives in the Settings Drawer.
*   **Pipeline Panel**: 
    *   3-way Sliding Switch: [ Manual | Auto | Sched ]
    *   "Gear" icon (or "Clock" icon if Scheduled) next to it.
    *   Clicking this opens the **Settings Drawer** directly to the Deep Enrichment tab.
    *   **Visual Feedback**: If "Sched" is selected, the Clock icon could have a small tooltip: "Next run: 2:00 AM".

**Mockup:**
```tsx
<div className="flex items-center gap-2">
  {/* Settings Trigger */}
  <Button variant="ghost" size="icon-sm" onClick={openSettings}>
    {deepMode === 'scheduled' ? <Clock className="w-3.5 h-3.5" /> : <Settings className="w-3.5 h-3.5" />}
  </Button>
  
  {/* Mode Switch */}
  <SlidingSwitch3
    options={[
      { label: 'Manual', value: 'manual' },
      { label: 'Auto',  value: 'auto' }, // Continuous 1-8 pipeline
      { label: 'Sched', value: 'scheduled' }
    ]}
    value={deepMode}
    onChange={handleModeChange}
  />
</div>
```

**Pros**: Cleanest dashboard UI; leverages existing Settings Drawer.
**Cons**: Context switch (Panel -> Drawer).

#### Option B: The "Inline Popover"
Settings are accessible immediately via a popover menu attached to the panel header.
*   **Pipeline Panel**:
    *   3-way Switch.
    *   "Clock/Gear" icon triggers a `Popover` or `DropdownMenu`.
    *   Inside the Popover: "Max Budget", "Schedule Frequency", "Threshold".
*   **Settings Drawer**:
    *   Still contains these settings for completeness, but they are duplicated/synced.

**Pros**: Immediate access; keeps user in context.
**Cons**: Popovers can be cramped for complex settings (like complex schedules).

#### Option C: The "Unified Card"
Move *all* deep enrichment controls into a dedicated dashboard widget, removing it from the global settings drawer entirely (except maybe defaults).
*   **New "Deep Enrichment" Widget**:
    *   Combines the Status/Progress view with the Configuration view.
    *   Tabs: [ Status | Configuration ].
    *   Status tab = Current pipeline view.
    *   Configuration tab = Schedule/Budget inputs.

**Pros**: High cohesion; all controls in one place.
**Cons**: Takes up more dashboard space; might hide configuration behind a tab.

### 4. Functional Specifications

#### "True Auto" (Continuous)
*   **Trigger**: Event-driven.
*   **Mechanism**: 
    1.  `KnowledgeEmbedding` (Stage 4) emits a `batch_complete` event.
    2.  `EnrichmentOrchestrator` listens. If `mode === 'auto'`, it immediately pushes the newly embedded chunk IDs to the `EpistemicEnrichment` (Stage 5) queue.
*   **Throttling**: Respects `budget_max_tokens` (if enabled) per 5-minute window to prevent API runaway.

#### "Scheduled" (Batch)
*   **Trigger**: Timer (CRON) OR Accumulation.
*   **Mechanism**:
    1.  Files change -> Stages 1-4 run (Fast Sync).
    2.  Stage 4 completes -> Chunks marked as `pending_deep_enrichment` in DB.
    3.  **Timer Tick** (e.g. 2am): Runner queries all `pending_deep_enrichment` chunks.
    4.  **Threshold Check**: If `pending_count > threshold` OR `time > next_run`, start Stage 5 batch.

#### "Manual" (On-Demand)
*   **Trigger**: User click.
*   **Mechanism**:
    1.  User clicks "Run".
    2.  Runner queries all `pending_deep_enrichment` chunks.
    3.  Starts Stage 5 batch immediately.

## Implementation Plan

1.  **Refactor Settings Interface**:
    *   Rename `DeepAnalysisSchedule` -> `DeepEnrichmentConfig`.
    *   Add `auto_enabled` boolean or merge into a `mode` enum that matches the UI.
2.  **Update `DeepAnalysisSettings.tsx`**:
    *   Make it context-aware (show relevant settings for the active mode).
3.  **Update `GraphEnrichmentPipeline.tsx`**:
    *   Wire up the new 3-way switch.
    *   Add the settings navigation button (Option A implementation).
4.  **Backend/Hook Logic**:
    *   Ensure "Auto" triggers the pipeline 5-8 loop immediately after Stage 4.

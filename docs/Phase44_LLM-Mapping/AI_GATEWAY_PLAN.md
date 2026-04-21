# AI Gateway & Mode Switching Design Plan

## 1. Objectives
1. **Explicit Mode Saving:** Introduce a hard "Save Changes" action for toggling between `Structured` and `Assigned` (Mapped) modes, located immediately next to the segmented control. 
2. **Dynamic AI Gateway Panel:** Update the "AI Gateway" panel to reflect the *saved* mode. If `Assigned` is active, it will dynamically list the user's assignment blocks and the specific tasks within them.
3. **Real-Volume Token Estimates (Hover):** Provide users with an upfront understanding of potential token volume per task. Instead of static generic strings, use the actual codebase metrics (e.g., file counts) to generate a realistic mathematical estimate (e.g., `~1,500 tokens × 400 files = ~600k tokens`).
4. **Itemized Cloud Indicators in Gateway:** Show visual token/usage indicators *itemized per task* within the AI Gateway block cards, rather than aggregating at the block level.
5. **Running State Mapping:** Ensure the AI Gateway correctly highlights blocks as "Running" by mapping the currently executing pipeline task to its assigned block.

---

## 2. Feature Breakdown

### Feature A: Token Estimates & Codebase-Aware Heuristics
- **Hover Tooltips:** When hovering over the cloud/local recommendation icons in the Assignments Pipeline (or Add Task dropdown), we will show an estimate.
- **Dynamic Calculation:** To give "real" usage volume *before* they run the pipeline, the frontend will pull the active project's metrics (e.g., `file_count` from the index status) and multiply it by a per-task heuristic.
  - *Example:* Deep Enrichment = `file_count * ~1,500 tokens`.
  - *Example:* Group Reasoning = `(file_count / 10) * ~3,000 tokens`.
- **Future Actuals:** This UI structure paves the way to replace the "estimated" calculation with actual telemetry data from the backend once token tracking is implemented.

### Feature B: Explicit Mode Saving
- **New Behavior:** 
  - The UI will hold a `draftMode` state.
  - When `draftMode !== savedMode`, a "Save Changes" button appears directly next to the Structured/Assigned segmented control.
  - Editing endpoints/models inside the blocks will *still auto-save* to the database (updating `assignment_blocks` in the background), but the actual pipeline execution mode won't flip until "Save Changes" is clicked.

### Feature C: Dynamic AI Gateway & Itemized Tasks
- **State Read:** The panel will read `llm_config.assignment_mode`.
- **Structured Render:** (Status Quo) Renders Embedding, Fast Model, Thinking Model, Code Model, Compression.
- **Assigned Render:**
  - Renders Embedding and Compression (these are universal).
  - Renders a card for **each** Assignment Block.
  - The card title will be the block's Model Name (e.g., `claude-3-5-sonnet`).
  - The card body will itemize the assigned tasks.
  - **Itemized Cloud Indicator:** Next to each task name in the gateway card, if the block uses a cloud provider, a badge will indicate the dynamic token estimate for *that specific task* (e.g., `Deep Enrichment: ☁️ ~600k tokens`).

### Feature D: Block "Running" State
- **Backend Mapping:** The backend orchestration currently tracks running states by slots (for Structured). For Assigned mode, the backend pipeline knows which `PrepTaskId` is currently running.
- **Frontend Resolution:** The AI Gateway will look at the `currentRunningTask` (e.g., `inferred_edges`). It will scan the Assignment Blocks, find the block containing `inferred_edges`, and mark that specific Gateway card as `Running`.

---

## 3. Implementation Status

### Phase 1: Frontend (Codebase-Aware Estimates) — COMPLETE
- [x] **`packages/ui/src/lib/token-estimates.ts`** — Token heuristic utility. Per-task `tokensPerUnit`, `multiplier(fileCount)`, and `description(fileCount)` functions. Volume categories: Low/Medium/High/Extreme.
- [x] **`LLMAssignmentsPipeline.tsx`** — Accepts `fileCount` prop. Cloud/local icons now show dynamic tooltips with math (e.g., `Cloud model recommended\nExtreme volume · ~600k tokens (400 files × ~1.5k tok/file)`).
- [x] **`AIModelsSettings.tsx`** — Mode toggle refactored to draft state. Toggling Structured/Assigned does NOT immediately save. A "Save" button appears next to the segmented control when the draft differs from the saved mode. Accepts `fileCount` prop and passes it to the pipeline.
- [x] **`LLMStatusWidget.tsx`** — Refactored to support assigned mode. When `assignmentMode === 'mapped'`, renders Embedding/Compression as universal cards, then renders each Assignment Block as a card with:
  - Model name + provider as header
  - Cloud icon if endpoint is a cloud provider
  - **Itemized task list** with per-task token volume badges (Low/Medium/High/Extreme)
  - Running state: if `runningTaskId` matches a task in the block, the block and the specific task get a blue "Running" indicator
- [x] **`types.ts`** — `deepening` updated to `cloud-preferred`. `TASK_CLOUD_PREF` now recommends cloud for: group_reasoning, atlas, deepening, audit.
- [x] **`index.ts`** — Exports `getTaskTokenEstimate`, `estimateTaskTokens`, `getTaskTokenDescription`, `getTaskTokenVolume`, and types.

### Phase 2: Backend (Actual Token Telemetry) — TODO
- [ ] **SQLite Table:** Add `token_usage` table to the project database (`project_id, task_id, timestamp, prompt_tokens, completion_tokens, total_tokens, model, provider`).
- [ ] **LLM Client Instrumentation:** Update the LLM client to intercept the `usage` field from OpenAI/Anthropic/Ollama responses and write to the `token_usage` table, keyed by `PrepTaskId`.
- [ ] **REST Endpoint:** `GET /api/projects/{id}/token-usage?since=...` to return aggregated token usage per task.
- [ ] **UI Swap:** Replace the heuristic-based estimates in `LLMStatusWidget` with actual historical data when available, falling back to heuristics for tasks that haven't run yet.

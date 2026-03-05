# Phase 44: LLM Mapping System (Power User Assignments)

## Overview

CoDRAG uses a **Structured** LLM assignment system: 3 tiers (Fast, Code, Thinking) plus Embedding. This works great for ~80% of users — intuitive, low-friction, and prevents VRAM mistakes.

For power users who want full control, we introduce a second mode: **Mapped**. Instead of abstract tiers, users explicitly assign specific models to specific pipeline tasks.

---

## 1. Dual-Mode Architecture

A segmented control at the top of the **right column** of the AI Models page:

```
[ Structured | Mapped ]
```

- **Structured (Default):** Current 3-tier system. Unchanged. The right column shows the 3 model cards (Fast, Code, Thinking) exactly as they appear today.
- **Mapped (Advanced):** The right column transforms into an assignment interface where users build LLM Assignment Blocks. The **left column is completely unaffected** — Embedding, Compression, Cloud Processing, and Saved Endpoints remain identical in both modes.

### Why Two Modes (Not Just Mapped)
Structured exists because it prevents VRAM thrashing by design — the pipeline orchestrator knows exactly which models will be loaded and in what order. Mapped removes those guardrails. Power users accept that tradeoff.

---

## 2. Page Layout

The AI Models page is already a two-column layout. This update **only changes the right column** when in Mapped mode.

```
┌─────────────────────────────────────────────────────────────┐
│  AI Models                                                  │
│  Configure LLMs for embedding, analysis, and compression    │
├──────────────────────────┬──────────────────────────────────┤
│                          │                                  │
│  LEFT COLUMN             │  RIGHT COLUMN                    │
│  (unchanged in both      │                                  │
│   modes)                 │  ┌────────────────────────────┐  │
│                          │  │ [ Structured | Mapped ]    │  │
│  ┌────────────────────┐  │  └────────────────────────────┘  │
│  │ Embedding Model    │  │                                  │
│  │ nomic-embed-v1.5   │  │  ── STRUCTURED ──               │
│  └────────────────────┘  │  3 model cards (current UI)      │
│                          │                                  │
│  ┌────────────────────┐  │  ── MAPPED ──                    │
│  │ Context            │  │  Unassigned Tasks Banner         │
│  │ Compression        │  │  Preset Selector                 │
│  └────────────────────┘  │  LLM Assignment Blocks           │
│                          │  + Add Assignment                │
│  ┌────────────────────┐  │                                  │
│  │ Cloud Processing   │  │                                  │
│  │ Batch mode         │  │                                  │
│  └────────────────────┘  │                                  │
│                          │                                  │
├──────────────────────────┴──────────────────────────────────┤
```

Once all 9 tasks are assigned and the "Unassigned" banner clears, the right column looks comparable in density to the current Structured view — just assignment blocks instead of tier cards.

---

## 3. Task Inventory (9 Execution Points)

Every task must be assigned to exactly one model. These are the atomic units:

| # | Task ID               | User-Facing Label             | Structured Default |
|---|-----------------------|-------------------------------|--------------------|
| 1 | `catalogue`           | Catalogue Summarization       | Fast               |
| 2 | `inferred_edges`      | Inferred Edge Discovery       | Code (→ Fast)      |
| 3 | `enrichment`          | Deep Reasoning                | Thinking           |
| 4 | `clustering`          | Module Synthesis              | Thinking           |
| 5 | `atlas`               | Atlas Generation              | Thinking           |
| 6 | `deepening`           | Deepening Loop                | Thinking           |
| 7 | `search_intent`       | Search Preprocessing          | Fast               |
| 8 | `audit`               | Automated Audits              | Thinking           |
| 9 | `augmentation`        | Trace Augmentation            | Fast               |

---

## 4. UI Design: LLM Assignment Blocks

### Core Concept: Model-Centric, Not Task-Centric

Instead of showing 9 rows of tasks with model dropdowns (overwhelming), we **invert the relationship**: each block starts with a model, and the user assigns tasks *to* it.

### Assignment Block Layout

Each block is a card:

```
┌──────────────────────────────────────────────────────┐
│  LLM Assignment                                 [×]  │
│                                                      │
│  Endpoint   [ Local Ollama (ollama)          ▾ ]     │
│  Model      [ qwen3:4b                      ▾ 🔄]   │
│                                                      │
│  Tasks                                               │
│  [ Catalogue Summarization                   ▾ ]     │
│  [ Search Preprocessing                      ▾ ]     │
│  [ Trace Augmentation                        ▾ ]     │
│  [+ Add Task]                                        │
│                                                      │
│  ─────────────────────────────────────────            │
│  ✓ Model responded successfully                      │
│              [ Test Connection ]                      │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  LLM Assignment                                 [×]  │
│                                                      │
│  Endpoint   [ Local LM Studio (lm-studio)    ▾ ]     │
│  Model      [ qwen3:32b                     ▾ 🔄]   │
│                                                      │
│  Tasks                                               │
│  [ Deep Reasoning                            ▾ ]     │
│  [ Module Synthesis                          ▾ ]     │
│  [ Atlas Generation                          ▾ ]     │
│  [ Deepening Loop                            ▾ ]     │
│  [ Automated Audits                          ▾ ]     │
│  [+ Add Task]                                        │
│                                                      │
│  ─────────────────────────────────────────            │
│  ✓ Model responded successfully                      │
│              [ Test Connection ]                      │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  LLM Assignment                                 [×]  │
│                                                      │
│  Endpoint   [ Local Ollama (ollama)          ▾ ]     │
│  Model      [ deepseek-coder:6.7b           ▾ 🔄]   │
│                                                      │
│  Tasks                                               │
│  [ Inferred Edge Discovery                   ▾ ]     │
│  [+ Add Task]                                        │
│                                                      │
│  ─────────────────────────────────────────            │
│  ✓ Model responded successfully                      │
│              [ Test Connection ]                      │
└──────────────────────────────────────────────────────┘

[+ Add LLM Assignment]
```

### Key Behaviors

- **Task dropdowns only show unassigned tasks.** Once "Catalogue Summarization" is claimed by Block 1, it disappears from other block dropdowns.
- **Reassigning:** A task can be dragged or re-selected in a different block — it auto-removes from the old block.
- **Deleting a block** un-assigns all its tasks (they return to the unassigned pool).
- **Minimum 1 task per block.** A block with 0 tasks is auto-removed.
- **Each block reuses the existing Endpoint + Model dropdowns** from the Structured model cards — identical components, just recomposed.

---

## 5. Unassigned Tasks Banner

Sits at the **top of the right column**, below the Structured/Mapped toggle. Only visible when tasks remain unassigned.

```
┌──────────────────────────────────────────────────────┐
│  ⚠  3 tasks unassigned                              │
│                                                      │
│  • Deep Reasoning                                    │
│  • Module Synthesis                                  │
│  • Automated Audits                                  │
│                                                      │
│  Pipeline stages with unassigned tasks will be       │
│  skipped during execution.                           │
└──────────────────────────────────────────────────────┘
```

- **Warning-level styling** (amber border, ⚠ icon) when 1+ tasks unassigned.
- **Gone entirely** once all 9 are assigned — the right column then looks clean and comparable to the Structured view.
- Tasks listed as clickable chips — clicking one scrolls to or highlights the `[+ Add Task]` button on the nearest block, pre-selecting that task.

---

## 6. Presets

Three preset configurations accessible via a dropdown or button row below the mode toggle:

### Preset 1: "Local Standard" (Mirrors Structured)
Auto-generated from the user's current Structured config. Creates 2-3 blocks:
- **Block 1** (Fast model): Catalogue, Search Preprocessing, Trace Augmentation
- **Block 2** (Thinking model): Deep Reasoning, Module Synthesis, Atlas, Deepening, Audits
- **Block 3** (Code model, if configured): Inferred Edge Discovery

This is the default when switching from Structured → Mapped. The user starts with a fully-assigned, working configuration that behaves identically to Structured mode.

### Preset 2: "Cloud / Hybrid"
For users running a local model for cheap tasks and a cloud API for expensive reasoning:
- **Block 1** (Local small, e.g. qwen3:4b via Ollama): Catalogue, Inferred Edges, Search Preprocessing, Trace Augmentation
- **Block 2** (Cloud, e.g. gpt-4.1-mini via OpenAI): Deep Reasoning, Module Synthesis, Atlas, Deepening, Audits

Encourages the hybrid pattern we recommend — not pure cloud.

### Preset 3: "Blank Slate"
Empty. No blocks. All 9 tasks unassigned. The banner shows the full list. For users who want to build from zero.

### Preset Behavior
- Selecting a preset **replaces** the current assignment blocks (with a confirmation dialog if blocks already exist).
- Presets auto-populate endpoint/model fields from the user's Saved Endpoints where possible. If no endpoints are saved, the endpoint dropdown is left empty.

---

## 7. Data Structure

```typescript
// -- Task IDs (canonical, used in backend + config) --
export type CodragTaskId =
  | 'catalogue'
  | 'inferred_edges'
  | 'enrichment'
  | 'clustering'
  | 'atlas'
  | 'deepening'
  | 'search_intent'
  | 'audit'
  | 'augmentation';

export const ALL_TASK_IDS: CodragTaskId[] = [
  'catalogue', 'inferred_edges', 'enrichment', 'clustering',
  'atlas', 'deepening', 'search_intent', 'audit', 'augmentation',
];

// -- Assignment Block --
export interface LLMAssignmentBlock {
  id: string;                  // UUID
  endpoint_id: string;         // References a SavedEndpoint
  model: string;               // Model name string
  tasks: CodragTaskId[];       // 1+ tasks assigned to this block
}

// -- Extended LLMConfig --
export interface LLMConfig {
  assignment_mode: 'structured' | 'mapped';

  // -- STRUCTURED MODE (existing, unchanged) --
  small_model: LLMSlotConfig;
  large_model: LLMSlotConfig;
  code_model: LLMSlotConfig;

  // -- MAPPED MODE --
  assignment_blocks: LLMAssignmentBlock[];

  // -- SHARED (both modes) --
  embedding: EmbeddingConfig;
  compression: CompressionConfig;
  saved_endpoints: SavedEndpoint[];
  batch_mode?: BatchMode;
}
```

### Validation Rules
- Every `CodragTaskId` must appear in exactly one block (no duplicates, no orphans for pipeline to run).
- A block must have ≥1 task.
- `endpoint_id` must reference a valid `saved_endpoints` entry.
- If a saved endpoint is deleted, blocks referencing it get an error state (red border, "Endpoint missing").

---

## 8. Backend: Unified LLM Resolver

### New Function: `_get_llm_client_for_task(task_id: CodragTaskId)`

Replaces all direct calls to `_get_llm_client_for_slot()`. Logic:

```python
def _get_llm_client_for_task(task_id: str) -> Optional[LLMClient]:
    """Resolve an LLM client for a specific pipeline/runtime task.
    
    In structured mode: maps task → slot → slot config (existing behavior).
    In mapped mode: maps task → assignment block → endpoint+model.
    """
    cfg = _load_ui_config()
    llm_cfg = cfg.get("llm_config", {})
    mode = llm_cfg.get("assignment_mode", "structured")

    if mode == "mapped":
        return _resolve_mapped_task(task_id, llm_cfg)
    else:
        return _resolve_structured_task(task_id, llm_cfg)
```

### Structured Resolver (existing behavior, extracted)

```python
# Maps task IDs to the structured slot names
TASK_TO_SLOT: Dict[str, str] = {
    "catalogue":       "small",
    "inferred_edges":  "code",   # falls back to small
    "enrichment":      "large",
    "clustering":      "large",
    "atlas":           "large",
    "deepening":       "large",
    "search_intent":   "small",
    "audit":           "large",
    "augmentation":    "small",
}

def _resolve_structured_task(task_id: str, llm_cfg: dict) -> Optional[LLMClient]:
    slot = TASK_TO_SLOT.get(task_id, "small")
    client = _get_llm_client_for_slot(slot)
    if not client and slot != "small":
        client = _get_llm_client_for_slot("small")  # fallback
    return client
```

### Mapped Resolver

```python
def _resolve_mapped_task(task_id: str, llm_cfg: dict) -> Optional[LLMClient]:
    blocks = llm_cfg.get("assignment_blocks", [])
    for block in blocks:
        if task_id in block.get("tasks", []):
            endpoint_id = block["endpoint_id"]
            model = block["model"]
            return _create_llm_client(endpoint_id, model)
    return None  # Task not assigned — stage will be skipped
```

### Migration Path
- `_get_llm_client_for_slot()` remains as an internal helper (used by the structured resolver).
- All pipeline workers and routers switch to `_get_llm_client_for_task(task_id)`.
- `STAGE_MODEL_SLOT` dict in `pipeline_orchestrator.py` is replaced by `STAGE_TASK_ID` mapping `StageId → CodragTaskId`.

---

## 9. VRAM Lifecycle in Mapped Mode

### The Problem
In Structured mode, the pipeline orchestrator tracks 3 abstract slots and unloads models at slot transitions. In Mapped mode, two different blocks might use the same physical model on the same endpoint — or different models that thrash.

### The Solution: Track by `(endpoint_id, model)` Tuple

```python
# Instead of tracking slot names, track the resolved model identity
def _get_model_identity(task_id: str) -> Optional[Tuple[str, str]]:
    """Returns (endpoint_id, model_name) for the task's assigned model."""
    ...

# In _maybe_unload_previous_model():
prev_identity = _get_model_identity(prev_task)
next_identity = _get_model_identity(next_task)
if prev_identity == next_identity:
    return  # Same model, no unload needed
# else: unload prev
```

### VRAM Thrashing: Accepted Risk, With Guardrails
- **No pipeline reordering.** Stages have dependency constraints that prevent safe reordering.
- **UI warning** (amber banner) if the user's assignment blocks create an interleaved local-model pattern across consecutive pipeline stages. Message: *"Adjacent pipeline stages use different local models. This may cause slow model loading between stages."*
- The pipeline orchestrator logs load/unload times so users can see the cost.

---

## 10. OOM / Concurrency Guardrails (Both Modes)

This is a pre-existing concern that affects both Structured and Mapped modes. The guardrails should be implemented regardless:

1. **Global VRAM Semaphore:** Before loading any local model, acquire a semaphore. If another model is already loaded for a different task, either:
   - Wait (queue the request) if the current model will finish soon
   - Unload the current model first (preempt)
   - Use the already-loaded model as a fallback
2. **Concurrent cloud calls are fine** — no VRAM cost, only API rate limits.
3. **Mixed local+cloud is fine** — cloud calls don't compete for VRAM.

---

## 11. Pitfalls & Edge Cases

### P1: Switching Modes Mid-Pipeline
If the user switches from Structured → Mapped (or vice versa) while a pipeline is running, the running pipeline must finish using the configuration it started with. The mode switch takes effect on the next run.

### P2: Deleted Endpoints
If a user deletes a Saved Endpoint that's referenced by an assignment block:
- The block shows an error state (red border, "Endpoint deleted").
- The task remains "assigned" but non-functional — it shows in the unassigned banner as "⚠ Endpoint missing" rather than fully unassigned.

### P3: Preset Overwrites
Selecting a preset replaces all blocks. If the user has customized blocks, show a confirmation: *"This will replace your current assignments. Continue?"*

### P4: Empty Model Field
A block with an endpoint selected but no model selected is in a warning state. Tasks assigned to it are effectively unassigned.

### P5: Backward Compatibility
Existing `ui_config.json` files with no `assignment_mode` field default to `"structured"`. The `assignment_blocks` field defaults to `[]`. No migration needed — Structured mode is the exact current behavior.

---

## 12. Implementation Roadmap

### Sprint 1: Types & Config (Backend + Frontend)
- Add `CodragTaskId` type, `LLMAssignmentBlock` interface, extend `LLMConfig` with `assignment_mode` and `assignment_blocks`.
- Update `config_manager.py` defaults and deep-merge logic.
- Add `TASK_TO_SLOT` mapping and `_get_llm_client_for_task()` resolver.
- All existing callers of `_get_llm_client_for_slot()` migrated to `_get_llm_client_for_task()`.
- **Tests:** Structured mode behaves identically to before. Mapped mode resolves correctly.

### Sprint 2: Pipeline Orchestrator
- Replace `STAGE_MODEL_SLOT` with `STAGE_TASK_ID` in `pipeline_orchestrator.py`.
- Update VRAM lifecycle to track `(endpoint_id, model)` tuples instead of slot names.
- Handle "task not assigned" gracefully (skip stage, log warning).
- **Tests:** Pipeline runs correctly in both modes. Unassigned tasks skip cleanly.

### Sprint 3: UI — Assignment Blocks
- Build `LLMAssignmentBlock` React component (reuses existing Endpoint/Model selects).
- Build `UnassignedTasksBanner` component.
- Wire up the Structured/Mapped segmented control.
- Implement task dropdown filtering (only show unassigned tasks).
- Implement block add/remove with task reassignment logic.
- **Tests:** Storybook stories for both modes, preset application.

### Sprint 4: Presets & Polish
- Implement 3 preset generators (Local Standard, Cloud/Hybrid, Blank Slate).
- Add VRAM thrashing warning banner.
- Add confirmation dialogs for preset overwrites and mode switches.
- E2E verification: full pipeline run in Mapped mode with 2-3 blocks.

---

## 13. Future Work: Reasoning Support (`<think>` Tags)

**TODO:** Add backend support for parsing and handling `<think>` reasoning tags when `enable_reasoning` is checked for an assignment block.
- When `enable_reasoning` is true, the backend LLM client needs to correctly parse and strip `<think>` tags from the output before passing the final response to the pipeline task logic.
- We should preserve the contents of the `<think>` tag for UI observability (e.g., streaming the reasoning process to the user in a collapsible panel or logging it).
- The actual pipeline prompts may need a system prompt injected instructing the model to "Please wrap your step-by-step reasoning in `<think>...</think>` tags before providing the final answer."
- This is a complex build on the backend, so the frontend UI currently just saves the boolean `enable_reasoning` state in the config block for future implementation.


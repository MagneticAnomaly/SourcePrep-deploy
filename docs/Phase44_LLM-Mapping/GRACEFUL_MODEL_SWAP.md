# Graceful Model Swap Mid-Pipeline

## Problem

When a user changes their LLM configuration while the pipeline is running — whether switching the model within a slot, changing endpoints, or toggling between Structured and Mapped assignment modes — the current behavior is undefined:

1. **Model change during pipeline run**: The running stage continues with the old model. New config only takes effect on the *next* pipeline run. No feedback to the user.
2. **Structured ↔ Mapped mode switch**: All model selectors spin/disable during pipeline runs. The user cannot reconfigure models until the pipeline finishes (which may take hours).
3. **No graceful transition**: The only options today are "wait for completion" or "cancel and lose progress."

## Goal

Allow users to change LLM configuration at any time. The pipeline should:
1. Pause the current stage at the next safe checkpoint
2. Apply the new model configuration
3. Resume from where it left off with the new model

---

## Existing Infrastructure (Already Built)

### State Machine (state_machine.py)
The pipeline state machine already supports the full pause/resume lifecycle:

```
RUNNING → PAUSING → PAUSED → RUNNING (resume)
```

- `Event.PAUSE` → transitions RUNNING → PAUSING
- `Event.STAGE_FLUSHED` → transitions PAUSING → PAUSED
- `Event.RESUME` → transitions PAUSED → RUNNING

### Orchestrator (orchestrator.py)
Fully implemented pause/resume methods:

- `pause_fast_sync(project_id)` / `pause_deep_enrichment(project_id)`
- `resume_paused(project_id, group)` — resumes from the paused stage index
- `_pause_group()` — signals worker via `cancel_token`, creates checkpoint, transitions state

### Worker Cooperation (workers.py)
All 6 LLM workers accept `cancel_token=slot.cancel_token`:
- `InferredEdgesAnalyzer.run(cancel_token=...)`
- `TraceAugmenter.run(cancel_token=...)`
- `EpistemicEnricher.run(cancel_token=...)`
- `GroupReasoningEngine.run(cancel_token=...)`
- `ClusterSynthesizer.run(cancel_token=...)`
- `DeepeningLoop.run(cancel_token=...)`

Each worker writes incremental results to disk (JSONL append), so resuming after pause skips already-processed items.

### REST API (pipeline.py)
Endpoints already exist:
- `POST /projects/{id}/pipeline/pause` — pauses a running group
- `POST /projects/{id}/pipeline/resume` — resumes a paused group

### Checkpointing (orchestrator.py)
`_create_checkpoint_if_needed()` backs up trace files before destructive stages. Used during pause to ensure safe resume.

---

## What Needs to Be Built

### Phase 1: Model Swap via Pause-Resume (Backend)

**New method: `PipelineOrchestrator.swap_model(project_id, group)`**

```python
def swap_model(self, project_id: str, group: str) -> bool:
    """Pause the current stage, reload LLM config, and resume.
    
    The resumed stage will pick up the new model configuration
    because workers call _get_llm_client_for_task() at stage start,
    not at group start.
    """
    paused = self._pause_group(project_id, group)
    if not paused:
        return False
    
    # Clear any cached LLM clients so next stage start reads fresh config
    self._invalidate_llm_cache(project_id)
    
    # Resume from the same stage — worker will re-read config
    return self.resume_paused(project_id, group)
```

**Key insight**: Workers already call `WorkerFactory._get_llm_client_for_task()` at the start of each stage, which reads from `_load_ui_config()`. So if we pause, change config, and resume, the new stage invocation automatically picks up the new model. **No worker changes needed.**

The only concern is the *currently running* stage mid-execution. The pause signal causes the worker to flush partial results and stop. On resume, the same stage restarts but skips already-processed items (incremental design). The new model handles the remaining items.

**Estimated effort**: ~20 lines of new code in orchestrator.

### Phase 2: Frontend Model Change Triggers Swap

**AIModelsSettings.tsx / LLMAssignmentBlockCard.tsx**

When the user changes a model or endpoint while a pipeline is running:

1. Save the new config immediately (already happens)
2. Detect if the changed slot affects the currently running stage
3. If yes, call `POST /projects/{id}/pipeline/swap-model` (new endpoint)
4. Show a brief toast: "Switching model... pipeline will resume with new model"

**Slot-to-stage mapping** (already exists as `STAGE_TASK_ID` in stages.py):
| Slot | Stages Affected |
|------|----------------|
| `small_model` (Fast) | catalogue, inferred_edges, validation |
| `code_model` (Code) | inferred_edges |
| `large_model` (Thinking) | enrichment, group_reasoning, clustering, atlas, deepening |
| `embedding` | knowledge, deep_knowledge |

If the user changes the thinking model and stage 6 (enrichment) is running, trigger a swap. If stage 1 (structural/Rust) is running, no swap needed — it doesn't use that slot.

### Phase 3: Structured ↔ Mapped Mode Switch

When the user toggles between Structured and Mapped assignment modes:

1. Save the new mode to config
2. If any pipeline group is running, trigger `swap_model` for the active group
3. The resumed stages will call `_get_llm_client_for_task()` which checks `assignment_mode` and dispatches to either structured or mapped resolution

**No special handling needed** — the existing `_get_llm_client_for_task()` already checks `assignment_mode` dynamically. A pause-resume cycle is sufficient to pick up the mode change.

### Phase 4: UI Polish

- Remove `disabled` state from model selectors when pipeline is running (already partially fixed)
- Add subtle indicator: "Pipeline will use new model after current item completes"
- Add "Swap Now" button that triggers immediate pause-resume if user doesn't want to wait
- Show brief transition animation during swap (spinner → checkmark)

---

## New REST Endpoint

```
POST /projects/{project_id}/pipeline/swap-model
Body: { "group": "fast_sync" | "deep_enrichment" }
Response: { "swapped": true, "paused_at_stage": "enrichment", "resumed": true }
```

Internally calls `orchestrator.swap_model(project_id, group)`.

---

## Edge Cases

1. **Stage not using the changed model**: No swap needed. E.g., changing embedding model while enrichment (LLM) is running.
2. **Rust stages (structural, validation)**: These don't use LLM models. No swap needed.
3. **Embedding stages (knowledge, deep_knowledge)**: Use the embedding model. Swap if embedding config changes.
4. **Race condition**: User changes model twice rapidly. Second swap waits for first pause-resume to complete (lock in `_pause_group`).
5. **Swap during batched request**: The current batch completes, then the worker checks cancel_token before starting the next batch. Partial batch results are kept.

---

## Implementation Order

| Step | Scope | Effort |
|------|-------|--------|
| 1 | `swap_model()` method in orchestrator | ~20 LOC |
| 2 | `POST /pipeline/swap-model` endpoint | ~15 LOC |
| 3 | Frontend: detect running pipeline + trigger swap on config change | ~40 LOC |
| 4 | Frontend: mode switch (Structured ↔ Mapped) triggers swap | ~10 LOC |
| 5 | UI polish: toast, indicator, "Swap Now" button | ~30 LOC |

**Total estimated effort**: ~115 lines of new code. No changes to workers, state machine, or core infrastructure needed.

---

## Why This Works

The key architectural insight is that **Prep's pipeline is already designed for interruption**:

- Workers write results incrementally (JSONL append)
- Cancel tokens enable cooperative stopping
- Resume skips already-processed items
- LLM clients are resolved per-stage, not per-group

A "model swap" is simply a pause → config change → resume. The infrastructure is 100% built — we just need a thin orchestration layer on top.

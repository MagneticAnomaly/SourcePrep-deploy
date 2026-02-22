# Research: Multi-Project Model Management

**Status:** Research TODO — not yet implemented  
**Priority:** Low (relevant to power users / team setups)  
**Related:** Phase 31 (CLaRa replacement), Pipeline VRAM lifecycle

## Context

The current pipeline VRAM lifecycle assumes **one active project at a time**:
- Models are loaded before their stage group and unloaded after.
- No two models occupy VRAM simultaneously.
- `_maybe_unload_previous_model()` handles slot transitions (small→large).
- `_unload_group_models()` frees VRAM when a group finishes.

This breaks down when **multiple projects run concurrently** — a scenario
relevant to:
- Power users with multiple repos indexed simultaneously
- Team setups with a centralized CoDRAG server serving multiple users
- CI/CD integration where multiple projects queue builds

## Questions to Research

### 1. Concurrent Pipeline Runs
- Currently blocked: `_start_group()` rejects if any group for the same
  project is already active, but allows different projects to run.
- If Project A is in catalogue (small model) and Project B starts
  enrichment (large model), both models compete for VRAM.
- **Options:**
  - Global model lock: only one model loaded at a time, queue others
  - Per-GPU scheduling: track VRAM budget and schedule accordingly
  - Sequential project queue: finish one project's pipeline before starting another

### 2. Model Sharing Across Projects
- If two projects use the same small_model, the second project shouldn't
  trigger a reload.
- Need a reference-counting or "last-used" tracking mechanism.

### 3. Multi-GPU / Distributed Ollama
- Ollama can shard models across GPUs but doesn't support running
  different models on different GPUs simultaneously (as of 2024).
- With separate Ollama instances per GPU, we could route small_model
  to GPU 0 and large_model to GPU 1.
- This requires endpoint-level GPU affinity in the config.

### 4. Cloud Provider Concurrency
- OpenAI-compatible endpoints don't have VRAM concerns.
- The unload() call is already a no-op for cloud providers.
- Mixed setups (Ollama small + cloud large) need no special handling.

### 5. VRAM Budget Estimation
- Could query Ollama for model size and available VRAM before loading.
- Ollama API: `GET /api/show` returns model metadata including size.
- Compare against `GET /api/ps` (running models) for available capacity.

## Proposed Architecture (Future)

```
ModelScheduler
├── tracks: which models are loaded, by which project, on which endpoint
├── load(slot, project_id) → waits if VRAM is full, queues if needed
├── unload(slot, project_id) → ref-counted, only unloads when no project needs it
├── budget_check(model_name) → can this model fit in available VRAM?
└── per-endpoint locks → prevents two loads on same Ollama instance
```

## Implementation Notes

- The current `LLMClient.unload()` + `STAGE_MODEL_SLOT` mapping is
  sufficient for single-project use.
- Multi-project support should be a separate phase with its own
  design doc and testing plan.
- Consider adding a `--single-project` mode flag that enforces the
  current behavior and rejects concurrent pipeline runs across projects.

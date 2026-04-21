# Phase 44C: Model Awareness State Machine

> **Status:** Phase 1 (Core SM + Pipeline-Safe Mode Switch) — Building  
> **Goal:** Replace the ad-hoc VRAM lifecycle with a proper state machine that  
> handles persistent models, mixed cloud/local endpoints, VRAM pressure,  
> and pipeline-safe configuration changes.

---

## 1. Problem Statement

The current VRAM lifecycle is a set of imperative helpers scattered across
`orchestrator.py` and `server.py`:

```
_maybe_unload_previous_model()  — unloads if model identity changes between stages
_unload_group_models()          — unloads all models when a group finishes
LLMClient.unload()              — sends keep_alive=0 to Ollama (skips if always_on)
ollama_ensure_ready()           — preloads a model if not already loaded
```

**Problems with the current approach:**

1. **No awareness of what's loaded.** The orchestrator calls `_maybe_unload_previous_model`
   reactively, but has no global view of which models are in VRAM right now.

2. **`always_on` is a dumb skip.** `LLMClient.unload()` just returns early if
   `always_on=True`. But what if VRAM is full and we *need* that slot? The
   pipeline crashes instead of gracefully evicting the persistent model.

3. **Cloud models are invisible.** Cloud endpoints (OpenAI, Anthropic) don't need
   VRAM management but the orchestrator doesn't distinguish them — it tries to
   "unload" them (no-op) and "preload" them (fails silently).

4. **Mode switch is unsafe.** When the user saves a switch from Structured →
   Assigned (or vice versa), the config changes immediately. If a pipeline stage
   is mid-execution, the next `_get_llm_client_for_task()` call reads the new
   config and may resolve to a completely different model that isn't loaded.

5. **No LM Studio awareness.** LM Studio doesn't support dynamic model
   loading/unloading via API. The system can't manage it the way it manages
   Ollama. Context window is also stuck at whatever LM Studio's UI is set to.

---

## 2. State Machine Design

### 2.1 Model Slot States

Each tracked model identity `(endpoint_id, model_name)` has a state:

```
         ┌──────────┐
         │   IDLE   │  Not loaded, not needed
         └────┬─────┘
              │ acquire()
              ▼
         ┌──────────┐
         │ LOADING  │  Preload in progress (Ollama only)
         └────┬─────┘
              │ loaded
              ▼
         ┌──────────┐
         │  READY   │  Loaded in VRAM, available for inference
         └────┬─────┘
              │ task_start()
              ▼
         ┌──────────┐
         │  ACTIVE  │  Currently processing a pipeline stage
         └────┬─────┘
              │ task_end()
              ▼
         ┌──────────┐
         │  READY   │  (back to ready, may stay or be unloaded)
         └────┬─────┘
              │ release() or evict()
              ▼
         ┌──────────┐      ┌──────────┐
         │UNLOADING │ ──── │ EVICTED  │  Was persistent, force-removed
         └────┬─────┘      └────┬─────┘
              │                  │ pressure_relieved()
              ▼                  ▼
         ┌──────────┐      ┌──────────┐
         │   IDLE   │      │ LOADING  │  (auto-reload)
         └──────────┘      └──────────┘


  Special: CLOUD — always "ready", no load/unload lifecycle
```

### 2.2 ModelSlot Data Structure

```python
@dataclass
class ModelSlot:
    identity: tuple[str, str]          # (endpoint_id, model_name)
    provider: str                       # "ollama" | "lm-studio" | "openai" | ...
    endpoint_url: str
    state: ModelState                   # enum: IDLE, LOADING, READY, ACTIVE, UNLOADING, EVICTED, CLOUD
    persistent: bool                    # always_on flag
    task_id: Optional[str]             # current PrepTaskId if ACTIVE
    last_used: float                   # monotonic timestamp
    eviction_warning: bool             # True if was evicted (for UI indicator)
```

### 2.3 ModelAwareness Class (Singleton)

```python
class ModelAwareness:
    """Global singleton tracking all model states across all providers."""
    
    _slots: Dict[tuple, ModelSlot]     # identity → slot
    _lock: threading.Lock
    
    # ── Core API ──
    def acquire(self, task_id: str) -> ModelSlot
    def release(self, task_id: str) -> None
    def evict(self, identity: tuple) -> bool
    def status() -> Dict[str, Any]     # for UI/API
    
    # ── VRAM Pressure ──
    def ensure_room_for(self, identity: tuple) -> bool
    def _eviction_candidates(self) -> List[ModelSlot]
    def _reload_evicted(self) -> None
```

---

## 3. VRAM Pressure Resolution

When `acquire()` is called for a model that isn't loaded:

```
1. Is target a cloud model? → State = CLOUD, return immediately
2. Is target already READY/ACTIVE? → Return existing slot
3. Can target fit alongside currently loaded models?
   → Yes: preload target, state = LOADING → READY
   → No:
     a. Find non-persistent READY models → unload (LRU order)
     b. Still not enough? Find persistent READY models → evict (LRU order)
        - Set state = EVICTED
        - Set eviction_warning = True
        - Emit SSE event: {"type": "model_evicted", "model": "...", "reason": "vram_pressure"}
     c. Still not enough? → Error (user has too many large models configured)
4. Preload target
5. State = READY
```

### 3.1 Eviction Recovery

After a heavy task completes and releases its model:

```
1. Check _slots for any EVICTED models where persistent=True
2. For each (in original priority order):
   a. Check if there's room now
   b. If yes: preload → LOADING → READY, clear eviction_warning
   c. Emit SSE event: {"type": "model_restored", "model": "..."}
```

---

## 4. Pipeline-Safe Mode Switch

When the user clicks "Save" on the Structured ↔ Assigned toggle:

### 4.1 Frontend Flow

```
1. User clicks Save
2. Frontend calls POST /api/llm/mode-switch
   Body: { mode: "mapped" | "structured", assignment_blocks?: [...] }
3. Frontend shows "Switching mode..." indicator
4. Backend responds with { success: true, paused_groups: [...] }
5. Frontend updates config only after backend confirms
```

### 4.2 Backend Flow (`/api/llm/mode-switch`)

```python
def handle_mode_switch(new_mode, new_blocks=None):
    # 1. Snapshot current pipeline state
    pipeline_status = pipeline_orchestrator.status(project_id)
    running_groups = []
    
    # 2. Pause any active pipeline groups
    if pipeline_status["fast_sync"] and pipeline_status["fast_sync"]["is_active"]:
        pipeline_orchestrator.pause_fast_sync(project_id)
        running_groups.append("fast_sync")
    if pipeline_status["deep_enrichment"] and pipeline_status["deep_enrichment"]["is_active"]:
        pipeline_orchestrator.pause_deep_enrichment(project_id)
        running_groups.append("deep_enrichment")
    
    # 3. Write new config atomically
    update_llm_config(mode=new_mode, blocks=new_blocks)
    
    # 4. For each paused group, verify the next stage's model is available
    for group in running_groups:
        run = pipeline_orchestrator._runs.get((project_id, group))
        if run:
            next_stage = run.stages[run.current_stage_index]
            next_task = STAGE_TASK_ID[next_stage]
            # Acquire the model for the next task under the NEW config
            model_awareness.acquire(next_task)
    
    # 5. Resume paused groups
    for group in running_groups:
        pipeline_orchestrator.resume_paused(project_id, group)
    
    return {"success": True, "paused_groups": running_groups}
```

---

## 5. Provider-Specific Behavior

| Provider | Load/Unload | always_on | Context Window | Notes |
|----------|-------------|-----------|----------------|-------|
| **Ollama** | Full API support (`/api/generate` keep_alive) | ✅ Works | Set via `num_ctx` option at load time | Primary target |
| **LM Studio** | ❌ No API for load/unload | ⚠️ Ignored | ❌ Must be set in LM Studio UI (defaults 4096) | SM treats as "always loaded" — warns if model mismatch |
| **OpenAI** | N/A (cloud) | N/A | Model-dependent | SM state = CLOUD always |
| **Anthropic** | N/A (cloud) | N/A | Model-dependent | SM state = CLOUD always |
| **Google** | N/A (cloud) | N/A | Model-dependent | SM state = CLOUD always |

### 5.1 LM Studio Limitations

The state machine handles LM Studio specially:
- State is always `READY` (we can't control loading)
- `acquire()` checks if the model is actually responding via a lightweight ping
- If the loaded model doesn't match what's configured, emit a warning:
  `"LM Studio has 'modelA' loaded but task requires 'modelB' — please switch in LM Studio UI"`
- `always_on` is effectively always true (no unload capability)
- Context window warning: if the task requires >4096 tokens and provider is lm-studio,
  emit a warning suggesting the user increase the context window in LM Studio UI

---

## 6. Implementation Phases

### Phase 1: Core State Machine + Pipeline-Safe Mode Switch ← NOW
- [x] Plan document (this file)
- [ ] `src/prep/core/model_awareness.py` — ModelState enum, ModelSlot, ModelAwareness singleton
- [ ] Wire `acquire()`/`release()` into `_advance_pipeline()` and `_on_build_transition()`
- [ ] `POST /api/llm/mode-switch` endpoint with pause→write→verify→resume flow
- [ ] Frontend: `handleModeSave()` calls the new endpoint instead of directly writing config

### Phase 2: VRAM Pressure + Eviction
- [ ] `ensure_room_for()` with LRU eviction of non-persistent then persistent models
- [ ] Eviction recovery after heavy task completes
- [ ] SSE events for eviction/restoration
- [ ] UI: eviction warning badge (⚠) on AI Gateway model cards

### Phase 3: Provider-Specific Intelligence
- [ ] LM Studio model mismatch detection and warning
- [ ] LM Studio context window warning
- [ ] Cloud provider always-ready optimization (skip preload entirely)
- [ ] Ollama `num_ctx` passthrough on preload

---

## 7. Integration Points

### Existing Code Modified

| File | Change |
|------|--------|
| `orchestrator.py` `_advance_pipeline()` | Replace `_maybe_unload_previous_model()` with `model_awareness.acquire()` |
| `orchestrator.py` `_on_build_transition()` | Call `model_awareness.release()` on stage completion |
| `orchestrator.py` `_unload_group_models()` | Replace with `model_awareness.release_group()` |
| `server.py` | Add `POST /api/llm/mode-switch` endpoint |
| `llm_client.py` `unload()` | Delegate to `model_awareness.release()` instead of direct Ollama call |

### New Files

| File | Purpose |
|------|---------|
| `src/prep/core/model_awareness.py` | State machine singleton |
| `docs/Phase44_LLM-Mapping/MODEL_AWARENESS_STATE_MACHINE.md` | This plan |

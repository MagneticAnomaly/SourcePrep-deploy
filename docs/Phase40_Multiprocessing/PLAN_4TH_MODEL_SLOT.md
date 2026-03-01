# Phase 40B: 4th Model Slot (Deep-Coder) + Stage 11 Planning

> **Status:** Planning only — not building yet.  
> **Goal:** Add a 4th model slot for deep code analysis and an optional 11th  
> pipeline stage for high-quality edge re-analysis during deep enrichment.

---

## 1. Problem Statement

The current pipeline has 3 model slots and 10 stages:

```
Model Slots:
  fast_model  → Stage 3 (catalogue)           e.g. qwen3:4b-instruct
  code_model  → Stage 2 (inferred edges)      e.g. qwen3-coder:30b
  deep_model  → Stages 6-9 (epistemic, etc.)  e.g. qwen3.5:27b

Pipeline:
  Group A — Fast Sync (stages 1-5):  structural, inferred_edges, catalogue, validation, knowledge
  Group B — Deep Enrichment (6-10):  epistemic, clustering, atlas, deepening, deep_knowledge
```

**The tension:** Stage 2 (inferred edges) is in the **fast sync group** but may
use a large coder model (30b+). This slows down the fast iteration loop that's
meant to be snappy for incremental code changes.

**When it matters:**
- **Initial indexing:** 4000+ files × slow coder model = very long fast sync
- **Incremental changes:** Only 2-3 changed files → fast even with a big coder
- **User expectation:** Fast sync should complete in seconds for small changes

**The opportunity:** A smarter coder model during deep enrichment could discover
edges that the fast model missed, improving graph quality without slowing fast sync.

---

## 2. Proposed Architecture: 4 Model Slots

```
Model Slots (4):
  fast_model       → Stage 3 (catalogue)
  code_model       → Stage 2 (inferred edges, fast sync)
  deep_model       → Stages 6-9 (epistemic, clustering, deepening)
  deep_code_model  → Stage 11 (deep edge re-analysis) [NEW]
```

### Fallback Chain

Each slot falls back gracefully if not configured:

```
deep_code_model → code_model → deep_model → fast_model
code_model      → fast_model
deep_model      → (required — no fallback, skip deep stages if missing)
fast_model      → (required — no fallback)
```

### Concurrency Settings (4 slots)

```
pipeline_config:
  llm_concurrency_fast: 1       # Stage 3
  llm_concurrency_code: 1       # Stage 2
  llm_concurrency_deep: 1       # Stages 6-9
  llm_concurrency_deep_code: 1  # Stage 11 [NEW]
```

---

## 3. Stage 11: Deep Edge Re-Analysis

### Purpose

Re-run inferred edge analysis with a smarter model during the deep enrichment
pass. This catches edges that the fast coder model missed:
- Complex cross-language patterns
- Subtle interface implementations
- Config-driven dependencies that require architectural understanding

### When It Runs

Stage 11 runs after epistemic enrichment (Stage 6) and before clustering
(Stage 7), because:
1. Epistemic data provides domain tags and architecture layers
2. These can be used as additional context in edge prompts
3. New edges feed into clustering for better subsystem grouping

### Proposed Stage Order (11 stages)

```
Group A — Fast Sync (stages 1-5):
  1. structural        Rust: AST parse
  2. inferred_edges    LLM (code_model): fast edge discovery
  3. catalogue         LLM (fast_model): file/symbol summaries
  4. validation        Rust: relationship validation
  5. knowledge         Embedding: fast-pass metadata

Group B — Deep Enrichment (stages 6-11):
  6. epistemic         LLM (deep_model): deep reasoning
  7. deep_edges        LLM (deep_code_model): edge re-analysis [NEW]
  8. clustering        LLM (deep_model): module-level synthesis
  9. atlas             LLM (deep_model): codebase orientation
 10. deepening         LLM (deep_model): re-enrich stale nodes
 11. deep_knowledge    Embedding: re-embed with deep metadata
```

### What Stage 11 (Deep Edges) Does

1. Load all existing inferred edges from Stage 2
2. Load epistemic entries (domain tags, architecture layers, subsystems)
3. For each file, re-run edge analysis with:
   - The deep_code_model (smarter than the fast coder)
   - Additional context: epistemic domain tags, architecture layers, neighbor summaries
   - Higher confidence thresholds (only keep high-quality edges)
4. Merge results: new edges are added, existing edges may be upgraded in confidence
5. Write updated `trace_inferred_edges.jsonl`

### Incremental Behavior

- **First run:** Analyzes all files (same as Stage 2 but with deep model)
- **Subsequent runs:** Only re-analyzes files whose source hash changed OR
  whose epistemic data changed since last deep edge pass
- **Manifest:** Separate `trace_deep_edges_manifest.json` to track what's been
  deeply analyzed

---

## 4. Multi-Backend VRAM Management

### The Problem

Users may run Ollama and LM Studio on the **same GPU** (shared unified memory).
Currently, CoDRAG only manages Ollama model loading/unloading. With LM Studio
as a second backend, we need coordinated VRAM management.

### Two Deployment Modes

**Mode 1: Same GPU (unified VRAM) — DEFAULT**

Both Ollama and LM Studio share the same memory pool. CoDRAG must:
- Unload Ollama models before loading LM Studio models (and vice versa)
- Track which backend currently has a model loaded
- Never load models on both backends simultaneously

```
Settings:
  backends:
    - name: "ollama"
      endpoint: "http://localhost:11434"
      type: "ollama"
      gpu_group: "default"        # Same GPU group = shared VRAM
    - name: "lmstudio"
      endpoint: "http://192.168.86.22:1234"
      type: "openai-compatible"
      gpu_group: "default"        # Same GPU group = shared VRAM
```

**Mode 2: Separate GPUs (dedicated VRAM)**

Different backends on different GPUs (e.g., one Mac Studio running Ollama,
another running LM Studio, or one NVIDIA GPU per backend). Models can
be loaded simultaneously.

```
Settings:
  backends:
    - name: "ollama-local"
      endpoint: "http://localhost:11434"
      type: "ollama"
      gpu_group: "gpu-0"         # Dedicated GPU
    - name: "lmstudio-remote"
      endpoint: "http://192.168.86.100:1234"
      type: "openai-compatible"
      gpu_group: "gpu-1"         # Different GPU
```

### LM Studio Load/Unload API

LM Studio exposes model management via its REST API:

**Check model state:**
```
GET /api/v0/models
→ Returns list with "state": "loaded" | "not-loaded" for each model
```

**Load a model (via CLI or implicit on first request):**
```
lms load <model-key> --context-length 32768 --gpu max
```

**Unload a model:**
```
lms unload <model-key>
```

**Via REST (implicit):** Sending a chat completion request to a model that's
not loaded will auto-load it. Setting `--ttl` on load will auto-unload after
idle timeout.

### VRAM Lifecycle Manager Changes

The current `_maybe_unload_between_stages()` in `pipeline_orchestrator.py`
only handles Ollama. It needs to be extended:

```python
class VRAMLifecycleManager:
    """Manages model loading/unloading across multiple backends."""
    
    def __init__(self, backends: List[BackendConfig]):
        self.backends = backends
        self.gpu_groups: Dict[str, List[BackendConfig]] = {}
        # Group backends by GPU
        for b in backends:
            self.gpu_groups.setdefault(b.gpu_group, []).append(b)
    
    def prepare_for_model(self, model_slot: str, backend: str):
        """Ensure the target backend has room for the model.
        
        If the backend shares a GPU group with other backends,
        unload models from ALL backends in that group first.
        """
        target = self.get_backend(backend)
        group = self.gpu_groups[target.gpu_group]
        
        for b in group:
            if b.name != backend:
                self.unload_all(b)  # Free VRAM on shared GPU
        
    def unload_all(self, backend: BackendConfig):
        """Unload all models from a backend."""
        if backend.type == "ollama":
            # Existing Ollama unload via /api/generate keep_alive=0
            ...
        elif backend.type == "openai-compatible":
            # LM Studio: lms unload or TTL-based
            ...
```

---

## 5. Settings UI Changes

### Model Configuration (AI Models tab)

Current:
```
Fast Model:   [provider] [endpoint] [model name]
Code Model:   [provider] [endpoint] [model name]  (optional)
Deep Model:   [provider] [endpoint] [model name]
```

Proposed:
```
Fast Model:        [provider] [endpoint] [model name]
Code Model:        [provider] [endpoint] [model name]  (optional)
Deep Model:        [provider] [endpoint] [model name]
Deep Code Model:   [provider] [endpoint] [model name]  (optional, falls back to code → deep)
```

### Backend Configuration (new section in Global tab)

```
Inference Endpoints:
  ┌─────────────────────────────────────────────────────────┐
  │ Endpoint 1: Local Ollama                                │
  │   URL: http://localhost:11434                           │
  │   Hardware Profile: [Apple Silicon (Unified) ▼]         │
  │   Resource Pool: [Pool 1 ▼]                             │
  │                                                         │
  │ Endpoint 2: Local LM Studio                             │
  │   URL: http://192.168.86.22:1234                        │
  │   Hardware Profile: [Apple Silicon (Unified) ▼]         │
  │   Resource Pool: [Pool 1 ▼]   ← same pool = shared VRAM │
  │                                                         │
  │ Endpoint 3: Remote Server (Tailscale)                   │
  │   URL: http://100.100.100.100:11434                     │
  │   Hardware Profile: [Dedicated GPU (NVIDIA/AMD) ▼]      │
  │   Max Concurrency: [ 2 ]                                │
  │   Resource Pool: [Pool 2 ▼]                             │
  │                                                         │
  │ [+ Add Endpoint]                                        │
  └─────────────────────────────────────────────────────────┘
```

*Note: The global "Pipeline Performance" concurrency sliders will be completely removed, as concurrency is now dictated by the Hardware Profile assigned to each Endpoint (see `PLAN_HARDWARE_PROFILES.md`).*

---

## 6. LM Studio "Channel Error" Investigation

The qwen3.5-27b model crashes with "Channel Error" after prompt processing
completes (100%). This happens on both attempts. Possible causes:

1. **Memory pressure:** The BF16 model (54.7 GB) + KV cache may exceed
   available memory when other models are also downloaded in LM Studio
2. **MLX compatibility:** The qwen3.5 architecture (Gated DeltaNet hybrid
   attention) may have issues with the current MLX-VLM version
3. **Context length:** The model may be trying to allocate a large default
   context window that doesn't fit

**Troubleshooting steps:**
- Try loading with explicit context length: `lms load qwen3.5-27b --context-length 4096`
- Try the 4-bit or 8-bit quantization instead of BF16
- Check Activity Monitor for memory pressure during loading
- Try unloading ALL other models first to maximize available RAM

---

## 7. Implementation Phases (When We Build)

### Phase A: Deep-Coder Model Slot (Backend only)

1. Add `deep_code_model` to `llm_config` schema in settings store
2. Add `STAGE_MODEL_SLOT` mapping for the new stage
3. Add `llm_concurrency_deep_code` to pipeline config
4. Update `_get_llm_concurrency()` to support `"deep_code"` stage
5. Update `LLMClient` factory in `WorkerFactory` to resolve deep_code_model

### Phase B: Stage 11 — Deep Edge Re-Analysis

1. Create `deep_inferred_edges.py` (extends `InferredEdgesAnalyzer`)
2. Add epistemic context to edge prompts (domain tags, architecture layers)
3. Add `deep_edges_manifest.json` for incremental tracking
4. Register in `pipeline_orchestrator.py` as stage between epistemic and clustering
5. Wire into `HeadlessWorkerFactory` for headless/benchmark runs

### Phase C: Multi-Backend VRAM Management

1. Add `backends` config to settings store (endpoint, type, gpu_group)
2. Implement `VRAMLifecycleManager` with GPU group awareness
3. Add LM Studio load/unload support (`/api/v0/models` state check, TTL-based unload)
4. Update `_maybe_unload_between_stages()` to use the new manager
5. Add Backend Configuration UI section to Global tab

### Phase D: UI for 4th Model Slot

1. Add Deep Code Model fields to AI Models settings
2. Add 4th concurrency dropdown to Pipeline Performance section
3. Add Backend Configuration section to Global tab

---

## 8. Recommended Model Assignments (When Built)

### 128GB Mac Studio — All 4 Slots

```
Fast Model:        qwen3:4b-instruct         (Ollama, 2.5 GB)
Code Model:        qwen3:4b-instruct         (Ollama, same — fast sync stays fast)
Deep Model:        qwen3.5:27b MLX BF16      (LM Studio, 54.7 GB)
Deep Code Model:   qwen3-coder:30b           (Ollama, 18 GB — runs during deep pass)

GPU Group:         "default" (all shared)
Lifecycle:         Ollama unloads before LM Studio loads (and vice versa)
```

**Why this works:**
- Fast sync (stages 1-5): Uses only Ollama models (4b fast + 4b coder) — very fast
- Deep enrichment (stages 6-11): Transitions to LM Studio for 27b deep reasoning,
  then back to Ollama for 30b deep coder, then back to LM Studio for clustering
- VRAM lifecycle manager handles load/unload transitions automatically

### 64GB MacBook Pro — 3 Slots (no deep coder)

```
Fast Model:        qwen3:4b-instruct         (Ollama)
Code Model:        (not configured — falls back to fast)
Deep Model:        qwen3.5:27b Q4_K_M        (Ollama, 17 GB)

Stage 11:          Skipped (no deep_code_model configured)
```

### NVIDIA RTX 5090 (32GB) — All 4 Slots

```
Fast Model:        qwen3:4b-instruct         (Ollama, 2.5 GB)
Code Model:        deepseek-coder:6.7b       (Ollama, 4 GB)
Deep Model:        qwen3.5:27b Q4_K_M        (Ollama, 17 GB)
Deep Code Model:   qwen3-coder:30b Q4_K_M    (Ollama, 18 GB — swapped with deep)

Concurrency:       Fast=4, Code=2, Deep=2, Deep-Code=1
```

---

## 9. Open Questions

1. **Should Stage 11 re-analyze ALL files or only files where epistemic data
   changed significantly?** Re-analyzing all files with a deep model is expensive.
   A targeted approach (only files where domain tags or architecture layer differ
   from the fast pass) would be more efficient.

2. **Edge merging strategy:** When deep edges conflict with fast edges (different
   confidence, different edge kind), which wins? Options:
   - Deep always wins (higher trust)
   - Higher confidence wins (regardless of source)
   - Keep both with a "source" tag (fast vs deep)

3. **LM Studio stability:** The "Channel Error" with qwen3.5-27b needs
   investigation before we can rely on LM Studio for production deep reasoning.

4. **Model transitions cost time:** Each Ollama↔LM Studio transition requires
   unloading one model and loading another. On a 128GB Mac Studio, loading a
   27B BF16 model takes ~15-30 seconds. With 4 model slots, the deep pass
   could have 3-4 transitions = 60-120s of overhead. Is this acceptable?

5. **Should the 4th slot be "deep_code" or "deep_fast"?** The same argument
   applies to the catalogue stage — a deep fast model could produce better
   summaries during the deep pass. But adding a 5th slot feels excessive.

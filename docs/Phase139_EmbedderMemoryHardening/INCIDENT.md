# Phase 139 — Incident Record

## Summary

On **2026-05-15** at ~09:49 EDT, Eric noticed the SourcePrep daemon
holding **97 GB** in Activity Monitor on a 128 GB Mac while believing
all LLM work was running on cloud Ollama (no local GPU/embedding).
A pipeline task had "stopped" earlier but memory was not released.

Investigation confirmed:

1. The daemon (`prep serve --port 8400`, PID 84689) had a **physical
   footprint of 100.8 GB** (peak 100.8 GB) — `sample(1)`, `top -l 1`.
2. The daemon was in **`STATE: stuck`**, 0 % CPU, 66 threads.
3. The main thread was blocked inside ONNX Runtime's CoreML execution
   provider, deep in `-[MLNeuralNetworkEngine setEspressoBlobShapes:...]`.
4. Active dispatch queues included `com.apple.CoreMLNNProcessingQueue`,
   `com.apple.CoreMLBatchProcessingQueue`, `com.Metal.CommandQueueDispatch`,
   and **10+ `H11ANEServicesThread`** (Apple Neural Engine).
5. System-wide: 116.72 GB memory used, **71.20 GB compressed**, **77.13 GB
   swap used** of 80 GB total — system was on the brink.

The user's intuition was correct: embeddings (not LLMs) were the cause.

## Why the user expectation was wrong

`embedding_source` resolution priority in
`src/prep/services/embedder_factory.py`:

1. Explicit project-level override
2. Dashboard `llm_config.embedding.source` in `ui_config.json`
3. CLI `--model` / `--ollama-url`
4. **Default: `NativeEmbedder` (local ONNX, CoreML EP on macOS)**

There is **no link** between "all LLM endpoints set to cloud" and the
embedder. The embedder is a separate dimension and defaults to local.

## Contributing causes (root cause is multifactorial)

### 1. No embedder singleton — multiple loaded sessions

`create_embedder()` builds a fresh `NativeEmbedder()` on every call.
Each instance owns its own `_session = ort.InferenceSession(...)` which
on macOS lazily allocates CoreML buffers + ANE-pinned memory.

Call sites (verified via grep):

- `src/prep/services/build_manager.py:143, 176, 219, 395, 625` (5×)
- `src/prep/services/pipeline/workers/__init__.py:939`
- `src/prep/services/pipeline/orchestrator.py:4395`
- `src/prep/api/routers/trace_routes/enrichment.py:1150`
- `src/prep/api/routers/llm.py:320, 362`
- `src/prep/services/headless_runner.py:135`

Each lazily loaded session has its own CoreML allocators. Nothing
deduplicates.

### 2. No release — `_session` is never nulled

`grep -rn "_session = None|del self._session|gc.collect|close()" src/prep/core/embedder.py`
returns nothing inside the embedder. No `__del__`, no `close()`,
no idle eviction. CoreML/ANE memory stays pinned until process exit.

### 3. Batch-scaling is upside-down on big machines

`src/prep/core/embedder.py:429-451` `_memory_scaled_batch_size()`:

| System RAM | GPU batch | CPU batch |
|---|---|---|
| ≤ 16 GB | 64 | 16 |
| ≤ 64 GB | 96 | 24 |
| **≥ 65 GB** | **128** | **32** |

Larger machines get **bigger** batches. Combined with the model's
`MAX_LENGTH = 8192` (line 473) and worst-case sequence padding,
the per-batch activation footprint on the BERT-style encoder
explodes. (Exact math will be in RESEARCH.md.)

### 4. No memory ceiling / no cap knob

There is no `PREP_EMBED_MAX_RAM_GB`, no `max_batch_tokens`, no
RSS-based throttle. The only effective lever is dashboard config.

### 5. CoreML EP can stall

The stuck stack (`setEspressoBlobShapes`) suggests CoreML re-shaping
its compute graph and not returning. This is consistent with reports
of CoreML EP hangs on shape changes — to be confirmed in RESEARCH.md.

### 6. `--cloud-only` is not a thing

There is no user-facing knob that says "do not load any local
inference model." Users who route all LLMs to a cloud endpoint
reasonably assume that includes embeddings.

## Evidence artifacts

- `sample 84689 1` output (saved at `/tmp/sample_84689.txt` at the time,
  may be gone after reboot). Key excerpts captured here:

  ```
  Physical footprint:         100.8G
  Physical footprint (peak):  100.8G
  ...
  753 Thread_109685652   DispatchQueue_4858: com.apple.CoreMLNNProcessingQueue
  753 Thread_109696327   DispatchQueue_15734: com.apple.CoreMLBatchProcessingQueue
  753 Thread_109710238   DispatchQueue_20976: com.Metal.CommandQueueDispatch
  753 Thread_109732356: H11ANEServicesThread   (×10+)
  ```

  Terminal call site under the main thread:

  ```
  onnxruntime::InferenceSession::Run(...)
    → ExecuteThePlan(...)
    → LaunchKernelStep::Execute(...)
    → CoreMLExecutionProvider::Compile(...) [lambda $_3]
    → onnxruntime::coreml::Execution::Predict(...)
    → -[MLDelegateModel predictionFromFeatures:options:error:]
    → -[MLNeuralNetworkEngine predictionFromFeatures:options:error:]
    → -[MLNeuralNetworkEngine evaluateInputs:options:error:]
    → -[MLNeuralNetworkEngine resetSizes:error:]
    → -[MLNeuralNetworkEngine resetSizesNoAutoRelease:error:]
    → -[MLNeuralNetworkEngine setEspressoBlobShapes:widths:heights:ks:batches:sequences:ranks:error:]
  ```

- `top -l 1 -pid 84689`:
  `Python  101G  N/A  0.0  66  stuck`

- System: `vm.swapusage: total=81920.00M used=80795.69M free=1124.31M`

## Resolution path forward

A. **Immediate (done):** daemon killed and restarted. Memory and swap
   recovered (~48 GB swap still draining at time of writing).

B. **Structural fixes:** see `IMPLEMENTATION_PLAN.md` after research.

## Followups not in scope of Phase 139

- Two orphan pytest processes were found running (PID 65960 for 9 d,
  PID 87429 for 1 d 20 h). Small footprint but worth a separate cleanup
  pass.
- Daemon should refuse to start if `vm.swapusage` shows <5 % free —
  general dev-environment safety net, not embedder-specific.

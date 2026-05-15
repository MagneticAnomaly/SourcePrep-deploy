# Phase 139 — Research Synthesis

Three parallel research streams: (1) ONNX Runtime + CoreML EP memory
lifecycle, (2) production embedding-service patterns, (3) transformer
inference memory math. This file consolidates the findings and resolves
contradictions before we propose code changes.

> **Bottom line up front.** Our 100 GB footprint is not a single bug; it
> is three independently-documented failure modes compounding on the
> same code path:
>
> 1. ONNX Runtime's CoreML EP **does not reliably return CoreML/ANE
>    memory to the OS** after `del session` — open since 2023, still
>    open in late 2025 (`#26831`, `#22007`, `#14455`).
> 2. **Dynamic input shapes** cause Apple's Espresso engine to
>    recompile per shape and re-allocate peak buffers; macOS 15.0 has
>    documented hangs in the recompile path — matches our stuck
>    `setEspressoBlobShapes` stack.
> 3. Our batch policy **scales upward** on big machines
>    (`batch=128, seq=8192`) and the resulting `(B, heads, S, S)` softmax
>    matrix at fp32 is **~103 GB by itself** — almost exactly the
>    observed footprint.
>
> The fix is not "tune CoreML harder." It's: **fixed shapes + token-
> budget batching + a process-wide singleton with explicit release**,
> plus a real cloud-only escape hatch.

---

## 1. ONNX Runtime + CoreML execution provider

### 1.1 Memory does not return after session destruction

ONNX Runtime's Python binding has **no public `close()`/`Dispose()`** —
release is implicit on garbage collection. Multiple open issues report
that even `del session; gc.collect()` does not return RSS to the OS:

- [#26831 — Memory leak when destroying InferenceSession (Dec 2025, open)](https://github.com/microsoft/onnxruntime/issues/26831)
  ORT 1.23.2: `ReleaseSession` + `ReleaseEnv` does not reclaim memory; the
  destructor depends on implicit-member-destruction that doesn't run.
- [#14590 — Destroying an inference session without exiting the Python process](https://github.com/microsoft/onnxruntime/issues/14590)
- [#12207 — How to release memory after Inference session run in Python](https://github.com/microsoft/onnxruntime/issues/12207)
  Repeated session construction adds ~260 MB per session, unreleased.

CoreML-specific:

- [#14455 — Memory leak in C++ API with Core ML backend (Jan 2023)](https://github.com/microsoft/onnxruntime/issues/14455) +
  [commit ce93987 — Add autoreleasepool block around CoreML API calls](https://github.com/microsoft/onnxruntime/runs/11432452468) —
  the EP creates Objective-C autoreleased objects from C++; without a
  drained `@autoreleasepool` they pin until process exit. The commit
  wrapped *some* sites; others remain unwrapped per the original
  reporter.
- [#22007 — Context leak detected with CoreMLExecutionProvider (Sep 2024)](https://github.com/microsoft/onnxruntime/issues/22007) —
  matches the literal log line `Context leak detected, msgtracer returned -1`
  visible in `.sourceprep/logs/pipeline_*.log` on our box.

**Implication:** restart-to-reclaim is the documented status quo. We
cannot rely on Python-side cleanup to bring the 100 GB back.

### 1.2 Dynamic shapes are an anti-pattern on Apple silicon

CoreML EP allows dynamic shapes by default
([CoreML EP docs](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html))
but the same paragraph warns "performance may be negatively impacted."
The actual cost is much worse than "performance":

- Apple's coremltools docs: with `RangeDim`, **ANE recompiles every time
  a new shape is fed**. `EnumeratedShapes` (≤128 fixed shapes) compiles
  once per shape *at load* and is the only path that keeps ANE engaged.
  ([Flexible Input Shapes](https://apple.github.io/coremltools/docs-guides/source/flexible-inputs.html))
- [coremltools #2370 — Flexible Input Shapes on Neural Engine](https://github.com/apple/coremltools/issues/2370) —
  `ReshapeFrequency.Frequent` doesn't actually keep `RangeDim` on ANE.
  Throughput collapses from 375 it/s to 60 it/s on non-default shapes.
- [Apple Dev Forum 763561 — CoreML crash on macOS 15.0 (24A335)](https://developer.apple.com/forums/thread/763561) —
  hangs in `MLModel` load + Espresso AOT recompile in macOS 15+.
  Our box is on macOS 15.0.

`setEspressoBlobShapes:widths:heights:ks:batches:sequences:ranks:error:`
is the private method `MLNeuralNetworkEngine` calls **when it has to
re-bind input/intermediate buffers to a new shape**
([iOS-Header MLNeuralNetworkEngine.h](https://github.com/xybp888/iOS-Header/blob/master/13.0/Frameworks/CoreML.framework/MLNeuralNetworkEngine.h)).
Being blocked there in `sample(1)` is exactly the symptom you'd expect
from a shape-driven re-bind that doesn't return. Concurrent CoreML
usage from multiple threads has also been reported to deadlock
([whisper.cpp #779](https://github.com/ggml-org/whisper.cpp/issues/779)).

ORT ships
[`onnxruntime.tools.make_dynamic_shape_fixed`](https://onnxruntime.ai/docs/tutorials/mobile/helpers/make-dynamic-shape-fixed.html)
specifically to bake fixed shapes ahead of time.

### 1.3 Provider options matter — our current config uses none

Documented [CoreMLExecutionProvider options](https://github.com/microsoft/onnxruntime/blob/main/include/onnxruntime/core/providers/coreml/coreml_provider_factory.h):

| Option | Values | Conservative pick |
|---|---|---|
| `MLComputeUnits` | `ALL`, `CPUOnly`, `CPUAndGPU`, `CPUAndNeuralEngine` | `CPUAndGPU` — skips ANE recompile + H11ANEServices hang |
| `ModelFormat` | `NeuralNetwork` (default), `MLProgram` | `MLProgram` (macOS 12+) — newer code path |
| `RequireStaticInputShapes` | `0` (default), `1` | `1` — dynamic-shape nodes fall back to CPU instead of recompile |
| `ModelCacheDirectory` | path | set a stable path — avoids recompiling `.mlmodelc` on every session |
| `SpecializationStrategy` | `Default`, `FastPrediction` | `FastPrediction` on macOS 14+ |

We pass none of these (verified: `core/embedder.py:553-571` just calls
`providers=providers` with the bare provider list).

Also worth noting: **CoreML EP silently converts weights to FP16**
([ONNX Runtime &amp; CoreML May Silently Convert to FP16](https://ym2132.github.io/ONNX_MLProgram_NN_exploration)).
So the model is already running at half precision on macOS regardless
of what we ship.

### 1.4 Per-call leaks are output-proportional

[Apple Dev Forum 692425](https://developer.apple.com/forums/thread/692425) +
[coremltools #1312](https://github.com/apple/coremltools/issues/1312) —
a `[1,3,3840,2160]` output leaks ~91.7 MB **per inference** without an
autoreleasepool wrap. The leak is proportional to output size. For
our embedder at batch 128 × seq 8192 × hidden 768 × fp32 = **3.2 GB
per call**, and even a fraction leaking per call reaches 100 GB inside
a single pipeline run.

[Apple Dev Forum 749640](https://developer.apple.com/forums/thread/749640):
peak RAM of 1.7–2.5 GB on 100 MB models is "normal" per Apple
engineers. Our model is 274 MB.

### 1.5 What works in production (CoreML EP path)

The convergent recommendation across ORT issues + Apple docs:

1. **One persistent InferenceSession**, never recreate.
2. **Fixed input shape** (`make_dynamic_shape_fixed`,
   `RequireStaticInputShapes=1`), pad inputs to that shape.
3. **Pre-allocated `io_binding`** so output buffers are reused.
4. **`MLComputeUnits=CPUAndGPU`** unless ANE is verified working for
   your model.
5. **`ModelCacheDirectory=<stable path>`** so the `.mlmodelc` compile
   happens once.
6. For deterministic reclaim, **process-level isolation** — run
   inference in a subprocess that can be killed.

---

## 2. Production embedding-service patterns

### 2.1 Singleton is the universal pattern

Every production embedding stack ships **one model handle per process**:

- ONNX Runtime's `InferenceSession.run()` is documented thread-safe and
  releases the GIL — true parallelism from a single shared session.
  ([#114](https://github.com/microsoft/onnxruntime/issues/114),
  [discussion #10107](https://github.com/microsoft/onnxruntime/discussions/10107))
  Session **construction** holds the GIL, so multiple sessions don't
  help and just multiply memory.
- HuggingFace Text Embeddings Inference (TEI) has a single backend
  instance behind a router.
  ([TEI architecture](https://deepwiki.com/huggingface/text-embeddings-inference))
- sentence-transformers + FastAPI: documented recipe is
  `get_model()` singleton in lifespan, or `gunicorn --preload` for
  fork-based workers.
  ([Zilliz FAQ](https://zilliz.com/ai-faq/how-do-you-deploy-a-sentence-transformer-model-as-a-service-or-api-for-example-using-flask-fastapi-or-torchserve),
   [fastapi #7069](https://github.com/fastapi/fastapi/discussions/7069))
- fastembed defaults to `lazy_load=True` for multi-worker setups —
  load *after* fork, never share weights across forks.
  ([fastembed ONNX integration](https://deepwiki.com/qdrant/fastembed/4.2-onnx-runtime-integration))

We violate this in 9+ call sites (see INCIDENT.md §1). Each
NativeEmbedder() holds its own InferenceSession + CoreML arena.

### 2.2 Idle release is the contested question

Three camps:

- **Never release** (sentence-transformers, TEI, fastembed) — model
  stays resident; restart to free.
- **Sleep/suspend** (vLLM Sleep Mode, Levels 1+2) — offload weights to
  CPU RAM or discard entirely. Wake takes 0.1–6 s.
  ([vLLM Sleep Mode](https://docs.vllm.ai/en/latest/features/sleep_mode/))
- **Idle-timeout LRU** (Ollama 5 min default, LocalAI, llamactl,
  llama-swap). Standard for multi-model servers.
  ([LocalAI VRAM management](https://localai.io/advanced/vram-management/),
   [Ollama keep-alive](https://mljourney.com/ollama-keep-alive-and-model-preloading-eliminate-cold-start-latency/))

Even vLLM has reported `del LLM` not actually freeing GPU
([#1908](https://github.com/vllm-project/vllm/issues/1908),
 [#23793](https://github.com/vllm-project/vllm/issues/23793)) —
confirming Python-side close is fundamentally hard.

For SourcePrep (single-model daemon, occasional pipeline bursts), idle
timeout + explicit close at `pipeline/rebuild/stop` is the
defensible middle path.

### 2.3 Batching strategy — token budgets, not item counts

The TEI pattern is converging on:

- `--max-batch-tokens` default **16384** instead of fixed batch size.
  The dispatcher accumulates incoming texts until the budget is hit.
  ([TEI CLI args](https://huggingface.co/docs/text-embeddings-inference/cli_arguments))
- Length-sorted batching with **dynamic padding** to the longest item
  in the batch — sentence-transformers already does this internally
  with `length_sorted_idx`.
  ([sentence-transformers efficiency](https://sbert.net/docs/sentence_transformer/usage/efficiency.html))
- Power-of-two bucket boundaries `[128, 256, 512, 1024, 2048, 4096,
  8192]` — universal in Triton, fairseq, HF.
  ([HF padding/truncation](https://huggingface.co/docs/transformers/en/pad_truncation),
   [Smart Batching tutorial](https://mccormickml.com/2020/07/29/smart-batching-tutorial/),
   [Triton ragged batching](https://github.com/triton-inference-server/server/blob/main/docs/user_guide/ragged_batching.md))
- MongoDB engineering report token-count batching for embeddings
  delivers **up to 8× throughput** vs flat `batch_size`.
  ([MongoDB blog](https://www.mongodb.com/company/blog/engineering/token-count-based-batching-faster-cheaper-embedding-inference-for-queries))

A subtle ONNX knob: `enable_cpu_mem_arena=False` in SessionOptions
*"will give significant memory savings during inference"* for small
models on CPU, at a small latency cost.
([ORT issue #11627](https://github.com/microsoft/onnxruntime/issues/11627),
 [ORT memory docs](https://onnxruntime.ai/docs/performance/tune-performance/memory.html))

### 2.4 Hard memory ceilings are not viable in Python

- `resource.setrlimit(RLIMIT_RSS, ...)` is **not honored** by modern
  Linux kernels.
- `RLIMIT_AS` (virtual address space) breaks NumPy/zlib because they
  probe `sys.maxsize` at startup.
  ([Python resource docs](https://docs.python.org/3/library/resource.html),
   [cpython #119881](https://github.com/python/cpython/issues/119881))
- macOS has no equivalent.

The standard pattern is a **psutil watchdog** that polls
`process.memory_info().rss`, refuses new batches above a soft
threshold, and (if idle release is enabled) drops the session.
gunicorn does the same via `--max-requests` / `--max-memory`.
([psutil docs](https://psutil.readthedocs.io/),
 [Python memory leak detection](https://www.techbuddies.io/2026/02/21/top-5-python-memory-leak-detection-techniques-for-long-running-services/))

### 2.5 Cloud-only mode — `/v1/embeddings` is the de-facto contract

Every agentic tool converges on **OpenAI-compatible HTTP endpoints**:

- Continue.dev: `provider: openai`, `apiBase: <url>`.
  ([Continue.dev Embed Role](https://docs.continue.dev/customize/model-roles/embeddings))
- Cursor: OpenAI-compatible, **HTTPS only**.
  ([Custom models in Cursor](https://github.com/bilal77511/custom-models-in-cursor-IDE))
- Ollama exposes `/v1/embeddings` precisely so it's a drop-in
  OpenAI replacement.
  ([Ollama OpenAI compat](https://github.com/ollama/ollama/issues/2416))
- TEI exposes the same shape.

Config shape: `{ provider: "openai", apiBase: "...", apiKey: "...", model: "..." }`.

### 2.6 Concrete numbers for `nomic-embed-text-v1.5`

- 137M params, 768-d, 8192-context.
- Disk: **274 MB** FP32 ONNX.
- Working set per session: **~315 MB** at fp16
  ([HF discussion](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/discussions/15)).
- **Known issue:** Ollama 0.12.10 crashes on macOS with
  `nomic-embed-text-v1.5`
  ([ollama #13054](https://github.com/ollama/ollama/issues/13054),
   [ollama #3029 — hangs under load](https://github.com/ollama/ollama/issues/3029)).
  Affects cloud-routing-to-Ollama-cloud option below.

---

## 3. Transformer inference memory math

### 3.1 Why our worst-case is 100 GB

Korthikanti et al. 2022 ([arXiv 2205.05198](https://arxiv.org/abs/2205.05198))
give the per-layer activation memory (no recomputation, t=1) as:

```
mem_per_layer (fp16) ≈ s·b·h · (34 + 5·a·s/h)   bytes
```

`s`=seq, `b`=batch, `h`=hidden, `a`=heads, `L`=layers. The first term is
linear in `s`; the second is quadratic — attention stores up to 5
tensors of shape `(b, a, s, s)` per layer.

For nomic-embed-text-v1.5 (L=12, H=768, a=12):

| Config | Linear `34·s·b·h·L` | Quadratic `5·a·s²·b·L` | Total |
|---|---:|---:|---:|
| B=4, S=512, fp16 | 0.60 GB | 0.08 GB | **~0.7 GB** |
| B=32, S=2048, fp16 | 19.3 GB | 4.8 GB | **~24 GB** |
| B=128, S=8192, fp16 (naive) | 308 GB | 1.23 TB | ~1.5 TB nominal |

A **single un-tiled `(B, heads, S, S)` fp32 softmax matrix** at
B=128, S=8192, 12 heads, 12 layers is `128·12·8192·8192·4·12` = **4.94 TB**.
Even one such matrix at B≈32 effective is ~103 GB — **almost exactly
our observed footprint.** ONNX Runtime is materializing the largest
live attention tensor, not the full chain.

The takeaway: memory is **O(B · S²)**. Halving S gives 4× the relief of
halving B. Padding a 30-token snippet to 8192 wastes 70,000× memory
per useful token.

### 3.2 Quantization helps weights, not activations

`onnx/model_quantized.onnx` is **dynamic quantization**:

- Weights → int8 ahead of time. 4× weight shrink (~70 MB → ~17 MB).
- Activations → int8 *at runtime, per tensor*, immediately dequantized
  back to fp32 for the next non-quantized op.

The `(B, heads, S, S)` matrix is still fp32. **Switching to
`model_quantized.onnx` will not move the 100 GB.**
([ORT Quantization docs](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html))

Static QDQ quantization would help, but typically loses 1–3 MTEB
points and is not the ORT fast path for BERT-family models. Not worth
it.

### 3.3 Bucketing + dynamic padding is the standard win

Code/text token-length distributions are heavily right-skewed (median
200–600, tail to 8000+). Pad-to-`max_length` is paying worst-case S²
every batch.

- HF `padding="longest"` — pad to longest in current batch.
- Sort the input queue by length first (sentence-transformers does
  this internally).
- Bucket into power-of-2 boundaries.
- Published gains: HF Smart Batching ~2× on T5-small/T4; MongoDB
  token-count batching **up to 8×**; Triton ragged batching skips
  padding entirely.

### 3.4 Apple Neural Engine has different rules

Apple's ML Research post
[Deploying Transformers on the Apple Neural Engine](https://machinelearning.apple.com/research/neural-engine-transformers):

- ANE operates on a **fixed, compile-time set of tensor shapes**
  (`EnumeratedShapes`, up to 128 variants). Flexible shapes drop the
  graph off ANE.
- Memory on ANE is determined by the **largest enumerated shape**, not
  the actual input. Compiling with seq=8192 in the set reserves an
  8192-sized IOSurface for *every* call.
- ANE's last-axis 64-byte alignment can balloon a singleton dim by 32×
  (fp16) — Apple's own warning. The reference
  [apple/ml-ane-transformers](https://github.com/apple/ml-ane-transformers)
  rewrites attention as a single einsum + split-softmax-per-head and
  achieves **14× lower peak memory + 10× speedup** vs the naive port.

For us: enumerated buckets `[128, 256, 512, 1024, 2048, 4096]` would use
*that* bucket's memory, not 8192's. But we'd need to either compile a
CoreML model with enumerated shapes (currently coremltools-only) or
trust ORT's CoreML EP to handle it, which per §1.2 it doesn't.

### 3.5 Token-budget batching — the cleanest fix

TEI's `--max-batch-tokens 16384` makes memory **approximately
O(max_batch_tokens × S_max_in_batch)** instead of `O(B × S_max_global)`.
A flat ceiling regardless of input mix:

| Incoming queue | Under `batch_size=128, max=8192` | Under `max_batch_tokens=16384` |
|---|---|---|
| 128 × 30 tok | 128×8192 = 1,048,576 tok padded | 128 × 30 ≈ 3,840 tok |
| 128 × 2048 tok | 1,048,576 tok | 8 × 2048 = 16,384 tok |
| 2 × 8000 tok | 1,048,576 tok | 2 × 8000 = 16,000 tok |

**273× less work per unit memory** in the small-input case.

---

## 4. Contradictions and gaps

- **Apple says `RangeDim` works on ANE; coremltools issues show it
  doesn't.** Use `EnumeratedShapes` only, or accept CPU fallback.
- **ORT docs say dynamic shapes are supported; multiple open issues
  document catastrophic memory growth with them.** Treat dynamic
  shapes as a CPU-EP-only feature until proven otherwise.
- **`model_quantized.onnx` is shipped as if it's a memory win.**
  It's not, for activation-bound workloads.
- **CoreML EP "silently converts to FP16."** Our model is effectively
  fp16 on macOS regardless of what the file says.

## 5. What we have not yet measured

- Actual per-call inference time on our box at fixed shapes.
- Whether `MLComputeUnits=CPUAndGPU` (no ANE) actually fixes the hang.
- Token-length distribution of our real corpus — needed to choose
  bucket boundaries and `max_batch_tokens`.

These are tractable post-implementation; not blocking the plan.

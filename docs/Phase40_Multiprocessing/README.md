# Phase 40: Pipeline Multiprocessing & Batch Optimization

> **Goal:** Identify every parallelism and batching opportunity in the CoDRAG
> trace pipeline, quantify the expected speedup, and propose an implementation
> plan that covers both local Ollama users and cloud BYOK users.

---

## 1. Current State — What We Have

### 1.1 Pipeline Architecture (10 stages, 2 groups)

```
Group A — Fast Sync (stages 1–5):
  1. structural      Rust: AST parse → nodes + edges           [NO LLM]
  2. inferred_edges  LLM (code/small): cross-language edges    [LLM - small/code]
  3. catalogue       LLM (small): file/symbol summaries        [LLM - small]
  4. validation      Rust: relationship validation              [NO LLM]
  5. knowledge       Embedding: embed fast-pass metadata        [ONNX/Ollama]

Group B — Deep Enrichment (stages 6–10):
  6. epistemic       LLM (large): deep reasoning + confidence  [LLM - large]
  7. clustering      LLM (large): module-level synthesis       [LLM - large]
  8. atlas           LLM (large): codebase orientation doc     [LLM - large]
  9. deepening       LLM (large): re-enrich stale nodes        [LLM - large]
 10. deep_knowledge  Embedding: re-embed with deep metadata    [ONNX/Ollama]
```

**Key constraint:** Stages within a group run **sequentially** — each stage
depends on the output of the prior stage. This is correct and must stay.

### 1.2 Current Execution Model Per Stage

| Stage | Current Model | Parallelism | Batching |
|-------|--------------|-------------|----------|
| **structural** | Rust `codrag-walker` + `codrag-parser` | ✅ Rayon parallel file walk + parse | N/A |
| **inferred_edges** | Sequential LLM calls, one file at a time | ❌ None (local) | ✅ BYOK batched |
| **catalogue** | Sequential or `ThreadPoolExecutor` (configurable) | ⚠️ `llm_concurrency` setting (default 1) | ✅ BYOK batched |
| **validation** | Pass-through (near-instant) | N/A | N/A |
| **knowledge** | Sequential ONNX `embed_batch()` with batch_size=32 | ⚠️ CPU batch only | N/A |
| **epistemic** | Sequential LLM calls per file (topo-sorted) | ❌ None (local) | ✅ BYOK tier-batched |
| **clustering** | Sequential LLM calls per cluster | ❌ None | ✅ BYOK batched |
| **atlas** | 1-2 LLM calls (root + segments) | ❌ None | N/A (too few items) |
| **deepening** | Sequential (re-enrichment loop) | ❌ None | ❌ None |
| **deep_knowledge** | Same as knowledge | ⚠️ CPU batch only | N/A |

### 1.3 Existing Parallelism Infrastructure

**Already built but underutilized:**

1. **`_get_llm_concurrency()` in `augmenter.py`** — reads `pipeline_config.llm_concurrency`
   from settings. Supports 1–8 concurrent threads via `ThreadPoolExecutor`.
   Currently defaults to 1. Only used in catalogue stage (file augmentation).
   
2. **BYOK batch processing** (`batch_profiles.py`, `batch_strategy.py`, `batch_prompts.py`) —
   full batching infrastructure for cloud APIs. Profiles: Large (100 items/batch),
   Standard (50), Compact (20), Off (1). Auto-detected from provider+model.
   Ollama hardcoded to `OFF`.

3. **`topological_sort_into_tiers()`** in `epistemic_enrichment.py` — sorts files
   into dependency tiers where all items within a tier can be processed in
   parallel (they only depend on earlier tiers). Currently only used for BYOK
   batch sizing, not for concurrent local execution.

4. **Rust engine** — `codrag-walker` uses `rayon` for parallel file walking.
   `codrag-parser` processes files sequentially in the PyO3 wrapper but tree-sitter
   parsing is inherently per-file and CPU-bound (trivially parallelizable).

5. **`NativeEmbedder.embed_batch()`** — ONNX runtime with batch_size=32.
   CPU-bound, not GPU-accelerated (onnxruntime CPU provider).

---

## 2. Parallelism Opportunities — What Can Be Done

### 2.1 Taxonomy of Parallelism Types

| Type | Description | Applicable Stages |
|------|------------|-------------------|
| **Intra-stage concurrency** | Multiple items processed simultaneously within one stage | 2, 3, 6, 7, 9 |
| **Intra-stage batching** | Multiple items packed into one LLM call | 2, 3, 6, 7 (BYOK already done) |
| **Intra-stage CPU parallelism** | Multiple CPU cores for non-LLM work | 1, 4, 5, 10 |
| **Inter-stage pipelining** | Stage N+1 starts on early results while N is still running | Theoretically 2→3, but risky |

**Inter-stage pipelining is NOT recommended** — the complexity and correctness
risk far outweigh the marginal speedup. Each stage reads the full output file
of the prior stage. Streaming partial results would require a fundamentally
different I/O architecture.

### 2.2 Per-Stage Analysis

#### Stage 1: Structural (Rust)
- **Already parallel** via `rayon`. File walk + parse are embarrassingly parallel.
- **Opportunity:** Ensure rayon thread count matches available cores. Currently
  uses rayon defaults (= logical CPU count). No action needed.
- **Speedup potential:** Already near-optimal. ~72ms for 547 nodes.

#### Stage 2: Inferred Edges (LLM — small/code model)
- **Current:** Sequential, one file at a time (local). BYOK batched.
- **Opportunity:** Each file analysis is **independent** — no dependency between files.
  Can safely parallelize to N concurrent LLM calls.
- **Constraint:** Ollama VRAM. Each concurrent request shares the model's KV cache.
  `OLLAMA_NUM_PARALLEL` controls this (see §3).
- **Speedup potential:** 2–4× with `llm_concurrency=2–4` on ≥16GB VRAM.

#### Stage 3: Catalogue / Augmentation (LLM — small model)
- **Current:** Has `ThreadPoolExecutor` path but defaults to `concurrency=1`.
  BYOK batched. Symbol augmentation is always sequential.
- **Opportunity:** Both file AND symbol augmentation are independent per-item.
  The `ThreadPoolExecutor` path already exists — just needs a better default
  and UI exposure.
- **Constraint:** Same VRAM constraint as stage 2. Uses the same model slot.
- **Speedup potential:** 2–4× with concurrency=2–4. This is the **highest-impact
  stage** because it processes every file AND every symbol (often 500+ items).

#### Stage 4: Validation
- Pass-through. No optimization needed.

#### Stage 5 & 10: Knowledge Embedding
- **Current:** Sequential `embed_batch()` with batch_size=32 on CPU (ONNX).
- **Opportunity:** 
  - ONNX can use `onnxruntime-gpu` for CUDA acceleration (10–50× for embedding).
  - Larger batch sizes (64, 128) if GPU memory permits.
  - `OllamaEmbedder.embed_batch()` sends one request per text — could batch.
- **Speedup potential:** 5–20× with GPU-accelerated ONNX. Moderate for Ollama.

#### Stage 6: Epistemic Enrichment (LLM — large model)
- **Current:** Sequential, one file at a time in topological order. BYOK tier-batched.
- **Opportunity:** Files within the same **dependency tier** are independent.
  `topological_sort_into_tiers()` already computes these tiers. Within each
  tier, all items can be processed concurrently.
- **Constraint:** Large model (8b–14b) needs more VRAM per concurrent request.
  Concurrency of 2 may be the practical limit on consumer GPUs.
- **Key insight:** Topological ordering means tier 0 (leaves) is often 40–60%
  of all files. Parallelizing just tier 0 would cut epistemic time nearly in half.
- **Speedup potential:** 1.5–2.5× with concurrency=2 within tiers.

#### Stage 7: Clustering (LLM — large model)
- **Current:** Sequential, one cluster at a time.
- **Opportunity:** Clusters are **independent** — each gets its own LLM call
  with its own member files. Trivially parallelizable.
- **Constraint:** Same large model VRAM constraint. Typically 5–20 clusters,
  so the parallelism window is smaller than stages 2/3/6.
- **Speedup potential:** 1.5–3× with concurrency=2–3.

#### Stage 8: Atlas
- Only 1–5 LLM calls (root + segments). Not worth parallelizing.
  Already uses 300s timeout for thinking models.

#### Stage 9: Deepening
- **Current:** Sequential loop: score → drift → queue → enrich → converge.
- **Opportunity:** Within each iteration's batch (default 20 items), the
  enrichment calls are independent (same as stage 6 within a tier).
- **Constraint:** Each iteration depends on the prior iteration's results.
  Only intra-iteration parallelism is safe.
- **Speedup potential:** 1.5–2× with concurrency=2 within each batch.

---

## 3. Ollama Parallel Request Mechanics

### 3.1 How Ollama Handles Concurrency

Ollama supports concurrent request processing via `OLLAMA_NUM_PARALLEL`:

- **Default:** 4 (or 1 if memory is limited)
- **Mechanism:** Multiple requests for the same model are **batched at the
  inference level** — they share the model weights but get separate KV caches.
- **Memory impact:** Each parallel slot allocates its own KV cache. For a 3B
  model with 2K context, each slot uses ~200–400MB additional VRAM.
- **Queuing:** Requests beyond `OLLAMA_NUM_PARALLEL` are queued FIFO.
  Queue limit: `OLLAMA_MAX_QUEUE` (default 512).

### 3.2 Multi-GPU Behavior

| Scenario | Behavior |
|----------|----------|
| **1 GPU, 1 model** | Model layers on single GPU. `NUM_PARALLEL` concurrent requests share weights. |
| **2 GPUs, 1 large model** | Model layers **split across GPUs** (tensor parallelism). Single request uses both GPUs. Does NOT double throughput — it reduces latency for large models that wouldn't fit on 1 GPU. |
| **2 GPUs, 1 small model** | Since Sept 2025, Ollama may spread model across both GPUs. Use `OLLAMA_SCHED_SPREAD=false` to pin to one GPU. |
| **2 GPUs, 2 different models** | Each model loaded on a separate GPU. True parallel execution. |

### 3.3 "Can we do 2× on 2 GPUs and get 4× speed?"

**Short answer: Not with a single model. Here's why:**

- 2 GPUs with the same model = Ollama splits the model across both GPUs for
  reduced latency, NOT doubled throughput. A 3B model on 2× RTX 3090s won't
  run 2× faster — the layer splitting adds inter-GPU communication overhead.

- **To get ~2× throughput from 2 GPUs**, you need `OLLAMA_NUM_PARALLEL ≥ 2`
  AND enough total VRAM for 2 KV cache slots. The GPUs share the compute
  cooperatively.

- **To get ~4× throughput**, you'd need `OLLAMA_NUM_PARALLEL=4` and enough
  VRAM for 4 KV cache slots. On 2× 24GB GPUs with a 3B model (~2GB), this
  is easily achievable. On a single 8GB GPU with a 7B model (~4GB), you
  can barely fit `NUM_PARALLEL=2`.

**Realistic multi-GPU throughput multipliers:**

| Hardware | Model | `NUM_PARALLEL` | Expected Throughput Multiplier |
|----------|-------|----------------|-------------------------------|
| 1× 8GB (M1/M2) | qwen3:4b | 1–2 | 1.0–1.5× |
| 1× 16GB (M1 Pro) | qwen3:4b | 2–3 | 1.8–2.5× |
| 1× 24GB (RTX 4090) | qwen3:8b | 2–4 | 1.8–3.5× |
| 2× 24GB (2× RTX 4090) | qwen3:8b | 4–6 | 3.0–5.0× |
| 1× 48GB (M2 Ultra) | qwen3:14b | 2–4 | 1.8–3.5× |

These are throughput multipliers for independent requests (our use case),
not latency improvements for a single request.

### 3.4 VRAM Budget Formula

```
VRAM_needed = model_size + (NUM_PARALLEL × context_size × bytes_per_token)

Example: qwen3:4b (2.5GB) with NUM_PARALLEL=3, 2K context:
  2.5GB + (3 × 2048 × 2 bytes × 2 layers) ≈ 2.5GB + 0.7GB = 3.2GB
  → Fits easily on 8GB

Example: qwen3:8b (5.2GB) with NUM_PARALLEL=3, 2K context:
  5.2GB + (3 × 2048 × 2 × 2) ≈ 5.2GB + 0.7GB = 5.9GB
  → Fits on 8GB, tight. Comfortable on 16GB+.
```

---

## 4. Batching vs. Concurrency — The Key Decision

### 4.1 Two Orthogonal Axes

| | **Single item per LLM call** | **Multiple items per LLM call (batching)** |
|--|---|---|
| **1 concurrent call** | Current default (local) | Current BYOK mode |
| **N concurrent calls** | **NEW: local concurrency** | **NEW: concurrent batched calls** |

### 4.2 When Each Strategy Wins

**Concurrency (multiple parallel single-item calls):**
- ✅ Works with ANY model (no structured output needed)
- ✅ Individual failures are isolated (one file fails, others succeed)
- ✅ Simpler prompts, higher per-item quality
- ✅ Progressive results (UI shows progress item by item)
- ❌ Higher per-token overhead (system prompt repeated per call)
- ❌ Limited by VRAM (each slot needs KV cache)

**Batching (multiple items packed into one call):**
- ✅ Much lower API cost (1 call for 50 items vs. 50 calls)
- ✅ Lower total token count (shared system prompt)
- ✅ Better for cloud APIs with per-request latency (network RTT amortized)
- ❌ Requires structured output / careful parsing
- ❌ One failure can lose the entire batch
- ❌ Quality degrades in long contexts (lost-in-the-middle)
- ❌ Only works well with high-output-limit models (≥8K output tokens)

**Recommendation:**

| Scenario | Strategy |
|----------|----------|
| **Local Ollama (small model, fast sync)** | Concurrency (2–4 parallel calls) |
| **Local Ollama (large model, deep enrichment)** | Concurrency (2 parallel calls) |
| **Cloud BYOK (any stage)** | Batching (existing infrastructure) + minor concurrency (2 batched calls) |
| **Apple Silicon unified memory** | Concurrency (2–3, benefits from memory bandwidth) |
| **Multi-GPU** | Concurrency (4–6, matches GPU count × 2) |

### 4.3 Should We Switch to a Larger Model for Batching?

**For local Ollama: No.**

Batching requires the model to output structured responses for N items in one
call. This requires:
1. Large output token budget (`num_predict = N × 200`)
2. Reliable structured output (JSON arrays)
3. Sufficient context window for N item prompts

Local models (3b–8b) struggle with all three. The quality degradation from
cramming 10 items into one prompt is worse than the time saved. The small
models we use for catalogue (qwen3:4b) have 32K context but only ~4K
reliable output — enough for ~10 items at best, with degraded quality.

**For local Ollama, concurrency is strictly better than batching.**

**For cloud BYOK: Already using batching, which is correct.** Cloud models
have 32K–64K output limits, reliable structured output, and per-request
latency that makes batching essential for cost efficiency.

---

## 5. Proposed Implementation Plan

### Sprint 1: Local LLM Concurrency (High Impact, Low Risk)

**Estimated effort: 1 day**

This is the single highest-impact change. Unlocks 2–4× speedup for the
slowest stages (catalogue, inferred_edges) with minimal code changes.

#### 5.1a: Wire `llm_concurrency` into all LLM stages

Currently `_get_llm_concurrency()` exists but is only used in catalogue's
file augmentation path. Extend to:

- **Stage 2 (inferred_edges):** Add `ThreadPoolExecutor` path in
  `InferredEdgesAnalyzer.run()` sequential branch. Files are independent.

- **Stage 3 (catalogue):** Already has `ThreadPoolExecutor`. Also add it to
  **symbol augmentation** (currently always sequential, but symbols are
  independent).

- **Stage 6 (epistemic):** Add concurrent processing **within each tier**.
  Use `topological_sort_into_tiers()` output. Process tier 0 with
  `ThreadPoolExecutor`, then tier 1, etc.

- **Stage 7 (clustering):** Add `ThreadPoolExecutor` for cluster synthesis.
  All clusters are independent.

- **Stage 9 (deepening):** Add `ThreadPoolExecutor` within each iteration's
  batch of nodes.

#### 5.1b: Smart default for `llm_concurrency`

Replace the hardcoded default of 1 with auto-detection:

```python
def _auto_detect_concurrency() -> int:
    """Estimate safe concurrency from available memory."""
    import psutil
    
    # Check GPU VRAM via Ollama API
    # Check system RAM
    # Return conservative estimate
    
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    
    if total_ram_gb >= 64:   # M2 Ultra, high-end workstation
        return 4
    elif total_ram_gb >= 32: # M1 Pro/Max, mid-range
        return 3
    elif total_ram_gb >= 16: # M1/M2, consumer GPU
        return 2
    else:
        return 1
```

Better: query Ollama's `/api/ps` endpoint to check loaded model size and
remaining VRAM, then compute safe concurrency.

#### 5.1c: Dashboard UI

Add "Pipeline Concurrency" setting to AI Models / Advanced settings:
- Auto (recommended) — uses auto-detection
- 1 (sequential) — safe, slow
- 2–4 (manual) — for users who know their hardware

#### 5.1d: Ollama configuration guidance

Document recommended `OLLAMA_NUM_PARALLEL` settings:
- Must be ≥ `llm_concurrency` (Ollama will queue excess requests)
- Recommend setting `OLLAMA_NUM_PARALLEL` to `llm_concurrency + 1` (headroom
  for embedding requests)

### Sprint 2: Embedding GPU Acceleration (Medium Impact, Low Risk)

**Estimated effort: 0.5 days**

#### 5.2a: ONNX GPU execution provider

`NativeEmbedder` currently uses `onnxruntime` CPU provider. Add optional
GPU acceleration:

```python
import onnxruntime as ort

providers = ['CUDAExecutionProvider', 'CoreMLExecutionProvider', 'CPUExecutionProvider']
session = ort.InferenceSession(model_path, providers=providers)
```

ONNX runtime will automatically use the best available provider. CoreML
gives 3–5× speedup on Apple Silicon. CUDA gives 10–50× on NVIDIA.

#### 5.2b: Larger embedding batch sizes

Current `embed_batch()` uses batch_size=32. With GPU acceleration:
- GPU: batch_size=128 or 256 (limited by GPU memory)
- CPU: keep 32 (limited by RAM bandwidth)

### Sprint 3: Concurrent Batched Calls for BYOK (Medium Impact, Low Risk)

**Estimated effort: 0.5 days**

Currently BYOK sends batched calls sequentially. For stages with many batches
(catalogue with 500 files / batch_size=50 = 10 batches), sending 2–3 batched
calls concurrently can further reduce wall-clock time.

Cloud APIs (OpenAI, Anthropic, Google) all support concurrent requests.
Rate limits are the constraint, not VRAM.

Add `ThreadPoolExecutor(max_workers=3)` around the batch loop in:
- `_augment_files_batched()` in `augmenter.py`
- `_enrich_tier_batched()` in `epistemic_enrichment.py`
- Batched path in `inferred_edges.py`

### Sprint 4: Rust Parser Parallelism (Low Impact, Already Mostly Done)

**Estimated effort: 0.5 days**

The Rust walker (`codrag-walker`) uses rayon for parallel file discovery.
The parser (`codrag-parser`) processes files sequentially in the PyO3 wrapper.

Add a parallel parse function:

```rust
pub fn parse_files_parallel(entries: Vec<(String, String)>) -> Vec<ParseResult> {
    entries.par_iter()
        .map(|(path, content)| parse_file(path, content))
        .collect()
}
```

Impact is small because parsing is already fast (~72ms for 547 files), but
this would help large repos (5000+ files).

---

## 6. Speed Projections

### 6.1 Baseline: 300-file Python project, local Ollama

| Stage | Current Time | With Concurrency=2 | With Concurrency=4 |
|-------|-------------|--------------------|--------------------|
| structural | 0.1s | 0.1s | 0.1s |
| inferred_edges (200 files × 3s) | 600s | 320s | 170s |
| catalogue (300 files × 2s) | 600s | 320s | 170s |
| validation | 0.1s | 0.1s | 0.1s |
| knowledge (300 chunks) | 5s | 5s (CPU) / 1s (GPU) | 5s / 1s |
| **Fast Sync Total** | **~1205s (20 min)** | **~645s (10.7 min)** | **~341s (5.7 min)** |
| epistemic (200 files × 8s) | 1600s | 880s | 480s |
| clustering (10 clusters × 5s) | 50s | 28s | 15s |
| atlas | 30s | 30s | 30s |
| deepening (3 iterations × 20 items × 8s) | 480s | 264s | 144s |
| deep_knowledge | 5s | 5s / 1s | 5s / 1s |
| **Deep Enrichment Total** | **~2165s (36 min)** | **~1207s (20 min)** | **~670s (11 min)** |
| **Full Pipeline** | **~56 min** | **~31 min (1.8×)** | **~17 min (3.3×)** |

*Assumptions: qwen3:4b for small, qwen3:8b for large. M1 Pro 16GB.*
*Concurrency overhead factor: 1.07× (Ollama batching is efficient).*
*LLM time dominates; non-LLM stages are noise.*

### 6.2 BYOK Cloud Scenario (already batched)

| Stage | Current (batch, sequential) | +Concurrent batches (×3) |
|-------|-----------------------------|--------------------------|
| inferred_edges | 40s (4 batches × 10s) | 15s |
| catalogue | 30s (6 batches × 5s) | 12s |
| epistemic | 80s (8 batches × 10s) | 30s |
| clustering | 5s (1 batch) | 5s |
| **Total LLM time** | **~155s** | **~62s (2.5×)** |

Cloud is already fast. The concurrent-batch optimization is a nice-to-have.

---

## 7. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| **OOM from too many concurrent requests** | Auto-detect concurrency from VRAM. Add `try/except` with fallback to concurrency=1. Checkpoint progress before each batch. |
| **Ollama response degradation under load** | Monitor per-item quality scores. If average confidence drops >10% vs. sequential, warn user. |
| **Race conditions in result aggregation** | Already handled — `augmenter.py` uses `threading.Lock()` around the shared `augmented` dict. Extend pattern to other stages. |
| **Cloud rate limiting** | Respect `Retry-After` headers. Exponential backoff. Cap concurrent batches at 3. |
| **Checkpoint correctness with concurrent writes** | Write checkpoints from the main thread only, after collecting results from the thread pool. |

---

## 8. Theoretical Limits

### 8.1 Amdahl's Law Applied to Pipeline

The pipeline has a serial fraction (stages that can't be parallelized) and
a parallel fraction (LLM calls within a stage).

```
Serial work: structural (0.1s) + validation (0.1s) + atlas (30s) + I/O (~5s)
           ≈ 35s per full pipeline run

Parallel work: all LLM calls ≈ 3350s (baseline)

Speedup = Total / (Serial + Parallel/N)
  N=2:  3385 / (35 + 1675) = 1.98×
  N=4:  3385 / (35 + 838)  = 3.88×
  N=8:  3385 / (35 + 419)  = 7.46×
  N=∞:  3385 / 35           = 96.7× (theoretical maximum)
```

**The pipeline is 99% parallelizable** — the serial fraction is negligible.
Practical limits are VRAM, not algorithmic.

### 8.2 VRAM-Bounded Concurrency Limits

| Hardware | Small Model (3b) Max N | Large Model (8b) Max N | Large Model (14b) Max N |
|----------|----------------------|----------------------|------------------------|
| 8GB (M1/M2, RTX 3060) | 3–4 | 1–2 | 1 |
| 16GB (M1 Pro, RTX 4070) | 6–8 | 2–4 | 1–2 |
| 24GB (RTX 4090) | 8+ | 4–6 | 2–3 |
| 32GB (M1 Max) | 8+ | 6–8 | 3–4 |
| 48GB (M2 Ultra) | 8+ | 8+ | 6–8 |
| 2×24GB (2× RTX 4090) | 8+ | 6–8 | 4–6 |

### 8.3 The "2 GPUs → 4× Speed?" Question Answered

**Best case scenario: 2× RTX 4090 (48GB total), qwen3:8b (5.2GB)**

- Model fits on 1 GPU with room for 4 KV cache slots
- With `OLLAMA_NUM_PARALLEL=6` and `llm_concurrency=6`: **~5× throughput**
- NOT 4× from "2 GPUs × 2 concurrency" — it's "6 parallel slots with 48GB
  headroom"
- The second GPU gives you VRAM headroom for more parallel slots, not a
  multiplication of the first GPU's throughput

**Worst case: 2× RTX 3060 (24GB total), qwen3:14b (9.3GB)**

- Model splits across both GPUs (tensor parallelism)
- Only 5.7GB left for KV caches → `NUM_PARALLEL=2–3` max
- **~2× throughput** (limited by VRAM, not GPU count)

---

## 9. Summary of Recommendations

### Immediate (Sprint 1 — highest ROI)

1. **Enable `llm_concurrency=2` as default** for all LLM stages (not just
   catalogue file augmentation)
2. **Add `ThreadPoolExecutor` to stages 2, 6, 7, 9** using the existing
   pattern from catalogue
3. **Auto-detect safe concurrency** from available VRAM
4. **Add UI setting** for manual override

### Near-term (Sprints 2–3)

5. **GPU-accelerate ONNX embeddings** (CoreML/CUDA execution providers)
6. **Concurrent batched cloud calls** for BYOK users
7. **Document `OLLAMA_NUM_PARALLEL` guidance** for users

### Future (Sprint 4+)

8. **Rust parser parallelism** (minor impact, nice-to-have)
9. **Adaptive concurrency** — start at N=2, increase if no OOM/timeout,
   decrease if errors detected
10. **Pipeline-level progress estimation** that accounts for concurrency
    (ETA calculation needs to know effective throughput)

---

## 10. Implementation Priority Matrix

| Item | Impact | Effort | Risk | Priority |
|------|--------|--------|------|----------|
| llm_concurrency to all stages | 🔴 High | 1 day | Low | **P0** |
| Auto-detect concurrency | 🟡 Medium | 0.5 day | Low | **P0** |
| UI setting for concurrency | 🟡 Medium | 0.5 day | Low | **P1** |
| ONNX GPU acceleration | 🟡 Medium | 0.5 day | Low | **P1** |
| Concurrent BYOK batches | 🟢 Low | 0.5 day | Low | **P2** |
| OLLAMA_NUM_PARALLEL docs | 🟢 Low | 0.25 day | None | **P2** |
| Rust parser parallelism | 🟢 Low | 0.5 day | Low | **P3** |
| Adaptive concurrency | 🟡 Medium | 1 day | Medium | **P3** |

**Total estimated effort for P0+P1: 2.5 days.**
**Expected speedup: 2–4× on local Ollama, depending on hardware.**

# Phase 40: Pipeline Multiprocessing & Batch Optimization

> **Goal:** Identify every parallelism and batching opportunity in the CoDRAG
> trace pipeline, quantify the expected speedup, and propose an implementation
> plan that covers both local Ollama users and cloud BYOK users.

---

## 1. Current State — What We Have

### 1.1 Pipeline Architecture (10 stages, 2 groups)

```
Group A — Fast Sync (stages 1–5):
  1. structural      Rust: AST parse → nodes + edges           [NO LLM]
  2. inferred_edges  LLM (code/small): cross-language edges    [LLM - small/code]
  3. catalogue       LLM (small): file/symbol summaries        [LLM - small]
  4. validation      Rust: relationship validation              [NO LLM]
  5. knowledge       Embedding: embed fast-pass metadata        [ONNX/Ollama]

Group B — Deep Enrichment (stages 6–10):
  6. epistemic       LLM (large): deep reasoning + confidence  [LLM - large]
  7. clustering      LLM (large): module-level synthesis       [LLM - large]
  8. atlas           LLM (large): codebase orientation doc     [LLM - large]
  9. deepening       LLM (large): re-enrich stale nodes        [LLM - large]
 10. deep_knowledge  Embedding: re-embed with deep metadata    [ONNX/Ollama]
```

**Key constraint:** Stages within a group run **sequentially** — each stage
depends on the output of the prior stage. This is correct and must stay.

### 1.2 Current Execution Model Per Stage

| Stage | Current Model | Parallelism | Batching |
|-------|--------------|-------------|----------|
| **structural** | Rust `codrag-walker` + `codrag-parser` | ✅ Rayon parallel file walk + parse | N/A |
| **inferred_edges** | Sequential LLM calls, one file at a time | ❌ None (local) | ✅ BYOK batched |
| **catalogue** | Sequential or `ThreadPoolExecutor` (configurable) | ⚠️ `llm_concurrency` setting (default 1) | ✅ BYOK batched |
| **validation** | Pass-through (near-instant) | N/A | N/A |
| **knowledge** | Sequential ONNX `embed_batch()` with batch_size=32 | ⚠️ CPU batch only | N/A |
| **epistemic** | Sequential LLM calls per file (topo-sorted) | ❌ None (local) | ✅ BYOK tier-batched |
| **clustering** | Sequential LLM calls per cluster | ❌ None | ✅ BYOK batched |
| **atlas** | 1-2 LLM calls (root + segments) | ❌ None | N/A (too few items) |
| **deepening** | Sequential (re-enrichment loop) | ❌ None | ❌ None |
| **deep_knowledge** | Same as knowledge | ⚠️ CPU batch only | N/A |

### 1.3 Existing Parallelism Infrastructure

**Already built but underutilized:**

1. **`_get_llm_concurrency()` in `augmenter.py`** — reads `pipeline_config.llm_concurrency`
   from settings. Supports 1–8 concurrent threads via `ThreadPoolExecutor`.
   Currently defaults to 1. Only used in catalogue stage (file augmentation).
   
2. **BYOK batch processing** (`batch_profiles.py`, `batch_strategy.py`, `batch_prompts.py`) —
   full batching infrastructure for cloud APIs. Profiles: Large (100 items/batch),
   Standard (50), Compact (20), Off (1). Auto-detected from provider+model.
   Ollama hardcoded to `OFF`.

3. **`topological_sort_into_tiers()`** in `epistemic_enrichment.py` — sorts files
   into dependency tiers where all items within a tier can be processed in
   parallel (they only depend on earlier tiers). Currently only used for BYOK
   batch sizing, not for concurrent local execution.

4. **Rust engine** — `codrag-walker` uses `rayon` for parallel file walking.
   `codrag-parser` processes files sequentially in the PyO3 wrapper but tree-sitter
   parsing is inherently per-file and CPU-bound (trivially parallelizable).

5. **`NativeEmbedder.embed_batch()`** — ONNX runtime with batch_size=32.
   CPU-bound, not GPU-accelerated (onnxruntime CPU provider).

---

## 2. Parallelism Opportunities — What Can Be Done

### 2.1 Taxonomy of Parallelism Types

| Type | Description | Applicable Stages |
|------|------------|-------------------|
| **Intra-stage concurrency** | Multiple items processed simultaneously within one stage | 2, 3, 6, 7, 9 |
| **Intra-stage batching** | Multiple items packed into one LLM call | 2, 3, 6, 7 (BYOK already done) |
| **Intra-stage CPU parallelism** | Multiple CPU cores for non-LLM work | 1, 4, 5, 10 |
| **Inter-stage pipelining** | Stage N+1 starts on early results while N is still running | Theoretically 2→3, but risky |

**Inter-stage pipelining is NOT recommended** — the complexity and correctness
risk far outweigh the marginal speedup. Each stage reads the full output file
of the prior stage. Streaming partial results would require a fundamentally
different I/O architecture.

### 2.2 Per-Stage Analysis

#### Stage 1: Structural (Rust)
- **Already parallel** via `rayon`. File walk + parse are embarrassingly parallel.
- **Opportunity:** Ensure rayon thread count matches available cores. Currently
  uses rayon defaults (= logical CPU count). No action needed.
- **Speedup potential:** Already near-optimal. ~72ms for 547 nodes.

#### Stage 2: Inferred Edges (LLM — small/code model)
- **Current:** Sequential, one file at a time (local). BYOK batched.
- **Opportunity:** Each file analysis is **independent** — no dependency between files.
  Can safely parallelize to N concurrent LLM calls.
- **Constraint:** Ollama VRAM. Each concurrent request shares the model's KV cache.
  `OLLAMA_NUM_PARALLEL` controls this (see §3).
- **Speedup potential:** 2–4× with `llm_concurrency=2–4` on ≥16GB VRAM.

#### Stage 3: Catalogue / Augmentation (LLM — small model)
- **Current:** Has `ThreadPoolExecutor` path but defaults to `concurrency=1`.
  BYOK batched. Symbol augmentation is always sequential.
- **Opportunity:** Both file AND symbol augmentation are independent per-item.
  The `ThreadPoolExecutor` path already exists — just needs a better default
  and UI exposure.
- **Constraint:** Same VRAM constraint as stage 2. Uses the same model slot.
- **Speedup potential:** 2–4× with concurrency=2–4. This is the **highest-impact
  stage** because it processes every file AND every symbol (often 500+ items).

#### Stage 4: Validation
- Pass-through. No optimization needed.

#### Stage 5 & 10: Knowledge Embedding
- **Current:** Sequential `embed_batch()` with batch_size=32 on CPU (ONNX).
- **Opportunity:** 
  - ONNX can use `onnxruntime-gpu` for CUDA acceleration (10–50× for embedding).
  - Larger batch sizes (64, 128) if GPU memory permits.
  - `OllamaEmbedder.embed_batch()` sends one request per text — could batch.
- **Speedup potential:** 5–20× with GPU-accelerated ONNX. Moderate for Ollama.

#### Stage 6: Epistemic Enrichment (LLM — large model)
- **Current:** Sequential, one file at a time in topological order. BYOK tier-batched.
- **Opportunity:** Files within the same **dependency tier** are independent.
  `topological_sort_into_tiers()` already computes these tiers. Within each
  tier, all items can be processed concurrently.
- **Constraint:** Large model (8b–14b) needs more VRAM per concurrent request.
  Concurrency of 2 may be the practical limit on consumer GPUs.
- **Key insight:** Topological ordering means tier 0 (leaves) is often 40–60%
  of all files. Parallelizing just tier 0 would cut epistemic time nearly in half.
- **Speedup potential:** 1.5–2.5× with concurrency=2 within tiers.

#### Stage 7: Clustering (LLM — large model)
- **Current:** Sequential, one cluster at a time.
- **Opportunity:** Clusters are **independent** — each gets its own LLM call
  with its own member files. Trivially parallelizable.
- **Constraint:** Same large model VRAM constraint. Typically 5–20 clusters,
  so the parallelism window is smaller than stages 2/3/6.
- **Speedup potential:** 1.5–3× with concurrency=2–3.

#### Stage 8: Atlas
- Only 1–5 LLM calls (root + segments). Not worth parallelizing.
  Already uses 300s timeout for thinking models.

#### Stage 9: Deepening
- **Current:** Sequential loop: score → drift → queue → enrich → converge.
- **Opportunity:** Within each iteration's batch (default 20 items), the
  enrichment calls are independent (same as stage 6 within a tier).
- **Constraint:** Each iteration depends on the prior iteration's results.
  Only intra-iteration parallelism is safe.
- **Speedup potential:** 1.5–2× with concurrency=2 within each batch.

---

## 3. Ollama Parallel Request Mechanics

### 3.1 How Ollama Handles Concurrency

Ollama supports concurrent request processing via `OLLAMA_NUM_PARALLEL`:

- **Default:** 4 (or 1 if memory is limited)
- **Mechanism:** Multiple requests for the same model are **batched at the
  inference level** — they share the model weights but get separate KV caches.
- **Memory impact:** Each parallel slot allocates its own KV cache. For a 3B
  model with 2K context, each slot uses ~200–400MB additional VRAM.
- **Queuing:** Requests beyond `OLLAMA_NUM_PARALLEL` are queued FIFO.
  Queue limit: `OLLAMA_MAX_QUEUE` (default 512).

### 3.2 Multi-GPU Behavior

| Scenario | Behavior |
|----------|----------|
| **1 GPU, 1 model** | Model layers on single GPU. `NUM_PARALLEL` concurrent requests share weights. |
| **2 GPUs, 1 large model** | Model layers **split across GPUs** (tensor parallelism). Single request uses both GPUs. Does NOT double throughput — it reduces latency for large models that wouldn't fit on 1 GPU. |
| **2 GPUs, 1 small model** | Since Sept 2025, Ollama may spread model across both GPUs. Use `OLLAMA_SCHED_SPREAD=false` to pin to one GPU. |
| **2 GPUs, 2 different models** | Each model loaded on a separate GPU. True parallel execution. |

### 3.3 "Can we do 2× on 2 GPUs and get 4× speed?"

**Short answer: Not with a single model. Here's why:**

- 2 GPUs with the same model = Ollama splits the model across both GPUs for
  reduced latency, NOT doubled throughput. A 3B model on 2× RTX 3090s won't
  run 2× faster — the layer splitting adds inter-GPU communication overhead.

- **To get ~2× throughput from 2 GPUs**, you need `OLLAMA_NUM_PARALLEL ≥ 2`
  AND enough total VRAM for 2 KV cache slots. The GPUs share the compute
  cooperatively.

- **To get ~4× throughput**, you'd need `OLLAMA_NUM_PARALLEL=4` and enough
  VRAM for 4 KV cache slots. On 2× 24GB GPUs with a 3B model (~2GB), this
  is easily achievable. On a single 8GB GPU with a 7B model (~4GB), you
  can barely fit `NUM_PARALLEL=2`.

**Realistic multi-GPU throughput multipliers:**

| Hardware | Model | `NUM_PARALLEL` | Expected Throughput Multiplier |
|----------|-------|----------------|-------------------------------|
| 1× 8GB (M1/M2) | qwen3:4b | 1–2 | 1.0–1.5× |
| 1× 16GB (M1 Pro) | qwen3:4b | 2–3 | 1.8–2.5× |
| 1× 24GB (RTX 4090) | qwen3:8b | 2–4 | 1.8–3.5× |
| 2× 24GB (2× RTX 4090) | qwen3:8b | 4–6 | 3.0–5.0× |
| 1× 48GB (M2 Ultra) | qwen3:14b | 2–4 | 1.8–3.5× |

These are throughput multipliers for independent requests (our use case),
not latency improvements for a single request.

### 3.4 VRAM Budget Formula

```
VRAM_needed = model_size + (NUM_PARALLEL × context_size × bytes_per_token)

Example: qwen3:4b (2.5GB) with NUM_PARALLEL=3, 2K context:
  2.5GB + (3 × 2048 × 2 bytes × 2 layers) ≈ 2.5GB + 0.7GB = 3.2GB
  → Fits easily on 8GB

Example: qwen3:8b (5.2GB) with NUM_PARALLEL=3, 2K context:
  5.2GB + (3 × 2048 × 2 × 2) ≈ 5.2GB + 0.7GB = 5.9GB
  → Fits on 8GB, tight. Comfortable on 16GB+.
```

---

## 4. Batching vs. Concurrency — The Key Decision

### 4.1 Two Orthogonal Axes

| | **Single item per LLM call** | **Multiple items per LLM call (batching)** |
|--|---|---|
| **1 concurrent call** | Current default (local) | Current BYOK mode |
| **N concurrent calls** | **NEW: local concurrency** | **NEW: concurrent batched calls** |

### 4.2 When Each Strategy Wins

**Concurrency (multiple parallel single-item calls):**
- ✅ Works with ANY model (no structured output needed)
- ✅ Individual failures are isolated (one file fails, others succeed)
- ✅ Simpler prompts, higher per-item quality
- ✅ Progressive results (UI shows progress item by item)
- ❌ Higher per-token overhead (system prompt repeated per call)
- ❌ Limited by VRAM (each slot needs KV cache)

**Batching (multiple items packed into one call):**
- ✅ Much lower API cost (1 call for 50 items vs. 50 calls)
- ✅ Lower total token count (shared system prompt)
- ✅ Better for cloud APIs with per-request latency (network RTT amortized)
- ❌ Requires structured output / careful parsing
- ❌ One failure can lose the entire batch
- ❌ Quality degrades in long contexts (lost-in-the-middle)
- ❌ Only works well with high-output-limit models (≥8K output tokens)

**Recommendation:**

| Scenario | Strategy |
|----------|----------|
| **Local Ollama (small model, fast sync)** | Concurrency (2–4 parallel calls) |
| **Local Ollama (large model, deep enrichment)** | Concurrency (2 parallel calls) |
| **Local Ollama (massive model, 35B+)** | Batching (1 call, N items) |
| **Cloud BYOK (any stage)** | Batching (existing infrastructure) + minor concurrency (2 batched calls) |
| **Apple Silicon unified memory** | Concurrency (2–3, benefits from memory bandwidth) |
| **Multi-GPU** | Concurrency (4–6, matches GPU count × 2) |

### 4.3 Should We Switch to a Larger Model for Batching?

**For local Ollama: No.**

Batching requires the model to output structured responses for N items in one
call. This requires:
1. Large output token budget (`num_predict = N × 200`)
2. Reliable structured output (JSON arrays)
3. Sufficient context window for N item prompts

Local models (3b–8b) struggle with all three. The quality degradation from
cramming 10 items into one prompt is worse than the time saved. The small
models we use for catalogue (qwen3:4b) have 32K context but only ~4K
reliable output — enough for ~10 items at best, with degraded quality.

**For local Ollama, concurrency is strictly better than batching.**

**For cloud BYOK: Already using batching, which is correct.** Cloud models
have 32K–64K output limits, reliable structured output, and per-request
latency that makes batching essential for cost efficiency.

---

## 5. Proposed Implementation Plan

### Sprint 1: Local LLM Concurrency (High Impact, Low Risk)

**Estimated effort: 1 day**

This is the single highest-impact change. Unlocks 2–4× speedup for the
slowest stages (catalogue, inferred_edges) with minimal code changes.

#### 5.1a: Wire `llm_concurrency` into all LLM stages

Currently `_get_llm_concurrency()` exists but is only used in catalogue's
file augmentation path. Extend to:

- **Stage 2 (inferred_edges):** Add `ThreadPoolExecutor` path in
  `InferredEdgesAnalyzer.run()` sequential branch. Files are independent.

- **Stage 3 (catalogue):** Already has `ThreadPoolExecutor`. Also add it to
  **symbol augmentation** (currently always sequential, but symbols are
  independent).

- **Stage 6 (epistemic):** Add concurrent processing **within each tier**.
  Use `topological_sort_into_tiers()` output. Process tier 0 with
  `ThreadPoolExecutor`, then tier 1, etc.

- **Stage 7 (clustering):** Add `ThreadPoolExecutor` for cluster synthesis.
  All clusters are independent.

- **Stage 9 (deepening):** Add `ThreadPoolExecutor` within each iteration's
  batch of nodes.

#### 5.1b: Smart default for `llm_concurrency`

Replace the hardcoded default of 1 with auto-detection:

```python
def _auto_detect_concurrency() -> int:
    """Estimate safe concurrency from available memory."""
    import psutil
    
    # Check GPU VRAM via Ollama API
    # Check system RAM
    # Return conservative estimate
    
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    
    if total_ram_gb >= 64:   # M2 Ultra, high-end workstation
        return 4
    elif total_ram_gb >= 32: # M1 Pro/Max, mid-range
        return 3
    elif total_ram_gb >= 16: # M1/M2, consumer GPU
        return 2
    else:
        return 1
```

Better: query Ollama's `/api/ps` endpoint to check loaded model size and
remaining VRAM, then compute safe concurrency.

#### 5.1c: Dashboard UI

Add "Pipeline Concurrency" setting to AI Models / Advanced settings:
- Auto (recommended) — uses auto-detection
- 1 (sequential) — safe, slow
- 2–4 (manual) — for users who know their hardware

#### 5.1d: Ollama configuration guidance

Document recommended `OLLAMA_NUM_PARALLEL` settings:
- Must be ≥ `llm_concurrency` (Ollama will queue excess requests)
- Recommend setting `OLLAMA_NUM_PARALLEL` to `llm_concurrency + 1` (headroom
  for embedding requests)

### Sprint 2: Embedding GPU Acceleration (Medium Impact, Low Risk)

**Estimated effort: 0.5 days**

#### 5.2a: ONNX GPU execution provider

`NativeEmbedder` currently uses `onnxruntime` CPU provider. Add optional
GPU acceleration:

```python
import onnxruntime as ort

providers = ['CUDAExecutionProvider', 'CoreMLExecutionProvider', 'CPUExecutionProvider']
session = ort.InferenceSession(model_path, providers=providers)
```

ONNX runtime will automatically use the best available provider. CoreML
gives 3–5× speedup on Apple Silicon. CUDA gives 10–50× on NVIDIA.

#### 5.2b: Larger embedding batch sizes

Current `embed_batch()` uses batch_size=32. With GPU acceleration:
- GPU: batch_size=128 or 256 (limited by GPU memory)
- CPU: keep 32 (limited by RAM bandwidth)

### Sprint 3: Concurrent Batched Calls for BYOK (Medium Impact, Low Risk)

**Estimated effort: 0.5 days**

Currently BYOK sends batched calls sequentially. For stages with many batches
(catalogue with 500 files / batch_size=50 = 10 batches), sending 2–3 batched
calls concurrently can further reduce wall-clock time.

Cloud APIs (OpenAI, Anthropic, Google) all support concurrent requests.
Rate limits are the constraint, not VRAM.

Add `ThreadPoolExecutor(max_workers=3)` around the batch loop in:
- `_augment_files_batched()` in `augmenter.py`
- `_enrich_tier_batched()` in `epistemic_enrichment.py`
- Batched path in `inferred_edges.py`

### Sprint 4: Rust Parser Parallelism (Low Impact, Already Mostly Done)

**Estimated effort: 0.5 days**

The Rust walker (`codrag-walker`) uses rayon for parallel file discovery.
The parser (`codrag-parser`) processes files sequentially in the PyO3 wrapper.

Add a parallel parse function:

```rust
pub fn parse_files_parallel(entries: Vec<(String, String)>) -> Vec<ParseResult> {
    entries.par_iter()
        .map(|(path, content)| parse_file(path, content))
        .collect()
}
```

Impact is small because parsing is already fast (~72ms for 547 files), but
this would help large repos (5000+ files).

---

## 6. Speed Projections

### 6.1 Baseline: 300-file Python project, local Ollama

| Stage | Current Time | With Concurrency=2 | With Concurrency=4 |
|-------|-------------|--------------------|--------------------|
| structural | 0.1s | 0.1s | 0.1s |
| inferred_edges (200 files × 3s) | 600s | 320s | 170s |
| catalogue (300 files × 2s) | 600s | 320s | 170s |
| validation | 0.1s | 0.1s | 0.1s |
| knowledge (300 chunks) | 5s | 5s (CPU) / 1s (GPU) | 5s / 1s |
| **Fast Sync Total** | **~1205s (20 min)** | **~645s (10.7 min)** | **~341s (5.7 min)** |
| epistemic (200 files × 8s) | 1600s | 880s | 480s |
| clustering (10 clusters × 5s) | 50s | 28s | 15s |
| atlas | 30s | 30s | 30s |
| deepening (3 iterations × 20 items × 8s) | 480s | 264s | 144s |
| deep_knowledge | 5s | 5s / 1s | 5s / 1s |
| **Deep Enrichment Total** | **~2165s (36 min)** | **~1207s (20 min)** | **~670s (11 min)** |
| **Full Pipeline** | **~56 min** | **~31 min (1.8×)** | **~17 min (3.3×)** |

*Assumptions: qwen3:4b for small, qwen3:8b for large. M1 Pro 16GB.*
*Concurrency overhead factor: 1.07× (Ollama batching is efficient).*
*LLM time dominates; non-LLM stages are noise.*

### 6.2 BYOK Cloud Scenario (already batched)

| Stage | Current (batch, sequential) | +Concurrent batches (×3) |
|-------|-----------------------------|--------------------------|
| inferred_edges | 40s (4 batches × 10s) | 15s |
| catalogue | 30s (6 batches × 5s) | 12s |
| epistemic | 80s (8 batches × 10s) | 30s |
| clustering | 5s (1 batch) | 5s |
| **Total LLM time** | **~155s** | **~62s (2.5×)** |

Cloud is already fast. The concurrent-batch optimization is a nice-to-have.

---

## 7. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| **OOM from too many concurrent requests** | Auto-detect concurrency from VRAM. Add `try/except` with fallback to concurrency=1. Checkpoint progress before each batch. |
| **Ollama response degradation under load** | Monitor per-item quality scores. If average confidence drops >10% vs. sequential, warn user. |
| **Race conditions in result aggregation** | Already handled — `augmenter.py` uses `threading.Lock()` around the shared `augmented` dict. Extend pattern to other stages. |
| **Cloud rate limiting** | Respect `Retry-After` headers. Exponential backoff. Cap concurrent batches at 3. |
| **Checkpoint correctness with concurrent writes** | Write checkpoints from the main thread only, after collecting results from the thread pool. |

---

## 8. Theoretical Limits

### 8.1 Amdahl's Law Applied to Pipeline

The pipeline has a serial fraction (stages that can't be parallelized) and
a parallel fraction (LLM calls within a stage).

```
Serial work: structural (0.1s) + validation (0.1s) + atlas (30s) + I/O (~5s)
           ≈ 35s per full pipeline run

Parallel work: all LLM calls ≈ 3350s (baseline)

Speedup = Total / (Serial + Parallel/N)
  N=2:  3385 / (35 + 1675) = 1.98×
  N=4:  3385 / (35 + 838)  = 3.88×
  N=8:  3385 / (35 + 419)  = 7.46×
  N=∞:  3385 / 35           = 96.7× (theoretical maximum)
```

**The pipeline is 99% parallelizable** — the serial fraction is negligible.
Practical limits are VRAM, not algorithmic.

### 8.1 The Physics of VRAM and Concurrency

When an LLM runs, VRAM is consumed by two completely separate things:
1. **Model Weights (Static):** The actual parameters of the model. This is loaded once and shared across all concurrent requests.
2. **KV Cache (Dynamic):** The "short-term memory" used to track the prompt and generated tokens. **Every concurrent request requires its own separate KV cache.**

**The VRAM Formula:**
`Total VRAM = Model_Weights + (NUM_PARALLEL × KV_Cache_Size)`

*Example 1: Massive model (35B) on a 32GB RTX 5090*
- Weights: ~20GB (4-bit quant)
- KV Cache (8K context): ~2.5GB
- If `NUM_PARALLEL=4`: 20GB + (4 × 2.5GB) = 30GB VRAM. **Fits perfectly.** You can run 4 simultaneous requests on a single GPU.

*Example 2: Massive model (35B) on a 128GB Mac Studio*
- Weights: ~20GB
- KV Cache (8K context): ~2.5GB
- If `NUM_PARALLEL=16`: 20GB + (16 × 2.5GB) = 60GB RAM. **Fits easily.** The Mac Studio's unified memory allows massive concurrency for 35B models.

*Example 3: Ultra model (122B) on a 128GB Mac Studio*
- Weights: ~70GB
- KV Cache (8K context): ~4.5GB
- If `NUM_PARALLEL=8`: 70GB + (8 × 4.5GB) = 106GB RAM. **Fits well.** You can achieve significant concurrency even with a 122B model.

**What about multiple endpoints?**
- **Multiple endpoints on the SAME machine:** This is inefficient. The endpoints cannot share weights in VRAM/RAM. You would pay the 20GB/70GB weight penalty twice, drastically reducing the memory left for KV caches. Always use one endpoint with `NUM_PARALLEL > 1` so weights are shared.
- **2 GPUs with their own endpoints:** This is called *Data Parallelism*. If you have two 32GB GPUs and the model fits *entirely* on one GPU (e.g. 35B model), you can run an endpoint on GPU 0 and an endpoint on GPU 1. **However**, it's usually better to just use one endpoint and let Ollama manage tensor/data parallelism, as it will automatically optimize weight sharing and KV cache placement across both cards.

### 8.2 VRAM-Bounded Concurrency Limits

| Hardware | Small Model (3b) Max N | Large Model (8b) Max N | Massive Model (35b) Max N | Ultra Model (122b) Max N |
|----------|----------------------|----------------------|---------------------------|----------------------------|
| 8GB | 3–4 | 1–2 | N/A | N/A |
| 16GB | 6–8 | 2–4 | N/A | N/A |
| 24GB (RTX 4090) | 8+ | 4–6 | 1 (tight) | N/A |
| 32GB (RTX 5090) | 8+ | 8+ | 4 | N/A |
| 48GB (2x 24GB) | 8+ | 8+ | 6-8 | N/A |
| 64GB (2x 32GB) | 8+ | 8+ | 8+ | N/A |
| 96GB (Mac Studio) | 8+ | 8+ | 8+ | 4 |
| 128GB (Mac Studio) | 8+ | 8+ | 8+ | 8-10 |

### 8.3 Massive Local Models (35B–122B)

If users run massive local models (like `qwen3.5:32b` or `qwen3.5:122b` via Ollama), the strategy depends entirely on their hardware class.

**Consumer Class (16GB - 24GB VRAM):**
VRAM is completely dominated by weights. You will only fit `NUM_PARALLEL=1`. 
**Strategy:** Treat these like Cloud BYOK models. Set `llm_concurrency=1` and enable **Intra-stage Batching** (e.g., `batch_size=10`). The models are smart enough to reliably output structured JSON for batched items, compensating for the lack of concurrency.

**Workstation Class (32GB RTX 5090, 64GB+, Mac Studio 96GB/128GB):**
You have ample VRAM/Unified RAM to store both the massive weights and multiple KV caches.
**Strategy:** Use **Concurrency**. Set `llm_concurrency=4` (or up to 8 on a Mac Studio) and process items individually in parallel. This yields the highest quality results (no batching context-loss) at massive throughput. The unified memory bandwidth of Apple Silicon (400-800 GB/s) is particularly well-suited for high-concurrency evaluation of independent files.

### 8.4 The "2 GPUs → 4× Speed?" Question Answered

**Best case scenario: 2× RTX 4090 (48GB total), qwen3:8b (5.2GB)**

- Model fits on 1 GPU with room for 4 KV cache slots
- With `OLLAMA_NUM_PARALLEL=6` and `llm_concurrency=6`: **~5× throughput**
- NOT 4× from "2 GPUs × 2 concurrency" — it's "6 parallel slots with 48GB
  headroom"
- The second GPU gives you VRAM headroom for more parallel slots, not a
  multiplication of the first GPU's throughput

**Worst case: 2× RTX 3060 (24GB total), qwen3:14b (9.3GB)**

- Model splits across both GPUs (tensor parallelism)
- Only 5.7GB left for KV caches → `NUM_PARALLEL=2–3` max
- **~2× throughput** (limited by VRAM, not GPU count)

---

## 9. Implementation Status & Revised Recommendations

### Completed (Sprints 1–4)

| Item | Status | Notes |
|------|--------|-------|
| ✅ `llm_concurrency` wired into all LLM stages | Done | Stages 2, 3, 6, 7, 9 all support ThreadPoolExecutor |
| ✅ Per-stage concurrency settings (fast/code/deep) | Done | `llm_concurrency_fast`, `llm_concurrency_code`, `llm_concurrency_deep` |
| ✅ UI for concurrency (Pipeline Performance section) | Done | **⚠️ Will be replaced by Hardware Profiles** |
| ✅ `thinking` field fix for qwen3.5/deepseek-r1 | Done | Critical bug — models with thinking crashed without this |
| ✅ VRAM lifecycle management (Ollama load/unload) | Done | `_maybe_unload_between_stages()` in orchestrator |
| ✅ Throughput benchmarks on Mac Studio 128GB | Done | 4b: 0.99/s, 8b: 0.71/s, 35b-a3b: 0.36/s (Ollama) |
| ✅ LM Studio MLX speed test | Done | 4b MLX: 1.95/s = **2× faster** than Ollama |

### Key Research Findings

1. **Concurrency on Apple Silicon is nearly useless** (5-9% speedup). Unified memory bus bottleneck. Should be locked to 1.
2. **Model selection matters far more than concurrency.** 4b at c=1 is 2.8× faster than 35b-a3b at c=2.
3. **LM Studio MLX is 2× faster than Ollama** on Apple Silicon (confirmed for `type=llm` models).
4. **qwen3.5-27b MLX crashes in LM Studio** — detected as `type=vlm`, MLX VLM engine bug. See `MODEL_SELECTION_GUIDELINES.md` §8.
5. **The 35b-a3b MoE is a trap** for reasoning — only 3B active params vs 27.8B for the dense 27b.

### Planned (Not Yet Built)

| Item | Plan Doc | Notes |
|------|----------|-------|
| **Hardware Profiles** (replace Pipeline Performance UI) | `PLAN_HARDWARE_PROFILES.md` | Ties concurrency to endpoint type. Deletes manual sliders. |
| **GPU Resource Pools** (unified VRAM across backends) | `PLAN_HARDWARE_PROFILES.md` | Cross-backend load/unload for shared physical VRAM. |
| **LM Studio API adapter** | `PLAN_HARDWARE_PROFILES.md` | `/api/v1/models/load` with explicit `context_length`. |
| **4th model slot (deep_code_model)** | `PLAN_4TH_MODEL_SLOT.md` | Optional deep coder for edge re-analysis. |
| **Stage 11 (deep edge re-analysis)** | `PLAN_4TH_MODEL_SLOT.md` | Re-runs edges with smarter model + epistemic context. |

### Remaining Research

1. **Pull + test `qwen3.5:27b` via Ollama** — throughput benchmark (llama.cpp, no VLM issue)
2. **Test `nightmedia/Qwen3.5-27B-Text-mxfp4-mlx`** — text-only MLX variant, may bypass VLM crash
3. **Quality comparison: 27b vs 122b-a10b** — is 122B worth 4× the VRAM?
4. **Quality comparison: qwen3-coder:30b vs qwen3.5:27b** — for inferred edge detection

---

## 10. Original Priority Matrix (Pre-Research Reference)

*Priorities shifted after benchmarks revealed concurrency is near-useless on Apple Silicon.*

| Item | Impact | Effort | Risk | Original Priority | Status |
|------|--------|--------|------|----------|--------|
| llm_concurrency to all stages | 🔴 High | 1 day | Low | **P0** | ✅ Done |
| Auto-detect concurrency | 🟡 Medium | 0.5 day | Low | **P0** | → Hardware Profiles |
| UI setting for concurrency | 🟡 Medium | 0.5 day | Low | **P1** | ✅ Done → Will be replaced |
| ONNX GPU acceleration | 🟡 Medium | 0.5 day | Low | **P1** | Pending |
| Concurrent BYOK batches | 🟢 Low | 0.5 day | Low | **P2** | Pending |
| OLLAMA_NUM_PARALLEL docs | 🟢 Low | 0.25 day | None | **P2** | → Hardware Profiles |
| Rust parser parallelism | 🟢 Low | 0.5 day | Low | **P3** | Pending |
| Adaptive concurrency | 🟡 Medium | 1 day | Medium | **P3** | → Hardware Profiles |

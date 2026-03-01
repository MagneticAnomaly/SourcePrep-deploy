# Phase 40: Model Selection & Performance Guidelines

> **Based on:** Benchmark data from Mac Studio 128GB, community benchmarks,
> architecture analysis, and Ollama/LM Studio research (Feb 2026).

---

## 1. Concurrency — Where It Actually Helps

### Apple Silicon (Unified Memory) — Minimal Benefit

Our benchmarks on a 128GB Mac Studio showed:

| Model | c=1 | c=2 | Speedup |
|-------|-----|-----|---------|
| qwen3:4b-instruct | 0.993 items/s | 1.087 items/s | **1.09x** |
| qwen3:8b | 0.711 items/s | 0.754 items/s | **1.06x** |
| qwen3.5:35b-a3b | 0.356 items/s | 0.375 items/s | **1.05x** |

**Why only 5-9%?** Apple Silicon's unified memory architecture shares bandwidth
between CPU and GPU. Sending 2 concurrent requests doesn't double throughput
because both requests compete for the same memory bus. The bottleneck is
**tokens per second** (memory bandwidth), not request parallelism.

### NVIDIA Discrete GPUs — Significant Benefit (Theoretical)

On discrete GPUs, each request gets dedicated VRAM bandwidth. Community reports:
- RTX 4090 (24GB): c=2 gives ~1.5-1.8x speedup
- 2× RTX 4090 (48GB): c=4 gives ~2.5-3x speedup
- RTX 5090 (32GB): c=2-3 should give ~1.5-2x with 8b models

**Recommendation:** Set concurrency to 1 on Apple Silicon. Only increase on
NVIDIA hardware or multi-GPU setups.

### Multi-GPU / Multi-Server — Best Case for Concurrency

True concurrency scaling requires:
- **Data Parallelism:** Two GPUs each running the same model independently
  (2 endpoints, each handles different requests)
- **Tensor Parallelism with high NUM_PARALLEL:** One model split across GPUs
  with many concurrent KV cache slots

---

## 2. The Qwen3.5 Model Lineup — Architecture Deep Dive

### Available Models (Ollama, Feb 2026)

| Model | Type | Total Params | Active Params | GGUF Q4 Size | Ollama Tag |
|-------|------|-------------|---------------|-------------|------------|
| **qwen3.5:27b** | Dense | 27.8B | **27.8B** | 17 GB | `qwen3.5:27b` |
| **qwen3.5:35b-a3b** | MoE | 35B | **3B** | 24 GB | `qwen3.5:35b-a3b` |
| **qwen3.5:122b-a10b** | MoE | 122B | **10B** | 81 GB | `qwen3.5:122b-a10b` |
| qwen3.5:397b (cloud) | MoE | 397B | 17B | — | `qwen3.5:cloud` |

### Key Architecture: Gated DeltaNet Hybrid Attention

All Qwen3.5 models use a 3:1 ratio of linear attention (Gated DeltaNet)
to full attention layers. This means:
- **75% of layers** use linear attention (near-linear scaling with context length)
- **25% of layers** use full quadratic attention (preserves fine-grained reasoning)
- **KV cache is dramatically smaller** than standard transformers
- **256K context window** supported efficiently

### Dense vs MoE — The Critical Tradeoff

**qwen3.5:27b (Dense):**
- ALL 27.8B parameters compute every token
- **9× more active compute** than the 35b-a3b MoE
- Community consensus: Significantly better for coding, complex reasoning,
  nuanced instruction following
- Benchmarks: Ties GPT-5 mini on SWE-bench Verified (72.4)
- Speed: ~15-25 tok/s on RTX 4090, ~8-12 tok/s on Mac Studio (estimated)
- VRAM: 17GB at Q4 — fits easily on 128GB Mac Studio

**qwen3.5:35b-a3b (MoE):**
- 35B total but only 3B active per token
- Equivalent intelligence to a ~10B dense model (sqrt formula: √(35×3) ≈ 10B)
- Speed: 60-100 tok/s on RTX 4090, ~30-40 tok/s on Mac Studio
- VRAM: 24GB at Q4 — also fits easily on 128GB Mac Studio
- Best for: Quick classification tasks, simple Q&A, high-volume low-complexity work

**qwen3.5:122b-a10b (MoE):**
- 122B total, 10B active per token
- Equivalent intelligence to a ~35B dense model (√(122×10) ≈ 35B)
- Leads on agentic benchmarks (BFCL-V4: 72.2, Terminal-Bench 2: 49.4)
- VRAM: 81GB at Q4 — fits on 128GB Mac Studio but leaves limited headroom
- Speed: Slower than 27B dense but smarter per-token

### The "√(Total × Active)" Rule

Community-derived heuristic for estimating MoE effective quality:

| Model | Total | Active | √(T×A) | "Feels like" dense |
|-------|-------|--------|---------|---------------------|
| 35b-a3b | 35B | 3B | ~10B | 8-14B dense |
| 122b-a10b | 122B | 10B | ~35B | 27-35B dense |
| 397b-a17b | 397B | 17B | ~82B | 70B+ dense |

---

## 3. The Qwen3-Coder-Next Model

### Architecture

Qwen3-Coder-Next is a **code-specialized MoE** model built on a different base
than Qwen3.5. Key facts:

- **80B total parameters, 3B active** (MoE, same sparsity as 35b-a3b)
- Built on `Qwen3-Next-80B-A3B-Base` (NOT Qwen3.5 architecture)
- Agentically trained: executable task synthesis, environment interaction, RL
- **SWE-bench Verified: >70%** with only 3B active params
- Achieves **Sonnet 4.5-level coding** performance
- 256K context window
- Runs on consumer hardware (64GB MacBook, RTX 5090)

### Qwen3-Coder-Next vs Qwen3.5:27b for Code Analysis

| | **qwen3-coder-next (80B-A3B)** | **qwen3.5:27b (Dense)** |
|--|---|---|
| **Active params** | 3B | 27.8B |
| **Total params** | 80B | 27.8B |
| **Effective intelligence** | ~15B (√80×3) | 27.8B |
| **Code specialization** | ⭐⭐⭐⭐⭐ (trained for it) | ⭐⭐⭐⭐ (general) |
| **General reasoning** | ⭐⭐⭐ (code-focused) | ⭐⭐⭐⭐⭐ (GPT-5 mini class) |
| **Speed** | Very fast (3B active) | Moderate (27.8B compute) |
| **GGUF Q4 size** | ~48GB | ~17GB |
| **SWE-bench** | >70% | 72.4% |
| **Best for** | Agentic coding, edge detection | Deep reasoning, architecture analysis |

**Key insight:** For CoDRAG's **inferred edges stage** (detecting cross-language
calls, dynamic dispatch, config references), the coder-next model is excellent.
But for **epistemic enrichment** (architecture understanding, domain classification,
tech debt), the 27b dense model's deeper reasoning wins.

**Recommendation:** Use `qwen3-coder-next` (or `qwen3-coder:30b` as the Ollama
variant) for Stage 2 (inferred edges), and `qwen3.5:27b` for Stages 6-9 (deep reasoning).

---

## 4. Model Recommendations for CoDRAG Pipeline Stages

### Fast/Catalogue Stage (Stage 3)

**Goal:** Fastest possible throughput for simple classification tasks.
The prompts are short, the required output is simple JSON.

> ⚠️ **Minimum model size: 4B parameters.**
> Models below 4B (e.g. `qwen3:1.7b`, `qwen3:2b`, any `1b`/`2b` variant) will
> **fail on real source files**. They cannot hold file content + prompt + JSON
> schema in their context window at useful quality. Testing on a codebase like
> click-python (103 files) showed **97.8% placeholder summaries** with `qwen3:1.7b` —
> the model emits `"Source file at src/click/core.py"` instead of a real summary.
> Every downstream stage (clustering, atlas, deepening) then has no signal to
> work with and produces degenerate output. **Do not use sub-4B models.**

| Recommendation | Model | Why |
|---------------|-------|-----|
| **Best speed** | `qwen3:4b-instruct` | 0.99 items/s — fastest raw throughput |
| **Best quality/speed** | `qwen3:8b` | 0.71 items/s — 40% slower but better summaries |
| **NOT recommended** | `qwen3:1.7b` / `qwen3:2b` | Too small — ~98% placeholder output on real files |
| **NOT recommended** | `qwen3.5:35b-a3b` | 0.36 items/s — 2.8× slower, no quality benefit for simple tasks |

**Verdict:** Use `qwen3:4b-instruct` or `qwen3:8b`. The catalogue stage
asks simple questions (summarize this function, classify this file) —
a 4B model handles these perfectly. Anything smaller will silently produce
garbage output that cascades through the entire pipeline.

### Coder Stage (Stage 2 — Inferred Edges)

**Goal:** Detect cross-language and dynamic edges that static parsing misses.
Requires understanding of code patterns, API calls, config references.

| Recommendation | Model | Why |
|---------------|-------|-----|
| **Best for edge detection** | `qwen3-coder:30b` | Code-specialized MoE, fast, good patterns |
| **Best speed** | `deepseek-coder:6.7b` | Small coder, very fast |
| **Alternative (quality)** | `qwen3.5:27b` | Dense model, excellent code understanding but slower |

### Deep/Thinking Stage (Stages 6-9 — Epistemic, Clustering)

**Goal:** Deep architectural understanding, domain classification,
cross-reference detection, tech debt analysis. **Quality matters most.**

| Recommendation | Model | Speed | Quality | Notes |
|---------------|-------|-------|---------|-------|
| **⭐ Recommended** | `qwen3.5:27b` | ~0.3-0.4/s | ⭐⭐⭐⭐⭐ | 27.8B active, best reasoning per VRAM |
| **Maximum quality** | `qwen3.5:122b-a10b` | ~0.2-0.3/s | ⭐⭐⭐⭐⭐ | ~35B effective, needs 85GB |
| **Good alternative** | `deepseek-r1:32b` | ~0.3/s | ⭐⭐⭐⭐ | Strong reasoning with thinking |
| **NOT recommended** | `qwen3.5:35b-a3b` | ~0.35/s | ⭐⭐⭐ | Only 3B active — worse than 27b |

**Critical insight:** The 35b-a3b is a TRAP for deep reasoning. Despite having
"35B" in the name, it only activates 3B parameters — making it effectively
a 10B-class model for reasoning quality. The 27B dense model uses ALL 27.8B
parameters and dramatically outperforms it on complex tasks.

**The 27B vs 122B question:**
- 27B: 17GB Q4 / 28GB Q8 / 55GB BF16 — all params active, best quality/VRAM ratio
- 122B: 81GB Q4 / 85GB 5-bit — 10B active (~35B effective), benchmark-leading
- For deep reasoning: **27B is the recommended default.** It leaves plenty of
  headroom on 128GB. The 122B should be tested for quality comparison but may
  not justify the 4× VRAM cost.

---

## 5. Quantization & Format Guide

### GGUF Quantization Levels (Ollama)

| Quant | Bits/param | Size (27B) | Quality Loss | Speed |
|-------|-----------|------------|-------------|-------|
| FP16 | 16 bits | ~56 GB | None | Baseline |
| Q8_0 | 8 bits | ~28 GB | Negligible | ~1.1× faster |
| Q6_K | 6 bits | ~21 GB | Very small | ~1.3× faster |
| Q5_K_M | 5 bits | ~19 GB | Small | ~1.4× faster |
| **Q4_K_M** | 4 bits | **~17 GB** | **Acceptable** | **~1.5× faster** |
| Q3_K_M | 3 bits | ~13 GB | Noticeable | ~1.7× faster |
| Q2_K | 2 bits | ~10 GB | Significant | ~2× faster |

### MLX Format Options (LM Studio)

MLX models run natively on Apple Silicon via LM Studio's MLX backend.
Community reports **~1.5-2× faster** inference than Ollama (llama.cpp) on the
same hardware. MLX format is Apple-specific — not available on NVIDIA/Windows.

**Qwen3.5:27B MLX options available on HuggingFace:**

| Model | Format | Size | Quality | Notes |
|-------|--------|------|---------|-------|
| `mlx-community/Qwen3.5-27B-bf16` | MLX BF16 | **54.7 GB** | ⭐⭐⭐⭐⭐ Full precision | Best quality, fits on 128GB |
| `mlx-community/Qwen3.5-27B-8bit` | MLX 8-bit | ~28 GB | ⭐⭐⭐⭐⭐ Near-lossless | Great balance |
| `mlx-community/Qwen3.5-27B-6bit` | MLX 6-bit | ~21 GB | ⭐⭐⭐⭐ | Good |
| `mlx-community/Qwen3.5-27B-4bit` | MLX 4-bit | ~17 GB | ⭐⭐⭐⭐ | Standard, most downloaded (7.8K) |

**Qwen3.5:122B-A10B MLX options:**

| Model | Format | Size | Quality | Notes |
|-------|--------|------|---------|-------|
| `mlx-community/Qwen3.5-122B-A10B-5bit` | MLX 5-bit | **84.9 GB** | ⭐⭐⭐⭐⭐ | **Largest that fits on 128GB** |
| `mlx-community/Qwen3.5-122B-A10B-4bit` | MLX 4-bit | ~81 GB | ⭐⭐⭐⭐ | Slightly more headroom |
| `mlx-community/Qwen3.5-122B-A10B-bf16` | MLX BF16 | ~244 GB | ⭐⭐⭐⭐⭐ | Does NOT fit on 128GB |

### Recommended Quantization by Hardware

**128GB Mac Studio (M2/M3/M4 Ultra):**

| Strategy | Model + Format | Size | Effective Quality |
|----------|---------------|------|-------------------|
| **⭐ Best value** | qwen3.5:27b MLX BF16 | 54.7GB | ⭐⭐⭐⭐⭐ Full precision + fast MLX |
| **Good balance** | qwen3.5:27b MLX 8-bit | ~28GB | ⭐⭐⭐⭐⭐ Near-lossless, lots of headroom |
| **Ollama default** | qwen3.5:27b Q4_K_M (Ollama) | 17GB | ⭐⭐⭐⭐ Standard quality |
| **Max quality** | qwen3.5:122b-a10b MLX 5-bit | 84.9GB | ⭐⭐⭐⭐⭐ Benchmark-leading (tight fit) |

**Key insight:** On a 128GB Mac Studio, you can run the 27B model at **full
BF16 precision** (54.7GB) via LM Studio MLX. This is a luxury most users don't
have — and it eliminates all quantization quality loss while getting ~2× faster
inference than Ollama's Q4 GGUF.

**64GB Mac (MacBook Pro M3 Max):**
- qwen3.5:27b MLX 4-bit (17GB) or 8-bit (28GB)
- qwen3.5:122b does NOT fit

**32GB Mac / NVIDIA 32GB:**
- qwen3.5:27b Q4_K_M (17GB) — fits with headroom
- qwen3.5:122b does NOT fit

**16GB Mac / NVIDIA 16GB:**
- qwen3:8b Q4_K_M (~5GB) — the realistic maximum for deep reasoning
- qwen3.5:27b does NOT fit

---

## 6. LM Studio as Alternative Backend

### Why Consider LM Studio

- **MLX backend on Apple Silicon:** Community reports show **2× faster inference**
  than Ollama on the same hardware (56 tok/s vs 30 tok/s for qwen3.5:35b)
- **More quantization options:** Supports GGUF and MLX formats
- **OpenAI-compatible API:** Drop-in replacement for Ollama in CoDRAG
- **Better GPU utilization:** MLX is specifically optimized for Apple's Metal GPU

### MLX vs llama.cpp (Ollama) on Apple Silicon

| Feature | Ollama (llama.cpp) | LM Studio (MLX) |
|---------|-------------------|------------------|
| Speed | Baseline | **~1.5-2× faster** |
| Format | GGUF | GGUF + MLX native |
| API | OpenAI-compatible | OpenAI-compatible |
| Setup | CLI, daemon | GUI + CLI |
| Multi-model | Automatic load/unload | Manual model switching |
| Concurrent requests | `NUM_PARALLEL` | Supported |
| Flash Attention | Supported | Native Metal |

### How to Use LM Studio with CoDRAG

CoDRAG already supports `openai-compatible` provider. To use LM Studio:

1. Start LM Studio local server (default: `http://localhost:1234`)
2. In CoDRAG settings → AI Models:
   - Provider: `openai-compatible`
   - Endpoint: `http://localhost:1234/v1`
   - Model: (the model name shown in LM Studio)
3. LM Studio's MLX backend will handle inference

**Important:** LM Studio's MLX models may need separate downloads from
Ollama's GGUF models. Search for "MLX" format models on Hugging Face.

---

## 7. Recommended Configurations by Hardware

### 128GB Mac Studio (M2/M3/M4 Ultra)

**Option A — Ollama (simplest):**
```
Fast Model:    qwen3:4b-instruct           (2.5 GB, ~1.0 items/s)
Coder Model:   qwen3-coder:30b             (18 GB, code-specialized)
Deep Model:    qwen3.5:27b @ Q4_K_M        (17 GB, Ollama default)

Concurrency:   Fast=1, Coder=1, Deep=1     (no benefit on unified memory)
Total VRAM:    ~37.5 GB (leaves 90.5 GB for KV caches + OS)
```

**Option B — LM Studio MLX (recommended, ~2× faster):**
```
Fast Model:    qwen3:4b-instruct           (2.5 GB via Ollama)
Coder Model:   qwen3-coder:30b             (18 GB via Ollama)  
Deep Model:    Qwen3.5-27B-bf16 MLX        (54.7 GB, FULL precision, ~2× tok/s)

Provider:      openai-compatible → http://localhost:1234/v1
Total RAM:     ~75 GB (leaves 53 GB for OS + other models)
```

**Option C — Maximum quality (needs restart for 122b):**
```
Deep Model:    Qwen3.5-122B-A10B-5bit MLX  (84.9 GB, benchmark-leading)
Total RAM:     ~105 GB (tight — close other apps, restart recommended)
```

**Why Option B is the sweet spot:**
- Full BF16 precision = zero quantization loss
- MLX backend = ~2× faster than Ollama's llama.cpp on Apple Silicon
- 54.7 GB leaves plenty of headroom for fast/coder models + KV caches
- 27B dense = 27.8B active params (vs 122B's 10B active = only ~35B effective)
- The 27B at BF16 may produce **better quality** than the 122B at 5-bit
  because full precision + 27.8B active > quantized + 10B active

### 32GB RTX 5090 (Discrete GPU)

```
Fast Model:    qwen3:4b-instruct          (2.5 GB)
Coder Model:   deepseek-coder:6.7b        (4 GB)
Deep Model:    qwen3.5:27b @ Q4_K_M       (17 GB)

Concurrency:   Fast=4, Coder=2, Deep=2
Total VRAM:    ~23.5 GB + KV caches (fits in 32GB)
```

### 24GB RTX 4090 (Discrete GPU)

```
Fast Model:    qwen3:4b-instruct          (2.5 GB)
Coder Model:   deepseek-coder:6.7b        (4 GB)
Deep Model:    qwen3:8b                    (5 GB)

Concurrency:   Fast=4, Coder=2, Deep=2
Total VRAM:    ~11.5 GB + KV caches (plenty of room)
```

### 16GB MacBook Pro (M1/M2/M3 Pro)

```
Fast Model:    qwen3:4b-instruct          (2.5 GB)
Coder Model:   (same as fast — single model)
Deep Model:    qwen3:8b                    (5 GB)

Concurrency:   All=1 (limited memory bandwidth)
Total VRAM:    ~7.5 GB (leaves 8.5 GB for OS + caches)
```

---

## 8. LM Studio VLM Crash — Critical Finding

### The Problem

**All Qwen3.5-27B MLX models crash in LM Studio** during the generation phase
with `Error: Channel Error`. This affects both BF16 (54.7 GB) and 8-bit (~28 GB)
variants. The crash happens after prompt processing completes (100%) but before
any tokens are generated. Even a 10-token "say hi" request crashes.

### Root Cause (Confirmed via API)

LM Studio's `/api/v0/models` endpoint reveals:
```
qwen3.5-27b@8bit  → type=vlm   arch=qwen3_5    ← CRASHES
qwen3-14b          → type=llm   arch=qwen3      ← WORKS
qwen3-coder:30b    → type=llm   arch=qwen3_moe  ← WORKS
```

**Qwen3.5 is a unified Vision-Language Model (VLM)**. There is no text-only
variant from Qwen. LM Studio routes all VLM models through its `mlx-vlm`
engine, which has a **generation-phase bug for the `qwen3_5` architecture**.
Every `type=llm` model on the same LM Studio instance works perfectly.

### Workarounds

| Option | Status | Notes |
|--------|--------|-------|
| **Use Ollama for qwen3.5:27b** | ✅ Works | llama.cpp backend, no VLM pipeline issue. Use `qwen3.5:27b` tag. |
| **Download text-only MLX variant** | 🔶 Untested | `nightmedia/Qwen3.5-27B-Text-mxfp4-mlx` strips vision adapter. Should be detected as `type=llm`. |
| **Wait for LM Studio fix** | ⏳ Pending | LM Studio 0.4.5-0.4.6 added Qwen3.5 fixes but VLM generation crash persists. |
| **Use a different model via MLX** | ✅ Works | `qwen3-14b` (LLM, 8bit) works. `qwen3-coder:30b` (LLM, 4bit) works. |

### Speed Benchmark Results (LM Studio MLX vs Ollama)

| Model | Backend | Speed | Speedup vs Ollama |
|-------|---------|-------|-------------------|
| qwen3:4b-instruct MLX | LM Studio | **1.95 items/s** | **2.0×** |
| qwen3:4b-instruct GGUF | Ollama | 0.99 items/s | baseline |
| qwen3:8b GGUF | Ollama | 0.71 items/s | baseline |
| qwen3.5:35b-a3b GGUF | Ollama | 0.36 items/s | baseline |

**MLX is confirmed ~2× faster** than Ollama on Apple Silicon for text-only
(type=llm) models. The qwen3.5-27b model cannot benefit from this until the
VLM engine bug is fixed or a text-only MLX variant is verified.

---

## 9. Deep Reasoning Quality Comparison (Tested Feb 2026)

### Head-to-Head: qwen3.5:27b vs qwen3:8b (Ollama, same prompt)

Both models were given a realistic epistemic enrichment prompt (analyze a Rust
`ConnectionHandler` for architectural role, domain tags, tech debt, relationships).

| | **qwen3.5:27b (27.8B dense)** | **qwen3:8b (8B dense)** |
|--|---|---|
| **Time** | 260s | 12s |
| **Thinking** | 11,163 chars (very deep) | 2,211 chars (focused) |
| **Content tokens** | ~500 (after thinking) | ~680 |
| **tok/s** | 11.1 | 51.7 |
| **Parsed JSON** | ✅ Valid | ✅ Valid |
| **Architecture layer** | `infrastructure` ✅ | `infrastructure` ✅ |
| **Confidence** | 0.90 | 0.85 |
| **Domain tags** | `networking, protocol-handling, authentication, storage-access, async-io` (5 tags) | `networking, redis-protocol, database-operations` (3 tags) |
| **Summary quality** | Excellent — mentions "request-response lifecycle", "authentication gates", "delegates command execution" | Good — mentions "tight coupling", "violating SRP" |
| **Tech debt** | **Outstanding** — "Fixed 4096-byte buffer risks truncating large commands; lacks streaming parser. Database ownership by value prevents shared state across connections." | Good — "Tight coupling. Missing separation. Basic error handling." |
| **Relationships** | 4 entries with ownership semantics ("owns", "delegates to", "parses", "propagates") | 3 entries with type labels ("dependency", "data_parser", "network_transport") |

### Quality Verdict

The **27b model produces noticeably deeper, more specific analysis**:
- 5 domain tags vs 3 (caught `authentication` and `async-io`)
- Tech debt identifies the **specific 4096-byte buffer risk** and the **ownership semantics issue** — the 8b just says "tight coupling"
- Relationships use richer semantic types (owns, delegates, propagates vs generic dependency)
- Higher confidence (0.90 vs 0.85)

The tradeoff: **22× slower** (260s vs 12s). For deep enrichment of a 300-file
project, this means ~22 hours for the 27b vs ~1 hour for the 8b.

### Practical Recommendation for Deep Reasoning

| VRAM | Recommended Deep Model | Time for 300 files | Quality |
|------|----------------------|--------------------|---------| 
| **128GB Mac Studio** | `qwen3.5:27b` (Q4, 17GB) | ~22 hours | ⭐⭐⭐⭐⭐ |
| **64GB Mac** | `qwen3.5:27b` (Q4, 17GB) | ~22 hours | ⭐⭐⭐⭐⭐ |
| **32GB NVIDIA** | `qwen3.5:27b` (Q4, 17GB) | ~8 hours (c=2) | ⭐⭐⭐⭐⭐ |
| **16GB Mac/NVIDIA** | `qwen3:8b` (5GB) | ~1 hour | ⭐⭐⭐⭐ |
| **8GB** | `qwen3:8b` (5GB) | ~1 hour | ⭐⭐⭐⭐ |

**Important:** The 27b model requires `num_predict >= 4000` in Ollama because
it generates ~2000 tokens of thinking before producing content. With the default
`num_predict=2000`, the model exhausts its budget on thinking and returns empty
content. CoDRAG must set this automatically.

### Models That Failed This Test

| Model | Issue |
|-------|-------|
| **qwen3.5:35b-a3b** (Ollama) | 8,439 chars of thinking, then failed to produce valid JSON in 2000 tokens. 3B active params insufficient for structured output. |
| **qwen3.5:27b** (LM Studio llama.cpp) | LM Studio doesn't separate thinking tokens — all output consumed by inline "Thinking Process:" text. |
| **qwen3.5:27b MLX** (LM Studio) | Crashes during generation — VLM engine bug (see §8). |

---

## 10. Summary: What We Learned

1. **Concurrency helps on NVIDIA, not on Apple Silicon** — unified memory
   architecture means requests share bandwidth. The speedup is 5-9%, not 50-100%.

2. **Model selection matters far more than concurrency** — Choose the right
   model for each stage, not more threads.

3. **The 35b-a3b MoE is a trap for quality** — Despite "35B" in the name, only
   3B parameters are active. It failed to produce valid structured output on our
   epistemic reasoning test. The 27B dense model is dramatically better.

4. **qwen3.5:27b produces the best deep reasoning** — Richer domain tags, specific
   tech debt analysis, ownership-aware relationships. Worth the 22× time cost for
   deep enrichment stages.

5. **qwen3:8b is the practical sweet spot** — Excellent quality, 12s per file,
   fits on 16GB hardware. Good enough for most users.

6. **Thinking models need high num_predict** — The 27b generates ~2000 tokens of
   thinking before content. CoDRAG must set `num_predict >= 4000` for thinking models
   or risk empty responses.

7. **LM Studio MLX is 2× faster than Ollama** for text-only (type=llm) models,
   but crashes on Qwen3.5 VLM models due to an mlx-vlm engine bug.

8. **LM Studio doesn't separate thinking tokens** via the OpenAI API — thinking
   appears inline in the response content. Ollama properly separates thinking into
   a hidden field. Use Ollama for thinking models.

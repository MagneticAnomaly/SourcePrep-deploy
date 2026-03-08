# Phase 46: Large Context Window Research, Recommendations & Tooling

## 1. Research Goals

CoDRAG processes codebases from 50 to 5,000+ files. The three "scope" tasks (Atlas, Group Reasoning, Audit) consume the most context window and produce the most critical outputs. This research answers:

1. **How much context window do we actually need?** (measured in tokens)
2. **How should `num_predict` and `num_ctx` scale with project size?**
3. **Which models produce the best output at large context?**
4. **How should tooling auto-configure based on available VRAM?**

---

## 2. Test Repos

| Repo | Files | Nodes | Edges | Modules | Atlas Prompt (50 mods) | Atlas Prompt (100 mods) | Atlas Prompt (ALL) |
|---|---|---|---|---|---|---|---|
| **TEST** (Next.js marketing) | 44 | 97 | 127 | 22 | ~5K tokens | N/A | ~5K tokens |
| **CoDRAG** (monorepo) | 1,341 | 4,927 | 19,690 | 3,328 | ~10K tokens | ~18K tokens | **~423K tokens** (exceeds all models) |
| **LinuxBrain** (AI assistant) | ~300 code + 1,375 docs | TBD | TBD | TBD | TBD | TBD | TBD |

**Critical finding:** CoDRAG's uncapped Atlas prompt is 423K tokens — far beyond any model's 256K context window. Module capping is mandatory for repos > ~200 modules.

---

## 3. Ollama Context Window Mechanics (Discovered)

### 3a. `num_predict` is a SHARED budget for thinking + response

When `think=True`, Ollama counts thinking tokens AND response tokens against `num_predict`. If the model uses all tokens on reasoning, the response field is empty.

**Fix applied** (`llm_client.py`): When `think=True`, automatically scale `num_predict` by 3× (or +8192, whichever is larger).

### 3b. `num_ctx` controls the total context window

Ollama defaults `num_ctx` based on the model's metadata (often 2048-8192 for older models, 32768 for newer Qwen models). For large prompts, we must explicitly set this. All Qwen3.5 models support up to 262,144 tokens.

### 3c. `num_predict` affects output volume, not just max length

The model does NOT always self-terminate before hitting `num_predict`. For large inputs (100+ modules), giving more `num_predict` budget produces proportionally more detailed output:

| Config (35b Q4, 100 modules) | num_predict | Output Chars | Eval Tokens | Time |
|---|---|---|---|---|
| np=8192 (prev default) | 8,192 | *not tested at 100 mods* | — | — |
| np=16384 | 16,384 | 13,598 | 2,839 | 109s |
| **np=32768** | **32,768** | **29,600** | **5,499** | **189s** |

**29,600 chars at np=32768** is 2.2× more content than np=16384. The model utilized the larger budget to add more SUBSYSTEMS detail, more RISKS entries, and more FLOW descriptions.

For small inputs (50 modules), the model self-terminates around 2,500 tokens regardless of budget — there simply isn't enough input to warrant more output.

---

## 4. Model Speed & Quality at Scale (CoDRAG Repo)

### 4a. Atlas Generation — All No-Think Configs

| Model | Quant | 50 mods (10K tok input) | 100 mods (18K tok input) | tok/s | Notes |
|---|---|---|---|---|---|
| **35b-a3b Q4** | Q4_K_M | 11,452 chars / 103s | **29,600 chars / 189s** | 26-29 | Best output volume at np=32768 |
| **35b-a3b Q8** | Q8_0 | 7,142 chars / 69s | 12,512 chars / 111s | 15-20 | Less output than Q4, slower |
| **27b Q4** | Q4_K_M | 8,428 chars / 217s | **6,739 chars** / 181s | ~10 | **DEGRADED at 100 mods** |
| **27b Q8** | Q8_0 | 6,478 chars / 180s | 9,285 chars / 240s | ~8 | Better than Q4 at large context |
| **122b-a10b** | Q4_K_M | 7,459 chars / 133s | 13,684 chars / 338s | 9-14 | Most accurate IDENTITY section |

**Key findings:**
- **35b-a3b Q4 with np=32768 produces the most comprehensive Atlas** (29.6K chars). It fills the budget aggressively.
- **27b Q4 DEGRADES at 100 modules** — produces less content with more input. Q8 doesn't have this problem.
- **122b-a10b has the best IDENTITY accuracy** (only model to explicitly say "retrieval-augmented generation").
- **Token speed:** Q4 35b (26-29 tok/s) > Q8 35b (15-20) > 122b (9-14) > 27b Q4 (10) > 27b Q8 (8).

### 4b. Group Reasoning — Think vs No-Think

| Model | Think | Time (5 groups) | Parse Success | Pattern Quality |
|---|---|---|---|---|
| 35b-a3b Q4 | OFF | 104s | 5/5 | Good — "Configuration-Driven Service Orchestration" |
| **35b-a3b Q4** | **ON** | **468s** | **5/5** | **Best — "Facade Pattern (via Hook Composition)"** |
| 35b-a3b Q8 | ON | 743s | 5/5 | Good — "Container/Presentational Component Pattern" |
| 122b-a10b | OFF | 170s | 5/5 | Good — "Barrel Module Aggregation" |
| 122b-a10b | ON | 928s | 5/5 | Good — "Centralized Documentation-Driven Evaluation Framework" |

**Key findings:**
- Think mode produces genuinely better architectural pattern names for Group Reasoning.
- The budget fix (3× num_predict) ensures thinking doesn't consume the response budget.
- All models correctly identified the test-fixture artifact group as synthetic/false-positive dependencies.

### 4c. Audit Summary

All models produced well-structured audit reports. Quality differences were minor. The 35b models produced the longest, most detailed reports.

### 4d. Think Mode for Atlas — Assessed and Rejected

| | No-Think Atlas | Think Atlas (fixed budget) |
|---|---|---|
| **Time** | 104s | 314s (3× slower) |
| **Output** | 11,202 chars | 5,681 chars (50% less) |
| **RISKS depth** | Detailed paragraph with file paths | Terse bullet list |

Atlas is a synthesis/summarization task, not a reasoning task. The model doesn't need to "figure out" a logical chain — it needs to organize known information. Think mode adds overhead that cannibalizes output volume.

---

## 5. Dynamic Context Sizing Algorithm (DESIGN)

### 5a. The Problem

CoDRAG currently uses fixed `num_predict=2048` for most tasks. This is:
- **Too small for Atlas** on large repos (should be 16K-32K for 100+ module repos)
- **Wasteful for simple tasks** like per-file augmentation (1K-2K is fine)
- **Ignorant of VRAM** — a 16GB Mac should use smaller context than a 128GB Mac Studio

### 5b. Proposed Algorithm

```
function compute_optimal_settings(task, prompt_tokens, available_vram_gb, model):
    # Step 1: Base num_ctx (must hold prompt + response)
    min_ctx = prompt_tokens * 1.5  # 50% headroom for response
    
    # Step 2: num_predict based on task type and input size
    if task == "atlas":
        if prompt_tokens < 5000:
            num_predict = 4096      # small repo, model self-terminates
        elif prompt_tokens < 15000:
            num_predict = 16384     # medium repo
        else:
            num_predict = 32768     # large repo, let model fill
    elif task == "group_reasoning":
        num_predict = 4096          # JSON output, capped naturally
    elif task == "audit":
        num_predict = 8192          # markdown, moderate length
    elif task == "augment" or task == "epistemic":
        num_predict = 2048          # per-file, short JSON
    
    # Step 3: Think mode multiplier
    if think_enabled:
        num_predict = max(num_predict * 3, num_predict + 8192)
    
    # Step 4: num_ctx = prompt + response budget
    num_ctx = prompt_tokens + num_predict + 512  # 512 token safety margin
    
    # Step 5: VRAM constraint
    # KV cache memory ≈ num_ctx × 2 × n_layers × d_head × n_heads × 2bytes
    # Simplified: ~0.5MB per 1K context tokens for 35b-a3b
    #             ~2MB per 1K context tokens for 27b dense
    #             ~1MB per 1K context tokens for 122b-a10b
    kv_cache_gb = (num_ctx / 1000) * kv_per_1k_tokens[model] / 1024
    model_gb = model_sizes[model]
    total_gb = model_gb + kv_cache_gb
    
    if total_gb > available_vram_gb * 0.85:  # leave 15% for OS
        # Scale back: reduce num_predict first, then num_ctx
        scale_factor = (available_vram_gb * 0.85 - model_gb) / kv_cache_gb
        num_ctx = int(num_ctx * scale_factor)
        num_predict = num_ctx - prompt_tokens - 512
        warn("Context window scaled back due to VRAM constraint")
    
    return num_predict, num_ctx
```

### 5c. Module Capping Strategy

| Project Modules | Module Cap for Atlas | Estimated Prompt Tokens | Recommended num_predict |
|---|---|---|---|
| < 25 | All modules | < 5K | 4,096 |
| 25 - 100 | All modules | 5K - 18K | 16,384 |
| 100 - 500 | Top 100 by file count | ~18K | 32,768 |
| 500 - 1,000 | Top 100 + Segmented Atlas | ~18K × N segments | 32,768 per segment |
| 1,000+ | Top 100 + Segmented Atlas | ~18K × N segments | 32,768 per segment |

### 5d. VRAM Warning System

When the computed context requirements exceed available VRAM:
```
⚠️ Context window scaled back: Your project has 3,328 modules requiring
   ~423K tokens for a full Atlas. Available VRAM (128GB) supports ~65K
   context tokens with this model. Using top 100 modules (18K tokens).
   For deeper coverage, consider:
   - Running Segmented Atlas (multiple passes)
   - Using a smaller model with lower KV cache overhead
   - Upgrading to a machine with more unified memory
```

---

## 6. Hardware-Specific Recommendations

### 6a. How Memory Works on Each Platform

**Apple Silicon (Unified Memory):**
- CPU and GPU share the **same physical RAM pool**. There is no separate VRAM.
- macOS reserves ~25% for OS/CPU tasks. On 128GB, only ~96GB is available to Metal GPU compute (`recommendedMaxWorkingSetSize`).
- **The entire model must fit in RAM** (the GPU-accessible portion, specifically).
- If a model exceeds the GPU portion, llama.cpp offloads excess layers to CPU processing — still using the same RAM, just without GPU acceleration. This is slower but works.
- If the model + KV cache exceeds **total physical RAM**, macOS pages to SSD — this is catastrophically slow (< 1 tok/s) and not a viable operating mode.
- There is NO "VRAM ↔ System RAM swap" on Mac because they are the same memory.

**NVIDIA Discrete GPU (Separate VRAM + System RAM):**
- GPU has dedicated VRAM (e.g., 24GB RTX 4090). System has separate DDR RAM (e.g., 64GB).
- llama.cpp splits model **layers** between GPU VRAM (fast) and system RAM (slow, CPU-processed). The `-ngl` flag controls how many layers go to GPU.
- PCIe bus bandwidth is the bottleneck for layers in system RAM.
- **MoE Expert Offloading** (`--n-cpu-moe N`): A newer llama.cpp feature that keeps dense/shared layers on GPU and offloads expert weights to system RAM. When the router selects a CPU-resident expert, the activation vector round-trips over PCIe. This is a game-changer for NVIDIA: a 120B MoE model can run on a 24GB GPU + 64GB system RAM with reasonable speed.
- Windows also has "Shared GPU Memory" which lets VRAM overflow into system RAM implicitly, but benchmarks show this offers minimal benefit vs explicit layer offloading.

### 6b. MoE Advantage — Platform-Agnostic

The MoE speed advantage applies equally to ALL platforms (not just Mac):
- **Computational:** Only active params compute per token (3B for 35b-a3b). Inference speed is comparable to a ~3B dense model regardless of the 35B total parameter count.
- **On NVIDIA:** Expert offloading is especially powerful — you can run MoE models far larger than your VRAM by keeping inactive experts in cheap system RAM.
- **On Mac:** The computational advantage still applies (fewer FLOPs per token = faster tok/s), but there is NO memory advantage — all 35B params must fit in unified RAM regardless of how many are active.
- **Key insight for CoDRAG:** MoE models (35b-a3b, 122b-a10b) are the best choice on ALL platforms for per-file tasks because they're simply faster. The NVIDIA-specific advantage is that expert offloading lets you run the 122b-a10b (81GB model) on machines with only 24GB VRAM + sufficient system RAM.

### 6c. VRAM Tier Recommendations

**Apple Silicon (Unified Memory):**

| RAM | GPU Available (~75%) | Recommended Model | Max Model Size | Notes |
|---|---|---|---|---|
| **16GB** | ~12GB | qwen3:8b Q4 (5GB) | ~10GB | 35b-a3b (24GB) does NOT fit |
| **32GB** | ~24GB | 35b-a3b Q4 (24GB) | ~22GB | Tight fit; minimal KV cache headroom |
| **64GB** | ~48GB | 35b-a3b Q8 (39GB) | ~45GB | Good headroom for KV cache |
| **128GB** | ~96GB | 122b-a10b Q4 (81GB) | ~90GB | Fits with headroom |

**NVIDIA Discrete GPU:**

| VRAM | System RAM | Recommended Model | Strategy |
|---|---|---|---|
| **16GB** | 32GB+ | 35b-a3b Q4 (24GB) | Expert offload 8GB to system RAM |
| **24GB** | 64GB+ | 35b-a3b Q4 (24GB) fully in VRAM | Full GPU speed |
| **24GB** | 64GB+ | 122b-a10b Q4 (81GB) | Expert offload ~57GB to system RAM |
| **2×24GB** | 64GB+ | 35b-a3b Q8 (39GB) tensor split | Full GPU speed, split across GPUs |
| **48GB** (A6000) | 128GB+ | 122b-a10b Q4 (81GB) | Expert offload ~33GB to system RAM |

### 6d. Corrected: Previous "Swap Tolerance" Claim Was Wrong

The earlier claim that "MoE models tolerate swap 3-5× better than dense models on Mac" was **incorrect**. On Mac:
- All model params must fit in unified RAM regardless of architecture (MoE or dense).
- There is no separate VRAM to "swap" between.
- The MoE advantage on Mac is purely computational speed (fewer active FLOPs), not memory efficiency.
- On NVIDIA, MoE expert offloading IS a real memory advantage, but it's layer-level offloading over PCIe, not "swap."

---

## 7. Cloud Considerations (Future)

For cloud/API providers (OpenAI, Anthropic, Google):
- Context window limits are provider-imposed, not VRAM-constrained
- `max_tokens` (equivalent to `num_predict`) is usually separately configurable
- Cost scales linearly with input + output tokens
- Strategy: Same module capping, but num_predict can be generous since cloud has no VRAM constraint
- Concern: Cost control — large Atlas prompts (18K tokens) + large responses (5K tokens) = $0.05-0.50 per Atlas call depending on provider

---

## 8. Tooling Implementation Plan

### 8a. Auto-Scaling Context Configuration (Priority: HIGH)

Add to `codrag/core/context_config.py`:
- `compute_num_predict(task, prompt_tokens, vram_gb, model)` → int
- `compute_num_ctx(prompt_tokens, num_predict)` → int
- `compute_module_cap(total_modules, vram_gb)` → int
- `estimate_vram_usage(model, num_ctx)` → float (GB)

### 8b. VRAM Detection (Priority: HIGH)

- macOS: `sysctl hw.memsize` for total unified memory
- Linux/NVIDIA: `nvidia-smi --query-gpu=memory.total --format=csv`
- Fallback: User-configurable in settings

### 8c. VRAM Warning System (Priority: MEDIUM)

When context requirements exceed VRAM:
- Log warning with specific numbers
- Automatically scale back module cap / num_predict
- Suggest alternatives (Segmented Atlas, smaller model)

### 8d. Per-Task Think Mode Policy (Priority: HIGH)

| Task | Think Default | Rationale |
|---|---|---|
| Augmentation (Pass 1) | OFF | Simple classification, no reasoning needed |
| Epistemic (Pass 2) | OFF | Per-file analysis, think overhead not justified |
| Group Reasoning | **ON** | Cross-file pattern inference, think genuinely helps |
| Atlas | OFF | Synthesis task, think cannibalizes output |
| Audit | OFF | Report generation, similar to Atlas |

---

## 9. Tooling Implementation: context_config.py (DONE)

The dynamic sizing algorithm is implemented in `src/codrag/core/context_config.py`. Verified output:

```
Scenario                                np     ctx VRAM est Warnings
------------------------------------------------------------------------------------------
Small repo Atlas (50 mods)           16384   21896    24.0GB
Large repo Atlas (100 mods)          32768   51280    24.0GB
Large repo Atlas + think             32768  116816    24.1GB
Group Reasoning (15 files)            8192   27388    24.0GB
Audit (CoDRAG)                        8192   10804    24.0GB
Per-file epistemic                    2048    3360    24.0GB
Atlas on 16GB Mac                    32768   51280    24.0GB ⚠️ Model may not fit
Atlas 122b on 128GB                  32768   51280    81.5GB

Module cap: 3328 modules @ 128GB → 150 | @ 32GB → 100 | @ 16GB → 75
```

### API:
- `compute_num_predict(task, prompt_tokens)` → base num_predict
- `compute_num_ctx(prompt_tokens, num_predict, model)` → context window
- `compute_module_cap(total_modules, vram_gb)` → module cap
- `estimate_vram_usage_gb(model, num_ctx)` → GB estimate
- `compute_optimal_settings(task, prompt_tokens, model, think, vram_gb)` → (np, ctx, warnings)
- `detect_available_vram_gb()` → auto-detect via sysctl / nvidia-smi

---

## 10. Group Reasoning: Think Mode Verified with Budget Fix

After the llm_client.py fix (3× num_predict scaling), think mode works correctly for Group Reasoning:

| Config | Thinking | Response | Time | Pattern |
|---|---|---|---|---|
| 35b Q4 think (auto→24576) | 5,887 chars | 3,222 chars | 87.7s | "Hub-and-Spoke Documentation Reference Pattern" |
| 35b Q4 think ctx=65536 | 3,013 chars | 2,379 chars | 44.4s | "Documentation Hub Pattern" |
| 122b think (auto→24576) | 3,344 chars | 2,014 chars | 170.5s | "Evaluation Framework with Central Documentation Hub" |

Clean separation of thinking and response fields. All models produced valid JSON with 5 coupling risks each.

---

## 12. Multi-Repo Validation Findings

To validate findings beyond the CoDRAG codebase, we ran a multi-repo benchmark against **TEST2** (React website, ~210 files), **TEST3** (React Native, ~200 files), and **HomeColab** (iOS Swift, ~665 files).

### 12a. Think Mode: Prose vs Structured (Confirmed)
We discovered a critical issue with think mode on small repos: when `think=True`, `llm_client.py` scales `num_predict` 3× to give the model room to think. For an Audit task on a small repo (prompt ~500 tokens), the model received a `num_predict` of 49,152. This caused the model to spend 30+ minutes generating thinking tokens without stopping.

**Solution implemented:**
1. Capped the think multiplier budget to 24,576 tokens maximum in `llm_client.py`.
2. Proved that **think mode should be strictly split by task type**:
   - **Prose tasks (Atlas, Audit):** Think mode OFF. It's slow and counterproductive.
   - **Structured tasks (Group Reasoning):** Think mode ON. It produces vastly superior JSON patterns.

With this split, TEST2 completed Atlas in 21s (no-think) and produced high-quality Group Reasoning in 143s (think).

### 12b. Q8 "Babbling" Anomaly
On TEST3 with `qwen3.5:35b-a3b-q8_0` (no-think), the Audit task took **581s** and output **62,770 characters**. The model entered a hallucination loop and output a wall of text until it hit the context limit. This confirms that:
- Generous `num_predict` allows the model to output full reports, but also allows infinite loops if the model degrades.
- Higher precision (Q8) does not guarantee better behavior at large contexts; the Q4 model completed the same task flawlessly in 26s (3,383 chars).
*(Note: We implemented a 3-layer defense against this in `llm_client.py` via `OutputMonitor` and repetition penalties.)*

### 12c. MoE Speed Consistency (Cross-Language)
Across all three repos (Python, React/TS, and iOS Swift), the MoE models scale precisely with their active parameter count:
- **35b Q4 (3B active):** ~21s on TEST2, ~45s on TEST3, ~130s on HomeColab.
- **122b Q4 (10B active):** ~47s on TEST2, ~84s on TEST3, ~204s on HomeColab.
The 122b model is consistently ~1.6× to 2.0× slower than the 35b model, despite being 3.5× larger in total parameters. This confirms the MoE computational advantage is highly stable across different prompt structures and programming languages.

### 12d. HomeColab (iOS Swift) Results
| Config | Atlas (100 mods) | Group Reasoning (5 groups) | Audit | Atlas Chars |
|---|---|---|---|---|
| 35b-q4 | 130s | 98s (no-think) | 23s | 12,269 |
| 35b-q4 (GR think) | 143s | 453s (think) | 26s | 12,966 |
| 35b-q8 | 120s | 110s (no-think) | 42s | 10,604 |
| 35b-q8 (GR think) | 114s | 546s (think) | 28s | 10,556 |
| 122b | 204s | 184s (no-think) | 54s | 9,230 |
| 122b (GR think) | 230s | 886s (think) | 93s | 10,613 |

*Key takeaway:* The `think` multiplier on Group Reasoning takes 4-5× longer, but produces significantly better architectural names (e.g., "Design System Architecture" vs generic "Configuration Pattern"). Q8 models produced slightly *less* Atlas content than Q4 models.

### 12e. Quality Analysis: Q4 vs Q8 vs 122b (Content, Not Volume)

More chars ≠ better quality. We compared the *content accuracy* and *specificity* of the same HomeColab prompts across quantizations:

**IDENTITY (Atlas opening line):**
| Model | Description Style | Example Specifics |
|---|---|---|
| **35b Q4** | High-level, user-facing | "vote on listings", "legal compliance", "monetization strategies" |
| **35b Q8** | Implementation-specific, technical | "CSV and URL parsing", "CMA logic", "3D comparison matrices" |
| **122b** | Balanced, platform-aware | "Firebase backend services", "share, compare, rank" |

The Q8 model describes *how the system works internally*. The Q4 model describes *what it does for users*. The 122b model splits the difference. For CoDRAG's purpose (developer orientation), **Q8's technical specificity is arguably more useful** — a developer needs to know about CSV parsing and CMA logic, not marketing language.

**ARCHITECTURE (Graph-aware reasoning):**
- **Q8 uniquely cited quantitative graph data:** "FirestoreManager.swift which acts as the central hub with 64 incoming edges" — this is the actual edge count from the knowledge graph. Neither Q4 nor 122b included this.
- All three models correctly identified the "Shared Core, Separate Apps" migration strategy.
- Q4 mentioned more file paths in the SUBSYSTEMS section (actual paths vs module names).

**GROUP REASONING (Structured JSON quality):**
| Model | Avg Confidence | Total Coupling Risks | Pattern Specificity |
|---|---|---|---|
| 35b Q4 no-think | 0.93 | 18 | Good — "Configuration-Driven Component Architecture" |
| 35b Q8 no-think | **0.94** | **21** | Better — "Spec-Driven Development with Centralized Schema Governance" |
| 35b Q4 think | 0.90 | 20 | Good — "Hub-and-Spoke Documentation Orchestration" |
| 35b Q8 think | 0.91 | 18 | Good — "Schema-First Architecture with Documentation Orchestration" |
| 122b no-think | 0.91 | 20 | Good — "Specification-Driven Development with Shared Schema Contract" |
| 122b think | 0.90 | 19 | Concise — "Design System Architecture" |

**Key finding:** Q8 no-think found the **most coupling risks** (21) with the **highest confidence** (0.94), and produced the most specific pattern names. The think multiplier didn't consistently improve risk detection — it sometimes produced fewer risks with longer reasoning.

**AUDIT (Health Report):**
- Q4 (2,584 chars): Concise, well-structured, mentions "179 warnings with no critical failures"
- Q8 (4,923 chars): More detailed, covers "incomplete SDK integrations, pervasive documentation inconsistencies"
- 122b (3,039 chars): Balanced, mentions "incomplete feature implementations, logical contradictions"

**Conclusion:** Q8 quantization produces **denser, more technically specific** content with better graph-awareness. Q4 produces more text but is more "marketing-level." For CoDRAG's developer-facing use case, **Q8 is qualitatively superior per token**. The tradeoff is ~40% slower generation and ~60% more RAM. The 122b model is the most balanced but 2× slower than 35b.

### 12f. Dynamic Optimization Opportunities (By Model/Quant)

Based on the quality analysis, different quantizations have different output characteristics that we can optimize for:

1. **Q8 models are more concise → lower `num_predict` budget needed.** Q8 consistently produced ~15% fewer chars than Q4 for the same task. We could reduce the token budget by 15-20% for Q8 models, saving time without losing content.

2. **Q8 models are more prone to repetition loops → higher `repeat_penalty`.** The 1/12 babbling incident was Q8. Raising `repeat_penalty` from 1.15 to 1.2 for Q8 models adds a safety margin.

3. **122b models produce the best IDENTITY accuracy → prioritize for Atlas.** If the pipeline has model choice, route Atlas generation to 122b and augmentation to 35b for best speed/quality balance.

4. **Think mode helps pattern naming but not risk detection.** The no-think Q8 found *more* coupling risks than any think config. Think mode's value is in pattern *naming quality*, not analytical depth. This suggests think mode should be optional/configurable per user preference, not mandatory.

### Future: Stress Tests
- Test with explicit `num_ctx=131072` (128K) on a large prompt
- Test Segmented Atlas on CoDRAG (multiple passes, then merge)
- Benchmark KV cache memory usage vs num_ctx on each model
- Test `qwen3-coder:30b` for Group Reasoning (code-specialized patterns)
- Integrate `context_config.py` into the main pipeline orchestrator

# GPU, VRAM & Model Reference — Source of Truth
*Last updated: Mar 7, 2026 — Phase 46 Large Context Window Research*

## 1. Qwen3.5 Model Lineup

| Model | Architecture | Total Params | Active Params | GGUF Q4 Size | GGUF Q8 Size | Max Context | Ollama Tag |
|---|---|---|---|---|---|---|---|
| qwen3.5:27b | Dense | 27.8B | **27.8B** | 17.4 GB | 30.0 GB | 262K | `qwen3.5:27b` / `qwen3.5:27b-q8_0` |
| qwen3.5:35b-a3b | MoE | 35B | **3B** | 23.9 GB | 38.7 GB | 262K | `qwen3.5:35b-a3b` / `qwen3.5:35b-a3b-q8_0` |
| qwen3.5:122b-a10b | MoE | 122B | **10B** | 81.4 GB | ~130 GB | 262K | `qwen3.5:122b-a10b` |
| qwen3:8b | Dense | 8B | **8B** | 5.2 GB | ~8.5 GB | 131K | `qwen3:8b` |
| qwen3:4b-instruct | Dense | 4B | **4B** | 2.5 GB | ~4 GB | 131K | `qwen3:4b-instruct` |
| qwen3-coder:30b | MoE (code) | 30B | **3B** | 18.6 GB | — | 131K | `qwen3-coder:30b` |

### Key Architecture Notes
- **Gated DeltaNet Hybrid Attention:** All Qwen3.5 models use 3:1 linear-to-full attention ratio. KV cache is dramatically smaller than standard transformers.
- **MoE (Mixture-of-Experts):** Only a subset of "expert" FFN layers activate per token. The router selects experts dynamically. ALL parameters must be loaded into memory even though only a fraction compute per token.
- **Dense:** All parameters compute every token. Higher quality per active-param but slower inference.

---

## 2. Measured Performance (CoDRAG Repo Benchmarks, Mar 2026)

### Token Generation Speed (Apple Silicon, 128GB Mac Studio)

| Model | Quant | tok/s (generation) | Notes |
|---|---|---|---|
| qwen3.5:35b-a3b | Q4 | **26-29 tok/s** | Fastest large model |
| qwen3.5:35b-a3b | Q8 | 15-20 tok/s | Higher precision, ~40% slower |
| qwen3.5:122b-a10b | Q4 | 9-14 tok/s | 10B active params |
| qwen3.5:27b | Q4 | ~10 tok/s | Dense, all 27.8B compute |
| qwen3.5:27b | Q8 | ~8 tok/s | Slowest tested config |

### Atlas Quality (100 modules, ~18K token input, no-think)

| Model | Quant | num_predict | Output Chars | Time | Quality Notes |
|---|---|---|---|---|---|
| **35b-a3b** | **Q4** | **32768** | **29,600** | **189s** | Most comprehensive output |
| 35b-a3b | Q4 | 16384 | 13,598 | 109s | Good but less detailed |
| 35b-a3b | Q8 | 32768 | 10,024 | 137s | Less output than Q4 |
| 122b-a10b | Q4 | 16384 | 13,551 | 212s | Most accurate IDENTITY |
| 122b-a10b | Q4 | 32768 | 13,684 | 338s | Slightly more than 16K |
| 27b | Q4 | 16384 | 6,739 | 181s | **DEGRADED** — less output with more input |
| 27b | Q8 | 16384 | 9,285 | 240s | Better than Q4 at large context |

### Group Reasoning (5 groups, CoDRAG repo)

| Model | Think | Time | Parse Success | Pattern Quality |
|---|---|---|---|---|
| 35b-a3b Q4 | OFF | 104s | 5/5 | Good |
| **35b-a3b Q4** | **ON** | **468s** | **5/5** | **Best — most specific patterns** |
| 35b-a3b Q8 | ON | 743s | 5/5 | Good |
| 122b-a10b | OFF | 170s | 5/5 | Good |
| 122b-a10b | ON | 928s | 5/5 | Good |

---

## 3. GPU/Hardware Reference

### Apple Silicon Chips

| Chip | Max RAM | GPU Available (~75%) | GPU Cores | Memory BW | Typical Device |
|---|---|---|---|---|---|
| M1 | 16GB | ~12GB | 7-8 | 68 GB/s | MacBook Air/Pro |
| M1 Pro | 32GB | ~24GB | 14-16 | 200 GB/s | MacBook Pro 14/16" |
| M1 Max | 64GB | ~48GB | 24-32 | 400 GB/s | MacBook Pro 16", Mac Studio |
| M1 Ultra | 128GB | ~96GB | 48-64 | 800 GB/s | Mac Studio |
| M2 | 24GB | ~18GB | 8-10 | 100 GB/s | MacBook Air/Pro |
| M2 Pro | 32GB | ~24GB | 16-19 | 200 GB/s | MacBook Pro, Mac mini |
| M2 Max | 96GB | ~72GB | 30-38 | 400 GB/s | MacBook Pro 16", Mac Studio |
| M2 Ultra | 192GB | ~144GB | 60-76 | 800 GB/s | Mac Studio, Mac Pro |
| M3 | 24GB | ~18GB | 8-10 | 100 GB/s | MacBook Air/Pro |
| M3 Pro | 36GB | ~27GB | 14-18 | 150 GB/s | MacBook Pro |
| M3 Max | 128GB | ~96GB | 30-40 | 400 GB/s | MacBook Pro 16", Mac Studio |
| M4 | 32GB | ~24GB | 10 | 120 GB/s | MacBook Air/Pro, iMac |
| M4 Pro | 48GB | ~36GB | 16-20 | 273 GB/s | MacBook Pro, Mac mini |
| M4 Max | 128GB | ~96GB | 40 | 546 GB/s | MacBook Pro 16" |

**Key facts:**
- GPU available = ~75% of total RAM (macOS Metal `recommendedMaxWorkingSetSize`)
- Memory bandwidth directly correlates with tok/s — higher BW = faster inference
- There is NO "VRAM swap" on Mac — model must fit in GPU-available memory

### NVIDIA Consumer GPUs

| GPU | VRAM | Memory BW | CUDA Cores | Typical Use |
|---|---|---|---|---|
| RTX 3060 | 12GB | 360 GB/s | 3584 | Entry-level LLM |
| RTX 3090 | 24GB | 936 GB/s | 10496 | Serious local LLM |
| RTX 4070 Ti | 12GB | 504 GB/s | 7680 | Budget option |
| RTX 4080 | 16GB | 717 GB/s | 9728 | Mid-range |
| RTX 4090 | 24GB | 1008 GB/s | 16384 | Best consumer GPU |
| RTX 5090 | 32GB | ~1792 GB/s | 21760 | Next-gen consumer |

### NVIDIA Professional/Data Center

| GPU | VRAM | Memory BW | Notes |
|---|---|---|---|
| RTX A6000 | 48GB | 768 GB/s | Professional workstation |
| A100 | 40/80GB | 2039 GB/s | Data center standard |
| H100 | 80GB | 3350 GB/s | Current gen data center |
| L40S | 48GB | 864 GB/s | Inference-optimized |

**Key facts:**
- VRAM is dedicated — separate from system RAM
- Models exceeding VRAM can offload layers to system RAM via PCIe (slower)
- MoE expert offloading (`--n-cpu-moe`) keeps dense layers on GPU, experts in system RAM
- Multi-GPU via tensor parallelism or data parallelism
- PCIe bandwidth (~32 GB/s for PCIe 4.0 x16) is the bottleneck for offloaded layers

---

## 4. Model Recommendations by Hardware

### What Model Fits Where?

| Hardware | RAM/VRAM | Best Model | Fits? | Strategy |
|---|---|---|---|---|
| **M1/M2/M3 Air** | 16GB (12GB GPU) | qwen3:8b Q4 (5.2GB) | ✅ | Only small models fit |
| **M1/M2/M3 Air** | 16GB | 35b-a3b Q4 (24GB) | ❌ | Does not fit |
| **M-Pro 32GB** | 32GB (24GB GPU) | 35b-a3b Q4 (24GB) | ⚠️ Tight | Model barely fits, little KV headroom |
| **M-Pro 36GB** | 36GB (27GB GPU) | 35b-a3b Q4 (24GB) | ✅ | ~3GB KV headroom |
| **M-Max 64GB** | 64GB (48GB GPU) | 35b-a3b Q8 (39GB) | ✅ | ~9GB KV headroom |
| **M-Ultra 128GB** | 128GB (96GB GPU) | 122b-a10b Q4 (81GB) | ✅ | ~15GB KV headroom |
| **RTX 4090 24GB** | 24GB VRAM | 35b-a3b Q4 (24GB) | ✅ | Fits entirely in VRAM |
| **RTX 4090 24GB** | 24GB + 64GB RAM | 122b-a10b Q4 (81GB) | ⚠️ | Expert offloading via `--n-cpu-moe` |
| **RTX 5090 32GB** | 32GB VRAM | 35b-a3b Q8 (39GB) | ⚠️ | Layer offloading for last ~7GB |
| **2×RTX 4090** | 48GB VRAM | 35b-a3b Q8 (39GB) | ✅ | Tensor split across GPUs |
| **A100 80GB** | 80GB VRAM | 122b-a10b Q4 (81GB) | ⚠️ | Just barely, minimal KV headroom |

### CoDRAG Pipeline Task Recommendations

| Task | Best Model | Think | num_predict | Why |
|---|---|---|---|---|
| **Augmentation** (per-file) | 35b-a3b Q4 | OFF | 2048 | Fastest, simple JSON |
| **Epistemic** (per-file) | 35b-a3b Q4 | OFF | 2048 | Speed matters, good quality |
| **Group Reasoning** | 35b-a3b Q4 | **ON** | 8192 | Think genuinely improves patterns |
| **Atlas** (small repo) | 35b-a3b Q4 | OFF | 4096 | Model self-terminates |
| **Atlas** (large repo) | 35b-a3b Q4 | OFF | 32768 | Models utilize larger budget |
| **Audit** | 35b-a3b Q4 | OFF | 16384 | Generous for detailed report |

### If You Want Maximum Quality (and Have Time)

| Task | Premium Model | Think | Notes |
|---|---|---|---|
| Group Reasoning | 122b-a10b | ON | Deepest architectural insights |
| Atlas | 122b-a10b | OFF | Most accurate IDENTITY section |
| Epistemic | 27b Q8 (dense) | OFF | Richest tech debt analysis (22× slower) |

---

## 5. Ollama Configuration Reference

### Key Parameters

| Parameter | Where | Effect | CoDRAG Default |
|---|---|---|---|
| `num_predict` | `options.num_predict` | Max generation tokens (thinking + response shared) | Dynamic via `context_config.py` |
| `num_ctx` | `options.num_ctx` | Total context window (prompt + response) | Auto-computed |
| `think` | `payload.think` | Enable reasoning trace | Per-task (ON for Group Reasoning only) |
| `temperature` | `options.temperature` | Sampling randomness | 0.3 (Atlas/Audit), 0.6 (Group Reasoning) |
| `num_gpu` | `options.num_gpu` | Layers offloaded to GPU | Default (all) |
| `-ngl` | CLI only | GPU layers (llama.cpp) | N/A (Ollama manages) |
| `--n-cpu-moe` | CLI only | MoE expert CPU offload layers | N/A (manual tuning) |

### Think Mode Budget (llm_client.py)

When `think=True`, `num_predict` is automatically scaled:
```
effective_num_predict = max(num_predict × 3, num_predict + 8192)
```
This ensures the model has budget for both reasoning trace AND the actual response.

**⚠️ Known issue:** For prose tasks (Atlas, Audit) on small repos, the 3× multiplier creates an excessively large budget (e.g., 16384 × 3 = 49152 tokens for a 500-token prompt). The model spends minutes generating thinking tokens. **Recommendation:** Don't use think mode for prose tasks — it's counterproductive (see Phase 46 RESEARCH.md §4d).

---

## 6. Integration with Phase 45 (Multi-GPU / AI Gateway)

### How context_config.py Maps to AI Gateway

The Phase 45 `ComputeNode` interface includes `gpu_vram_gb`:
```typescript
interface ComputeNode {
  gpu_vram_gb?: number;  // 24, 96, etc.
  hardware_profile?: 'apple_silicon' | 'nvidia' | ...;
}
```

`context_config.py` should eventually pull VRAM from the AI Gateway's compute node config rather than auto-detecting:
```python
# Future: read from AI Gateway config
vram_gb = compute_node.gpu_vram_gb or detect_available_vram_gb()
is_mac = compute_node.hardware_profile == "apple_silicon"
```

### Concurrency × Context Window Interaction

On Apple Silicon (concurrency=1), the full GPU memory is available for one model's context window.

On NVIDIA with concurrency>1, each concurrent request needs its own KV cache allocation. This means:
- `available_vram_for_kv = VRAM - model_size`
- `kv_per_request = num_ctx × kv_per_1k / 1000`
- `max_concurrent = available_vram_for_kv / kv_per_request`

Example: RTX 4090 (24GB) with 35b-a3b Q4 (24GB):
- Available for KV: ~0GB → concurrency=1 only
- With layer offloading (model uses 18GB VRAM): 6GB for KV → ~3-4 concurrent with 8K context

This interaction should be modeled in the AI Gateway's concurrency settings.

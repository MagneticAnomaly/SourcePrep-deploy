# Hardware & VRAM Tier Recommendations for CoDRAG
*Based on large-context benchmark results across qwen3.5 dense and MoE models.*

> **⚠️ CORRECTION (Mar 7 2026):** The "RAM Swap Theory" section below contained
> inaccurate claims about MoE models and Mac memory swapping. The corrected
> analysis is in `docs/Phase46_large-context-window-research-reccommendations-tooling/RESEARCH.md`
> Section 6. Key corrections:
> - Mac has NO "VRAM ↔ System RAM swap" — it's all the same unified memory.
> - ALL model params must fit in RAM on Mac, regardless of MoE/dense.
> - A 24GB model does NOT fit on a 16GB Mac — there's nowhere to "swap" to.
> - MoE speed advantage is computational (fewer FLOPs), not memory-based.
> - On NVIDIA, MoE expert offloading (--n-cpu-moe) IS a real memory advantage.

## ~~RAM Swap Theory: Why MoE Models Win on Mac~~ (INCORRECT — see correction above)
~~Apple Silicon unifies VRAM and System RAM. When a model exceeds available RAM/VRAM, macOS uses aggressive memory swapping (paging to the SSD).~~
~~- **Dense Models (e.g., 27b):** Must load all 27 billion parameters into active memory for *every single token generated*. If the model is 17GB (Q4) but the system only has 16GB free, the Mac swaps to disk constantly, crippling generation speed to <1 token/s.~~
~~- **MoE Models (e.g., 35b-a3b, 122b-a10b):** A Mixture-of-Experts model only activates a small subset of parameters per token. The 35b-a3b has 35 billion parameters total, but only **3 billion active** per token. The 122b-a10b has 122B total, but only **10B active**. The OS page manager keeps the active experts in RAM and leaves the inactive ones swapped to disk or compressed. This allows a 24GB MoE model to run incredibly fast on a 16GB Mac because the active working set easily fits in memory.~~

---

## Model Recommendations by Hardware Tier

### Tier 1: 16GB RAM / VRAM (Entry Level)
*Typical: M1/M2/M3 MacBook Air/Pro base models, RTX 4080 (16GB)*
- **Fast Tier (Augmentation/Epistemic):** `qwen3.5:35b-a3b` (Q4 - 24GB). Thanks to MoE swapping, this will run fast despite exceeding RAM.
- **Deep Tier (Group Reasoning):** `qwen3.5:35b-a3b` (Q4) with `think=True`.
- **Scope Tier (Atlas/Audit):** `qwen3.5:35b-a3b` (Q4). Limit context windows to ~10K tokens (Top 50 modules) to prevent prompt evaluation from thrashing memory.
- *Avoid:* Dense models >14B. The 27b will thrash the swap file heavily.

### Tier 2: 24GB - 32GB RAM / VRAM (Mid-Range)
*Typical: M1/M2/M3 Pro Macs (36GB), RTX 3090/4090 (24GB), Mac Studio (32GB)*
- **Fast Tier (Augmentation/Epistemic):** `qwen3.5:35b-a3b-q8_0` (Q8 - 39GB). The Q8 model's active parameters easily fit in 24GB.
- **Deep Tier (Group Reasoning):** `qwen3.5:35b-a3b-q8_0` with `think=True`.
- **Scope Tier (Atlas/Audit):** `qwen3.5:35b-a3b-q8_0` (Q8). This tier unlocks the ability to use 20K+ token context windows (Top 100 modules). Q8 quantization dramatically improves the model's ability to maintain coherence over large context windows.
- *Avoid:* 122b models; prompt processing at 81GB will be too slow.

### Tier 3: 64GB - 128GB RAM (High-End Mac)
*Typical: Mac Studio M-Max/Ultra, MacBook Pro Max (64GB-128GB)*
- **Fast Tier (Augmentation/Epistemic):** `qwen3.5:35b-a3b-q8_0` (Fastest and highly accurate).
- **Deep Tier (Group Reasoning):** `qwen3.5:35b-a3b-q8_0` with `think=True`.
- **Scope Tier (Atlas/Audit):** `qwen3.5:122b-a10b` (81GB). This model has 10B active parameters and fits comfortably in 128GB of RAM. It delivers the highest quality architectural insights and the most accurate Atlas generations.
- *Alternative Scope:* If speed is preferred over the absolute deepest context, use `qwen3.5:35b-a3b-q8_0`, which processes Atlas prompts 2-3x faster than the 122b.

### Tier 4: Dual GPU / Data Center (e.g. 2x 32GB NVIDIA)
*Typical: Cloud VMs, multi-GPU rigs*
- Since VRAM is strictly partitioned (no Apple unified memory magic), MoE models must be split across GPUs. 
- The `qwen3.5:122b-a10b` (81GB) requires at least 3-4x 24GB GPUs or 2x 48GB GPUs.
- The `qwen3.5:35b-a3b-q8_0` (39GB) runs comfortably spanning two 24GB GPUs.

---

## Critical Settings Summary

1. **Think Mode Rules:**
   - `think=True` produces significantly better architectural patterns for JSON/Structured outputs (Group Reasoning).
   - **DO NOT use `think=True` for Prose tasks (Atlas, Audit).** All tested Qwen models leak their thinking process directly into the final prose output, ruining the document format.

2. **Context Window Limits:**
   - MoE models (35b, 122b) scale their output quality effectively with larger context (Top 100 modules vs Top 50).
   - Low-quantization dense models (27b Q4) **degrade** when given larger contexts (output length drops by 20%). Always use Q8 if large context (>10K tokens) is required.

3. **Module Capping:**
   - Atlas prompts must be capped at max ~18K tokens (Top 100 modules). Uncapped repositories like CoDRAG (3,300 modules) generate 420K+ token prompts, blowing past the 256K limit.

"""Dynamic context window configuration for RunPrep pipeline tasks.

Phase 46: Auto-scales num_predict and num_ctx based on task type,
prompt size, model, and available VRAM.  Provides warnings when
context requirements exceed hardware capacity.

The key insight from benchmarking (Mar 2026):
- Ollama's num_predict is a SHARED budget for thinking + response tokens.
- Models utilize larger num_predict budgets proportionally for large inputs
  (e.g., 29.6K chars at np=32768 vs 13.6K at np=16384 for 100-module Atlas).
- For small inputs (<5K tokens), models self-terminate around 2.5K eval tokens
  regardless of budget.
- Think mode is handled by llm_client.py (3× auto-scale) — callers should
  pass the base num_predict and let the client layer handle the multiplier.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ── Task types ────────────────────────────────────────────────────────

class PipelineTask(str, Enum):
    AUGMENT = "augment"             # Pass 1: per-file summary (short JSON)
    EPISTEMIC = "epistemic"         # Pass 2: per-file deep analysis (JSON)
    GROUP_REASONING = "group_reasoning"  # Cross-file pattern inference (JSON)
    ATLAS = "atlas"                 # Whole-repo orientation (prose)
    AUDIT = "audit"                 # Whole-repo health report (markdown)
    CLUSTER = "cluster"             # Module synthesis (JSON)


# ── Model metadata ────────────────────────────────────────────────────

# Model file sizes (GB) for VRAM estimation
MODEL_SIZES_GB = {
    "qwen3.5:35b-a3b": 24.0,
    "qwen3.5:35b-a3b-q8_0": 39.0,
    "qwen3.5:27b": 17.4,
    "qwen3.5:27b-q8_0": 30.0,
    "qwen3.5:122b-a10b": 81.4,
    "qwen3:8b": 5.2,
    "qwen3:4b-instruct": 2.5,
    "qwen3-coder:30b": 18.6,
}

# KV cache overhead per 1K context tokens (MB) — approximate
# MoE models have smaller KV caches because fewer layers are active
KV_CACHE_MB_PER_1K = {
    "qwen3.5:35b-a3b": 0.5,
    "qwen3.5:35b-a3b-q8_0": 0.8,
    "qwen3.5:27b": 2.0,
    "qwen3.5:27b-q8_0": 3.0,
    "qwen3.5:122b-a10b": 1.0,
    "qwen3:8b": 0.8,
    "qwen3:4b-instruct": 0.4,
    "qwen3-coder:30b": 1.5,
}

# Maximum context window supported by each model (tokens)
MAX_CONTEXT = {
    "qwen3.5:35b-a3b": 262_144,
    "qwen3.5:35b-a3b-q8_0": 262_144,
    "qwen3.5:27b": 262_144,
    "qwen3.5:27b-q8_0": 262_144,
    "qwen3.5:122b-a10b": 262_144,
    "qwen3:8b": 131_072,
    "qwen3:4b-instruct": 131_072,
    "qwen3-coder:30b": 131_072,
}


# ── VRAM detection ────────────────────────────────────────────────────

def detect_available_vram_gb() -> float:
    """Best-effort detection of memory available for model loading (GB).

    - macOS (Apple Silicon): Returns ~75% of total unified memory.
      macOS reserves ~25% for OS/CPU tasks; the Metal GPU backend
      (`recommendedMaxWorkingSetSize`) limits GPU allocations to ~75%.
      The entire model must fit in this budget — there is no separate
      VRAM on Mac, and SSD paging is too slow to be viable.
    - Linux/Windows with NVIDIA: Returns total dedicated GPU VRAM.
      On NVIDIA, models that exceed VRAM can be partially offloaded to
      system RAM via llama.cpp layer offloading, but this is slower.
    - Fallback: Returns 0.0 (caller should use user-configured value).
    """
    system = platform.system()

    if system == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=5,
            ).strip()
            total_gb = int(out) / (1024 ** 3)
            # macOS Metal limits GPU to ~75% of unified memory
            return total_gb * 0.75
        except Exception:
            pass

    elif system in ("Linux", "Windows"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=5,
            ).strip()
            # Sum across GPUs (multi-GPU)
            total_mb = sum(int(line.strip()) for line in out.splitlines() if line.strip())
            return total_mb / 1024
        except Exception:
            pass

    return 0.0


def detect_system_memory_gb() -> float:
    """Detect total system RAM in GB (raw, not GPU-adjusted).

    Unlike ``detect_available_vram_gb()`` which returns the GPU-usable
    portion, this returns the physical RAM installed.  Used by the
    embedding scheduler to decide concurrency limits.

    Returns 0.0 on detection failure.
    """
    system = platform.system()

    if system == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=5,
            ).strip()
            return int(out) / (1024 ** 3)
        except Exception:
            pass

    elif system == "Linux":
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # Format: "MemTotal:       16384000 kB"
                        kb = int(line.split()[1])
                        return kb / (1024 ** 2)
        except Exception:
            pass

    elif system == "Windows":
        try:
            out = subprocess.check_output(
                ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"],
                text=True, timeout=5,
            ).strip()
            # Output has a header line, then the value in bytes
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line) / (1024 ** 3)
        except Exception:
            pass

    return 0.0


# ── Core sizing functions ─────────────────────────────────────────────

def compute_num_predict(
    task: PipelineTask,
    prompt_tokens: int,
    *,
    think: bool = False,
) -> int:
    """Compute the optimal num_predict for a given task and prompt size.

    This returns the BASE num_predict.  The llm_client.py layer will
    automatically scale by 3× when think=True — callers should NOT
    pre-multiply.

    Benchmarked findings (RunPrep repo, Mar 2026):
    - Atlas with 100 modules (~18K tokens): np=32768 → 29.6K chars output
    - Atlas with 50 modules (~10K tokens): np=8192 sufficient (model self-terminates)
    - Group Reasoning: JSON output naturally bounded at ~1-3K tokens
    - Audit: Markdown report, ~3-5K tokens typical
    """
    if task == PipelineTask.AUGMENT:
        return 2048

    if task == PipelineTask.EPISTEMIC:
        return 2048

    if task == PipelineTask.CLUSTER:
        return 4096

    if task == PipelineTask.GROUP_REASONING:
        return 8192

    if task == PipelineTask.AUDIT:
        # Audit reports benefit from generous budget
        if prompt_tokens < 5000:
            return 8192
        return 16384

    if task == PipelineTask.ATLAS:
        # Atlas output scales with input size when given room
        if prompt_tokens < 5000:
            return 4096       # small repo, model self-terminates ~2.5K
        elif prompt_tokens < 15000:
            return 16384      # medium repo
        else:
            return 32768      # large repo, let model fill

    # Fallback
    return 4096


def compute_num_ctx(
    prompt_tokens: int,
    num_predict: int,
    model: str = "",
) -> int:
    """Compute the minimum num_ctx needed for prompt + response.

    Returns the context window size that should be passed to Ollama's
    options.num_ctx.  Includes a safety margin.

    If the model's max context is smaller, clamps to that.
    """
    # prompt + response + 512 safety margin
    needed = prompt_tokens + num_predict + 512

    max_ctx = MAX_CONTEXT.get(model, 262_144)
    return min(needed, max_ctx)


def compute_module_cap(
    total_modules: int,
    available_vram_gb: float = 0.0,
    model: str = "",
) -> int:
    """Compute how many modules to include in an Atlas prompt.

    Large repos (3000+ modules) produce prompts that exceed any model's
    context window.  This caps the module count to keep the prompt within
    a usable range while maximizing coverage.

    Returns:
        Module cap (int).  Pass this to sorted_modules[:cap].
    """
    if total_modules <= 100:
        return total_modules  # no capping needed

    # For large repos, cap based on available VRAM
    # Each module adds ~180 chars (~45 tokens) to the prompt
    # Target: keep Atlas prompt under ~20K tokens for mid-range hardware
    if available_vram_gb >= 64:
        return min(total_modules, 150)  # ~27K tokens, fits in 128K ctx
    elif available_vram_gb >= 32:
        return min(total_modules, 100)  # ~18K tokens
    elif available_vram_gb >= 16:
        return min(total_modules, 75)   # ~13K tokens
    else:
        return min(total_modules, 50)   # ~9K tokens, conservative


def estimate_vram_usage_gb(
    model: str,
    num_ctx: int,
) -> float:
    """Estimate total VRAM usage for a model + context window.

    Returns approximate GB needed (model weights + KV cache).
    """
    model_gb = MODEL_SIZES_GB.get(model, 20.0)
    kv_per_1k = KV_CACHE_MB_PER_1K.get(model, 1.0)
    kv_gb = (num_ctx / 1000) * kv_per_1k / 1024
    return model_gb + kv_gb


# ── High-level convenience ────────────────────────────────────────────

def compute_optimal_settings(
    task: PipelineTask,
    prompt_tokens: int,
    model: str,
    *,
    think: bool = False,
    available_vram_gb: Optional[float] = None,
) -> Tuple[int, int, list]:
    """Compute optimal (num_predict, num_ctx) with VRAM awareness.

    Returns:
        (num_predict, num_ctx, warnings)
        where warnings is a list of human-readable warning strings.
        num_predict is the BASE value — llm_client handles think scaling.
    """
    if available_vram_gb is None:
        available_vram_gb = detect_available_vram_gb()

    warnings = []

    num_predict = compute_num_predict(task, prompt_tokens, think=think)

    # For think mode, the effective budget is 3× — account for that in ctx
    effective_np = max(num_predict * 3, num_predict + 8192) if think else num_predict
    num_ctx = compute_num_ctx(prompt_tokens, effective_np, model)

    vram_needed = estimate_vram_usage_gb(model, num_ctx)

    is_mac = platform.system() == "Darwin"
    # On Mac: model MUST fit in GPU-available unified memory (~75% of total RAM).
    # On NVIDIA: model can spill to system RAM via layer offloading (slower but works).
    safety_factor = 0.85 if is_mac else 0.95  # Mac needs more headroom for OS

    if available_vram_gb > 0 and vram_needed > available_vram_gb * safety_factor:
        headroom_gb = available_vram_gb * safety_factor - MODEL_SIZES_GB.get(model, 20.0)
        if headroom_gb <= 0:
            if is_mac:
                warnings.append(
                    f"Model {model} ({MODEL_SIZES_GB.get(model, '?')}GB) exceeds "
                    f"available GPU memory ({available_vram_gb:.0f}GB) on this Mac. "
                    f"The model must fit in memory — there is no VRAM swap on Apple Silicon. "
                    f"Consider a smaller model (e.g., qwen3:8b) or higher quantization."
                )
            else:
                warnings.append(
                    f"Model {model} ({MODEL_SIZES_GB.get(model, '?')}GB) exceeds "
                    f"GPU VRAM ({available_vram_gb:.0f}GB). Layers will be offloaded "
                    f"to system RAM, which is slower. For best speed, use a model "
                    f"that fits entirely in VRAM."
                )
        else:
            kv_per_1k = KV_CACHE_MB_PER_1K.get(model, 1.0)
            max_ctx_tokens = int(headroom_gb * 1024 / kv_per_1k * 1000)
            if max_ctx_tokens < prompt_tokens + 1024:
                warnings.append(
                    f"Prompt ({prompt_tokens} tokens) is too large for available "
                    f"VRAM ({available_vram_gb:.0f}GB) with model {model}. "
                    f"Consider reducing module cap or using a smaller model."
                )
            else:
                old_np = num_predict
                num_ctx = min(num_ctx, max_ctx_tokens)
                num_predict = max(1024, num_ctx - prompt_tokens - 512)
                if num_predict < old_np:
                    warnings.append(
                        f"Context window scaled back: num_predict reduced from "
                        f"{old_np} to {num_predict} due to VRAM constraint "
                        f"({available_vram_gb:.0f}GB). For deeper output, "
                        f"consider upgrading RAM or using a smaller model."
                    )
                    # Recompute num_ctx with scaled-back num_predict
                    effective_np = max(num_predict * 3, num_predict + 8192) if think else num_predict
                    num_ctx = compute_num_ctx(prompt_tokens, effective_np, model)

    for w in warnings:
        logger.warning(w)

    return num_predict, num_ctx, warnings

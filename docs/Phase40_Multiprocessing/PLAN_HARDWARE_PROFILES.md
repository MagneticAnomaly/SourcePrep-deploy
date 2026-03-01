# Phase 40C: Hardware Profiles & Unified VRAM Management

> **Status:** Planning  
> **Goal:** Rethink the "Pipeline Performance" UI and automate VRAM management across multiple inference backends (Ollama + LM Studio) that share the same physical hardware.

---

## 1. The Death of Manual Concurrency (For Local)

### Why the current UI is obsolete
Currently, the settings page asks users to manually set concurrency sliders for Fast, Code, and Deep models. Based on our extensive Phase 40 benchmarks, this is fundamentally flawed for our target audience:
1. **Apple Silicon (Mac Studio/MacBook):** Concurrency > 1 provides only a **5-9% speedup** but risks VRAM fragmentation and context explosion. It should be strictly locked to `1`. Manual sliders just allow users to break their local setup for zero gain.
2. **Cloud APIs:** Concurrency should be high (e.g., 5-10) because network latency is the bottleneck, not memory bandwidth. 
3. **Discrete GPUs (NVIDIA):** Concurrency actually works here (1.5-2x speedups) because each request gets dedicated VRAM bandwidth.

**Conclusion:** We are asking the user to tune a knob that only makes sense if they understand hardware memory architectures. We should automate this.

### The New Paradigm: Endpoint Hardware Profiles
We will completely **delete the "Pipeline Performance" section** from the Global settings tab. 

Instead, CoDRAG will tie concurrency to the **Inference Provider / Endpoint**. This perfectly handles remote execution (e.g., a Mac user connecting to a remote Windows PC over Tailscale). The user configures the hardware profile for *that specific endpoint*.

When configuring an endpoint (Ollama, LM Studio, OpenAI, etc.), the user selects a **Hardware Profile**:

| Profile | Behavior | Use Case |
|---------|----------|----------|
| `Apple Silicon (Unified)` | **Concurrency Locked to 1.** | Local Mac Studio, remote MacBook Pro. Maximizes single-stream tokens/sec and prevents unified memory bandwidth contention. |
| `Dedicated GPU (NVIDIA/AMD)` | **Requires `Max Concurrency` input.** | Local or remote PC with CUDA. User inputs the max concurrent requests (e.g., 2 to 4) based on their VRAM and model size. |
| `Cloud API` | **Requires `Max Concurrency` input.** | OpenAI, Anthropic, DeepSeek. User sets high concurrency (e.g., 5-10) for network-bound tasks. |

**Why not auto-calculate from a "VRAM (GB)" input?**
If a user inputs "24GB VRAM", CoDRAG still doesn't know the exact loaded size of the model (especially via LM Studio's OpenAI endpoint, where the model size is hidden behind an API). Calculating `(24GB - Model_Size) / KV_Cache_Size` is brittle.
Instead, giving the user a **Max Concurrency setting per-endpoint** (only visible for Dedicated GPU and Cloud profiles) provides the exact control they need without the fragility of estimating memory footprints.

**How it works in the Orchestrator:**
When Stage 3 (Fast) runs, it looks up the Fast Model's assigned endpoint. If that endpoint is set to "Apple Silicon", it uses a concurrency of 1. If the Deep Model is hosted on a "Dedicated GPU" endpoint with Max Concurrency set to 3, Stage 6 runs with a concurrency of 3. The pipeline automatically throttles itself based on the endpoint's configured limits.

---

## 2. Unified VRAM Management (Resource Pools)

### The Problem
If the user runs Ollama on port 11434 and LM Studio on port 1234 on the *same Mac Studio*, they share the same physical 128GB of unified memory. If CoDRAG treats them as separate servers, it might leave an 80B model loaded in Ollama while trying to load a 27B model in LM Studio, causing an Out of Memory (OOM) crash.

### The Solution: Resource Pools
We introduce the concept of `GPU Resource Pools`. 

**Configuration:**
- **Pool 1: "Local Host"** (Type: Apple Silicon)
  - Endpoint A: Ollama (`http://localhost:11434`)
  - Endpoint B: LM Studio (`http://localhost:1234`)

**The VRAM Lifecycle Manager:**
Before starting a pipeline stage, the Orchestrator checks which model it needs and which Endpoint it lives on.
1. It looks up the Endpoint's Resource Pool ("Local Host").
2. It sees that Ollama and LM Studio share this pool.
3. It sends an **UNLOAD command to ALL other endpoints in the pool** before loading the new model.
   - *Example:* Transitioning from Stage 3 (Fast, Ollama) to Stage 6 (Deep, LM Studio).
   - CoDRAG calls `POST /api/generate` with `keep_alive: 0` to Ollama.
   - Then CoDRAG sends the chat request to LM Studio (which auto-loads the MLX model into the now-freed VRAM).

---

## 3. LM Studio Unload API Support

To make this work, CoDRAG needs an LM Studio-specific adapter.

LM Studio implements the OpenAI API, but standard OpenAI doesn't have an "unload" endpoint. Fortunately, LM Studio provides its own REST API (`/api/v0`) and CLI (`lms`).

**How CoDRAG will unload LM Studio models:**
LM Studio's `/api/v0/models` endpoint shows loaded models. To unload via REST, the safest programmatic way in LM Studio is currently setting a TTL, or using their internal memory management endpoints. Since LM Studio v0.3+, they provide ways to evict models to free space. If a direct REST unload isn't exposed, CoDRAG can execute `lms unload --all` via local shell (if local) or rely on LM Studio's "Evict to fit" setting.

*Note: We will need to test LM Studio's exact REST unload sequence, or instruct the user to enable "Just-in-Time Loading / Evict to Fit" in LM Studio settings so it automatically drops its own models when memory pressure hits (though it won't drop Ollama's models).*

---

## 4. Programmatic Context Window Management

The `qwen3.5-27b` model crashed in LM Studio because by default, LM Studio attempts to allocate the maximum context window supported by the model (256K for Qwen3.5). At BF16 precision, allocating 256K context instantly OOMs a 128GB Mac.

**Instead of relying on the user to manually cap context length in the UI, CoDRAG will enforce it programmatically.**

### Enforcing Context Limits via API
Both LM Studio (OpenAI compat) and Ollama support passing context limits at the *request* level or *load* level.

**For Ollama:**
We already pass `num_ctx: 32768` in the `options` block of the generate request:
```json
{
  "model": "qwen3.5:27b",
  "prompt": "...",
  "options": {
    "num_ctx": 32768
  }
}
```

**For LM Studio (OpenAI Endpoint):**
The standard OpenAI `/v1/chat/completions` endpoint doesn't officially support `max_context_length`. However, LM Studio's `/api/v0/models/load` REST API allows explicit context configuration:
```bash
POST /api/v0/models/load
{
  "model": "qwen3.5-27b",
  "context_length": 32768,
  "gpu_offload": "max"
}
```

**Implementation in the Lifecycle Manager:**
When the VRAM Lifecycle Manager (Phase 40C) transitions models, it won't just rely on "Just-In-Time" loading by hitting the chat endpoint. Instead:
1. It will hit `POST /api/v0/models/load`.
2. It will explicitly request a `context_length` of 32768 (or whatever is set in CoDRAG settings).
3. This prevents the "256K auto-allocation" crash and guarantees the model loads cleanly within VRAM limits.

---

## 5. Summary of Proposed Changes

1. **Remove manual concurrency sliders** from the main settings UI.
2. **Add "Hardware Profile" selection** to the AI Provider configuration.
3. **Implement GPU Resource Pools** in the backend to link Ollama and LM Studio together for VRAM clearing.
4. **Build LM Studio API adapter** to handle explicit model state checking, explicit loading with bounded `context_length`, and unloading.

# Swarm UI & Configuration Plan

## 1. The Problem: The "Thinking" Slot Overload
Currently, CoDRAG's `Large` (Thinking) slot serves a dual purpose in the Deep Enrichment pipeline:
1.  **Individual File Reasoning (Worker):** Executing the epistemic analysis on single files and their direct structural neighbors.
2.  **Swarm Orchestration (Coordinator & Synthesis):** Reading summaries of hundreds of files, deciding how to partition them, and then synthesizing the final outputs into cohesive Domain Modules.

This becomes a problem with frontier open-weight reasoning models like **Kimi 2.5**:
- Kimi 2.5 is excellent at individual file reasoning.
- Kimi 2.5 is *terrible* at being a Swarm Coordinator because it hits token exhaustion (Bug F-29) writing its `<think>` tags, failing to output the rigid JSON routing schemas that the Swarm Fan-out requires. 

Conversely, **Gemini 3 Flash** is incredibly fast, has a massive 1M context window for synthesis, and flawlessly outputs JSON without the "thinking" overhead. 
However, right now, users cannot assign Gemini 3 Flash strictly as the Coordinator while keeping Kimi 2.5 as the deep-thinking Worker. 

## 2. Proposed Solution: Decoupled Swarm Slots
We need to separate the single `Large` configuration into distinct Swarm roles, allowing users to leverage hybrid multi-model strategies. 

### API / Config Changes (`codrag/types.ts` & `codrag/config_manager.py`)
Add a new dedicated configuration block for Swarm Coordination.
If a user leaves the Coordinator unassigned, CoDRAG will gracefully fall back to using the `Large` (Thinking) model for both, preserving backward compatibility.

```json
"llm": {
  "small": { "endpoint_id": "local", "model": "qwen3:4b" }, // NO 4B is way too small 8 b is questionable too small
  "large": { "endpoint_id": "cloud", "model": "kimi-k2.5:cloud" },
  "coordinator": { "endpoint_id": "cloud", "model": "gemini-3-flash-preview:cloud" }, // NEW
  "code": { "endpoint_id": "local", "model": "qwen3-coder:30b" }
}
```

### Python Backend Changes (`src/codrag/core/swarm_orchestrator.py`)
The `SwarmOrchestrator` constructor currently accepts a single `llm: LLMClient`. It needs to be updated to accept:
- `coordinator_llm: LLMClient` (Handles Phase 1: Planning and Phase 3: Synthesis)
- `worker_llm: LLMClient` (Handles Phase 2: Fan-out execution)

```python
class SwarmOrchestrator:
    def __init__(
        self,
        coordinator_llm: LLMClient,
        worker_llm: LLMClient,
        # ...
```
This requires plumbing changes through `deep_enrichment.py` and `cluster.py` to initialize the Swarm with both configured models.

## 3. UI Implementation Plan (`AIModelsSettings.tsx`)

### The Visual Layout
We should introduce a new card in the AI Models Settings specifically for Swarm Orchestration, placed right beneath the Thinking Model.

1.  **⚡ Fast Model (Small)** 
    - Used for: File cataloguing, intent detection
    - Recommended: `qwen3:4b`
2.  **🧠 Thinking Model (Large / Swarm Worker)**
    - Used for: Deep reasoning, epistemic enrichment, Swarm Fan-out
    - Recommended: `kimi-k2.5:cloud` or `qwen3:14b`
3.  **🐝 Swarm Coordinator (New)**
    - Used for: Cluster routing, large-context synthesis
    - Recommended: `gemini-3-flash-preview:cloud`
    - *UI State:* Needs an "Inherit from Thinking Model" toggle so users aren't forced to configure it if they just want a simple setup.
4.  **💻 Code Model**
    - Used for: Edge discovery, structural tracing
    - Recommended: `qwen3-coder-next:cloud`

### Component Modifications
- **`ModelCard.tsx`**: Add support for a `'coordinator'` slot type.
- **`AIModelsSettings.tsx`**: Render the new Swarm Coordinator `ModelCard`. Add `gemini-3-flash` to the `RECOMMENDED_MODELS['coordinator']` constant.
- **`useDashboardPanels.tsx`**: Wire the `'coordinator'` slot to the backend configuration saving loop.

## 4. Benefits of this Architecture
1. **Cost Efficiency:** Users can run cheap local reasoning models (like `qwen3:8b`) for the 500+ worker tasks, while leveraging a cheap, fast API like Gemini 3 Flash for the 2 massive synthesis tasks.
2. **Eliminates Stalls:** By routing the JSON-heavy orchestration to Gemini and the reasoning-heavy file analysis to Kimi, we bypass the F-29 thinking bug without sacrificing deep analysis quality.
3. **Extensibility:** Positions CoDRAG perfectly for future massive-context routing tasks as open-weight models begin to catch up to the 1M+ context tiers.

## 5. Uncapped Cloud Optimization (The "Deep Pockets" Strategy)
With the understanding that Ollama Cloud limits are based on dynamic GPU time rather than a hard server-side 16K token cap, and assuming the user has "deep pockets" (or the Max plan), we can vastly optimize our recommended stack:
`kimi-k2.5:cloud` (Worker) + `gemini-3-flash-preview:cloud` (Coordinator) + `qwen3-coder-next:cloud` (Code)

Instead of ripping out CoDRAG's built-in safety limits, we will preserve them but move them to a new **Advanced Settings** panel, defaulting to OFF (uncapped) for power users.

### 5.1. Make the `CLOUD_SMALL` (16K) Bottleneck Configurable
**File:** `src/codrag/core/batch_profiles.py`
Currently, any model containing `:cloud` is forced into the `CLOUD_SMALL` profile (maximum 16K output, batch sizes 5-8). 
- *Action:* We will add a toggle in Advanced Settings: "Enforce Cloud Token Safety Limits" (default: disabled).
- *Impact:* When disabled, `gemini-3-flash-preview:cloud` promotes to the `LARGE` profile (64K output, batch size 100). `qwen3-coder-next:cloud` and `kimi-k2.5:cloud` promote to `STANDARD` (32K output, batch size 50).

### 5.2. Make Kimi's Thinking Budget Configurable
**File:** `src/codrag/core/llm_client.py`
Currently, when `think=True` is enabled, CoDRAG artificially caps `num_predict` at 24,576 to prevent runaway billing.
- *Action:* Add this cap to the Advanced Settings panel alongside the existing "Budget Per Session" controls.
- *Impact:* For `kimi-k2.5:cloud`, users can uncap this entirely. We *want* Kimi to think extensively about complex domain logic before synthesizing. If budget is not a concern, we should let the model utilize its full context for deep chain-of-thought.

### 5.3. Maximize Swarm Concurrency (Dynamic Throttling)
**File:** `src/codrag/core/swarm_orchestrator.py` & `src/codrag/core/cluster.py`
Previously, Bug F-59 was thought to completely hang concurrent `requests.post()` calls. However, Swarm *does* run concurrently, dynamically clamping to 3, 5, or 10 concurrent threads (which perfectly mirrors the Ollama Cloud plan tiers: Free=1, Pro=3, Max=10).
- *Action:* Expose Swarm Concurrency logic in Advanced Settings. Allow users to manually specify their Ollama Cloud plan tier (Free/Pro/Max) or enter a custom concurrency limit, ensuring the internal `ThreadPoolExecutor` correctly maximizes parallel execution without overwhelming their specific plan's queue.
- *Impact:* This guarantees that a user on the Max plan can consistently push 10 concurrent Swarm Workers, maximizing throughput for Kimi's deep reasoning passes.

### 5.5. Implementation TODOs (Advanced Settings Migration)
- [ ] **TODO:** Build "Advanced LLM Settings" UI panel (nested under or near AI Models).
- [ ] **TODO:** Add "Enforce Cloud Token Safety Limits" toggle (default: false for power user stack). Wire to `is_cloud_model_via_ollama` in `batch_profiles.py`.
- [ ] **TODO:** Add "Max Thinking Budget" input. Wire to `llm_client.py` to bypass the 24K `num_predict` hardcap when `think=True`.
- [ ] **TODO:** Add "Ollama Cloud Plan" selector (Free/Pro/Max/Custom) to dictate Swarm concurrency.

## 6. Dynamic Swarm Batching & Concurrency Optimizer
To maximize the `kimi-k2.5` + `gemini-3-flash` stack across different Ollama Cloud plans (Free, Pro, Max), we cannot rely on static batch profiles. We need a dynamic tool that calculates the optimal `batch_size` and `concurrency` at runtime based on the actual plan constraints.

### The Real Limitations (Ollama Cloud)
1. **Free Plan:** 1 Concurrent Model. (Severe bottleneck. High usage will quickly hit session caps).
2. **Pro Plan:** 3 Concurrent Models. (50x more usage allowance).
3. **Max Plan:** 10 Concurrent Models. (5x more than Pro).
*Constraint:* Billing is by **GPU Time**, meaning heavy reasoning (Kimi) costs exponentially more than fast processing (Gemini).

### Dynamic Tool Design: `get_optimal_swarm_config()`
We will introduce a dynamic calculator in `batch_profiles.py` (or a new `swarm_optimizer.py`) that takes the `model_id`, `plan_tier`, and `total_work_items`, and returns the exact batch size and concurrency to use.

#### Scenario A: The Swarm Worker (`kimi-k2.5:cloud`)
Kimi's goal is deep reasoning per file. Putting too many files in one Kimi prompt dilutes its attention. We want to maximize concurrency first, then scale batch size to cover the remaining files.
- **Formula:** `concurrency = plan_max_slots`, `batch_size = ceil(total_items / concurrency)` (capped at a safe reasoning limit, e.g., 10 files per prompt).
- **Max Plan (100 files):** Concurrency = 10. Batch Size = 10. (Perfect distribution. 10 simultaneous Kimi requests deeply analyzing 10 files each).
- **Pro Plan (100 files):** Concurrency = 3. Batch Size = 34. (Too large for deep reasoning. The tool dynamically caps batch size at 15, yielding ~7 sequential waves across 3 concurrent threads).
- **Free Plan (100 files):** Concurrency = 1. Batch Size = 20. (Will take a long time, but avoids 100 individual API roundtrips).

#### Scenario B: The Swarm Coordinator (`gemini-3-flash-preview:cloud`)
Gemini's goal is massive context synthesis. It has a 1M token window, is incredibly fast, and costs very little GPU time. Concurrency doesn't matter here; batch size is everything.
- **Formula:** `concurrency = 1` (or whatever is needed for disjoint clusters), `batch_size = 100 to 500`.
- **All Plans:** We feed Gemini as much as possible in a single prompt. If Kimi produced 100 JSON outputs, Gemini swallows all 100 in one API call. This leverages its 1M context to perfectly map cross-module dependencies without fragmenting its understanding.

### 6.1. Light Safeguards
Even in an "uncapped" environment, we must maintain *light* safeguards to prevent complete pipeline failures or API timeouts:
- **Kimi Batch Cap:** Never exceed 20 files per batch, even if the math suggests it. Beyond 20, reasoning degrades and JSON schemas break down, regardless of the context window.
- **Gemini Context Buffer:** Cap the synthesis payload at 80% of the 1M token limit (approx. 800K tokens) to leave ample room for the generated output and system prompts.

## 7. Universality & Future Native APIs
While Ollama Cloud's plan tiers (Free/Pro/Max) are the guiding light for this optimizer, the architecture is universally applicable. 

**Future Planning / TODOs:**
- **OpenAI / Anthropic / Google Native:** Direct API providers enforce rate limits via RPM (Requests Per Minute) and TPM (Tokens Per Minute) rather than rigid concurrent connection slots.
- The `get_optimal_swarm_config()` function will be extended to accept these rate limits, translating them into dynamic `concurrency` and `batch_size` thresholds to ride exactly at the edge of the user's tier limits (e.g., OpenAI Tier 1 vs Tier 5).

## 8. MVC Implementation Path: The `Gemini 3` + `Kimi 2.5` Stack
With the research complete, we are ready to move to implementation. The Minimum Viable Configuration (MVC) focuses entirely on establishing this dual-model Swarm flow via Ollama Cloud.

### Step 1: Core Optimizer Logic
Create the dynamic sizing logic that determines `concurrency` and `batch_size` based on model intent (Worker vs Coordinator) and tier limits.
- **Target:** `src/codrag/core/batch_profiles.py` (or a new `swarm_optimizer.py`).

### Step 2: Decoupled Swarm Initialization
Update the Swarm Orchestrator to accept and utilize two distinct LLMs.
- **Target:** `src/codrag/core/swarm_orchestrator.py` & `src/codrag/core/cluster.py`.
- **Change:** Inject `coordinator_llm` (Gemini) and `worker_llm` (Kimi) and apply the optimizer's dynamic sizing to each phase.

### Step 3: UI & Advanced Settings Configuration
Expose the dual slots and the tier/budget controls to the user.
- **Target:** `packages/ui/src/components/llm/AIModelsSettings.tsx`.
- **Change:** Add the Swarm Coordinator slot and the "Advanced Settings" overrides (Ollama Tier selector, Max Thinking Budget, Safety Limits toggle) so Enterprise users can immediately leverage them.

## 9. Recommended Target Optimization Stacks
With Swarm roles decoupled, we can define specific target optimizations. The architectural reality of CoDRAG is that **Worker tasks scale with codebase size `O(N)`** (high volume, small context, needs deep reasoning), while **Coordinator tasks are fixed `O(1)`** (low volume, massive context, needs perfect JSON and synthesis).

This cost/volume profile dictates our recommended stacks:

### Stack A: The Ollama Cloud "Value Performance" (Default Recommended)
*Target: Best ratio of intelligence to zero-friction setup without paid API keys.*
- **Coordinator:** `gemini-3-flash-preview:cloud` (Lightning fast, massive 1M context, cheap GPU time).
- **Worker:** `kimi-k2.5:cloud` (Deep reasoning via `<think>`, handles individual file complexity).
- **Code:** `qwen3-coder-next:cloud` (Specialized structural edge discovery).
- **Fast:** `gemini-3-flash-preview:cloud` (Instanttime-to-first-token, excellent for O(N) high-volume cataloging without draining Ollama GPU credits).

### Stack B: The "Hybrid Hacker" (Maximum ROI)
*Target: Power users who want frontier intelligence but refuse to pay API costs for O(N) file scanning.*
- **Coordinator:** **Anthropic API** `claude-3-7-sonnet` OR **Google API** `gemini-1.5-pro` (Pay $0.50 for a single massive 200K+ token API call to synthesize the entire architecture perfectly).
- **Worker:** **Local / Ollama** `kimi-k2.5:cloud` or `deepseek-r1:14b` (Pay $0 to analyze 500 files locally or via free cloud tier using deep reasoning).
- **Code:** **Local** `qwen3-coder:32b`.
- **Fast:** **Local** `qwen3:8b`.

### Stack C: The Frontier Enterprise (Unlimited Budget)
*Target: Enterprise teams where API cost is irrelevant compared to accuracy and speed.*
- **Coordinator:** **Anthropic API** `claude-3-7-sonnet` (Absolute best-in-class JSON adherence and holistic reasoning across 200K context).
- **Worker:** **Anthropic API** `claude-3-5-haiku` (Blistering fast, parallelizes instantly, excellent coding logic) OR `claude-3-7-sonnet` if budget is truly infinite.
- **Code:** **Anthropic API** `claude-3-7-sonnet`.
- **Fast:** **Anthropic API** `claude-3-5-haiku`.

### Stack D: Fully Local / Air-Gapped
*Target: High-security environments where data cannot leave the machine.*
- **Coordinator:** `command-r:35b` or `qwen2.5:32b` (Requires a model with strong RAG capabilities and at least 128K context window running on 24GB+ VRAM).
- **Worker:** `deepseek-r1:14b` or `qwen3:14b` (Strong local reasoning).
- **Code:** `qwen3-coder:14b` or `32b`.
- **Fast:** `llama-3.2-3b` or `qwen3:8b`.

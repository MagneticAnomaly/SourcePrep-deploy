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
  "small": { "endpoint_id": "local", "model": "qwen3:4b" },
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

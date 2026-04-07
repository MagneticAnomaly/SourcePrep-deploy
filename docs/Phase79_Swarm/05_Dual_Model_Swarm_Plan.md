# Phase 79: Dual-Model Swarm Strategy — Implementation Plan

> Date: 2026-04-07
> Status: Planning / Exploratory
> Goal: Architect a strategy for mixed-model swarms (e.g., Haiku workers + Sonnet coordinator) to optimize cost while maintaining high synthesis quality.

## Background

The initial Phase 79 Swarm design (see `02_Swarm_Integration_Design.md`) assumes a **single-model swarm**: the same model acts as both the Coordinator (Phase 1), the Workers (Phase 2), and the Synthesizer (Phase 3). 

While simple, this leaves cost/quality optimization on the table. As established in `04_SwarmBatch.md`:
- **Worker tasks** (e.g., analyzing a single group) are highly scoped, structurally rigid, and require small context windows. Fast, cheap models like Claude Haiku 4.5 or GPT-5.4 mini excel here.
- **Coordinator/Synthesis tasks** require cross-cutting reasoning, task decomposition, and larger context windows. Frontier models like Claude Sonnet 4.6 or GPT-5.4 are required for highest quality.

A **Dual-Model Swarm** mixed strategy allocates cheaper models to the high-volume worker phase and frontier models to the low-volume coordination phases, maximizing quality while minimizing cost.

## 1. Architectural Changes Required

To support dual-model swarms, the pipeline needs to decouple the unified `STAGE_MODEL_SLOT` concept during swarm execution. 

### Current State
`src/codrag/services/pipeline/stages.py` defines:
```python
STAGE_MODEL_SLOT: Dict[StageId, Optional[str]] = {
    StageId.GROUP_REASONING: "large",
    # ...
}
```
Currently, the `PipelineOrchestrator` resolves `"large"` to a single model identifier before calling the stage's `run()` method. The standard `LLMClient` initialized for that stage is locked to that single model.

### Target State
The `SwarmOrchestrator` needs access to two distinct models. 

1. **Coordinator Client**: Fetched from the `"large"` slot (e.g., Sonnet 4.6).
2. **Worker Client**: Fetched from a new `"small"` fallback slot (e.g., Haiku 4.5), OR the same model if dual-mode is disabled/unavailable.

## 2. Configuration & UI Updates

Users need control over this optimization, as mixing models might not be desired in all environments (e.g., local Ollama deployments where loading a second model into VRAM causes swapping).

**New Pipeline Settings (`codrag_settings.db`)**:
- `swarm_enabled` (bool, default `true`): The existing master toggle.
- `swarm_dual_model` (bool, default `true`): Enable mixed-model routing. If false, uses the stage's primary model for both roles.

**UI Adjustments**:
In the AI Gateway sidebar / Pipeline Settings panel, add a sub-toggle under Swarm Orchestration:
* [x] Enable Agentic Swarm Processing
  * [x] Optimize costs via Dual-Model Swarm (Use smaller, faster models for worker tasks)

## 3. Implementation Steps

### Step 1: Update the Swarm Registry
Modify `swarm_models.json` and `swarm_registry.py` to understand explicit pairing.

```json
{
  "id": "claude-sonnet-4",
  "tier": "coordinator",
  "recommended_worker_pairing": "claude-haiku-4"
}
```

### Step 2: Orchestrator Factory Modification
Update `src/codrag/core/swarm_orchestrator.py` to accept `coordinator_llm` and `worker_llm` separately.

```python
class SwarmOrchestrator:
    def __init__(
        self, 
        coordinator_llm: LLMClient, 
        worker_llm: LLMClient,
        ...
    ):
        self.coordinator_llm = coordinator_llm
        self.worker_llm = worker_llm
```

### Step 3: Stage Resolution Logic
In `PipelineOrchestrator` or `WorkerFactory` (where the stages are instantiated), we must securely resolve the second model without breaking the existing VRAM lifecycle manager.

```python
# Pseudo-logic in pipeline setup
primary_model = resolve_slot(STAGE_MODEL_SLOT[stage_id]) # e.g. "large" -> Sonnet
worker_model = primary_model

if settings.swarm_dual_model and is_swarm_capable(primary_model):
    pairing = get_recommended_pairing(primary_model)
    if pairing and is_model_available(pairing):
        worker_model = resolve_specific_model(pairing)

# Inject both into the stage worker
stage_worker = GroupReasoningEngine(
    llm=primary_model,
    worker_llm=worker_model,  # New optional parameter
    ...
)
```

## 4. Edge Cases & Fallbacks

- **Local VRAM limits**: If running locally on Ollama, loading two models (e.g., Kimi 14b + Llama-3-8b) might cause VRAM thrashing. The `model_readiness.py` pre-flight check must verify if the hardware can support both concurrently. If not, silently fall back to single-model swarm.
- **Provider mixing**: Stick to same-provider pairings by default (Anthropic + Anthropic, OpenAI + OpenAI) to avoid API key dependency issues where a user has one configured but not the other.
- **Fallback**: If `worker_llm` fails to load or error rate spikes, the worker loop should fall back to `coordinator_llm` automatically.

## 5. Cost Savings Estimate

Recalculating the Group Reasoning stage for a 1,000-file repo (25 calls total):

**Single-Model (Claude Sonnet 4.6)**:
- 25 calls total = **~41¢ per run**

**Dual-Model (Sonnet 4.6 Coordinator + Haiku 4.5 Workers)**:
- 2 calls Sonnet (Coord + Synthesis): ~10K tokens = ~8¢
- 23 calls Haiku (Workers): ~70K tokens = ~10¢
- Total = **~18¢ per run**

**Savings: >50% cost reduction** with zero degradation in synthesis quality, making this feature highly valuable for production deployments.

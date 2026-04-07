# Pipeline Stage Execution Profiles

> Phase 79 reference document  
> Date: 2026-04-07  
> Purpose: Define how each pipeline stage should be executed — sequential vs. concurrent vs. swarm — and which model tier each benefits from.

## Overview

CoDRAG's 11-stage pipeline has three execution modes:

| Mode | Pattern | When |
|------|---------|------|
| **Sequential** | One item at a time | Local models with limited VRAM, or stages with inherent ordering |
| **Concurrent** | N items in parallel, independent | Cloud models with token budget, batching-capable stages |
| **Swarm** | Coordinator → N parallel workers → synthesis | Swarm-capable models, stages where cross-item awareness improves quality |

The mode is chosen **per-stage, per-run** based on the model's capabilities and the work volume. A stage that benefits from swarm still runs concurrent when the model isn't swarm-capable.

---

## Stage-by-Stage Profiles

### Stage 1: Structural (Rust Engine)

| Property | Value |
|----------|-------|
| **Queue** | RUST (CPU-only, no GPU) |
| **Execution** | Single-threaded Rust, runs in seconds |
| **LLM needed** | No |
| **Model slot** | None |
| **Concurrency** | N/A — Rust engine handles its own parallelism |
| **Swarm benefit** | None |
| **Notes** | Deterministic. Tree-sitter AST parsing. Always runs first. |

### Stage 2: Inferred Edges

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | Concurrent batches |
| **LLM needed** | Yes — analyzes code to find implicit dependencies |
| **Model slot** | `code` (coder model) |
| **Thinking** | No (`think=False`) |
| **Concurrency** | Uses `llm_concurrency_code` budget, batched per `BatchProfile` |
| **Swarm benefit** | **Low.** Each edge inference is independent — no cross-item reasoning helps. Standard concurrent batching is optimal. |
| **Ideal model** | Fast, cheap, good at code understanding. GPT-5.x-mini, Claude Haiku, Gemini Flash. |
| **Notes** | High volume (hundreds of file pairs). Speed matters more than depth. |

### Stage 3: Catalogue

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | Concurrent batches |
| **LLM needed** | Yes — generates summaries, domain tags, architecture layer |
| **Model slot** | `small` (instruct/fast model) |
| **Thinking** | No (`think=False`) |
| **Concurrency** | Uses `llm_concurrency_fast` budget, batched per `BatchProfile` |
| **Swarm benefit** | **None.** Each file is catalogued independently. Summaries don't benefit from cross-file awareness at this stage. |
| **Ideal model** | Fastest available. This is the highest-volume LLM stage. GPT-5.x-mini, Claude Haiku, Gemini Flash. Frontier models are pure waste here. |
| **Notes** | Largest batch sizes (up to 100 items per call on LARGE profile). Throughput is the bottleneck. |

### Stage 4: Validation (Rust Engine)

| Property | Value |
|----------|-------|
| **Queue** | RUST (CPU-only) |
| **Execution** | Single pass, deterministic |
| **LLM needed** | No |
| **Model slot** | None |
| **Concurrency** | N/A |
| **Swarm benefit** | None |
| **Notes** | Validates edge consistency. Fast. |

### Stage 5: Knowledge (Embeddings)

| Property | Value |
|----------|-------|
| **Queue** | EMBEDDING (ONNX/CoreML/CUDA — independent from LLM server) |
| **Execution** | Batch embedding, hardware-accelerated |
| **LLM needed** | No (uses embedding model, not generative LLM) |
| **Model slot** | None |
| **Concurrency** | Runs in parallel with LLM stages without contention |
| **Swarm benefit** | None |
| **Notes** | Can run alongside any LLM stage. Uses NativeEmbedder (CoreML/CUDA) unless user configured OllamaEmbedder. |

### Stage 6: Epistemic Enrichment

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | Concurrent batches |
| **LLM needed** | Yes — deep per-file analysis (architecture layer, coupling, tech debt, confidence) |
| **Model slot** | `large` (deep/thinking model) |
| **Thinking** | No (`think=False`) — but uses the deep model for quality |
| **Concurrency** | Uses `llm_concurrency_deep` budget, batched per `BatchProfile` |
| **Swarm benefit** | **Low.** Each file is analyzed independently. A coordinator could assign analysis angles based on file role (hub vs. leaf), but the quality gain is marginal vs. the token cost. |
| **Ideal model** | Mid-tier with good JSON output. Claude Sonnet, GPT-5.2–5.4, Kimi K2.5. Haiku/mini are too shallow for the nuanced analysis. Opus/frontier is overkill. |
| **Notes** | Multi-pass: code files get one prompt, doc files get another. Batch sizes are smaller than Catalogue (10–50 items). |

### Stage 7: Group Reasoning

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | **Swarm** (when model supports it) or concurrent |
| **LLM needed** | Yes — cross-file architectural analysis with deep reasoning |
| **Model slot** | `large` (deep/thinking model) |
| **Thinking** | **Yes** (`think=True`) — this is where deep reasoning adds genuine value |
| **Concurrency** | **Swarm: full slot budget** (bypasses fair-share). Standard: `llm_concurrency_deep`. |
| **Swarm benefit** | **HIGH.** This is the primary swarm target. Groups are clusters of related files — a coordinator can assign analysis angles (e.g., "focus on API contract stability" vs. "focus on data access coupling"), and synthesis discovers cross-group patterns that no individual analysis can find. |
| **Ideal model** | Best available reasoning model. Kimi K2.5 (native swarm), Claude Sonnet, GPT-5.2–5.4 with thinking. This stage justifies the token spend — it produces architectural insights that shape downstream Atlas and module structure. |
| **Notes** | Minimum 3 groups to activate swarm (below that, overhead isn't worth it). Swarm adds ~15% token overhead but produces cross-group synthesis. |

### Stage 8: Clustering (Module Synthesis)

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | Concurrent batches |
| **LLM needed** | Yes — synthesizes file clusters into named modules with descriptions |
| **Model slot** | `large` (deep/thinking model) |
| **Thinking** | No (`think=False`) |
| **Concurrency** | Uses `llm_concurrency_deep` budget, batched per `BatchProfile` |
| **Swarm benefit** | **Medium.** Clusters are somewhat independent, but a coordinator could assign naming conventions or ensure modules don't overlap. Future swarm candidate. |
| **Ideal model** | Strong at summarization and naming. Claude Sonnet, GPT-5.2–5.4. Needs to produce clean, consistent module names. |
| **Notes** | Consumes Group Reasoning output. Batch sizes are moderate (10–30 clusters). |

### Stage 9: Atlas Generation

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | Sequential (small number of calls) |
| **LLM needed** | Yes — generates project identity, stack summary, workspace map |
| **Model slot** | `large` (deep/thinking model) |
| **Thinking** | No (`think=False`) |
| **Concurrency** | Low — typically 1–3 LLM calls total |
| **Swarm benefit** | **Medium.** Workspace segments are independent and could be analyzed in parallel by scoped sub-agents, with a synthesis step for cross-segment coherence. Future swarm candidate once Group Reasoning swarm is proven. |
| **Ideal model** | Best available for synthesis. This stage produces the "executive summary" of the codebase — quality matters more than speed. Claude Sonnet, Gemini Pro (long context helps for large codebases). |
| **Notes** | Low volume but high impact — the Atlas is the first thing agents see. |

### Stage 10: Deepening

| Property | Value |
|----------|-------|
| **Queue** | LLM |
| **Execution** | Concurrent batches |
| **LLM needed** | Yes — refines epistemic scores using module context |
| **Model slot** | `large` (deep/thinking model) |
| **Thinking** | No (`think=False`) |
| **Concurrency** | Uses `llm_concurrency_deep` budget |
| **Swarm benefit** | **Low.** Each file is deepened independently with module context. Similar to Epistemic Enrichment — independent items, no cross-item reasoning needed. |
| **Ideal model** | Same as Epistemic Enrichment. Mid-tier with good JSON. |
| **Notes** | Re-runs epistemic analysis with richer context from Clustering/Atlas. |

### Stage 11: Deep Knowledge (Embeddings)

| Property | Value |
|----------|-------|
| **Queue** | EMBEDDING |
| **Execution** | Batch embedding, hardware-accelerated |
| **LLM needed** | No |
| **Model slot** | None |
| **Concurrency** | Runs in parallel with LLM stages |
| **Swarm benefit** | None |
| **Notes** | Re-embeds with enriched data from deep stages. Same as Stage 5. |

---

## Summary Matrix

| Stage | Queue | LLM | Model Tier | Thinking | Execution Mode | Swarm Benefit | Swarm Priority |
|-------|-------|-----|------------|----------|----------------|---------------|----------------|
| 1. Structural | Rust | No | — | — | Rust engine | None | — |
| 2. Inferred Edges | LLM | Yes | `code` (fast) | No | Concurrent batch | Low | — |
| 3. Catalogue | LLM | Yes | `small` (fast) | No | Concurrent batch | None | — |
| 4. Validation | Rust | No | — | — | Rust engine | None | — |
| 5. Knowledge | Embed | No | — | — | Batch embed | None | — |
| 6. Enrichment | LLM | Yes | `large` (deep) | No | Concurrent batch | Low | — |
| **7. Group Reasoning** | **LLM** | **Yes** | **`large` (deep)** | **Yes** | **Swarm / Concurrent** | **HIGH** | **Phase 79** |
| **8. Clustering** | **LLM** | **Yes** | **`large` (deep)** | **No** | **Swarm / Concurrent** | **Medium** | **Phase 79** |
| **9. Atlas** | **LLM** | **Yes** | **`large` (deep)** | **No** | **Swarm / Sequential** | **Medium** | **Phase 79** |
| 10. Deepening | LLM | Yes | `large` (deep) | No | Concurrent batch | Low | — |
| 11. Deep Knowledge | Embed | No | — | — | Batch embed | None | — |

---

## Model Tier Recommendations by Stage

### Frontier models (Claude Opus, GPT-5.4 Pro, etc.) — where they're justified

**Nowhere in the pipeline.** Frontier models are cost-prohibitive for pipeline work. Even Group Reasoning with swarm benefits more from a good mid-tier model (Sonnet, GPT-5.2–5.4, Kimi K2.5) run with `think=True` than from an expensive frontier model without thinking.

The one exception: **MCP tool calls** (not pipeline stages). When an AI agent calls `codrag_search` or `codrag_impact`, those are single interactive queries where response quality directly affects the developer's experience. But the pipeline is batch work — the quality floor is "good enough" and the cost ceiling matters.

### Mid-tier models (Claude Sonnet, GPT-5.2–5.4, Kimi K2.5) — the sweet spot

**Stages 6–10** (all deep enrichment stages). These stages need good reasoning, reliable JSON, and decent instruction following. Mid-tier models deliver 90% of frontier quality at 10–20% of the cost.

### Fast/cheap models (Claude Haiku, GPT-5.x-mini, Gemini Flash) — high volume

**Stages 2–3** (Inferred Edges, Catalogue). These are the highest-volume stages with hundreds or thousands of LLM calls. Speed and cost dominate — the analysis per item is straightforward.

### No model needed

**Stages 1, 4, 5, 11** (Structural, Validation, Knowledge, Deep Knowledge). Rust engine or embedding model only. These run independently of the LLM server and can execute in parallel with LLM stages.

---

## Scheduler Behavior Summary

| Scenario | Concurrency Source | Division |
|----------|-------------------|----------|
| Single project, any stage | `slot.max_concurrent` (full budget) | None — gets everything |
| Multiple projects, non-swarm stage | `_weighted_share()` | Fair split with boost weighting |
| Multiple projects, swarm stage | `full_budget_for_swarm()` | **None — gets full budget** |
| Exclusive priority project | `slot.max_concurrent` | None — exclusive always gets full |

The key Phase 79 change: swarm stages bypass `_weighted_share()` and get the full slot budget when it's their turn. They still wait in the LLM queue like any other stage — only the concurrency division is skipped, not the scheduling.

---

## Future Swarm Expansion

Once Group Reasoning swarm is validated, the next candidates are:

1. **Clustering (Stage 8)** — Coordinator assigns naming conventions, workers synthesize clusters, synthesis ensures consistency. Medium benefit.
2. **Atlas (Stage 9)** — Coordinator assigns workspace segments, workers analyze independently, synthesis produces coherent project identity. Medium benefit.
3. **Epistemic Enrichment (Stage 6)** — Coordinator assigns analysis depth based on file role (hub files get deeper analysis). Low benefit — the per-file prompt is already role-aware.

Each expansion reuses the same `SwarmOrchestrator` — just needs stage-specific coordinator/worker/synthesis prompts.

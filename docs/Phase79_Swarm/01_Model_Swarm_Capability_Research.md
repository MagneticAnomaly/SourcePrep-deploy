# Model Swarm Capability Research

> Phase 79 — Agent Swarm Integration  
> Research Date: 2026-04-07  
> Status: Active research — models and capabilities change frequently

## What "Swarm-Capable" Means

"Agent Swarm" is an orchestration pattern, not a model feature. No LLM API exposes a `supports_swarm` flag. The pattern requires a model to excel at three compound skills:

1. **Coordinator skills** — Decompose a complex task into well-scoped sub-tasks, assign analysis angles, and later synthesize N independent results into cross-cutting insights
2. **Worker skills** — Follow a scoped system prompt faithfully, produce reliable structured output (JSON), and stay focused on the assigned sub-task without drifting
3. **Structural reliability** — Consistently produce valid JSON matching a specified schema, even for complex nested output

These skills are not binary — they exist on a spectrum. A model can be an excellent worker but a poor coordinator (e.g., Haiku: follows narrow instructions well, but can't decompose complex tasks). The reverse is also possible but rarer.

### Why We Need a Curated Registry

Since swarm fitness cannot be auto-detected from API metadata, we maintain a **curated tight list** of validated models. This mirrors the existing `_MODEL_REGISTRY` pattern in `batch_profiles.py`, which maps `(provider, model_pattern)` to batch capability tiers via regex matching.

A model that technically has JSON mode and a large context window may still produce terrible coordinator output (verbose, unfocused decomposition) or unreliable worker output (schema drift, role leakage). The tight list prevents wasting tokens on models that will degrade pipeline quality.

## Capability Assessment Criteria

Each model is evaluated on five dimensions:

| Dimension | What We're Measuring | Must-Have For |
|-----------|---------------------|---------------|
| **JSON reliability** | Produces valid JSON matching schema on first attempt, no post-processing | Both |
| **Role adherence** | Stays within scoped system prompt; doesn't add unrequested analysis | Worker |
| **Decomposition** | Breaks complex task into well-bounded sub-tasks with clear scope | Coordinator |
| **Synthesis** | Merges N independent results, finds cross-cutting patterns, resolves conflicts | Coordinator |
| **Context efficiency** | Maintains quality across long prompts (coordinator sees all group summaries) | Coordinator |

## Model Assessment — Tight List

### Tier Definitions

| Tier | Role | Meaning |
|------|------|---------|
| **COORDINATOR** | Can plan, decompose, and synthesize | Best used as the swarm coordinator; may also work as a worker but is overqualified/expensive |
| **BOTH** | Can coordinate or work | Good all-rounder; cost-effective as coordinator for smaller swarms |
| **WORKER** | Can execute scoped sub-tasks reliably | Good for parallel execution of focused analysis; not reliable enough for planning/synthesis |
| **UNSUITABLE** | Not recommended for swarm | Missing critical capabilities (poor JSON, weak instruction following, insufficient context) |

### Cloud-Native Models

*Note: For Agent Swarm, you are running many concurrent workers. Heavy flagship models (like Opus 4.6 or Sonnet 4.6) are generally **cost overkill** and NOT recommended for regular use. Focus on pragmatic, fast models.*

| Model | Provider | JSON | Role Focus | Decomposition | Synthesis | Context | Swarm Tier | Notes |
|-------|----------|------|------------|---------------|-----------|---------|------------|-------|
| GPT-5.2 to 5.4 | openai | Excellent | Very Good | Very Good | Very Good | 1M | **BOTH** | Structured outputs reliable. (GPT-5.4 Pro/flagships are cost overkill). |
| GPT-5.x-mini | openai | Very Good | Good | Good | Good | 1M | **WORKER** | Highly cost-effective worker at scale |
| Claude Sonnet 4.0-4.6 | anthropic | Excellent | Very Good | Very Good | Very Good | 200K | **BOTH** | Good ratio, but newer 4.6 can be cost overkill for basic coordination |
| Claude Haiku 4.0-4.6 | anthropic | Good | Good | Adequate | Adequate | 200K | **WORKER** | Fast worker, sometimes schema drift on complex nested output |
| Claude Opus 4.x | anthropic | Excellent | Excellent | Excellent | Excellent | 200K | **UNSUITABLE** | **NOT RECOMMENDED** - Massive overkill. Cost-prohibitive for swarms. |
| Gemini 3 / 3.1 Pro | google | Very Good | Very Good | Excellent | Very Good | 1M (effective) | **COORDINATOR** | Strong long-context coordination, but monitor API costs |
| Gemini 3 / 3.1 Flash | google | Good | Good | Good | Good | 1M | **WORKER** | Fast and cheap; good for high-volume fan-out |
| DeepSeek-R1 | deepseek | Adequate | Moderate | Good reasoning | Good patterns | 128K | **WORKER** | Chain-of-thought interferes with JSON; post-processing needed |
| DeepSeek-V3 | deepseek | Good | Good | Good | Good | 128K | **WORKER** | Solid worker; very cheap API cost |
| Grok 4.x | xai | Good | Very Good | Good | Good | 128K | **BOTH** | Strong real-time context |

### Ollama Cloud Models

These are accessed through Ollama's cloud routing (`:cloud` suffix or known cloud patterns). Prep already detects these via `is_cloud_model_via_ollama()` in `batch_profiles.py`.

| Model | Ollama Tag | JSON | Role Focus | Decomposition | Synthesis | Context | Swarm Tier | Notes |
|-------|-----------|------|------------|---------------|-----------|---------|------------|-------|
| Kimi K2.5 | `kimi-k2.5:cloud` | Good | Good | Good (native swarm design) | Needs evaluation | 256K | **BOTH** | The model that inspired this feature; designed for swarm from the ground up |
| Gemini 3.1 Pro | `gemini-3.1-pro:cloud` | Very Good | Very Good | Excellent | Very Good | 1M | **COORDINATOR** | Same as direct Gemini 3.1 Pro but via Ollama |
| Gemini 3.1 Flash | `gemini-3.1-flash:cloud` | Good | Good | Good | Good | 1M | **WORKER** | Same as direct Flash but via Ollama |

### Ollama Local Models

| Model | Ollama Tag | JSON | Role Focus | Decomposition | Synthesis | Context | Swarm Tier | Notes |
|-------|-----------|------|------------|---------------|-----------|---------|------------|-------|
| Qwen3 235B (MoE) | `qwen3:235b` | Very Good | Good | Good | Good | 128K | **BOTH** | Requires significant VRAM; best local coordinator candidate |
| Qwen3 32B | `qwen3:32b` | Good | Good | Adequate | Adequate | 128K | **WORKER** | Best practical local worker (runs on 24GB GPU) |
| Qwen3 14B | `qwen3:14b` | Adequate | Good | Limited | Limited | 128K | **WORKER** | Acceptable for narrow sub-tasks only |
| Qwen3 8B | `qwen3:8b` | Adequate | Adequate | Limited | Limited | 128K | **UNSUITABLE** | Too much drift for reliable swarm participation |
| Llama 4 Maverick | `llama4:maverick` | Good | Good | Good | Adequate | 1M | **WORKER** | Improved structured output over Llama 3 |
| Llama 3.3 70B | `llama3.3:70b` | Good | Good | Adequate | Adequate | 128K | **WORKER** | Reliable workhorse; no native tool calling |
| Mistral Large | `mistral-large` | Very Good | Very Good | Good | Good | 128K | **BOTH** | Strong instruction following; cloud-only via Mistral API |
| Command-R+ | `command-r-plus` | Very Good | Good | Adequate | Good | 128K | **WORKER** | RAG-optimized synthesis; useful for specific sub-tasks |
| Phi-4 | `phi4` | Adequate | Adequate | Limited | Limited | 16K | **UNSUITABLE** | Context too small; schema drift too high |

## Recommended Models (Top 6)

The following six models are the **officially recommended** set that we will test thoroughly and surface as defaults in the UI. They balance capability with cost and are explicitly supported for swarm orchestration.

| Model | Provider | Tier | Reason |
|-------|----------|------|--------|
| Kimi K2.5 (cloud) | ollama | **BOTH** (Coordinator & Worker) | Flat‑rate pricing, built‑in swarm design. |
| GPT‑5.x‑mini | openai | **WORKER** | Cheapest high‑quality worker with reliable JSON output. |
| Claude Haiku 4.0‑4.6 | anthropic | **WORKER** | Fast, low‑cost worker; good role adherence. |
| GPT‑5.2‑5.4 | openai | **BOTH** | Strong coordinator with stable structured output. |
| Claude Sonnet 4.0‑4.6 | anthropic | **BOTH** | Excellent coordination/synthesis, reasonable pricing. |
| Gemini 2.5/3.0 Pro (or 3.1 Pro via Ollama) | google | **COORDINATOR** | Massive context window (1‑2M) for large codebases. |

---

## Supported Models (Range)

These models are **supported** by the swarm registry and can be matched via regex patterns. They are not part of the default recommendation but remain usable for advanced users.

| Model Pattern | Provider | Tier |
|---------------|----------|------|
| `kimi.*k2` | ollama | **BOTH** |
| `gpt-5\.[2-4]` | openai | **BOTH** |
| `gpt-5\.x-mini` | openai | **WORKER** |
| `claude.*haiku.*4` | anthropic | **WORKER** |
| `claude.*sonnet.*4` | anthropic | **BOTH** |
| `gemini.*(?:2\.5|3).*pro` | google | **COORDINATOR** |
| `gemini.*(?:2\.5|3).*flash` | google | **WORKER** |
| `deepseek.*r1` | deepseek | **WORKER** |
| `deepseek.*v3` | deepseek | **WORKER** |
| `grok.*4` | xai | **BOTH** |
| `qwen3:.*` | unknown | **BOTH/WORKER** |
| `llama.*` | unknown | **WORKER** |
| `mistral-large` | unknown | **BOTH** |
| `command-r-plus` | unknown | **WORKER** |

> **Note:** `Claude Opus` models are technically **UNSUITABLE** for regular swarm use due to high cost. They remain in the registry for completeness but are not advertised.

---

## Recommended Swarm Configurations

We keep the configuration examples for reference, now aligned with the top‑6 list:

### Configuration 1: Ollama Cloud w/ Kimi K2.5 (👑 Top Recommendation)

- **Coordinator:** Kimi K2.5
- **Workers:** Kimi K2.5
- **Why:** Flat‑rate cost, native swarm design.

### Configuration 2: Cloud‑Agnostic Budget Swarm

- **Coordinator:** Claude Sonnet 4.0‑4.6, GPT‑5.2‑5.4, or Gemini 2.5/3.0 Pro
- **Workers:** GPT‑5.x‑mini, Claude Haiku 4.0‑4.6, Gemini 2.5/3.0 Flash
- **Why:** Cost‑effective mix of coordinator and workers.

### Configuration 3: Local + Cloud Hybrid

- **Coordinator:** Cloud model (Kimi K2.5 or Gemini 3.1 Pro)
- **Workers:** Local Qwen3 32B or Llama 3.3 70B
- **Why:** Leverage local GPU for cheap workers.

### Configuration 4: Fully Local (Limited)

- **Coordinator:** Qwen3 235B (if VRAM permits)
- **Workers:** Qwen3 32B
- **Why:** Air‑gapped environments; limited utility.

## Prep Integration Points

### Where Swarm Tier Lives

The swarm tier registry follows the same `(provider, model_pattern) → tier` pattern as `batch_profiles.py`'s `_MODEL_REGISTRY`. It will be maintained as:

1. **`swarm_models.json`** — External JSON file for easy updates without code changes
2. **Fallback registry in code** — Hardcoded `_SWARM_REGISTRY` for when JSON file is missing

### How It Connects to Existing Systems

| Existing System | Swarm Integration |
|-----------------|-------------------|
| `batch_profiles.py` `_MODEL_REGISTRY` | Swarm registry follows same pattern; a model's batch profile and swarm tier are independent |
| `model_awareness.py` `ModelSlot` | Add `swarm_tier` to ModelSlot capabilities dict on acquisition |
| `llm_client.py` concurrency tiers | Swarm respects `llm_concurrency_deep` as max worker parallelism |
| `batch_profiles.py` `is_cloud_model_via_ollama()` | Reuse for detecting Ollama cloud models that may be swarm-capable |
| Pipeline settings (UI) | New "Agent Swarm" toggle; on by default when model is COORDINATOR or BOTH |

### Detection Flow

```
Model acquired for pipeline task
  → Check swarm_models.json for (provider, model) match
  → If match: set ModelSlot.capabilities["swarm_tier"] = COORDINATOR|BOTH|WORKER|UNSUITABLE
  → If no match: default to UNSUITABLE (safe fallback)
  → Pipeline stage checks swarm_tier before deciding orchestration strategy
  → If tier is COORDINATOR or BOTH and group count >= 3 and user hasn't disabled swarm:
      → Use swarm orchestration (coordinator → fan-out → synthesis)
  → Otherwise:
      → Use standard concurrent batching (existing behavior)
```

## Open Questions

1. **Same model for coordinator + workers, or different?** Single-model swarm is simpler (Kimi K2.5 as both coordinator and worker) but mixed-model could be more cost-effective (expensive coordinator, cheap workers). Start with same-model.

2. **Coordinator token budget.** The coordinator sees summaries of all groups to plan decomposition, then sees all worker results for synthesis. For a codebase with 20 groups, this could be 10-20K tokens per coordinator call. Need to validate this fits within Ollama Cloud's 16K output limit.

3. **Failure handling.** If a worker sub-agent fails, should the coordinator re-scope and re-dispatch, or just proceed with partial results? Start with partial results (simpler, and Group Reasoning already handles partial results).

4. **Evaluation.** How do we measure whether swarm produces better Group Reasoning output than standard concurrent? Need a quality rubric before we can validate the tight list. Candidate metrics: cross-group pattern discovery rate, coupling risk specificity, architectural insight novelty.

## Maintenance Plan

This registry will need updates as:
- New models are released (quarterly review)
- Ollama adds new cloud models
- We empirically validate models via pipeline quality metrics

The `swarm_models.json` file is the primary update surface. Code changes should rarely be needed for model additions.

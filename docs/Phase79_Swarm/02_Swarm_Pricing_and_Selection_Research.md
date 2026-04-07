# Swarm Model Pricing & Selection Research

> Phase 79 — Agent Swarm Integration  
> Research Date: 2026-04-07  
> Status: Model Architecture Selection

## Executive Summary

As we migrate to a swarm architecture where highly orchestrated worker sub-agents process huge token volumes in parallel, token economy becomes an architectural necessity rather than a minor line item. A 20-worker swarm completing a single synchronization pipeline can easily burn 100,000+ output tokens. Under this volume, utilizing "flagship" frontier models makes the system economically unviable for standard users. We must curate an officially supported registry of highly capable, but pragmatically priced, models.

This document details the pricing dynamics of leading API providers (OpenAI, Anthropic, Google, xAI, Ollama) in April 2026 and sets the officially supported tier matrix.

---

## 1. The Cost Threat: Flagship Overkill

Models like **Claude Opus 4.6** and **GPT-5.4 Pro** possess incredible intelligence and zero-shot reasoning. However, their pricing reflects this capability ceiling.

*   **Claude Opus 4.x/4.6:** ~$5.00 In / $25.00 Out per 1M tokens.
*   **GPT-5.4 Pro:** ~$5.00 In / $20.00 Out per 1M tokens.

**The Math:** If a swarm requires 100K output tokens to synthesize project contexts, Opus costs roughly $2.50 *per sync invocation*. Over a month of active development, this translates to hundreds of dollars purely in API overhead for a single user project.

**Action:** We are designating Opus and massive OpenAI flagships as technically capable `COORDINATOR` components, but we will purposefully **hide them from primary UI recommendations and documentation.** They are overkill. Users who want to force them can do so via manual regex matches.

---

## 2. API Pricing Matrices (April 2026)

To identify our "good enough" worker network and our "synthesis capable" coordinators, we evaluated current generation pricing thresholds.

### The Anthropic Family (Claude 4.0 - 4.6)
Anthropic has moved to a standard tri-tier structure. While older models (4.0/4.5) remain supported via API, 4.6 is the current active target. 

| Model | Input (/1M) | Output (/1M) | Swarm Viability |
|-------|-------------|--------------|-----------------|
| Claude 4.5/4.6 Haiku | $1.00 | $5.00 | **Top Worker.** Exceptionally fast; good for isolated classification tasks. |
| Claude 4.5/4.6 Sonnet| $3.00 | $15.00| **Strong Coordinator.** Excellent JSON generation, but $15 output requires careful token budgeting. |
| Claude Opus 4.x/4.6 | $5.00 | $25.00 | **Unsuited.** Dangerously expensive for parallel processing. |

### The OpenAI Family (GPT-5.2 - 5.4)
The current standard pricing for the active GPT-5.4 family showcases highly competitive worker pricing.

| Model | Input (/1M) | Output (/1M) | Swarm Viability |
|-------|-------------|--------------|-----------------|
| GPT-5.x-nano | $0.20 | $1.25 | Too much schema drift; unviable. |
| GPT-5.x-mini | $0.75 | $4.50 | **Ultimate Worker.** Incredible value-to-performance ratio; highly structured outputs. |
| GPT-5.2/5.4 | $2.50 | $15.00| **Strong Coordinator.** Extremely stable. |

### The Google Family (Gemini 2.5 / 3.0 / 3.1)
The "3.1 Pro" model is currently locked inside an exclusive Enterprise/Vertex AI preview for G-Suite administrators. For standard API developers and our broader user base, Gemini 2.5 and 3.0 denote the current mainline limit.

| Model | Input (/1M) | Output (/1M) | Swarm Viability |
|-------|-------------|--------------|-----------------|
| Gemini 2.5/3.0 Flash| ~$0.50 | ~$1.50 | **Cheap Worker.** High fan-out volume but sometimes struggles with complex nested JSON. |
| Gemini 2.5/3.0 Pro | ~$1.50 | ~$5.00 | **Massive Context Coordinator.** 1M-2M context window makes this highly valuable for ingesting large chunks of code. |

### The xAI Family (Grok 4.x)
Grok 4.20 models have advanced rapidly with native reasoning endpoints.

| Model | Input (/1M) | Output (/1M) | Swarm Viability |
|-------|-------------|--------------|-----------------|
| Grok 4.20 | ~$3.00 | ~$15.00| **The Speed Coordinator.** Phenomenally fast output speeds, making it highly attractive if users are impatient with wait times. |

### The Ollama Paradigm (Kimi 2.5)
Ollama bypasses the "per token" model completely when utilizing local hardware or a flat-rate Ollama Cloud subscription (e.g., ~$100/mo). Because the **Kimi 2.5** model architecture was specifically engineered to support multi-agent reasoning out-of-the-box, applying it via a flat fee effectively neutralizes the entire swarm cost debate.

---

## 3. The Supported Registry: "The Top 6"

Based on the research above, we are establishing an officially curated "Top 6" matrix. These models will receive first-class integrations, UI default settings, and designated profile routing.

1.  **Kimi K2.5 (via Ollama)** 
    - The reigning champion. Flat pricing, structural architectural support for swarm clustering. Both `COORDINATOR` and `WORKER`.
2.  **GPT-5.x-mini (OpenAI)**
    - The most cost-efficient worker ($4.50/M out). Guaranteed structured output APIs.
3.  **Claude Haiku 4.0-4.6 (Anthropic)**
    - The fastest Anthropic routing mechanism; excellent execution parameters.
4.  **GPT-5.2 to 5.4 (OpenAI)**
    - The primary coordinator for users operating within the standard OpenAI ecosystem.
5.  **Claude Sonnet 4.0-4.6 (Anthropic)**
    - The primary coordinator for Anthropic users. Perfect balance of zero-shot synthesis capabilities without Opus-level pricing.
6.  **Gemini 2.5/3.0 Pro / Flash (Google)**
    - Crucial for users with hyper-extended codebases where a 1M+ token context window is the primary requirement for phase orchestration.

### Runner Up / Honorable Mention
*   **Grok 4.20:** A deeply impressive and lightning-fast model, though we are retaining the core 6 footprint above to manage tool integration spread. Grok 4.x can be added if users explicitly request extreme generation speed.

This Top 6 list dictates the structure of our JSON manifests going forward. Opus and GPT-5.4-Pro are downgraded from explicit recommendation to background "capable if forced" legacy tiers.

# Model Recommendations Research

**Status:** COMPLETE  
**Updated:** 2026-02-21  
**Scope:** Ollama (local) + BYOK (cloud) model recommendations for all CoDRAG pipeline slots

---

## CoDRAG Pipeline Slot Summary

Each slot has different requirements — understanding what each slot *does* determines what model properties matter.

| Slot | Pipeline Stages | Task Type | Key Requirement |
|------|----------------|-----------|-----------------|
| **Embedding** | Knowledge Embedding, Deep Knowledge | Vector encoding | Semantic similarity quality |
| **Small (Fast)** | Catalogue (augmentation) | JSON structured output per file/symbol | Fast, reliable JSON, cheap |
| **Code** | Inferred Edges (Stage 1.5) | Cross-file edge discovery from source | Code comprehension, JSON output |
| **Large (Thinking)** | Epistemic Enrichment, Clustering, Atlas, Deepening | Multi-hop reasoning with neighbor context | Reasoning depth, large context |

### What matters per slot

- **Small/Fast**: Speed + JSON reliability + cost. Processes hundreds of files sequentially (local) or batched (cloud). The model sees one file at a time and must output structured JSON with role/summary/confidence.
- **Code**: Code comprehension — detecting cross-language calls, dynamic dispatch, interface implementations. Falls back to Small if not configured.
- **Large/Thinking**: Reasoning quality. Sees a file + its enriched neighbors and must produce extended summaries, domain tags, architectural assessments. Processes fewer items but each requires deeper understanding.
- **Embedding**: Already solved — nomic-embed-text-v1.5 via ONNX is the production model (see Phase 33 research).

---

## Part 1: Ollama (Local) Model Recommendations

### Current landscape (Feb 2026)

The Qwen3 family has dramatically changed the local model landscape. Key developments:

1. **Qwen3 MoE models** — The 30B-A3B (30B total, 3B active) outperforms QwQ-32B while being 10× more efficient. The 4B dense model rivals Qwen2.5-72B performance.
2. **Qwen3-Coder** — Dedicated code model: 30B-A3B (19GB) and 480B, with 256K context. Purpose-built for agentic coding tasks.
3. **Gemma 3** — Google's 1B/4B/12B/27B models with 128K context and multimodal support.

### Recommended Ollama models by slot

#### Small/Fast Slot — `qwen3:4b` (PRIMARY)

| Model | Size | VRAM | Context | Why |
|-------|------|------|---------|-----|
| **qwen3:4b** ⭐ | 2.5GB | ~3GB | 256K | Best-in-class at this size. Rivals Qwen2.5-72B on benchmarks. Excellent structured JSON output. MoE-ready architecture. 256K context. |
| qwen3:1.7b | 1.4GB | ~2GB | 40K | Ultra-light option for very constrained VRAM. Decent JSON but less reliable. |
| gemma3:4b | 3.3GB | ~4GB | 128K | Good alternative. Multimodal. Slightly worse at structured output than Qwen3. |
| qwen3:0.6b | 523MB | ~1GB | 40K | Smallest viable option. Only for extremely VRAM-constrained setups. |

**Why not the old recommendations?**
- `ministral-3:3b` — Mistral's 3B model is outclassed by Qwen3:4b on every benchmark while being similar size
- `qwen2.5:3b` — Superseded by Qwen3:4b which is dramatically better at the same size class
- `phi3:mini` — Microsoft's Phi-3 is decent but Qwen3 wins on structured output tasks

#### Large/Thinking Slot — `qwen3:8b` (PRIMARY)

| Model | Size | VRAM | Context | Why |
|-------|------|------|---------|-----|
| **qwen3:8b** ⭐ | 5.2GB | ~6GB | 40K | Default Qwen3. Strong reasoning, great at multi-hop analysis with neighbor context. |
| qwen3:14b | 9.3GB | ~10GB | 40K | Significantly better reasoning if VRAM allows. Best local option for epistemic enrichment quality. |
| qwen3:30b | 19GB | ~20GB | 256K | MoE (30B total, 3B active). Outstanding reasoning with only 3B active parameters. Needs ~20GB VRAM for weights but inference is efficient. 256K context. |
| gemma3:12b | 8.1GB | ~9GB | 128K | Good alternative. 128K context is useful for large neighbor windows. |
| gemma3:27b | 17GB | ~18GB | 128K | Premium local option if VRAM is available. |

**Why not the old recommendations?**
- `ministral-3:8b` — Outclassed by Qwen3:8b
- `mistral-nemo` — 12B model, Qwen3:14b is better at same size class
- `deepseek-coder-v2` — 16B, better used in code slot. Qwen3:14b is better for general reasoning

#### Code Slot — `qwen3-coder:30b` (PRIMARY)

| Model | Size | VRAM | Context | Why |
|-------|------|------|---------|-----|
| **qwen3-coder:30b** ⭐ | 19GB | ~20GB | 256K | MoE (30B total, 3.3B active). Purpose-built for code analysis. 256K context for large file analysis. Best code model on Ollama. |
| qwen3:4b | 2.5GB | ~3GB | 256K | Falls back to Fast model. Decent code understanding, just not specialized. |
| qwen2.5-coder:7b | 4.7GB | ~5GB | 32K | Still viable if VRAM is limited. Specialized for code. |

**Why not the old recommendations?**
- `qwen2.5-coder:3b` — Too small for reliable edge detection. Qwen3:4b (general) is better as fallback.
- `deepseek-coder-v2` — 16B is large and not MoE. Qwen3-Coder:30b is better with only 3.3B active.
- `codellama:7b` — Outdated. Qwen2.5-coder and Qwen3-coder are significantly better.

#### Embedding — `nomic-embed-text-v1.5` (ONNX) — UNCHANGED

Built-in ONNX model. No Ollama needed. 768-dim, works offline. This is settled (Phase 33).

### VRAM Budget Guide (Local)

| Setup | VRAM | Recommended Config |
|-------|------|--------------------|
| **Minimal** (8GB GPU / Apple M1 8GB) | ~6GB usable | Small: qwen3:1.7b, Large: qwen3:4b, Code: (use Fast) |
| **Standard** (16GB GPU / Apple M1 Pro 16GB) | ~12GB usable | Small: qwen3:4b, Large: qwen3:8b, Code: (use Fast) |
| **Power** (24GB GPU / Apple M2 Pro 32GB) | ~20GB usable | Small: qwen3:4b, Large: qwen3:14b, Code: qwen2.5-coder:7b |
| **Enthusiast** (48GB+ / Apple M3 Max 64GB) | ~40GB+ usable | Small: qwen3:4b, Large: qwen3:30b, Code: qwen3-coder:30b |

> **Note:** Ollama swaps models in/out of VRAM. Only one model runs at a time in CoDRAG's pipeline (VRAM lifecycle managed by pipeline orchestrator). The budget above is per-model, not cumulative.

---

## Part 2: BYOK (Cloud) Model Recommendations

### Pricing landscape (Feb 2026)

#### Anthropic Claude

| Model | Input/1M | Output/1M | Max Output | Context | Batch (50% off) | Best For |
|-------|----------|-----------|------------|---------|-----------------|----------|
| Haiku 3 | $0.25 | $1.25 | 4K | 200K | $0.13/$0.63 | Legacy, very cheap |
| **Haiku 3.5** | $0.80 | $4.00 | 8K | 200K | $0.40/$2.00 | Budget structured output |
| Sonnet 4 | $3.00 | $15.00 | 64K | 200K | $1.50/$7.50 | Balanced quality/cost |
| **Sonnet 4.5** | $3.00 | $15.00 | 64K | 200K | $1.50/$7.50 | Best coding, same price as Sonnet 4 |
| Sonnet 4.6 | $3.00 | $15.00 | 64K | 200K | $1.50/$7.50 | Latest, matches Opus performance |
| Opus 4.5 | $5.00 | $25.00 | 64K | 1M | $2.50/$12.50 | Maximum quality |
| Opus 4.6 | $15.00 | $75.00 | 64K | 1M | $7.50/$37.50 | Overkill for CoDRAG |

**Recommendation:** Use **Sonnet 4.5** (or 4.6) — same price as Sonnet 4 but much better coding ability. Haiku 3.5 is viable for budget users but output limit (8K) constrains batching.

#### OpenAI GPT

| Model | Input/1M | Output/1M | Max Output | Context | Best For |
|-------|----------|-----------|------------|---------|----------|
| **GPT-4.1-nano** | $0.10 | $0.40 | 32K | 128K | Ultra-cheap, good structured output |
| **GPT-4.1-mini** | $0.40 | $1.60 | 32K | 1M | Best value for quality/cost |
| GPT-4.1 | $2.00 | $8.00 | 32K | 1M | High quality, expensive |
| GPT-4o-mini | $0.15 | $0.60 | 16K | 128K | Legacy, still cheap |
| GPT-5 Nano | $0.05 | $0.40 | ? | ? | Newest ultra-cheap (if available) |
| GPT-5 Mini | $0.25 | $2.00 | ? | 200K | Newer but more expensive than 4.1-mini |

**Recommendation:** Use **GPT-4.1-mini** — $0.40/$1.60 with 32K output and 1M context. Excellent structured JSON output (strict `json_schema` mode). For maximum budget savings, **GPT-4.1-nano** at $0.10/$0.40 is remarkably capable for its price.

#### Google Gemini

| Model | Input/1M | Output/1M | Max Output | Context | Best For |
|-------|----------|-----------|------------|---------|----------|
| **2.5 Flash** | $0.15 | $0.60 | 8K–32K | 1M | Ultra-cheap, hybrid reasoning |
| 2.5 Flash-Lite | $0.075 | $0.30 | 8K | 1M | Cheapest option, limited output |
| **2.5 Pro** | $1.25 | $10.00 | 64K | 1M | Best value pro-tier |
| 3 Flash (Preview) | $0.50 | $3.00 | ? | ? | Newer, better reasoning |
| 3 Pro (Preview) | $2.00 | $12.00 | ? | ? | Latest flagship |
| 3.1 Pro (Preview) | $2.00 | $12.00 | ? | ? | Newest, may not be stable |

**Recommendation:** **Gemini 2.5 Flash** at $0.15/$0.60 is the cheapest viable option with good JSON support. **Gemini 2.5 Pro** at $1.25/$10.00 for users wanting better quality. Note: Gemini models require `openai-compatible` provider type in CoDRAG.

### BYOK Cost-Optimized Recommendations by Slot

For CoDRAG, the key insight is: **the older, cheaper generation is almost always the right pick.** CoDRAG's tasks (JSON extraction, file summarization, edge detection) don't need frontier reasoning — they need reliable structured output.

#### Single-Model Setup (Simplest)

Use ONE model for both Fast and Thinking slots:

| Provider | Model | Cost | Batch Profile | Why |
|----------|-------|------|---------------|-----|
| **OpenAI** | gpt-4.1-mini | $0.40/$1.60 | Standard (32K) | Best all-around value |
| **Anthropic** | claude-sonnet-4-20250514 | $3/$15 | Large (64K) | Premium quality, great JSON |
| **Google** | gemini-2.5-flash | $0.15/$0.60 | Compact (8K) | Cheapest viable option |

#### Split-Model Setup (Cost-Optimized)

Use a cheaper model for Fast/Code, a better one for Thinking:

| Slot | OpenAI | Anthropic | Google |
|------|--------|-----------|--------|
| **Fast** | gpt-4.1-nano ($0.10/$0.40) | claude-haiku-3.5 ($0.80/$4) | gemini-2.5-flash-lite ($0.075/$0.30) |
| **Thinking** | gpt-4.1-mini ($0.40/$1.60) | claude-sonnet-4.5 ($3/$15) | gemini-2.5-pro ($1.25/$10) |
| **Code** | (use Fast) | (use Fast) | (use Fast) |

### Estimated Cost per 1,000 Files

Assuming ~500 tokens input and ~100 tokens output per file for catalogue, ~800/200 for epistemic:

| Config | Catalogue (Fast) | Epistemic (Thinking) | Total ~1K files |
|--------|-----------------|---------------------|-----------------|
| GPT-4.1-nano + mini | ~$0.09 | ~$0.72 | **~$0.81** |
| GPT-4.1-mini only | ~$0.36 | ~$0.72 | **~$1.08** |
| Gemini 2.5 Flash only | ~$0.09 | ~$0.27 | **~$0.36** |
| Claude Sonnet 4.5 only | ~$3.15 | ~$6.30 | **~$9.45** |
| Claude Haiku 3.5 + Sonnet | ~$0.84 | ~$6.30 | **~$7.14** |

> **Key insight:** Gemini 2.5 Flash is by far the cheapest. GPT-4.1-nano is the cheapest from OpenAI. Claude is 10× more expensive but produces excellent quality.

---

## Part 3: Updated Model Registry (batch_profiles.py)

The model registry needs updates for:
- GPT-5 family (output limits TBD, treat as Standard for now)
- Claude 4.5/4.6 (Large profile — 64K output)
- Gemini 3.x (preview, treat as Compact until stable)
- Haiku 3.5 (Compact — only 8K output)

---

## Part 4: Recommendation Tool — Design Decisions

### Context Window: Not a Selection Parameter

Context window is **irrelevant** for model selection in CoDRAG's pipeline:

- **Fast/Small slot**: Catalogue sends ~300–1,000 tokens per file. Even 4K context is
  10× more than needed. 40K vs 128K vs 256K makes zero difference.
- **Thinking/Large slot**: Epistemic sends one file + up to 8 neighbor summaries
  (~100–200 tok each). Worst-case prompt is ~3–4K tokens. Even the smallest
  40K model (qwen3:8b) has 10× headroom.
- **Code slot**: Inferred edges sends one file + known file list. Same story — ~2–4K.

**What actually matters per slot:**
- Fast: JSON reliability, speed, VRAM footprint
- Thinking: Reasoning quality, VRAM footprint
- Code: Code comprehension, VRAM footprint

### GPU Speed Tiers

Three qualitative tiers that affect **throughput expectations** (how long the
pipeline takes), not model selection. Shown in the advisor as context.

| Tier | Description | Examples | Tokens/sec (7B-class) |
|------|-------------|----------|----------------------|
| **High-end** | Latest gen, fast inference | RTX 4090, RTX 5090, M3 Max, M4 Max, A100 | ~50–80 tok/s |
| **Fast** | Mid-range, comfortable | RTX 3080, RTX 4070, M2 Pro, M3 Pro | ~25–45 tok/s |
| **Standard** | Entry-level or older | RTX 3060, GTX 1080 Ti, M1, M2 base | ~10–20 tok/s |

Speed tier affects the advisor messaging:
- High-end: "Pipeline will complete quickly"
- Fast: "Pipeline will take a few minutes per stage"
- Standard: "Pipeline will be slower — consider Hybrid mode for large repos"

### Single-Model Edge Case (Tiny VRAM)

When usable VRAM is **≤ 4GB** (e.g. M1 8GB base, GTX 1650), recommend
**one model for all slots**:

| VRAM | Single Model | Why |
|------|-------------|-----|
| ≤ 2GB | qwen3:0.6b (523MB) | Only option. Unreliable JSON — warn user. |
| 2–3GB | qwen3:1.7b (1.4GB) | Decent JSON. Usable for small repos. |
| 3–4GB | qwen3:4b (2.5GB) | Best single-model pick. Reliable JSON, good reasoning. |

The advisor should show: "Limited VRAM — using one model for all slots. For better
results, consider Hybrid mode (local Fast + cloud Thinking)."

### Model Advisor: Three Modes

#### Mode 1: Local (Free, Private)

User selects GPU → advisor calculates usable VRAM → recommends models.

**Output: 1–3 models** depending on VRAM:
- Tiny VRAM (≤4GB): 1 model for all slots
- Standard (5–12GB): Fast + Thinking (2 models, Code uses Fast)
- Power (12GB+): Fast + Thinking + Code (3 models)

Since Ollama swaps models, peak VRAM = largest single model (not cumulative).

#### Mode 2: Cloud (Fastest, Best Quality)

User selects provider preference → advisor recommends **1 or 2 models**.

**1-model setup** (simplest):
| Provider | Model | Cost | Batch Profile |
|----------|-------|------|---------------|
| OpenAI | gpt-4.1-mini | $0.40/$1.60 | Standard |
| Google | gemini-2.5-flash | $0.15/$0.60 | Compact |
| Anthropic | claude-sonnet-4.5 | $3/$15 | Large |

**2-model setup** (cost-optimized — only show if savings are meaningful):
| Slot | OpenAI | Google | Anthropic |
|------|--------|--------|-----------|
| Fast | gpt-4.1-nano ($0.10/$0.40) | gemini-2.5-flash-lite ($0.08/$0.30) | claude-haiku-3.5 ($0.80/$4) |
| Thinking | gpt-4.1-mini ($0.40/$1.60) | gemini-2.5-flash ($0.15/$0.60) | claude-sonnet-4.5 ($3/$15) |

Code slot always uses Fast for cloud — edge detection doesn't need a separate
cloud model. No 3-model cloud setup.

#### Mode 3: Hybrid (Best of Both)

Local model for Fast slot (free, high-volume) + cloud model for Thinking (quality).
Code falls back to local Fast.

**Output: 1 local model + 1 cloud model** (always 2 total).

| Component | Model | Why |
|-----------|-------|-----|
| **Local Fast** | qwen3:4b (2.5GB) | Handles catalogue — hundreds of calls, free |
| **Cloud Thinking** | (user picks provider) | Handles epistemic — fewer calls, needs quality |

The advisor asks two questions:
1. GPU selection → determines local Fast model
2. Cloud provider preference → determines Thinking model

No separate Code recommendation in hybrid — it falls back to the local Fast
model, which is good enough for edge detection.

**Why this works:** Catalogue (Fast slot) is the high-volume stage — hundreds
of sequential calls. Running this locally saves the most money. Epistemic
(Thinking slot) is fewer calls but needs reasoning quality — cloud shines here.

### UI Flow

```
┌─────────────────────────────────────────────────────┐
│ Model Setup Advisor                                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  How do you want to run CoDRAG?                     │
│                                                      │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐            │
│  │  Local   │  │  Hybrid  │  │  Cloud  │            │
│  │  Free &  │  │ Best of  │  │ Fastest │            │
│  │  Private │  │  both    │  │ Quality │            │
│  └─────────┘  └──────────┘  └─────────┘            │
│                                                      │
│  ── Local / Hybrid shows: ──────────────────────    │
│                                                      │
│  GPU:  [ Apple Silicon ▾ ] [ M2 Pro 16GB ▾ ]       │
│  Speed: Fast (~30 tok/s)                             │
│  VRAM:  ████████████░░░░░░ 12GB usable              │
│                                                      │
│  ── Cloud / Hybrid shows: ──────────────────────    │
│                                                      │
│  Provider: [ OpenAI ▾ ]                             │
│  Setup:    ○ 1 model (simple)  ● 2 models (save $) │
│                                                      │
│  ── Recommendation ─────────────────────────────    │
│                                                      │
│  Fast:     qwen3:4b        (local, 2.5GB)     ✓    │
│  Thinking: gpt-4.1-mini    (cloud, ~$1/1K files) ✓ │
│  Code:     (uses Fast)                         ✓    │
│  ───────────────────────────────────                │
│  Est. cost: ~$0.72 per 1K files (Thinking only)    │
│  Pipeline speed: ~5 min per 1K files               │
│                                                      │
│  [ Apply Recommendations ]                           │
└─────────────────────────────────────────────────────┘
```

### Implementation Plan

1. **New component**: `ModelAdvisor.tsx`
2. **GPU database**: JSON — each entry has `{ vram_gb, usable_gb, speed_tier }`
3. **Model database**: JSON — each entry has `{ ollama_name, vram_gb, quality_tier, slot_fit }`
4. **Recommendation engine**: Pure function `(mode, vram?, provider?) → ModelPlan`
5. **"Apply" action**: Populates the slot configs + endpoint assignments

### Files to create/modify

- `packages/ui/src/components/llm/ModelAdvisor.tsx` — New interactive component
- `packages/ui/src/data/gpu-database.ts` — GPU VRAM + speed tier lookup
- `packages/ui/src/data/model-database.ts` — Model specs lookup
- `packages/ui/src/components/llm/AIModelsSettings.tsx` — Replace info box with ModelAdvisor

### Priority

1. ✅ Update static recommendations (done)
2. ✅ Design decisions finalized (this session)
3. 🔜 Build ModelAdvisor component
4. 🔜 VRAM calculator + "Apply" functionality

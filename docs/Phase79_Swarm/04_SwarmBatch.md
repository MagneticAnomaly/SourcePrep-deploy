# Swarm Size & Batch Tuning Research

> Phase 79 — Agent Swarm Integration
> Research Date: 2026-04-07
> Status: Active research — data sourced from official provider documentation

**Context**: A repository with ~1,000 source files. We want to compare **batch processing** vs **swarm orchestration** across the recommended model registry, using real pricing and throughput data from each provider's published API documentation (April 2026).

---

## 1. Baseline Assumptions

Our reference workload is a medium-large codebase that CoDRAG's pipeline needs to analyze end-to-end. Not every file is sent raw — the pipeline stages work with epistemic summaries, edges, and group contexts — but understanding the raw scale helps frame the cost math.

| Metric | Value | Source |
|--------|-------|--------|
| Files in repo | ~1,000 | Typical mid-size project (React app, Python backend, etc.) |
| Avg lines per file | ~200–400 | Varies; config files are small, service files large |
| Avg characters per file | ~10,000–20,000 | ~15,000 midpoint |
| Tokens per file (÷4 chars/token) | ~2,500–5,000 | ~3,750 midpoint |
| **Total raw repo tokens** | **~3.75 M** | Conservative — many files are smaller |
| Tokens per group context (pipeline) | ~2,000–5,000 | What we actually send per LLM call in Group Reasoning |
| Typical group count in pipeline | 15–30 | CoDRAG clustering output for a 1K-file repo |

> **Important correction from earlier drafts**: Previous versions of this document used 11,250 tokens/file, which assumed 0.75 chars/token. The industry standard is ~4 characters per token for English code. The corrected midpoint is ~3,750 tokens/file. This dramatically changes batch sizing.

---

## 2. Verified Model Specifications (April 2026)

All pricing below is sourced from official provider pricing pages and confirmed via web research on 2026-04-07.

### 2.1 Pricing per 1M Tokens

| Model | Provider | Input (/1M) | Cached Input (/1M) | Output (/1M) | Context Window |
|-------|----------|-------------|---------------------|--------------|----------------|
| **Kimi K2.5** (Ollama Cloud Max) | Ollama | **$100/mo flat** | — | **$100/mo flat** | 256K |
| **Kimi K2.5** (direct Moonshot API) | Moonshot | ~$0.60 | — | ~$2.50–$3.00 | 256K |
| **GPT-5.4 mini** | OpenAI | $0.75 | $0.075 | $4.50 | 400K |
| **GPT-5.4** (standard) | OpenAI | $2.50 | $0.25 | $15.00 | 400K |
| **GPT-5.4 nano** | OpenAI | $0.20 | $0.02 | $1.25 | 400K |
| **Claude Haiku 4.5** | Anthropic | $1.00 | — | $5.00 | 200K |
| **Claude Sonnet 4.6** | Anthropic | $3.00 | — | $15.00 | 1M |
| **Claude Opus 4.6** | Anthropic | $5.00 | — | $25.00 | 1M |
| **Gemini 2.5 Pro** | Google | $1.25 (≤200K) / $2.50 (>200K) | 90% discount w/ cache | $10.00 (≤200K) / $15.00 (>200K) | 1M |
| **Gemini 2.5 Flash** | Google | $0.30 | — | $2.50 | 1M |
| **Gemini 2.5 Flash-Lite** | Google | $0.10 | — | $0.40 | 1M |
| **Grok 4.20** | xAI | $2.00 | $0.05 (cached) | $6.00 | 2M |
| **Grok 4.1 Fast** | xAI | $0.20 | — | $0.50 | 2M |

**Key notes:**
- All providers offer a **Batch API** (50% discount on async, non-real-time requests with ~24h turnaround). This is irrelevant for swarm since swarm requires real-time responses.
- Anthropic's Sonnet/Opus 4.6 now support **1M context windows** at standard pricing — a significant upgrade from the 200K of earlier generations.
- GPT-5.2 is being **retired June 5, 2026**. We should target GPT-5.4 and GPT-5.4 mini as the primary OpenAI models.
- **Grok 4.20** has an exceptional output price ($6/M) relative to its capability tier — significantly cheaper than Claude Sonnet ($15/M) or GPT-5.4 ($15/M).

### 2.2 Throughput (Output Tokens/Second)

Providers do not publish standardized tok/s benchmarks. The following ranges are compiled from third-party benchmarks and community reports:

| Model | Typical Output tok/s | TTFT (Time to First Token) | Rate Limits |
|-------|---------------------|----------------------------|-------------|
| **Kimi K2.5** (Ollama Cloud) | ~80–150 | ~1–2s | Governed by plan (Max: 10 concurrent models) |
| **GPT-5.4 mini** | ~100–200 | ~0.5–1s | Tier-based (default ~10M TPM) |
| **GPT-5.4** | ~60–120 | ~1–3s | Tier-based |
| **Claude Haiku 4.5** | ~150–250 | ~0.3–0.8s | 200 RPM standard tier |
| **Claude Sonnet 4.6** | ~50–120 | ~1–3s | 200 RPM standard tier |
| **Gemini 2.5 Pro** | ~60–150 | ~1–2s | Google AI Studio free tier has lower limits |
| **Gemini 2.5 Flash** | ~150–300 | ~0.3–0.8s | High throughput |
| **Grok 4.20** | ~100–200 | ~0.5–1.5s | 1,800 RPM / 10M TPM |

> **Caveat**: These are representative ranges. Actual throughput depends on prompt complexity, output length, current load, and whether extended-thinking/reasoning is enabled. For swarm purposes, we assume **non-reasoning, standard mode** to keep latency low.

### 2.3 Context Windows — Batch Sizing Impact

| Model | Context Window | Safe Batch Limit (80% fill) | Files per Batch (@ 3,750 tok/file) |
|-------|----------------|---------------------------|--------------------------------------|
| Kimi K2.5 | 256K | 200K | ~53 |
| GPT-5.4 mini | 400K | 320K | ~85 |
| GPT-5.4 | 400K | 320K | ~85 |
| Claude Haiku 4.5 | 200K | 160K | ~42 |
| Claude Sonnet 4.6 | 1M | 800K | ~213 |
| Gemini 2.5 Pro | 1M | 800K | ~213 |
| Gemini 2.5 Flash | 1M | 800K | ~213 |
| Grok 4.20 | 2M | 1.6M | ~426 |

> **Correction**: Earlier drafts listed Claude Haiku/Sonnet at 200K context. The latest Sonnet 4.6 and Opus 4.6 now support **1M context windows**. Haiku 4.5 remains at 200K. This changes the batch math significantly — Sonnet can now process 200+ files per batch.

---

## 3. Cost Modeling: Batch vs Swarm

### Scenario: 1,000-file repo, Group Reasoning stage

In practice, CoDRAG's Group Reasoning stage doesn't send raw files — it sends pre-computed epistemic summaries and edge data for each **group** (cluster of related files). A 1,000-file repo typically produces 15–30 groups.

| Parameter | Batch Mode | Swarm Mode |
|-----------|-----------|------------|
| LLM calls | 15–30 (one per group, concurrent) | 15–30 workers + 1 coordinator + 1 synthesis = 17–32 |
| Input tokens per call | ~3K (group context) | Workers: ~3K; Coordinator: ~2K; Synthesis: ~5K |
| Output tokens per call | ~500 (JSON entry) | Workers: ~500; Coordinator: ~1K; Synthesis: ~1K |
| **Total input tokens** | ~60K (20 groups × 3K) | ~69K (+9K for coord/synth) |
| **Total output tokens** | ~10K (20 groups × 500) | ~13K (+3K for coord/synth) |

### 3.1 Cost per Full Pipeline Run (Group Reasoning Only)

| Model | Batch Cost | Swarm Cost | Delta | Notes |
|-------|-----------|------------|-------|-------|
| **Kimi K2.5 (Ollama Max)** | $0.00 (flat) | $0.00 (flat) | $0 | Winner — no per-token concern |
| **Kimi K2.5 (Moonshot API)** | $0.04 in + $0.03 out = **$0.07** | $0.04 + $0.04 = **$0.08** | +$0.01 | Negligible |
| **GPT-5.4 mini** | $0.045 in + $0.045 out = **$0.09** | $0.05 + $0.06 = **$0.11** | +$0.02 | Very cheap |
| **GPT-5.4** | $0.15 in + $0.15 out = **$0.30** | $0.17 + $0.20 = **$0.37** | +$0.07 | Moderate |
| **Claude Haiku 4.5** | $0.06 in + $0.05 out = **$0.11** | $0.07 + $0.07 = **$0.14** | +$0.03 | Still cheap |
| **Claude Sonnet 4.6** | $0.18 in + $0.15 out = **$0.33** | $0.21 + $0.20 = **$0.41** | +$0.08 | Noticeable |
| **Gemini 2.5 Flash** | $0.02 in + $0.025 out = **$0.04** | $0.02 + $0.03 = **$0.05** | +$0.01 | Extremely cheap |
| **Grok 4.20** | $0.12 in + $0.06 out = **$0.18** | $0.14 + $0.08 = **$0.22** | +$0.04 | Good value |

> **Takeaway**: For a single Group Reasoning run, the cost delta between batch and swarm is **negligible** ($0.01–$0.08). The swarm adds ~2 extra LLM calls (coordinator + synthesis) which cost very little. The quality improvement (scoped analysis + cross-group synthesis) easily justifies this overhead.

### 3.2 Monthly Cost Projection (Active Development)

Assume 5 pipeline runs/day × 22 work days = 110 runs/month:

| Model | Batch Monthly | Swarm Monthly | Flat-Rate Alternative |
|-------|-------------|---------------|----------------------|
| **GPT-5.4 mini** | $9.90 | $12.10 | — |
| **Claude Haiku 4.5** | $12.10 | $15.40 | — |
| **Gemini 2.5 Flash** | $4.40 | $5.50 | — |
| **Grok 4.20** | $19.80 | $24.20 | — |
| **Claude Sonnet 4.6** | $36.30 | $45.10 | — |
| **GPT-5.4** | $33.00 | $40.70 | — |
| **Kimi K2.5 (Ollama Max)** | **$100.00** | **$100.00** | ← Flat regardless of usage |

> **Break-even analysis**: At 110 runs/month, Kimi K2.5 at $100/mo is more expensive than per-token alternatives for Group Reasoning alone. However, the $100/mo covers ALL pipeline stages (not just Group Reasoning), plus any other Ollama Cloud usage. For teams running multiple projects or heavy incremental pipelines, the flat rate becomes the clear winner.

---

## 4. Runtime Modeling

### 4.1 Time Per Group Reasoning Run (20 groups, concurrency = 10)

| Model | Batch Time | Swarm Time | Swarm Overhead |
|-------|-----------|------------|----------------|
| **Kimi K2.5** | ~8s (2 waves × 4s) | ~12s (+coord +synth) | +4s |
| **GPT-5.4 mini** | ~5s (2 waves × 2.5s) | ~9s | +4s |
| **Claude Haiku 4.5** | ~4s (2 waves × 2s) | ~8s | +4s |
| **Claude Sonnet 4.6** | ~10s (2 waves × 5s) | ~14s | +4s |
| **Gemini 2.5 Flash** | ~4s (2 waves × 2s) | ~8s | +4s |
| **Grok 4.20** | ~5s (2 waves × 2.5s) | ~9s | +4s |

> The swarm overhead is roughly constant (~4s) regardless of model — it's the time for 2 extra sequential LLM calls (coordinator + synthesis). The parallel worker phase takes the same time as batch mode since both use the same concurrency budget.

### 4.2 Scaling: What Happens With Larger Repos?

| Repo Size | Groups | Batch (c=10) | Swarm (c=10) | Swarm Advantage |
|-----------|--------|-------------|-------------|-----------------|
| 200 files | 5 | ~3s (1 wave) | ~7s (1 wave + coord/synth) | ❌ Overhead dominates |
| 500 files | 12 | ~7s (2 waves) | ~11s | ⚠️ Marginal |
| 1,000 files | 20 | ~10s (2 waves) | ~14s | ✅ Quality gain worth it |
| 3,000 files | 45 | ~25s (5 waves) | ~29s | ✅ Synthesis very valuable |
| 10,000 files | 100+ | ~60s (10 waves) | ~64s | ✅ Cross-group patterns essential |

> **Decision threshold**: Swarm becomes worthwhile at **≥15 groups** (~500+ files). Below that, the coordinator/synthesis overhead adds time without enough groups to produce meaningful cross-group patterns.

---

## 5. Tuning Guidelines (Corrected)

### 5.1 Model-Specific Concurrency Recommendations

| Model | Max Concurrency | Reasoning |
|-------|----------------|-----------|
| **Kimi K2.5 (Ollama Max)** | 10 | Plan allows 10 concurrent cloud models |
| **GPT-5.4 mini** | 10 | Default ~10M TPM easily handles 10 parallel calls |
| **Claude Haiku 4.5** | 8–10 | 200 RPM limit; 10 concurrent is fine |
| **Claude Sonnet 4.6** | 5–8 | Higher per-call latency; more than 8 wastes slots waiting |
| **Gemini 2.5 Flash** | 10 | High throughput, handles parallel well |
| **Grok 4.20** | 10–15 | 1,800 RPM capacity could support more; CoDRAG caps at 10 |

### 5.2 Batch vs Swarm Decision Matrix (Updated)

| Groups | Model Tier | Mode | Why |
|--------|-----------|------|-----|
| < 5 | Any | **Batch** | Too few groups for meaningful cross-group synthesis |
| 5–14 | Any | **Batch** | Swarm overhead (~4s) not justified for modest analysis |
| 15–30 | Budget (Haiku, mini, Flash) | **Swarm** | Cheap enough that +2 calls are negligible; synthesis adds real value |
| 15–30 | Mid-tier (Sonnet, GPT-5.4) | **Swarm** | Cost delta is $0.04–$0.08; synthesis is worth it |
| 30+ | Any | **Swarm** | Cross-group patterns are critical at this scale |
| Any | Flat-rate (Kimi Ollama) | **Swarm** | No cost penalty; always use swarm when groups ≥ 3 |

### 5.3 Batch Size Optimization

Batch size is governed by context window minus the system prompt overhead (~2K tokens) and the required output headroom (~5K tokens):

```
effective_batch_capacity = (context_window × 0.8) - system_prompt_tokens - output_headroom
files_per_batch = effective_batch_capacity / avg_tokens_per_group_context
```

| Model | Safe Capacity | Groups per Batch |
|-------|--------------|-----------------|
| Kimi K2.5 (256K) | ~200K | ~50 groups |
| GPT-5.4 mini (400K) | ~310K | ~77 groups |
| Claude Haiku (200K) | ~155K | ~38 groups |
| Claude Sonnet (1M) | ~790K | All groups fit in 1 batch |
| Gemini 2.5 Flash (1M) | ~790K | All groups fit in 1 batch |
| Grok 4.20 (2M) | ~1.6M | All groups fit in 1 batch |

> For models with ≥1M context, a single batch call can process the entire repo's groups in one shot. This makes the batch vs swarm decision purely about quality (swarm adds scoped analysis + synthesis) rather than capacity.

---

## 6. Practical Recommendations

### For Solo Developers / Small Teams
1. **Use Kimi K2.5 via Ollama Cloud Max ($100/mo)** — flat rate, no surprises, always enable swarm.
2. **Alternative**: Gemini 2.5 Flash ($0.04/run) or GPT-5.4 mini ($0.09/run) — both absurdly cheap.
3. Enable swarm for any project with 15+ groups.

### For Enterprise / Multi-Project Teams
1. **Kimi K2.5 Ollama Max** remains the best value if running multiple projects.
2. For teams already on OpenAI contracts: **GPT-5.4 mini workers + GPT-5.4 coordinator** — mixed-model swarm for best cost/quality ratio.
3. For teams on Anthropic: **Claude Haiku 4.5 workers + Claude Sonnet 4.6 coordinator** — same pattern.

### For Cost-Sensitive / Hobby Users
1. **Gemini 2.5 Flash-Lite** ($0.10 in / $0.40 out) — the cheapest viable option at ~$0.01/run.
2. **Grok 4.1 Fast** ($0.20 in / $0.50 out) — similarly cheap with a massive 2M context window.
3. Disable swarm; use batch-only to minimize API calls.

### Surprising Finding: Grok 4.20 as a Dark Horse
**Grok 4.20** ($2.00 in / $6.00 out) offers **better output pricing than Claude Sonnet ($15.00 out) or GPT-5.4 ($15.00 out)** at 60% less cost for output tokens. Its 2M context window means every CoDRAG group reasoning batch fits in a single call. The 1,800 RPM rate limit is the most generous of any provider. For users who want frontier-quality coordination without Anthropic/OpenAI pricing, Grok is the sleeper pick.

---

## 7. Next Steps

1. **Benchmark on real repos**: Run Group Reasoning with swarm on/off for CoDRAG's own codebase (~320 files, ~12 groups) and a larger target (1K+ files).
2. **Implement auto-mode**: Add heuristic in `batch_profiles.py` that selects `mode = "swarm"` when `group_count >= 15` and model tier is BOTH or COORDINATOR.
3. **Mixed-model swarm**: Prototype using a cheaper worker model (Haiku/mini) with a more capable coordinator (Sonnet/GPT-5.4) to optimize cost.
4. **Feed benchmarks into registry**: Add `recommended_batch_size` and `default_concurrency` fields to `swarm_models.json`.

---

## 8. Context Window Quality: The "Lost in the Middle" Problem

> **This section answers the question: if Grok has a 2M context window and Gemini 2.5 Pro has 1M, can we just stuff the whole repo in and skip batching entirely? And if we do, will quality suffer?**

### 8.1 The Research Findings

The short answer: **yes, quality degrades significantly** as context fills up, even well before hitting the advertised ceiling. This is one of the most well-studied problems in LLM engineering as of 2026.

**"Lost in the Middle" (2023, confirmed through 2026)**  
Research consistently shows that transformer models exhibit a **U-shaped attention bias**: they attend strongly to information at the very beginning and very end of the prompt, but struggle with content buried in the middle. For a 1M token context stuffed with 200+ file summaries, anything past the first ~50 and before the last ~50 groups is significantly more likely to be misinterpreted or ignored during synthesis.

**"Context Rot" (Chroma, 2025 → confirmed 2026)**  
Chroma's research formalized "context rot" — the measurable, continuous degradation of output quality as input length increases, even when far from the maximum capacity. Key findings:
- **Affects every tested model** — this is a fundamental property of current transformer architectures, not a model-specific bug
- **Starts earlier than expected** — detectable quality degradation can begin at 30%–50% fill, depending on task complexity
- **Retrieval vs. reasoning**: models are much better at *finding* things in large contexts (needle-in-haystack) than at *synthesizing across* many things simultaneously (which is exactly what Group Reasoning does)

**Attention Dilution**  
Transformer attention is softmax-normalized. As the token count grows, the attention "budget" is spread proportionally thinner across more tokens. Each individual file's summary competes with every other file for the model's working memory. Past a certain point, the model can't meaningfully hold all the patterns simultaneously, even if it "saw" them all.

### 8.2 Effective Context Window (MECW) vs. Advertised Window

The research community has established the concept of the **Maximum Effective Context Window (MECW)** — the point beyond which complex reasoning output quality drops measurably. The MECW is typically a fraction of the advertised limit:

| Model | Advertised Limit | Est. MECW (Complex Reasoning) | Tasks at MECW |
|-------|-----------------|-------------------------------|---------------|
| **Kimi K2.5** | 256K | ~50K–80K | ~13–21 groups |
| **GPT-5.4 mini** | 400K | ~80K–120K | ~21–32 groups |
| **GPT-5.4** | 400K | ~100K–150K | ~26–40 groups |
| **Claude Haiku 4.5** | 200K | ~40K–60K | ~10–16 groups |
| **Claude Sonnet 4.6** | 1M | ~150K–250K | ~40–66 groups |
| **Gemini 2.5 Flash** | 1M | ~150K–300K | ~40–80 groups |
| **Gemini 2.5 Pro** | 1M–2M | ~200K–400K | ~53–107 groups |
| **Grok 4.20** | 2M | ~200K–500K | ~53–133 groups |

> **Critical caveat**: Gemini models have been shown to maintain high *retrieval accuracy* (needle-in-haystack >99%) across their full context, but their *synthesis reasoning quality* — exactly what we need for cross-group pattern detection — degrades much earlier. The MECW estimates above are for synthesis tasks, not retrieval tasks.

### 8.3 What This Means for a 1,000-File Repo

**Scenario: You have 1,000 files → ~25–30 groups.**

Each group context is ~3K–5K tokens. Total batch input for all 30 groups ≈ **100K–150K tokens**.

- **Kimi K2.5 (256K window)**: 100–150K tokens is 40%–60% fill. **Right in the danger zone for context rot.** A Kimi batch trying to process all 30 groups at once in a single call will produce noticeably lower quality than batching in chunks of 8–10 groups.
- **Grok 4.20 (2M window)**: 100–150K tokens is only 5%–7% fill. **Well within safe range.** Grok can genuinely do the whole thing in one call and get good results.
- **Gemini 2.5 Pro (1M–2M window)**: Same — 5%–15% fill. Synthesis quality should remain high.
- **Claude Sonnet 4.6 (1M window)**: 10%–15% fill. Also safe for a 1K-file repo.

**The Kimi disadvantage is real**: For a 1,000-file repo with 30 groups, Kimi needs to partition into 3–4 sub-batches (8–10 groups each), while Grok/Gemini/Sonnet can do it in one pass. This means:
- More API calls (3–4 vs. 1)
- No cross-group patterns visible within the same call
- Synthesis quality is limited to per-sub-batch, not holistic
- The swarm architecture partially compensates by using a coordinator for synthesis, but the workers still see less context

### 8.4 Recommended Context Fill Caps (Per Model)

Based on the research, we should implement **hard fill caps** in CoDRAG's batch sizing logic. The cap is expressed as a percentage of the model's advertised context window:

| Model | Advertised Window | **Recommended Fill Cap** | **Max tokens to use** | Notes |
|-------|-----------------|--------------------------|----------------------|-------|
| **Kimi K2.5** | 256K | **35%** | ~90K | Context rot observed past 40% for synthesis tasks |
| **GPT-5.4 mini** | 400K | **40%** | ~160K | Mini models degrade faster than full-size |
| **GPT-5.4** | 400K | **45%** | ~180K | Structured outputs help maintain quality |
| **Claude Haiku 4.5** | 200K | **35%** | ~70K | Smallest effective window in our registry |
| **Claude Sonnet 4.6** | 1M | **50%** | ~500K | Extensive training on long-context; holds up better |
| **Gemini 2.5 Flash** | 1M | **50%** | ~500K | High retrieval accuracy maintained longer |
| **Gemini 2.5 Pro** | 1M | **55%** | ~550K | Best synthesis quality at long context in our registry |
| **Grok 4.20** | 2M | **50%** | ~1M | Strong architecture; 50% is conservative but safe |

> **Why not 80%+?** The earlier draft used 80% as the headroom cap, leaving room for system prompt + response. But the context rot research makes a stronger argument for much lower caps on *synthesis quality* grounds. Even if the API accepts the full request, reasoning quality degrades. CoDRAG's goal is high-quality architectural analysis, not just "it returned something."

### 8.5 Revised Batch Size Table (With Quality-Aware Caps)

| Model | Quality-Aware Token Cap | Groups per Batch (@ 4K tokens/group) |
|-------|------------------------|--------------------------------------|
| Kimi K2.5 | 90K | **~22 groups** |
| GPT-5.4 mini | 160K | **~40 groups** |
| GPT-5.4 | 180K | **~45 groups** |
| Claude Haiku 4.5 | 70K | **~17 groups** |
| Claude Sonnet 4.6 | 500K | **~125 groups** ✅ single pass for any repo |
| Gemini 2.5 Flash | 500K | **~125 groups** ✅ single pass for any repo |
| Gemini 2.5 Pro | 550K | **~137 groups** ✅ single pass for any repo |
| Grok 4.20 | 1M | **~250 groups** ✅ single pass for any repo |

For a 1,000-file repo with ~25–30 groups, **only Kimi K2.5** requires multiple batch passes (1.5–2 passes). All other models in the registry can handle the entire repo in a single Group Reasoning batch call.

### 8.6 CoDRAG Implementation Guidance

The batch sizing logic in `batch_profiles.py` should be updated to use quality-aware caps rather than the naive "80% of context window" formula:

```python
# Quality-aware context fill caps per model family
QUALITY_FILL_CAPS = {
    "kimi":         0.35,  # Context rot observed past 40% for synthesis
    "gpt-5.4-mini": 0.40,
    "gpt-5.4":      0.45,
    "haiku":        0.35,
    "sonnet":       0.50,  # Sonnet 4.6 1M window; holds quality longer
    "gemini-flash": 0.50,
    "gemini-pro":   0.55,  # Best long-context synthesis in registry
    "grok":         0.50,
    "default":      0.40,  # Conservative fallback for unknown models
}

def get_max_batch_tokens(model_family: str, context_window: int) -> int:
    """Return quality-safe max input tokens for a model family."""
    fill_cap = QUALITY_FILL_CAPS.get(model_family, QUALITY_FILL_CAPS["default"])
    # Reserve 5K for system prompt + 5K for output headroom
    available = (context_window * fill_cap) - 5000 - 5000
    return max(0, int(available))
```

**Additional mitigations to implement:**
1. **Front-load critical context**: Always place the most architecturally significant groups (highest coupling score, most edges) at the top of the batch prompt. Groups at the bottom get less attention, so put less critical ones there.
2. **Structured JSON input**: Use compact JSON for group data rather than free-form text. This increases information density and reduces context usage per group.
3. **Dynamic cap enforcement**: Before each LLM call, measure estimated token count of the assembled batch and split if it exceeds the model's quality cap — don't just trust the API to accept it.

### 8.7 Practical Implication: Kimi vs. Large-Window Models

This confirms a real trade-off:

| | Kimi K2.5 (Ollama, flat rate) | Grok 4.20 / Gemini Pro (per token) |
|--|-------------------------------|--------------------------------------|
| **Cost** | $100/mo flat | ~$0.18–$0.22/run |
| **Context window** | 256K (35% cap → 90K usable) | 1M–2M (50% cap → 500K–1M usable) |
| **Groups per batch** | ~22 | ~125–250 |
| **Batch passes for 30 groups** | **~2** | **1** |
| **Cross-group synthesis** | Per sub-batch (limited) | Whole-repo in one pass (superior) |
| **Break-even** | Wins at >500 runs/mo | Wins at <500 runs/mo |

**The honest conclusion**: For users who run the pipeline heavily (daily across many projects), Kimi at $100/mo is still a strong deal — but they need to accept that the 256K context means sub-batch processing for large repos. For users who want the **highest quality single-pass analysis** without worrying about context rot, **Grok 4.20** or **Gemini 2.5 Pro** offer genuine architectural advantages, not just marketing.

The swarm orchestrator partially bridges this gap for Kimi — by having the coordinator synthesize across sub-batches — but it cannot fully replicate the quality of a model that saw all 30 groups in one attention pass.

---

*All pricing verified against official provider documentation as of 2026-04-07. Throughput estimates from third-party benchmarks (morphllm.com, benchlm.ai) and community reports. Context window quality research from Liu et al. (2023), Chroma (2025), and corroborating studies through 2026. Prices subject to change — always verify with provider pricing pages before production deployment.*

---

## 9. What "Whole Repo in One Call" Actually Means Per Stage

> **This section answers: "Which stages are we talking about? Could each pipeline stage realistically be one API call? And doesn't that make Opus a viable option if there are only 7–8 total calls?"**

This is exactly the right question to ask before committing to any model recommendation, so let's ground this in the actual code.

### 9.1 The 11 CoDRAG Pipeline Stages: What Each Actually Does

From `src/codrag/services/pipeline/stages.py`, the 11 stages divide into two groups:

**Fast-Sync Stages (no LLM, or trivial LLM):**

| Stage | LLM? | What it does | Calls for 1K files |
|-------|-------|-------------|---------------------|
| `STRUCTURAL` | ❌ No — Rust | Walks the file tree, extracts AST nodes/edges | 0 LLM calls |
| `INFERRED_EDGES` | ✅ Yes | Infers implicit edges between files not caught by AST | ~1K calls (1 per file) |
| `CATALOGUE` | ✅ Yes | Short summary + role for every file/symbol | ~1K calls — **batched** (batches of ~5–10) |
| `VALIDATION` | ❌ No — Rust | Validates edges + schema consistency | 0 LLM calls |
| `KNOWLEDGE` | ❌ No — Embeddings | Generates vector embeddings for RAG | 0 LLM calls |

**Deep-Enrichment Stages (heavy LLM, multiple calls):**

| Stage | LLM? | What it does | Calls for 1K files |
|-------|-------|-------------|---------------------|
| `ENRICHMENT` | ✅ Yes (large slot) | Deep epistemic analysis of every file — incl. neighbor context, topology ordering | **~1K calls, batched into tiers** |
| `GROUP_REASONING` | ✅ Yes (large slot) | Analyzes interdependencies within each cluster of related files | **~20–30 calls** (one per group) |
| `CLUSTERING` | ✅ Yes (large slot) | Synthesizes each cluster into a named module entry | **~20–30 calls** (one per cluster) |
| `ATLAS` | ✅ Yes (large slot) | Generates the high-level codebase atlas overview | **~1–3 calls** (whole-codebase synthesis) |
| `DEEPENING` | ✅ Yes (large slot) | Re-enriches files that scored low confidence, with more context | **~200–500 calls** (variable, only stale/low-conf files) |
| `DEEP_KNOWLEDGE` | ❌ No — Embeddings | Re-embeds with enriched content | 0 LLM calls |

### 9.2 The Real API Call Count (1,000-File Repo)

The critical insight: **most LLM calls happen in the per-file stages (CATALOGUE, ENRICHMENT, DEEPENING), not the synthesis stages.** Here's the actual math:

| Stage | ~API Calls (1K files) | Tokens per call | Stage total tokens |
|-------|-----------------------|-----------------|-------------------|
| `INFERRED_EDGES` | ~1,000 | ~2K–4K | ~3M |
| `CATALOGUE` | ~150 (batched 7/call) | ~12K–15K | ~2M |
| `ENRICHMENT` | ~1,000 | ~3K–5K (file + neighbors) | ~4M |
| `GROUP_REASONING` | ~25 | ~4K–8K (group context) | ~150K |
| `CLUSTERING` | ~25 | ~3K–5K (cluster summary) | ~100K |
| `ATLAS` | ~1–3 | ~20K–50K (all modules) | ~100K |
| `DEEPENING` | ~300 (30% re-run) | ~4K–6K | ~1.5M |
| **Total** | **~2,500 calls** | — | **~11M tokens** |

> **Key finding from actual code**: `augmenter.py` line 8 explicitly states: *"Each LLM call is self-contained (~2-4k tokens), never whole-repo context."* The architecture was deliberately designed this way. The claim that a large context window lets you "do the whole repo in one call" is **only true for the synthesis stages** (`GROUP_REASONING`, `CLUSTERING`, `ATLAS`), which together represent fewer than 60 of those ~2,500 total calls.

### 9.3 Why Can't We Collapse Everything Into Fewer Calls?

**ENRICHMENT stage** (`epistemic_enrichment.py`): processes nodes in **reverse topological order** (leaf files first) specifically so each file's enrichment can use its neighbors' already-enriched summaries as context. This is a dependency chain — you *cannot* enrich all 1,000 files in a single call because file B's enrichment depends on file A being enriched first. The tiers must be sequential.

**CATALOGUE stage** (`augmenter.py`): batches multiple files per call (currently ~5–10 per call), but there's no benefit to putting all 1,000 files in one call — the model would need to hold 4M tokens of raw source in context and output 1,000 separate JSON entries. This is precisely the context rot scenario: quality would collapse. The current batching strategy (small focused batches) is correct by design.

**INFERRED_EDGES stage**: each file needs its own isolated call because inferred-edge detection is about inferring implicit relationships between *specific* file pairs, one at a time. Batching them together degrades the signal.

### 9.4 So Which Stages *Could* Be Collapsed With a Large Context Window?

Only the **synthesis stages** at the end:

| Stage | Current behavior | With large context (Grok 4.20 / Gemini Pro) |
|-------|-----------------|---------------------------------------------|
| `GROUP_REASONING` | 25 parallel calls (1/group) | Same — already 1 call per group, concurrency handles parallelism |
| `CLUSTERING` | 25 batched calls | Could reduce to 1–3 calls (all clusters in one prompt) |
| `ATLAS` | 1–3 calls already | Already 1 call — nothing to optimize |

**The bottom line**: large context windows do not meaningfully reduce total API calls. They improve quality *within* the synthesis calls by allowing more member context per call — but the high-volume stages (CATALOGUE: ~150, ENRICHMENT: ~1,000, INFERRED_EDGES: ~1,000) are bounded by architecture, not context window size.

### 9.5 Does This Make Claude Opus Viable?

Short answer: **No, and here's the actual math.**

Let's assume a universe where we could collapse everything into 8 synthesis-level calls:

| Model | Cost for 8 calls @ 50K tokens each (400K total) | Cost feasibility |
|-------|---------------------------------------------------|-----------------|
| **Claude Opus 4.6** | 400K × $5.00/M in + 100K × $25.00/M out = **$2.00 + $2.50 = $4.50** | Cheap *for those 8 calls* |

But that's not the real picture. The actual 2,500 calls look like:

| Model | Total cost (2,500 calls, 11M tokens in, ~3M out) |
|-------|--------------------------------------------------|
| **Claude Opus 4.6** | 11M × $5.00/M + 3M × $25.00/M = **$55 + $75 = $130 per run** |
| **Claude Sonnet 4.6** | 11M × $3.00/M + 3M × $15.00/M = **$33 + $45 = $78 per run** |
| **Claude Haiku 4.5** | 11M × $1.00/M + 3M × $5.00/M = **$11 + $15 = $26 per run** |
| **GPT-5.4 mini** | 11M × $0.75/M + 3M × $4.50/M = **$8.25 + $13.50 = $21.75/run** |
| **Gemini 2.5 Flash** | 11M × $0.30/M + 3M × $2.50/M = **$3.30 + $7.50 = $10.80/run** |
| **Kimi K2.5 (Ollama)** | **$0.00** (flat $100/mo regardless of usage) |

Opus at **$130/run** vs. Haiku at **$26/run** — for a codebase that gets re-analyzed daily, that's:
- Opus: $2,860/mo
- Haiku: $572/mo
- GPT-5.4 mini: $478/mo
- Gemini Flash: $238/mo
- Kimi Ollama: $100/mo flat

**And Opus doesn't produce 5× better output for CoDRAG's per-file tasks.** The CATALOGUE and ENRICHMENT stages need focused, structured JSON — not creative reasoning. Haiku and mini-tier models perform those tasks at near-Opus quality because the prompt is small and the task is well-defined. Opus's intelligence advantage pays off in **synthesis tasks** (ATLAS, GROUP_REASONING) where cross-cutting insight matters — but those are only ~60 of the 2,500 calls.

### 9.6 The Practical Architecture: Mixed-Model Strategy

This is why the recommended approach is **role-appropriate model routing**:

| Stage | Recommended Model | Reason |
|-------|------------------|--------|
| `INFERRED_EDGES` | Haiku / GPT-5.4 mini | Simple pairwise relationship detection — small model fine |
| `CATALOGUE` | Haiku / GPT-5.4 mini | Short summaries of small snippets — small model fine |
| `ENRICHMENT` | Haiku / Kimi | Structured analysis per file — moderate capability needed |
| `GROUP_REASONING` | Sonnet / GPT-5.4 / Grok 4.20 | Cross-file synthesis — mid-tier worthwhile here |
| `CLUSTERING` | Sonnet / GPT-5.4 | Module naming + architecture description — mid-tier |
| `ATLAS` | Sonnet / GPT-5.4 | Whole-codebase narrative — this is where quality matters most |
| `DEEPENING` | Haiku / mini | Re-enriching low-confidence files — same as ENRICHMENT |

This is already reflected in `STAGE_MODEL_SLOT` in `stages.py`:
- `CATALOGUE` → `"small"` slot
- `ENRICHMENT`, `GROUP_REASONING`, `CLUSTERING`, `ATLAS`, `DEEPENING` → `"large"` slot
- `INFERRED_EDGES` → `"code"` slot

Opus would be the right choice for the `"large"` slot if cost were no object, but Sonnet 4.6 or GPT-5.4 at 60%+ less cost with comparable synthesis quality is the pragmatic choice. **Opus is for humans who want the highest possible quality on a rarely-run analysis, not for automated pipeline workers.**

### 9.7 Updated Swarm Cost (Corrected Total)

Given the real call count (~2,500 calls, ~14M total tokens), a "swarm" mode that adds coordinator + synthesis calls on top adds roughly:

- **+2 calls** (coordinator decomposition + synthesis) = **+0.08% more calls**
- **+100K tokens** (coordinator input/output) = **+0.7% more tokens**

The swarm overhead is truly negligible — the documents were correct about that. The savings from Kimi's flat rate vs. per-token models are what drive the real economics, not the swarm multiplier.

---

*Source code verified as of 2026-04-07: `src/codrag/services/pipeline/stages.py`, `src/codrag/core/augmenter.py` (line 8), `src/codrag/core/epistemic_enrichment.py`, `src/codrag/core/cluster.py`. All pricing verified against official provider documentation.*

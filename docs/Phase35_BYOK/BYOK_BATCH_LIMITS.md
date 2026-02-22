# Research: BYOK Prompt Batching — Multi-Item LLM Calls

**Status:** Research IN PROGRESS — model specs verified, batch sizes calculated  
**Updated:** 2026-02-21  
**Priority:** High (core feasibility question for BYOK users)  
**Related:** Pipeline orchestrator, augmenter, epistemic enrichment, inferred edges, cluster synthesis

## The Core Idea

CoDRAG's pipeline was designed for small local models (3b). Each stage loops
over items one at a time: one file per LLM call, one symbol per LLM call.
That works fine when the model is local and free — latency per call is the
only cost, and small models can't handle much context anyway.

**BYOK changes the equation entirely.** When a user connects Claude Sonnet 4.5,
GPT-4.1, or Gemini 2.5 Pro, we have access to:
- 200K–1M token context windows (vs ~4K–8K for local 3b)
- 32K–64K output token limits (vs ~2K for local models)
- Much stronger instruction-following for structured multi-item output
- Per-token pricing where **one big call costs the same as many small calls**
  (input tokens × rate is identical either way)
- Network latency that makes many sequential small calls *slower* than
  fewer large calls

**Instead of calling Sonnet 200 times (once per file), we should batch 50–100
files into a single call and get all results back at once.**

This is not about "limiting" the pipeline. It's about making the pipeline
*smarter* when a powerful model is available.

---

## Research Questions

### Q1: What are the context window limits of target models?

**VERIFIED (2026-02-21)** — Output limits have **massively increased** since
early 2025. Most frontier models now support 32K–64K output tokens, not 8K.
This completely changes the batching math in our favor.

#### Current-generation models (recommended BYOK targets)

| Model | Input | Output | Structured Output | Pricing (in/out per 1M) |
|-------|-------|--------|-------------------|------------------------|
| **Claude Sonnet 4.5** | 200K | **64,000** | ✅ JSON schema (beta) | $3 / $15 |
| **Claude Haiku 4.5** | 200K | **64,000** | ✅ JSON schema (beta) | ~$0.80 / $4 |
| **Claude Opus 4.5** | 1M | **64,000** | ✅ JSON schema (beta) | $5 / $25 |
| **GPT-4.1** | 1M | **32,768** | ✅ json_schema (strict) | $2 / $8 |
| **GPT-4.1 mini** | 1M | **32,768** | ✅ json_schema (strict) | $0.40 / $1.60 |
| **Gemini 2.5 Pro** | 1M | **64,000** | ✅ JSON mode | varies |
| **Gemini 2.5 Flash** | 200K | 8K–32K | ✅ JSON mode | cheap |
| **DeepSeek V3.2** | 128K | ~8,192 | ✅ JSON mode + tools | $0.27 / $1.10 |

#### Previous-generation (still supported, lower limits)

| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| Claude 3 Opus/Sonnet/Haiku | 200K | 32,000 | Legacy, lower pricing |
| GPT-4o | 128K | 16,384 | Still widely used |
| GPT-4o-mini | 128K | 16,384 | Budget OpenAI option |
| Gemini 1.5 Pro | 1M–2M | 8,192 | Huge input, low output |

#### Key findings

- **64K output is now standard** on Claude 4.5 and Gemini 2.5 Pro
- **32K output** on GPT-4.1 family
- **Structured output** (JSON schema enforcement) available on all major
  providers — eliminates most parse reliability concerns
- **DeepSeek is the outlier** with only 8K output — still enough for
  batches of 20–40 items on most stages
- **o3/o4-mini** (OpenAI reasoning models) support 100K output but are
  expensive and slow — not ideal for pipeline batching

### Q2: How big are our per-item prompts?

Measured from the actual prompt templates in the codebase:

| Stage | Per-item input size | Per-item output size | Notes |
|-------|-------------------|---------------------|-------|
| **Catalogue (symbol)** | ~300–1,000 tok | ~50–80 tok | Source snippet + imports |
| **Catalogue (file)** | ~200–600 tok | ~80–120 tok | File head (30 lines) + symbol names |
| **Catalogue (doc)** | ~300–2,000 tok | ~80–120 tok | Strategic excerpt (up to 100 lines) |
| **Inferred edges** | ~500–2,000 tok | ~100–200 tok | Full source + known files list |
| **Epistemic (code)** | ~500–3,000 tok | ~200–350 tok | 150-line excerpt + neighbor context |
| **Epistemic (doc)** | ~1,000–8,000 tok | ~200–350 tok | Up to 3000-line excerpt |
| **Clustering** | ~500–3,000 tok | ~200–400 tok | Member summaries (up to 30 files) |

**Key observation:** Output per item is small (50–400 tokens). The output
limit is what constrains batch size — not the input window.

### Q3: How many items can we realistically batch per call?

**REVISED with verified output limits.** Using 32K output (GPT-4.1, most
conservative modern model) and 64K output (Claude 4.5, Gemini 2.5 Pro):

#### Conservative estimates (32K output — GPT-4.1)

| Stage | Items/batch | Est. input | Est. output | Headroom |
|-------|------------|-----------|------------|----------|
| Catalogue (symbols) | **100** | 30K–100K | 5K–8K | ✅ 24K spare |
| Catalogue (files) | **100** | 20K–60K | 8K–12K | ✅ 20K spare |
| Inferred edges | **50** | 25K–100K | 5K–10K | ✅ 22K spare |
| Epistemic (code) | **50** | 25K–150K | 10K–17.5K | ✅ 14K spare |
| Epistemic (docs) | **10–20** | 10K–160K | 2K–7K | ✅ (input-limited) |
| Clustering | **30** | 15K–90K | 6K–12K | ✅ 20K spare |

#### Generous estimates (64K output — Claude 4.5 / Gemini 2.5 Pro)

| Stage | Items/batch | Est. output | Notes |
|-------|------------|------------|-------|
| Catalogue (symbols) | **200+** | 10K–16K | Input window becomes the limit |
| Catalogue (files) | **200+** | 16K–24K | Easily fits |
| Inferred edges | **100** | 10K–20K | Fits comfortably |
| Epistemic (code) | **100** | 20K–35K | Fits with margin |
| Epistemic (docs) | **20–30** | 4K–10.5K | Input-limited (docs are big) |
| Clustering | **50** | 10K–20K | Fits easily |

**Conclusion: Batching 50 items per call is trivially feasible on all
current-gen models for all pipeline stages.** For catalogue (small items),
we could go to 100–200 per call. Epistemic docs are the tightest because
each item carries up to 3000 lines of content — input window is the limit.

**TODO:** Validate with actual token measurements from a real pipeline run.
The per-item estimates above are from prompt template analysis, not runtime.

### Q4: Does quality degrade when batching?

#### Structured output eliminates most parse reliability concerns

All three major providers now support **schema-enforced JSON output**:

- **OpenAI**: `response_format: { type: "json_schema", json_schema: {...} }`
  with `strict: true`. Guaranteed valid JSON matching the schema. Supported
  on GPT-4.1 and GPT-4o. Can define an array schema (e.g.
  `{ type: "array", items: { ... per-item schema } }`).
- **Anthropic**: `output_config.format` with JSON schema. Beta header
  `structured-outputs-2025-11-13`. Enforces valid JSON matching schema.
  Supported on all Claude 4.x models.
- **Google**: JSON mode via `response_mime_type: "application/json"` +
  `response_schema`. Supported on Gemini 2.5+.

With structured output, the model **cannot** produce invalid JSON. The schema
can define an array of per-item results, guaranteeing we get exactly N items
back in the correct format.

#### Remaining quality concerns

- **"Lost in the Middle"**: Less relevant here. Each item is clearly
  delimited with headers (`=== FILE 1 ===`). The model isn't searching for
  a needle — it's processing a structured list. Quality degradation is more
  likely to manifest as **laziness on later items** (shorter summaries,
  less detail) than as missed items.
- **Item count sweet spot**: Even with 64K output, there's likely a
  practical quality ceiling. 50 items is probably fine; 200 might cause
  the model to rush. Need empirical testing.
- **Error isolation**: With structured output, partial failures shouldn't
  happen (the whole response is valid or the API returns an error). If the
  model times out mid-response, we lose the whole batch. Mitigation: keep
  batches small enough that generation completes well within timeout.

**TODO (empirical):** Test with 20, 50, 100 items on Sonnet 4.5 and GPT-4.1.
Measure summary quality (length, specificity) for items at positions 1, 25, 50,
100. Check for lazy-tail degradation.

### Q5: What prompt structure works best for batched calls?

Candidate formats for the batched prompt:

**Option A: Numbered item list**
```
Analyze each of the following files. For EACH file, produce one JSON object.
Return a JSON array with one entry per file, in the same order.

=== FILE 1: src/core/trace.py ===
Language: Python
Symbols: TraceBuilder, TraceIndex, ...
First 30 lines:
{code}

=== FILE 2: src/core/index.py ===
...

Respond with:
[{"file": "src/core/trace.py", "summary": "...", "role": "...", ...},
 {"file": "src/core/index.py", "summary": "...", "role": "...", ...}]
```

**Option B: System prompt defines the task, user sends items as JSONL**
```
System: You are a code analyst. For each item in the input, produce a JSON
analysis. Return results as a JSON array.

User:
{"id": 1, "file": "trace.py", "head": "...", "symbols": [...]}
{"id": 2, "file": "index.py", "head": "...", "symbols": [...]}
```

**Option C: Structured output with JSON schema (RECOMMENDED)**
All three major providers now support this. Define a schema like:
```json
{
  "type": "object",
  "properties": {
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file": {"type": "string"},
          "summary": {"type": "string"},
          "role": {"type": "string", "enum": ["api", "core", "utility", ...]},
          "confidence": {"type": "number"}
        },
        "required": ["file", "summary", "role", "confidence"]
      }
    }
  },
  "required": ["results"]
}
```
The model is **guaranteed** to return valid JSON matching this schema.
No parse failures, no regex fallbacks needed.

**Recommendation:** Use Option C (structured output) when the provider
supports it (OpenAI, Anthropic, Google all do). Fall back to Option A
(numbered list + raw JSON) for providers without schema enforcement
(DeepSeek, self-hosted models).

### Q6: How does batching change cost economics?

With batching, the total tokens are roughly the same (same input data, same
output data), but:

- **Fewer API calls** → lower latency overhead, fewer rate-limit hits
- **Per-call overhead tokens** (system prompt, instructions) are amortized
  across N items instead of repeated N times → ~10-30% token savings
- **Parallel batches** possible: send 4 batches of 50 concurrently instead
  of 200 sequential calls

**Cost estimate (Sonnet 4.5 pricing: $3/M in, $15/M out):**

| Repo size | Files | Individual calls | Batched (50/call) | Savings |
|-----------|-------|-----------------|-------------------|----------|
| Small | 50 | ~300 calls, ~$2 | ~6 calls, ~$1.50 | ~25% |
| Medium | 200 | ~1,200 calls, ~$10 | ~24 calls, ~$7 | ~30% |
| Large | 1,000 | ~5,000 calls, ~$50 | ~100 calls, ~$35 | ~30% |

**Budget option: GPT-4.1 mini ($0.40/M in, $1.60/M out) — 15× cheaper:**

| Repo size | Files | Individual calls | Batched (50/call) | Savings |
|-----------|-------|-----------------|-------------------|----------|
| Small | 50 | ~300 calls, ~$0.15 | ~6 calls, ~$0.10 | ~33% |
| Medium | 200 | ~1,200 calls, ~$0.60 | ~24 calls, ~$0.40 | ~33% |
| Large | 1,000 | ~5,000 calls, ~$3 | ~100 calls, ~$2 | ~33% |

The token cost savings from batching are ~25–33% (amortized system prompt).
The **real win is wall-clock time**: 6 API calls complete in ~30 seconds vs
300 sequential calls taking 10–15 minutes. With parallel batches (4 concurrent),
a 200-file repo finishes in under a minute.

**GPT-4.1 mini is the standout BYOK recommendation**: full pipeline run on a
1,000-file repo for ~$2. That's cheaper than a coffee.

### Q7: What about stages with inter-item dependencies?

Not all stages are embarrassingly parallel:

- **Catalogue**: ✅ Fully independent — each file/symbol analyzed in isolation
- **Inferred edges**: ✅ Independent per file (needs known_files list, but
  that's shared context, not per-item dependency)
- **Epistemic enrichment**: ⚠️ **Has dependencies** — uses `topological_sort_files()`
  (Kahn's algorithm) to process leaves first. Each node reads neighbor enrichment
  from earlier nodes via the `enriched` dict (see `_get_neighbor_context()`).

  **Batching strategy: tier-based.** Kahn's algorithm naturally creates tiers:
  - **Tier 0** (leaves): Files with no outgoing import/reference edges. These
    have no enriched neighbors — their neighbor context falls back to Pass 1
    augmentation summaries. **All tier-0 files can be batched together.**
  - **Tier 1**: Files that only depend on tier 0. After tier 0 completes,
    all tier-1 files see their tier-0 neighbors' enrichment. **All tier-1
    files can be batched together.**
  - **Tier N**: Depends on tiers 0..N-1. Process after tier N-1 completes.

  For a typical 200-file repo, the tier distribution is likely:
  - Tier 0: ~60-80 files (utilities, configs, leaf modules) → 1-2 batch calls
  - Tier 1: ~40-60 files (modules importing utilities) → 1 batch call
  - Tier 2: ~20-40 files (higher-level orchestrators) → 1 batch call
  - Tier 3+: ~10-20 files (entry points, top-level) → 1 batch call
  - **Total: ~5-6 sequential batch calls instead of 200 individual calls**

  **Quality impact**: Within a tier, items don't see each other's epistemic
  enrichment — only Pass 1 summaries. This is a minor quality loss (neighbor
  context is slightly less rich) but probably acceptable since the primary
  analysis comes from the file's own source code, not neighbor context.

- **Clustering**: ✅ Each cluster is independent of other clusters. Clusters
  vary in size (5-50 files), but the prompt is per-cluster, not per-file.
  Small clusters can be batched together easily. A 200-file repo typically
  has 10-20 clusters → fits in 1-2 batch calls.

---

## Proposed Architecture

### Dual-Path Pipeline

The pipeline should detect whether the configured model is local or BYOK
and choose the appropriate execution strategy:

```
Local (Ollama/3b):     for item in items: llm.generate(per_item_prompt)
BYOK (Sonnet/GPT-4.1): for batch in chunk(items, batch_size): llm.generate(batched_prompt)
```

This is a **per-stage strategy**, not a global setting. Each stage's worker
gets a `BatchStrategy` that knows:
- Whether to batch
- Optimal batch size for this stage × this model
- Prompt template for batched calls
- Parser for batched responses

### Single-Setting Batch Profiles

The user should **never see per-stage batch sizes**. That's an implementation
detail. Instead, we expose **one setting** and derive everything under the hood.

**How it works:** When the user configures a BYOK model, we detect (or they
select) the model's output token class. That maps to a named batch profile
which sets all per-stage numbers automatically:

| Profile | Output class | Catalogue | Inferred | Epistemic (code) | Epistemic (docs) | Clustering |
|---------|-------------|-----------|----------|-------------------|-------------------|------------|
| **Large** | 64K (Claude 4.5, Gemini 2.5 Pro) | 100 | 50 | 50 | 15 | 30 |
| **Standard** | 32K (GPT-4.1, Claude 3) | 50 | 30 | 25 | 10 | 20 |
| **Compact** | 8K–16K (DeepSeek, GPT-4o, Gemini Flash) | 20 | 15 | 10 | 5 | 10 |
| **Local** | <8K (Ollama/3b) | 1 | 1 | 1 | 1 | 1 |

**Auto-detection logic:**
1. User configures a model → we know the provider + model name
2. Look up output token limit from a built-in model registry
3. Select the matching profile
4. Done — user never has to think about batch sizes

If the user *really* wants control, they can override the profile via an
advanced dropdown, but the default is "Auto" which just works.

### UI: BYOK Batch Configuration

```
┌─────────────────────────────────────────────────┐
│ Cloud Processing                                 │
│                                                  │
│ Batch mode: [Auto (Standard - 50/call) ▼]        │
│                                                  │
│ Estimated: 8 API calls for 237 files             │
│ vs. 237 individual calls without batching        │
│                                                  │
│ ⓘ Based on GPT-4.1 mini (32K output tokens)     │
└─────────────────────────────────────────────────┘
```

The dropdown shows:
- **Auto** (default) — detects model, picks profile
- **Large** — for 64K output models
- **Standard** — for 32K output models
- **Compact** — for 8K–16K models
- **Off** — process one item at a time (local-model behavior)

### Response Parsing

Need a robust multi-item JSON parser that:
1. Tries `json.loads()` on the whole response (JSON array)
2. Falls back to splitting on `\n` and parsing each line (JSONL)
3. Falls back to regex extraction of individual `{...}` objects
4. Maps each result back to its input item by file path / ID
5. Items that fail to parse get re-queued as individual calls (fallback)

---

## Implementation Plan

### Phase 1: Measure & Validate
- [ ] Pull actual token counts from real pipeline runs (augmenter, epistemic)
- [ ] Test batched prompts manually with Opus + GPT-4o (10, 25, 50 items)
- [ ] Measure: parse success rate, quality vs individual, wall-clock time
- [ ] Document optimal batch sizes per stage per model

### Phase 2: Batched Prompt Templates
- [ ] Write batched variants of each prompt template
- [ ] Implement `BatchedResponseParser` (multi-item JSON extraction)
- [ ] Add `batch_size` to `LLMClient` or `StageConfig`

### Phase 3: Pipeline Integration
- [ ] `BatchStrategy` class: decides batch vs individual per stage
- [ ] Wire into pipeline_orchestrator stage workers
- [ ] Handle partial failures (re-queue failed items as individual calls)
- [ ] Dependency-tier batching for epistemic enrichment

### Phase 4: UI & Cost Estimation
- [ ] Batch size selector in AI Models settings
- [ ] Pre-run estimate: "8 API calls, ~$7 estimated"
- [ ] Post-run summary: "Processed 237 files in 8 calls (42 seconds)"

---

## Resolved Questions

1. **Output limit extensions**: ✅ RESOLVED — Standard output limits (32K–64K)
   are more than sufficient. No need for extended thinking or special modes.
2. **Structured output**: ✅ RESOLVED — All 3 major providers support JSON
   schema enforcement. Parse reliability is a non-issue when using it.

## Remaining Open Questions

1. **Rate limits**: Does batching help or hurt? Most providers rate-limit on
   tokens/min, not calls/min — batching shouldn't help or hurt. But fewer
   calls = fewer chances to hit RPM (requests per minute) limits.
2. **Streaming**: Should batched calls stream? Could show per-item progress
   as items arrive in the stream. More complex to parse, but possible with
   structured output (stream until valid JSON array closes).
3. **Mixed-model batching**: User has Haiku for catalogue (cheap) and Sonnet
   for epistemic (quality). Batch sizes should differ per slot. Already
   handled by the per-stage BatchStrategy design.
4. **Retry granularity**: If a batch of 50 times out, retry whole batch or
   split? Recommendation: retry once, then halve batch size, then fall back
   to individual calls.
5. **Token counting**: Need pre-flight token estimation to avoid exceeding
   context window. Options: tiktoken (OpenAI), anthropic tokenizer, or
   simple chars÷4 heuristic (good enough for planning, not billing).
6. **Lazy-tail degradation**: Do models produce lower-quality output for
   items near the end of a large batch? Needs empirical testing.
7. **Optimal BYOK model recommendation**: GPT-4.1 mini looks like the sweet
   spot (cheapest, 1M context, 32K output, structured output). Should we
   default-recommend it in the UI when user selects BYOK?

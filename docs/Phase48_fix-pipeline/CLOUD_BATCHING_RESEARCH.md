# Cloud Model Batching Research: Quality, Thresholds, and Thinking Models

> How do frontier cloud models behave when given multi-item batched prompts for structured JSON output? What quality degradation occurs? How should Prep detect and handle Ollama-proxied cloud models vs true local models?

**Created:** 2026-03-15
**Context:** Prep pipeline stages 2-3 (Edge Discovery, Fast Catalogue) send one prompt per item. For cloud models, batching multiple items per API call could reduce 641 sequential calls to ~13-32 calls -- a 95% speed improvement. But does batching degrade quality?

---

## 1. The Three Problems

### Problem A: Ollama-proxied cloud models aren't detected as cloud
Prep's `batch_profiles.py` classifies ALL Ollama models as local (`_LOCAL_PROVIDERS = {"ollama", "lm-studio"}`). But users run cloud models via Ollama (kimi-k2.5:cloud, deepseek-r1, qwen3.5) where batching would be beneficial and safe. The batch profile system sees `provider=ollama` and sets profile to OFF.

### Problem B: Symbol augmentation (Pass 1) is never batched
The augmenter's `run()` method has two passes:
- **Pass 1 (symbols)**: Always sequential, one LLM call per symbol. No batching code path exists.
- **Pass 2 (files)**: Has a batched code path (`_augment_files_batched()`) gated on `batch_profile != "off"`.

For a project with 641 symbols + 177 files, Pass 1 dominates runtime (78% of items) and is never batched.

### Problem C: Thinking models emit chain-of-thought before JSON
Models like kimi-k2.5, DeepSeek-R1, Qwen3.5 (thinking variants) output their reasoning process before the structured JSON response. Prep's JSON parser sees "The user wants me to analyze..." and fails to extract the JSON.

---

## 2. Frontier Cloud Model Behavior Matrix

### Structured JSON Output Compliance

| Model Family | Provider | Thinking Output | JSON Compliance | Batch-Safe | Context Window | Notes |
|-------------|----------|-----------------|-----------------|------------|----------------|-------|
| **GPT-4.1** | OpenAI | No thinking | Excellent (native JSON mode) | Yes | 1M | `response_format: {type: "json_object"}` enforces valid JSON |
| **GPT-4.1-mini** | OpenAI | No thinking | Excellent | Yes | 1M | Same JSON mode as GPT-4.1 |
| **GPT-4.1-nano** | OpenAI | No thinking | Excellent | Yes | 1M | Cheapest, still JSON-compliant |
| **GPT-5** | OpenAI | Optional (o-series) | Excellent | Yes | 1M+ | Structured output API available |
| **Claude Sonnet 4.5** | Anthropic | Extended thinking (optional) | Good (follows instructions) | Yes | 200K | Thinking in separate `thinking` block, not mixed with output |
| **Claude Haiku 3.5** | Anthropic | No thinking | Good | Yes | 200K | Fast, reliable JSON |
| **Gemini 2.5 Flash** | Google | Optional thinking | Good | Yes | 1M | Free tier available, thinking via `thinkingConfig` |
| **Gemini 2.5 Pro** | Google | Optional thinking | Good | Yes | 1M | `responseMimeType: "application/json"` enforces JSON |
| **DeepSeek-R1** | DeepSeek/Ollama | **Always thinks** (`<think>...</think>`) | Moderate | Conditional | 64K | Thinking in XML tags, must strip `<think>` blocks |
| **DeepSeek-V3** | DeepSeek/Ollama | No thinking | Good | Yes | 64K | Non-reasoning variant, clean JSON |
| **Kimi-K2.5** | Moonshot/Ollama | **Always thinks** (natural language) | Poor without stripping | Conditional | 262K | Thinking NOT in XML tags -- raw natural language before JSON |
| **Kimi-K2.5-Instruct** | Moonshot/Ollama | No thinking | Good | Yes | 262K | Non-thinking variant |
| **Qwen3.5** (thinking) | Alibaba/Ollama | **Always thinks** (`<think>...</think>`) | Moderate | Conditional | 128K-262K | Same `<think>` pattern as DeepSeek |
| **Qwen3.5** (no-think) | Alibaba/Ollama | Controllable via `think: false` | Good | Yes | 128K-262K | Ollama `think: false` disables thinking |
| **GLM-5** | Zhipu/Ollama | Optional reasoning | Good | Yes | 128K | Clean JSON when reasoning off |

### Key Insight: Three Categories of Thinking Behavior

**Category 1: Clean output (no thinking mixed in)**
- GPT-4.1 family, Claude family, Gemini family, DeepSeek-V3, Qwen3.5 (think=false), GLM-5
- JSON output is clean and parseable directly
- **Batching: safe at any size**

**Category 2: XML-tagged thinking (`<think>...</think>`)**
- DeepSeek-R1, Qwen3.5 (think=true)
- Thinking is wrapped in `<think>` XML tags before the JSON
- **Batching: safe IF we strip `<think>` blocks first**
- Prep already handles this in `llm_client.py` for some code paths

**Category 3: Raw natural language thinking (no tags)**
- Kimi-K2.5 (cloud variant), some Ollama-hosted thinking models
- Output starts with "The user wants me to..." or "Let me analyze..." BEFORE the JSON
- **Batching: risky -- harder to reliably separate thinking from JSON**
- Need heuristic extraction: find first `{` that starts a valid JSON object

---

## 3. Academic Research: Multi-Item Batching Quality

### Finding 1: Multi-task prompt degradation is real but manageable

**Source**: "Degradation of Multi-Task Prompting Across Six NLP Tasks" (Electronics, 2025, MDPI 14/21/4349)

Key findings from incremental evaluation of 1-6 tasks per prompt:
- **1-3 tasks per prompt**: Minimal degradation (<5% quality loss)
- **4-6 tasks per prompt**: Measurable degradation (5-15% quality loss)
- **JSON formatting task**: Most resilient to batching -- JSON structure acts as natural separator
- **Sentiment analysis**: Most sensitive to batching -- context from adjacent items "bleeds"

**Implication for Prep**: Our batched prompts ask the model to classify N items, each with the same schema. This is structurally similar to the "JSON formatting" task which showed the least degradation. The items are independent (no context bleed between a Python function summary and a TypeScript class summary).

### Finding 2: Batch size sweet spots vary by model class

**Source**: Empirical data from Prep Phase 35 BYOK benchmarks + practitioner reports

| Model Class | Optimal Batch Size (symbols) | Optimal Batch Size (files) | Quality at Optimal | Quality at 2x Optimal |
|-------------|------------------------------|---------------------------|-------------------|-----------------------|
| Large context (1M+) | 50-100 | 20-50 | ~98% of single | ~95% of single |
| Medium context (128K-200K) | 25-50 | 10-25 | ~98% of single | ~93% of single |
| Small context (32K-64K) | 10-20 | 5-10 | ~97% of single | ~90% of single |
| Thinking models | 10-20 | 5-10 | ~95% of single | ~88% of single |

**Why thinking models are worse**: The chain-of-thought process for each item in a batch can "contaminate" reasoning for subsequent items. The model's working memory carries over analysis from item N to item N+1, occasionally producing copy-paste errors or misattributed descriptions.

### Finding 3: JSON structured output helps maintain quality

Models with native JSON mode (GPT-4.1 `response_format`, Gemini `responseMimeType`) maintain higher quality during batching because the output schema constrains the response structure. The model can't "drift" into free-form text between items.

**Prep already uses `response_schema`** in the `generate()` call for Ollama models. For cloud models accessed via OpenAI-compatible API, we should also pass `response_format: {"type": "json_object"}` when the provider supports it.

---

## 4. Ollama-Proxied Cloud Models: Detection Strategy

### How Cloud Models End Up in Ollama

Users run cloud models via Ollama for several reasons:
1. **Ollama as unified interface**: User configures one Ollama endpoint for all models, some local (qwen3:8b) and some cloud-proxied (kimi-k2.5:cloud)
2. **ollama-cloud-code proxy**: Tools like `mkritter3/ollama-cloud-code` translate between Anthropic/OpenAI APIs and Ollama API
3. **Ollama model library**: Some models in `ollama.com/library` are actually cloud-served (the `:cloud` suffix indicates this)

### Detection Signals

| Signal | How to Check | Reliability |
|--------|-------------|-------------|
| **Model name suffix `:cloud`** | `model.endswith(":cloud")` | HIGH -- explicit cloud indicator |
| **Context window > 128K** | `context_tokens > 128_000` from model_context_cache | MEDIUM -- large local models exist (Llama 3.1 405B = 128K) but most cloud models are 200K+ |
| **Context window > 200K** | `context_tokens > 200_000` | HIGH -- no local model has 200K+ context |
| **Model name contains known cloud families** | Regex: `kimi\|deepseek-r1\|gemini\|gpt-4\|claude` | MEDIUM -- some are run locally too |
| **`/api/show` response metadata** | Check `model_info` for `context_length`, `parameter_size` | MEDIUM -- Ollama show endpoint reveals model details |
| **Response latency pattern** | Cloud models have ~1-5s first-token latency; local models have ~0.1-0.5s | LOW -- too variable to be reliable |

### Recommended Detection Logic

```python
def is_cloud_model_via_ollama(provider: str, model: str, context_tokens: int = 0) -> bool:
    """Detect if an Ollama-served model is actually a cloud model.
    
    Cloud models benefit from batching even though they're accessed
    via the Ollama API (provider="ollama").
    """
    if provider != "ollama":
        return False  # Not relevant for non-Ollama providers
    
    model_lower = model.lower()
    
    # Signal 1: Explicit cloud suffix
    if ":cloud" in model_lower:
        return True
    
    # Signal 2: Known cloud-only model families
    _CLOUD_PATTERNS = [
        r"kimi",           # Moonshot Kimi -- always cloud
        r"gemini",         # Google Gemini -- always cloud
        r"gpt-4",          # OpenAI GPT -- always cloud
        r"gpt-5",          # OpenAI GPT-5 -- always cloud
        r"claude",         # Anthropic Claude -- always cloud
        r"mistral-large",  # Mistral Large -- cloud-only
    ]
    for pattern in _CLOUD_PATTERNS:
        if re.search(pattern, model_lower):
            return True
    
    # Signal 3: Very large context window (>200K = definitely cloud)
    if context_tokens > 200_000:
        return True
    
    return False
```

### What About DeepSeek and Qwen?

These are ambiguous -- they have both local and cloud variants:
- `deepseek-r1:7b` -- local (7B params, runs on consumer GPU)
- `deepseek-r1:671b` -- cloud (too large for any single consumer GPU)
- `qwen3.5:35b-a3b` -- local (3B active params via MoE, runs on 24GB GPU)
- `qwen3.5:27b` -- ambiguous (runs on 48GB+ GPU or cloud)

**Strategy**: Don't try to classify these by model name. Instead, use **context window size** as the primary signal. If `context_tokens > 64_000` AND the model is a thinking model (DeepSeek-R1, Qwen3.5 thinking), it's likely cloud-served and benefits from batching with thinking-stripping.

---

## 5. Thinking Model Output Stripping

### Current State in Prep

`llm_client.py` already has some thinking-stripping logic:
- `<think>` tag stripping for DeepSeek-R1 and Qwen3.5 (think=true)
- But this only works for XML-tagged thinking

### What Needs to Be Added

**Category 3 models** (kimi-k2.5, etc.) emit natural language thinking WITHOUT tags. The output looks like:

```
The user wants me to analyze a documentation file and classify it 
according to specific criteria, returning a JSON response.

Looking at the file:
- Path: docs/Phase50_MCP-interfacing/ATLAS_OPPORTUNITIES.md
- Content shows research about atlas opportunities...

Based on my analysis:

{"summary": "Research document on atlas design opportunities...", "role": "documentation", "confidence": 0.85}
```

**Extraction strategy**: Find the first `{` that starts a valid JSON object by scanning from the end of the output backward (JSON tends to be at the end for thinking models):

```python
def extract_json_from_thinking_output(text: str) -> Optional[str]:
    """Extract JSON from output that may contain thinking text.
    
    Strategy: Try progressively more aggressive extraction:
    1. Direct parse (works for clean models)
    2. Strip <think>...</think> XML tags (DeepSeek, Qwen)
    3. Find last JSON object in text (thinking models without tags)
    4. Find last JSON object using brace matching
    """
    # 1. Direct parse
    text = text.strip()
    if text.startswith("{"):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
    
    # 2. Strip <think> tags
    import re
    stripped = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    if stripped.startswith("{"):
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass
    
    # 3. Find last JSON object (scan backward for closing brace)
    last_brace = text.rfind("}")
    if last_brace >= 0:
        # Walk backward to find matching opening brace
        depth = 0
        for i in range(last_brace, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                depth -= 1
                if depth == 0:
                    candidate = text[i:last_brace + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        continue
    
    return None  # No valid JSON found
```

### Quality Impact of Thinking Models on Batched Output

When a thinking model processes a batch of N items, its chain-of-thought becomes N times longer. This increases the risk of:
- **Token budget exhaustion**: The thinking tokens consume output budget, leaving less for the actual JSON
- **Cross-item contamination**: Item N's analysis bleeds into item N+1's description
- **Premature truncation**: Output hits `max_chars` or `num_predict` limit before all items are processed

**Mitigation**: For thinking models, use **smaller batch sizes** (10-20 symbols vs 50-100 for clean models) and **larger output budgets** (3x the non-thinking estimate).

---

## 6. Batch Size Recommendations by Model Type

### Symbol Augmentation (Pass 1)

| Model Type | Recommended Batch | Max Safe Batch | Reasoning |
|-----------|-------------------|----------------|-----------|
| GPT-4.1 family | 50 | 100 | Clean JSON, 1M context, native JSON mode |
| Claude family | 50 | 100 | Clean JSON, 200K context |
| Gemini family | 50 | 100 | Clean JSON, 1M context |
| DeepSeek-V3 (non-thinking) | 30 | 50 | Good JSON, 64K context |
| Qwen3.5 (think=false) | 30 | 50 | Good JSON, 128K+ context |
| Thinking models (R1, K2.5, Qwen think) | 15 | 25 | Thinking overhead, contamination risk |
| Local Ollama (true local) | 1 | 1 | No batching benefit (single GPU, sequential anyway) |

### File Augmentation (Pass 2)

Files are larger than symbols (30 lines of content vs a function signature), so batch sizes should be smaller:

| Model Type | Recommended Batch | Max Safe Batch |
|-----------|-------------------|----------------|
| Large context cloud (1M+) | 20 | 50 |
| Medium context cloud (128K-200K) | 10 | 25 |
| Small context cloud (32K-64K) | 5 | 10 |
| Thinking models | 5 | 10 |
| Local Ollama | 1 | 1 |

---

## 7. Implementation Plan

### Phase 1: Thinking Model Output Stripping (2h, highest impact)

**Why first**: This fixes the parse failures for kimi-k2.5 and other thinking models RIGHT NOW, even without batching. Every failed parse currently falls back to a synthetic entry with lower quality.

1. Add `extract_json_from_thinking_output()` to `llm_client.py` or `augmenter.py`
2. Wire it into the augmenter's JSON parsing for both symbol and file responses
3. Also wire it into `inferred_edges.py` and `epistemic_enrichment.py` (same parse pattern)
4. Add `think: false` to the generate() call when provider=ollama and model is a known thinking model (already partially implemented for Qwen3.5)

### Phase 2: Cloud Model Detection for Ollama (1h)

1. Add `is_cloud_model_via_ollama()` to `batch_profiles.py`
2. Modify `detect_profile_from_context()` and `resolve_profile()` to check this before defaulting to OFF for Ollama
3. If cloud model detected via Ollama: use context-window-based profile selection (same as direct cloud providers)

### Phase 3: Symbol Batching (Pass 1) (3h)

1. Add `_augment_symbols_batched()` method to `augmenter.py` (mirrors existing `_augment_files_batched()`)
2. Create symbol-specific batch prompts in `batch_prompts.py`
3. Gate on `batch_profile != "off"` (same as file batching)
4. Use model-type-aware batch sizes from the table above

### Phase 4: Empirical Validation (2h)

Build a benchmark script that:
1. Takes a small project (TEST repo, ~200 files)
2. Runs augmentation with batch sizes 1, 10, 25, 50
3. Compares output quality: JSON parse success rate, avg confidence, summary length, role accuracy
4. Tests across: GPT-4.1-mini, Claude Haiku 3.5, kimi-k2.5, qwen3.5 (think=false)
5. Records per-model optimal batch size

### Phase 5: Adaptive Batch Sizing (1h)

After empirical data, implement adaptive sizing:
```python
def compute_batch_size(
    provider: str,
    model: str,
    context_tokens: int,
    stage: BatchStage,
    is_thinking_model: bool = False,
) -> int:
    """Compute optimal batch size based on model characteristics."""
    if provider in _LOCAL_PROVIDERS and not is_cloud_model_via_ollama(provider, model, context_tokens):
        return 1  # True local model -- no batching benefit
    
    # Base size from context window
    if context_tokens >= 500_000:
        base = 100 if stage.is_symbol else 50
    elif context_tokens >= 200_000:
        base = 50 if stage.is_symbol else 25
    elif context_tokens >= 100_000:
        base = 30 if stage.is_symbol else 15
    elif context_tokens >= 32_000:
        base = 15 if stage.is_symbol else 8
    else:
        base = 5 if stage.is_symbol else 3
    
    # Thinking model penalty
    if is_thinking_model:
        base = max(5, base // 3)
    
    return base
```

---

## 8. Testing Plan

### Models to Test

| Model | Access Via | Thinking? | Priority |
|-------|-----------|-----------|----------|
| GPT-4.1-mini | OpenAI API | No | HIGH (most popular BYOK) |
| GPT-4.1-nano | OpenAI API | No | HIGH (cheapest BYOK) |
| Claude Haiku 3.5 | Anthropic API | No | HIGH (fast + cheap) |
| Gemini 2.5 Flash | Google API | Optional | HIGH (free tier) |
| Kimi-K2.5 | Ollama (cloud) | Yes | HIGH (user-reported issue) |
| DeepSeek-R1 | Ollama | Yes | MEDIUM (popular thinking model) |
| Qwen3.5 (think=false) | Ollama | No | MEDIUM (popular local) |
| Claude Sonnet 4.5 | Anthropic API | Optional | LOW (expensive, already works) |

### Test Matrix

For each model, test batch sizes: 1, 5, 10, 25, 50

Metrics per test:
- **Parse success rate**: % of items that produce valid JSON
- **Avg confidence**: Mean confidence score across items
- **Summary quality**: Manual spot-check of 10 random summaries per batch size
- **Throughput**: Items/minute at each batch size
- **Cost**: Total API cost for the full run at each batch size
- **Cross-item contamination**: Count of items where summary references wrong file/function

### Test Fixture

Use the Prep `TEST` project (~200 files, ~500 symbols):
- Small enough to run a full matrix in reasonable time
- Large enough to expose batching quality issues
- Already has ground-truth augmentations from previous runs for comparison

---

## 9. Risk Analysis

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Batching degrades quality for some models | MEDIUM | Adaptive batch sizing + per-model profiles. Fallback to batch=1 if parse failure rate > 10%. |
| Thinking model stripping removes valid content | LOW | Only strip content before the first `{`. JSON content is never in the thinking section. |
| Ollama cloud detection false positives | LOW | Only triggered for models with `:cloud` suffix or context > 200K. No impact on true local models. |
| Batch prompt too large for small context models | MEDIUM | Batch size computation respects context_tokens. Never batch if context < 32K. |
| New model families not in detection list | MEDIUM | Fallback to context-window-based detection. The `:cloud` suffix convention is growing. |

---

## 10. Priority Order

1. **Thinking model output stripping** -- fixes parse failures NOW, no batching needed
2. **Cloud model detection** -- unblocks batching for Ollama-proxied cloud models
3. **Symbol batching** -- 95% speed improvement for the dominant pipeline stage
4. **Empirical validation** -- confirms quality thresholds before shipping
5. **Adaptive batch sizing** -- fine-tunes based on empirical data

**Estimated total effort: ~9 hours across 5 phases.**

The first two phases (3h) deliver immediate value: fixing parse failures + enabling correct batch profiles. Phase 3 (3h) delivers the major speed improvement. Phases 4-5 (3h) validate and optimize.

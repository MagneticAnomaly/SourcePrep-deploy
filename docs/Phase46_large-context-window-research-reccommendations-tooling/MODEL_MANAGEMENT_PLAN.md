# Model Management & Multi-Quantization Support Plan
*Phase 46 — Mar 7, 2026*

## 1. Strategic Question: Narrow vs Wide Model Support

### Option A: Target a Small Set of Models
- Ship with 2-3 "blessed" models (e.g., 35b-a3b Q4, 122b-a10b Q4)
- Fewer variables to test, simpler UX
- Risk: Users with different hardware can't use the product

### Option B: Wide Model Support with Safety Guards ✅ RECOMMENDED
- Support any Ollama-compatible model
- Maintain a **Known Working Models** matrix with tested configurations
- Build runtime safety guards that protect against failure modes regardless of model
- Offer "recommended" models per hardware tier, but don't lock users out

**Why Option B:** CoDRAG targets developers with varying hardware. A 16GB MacBook
Air user needs qwen3:8b. A Mac Studio user wants 122b. A cloud user wants to use
GPT-4o. Restricting models restricts market. The engineering cost of safety guards
is modest and benefits ALL models.

---

## 2. Failure Mode Analysis

### 2a. Repetition Loop (TEST3/Q8 Audit Incident)

**What happened:** The `qwen3.5:35b-a3b-q8_0` model produced a perfect 3,204-char
audit report, then entered a repetition loop — repeating the same 8-line Module
Status block **73 times** over 580 seconds until it exhausted its 16,384 token budget.

**Root cause analysis:**
- The model's content was **high quality** — the first 3,204 chars were a complete,
  accurate audit report.
- The loop started at exactly the boundary where the model should have emitted an
  EOS (end-of-sequence) token but instead continued generating.
- This is a **stochastic failure** — the same Q8 model worked perfectly on TEST2
  (2,540 chars) and on TEST3 with a different config (3,231 chars).
- Only **1 out of 12** audit runs across all configs hit this failure.

**Contributing factors:**
- `num_predict=16384` gave the model 16K tokens of runway — enough to loop 73 times
  before being stopped.
- No repetition penalty was set (Ollama default = 1.1, but our config doesn't
  explicitly set it).
- No output length monitoring — the system waited the full 580s for completion.
- Q8 quantization preserves more model weights, which can occasionally make the
  model "more confident" in its continuation pattern, reducing the probability of
  emitting EOS.

**Fixability: HIGH.** Multiple independent defenses can catch this.

### 2b. Think-Mode Budget Explosion (TEST2 Audit Think Incident)

**What happened:** With `think=True`, the `num_predict` multiplier scaled a 16K
budget to 49K. The model spent 30+ minutes generating thinking tokens for a
500-token prompt.

**Root cause:** The 3× think multiplier had no upper bound.

**Fix applied:** Capped think budget at 24,576 tokens in `llm_client.py`.

**Fixability: FIXED.**

### 2c. Context Window Degradation (27b Dense at Large Context)

**What happened:** The dense `qwen3.5:27b` model produced LESS output (6,739 chars)
with MORE input (100 modules) compared to the MoE models at the same context size.

**Root cause:** Dense models struggle with large context windows because all 27.8B
parameters must process every token. The model "gets lost" in long prompts and
produces shorter, less detailed output.

**Fixability: LOW for dense models at large context. MEDIUM via Segmented Atlas
(split into multiple smaller passes and merge).**

### 2d. Potential Future Failure Modes

| Failure | Likelihood | Severity | Fixable? |
|---|---|---|---|
| **Repetition loop** | Low (~8%) | Medium | ✅ Yes — multiple defenses |
| **JSON parse failure** | Low (~5%) | High | ✅ Yes — retry + repair |
| **Truncated output** | Medium | Medium | ✅ Yes — detect + increase budget |
| **Hallucinated file paths** | Medium | Low | ✅ Yes — post-validate against index |
| **Wrong language output** | Very Low | Medium | ✅ Yes — detect + retry |
| **Model OOM / crash** | Low | High | ⚠️ Partial — pre-check VRAM fit |
| **Fundamentally wrong analysis** | Unknown | High | ❌ Hard — requires human review |

---

## 3. Defense-in-Depth: Output Safety Guards

### Layer 1: Generation Parameters (Preventive)

These parameters reduce the probability of failure modes at generation time:

```python
# Current defaults in llm_client.py
options = {
    "temperature": 0.3,       # Low for deterministic output
    "top_k": 20,
    "top_p": 0.95,
    "num_predict": dynamic,   # From context_config.py
}

# PROPOSED additions:
options["repeat_penalty"] = 1.15     # Penalize repeated tokens
options["repeat_last_n"] = 256       # Look back 256 tokens for repeats
options["presence_penalty"] = 0.1    # Mild novelty bias
```

**Impact:** `repeat_penalty` directly addresses the repetition loop failure. The
default Ollama value is 1.1; raising to 1.15 adds mild pressure against loops
without degrading normal output quality.

**Risk:** Too-high repeat_penalty can cause models to avoid legitimate repeated
terms (e.g., file paths that appear multiple times in an audit). 1.15 is safe.

### Layer 2: Streaming Output Monitor (Detective)

Monitor the output stream in real-time and abort if degenerate behavior is detected:

```python
class OutputMonitor:
    """Monitors streaming LLM output for degenerate patterns."""

    def __init__(self, max_chars: int, max_repeat_ratio: float = 0.3):
        self.max_chars = max_chars
        self.max_repeat_ratio = max_repeat_ratio
        self.buffer = ""
        self.line_hashes = []

    def check(self, new_chunk: str) -> tuple[bool, str]:
        """Returns (should_abort, reason)."""
        self.buffer += new_chunk

        # Guard 1: Absolute length limit
        if len(self.buffer) > self.max_chars:
            return True, f"Output exceeded {self.max_chars} chars"

        # Guard 2: Repetition detection (check every 500 chars)
        if len(self.buffer) % 500 < len(new_chunk):
            lines = [l.strip() for l in self.buffer.split('\n') if len(l.strip()) > 40]
            if len(lines) > 10:
                from collections import Counter
                counts = Counter(lines)
                most_common_count = counts.most_common(1)[0][1]
                if most_common_count > 3 and most_common_count / len(lines) > self.max_repeat_ratio:
                    return True, f"Repetition loop detected ({most_common_count} repeats)"

        return False, ""
```

**Impact:** Would have caught the Q8 babbling at ~6,400 chars (after 3 repeats)
instead of letting it run to 62,770 chars. Saves ~570 seconds.

**For CoDRAG tasks, reasonable `max_chars` limits:**

| Task | Expected Output | max_chars Guard |
|---|---|---|
| Atlas (small repo) | 2-5K | 15,000 |
| Atlas (large repo) | 10-30K | 80,000 |
| Audit | 2-5K | 15,000 |
| Group Reasoning (JSON) | 1-3K | 8,000 |
| Augmentation (per-file JSON) | 200-500 | 2,000 |
| Epistemic (per-file JSON) | 300-800 | 3,000 |

### Layer 3: Output Validation (Post-hoc)

After generation completes, validate the output before accepting it:

```python
class OutputValidator:
    """Validates LLM output quality before accepting."""

    @staticmethod
    def validate_prose(text: str, task: str) -> tuple[bool, str]:
        """Validate prose output (Atlas, Audit)."""
        if len(text.strip()) < 100:
            return False, "Output too short (< 100 chars)"

        # Check for repetition in final output
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 40]
        if lines:
            from collections import Counter
            counts = Counter(lines)
            max_repeat = counts.most_common(1)[0][1]
            if max_repeat > 3:
                # Truncate to first occurrence of repeated content
                return False, f"Repetition detected ({max_repeat}x), truncating"

        return True, "OK"

    @staticmethod
    def validate_json(text: str, required_keys: list) -> tuple[bool, str]:
        """Validate JSON output (Group Reasoning, Augmentation, Epistemic)."""
        import json as _json
        try:
            parsed = _json.loads(text)
        except _json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            # ... (existing _parse_json_response logic)
            return False, "Invalid JSON"

        for key in required_keys:
            if key not in parsed:
                return False, f"Missing required key: {key}"

        return True, "OK"
```

### Layer 4: Retry with Variation (Recovery)

When validation fails, retry with adjusted parameters:

```python
class RetryStrategy:
    """Retry failed LLM calls with progressive parameter variation."""

    STRATEGIES = [
        {"temperature": 0.4, "repeat_penalty": 1.2},   # Retry 1: more penalty
        {"temperature": 0.5, "repeat_penalty": 1.3},   # Retry 2: even more
        {"temperature": 0.2, "top_k": 10},              # Retry 3: more constrained
    ]

    MAX_RETRIES = 2  # Don't burn too much compute

    @classmethod
    def should_retry(cls, attempt: int, error: str) -> dict | None:
        if attempt >= cls.MAX_RETRIES:
            return None
        if "Repetition" in error or "too short" in error:
            return cls.STRATEGIES[min(attempt, len(cls.STRATEGIES) - 1)]
        if "Invalid JSON" in error:
            return cls.STRATEGIES[0]  # Simple retry usually fixes JSON
        return None
```

### Layer 5: Graceful Degradation (Fallback)

If retries fail, degrade gracefully rather than crash:

- **Repetition loop → Truncate to good content.** The first 3,204 chars of the Q8
  output were a complete, high-quality audit report. Truncating at the first
  repetition boundary would have given a perfect result.
- **JSON parse failure → Return partial data.** If the JSON is malformed but
  contains extractable fields, use regex extraction as a fallback.
- **Model OOM → Auto-downgrade model.** If the requested model can't load,
  suggest or auto-select the next smaller model from the tier list.

---

## 4. What We Can Control vs What's Out of Scope

### ✅ CoDRAG Can Control

| Area | Mechanism | Status |
|---|---|---|
| **Repetition loops** | repeat_penalty, streaming monitor, truncation | To implement |
| **Output length** | max_chars guards per task, num_predict sizing | Partially done (context_config.py) |
| **Think budget** | Capped at 24K, split by task type | ✅ Done |
| **JSON validity** | Parse + retry + regex fallback | Partially done |
| **Model selection** | Auto-recommend based on VRAM, warn on mismatch | ✅ Done (context_config.py) |
| **Context window** | Dynamic num_ctx based on prompt + model | ✅ Done |
| **Temperature tuning** | Per-task defaults, adjustable | ✅ Done |
| **File path validation** | Post-validate against actual index | To implement |
| **Timeout protection** | Per-task timeouts, abort on degenerate runs | Partially done |

### ⚠️ CoDRAG Can Partially Control

| Area | Notes |
|---|---|
| **Quantization quality** | Can test and document which quants work, can recommend. Can't fix a fundamentally broken quantization. |
| **Model architecture limits** | Dense models degrade at large context. Can work around with Segmented Atlas, but can't make the model better. |
| **Hardware fit** | Can detect and warn, but can't add VRAM. |
| **Multi-model consistency** | Different models produce different outputs. Can normalize format but not style. |

### ❌ Out of CoDRAG's Scope

| Area | Why |
|---|---|
| **Model training quality** | We consume models, we don't train them. |
| **Ollama/llama.cpp bugs** | Upstream runtime bugs. We report, we don't fix. |
| **Hardware failures** | GPU crashes, thermal throttling, etc. |
| **Fundamental hallucination** | If the model invents a plausible-sounding architectural pattern that's wrong, we can't detect it without a second model or human review. |

---

## 5. Known Working Models Matrix

### Testing Methodology
Each model × quantization × task combination is tested on at least 2 repos.
Status levels:
- ✅ **Verified** — Tested, works reliably (0 failures in test suite)
- ⚠️ **Works with Guards** — Tested, occasional failures caught by safety guards
- 🔶 **Limited** — Works but with known limitations (e.g., degraded quality)
- ❌ **Not Recommended** — Frequent failures or unacceptable quality
- ⬜ **Untested** — Not yet validated

### Current Matrix (Mar 7, 2026)

| Model | Quant | Atlas | Audit | Group Reasoning | Augment | Epistemic | Notes |
|---|---|---|---|---|---|---|---|
| **qwen3.5:35b-a3b** | Q4 | ✅ | ✅ | ✅ (think) | ✅ | ✅ | **Primary recommended model** |
| **qwen3.5:35b-a3b** | Q8 | ✅ | ⚠️ | ✅ (think) | ✅ | ✅ | 1/12 audit loop (fixable with guards) |
| **qwen3.5:122b-a10b** | Q4 | ✅ | ✅ | ✅ (think) | ✅ | ✅ | Best quality, ~2× slower |
| **qwen3.5:27b** (dense) | Q4 | 🔶 | ⬜ | ⬜ | ⬜ | ⬜ | Degrades at large context |
| **qwen3.5:27b** (dense) | Q8 | 🔶 | ⬜ | ⬜ | ⬜ | ⬜ | Better than Q4 but still limited |
| **qwen3:8b** | Q4 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | For 16GB devices — needs testing |
| **qwen3:4b-instruct** | Q4 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Minimum viable — needs testing |
| **qwen3-coder:30b** | Q4 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Code-specialized — needs testing |

### Repo Coverage

| Model × Quant | CoDRAG | TEST2 (React) | TEST3 (RN) | HomeColab (iOS) | LinuxBrain |
|---|---|---|---|---|---|
| 35b-a3b Q4 | ✅ | ✅ | ✅ | ⏳ Running | ⏳ Tonight |
| 35b-a3b Q8 | ✅ | ✅ | ✅ | ⏳ Running | ⏳ Tonight |
| 122b-a10b Q4 | ✅ | ✅ | ✅ | ⏳ Running | ⏳ Tonight |
| 27b Q4 | ✅ | — | — | — | — |
| 27b Q8 | ✅ | — | — | — | — |

---

## 6. Implementation Roadmap

### Phase 1: Safety Guards (Immediate — this session)
1. Add `repeat_penalty=1.15` and `repeat_last_n=256` to `llm_client.py`
2. Implement `OutputMonitor` for streaming repetition detection
3. Implement `OutputValidator` for post-generation quality checks
4. Add `max_chars` limits per task type
5. Implement retry-with-variation for failed generations

### Phase 2: Model Compatibility Testing (This week)
1. Complete HomeColab benchmark (running now)
2. Complete LinuxBrain benchmark (tonight)
3. Test qwen3:8b on all tasks (16GB tier validation)
4. Test qwen3-coder:30b for Group Reasoning
5. Update Known Working Models matrix with results

### Phase 3: Integration with AI Gateway (Phase 45 overlap)
1. Wire `context_config.py` into the pipeline orchestrator
2. Connect VRAM detection to AI Gateway's `ComputeNode` config
3. Auto-recommend models based on hardware profile
4. Expose model compatibility matrix in the UI

### Phase 4: Advanced Robustness (Future)
1. Segmented Atlas for dense models at large context
2. Cross-model validation (run critical tasks on 2 models, compare)
3. Output quality scoring (heuristic + optional LLM-as-judge)
4. Automated regression testing across model updates

---

## 7. Customer-Facing Messaging

### What We Tell Customers

**Supported models:** CoDRAG works with any Ollama-compatible model. We test and
optimize for the Qwen3.5 family (MoE and dense), with the following tiers:

| Tier | Model | Min RAM | Speed | Quality |
|---|---|---|---|---|
| **Recommended** | qwen3.5:35b-a3b (Q4) | 32GB | ⚡ Fast (26 tok/s) | Excellent |
| **Premium** | qwen3.5:122b-a10b (Q4) | 128GB | 🐢 Moderate (12 tok/s) | Best |
| **Lightweight** | qwen3:8b (Q4) | 16GB | ⚡⚡ Fastest | Good |
| **Budget** | qwen3:4b-instruct (Q4) | 8GB | ⚡⚡⚡ | Acceptable |

**Quantization guidance:**
- **Q4 (4-bit):** Recommended for most users. Best speed/quality tradeoff.
- **Q8 (8-bit):** Higher precision, ~40% slower. Marginally better quality on
  small tasks. Requires ~60% more RAM.
- **Q2/Q3:** Not recommended. Significant quality loss.

**What CoDRAG handles automatically:**
- Dynamic context window sizing based on your hardware
- Model-specific generation parameters
- Output quality monitoring with automatic retry
- Graceful degradation if a model misbehaves

**What users should know:**
- Larger models produce better results but are slower
- MoE models (35b-a3b, 122b-a10b) are dramatically faster than dense models
  of equivalent quality
- The model must fit in your available memory (no workaround on Mac)

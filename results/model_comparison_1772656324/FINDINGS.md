# Model Comparison: qwen3.5-9b vs qwen3-14b vs qwen3.5-27b

**Date:** 2026-03-04  
**Repo:** mini-redis-rust (real-world Tokio Redis implementation)  
**Hardware:** Apple Silicon (MLX backend via LM Studio)  
**Models:** `qwen3.5-9b` (dense 9B) · `qwen/qwen3-14b` (dense 14B) · `qwen3.5-27b-mxfp8` (dense 27B)

## Critical Finding: Thinking Token Waste

**ALL three models are "thinking" models.** They generate `<think>...</think>` blocks before producing useful JSON output. This cannot be disabled via LM Studio — tested `/no_think` suffix, `chat_template_kwargs`, and strong system prompts. All failed.

### Token waste on a trivial JSON task (fn add):

| Model | Time | Total tokens | Useful JSON tokens | **Think waste** |
|-------|------|-------------|-------------------|-----------------|
| qwen3.5-9b | 36s | 341 | ~15 | **96%** |
| qwen3-14b | 35s | 348 | ~15 | **96%** |
| qwen3.5-27b | 103s | 1,633 | ~15 | **99%** |

The 27b generates **5× more thinking tokens** than the 9b/14b for identical output.

## Speed Results

### Run 2: 3-model comparison (5 files, max_tokens=4096)

| Metric | qwen3.5-9b | qwen3-14b | qwen3.5-27b |
|--------|------------|-----------|-------------|
| **Augment total** | 594s | **127s** | >250s/file* |
| **Augment per file** | 118.9s | **25.4s** | >250s* |
| **Augment tok/s** | 28.0 | 23.1 | 16 |
| **Augment parse rate** | 60% | **100%** | FAIL* |
| **Epistemic total** | 328s | **34s** | ~1,238s† |
| **Epistemic per file** | 65.6s | **6.8s** | ~124s† |
| **Epistemic tok/s** | 26.4 | 20.6 | 15.6† |
| **Epistemic parse rate** | **100%** | **100%** | 70%† |

*27b killed after first file (250s, still failed parse at 4096 tokens)  
†27b epistemic from Run 1 (10 files, max_tokens=2048)

### Run 1: 14b vs 27b (10 files, max_tokens=1024/2048)

| Metric | qwen3-14b | qwen3.5-27b | Ratio |
|--------|-----------|-------------|-------|
| Augment total | 182s | 677s | 3.7× slower |
| Epistemic total | 82s | 1,238s | **15× slower** |
| Epistemic per file | 8.2s | 123.8s | **15× slower** |

### Why is the 9b slower than the 14b?

Despite being a smaller model, the 9b generates at **28 tok/s** (faster than 14b's 23 tok/s) but produces **~4,000 thinking tokens** per response vs the 14b's ~400. The 9b "over-thinks" — its thinking blocks are 10× larger than the 14b's, more than canceling out the tok/s advantage.

### Why is epistemic 15× slower on the 27b (not just 3.7×)?

The tok/s gap is only 1.5×, but the 27b generates **far more tokens** per response. For epistemic: ~2,000 tokens (27b) vs ~150 (14b). Combined: slower generation × more tokens = 15× wall time.

## Quality Results (from Run 1, 10 files)

### Epistemic Enrichment (Pass 2) — where 27b succeeded

| Metric | qwen3-14b | qwen3.5-27b |
|--------|-----------|-------------|
| JSON parse rate | **100%** | 70% |
| Avg confidence | 0.85 | **0.92** |
| Avg summary length | 335 chars | **419 chars** |
| Unique domain tags | **25** | 19 |

### Per-File Epistemic Comparison (14b vs 27b)

| File | 14b conf | 27b conf | 14b layer | 27b layer |
|------|----------|----------|-----------|-----------|
| examples/chat.rs | 0.85 | 0.85 | presentation | documentation |
| examples/hello_world.rs | 0.85 | **0.95** | testing | documentation |
| examples/pub.rs | 0.85 | **0.95** | business_logic | documentation |
| examples/sub.rs | 0.85 | **0.95** | business_logic | documentation |
| src/bin/cli.rs | 0.85 | **0.92** | presentation | presentation |
| src/bin/server.rs | 0.85 | FAIL | infrastructure | — |
| src/clients/blocking_client.rs | 0.85 | **0.90** | infrastructure | infrastructure |
| src/clients/buffered_client.rs | 0.85 | FAIL | infrastructure | — |
| src/clients/client.rs | 0.85 | FAIL | infrastructure | — |
| src/clients/mod.rs | 0.85 | **0.92** | infrastructure | infrastructure |

### Quality Observations

1. **14b always assigns 0.85 confidence** — it doesn't differentiate between files. The 27b varies (0.85–0.95), showing more nuanced self-assessment.
2. **27b classifies examples as "documentation"** — arguably more accurate (they're runnable docs, not business logic).
3. **14b generates more diverse tags** (25 unique vs 19) — more granular but possibly noisier.
4. **27b writes longer, more detailed summaries** (419 vs 335 chars) with better technical accuracy.
5. **27b has 30% JSON parse failure** even at 2048 max_tokens — thinking blocks consume the token budget.
6. **9b quality is comparable to 14b** on epistemic (100% parse, similar summaries) but 40% augmentation failure.

## Disabling Thinking — Not Possible via LM Studio

Tested three approaches on qwen3.5-27b-mxfp8:

| Approach | Result |
|----------|--------|
| `/no_think` suffix in user message | Still thinks (wrapped in `<think>` tags) |
| `chat_template_kwargs: {enable_thinking: false}` | Still thinks (ignored) |
| Strong system prompt: "Do NOT think. Output ONLY JSON." | Still thinks |

**Root cause:** Thinking behavior is controlled by the Jinja chat template's `enable_thinking` parameter. LM Studio's MLX engine doesn't expose this parameter — it always renders the template with thinking enabled.

**Workaround options:**
- Use a non-thinking model variant (e.g., `qwen3.5-27b-text` if available as a text-only fine-tune)
- Use Ollama instead of LM Studio (llama.cpp may handle the template parameter differently)
- Strip `<think>` tags from output and increase max_tokens to 8192+ to ensure JSON survives

## Root Cause: Why the Smoke Test Took 1 Hour

The rust_repo smoke test (5 files, 21 nodes) took ~1 hour because:

1. **Deepening Loop**: 10 iterations × 21 nodes × 27b model (~120s per enrichment call)
2. **Poor convergence**: Symbol nodes (16/21) had 0% neighbor_coverage because `compute_epistemic_score()` counted all neighbors including symbols, but only files get enriched. **Fixed:** now only counts `file:` neighbors.
3. **Thinking token waste**: 27b generates ~2,000 tokens per response, of which ~50 are useful JSON. At 15 tok/s, that's 133s per call to get 50 useful tokens.

## Recommendations

### For the CoDRAG pipeline:

1. **Use qwen3-14b as default for ALL pipeline passes on Apple Silicon** — it's the fastest by a wide margin (6.8s/file epistemic vs 65.6s for 9b and 124s for 27b)
2. **Increase max_tokens to 8192** for all thinking models — even 4096 fails on complex files
3. **Cap Deepening Loop iterations for small repos** — `max_iterations = min(10, max(3, file_count // 5))`
4. **The neighbor_coverage fix is critical** — will dramatically reduce deepening iterations
5. **Consider Ollama for thinking control** — llama.cpp may properly support `enable_thinking: false`

### Model selection guidance:

| Scenario | Recommended |
|----------|-------------|
| **Local Apple Silicon, all passes** | **qwen3-14b** — 5-15× faster than alternatives |
| Local, ultra-fast (quality ok) | qwen3-4b |
| Cloud API, deep enrichment | qwen3.5-27b — speed is server-limited, quality is better |
| Budget/time constrained | qwen3-14b for everything |

### Model characteristics (dense, all thinking):

| Model | Params | Architecture | tok/s (MLX) | Think verbosity | Parse reliability |
|-------|--------|--------------|-------------|-----------------|-------------------|
| qwen3.5-9b | 9B dense | qwen3.5 | 28 | **VERY HIGH** (4K tokens) | 60-100% |
| qwen3-14b | 14B dense | qwen3 | 23 | LOW (~400 tokens) | **90-100%** |
| qwen3.5-27b | 27B dense | qwen3.5 | 16 | **EXTREME** (1.6K-4K+) | 10-70% |

**Key insight:** The qwen3.5 architecture (9b and 27b) thinks far more verbosely than qwen3 (14b). This is NOT a size effect — it's an architecture/training difference. The qwen3-14b is the sweet spot for structured JSON output tasks.

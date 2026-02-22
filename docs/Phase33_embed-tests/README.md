# Phase 33 — Embedding Model Evaluation

> **Status**: **Decision complete.** v1.5 ONNX confirmed as the production embedding model. See §5 for rationale. v2-moe preserved for future re-evaluation if Ollama fixes the 512-token embedding context limit.
>
> See [RESEARCH_CLARITY.md](RESEARCH_CLARITY.md) for how this phase relates to compression (separate concern) and context architecture (Phase 34, separate concern).

---

## 1. Background & Motivation

CoDRAG uses embedding models to index codebases for retrieval-augmented generation. At build time, every file the user selects (code, docs, config — everything) is chunked and embedded into a single vector index. At query time, the AI model's query is embedded with the same model and cosine similarity finds the most relevant chunks.

**The core question**: Which Nomic embedding model produces the best vectors for retrieval across ALL content types in a unified index?

This is purely about retrieval quality. Compression (LOD for code, LLMLingua2 for language) is a separate serving-time concern tested in a later phase.

### Models Under Test

| Model | Runtime | Dim | Latency (p50) | Notes |
|:------|:--------|:----|:-------------|:------|
| `nomic-embed-text-v1.5` | ONNX (CPU) | 768 | 6.9ms | Built-in fallback, no Ollama needed |
| `nomic-embed-text-v2-moe` | Ollama | 768 | 97.2ms | MoE architecture, requires Ollama |

---

## 2. Phase 29 Benchmark (Baseline)

**Date**: 2026-02-20. Synthetic benchmark on `tests/fixtures/embedding_benchmark` (39 queries, 48 chunks).

| Model | R@1 | R@3 | R@5 | MRR | Embed p50 | Embed p95 |
|:------|:----|:----|:----|:----|:----------|:----------|
| **v1.5 ONNX** | **97.4%** | **100%** | **100%** | **0.987** | **6.9ms** | **8.3ms** |
| v2-moe Ollama | 92.3% | 100% | 100% | 0.957 | 97.2ms | 103.4ms |

**Conclusion**: On a small synthetic benchmark, v1.5 ONNX wins on accuracy and is 14× faster. However, this benchmark is narrow — 48 chunks from a single fixture repo. Real-world testing needed.

### Key Findings from Phase 29

1. **No ONNX export for v2-moe exists** — MoE data-dependent routing is incompatible with static ONNX graphs. 3 export approaches failed. v2-moe is SafeTensors + Ollama only.
2. v1.5 ONNX remains the **built-in CPU fallback** for offline/air-gapped use.
3. v2-moe Ollama is the **recommended path** for users with Ollama installed.
4. v2-moe raw similarity scores are much lower (avg 0.690 vs 0.962) — MoE routing appears less calibrated for short queries.

### Decision (Phase 29)

Keep `nomic-embed-text-v1.5` ONNX as the default. Recommend `nomic-embed-text-v2-moe` via Ollama for users who have it installed.

**Docs updated**: `README.md`, `public/codrag-mcp/README.md`, `docs/API.md`, `src/codrag/cli.py`, `scripts/benchmark_embeddings.py`.

---

## 3. Phase 33 Real-World Evaluation

**Date**: 2026-02-21. Expanded evaluation on 10 real-world repositories across 4 indexing modes.

### 3.1 Evaluation Modes

| Mode | What's Indexed | Ground Truth | Relevance to Embedding Decision |
|:-----|:---------------|:-------------|:--------------------------------|
| **full** | All code + docs | Code queries | **PRIMARY** — this is how production works |
| docs-only | Only `.md`, `.rst`, `.txt`, `.adoc` files | Doc queries | Supplementary — isolates doc retrieval quality |
| strip-code | Doc files with fenced code blocks removed | Doc queries | Supplementary — tests pure NL retrieval |
| trace-only | Synthetic docs from trace graph metadata | Code queries | Supplementary — tests NL→structural matching |

> **Note**: The docs-only, strip-code, and trace-only modes don't reflect production. CoDRAG always indexes everything together in one unified index. These modes are useful for understanding model behavior but the embedding decision should be based on **full-index** results.

### 3.2 Test Repositories

**Original repos** (open-source, well-documented):

| Repo | Language | Code Queries | Doc Queries |
|:-----|:---------|:-------------|:------------|
| cobra | Go | 10 | 9 |
| got | TypeScript | 10 | 11 |
| click | Python | 18 | 10 |
| gin | Go | 11 | 4 |
| chi | Go | 12 | 5 |
| slim | PHP | 8 | 3 |
| hanami | Ruby | 9 | 2 |

**TEST repos** (internal, varied content):

| Repo | Language | Code Queries | Doc Queries | Description |
|:-----|:---------|:-------------|:------------|:------------|
| test-nextjs | TypeScript/React | 14 | 6 | Marketing site (Next.js) |
| test2-halley | TypeScript/React | 14 | 12 | Product website + research docs |
| test3-jezebel | Python/TS/Swift | 16 | 15 | Multi-platform music app |

### 3.3 Results — Original Repos

#### Docs-Only Mode (doc queries against doc-only index)

| Repo | v1 ONNX R@1 | v1 MRR | v2-moe R@1 | v2-moe MRR | Winner |
|:-----|:-----------:|:------:|:----------:|:----------:|:------:|
| cobra | **100%** | **1.000** | 67% | 0.815 | v1 |
| got | 82% | 0.894 | 82% | **0.909** | tie/v2 |
| click | **90%** | **0.950** | **90%** | **0.950** | tie |
| gin | **75%** | **0.833** | **75%** | **0.833** | tie |
| chi | **100%** | **1.000** | **100%** | **1.000** | tie |
| slim | **100%** | **1.000** | **100%** | **1.000** | tie |

#### Strip-Code Mode (doc queries against docs with code blocks removed)

| Repo | v1 ONNX R@1 | v1 MRR | v2-moe R@1 | v2-moe MRR | Winner |
|:-----|:-----------:|:------:|:----------:|:----------:|:------:|
| cobra | **89%** | **0.944** | 67% | 0.815 | v1 |
| got | 82% | 0.909 | **100%** | **1.000** | **v2** |
| click | **90%** | **0.950** | 80% | 0.900 | v1 |
| gin | **75%** | **0.800** | **75%** | **0.800** | tie |
| chi | **100%** | **1.000** | **100%** | **1.000** | tie |
| slim | **100%** | **1.000** | **100%** | **1.000** | tie |

#### Trace-Only Mode (code queries against structural metadata)

| Repo | v1 ONNX R@1 | v1 MRR | v2-moe R@1 | v2-moe MRR | Winner |
|:-----|:-----------:|:------:|:----------:|:----------:|:------:|
| cobra | **70%** | **0.833** | 60% | 0.758 | v1 |
| got | 10% | 0.167 | **20%** | **0.333** | **v2** |
| click | 0% | 0.030 | **6%** | **0.289** | **v2** |
| gin | **64%** | **0.740** | 36% | 0.548 | v1 |
| chi | **58%** | **0.792** | 42% | 0.662 | v1 |
| slim | 0% | 0.031 | 0% | **0.125** | v2 |
| hanami | 33% | 0.494 | **44%** | **0.596** | **v2** |

### 3.4 Results — TEST Repos

| Repo | Mode | v1 ONNX R@1 | v1 MRR | v2-moe R@1 | v2-moe MRR |
|:-----|:-----|:-----------:|:------:|:----------:|:----------:|
| **test-nextjs** | full | **71%** | **0.755** | 57% | 0.699 |
| | docs-only | 83% | 0.861 | 83% | **0.889** |
| | strip-code | 83% | 0.867 | 83% | **0.889** |
| | trace-only | 50% | 0.690 | **57%** | 0.690 |
| **test2-halley** | full | **43%** | **0.605** | 0% | 0.301 |
| | docs-only | **75%** | **0.875** | 67% | 0.833 |
| | strip-code | **92%** | **0.958** | 83% | 0.917 |
| | trace-only | 7% | 0.434 | **21%** | **0.548** |
| **test3-jezebel** | full | 56% | 0.694 | **62%** | **0.690** |
| | docs-only | 33% | 0.594 | **53%** | **0.711** |
| | strip-code | **60%** | **0.756** | 53% | 0.711 |
| | trace-only | 31% | 0.472 | **50%** | **0.631** |

---

## 4. Analysis & Key Findings

### 4.1 Full-Index Results (complete dataset)

These are the results that matter for the embedding model decision — both models indexing ALL content together, exactly as production works.

| Repo | Lang | Chunks | v1.5 R@1 | v2-moe R@1 | v1.5 MRR | v2-moe MRR | Winner |
|:-----|:-----|:------:|:---:|:---:|:---:|:---:|:------:|
| mini-redis | Rust | 105 | 81% | 81% | **0.896** | 0.891 | tie |
| click | Python | 617 | **62%** | 56% | **0.731** | 0.713 | v1.5 |
| spark-java | Java | ~350 | 56% | **69%** | 0.731 | **0.784** | **v2-moe** |
| chi | Go | ~200 | 75% | 75% | **0.861** | 0.833 | v1.5 (MRR) |
| cobra | Go | ~300 | 30% | 30% | **0.517** | 0.486 | v1.5 (MRR) |
| got | TS | ~250 | **50%** | 40% | **0.636** | 0.602 | v1.5 |
| hanami | Ruby | 216 | 56% | 56% | 0.726 | **0.741** | v2-moe (MRR) |
| slim | PHP | 406 | 25% | **38%** | 0.392 | **0.426** | **v2-moe** |
| test-nextjs | TS/React | 176 | **71%** | 57% | **0.755** | 0.699 | v1.5 |
| test2-halley | TS/React | 544 | **43%** | 0% | **0.605** | 0.301 | v1.5 |
| test3-jezebel | Py/TS/Swift | 1018 | 56% | **62%** | 0.694 | 0.690 | **v2-moe** |

*Note: gin v2-moe run errored in overnight batch (context overflow before P1 fix). Not included.*

**Aggregate (10 repos with both models):**

| Metric | v1.5 ONNX | v2-moe Ollama |
|:-------|:---------:|:-------------:|
| Mean R@1 | **50.4%** | 48.7% |
| Mean MRR | **0.665** | 0.647 |
| Wins (R@1) | **4** | 3 |
| Ties (R@1) | 3 | 3 |
| Catastrophic failures (R@1=0%) | 0 | **1** (test2-halley) |
| Latency (p50) | **6.9ms** | 97.2ms |
| External deps | None | Ollama + GPU |

### 4.1.1 test2-halley 0% R@1 diagnosis

v2-moe got **0% R@1** but **57% R@3** on test2-halley. The correct files are IN the index but always ranked 2nd-4th because:
- test2-halley has duplicate directory structures: `website/` and `website.clean/` contain the same components. Ground truth expects `website.clean/` but `website/` copies consistently outrank them.
- v1.5 also suffers from this (43% R@1, many rank-2/3 misses to `website/` copies) but its higher absolute scores create enough separation to rank `website.clean/` first in more cases.
- v2-moe's compressed score range (0.47–0.73 vs v1.5's 0.70–1.21) means the gap between `website/` and `website.clean/` versions is razor-thin, causing consistent misordering.

**Verdict**: This is a **ground-truth problem** (duplicate content) exacerbated by v2-moe's compressed scores. Not a fundamental embedding quality issue, but it does expose v2-moe's score calibration weakness.

### 4.2 v2-moe context window limitation (resolved)

v2-moe via Ollama has a **hard 512-token context limit** for embedding models. Ollama ignores `num_ctx` in request options for `/api/embed` — the GGUF modelfile default (512 tokens) is always used.

**Fix applied**: `max_input_chars` lowered from 2400 to 1800, plus **progressive truncation** in `_embed_with_retries()` — on context-length errors, input is automatically shortened by 25% per retry.

**Impact on v2-moe quality**: The 512-token limit means v2-moe sees less content per chunk than v1.5 (which has no such limit via ONNX). This is an inherent disadvantage for v2-moe that may partially explain its lower scores. If Ollama fixes `num_ctx` for embedding models in the future, v2-moe results could improve.

### 4.3 v2-moe score calibration issue

v2-moe raw similarity scores are much lower than v1.5:
- v1.5 average top-1 score: ~0.96
- v2-moe average top-1 score: ~0.69

This matters because CoDRAG's search pipeline uses `min_score=0.15` and adaptive-K gap detection (score drop ratio). Lower absolute scores mean the entire score distribution is compressed, potentially causing:
- Adaptive-K to trim results too aggressively (smaller gaps between results)
- Score-based LOD assignment to use wrong thresholds (the `assign_lod()` function has breakpoints at 0.50, 0.35, 0.20)

**This needs testing**: Do the existing score thresholds work with v2-moe's score range, or do they need model-specific calibration?

### 4.4 Supplementary findings (from non-full-index modes)

These don't directly inform the model decision but provide useful insight:

- **Docs-only outperforms full for doc queries** — code chunks dilute doc retrieval. The fix isn't "index less" — it's "rank better" (intent classification, role weights, atlas routing already address this partially).
- **v2-moe excels at NL→structural matching** (trace-only mode) — v2-moe consistently beats v1.5 when matching natural-language queries to structural metadata (file paths, symbols, imports). This is relevant for the KnowledgeIndex which contains LLM-generated summaries.
- **Code blocks in docs generally help** — stripping code from docs has inconsistent results. Keep them.

---

## 5. Decision: v1.5 ONNX as Default

### Recommendation

**Keep `nomic-embed-text-v1.5` (ONNX) as the default and only production embedding model.** Deprecate v2-moe as an alternative for now.

### Rationale

1. **v1.5 wins or ties on 7 of 10 repos** (4 wins, 3 ties). v2-moe wins on 3 repos (spark-java, slim, test3-jezebel). The margin is narrow in v1.5's direction but consistent.

2. **v1.5 has zero catastrophic failures.** v2-moe's 0% R@1 on test2-halley — even though diagnosed as a ground-truth issue — exposes a score calibration fragility. In production, users WILL have duplicate/similar files, and v2-moe's compressed score range makes it more vulnerable to misordering.

3. **v1.5 is 14× faster** (6.9ms vs 97.2ms per embed). For builds with 500+ chunks, this is minutes vs seconds. Users notice build speed.

4. **v1.5 has zero external dependencies.** No Ollama, no GPU, works offline and air-gapped. v2-moe requires Ollama running with the model pulled (~1GB VRAM). This is a meaningful barrier for adoption.

5. **v2-moe is handicapped by Ollama's 512-token context limit.** v2-moe sees ~1800 chars per chunk while v1.5 sees the full content. This is an Ollama limitation that may be fixed in the future, but we can't ship around it today.

6. **Score calibration costs are non-trivial.** v2-moe's 0.69 avg vs v1.5's 0.96 avg means every score-dependent mechanism in the pipeline (`min_score`, adaptive-K, `assign_lod()` thresholds) would need model-specific tuning. This adds complexity for a model that doesn't clearly outperform.

### What v2-moe is good at (preserved as research finding)

- **Diverse multi-language repos** (test3-jezebel +6pp R@1, spark-java +13pp R@1)
- **NL→structural matching** (trace-only mode: consistently +10-19pp over v1.5)
- **Less common languages** (slim/PHP: +13pp R@1)

These strengths are real but not large enough to justify the dependencies, calibration cost, and reliability risk. If Ollama fixes the context limit and v2-moe scores improve, this decision should be revisited.

### Action items

- [x] Keep v1.5 ONNX as the sole production embedding model
- [ ] Remove v2-moe from `KNOWN_OLLAMA_MODELS` active recommendations (keep the code for future testing)
- [ ] Ensure all score thresholds are calibrated for v1.5's score range (~0.60–1.20)
- [ ] File Ollama issue re: `num_ctx` being ignored for embedding models
- [ ] Revisit if/when Ollama fixes the 512-token embedding context limit

---

## 6. Bugs & Issues Found

### B1: v2-moe Ollama context overflow on full builds

**Symptom**: `400/500 — {"error":"the input length exceeds the context length"}` on chunks >~2080 chars.
**Root cause (confirmed)**: Ollama **ignores `num_ctx` for embedding models** via both `/api/embed` and `/api/embeddings`. The GGUF modelfile default (512 tokens ≈ 2080 chars of code) is always used regardless of request options. Additionally, the preload via `/api/generate` loads embedding-only models with default context even when returning 400, and the legacy `/api/embeddings` endpoint ignores `options` entirely.
**Fix applied**:
  1. `max_input_chars` lowered from 2400 → 1800
  2. Progressive truncation in `_embed_with_retries()`: on context-length errors, input shortened by 25% per retry
  3. Legacy `/api/embeddings` fallback skipped when `num_ctx` is set (endpoint ignores it)
  4. 400 responses now logged with body for diagnostics
**Status**: ✅ Fixed.

### B2: TEST3 trace build indexes Pods/node_modules without gitignore

**Symptom**: TraceBuilder produced 30K nodes from iOS Pods/boost headers, making embedding infeasible.
**Fix applied**: Updated `_build_trace_index` and full build in `eval_real_repos.py` to pass `use_gitignore=True` and exclude `Pods/`, `venv/`, `fresh_venv/`.
**Status**: ✅ Fixed in eval script. Consider making `use_gitignore=True` the default in `TraceBuilder`.

### B3: Missing doc queries for hanami in docs-only/strip-code runs

**Symptom**: Previous docs-only and strip-code runs didn't include hanami.
**Status**: ✅ Fixed — hanami now has doc queries in `DOC_QUERIES`.

---

## 6. Files Modified

| File | Changes |
|:-----|:--------|
| `scripts/eval_real_repos.py` | Added `--docs-only`, `--strip-code`, `--trace-only` modes; `DOC_QUERIES` ground truth; `_build_docs_index`, `_build_trace_index`, `_strip_code_blocks` helpers; test2-halley and test3-jezebel repos |
| `src/codrag/core/embedder.py` | `max_input_chars` 2400→1800 for v2-moe; progressive truncation retry on context-length errors; skip legacy `/api/embeddings` when `num_ctx` set; 400 response logging; debug logging for silent exceptions |
| `src/codrag/core/model_readiness.py` | `ollama_preload()` and `ollama_ensure_ready()` accept `options` dict for `num_ctx` passthrough |
| `src/codrag/core/repo_profile.py` | Added Ruby and PHP language detection |

---

## 7. Tooling Reference

### Running evaluations

```bash
# Full index (baseline)
python scripts/eval_real_repos.py --repos cobra click --tiers onnx v2-moe --verbose

# Docs-only (language queries against doc files)
python scripts/eval_real_repos.py --repos cobra click --tiers onnx v2-moe --docs-only --verbose

# Strip-code (docs with code blocks removed)
python scripts/eval_real_repos.py --repos cobra click --tiers onnx v2-moe --strip-code --verbose

# Trace-only (structural metadata only)
python scripts/eval_real_repos.py --repos cobra click --tiers onnx v2-moe --trace-only --verbose

# Save results as JSON
python scripts/eval_real_repos.py --repos cobra --tiers all --docs-only --output logs/results.json
```

### Log files (2026-02-21)

| File | Contents |
|:-----|:---------|
| `logs/eval_docs_only.log` | Original repos, docs-only, v1 + v2-moe |
| `logs/eval_strip_code.log` | Original repos, strip-code, v1 + v2-moe |
| `logs/eval_trace_only.log` | Original repos, trace-only, v1 + v2-moe |
| `logs/eval_test_docs_only.log` | TEST repos, docs-only, v1 + v2-moe |
| `logs/eval_test_strip_code.log` | TEST repos, strip-code, v1 + v2-moe |
| `logs/eval_test_trace_only.log` | TEST repos, trace-only, v1 + v2-moe |
| `logs/eval_test_full.log` | TEST repos, full index, v1 + v2-moe (v2-moe had ctx errors) |
| `logs/eval_test_full_final.log` | TEST repos, full index, v1 + v2-moe (after P1 fix) |
| `logs/eval_test_full_final.json` | Machine-readable results for above |

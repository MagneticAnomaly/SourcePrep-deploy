# Phase 28 — Context Window Improvements: TODO & Implementation Strategy

> Based on the research in CONTEXT_VOLUME_RESEARCH.md and self-assessment in PROBLEMS_AND_IMPROVEMENTS.md.

---

## Implementation Waves

The improvements are grouped into 3 waves based on effort, impact, and dependencies.

### Wave 1: Quick Wins (search quality)
Low effort, high impact. All changes are in `index.py` search/context assembly. No new dependencies, no API changes.

### Wave 2: Trace Quality + MCP API
Medium effort. Improves trace expansion (our key differentiator) and adds an MCP parameter. Touches `index.py` and `mcp_tools.py`.

### Wave 3: Embedding Upgrade + Future
Larger effort. Requires benchmarking, potential model swap, and infrastructure work.

---

## Wave 1: Search Quality

### 1.1 — Adaptive K (score gap detection) ✅ DONE
- **Problem:** Fixed K=5 sends low-relevance padding when only 2 chunks truly match.
- **Status:** ✅ Implemented — `_adaptive_k_trim()` in `index.py`, 10 tests in `test_adaptive_k.py`
- **File:** `src/codrag/core/index.py` → `search()` (~line 890)
- **Approach:** After sorting by score, compute deltas between consecutive results. If delta > `score_drop_ratio * top_score`, stop. This is the "Adaptive-K" technique from EMNLP 2025 ("No Tuning, No Iteration, Just Adaptive-k").
- **Algorithm:**
  ```
  scores = [0.85, 0.82, 0.79, 0.31, 0.28]
  deltas = [0.03, 0.03, 0.48, 0.03]
  max_delta at index 2 → gap between 0.79 and 0.31
  If 0.48 > 0.4 * 0.85 (= 0.34): cut after index 2 → return 3 results
  ```
- **Default:** `score_drop_ratio=0.4` (configurable). When the gap between consecutive scores exceeds 40% of the top score, stop.
- **Fallback:** Always return at least 1 result. If no significant gap, return all K.
- **Tests:** Add `test_adaptive_k.py` — verify gap detection, verify fallback to full K, verify min 1 result.
- **Risk:** Low. Purely additive — when all scores are close, behavior is identical to current.

### 1.2 — Raise min_score Default
- **Problem:** `min_score=0.15` is very permissive. Cosine 0.15 with nomic-embed-text is barely related.
- **Status:** 🔬 Test file written — run with NativeEmbedder to get real data
- **File:** `src/codrag/core/index.py`, `src/codrag/mcp_tools.py`, `src/codrag/api/routers/projects.py`
- **Approach:** Raise default from `0.15` to `0.25`. One-line change in each file.
- **Research command:**
  ```bash
  pytest tests/test_min_score_threshold.py -v
  # (requires NativeEmbedder deps: pip install onnxruntime tokenizers huggingface-hub)
  ```
- **Tests check:** ground-truth files score > 0.15, majority > 0.25, raising threshold doesn't lose top-1 results
- **Risk:** Could break sparse indexes where all scores are low. Mitigate by combining with adaptive K (1.1) — if adaptive K cuts early anyway, the floor matters less.

### 1.3 — Result Diversity (MMR) ✅ DONE
- **Problem:** No deduplication. Two chunks from the same function can both rank in top-K.
- **Status:** ✅ Implemented — `_mmr_rerank()` in `index.py`, 10 tests in `test_mmr_diversity.py`
- **File:** `src/codrag/core/index.py` → new `_mmr_rerank()` method, called from `search()`
- **Approach:** Maximal Marginal Relevance. After computing scores, select results greedily:
  ```
  selected = [highest_scoring_doc]
  for each remaining candidate:
      mmr_score = λ * relevance(candidate) - (1-λ) * max_similarity(candidate, selected)
      pick candidate with highest mmr_score
  ```
- **λ:** Default `0.7` (favor relevance over diversity). Configurable.
- **Implementation detail:** Pairwise similarity between candidates uses the already-computed embeddings (`self._embeddings`). No extra embedding calls needed — just index into the matrix.
- **Perf cost:** For K=5 from a candidate pool of ~20 (top_idx), this is ~100 cosine similarity ops. Negligible.
- **Tests:** Add test cases: (a) two near-identical chunks from same file → only one selected, (b) diverse chunks → all preserved, (c) λ=1.0 → identical to current behavior.
- **Risk:** Low. λ=1.0 is a no-op escape hatch.

---

## Wave 2: Trace Quality + MCP API

### 2.1 — Ranked Trace Expansion ✅ DONE
- **Problem:** Trace neighbors are sorted alphabetically, not by query relevance. A utility file imported everywhere can beat a directly-relevant caller.
- **Status:** ✅ Implemented — single-pass scoring in `get_context_with_trace_expansion()`, 4 tests in `test_trace_expansion_ranking.py`
- **File:** `src/codrag/core/index.py` → `get_context_with_trace_expansion()` (~line 1143)
- **Approach:** After collecting `related_paths`, score each neighbor's chunks against the query embedding and select the highest-scoring ones.
  ```
  # Current: for rp in sorted(related_paths)
  # New:     score each related_path's chunks against query, sort by score desc
  ```
- **Implementation:**
  1. Collect all candidate chunks from `related_paths`
  2. Compute cosine similarity of each candidate's embedding against the query vector
  3. Sort by similarity descending
  4. Fill the `max_additional_chars` budget from highest-scoring candidates first
- **Perf cost:** Requires the query embedding (already computed in `search()`) to be passed through. Need to refactor slightly — `get_context_with_trace_expansion()` should accept `query_vector` or re-embed.
- **Tests:** Test that trace expansion returns the most relevant neighbor, not the alphabetically first one. Mock trace index with known structure.
- **Risk:** Low-Medium. Refactoring to pass query embedding is the main complexity.

### 2.2 — Smart Chunk Selection for Trace ✅ DONE
- **Problem:** When a trace neighbor file is found, CoDRAG grabs the first chunk (often imports/boilerplate), not the best chunk.
- **Status:** ✅ Implemented — `path_best` dict tracks (best_score, best_doc) per file, 3 tests in `test_trace_expansion_ranking.py`
- **File:** Same as 2.1
- **Approach:** Instead of `break` after first chunk per file, collect ALL chunks for each neighbor file, score them against the query, and pick the best one.
  ```
  # Current: takes first chunk matching source_path, breaks
  # New:     collects all chunks for source_path, picks highest query similarity
  ```
- **Dependencies:** Builds on 2.1 (same scoring infrastructure).
- **Risk:** Low. Just removes a premature `break`.

### 2.3 — `exclude_paths` MCP Parameter ✅ DONE
- **Problem:** CoDRAG doesn't know what files the AI tool already has in context. Could send redundant chunks.
- **Status:** ✅ Implemented — `search()`, `SearchRequest`, `ContextRequest`, `mcp_tools.py`, `mcp_server.py` dispatch, 7 tests in `test_exclude_paths.py`
- **Files:** `src/codrag/mcp_tools.py` (schema), `src/codrag/mcp_server.py` (handler), `src/codrag/api/routers/projects.py` (API), `src/codrag/core/index.py` (search filter)
- **Approach:** Add `exclude_paths: string[]` param to the `codrag` and `codrag_search` tools. Before scoring, filter out documents whose `source_path` matches any excluded path.
- **Schema addition:**
  ```json
  "exclude_paths": {
      "type": "array",
      "items": {"type": "string"},
      "description": "File paths already in your context. CoDRAG will exclude these from results to avoid redundancy.",
      "default": []
  }
  ```
- **Tests:** Verify excluded files don't appear in results. Verify empty exclude_paths = current behavior.
- **Risk:** Very low. Additive parameter with empty default.

### 2.4 — Hub-File Filtering for Trace
- **Problem:** Files imported by everything (e.g., `__init__.py`, `utils.py`) aren't specifically relevant but appear as trace neighbors for every match.
- **Status:** 🔬 Needs research — what's the right threshold?
- **File:** `src/codrag/core/index.py` → `get_context_with_trace_expansion()`
- **Approach:** Count how many of the source_paths each neighbor appears as a neighbor of. If it's a neighbor of ALL source_paths (or >80%), it's a hub — skip it or deprioritize it.
- **Research needed:** 🔬 Analyze trace graphs from real projects. What's the distribution of neighbor fanout? Is `__init__.py` always a hub? Are there legitimate high-connectivity files?
- **Risk:** Medium. Overly aggressive filtering could remove genuinely important structural nodes.

---

## Wave 3: Embedding Upgrade + Future

### 3.1 — Benchmark Code Embedding Models ✅ COMPLETE
- **Problem:** nomic-embed-text-v1.5 is general-purpose, not code-specialized.
- **Status:** ✅ Done — see `EMBEDDING_MODEL_RESEARCH.md` for full results
- **Deliverables:**
  - `docs/Phase28_ContextWindowResearch/EMBEDDING_MODEL_RESEARCH.md` — full research + results
  - `scripts/benchmark_embeddings.py` — reusable benchmark script
  - `tests/fixtures/embedding_benchmark/` — 10-file fixture with 15 ground-truth queries
- **Benchmark results (15 queries, 18 chunks):**
  | Model | R@1 | MRR | Latency |
  |---|---|---|---|
  | **CodeRankEmbed** (137M, code) | **100%** | **1.000** | 118ms (PyTorch) |
  | nomic-embed-text-v1.5 (current) | 93.3% | 0.956 | 7ms (ONNX) |
  | nomic-embed-text (Ollama) | 93.3% | 0.967 | 20ms |
  | Jina Code V2 | — | — | BROKEN (transformers 5.x incompatible) |
- **Winner: CodeRankEmbed** — same architecture (nomic_bert, 137M, 768 dim, Apache 2.0). Drop-in upgrade. Needs ONNX export.

### 3.2 — Embedding Model Swap to CodeRankEmbed
- **Status:** Unblocked — benchmark confirms CodeRankEmbed wins
- **File:** `src/codrag/core/embedder.py` → `NativeEmbedder`
- **Steps:**
  1. Export CodeRankEmbed to ONNX via `optimum` and quantize
  2. Update `NativeEmbedder.HF_REPO_ID` to `nomic-ai/CodeRankEmbed`
  3. Change `query_prefix` to `"Represent this query for searching relevant code: "`
  4. Change `document_prefix` to `""` (CodeRankEmbed embeds code without prefix)
  5. Add model version check — detect mismatch and prompt rebuild
- **Migration concern:** Changing the embedding model invalidates all existing indexes. Users must rebuild. Auto-detect via stored model name in index metadata.
- **Effort:** Medium.

### 3.3 — Intent Detection Improvement
- **Problem:** Keyword-based intent classification is brittle.
- **Status:** 🔬 Low priority — current multiplier spread is narrow enough that misclassification rarely matters
- **Approach:** Multi-label scoring instead of first-match. Count overlap with each category, pick highest.
- **Dependency:** Only matters if we widen role weight spread (item 3.4).
- **Effort:** Low.

### 3.4 — Widen Role Weight Spread
- **Problem:** Max swing is ~25%. Too narrow to meaningfully change results.
- **Status:** Blocked on 3.3 (intent detection accuracy)
- **Approach:** When intent is "code", set docs multiplier to 0.7 instead of 0.93. When intent is "tests", set code multiplier to 0.85 instead of 1.0.
- **Risk:** Wider spread + bad intent detection = worse results. Fix 3.3 first.
- **Effort:** Trivial constant change.

### 3.5 — Score-Based Compression
- **Problem:** CLaRa compresses the entire context uniformly.
- **Status:** Later — requires per-chunk compression calls
- **Approach:** High-score chunks (>0.7) → no compression. Mid-score (0.4–0.7) → light compression. Low-score (<0.4) → aggressive compression or one-line summary.
- **Effort:** Medium-High.

### 3.6 — Feedback Loop (long-term)
- **Problem:** No way to know if context was useful.
- **Status:** Long-term infrastructure
- **Approaches:**
  - `codrag_feedback` MCP tool for explicit thumbs up/down
  - Implicit signal: if same query is repeated with higher K, first result was insufficient
  - Track if files in CoDRAG results appear in the AI tool's subsequent edits
- **Effort:** High.

---

## Deferred (not worth doing now)

| Item | Why deferred |
|---|---|
| **Position optimization** (best at start, 2nd-best at end) | Negligible at 1,500-token context sizes. Only matters at >10K. |
| **Token-based budget** (vs character-based) | `// 4` approximation is close enough at current small budgets. |
| **Redundancy with native tool indexing** | Documentation issue, not a code change. Addressed in FAQ.md. |

---

## Implementation Order

```
Wave 1 (search quality):
  ┌─ 1.1 Adaptive K ✅ DONE
  ├─ 1.2 Test min_score (pending research)
  └─ 1.3 MMR diversity ✅ DONE

Wave 2 (trace quality):
  ┌─ 2.1 Ranked trace expansion ✅ DONE
  ├─ 2.2 Smart chunk selection ✅ DONE
  ├─ 2.3 exclude_paths param ✅ DONE
  └─ 2.4 Hub-file filtering (needs research)

Wave 3 (3.1 done, 3.2 unblocked, 3.3 → 3.4):
  ┌─ 3.1 Benchmark embedding models ✅ DONE (CodeRankEmbed wins)
  ├─ 3.2 Model swap to CodeRankEmbed (unblocked)
  ├─ 3.3 Intent detection improvement
  ├─ 3.4 Widen role weights (blocked on 3.3)
  ├─ 3.5 Score-based compression
  └─ 3.6 Feedback loop (long-term)
```

### Estimated effort per wave

| Wave | Items | Est. Lines Changed | Est. Time |
|---|---|---|---|
| Wave 1 | 1.1, 1.2, 1.3 | ~80–120 in index.py + tests | 1–2 sessions |
| Wave 2 | 2.1, 2.2, 2.3, 2.4 | ~150–250 across index.py, mcp_tools.py, mcp_server.py + tests | 2–3 sessions |
| Wave 3 | 3.1–3.6 | Variable — 3.1 is a script, 3.2 is ~100 lines, 3.6 is new infrastructure | 4+ sessions |

---

## Test Strategy

Each item gets regression tests in `tests/`:

| Item | Test file | Status | What it verifies |
|---|---|---|---|
| 1.1 Adaptive K | `test_adaptive_k.py` | ✅ 10 pass | Gap detection, fallback, edge cases |
| 1.2 min_score | `test_min_score_threshold.py` | 🔬 Run with NativeEmbedder | GT files score > 0.15/0.25, threshold raise doesn't lose top-1, score distribution |
| 1.3 MMR | `test_mmr_diversity.py` | ✅ 10 pass | Dedup, diversity, λ=1.0 no-op, integration |
| 2.1/2.2 Trace ranking | `test_trace_expansion_ranking.py` | ✅ 7 pass | Relevance sort, best chunk, fallback, budget |
| 2.3 exclude_paths | `test_exclude_paths.py` | ✅ 7 pass | Excluded absent, empty=no-op, multi-exclude, rank promotion |
| 3.1 Benchmark | `scripts/benchmark_embeddings.py` | ✅ Three-tier run complete (2026-02-19) | Full accuracy + latency comparison |
| Problem #3 Score calibration | `test_score_calibration.py` | ✅ 8 pass, 1 skip | Scores bounded, ordered, min_score filter, k limit, adaptive k, MMR, distractor |
| Problem #5 Intent detection | `test_intent_detection.py` | ✅ 18 pass, 3 xfail | Classification accuracy; xfail = known gaps ('implement', 'assert', 'how does X work') |

### Three-tier embedding benchmark commands

Run once you have both Ollama models pulled (`manutic/nomic-embed-code` and `nomic-embed-text`):

```bash
# Side-by-side: ONNX CPU vs nomic-embed-text (Ollama) vs nomic-embed-code (Ollama)
python scripts/benchmark_embeddings.py --three-tiers

# Save results for documentation
python scripts/benchmark_embeddings.py --three-tiers --output docs/Phase28_ContextWindowResearch/three_tier_results.json

# Individual model
python scripts/benchmark_embeddings.py --models nomic-code-ollama
python scripts/benchmark_embeddings.py --models nomic-text-ollama

# Custom Ollama model (e.g., official nomic-embed-code if/when released)
python scripts/benchmark_embeddings.py --ollama nomic-embed-code
```

Output includes per-model: R@1, R@3, R@5, MRR, avg top-1 score, embed p50/p95/p99, search p50/p95/p99.

### Quality analysis tests requiring NativeEmbedder

These skip with FakeEmbedder (used in CI). Run locally with the full deps installed:

```bash
pip install onnxruntime tokenizers huggingface-hub
pytest tests/test_min_score_threshold.py -v          # Wave 1.2 decision data
pytest tests/test_score_calibration.py -v             # Score sanity (1 skip becomes pass)
pytest tests/test_intent_detection.py -v              # Intent gaps (3 xfail = known Problem #5 gaps)
```

When xfail tests flip to xpass after fixing Problem #5, the `strict=True` ones will enforce the improvement is real.

---

*See also: [PROBLEMS_AND_IMPROVEMENTS.md](./PROBLEMS_AND_IMPROVEMENTS.md) for detailed analysis of each problem.*
*See also: [FAQ.md](./FAQ.md) for the user-facing questions this work addresses.*
*See also: [CONTEXT_VOLUME_RESEARCH.md](./CONTEXT_VOLUME_RESEARCH.md) for the academic research backing.*

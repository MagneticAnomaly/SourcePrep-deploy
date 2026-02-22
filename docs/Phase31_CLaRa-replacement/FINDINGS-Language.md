# Phase 31B: CLaRa Language-Only Compression — Findings

> **Test Date**: 2026-02-20
> **Hypothesis**: CLaRa might work on CoDRAG's natural language content (augmentation summaries, epistemic enrichments, docs, atlas) even though it failed on code.
> **Result**: ❌ Language content does NOT rescue CLaRa. 20% overall retention (worse than code's 29%).

---

## Test Setup

6 scenarios with realistic CoDRAG pipeline output, all **pure natural language**:

| Scenario | Content Types | Memories | Input Chars |
|----------|--------------|----------|-------------|
| augmentations_only | Augmentation summaries (10) | 10 | 2,935 |
| epistemic_only | Epistemic enrichments (5) | 5 | 2,074 |
| modules_only | Module descriptions (4) | 4 | 1,310 |
| docs_only | User markdown docs (4) | 4 | 2,883 |
| mixed_language_full | All 5 types mixed (14) | 14 | 6,029 |
| atlas_routing | Atlas + augmentation + epistemic (6) | 6 | 2,175 |

---

## Results

### Per-Scenario

| Scenario | Output | Ratio | Facts | File Refs | Concepts | Overall | Latency |
|----------|--------|-------|-------|-----------|----------|---------|---------|
| augmentations_only | 1,964 | 1.5× | 0/7 (0%) | 0/4 (0%) | 2/5 (40%) | 12% | 45.6s |
| epistemic_only | 1,304 | 1.6× | 1/6 (17%) | 0/4 (0%) | 3/7 (43%) | 24% | 23.2s |
| modules_only | 831 | 1.6× | 0/4 (0%) | 1/5 (20%) | 4/8 (50%) | 29% | 16.5s |
| docs_only | 1,635 | 1.8× | 0/10 (0%) | 0/3 (0%) | 3/8 (38%) | 14% | 30.9s |
| mixed_language_full | 2,189 | 2.8× | 0/9 (0%) | 1/4 (25%) | 3/9 (33%) | 18% | 47.9s |
| atlas_routing | 752 | 2.9× | 1/5 (20%) | 0/2 (0%) | 2/5 (40%) | 25% | 17.9s |

### Language vs Code Comparison

| Metric | Code (Phase B) | Language (31B) | Delta |
|--------|---------------|----------------|-------|
| **Overall retention** | 29% | **20%** | −9% |
| **File/path refs** | 0% | **8%** | +8% |
| **Key facts** | 19% | **9%** | −10% |
| **Concepts** | N/A | **38%** | new |
| **Hallucinations** | 4.0 avg | **0.7 avg** | −3.3 ✅ |
| **Compression ratio** | 3.4× | **2.0×** | lower |
| **Latency (MPS)** | 19.5s | **30.3s** | +10.8s |

### Decision Gates

| Gate | Criteria | Result | Verdict |
|------|----------|--------|---------|
| Overall retention ≥60% | — | 20% | ❌ FAIL |
| File refs ≥50% | — | 8% | ❌ FAIL |
| Concepts ≥70% | — | 38% | ❌ FAIL |
| Hallucinations <3 avg | — | 0.7 | ✅ PASS |

**3 of 4 gates failed. Language content does not rescue CLaRa.**

---

## Key Observations

1. **Language retention is WORSE than code (20% vs 29%).** CLaRa generates generic prose rather than preserving specific facts from the input memories.

2. **Hallucinations dropped significantly (4.0 → 0.7).** Language content is more "normal" for the Mistral-7B base model. But it still fabricated:
   - "CoDRA (CoDEbase for Reverse-engineering and Analysis)" — invented acronym
   - `core.py`, `query.py`, `ranking.py` — invented file paths
   - "atlasis" — garbled term

3. **Concept-level understanding is moderate (38%).** CLaRa captures high-level themes (search, indexing, pipeline, trace) but drops every specific detail — file names, numbers, config parameters, proper nouns.

4. **The model answers questions, it doesn't compress.** Output previews confirm: CLaRa treats memories as background context and generates a free-form QA answer. It's not distilling — it's generating from priors with light grounding.

5. **Specific facts score 0–17%.** Terms like "cosine similarity", "adaptive-K", "nomic-embed-text", "MMR", "8-stage pipeline" — almost none survive. These are exactly the details a developer needs.

---

## Root Cause (Refined)

The issue is **not** content type. The issue is that `CLaRa-7B-Instruct` is a **question-answering model**, not a **compression/summarization model**.

| What CLaRa does | What CoDRAG needs |
|----------------|-------------------|
| Takes memories + question → generates a free-form answer | Takes memories + question → generates a **faithful distillation** |
| Optimized for 64–128 token QA responses | Needs 500–2000 token detail-preserving summaries |
| Draws on Mistral-7B base knowledge | Must use ONLY the provided memories |
| Treats specific terms as interchangeable | Must preserve exact names, paths, values |

---

## Updated Compression Strategy

### What We Learned

| Content type | CLaRa works? | Why / Why not |
|-------------|-------------|---------------|
| Code | ❌ (29%) | Generates prose, drops file paths and signatures |
| Documentation | ❌ (14%) | Generates generic answers, drops specific details |
| Augmentation summaries | ❌ (12%) | Same — QA model ignores specifics |
| Epistemic enrichments | ❌ (24%) | Best of the bunch but still way below threshold |
| Module descriptions | ⚠️ (29%) | Moderate concept retention, but facts still lost |
| Atlas segments | ❌ (25%) | Hallucinates terminology ("atlasis") |

### Next Candidates

| Approach | Type | Preserves Details? | Hallucination Risk | Speed | Effort |
|----------|------|-------------------|-------------------|-------|--------|
| **LLMLingua-2** | Token pruning | ✅ Yes (original text) | Zero | Fast (~50ms) | Low |
| **Extractive** | AST + heuristic | ✅ Yes (signatures kept) | Zero | Instant | Low |
| **Code LLM summary** | Generation | Likely good | Medium | ~1–5s | Medium |
| **CLaRa** | QA generation | ❌ No (20–29%) | Low | 20–45s | Done |

**Recommendation: LLMLingua-2** is the strongest next candidate because:
- Prunes tokens by importance (small classifier, ~350M params)
- Original text preserved exactly — no hallucination possible
- Up to 20× compression with <2% quality loss on benchmarks
- Fast inference (~50ms on CPU)
- Works on both code AND language (it just removes less-important tokens)

---

## Raw Data

- Results: `docs/Phase31_CLaRa-tests/language_results.json`
- Script: `scripts/clara_language_test.py`
- Comparison baseline: `docs/Phase31_CLaRa-tests/quality_512tokens.json` (Phase B code results)

---

*Written: 2026-02-20. Phase 31B — Language-only CLaRa testing.*

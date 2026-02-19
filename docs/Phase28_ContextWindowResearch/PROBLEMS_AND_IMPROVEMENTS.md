# CoDRAG — Problems & Improvement Opportunities

> A critical self-assessment based on the context window research in this phase. What's working, what's weak, and what could be better.

---

## Table of Contents

1. [No Result Diversity / Deduplication](#1-no-result-diversity--deduplication)
2. [Fixed K Regardless of Match Quality](#2-fixed-k-regardless-of-match-quality)
3. [Low min_score Default Invites Distractors](#3-low-min_score-default-invites-distractors)
4. [Trace Expansion Is Unranked](#4-trace-expansion-is-unranked)
5. [Intent Detection Is Keyword-Based](#5-intent-detection-is-keyword-based)
6. [Character Budget ≠ Token Budget](#6-character-budget--token-budget)
7. [No Awareness of What the AI Tool Already Has](#7-no-awareness-of-what-the-ai-tool-already-has)
8. [Compression Is All-or-Nothing](#8-compression-is-all-or-nothing)
9. [No Feedback Loop](#9-no-feedback-loop)
10. [Embedding Model Is Not Code-Specialized](#10-embedding-model-is-not-code-specialized)
11. [Trace Expansion Picks First Chunk Per File](#11-trace-expansion-picks-first-chunk-per-file)
12. [Role Weight Spread Is Too Narrow](#12-role-weight-spread-is-too-narrow)
13. [No Position Optimization](#13-no-position-optimization)
14. [Potential Redundancy With Native Tool Indexing](#14-potential-redundancy-with-native-tool-indexing)
15. [Summary Table](#summary-table)

---

## 1. No Result Diversity / Deduplication ✅ DONE

**Problem:** If a function appears in multiple chunks (e.g., its definition and a test that includes it), both can rank highly and consume budget on redundant information. There's no deduplication or diversity check in `search()`.

**What the research says:** Chroma Research (2025) showed that semantically similar distractors are the most damaging type of noise. Redundant chunks from the same file or about the same symbol are essentially self-inflicted distractors.

**Where in code:** `index.py` `search()` (line ~890) — results are sorted by score and returned. No check for overlapping `source_path` or content similarity between results.

**Possible fix:**
- **MMR (Maximal Marginal Relevance):** After scoring, penalize chunks that are too similar to already-selected chunks. Standard technique in RAG.
- **File-level dedup:** If two chunks from the same file rank in top-K, keep only the highest-scoring one (or merge them).
- **Content hash dedup:** Skip chunks whose content is >80% identical to an already-selected chunk.

**Effort:** Medium. MMR requires computing pairwise similarity on top-K candidates. File-level dedup is a few lines.

**Impact:** Moderate. Prevents wasting 2 of 5 slots on near-identical content.

---

## 2. Fixed K Regardless of Match Quality ✅ DONE

**Problem:** If you ask a query that only has 2 genuinely relevant matches but K=5, the other 3 chunks are padding — effectively distractors. The current logic takes all K results as long as they pass `min_score`.

**What the research says:** Chen et al. (2025) showed that even irrelevant whitespace degrades reasoning. Chroma (2025) showed distractors compound non-linearly. Sending 3 low-relevance chunks alongside 2 high-relevance ones could actively hurt.

**Where in code:** `index.py` `search()` (line ~892–898) — the loop fills up to K results above min_score. There's no score gap detection or diminishing-returns cutoff.

**Possible fix:**
- **Score gap detection:** If the score drops by >50% between consecutive results, stop early. E.g., scores [0.85, 0.82, 0.31, 0.28, 0.25] → stop after 2.
- **Adaptive K:** Return min(K, number of results above a dynamic threshold like `max_score * 0.5`).
- **Confidence-based cutoff:** If the top result is 0.9 and the 4th result is 0.2, the 4th result isn't adding value.

**Effort:** Low. A few lines in the search loop.

**Impact:** High. This directly addresses the core research finding: less noise = better reasoning.

---

## 3. Low min_score Default Invites Distractors 🔬 TESTING

**Status:** Test file written (`test_min_score_threshold.py`, 6 tests). Needs NativeEmbedder run for final decision.

**Problem:** `min_score=0.15` is very permissive. Cosine similarity of 0.15 with nomic-embed-text means the chunk is barely related to the query. These are exactly the kind of low-relevance results that research identifies as harmful.

**What the research says:** Databricks (2024) found that adding more retrieved documents beyond the saturation point hurts. Low-scoring documents are the ones that push you past that point.

**Where in code:** `index.py` `search()` default, `mcp_tools.py` default, `ContextRequest` model default.

**Possible fix:**
- Raise default to `0.25` or `0.30`. Users can always lower it.
- Or combine with adaptive K (item #2) so the floor matters less.

**Effort:** Trivial — one-line default change. But needs testing to ensure it doesn't break projects with sparse indexes.

**Impact:** Moderate. Prevents low-quality chunks from consuming budget slots.

---

## 4. Trace Expansion Is Unranked ✅ DONE

**Problem:** `get_context_with_trace_expansion()` follows graph edges from matched files and adds neighbors — but it doesn't rank those neighbors by relevance to the query. Neighbors are sorted alphabetically by path (`sorted(related_paths)`) and the first chunk per file is taken. A utility file imported by everything could be selected over a directly-relevant caller.

**What the research says:** Han et al. (2025) found that even local GraphRAG can underperform flat RAG if the graph retrieval isn't filtered well. The value of graph expansion depends on the quality of what's expanded.

**Where in code:** `index.py` `get_context_with_trace_expansion()` (line ~1143) — `for rp in sorted(related_paths)` iterates alphabetically. No scoring against the query.

**Possible fix:**
- **Re-rank trace neighbors:** After collecting related_paths, compute embedding similarity of each neighbor's content against the query. Sort by that score.
- **Edge-type prioritization:** Weight `calls` edges higher than `imports` edges when the query is about behavior (not structure).
- **Frequency filtering:** If a file is a neighbor of ALL source_paths (e.g., `__init__.py`, `utils.py`), it's probably not specifically relevant.

**Effort:** Medium. Requires embedding lookup for trace candidates.

**Impact:** High. This is the difference between trace expansion being genuinely useful vs. adding noise.

---

## 5. Intent Detection Is Keyword-Based 🔬 1 GAP REMAINING

**Status:** 13 pass, 1 xfail (`test_intent_detection.py`). Fixed: added 'implement', 'assert', 'explain', 'overview', 'purpose', 'mock', 'fixture', 'debug', etc. Remaining gap: 'how does X work' (needs semantic classification).

**Problem:** `_classify_query_intent()` uses simple token set intersection. "How do I fix the error handler?" matches both `debug_tokens` ("fix", "error") and `code_tokens` ("handler"). The current logic checks `tests_tokens` first, then `docs_tokens`, then `debug_tokens`, then `code_tokens` — so priority order is implicit and sometimes wrong.

**What the research says:** Intent-aware retrieval is a real differentiator (this is something competitors don't do), but it needs to actually work. A misclassified intent boosts the wrong content types.

**Where in code:** `index.py` `_classify_query_intent()` (line ~675–752). Returns the first matching category. The multipliers are narrow (1.08–1.15) so misclassification impact is small currently — but if we widen them, this matters more.

**Possible fix:**
- **Multi-label scoring:** Instead of first-match, count token overlap with each category and pick the highest.
- **LLM-based classification:** For Pro users, use a lightweight model to classify intent. Overkill for now.
- **Phrase patterns:** "fix the bug" and "error in the handler" have different intents but both match debug tokens. Bigram/trigram matching would help.

**Effort:** Low-Medium. Multi-label scoring is straightforward.

**Impact:** Low currently (multipliers are narrow). Higher if we ever widen the multiplier spread.

---

## 6. Character Budget ≠ Token Budget

**Problem:** CoDRAG budgets in characters (`max_chars=6000`), but LLMs consume tokens. The `estimated_tokens = total // 4` approximation is rough. Code has different token density than prose — a Python file with short variable names tokenizes differently than a documentation paragraph.

**What the research says:** The saturation points from Databricks are measured in tokens, not characters. A 6000-char code block could be 1,200 or 2,000 tokens depending on content.

**Where in code:** `index.py` `get_context_structured()` (line ~1065) — `"estimated_tokens": total // 4`. Also `max_chars` is the hard ceiling everywhere.

**Possible fix:**
- **Add token counting.** Use `tiktoken` (for OpenAI models) or a generic tokenizer to count actual tokens. Expose both `max_chars` and `max_tokens` parameters.
- **Or:** Accept that `// 4` is close enough for CoDRAG's small budgets. The error matters less when you're at 1,500 tokens than when you're at 50,000.

**Effort:** Low (add tiktoken) to Medium (support dual budgets).

**Impact:** Low for current defaults. More important if users increase budgets significantly.

---

## 7. No Awareness of What the AI Tool Already Has ✅ DONE

**Problem:** CoDRAG doesn't know what the AI tool already has in its context. If the user @-referenced `auth.py` and then CoDRAG also returns chunks from `auth.py`, that's redundant context — wasted tokens that research says degrade performance.

**What the research says:** Every redundant token is a distractor. The research doesn't distinguish between "irrelevant" and "already present" — both dilute the signal.

**Where in code:** The MCP protocol doesn't provide a mechanism for the AI tool to tell CoDRAG "I already have these files in context." CoDRAG's `tool_context()` has no `exclude_paths` parameter.

**Possible fix:**
- **Add `exclude_paths` parameter** to `codrag` tool: let the AI tool pass in files it already has. Simple, backwards-compatible.
- **MCP context hints:** Future MCP spec versions might support this natively. For now, a tool parameter is sufficient.
- **Conversation-aware caching:** Track which files CoDRAG has already served in this session. Diminish their scores on repeat queries. Heavier lift.

**Effort:** Low (exclude_paths param). Medium (session awareness).

**Impact:** Moderate. Prevents the most obvious source of redundancy.

---

## 8. Compression Is All-or-Nothing

**Problem:** CLaRa compression applies uniformly to the entire assembled context. A high-relevance chunk (score 0.9) gets the same compression as a borderline chunk (score 0.2). The high-relevance chunk should arguably be preserved verbatim while the low-relevance chunk should be compressed aggressively or dropped.

**What the research says:** "Retrieve then Solve" (Chen et al., 2025) works because it shortens the prompt. But the research doesn't say "compress everything equally" — it says "extract the evidence." High-confidence evidence should be kept intact.

**Where in code:** `projects.py` `_apply_compression()` (line ~943) — passes the entire context string to the compressor. No per-chunk compression level.

**Possible fix:**
- **Score-based compression:** Compress chunks below a threshold (e.g., score < 0.5) and leave high-scoring chunks untouched.
- **Tiered compression:** "light" for top chunk, "standard" for middle chunks, "aggressive" for trace-expanded chunks.
- **Summary-only mode:** For low-scoring chunks, generate a one-line summary instead of including the full content.

**Effort:** Medium-High. Requires per-chunk compression calls.

**Impact:** Moderate. Better signal preservation for the most relevant content.

---

## 9. No Feedback Loop

**Problem:** CoDRAG has no way to know if its context was actually useful. Did the LLM use the chunks? Did the user accept the generated code? There's no signal flowing back.

**What the research says:** RAG systems improve dramatically with relevance feedback. Without it, you're optimizing in the dark.

**Where in code:** Nowhere — this doesn't exist yet.

**Possible fix:**
- **Usage tracking via MCP:** When the AI tool calls `codrag` and then produces output, track whether the same files appear in the tool's edits. Crude but directional.
- **Thumbs up/down on chunks:** Expose a `codrag_feedback` tool that the AI tool (or user) can call to mark chunks as helpful or not.
- **Implicit signals:** If the same query is repeated with different K or max_chars, the first result probably wasn't sufficient.

**Effort:** High. Requires new infrastructure.

**Impact:** High long-term. This is how CoDRAG gets measurably better over time.

---

## 10. Embedding Model Is Not Code-Specialized ✅ BENCHMARKED (v1 + v2)

**Status:** Three-tier benchmark complete. v1 (10 files, 15 queries): nomic-embed-code 100% R@1. **v2 (22 files, 39 queries): ONNX best at 84.6% R@1**, all tiers converge. Built-in ONNX confirmed as best default. See `EMBEDDING_MODEL_RESEARCH.md`.

**Problem:** nomic-embed-text-v1.5 is a general-purpose text embedding model. It handles code reasonably well but wasn't trained specifically on code retrieval tasks. Code-specialized models (like CodeBERT, UniXcoder, or Voyage Code) may produce better similarity scores for code queries.

**What the research says:** Embedding quality is the foundation of RAG. Everything downstream (ranking, filtering, trace expansion) depends on the initial similarity scores being meaningful.

**Where in code:** `embedder.py` `NativeEmbedder` — hardcoded to nomic-embed-text-v1.5.

**Possible fix:**
- **Benchmark:** Test nomic-embed-text against code-specialized models on CoDRAG's own test queries. Measure retrieval accuracy.
- **Pluggable embedder:** CoDRAG already supports Ollama as an alternative. Could add Voyage Code or other specialized models as options.
- **Hybrid:** Use code-specialized embeddings for code chunks and general embeddings for docs. Complex but theoretically optimal.

**Effort:** Low (benchmark) to Medium (add model options).

**Impact:** Potentially high. If code retrieval accuracy improves by even 10%, every downstream stage benefits.

---

## 11. Trace Expansion Picks First Chunk Per File ✅ DONE

**Problem:** When trace expansion finds a related file, it picks the **first chunk** from that file (line ~1147–1160: `break` after first match). The first chunk may be imports/boilerplate, not the relevant function.

**Where in code:** `index.py` `get_context_with_trace_expansion()` (line ~1147) — iterates `self._documents`, takes the first match for each `source_path`, breaks.

**Possible fix:**
- **Query-scored selection:** For each related file, score all its chunks against the query and pick the best one.
- **Section-aware selection:** Prefer chunks that contain function/class definitions over import blocks.
- **Edge-aware selection:** If the trace edge points to a specific symbol (e.g., `auth.verify_token`), find the chunk containing that symbol, not just any chunk from the file.

**Effort:** Medium. Requires either embedding lookups or section metadata inspection.

**Impact:** High. This is the difference between trace expansion returning useful code vs. returning `import os; import sys; ...`.

---

## 12. Role Weight Spread Is Too Narrow

**Problem:** Default role weights are `code: 1.0, docs: 0.95, tests: 0.98, other: 0.9`. Intent multipliers range from 0.9 to 1.15. The combined effect is a maximum swing of ~25%. This is so small that it rarely changes which chunks make top-K.

**What the research says:** If we're going to claim intent-aware weighting as a differentiator, it needs to actually shift results noticeably.

**Where in code:** `repo_profile.py` `DEFAULT_ROLE_WEIGHTS` (line ~70). `index.py` `_intent_role_multipliers()` (line ~772).

**Possible fix:**
- Widen the spread. E.g., when intent is "code", set docs multiplier to 0.7 instead of 0.93.
- Or make this user-configurable with wider defaults and let users narrow it if they prefer.
- Caveat: wider spread + bad intent detection (#5) = worse results. Fix #5 first or widen cautiously.

**Effort:** Trivial — change constants.

**Impact:** Low-Medium. Only matters if intent detection is accurate enough to justify wider swings.

---

## 13. No Position Optimization

**Problem:** CoDRAG sorts chunks by descending score (best first). This is good for "lost in the middle" mitigation — the best chunk is at the start. But research shows the *end* of context also gets strong attention. Currently, the last chunk is the *lowest-scoring* semantic result (or the last trace chunk). The second-best chunk should arguably go last.

**What the research says:** Liu et al. (2023) found U-shaped attention. Optimal placement: best at start, second-best at end, weakest in the middle.

**Where in code:** `index.py` `get_context_structured()` — chunks are assembled in descending score order. Trace chunks are appended at the very end (which is good — they're at the "end" attention hotspot). But within the semantic results, the ordering isn't optimized.

**Possible fix:**
- **Interleave:** Place chunks in order [1st, 3rd, 5th, 4th, 2nd] — best at start, second-best at end.
- **Or:** Accept that at 1,500 tokens, position effects are negligible. This matters more at >10K tokens.

**Effort:** Low. Reorder the list before assembly.

**Impact:** Negligible at current default sizes. Could matter if users increase budgets.

---

## 14. Potential Redundancy With Native Tool Indexing

**Problem:** Cursor and Windsurf already embed and search your codebase. When a user has CoDRAG installed, both systems may be retrieving similar chunks for the same query — CoDRAG via MCP and the tool natively. The AI tool then has two overlapping sets of context, wasting tokens.

**What the research says:** Every redundant token is a distractor.

**Where in code:** N/A — this is an architectural concern, not a code bug.

**Possible fix:**
- **Documentation:** Make it clear that CoDRAG is most valuable when: (a) the tool's native indexing is weak (Claude Code), (b) the user needs trace expansion, (c) the user needs specific weight tuning. For basic retrieval in Cursor, CoDRAG may not add enough over @codebase to justify the extra tokens.
- **Dedup hint header:** CoDRAG could include file paths in a structured header so the AI tool can skip those files in its own retrieval.
- **"Replace native" mode:** Instruct users to disable their tool's native codebase indexing when using CoDRAG. This is a bold claim and only justified if CoDRAG's retrieval is demonstrably better.

**Effort:** Low (documentation). Medium (dedup headers). High (prove superiority).

**Impact:** High for positioning. This is the "reinventing the wheel" question — being clear about when CoDRAG adds value vs. when it's redundant.

---

## Summary Table

| # | Problem | Effort | Impact | Status |
|---|---|---|---|---|
| 1 | No result diversity/dedup | Medium | Moderate | ✅ Done (MMR) |
| 2 | Fixed K regardless of match quality | Low | **High** | ✅ Done (Adaptive K) |
| 3 | Low min_score default | Trivial | Moderate | 🔬 Testing (`test_min_score_threshold.py`) |
| 4 | Trace expansion is unranked | Medium | **High** | ✅ Done (ranked trace) |
| 5 | Intent detection is keyword-based | Low-Medium | Low (currently) | 🔬 1 gap remaining (1 xfail) |
| 6 | Character budget ≠ token budget | Low | Low | Deferred |
| 7 | No awareness of tool's existing context | Low | Moderate | ✅ Done (exclude_paths) |
| 8 | Compression is all-or-nothing | Medium-High | Moderate | Later |
| 9 | No feedback loop | High | High (long-term) | Later |
| 10 | Embedding model not code-specialized | Low-Medium | Potentially high | ✅ Benchmarked v2 (ONNX=84.6% best, code=82.1%) |
| 11 | Trace picks first chunk per file | Medium | **High** | ✅ Done (smart chunk) |
| 12 | Role weight spread too narrow | Trivial | Low-Medium | After #5 |
| 13 | No position optimization | Low | Negligible | Deferred |
| 14 | Redundancy with native tool indexing | Low-High | High (positioning) | Documentation |

### Priority order (updated 2026-02-19):

1. ~~**#2 Adaptive K**~~ ✅ Done
2. ~~**#4 Ranked trace expansion**~~ ✅ Done
3. ~~**#11 Smart chunk selection for trace**~~ ✅ Done
4. ~~**#7 exclude_paths parameter**~~ ✅ Done
5. ~~**#1 Result diversity (MMR)**~~ ✅ Done
6. **#3 Raise min_score** — 🔬 test file written, awaiting NativeEmbedder run for final decision
7. ~~**#10 Embedding benchmark**~~ ✅ Done — nomic-embed-code = 100% R@1
8. **#5 Intent detection** — fixed keywords, 1 xfail remaining ('how does X work')
9. **#2.4 Hub-file filtering** — needs trace graph analysis from real projects
10. **#8 Score-based compression** — medium-high effort, later
11. **#12 Widen role weights** — blocked on #5

---

*See also: [FAQ.md](./FAQ.md) and [CONTEXT_VOLUME_RESEARCH.md](./CONTEXT_VOLUME_RESEARCH.md)*

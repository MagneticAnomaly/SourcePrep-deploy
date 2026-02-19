# CoDRAG — Context Window FAQ

> These are the questions people will ask first. Written for developers evaluating CoDRAG, beta testers, and anyone who's been burned by "smart context" tools that silently eat their token budget.

---

## Won't this just use up my whole context window?

**No.** CoDRAG's default output is **~1,500 tokens** (6,000 characters). With trace expansion enabled, it's ~2,000 tokens.

For perspective:

| What | Tokens |
|---|---|
| CoDRAG default context | ~1,500 |
| CoDRAG + trace expansion | ~2,000 |
| Cursor's default chat cap | ~20,000 |
| Claude Code usable window | ~140,000 |
| GPT-4o full window | 128,000 |
| Claude 3.5 Sonnet full window | 200,000 |

CoDRAG typically consumes **1–3% of your available context window.** The rest is used by your AI tool for its system prompt, conversation history, files you @-reference, and its own response.

CoDRAG is designed to be a *precision instrument*, not a firehose. It sends the 5 most relevant code chunks under a hard character ceiling — not your entire codebase.

---

## How much context is too much? Is there a number?

Yes, and it's lower than you'd think.

Research consistently shows that **RAG context saturates between 4K and 16K tokens** depending on the model. After that, adding more context produces diminishing returns — and eventually *hurts* performance.

| Model | Saturation Point | Source |
|---|---|---|
| Mixtral-8x7B | ~4K tokens | Databricks, 2024 |
| GPT-4-turbo | ~16K tokens | Databricks, 2024 |
| Claude 3.5 Sonnet | ~32K tokens | Databricks, 2024 |
| Llama-3.1-8B | 30K tokens causes **24% accuracy drop** (even with perfect retrieval) | Chen et al., 2025 |

The most surprising finding: **even when the model can perfectly retrieve the answer from the context, its reasoning accuracy still degrades as input length increases.** This was demonstrated with whitespace padding — literally adding blank lines degrades reasoning. The problem isn't distraction, it's distance.

CoDRAG's defaults (1,500–2,000 tokens) sit well below every known saturation point.

---

## Doesn't my AI tool (Cursor, Windsurf, Claude Code) already index my codebase?

**Yes — and CoDRAG doesn't replace that.** Here's the breakdown:

### What they already do

| Capability | Cursor | Windsurf | Claude Code |
|---|---|---|---|
| Embeds your codebase | Yes | Yes | No (reads on demand) |
| Semantic search | Yes (@codebase) | Yes | Via grep/tools |
| Sends relevant chunks to LLM | Yes | Yes | Yes (via file reads) |
| Retrieval is scoped per command | Yes (@file, @folder) | Yes (@file, @folder) | Yes (@file, manual reads) |

All three tools solve the basic problem of "find relevant code and inject it." CoDRAG uses the same foundational technique (embed → cosine similarity → top-K) for its core retrieval. **We are not reinventing that wheel.**

### What CoDRAG adds

| Capability | Cursor | Windsurf | Claude Code | CoDRAG |
|---|---|---|---|---|
| **Trace graph** (imports, calls, inheritance) | No | No | No | Yes |
| **Structural expansion** ("also show me what calls this") | No | No | No | Yes (`trace_expand`) |
| **Role weights** (auto-boost code vs docs vs tests) | No | No | No | Yes |
| **Path weights** (user-tunable per-directory relevance) | No | No | No | Yes |
| **Intent detection** (query → intent → weight adjustment) | No | No | No | Yes |
| **Context compression** (CLaRa distillation) | No | No | No | Yes |
| **Transparency** (see scores, chunks, what was sent) | No | No | Partial | Yes |
| **Works across all tools** (MCP standard) | — | — | — | Yes |
| **User-configurable parameters** (K, max_chars, min_score) | No | No | No | Yes |

### Summary

If you just need "find me the relevant function" — your tool probably already does that. CoDRAG's value is in the layers on top:

1. **The trace graph** gives your AI tool structural understanding of your codebase — not just "this chunk is semantically similar" but "this function calls that one, which imports this module." No AI coding tool has this natively.

2. **User control** means you can tune what gets sent instead of trusting a black box. If you know your `utils/` folder is never useful, weight it down. If you know tests matter for your workflow, weight them up.

3. **Cross-tool portability** means your index, weights, and configuration work whether you're in Cursor today and Windsurf tomorrow. Your codebase understanding isn't locked to one vendor.

4. **Compression** via CLaRa means you can send the same semantic information in fewer tokens — the research equivalent of "Retrieve then Solve" which is the recommended mitigation for context-length degradation.

---

## Does the trace graph get dumped into my context?

**No. Never.**

The trace graph for even a small project (~40 Python files) is **547 nodes and 656 edges**. Dumping that raw would be ~68,000 tokens — research shows this would *catastrophically* degrade LLM performance.

Instead, CoDRAG uses the trace graph as a **navigation structure**:

1. Semantic search finds the 5 most relevant chunks (regular embedding search)
2. If `trace_expand` is on, CoDRAG follows the graph edges from those 5 chunks to find structurally related code (imports, callers, callees)
3. Those related chunks are added under a **separate 2,000-character budget**
4. Total trace contribution: ~500 additional tokens

Think of it as using Google Maps to find directions vs. printing out every road in the city. CoDRAG reads the map, gives you just the route.

This approach is validated by research: Han et al. (2025) found that GraphRAG with *local* community search excels at multi-hop queries, while *global* graph retrieval (dumping everything) actively causes hallucination on detail-oriented tasks.

---

## If I set a file's weight to 0.5, does that save context space?

**No.** Path weights change *ranking*, not *volume*.

Here's what actually happens:

```
File: utils/helpers.py
Similarity score: 0.82
Path weight: 0.5
Final score: 0.82 × 0.5 = 0.41   ← ranks lower
```

That file is now **less likely** to appear in the top-5 results. But if it's so relevant that it *still* ranks in the top 5 (e.g., it's the only match), it takes up the exact same space as any other chunk.

**To control how much context is sent, use these knobs:**

| Want less context? | Do this |
|---|---|
| Fewer chunks | Lower `k` (default: 5) |
| Smaller total output | Lower `max_chars` (default: 6,000) |
| Stricter relevance filter | Raise `min_score` (default: 0.15) |
| Compress what's sent | Enable `compression: "clara"` |

Path weights are a **relevance tool** — "I care more about `src/` than `docs/`." They shape *what* gets sent, not *how much*.

---

## What's the "lost in the middle" problem? Should I worry about it?

"Lost in the middle" (Liu et al., 2023) is a well-documented phenomenon: LLMs pay the most attention to the **beginning and end** of their context window, and systematically under-utilize information in the middle.

**Should you worry?** Less than you think, because CoDRAG already mitigates it:

1. **Most relevant first.** CoDRAG sorts chunks by descending relevance score. The highest-scoring chunk is at the top — exactly where models pay the most attention.

2. **Small context volume.** At 1,500–2,000 tokens, CoDRAG's output is short enough that there *isn't* a meaningful "middle" to get lost in. The problem primarily affects contexts >10K tokens.

3. **Trace chunks are appended last.** Structurally related (but potentially less directly relevant) trace chunks go at the end — the other position where models pay strong attention.

Where "lost in the middle" *does* matter is in the overall context your AI tool assembles — system prompt + conversation + all tool results + your question. CoDRAG can't control that, but by keeping its contribution small and well-ordered, it avoids making the problem worse.

---

## Can't I just paste my whole codebase into Claude with its 200K window?

You can. It will work worse than you expect.

Chen et al. (2025) demonstrated that even with **perfect retrieval** — the model can literally recite the evidence verbatim — reasoning accuracy drops 13.9% to 85% as input length increases. This was tested on math, QA, and *coding tasks* specifically.

Chroma Research (2025) tested 18 current LLMs and found that **even on trivial retrieval tasks**, performance degrades non-uniformly with input length. This includes Claude Sonnet 4, GPT-4o, and Gemini 2.5 — the latest models with the biggest windows.

The problem isn't the model's ability to *find* the code. It's that the sheer *distance* between the relevant code and the question degrades the model's ability to *reason about* it.

**Practical translation:** A 200K window can hold ~300 pages. But a human doesn't read better by having 300 irrelevant pages open on their desk. Neither does an LLM.

CoDRAG's approach — find the 5 best chunks, optionally follow structural relationships, and deliver ~2K tokens of high-signal context — aligns with the research recommendation of "Retrieve then Solve": extract evidence into a shorter prompt, then reason over that.

---

## What if CoDRAG's 5 chunks aren't enough?

This is a real concern. Here's how to address it:

**First: increase K before increasing max_chars.** Getting 8 diverse chunks is usually better than getting 5 longer chunks. More perspectives on the problem beat more text from one file.

**Second: turn on trace expansion.** If your question is structural ("what calls this?", "what does this depend on?"), trace expansion adds the connected code automatically — without you having to know where it lives.

**Third: check your weights.** If important files are being outranked, adjust path weights or role weights. Maybe your tests are relevant but being deprioritized.

**Fourth: if you truly need more, increase max_chars — but cautiously.** Research shows diminishing returns beyond ~15K tokens. Going from 6K to 10K chars is reasonable. Going to 50K is likely counterproductive.

| Adjustment | When to use |
|---|---|
| `k: 8` | Want broader coverage across files |
| `trace_expand: true` | Need structural relationships |
| `max_chars: 10000` | Complex multi-file question |
| `compression: "clara"` | Same info, fewer tokens |
| `max_chars: 15000+` | Rarely — verify it actually helps |

---

## Is this just another RAG tool?

CoDRAG's *foundation* is RAG — embed, search, retrieve. That's the same technique Cursor, Windsurf, and most modern tools use internally.

What makes CoDRAG different is what happens **on top of** basic retrieval:

1. **Graph-aware retrieval.** The trace graph (built by a Rust engine that parses your code's AST) captures imports, function calls, class inheritance, and module dependencies. When you ask "how does authentication work?", CoDRAG doesn't just find the `auth.py` file — it can follow the call chain to find the middleware, the token validator, and the user model. No other AI coding tool does this natively.

2. **Intent-aware weighting.** CoDRAG detects whether your query is about implementation ("how does X work?"), debugging ("why does X fail?"), or architecture ("what depends on X?") and adjusts which types of content (code, docs, tests) are prioritized. This is automated — not something you configure per query.

3. **User transparency and control.** Every other tool is a black box. CoDRAG shows you the scores, lets you set weights, and tells you exactly what was sent and why. When something goes wrong, you can debug it.

4. **Tool-agnostic via MCP.** CoDRAG works with any MCP-compatible tool. Your index, configuration, and codebase understanding aren't locked to one vendor. Switch from Cursor to Claude Code tomorrow — CoDRAG works the same.

5. **Context compression.** The CLaRa sidecar can distill context by 30–70%, sending the same semantic information in fewer tokens. This directly addresses the research finding that shorter context = better reasoning.

So: the base is RAG (same as everyone), the differentiation is in graph-awareness, user control, portability, and compression.

---

## How does CoDRAG compare on token efficiency?

Here's a realistic comparison for a typical query like "how does the authentication middleware work?":

| Approach | Tokens Sent | What You Get |
|---|---|---|
| Paste the whole file | 5,000–20,000 | The whole file, mostly irrelevant |
| Cursor @codebase | ~2,000–5,000 | Black-box selection, no trace context |
| Claude Code file read | ~3,000–8,000 | Whole file or manual line range |
| CoDRAG default | ~1,500 | Top 5 ranked chunks, headers with paths |
| CoDRAG + trace | ~2,000 | Same + structurally related code (callers, imports) |
| CoDRAG + trace + CLaRa | ~800–1,200 | Compressed: same info, 30–70% fewer tokens |

The `zilliztech/claude-context` MCP server (vector search for Claude Code) reports ~40% token reduction at equivalent retrieval quality. CoDRAG achieves similar efficiency, with the added benefit of graph-aware expansion and user-configurable weights.

---

## What's the bottom line?

1. **More context is not better context.** Research from 2023–2025 unanimously shows that LLM performance degrades with input length — even with perfect retrieval, even with the latest models, even with simple tasks.

2. **CoDRAG is deliberately conservative.** 1,500–2,000 tokens of high-signal context, filtered through 8 stages of ranking and truncation. This is a feature, not a limitation.

3. **CoDRAG adds real value on top of what your AI tool already does.** The trace graph, user-configurable weights, cross-tool portability, and compression are meaningful differentiators — not reinvention of basic retrieval.

4. **The trace graph is a navigation tool, not a context dump.** It makes CoDRAG smarter about *which* code to send, without making the context bigger.

5. **You can tune everything.** K, max_chars, min_score, path weights, role weights, trace expansion, compression. If the defaults aren't right for your project, every knob is exposed.

---

*See also: [CONTEXT_VOLUME_RESEARCH.md](./CONTEXT_VOLUME_RESEARCH.md) for the full academic research backing these answers.*

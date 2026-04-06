# Phase 73.3b — Compression × Distribution Tier Research

> Date: 2026-04-05 | How CoDRAG's 14 context knobs map to 3 client tiers, validated by 2024-2025 research

---

## 1. The Question

We have **14 mechanisms** that control context volume and quality. We have **3 client tiers** (20K / 30K / 50K). How should each mechanism behave at each tier to maximize agent effectiveness?

The research evidence is clear on one overriding principle: **less, better context outperforms more, worse context** — even with 1M-token windows. The goal is not to fill the window; it's to fill it with the *right* content at the *right* fidelity.

---

## 2. Evidence Base

### 2.1 Token Pruning (LLMLingua-2) Is Wrong for Code

**LongCodeZip (Shi et al., 2025)** explicitly demonstrates that LLMLingua-style token pruning corrupts code syntax. Token-level removal destroys brackets, type annotations, and variable names that are low-perplexity but structurally essential. Function-level extractive compression (which is what LOD does) is the validated approach.

> **Decision: Drop LLMLingua-2 for code entirely. Keep it ONLY for documentation/markdown compression. LOD is our code compression engine.**

### 2.2 Context Rot Is Real and Universal

**Context Rot (Chroma, 2025)** tested 18 frontier models including Claude Opus 4, GPT-4.1, Gemini 2.5 Pro. Every model degrades as input grows. Three mechanisms compound:
1. **Lost-in-the-middle** — content in the middle of the context gets 30%+ less attention (Liu et al., 2023)
2. **Attention dilution** — more tokens = less attention per token
3. **Distractor interference** — semantically similar but irrelevant content actively harms accuracy

**Du et al. (2025)**: Even with 100% perfect retrieval, longer context hurts. GPT-4o lost 67.6% accuracy on MMLU at 30K tokens.

**Paulsen (2025)**: Maximum Effective Context Window (MECW) falls up to 99% short of advertised MCW. Some models fail with as few as 100 tokens.

> **Decision: Our current budget strategy (1-6% of window) is correct. The danger is over-filling, not under-filling. Every additional char must earn its place.**

### 2.3 Structural Compression Is Validated

**Aider repo maps** (Gauthier, 2023): tree-sitter signatures + PageRank ranking is sufficient for GPT to understand cross-file relationships. Widespread production success.

**CodexGraph (Liu et al., 2024)**: Graph-based structural retrieval (27.90% EM) dramatically outperforms BM25 (21.20%) and no-RAG (10.80%) on CrossCodeEval.

**Context Inlining (2025)**: Full source for focal code, signatures/types for dependencies — this "capsule context" pattern improves repo-level code generation.

> **Decision: LOD 0 for focal code, LOD 2-4 for neighbors is the right architecture. We should be more aggressive about LOD differentiation between tiers.**

### 2.4 Hierarchical Summaries Work

**Code-Craft (Sounthiraraj et al., 2025)**: Bottom-up hierarchical summarization achieved 82% relative improvement in Pass@1. Module summaries built from function → file → module chain.

**Li et al. (2024)**: Summarization-based retrieval performs comparably to full long-context.

> **Decision: Our module summaries are a validated compression tier. Use them more aggressively at lower budgets instead of cutting modules.**

### 2.5 Position Matters

**Lost in the Middle (Liu et al., 2023)**: Performance highest when relevant info is at the beginning or end. Middle content gets neglected.

> **Decision: Structure context as: orientation header → focal code → hub files → neighbors → module summaries. Most-relevant first, least-relevant last.**

---

## 3. Complete Mechanism Inventory

Here are all 14 context control mechanisms, their current defaults, and where they live:

| # | Mechanism | What It Controls | Current Default | File:Line | Configurable? |
|---|-----------|-----------------|----------------|-----------|--------------|
| 1 | **Client budget tiers** | Total max_chars per response | 20K/24K/30K/50K | `mcp/server.py:145-162` | Auto-detected |
| 2 | **First-call boost** | 50% more on first `codrag` call | 1.5× multiplier | `mcp/server.py:184-186` | Hardcoded |
| 3 | **LOD score thresholds** | Which compression level per chunk | ≥0.50→LOD0, 0.35→LOD2, 0.20→LOD4 | `lod_extractor.py:366-384` | Hardcoded |
| 4 | **Hub file count** | How many hub files in ambient | k=8 | `search.py:468` | Hardcoded |
| 5 | **Hub budget ratio** | Hub vs neighbor budget split | 70% hub / 30% neighbor | `search.py:544-546` | Hardcoded |
| 6 | **Hub LOD** | Fidelity of hub file content | LOD 0 (full source) | `search.py:560-586` | Hardcoded |
| 7 | **Neighbor LOD** | Fidelity of neighbor content | LOD 2 (signatures) | `search.py:606-624` | Hardcoded |
| 8 | **Module tier thresholds** | Which modules show detail | ≥5 files=significant, 2-4=small, <2=tiny | `search.py:432-456` | Hardcoded |
| 9 | **Atlas budget formula** | Size of structural overview | 1200-4000 chars (file-count adaptive) | `atlas/routing.py:29-48` | Hardcoded |
| 10 | **Role vector detail_level** | Granularity for role-filtered atlas | 0.2 (CEO) to 1.0 (intern) | `atlas/role_vectors.py:91-110` | Preset roles |
| 11 | **Trace expansion budget** | Chars for structural neighbors | 4000 chars | `models.py:56` | Per-request |
| 12 | **Score filtering** | Minimum relevance to include | min_score=0.15, drop_ratio=0.4 | `models.py:50-51` | Per-request |
| 13 | **Module cap (VRAM)** | Max modules in Atlas prompt | 50-150 (VRAM-adaptive) | `context_config.py:240-267` | Hardcoded |
| 14 | **Segment routing** | Which codebase segments respond | boost=0.12, max_segments=3 | `atlas/routing.py:60-65` | Hardcoded |

---

## 4. Tier-Specific Optimization Strategy

### The Core Insight

The 14 mechanisms above fall into **3 categories**:

| Category | Mechanisms | What They Control |
|----------|-----------|------------------|
| **Volume** | #1, #2, #4, #5, #9, #11, #13 | How much content total |
| **Fidelity** | #3, #6, #7, #10 | How detailed each piece is (LOD level) |
| **Selection** | #8, #12, #14 | Which content makes the cut |

The research says: **Selection > Fidelity > Volume.** Sending the right files at any LOD beats sending wrong files at LOD 0. And sending fewer right files beats sending more mixed-quality files.

### 4.1 Tier 2.5 — Local Models (20K budget, 30K orient)

**Philosophy: Maximum signal density. Every char must be structural orientation.**

| Mechanism | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| Hub files | 8 at LOD 0 | **4 at LOD 2** | Full source of 8 hubs ≈ 20K alone. Signatures of 4 top hubs fit in 3K. |
| Neighbors | LOD 2, 30% budget | **LOD 4 (imports+names), 15% budget** | At 20K, neighbor signatures crowd out hubs. Names-only gives orientation without cost. |
| Module summaries | Full tiered display | **Significant modules only** (≥5 files) | Small/tiny modules are noise at this budget. Save 500-800 chars. |
| Atlas | Up to 4000 chars | **Cap at 2000** | Structural overview shouldn't eat 20% of budget. |
| Trace expansion | 4000 chars | **2000 chars** | Halve expansion budget to leave room for primary results. |
| Score threshold | min_score=0.15 | **min_score=0.25** | Be more selective — only high-confidence results. |

**Expected budget usage at 20K:**
```
Module list (significant only):   2,000 chars  (10%)
Atlas overview:                   2,000 chars  (10%)
Hub files (4× LOD 2):            4,000 chars  (20%)
Neighbors (6× LOD 4):            1,500 chars   (8%)
Search results (top-3 LOD 0):    8,000 chars  (40%)
Trace expansion:                  2,000 chars  (10%)
Headers/formatting:                 500 chars   (2%)
                                 ──────────
Total:                           20,000 chars (100%)
```

### 4.2 Tier 2 — IDE Integrations (30K budget, 45K orient)

**Philosophy: Standard structural context. Enough for single-file tasks without extra search calls.**

| Mechanism | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| Hub files | 8 at LOD 0 | **6 at LOD 0** (top 3) + **LOD 2** (next 3) | Top hubs full source, rest signatures. Gradual fidelity falloff. |
| Neighbors | LOD 2, 30% budget | **LOD 2, 25% budget** | Signatures are the right level per Aider/CodexGraph evidence. |
| Module summaries | Full tiered display | **Significant + small** | Include 2-4 file modules as one-liners. |
| Atlas | Up to 4000 chars | **Up to 3000** | Slightly more than T2.5 but not full budget. |
| Trace expansion | 4000 chars | **4000 chars** (keep) | Standard — enough for 3-5 neighbor signatures. |
| Score threshold | min_score=0.15 | **min_score=0.20** | Slightly more selective than current. |

**Expected budget usage at 30K:**
```
Module list (sig + small):        3,000 chars  (10%)
Atlas overview:                   3,000 chars  (10%)
Hub files (3× LOD0, 3× LOD2):    8,000 chars  (27%)
Neighbors (8× LOD 2):            4,000 chars  (13%)
Search results (top-5 LOD 0):   10,000 chars  (33%)
Trace expansion:                  2,000 chars   (7%)
                                 ──────────
Total:                           30,000 chars (100%)
```

### 4.3 Tier 1 — Claude/Gemini (50K budget, 75K orient)

**Philosophy: Rich multi-file context. Agent can plan refactors in one shot.**

| Mechanism | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| Hub files | 8 at LOD 0 | **10 at LOD 0** | More structural spine. These models handle it. |
| Neighbors | LOD 2, 30% budget | **LOD 1** (source minus comments), **30% budget** | Per research: more fidelity helps with multi-file reasoning. LOD 1 is cheap (only strips comments). |
| Module summaries | Full tiered display | **Full tiered** (current is fine) | At 50K there's room for all tiers. |
| Atlas | Up to 4000 chars | **Up to 4000** (keep) | Full structural overview earned. |
| Trace expansion | 4000 chars | **6000 chars** | More expansion budget → deeper structural graph. |
| Score threshold | min_score=0.15 | **min_score=0.15** (keep) | Wider net is fine when budget allows it. |
| Concept summaries | Not included | **Include top 3** | These models benefit from semantic orientation. |

**Expected budget usage at 50K:**
```
Module list (full tiered):        3,500 chars   (7%)
Atlas overview:                   4,000 chars   (8%)
Hub files (10× LOD 0):          15,000 chars  (30%)
Neighbors (12�� LOD 1):           8,000 chars  (16%)
Search results (top-5 LOD 0):   12,000 chars  (24%)
Trace expansion:                  5,000 chars  (10%)
Concept summaries:                2,000 chars   (4%)
                                 ──────────
Total:                           49,500 chars  (99%)
```

### 4.4 Tier 1 Orient (75K, first call only)

Same as Tier 1 but with boosted quantities:

| Delta from Tier 1 | Change |
|---|---|
| Hub files | 12 at LOD 0 (vs 10) |
| Neighbors | 15× LOD 0-1 (vs 12× LOD 1) |
| Module summaries | Include dependency arrows |
| Concept summaries | Include top 5 with content |

---

## 5. LOD Level Optimization

### 5.1 Current LOD Score Thresholds (Hardcoded)

```
≥ 0.50 → LOD 0 (full source)
0.35–0.49 → LOD 2 (signatures + docstrings)
0.20–0.34 → LOD 4 (names + imports)
trace-expanded → LOD 4
< 0.20 → LOD 5 (summary only)
```

### 5.2 Problem: LOD 2 Underperforms on Constant-Heavy Files

Our test results from `test_compressor.py`:

| File Type | LOD 2 Ratio | LOD 4 Ratio | Explanation |
|-----------|-------------|-------------|-------------|
| `feature_gate.py` (function-heavy) | 2.6× | 13.2× | Most code in functions → LOD 2 compresses bodies well |
| `compressor.py` (mixed) | 1.4× | 8.1× | Module-level constants, dicts pass through LOD 2 |
| `lod_extractor.py` (constant-heavy) | 1.3× | 14.0× | Regex patterns, dicts dominate; LOD 2 barely compresses |

**Root cause**: LOD 2 only replaces function/method bodies with `...`. Module-level constants, class variables, regex patterns, and dict literals are not inside any function body → they pass through unchanged.

### 5.3 Proposed: Tier-Adaptive LOD Thresholds

Instead of one hardcoded set of thresholds, adapt based on budget tier:

```python
# Current (one-size-fits-all):
def assign_lod(score, *, is_trace_expanded=False):
    if is_trace_expanded: return 4
    if score >= 0.50: return 0
    if score >= 0.35: return 2
    if score >= 0.20: return 4
    return 5

# Proposed (tier-aware):
def assign_lod(score, *, is_trace_expanded=False, tier=2):
    if is_trace_expanded:
        return 4 if tier >= 2 else 5
    
    if tier == 1:      # Generous — full source for more chunks
        if score >= 0.40: return 0
        if score >= 0.25: return 2
        if score >= 0.15: return 4
        return 5
    elif tier == 2:    # Standard — current thresholds
        if score >= 0.50: return 0
        if score >= 0.35: return 2
        if score >= 0.20: return 4
        return 5
    else:              # Tier 2.5 — Aggressive compression
        if score >= 0.60: return 0
        if score >= 0.40: return 2
        if score >= 0.25: return 4
        return 5
```

**Effect**: Tier 1 agents see full source for more chunks (score ≥ 0.40 vs 0.50). Tier 2.5 agents get more compressed views, saving budget for the truly relevant hits.

### 5.4 Proposed: LOD 2.5 — Strip Module-Level Constants

A new intermediate level between LOD 2 and LOD 4 that addresses the constant-heavy file problem:

```
LOD 2   = signatures + docstrings + module-level code (current)
LOD 2.5 = signatures + docstrings ONLY (strip module-level constants/dicts/regexes)
LOD 4   = imports + first line of each symbol
```

This would give `lod_extractor.py` a ~3-4× ratio at LOD 2.5 instead of 1.3× at LOD 2. Implementation: any line not inside a function/class body AND not an import → skip.

---

## 6. Content Ordering Strategy (Lost-in-the-Middle)

Based on Liu et al. (2023) and Chroma's Context Rot findings, content position in the context window matters. The model attends most to the beginning and end, least to the middle.

### Current ordering (ambient context):
```
1. Module list         (orientation — good at top)
2. Hub file content    (structural spine — good at top)
3. Architecture dump   (noise — bad anywhere, worse in middle)
4. Neighbor content    (supplementary — ok in middle)
```

### Proposed ordering:
```
1. Module list + atlas   (orientation header — top position, high attention)
2. Search results LOD 0  (focal code — right after orientation)
3. Hub files LOD 0       (structural spine — early-middle, still high attention)
4. Trace neighbors LOD 2 (supplementary — late-middle)
5. Module summaries      (orientation tail — end position, high attention)
```

Rationale: Put the most *actionable* content (search results, focal code) near the top where attention is highest. Put *orientation* content (module summaries) at the end where the "recency" attention bump helps. Neighbor signatures go in the middle where they're least likely to distract from focal code but still available for cross-reference.

---

## 7. LLMLingua-2: Revised Strategy

### What the research says:
- **Good for**: Natural language documentation, markdown, README files, commit messages, comments
- **Bad for**: Code, structured data, anything with syntactic significance
- **Ratio**: ~1.6× on docs at "light" (60% keep), ~2.5× at "standard" (40% keep)

### Where to use it in CoDRAG:

| Content Type | Compression | Rationale |
|---|---|---|
| Code files | LOD (structural) | Token pruning corrupts syntax (LongCodeZip, 2025) |
| Markdown docs | LLMLingua-2 (light) | Natural language tolerates token pruning |
| Module summaries | LLMLingua-2 (standard) | Generated text, high redundancy |
| Atlas overview | None | Already curated/short |
| Docstrings within LOD | None | Already compressed by LOD extraction |
| Code-in-docs (fenced blocks) | Splice strategy | Strip fences → compress prose → recombine |

### The splice strategy (from `scripts/test_code_in_docs_compression.py`):
```
1. Detect code fences (``` blocks) in markdown
2. Extract and set aside code blocks
3. Compress remaining prose with LLMLingua-2
4. Re-insert code blocks unchanged
5. Result: compressed prose + intact code
```

This should be promoted from script to production code in `compressor.py` when we enable LLMLingua.

---

## 8. Summary: What to Implement

### Phase 1 (Current sprint — no new dependencies)

| Change | Mechanism(s) | Impact | Effort |
|--------|-------------|--------|--------|
| **Tier-adaptive LOD thresholds** | #3 | Better budget utilization per tier | Small — parameterize `assign_lod()` |
| **Tier-adaptive hub count + LOD** | #4, #6 | T2.5: 4 hubs at LOD 2. T1: 10 at LOD 0 | Medium — add tier param to `_resolve_hub_files` |
| **Tier-adaptive neighbor LOD** | #7 | T2.5: LOD 4. T2: LOD 2. T1: LOD 1 | Small — pass tier to neighbor assembly |
| **Content ordering fix** | N/A | Focal code first, orientation at end | Medium — reorder `_assemble_ambient_context` |
| **Raise Tier 2.5 min_score** | #12 | Fewer low-quality results at constrained budgets | Trivial |

### Phase 2 (Next sprint — requires LLMLingua install)

| Change | Mechanism(s) | Impact | Effort |
|--------|-------------|--------|--------|
| **Add `llmlingua` to extras** | N/A | Unblock the feature | Trivial |
| **Splice strategy in compressor.py** | New | Safe compression for docs with code fences | Medium |
| **Auto-route code→LOD, docs→Lingua** | #3+new | The "dual-channel" we advertise | Medium |
| **Write `tests/test_compressor_lingua.py`** | N/A | Validate before shipping to users | Small |

### Phase 3 (Future — architecture)

| Change | Mechanism(s) | Impact | Effort |
|--------|-------------|--------|--------|
| **LOD 2.5 (strip module constants)** | #3 | Fix weak LOD 2 on constant-heavy files | Medium — new extraction logic |
| **Tier parameter through MCP schema** | #1 | Let agents request specific compression | Medium — schema + handler change |
| **Concept summaries in Tier 1** | New | Richer semantic orientation for 1M models | Medium |

---

## 9. Key Research References

| Paper | Year | Key Finding for CoDRAG |
|-------|------|----------------------|
| LLMLingua-2 (Pan et al.) | 2024 | 2-5× on NL, but not designed for code |
| LongCodeZip (Shi et al.) | 2025 | Token pruning corrupts code; extractive compression is correct |
| Lost in the Middle (Liu et al.) | 2023 | Position matters — beginning and end get most attention |
| Context Rot (Chroma) | 2025 | Every model degrades with length; distractors actively harm |
| MECW (Paulsen) | 2025 | Effective context is up to 99% smaller than advertised |
| Context Length Alone Hurts (Du et al.) | 2025 | Even perfect retrieval + long context hurts accuracy |
| CodexGraph (Liu et al.) | 2024 | Graph retrieval 2.5× better than embedding-only for code |
| Code-Craft (Sounthiraraj et al.) | 2025 | Hierarchical code summarization: 82% Pass@1 improvement |
| RAG vs LC (Li et al.) | 2024 | Summary-based retrieval matches long-context performance |
| Context Inlining | 2025 | Full source for focal, signatures for deps — validates capsule context |
| Aider repo map (Gauthier) | 2023 | Signatures + PageRank sufficient for cross-file reasoning |
| RepoHyper | 2024 | Graph-based retrieval outperforms flat similarity for code |

# Phase 110 -- Retrieval Intelligence: Intent, Chunking & Weights

> **Scope:** Dramatically improve search result quality through intent classification, semantic chunking, and path weight enforcement.
> **Prior art:** Phases 86, 93, 95, 104
> **Status:** Research & TODO (**reality-checked 2026-04-15** — see §1.5; Problem Statement largely stale)
> **Date:** 2026-04-15

> **⚠️ Reality-check delta (2026-04-15):** The Problem Statement in §1 is **significantly stale**. The claim that only 4 keyword-based intents exist is wrong — a 7-intent classifier (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, COMPARE, DISCOVER) shipped in commit `6a1134ea` and routes to distinct retrieval strategies (`mcp/server.py:3789-3860`). Explicit path weights shipped and are applied in search ranking (`index.py:1088-1114`). Semantic markdown chunking with Savitzky-Golay boundary detection shipped (`chunking.py:120-206`). The remaining real work is narrower than originally framed: coverage_ratio wiring, EXAMPLE/COMPARE intent polish, per-chunk context headers decision, LOD/atlas/trace path-weight propagation audit, dashboard path_weights UI, Phase 104 role-lens verification. See §1.5 for full verdict.

---

## 1. Problem Statement

CoDRAG's retrieval pipeline currently treats every query the same way: embed it, find nearest neighbors, expand via trace graph, return results. Phase 82 dogfooding and Phase 38 repo health audits revealed that this one-size-fits-all approach produces mediocre results for many query types:

- **"Where is the auth middleware?"** needs symbol lookup, not semantic search.
- **"Why does auth use JWT instead of sessions?"** needs concept retrieval, not code chunks.
- **"What calls the payment handler?"** needs trace graph traversal, not embedding similarity.

Additionally, path weights are **advertised on the marketing site but not fully implemented** (Phase 95 discovery). The Knowledge Graph UI exists for folder selection, but explicit per-folder weight multipliers don't propagate through search ranking, LOD compression, or atlas routing.

**Current state from `index.py`:**
- Intent detection exists (`_detect_intent`) but only uses keyword matching for 4 intents (debug, refactor, add_feature, understand) + general fallback.
- Intent affects trace expansion parameters (direction, hops, edge kinds) but NOT retrieval strategy.
- No query expansion, no rephrase, no decomposition.
- Chunking is file-based (chunk_code, chunk_markdown) -- no semantic boundary detection.
- `QuerySignals` extracts file names, file paths, symbols, and keywords from queries but coverage ratio isn't used for result filtering.

**Current state from `query_analyzer.py`:**
- Extracts structural signals: file paths, file names (regex), CamelCase symbols, snake_case symbols, stop words.
- `coverage_ratio()` computes keyword overlap but isn't wired into ranking.

## 1.5 Reality Check Against Current Code (2026-04-15)

§1's Problem Statement was written against pre-`6a1134ea` summaries. Here's what is actually shipped:

| Claim (from §1) | Verdict | Evidence |
|---|---|---|
| "Intent detection exists but only uses keyword matching for 4 intents" | **STALE — 7 intents shipped** | `core/intent.py:13-20` — `SearchIntent` enum: LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, COMPARE, DISCOVER. Implementation uses regex-based classification (`intent.py:23-66`), not keyword lists. Commit `6a1134ea`. |
| "Intent affects trace expansion parameters but NOT retrieval strategy" | **STALE** | `mcp/server.py:3789-3860` routes per-intent: LOCATE→symbol search, TRACE→impact graph, RATIONALE→concepts, DISCOVER→expanded semantic, others→semantic. Strategy dispatch is live. |
| "No query expansion, no rephrase, no decomposition" | **PARTIALLY STALE** | `intent.py:69-103` implements `rewrite_query()` (strips signal words). Structural decomposition via QueryAnalyzer lives at `index.py:1065-1068`. |
| "Chunking is file-based -- no semantic boundary detection" | **STALE** | `chunking.py:120-206` — `_semantic_split()` uses Savitzky-Golay filter on sentence embeddings. Called for oversized markdown at `index.py:296-299`. Commits `58b8950e`, `96958308`. |
| "`coverage_ratio` isn't used for result filtering" | **STILL ACCURATE** | Method defined at `query_analyzer.py:54-59` but never called for filtering/boost. |
| "DEFAULT_ROLE_WEIGHTS exists with docs/other/code multipliers" | **CONFIRMED** | `repo_profile.py:128-133` (code:1.0, docs:0.85, tests:0.95, other:0.80) |
| "Explicit user-defined path weights not implemented" | **STALE — SHIPPED** | `index.py:1088-1090, 1112-1114` reads & applies path_weights from config. `repo_policy.py:71, 132` normalizes. `feature_gate.py:56` marks as FREE tier. |
| "Semantic chunking 0/32 tasks" | **STALE — scoped MVP SHIPPED** | See row 4. Full SG filter still not built; scoped version is active. |
| "Sub-atlas & role lens 0/6 tasks" | **NEEDS-VERIFICATION** | Out of scope for this read-only pass. Role param exists on `codrag`/`codrag_search`. AtlasLensPanel status untested. |

**Commits landed after first draft that invalidate or partially fulfill the plan:**
- `6a1134ea` — 7-intent rule-based classifier
- `9aa5773a` — immune + intent fixes: path_matches false positive, import pattern greedy capture, intent docstring priority
- `7bc4bc67` — Tier 1 contextual retrieval: synopsis prefix in embeddings
- `96958308` — wire semantic chunking into `CodeIndex.build()`
- `58b8950e` — semantic boundary detection for oversized markdown sections
- `2da5dafd` — inject meta-chunk synopsis for multi-chunk files
- `5c4d2dee` — structural query decomposition: boost files/symbols named in queries
- `5acc0680` — index build progress reflects work done, not work starting (F-43)

**Bottom line:** Phase 110's original framing is largely an archived description. The genuinely remaining work (see reframed §4.x) is (a) wire `coverage_ratio` into scoring, (b) polish EXAMPLE (test-file boost) + COMPARE (side-by-side interleave) intents, (c) decide on per-chunk context headers (file synopsis currently used only in meta-chunks), (d) audit path-weight propagation through LOD, atlas routing, trace expansion, (e) verify dashboard Knowledge Graph UI can write `path_weights` to config (likely can't — see Phase 111 §5.8), (f) Phase 104 role-lens verification.

## 2. Existing Infrastructure Assessment

### 2.1 Intent Detection (`index.py:38-82`)

4 intent categories with keyword lists. Returns intent string used to select `_INTENT_PARAMS` (trace direction, hops, edge kinds). This is Phase 39's W2a work.

**Gap:** Intent should route to fundamentally different retrieval strategies, not just tweak trace parameters. Phase 86 designed this but 0 tasks are implemented.

### 2.2 Path Weights (`repo_profile.py`)

`DEFAULT_ROLE_WEIGHTS` exists with per-role multipliers:
- docs: 0.85 (15% penalty)
- other: 0.80 (20% penalty)
- code: 1.0 (no penalty)

These apply during search. But **explicit user-defined path weights** (e.g., "boost src/core/ to 1.5x, suppress vendor/ to 0.3x") are not implemented despite being:
1. Advertised on the marketing site
2. Designed in Phase 95
3. Listed as a Phase 16 (S-10.2) deliverable

The Knowledge Graph UI lets users select folders for indexing, but selection != weighting.

### 2.3 Semantic Chunking (Phase 93)

Extensive research produced:
- Semantic Gradient (SG) filter design for detecting semantic boundaries in code
- Contextual retrieval design (prepend file-level context to each chunk)
- Adaptive chunk merging for small chunks
- 32 implementation tasks, 0 completed

Current chunking in `chunking.py` splits by function/class boundaries for code and by heading for markdown. This is adequate for structured code but misses semantic shifts within large functions.

### 2.4 Sub-Atlas & Role Lens (Phase 104)

Designed a per-subsystem "lens" that shows the atlas from a specific role's perspective. 6 tasks pending. Depends on path weights working correctly.

## 3. Proposed Solutions

### Solution A: Multi-Strategy Intent Router (Phase 86 completion)

Implement 7 intent types with distinct retrieval strategies:

| Intent | Detection | Strategy |
|---|---|---|
| LOCATE | "where is X", file/symbol names in query | Symbol search first, then semantic |
| EXPLAIN | "how does X work", "walk me through" | Full source (LOD 0) for matched files |
| RATIONALE | "why does X use Y" | Concept search first, then code context |
| TRACE | "what calls X", "who imports X" | Trace graph traversal, no embedding needed |
| EXAMPLE | "show me how to use X" | Search for usage patterns, test files |
| COMPARE | "difference between X and Y" | Parallel search for both, side-by-side |
| DISCOVER | broad exploratory queries | Current default behavior (semantic + trace) |

**Implementation:** Add `_classify_intent(query, signals)` that uses `QuerySignals` + keyword matching + heuristics. Each intent maps to a retrieval function in a strategy registry.

### Solution B: Explicit Path Weights

Add `path_weights: Dict[str, float]` to project config. Apply during:
1. **Search ranking:** Multiply search scores by path weight before sorting
2. **LOD assignment:** Path weight influences LOD level (higher weight = lower LOD = more detail)
3. **Atlas routing:** Boosted paths get priority in segment selection
4. **Trace expansion:** Neighbors in boosted paths get higher expansion priority

### Solution C: Query Signal Coverage Filtering

Wire `QuerySignals.coverage_ratio()` into result filtering:
- If a query mentions specific symbols/files, results that don't match any signal get a penalty
- Results with high keyword coverage get a boost
- This prevents "semantic similarity drift" where embeddings find topically related but structurally irrelevant files

### Solution D: Adaptive Chunking (Phase 93 scoped MVP)

Instead of the full semantic gradient filter, ship a simpler improvement:
1. **Context header:** Prepend `# File: {path}\n# Module: {module_name}` to every chunk
2. **Merge small chunks:** Consecutive chunks under 200 chars get merged
3. **Split large functions:** Functions > 100 lines get sub-chunked at logical boundaries (blank lines, comment blocks)

## 4. TODO

### 4.1 Intent Classification (Phase 86 completion) — **MOSTLY SHIPPED**
- [x] Design `IntentType` enum with 7 intents — **[FIXED: 6a1134ea]** (`intent.py:13-20`, `SearchIntent`)
- [x] Implement `classify_intent(query, signals) -> IntentType` — **[FIXED: 6a1134ea]** (`intent.py:23-66`, regex-based)
- [x] LOCATE: symbol search first via trace graph, fall back to semantic — **[FIXED]** (`mcp/server.py:3789-3795`)
- [x] RATIONALE: concepts first, fall back to code — **[FIXED]** (`mcp/server.py:3804-3834`)
- [x] TRACE: use impact graph directly, no embedding — **[FIXED]** (`mcp/server.py:3796-3803`)
- [x] EXPLAIN: semantic + trace expansion — **[FIXED]** (`mcp/server.py:3849-3860`)
- [ ] EXAMPLE: boost test files, filter for usage patterns — **[PARTIAL]** routed to semantic search; no explicit test-file boost
- [ ] COMPARE: parallel search + interleave — **[PARTIAL]** routed to semantic search; no side-by-side interleaving
- [x] DISCOVER: default semantic+trace behavior — **[FIXED]**
- [x] Wire intent router into `codrag_search` — **[FIXED]** (`mcp/server.py:3770-3787`)
- [x] Add `detected_intent` to response metadata — **[FIXED]** (`mcp/server.py:3862-3869`)
- [ ] Write tests: 5 queries per intent type — **[NEEDS-VERIFICATION]** (no test file found in grep; may exist under a different name)

### 4.2 Explicit Path Weights (Phase 95 completion) — **MOSTLY SHIPPED**
- [x] Add `path_weights: Dict[str, float]` to project config schema — **[FIXED]** (`repo_policy.py:132`)
- [x] Backend reads path weights from config in search endpoints — **[FIXED]** (`index.py:1088-1090`)
- [x] Apply path weight multiplier in `search()` — **[FIXED]** (`index.py:1112-1114`)
- [ ] Apply path weight in `assign_lod()` — **[NEEDS-VERIFICATION]** (LOD code not inspected)
- [ ] Apply path weight in atlas routing — **[NEEDS-VERIFICATION]**
- [ ] Apply path weight in trace expansion — **[NEEDS-VERIFICATION]**
- [x] MCP surfaces path weights in responses — **[FIXED: PARTIAL]** (`index.py:694` includes in policy output)
- [ ] Dashboard: verify Knowledge Graph folder selection writes path_weights — **[STILL-OPEN]** — see Phase 111 §5.8. UI likely doesn't write weights; users must edit config JSON or hit API. This is the real consumer-facing gap.
- [ ] Document path weight behavior in generated AGENTS.md — **[PARTIAL]** (feature-gated to FREE tier; full behavior doc pending)

### 4.3 Role-Based Weight Composition
- [x] Ensure `role` param applies role-derived modifiers — **[FIXED: PARTIAL]** (`mcp_tools.py:131-136` surfaces `role`; index uses it)
- [ ] Role resolver maps roles to implicit path-weight overrides — **[NEEDS-VERIFICATION]** (resolver code not located in this pass)
- [ ] `role="ceo"` boosts hub files + atlas summaries — **[NEEDS-VERIFICATION]**
- [ ] Verify role weights compose with explicit path weights (explicit wins) — **[NEEDS-VERIFICATION]**
- [ ] Test: `role="security"` + explicit `{"vendor/": 0.3}` — vendor suppression wins — **[STILL-OPEN]**

### 4.4 Query Signal Wiring — **STILL-OPEN (partial extract only)**
- [x] Extract QuerySignals from query — **[FIXED]** (`index.py:1065-1068`)
- [ ] Wire `QuerySignals.coverage_ratio()` into scoring — **[STILL-OPEN]** (method defined at `query_analyzer.py:54-59`, never called)
- [ ] Implement signal_boost (additive, like hub_boost) — **[STILL-OPEN]**
- [ ] Filter results with 0 keyword coverage below threshold — **[STILL-OPEN]**
- [ ] Test: "fix the login handler in auth.py" ranks `auth.py` higher — **[PARTIAL]** — structural boost exists via `_structural_boosts` but coverage_ratio filtering absent

### 4.5 Chunking Improvements (Phase 93 scoped MVP) — **MOSTLY SHIPPED**
- [ ] Add context header `# File: {path}` to every chunk — **[STILL-OPEN (DECISION NEEDED)]** `extract_file_synopsis()` at `chunking.py:383-429` exists but is used for meta-chunk injection (commit `2da5dafd`), not prepended to every chunk. Decide: commit to per-chunk headers or accept meta-chunk approach as sufficient.
- [x] Implement small-chunk merging — **[FIXED]** (`chunking.py:264-270`, `_semantic_split:173-196`)
- [x] Implement large-function splitting — **[FIXED]** (semantic split at sentence/paragraph boundaries for markdown `chunking.py:162-171`; code chunking uses size-based overlap `chunking.py:351-378`)
- [ ] Measure R@1 impact on `scripts/benchmark_embeddings.py` — **[STILL-OPEN]** (benchmark not run post-shipping)
- [ ] Decide ship/defer based on 3pp improvement — **[MOOT]** — chunking already shipped; re-benchmark retrospectively

### 4.6 Sub-Atlas Role Lens (Phase 104 scoped)
- [ ] Verify sub-atlas segments render in AtlasLensPanel — **[NEEDS-VERIFICATION]**
- [ ] Wire role lens to `codrag(role=...)` — **[NEEDS-VERIFICATION]** (role param supported; atlas rendering per-role not verified)
- [ ] Test `role="security"` focuses on auth subsystems — **[STILL-OPEN]**
- [ ] Run Phase 104 verification tasks (ruff, pytest, typecheck, storybook) — **[STILL-OPEN]**

### 4.7 Query Signal Wiring — **NEW (consolidates the genuine open items)**
The real remaining retrieval work, separated from the stale framing above:

- [ ] Wire `coverage_ratio` into search scoring — additive boost + floor filter
- [ ] EXAMPLE intent: boost test files, prefer usage over definition
- [ ] COMPARE intent: parallel-search both terms, interleave results
- [ ] Audit path-weight propagation: confirm it flows through LOD, atlas routing, trace expansion (or decide scope)
- [ ] Decide on per-chunk context headers (vs current meta-chunk synopsis)
- [ ] Re-benchmark R@1 with current chunking state; publish delta vs pre-`58b8950e`

## 5. Links to Prior Work

| Phase | What it built | Status | Gap this phase addresses |
|---|---|---|---|
| 86 | Intent Classification Design | **SHIPPED** (`6a1134ea`, `9aa5773a`) | EXAMPLE + COMPARE polish remain |
| 93 | Chunking Research (SG filter, contextual retrieval) | **Scoped MVP SHIPPED** (`58b8950e`, `96958308`) | Re-benchmark + context-header decision |
| 95 | Path Weights TODO | **Config + search ranking SHIPPED** | LOD/atlas/trace propagation audit + dashboard UI remain |
| 104 | Sub-Atlas & Role Lens | 0/6 tasks done | Section 4.6 |
| 28 | Context Window Research (Adaptive-K, MMR, min_score) | Research complete | Foundation for signal wiring (4.4) |
| 33 | Embedding model eval (v1.5 ONNX confirmed) | Complete | Chunking changes need re-benchmark |
| 34 | Context-First Architecture (scope boost, trace-always-on) | Complete | Foundation for intent routing |
| 39 | Invisible Upgrades (intent-aware search, edge weights) | Complete | Intent detection exists but limited |

## 6. Success Criteria

1. Intent classifier correctly routes >= 80% of test queries to the right strategy
2. `codrag_search` with LOCATE intent finds the correct file in top-1 for symbol queries
3. `codrag_search` with RATIONALE intent returns concepts when they exist
4. Path weights propagate through search, LOD, atlas routing, and trace expansion
5. R@1 on benchmark suite improves >= 3pp from chunking improvements
6. Marketing claim "path weights" is verified as implemented end-to-end

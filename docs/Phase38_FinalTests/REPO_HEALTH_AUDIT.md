# CoDRAG Repo Health Audit — Feb 23, 2026

## Executive Summary

Four test repositories were audited end-to-end: TEST (small Next.js), TEST2 (medium docs+website), TEST3 (large multi-platform app), and slim-php (open-source PHP framework). All repos completed the full pipeline and produce usable context. However, several systemic issues were identified that reduce trace graph quality and MCP output relevance.

**Overall Health Grades:**

| Repo | Pipeline | Trace Graph | Clustering | Search Relevance | Ambient Context | Grade |
|------|----------|-------------|------------|-----------------|-----------------|-------|
| TEST | ✅ Full | ⚠️ Sparse | ⚠️ 1 module | ✅ Good | ✅ Good | B |
| TEST2 | ✅ Full | ⚠️ Sparse | ✅ 6 modules | ✅ Good (routed) | ✅ Good | B+ |
| TEST3 | ✅ Full | ⚠️ Low cross-file | ❌ Auth=136 files | ⚠️ Relevance miss | ✅ Good | B- |
| slim-php | ✅ Full | ❌ 0 cross-file edges | ✅ 9 modules | ✅ Good (routed) | ✅ Good | C+ |

---

## 1. Pipeline Completeness

All 4 repos have every expected pipeline artifact:

| Artifact | TEST | TEST2 | TEST3 | slim-php |
|----------|------|-------|-------|----------|
| trace_nodes.jsonl | ✅ 97 | ✅ 307 | ✅ 1334 | ✅ 1138 |
| trace_edges.jsonl | ✅ 127 | ✅ 307 | ✅ 1639 | ✅ 1558 |
| trace_augmented.jsonl | ✅ 89 | ✅ 288 | ✅ 1223 | ✅ 999 |
| trace_inferred_edges.jsonl | ✅ | ✅ | ✅ | ✅ 822 |
| trace_epistemic.jsonl | ✅ 43 | ✅ 135 | ✅ 249 | ✅ 135 |
| trace_modules.jsonl | ✅ 1 | ✅ 6 | ✅ 18 | ✅ 9 |
| atlas.json | ✅ structural | ✅ LLM | ✅ LLM | ✅ LLM |
| atlas_routing.json | ❌ too small | ✅ | ✅ | ✅ |
| documents.json (CodeIndex) | ✅ 46 | ✅ 59 | ✅ 61 | ✅ 27 |
| knowledge_documents.json | ✅ 132 | ✅ 423 | ✅ 1472 | ✅ 1134 |
| embeddings.npy | ✅ | ✅ | ✅ | ✅ |

**Finding P-1**: All pipeline stages ran. Zero `files_failed` across all repos. Augmentation model: `qwen3:8b`, Atlas model: `qwen3-30b-a3b-thinking`.

---

## 2. Trace Graph Quality

### 2.1 Edge Connectivity — CRITICAL ISSUES

| Metric | TEST | TEST2 | TEST3 | slim-php |
|--------|------|-------|-------|----------|
| Files parsed | 44 | 135 | 248 | 135 |
| Nodes | 97 | 307 | 1334 | 1138 |
| Static edges | 127 | 307 | 1639 | 1558 |
| Edge kinds | imports:69, contains:58 | imports:154, contains:153 | contains:975, imports:664 | contains:864, imports:694 |
| **Cross-file import edges** | **11** | **~5** | **~54** | **0** |
| Same-file import edges | ~1 | 0 | 0 | 0 |
| **Dangling import edges** | **~57** | **~149** | **~610** | **694** |
| Files with 0 neighbors | 27/44 (61%) | 107/135 (79%) | 195/249 (78%) | **135/135 (100%)** |

**🔴 Finding T-1: PHP parser produces ZERO cross-file edges.** All 694 import edges in slim-php are dangling (source or target node has no `file_path`). The Rust parser doesn't resolve PHP `use` statements to file paths. This means trace expansion is completely non-functional for PHP repos. The inferred_edges stage partially compensates (822 inferred edges), but these don't flow through the standard hub/neighbor analysis.

**🔴 Finding T-2: External nodes fail trace validation.** `run_tests.py` raises `Node ext:gsap missing required field: file_path` for TEST. External dependency nodes (prefixed `ext:`) have no file_path by design, but the validator doesn't account for this. The validator should skip `ext:*` nodes or treat `file_path` as optional for external nodes.

**🟡 Finding T-3: Very high dangling-edge ratio across ALL repos.** Even for TEST (TypeScript/JavaScript), 57 of 69 import edges are dangling. This means the parser creates import edges targeting external packages (e.g., `react`, `gsap`, `next`) that don't resolve to in-project files. These edges are wasted — they don't contribute to trace expansion or neighbor discovery. The hub file analysis is misleadingly thin because of this.

**🟡 Finding T-4: Most files have 0 neighbors.** 61-100% of files have zero file-level neighbors. For small repos this is somewhat expected, but for TEST3 (248 files) having 78% with 0 neighbors means the trace graph is essentially disconnected at the file level.

### 2.2 Inferred Edges (LLM-generated)

| Repo | Inferred edges | Kinds |
|------|---------------|-------|
| TEST | present (size suggests ~100s) | — |
| TEST2 | present | — |
| TEST3 | present | — |
| slim-php | 822 | implements:257, calls:415, dispatches:136, configures:14 |

The inferred edges stage is working and generating meaningful relationships (especially for PHP where static parsing fails). However, **inferred edges are not loaded into the hub file analysis or neighbor expansion**. They exist in `trace_inferred_edges.jsonl` but the hub analysis script only reads `trace_edges.jsonl`.

**🟡 Finding T-5**: Inferred edges aren't included in hub/neighbor file-level analysis. Need to verify they're loaded by `TraceIndex` for search-time trace expansion.

### 2.3 External Nodes

| Repo | External nodes | % of total |
|------|---------------|------------|
| TEST | 8 | 8.2% |
| TEST2 | 19 | 6.2% |
| TEST3 | 110 | 8.2% |
| slim-php | 139 | 12.2% |

These are fine — they represent imports from external packages. The issue is only that the validator doesn't handle them.

---

## 3. Augmentation Quality

| Metric | TEST | TEST2 | TEST3 | slim-php |
|--------|------|-------|-------|----------|
| Total augmented | 89 | 288 | 1223 | 999 |
| LLM-augmented | 52 (58%) | 183 (64%) | 1067 (87%) | 525 (53%) |
| Synthetic (empty_source) | 37 (42%) | 105 (36%) | 156 (13%) | 474 (47%) |
| Failed | 0 | 0 | 1 | 0 |
| Avg confidence | 0.57 | 0.60 | 0.77 | 0.50 |
| Median confidence | 0.85 | 0.85 | 0.85 | 0.85 |
| Avg summary length | 90 chars | 91 chars | 104 chars | 83 chars |

**🟡 Finding A-1: High synthetic rate in TEST/TEST2/slim-php (36-47%).** Synthetic entries are generated for nodes where the source file is empty or unreadable. The `empty_source` reason suggests the augmenter couldn't read the file content for these nodes. For slim-php this is likely because many nodes are symbols within PHP files that the augmenter couldn't extract source for.

**🟡 Finding A-2: Bimodal confidence distribution.** Avg confidence is 0.50-0.60 but median is 0.85 across all repos. This means synthetic entries (confidence ~0.0-0.3) pull the average down while real LLM augmentations cluster around 0.85.

---

## 4. Epistemic Enrichment (Deep Reasoning)

| Metric | TEST | TEST2 | TEST3 | slim-php |
|--------|------|-------|-------|----------|
| Enriched nodes | 43 | 135 | 249 | 135 |
| Mean composite score | 0.647 | 0.623 | 0.618 | 0.568 |
| Median composite score | 0.651 | 0.645 | 0.645 | 0.565 |
| Settled (≥0.60) | 39 (91%) | 92 (68%) | 167 (67%) | **27 (20%)** |
| Tech debt detected | 0 | 2 | 10 | 1 |
| Design patterns detected | 19 (44%) | 8 (6%) | 71 (29%) | 33 (24%) |

**🔴 Finding E-1: slim-php has only 20% settled nodes.** The low composite score (0.568 mean) is driven by low cross-reference density (0/4 = 0 for all nodes since PHP has 0 cross-file edges) and low neighbor coverage (no enriched neighbors reachable). This is downstream of the PHP parser issue (T-1).

**🟢 Finding E-2: TEST has 91% settled — good convergence.** The small project size and interconnected TSX components help.

---

## 5. Clustering (Module Synthesis)

| Repo | Modules | Largest module | Issue |
|------|---------|---------------|-------|
| TEST | 1 | Ui (43 files) | Only 1 module = no segmentation |
| TEST2 | 6 | Ui (94 files) | Ui is catch-all |
| TEST3 | 18 | **Auth (136 files)** | Auth is mega-module |
| slim-php | 9 | Routing (67 files) | 2 duplicate "Http" modules |

**🔴 Finding C-1: TEST3 "Auth" module contains 136 of 248 files (55%).** This is a clustering failure. The module has 150+ domain tags — it's a catch-all that swallowed most of the project. The cluster synthesizer should have a maximum module size threshold or should split modules that exceed it.

**🟡 Finding C-2: Duplicate module names.** TEST3 has two "Ui" modules (3 and 4 files). slim-php has two "Http" modules (17 and 4 files). These should either be merged or given distinguishing names.

**🟡 Finding C-3: TEST has only 1 module.** For a 44-file project this might be acceptable, but it means the atlas and ambient context have no segmentation to work with.

---

## 6. Atlas Quality

| Repo | Mode | Content quality | Issue |
|------|------|----------------|-------|
| TEST | structural | ✅ Clean, factual | No routing (too small) |
| TEST2 | LLM | ❌ Leaked `<think>` tokens | **LLM thinking leaked** |
| TEST3 | LLM | ✅ Clean, factual | Good |
| slim-php | LLM | ❌ Leaked `<think>` tokens | **LLM thinking leaked** |

**🔴 Finding AT-1: Atlas content contains raw LLM thinking tokens.** TEST2 and slim-php atlas.json `content` fields start with `<think>` followed by the model's internal reasoning chain. This is injected directly into the context that the AI receives. The atlas generator should strip `<think>...</think>` tags from LLM output.

- TEST2 atlas content starts with: `"<think>\nWe are given specific data to use..."`
- slim-php atlas content starts with: `"<think>\nWe are given specific sections to write..."`

This wastes context tokens and could confuse the consuming AI.

**needs testing with different LLMs** currently testing hopephoto/qwen3-30b-a3b-thinking_q8:latest 

---

## 7. Search & Context Quality (MCP Tooling)

### 7.1 codrag_search (query-based context)

All 4 repos return context successfully with the context endpoint. Atlas routing works for TEST2, TEST3, and slim-php (all routed to 3 segments).

| Repo | Query | Context len | Relevant? |
|------|-------|-------------|-----------|
| TEST | "hero section animation" | 6069 chars | ✅ Returns EnhancedHero.tsx |
| TEST2 | "checkout payment flow" | 6069 chars | ✅ Returns checkout/page.tsx |
| TEST3 | "Spotify OAuth authentication" | 6069 chars | **⚠️ Returns audio_analysis.py** |
| slim-php | "routing middleware HTTP requests" | 6014 chars | ✅ Returns RoutingMiddleware.php |

**🔴 Finding S-1: TEST3 Spotify OAuth query returns audio_analysis.py as top result.** The query "How does the Spotify OAuth authentication work?" should return `backend/src/api/spotify_oauth.py` but instead returns `backend/src/ai/audio_analysis.py`. This suggests:
- The CodeIndex only has 61 chunks for a 248-file project (many files not in knowledge base)
- The knowledge_documents.json has 1472 chunks but CodeIndex (documents.json) has only 61
- The search is running against the CodeIndex (documents.json + embeddings.npy), which only indexes files selected in the knowledge tree

**🟡 Finding S-2: CodeIndex chunk count is very low relative to knowledge index.** This is by design (CodeIndex = user-selected files, KnowledgeIndex = full project), but it means codrag_search only returns context from a small subset of files.

| Repo | CodeIndex chunks | KnowledgeIndex chunks | Ratio |
|------|------------------|-----------------------|-------|
| TEST | 46 | 132 | 35% |
| TEST2 | 59 | 423 | 14% |
| TEST3 | 61 | 1472 | **4%** |
| slim-php | 27 | 1134 | **2%** |

For TEST3 and slim-php, the CodeIndex only covers 2-4% of the knowledge chunks. If a user asks about a file not in their knowledge tree selection, `codrag_search` will miss it entirely.

### 7.2 codrag (ambient context)

All 4 repos return ambient context successfully with modules, hub files, and neighbor information.

| Repo | Ambient len | Modules | Hub files |
|------|-------------|---------|-----------|
| TEST | 4211 chars | ✅ Ui | ✅ |
| TEST2 | 3245 chars | ✅ Ui, Legal, etc. | ✅ |
| TEST3 | 3959 chars | ✅ Auth, Music Integration | ✅ |
| slim-php | 3956 chars | ✅ Routing, Error Handling | ✅ |

Ambient context quality is good across the board. Module summaries are concise and relevant.

### 7.3 hi_codrag

Not tested via API (requires MCP protocol), but the tool definition and handler code look correct. The tool aggregates status, included paths, hub files, and coverage data into a conversational summary.

---

## 8. Identified Improvements (Priority Ordered)

### P0 — Critical (affects core functionality)

| ID | Issue | Impact | Fix complexity |
|----|-------|--------|----------------|
| T-1 | PHP parser produces 0 cross-file edges | Trace expansion non-functional for PHP | High — needs PHP namespace/use resolution in Rust parser |
| AT-1 | Atlas content leaks `<think>` tokens | Wasted context tokens, confusing AI output | Low — strip `<think>.*?</think>` from LLM atlas output |
| C-1 | Auth mega-module (136/248 files in TEST3) | Useless clustering, bad ambient context segmentation | Medium — add max_module_size threshold + splitting logic |
| S-1 | Search misses relevant files (TEST3 Spotify OAuth) | User gets wrong context for targeted queries | Design issue — CodeIndex only searches selected files |

### P1 — Important (reduces quality)

| ID | Issue | Impact | Fix complexity |
|----|-------|--------|----------------|
| T-3 | High dangling-edge ratio (external package imports) | Inflated edge count, thin neighbor graph | Medium — filter ext: targets from import edge creation, or resolve to ext: nodes |
| T-5 | Inferred edges not in hub/neighbor analysis | Missing connectivity data at search time | Low — verify TraceIndex loads inferred edges for search |
| T-2 | Trace validator rejects external nodes | Can't run validation on any repo with ext: deps | Low — skip ext:* nodes or make file_path optional for them |
| E-1 | slim-php 20% settled (downstream of T-1) | Low epistemic quality for PHP repos | Resolves when T-1 is fixed |

### P2 — Quality of life

| ID | Issue | Impact | Fix complexity |
|----|-------|--------|----------------|
| A-1 | High synthetic augmentation rate (36-47%) | Lower confidence averages, weaker summaries | Medium — investigate empty_source cause per language |
| C-2 | Duplicate module names | Confusing in ambient context | Low — append segment prefix or dedup logic |
| C-3 | Single-module repos | No segmentation benefit | By design for small repos — acceptable |
| S-2 | CodeIndex/KnowledgeIndex ratio (2-4% for large repos) | Search only covers selected files | Design decision — document for users |

---

## 9. Existing Test Scripts Assessment

| Script | What it tests | Covers our repos? |
|--------|--------------|-------------------|
| `smoke_test_repos.py` | CodeIndex build + 1 search probe | Real repos only, not TEST/TEST2/TEST3 |
| `analyze_quality.py` | Augmentation, epistemic, clustering, knowledge stats | ✅ Works on all repos |
| `analyze_hub_files.py` | Hub file identification + neighbor stats | ✅ Works on all repos |
| `run_tests.py` | Trace validation (schema) + pytest | ⚠️ Fails on ext: nodes |
| `eval_real_repos.py` | Full embedding benchmark with ground-truth | Real repos only |
| `benchmark_embeddings.py` | Embedding model comparison | Synthetic queries |

**Missing test coverage:**
1. No end-to-end MCP tool testing (codrag_search, codrag, hi_codrag)
2. No search relevance regression tests (query → expected top file)
3. No atlas content quality checks (e.g., no `<think>` tokens)
4. No clustering quality assertions (max module size, no duplicates)
5. No cross-file edge connectivity assertions per language

---

## 10. Recommended Test Harness

A new `scripts/repo_health_check.py` should be created that runs against any repo's `.codrag/` directory and produces a structured report with pass/fail assertions:

1. **Pipeline completeness**: all expected artifacts exist
2. **Trace graph health**: edge connectivity ratio, dangling edge %, files with 0 neighbors
3. **Augmentation quality**: synthetic rate < 50%, avg confidence > 0.5
4. **Epistemic convergence**: settled % > 50%
5. **Clustering quality**: no module > 40% of files, no duplicate names
6. **Atlas quality**: no `<think>` tokens, content < 2000 chars
7. **Search relevance**: per-repo probe queries with expected file in top-3
8. **Context assembly**: ambient context returns modules + hub files

---

*Generated: 2026-02-23T07:37 EST*
*Repos analyzed: TEST, TEST2, TEST3, slim-php*
*Daemon: http://127.0.0.1:8400*

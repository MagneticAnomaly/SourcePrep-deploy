# Atlas Opportunities: Research-Backed Design for LLM Codebase Understanding

> What do LLMs actually need when they encounter an unfamiliar codebase? How can Prep's atlas be the most effective possible structural primer -- and what new opportunities does the trend toward larger context windows unlock?

**Created:** 2026-03-14
**Based on:** SWE-QA (arXiv:2509.14635), DependEval (arXiv:2503.06689), "On the Impacts of Contexts on Repository-Level Code Generation" (ACL 2025), Prep Phase 34/50 architecture

---

## 1. Academic Research: What LLMs Struggle With

### SWE-QA Developer Question Taxonomy (127,415 real questions, 11 repos)

| Question Type | % | What LLM Needs | Prep Data Source |
|--------------|---|----------------|-------------------|
| **How** (implementation, data flow, algorithms) | 35.2% | Flow paths, entry points, call chains | trace_edges.jsonl, inferred_edges, module summaries |
| **Where** (feature location, identifiers, data flows) | 28.4% | File-to-feature mapping, symbol locations | trace_nodes.jsonl, hub files, module-file assignments |
| **Why** (design rationale, purpose) | 23.1% | Module summaries, enriched descriptions | trace_augmented.jsonl (Stage 3), epistemic (Stage 6) |
| **What** (definitions, architecture summaries) | 13.3% | Atlas IDENTITY, STACK, ARCHITECTURE sections | atlas.json (Stage 9) |

### DependEval Findings (LLM dependency understanding benchmark)

- **LLMs struggle with directory structure** -- they can't organize hierarchical projects or understand which directories correspond to which subsystems
- **Cross-file modifications remain challenging** -- editing File A without knowing it breaks File B
- **Import chain resolution degrades at 3+ hops** -- LLMs lose track of A -> B -> C -> D chains
- **Circular dependencies confuse all tested models** -- they can't reason about bidirectional coupling

### "On the Impacts of Contexts" (ACL 2025 Findings)

- **Cross-file context improves code generation by 15-30%** when the right files are selected
- **Random context is worse than no context** -- quality of context selection matters more than quantity
- **Import-based context retrieval outperforms embedding-based** for code completion tasks
- **Trace-expanded context (our approach) is the gold standard** -- following actual dependency edges

---

## 2. Data Available at Each Pipeline Stage

| Stage | ID | Data Produced | Available for Atlas |
|-------|------|---------------|---------------------|
| 1 | STRUCTURAL | trace_nodes.jsonl, trace_edges.jsonl, trace_manifest.json | File tree, import graph, hub files, languages, subsystem dirs |
| 2 | INFERRED_EDGES | inferred_edges.jsonl | Semantic relationships beyond imports (call patterns, shared types) |
| 3 | CATALOGUE | trace_augmented.jsonl | LLM-generated file summaries (1-2 sentence purpose per file) |
| 4 | VALIDATION | validation results | Correctness scores, confidence levels |
| 5 | KNOWLEDGE | knowledge index | Embedded chunks, search index |
| 6 | ENRICHMENT | trace_epistemic.jsonl | Architecture layers, domain tags, epistemic confidence |
| 7 | GROUP_REASONING | group reasoning results | Cross-file relationship narratives |
| 8 | CLUSTERING | trace_modules.jsonl | Module assignments, module summaries |
| 9 | ATLAS | atlas.json | Full architectural overview (current LLM atlas) |
| 10 | DEEPENING | deepened augmentations | Enhanced file descriptions with cross-references |
| 11 | DEEP_KNOWLEDGE | re-indexed knowledge | Updated search index with richer content |

---

## 3. Opportunities: Structural (Preliminary) Atlas

The structural atlas is generated after Stage 1 with NO LLM calls (~100ms). It's the "first impression" -- what the AI sees before the full pipeline completes.

### OPP-S1: Inter-Subsystem Dependency Arrows (IDENTIFIED)
**Data source:** trace_edges.jsonl (Stage 1)
**What:** Add "A -> B, C" style dependency lines showing which subsystems import from which others.
**Why:** DependEval shows LLMs fail at cross-file dependency reasoning. Explicitly stating "api/ depends on core/ and models/" gives the LLM a dependency map it can't infer from file names alone.
**Token cost:** ~30 tokens (one line per subsystem pair)
**Priority:** HIGH

### OPP-S2: Entry Point Detection
**Data source:** trace_nodes.jsonl (Stage 1)
**What:** Identify likely entry points: files named main.py, app.py, index.ts, server.py, cli.py, __main__.py, or files with 0 in-degree (nothing imports them, they import many things).
**Why:** "Where does execution start?" is the #1 question a developer asks on a new codebase (falls in the 28.4% "Where" category). Entry points are the natural starting point for understanding flow.
**Token cost:** ~20 tokens
**Priority:** HIGH

### OPP-S3: File Count per Language
**Data source:** trace_nodes.jsonl language extension counts (Stage 1)
**What:** Instead of just listing extensions with counts, add percentage and primary/secondary classification. "Python (78%), TypeScript (15%), Rust (7%)" reads better than ".py: 312, .ts: 60, .rs: 28"
**Token cost:** Same (reformatted)
**Priority:** MEDIUM

### OPP-S4: Test Directory Detection
**Data source:** trace_nodes.jsonl file paths (Stage 1)
**What:** Detect test directories (tests/, test/, __tests__/, spec/) and report "Tests: 45 files in tests/" as a SUBSYSTEMS entry. LLMs often hallucinate test file paths -- telling them where tests actually live prevents this.
**Why:** Avoids the common LLM failure mode of creating tests in wrong directories or missing existing test infrastructure.
**Token cost:** ~15 tokens
**Priority:** MEDIUM

### OPP-S5: Config/Build File Inventory
**Data source:** trace_nodes.jsonl (Stage 1)
**What:** List config files at project root: pyproject.toml, package.json, Cargo.toml, docker-compose.yml, etc. These reveal the build system and deployment model.
**Why:** "What" questions (13.3%) often ask about tooling and config. A developer immediately wants to know "Is this managed by npm or yarn? Does it use Docker?"
**Token cost:** ~20 tokens
**Priority:** LOW (the LLM can discover these via native file reading)

---

## 4. Opportunities: Enriched (LLM) Atlas

The enriched atlas is generated at Stage 9 using all data from Stages 1-8 + an LLM call. It currently produces IDENTITY, STACK, ARCHITECTURE, SUBSYSTEMS, FLOW, PATTERNS, RISKS sections.

### OPP-E1: API Surface Map
**Data source:** trace_augmented.jsonl summaries + trace_nodes.jsonl kinds (Stage 3)
**What:** A dedicated section listing the public API surface: REST endpoints (from router/controller files), CLI commands (from argparse/click files), exported classes/functions. "Where do external consumers touch this codebase?"
**Why:** 35.2% of questions are "How" -- many of these are "How does X get called?" Having the API surface explicitly listed means the AI knows the external contract immediately.
**Token cost:** ~60-100 tokens
**Priority:** HIGH

### OPP-E2: Data Model Section
**Data source:** trace_nodes.jsonl (model/schema files), trace_augmented.jsonl summaries
**What:** Identify model files (models.py, schema.py, types.ts, entities/) and list the core data types. "The primary data models are: Project, User, Build, TraceNode."
**Why:** Data models are the vocabulary of a codebase. Without knowing the core types, the AI can't reason about data flow ("How does a Project become a Build?"). This is central to the 35.2% "How" questions.
**Token cost:** ~40-60 tokens
**Priority:** HIGH

### OPP-E3: Dependency Direction Summary
**Data source:** trace_edges.jsonl edge kinds + inferred_edges.jsonl (Stages 1-2)
**What:** Summarize the edge kinds: "547 imports, 312 calls, 89 type references, 34 inheritance edges." This tells the AI what kinds of relationships exist and their relative density.
**Why:** DependEval shows LLMs don't understand *types* of dependencies -- they conflate imports with calls with inheritance. Quantifying edge kinds helps the AI reason about what "connected" means in this specific codebase.
**Token cost:** ~25 tokens
**Priority:** MEDIUM

### OPP-E4: Circular Dependency Warnings
**Data source:** trace_edges.jsonl (cycle detection, Stage 1-2)
**What:** If the trace graph contains cycles, list them. "CIRCULAR: core/index.py <-> core/trace.py (import cycle)." Even just the count: "3 import cycles detected."
**Why:** DependEval specifically found circular dependencies confuse all tested models. Flagging them in the atlas means the AI won't naively assume a clean DAG when it's not.
**Token cost:** ~20 tokens
**Priority:** MEDIUM

### OPP-E5: Module Relationship Matrix
**Data source:** trace_modules.jsonl + trace_edges.jsonl (Stage 8)
**What:** After modules are computed, show which modules depend on which: "Core Engine -> API Layer, Dashboard. API Layer -> Core Engine. Dashboard -> API Layer, Core Engine."
**Why:** This is the enriched version of OPP-S1. With actual module names (not just directories), the dependency map becomes semantically meaningful.
**Token cost:** ~50-80 tokens
**Priority:** HIGH

### OPP-E6: Confidence/Quality Indicators
**Data source:** trace_epistemic.jsonl (Stage 6)
**What:** Report the average epistemic confidence and any files flagged as uncertain. "Confidence: 0.87 avg across 312 files. 5 files flagged as low-confidence (<0.3)."
**Why:** This helps the AI calibrate trust. If it knows certain areas are well-documented vs. poorly-understood, it can adjust its recommendations accordingly.
**Token cost:** ~20 tokens
**Priority:** LOW

---

## 5. The Larger Context Window Opportunity

### The Trend
- Claude Sonnet 4: 200K tokens
- GPT-4o: 128K tokens  
- Gemini 2.5: 1M tokens
- Many models trending toward 500K-1M token windows by late 2026

### What This Means for Prep

Our current design is optimized for token scarcity (~300-600 token atlas, ~12K context response). With 200K+ windows, the constraint shifts from "fit in the window" to "don't overwhelm with noise." The opportunities:

### OPP-W1: Tiered Atlas (Compact + Extended)
**What:** Generate two versions of the atlas:
- **Compact** (~300 tokens): Current size. Used in rules files (always-on, every prompt).
- **Extended** (~2,000-4,000 tokens): Richer version returned by the `prep` tool call. Includes all the new sections (API surface, data models, module relationships, flow details).

**Why:** The rules file atlas is always in context (every single prompt), so it must stay compact. But when the AI explicitly calls `prep`, it's asking for structural context -- we can be much more generous. With 200K windows, a 4K token atlas is 2% of the budget.

### OPP-W2: Per-Subsystem Deep Dives
**What:** When the AI calls `prep_search` for files in a specific subsystem, include the segment atlas for that subsystem in the response. This is already supported by the segmented atlas (ROOT_ATLAS + SEGMENT_ATLAS in prompts.py) but not yet wired to the MCP tool responses.
**Why:** With large windows, we can afford to send the full segment atlas (~500-1,000 tokens per segment) alongside search results. The AI gets both the answer and the architectural context for that area.

### OPP-W3: File Summary Injection
**Data source:** trace_augmented.jsonl (Stage 3 -- LLM-generated 1-2 sentence summaries per file)
**What:** When returning hub files in the `prep` response, include each file's augmented summary alongside its LOD-compressed content. Currently hub files show compressed code; with larger windows we can prepend "This file handles X, imports Y, exports Z" from the augmentation data.
**Why:** This directly addresses the 28.4% "Where" question type. Instead of the AI having to read compressed code to understand what a file does, it gets a pre-computed summary.

### OPP-W4: Call Chain Visualization
**Data source:** trace_edges.jsonl + inferred_edges.jsonl
**What:** For the extended atlas, include the top 5-10 call chains by depth. "Request flow: server.py -> router.py -> handler.py -> service.py -> repository.py -> models.py"
**Why:** This directly addresses the 35.2% "How" question type. Multi-hop call chains are exactly what DependEval found LLMs fail at. Pre-computing and presenting them eliminates the need for the AI to trace imports manually.

### OPP-W5: Adaptive Token Budget
**What:** Detect the AI tool's likely context window size from clientInfo (captured in MCP initialize) and adjust the atlas/context token budget accordingly:
- Cursor/Windsurf (Claude Sonnet 4, 200K): Extended atlas + generous context
- Claude Code (200K): Full extended atlas
- Cline with local LLM (8K-32K): Compact atlas only, aggressive LOD compression
- Gemini CLI (1M): Send everything -- full segment atlases, all file summaries

**Why:** One size doesn't fit all. A local Ollama model with 8K context needs a very different atlas than Gemini with 1M tokens. Prep already captures clientInfo -- we can use it to tier the response.

---

## 6. Priority Matrix

### Implemented (Phase 50, 2026-03-14)

| OPP | Description | Atlas Type | Tokens | Status |
|-----|------------|------------|--------|--------|
| S1 | Inter-subsystem dependency arrows | Structural | ~30 | DONE -- `_load_graph_stats` computes `dir_dependencies`, `_build_structural_content` renders DEPENDENCIES section |
| S2 | Entry point detection | Structural | ~20 | DONE -- detects common entry names + 0-in-degree/high-out-degree files |
| S3 | Language percentages | Structural | ~0 | DONE -- STACK now shows ".py 78%" instead of ".py: 312" |
| S4 | Test directory detection | Structural | ~15 | DONE -- detects tests/, test/, __tests__/, spec/ directories |
| E1 | API surface map | Enriched | ~80 | DONE -- added API SURFACE section to LLM atlas prompt |
| E2 | Data model section | Enriched | ~50 | DONE -- added DATA MODELS section to LLM atlas prompt |
| E3 | Dependency direction summary | Enriched | ~25 | DONE -- `edge_kinds` computed and rendered in EDGE TYPES section + fed to LLM prompt |
| E4 | Circular dependency warnings | Enriched | ~20 | DONE -- bidirectional edge detection, CIRCULAR DEPS section |
| E5 | Module relationship matrix | Enriched | ~60 | DONE -- MODULE DEPENDENCIES section in LLM prompt + dir_dependencies in graph stats |
| W1 | Tiered atlas (compact + extended) | Both | -- | DONE -- `tool_context()` requests `include_atlas=True`, compact stays in rules files |

### Also Implemented (Phase 50, 2026-03-14)

| OPP | Description | Atlas Type | Tokens | Status |
|-----|------------|------------|--------|--------|
| W2 | Per-subsystem deep dives in search | MCP | -- | DONE -- `tool_search()` detects >60% result clustering in one dir, prepends `[Subsystem focus: dir/]` hint |
| W3 | File summary injection | MCP | -- | DONE -- `include_sources=True` sends augmented summaries; W2 adds subsystem orientation |
| W4 | Call chain visualization | Structural+Enriched | ~100 | DONE -- BFS from entry points in `_load_graph_stats`, CALL CHAINS section + fed to LLM prompt |
| W5 | Adaptive token budget from clientInfo | MCP | -- | DONE -- `_get_context_budget()` with 10 client patterns (Gemini 24K, Claude 18K, Cursor 14K, Cline 10K) |
| E6 | Confidence/quality indicators | Structural | ~20 | DONE -- CONFIDENCE section from epistemic `avg_confidence` + file count |

**All 15 opportunities are now implemented.**

---

## 7. Design Principle: Atlas as "Mental Model Primer"

The research converges on a single insight: **an LLM encountering an unfamiliar codebase is like a senior developer on their first day.** Both need the same things:

1. **What is this?** (IDENTITY) -- 5 seconds
2. **What's it built with?** (STACK) -- 10 seconds
3. **What are the major parts?** (SUBSYSTEMS) -- 30 seconds
4. **How do they connect?** (ARCHITECTURE/FLOW) -- 2 minutes
5. **What are the important files?** (HUB FILES) -- 5 minutes
6. **Where do I find specific things?** (API surface, data models) -- ongoing

The atlas should deliver layers 1-4 in the compact version (~300 tokens, always-on in rules file), and layers 1-6 in the extended version (~2,000-4,000 tokens, returned by `prep` tool call).

This layered approach means:
- **Every prompt** gets the mental model (layers 1-4 via rules file)
- **First tool call** gets the full picture (layers 1-6 via `prep` response)
- **Subsequent queries** get targeted context (per-subsystem deep dives via `prep_search`)

The larger context window trend makes layers 5-6 viable on every tool call, not just occasionally. When Gemini 2.5 with 1M tokens is the norm, we can send the entire extended atlas + all segment atlases + file summaries in a single `prep` response and still use less than 1% of the context window.

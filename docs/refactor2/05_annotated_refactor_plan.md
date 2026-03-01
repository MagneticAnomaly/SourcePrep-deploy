# Annotated Refactor Plan — With Purpose Research

Each refactoring target below includes:
- **What it is** — structural contents
- **Why it exists** — design rationale, referenced from docs or inferred from context
- **Who depends on it** — downstream consumers
- **What we'd change** — proposed split
- **Risk notes** — things that could break

---

## 1. `src/codrag/core/trace.py` (2,460 lines)

### What It Is
The trace graph subsystem — CoDRAG's structural backbone. Contains:

| Component | Lines | Purpose |
|-----------|-------|---------|
| `TraceNode`, `TraceEdge`, `FileError`, `TraceBuildResult` | 1–130 | Graph data model. Frozen schema shared across Rust and Python backends. |
| 20 language extension sets + `SUPPORTED_EXTENSIONS` | 42–67 | File type detection constants for all 20 supported languages. |
| `_detect_language()`, `_to_posix()`, `_is_relevant()` | 133–204 | Shared utility functions used by both `TraceBuilder` and `compute_trace_coverage()`. |
| `PythonAnalyzer` | 207–422 | **AST-based** Python parser using `ast.parse()`. Extracts functions, classes, methods, imports (absolute + relative). Resolves relative imports against the repo root filesystem. Highest-fidelity analyzer. |
| `SwiftAnalyzer` | 425–539 | **Regex-based** Swift parser. Extracts `class/struct/enum/protocol/func` symbols and `import` statements. Lower confidence (0.8) due to regex limitations. |
| `GenericRegexAnalyzer` | 542–768 | **Configurable regex** for 14 languages (Kotlin, C#, Ruby, PHP, Dart, Scala, Lua, Zig, Elixir, Shell, Go, Rust, Java, C, C++). `LANGUAGE_CONFIGS` dict maps language → regex patterns. 130 lines of data. |
| `JSAnalyzer` | 770–1002 | **Regex-based** JS/TS parser. Handles ES6 import/export, CommonJS require, JSX class/function components. Most complex regex analyzer. |
| `TraceBuilder` | 1004–1590 | Orchestrates file scanning, dispatches to the correct analyzer per language, writes JSONL output. Has a `_build_rust()` path that delegates to the Rust engine when available. Contains **duplicate external module handling** across 4 dispatch branches. |
| `TraceIndex` | 1595–2130 | **Query interface** for the built graph. Dual backend: Rust `TraceHandle` vs Python dicts. Methods: `load()`, `search_nodes()`, `get_neighbors()`, `node_degree()`, `status()`, `get_node()`, `get_file_skeleton()`. Loads 3 edge files (static, inferred, LSP). |
| `build_trace()` | 2131–2160 | Convenience entry point wrapping `TraceBuilder`. |
| `compute_trace_coverage()` | 2161–2461 | **Coverage analysis** — walks filesystem, compares against manifest file hashes, classifies files as traced/untraced/stale/excluded. Includes Rust manifest backfill migration logic. |

### Why It Exists This Way
- **Python fallback analyzers exist because the Rust engine wasn't available initially.** The Rust engine (`codrag-parser` crate) now handles Python/TS/JS/Go/Rust/Java/C/C++ via tree-sitter but the Python path remains for: (a) resilience when the Rust wheel isn't installed, (b) languages the Rust engine doesn't cover yet (Swift, Kotlin, C#, Ruby, PHP, Dart, Scala, Lua, Zig, Elixir, Shell).
- **Dual backend pattern**: `TraceIndex` checks `_ENGINE == "rust"` at every method. This is intentional — the Rust engine is optional and may not be installed.
- **`compute_trace_coverage()` is here** because it needs `_detect_language()`, `stable_file_hash()`, and the same extension constants. It's consumed by the trace router and the MCP `hi_codrag` tool.

### Who Depends On It
- `src/codrag/api/routers/trace.py` — all `/trace/*` endpoints
- `src/codrag/api/routers/projects.py` — coverage, status, build
- `src/codrag/services/pipeline_orchestrator.py` — structural stage worker
- `src/codrag/services/build_manager.py` — trace build thread
- `src/codrag/core/augmenter.py` — reads trace nodes for augmentation
- `src/codrag/core/index.py` — `get_context_with_trace_expansion()` uses TraceIndex
- `src/codrag/mcp_server.py` — trace_search, trace_neighbors, trace_coverage, hi tools
- `src/codrag/core/__init__.py` — re-exports TraceBuilder, TraceIndex, TraceNode, TraceEdge, etc.

### Proposed Split → `src/codrag/core/trace/` subpackage
- `models.py` — TraceNode, TraceEdge, FileError, TraceBuildResult, extension constants, SUPPORTED_LANGUAGES
- `utils.py` — `_detect_language()`, `_to_posix()`, `_is_relevant()`
- `analyzers/python_analyzer.py` — PythonAnalyzer (AST-based)
- `analyzers/swift_analyzer.py` — SwiftAnalyzer (regex)
- `analyzers/generic_regex.py` — GenericRegexAnalyzer + LANGUAGE_CONFIGS
- `analyzers/js_analyzer.py` — JSAnalyzer (regex)
- `analyzers/__init__.py` — barrel exports
- `builder.py` — TraceBuilder + `build_trace()` convenience function
- `index.py` — TraceIndex
- `coverage.py` — `compute_trace_coverage()`
- `__init__.py` — re-export everything for backward compatibility

### Risk Notes
- **The `_ENGINE` / `_rust_engine` imports from `core.__init__`** must remain accessible to both `builder.py` and `index.py`.
- **Circular import danger**: `TraceBuilder` creates `TraceNode`/`TraceEdge` instances. Analyzers also create them. All must import from `models.py`.
- **Extensive test coverage exists**: `tests/test_trace*.py` — all must pass unchanged.

---

## 2. `src/codrag/core/atlas.py` (2,315 lines)

### What It Is
The codebase atlas — a pre-retrieval routing index and architectural narrative generator.

| Component | Lines | Purpose |
|-----------|-------|---------|
| `AtlasDocument` | 44–84 | Cached atlas narrative (content, fingerprint, staleness metadata). |
| `Segment` | 88–119 | Directory-based file grouping for segmented atlas generation. |
| `SegmentDocument` | 123–168 | A per-segment atlas narrative (sub-document of the full atlas). |
| `SegmentDescriptor` | 170–220 | Routing descriptor — COVERS text, key files, boundaries. Embedded for cosine routing. |
| Prompt templates | ~220–400 | `_ROOT_ATLAS_SYSTEM_PROMPT`, `_ROOT_ATLAS_USER_PROMPT`, segment prompts. Hardcoded multi-line strings with formatting instructions. |
| Standalone routing functions | ~400–956 | `build_routing_descriptors()`, `route_query()` — structural descriptor construction and cosine similarity routing. No LLM needed. |
| `CodebaseAtlas` | 957–2315 | **Main class**: segment discovery, parallel LLM generation, `generate_segmented()`, `generate_routing()`, staleness detection, persistence, `_postprocess()` (think-tag stripping). |

### Why It Exists This Way
- **Two modes by design** (see docstring): LLM Atlas (rich narrative from reasoning model, ~30s) and Structural Atlas (stats-only fallback, no LLM, available to Free tier).
- **Routing is the core value** (Phase 29B): `route_query()` pre-filters the vector search to the right subsystem. Atlas text is NOT injected into AI context — it scopes retrieval.
- **Prompt templates are here** because they're tightly coupled to the atlas generation logic. They reference specific data structures (module summaries, domain tags, hub files).
- **`_postprocess()`** strips `<think>` tags from reasoning models (Qwen3.5, DeepSeek-R1) — a critical bug fix (Phase 38 AT-1).

### Who Depends On It
- `src/codrag/services/pipeline_orchestrator.py` — atlas stage worker
- `src/codrag/api/routers/projects.py` — atlas routing in context endpoint
- `src/codrag/mcp_server.py` — `codrag_atlas` tool (returns atlas narrative)
- `src/codrag/core/__init__.py` — exports CodebaseAtlas, SegmentDescriptor, route_query, etc.

### Proposed Split → `src/codrag/core/atlas/` subpackage
- `models.py` — AtlasDocument, Segment, SegmentDocument, SegmentDescriptor
- `prompts.py` — All prompt template constants
- `routing.py` — `build_routing_descriptors()`, `route_query()`, ROUTING_* constants
- `generator.py` — CodebaseAtlas class (generation, persistence, staleness, postprocessing)
- `__init__.py` — re-exports

### Risk Notes
- `CodebaseAtlas.__init__` takes `index_dir` and discovers segments from pipeline data on disk. The generator must retain filesystem access.
- The routing functions are pure (no side effects) and cleanly separable.
- 85 atlas tests in `tests/test_atlas.py` — must all pass.

---

## 3. `src/codrag/api/routers/projects.py` (2,228 lines)

### What It Is
The central HTTP router for all project-scoped operations.

| Component | Lines | Purpose |
|-----------|-------|---------|
| Query preprocessing | 106–161 | `_preprocess_query()` — strips conversational filler, truncates, preserves code entities. Phase 34e. |
| Pydantic models | 175–258 | 11 request/response models (BuildRequest, SearchRequest, ContextRequest, etc.) |
| `_srv()` lazy import | 167–170 | Avoids circular imports with server.py |
| Project CRUD | ~260–450 | POST/GET/PUT/DELETE /projects, project config management |
| Build endpoint | ~450–550 | POST /projects/{id}/build — triggers index build with pipeline-active guard |
| Search endpoint | ~550–650 | POST /projects/{id}/search — vector search with LOD compression |
| **Context endpoint** | ~650–700 (+ helpers) | POST /projects/{id}/context — **the most complex endpoint**: ambient detection, query preprocessing, atlas routing, trace expansion, LOD compression, observation injection, compression. ~400 lines of orchestration. |
| Watch control | ~700–733 | POST/GET watch/start, watch/stop, watch/status |
| Activity/Coverage | ~735–761 | GET activity, GET coverage |
| File operations | ~764–933 | GET file (with security checks), GET files (recursive tree scan), GET detect-stack, GET roots |
| Included paths | ~1050+ | GET/PUT included_paths with localStorage persistence |

### Why It Exists This Way
- Extracted from the original monolithic `server.py` (4,352 lines) during Phase 23 Sprint 15.
- The **context endpoint** is large because it orchestrates multiple subsystems: atlas routing → vector search → trace expansion → LOD compression → observation injection → response formatting. This is the primary value delivery path for CoDRAG.
- `_srv()` lazy import pattern was chosen to avoid circular imports — `projects.py` needs `server.py`'s singletons (BuildManager, watchers, indexes) but `server.py` needs to mount the router.

### Who Depends On It
- `src/codrag/server.py` — mounts the router
- `src/codrag/mcp_server.py` — all MCP tools proxy to these endpoints
- `packages/ui/src/api/client.ts` — all dashboard API calls

### Proposed Split → `src/codrag/api/routers/projects/` subpackage
- `crud.py` — Project lifecycle (POST/GET/PUT/DELETE /projects)
- `search.py` — Search and Context endpoints (the heaviest: ~500 lines)
- `watch.py` — Watcher control (start/stop/status)
- `files.py` — File tree, file content, roots, detect-stack
- `models.py` — All 11 Pydantic request/response models
- `helpers.py` — `_preprocess_query()`, `_srv()`, shared glob matching
- `__init__.py` — assembles a composite router

### Risk Notes
- **The context endpoint shares state with the search endpoint** (both use `_get_project_index`, `_get_project_trace_index`). These must remain accessible to both sub-routers.
- **`_preprocess_query()` is imported by nothing else currently**, but logically belongs in `core/` since MCP could benefit from it.
- OpenAPI schema must remain identical before/after split.

---

## 4. `src/codrag/core/augmenter.py` (1,978 lines)

### What It Is
LLM-based augmentation of trace nodes and the shared LLM client.

| Component | Lines | Purpose |
|-----------|-------|---------|
| `AugmentationEntry` | 90–170 | Overlay data for a trace node: summary, role, confidence, validation status, related_files, doc_type. |
| `AugmentResult` | 202–213 | Stats from an augmentation run. |
| `LLMClient` | 215–477 | **Universal multi-provider LLM client** — Ollama, OpenAI, Anthropic, Google. `generate()` method with JSON mode, structured output, temperature, think mode. Also `is_available()` and `unload()` (VRAM management). |
| Prompt templates | 480–649 | `SYMBOL_SUMMARY_SYSTEM/PROMPT`, `DOC_ROLE_SYSTEM/PROMPT`, `FILE_SUMMARY_PROMPT`, batched variants. |
| `TraceAugmenter` | 650–1978 | Main augmentation orchestrator: reads trace nodes, dispatches LLM calls per file/symbol, writes `trace_augmented.jsonl`. Has incremental mode (skip unchanged files), checkpoint/resume, parallel execution, batched augmentation (BYOK). Pass 0.5: extracts related_files → Rust validation → inferred edges. |

### Why It Exists This Way
- **`LLMClient` is here because it was created alongside the augmenter** — the first LLM-dependent feature. It's now the shared interface for 4+ consumers.
- **Checkpoint/resume** exists because augmentation of large repos takes 30+ minutes on local models. Mid-run crashes (OOM, timeouts) would lose all progress without checkpoints.
- **Batched augmentation** (BYOK) processes multiple nodes per LLM call for cloud providers. Local models always use single-item mode.

### Who Depends On `LLMClient`
- `src/codrag/core/cluster.py` — imports `LLMClient`, `_parse_json_response`, `_parse_confidence`
- `src/codrag/core/epistemic_enrichment.py` — imports `LLMClient`
- `src/codrag/core/inferred_edges.py` — imports `LLMClient`
- `src/codrag/core/atlas.py` — uses `LLMClient` via pipeline orchestrator
- `src/codrag/services/pipeline_orchestrator.py` — creates `LLMClient` instances

### Proposed Split
- **`src/codrag/core/llm_client.py`** — Extract `LLMClient`, `_parse_json_response`, `_parse_confidence`, `_strip_think_tags`, `_get_llm_concurrency`. This is the highest-impact single extraction — it eliminates the misplaced dependency.
- **`src/codrag/core/augmenter/prompts.py`** — Move all prompt template constants.
- **Keep `TraceAugmenter` in `augmenter.py`** (or `augmenter/core.py`) — it's already well-scoped.

### Risk Notes
- **`LLMClient` extraction is the #1 priority** — it's imported by 4 other modules from `augmenter.py`, creating a false dependency chain (importing augmentation code to get an LLM client).
- All existing `from .augmenter import LLMClient` must be updated to `from .llm_client import LLMClient`.

---

## 5. `src/codrag/core/index.py` (1,927 lines)

### What It Is
The hybrid semantic + keyword search engine — both index construction and retrieval.

| Component | Lines | Purpose |
|-----------|-------|---------|
| Intent detection | 35–95 | `_detect_intent()`, `_INTENT_KEYWORDS`, `_INTENT_PARAMS` — keyword-based query classification (debug/refactor/add_feature/understand/general). Guides trace expansion direction/hops. |
| `EDGE_KIND_WEIGHT` | 85–95 | Weighted importance of edge types for trace expansion. Phase 39 W1b/SR-3. |
| `SearchResult` | 98–103 | Frozen dataclass with doc + score. |
| `CodeIndex.__init__` + `_load()` | 105–165 | Initialize from on-disk files (documents.json, embeddings.npy, manifest.json, fts.sqlite3). |
| `CodeIndex.build()` | 208–650 | **Index construction**: file scanning, .gitignore, incremental reuse, chunking, embedding, FTS5, atomic directory swap. ~450 lines. |
| `CodeIndex.search()` | 949–1082 | **Core retrieval**: cosine similarity, keyword boosts, FTS5 boosts, primer boosts, atlas segment routing boost, role/intent/path weight multipliers, adaptive-K gap detection, MMR diversity reranking. ~130 lines of dense scoring logic. |
| `get_context()` / `get_context_structured()` | 1182–1393 | Context assembly: formats search results into text blocks with headers, boundaries, primer chunks. Structured mode includes chunk metadata. |
| `get_context_with_trace_expansion()` | 1400+ | Extended context: runs base search, expands via trace graph neighbors, interleaves trace results with hub file boosts. Phase 34d. |
| Helper methods | various | `_keyword_boosts()`, `_fts_boosts()`, `_primer_boosts()`, `_adaptive_k_trim()`, `_mmr_rerank()`, `_classify_query_intent()`, `_resolve_path_weight()`, `query_policy()`. |

### Why It Exists This Way
- **Build and Search are in the same class** because they share the same on-disk state (`_documents`, `_embeddings`, `_manifest`). The build path writes these files; the search path reads them. Splitting would require a shared state manager.
- **The scoring pipeline is complex by necessity** — each boost layer addresses a specific retrieval failure mode identified through Phase 28/33/39 research.
- **Atomic directory swap in build()** prevents serving a half-built index. The `_PRESERVE_FILES` list protects pipeline enrichment data from being destroyed.

### Proposed Split (lighter touch)
Rather than a full subpackage, extract the **build path** since it's the most cleanly separable:
- `src/codrag/core/index_builder.py` — `CodeIndex.build()` method body + file scanning + chunking + embedding. The `CodeIndex` class retains a thin `build()` that delegates.
- Or alternatively, extract the scoring helpers into `src/codrag/core/scoring.py` — intent detection, keyword boosts, MMR, adaptive-K.

### Risk Notes
- **build() and search() share `_documents` and `_embeddings`** — they can't be fully separated without a mediator.
- The atomic swap logic in `build()` is fragile and well-tested. Move it carefully.

---

## 6. `src/codrag/mcp_server.py` (1,785 lines)

### What It Is
The MCP (Model Context Protocol) integration — CoDRAG's primary interface with AI IDE tools.

| Component | Lines | Purpose |
|-----------|-------|---------|
| Protocol constants + error codes | 77–101 | MCP spec version, JSON-RPC error codes, CoDRAG-specific error codes. |
| `MCPServer.__init__` + HTTP client | 116–223 | Async httpx client, daemon URL, `_api_get()` / `_api_post()` with envelope unwrapping. |
| `_resolve_project_id()` | 256–349 | 5-level priority chain for determining which project to target. Critical for multi-project setups. |
| Tool implementations | 355–920 | 12 tools: `tool_status`, `tool_build`, `tool_search`, `tool_context`, `tool_trace_search`, `tool_trace_neighbors`, `tool_trace_coverage`, `tool_impact`, `tool_save_observation`, `tool_get_observations`, `tool_hi`, `tool_atlas`. Each validates params, calls daemon, formats response for AI token efficiency. |
| `tool_hi()` | 764–1100+ | **Enormous**: parallel data fetching (7 endpoints), file categorization, topic detection, hub file analysis, health diagnostics, prompt suggestions. ~350 lines of inline data processing. |
| JSON-RPC handling | 1100+ | `handle_message()`, `_handle_single()`, `_dispatch_tool()`, `handle_initialize()`. MCP lifecycle. |
| Transport layers | 1400+ | stdio transport (`run_stdio()`), Streamable HTTP transport (`run_http()`). |

### Why It Exists This Way
- **MCP is a stdio JSON-RPC protocol** — the server reads from stdin, writes to stdout. This means stdout is reserved for protocol messages (logging goes to stderr).
- **The server is a thin async HTTP proxy** to the daemon — it doesn't import core classes directly. This is intentional: the MCP process runs in a separate process from the daemon.
- **`tool_hi()` is large** because it aggregates 7 endpoints into a single AI-friendly summary. The inline processing logic (file categorization, topic detection) could be a server-side endpoint.

### Proposed Split → `src/codrag/mcp/` subpackage
- `protocol.py` — Constants, error codes, JSON-RPC handling
- `client.py` — `_api_get()`, `_api_post()`, `_unwrap_envelope()`, error classes
- `resolver.py` — `_resolve_project_id()`, `_best_project_match()`, `_uri_to_path()`
- `tools/` — One file per tool group (status_tools.py, search_tools.py, trace_tools.py, observation_tools.py, hi_tool.py)
- `transport.py` — stdio and HTTP transports
- `server.py` — MCPServer class (thin dispatcher)

### Risk Notes
- **stdio transport is sensitive** — any accidental stdout write breaks the protocol.
- `mcp_tools.py` already exists as a separate file for tool schema definitions. The split must coordinate with it.
- The `handle_initialize()` method extracts workspace roots from the IDE — this is transport-layer concern that touches project resolution.

---

## 7. `src/codrag/services/pipeline_orchestrator.py` (1,483 lines)

### What It Is
The 11-stage enrichment pipeline state machine.

| Component | Lines | Purpose |
|-----------|-------|---------|
| `StageId` enum | 73–86 | 11 pipeline stages (structural → deep_knowledge). |
| Stage mappings | 89–118 | `STAGE_BUILD_TYPE`, `FAST_SYNC_STAGES`, `DEEP_ENRICHMENT_STAGES`, `STAGE_MODEL_SLOT`. |
| `WorkerFactory` | ~140–600 | Creates worker callables for each stage. Each worker: loads data, calls core class, writes results. Workers for: structural, inferred_edges, augment, validate, knowledge, enrichment, group_reasoning, cluster, atlas, deepening, deep_knowledge. |
| `PipelineRun` | ~600–800 | Tracks a group run: current stage, progress, errors, started_at, completed_at. |
| `PipelineOrchestrator` | ~800–1483 | **Main class**: `_start_group()`, `_run_group()`, `_advance_stage()`, cross-group concurrency guard, VRAM lifecycle (load/unload models at slot transitions), crash recovery (journal), auto-chain (fast → deep). |

### Why It Exists This Way
- **Two groups is a product design choice**: Fast Sync (quick, runs on file change) vs Deep Enrichment (expensive, manual/auto/scheduled). Users control groups, not individual stages.
- **WorkerFactory creates closures** that capture `project`, `index_dir`, `build_manager` — avoiding god-function parameters.
- **VRAM lifecycle** is managed at slot transitions (small→large model). The pipeline unloads the previous model before loading the next to prevent OOM on Apple Silicon.

### Proposed Split
- `src/codrag/services/pipeline/stages.py` — StageId, stage mappings, STAGE_MODEL_SLOT
- `src/codrag/services/pipeline/workers.py` — WorkerFactory
- `src/codrag/services/pipeline/orchestrator.py` — PipelineOrchestrator + PipelineRun
- `src/codrag/services/pipeline/__init__.py` — re-exports

### Risk Notes
- Workers import from `core/` modules (augmenter, cluster, epistemic, etc.) — these imports must remain valid.
- The crash recovery journal integration is delicate.

---

## 8. Frontend Targets

### 8.1 `packages/ui/src/types.ts` (998 lines)
**What**: All TypeScript type definitions for the UI package. ~150 exported types spanning 10+ domains.
**Why**: Grew organically as features were added. Never split because barrel-export pattern makes it easy to add types.
**Proposed**: Split into `types/project.ts`, `types/trace.ts`, `types/pipeline.ts`, `types/llm.ts`, `types/layout.ts` with `types/index.ts` barrel export. TypeScript compiler guarantees nothing is lost.

### 8.2 `packages/ui/src/components/marketing/MarketingHero.tsx` (825 lines)
**What**: 10 hero layout variants (Centered, Neo, Swiss, Glass, Retro, Split, Studio, Yale, Focus, Enterprise) in one giant switch statement.
**Why**: All variants share the same props interface and were iterated simultaneously during the design exploration phase.
**Proposed**: Extract each variant into `components/marketing/heroes/CenteredHero.tsx`, etc. Keep `MarketingHero.tsx` as a thin router.

### 8.3 `packages/ui/src/components/project/FolderTree.tsx` (719 lines)
**What**: Recursive file tree with selection logic, ancestral explosion, drag targets.
**Why**: The "ancestor explosion" logic (Phase 15 fix) is tightly coupled to the tree rendering — when you uncheck a child of a selected parent, it must "explode" the parent selection into siblings.
**Proposed**: Extract `FolderTreeNode.tsx` (recursive renderer) and `useFolderSelection.ts` (selection/explosion logic).

### 8.4 `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` (883 lines)
**What**: Massive hook returning 120+ props organized into 7 domain sub-objects (search, files, trace, enrichment, watch, llm, deepAnalysis).
**Why**: Phase 24D organized the flat props into domain objects, but the hook still constructs everything in one place.
**Proposed**: Continue the Phase 24 refactor — extract each domain into its own hook/context provider.

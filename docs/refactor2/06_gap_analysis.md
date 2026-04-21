# Gap Analysis — Structural Debt & Misplaced Concerns

This document identifies architectural gaps, misplaced concerns, duplicated logic, and missing abstractions discovered during the deep research phase. Each gap is annotated with severity, affected files, and recommended resolution.

---

## GAP-1: LLMClient Is Misplaced in augmenter.py (CRITICAL)

**Severity:** High — affects 5+ modules
**Files affected:** `augmenter.py`, `cluster.py`, `epistemic_enrichment.py`, `inferred_edges.py`, `pipeline_orchestrator.py`, `atlas.py` (indirectly)

**Problem:** `LLMClient` is a general-purpose multi-provider HTTP client (Ollama, OpenAI, Anthropic, Google) that lives inside `augmenter.py`. Every module that needs LLM access must `from .augmenter import LLMClient`, creating a false dependency on augmentation code. Helper functions `_parse_json_response`, `_parse_confidence`, `_strip_think_tags`, and `_get_llm_concurrency` are also trapped in `augmenter.py` and imported by `cluster.py` and others.

**Impact:**
- `cluster.py` line 29: `from .augmenter import LLMClient, _get_llm_concurrency, _parse_confidence, _parse_json_response`
- `epistemic_enrichment.py`: `from .augmenter import LLMClient`
- `inferred_edges.py`: `from .augmenter import LLMClient`
- Any future LLM consumer must also depend on augmenter.py

**Resolution:** Extract `LLMClient` and its helper functions into `src/prep/core/llm_client.py`. Update all imports. This is the single highest-value extraction in the entire refactor.

---

## GAP-2: Duplicate External Module Handling in TraceBuilder (MEDIUM)

**Severity:** Medium — code duplication, maintenance burden
**File affected:** `src/prep/core/trace.py` lines 1148–1255

**Problem:** `TraceBuilder.build()` has **4 nearly identical code blocks** for handling external modules across the Python, Swift, JS, and Generic analyzer dispatch branches. Each block:
1. Iterates `sym_edges` looking for `edge.metadata.get("external")`
2. Creates a `TraceNode(kind="external_module", ...)` if not already seen
3. Adds it to `external_modules` dict
4. Extends `edges` and increments `files_parsed`
5. Handles exceptions identically

The only difference between the 4 blocks is which analyzer class is instantiated.

**Resolution:** Extract a helper method `_process_analyzer_result(sym_nodes, sym_edges, external_modules)` that handles the shared logic. The dispatch becomes:
```python
analyzer = self._get_analyzer(language, rel_path, source)
if analyzer:
    sym_nodes, sym_edges = analyzer.analyze()
    self._process_result(sym_nodes, sym_edges, nodes, edges, external_modules)
```

---

## GAP-3: Query Preprocessing Lives in the Wrong Layer (LOW)

**Severity:** Low — functional but architecturally impure
**File affected:** `src/prep/api/routers/projects.py` lines 106–161

**Problem:** `_preprocess_query()` (Phase 34e) performs filler stripping, truncation, and code entity preservation. It lives in the HTTP router layer (`projects.py`) but is a pure text transformation that could benefit MCP tool calls directly. Currently the MCP server sends raw queries to the daemon, and preprocessing only happens inside the `/context` endpoint.

**Impact:** If query preprocessing were applied in the MCP layer before the HTTP call, the query sent to the daemon would already be clean. This would also allow standalone use (CLI search, scripts).

**Resolution:** Move `_preprocess_query()`, `_FILLER_PREFIXES`, `_CODE_ENTITY`, `_MAX_QUERY_CHARS` to `src/prep/core/query.py`. Import from both `projects.py` and optionally `mcp_server.py`.

---

## GAP-4: Context Assembly Logic Is Split Across Two Layers (MEDIUM)

**Severity:** Medium — hard to reason about the full context pipeline
**Files affected:** `src/prep/core/index.py` and `src/prep/api/routers/projects.py`

**Problem:** The context assembly pipeline is split:
- **index.py** owns: `get_context()`, `get_context_structured()`, `get_context_with_trace_expansion()` — these handle base search, scoring, primer chunks, chunk formatting.
- **projects.py** owns: atlas routing (pre-retrieval), LOD compression (post-retrieval), observation injection (post-retrieval), ambient context detection, compression dispatch.

The `/context` endpoint in `projects.py` has ~400 lines of orchestration that wraps `CodeIndex` methods with additional concerns. This means understanding "how context is assembled" requires reading two files.

**Impact:** Adding a new context feature (e.g., a new compression mode or a new injection source) requires modifying both files and understanding their interaction boundary.

**Resolution:** Consider creating `src/prep/core/context_assembler.py` that encapsulates the full pipeline:
1. Ambient detection
2. Query preprocessing
3. Atlas routing
4. Base search (delegates to CodeIndex)
5. Trace expansion
6. LOD compression
7. Observation injection
8. Final formatting

The `/context` endpoint would become a thin HTTP adapter calling `ContextAssembler.assemble()`.

**Deferral note:** This is the most complex extraction. It should come AFTER the simpler splits (trace.py, atlas.py, LLMClient) are validated.

---

## GAP-5: Prompt Templates Are Scattered (LOW)

**Severity:** Low — functional, but makes prompt auditing difficult
**Files affected:** `augmenter.py`, `atlas.py`, `cluster.py`, `epistemic_enrichment.py`, `inferred_edges.py`, `batch_prompts.py`

**Problem:** Every LLM-consuming module defines its own prompt templates as module-level string constants. There's no central registry of all prompts used by the system.

**Prompts inventory:**
- `augmenter.py`: `SYMBOL_SUMMARY_SYSTEM/PROMPT`, `DOC_ROLE_SYSTEM/PROMPT`, `FILE_SUMMARY_PROMPT`, batched variants
- `atlas.py`: `_ROOT_ATLAS_SYSTEM_PROMPT`, `_ROOT_ATLAS_USER_PROMPT`, segment prompts (~180 lines)
- `cluster.py`: `MODULE_SYNTHESIS_PROMPT` (~80 lines)
- `epistemic_enrichment.py`: `CODE_ENRICHMENT_PROMPT`, `DOC_ENRICHMENT_PROMPT` (~100 lines)
- `inferred_edges.py`: `INFERRED_EDGES_PROMPT` (~60 lines)
- `batch_prompts.py`: Batched versions of the above (~200 lines)

**Impact:** When changing prompt style (e.g., adding structured output schemas globally), every file must be updated independently. No way to audit all prompts from one location.

**Resolution:** Create `src/prep/core/prompts/` with per-domain prompt files. Low priority — prompts are tightly coupled to their consumers' data structures, so co-location has real benefits.

---

## GAP-6: MCP tool_hi() Contains 350+ Lines of Inline Data Processing (MEDIUM)

**Severity:** Medium — bloats the MCP server, logic untestable in isolation
**File affected:** `src/prep/mcp_server.py` lines 764–1100+

**Problem:** `tool_hi()` fetches data from 7 daemon endpoints in parallel, then performs extensive inline processing:
- File categorization by extension (docs/code/tests/config)
- Topic detection via keyword clustering (`_detect_topics()` — 50 lines of topic cluster dicts)
- Hub file analysis
- Health diagnostics
- Content-aware prompt suggestions
- File inventory building

This is all business logic that should live on the daemon side as a `/projects/{id}/hi` endpoint, not in the MCP transport layer.

**Impact:** The MCP server process is supposed to be a thin proxy. This inline processing can't be tested without mocking 7 HTTP endpoints. It also makes the hi tool slower (7 sequential HTTP round-trips vs one).

**Resolution:** Create a `GET /projects/{id}/overview` endpoint on the daemon that returns the aggregated data. The MCP `tool_hi()` becomes a single HTTP call + response formatting.

---

## GAP-7: GenericRegexAnalyzer LANGUAGE_CONFIGS Is Data, Not Code (LOW)

**Severity:** Low — functional but hard to maintain
**File affected:** `src/prep/core/trace.py` lines 552–675

**Problem:** The `LANGUAGE_CONFIGS` dict is 130 lines of regex pattern data for 14 languages. It's defined as a class-level dict on `GenericRegexAnalyzer`. Adding or modifying language support requires editing a deeply nested dict literal inside a class definition.

**Resolution:** Either:
- (a) Move to a separate `language_patterns.py` or `analyzers/patterns.py`
- (b) Move to a JSON/YAML config file (enables external contributions without touching Python code)

---

## GAP-8: Inconsistent Glob Matching Across Files (LOW)

**Severity:** Low — subtle behavior differences possible
**Files affected:** `trace.py` (`_is_relevant`), `projects.py` (file endpoint glob matching), `index.py` (build glob matching)

**Problem:** Three different files implement glob matching with slightly different approaches:
- `trace.py _is_relevant()`: Uses `fnmatch` with manual `**/` prefix stripping
- `projects.py`: Uses `fnmatch` with a `_glob_match()` helper that also strips `**/`
- `index.py build()`: Uses `pathspec.PathSpec.from_lines("gitignore", ...)` for exclude globs

The `fnmatch` approach and `pathspec` approach can behave differently for edge cases (e.g., patterns with `{}` braces, nested `**` patterns).

**Resolution:** Centralize glob matching into a single utility in `src/prep/core/glob_utils.py` that all three consumers use. Use `pathspec` consistently (it handles `.gitignore`-style patterns correctly).

---

## GAP-9: Missing Abstraction for "Project Context" in Routers (MEDIUM)

**Severity:** Medium — repeated boilerplate across endpoints
**File affected:** `src/prep/api/routers/projects.py`

**Problem:** Many endpoints repeat the same boilerplate:
```python
proj = _srv()._require_project(project_id)
cfg = proj.config or {}
include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
include_globs = list(include_raw) if isinstance(include_raw, list) else list(_srv()._DEFAULT_UI_CONFIG.get("include_globs") or [])
exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(_srv()._DEFAULT_UI_CONFIG.get("exclude_globs") or [])
```

This 6-line pattern appears in `start_project_watch`, `get_project_coverage`, `get_project_file_content`, `list_project_files`, and the search/context endpoints.

**Resolution:** Create a `ProjectContext` helper class or a `_get_project_globs(proj)` utility that encapsulates this pattern. Returns `(project, include_globs, exclude_globs, repo_root)` in one call.

---

## GAP-10: No Central Type Registry for Pipeline Stages (LOW)

**Severity:** Low — works but fragile
**Files affected:** `pipeline_orchestrator.py`, `types.ts`, `GraphEnrichmentPipeline.tsx`

**Problem:** Pipeline stage IDs are defined in three places:
- Python: `StageId` enum in `pipeline_orchestrator.py`
- TypeScript: `EnrichmentStageId` type in `types.ts`
- React: Stage labels in `GraphEnrichmentPipeline.tsx`

Adding a new pipeline stage requires updating all three files manually. There's no shared schema or code generation step.

**Impact:** Stage 11 (`group_reasoning`) was added to the Python enum but the TypeScript type may lag behind.

**Resolution:** For now, document the sync requirement. Long-term, consider generating the TypeScript types from the Python enum via a build script.

---

## Summary: Priority Ranking

| Gap | Severity | Effort | Priority |
|-----|----------|--------|----------|
| GAP-1: LLMClient extraction | High | Small (1 file + import updates) | **P0** |
| GAP-2: Duplicate analyzer handling | Medium | Small (1 helper method) | **P1** |
| GAP-4: Context assembly split | Medium | Large (new abstraction) | **P2** (defer) |
| GAP-6: tool_hi inline processing | Medium | Medium (new endpoint) | **P2** |
| GAP-9: Project context boilerplate | Medium | Small (1 utility) | **P1** |
| GAP-3: Query preprocessing layer | Low | Small (move 1 function) | **P3** |
| GAP-5: Scattered prompts | Low | Medium (new directory) | **P3** |
| GAP-7: LANGUAGE_CONFIGS as data | Low | Small (move dict) | **P3** |
| GAP-8: Glob matching inconsistency | Low | Medium (centralize) | **P3** |
| GAP-10: Pipeline stage sync | Low | None (document only) | **P4** |

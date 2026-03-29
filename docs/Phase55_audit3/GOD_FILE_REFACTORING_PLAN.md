# God-File Refactoring Plan — Phase 55

> Preliminary architectural plan for splitting the four critical god-files identified in the codebase audit.
> 
> **Target Files:**
> - `services/pipeline/orchestrator.py` — 2,356 lines (was 2,459)
> - `mcp/server.py` — 2,506 lines (was 2,251, **grew 255 lines**)
> - `core/augmenter.py` — 2,042 lines (was 2,096)
> - `core/index.py` — 1,925 lines (was 1,843, **grew 82 lines**)
>
> **Total:** 8,829 lines → target: <5,000 lines across all 4 files (~43% reduction)

---

## 1. Orchestrator Split Strategy (`orchestrator.py`)

### Current Analysis
**2,356 lines** — Pipeline sequencing, stage management, state transitions, retry/checkpoint logic.

### Extraction Targets

| New Module | Lines (est.) | Responsibility |
|------------|--------------|----------------|
| `stage_definitions.py` | ~200 | `StageId`, `STAGE_BUILD_TYPE`, `STAGE_TASK_ID`, `STAGE_MODEL_SLOT`, `STAGE_QUEUE_TYPE`, `STAGE_MANIFEST_FILE`, `STAGE_OUTPUT_FILE`, `STAGE_CONFIDENCE_FIELD` |
| `retry_logic.py` | ~250 | Checkpoint logic, retry strategies, exponential backoff, stage resume detection |
| `state_transitions.py` | ~300 | `_advance_pipeline`, `_on_build_transition`, phase progression, group completion |
| `metadata_tracker.py` | ~180 | `_run_metadata`, `PipelineRunMetadata`, per-run logging |
| `public_api.py` | ~150 | `run_fast_sync`, `run_deep_enrichment`, `run_all`, `status` |

### Refactoring Order
1. **Extract `stage_definitions.py`** — Pure constants, zero dependencies, safest start
2. **Extract `retry_logic.py`** — Self-contained, well-tested logic
3. **Extract `state_transitions.py`** — Requires careful handling of `_runs` dict
4. **Extract `metadata_tracker.py`** — Isolates file logger complexity
5. **Slim `orchestrator.py`** to ~1,500 lines — Core orchestration only

### Risk Assessment
- **Low:** `stage_definitions.py` (constants only)
- **Medium:** `retry_logic.py` (needs mock BuildOrchestrator for tests)
- **High:** `state_transitions.py` (core pipeline flow, 76 tests depend on this)

---

## 2. MCP Server Split Strategy (`server.py`)

### Current Analysis
**2,506 lines** — Tool handlers, project resolution, protocol handling, all in one class.

### Extraction Targets

| New Module | Lines (est.) | Responsibility |
|------------|--------------|----------------|
| `handlers/audit.py` | ~280 | `tool_audit`, `handle_audit_request`, audit result formatting |
| `handlers/search.py` | ~320 | `tool_search`, context assembly, LOD compression, atlas integration |
| `handlers/observe.py` | ~200 | `tool_observe`, memory save/get operations |
| `handlers/impact.py` | ~180 | `tool_impact`, blast radius analysis |
| `project_resolver.py` | ~350 | `_resolve_project_id`, `_best_project_match`, `_uri_to_path`, CWD matching, env var handling |
| `protocol_handler.py` | ~250 | `handle_initialize`, `handle_tools_list`, JSON-RPC framing, error codes |
| `logging_config.py` | ~80 | `configure_logging`, RotatingFileHandler setup |

### New Directory Structure
```
mcp/
├── __init__.py
├── server.py                 # ~900 lines (was 2,506)
├── errors.py                 # Existing
├── protocol_handler.py       # NEW — JSON-RPC protocol
├── project_resolver.py       # NEW — multi-project routing
├── logging_config.py         # NEW
└── handlers/
    ├── __init__.py
    ├── audit.py              # NEW
    ├── search.py             # NEW
    ├── observe.py            # NEW
    └── impact.py             # NEW
```

### Refactoring Order
1. **Extract `logging_config.py`** — Standalone, no dependencies
2. **Extract `protocol_handler.py`** — Protocol constants + framing logic
3. **Extract `project_resolver.py`** — Complex logic, many edge cases
4. **Extract handlers one-by-one:** audit → search → observe → impact
5. **Slim `server.py`** to ~900 lines — MCPServer class, registration, delegation only

### Risk Assessment
- **Low:** `logging_config.py`
- **Medium:** `protocol_handler.py` (needs MCP protocol tests)
- **High:** `project_resolver.py` (46 tests for multi-project routing)
- **High:** Handler extractions (each tool has integration tests)

---

## 3. Augmenter Split Strategy (`augmenter.py`)

### Current Analysis
**2,042 lines** — Augmentation logic, prompt templates, batch processing, LLM calls.

### Extraction Targets

| New Module | Lines (est.) | Responsibility |
|------------|--------------|----------------|
| `prompts/augmentation.py` | ~350 | All prompt templates: `_SYSTEM_PROMPT`, `_USER_PROMPT_TEMPLATE`, `_SUFFIX_PROMPT` |
| `batch_processor.py` | ~280 | `_augment_files_batched`, `BatchStrategy`, `BatchedResponseParser` |
| `tier_scheduler.py` | ~200 | `topological_sort_into_tiers`, tier-based dispatch logic |
| `result_builder.py` | ~180 | `_build_result_entry`, `_create_fallback_entry`, synthetic entry creation |
| `file_selector.py` | ~150 | File filtering, exclude patterns, file list preparation |

### New Directory Structure
```
core/
├── augmenter.py              # ~900 lines (was 2,042)
├── augmenter_core.py         # NEW — if needed for shared types
└── prompts/
    ├── __init__.py
    ├── augmentation.py       # NEW
    └── batching.py         # NEW (optional)
```

### Refactoring Order
1. **Extract `prompts/augmentation.py`** — Pure strings, easy to test
2. **Extract `batch_processor.py`** — Complex but self-contained
3. **Extract `tier_scheduler.py`** — Topological sort logic
4. **Extract `result_builder.py`** — Entry creation logic
5. **Slim `augmenter.py`** to ~900 lines — Main `TraceAugmenter` class only

### Risk Assessment
- **Low:** `prompts/augmentation.py`
- **Medium:** `batch_processor.py` (batch tests in `test_batch_profiles.py`)
- **Medium:** `tier_scheduler.py` (dependency graph logic)

---

## 4. Index Split Strategy (`index.py`)

### Current Analysis
**1,925 lines** — Search, index management, scoring, trace expansion, context assembly.

### Extraction Targets

| New Module | Lines (est.) | Responsibility |
|------------|--------------|----------------|
| `search_engine.py` | ~400 | `search()`, `_search_semantic()`, `_search_keyword()`, result ranking |
| `scoring.py` | ~250 | Score normalization, MMR rerank, score gaps, confidence calculation |
| `trace_expansion.py` | ~300 | `_get_context_with_trace_expansion`, hub boost, neighbor interleaving |
| `context_builder.py` | ~280 | `ContextBuilder`, LOD compression, context assembly |
| `index_manager.py` | ~200 | `CoDRAGIndex` class, build/refresh operations |

### New Directory Structure
```
core/
├── index.py                  # ~600 lines (was 1,843)
├── index/                    # NEW directory
│   ├── __init__.py
│   ├── search_engine.py      # NEW
│   ├── scoring.py            # NEW
│   ├── trace_expansion.py    # NEW
│   ├── context_builder.py    # NEW
│   └── index_manager.py      # NEW
```

### Refactoring Order
1. **Extract `scoring.py`** — Pure functions, well-defined inputs/outputs
2. **Extract `index_manager.py`** — Index lifecycle operations
3. **Extract `context_builder.py`** — Context assembly logic
4. **Extract `trace_expansion.py`** — Complex but isolated
5. **Extract `search_engine.py`** — Main search orchestration
6. **Slim `index.py`** to ~600 lines — Public API only

### Risk Assessment
- **Low:** `scoring.py` (pure math)
- **Medium:** `index_manager.py` (file operations)
- **High:** `trace_expansion.py` (804 tests depend on context behavior)
- **High:** `search_engine.py` (core retrieval logic)

---

## Implementation Phases

### Phase 1: Low-Risk Extractions (Week 1)
1. `stage_definitions.py` from orchestrator
2. `logging_config.py` from mcp server
3. `prompts/augmentation.py` from augmenter
4. `scoring.py` from index

**Expected:** ~1,000 lines moved, zero functional changes, all tests pass.

### Phase 2: Medium-Risk Extractions (Week 2)
1. `retry_logic.py` from orchestrator
2. `protocol_handler.py` from mcp server
3. `batch_processor.py` from augmenter
4. `index_manager.py` from index

**Expected:** ~1,100 lines moved, some test file reorganization needed.

### Phase 3: High-Risk Extractions (Week 3-4)
1. `state_transitions.py` from orchestrator
2. `project_resolver.py` + handlers from mcp server
3. `tier_scheduler.py` + `result_builder.py` from augmenter
4. `trace_expansion.py` + `context_builder.py` + `search_engine.py` from index

**Expected:** ~3,500 lines moved, significant test refactoring, 76+ tests may need updates.

---

## Testing Strategy

### Per-Extraction Checklist
- [ ] All original tests pass with new imports
- [ ] New module has dedicated unit tests
- [ ] Import cycles checked (`mcp0_codrag_impact` tool)
- [ ] Performance regression test (search latency, pipeline throughput)

### Risk Mitigation
1. **Feature flags:** Add `USE_LEGACY_ORCHESTRATOR` env var for rollback
2. **Gradual rollout:** Deploy Phase 1 to all devs, Phase 2 to team leads, Phase 3 after burn-in
3. **Test coverage:** Maintain >90% coverage on extracted modules

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Max file lines | 2,506 | <1,500 | `wc -l` |
| Total god-file lines | 8,829 | <5,000 | `wc -l` across 4 files |
| Test pass rate | ~94% | >95% | `pytest` |
| Import cycle count | TBD | No new cycles | `mcp0_codrag_audit` |
| Pipeline latency | Baseline | <5% regression | Benchmark |

---

## Open Questions

1. **Should we extract common types to a shared module?** `PipelineRun`, `PipelineRunMetadata` used across multiple files.
2. **Handler registration pattern:** Decorator-based (`@register_tool`) or explicit dict in `server.py`?
3. **Test file organization:** Keep tests in `tests/` or co-locate with source (`*_test.py`)?
4. **Circular dependencies:** `orchestrator.py` imports from `workers.py` — will extraction create cycles?

---

*Created: 2026-03-27*  
*Status: Preliminary — ready for team review*

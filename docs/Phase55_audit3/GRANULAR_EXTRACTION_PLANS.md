# Granular God-File Extraction Plans — Phase 55

> Line-level extraction strategies for the four critical god-files.
> Generated from direct source analysis of current codebase state.

---

## 1. Orchestrator Extraction Plan (`orchestrator.py` — 2,356 lines)

### Extraction 1A: `_sse_bridge` Module (Lines 2299–2356)
**Target:** `services/pipeline/sse_bridge.py` (58 lines)

```python
# Current location: lines 2299–2356
def _create_sse_bridge(pipeline: PipelineOrchestrator) -> None:
    """Create SSE bridge for pipeline progress streaming."""
    ...
```

**Dependencies:** None (standalone function)
**Risk:** LOW — Pure I/O, no state mutation
**Tests to move:** `test_sse_bridge.py` (if exists)

---

### Extraction 1B: `resume_logic` Module (Lines 651–760)
**Target:** `services/pipeline/resume_logic.py` (~110 lines)

**Functions to extract:**
- `_detect_resume_point()` — Line 651
- `_is_deep_enrichment_auto()` — Line 761
- `_maybe_retrigger_for_coverage()` — Line 522
- `check_coverage_gap()` — Line 464 (static function)

**Data classes:**
- `ResumePoint` — dataclass for resume state (new)
- `StageOutputStatus` — enum for output states (new)

**Dependencies:** 
- `STAGE_MANIFEST_FILE` (from .stages)
- `STAGE_OUTPUT_FILE` (from .stages)
- `FAST_SYNC_STAGES`, `DEEP_ENRICHMENT_STAGES` (from .stages)

**Risk:** MEDIUM — Core resume detection, 12 tests depend on this
**Estimated lines to move:** 110

---

### Extraction 1C: `state_transitions` Module (Lines 884–1090)
**Target:** `services/pipeline/state_transitions.py` (~206 lines)

**Functions to extract:**
- `_advance_pipeline()` — Line 884 (core state machine driver)
- `_on_build_transition()` — Line 1090 (event handler)
- `_journal_stage_started()` — Line 1830
- `_journal_stage_completed()` — Line 1882
- `_journal_stage_failed()` — Line 1891
- `_resume_queued_pipeline()` — Line 1839

**Dependencies:**
- `PipelineGroupStateMachine` (from .state_machine)
- `Event` (from .state_machine)
- `PipelineState` (from .state_machine)
- `StageId` (from .stages)

**Risk:** HIGH — Core orchestration flow, 76 tests
**Estimated lines to move:** 206 + helper functions

---

### Extraction 1D: `metadata_tracker` Module (Lines 70–200)
**Target:** `services/pipeline/metadata_tracker.py` (~130 lines)

**Functions to extract:**
- `_get_file_logger()` — Line 78–91
- `_create_run_metadata()` — Line range TBD
- `_update_run_metadata()` — Line range TBD
- `_cleanup_run_metadata()` — Line range TBD

**Data classes:**
- `PipelineRunMetadata` — Currently inline dict, promote to dataclass

**Risk:** LOW — Isolated per-run tracking

---

### Extraction 1E: `pause_resume` Module (Lines 1370–1500)
**Target:** `services/pipeline/pause_resume.py` (~130 lines)

**Functions to extract:**
- `_pause_group()` — Line 1370
- `_cancel_group()` — Line 1338
- `_release_group_models_via_sm()` — Line 1442
- `_maybe_unload_previous_model()` — Line 1463
- `_unload_group_models()` — Line 1501

**Dependencies:**
- `BuildOrchestrator.pause()`
- `BuildOrchestrator.resume()`
- `PipelineGroupStateMachine` (from .state_machine)

**Risk:** MEDIUM — Pause/resume is actively used
**Estimated lines to move:** 130

---

### Refactoring Sequence (Orchestrator)

```
Week 1: 1A → 1D (low risk, build confidence)
Week 2: 1B → 1E (medium risk, core logic)
Week 3: 1C (high risk, save for last)

Target final size: 2,356 → ~1,400 lines (40% reduction)
```

---

## 2. MCP Server Extraction Plan (`server.py` — 2,506 lines)

### Extraction 2A: `logging_config` Module (Lines 35–56)
**Target:** `mcp/logging_config.py` (21 lines)

```python
# Already a standalone function — trivial extraction
def configure_logging(*, debug: bool = False, log_file: Optional[str] = None) -> None:
    ...
```

**Risk:** TRIVIAL

---

### Extraction 2B: `protocol_handler` Module (Lines 285–450)
**Target:** `mcp/protocol_handler.py` (~165 lines)

**Functions to extract:**
- `handle_initialize()` — MCP init handshake
- `handle_tools_list()` — Tool enumeration
- `handle_ping()` — Keepalive
- `handle_shutdown()` — Graceful shutdown

**Constants to extract:**
- `MCP_PROTOCOL_VERSION` (line 63)
- `JSONRPC_VERSION` (line 64)
- All error codes (lines 67–78)
- `MAX_SEARCH_K`, `MAX_CONTEXT_K`, `MAX_CONTEXT_CHARS` (lines 80–82)

**Risk:** LOW — Protocol framing, well-defined interface

---

### Extraction 2C: `client_budgets` Module (Lines 124–153)
**Target:** `mcp/client_budgets.py` (~30 lines)

**Extract:**
- `_CLIENT_BUDGETS` dict (lines 126–137)
- `_DEFAULT_BUDGET` constant (line 138)
- `_get_context_budget()` method (lines 140–152)

**Risk:** LOW — Pure data + simple logic

---

### Extraction 2D: `project_resolver` Module (Lines 450–800)
**Target:** `mcp/project_resolver.py` (~350 lines)

**Functions to extract:**
- `_resolve_project_id()` — Main resolution logic
- `_best_project_match()` — CWD matching
- `_uri_to_path()` — URI normalization
- `_get_project_path_sync()` — Line 205–218
- `_project_has_rules_file()` — Line 154–203
- `_check_atlas_signal()` — Line 220–273

**Dependencies:**
- `ProjectNotFoundError` (from .errors)
- `ProjectSelectionAmbiguousError` (from .errors)

**Risk:** HIGH — 46 tests for multi-project routing, complex edge cases

---

### Extraction 2E: `handlers/` Directory (Lines 684–1672)
**Create package:** `mcp/handlers/`

| File | Lines | Functions | Line Numbers | Risk |
|------|-------|-----------|--------------|------|
| `build.py` | ~22 | `tool_build()` | 684–705 | LOW |
| `search.py` | ~91 | `tool_search()`, `tool_trace_search()` | 706–971 | MEDIUM |
| `context.py` | ~97 | `tool_context()`, `_format_context_response()` | 797–911 | MEDIUM |
| `trace.py` | ~50 | `tool_trace_neighbors()`, `tool_trace_coverage()` | 972–1044 | LOW |
| `impact.py` | ~75 | `tool_impact()` | 1045–1119 | LOW |
| `observe.py` | ~56 | `tool_save_observation()`, `tool_get_observations()` | 1120–1232 | LOW |
| `audit.py` | ~94 | `tool_audit()`, `tool_audit_refactor()`, `tool_audit_check()`, `tool_audit_report()` | 1233–1511 | LOW |
| `advise.py` | ~77 | `tool_advise()`, `tool_roadmap()` | 1512–1671 | LOW |
| `hi.py` | ~13 | `tool_hi()` | 1672–1684 | TRIVIAL |

**Handler line ranges from grep:**
- `tool_build`: 684–705 (~22 lines)
- `tool_search`: 706–796 (~91 lines)
- `tool_context`: 797–893 (~97 lines)
- `tool_trace_search`: 912–971 (~60 lines)
- `tool_trace_neighbors`: 972–1021 (~50 lines)
- `tool_trace_coverage`: 1022–1044 (~23 lines)
- `tool_impact`: 1045–1119 (~75 lines)
- `tool_save_observation`: 1120–1176 (~57 lines)
- `tool_get_observations`: 1177–1232 (~56 lines)
- `tool_audit`: 1233–1326 (~94 lines)
- `tool_audit_refactor`: 1327–1418 (~92 lines)
- `tool_audit_check`: 1419–1489 (~71 lines)
- `tool_audit_report`: 1490–1511 (~22 lines)
- `tool_advise`: 1512–1588 (~77 lines)
- `tool_roadmap`: 1589–1671 (~83 lines)
- `tool_hi`: 1672–1684 (~13 lines)

**Total handler lines:** ~984 lines

**Common dependencies:**
- `MCPServer._get_client()`
- `MCPServer.daemon_url`
- `MCPServer._resolve_project_id()`
- `MCPServer._get_context_budget()`

**Handler registration pattern:**
```python
# In server.py after extraction:
from .handlers import build, search, context, trace, impact, observe, audit, advise, hi

self._handlers = {
    "codrag_build": build.handle,
    "codrag_search": search.handle,
    "codrag_context": context.handle,
    "codrag_trace_search": trace.handle_search,
    "codrag_trace_neighbors": trace.handle_neighbors,
    "codrag_trace_coverage": trace.handle_coverage,
    "codrag_impact": impact.handle,
    "codrag_save_observation": observe.handle_save,
    "codrag_get_observations": observe.handle_get,
    "codrag_audit": audit.handle,
    "codrag_advise": advise.handle,
    "codrag_roadmap": advise.handle_roadmap,
    "hi_codrag": hi.handle,
}
```

**Risk:** MEDIUM — Each handler has integration tests (46+ tests total)
**Estimated total lines to move:** ~984

---

### Refactoring Sequence (MCP Server)

```
Week 1: 2A → 2B → 2C (foundation, zero risk)
Week 2: 2D (project resolution — most complex)
Week 3: 2E (handlers — one per day)

Target final size: 2,506 → ~850 lines (66% reduction)
```

---

## 3. Augmenter Extraction Plan (`augmenter.py` — 2,042 lines)

### Extraction 3A: `prompts/augmentation` Package (Lines 143–246)
**Target:** `core/prompts/augmentation.py` (~103 lines)

**Constants to extract:**
```python
SYMBOL_SUMMARY_SYSTEM = """..."""  # Lines 143–145
SYMBOL_SUMMARY_PROMPT = """..."""   # Lines 147–185
FILE_ROLE_SYSTEM = """..."""        # Lines 201–202
FILE_ROLE_PROMPT = """..."""       # Lines 204–221
DOC_ROLE_SYSTEM = """..."""        # Lines 223–224
DOC_ROLE_PROMPT = """..."""        # Lines 226–245
```

**Risk:** TRIVIAL — String constants only

---

### Extraction 3B: `data_models` Module (Lines 80–200)
**Target:** `core/augmenter_models.py` (~120 lines)

**Classes to extract:**
- `AugmentationEntry` — Lines 81–141 (dataclass with methods)
- `AugmentResult` — Lines 146–200 (dataclass with methods)
- `VALID_ROLES` — Lines 34–38 (frozenset)
- `VALID_DOC_TYPES` — Lines 41–44 (frozenset)
- `VALID_DOC_STATUSES` — Lines 46–48 (frozenset)

**Risk:** LOW — Pure data models

---

### Extraction 3C: `io_ops` Module (Lines 399–576)
**Target:** `core/augmenter_io.py` (~177 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `load_existing()` | 399 | ~14 |
| `load_trace_nodes()` | 415 | ~11 |
| `load_trace_edges()` | 427 | ~11 |
| `load_file_hashes()` | 439 | ~10 |
| `_needs_augmentation()` | 451 | ~17 |
| `_read_source_snippet()` | 470 | ~16 |
| `_get_file_head()` | 488 | ~11 |
| `_get_strategic_excerpt()` | 500 | ~60 |
| `_get_file_imports()` | 561 | ~15 |

**Total:** ~165 lines
**Risk:** LOW — File I/O, easy to mock

---

### Extraction 3D: `synthetic_entries` Module (Lines 586–663)
**Target:** `core/synthetic_entries.py` (~77 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `_infer_role_from_path()` | 586 | ~19 |
| `_lang_label()` | 606 | ~17 |
| `_synthetic_entry()` | 624 | ~39 |

**Total:** ~75 lines
**Dependencies:** None (pure heuristics)

**Risk:** LOW — No external deps, deterministic

---

### Extraction 3E: `batch_processor` Module (Lines 1031–1499)
**Target:** `core/batch_processor.py` (~468 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `_augment_symbols_batched()` | 1031 | ~163 |
| `_augment_files_batched()` | 1195 | ~304 |

**Total:** ~467 lines
**Dependencies:**
- `BatchRetryStrategy` (from .batch_strategy)
- `BatchedResponseParser` (from .batch_strategy)

**Risk:** MEDIUM — Complex retry logic, has telemetry

---

### Extraction 3F: `node_helpers` Module (Lines 794–838)
**Target:** `core/node_helpers.py` (~44 lines)

**Functions to extract:**
- `_get_section_nodes_for_file()` — Lines 794–807
- `_get_reference_targets()` — Lines 809–822
- `_get_link_targets()` — Lines 824–837

**Risk:** LOW — Simple graph traversal

---

### Refactoring Sequence (Augmenter)

```
Week 1: 3A → 3B → 3F (constants, models, helpers)
Week 2: 3C → 3D (I/O and synthetic entries)
Week 3: 3E (batch processing — most complex)

Target final size: 2,042 → ~950 lines (53% reduction)
```

---

## 4. Index Extraction Plan (`index.py` — 1,925 lines)

### Extraction 4A: `intent_detection` Module (Lines 35–79)
**Target:** `core/search/intent_detection.py` (~44 lines)

**Extract:**
- `_INTENT_KEYWORDS` dict — Lines 38–56
- `_INTENT_PARAMS` dict — Lines 58–64
- `_detect_intent()` function — Lines 67–79

**Risk:** TRIVIAL — Pure data + keyword matching

---

### Extraction 4B: `edge_weights` Module (Lines 82–95)
**Target:** `core/search/edge_weights.py` (~13 lines)

**Extract:**
- `EDGE_KIND_WEIGHT` dict — Lines 85–95

**Risk:** TRIVIAL — Constant only

---

### Extraction 4C: `scoring` Module (Lines 1077–1204)
**Target:** `core/search/scoring.py` (~127 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `_adaptive_k_trim()` | 1077 | ~35 |
| `_mmr_rerank()` | 1112 | ~60 |
| `_keyword_boosts()` | 1764 | ~20 |
| `_primer_boosts()` | 1784 | ~25 |

**Total:** ~140 lines

**Risk:** MEDIUM — Math-heavy, has edge cases

---

### Extraction 4D: `trace_expansion` Module (Lines 1403–1749)
**Target:** `core/search/trace_expansion.py` (~346 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `get_context_with_trace_expansion()` | 1403 | ~268 |
| `_inject_module_summary()` | 1672 | ~77 |

**Total:** ~345 lines

**Risk:** HIGH — 804 tests depend on context behavior

---

### Extraction 4E: `context_assembly` Module (Lines 1172–1393)
**Target:** `core/search/context_assembly.py` (~221 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `get_context()` | 1172 | ~64 |
| `get_context_structured()` | 1236 | ~157 |
| `get_chunk()` | 1394 | ~8 |

**Total:** ~229 lines

**Risk:** MEDIUM — Context assembly is finicky

---

### Extraction 4F: `index_lifecycle` Module (Lines 143–350)
**Target:** `core/search/index_lifecycle.py` (~207 lines)

**Functions to extract:**
| Function | Line | Lines |
|----------|------|-------|
| `_load()` | 143 | ~22 |
| `is_loaded()` | 166 | ~5 |
| `stats()` | 172 | ~35 |
| `build()` | 208 | ~472 |
| `_swap_index_dir()` | 681 | ~17 |
| `_cleanup_stale_builds()` | 699 | ~47 |

**Note:** `build()` is very long (472 lines) — consider further splitting into `index_builder.py`

**Total:** ~598 lines (without build) or ~1070 (with build)

**Risk:** MEDIUM — File operations, locking

---

### Refactoring Sequence (Index)

```
Week 1: 4A → 4B → 4F (simple constants → lifecycle)
Week 2: 4C → 4E (scoring → context building)
Week 3: 4D (trace expansion — most complex, most tests)

Target final size: 1,925 → ~700 lines (64% reduction)
```

---

## Cross-Cutting Concerns

### Import Cycle Prevention

After extraction, check for these cycles:
```
# Check with: mcp0_codrag_impact on each new file
mcp0_codrag_impact(file_path="services/pipeline/resume_logic.py")
mcp0_codrag_impact(file_path="mcp/project_resolver.py")
mcp0_codrag_impact(file_path="core/batch_processor.py")
```

### Shared Types

Consider extracting these dataclasses to `core/types.py`:
- `AugmentationEntry` (from augmenter)
- `AugmentResult` (from augmenter)
- `SearchResult` (from index)
- `PipelineRunMetadata` (from orchestrator)

### Test Organization

For each extraction:
1. Move related tests to `tests/<module_path>/`
2. Create `conftest.py` with shared fixtures
3. Update imports in test files

### Re-export Strategy

Keep backward compatibility with re-exports:
```python
# In original file after extraction:
from .resume_logic import _detect_resume_point  # noqa: F401
```

Remove after 2-week burn-in period.

---

## Consolidated Timeline

| Week | Orchestrator | MCP Server | Augmenter | Index |
|------|-------------|------------|-----------|-------|
| 1 | 1A, 1D | 2A, 2B, 2C | 3A, 3B, 3F | 4A, 4B, 4F |
| 2 | 1B, 1E | 2D | 3C, 3D | 4C, 4E |
| 3 | 1C | 2E (daily) | 3E | 4D |
| 4 | Integration | Integration | Integration | Integration |

**Total lines before:** 8,829  
**Total lines after:** ~3,000 (target)  
**Reduction:** 66%

---

## Line Count Summary

### Orchestrator (`orchestrator.py` — 2,356 lines)
| Extraction | Lines | New File Size |
|------------|-------|---------------|
| 1A: sse_bridge | 58 | 58 |
| 1B: resume_logic | 110 | 110 |
| 1C: state_transitions | 206+ | 250 (est.) |
| 1D: metadata_tracker | 130 (est.) | 130 |
| 1E: pause_resume | 130 | 130 |
| **Total moved** | **634+** | **678** |
| **Remaining** | **~1,722** | Target: ~1,400 |

### MCP Server (`server.py` — 2,506 lines)
| Extraction | Lines | New File Size |
|------------|-------|---------------|
| 2A: logging_config | 21 | 21 |
| 2B: protocol_handler | 165 (est.) | 200 (est.) |
| 2C: client_budgets | 30 | 30 |
| 2D: project_resolver | 350 (est.) | 400 (est.) |
| 2E: handlers (9 files) | 984 | 1,000 |
| **Total moved** | **1,550** | **1,651** |
| **Remaining** | **~855** | Target: ~850 |

### Augmenter (`augmenter.py` — 2,042 lines)
| Extraction | Lines | New File Size |
|------------|-------|---------------|
| 3A: prompts/augmentation | 103 | 103 |
| 3B: data_models | 120 | 120 |
| 3C: io_ops | 165 | 165 |
| 3D: synthetic_entries | 75 | 75 |
| 3E: batch_processor | 467 | 467 |
| 3F: node_helpers | 44 | 44 |
| **Total moved** | **974** | **974** |
| **Remaining** | **~1,068** | Target: ~950 |

### Index (`index.py` — 1,925 lines)
| Extraction | Lines | New File Size |
|------------|-------|---------------|
| 4A: intent_detection | 44 | 44 |
| 4B: edge_weights | 13 | 13 |
| 4C: scoring | 140 | 140 |
| 4D: trace_expansion | 345 | 345 |
| 4E: context_assembly | 229 | 229 |
| 4F: index_lifecycle | 207 (without build) | 250 (est.) |
| **Total moved** | **978** | **1,021** |
| **Remaining** | **~904** | Target: ~700 |

---

## Recommended First Step

### Start with 2A: `mcp/logging_config.py`

**Why this first:**
1. **Zero risk** — 21 lines, standalone function
2. **No dependencies** — Only uses stdlib `logging`
3. **Easy verification** — One test: logging still works
4. **Builds confidence** — Quick win for team morale

**Implementation:**
```bash
# 1. Create the new file
touch src/codrag/mcp/logging_config.py

# 2. Move the function (lines 35–56)
# 3. Add re-export in server.py:
from .logging_config import configure_logging  # noqa: F401

# 4. Run tests
pytest tests/mcp/test_logging.py -v

# 5. Merge and deploy
```

**Estimated time:** 30 minutes  
**Risk:** None  
**Tests affected:** 0 (if no tests), or update `test_logging.py`

---

## Pre-Extraction Checklist (Per Module)

Before extracting each module:

- [ ] Read the source lines to confirm they match plan
- [ ] Identify all imports needed in new file
- [ ] Identify all symbols exported to original file
- [ ] Check for circular dependencies with `mcp0_codrag_impact`
- [ ] Create unit tests for the new module
- [ ] Create re-export in original file
- [ ] Run full test suite
- [ ] Measure performance (baseline vs after)
- [ ] Document the extraction in CHANGELOG.md

---

## Post-Extraction Cleanup (After All Modules)

After all 20+ extractions complete:

1. **Remove re-exports** — Delete `# noqa: F401` imports
2. **Update imports** — Change internal imports to direct module paths
3. **Delete empty sections** — Remove comment blocks that no longer apply
4. **Run final audit** — `codrag_audit` to verify god-files are gone
5. **Update docs** — Remove references to old file locations

---

*Last updated: 2026-03-28*  
*Status: Ready for implementation — start with 2A*

---

*Created: 2026-03-28*  
*Based on: Current source analysis*  
*Next step: Create first extraction PR (2A: logging_config)*

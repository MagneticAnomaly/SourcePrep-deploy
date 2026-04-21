# Phase 04 Implementation Plan — Trace Index

This document outlines the step-by-step implementation plan for the **Trace Index** (Codebase Graph), moving from the current backend prototypes to a fully integrated feature with Dashboard UX.

## 1. Current Status (Baseline)

The following core components are **already implemented** (Sprint S-04):
- **Storage:** `trace_nodes.jsonl`, `trace_edges.jsonl`, `trace_manifest.json` persistence.
- **IDs:** Deterministic, stable IDs for files, symbols, and edges (`src/prep/core/ids.py`).
- **Analyzer:** Python AST analyzer extracting functions, classes, and imports (`src/prep/core/trace.py`).
- **API:**
  - `GET /projects/{id}/trace/status`
  - `GET /projects/{id}/trace/search`
  - `GET /projects/{id}/trace/nodes/{node_id}`
  - `GET /projects/{id}/trace/nodes/{node_id}/neighbors`
- **Context:** Trace-aware expansion in `CodeIndex.get_context_with_trace_expansion()`.

## 2. Implementation Phases

### Phase 4.1: Incremental Trace Rebuild (Backend)
**Goal:** Avoid re-parsing the entire codebase when only a few files change.

- [ ] **Dependency:** Phase 03 `changed_paths` availability in `build()`
- [ ] **Logic:**
  1. Load existing `trace_nodes` and `trace_edges` into memory (or temp DB).
  2. Identify `changed_paths` from the build request.
  3. **Prune:** Remove all nodes/edges where `file_path` is in `changed_paths`.
  4. **Re-parse:** Run analyzer only on `changed_paths`.
  5. **Merge:** Append new nodes/edges to the index.
  6. **Re-link:** Re-run import resolution (since a changed file might now resolve an import that was previously external, or vice versa). *Note: This is the hard part; naive incrementalism might miss cross-file edge updates. MVP approach: full rebuild for imports, or accepted staleness until full rebuild.*
- [ ] **Output:** Updated JSONL files.

### Phase 4.2: Dashboard Symbol Browser (Frontend)
**Goal:** Allow users to explore the graph structure visually (list/detail view, not node-link diagram).

- [ ] **Components:**
  - `TracePage`: Main entry point (tab).
  - `SymbolSearch`: Search input hitting `/trace/search`.
  - `SymbolList`: Results table (Kind, Name, File, Location).
  - `SymbolDetailPanel`:
    - Header: Name + Kind + File Link.
    - Metadata: Docstring preview, decorators.
    - `NeighborsList` (Inbound): "Called by / Imported by".
    - `NeighborsList` (Outbound): "Calls / Imports".
- [ ] **Interaction:**
  - Clicking a neighbor navigates to that symbol's detail.
  - "Reveal in File" button opens the file content at the specific line.

### Phase 4.3: Trace-to-Chunk Alignment (Context Quality)
**Goal:** Ensure that when we pull a trace node into context, we pull the *best* text chunk for it.

- [ ] **Strategy:**
  - Currently, we might just include the raw code span.
  - **Improvement:** Map `node.span` to existing `chunks` in `documents.json`.
  - If a node is selected for expansion, prefer including the pre-computed chunk that contains its definition, rather than raw file slicing (which might break formatting).
- [ ] **Cache:** Build a lightweight `node_id -> chunk_id` map during build time if performance requires.

### Phase 4.4: Multi-Language Support (Rust Engine)
**Goal:** Expand beyond Python.

- [ ] **Integration:**
  - The Rust `prep-engine` already supports TS, JS, Go, etc. via Tree-sitter.
  - Ensure `TraceBuilder` correctly delegates to the Rust engine when `PREP_ENGINE=rust` or `auto`.
  - Validate that `node.kind` and `edge.kind` taxonomy aligns across languages (e.g., `class` vs `struct`, `function` vs `method`).

## 3. Testing Plan

### 3.1 Unit Tests
- `tests/test_trace_incremental.py`: Verify that modifying 1 file updates only relevant nodes.
- `tests/test_trace_resolution.py`: Verify imports resolve to correct file nodes.

### 3.2 Integration Tests
- **Full Loop:**
  1. Add Project (Fixtures).
  2. Build (Embeddings + Trace).
  3. Search Trace for "CoreClass".
  4. Verify "CoreClass" has edge to "HelperFunction".
  5. Call Context with `trace_expand=true`.
  6. Verify context includes "HelperFunction" text even if query didn't match it directly.

## 4. Risks & Mitigations

- **Performance:** JSONL files can get large (100MB+) for big repos.
  - *Mitigation:* Stream processing; do not load full graph into Python dicts if not needed. Switch to SQLite for trace storage if JSONL becomes a bottleneck.
- **Graph Explosion:** "God objects" might have 1000s of neighbors.
  - *Mitigation:* Strict caps on `max_nodes` and `max_edges` in API responses.
- **Accuracy:** Dynamic languages (Python/JS) have ambiguous imports.
  - *Mitigation:* "Best effort" resolution. Explicitly mark edges with `confidence < 1.0` if unsure.

## 5. Success Metrics

- **Build Time:** Trace build adds < 20% overhead to total build time.
- **Context Quality:** "Explain how X works" queries show measurable improvement when X's dependencies are pulled in via trace.
- **UX Latency:** Symbol browser navigates in < 200ms.

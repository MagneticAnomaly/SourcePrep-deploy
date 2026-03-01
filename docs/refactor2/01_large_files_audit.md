# Large Files Audit

The following files were identified as exceptionally large and are candidates for refactoring/splitting:

## Python Backend
1. **`src/codrag/core/trace.py`** (2,460 lines)
   - Contains `TraceNode`, `TraceEdge`, `TraceBuilder`, `TraceIndex` and multiple language analyzers (`PythonAnalyzer`, `SwiftAnalyzer`, `GenericRegexAnalyzer`, `JSAnalyzer`).
   - *Optimization Opportunity*: Move language-specific analyzers into their own files under a `src/codrag/core/analyzers/` directory.

2. **`src/codrag/core/atlas.py`** (2,315 lines)
   - Contains `AtlasDocument`, `Segment`, `CodebaseAtlas` and likely prompting/LLM integration logic.
   - *Optimization Opportunity*: Separate the data models, generation logic, and routing logic into an `atlas/` subpackage.

3. **`src/codrag/api/routers/projects.py`** (2,228 lines)
   - Handles project CRUD, build, search, context, watch, files, and legacy endpoints.
   - *Optimization Opportunity*: Extract search/context endpoints into `search.py`, watch endpoints into `watch.py`, and keep `projects.py` purely for CRUD.

4. **`src/codrag/core/augmenter.py`** (1,978 lines)
   - Contains `TraceAugmenter`, LLM integration, and prompting logic.
   - *Optimization Opportunity*: Separate LLM clients/prompts from the core traversal/augmentation logic.

5. **`src/codrag/core/index.py`** (1,926 lines)
   - Contains `CodeIndex`, `SearchResult` and likely dense FAISS/Numpy embedding logic.
   - *Optimization Opportunity*: Separate retrieval/ranking logic from ingestion/build logic.

6. **`src/codrag/mcp_server.py`** (1,784 lines)
   - Contains the main MCP server implementation.
   - *Optimization Opportunity*: Abstract out tool dispatching and project resolution into separate modules.

7. **`src/codrag/api/routers/trace.py`** (1,606 lines)
   - Handles all trace endpoints.
   - *Optimization Opportunity*: Break down into `trace_build.py`, `trace_query.py`, and `trace_enrichment.py`.

8. **`src/codrag/services/pipeline_orchestrator.py`** (1,482 lines)
   - Manages state machine for pipeline stages.
   - *Optimization Opportunity*: Extract individual stage workers into separate files.

9. **`src/codrag/core/cluster.py`** (1,359 lines)
   - Graph clustering algorithms and synthesis.

10. **`src/codrag/cli.py`** (1,320 lines)
    - Command line interface.
    - *Optimization Opportunity*: Group commands into submodules (e.g., `cli_mcp.py`, `cli_pipeline.py`).

## Rust Engine
1. **`engine/crates/codrag-graph/src/lib.rs`** (1,493 lines)
   - Graph representation and PyO3 bindings.
   - *Optimization Opportunity*: Separate PyO3 bindings from the core graph logic.

2. **`engine/crates/codrag-parser/src/typescript.rs`** (992 lines)
   - TypeScript parsing via tree-sitter.

## Frontend (React/TypeScript)
1. **`packages/ui/src/types.ts`** (997 lines)
   - Contains all type definitions.
   - *Optimization Opportunity*: Split into domain-specific types (e.g., `types/project.ts`, `types/trace.ts`, `types/pipeline.ts`).

2. **`packages/ui/src/api/client.ts`** (889 lines)
   - Giant API client class.
   - *Optimization Opportunity*: Divide into separate client modules based on domain.

3. **`src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`** (883 lines)
   - Massive hook for dashboard state.
   - *Optimization Opportunity*: Continue Phase 24 state machine refactor by splitting into smaller hooks.

4. **`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`** (851 lines)
   - *Optimization Opportunity*: Break out individual stage components.

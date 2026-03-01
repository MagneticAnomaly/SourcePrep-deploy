# Architectural Optimizations Audit

Following the large files audit, we've identified several architectural patterns and structural optimizations that can be applied to improve maintainability, separation of concerns, and modularity.

## 1. Backend: Core Engine Decoupling

The `src/codrag/core/` directory contains several "god-objects" and mixed concerns.

### A. Trace Subsystem (`trace.py`)
- **Current State:** A single 2,400+ line file containing data structures (`TraceNode`, `TraceEdge`), construction logic (`TraceBuilder`), querying logic (`TraceIndex`), and language-specific AST parsers (`PythonAnalyzer`, `SwiftAnalyzer`, etc.).
- **Optimization:** Create a `codrag/core/trace/` subpackage.
  - `models.py` (Nodes, Edges, Enums)
  - `builder.py` (TraceBuilder)
  - `index.py` (TraceIndex, querying)
  - `analyzers/` (Language-specific extractors)

### B. Atlas Subsystem (`atlas.py`)
- **Current State:** Mixes Pydantic data models, hardcoded LLM prompt templates, parallel LLM execution, and file I/O into a 2,300+ line file.
- **Optimization:** Create a `codrag/core/atlas/` subpackage.
  - `models.py` (AtlasDocument, Segment, SegmentDescriptor)
  - `prompts.py` (System prompts and instructions)
  - `generator.py` (Core generation logic)
  - `router.py` (Routing embedding generation)

### C. Indexing Subsystem (`index.py` & `augmenter.py`)
- **Current State:** `index.py` handles both building the FAISS/Numpy index and performing search/retrieval queries. `augmenter.py` handles LLM interactions and file parsing.
- **Optimization:** Separate the Write (Build) path from the Read (Search/Context) path (CQRS pattern). 
  - `codrag/core/search/` (Query parsing, context assembly, trace expansion)
  - `codrag/core/indexing/` (Vector ingestion, embeddings)

## 2. Backend: API Layer Refinement

### A. The Projects Router (`projects.py`)
- **Current State:** Even after Phase 23, `projects.py` is 2,200+ lines. It acts as a catch-all for `GET /projects/*` endpoints.
- **Optimization:** Split `projects.py` into a sub-router module:
  - `routers/projects/crud.py` (Create/Read/Update/Delete projects)
  - `routers/projects/search.py` (Search and Context endpoints)
  - `routers/projects/watch.py` (Watcher control endpoints)
  - `routers/projects/files.py` (File tree, file content)

### B. Pipeline Orchestration (`pipeline_orchestrator.py`)
- **Current State:** 1,400+ lines managing an 8-stage state machine.
- **Optimization:** Adopt the Strategy/Command pattern for pipeline stages. Move each stage's logic into `services/pipeline/stages/` so the orchestrator purely manages the DAG and state transitions.

## 3. Frontend: Component & Type Splitting

### A. Type Definitions (`types.ts`)
- **Current State:** A 1,000-line monolith of all TypeScript interfaces.
- **Optimization:** Move to a `packages/ui/src/types/` folder with domain files:
  - `models.ts` (LLM, configs)
  - `project.ts` (Project, Status, Activity)
  - `trace.ts` (Trace nodes, edges, coverage)
  - `pipeline.ts` (Pipeline runs, stages)
  - `index.ts` (Barrel export for backward compatibility)

### B. Massive UI Components
- **Current State:** `GraphEnrichmentPipeline.tsx` (850 lines), `MarketingHero.tsx` (825 lines), `FolderTree.tsx` (720 lines).
- **Optimization:**
  - **Pipeline:** Extract individual stage renderers (e.g., `<ValidationStage />`, `<ClusteringStage />`).
  - **Marketing:** The various hero variants (Neo, Swiss, Glass) should be their own components inside a `components/marketing/heroes/` directory.
  - **FolderTree:** Extract the recursive `TreeNode` component and the complex selection/explosion logic into custom hooks (`useFolderSelection`).

### C. Dashboard Hooks
- **Current State:** `useDashboardPanels.tsx` (880 lines) manages a massive dictionary of props.
- **Optimization:** Continue the Phase 24 state machine refactor. Break down the hook into smaller domain-specific Panel Providers using React Context where appropriate, to avoid returning 120+ flat props.

## 4. MCP Server Abstraction
- **Current State:** `mcp_server.py` (1,700+ lines) mixes protocol handling, project resolution, and tool execution.
- **Optimization:** Extract tool implementations into `codrag/mcp/tools/` and keep `mcp_server.py` strictly focused on the MCP protocol lifecycle and initialization.

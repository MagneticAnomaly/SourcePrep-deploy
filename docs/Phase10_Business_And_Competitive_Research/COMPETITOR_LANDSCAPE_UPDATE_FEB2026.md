# Competitor Landscape Update (Feb 2026)

This document analyzes a new wave of local-first, context-centric AI coding tools and agents, extracting competitive differentiation and actionable product insights for CoDRAG.

## New Competitor Patterns Analyzed

### 1. AST-Based Context Engines (e.g., Vexp)
**What they are:** Local-first context engines distributed as IDE extensions (e.g., VS Code). They use parsers like tree-sitter + local databases (like SQLite) to build an AST graph.
**Key Features Observed:**
- **Hybrid Search Without Embeddings:** Using FTS5 + TF-IDF + Graph Centrality instead of vector embeddings to save overhead.
- **Capsule Context:** Returning full source for pivot nodes, but only signatures/docstrings for adjacent nodes (identical to CoDRAG's LOD compression).
- **LSP Edge Capture:** Capturing runtime type-resolved call edges from the IDE Language Server to supplement static analysis.
- **Session Memory:** Saving observations and cross-session context tied to graph nodes.
**CoDRAG Differentiation:**
- CoDRAG uses true semantic vector search (nomic-embed ONNX) which handles conceptual queries better than TF-IDF, while remaining 100% local.
- CoDRAG has a dedicated dashboard for inspectability and health tracking, not just a background process.
- CoDRAG is a standalone daemon with broader IDE support via MCP, rather than being locked to a single editor extension.

### 2. Epistemic / AI Self-Awareness Frameworks (e.g., Empirica)
**What they are:** Frameworks focused on context continuity and maintaining the agent's epistemic state across sessions.
**Key Features Observed:**
- **Git-Native Coordination:** Storing epistemic checkpoints and reasoning state in `git notes`, allowing distributed, version-controlled coordination without a central server.
- **Mirror Drift Detection:** Tracking capability drops and knowledge degradation across sessions.
- **Preflight/Postflight:** Agents assess their knowledge before and after tasks.
**CoDRAG Differentiation:**
- CoDRAG already implements deep epistemic enrichment (Graph Enrichment Pipeline). However, the use of `git notes` for state persistence is a novel mechanism we could adopt for sharing context across teams.
- CoDRAG is a pure context engine, whereas these are often agent-behavior frameworks that dictate how the AI should act.

### 3. LSP-Backed MCP Servers (e.g., Serena)
**What they are:** Coding agent toolkits providing semantic retrieval and editing by wrapping existing Language Servers.
**Key Features Observed:**
- **IDE-like Tools:** Exposing tools like `find_symbol`, `find_referencing_symbols`, and `insert_after_symbol` to the AI.
- **LSP / IDE Backend:** Using the Language Server Protocol or native IDE plugins to perform semantic analysis instead of parsing code directly.
**CoDRAG Differentiation:**
- CoDRAG builds its own persistent trace graph (tree-sitter + LLM inferred edges) which is offline, faster, and more resilient than requiring an active LSP server to be running and properly configured for every query.
- CoDRAG focuses purely on reading and assembling context, leaving the editing and execution to the agent.

### 4. CLI Semantic Search Tools (e.g., Grepai)
**What they are:** Privacy-first semantic code search command-line tools.
**Key Features Observed:**
- "Grep for the AI era", allowing natural language search over code bases.
- Basic MCP integrations to pass search results to agents.
**CoDRAG Differentiation:**
- These are primarily static search tools. CoDRAG offers a full continuous-enrichment pipeline, auto-rebuilds when files change, and a UI for managing scope and verifying the health of the trace graphs.

### 5. Precomputed Graph RAG (e.g., GitNexus)
**What they are:** Tools that build a complete knowledge graph of the codebase (using Tree-sitter + local graph DBs like KuzuDB) to precompute relational intelligence before the AI agent queries it.
**Key Features Observed:**
- **Precomputed Relational Intelligence:** Precomputing clusters, processes (execution flows), and impact analysis so that a single MCP tool call returns the complete context, instead of requiring the LLM to make multiple iterative queries.
- **Embedded Graph Databases:** Using KuzuDB (with vector support) to run complex Cypher queries over the codebase structure.
- **Wiki Generation:** Leveraging the structured graph to automatically group files into modules and generate comprehensive, cross-referenced documentation.
- **WASM / Browser Architecture:** Offering a version that runs entirely in the browser using WASM (Tree-sitter, KuzuDB, transformers.js) alongside a native Node.js CLI.
**CoDRAG Differentiation:**
- **Architecture & Performance:** CoDRAG uses a high-performance native Rust engine and ONNX embeddings, avoiding the overhead of Node.js or the limitations of browser-based WASM runtimes for large codebases.
- **Continuous Deep Enrichment:** While competitors precompute structural clusters and processes, CoDRAG goes further with our "Trace Epistemology" — continuously enriching the graph with LLM-validated reasoning, epistemic scores, and drift detection across sessions.
- **Focus on the Dashboard:** CoDRAG emphasizes an inspectable, dedicated desktop dashboard for tracking the health and epistemic state of the knowledge base.
- **Shared Vision:** Both tools correctly identify that giving raw graph edges to an LLM (Traditional Graph RAG) is inefficient and prone to failure. This validates CoDRAG's approach of delivering assembled, high-signal "capsule context" (LOD compression) rather than raw relationships.

### 6. Cognitive-Inspired Dual-Hypergraph RAG (e.g., Cog-RAG)
**What they are:** Advanced academic RAG frameworks (arXiv:2511.13201) that model knowledge simultaneously at a global thematic level and a granular entity level, avoiding the limitations of simple pairwise graph connections.
**Key Features Observed:**
- **Dual-Hypergraph Structure:** Maintains two layers of graphs—a *Theme Hypergraph* (for inter-chunk thematic structures) and an *Entity Hypergraph* (for high-order semantic relations between entities/code elements).
- **Hyperedges:** Uses hyperedges to connect *multiple* related entities at once (n-ary relationships), rather than just pairwise (1-to-1) edges common in traditional Graph RAG.
- **Top-Down Cognitive Retrieval:** Implements a two-stage retrieval strategy mimicking human reasoning. It first activates the "theme" (global context) and then uses it to guide fine-grained recall in the entity graph (local details).
**CoDRAG Differentiation:**
- **Architectural Validation:** Cog-RAG's dual-layer approach heavily validates CoDRAG's existing architecture. CoDRAG's *Atlas / Module Clusters* serve the exact role of the "Theme Hypergraph," while our *Trace Graph* serves as the "Entity Hypergraph."
- **Practical vs Academic:** While Cog-RAG uses mathematical hypergraphs, CoDRAG applies this concept pragmatically to software engineering. We use semantic routing (Atlas) to identify the "theme" and then expand through the Trace Graph (LOD compressed neighbors) for the "entity" details.
- **Actionable Insight:** CoDRAG's cluster synthesis could be enhanced to form true "hyperedges" by treating an entire multi-file cluster as a single addressable node during retrieval, ensuring that closely coupled components are activated as a complete set rather than relying purely on transitive pairwise hops.

## Proposed Code / Feature Changes (Easy Wins)

1. **LSP Edge Ingestion:**
   - **Idea:** Supplement our tree-sitter static trace graph with type-resolved edges from the user's IDE Language Server.
   - **Implementation:** Add an MCP tool `codrag_submit_lsp_edges` or a VS Code extension hook that sends active LSP call-graph data to CoDRAG's `/trace/inferred_edges` endpoint. This bypasses the need for LLM-inferred edges for supported languages and provides perfect accuracy.

2. **Git-Native Epistemic Checkpoints:**
   - **Idea:** Store the pipeline's module summaries and deep enrichment states in `git notes` instead of just `.codrag_data/` SQLite/JSON.
   - **Implementation:** This allows teammates to pull the repo and instantly share the AI's "understanding" of the codebase without needing a centralized vector DB. It fits our "Local-First" ethos perfectly.

3. **Impact Graph Tool:**
   - **Idea:** We already have the trace graph. We should expose a specific MCP tool called `codrag_impact_graph` or `codrag_blast_radius`.
   - **Implementation:** When a user asks "What happens if I change X?", this tool traverses reverse-dependencies (callers, importers) and returns the LOD-compressed signatures of everything that depends on X.

4. **Session Memory / Observations:**
   - **Idea:** Allow the agent to write observations linked to specific nodes in the trace graph.
   - **Implementation:** `save_observation` MCP tool that attaches a note to a trace node. When the node changes, the memory is marked "stale" via our existing DriftDetector.

5. **Cluster Hyperedges (Inspired by Cog-RAG):**
   - **Idea:** Enhance our search retrieval to treat synthesized Module Clusters as "Hyperedges" that group multiple files together.
   - **Implementation:** When a search query strongly matches a Cluster/Module summary, automatically inject a lightweight (LOD 4/5) representation of *all* files in that cluster to provide high-order structural context without doing individual file lookups.

## Proposed Marketing and Messaging Changes

1. **Sharpen the "Embeddings vs. TF-IDF" Narrative:**
   - Some competitors boast about "No Embeddings" to claim speed. We need to clearly articulate *why* ONNX-native embeddings (which we shipped in Phase 16) are superior to basic TF-IDF for conceptual searches (e.g., matching "authentication" to "login"), while still being 100% local, offline, and blazingly fast.

2. **Highlight "Inspectable Context":**
   - Many tools operate invisibly in the background. CoDRAG has a beautiful Dashboard. Our messaging should emphasize: *"Don't fly blind. See exactly what your AI sees. Inspect the graph, view the health score, and control the context budget."*
   - Position the Dashboard as the key to trust.

3. **Position Epistemology as a Differentiator:**
   - We already have a "Graph Enrichment Pipeline" that computes "Understanding Scores". We should lean into this: *"CoDRAG doesn't just index code; it builds an epistemic understanding of your modules."* Make it clear we've already built the deep reasoning pipeline that other tools are just starting to explore.

4. **The "Companion, not a framework" Pitch:**
   - Clarify that CoDRAG is an MCP-first companion that supercharges existing tools (Cursor, Windsurf, Claude), rather than trying to dictate agent behavior or handle file editing itself. CoDRAG is the ultimate Read-Only Context Engine.

5. **"Dual-Layer Cognitive Retrieval" Narrative:**
   - Adopt the terminology from state-of-the-art research. Describe CoDRAG's Atlas + Trace combination as a "Cognitive Dual-Graph" that reasons top-down from global themes (Modules/Atlas) to local details (Trace Graph), matching how human engineers understand code.

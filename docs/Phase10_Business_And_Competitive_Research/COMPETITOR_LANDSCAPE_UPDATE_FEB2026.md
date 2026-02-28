# Competitor Landscape Update (Feb 2026)

This document analyzes a new wave of local-first, context-centric AI coding tools and agents, extracting competitive differentiation and actionable product insights for CoDRAG.

## New Competitors Analyzed

### 1. Vexp (vexp.dev)
**What it is:** A local-first context engine distributed as a VS Code extension. Uses tree-sitter + SQLite to build an AST graph.
**Key Features:**
- **Hybrid Search Without Embeddings:** Uses FTS5 + TF-IDF + Graph Centrality instead of vector embeddings.
- **Capsule Context:** Returns full source for pivot nodes, but only signatures/docstrings for adjacent nodes (identical to CoDRAG's LOD compression).
- **LSP Edge Capture:** Captures runtime type-resolved call edges from the VS Code Language Server to supplement static analysis.
- **Session Memory:** Saves observations and cross-session context.
**CoDRAG Differentiation:**
- CoDRAG uses true semantic vector search (nomic-embed ONNX) which handles conceptual queries better than TF-IDF.
- CoDRAG has a dedicated dashboard for inspectability and health tracking.
- Vexp relies entirely on VS Code; CoDRAG is a standalone daemon with broader IDE support via MCP.

### 2. Empirica (getempirica.com)
**What it is:** An "AI Self-Awareness" framework focused on context continuity and epistemic state.
**Key Features:**
- **Git-Native Coordination:** Stores epistemic checkpoints and reasoning state in `git notes`, allowing distributed, version-controlled coordination without a central server.
- **Mirror Drift Detection:** Tracks capability drops and knowledge degradation across sessions.
- **Preflight/Postflight:** Agents assess their knowledge before and after tasks.
**CoDRAG Differentiation:**
- CoDRAG already implements deep epistemic enrichment (Graph Enrichment Pipeline), but Empirica's use of `git notes` for state persistence is a novel mechanism we could adopt.
- CoDRAG is a context engine; Empirica is more of an agent-behavior framework.

### 3. Serena (github.com/oraios/serena)
**What it is:** A coding agent toolkit (MCP server) providing semantic retrieval and editing.
**Key Features:**
- **IDE-like Tools:** Exposes tools like `find_symbol`, `find_referencing_symbols`, and `insert_after_symbol`.
- **LSP / JetBrains Backend:** Uses the Language Server Protocol or a JetBrains plugin to perform semantic analysis instead of its own parser.
**CoDRAG Differentiation:**
- CoDRAG builds its own persistent trace graph (tree-sitter + LLM inferred edges) which is faster and more resilient than querying an active LSP server for every node.
- Serena provides editing tools; CoDRAG focuses purely on reading/assembling context.

### 4. Grepai (yoanbernabeu.github.io/grepai)
**What it is:** A privacy-first semantic code search CLI.
**Key Features:**
- "Grep for the AI era", allowing natural language search over code bases.
- MCP integration for Claude Code, Cursor, etc.
**CoDRAG Differentiation:**
- Grepai is primarily a CLI search tool. CoDRAG offers a full continuous-enrichment pipeline, auto-rebuilds, and a UI for managing scope and trace graphs.

## Proposed Code / Feature Changes (Easy Wins)

1. **LSP Edge Ingestion (from Vexp):**
   - **Idea:** Supplement our tree-sitter static trace graph with type-resolved edges from the user's IDE Language Server.
   - **Implementation:** Add an MCP tool `codrag_submit_lsp_edges` or a VS Code extension hook that sends active LSP call-graph data to CoDRAG's `/trace/inferred_edges` endpoint. This bypasses the need for LLM-inferred edges for supported languages and provides perfect accuracy.

2. **Git-Native Epistemic Checkpoints (from Empirica):**
   - **Idea:** Store the pipeline's module summaries and deep enrichment states in `git notes` instead of just `.codrag_data/` SQLite/JSON.
   - **Implementation:** This allows teammates to pull the repo and instantly share the AI's "understanding" of the codebase without needing a centralized vector DB. It fits our "Local-First" ethos perfectly.

3. **Impact Graph Tool (from Vexp / Serena):**
   - **Idea:** We already have the trace graph. We should expose a specific MCP tool called `codrag_impact_graph` or `codrag_blast_radius`.
   - **Implementation:** When a user asks "What happens if I change X?", this tool traverses reverse-dependencies (callers, importers) and returns the LOD-compressed signatures of everything that depends on X.

4. **Session Memory / Observations (from Vexp):**
   - **Idea:** Allow the agent to write observations linked to specific nodes in the trace graph.
   - **Implementation:** `save_observation` MCP tool that attaches a note to a trace node. When the node changes, the memory is marked "stale" via our existing DriftDetector.

## Proposed Marketing and Messaging Changes

1. **Sharpen the "Embeddings vs. LSP/TF-IDF" Narrative:**
   - Competitors like Vexp boast about "No Embeddings" to claim speed. We need to clearly articulate *why* ONNX-native embeddings (which we shipped in Phase 16) are superior to TF-IDF for conceptual searches (e.g., matching "authentication" to "login"), while still being 100% local, offline, and blazingly fast.

2. **Highlight "Inspectable Context":**
   - Serena and Vexp operate mostly in the background. CoDRAG has a beautiful Dashboard. Our messaging should emphasize: *"Don't fly blind. See exactly what your AI sees. Inspect the graph, view the health score, and control the context budget."* 
   - Position the Dashboard as the key to trust.

3. **Position Epistemology as a Differentiator:**
   - Empirica uses the term "Epistemic Noesis". We already have a "Graph Enrichment Pipeline" that computes "Understanding Scores". We should lean into this: *"CoDRAG doesn't just index code; it builds an epistemic understanding of your modules."* Make it clear we've already built the deep reasoning pipeline.

4. **The "Companion, not a framework" Pitch:**
   - Clarify that CoDRAG is an MCP-first companion that supercharges Cursor/Windsurf/Claude, unlike Empirica which tries to dictate agent behavior, or Serena which tries to handle file editing. CoDRAG is the ultimate Read-Only Context Engine.

# Competitor Landscape Update (Feb 2026)

This document analyzes a new wave of local-first, context-centric AI coding tools and agents, extracting competitive differentiation and actionable product insights for CoDRAG.

## New Competitor Patterns Analyzed

### 1. AST-Based Context Engines
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

### 2. Epistemic / AI Self-Awareness Frameworks
**What they are:** Frameworks focused on context continuity and maintaining the agent's epistemic state across sessions.
**Key Features Observed:**
- **Git-Native Coordination:** Storing epistemic checkpoints and reasoning state in `git notes`, allowing distributed, version-controlled coordination without a central server.
- **Mirror Drift Detection:** Tracking capability drops and knowledge degradation across sessions.
- **Preflight/Postflight:** Agents assess their knowledge before and after tasks.
**CoDRAG Differentiation:**
- CoDRAG already implements deep epistemic enrichment (Graph Enrichment Pipeline). However, the use of `git notes` for state persistence is a novel mechanism we could adopt for sharing context across teams.
- CoDRAG is a pure context engine, whereas these are often agent-behavior frameworks that dictate how the AI should act.

### 3. LSP-Backed MCP Servers
**What they are:** Coding agent toolkits providing semantic retrieval and editing by wrapping existing Language Servers.
**Key Features Observed:**
- **IDE-like Tools:** Exposing tools like `find_symbol`, `find_referencing_symbols`, and `insert_after_symbol` to the AI.
- **LSP / IDE Backend:** Using the Language Server Protocol or native IDE plugins to perform semantic analysis instead of parsing code directly.
**CoDRAG Differentiation:**
- CoDRAG builds its own persistent trace graph (tree-sitter + LLM inferred edges) which is offline, faster, and more resilient than requiring an active LSP server to be running and properly configured for every query.
- CoDRAG focuses purely on reading and assembling context, leaving the editing and execution to the agent.

### 4. CLI Semantic Search Tools
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

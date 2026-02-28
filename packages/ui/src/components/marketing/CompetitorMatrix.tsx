import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Check, X, Minus, ArrowRight, Info } from 'lucide-react';

export interface CompetitorMatrixProps {
  className?: string;
}

type Status = 'full' | 'partial' | 'none';

interface Competitor {
  id: string;
  name: string;
  category: string;
}

const competitors: Competitor[] = [
  { id: 'gitnexus', name: 'GitNexus', category: 'Precomputed RAG' },
  { id: 'vexp', name: 'Vexp', category: 'AST Context Engine' },
  { id: 'empirica', name: 'Empirica', category: 'Epistemic Agents' },
  { id: 'serena', name: 'Serena', category: 'LSP Agent Toolkit' },
  { id: 'grepai', name: 'Grepai', category: 'CLI Semantic Search' },
  { id: 'bloop', name: 'bloop', category: 'AST Search Tools' },
];

const tandemTools = [
  { id: 'cursor', name: 'Cursor', category: 'AI IDE', desc: 'Connect CoDRAG via MCP to give Cursor perfect project-wide context without copying files.' },
  { id: 'windsurf', name: 'Windsurf', category: 'AI IDE', desc: 'Windsurf agents use CoDRAG to autonomously navigate the trace graph before editing.' },
  { id: 'cline', name: 'Cline / Roo', category: 'VS Code Extension', desc: 'Stop dropping raw files into context. Give your agent the CoDRAG LOD capsule instead.' },
  { id: 'claude', name: 'Claude Code', category: 'CLI Agent', desc: "Supercharge Anthropic's CLI with blazing-fast local ONNX semantic routing." },
];

interface CellData {
  text: string;
  status: Status;
  detail: string;
}

interface FeatureRow {
  category: string;
  features: {
    id: string;
    name: string;
    description: string;
    codrag: CellData;
    competitors: Record<string, CellData>;
  }[];
}

const matrixData: FeatureRow[] = [
  {
    category: 'Architecture & Parsing',
    features: [
      {
        id: 'graph',
        name: 'Graph Construction',
        description: 'How the codebase is parsed and understood',
        codrag: {
          text: 'Native Rust Engine (Tree-sitter)',
          status: 'full',
          detail: "CoDRAG's Rust-native parser uses Tree-sitter to build a complete structural trace graph offline. Unlike tools that depend on an active IDE or LSP server, CoDRAG works headlessly \u2014 in CI/CD, on servers, or anywhere Rust runs. The parser handles 15+ languages and produces call-graph, import, and containment edges in a single pass.",
        },
        competitors: {
          gitnexus: {
            text: 'Node.js / WASM',
            status: 'partial',
            detail: "GitNexus uses a Node.js/WASM architecture with Tree-sitter running in JavaScript. This works well for smaller repos, and their browser-based WASM option is genuinely innovative \u2014 zero installation needed. However, the Node.js runtime adds overhead for large codebases, and the browser sandbox limits memory. CoDRAG's native Rust engine is significantly faster for repos over 10K files.",
          },
          vexp: {
            text: 'SQLite / Tree-sitter',
            status: 'partial',
            detail: "Vexp builds an AST graph using Tree-sitter stored in SQLite. This is a solid, well-engineered approach \u2014 fast for moderate repos and tightly integrated with VS Code. However, Vexp is locked to VS Code as its distribution mechanism. CoDRAG's standalone daemon works with any editor via MCP, can run headlessly for CI/CD team builds, and enriches the graph with LLM-inferred edges beyond what static parsing provides.",
          },
          empirica: {
            text: 'Git Notes / No Graph',
            status: 'none',
            detail: "Empirica doesn't build a code graph at all. It focuses on epistemic state tracking via git notes \u2014 a fundamentally different philosophy. This is powerful for agent coordination and tracking what the AI thinks it knows, but provides no structural understanding of how the codebase is organized. CoDRAG combines structural graph analysis with epistemic enrichment, giving you both.",
          },
          serena: {
            text: 'Active LSP Server',
            status: 'partial',
            detail: "Serena delegates all parsing to an active Language Server running in your IDE. This gives perfect type-resolved accuracy when the LSP is available \u2014 genuinely better than static analysis for type inference. However, it fails when the server isn't running, isn't configured for your language, or in headless environments. CoDRAG's offline Rust parser works without any running IDE process and produces a persistent graph that survives restarts.",
          },
          grepai: {
            text: 'Text Index',
            status: 'none',
            detail: "Grepai builds a basic text index for semantic search but doesn't parse code structure at all. There are no call-graph edges, no containment relationships, and no module boundaries. It's a powerful search tool, but CoDRAG provides full structural understanding on top of semantic search.",
          },
          bloop: {
            text: 'Rust (Tree-sitter)',
            status: 'full',
            detail: "bloop also uses a Rust-native Tree-sitter parser, matching CoDRAG's parsing quality and speed. Their AST analysis is solid and well-engineered \u2014 credit where it's due. Where CoDRAG differentiates is in what happens after parsing: CoDRAG enriches the graph with LLM-inferred edges, epistemic understanding scores, and continuous deep analysis that evolves over time.",
          },
        },
      },
      {
        id: 'search',
        name: 'Search Architecture',
        description: 'How relevant context is found',
        codrag: {
          text: 'Local ONNX Embeddings + BM25',
          status: 'full',
          detail: "CoDRAG combines local ONNX embeddings (nomic-embed-text-v1.5) with BM25 keyword search in a hybrid architecture. Semantic search handles conceptual queries ('find the authentication flow') while BM25 catches exact identifiers ('handleLogin'). Everything runs 100% locally with no cloud dependency \u2014 embedding latency is ~7ms per query. Intent-aware routing automatically picks the best strategy per query.",
        },
        competitors: {
          gitnexus: {
            text: 'KuzuDB / FTS',
            status: 'partial',
            detail: "GitNexus uses KuzuDB (an embedded graph database with vector support) and full-text search. This is a capable architecture, especially strong for graph traversal queries like 'what calls this function?' GitNexus deserves credit for integrating graph-native vector search. CoDRAG's advantage is the hybrid BM25+ONNX approach with intent-aware routing that automatically detects whether a query needs semantic, structural, or trace-based search.",
          },
          vexp: {
            text: 'FTS5 + TF-IDF (No Embeddings)',
            status: 'partial',
            detail: "Vexp explicitly avoids embeddings, using FTS5 + TF-IDF + graph centrality instead. They position this as faster and simpler, and for exact keyword matches, it works very well. But TF-IDF fundamentally cannot match 'authentication' to 'login' \u2014 it only finds literal string overlaps. CoDRAG's ONNX embeddings handle conceptual similarity while still being fully local and completing in under 10ms.",
          },
          empirica: {
            text: 'Git Commit Hashes',
            status: 'none',
            detail: "Empirica doesn't provide code search. It references code via git commit hashes and file paths \u2014 its purpose is tracking the agent's epistemic state, not finding relevant code. These are complementary concerns, not competing ones.",
          },
          serena: {
            text: 'LSP Queries',
            status: 'none',
            detail: "Serena queries the running Language Server for symbol lookups (find_symbol, find_references). This gives perfect accuracy for structured queries but cannot handle natural language or conceptual searches. You can ask 'find all callers of handleLogin' but not 'find the authentication flow.' CoDRAG handles both structured and natural language queries.",
          },
          grepai: {
            text: 'Local Semantic Index',
            status: 'partial',
            detail: "Grepai provides solid local semantic search with a privacy-first local embedding index. It handles natural language queries well and has clean MCP integration. However, it's purely a search tool \u2014 no graph traversal, no trace expansion, no module-aware routing. CoDRAG layers semantic search on top of a full trace graph that understands call relationships and module boundaries.",
          },
          bloop: {
            text: 'Local Qdrant / Vector',
            status: 'partial',
            detail: "bloop uses Qdrant (a local vector database) for semantic search. Their approach is well-engineered and handles semantic queries effectively. CoDRAG's advantage is the hybrid BM25+ONNX approach combined with intent-aware routing and trace-based expansion \u2014 when a function is found, CoDRAG automatically includes its callers, callees, and module context.",
          },
        },
      },
    ],
  },
  {
    category: 'Context Assembly',
    features: [
      {
        id: 'delivery',
        name: 'Context Delivery',
        description: 'What the AI actually receives',
        codrag: {
          text: 'LOD (Level of Detail) Capsule Context',
          status: 'full',
          detail: "CoDRAG delivers LOD capsule context: full source for focal nodes, signatures+docstrings for adjacent nodes, and module summaries for distant context. This gives the AI a natural zoom-in/zoom-out perspective that mirrors how human developers understand code. The result is rich, structured context that maximizes signal per token.",
        },
        competitors: {
          gitnexus: {
            text: 'Precomputed Raw Graph Data',
            status: 'partial',
            detail: "GitNexus precomputes clusters and execution flows, then returns the raw graph data. This is more structured than sending raw files \u2014 the AI gets relational context instead of flat text. However, the AI still needs to parse the graph relationships itself. CoDRAG pre-assembles the context into human-readable capsules so the AI doesn't waste tokens interpreting graph structure.",
          },
          vexp: {
            text: 'Capsule Context',
            status: 'full',
            detail: "Vexp implements capsule context very similarly to CoDRAG \u2014 full source for pivot nodes, signatures for neighbors. Credit where it's due: this is one of the closest approaches to CoDRAG's LOD system and validates the core idea. The difference is CoDRAG's dual-engine compression and module-summary injection, which provide additional layers of context beyond what Vexp includes, plus CoDRAG's dashboard lets you visually inspect the assembled capsule before it's sent.",
          },
          empirica: {
            text: 'Reasoning Checkpoints',
            status: 'partial',
            detail: "Empirica delivers epistemic reasoning checkpoints \u2014 what the agent knew, what it learned, what changed. This is valuable for agent coordination but is orthogonal to code context delivery. It tells the agent about its own state, not about the codebase structure. Both types of context are useful; CoDRAG focuses on the code side.",
          },
          serena: {
            text: 'Raw Symbol Matches',
            status: 'none',
            detail: "Serena returns raw symbol definitions and references from the LSP. These are accurate but uncompressed \u2014 you get the full function body, all references, with no prioritization or level-of-detail control. CoDRAG's LOD compression ensures the AI receives the right level of detail for each piece of context based on its distance from the focal point.",
          },
          grepai: {
            text: 'Raw File Chunks',
            status: 'none',
            detail: "Grepai returns raw file chunks matching the search query. There's no structural awareness, no LOD compression, and no context about how the matched code relates to the rest of the codebase. The search quality is good, but the delivery format wastes tokens on irrelevant surrounding code.",
          },
          bloop: {
            text: 'Raw Snippets',
            status: 'none',
            detail: "bloop returns raw code snippets matching the search query. The snippets are accurate and include surrounding context lines for readability, which is a nice touch. However, they lack structural context \u2014 there's no information about callers, imports, or module relationships that would help the AI understand how the code fits into the larger system.",
          },
        },
      },
      {
        id: 'tokens',
        name: 'Token Efficiency',
        description: 'Minimizing distractor tokens',
        codrag: {
          text: 'Dual-Engine Compression (3\u201320x)',
          status: 'full',
          detail: "CoDRAG achieves 3\u201320x token compression through a dual-engine approach: LOD-based structural compression (signatures instead of full bodies) and module-summary injection (one paragraph replacing hundreds of lines). In benchmarks, this reduces the average context window from ~15K tokens to 2\u20135K tokens while retaining the information the AI actually needs. The compression level adapts dynamically per query.",
        },
        competitors: {
          gitnexus: {
            text: 'High (via Precomputation)',
            status: 'partial',
            detail: "GitNexus achieves high efficiency through precomputation \u2014 complex graph queries are resolved before the AI asks, so the response is already focused. This is a legitimate efficiency win that we respect. However, the precomputed responses are static and can't adapt their compression level based on the specific query. CoDRAG dynamically adjusts LOD per query, compressing more aggressively for broad questions and less for targeted ones.",
          },
          vexp: {
            text: 'High (Signature Only)',
            status: 'partial',
            detail: "Vexp achieves good efficiency by returning only signatures for non-focal nodes. This is the same core strategy as CoDRAG's LOD system, and it works well. Vexp's compression is query-adaptive and effective. CoDRAG's additional edge comes from module-summary injection (providing project-level context that Vexp doesn't include) and the dual BM25+semantic scoring that better prioritizes which nodes to include at all.",
          },
          empirica: {
            text: 'Low (State Dumps)',
            status: 'none',
            detail: "Empirica's epistemic state dumps can be verbose \u2014 serialized reasoning chains and pre/postflight checkpoints aren't optimized for token budgets. The content is high-value but the format isn't compressed.",
          },
          serena: {
            text: 'Low (Full Symbols)',
            status: 'none',
            detail: "Serena returns full symbol bodies from the LSP. A single find_references call can return thousands of tokens of raw code. There's no compression, prioritization, or level-of-detail control.",
          },
          grepai: {
            text: 'Low (Sends full chunks)',
            status: 'none',
            detail: "Grepai sends full file chunks matching the search. No compression, no structural awareness of what parts of the chunk are relevant to the query.",
          },
          bloop: {
            text: 'Low (Full snippets)',
            status: 'none',
            detail: "bloop sends full code snippets with surrounding context. This is helpful for readability but increases token count significantly. There's no structural compression or level-of-detail control.",
          },
        },
      },
    ],
  },
  {
    category: 'Epistemology & Trust',
    features: [
      {
        id: 'enrichment',
        name: 'Continuous Enrichment',
        description: 'Refining understanding over time',
        codrag: {
          text: 'Trace Epistemology Pipeline',
          status: 'full',
          detail: "CoDRAG's Trace Epistemology Pipeline continuously enriches the knowledge graph: deep analysis generates module summaries, cross-module relationship analysis, and understanding scores. Each pipeline run builds on previous results, and the file watcher triggers incremental re-enrichment when code changes. The result is a knowledge base that gets measurably smarter over time \u2014 visible in the dashboard's health scores.",
        },
        competitors: {
          gitnexus: {
            text: 'Static until re-indexed',
            status: 'none',
            detail: "GitNexus builds its graph once and serves it statically until explicitly re-indexed. There's no continuous learning or enrichment between builds. For stable codebases this is fine, but for active development, the index quickly becomes stale.",
          },
          vexp: {
            text: 'Session Memory',
            status: 'partial',
            detail: "Vexp supports session memory \u2014 agents can save observations attached to graph nodes, and these persist across sessions. This is a thoughtful feature that enables incremental learning. However, it relies entirely on the agent to drive enrichment by writing good observations. CoDRAG's pipeline runs automatically in the background with no agent involvement needed, producing structured module summaries and understanding scores.",
          },
          empirica: {
            text: 'Git-Native Pre/Postflight',
            status: 'full',
            detail: "Empirica genuinely excels here. Its pre/postflight system has agents assess their knowledge before and after tasks, storing these assessments in git notes for version-controlled epistemic continuity. This creates real cross-session learning. CoDRAG's pipeline is more automated (no agent involvement needed) and produces structured graph enrichment, but Empirica's approach to tracking what the agent thinks it knows is innovative and we tip our hat to it.",
          },
          serena: {
            text: 'None',
            status: 'none',
            detail: "Serena provides no enrichment. It queries the LSP in real-time and returns results. There's no persistent knowledge accumulation between sessions.",
          },
          grepai: {
            text: 'None',
            status: 'none',
            detail: "Grepai rebuilds its index from scratch on each run. No continuous enrichment or persistent learning.",
          },
          bloop: {
            text: 'None',
            status: 'none',
            detail: "bloop rebuilds its index from scratch. No continuous enrichment or persistent learning between index builds.",
          },
        },
      },
      {
        id: 'drift',
        name: 'Drift Detection',
        description: 'Knowing when agent assumptions are stale',
        codrag: {
          text: 'Automated via Watcher & Graph',
          status: 'full',
          detail: "CoDRAG's file watcher monitors the codebase for changes and automatically marks affected trace nodes, observations, and enrichment data as stale. When a function changes, all observations about that function are flagged. The dashboard shows drift status at a glance with per-node granularity. No manual intervention needed.",
        },
        competitors: {
          gitnexus: {
            text: 'Manual git-diff checks',
            status: 'partial',
            detail: "GitNexus can detect changes via git-diff but requires manual re-indexing to update the knowledge graph. There's no automatic staleness tracking for individual nodes \u2014 the entire index is either current or it isn't.",
          },
          vexp: {
            text: 'Manual Observation Staling',
            status: 'partial',
            detail: "Vexp marks observations as stale when their linked nodes change \u2014 a correct and useful approach. However, this only works for nodes that have agent-written observations attached. There's no automatic detection of semantic drift in the broader graph for nodes without observations.",
          },
          empirica: {
            text: 'Mirror Drift Detection',
            status: 'full',
            detail: "Empirica's Mirror Drift Detection is genuinely strong. It tracks capability drops and knowledge degradation across sessions, alerting when the agent's understanding has become unreliable. This is one of Empirica's best features \u2014 they focus deeply on epistemic reliability. CoDRAG's approach is more granular (per-node vs per-session) and more visual (dashboard vs git log), but Empirica deserves real credit for pioneering this concept.",
          },
          serena: {
            text: 'None',
            status: 'none',
            detail: "Serena has no drift detection. It queries the LSP live, so in theory results are always current \u2014 but it has no concept of tracking what changed or what assumptions from previous sessions might be stale.",
          },
          grepai: {
            text: 'None',
            status: 'none',
            detail: "No drift detection. The index must be manually rebuilt when code changes.",
          },
          bloop: {
            text: 'None',
            status: 'none',
            detail: "No drift detection. The index must be manually rebuilt when code changes.",
          },
        },
      },
      {
        id: 'inspect',
        name: 'Inspectability',
        description: 'Seeing what the AI sees',
        codrag: {
          text: 'Dedicated Desktop Health Dashboard',
          status: 'full',
          detail: "CoDRAG's dedicated desktop dashboard lets you visually browse the trace graph, see module health scores, inspect enrichment pipeline status, and fine-tune scope with a folder tree. You can see exactly what context the AI will receive before it receives it. This bird's-eye perspective of your codebase builds trust and gives developers real control over the AI's knowledge.",
        },
        competitors: {
          gitnexus: {
            text: 'Web UI / Terminal',
            status: 'partial',
            detail: "GitNexus offers a web UI and terminal interface for browsing the graph. The web UI is functional and shows precomputed clusters and wiki documentation. It's less purpose-built for context-inspection than CoDRAG's dashboard but provides reasonable visibility into the knowledge graph.",
          },
          vexp: {
            text: 'VS Code Only',
            status: 'partial',
            detail: "Vexp operates as a VS Code extension with in-editor views. You can see the graph within VS Code, which is convenient and well-integrated. However, it's limited to VS Code users and doesn't offer the birds-eye project health view with health scores, scope management, and enrichment pipeline monitoring that CoDRAG's standalone dashboard provides.",
          },
          empirica: {
            text: 'Git Log Only',
            status: 'none',
            detail: "Empirica stores everything in git notes, viewable via git log. This is maximally transparent \u2014 everything is version-controlled and auditable, which is admirable. But it requires git expertise to inspect and there's no visual dashboard for at-a-glance understanding of the epistemic state.",
          },
          serena: {
            text: 'Opaque',
            status: 'none',
            detail: "Serena is largely opaque. The MCP tools execute and return results, but there's no interface to see what the system 'knows,' how it's reasoning about the codebase, or what context it would assemble for a given query.",
          },
          grepai: {
            text: 'Terminal Only',
            status: 'none',
            detail: "Grepai is a CLI tool \u2014 terminal output only. You can see search results but there's no way to visualize the index, understand coverage gaps, or inspect what context would be assembled.",
          },
          bloop: {
            text: 'Desktop App',
            status: 'full',
            detail: "bloop has a dedicated desktop app with a polished code search UI. Credit where it's due \u2014 bloop's search interface is clean, fast, and pleasant to use. However, it focuses on search results rather than graph health, enrichment status, or context assembly inspection. CoDRAG's dashboard is specifically built for understanding and controlling the AI's knowledge, not just searching code.",
          },
        },
      },
    ],
  },
  {
    category: 'Control & Customization',
    features: [
      {
        id: 'scope',
        name: 'Scope Management',
        description: 'Controlling what the AI can see',
        codrag: {
          text: 'Visual Folder-Tree with Include/Exclude',
          status: 'full',
          detail: "CoDRAG provides a visual folder-tree in the dashboard for precise scope control. Include or exclude entire directories, individual files, or use glob patterns. Changes take effect immediately and the dashboard shows exactly which files are in-scope, how many nodes are indexed, and what percentage of the codebase is covered. This gives developers fine-grained control over the AI's view of the project.",
        },
        competitors: {
          gitnexus: {
            text: '.gitignore-style Patterns',
            status: 'partial',
            detail: "GitNexus uses .gitignore-style patterns for scope control. This is functional and familiar to developers, but there's no visual interface \u2014 you edit config files directly. You can't easily see at a glance which files are included or excluded, or what percentage of your codebase is covered.",
          },
          vexp: {
            text: 'VS Code Workspace Scope',
            status: 'partial',
            detail: "Vexp scopes to the VS Code workspace and supports include/exclude patterns in settings. This is adequate for single-workspace projects. However, there's no visual tree view for managing scope, and the settings are buried in VS Code's configuration UI rather than being front-and-center in a purpose-built dashboard.",
          },
          empirica: {
            text: 'Git Repo Scope Only',
            status: 'none',
            detail: "Empirica scopes to the entire git repository. There's no fine-grained file or folder control. This makes sense for its epistemic-tracking purpose but doesn't allow developers to focus the AI on specific areas of a large monorepo.",
          },
          serena: {
            text: 'LSP Workspace Scope',
            status: 'none',
            detail: "Serena scopes to whatever the LSP can see. There's no independent scope configuration. If the Language Server indexes it, Serena can query it; if not, it can't.",
          },
          grepai: {
            text: 'CLI Path Arguments',
            status: 'none',
            detail: "Grepai accepts path arguments on the command line. This is basic but functional for one-off searches. There's no persistent scope configuration or visual management.",
          },
          bloop: {
            text: 'Repo-Level Selection',
            status: 'partial',
            detail: "bloop lets you choose which repositories to index. This is scope control at the repo level, which is useful for multi-repo setups. However, there's no file-level or folder-level control within a repo, and no visual tree for fine-tuning what's included.",
          },
        },
      },
      {
        id: 'weighting',
        name: 'Edge & Module Weighting',
        description: 'Prioritizing what matters most in the graph',
        codrag: {
          text: 'Configurable Edge Weights + Module Importance',
          status: 'full',
          detail: "CoDRAG assigns edge weights by kind (call, import, containment, inferred, LSP) that affect trace expansion priority. Module importance scores from the enrichment pipeline influence which context gets included first when token budgets are tight. The dashboard exposes these weights, letting developers fine-tune how the graph prioritizes different parts of the codebase \u2014 for example, boosting your core business logic over utility helpers.",
        },
        competitors: {
          gitnexus: {
            text: 'Graph Centrality Metrics',
            status: 'partial',
            detail: "GitNexus uses graph centrality metrics to rank nodes in its precomputed clusters. This implicitly weights important hub files higher. It's an automated, sensible approach. However, there are no user-facing controls to override the heuristics \u2014 you can't tell the system that your 'auth' module matters more than your 'utils' module.",
          },
          vexp: {
            text: 'Graph Centrality in Ranking',
            status: 'partial',
            detail: "Vexp incorporates graph centrality into its search ranking. Similar concept to CoDRAG's edge weights but not user-configurable. The ranking is purely algorithmic with no developer input on priorities.",
          },
          empirica: {
            text: 'N/A',
            status: 'none',
            detail: "Empirica doesn't model code structure, so graph weighting isn't applicable to its approach. Its focus is on the agent's epistemic state, not code topology.",
          },
          serena: {
            text: 'No Ranking',
            status: 'none',
            detail: "Serena returns LSP results without ranking or weighting. All symbols are treated equally \u2014 the response to 'find references' includes every reference with no prioritization by importance.",
          },
          grepai: {
            text: 'Embedding Similarity Only',
            status: 'none',
            detail: "Grepai ranks results by embedding similarity score only. There's no structural weighting, no graph-based prioritization, and no way to influence ranking beyond the query text.",
          },
          bloop: {
            text: 'Vector Similarity Only',
            status: 'none',
            detail: "bloop ranks results by vector similarity. The search is effective but there's no graph-based weighting or user-configurable prioritization of modules or file groups.",
          },
        },
      },
      {
        id: 'privacy',
        name: 'Privacy & Local-First',
        description: 'Where your code data lives',
        codrag: {
          text: '100% Local: Rust + ONNX, Zero Cloud',
          status: 'full',
          detail: "Everything in CoDRAG runs 100% locally. The Rust parser, ONNX embeddings (nomic-embed-text-v1.5), SQLite storage, and the dashboard all work fully offline. No code ever leaves your machine unless you explicitly configure team sync to your own S3 bucket. The ONNX runtime embeds at ~7ms per query with zero cloud dependencies, zero API keys, and zero data transmission.",
        },
        competitors: {
          gitnexus: {
            text: 'Local (Node.js + WASM option)',
            status: 'partial',
            detail: "GitNexus runs locally via Node.js CLI and offers an innovative browser-based WASM option that requires zero installation. Both modes are fully offline. Their WASM approach means you can even run it in a sandboxed browser tab. CoDRAG's native Rust engine is faster for large codebases, but GitNexus's zero-install browser option is a genuinely clever distribution strategy.",
          },
          vexp: {
            text: 'Local (VS Code Extension)',
            status: 'full',
            detail: "Vexp is fully local-first, running entirely within VS Code. No cloud calls. SQLite storage stays on disk. Strong privacy story \u2014 comparable to CoDRAG's approach. The main difference is CoDRAG works across any IDE via MCP and can run headlessly.",
          },
          empirica: {
            text: 'Git-Native (LLM calls needed)',
            status: 'partial',
            detail: "Empirica stores everything in git notes \u2014 maximally local and version-controlled, which is excellent. However, the pre/postflight epistemic assessments require LLM calls, which means code context may be sent to cloud providers depending on configuration. The storage layer is private but the reasoning layer may not be.",
          },
          serena: {
            text: 'Local Server (LLM calls needed)',
            status: 'partial',
            detail: "Serena runs locally as an MCP server, querying the local LSP. The tool itself is private. However, it's designed to be used with cloud-hosted LLMs, so code context inevitably flows to the model provider when the agent uses Serena's results.",
          },
          grepai: {
            text: 'Privacy-First Local',
            status: 'full',
            detail: "Grepai is explicitly privacy-first with local embeddings. Strong privacy story, comparable to CoDRAG's approach. Both tools keep everything on-device with zero cloud dependencies for the core functionality.",
          },
          bloop: {
            text: 'Local (Qdrant Instance)',
            status: 'full',
            detail: "bloop runs locally with its own Qdrant vector database instance. Fully offline capable with a good privacy story. Comparable to CoDRAG's local-first approach.",
          },
        },
      },
    ],
  },
];

// ── Tooltip Component ──────────────────────────────────────
interface TooltipState {
  content: string;
  featureName: string;
  toolName: string;
  x: number;
  y: number;
}

function ComparisonTooltip({ tooltip }: { tooltip: TooltipState }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: tooltip.x, y: tooltip.y });

  useEffect(() => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      let nx = tooltip.x;
      let ny = tooltip.y;
      // Prevent overflow right
      if (nx + rect.width > vw - 16) nx = vw - rect.width - 16;
      // Prevent overflow left
      if (nx < 16) nx = 16;
      // Prevent overflow bottom — flip above if needed
      if (ny + rect.height > vh - 16) ny = tooltip.y - rect.height - 8;
      // Prevent overflow top
      if (ny < 16) ny = 16;
      setPos({ x: nx, y: ny });
    }
  }, [tooltip.x, tooltip.y]);

  return (
    <div
      ref={ref}
      className="fixed z-[9999] max-w-sm w-[360px] bg-surface border border-border rounded-xl shadow-2xl p-5 text-left animate-fade-in pointer-events-none"
      style={{ left: pos.x, top: pos.y }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Info className="w-4 h-4 text-primary flex-shrink-0" />
        <div className="text-xs font-bold text-primary uppercase tracking-wider">{tooltip.toolName}</div>
        <div className="text-[10px] text-text-muted ml-auto">{tooltip.featureName}</div>
      </div>
      <p className="text-sm text-text leading-relaxed">{tooltip.content}</p>
    </div>
  );
}

// ── Status Icon ────────────────────────────────────────────
const StatusIcon = ({ status, className = '' }: { status: Status; className?: string }) => {
  if (status === 'full') return <Check className={`w-4 h-4 text-primary ${className}`} strokeWidth={3} />;
  if (status === 'partial') return <Minus className={`w-4 h-4 text-text-muted ${className}`} strokeWidth={2} />;
  return <X className={`w-4 h-4 text-border-subtle ${className}`} strokeWidth={2} />;
};

// ── Main Component ─────────────────────────────────────────
export function CompetitorMatrix({ className = '' }: CompetitorMatrixProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const tooltipTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const checkScroll = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScrollRight(Math.ceil(scrollLeft + clientWidth) < scrollWidth);
    }
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, []);

  // Add wheel event listener for horizontal scrolling
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      // Only intercept if we are scrolling vertically without holding Shift
      if (e.deltaY !== 0 && Math.abs(e.deltaX) < Math.abs(e.deltaY)) {
        const canScrollLeft = el.scrollLeft > 0;
        const canScrollRight = Math.ceil(el.scrollLeft + el.clientWidth) < el.scrollWidth;

        // If we can scroll in the requested direction, intercept it
        if ((e.deltaY > 0 && canScrollRight) || (e.deltaY < 0 && canScrollLeft)) {
          e.preventDefault();
          el.scrollLeft += e.deltaY;
        }
      }
    };

    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, []);

  const scrollRight = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: 300, behavior: 'smooth' });
    }
  };

  const showTooltip = useCallback((e: React.MouseEvent, content: string, featureName: string, toolName: string) => {
    if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    tooltipTimer.current = setTimeout(() => {
      setTooltip({
        content,
        featureName,
        toolName,
        x: rect.right + 8,
        y: rect.top,
      });
    }, 300);
  }, []);

  const hideTooltip = useCallback(() => {
    if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
    tooltipTimer.current = setTimeout(() => setTooltip(null), 200);
  }, []);

  return (
    <div className={`w-full ${className}`}>

      {/* Tooltip Portal */}
      {tooltip && (
        <ComparisonTooltip
          tooltip={tooltip}
        />
      )}

      {/* Desktop Matrix */}
      <div className="hidden lg:block relative w-full mb-8">
        {canScrollRight && (
          <div className="absolute -top-12 right-0 flex items-center justify-end z-40">
            <button
              onClick={scrollRight}
              className="inline-flex items-center gap-2 bg-primary text-background px-4 py-2 rounded-full text-sm font-bold shadow-lg hover:scale-105 transition-transform animate-bounce"
            >
              Scroll to see more <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="relative w-full rounded-xl border border-border bg-background shadow-xl overflow-hidden">
          {canScrollRight && (
            <div className="absolute top-0 right-0 bottom-0 w-32 bg-gradient-to-l from-background to-transparent z-40 pointer-events-none" />
          )}

          <div ref={scrollRef} onScroll={checkScroll} className="overflow-x-auto w-full custom-scrollbar pb-2">
            <table className="w-max text-sm border-separate border-spacing-0 text-left">
              <thead>
                <tr>
                  <th className="sticky top-0 left-0 z-50 w-[260px] min-w-[260px] bg-background border-b border-r border-border p-5 align-bottom">
                    <div className="text-xs font-bold uppercase tracking-widest text-text-subtle">Feature Comparison</div>
                    <div className="text-[10px] text-text-muted mt-1">Hover any cell for details</div>
                  </th>
                  <th className="sticky top-0 left-[260px] z-50 w-[180px] min-w-[180px] bg-[#0c1222] border-b border-r border-primary/30 p-5 text-center align-bottom shadow-[8px_0_15px_-4px_rgba(0,0,0,0.3)]">
                    <div className="inline-flex items-center justify-center px-4 py-1.5 rounded-lg bg-primary border border-primary-hover text-background font-bold text-lg mb-2 shadow-lg shadow-primary/20">CoDRAG</div>
                    <div className="text-[10px] font-bold text-primary uppercase tracking-wider">Continuous Graph RAG</div>
                  </th>
                  {competitors.map((comp) => (
                    <th key={comp.id} className="sticky top-0 z-40 w-[160px] min-w-[160px] bg-background border-b border-r border-border-subtle p-5 text-center align-bottom">
                      <div className="font-bold text-text mb-1">{comp.name}</div>
                      <div className="text-[10px] text-text-muted uppercase tracking-wider">{comp.category}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixData.map((category, catIdx) => (
                  <React.Fragment key={catIdx}>
                    <tr>
                      <td className="sticky left-0 z-30 bg-surface border-b border-r border-border px-5 py-3 font-bold text-text text-xs uppercase tracking-wider">{category.category}</td>
                      <td className="sticky left-[260px] z-30 bg-[#0c1222] border-b border-r border-primary/30 shadow-[8px_0_15px_-4px_rgba(0,0,0,0.3)]" />
                      {competitors.map((comp) => (
                        <td key={comp.id} className="bg-surface border-b border-r border-border-subtle" />
                      ))}
                    </tr>
                    {category.features.map((feature) => (
                      <tr key={feature.id} className="group">
                        <td className="sticky left-0 z-20 bg-background group-hover:bg-surface border-b border-r border-border p-5 align-top transition-colors duration-150">
                          <div className="font-semibold text-text mb-1.5">{feature.name}</div>
                          <div className="text-xs text-text-muted leading-relaxed">{feature.description}</div>
                        </td>
                        <td
                          className="sticky left-[260px] z-20 bg-[#0c1222] group-hover:bg-[#11192e] border-b border-r border-primary/30 text-center shadow-[8px_0_15px_-4px_rgba(0,0,0,0.3)] p-5 align-top transition-colors duration-150 cursor-help"
                          onMouseEnter={(e) => showTooltip(e, feature.codrag.detail, feature.name, 'CoDRAG')}
                          onMouseLeave={hideTooltip}
                        >
                          <div className="flex flex-col items-center justify-start gap-2">
                            <StatusIcon status={feature.codrag.status} />
                            <span className="text-xs font-bold text-text leading-tight">{feature.codrag.text}</span>
                          </div>
                        </td>
                        {competitors.map((comp) => {
                          const cd = feature.competitors[comp.id];
                          return (
                            <td
                              key={comp.id}
                              className="bg-background group-hover:bg-surface border-b border-r border-border-subtle p-5 text-center align-top transition-colors duration-150 cursor-help"
                              onMouseEnter={(e) => showTooltip(e, cd.detail, feature.name, comp.name)}
                              onMouseLeave={hideTooltip}
                            >
                              <div className="flex flex-col items-center justify-start gap-2">
                                <StatusIcon status={cd.status} />
                                <span className="text-[11px] text-text-muted leading-tight">{cd.text}</span>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Mobile Stacked View */}
      <div className="lg:hidden space-y-8">
        {matrixData.map((category, catIdx) => (
          <div key={catIdx} className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest text-primary border-b border-border pb-2 pl-1">{category.category}</h3>
            <div className="grid grid-cols-1 gap-4">
              {category.features.map((feature) => (
                <div key={feature.id} className="bg-surface border border-border rounded-xl overflow-hidden shadow-sm flex flex-col">
                  <div className="p-4 bg-background border-b border-border">
                    <div className="font-bold text-text mb-1">{feature.name}</div>
                    <div className="text-xs text-text-muted">{feature.description}</div>
                  </div>
                  <div className="p-4 bg-[#0c1222] border-b border-primary/30 shadow-inner">
                    <div className="flex items-start gap-3 mb-3">
                      <div className="mt-0.5"><StatusIcon status={feature.codrag.status} className="w-5 h-5" /></div>
                      <div>
                        <div className="text-xs font-bold text-primary uppercase tracking-wider mb-1">CoDRAG</div>
                        <div className="text-sm font-semibold text-text">{feature.codrag.text}</div>
                      </div>
                    </div>
                    <p className="text-xs text-text-muted leading-relaxed pl-8">{feature.codrag.detail}</p>
                  </div>
                  <div className="p-0 flex-1">
                    <div className="divide-y divide-border-subtle">
                      {competitors.map((comp) => {
                        const cd = feature.competitors[comp.id];
                        return (
                          <details key={comp.id} className="group/detail">
                            <summary className="flex items-center justify-between gap-3 p-3 text-sm bg-background cursor-pointer hover:bg-surface transition-colors list-none">
                              <span className="font-medium text-text-muted text-xs">{comp.name}</span>
                              <div className="flex items-center gap-2 text-right">
                                <span className="text-[11px] text-text-subtle max-w-[140px] truncate">{cd.text}</span>
                                <StatusIcon status={cd.status} className="flex-shrink-0" />
                              </div>
                            </summary>
                            <div className="px-4 pb-3 pt-1 bg-surface text-xs text-text-muted leading-relaxed">{cd.detail}</div>
                          </details>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Tandem Integrations */}
      <div className="mt-20">
        <div className="text-center mb-10">
          <h3 className="text-2xl font-medium tracking-tight text-text sm:text-3xl mb-3">Companion, not a framework</h3>
          <p className="text-text-muted max-w-2xl mx-auto">
            CoDRAG isn't trying to replace your favorite tools. It's an MCP-native context engine designed to supercharge the AI IDEs and agents you already use.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {tandemTools.map((tool) => (
            <div key={tool.id} className="bg-surface border border-border rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow group">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                  <Check className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-text">{tool.name}</h4>
                  <span className="text-xs font-medium text-text-subtle uppercase tracking-wider">{tool.category}</span>
                </div>
              </div>
              <p className="text-sm text-text-muted leading-relaxed">{tool.desc}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}

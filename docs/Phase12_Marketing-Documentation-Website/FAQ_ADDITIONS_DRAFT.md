# FAQ Additions Draft (Based on Competitive Research & Community Feedback)

This document drafts new FAQ entries based on recurring questions, skepticism, and technical inquiries observed in developer communities (like r/ClaudeAI and r/LocalLLaMA) regarding local context engines.

**Ordering rationale:** Lead with our most unique, hardest-to-replicate capabilities. Intersperse competitor-comparison entries with pure product questions. End with practical/operational items.

**Naming discipline:** Avoid competitor-branded terms. "Session Memory" → we use "Persistent Agent Memory" / "Cross-Session Observations." "Capsule Context" → we use "LOD Compression" / "Structural Compression."

---

### 1. Does the AI remember what it learned about my code in previous sessions?
**Draft Answer:**
Yes — and this is where CoDRAG diverges from every other context tool on the market. CoDRAG maintains a **Persistent Agent Memory**: a local store of observations — architectural decisions, discovered bugs, design patterns, working assumptions — each linked directly to specific files and symbols in your codebase.

What makes this different from bolting a memory file onto your repo: CoDRAG's observations are **staleness-aware**. When you modify `auth.py`, every observation tied to that file is automatically flagged `[STALE]`. In the next session, the AI receives both the updated code *and* a signal that its prior assumptions may no longer hold. It doesn't blindly repeat outdated notes — it knows to re-evaluate.

This is not a prompt cache or a conversation log. It's a structured, file-linked, searchable knowledge layer that the AI maintains about your specific codebase. It works on **every tier, including Free** — it's local SQLite, zero cloud cost, zero telemetry. And because observations are injected alongside code context (not dumped in bulk), they respect the same tight token budget as everything else.

### 2. My code changes constantly. Does the AI just get stale context?
**Draft Answer:**
This is the central challenge of any indexing tool, and CoDRAG takes it more seriously than most. Three mechanisms work together:

1. **Incremental re-indexing.** CoDRAG tracks file hashes at the individual symbol level. When you edit a file, only the affected chunks are re-embedded — not the entire project. A real-time file watcher detects changes within seconds.

2. **Automatic observation staleness.** CoDRAG's Persistent Agent Memory (see above) links observations to files. When a file changes, those observations are flagged `[STALE]` — the AI sees them with a clear warning, not as gospel.

3. **A visible health indicator.** The Dashboard shows exactly which files have changed since the last index, how many are stale, and whether a rebuild is in progress. You never have to guess whether the AI's context is current.

Most other tools stop at #1. CoDRAG is the only local context engine that extends freshness tracking all the way into the AI's own learned knowledge.

### 3. Doesn't my AI tool (Cursor, Windsurf, Claude Code) already do this?
**Draft Answer:**
They all solve the foundational problem: find some relevant code and inject it. CoDRAG uses the same base technique (embed, rank, retrieve) — we're not pretending we invented vector search.

What CoDRAG adds is a **structural reasoning layer** that none of them have:
- **A dependency graph** (imports, function calls, class inheritance) built by a Rust parser. When the AI asks "what calls this function?", it gets a deterministic answer — not a probabilistic guess.
- **Multi-level compression** — full source for the most relevant results, signatures for structurally adjacent code, names only for distant context. This means more files fit in fewer tokens.
- **Intent detection** — CoDRAG recognizes whether you're debugging, understanding architecture, or writing implementation, and adjusts which types of files get priority. Automatic, per-query.
- **Full transparency** — relevance scores, token counts, which chunks were sent and why. No other AI coding tool exposes this.
- **Tool portability** — your index, weights, and the AI's learned observations move with you if you switch editors tomorrow. CoDRAG works via the open MCP standard, not a proprietary IDE hook.

### 4. Why not just put everything in a `CLAUDE.md` or rules file?
**Draft Answer:**
Use both. Seriously — they solve different problems and work well together.

A `CLAUDE.md` is ideal for conventions a human can articulate: "We use Tailwind," "Never mutate state directly," "Deploy via Terraform." That's high-level project DNA. CoDRAG cannot generate those rules for you.

What a rules file *cannot* do is track the 3,000+ dependency edges in a real codebase. It can't tell the AI that `PaymentService.charge()` calls `StripeClient.create_intent()` which imports `crypto.sign()`. It can't automatically update when someone refactors the call chain. It can't compress 200 files into 2,000 tokens of structurally meaningful context.

CoDRAG automates the granular, structural layer — the connective tissue of your codebase. Your rules file handles the human intent. Together, the AI gets both "what the code does" and "what the team wants."

### 5. Is this just another RAG tool?
**Draft Answer:**
CoDRAG's foundation is retrieval-augmented generation. So is Cursor's. So is Windsurf's. The question isn't "does it use RAG?" — it's "what does it do with the results?"

CoDRAG layers three things on top of basic retrieval that you won't find in a standard RAG pipeline:

- **Graph-navigated context.** A Rust-powered parser builds a trace graph of your code's actual structure — every import, call, and class relationship. When retrieval finds a relevant function, the graph finds everything structurally connected to it and includes them under a separate budget. This is deterministic navigation, not fuzzy similarity.

- **Adaptive compression.** Code results get structural compression (full source → signatures → names, depending on relevance). Documentation gets language-aware compression that preserves concepts while stripping filler. Two distinct compression engines, chosen automatically per chunk.

- **Persistent cross-session knowledge.** The AI accumulates linked observations about your codebase over time, with automatic staleness detection when files change. This means the AI's understanding of your project gets deeper across sessions, not just per-conversation.

### 6. Is my code uploaded to the cloud?
**Draft Answer:**
No. CoDRAG is local-first software — indexing, embedding, graph construction, search, and compression all happen on your machine. Your code never leaves your filesystem.

The only exceptions are things you explicitly opt into: if you configure a cloud LLM provider (OpenAI, Anthropic, Google) for the optional enrichment pipeline, only retrieved context snippets are sent to that provider — never your raw codebase. CoDRAG also makes a single HTTPS call during license activation. Both are optional and auditable.

What makes this different from tools that *claim* local-first: CoDRAG ships its own embedding model (ONNX, runs on CPU) and its own Rust parser. You don't need Ollama, you don't need Docker, you don't need an internet connection for core functionality. The entire stack runs offline, cold.

### 7. Is this just a wrapper around the Language Server Protocol?
**Draft Answer:**
No — and the distinction matters. LSP-backed tools require a running language server with the correct runtime environment configured for every project. Switch from Python to TypeScript? You need a different server. Working on a legacy project without a proper `tsconfig.json`? LSP can't help.

CoDRAG builds its own persistent trace graph using tree-sitter, a zero-dependency parser that handles 15+ languages from a single binary. The graph persists to disk, loads instantly, and works offline. No runtime, no IDE backend, no configuration per language.

The deeper difference: LSP gives you *live* analysis (great for autocomplete), but it can't answer cross-session questions, doesn't persist observations, and can't compress structural context into a token budget. CoDRAG is a read-only context engine designed for a fundamentally different job — giving AI agents the right context at query time.

### 8. Which editors does it work with?
**Draft Answer:**
CoDRAG is a standalone daemon and an MCP (Model Context Protocol) server. It is not locked to any IDE. Today it works with **Cursor**, **Windsurf**, **Claude Desktop**, and **Claude Code** (terminal). A VS Code extension is in development.

Because CoDRAG uses the open MCP standard, any future editor or agent that supports MCP will work automatically — no integration work on our end. Your index, weights, observations, and full project configuration are stored locally and editor-independent. Switch tools without losing anything.

### 9. I already use semantic search tools. How is CoDRAG different?
**Draft Answer:**
Pure semantic search (vector embeddings) excels at fuzzy discovery — finding code when you describe it in natural language. CoDRAG includes a full semantic search engine (ONNX embeddings, runs locally on CPU, no external service needed).

But semantic search alone struggles with **structural precision**. It can find code that *sounds* related to "authentication," but it can't traverse the actual import chain to tell you what `AuthService.validate()` calls, or what breaks if you change its signature.

CoDRAG adds a **deterministic dependency graph** on top of embeddings. When the AI asks about blast radius, it gets exact callers and importers from the parsed AST — not a list of files that happen to mention similar words. And because the graph and the vector index share a token budget, you get both conceptual relevance and structural precision without blowing up your context window.

### 10. Do I need a GPU?
**Draft Answer:**
No. Core features — indexing, trace graph construction, search, and structural compression — run on CPU. The built-in embedding model is a quantized ONNX model optimized for CPU inference (~274 MB, auto-downloaded on first use).

If you want to run the optional enrichment pipeline (which generates deeper module summaries and inferred edges), you can point CoDRAG at any LLM: a cloud API (OpenAI, Anthropic, Google) or a local model via Ollama. A GPU helps for local models, but is never required.

### 11. Why pay for this? Can't I build it myself?
**Draft Answer:**
You could build a basic RAG pipeline over a weekend. What takes years is everything beyond that: incremental rebuilds that don't re-embed your entire project on every save. A Rust parser that handles 15+ languages and produces a navigable dependency graph. Compression that treats code and documentation differently. An observation store that links AI knowledge to specific files and flags it stale when those files change. A real-time file watcher that triggers rebuilds without polling. A dashboard that shows you exactly what the AI sees.

CoDRAG offers a **Free tier** for evaluation. Pro is a **one-time $79 perpetual license** — not a subscription. You pay once, own the software, and it works offline forever. We fund development through that, not by monetizing your data or adding telemetry.

### 12. Does it work on documentation, not just code?
**Draft Answer:**
Yes — and it handles docs differently than code, which matters. CoDRAG runs two distinct compression strategies: **structural compression** for code files (preserving full source for top results, signatures for medium-relevance, names for peripheral) and **language-aware compression** for Markdown and text (preserving concepts while stripping filler words and redundant phrasing).

This means you can include architecture docs, API references, and design decisions in your project scope, and CoDRAG will compress them intelligently alongside your code. The AI gets both implementation details and the human reasoning behind them.

### 13. Why SQLite instead of a graph database?
**Draft Answer:**
CoDRAG uses SQLite for its registry, pipeline journal, observation store, and full-text keyword index (FTS5). This keeps the tool zero-config, single-file portable, and requires no background infrastructure. The actual dependency graph and vector index are loaded into memory at query time — you get in-memory speed with disk persistence.

For team and enterprise deployments, the architecture is designed with extensibility for optional backends. But for the core product — a local companion app running on a developer's laptop — SQLite is the right choice: battle-tested, zero-admin, and fast enough that you'll never notice it.

### 14. How does it handle circular dependencies and dynamic references?
**Draft Answer:**
Real codebases are messy. CoDRAG's tree-sitter parsers handle circular imports without infinite loops — the graph builder tracks visited nodes and terminates cleanly. For dynamic references (e.g., `getattr()` in Python, bracket notation in JavaScript), CoDRAG's enrichment pipeline uses an LLM to analyze code patterns and infer edges that static parsing can't capture. These inferred edges are stored alongside parsed edges in the trace graph, with a distinct edge type so you can distinguish them.

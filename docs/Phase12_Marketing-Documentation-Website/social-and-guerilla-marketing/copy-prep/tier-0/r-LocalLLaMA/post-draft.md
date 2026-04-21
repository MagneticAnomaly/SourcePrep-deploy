# Post Draft for r/LocalLLaMA

## Title Options
1. **I built a local-first code context engine that runs without an LLM (Rust + graph analysis)**
2. **Projects: Prep - A structural context engine for local AI coding (No Ollama required)**
3. **Sharing my project: A local context graph for codebases that plugs into Cursor/MCP (0% cloud)**

## Body Structure

### Hook
I’ve spent the last few months building **Prep**, a local-first "context engine" for large codebases. The weird part? **It doesn't use an LLM for its core index.**

Instead of just embedding chunks into a vector DB (which I found gets messy with large repos), it builds a structural "trace graph" of your code—definitions, references, imports—using Tree-sitter and a custom Rust graph engine.

### Why I built this
I love local LLMs, but I got tired of:
1.  **Context window limits:** Even with 128k context, dumping 50 files confuses the model.
2.  **Stale embeddings:** Most local RAG tools don't update instantly when I change a file.
3.  **Privacy:** I didn't want my proprietary repo index living on someone else's cloud.

### How it works (The Technical Bit)
It runs as a local desktop daemon (Tauri + Python/Rust sidecar).
1.  **Watcher:** Detects file changes in real-time.
2.  **Indexer:** Incremental Tree-sitter parsing builds a dependency graph.
3.  **Retrieval:** When you ask a question, it uses "Trace-Assisted Grasping" (TRAG) to walk the graph. If you ask about `AuthService`, it pulls the interface *and* the relevant implementation details from connected files, without needing a semantic search step (though it supports hybrid search too).
4.  **MCP:** It exposes this context via the Model Context Protocol (MCP) so you can use it directly in Cursor, Windsurf, or Claude Desktop.

**No GPU required for the core loop.** It’s just graph traversal.

### Links & Code
*   **Repo/Docs:** [Link to GitHub/Docs]
*   **Deep dive on the graph architecture:** [Link to Blog Post]
*   **Download (Mac/Windows):** [Link]

### Discussion
I'm curious what you all think about "structural" vs "semantic" retrieval for code. I've found that for precise refactoring, the graph beats embeddings 9 times out of 10. But for vague questions ("how does auth work?"), embeddings still win.

Has anyone else tried combining Tree-sitter graphs with local RAG?

## Tone
Technical, engineering-focused, "builder to builder." Avoid marketing fluff. Be honest about limitations (e.g., "embeddings still win for vague questions").

## Timing
Post on a Tuesday or Wednesday morning (US time). Ensure I'm around to answer comments about the Rust implementation and graph algorithms.

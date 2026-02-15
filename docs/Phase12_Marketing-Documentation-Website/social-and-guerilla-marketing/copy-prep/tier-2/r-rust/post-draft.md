# Post Draft for r/rust

## Title Options
1. **Building a local code graph engine in Rust (using Tree-sitter + PyO3)**
2. **Replacing vector search with graph traversal for code RAG (Rust implementation)**
3. **CoDRAG: A Rust-based MCP server for structural code context**

## Body Structure

### Hook
I've been working on **CoDRAG**, a desktop tool to index large codebases locally for AI context. I initially prototyped the graph analysis in Python, but it choked on monorepos.

### The Rust Rewrite
I rewrote the core indexer in Rust. It uses:
*   `tree-sitter` for incremental parsing.
*   `petgraph` (or custom structure) for the dependency graph.
*   `PyO3` to expose the high-performance core to the local Python daemon.

### Technical Challenges
*   **Incremental Updates:** Handling file watcher events and updating only the affected subgraph without rebuilding the world.
*   **Concurrency:** Parsing files in parallel while maintaining graph consistency.
*   **Memory Safety:** Why Rust was critical for long-running daemon stability.

### The Result
It now runs locally with minimal RAM footprint, serving context to tools like Cursor via MCP.

### Links
*   **Crate/Repo:** [Link]
*   **Architecture Blog:** [Link]

## Tone
Pure engineering. Discuss crates, ownership, FFI challenges.

## Timing
Weekday.

# Post Draft for r/rust

## Title Options
1. **Building a local code graph engine in Rust (using Tree-sitter + PyO3)**
2. **Replacing vector search with graph traversal for code RAG (Rust implementation)**
3. **Prep: A Rust-based MCP server for structural code context**

## Body Structure

### Hook
I've been working on **Prep**, a desktop tool to index large codebases locally for AI context. I initially prototyped the graph analysis in Python, but it choked on monorepos.

### The Rust Rewrite
I rewrote the core indexer in Rust. It uses:
*   `tree-sitter` for incremental parsing (multi-language: Python, TS, Rust, Go, Java, C++).
*   A custom in-memory graph structure (`prep-graph`) — no third-party graph lib, hand-rolled for performance.
*   `PyO3` bindings so Python can call the Rust graph directly (`import prep_engine`) — fast FFI, no subprocess overhead.

### Technical Challenges
*   **Incremental Updates:** Handling file watcher events and updating only the affected subgraph without rebuilding the world.
*   **Concurrency:** Parsing files in parallel while maintaining graph consistency.
*   **Memory Safety:** Why Rust was critical for long-running daemon stability.

### The Result
It now indexes large repos in seconds and serves context to tools like Cursor via MCP, all from a single native binary.

### Links
*   **Crate/Repo:** [Link]
*   **Architecture Blog:** [Link]

## Tone
Pure engineering. Discuss crates, ownership, FFI challenges.

## Timing
Weekday.

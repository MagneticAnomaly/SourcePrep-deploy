# Organic/Personal Post Draft for r/rust

## Title Options
1. **Rewriting my Python graph engine in Rust (100x speedup on indexing)**
2. **My journey building a local-first MCP server with Petgraph and Tree-sitter**

## Body Structure

### The Prototype
I started building **CoDRAG** in Python. It worked for small scripts.
But when I pointed it at a 50k LOC repo, the graph analysis (finding all downstream dependents) took 30 seconds. Unacceptable for a "real-time" tool.

### The Rewrite
I ported the core indexer to Rust.
*   **Tree-sitter** for parsing (incremental updates are tricky!).
*   **Petgraph** for the dependency storage.
*   **PyO3** to bind it back to my Python API (best of both worlds).

### The Result
Indexing is now near-instant. The memory footprint dropped by 80%.
And I learned a ton about `RefCell` hell along the way.

**Repo:** [Link] (Critique my code please!)

## Tone
Humble bragging about the rewrite. Asking for code review.

# Organic/Personal Post Draft for r/rust

## Title Options
1. **Rewriting my Python graph engine in Rust (100x speedup on indexing)**
2. **My journey building a local-first MCP server with a custom graph engine and Tree-sitter**

## Body Structure

### The Prototype
I started building **Prep** in Python. It worked for small scripts.
But when I pointed it at a 50k LOC repo, the graph analysis (finding all downstream dependents) took 30 seconds. Unacceptable for a "real-time" tool.

### The Rewrite
I ported the core indexer to Rust.
*   `tree-sitter` for incremental parsing.
*   A hand-rolled in-memory graph (`prep-graph` crate) — we evaluated petgraph but rolled our own to keep query semantics simple.
*   `PyO3` bindings (`prep-engine` crate, compiled as a `cdylib`) so Python imports the Rust core directly.

### The Result
Indexing is now near-instant on repos that choked the Python prototype. The memory footprint dropped ~80%.
And I learned a lot about `RefCell` hell along the way.

**Repo:** [Link] (Critique my code please!)

## Tone
Humble bragging about the rewrite. Asking for code review.

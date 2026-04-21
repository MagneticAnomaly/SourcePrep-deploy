# Organic/Personal Post Draft for Lobsters

## Title Options
1. **Prep: Local-first code indexing using Tree-sitter and a custom dependency graph**
2. **Experience Report: Replacing Vector Search with Graph Traversal for Code RAG**

## Body (Comment)
Author here.
We built this because standard embedding-based retrieval falls apart on large monorepos where precise dependency tracking matters (e.g., finding the implementation of an interface defined in a different crate).

It uses Tree-sitter for AST parsing and a custom in-memory Rust graph engine for dependency storage and traversal. Results are served to editors via MCP.

Happy to discuss the graph design choices — we evaluated petgraph and rolled our own instead, which has tradeoffs worth talking about.

## Tone
High-signal engineering discussion.

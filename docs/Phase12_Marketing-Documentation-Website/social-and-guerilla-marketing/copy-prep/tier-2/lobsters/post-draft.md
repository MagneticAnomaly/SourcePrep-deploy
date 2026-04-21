# Post Draft for Lobsters

## Title Options (Link Post)
1. **Prep: A local-first, structural code indexer in Rust**
2. **Replacing vector search with graph traversal for code retrieval**
3. **Trace-Assisted Grasping: Using Tree-sitter for deterministic RAG**

## Body (Comment)
*Lobsters is a link aggregator. The content is the Blog Post. The "Post Draft" here is the first comment to add context.*

**Comment Draft:**
Author here. We built this because we found that standard embedding-based retrieval falls apart on large monorepos where precise dependency tracking is needed (e.g., finding the implementation of an interface defined in a different crate).

It uses Tree-sitter to build a local graph and exposes it via the Model Context Protocol (MCP) to editors like Cursor/Windsurf.

Happy to answer questions about the graph traversal implementation in Rust.

## Tone
Humble, technical, direct. No marketing fluff.

## Timing
When the "Architecture Overview" blog post is published.

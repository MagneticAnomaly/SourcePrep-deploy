# Organic/Personal Post Draft for Lobsters

## Title Options
1. **CoDRAG: Local-first code indexing using Tree-sitter and Petgraph**
2. **Experience Report: Replacing Vector Search with Graph Traversal for Code RAG**

## Body (Comment)
Author here.
We built this to solve the "context window" precision problem in large monorepos.
We found that vector search (embeddings) is great for "fuzzy" concepts but terrible for strict engineering questions ("Who calls this?").

We chose Rust for the engine to handle the graph scale (100k+ nodes) on consumer hardware.
Happy to answer Qs about the architecture or the move away from pure Python.

## Tone
High-signal engineering discussion.

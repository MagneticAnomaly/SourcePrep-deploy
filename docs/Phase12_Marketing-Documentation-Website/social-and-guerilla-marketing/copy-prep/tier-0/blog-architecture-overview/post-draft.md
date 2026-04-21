# Blog Post Draft: Architecture Overview

## Title Options
1. **Why we built a structural code indexer in Rust (and why embeddings aren't enough)**
2. **Under the hood of Prep: Local-first, graph-based code retrieval**
3. **The case for "Trace-Assisted Grasping" in AI coding tools**

## Outline

### Introduction
*   The problem: "Vibe-based coding." LLMs are great at guessing, but bad at strict dependency chains.
*   The standard solution: RAG (Vector Search). Good for "how do I...?", bad for "where is `init_db` called and what argument does it take?".
*   Our thesis: You need **structure** + **semantics**, not just semantics.

### The Architecture
*   **The "Context Engine"**: It's not just a database; it's a live view of your code.
*   **Local-First Design**:
    *   **Tauri Frontend**: Fast, native feel.
    *   **Rust Core**: High-performance graph traversal and file watching.
    *   **Python Sidecar**: For optional ML tasks (re-ranking), keeping the heavy lifting isolated.

### Component 1: The Graph Indexer (Rust)
*   Using Tree-sitter to parse code into an AST.
*   Extracting "nodes" (functions, classes) and "edges" (calls, imports).
*   Why Rust? Memory safety, speed, and thread-safe concurrency for indexing large monorepos.

### Component 2: Trace-Assisted Grasping (TRAG)
*   How a query works:
    1.  **Anchor**: Find the starting point (e.g., filename or symbol name).
    2.  **Trace**: Walk the graph (1-hop, 2-hops) to find dependencies.
    3.  **Bound**: Prune the results to fit the context window (token budgeting).
*   *Include a diagram here comparing "Vector Chunk" vs "Graph Trace".*

### Component 3: The MCP Layer
*   Why we chose MCP (Model Context Protocol).
*   It decouples the *intelligence* (Cursor/Windsurf) from the *context* (Prep).
*   Allows us to build a specialized tool that works with any editor.

### Conclusion
*   We're betting on **Local + Structural**.
*   Download link / GitHub link.
*   Invitation to contribute.

## Tone
Authoritative, transparent, engineering-heavy. Show code snippets of the Rust structs or the Python Pydantic models. Be proud of the complexity but explain it simply.

## Links to Include
- GitHub Repo
- Documentation
- Comparison benchmarks (if available)

# Organic/Personal Post Draft for r/programming

## Title Options
1. **I built a structural code search engine because "semantic" search kept failing me**
2. **Why vector embeddings weren't enough for my monorepo (so I used graphs)**
3. **Building a local "LSP-like" indexer for RAG context**

## Body Structure

### The Motivation
I've been working on a large legacy codebase recently, and I tried using standard RAG tools to help navigate it. The problem? **Hallucinations.**

If I asked "Who calls `init_payment`?", the vector search would return 3 files that *mentioned* payment but missed the actual call site because it was dynamic or named slightly differently.

### The Engineering
I realized that for code, "vibe" (vectors) isn't enough. You need **truth** (structure).
So I spent my weekends building a local graph engine in Rust.

It uses Tree-sitter to parse the code into an AST, then builds a directed graph of definitions and references. It's basically a lightweight LSP server that runs in the background.

### The "Hybrid" Approach
Now, when I query my code, it does a "Trace-Assisted Grasping" (TAG):
1.  Find the symbol `init_payment`.
2.  Traverse the graph to finding the *exact* call sites.
3.  Feed *those* specific lines to the LLM.

### Trade-offs
It's harder to build than a 5-line LangChain script, but the precision is worth it. It struggles a bit with dynamic languages (Python is tricky), but for Rust/Go/TS it's rock solid.

### Links
*   **Repo:** [Link]
*   **Architecture writeup:** [Link]

## Tone
Engineer-to-engineer. Discussing the trade-offs of the approach.

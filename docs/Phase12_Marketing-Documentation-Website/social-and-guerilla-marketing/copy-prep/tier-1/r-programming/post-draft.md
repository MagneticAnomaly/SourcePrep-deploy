# Post Draft for r/programming

## Title Options
1. **Why vector search is often the wrong tool for code retrieval**
2. **From RAG to TAG: Moving beyond "vibe-based" code search with structural graphs**
3. **The limits of embeddings for large codebases: a case for structural indexing**

## Body Structure

### The Problem with "Naive RAG" on Code
We've all seen the demo: embedding a codebase into a vector database and asking "how does auth work?". It looks magical.

But in practice, when you're refactoring a complex system, "semantic similarity" often fails.
*   It retrieves comments that *talk* about the function, not the function itself.
*   It misses the interface definition defined 3 files away because the variable names didn't match the query keywords.
*   It hallucinates connections based on variable name overlap rather than actual import paths.

### A Structural Approach (Graph Analysis)
I've been working on a different approach that treats code as a **graph**, not just a bag of text chunks.
By using Tree-sitter to build a dependency graph (definitions, references, imports), we can perform "Trace-Assisted Grasping" (TAG?) instead of just RAG.

If I query `AuthService.login`, the system:
1.  Finds the symbol `AuthService`.
2.  Traverses the graph to find the `login` method implementation.
3.  Follows imports to find the `User` type definition.
4.  Bundles *only* those nodes into the context window.

### Trade-offs
*   **Pros:** deterministic, precise, no hallucinated dependencies.
*   **Cons:** requires language-specific parsers (Tree-sitter), can be slower to index than simple chunking.

### Discussion Question
For those building dev tools, have you found a sweet spot between semantic search (embeddings) and structural search (LSP/Graphs)? Or is the future just "dump it all in a 10M token context window" and hope?

## Tone
Academic, thoughtful, experienced. NOT "I built a tool, download it here." Focus on the *methodology* and the *engineering trade-offs*.

## Links to Include
*   **None in the body** (strictly discussion).
*   **First comment:** "If you're interested in playing with this approach, I'm building a local tool called CoDRAG that implements this graph-based retrieval: [Link to GitHub/Docs]"

## Timing
Weekday morning (EU/US overlap). Monitor closely for technical debate.

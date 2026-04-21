# Post Draft for r/MachineLearning

## Title Options
1. **[P] Prep: A local structural trace engine for code retrieval (Graph > Vectors?)**
2. **[P] Replacing vector search with structural graph traversal for code RAG**
3. **[P] Trace-Assisted Grasping: A deterministic approach to context retrieval for LLMs**

## Body Structure

### The Abstract (Hook)
Most RAG systems for code rely on chunking and cosine similarity. We found this introduces high noise for large repositories (retrieving semantically similar but structurally irrelevant code).

We built **Prep**, an open-source(ish) local engine that uses **Tree-sitter** to build a deterministic dependency graph of the codebase.

### The Methodology
Instead of `query -> embedding -> k-NN`, the pipeline is:
1.  **Anchor Extraction:** Identify symbols in the user query (e.g., "AuthService").
2.  **Graph Traversal:** Walk the AST-derived graph (Definition -> References -> Imports).
3.  **Context Bounding:** Use a token budget algorithm to select the most relevant connected subgraph.

### Why this matters for ML/Agents
This allows "Agentic" workflows to reliably navigate a codebase without hallucinating file existence. It provides a **grounded** context window.

We are experimenting with hybrid approaches (Graph + Small Language Model for re-ranking) and would love feedback from the community on recent research in "GraphRAG" applied to syntax trees.

### Links
*   **Project Page:** [Link]
*   **Architecture Writeup:** [Link]

## Tone
Academic, research-oriented, soliciting feedback on the *algorithm* and *approach*. Use standard ML terminology (RAG, embeddings, precision/recall).

## Timing
Weekday morning.

## Links to Include
- **Primary:** GitHub Repo.
- **Secondary:** Architecture Blog Post.

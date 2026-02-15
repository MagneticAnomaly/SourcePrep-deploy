# Organic/Personal Post Draft for r/MachineLearning

## Title Options
1. **[P] We replaced vector search with graph traversal for code RAG. Here's what we found.**
2. **[P] "Trace-Assisted Grasping": A deterministic alternative to embeddings for code**

## Body Structure

### The Experiment
We started with the hypothesis that for code retrieval, **precision > recall**.
Standard RAG (chunking + cosine similarity) has high recall but terrible precision for strict dependencies.

### The Implementation
We built a system that uses **Tree-sitter** to extract symbols and build a dependency graph.
When a query comes in, we identify "anchor" nodes (e.g., function names) and perform a bounded graph walk (1-2 hops).

### Results
*   **Hallucinations:** Drastically reduced for API usage questions.
*   **Context Window:** We can fit "more relevant" code into 8k tokens than vector search could into 32k.
*   **Latency:** Slower index time (parsing), but faster retrieval (graph lookup vs ANN).

### Open Source
We packaged this into a desktop app called **CoDRAG**.
We'd love feedback on the graph traversal algorithm (implemented in Rust).

**Repo:** [Link]

## Tone
Research-sharing. "We tried X, here are the results."

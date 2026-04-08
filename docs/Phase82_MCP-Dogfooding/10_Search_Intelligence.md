# 10 — Search Intelligence Deep Dive

Making `codrag_search` the best codebase search tool an agent can use.

---

## The Current State

`codrag_search` today does:
1. **Semantic search** (type="context"): Embed the query, find nearest chunks, expand via trace graph, assemble with LOD compression. Returns code content with metadata annotations.
2. **Symbol search** (type="symbol"): Exact/fuzzy match on trace node names. Returns file paths only.

Both modes operate on a single query, return results in a single pass, and have no memory of previous searches.

## What "Great Search" Looks Like

The best codebase search would feel like asking a senior developer who knows the whole codebase: "Where does error handling happen in the MCP layer?" They wouldn't grep — they'd think about what you mean, consider multiple locations, cross-reference their knowledge, and give you a curated answer with context about *why* each location matters.

CoDRAG has all the ingredients for this. The trace graph gives structural relationships. The concepts store gives rationale. The observations give historical context. The embeddings give semantic matching. But these are used in isolation today.

---

## Improvement Area 1: Intent Detection

### The Problem
All queries are treated the same. But "where is the auth middleware?" and "how does the auth middleware work?" and "why does the auth middleware use JWTs?" are three fundamentally different questions requiring different retrieval strategies.

### Proposed Intent Classification

| Intent | Signal words | Retrieval strategy |
|--------|-------------|-------------------|
| **Locate** | "where is", "find", "which file" | Symbol search + file path matching. Return locations, not explanations. |
| **Explain** | "how does", "what does", "explain" | Semantic search with trace expansion. Include related files and call chains. |
| **Rationale** | "why", "reason", "decision" | Concept search first, then observations, then code comments. |
| **Impact** | "what uses", "what calls", "who depends on" | Graph traversal (redirect to `codrag_impact` with a search-friendly interface). |
| **Example** | "show me how", "usage of", "example" | Reverse search: find call sites, not definitions. |
| **Diff** | "what changed", "recently", "new" | Git-aware search: filter by recency or branch diff. |
| **Compare** | "difference between", "vs", "compare" | Multi-entity retrieval: find both targets and highlight differences. |

### Implementation Approach
Add a lightweight classifier (could be rule-based for v1, LLM for v2) that runs before retrieval:

```python
def classify_intent(query: str) -> Intent:
    query_lower = query.lower()
    if any(w in query_lower for w in ["where", "find", "which file", "locate"]):
        return Intent.LOCATE
    if any(w in query_lower for w in ["how does", "what does", "explain", "walk me through"]):
        return Intent.EXPLAIN
    if any(w in query_lower for w in ["why", "reason", "decision", "rationale"]):
        return Intent.RATIONALE
    if any(w in query_lower for w in ["what uses", "what calls", "depends on", "imported by"]):
        return Intent.IMPACT
    if any(w in query_lower for w in ["example", "usage", "show me how", "in practice"]):
        return Intent.EXAMPLE
    return Intent.EXPLAIN  # default
```

Each intent routes to a different retrieval pipeline but returns through the same output format.

---

## Improvement Area 2: Multi-Source Retrieval

### The Problem
Semantic search only searches embeddings. But the richest answer often requires combining:
- **Embeddings** → semantically similar code
- **Trace graph** → structurally connected code
- **Concepts** → design rationale
- **Observations** → historical context
- **Symbol index** → exact name matches
- **Git history** → recent changes

Today, `working_dir` injection adds observations, and trace expansion adds structural context. But this is opportunistic, not systematic.

### Proposed Multi-Source Pipeline

```
Query → Intent Classification → Source Selection → Parallel Retrieval → Fusion → Ranking → Assembly

Source Selection (per intent):
  LOCATE:   [symbols(weight=0.6), embeddings(0.3), git(0.1)]
  EXPLAIN:  [embeddings(0.4), trace(0.3), concepts(0.2), observations(0.1)]
  RATIONALE: [concepts(0.5), observations(0.3), embeddings(0.2)]
  IMPACT:   [trace(0.7), embeddings(0.2), observations(0.1)]
  EXAMPLE:  [trace_reverse(0.5), embeddings(0.3), git(0.2)]
```

Each source returns scored candidates. The fusion step merges and re-ranks using reciprocal rank fusion or learned weights. The assembly step applies LOD compression within the token budget.

### Concrete Example

Query: "Why does the MCP server use httpx instead of requests?"

1. **Intent: RATIONALE**
2. Source selection: concepts (0.5), observations (0.3), embeddings (0.2)
3. Parallel retrieval:
   - Concepts: "A2A protocol adoption" mentions httpx for async support
   - Observations: (nothing specific)
   - Embeddings: server.py chunk importing httpx, with docstring about async
4. Fusion: Concept provides the "why", code provides the "what"
5. Assembly:
   ```
   ## Why httpx in MCP server
   
   The MCP server uses httpx (async HTTP client) instead of requests because 
   the server operates in an async event loop (concept: "A2A protocol adoption"). 
   The server.py handler at line 19 imports httpx for non-blocking daemon 
   communication. The requests library is synchronous and would block the 
   event loop.
   
   → See concept "A2A protocol adoption" for full rationale.
   ```

---

## Improvement Area 3: Search Feedback Loops

### The Problem
Every search starts from zero. If an agent searches for "auth middleware", gets results, then searches for "rate limiting" — the second search doesn't know the agent is exploring the API security surface area. Each query is independent.

### Proposed Session Context

Track searches within a session (in-memory, no persistence needed):

```python
class SearchSession:
    queries: List[str]           # previous queries
    result_files: Set[str]       # files returned in previous results
    working_area: Set[str]       # modules/directories the agent is exploring
    
    def contextualize(self, query: str) -> str:
        """Expand query with session context."""
        if self.working_area:
            # Boost results in the agent's working area
            return query  # + internal boosting signal
        return query
    
    def update(self, query: str, results: List[SearchResult]):
        self.queries.append(query)
        self.result_files.update(r.file_path for r in results)
        self.working_area = infer_working_area(self.result_files)
```

### Benefits
- Second query "rate limiting" would boost results near files that handle auth (since the agent is exploring that area)
- "More like this" becomes possible: agent liked result #2, search for more files structurally/semantically similar to it
- Avoid returning the same file twice unless it's highly relevant to the new query

---

## Improvement Area 4: Result Quality Signals

### The Problem
Results come with confidence scores (0.0-1.0) but no explanation of *why* a result was returned or *how* to evaluate it.

### Proposed Rich Metadata

```markdown
## Result 1: src/codrag/mcp/server.py (confidence: 0.86)
[match: semantic(0.72) + structural(0.14) | via: trace expansion from mcp_tools.py]
[freshness: modified 2 days ago | coverage: 67% test coverage]
[context: this file is a hub (23 dependents) — changes here have wide impact]

{code content}
```

Each result gets:
- **Match explanation**: Why this result? Which sources contributed?
- **Freshness**: When was this code last modified? Is it active or legacy?
- **Risk signal**: Is this a hub file? Is it well-tested? Has it caused issues before?
- **Structural position**: Where does this file sit in the module hierarchy?

### Not every result needs all signals
Apply progressive disclosure here too:
- High-confidence results (>0.8): Just show the code, match is obvious
- Medium-confidence (0.5-0.8): Show match explanation so agent can evaluate
- Low-confidence (<0.5): Show full metadata so agent understands why this was the best match

---

## Improvement Area 5: Search-Driven Navigation

### The Problem
Search returns results. Then the agent has to manually decide what to explore next. There's no "what should I look at next?" guidance.

### Proposed Navigation Suggestions

After search results, add a "Related Explorations" section:

```markdown
## Related Explorations
Based on your search and results, you might also want to explore:
- `codrag_search("MCP error handling")` — 3 results in the same module
- `codrag_impact("src/codrag/mcp/server.py")` — this hub file has 23 dependents
- `codrag_concepts(query="MCP design")` — 1 concept about MCP architecture
```

This turns search from a dead-end lookup into a navigation starting point. The agent can follow the thread or stop — but the options are visible.

---

## Improvement Area 6: Embedding Model Awareness

### The Problem
CoDRAG supports multiple embedding backends (ONNX native, Ollama). The quality of search results depends heavily on which model is used, but this is invisible to the agent.

### Proposed Transparency

```markdown
[search: nomic-embed-text v1.5 (768d) via ONNX | index: 847 chunks, 312 files]
```

For power users, also expose:
- Which files aren't indexed (too large, excluded by policy, binary)
- Embedding coverage: "312 of 323 Python files indexed (96%)"
- Model characteristics: "This model is general-purpose. For code-heavy queries, a code-specific model may produce better results."

### Long-Term: Model-Aware Query Routing
If multiple embedding models are available, route code queries to the code model and doc queries to the general model. Or embed with both and fuse results.

---

## Improvement Area 7: Failure Modes

### What happens when search fails?

**Current behavior:** Returns the best available result, even if it's terrible. No signal to the agent that the result is likely irrelevant.

**Proposed graduated failure responses:**

```
Score > 0.8: Normal result (high confidence)
Score 0.5-0.8: Result with warning: "Moderate match — verify relevance"
Score 0.3-0.5: Minimal result with suggestion: "Weak match. Try: 
  - Rephrase: 'MCP tool registration' instead of 'how tools get added'
  - Use symbol search: codrag_search(query='register_tool', type='symbol')
  - Use grep for exact string: 'tool registration'"
Score < 0.3: No result returned: "No relevant matches found. The index 
  may not cover this topic. Suggestions: [rephrase, grep, manual exploration]"
```

The key insight: returning a bad result with high apparent confidence is worse than returning nothing. An agent that acts on a bad result wastes time. An agent that knows the search failed can try alternatives immediately.

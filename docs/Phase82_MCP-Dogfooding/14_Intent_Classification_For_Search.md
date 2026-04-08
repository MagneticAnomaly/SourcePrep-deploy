# 14 — Intent Classification for Search: Making `codrag_search` Understand What You Actually Want

## The Core Problem

Every query to `codrag_search` gets the same treatment: embed the query, find nearest chunks, expand via trace graph, assemble. But consider these five queries:

1. "Where is handle_tools_list?" → **LOCATE** — I want a file path and line number
2. "How does the MCP tool dispatch work?" → **EXPLAIN** — I want a walkthrough with connected code
3. "Why does the server use httpx?" → **RATIONALE** — I want design reasoning, not code
4. "What calls tool_impact?" → **TRACE** — I want a call graph / usage sites
5. "Show me how useEventStream is used in components" → **EXAMPLE** — I want call sites, not the definition

Today, all five get semantic embedding search. Query 1 would be better served by symbol lookup. Query 3 would be better served by concept search. Query 4 would be better served by graph traversal. Query 5 would be better served by reverse-dependency search.

The embedding search isn't *wrong* for any of these — it'll return something related. But it's suboptimal for all of them because it doesn't understand what the agent actually needs.

## Intent Taxonomy

### The Seven Intents

| Intent | Agent need | Optimal retrieval | Output shape |
|--------|-----------|-------------------|-------------|
| **LOCATE** | Find where something is | Symbol search + file path | Path, line, signature |
| **EXPLAIN** | Understand how something works | Semantic search + trace expansion + call chain | Code with structural annotations |
| **RATIONALE** | Understand why something is this way | Concept search → observation search → code comments | Narrative with source citations |
| **TRACE** | Find what uses/calls/depends on something | Graph traversal (callers, importers) | Dependency list with context |
| **EXAMPLE** | See how something is used in practice | Reverse search (call sites, not definitions) | Usage snippets from consuming code |
| **COMPARE** | Understand differences between two things | Multi-entity retrieval + diff | Side-by-side with annotations |
| **DISCOVER** | Explore what exists in an area | Module-scoped browse + related concepts | Categorized file/symbol list |

### Why Seven and Not Three

You could simplify to "find", "explain", "why" — but the retrieval strategies are genuinely different for each intent. TRACE and EXAMPLE both involve reverse lookups but with different scoping (all callers vs representative usage patterns). COMPARE requires multi-entity retrieval that no other intent needs. DISCOVER is exploratory with no specific target. Collapsing these would mean the same retrieval strategy handles "what calls X" and "show me how X is used in tests" — but those need very different result sets.

## Classification Approaches

### Approach 1: Rule-Based (V1 — Ship This Week)

Pattern matching on query text. Simple, fast, transparent, debuggable.

```python
import re
from enum import Enum

class SearchIntent(Enum):
    LOCATE = "locate"
    EXPLAIN = "explain" 
    RATIONALE = "rationale"
    TRACE = "trace"
    EXAMPLE = "example"
    COMPARE = "compare"
    DISCOVER = "discover"

# Patterns ordered by specificity (most specific first)
INTENT_PATTERNS = [
    # LOCATE — agent wants a position
    (SearchIntent.LOCATE, [
        r"\bwhere\s+is\b", r"\bfind\s+(the\s+)?(function|class|method|file|module)\b",
        r"\bwhich\s+file\b", r"\blocate\b", r"\bpath\s+(to|of|for)\b",
        r"\bgo\s+to\b", r"\bnavigate\s+to\b",
    ]),
    # TRACE — agent wants usage/dependency info
    (SearchIntent.TRACE, [
        r"\bwhat\s+(uses|calls|imports|depends\s+on|references)\b",
        r"\bwho\s+(calls|uses|imports)\b", r"\bcallers?\s+of\b",
        r"\bimported\s+by\b", r"\bdependents?\s+of\b",
        r"\bwhat\s+breaks\s+if\b", r"\bblast\s+radius\b",
    ]),
    # EXAMPLE — agent wants usage patterns
    (SearchIntent.EXAMPLE, [
        r"\bshow\s+me\s+how\b", r"\bexample\s+of\b", r"\busage\s+of\b",
        r"\bhow\s+is\s+.+\s+used\b", r"\bin\s+practice\b",
        r"\bpattern\s+for\b", r"\bhow\s+to\s+use\b",
    ]),
    # RATIONALE — agent wants the "why"
    (SearchIntent.RATIONALE, [
        r"\bwhy\s+(does|did|is|was|do|are)\b", r"\breason\s+(for|behind)\b",
        r"\bdecision\s+(to|behind|about)\b", r"\brationale\b",
        r"\bwhat\s+motivated\b", r"\bdesign\s+choice\b",
    ]),
    # COMPARE — agent wants differences
    (SearchIntent.COMPARE, [
        r"\bdifference\s+between\b", r"\bcompare\b", r"\bvs\.?\b",
        r"\bhow\s+.+\s+differ\b", r"\bcontrast\b",
    ]),
    # DISCOVER — agent wants to explore
    (SearchIntent.DISCOVER, [
        r"\bwhat\s+(exists|is\s+available|do\s+we\s+have)\b",
        r"\blist\s+(all|the)\b", r"\boverview\s+of\b",
        r"\bwhat's\s+in\b", r"\bexplore\b",
    ]),
    # EXPLAIN — default for "how" questions
    (SearchIntent.EXPLAIN, [
        r"\bhow\s+does\b", r"\bwhat\s+does\b", r"\bexplain\b",
        r"\bwalk\s+me\s+through\b", r"\bdescribe\b",
        r"\bhow\s+.+\s+work\b", r"\bunderstand\b",
    ]),
]

def classify_intent(query: str) -> SearchIntent:
    query_lower = query.lower().strip()
    for intent, patterns in INTENT_PATTERNS:
        if any(re.search(p, query_lower) for p in patterns):
            return intent
    # Default: if the query looks like a symbol name, LOCATE; else EXPLAIN
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', query_lower):
        return SearchIntent.LOCATE
    return SearchIntent.EXPLAIN
```

**Advantages:**
- Zero latency (regex is microseconds)
- Fully transparent — the agent can see "Classified as: TRACE" and understand why
- No model dependency — works without LLM
- Easy to iterate — add a pattern when a misclassification is observed
- Testable — unit tests per intent with example queries

**Limitations:**
- Ambiguous queries ("how is auth used" — EXPLAIN or EXAMPLE?) may misclassify
- Non-English queries won't match
- Doesn't handle implicit intent ("auth middleware" — is this LOCATE or EXPLAIN?)

### Approach 2: Hybrid (V2 — After V1 Proves Value)

Rule-based classification with LLM fallback for ambiguous queries.

```python
def classify_intent_hybrid(query: str) -> SearchIntent:
    # Try rules first
    intent = classify_intent_rules(query)
    confidence = measure_pattern_confidence(query, intent)
    
    if confidence > 0.7:
        return intent  # High-confidence rule match
    
    # Ambiguous — use LLM classifier (small model, cached)
    return classify_intent_llm(query, hint=intent)
```

The LLM classifier only fires for ambiguous queries (~20% of cases), keeping latency low. The rule-based result is passed as a hint so the LLM has a starting point.

### Approach 3: Learned Classifier (V3 — Long Term)

Train a lightweight classifier on (query, intent, was_helpful) triples collected from agent feedback. Could be as simple as a logistic regression on TF-IDF features, or a small fine-tuned model.

**Not recommended until V1 has been running long enough to generate training data.**

## Per-Intent Retrieval Strategies

### LOCATE → Symbol-First Pipeline

```python
async def retrieve_locate(query: str) -> SearchResult:
    # 1. Extract likely symbol name from query
    symbol = extract_symbol_from_query(query)  
    # e.g., "where is handle_tools_list" → "handle_tools_list"
    
    # 2. Symbol search (exact + fuzzy)
    results = await trace_idx.search_nodes(symbol, fuzzy=True)
    
    # 3. Enrich with signatures and context
    for result in results:
        result.signature = get_function_signature(result.file, result.line)
        result.docstring = get_docstring(result.file, result.line)
    
    # 4. If no symbol matches, fall back to semantic search
    if not results:
        return await retrieve_explain(query)  # graceful degradation
    
    return format_locate_results(results)
```

**Output shape:**
```markdown
## Found: handle_tools_list (2 locations)

1. `src/codrag/mcp/server.py:892`
   ```python
   async def handle_tools_list(self) -> list[types.Tool]:
       """Return the list of available MCP tools."""
   ```
   Module: MCP Server | Hub file (23 dependents)

2. `src/codrag/mcp_direct.py:145`
   ```python
   async def handle_tools_list(self) -> list[types.Tool]:
       """Direct mode tool listing (subset of server mode)."""
   ```
   Module: MCP Direct | Non-hub (2 dependents)
```

### EXPLAIN → Multi-Source Deep Dive

```python
async def retrieve_explain(query: str) -> SearchResult:
    # 1. Semantic search for relevant code
    chunks = await embedding_search(query, k=5)
    
    # 2. Trace expansion — find structurally connected code
    expanded = await trace_expand(chunks, hops=1)
    
    # 3. Concept check — any relevant design rationale?
    concepts = await concept_search(query, limit=2)
    
    # 4. Assemble with call chain context
    for chunk in expanded:
        chunk.callers = await get_callers(chunk.symbol, limit=3)
        chunk.callees = await get_callees(chunk.symbol, limit=3)
    
    # 5. LOD compression to fit budget
    return assemble_with_lod(expanded, concepts, max_tokens=3000)
```

**Output shape:**
```markdown
## How MCP tool dispatch works

[confidence: 0.86 | sources: semantic + trace expansion + 1 concept]

The MCP server dispatches tool calls through a pattern-matching handler 
in `server.py`. When a tool call arrives:

1. `handle_call_tool()` (server.py:3150) receives the tool name and arguments
2. It matches against known tool names (lines 3163-3246)
3. Each tool routes to a specific handler:
   - "codrag" → `tool_context()` (line 3165)
   - "codrag_search" → `tool_search()` or `tool_trace_search()` (line 3189)
   - "codrag_impact" → `tool_impact()` or `tool_trace_neighbors()` (line 3207)

{code snippet from server.py:3150-3170}

→ Concept: "MCP handler simplification" planned to consolidate 16 tools 
  into 4 (Phase 50). Current state is the result of that consolidation.
```

### RATIONALE → Concepts-First Pipeline

```python
async def retrieve_rationale(query: str) -> SearchResult:
    # 1. Search concepts first — they contain design rationale
    concepts = await concept_search(query, limit=5)
    
    # 2. Search observations — they contain decision history  
    observations = await observation_search(query, limit=5)
    
    # 3. Search code comments and docstrings for inline rationale
    code_comments = await search_comments(query, limit=3)
    
    # 4. If nothing found in knowledge stores, fall back to semantic search
    if not concepts and not observations:
        return await retrieve_explain(query + " reason design decision")
    
    # 5. Assemble narrative
    return format_rationale(concepts, observations, code_comments)
```

**Output shape:**
```markdown
## Why the server uses httpx instead of requests

[source: 1 concept, 1 observation, code comment]

**Concept: "A2A protocol adoption" (Phase 62)**
The MCP server uses httpx because it operates in an async event loop. 
The requests library is synchronous and would block the loop. httpx 
provides the same API surface but with native async/await support.

**Observation (Phase 62, doc 10):**
"CoDRAG will implement A2A protocol alongside MCP. This requires async 
HTTP handling for the JSON-RPC 2.0 endpoint."

**Code (server.py:19):**
```python
import httpx  # async HTTP client for non-blocking daemon communication
```

→ This is an architectural decision, not a preference. Changing to requests 
  would require restructuring the event loop.
```

### TRACE → Graph Traversal Pipeline

```python
async def retrieve_trace(query: str) -> SearchResult:
    # 1. Extract the target symbol/file
    target = extract_target(query)  
    # "what calls tool_impact" → target = "tool_impact"
    
    # 2. Find the symbol in the trace graph
    node = await trace_idx.find_node(target)
    if not node:
        return await retrieve_locate(target)  # graceful degradation
    
    # 3. Get callers/importers (reverse edges)
    direction = infer_direction(query)  # "calls" → dependents, "depends on" → dependencies
    neighbors = await trace_idx.get_neighbors(node, direction=direction, max_hops=2)
    
    # 4. Filter external/stdlib
    internal = [n for n in neighbors if not n.is_external]
    
    # 5. Enrich with module context
    for n in internal:
        n.module = await get_module(n.file_path)
    
    return format_trace_results(node, internal, direction)
```

**Output shape:**
```markdown
## What calls tool_impact (7 callers)

Target: `tool_impact()` @ src/codrag/mcp/server.py:1438

Direct callers (3):
- `handle_call_tool()` @ server.py:3232 — MCP dispatcher, routes "codrag_impact" calls
- `_test_impact()` @ tests/test_mcp.py:445 — Unit test
- `enrich_finding()` @ server.py:1820 — Audit enrichment (adds impact to findings)

Transitive callers (4):
- Main MCP entry point → handle_call_tool → tool_impact
- Test suite → _test_impact → tool_impact
- Audit report generator → enrich_finding → tool_impact (2 paths)

→ Blast radius: MEDIUM — 3 direct callers, all internal. Safe to refactor 
  with targeted test updates.
```

### EXAMPLE → Reverse Search Pipeline

```python
async def retrieve_example(query: str) -> SearchResult:
    # 1. Find the definition
    target = extract_target(query)
    definition = await trace_idx.find_node(target)
    
    # 2. Find all import/call sites
    usages = await trace_idx.get_usages(definition, limit=10)
    
    # 3. For each usage, extract the surrounding code context (5 lines around the call)
    examples = []
    for usage in usages:
        context = await read_lines(usage.file, usage.line - 3, usage.line + 5)
        examples.append(UsageExample(
            file=usage.file,
            line=usage.line,
            context=context,
            module=await get_module(usage.file),
        ))
    
    # 4. Rank by representativeness (diverse modules, different patterns)
    ranked = rank_by_diversity(examples)
    
    return format_examples(ranked[:5])
```

**Output shape:**
```markdown
## How useEventStream is used (5 examples from 3 modules)

### In dashboard components:
```tsx
// src/codrag/dashboard/src/hooks/useDashboardPanels.tsx:45
const { data, error } = useEventStream('/api/pipeline/events');
// Used for real-time pipeline progress updates
```

### In search UI:
```tsx
// packages/ui/src/components/search/SearchInput.tsx:23
const { data: results } = useEventStream(`/api/search/${query}`);
// Used for streaming search results as they arrive
```

### In Storybook stories (test/demo):
```tsx
// packages/ui/src/stories/search/SearchComponents.stories.tsx:67
const stream = useEventStream('/api/mock/events');
// Used with mock endpoint for visual testing
```

→ Pattern: useEventStream takes an API path and returns { data, error }. 
  Always used for real-time server-sent events.
```

### COMPARE → Multi-Entity Pipeline

```python
async def retrieve_compare(query: str) -> SearchResult:
    # 1. Extract the two entities being compared
    entity_a, entity_b = extract_comparison_targets(query)
    # "difference between server.py and mcp_direct.py" → (server.py, mcp_direct.py)
    
    # 2. Get structural info for both
    info_a = await get_file_info(entity_a)  # module, dependents, hub status, concepts
    info_b = await get_file_info(entity_b)
    
    # 3. Find shared and divergent dependencies
    deps_a = set(await get_dependencies(entity_a))
    deps_b = set(await get_dependencies(entity_b))
    shared = deps_a & deps_b
    only_a = deps_a - deps_b
    only_b = deps_b - deps_a
    
    # 4. Check for relevant concepts explaining the distinction
    concepts = await concept_search(f"{entity_a} vs {entity_b}", limit=2)
    
    return format_comparison(info_a, info_b, shared, only_a, only_b, concepts)
```

### DISCOVER → Module-Scoped Browse

```python
async def retrieve_discover(query: str) -> SearchResult:
    # 1. Identify the area to explore
    area = extract_area(query)  # "what's in the MCP module" → "src/codrag/mcp/"
    
    # 2. Get the module summary
    module = await get_module_for_path(area)
    
    # 3. List key files with one-line descriptions
    files = await list_files_with_summaries(area, limit=20)
    
    # 4. Get related concepts
    concepts = await concept_search(area, limit=3)
    
    # 5. Get recent observations about this area
    observations = await observation_search(file_path=area, limit=3)
    
    return format_discovery(module, files, concepts, observations)
```

## Integration Points

### Where Classification Happens

```
Agent calls codrag_search(query="...", type="context")
    │
    ▼
MCP handler (server.py)
    │
    ├── If type="symbol" → skip classification, use symbol search
    │
    ├── If type="context" → classify intent
    │       │
    │       ▼
    │   classify_intent(query) → LOCATE | EXPLAIN | RATIONALE | TRACE | EXAMPLE | COMPARE | DISCOVER
    │       │
    │       ▼
    │   Route to intent-specific pipeline
    │       │
    │       ▼
    │   Return results with [intent: EXPLAIN] tag in metadata
    │
    └── If type specified → honor it (backward compat)
```

### Backward Compatibility

- No new parameters required — classification is automatic
- `type="context"` still works, just smarter about retrieval
- `type="symbol"` bypasses classification entirely
- Add optional `intent` parameter for agents that want to override: `codrag_search(query="...", intent="rationale")`

### Observability

Include the classified intent in the response so agents (and dogfooders) can evaluate:

```markdown
[intent: RATIONALE (confidence: 0.9, pattern: "why does")]
[sources: concepts(2), observations(1), code_comments(0)]
```

If the classification seems wrong, agents can override with the `intent` parameter, and we collect the override as training signal for V2.

## Measuring Impact

How do we know intent classification improves search quality?

1. **Retrieval relevance**: Compare search result relevance before/after classification (manual eval or agent feedback)
2. **Grep fallback rate**: If agents stop falling back to grep after CoDRAG search, classification is working
3. **Intent distribution**: Track which intents are most common — this tells us where to invest optimization effort
4. **Override rate**: How often agents override the classified intent — high override rate means the classifier is wrong
5. **Follow-up search rate**: If agents need fewer follow-up searches, the first search is landing better

## Implementation Plan

| Phase | Scope | Effort |
|-------|-------|--------|
| V1 | Rule-based classifier + LOCATE/EXPLAIN routing | 1-2 days |
| V1.1 | Add RATIONALE routing (concepts-first) | 1 day |
| V1.2 | Add TRACE routing (graph traversal) | 1 day |
| V1.3 | Add EXAMPLE routing (reverse search) | 1 day |
| V2 | Hybrid classifier with LLM fallback for ambiguous | 2 days |
| V2.1 | Add COMPARE and DISCOVER routing | 2 days |
| V3 | Learned classifier from agent feedback | Ongoing |

V1 delivers the highest-value improvement (LOCATE and EXPLAIN are ~70% of queries) with minimal effort. Each subsequent phase adds a new intent without modifying previous ones.

# Phase 86 — Intent Classification: Making Search Understand What You're Actually Asking

**Date:** 2026-04-08
**Status:** Design finalized
**Scope:** Add intent detection to `codrag_search` so different types of questions route to different retrieval strategies, dramatically improving result quality
**Dependencies:** Phase 84 (concepts formalization — RATIONALE intent needs structured concepts)
**Predecessor:** Phase 82 doc 14 (Intent Classification for Search)

---

## Executive Summary

Phase 82 dogfooding revealed that `codrag_search` treats every query the same way: embed it, find nearest neighbors, expand via trace graph, return results. But "Where is the auth middleware?" and "Why does the auth middleware use JWT instead of sessions?" are fundamentally different questions requiring fundamentally different retrieval strategies.

The first question needs **symbol lookup** — find the file, return the path and signature. The second needs **concept retrieval** — find the design decision, return the rationale with code anchors for context. Treating both as semantic similarity search means the first returns too much context and the second misses the conceptual layer entirely.

Intent classification adds a lightweight detection layer in front of search that routes queries to specialized retrieval pipelines. The agent doesn't need to know about intents — it just calls `codrag_search(query="...")` and gets better results because the system understood what kind of answer was needed.

---

## Design

### Intent Taxonomy

Seven intents covering the observed patterns of how AI agents query codebases:

| Intent | Signal Words | What the Agent Wants | Retrieval Strategy |
|--------|-------------|---------------------|--------------------|
| **LOCATE** | "where is", "find", "which file", "path to" | A file path, symbol location, or definition | Symbol search → return path + signature + line number |
| **EXPLAIN** | "how does", "what does", "walk me through", "explain" | Understanding of mechanism/behavior | Semantic search + trace expansion → return code with structural context |
| **RATIONALE** | "why", "reason for", "decision behind", "motivation" | Design rationale or historical context | Concepts-first → return concepts with code anchors, fall back to observations |
| **TRACE** | "what calls", "who imports", "dependents of", "callers" | Dependency/call relationships | Graph traversal → delegates to codrag_impact internally |
| **EXAMPLE** | "how to use", "example of", "usage of", "call sites" | Usage patterns and call sites | Reverse search → find call sites and usage patterns in the codebase |
| **COMPARE** | "difference between", "vs", "compare", "which is better" | Side-by-side analysis of two+ entities | Multi-entity lookup → return parallel descriptions with diff highlights |
| **DISCOVER** | "what's in", "overview of", "modules in", "list" | Browsing/exploration of an area | Module map + file listing → return structured overview of scope |

### V1 Classifier: Rule-Based (Zero Latency)

The classifier is a deterministic rule engine — no LLM, no embedding, no latency cost. It runs before every search query and routes to the appropriate pipeline.

**Classification logic:**

```python
def classify_intent(query: str) -> Intent:
    q = query.lower().strip()
    
    # LOCATE — asking for a position/definition
    if re.match(r"(where|find|locate|which file|path to|definition of)\b", q):
        return Intent.LOCATE
    if re.match(r"(show me|open|go to)\b", q) and not re.search(r"(how|why|explain)", q):
        return Intent.LOCATE
    
    # TRACE — asking about relationships
    if re.search(r"(what calls|who (calls|imports|uses)|dependents|dependencies|callers|importers)\b", q):
        return Intent.TRACE
    
    # RATIONALE — asking why
    if re.match(r"(why|reason|rationale|motivation|decision behind)\b", q):
        return Intent.RATIONALE
    if re.search(r"(instead of|rather than|chose|decision)\b", q):
        return Intent.RATIONALE
    
    # COMPARE — asking about differences
    if re.search(r"(difference|compare|vs\.?|versus|between .+ and)\b", q):
        return Intent.COMPARE
    
    # EXAMPLE — asking for usage
    if re.search(r"(example|usage|how to use|how do I use|call sites|who uses)\b", q):
        return Intent.EXAMPLE
    
    # DISCOVER — asking for overview
    if re.search(r"(what's in|overview|modules|list|browse|contents of)\b", q):
        return Intent.DISCOVER
    
    # EXPLAIN — asking how (broad default for mechanism questions)
    if re.search(r"(how does|what does|explain|walk me through|tell me about)\b", q):
        return Intent.EXPLAIN
    
    # Default: EXPLAIN (semantic search is the safest fallback)
    return Intent.EXPLAIN
```

**Why rule-based, not ML:**
- Zero latency — adds no overhead to search
- Deterministic — same query always routes the same way
- Debuggable — when classification is wrong, you can read the rules and fix them
- Good enough — 7 intents with clear signal words covers 90%+ of agent queries
- Upgradeable — can swap in an ML classifier later without changing the pipeline interface

### Query Rewriting

Before passing the query to the selected pipeline, strip signal words that helped classify but add noise to retrieval:

- LOCATE: "where is the auth middleware" → "auth middleware"
- RATIONALE: "why does server.py use dispatch pattern" → "server.py dispatch pattern"
- EXPLAIN: "how does the pipeline work" → "pipeline"

Simple prefix stripping for V1. More sophisticated rewriting can be added later.

### Per-Intent Retrieval Pipelines

#### LOCATE Pipeline
```
1. Symbol search (exact match first, fuzzy second)
2. Return: file path, line number, qualified name, function signature, first-line docstring
3. If multiple matches: list all with module context to disambiguate
4. Format: concise — this is a lookup, not an explanation
```

#### EXPLAIN Pipeline
```
1. Semantic search (embed query, find top-k chunks)
2. Trace expansion (for each result, include direct callers/callees)
3. LOD compression (detail level based on result relevance score)
4. Return: code context with structural annotations
5. Format: detailed — include enough context to understand mechanism
```

#### RATIONALE Pipeline
```
1. Concepts search (query concepts by semantic similarity to question)
2. Observations search (find relevant decision events)
3. Code anchor expansion (for each concept/observation, include the code it refers to)
4. Return: rationale first, code second — concepts are primary, code is supporting
5. Format: narrative — design decisions need explanation, not just code
6. Fallback: if no concepts match, fall back to EXPLAIN pipeline with a note
   (acceptable degradation when Phase 84 concepts aren't populated yet)
```

#### TRACE Pipeline
```
1. Symbol/file resolution (identify what entity the user is asking about)
2. Delegate to codrag_impact internally (single source of truth for graph traversal)
3. Return: dependency chain with file paths and relationship types
4. Format: tree/list — structural relationships are best shown as hierarchies
```

#### EXAMPLE Pipeline
```
1. Symbol resolution (find the function/class being asked about)
2. Reverse call-site search (find all places in the codebase that call/use this symbol)
3. Return: call sites with surrounding context (3-5 lines around each usage)
4. Format: code snippets with file locations
```

#### COMPARE Pipeline
```
1. Entity extraction (identify the two+ things being compared)
2. Parallel lookup (run EXPLAIN pipeline for each entity)
3. Diff generation (highlight structural differences: dependencies, module, size, hub status)
4. Return: side-by-side comparison with diff highlights
5. Format: table or parallel sections
```

#### DISCOVER Pipeline
```
1. Scope resolution (identify the module/directory being explored)
2. Module map query (get file listing with structural annotations)
3. Hub identification (highlight important files in the scope)
4. Concept overlay (include concepts anchored to this scope)
5. Return: structured overview — file listing + hub files + concepts + entry points
6. Format: overview — like a mini atlas for the scoped area
```

### Multi-Intent Queries

"Where is the auth middleware and why does it use JWT?" contains LOCATE + RATIONALE signals.

**V1: classify as dominant intent.** Priority order when multiple intents match: RATIONALE > TRACE > COMPARE > EXAMPLE > EXPLAIN > LOCATE > DISCOVER. "Why" questions are usually the real question; "where" is just preamble.

**Future:** Multi-pipeline composition — detect compound queries, run both pipelines, merge results. See master roadmap.

### Transparent Intent Reporting

Every response includes a `_meta` block:

```json
{
  "_meta": {
    "intent": "RATIONALE",
    "confidence": "high",
    "pipeline": "concepts-first",
    "fallback_used": false
  }
}
```

### Override Parameter

Optional `intent` parameter bypasses classification:

```
codrag_search(query="server.py", intent="trace")
```

Override usage is logged for manual rule tuning (no auto-learning in V1).

---

## Implementation Plan

### Stage 1: Intent Classifier

**New file:** `src/codrag/core/intent.py`

**What to build:**
1. Intent enum (7 values)
2. Rule-based classifier function
3. Query rewriter (per-intent signal word stripping)
4. Confidence scoring ("high" if multiple signal words, "low" if default fallback)
5. Unit tests with 50+ example queries covering all intents and edge cases

### Stage 2: Pipeline Router

**Files to modify:**
- `src/codrag/mcp/server.py` — Add intent classification before search dispatch
- `src/codrag/mcp_tools.py` — Add optional `intent` override parameter to `codrag_search`

**What to build:**
1. Pipeline router: classify intent → rewrite query → select pipeline → execute → format response
2. LOCATE pipeline (mostly exists as symbol search — add signature/docstring extraction)
3. RATIONALE pipeline (new — concepts-first retrieval with code anchor expansion, EXPLAIN fallback)
4. DISCOVER pipeline (new — scoped module map with concept overlay)

### Stage 3: Enhanced Pipelines

**What to build:**
1. TRACE pipeline (delegates to `codrag_impact` internally)
2. EXAMPLE pipeline (reverse call-site search — needs new trace graph query)
3. COMPARE pipeline (parallel entity lookup with diff generation)
4. Fallback handling — when primary pipeline returns no results, fall back to EXPLAIN

### Stage 4: Response Formatting

**What to build:**
1. Per-intent response templates (LOCATE is concise, RATIONALE is narrative, DISCOVER is structured)
2. `_meta` block injection on all responses
3. Token budget awareness — each pipeline respects per-client context budget
4. Progressive disclosure — each pipeline has "headline" and "full" mode based on budget

### Stage 5: Tuning & Dogfooding

**What to do:**
1. Run 50+ test queries against CoDRAG's own codebase
2. Measure: classification accuracy, result relevance (manual evaluation), token efficiency
3. Tune rules based on misclassifications
4. A/B comparison: intent-classified search vs. current uniform search
5. Log override usage for rule improvement

---

## Success Criteria

1. **Classification accuracy >85%** — measured against a labeled test set of 100+ real agent queries
2. **Zero added latency** — rule-based classifier adds <1ms to search time
3. **LOCATE queries return signatures** — no more bare file paths for "where is X?" queries
4. **RATIONALE queries return concepts** — "why" questions surface design decisions, not just code
5. **DISCOVER queries return structured overviews** — "what's in X?" gets a module map, not random search results
6. **Transparent** — every response includes `_meta.intent` so routing is observable
7. **Override works** — `intent` parameter bypasses classifier when needed

---

## Resolved Questions

1. **Multi-intent queries** — Classify as dominant intent for V1. Priority: RATIONALE > TRACE > COMPARE > EXAMPLE > EXPLAIN > LOCATE > DISCOVER. Multi-pipeline composition is future work.
2. **Query rewriting** — Yes, simple prefix stripping per intent before retrieval.
3. **Learning from corrections** — Log override usage for manual rule tuning. No auto-learning in V1.
4. **TRACE vs codrag_impact overlap** — TRACE delegates to codrag_impact internally. Single source of truth.
5. **Concept dependency** — RATIONALE falls back to EXPLAIN if concepts aren't populated. Acceptable, documented degradation path.

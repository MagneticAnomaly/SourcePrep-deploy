# 02 — `codrag_search` Tool (Semantic Search)

**Grade: B**
**Calls tested:** 3 (semantic context, symbol by name, working_dir scoped)

## What Works Well

### Semantic search lands good hits
Query: "error handling when daemon is unreachable" → returned `model_readiness.py` with `ModelStatus.ERROR` and `ollama_server_reachable()`. Confidence 0.83, directly relevant. The search understood "unreachable" maps to network connectivity checks, not just the string "unreachable."

### Query coverage indicators are useful
The output includes `[query terms: error✓ daemon✓ unreachable✓ | handling✗]` which tells the agent which terms contributed to retrieval. This is rare among RAG tools and genuinely helpful for knowing whether to rephrase.

### working_dir scoping adds session-memory context
When `working_dir="src/codrag/mcp"` was provided, the search injected a relevant observation about Pi Agent from `codrag_observe`. This cross-tool integration is a differentiator.

### Structural trace expansion is real
The semantic hit on `model_readiness.py` for an MCP-related query works because the trace graph knows `model_readiness.py` is structurally connected to the server infrastructure. Pure embedding similarity wouldn't surface this.

---

## Issues Found

### ISSUE 1: Symbol search returns no code context (HIGH)

**Test:** `codrag_search(query="handle_tools_list", type="symbol")`
**Expected:** Function signature, parameter list, docstring, maybe first few lines of body.
**Got:**
```
## Symbol search: handle_tools_list (2 results)
- `handle_tools_list` (symbol) @ `src/codrag/mcp/server.py`
- `handle_tools_list` (symbol) @ `src/codrag/mcp_direct.py`
```

No line numbers. No function signatures. No parameter types. No docstrings. Just file paths.

**Root cause:** `src/codrag/mcp/server.py:1305-1363` (`tool_trace_search`)

The symbol search handler (lines 1335-1343) extracts only 5 fields from each trace node: `id`, `name`, `kind`, `path`, `line`. The markdown formatter (lines 1347-1352) then renders just `name (kind) @ path`.

However, trace nodes in the graph *do* store richer metadata (confirmed in `src/codrag/core/trace/models.py:43-62`):
- `qualname`: fully qualified name (e.g., `ClassName.method_name`)
- `docstring`: function/class documentation
- `parameters`: function signatures
- `return_type`: return type info
- `span`: start/end line numbers

All of this data is available in the `metadata` dict but the MCP formatter explicitly discards it, keeping only the 5 basic fields.

**Impact:** Symbol search is the tool agents would use for "find me this function" — the most common code navigation task. Returning bare file paths makes it barely more useful than `grep`. Agents have to follow up with a `Read` call every time.

**Suggested fix:**
1. Include `qualname`, `docstring` (first 200 chars), and `line` in symbol search results
2. If `span` data exists, include a compact signature: `def handle_tools_list(self, request) -> dict:` 
3. Consider returning a 5-10 line code snippet for each symbol match (like GitHub code search does)

**Code pointers:**
- `src/codrag/mcp/server.py:1335-1343` — node field extraction (where data is lost)
- `src/codrag/mcp/server.py:1347-1352` — markdown formatting (minimal template)
- `src/codrag/core/trace/models.py:43-62` — TraceNode dataclass with rich metadata
- `src/codrag/api/routers/trace_routes/query.py:312-354` — backend returns full nodes

---

### ISSUE 2: Semantic search misses actual code for "build pipeline" (MEDIUM)

**Test:** `codrag_search(query="how does the build pipeline work")`
**Expected:** Hits in `src/codrag/services/pipeline/orchestrator.py` or `src/codrag/services/pipeline/` files.
**Got:** `docs/Phase64_prep-for-agents+paperclip/AGENTS/paperclip-agent-builder.md` (a doc about building Paperclip agent teams) and `src/codrag/core/watcher.py`.

The semantic engine matched "build" + "pipeline" but the intent was "the CoDRAG indexing pipeline build process," not "a pipeline for building Paperclip agents." The watcher.py result was a trace expansion that happened to be useful.

**Root cause:** The embedding model scores "build pipeline" in both contexts similarly. Without intent disambiguation, the doc that literally says "Builder Pipeline" scores higher than the orchestrator code which describes itself as a "pipeline orchestrator."

**Suggested fix:**
1. When a query contains code-suggestive terms ("how does X work"), boost code files over docs in the retrieval ranking
2. Consider query expansion: "build pipeline" → also search for "pipeline orchestrator", "pipeline stages"
3. Or: accept a `scope` parameter that can be set to "code" vs "docs" vs "all"

---

### ISSUE 3: Retrieval confidence metadata is opaque (LOW)

**Output:** `[retrieval confidence: high | top score: 0.86 | 2 chunks]`

What does "2 chunks" mean? Is that 2 matches out of 500 candidates, or 2 chunks from 2 files? What's the score distribution — is 0.86 a clear winner, or are scores 0.86 and 0.85 neck-and-neck?

**Suggested fix:**
- Show the score range: `[top: 0.86, #2: 0.71, #3: 0.58]` — this tells agents whether the top result is a confident match or an ambiguous tie
- Show the candidate pool size: `2 of 847 chunks` vs `2 of 3 chunks` tells very different stories
- Consider a `verbose=true` parameter that returns full scoring details

---

## Opportunities

### OPPORTUNITY 1: "Find usages" query type
Agents frequently need "where is this function called?" — not what it is (symbol), not semantically related code (context), but call sites. This is a graph traversal that CoDRAG's trace graph could answer but neither search type currently supports. Could be `type="usages"` or `type="callers"`.

### OPPORTUNITY 2: Multi-query batching
In real workflows, agents often need 3-5 searches in rapid succession. Each MCP round-trip has latency. A batch query API (`queries: ["auth middleware", "rate limiting", "CORS config"]`) could return results for all in one call.

### OPPORTUNITY 3: Negative examples in search
"Find files that handle authentication BUT NOT the OAuth flow" — exclusion filtering would help narrow results in large codebases. The `exclude_paths` parameter exists but only works on file paths, not semantic content.

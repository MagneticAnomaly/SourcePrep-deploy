# Improvement Roadmap — Prioritized Fixes

> Phase 73: From assessment to action
> Date: 2026-04-04

---

## Priority 1: Fix Search Retrieval (Impact: Critical)

Search is the core value proposition. An agent that can't find the right code might as well not have the tool.

### Problem
Large, important files (orchestrator.py, server.py) are systematically missed in favor of smaller peripheral files. Three test queries all failed to return the most relevant file.

### Root Cause Hypothesis
When a 2,600-line file is chunked into 20-30 segments, each chunk's embedding captures only a fragment of the file's identity. A small, focused 50-line file maintains a coherent semantic identity. Result: small files win retrieval even when large files are objectively more relevant.

### Proposed Fixes

**Fix 1A: File-level boosting (quick win)**
- Extract file-level metadata (path, module name, docstring, class names) as a separate embedding
- When a query mentions a subsystem name that matches a file path, boost that file's chunks
- Example: query contains "MCP" → boost all chunks from `src/prep/mcp/*`

**Fix 1B: Query decomposition**
- Parse the query for structural signals: file names, module names, stage numbers
- Route structural queries to the graph (exact match) before falling back to semantic search
- "how does the orchestrator process files" → graph lookup for "orchestrator" → find `orchestrator.py` → then semantic search within that file

**Fix 1C: Retrieval fusion**
- Blend BM25 (keyword) retrieval with embedding (semantic) retrieval
- BM25 catches exact-match cases (query mentions "MCP", file contains "MCP" hundreds of times)
- Embedding catches conceptual matches
- Score = α × BM25_score + (1-α) × embedding_score, tune α on evaluation set

**Fix 1D: Return multiple candidates**
- Instead of committing to one file, return top 3-5 with relevance indicators
- Let the consuming agent decide which to explore further
- Format: `[0.92] src/prep/mcp/server.py`, `[0.71] src/prep/core/llm_client.py`

### Validation
Create a test suite of 20 queries with expected file results. Measure recall@1 and recall@5.

---

## Priority 2: Deduplicate & Tier the `prep` Overview (Impact: High)

### Problem
The overview returns 745 lines, of which ~13% is useful. The 602-module exhaustive list is counterproductive, and hub content is duplicated 3×.

### Proposed Fixes

**Fix 2A: Chunk-level deduplication (quick win)**
- Hash each assembled chunk content before including it
- If a chunk hash was already included, skip it with a note: "(same as above, omitted)"
- This alone would save ~85 lines (11% of output)

**Fix 2B: Tiered module display**
- Tier 1 (always show): Modules with >10 files OR >3 cross-module dependencies (~15-20 modules)
- Tier 2 (show count): Modules with 3-10 files ("... and 83 modules of 3-10 files")
- Tier 3 (collapse): Single-file modules ("... and 489 single-file modules")
- Provide a hint: "Use `prep_search` to explore smaller modules"

**Fix 2C: Smart context budget**
- Cap the overview at ~200 lines of genuinely novel content
- Allocate budget: 40% module summaries, 30% hub content, 20% focus areas, 10% metadata
- If focus areas are set, give them priority over exhaustive module listing

### Validation
Compare before/after token counts. Target: <200 lines with >60% useful signal rate (up from 13%).

---

## Priority 3: Make Audit File-Type-Aware (Impact: Medium)

### Problem
4 of 11 "critical" findings are lockfiles. Generic advice ("split into subpackages") is given for all file types including auto-generated files and documentation.

### Proposed Fixes

**Fix 3A: File-type classification (quick win)**
- Maintain a list of auto-generated file patterns: `*-lock.*`, `*.lock`, `package-lock.json`, `dist/*`, `build/*`, `*.min.js`
- Exclude or downgrade these from audit severity
- Separate category: "Large auto-generated files" (info-only)

**Fix 3B: Context-aware advice**
- Python/TypeScript large files → "Consider splitting into focused modules"
- Markdown/doc files → "Consider creating a table of contents or splitting into sub-documents"
- Config/lock files → (suppress or info-only)
- Log files → "Consider adding to .gitignore or archiving"

**Fix 3C: Surface graph-based findings**
- The system has 162 known import cycles — surface the top 10 in the default scan
- Surface hub file concentration: "4 files account for 40% of all edges"
- Surface modules with zero incoming edges (orphan detection)
- These are far more interesting than file size

### Validation
Track actionable-finding rate. Target: >80% of "critical" findings should be genuinely critical (vs 27% today).

---

## Priority 4: Add Relevance Signals (Impact: Medium)

### Problem
All search results are presented with equal confidence. An agent can't tell a strong match from a weak one.

### Proposed Fixes

**Fix 4A: Relevance score in output**
- Include the cosine similarity or reranker score with each result
- Format: `[relevance: 0.92] @src/prep/mcp/server.py`
- An agent can interpret 0.92 vs 0.45 as "strong match" vs "best available but weak"

**Fix 4B: Query coverage indicator**
- Show which query terms were matched: "Matched: MCP ✓, tool ✓, handler ✓, request ✗, response ✗"
- This gives the agent (and the human reviewing the agent's work) insight into why a result was selected

**Fix 4C: Empty/low result handling**
- If the best match score is below a threshold, say so: "No strong matches found. Best candidates: ..."
- Better to admit uncertainty than to present a weak match with false confidence

---

## Priority 5: Protect and Extend `prep_impact` (Impact: Maintenance)

### What's Already Good
- Dense, actionable output
- Relationship type annotations
- Direct/transitive separation
- Zero noise

### Small Extensions
- Add intermediate paths for transitive deps: "events.py → via augmenter.py → llm_client.py"
- Add a compact `direction='all'` output format that shows both directions
- Consider adding a "change risk score" based on the number and type of dependents

---

## Implementation Order

*For exact file locations and code snippets for these fixes, see [04_Source_Trace_Analysis.md](04_Source_Trace_Analysis.md) and [05_Epistemic_Depth_Analysis.md](05_Epistemic_Depth_Analysis.md).*

| Phase | Fix | Location / Root Cause | Effort | Impact |
|-------|-----|-----------------------|--------|--------|
| 73.1 | 2A: Chunk dedup | `search.py:524-549` | Small | High |
| 73.1 | 2B: Tiered modules | `search.py:448-464` | Small | High |
| 73.1 | 3A: Audit Cache Invalidation | `mcp/server.py:1302` (stale disk read) | Small | Medium |
| 73.1 | 4A: Relevance scores | `mcp/server.py:781` | Small | Medium |
| 73.1 | 5A: Better module names | `cluster.py:113` (prompt update) | Small | Medium |
| 73.2 | 1A: File-name keyword boost | `search.py:876` | Medium | Critical |
| 73.3 | 1D: Multiple candidates | `search.py:870` | Medium | High |
| 73.4 | 1E: Semantic meta-chunk | `index.py:521-552` (mitigates blind slicing) | Large | Critical |
| 73.4 | 1C: Retrieval fusion | `index.py` (BM25 index) | Large | Critical |
| 73.5 | 1B: Query decomposition | NLP/classification logic | Large | High |
| 73.5 | 4B: Query coverage | `index.py` scoring | Medium | Medium |

Phases 73.1 and 73.2 are immediate quick wins that can be shipped in hours and will drastically raise the signal-to-noise ratio. Phase 73.3-73.4 addresses structural retrieval barriers (the "blind string slicing" of AST nodes). Phase 73.5 is forward-looking.

# Epistemic Depth Analysis — Audit & Embedding Limitations

> Phase 73: Deep dive into chunking, retrieval barriers, and audit synchronization
> Date: 2026-04-04

This document continues the critical epistemic audit by tracing the deep backend logic governing `prep_audit` staleness and `prep_search` chunking strategies.

---

## 1. Audit Staleness & Auto-Generated File Noise

### The Symptom
The `prep_audit` tool repeatedly flags lockfiles like `package-lock.json` as "large files" with generic advice to "split into a subpackage", despite the codebase (`src/prep/core/audit/analyzers/large_files.py`) containing an explicit filter:

```python
EXPECTED_LARGE_BASENAMES = frozenset({
    "package-lock.json",
    "yarn.lock",
    # ...
})
```

### The Root Cause: Cache Invalidation
The `LargeFileAnalyzer` logic is correct, but **the output is stale**. 

In `src/prep/mcp/server.py` (`tool_audit`), the MCP tool fetches findings using this sequence:
1. `data = await self._api_get(f"/projects/{project_id}/audit/findings")`
2. If findings exist in the cache/database, it returns them *immediately*.
3. It only forces a new calculation `IF not findings:`.

Because `trace_findings.jsonl` persists on disk, the UI/MCP continuously serves the old findings generated *before* `package-lock.json` was added to the ignore list. The backend orchestrator only recalculates the graph when code changes, and it doesn't know that the *analyzer logic itself* was updated.

### The Fix
Modify `prep_audit` to accept a `force_refresh` parameter (translating to `synthesize=True` or an explicit fresh endpoint call), or implement backend cache invalidation when the Prep engine version changes. As a quick fix, changing the `prep_audit action="scan"` logic to always trigger a fresh run for AI calls guarantees accurate context.

---

## 2. The Semantic Rupture in Code Chunking

### The Symptom
`prep_search` systematically fails to retrieve large, architectural files like `orchestrator.py` because the query isn't matched against the file's holistic concept.

### The Root Cause: Blind String Slicing
Tracing the `LayeredIndex` build process reveals a critical semantic rupture:

1. **Large File Truncation**: In `index.py:521-552`, files larger than 500KB are aggressively truncated into a single 8000-character synthetic chunk.
2. **Blind Slicing**: Normal files (like the 100KB `orchestrator.py`) are passed to `chunk_code` (`src/prep/core/chunking.py:208`). 
3. **No AST Awareness**: `chunk_code` splits files purely by character limit (2000 chars) with 200 overlap chars. It literally does `chunk_text = text[start:end]`. 

For `orchestrator.py`, a 2000-char slice in the middle of the file (lines 1000-1100) might contain only loop logic. When embedded via `_format_chunk_for_embedding`, the chunk gets prepended with:
```text
Path: src/prep/core/orchestrator.py
Hash: abc1234

<loop logic>
```
But it receives **no semantic markers** indicating that this code belongs to the "Pipeline Orchestrator" class. Unless the word "orchestrator" appears in the loop body, a query for "orchestrator processing" will score very low against this chunk.

### The Fix
**Short Term: File-Name Keyword Boosting**
Implement the Fix 3A proposed in `04_Source_Trace_Analysis.md`: artificially boost chunks whose `source_path` basename matches query keywords.

**Long Term: Semantic AST Chunking**
Refactor `chunk_code` in `chunking.py` to use AST-aware slicing (e.g., via `tree-sitter`), ensuring chunks break at class or function boundaries. Wait until Phase 74 to attempt AST integration, as it requires heavy dependency additions.

**Immediate Quick Win: Meta-Chunk Injection**
In `index.py`, before or during chunk generation, generate a 0th chunk that contains the file's top-level docstring, class names, and any `domain_tags` generated from the epistemic enrichment suite. This creates a "global file summary" chunk that easily hits keyword matches.

# Phase 73: Quality Recommendations Implementation Plan

This document details the architectural changes required to resolve the issues outlined in the Phase 73 Quality Recommendations evaluation, specifically focusing on context resolution size, semantic search routing, and codebase audit noise.

## Issue 1: Context Budget Misallocation (The 258KB Payload Bug)

**The Problem**: 
The CoDRAG tool failed with a context overflow `result (258,887 characters) exceeds maximum allowed tokens. Output has been saved to txt.` This was caused by the newly introduced Architecture layer logic. In `src/codrag/api/routers/architecture.py`, the `get_architecture_context` endpoint loops through **all** modules found in trace data (regularly >600 modules in this repo) and returns their full dependency arrays. This payload is then unconditionally included by the MCP server `tool_context` without applying budget truncation, thereby causing complete protocol failure and clogging the agent context window with useless noise.

**The Solution**: Tier the `architecture/context` response so the context is heavily compressed.
1. **Target File**: `src/codrag/api/routers/architecture.py`
2. **Modifications to `get_architecture_context`**:
   - Instead of writing out every module from `modules`, we will categorize them based on significance criteria.
   - **Inclusion Criteria**: We will ONLY emit the full markdown string for a module if:
     - It has at least 5 files (`file_count >= 5`).
     - OR it has Notes annotated by the user (`len(notes) > 0`).
     - OR it has active ACRs (Architecture Change Requests) (`len(acrs) > 0`).
     - OR it has Linked Issues (`len(issues) > 0`).
   - Modules that don't match this criteria (which are typically auto-inferred 1-2 file peripheral modules) will be filtered out from the verbose array.
   - We will count these filtered modules, bucket them by size (e.g. `small` for 2-4 files, `tiny` for 1 file), and append a summary statement at the end instead of listing them:
     - `*Plus X smaller modules (2-4 files) without explicit annotations.*`
     - `*Plus Y single-file modules without explicit annotations.*`
3. **Outcome**: The architecture payload will drop from 248KB to just 5-10KB, consisting only of the Tier 1 architectural backbone and any modules explicitly annotated or managed by humans.

## Issue 2: Retrieval Misses on "Home Base" Queries

**The Problem**: 
As noted in the research, a `codrag_search` for queries like "how does the pipeline orchestrator process files" failed to retrieve `orchestrator.py`, returning tangentially related files instead because embedding spaces often favor conceptual similarities over explicit file names. Querying for "MCP tool handler request response" missed `server.py` entirely.

**The Solution**: Implement "Path-Keyword Boosting" within the core CodeIndex to blend semantic retrieval with structural filesystem priors.
1. **Target File**: `src/codrag/core/index.py`
2. **Modifications to `CodeIndex.search()`**:
   - We will introduce a path-matching heuristic algorithm just after the base tensor dot-product embeddings are calculated (`sims`).
   - Tokenize the user's `query` into clean alphanumeric keywords (excluding stop words or generic terms like 'how', 'does', 'the', if possible, or just all words `len > 3`).
   - Iterate through the indexed document paths (`docs[i].get("source_path")`).
   - If a query word is a substring of the directory path, add a minor `+0.15` boost score.
   - If a query word matches or strongly correlates with the exact basename (e.g. `orchestrator` in `orchestrator.py`), add a major `+0.25` boost score.
   - Apply these dynamic boosts directly to the similarity matrix (`sims = sims + path_boosts`) before MMR re-ranking.
3. **Outcome**: When the user explicitly queries for an infrastructure term like "orchestrator" or "mcp server", chunks whose source file explicitly maps to those names will heavily float to the top of standard semantic overlaps.

## Issue 3: Audit Noise (`codrag_audit`)

**The Problem**:
The `codrag_audit` codebase health scanner reports `package-lock.json` and generated compilation folders as "Critical" findings for large/over-coupled architectures. This pollutes the finding ratio.

**The Solution**: Pre-filter generated static files before the analyzer executes its findings.
1. **Target File**: `src/codrag/core/audit/analyzers/large_files.py` (and potentially `base_analyzer.py` or the specific metric analyzers).
2. **Modifications**:
   - The current `EXPECTED_LARGE_BASENAMES` checks for exact matches of specific root files, but it misses arbitrary `.lock` files or minified build files.
   - Update the filter to check for suffix exclusions: `basename.endswith(".lock")`, `.min.js`.
   - Update the filter to exclude paths from common generated directories. If the `file_path` contains `/dist/`, `/build/`, `/out/`, `/.next/`, etc., the analyzer will immediately `continue` and ignore the file.
3. **Outcome**: Actionability is increased. 100% of large-file warnings will correspond to actual human-written logic needing refactoring rather than auto-generated manifest files.

---

## Verification Plan

1. **Architecture Endpoint**: Call `python3 -c "import requests; print(len(requests.get('http://127.0.0.1:8400/projects/.../architecture/context').json()['data']['text']))"` and confirm the size drops from ~248,000 characters to under 10,000.
2. **Home Base Query Test**: Use the MCP `codrag_search` tool for "how does the pipeline orchestrator process files" and verify `src/codrag/services/pipeline/orchestrator.py` appears in the top chunks.
3. **Audit Results**: Trigger `codrag_audit`, inspect the markdown output, and confirm `package-lock.json` has disappeared from the critical size warnings.

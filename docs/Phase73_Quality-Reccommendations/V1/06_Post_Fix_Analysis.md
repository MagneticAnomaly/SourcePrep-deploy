# Phase 73.2 — Deep Source Trace: Remaining Issues & New Opportunities

> Date: 2026-04-05 | Post-Fix-1-through-5 Analysis

---

## Issue 1: Atlas Module Dump (Lines 73-110 in overview)

### The Symptom
The `prep` overview still shows ~35 module names in an "Architecture" section at the bottom of the output:
```
### Architecture (3742 modules, 239 shown)
- **Lucide Icon Components** (47 files) → depends on: none
- **Ui Subsystem (Docs) #2** (46 files) → depends on: none
...
```

### Root Cause Traced
This is NOT from `_assemble_ambient_context` (which we already fixed). It comes from a **completely different code path**:

1. `server.py:tool_context` (line 970) calls `GET /projects/{id}/architecture/context`
2. That hits `architecture.py:get_architecture_context` (line 424)
3. Which loads ALL modules from `trace_modules.jsonl` and renders them into text
4. The text is then appended to the overview output at `server.py:978`

Key detail at **architecture.py:468-488**: This path already has its own tiering logic (Phase 73 was applied there too), but it still shows **239 "significant" modules** because the threshold is `fc >= 5 OR has_notes OR has_acrs OR has_issues`. With 3742 total modules (from all segments), there are 239 modules with 5+ files.

### Fix Proposal
Two options:
1. **Short term:** In `architecture.py:488`, add a hard cap: only show the top N significant modules (e.g., top 30 by file count). Add a collapsed count for the rest.
2. **Medium term:** In `server.py:977`, add `_truncate_section` with a tighter budget (e.g., 1500 chars instead of 3000) for the architecture context section.

**Location:** `src/prep/api/routers/architecture.py:488-521`

---

## Issue 2: Relevance Scores Not Displaying

### The Symptom
We set `include_scores: True` in `server.py:781`, but the `[retrieval confidence: ...]` line doesn't appear.

### Root Cause Traced
The MCP server sends `structured: True` (line 782), which routes to the **structured search path** in `search.py:988-1057` (using `get_context_with_trace_expansion`). 

This structured path does NOT pass `include_scores` through to the index. Scores live inside the `chunks` array in the response, but `_format_context_response` (server.py:1029) extracts only `context`, `chunks_used`, `total_chars`, and `estimated_tokens` — it drops `chunks` entirely and never reads `sources`.

The confidence display code at `server.py:820` reads `data.get("sources", [])`, but the structured path returns chunks as `data.get("chunks", [])`, and each chunk may have a `score` field.

### Fix Proposal
In `server.py:820`, read scores from `chunks` instead of `sources`:

```python
# Try chunks first (structured path), then sources (non-structured)
score_items = data.get("chunks", data.get("sources", []))
if score_items:
    scores = [s.get("score", 0) for s in score_items if isinstance(s, dict) and s.get("score")]
```

**Location:** `src/prep/mcp/server.py:820-829`

---

## Issue 3: Search Retrieval Quality (Structural, NOT a quick fix)

### The Symptom
Querying "how does the orchestrator process files" returns agent adapter docs instead of `orchestrator.py`.

### Root Cause (confirmed)
The structured search path at `search.py:999` calls `get_context_with_trace_expansion`, which internally calls `idx.search()` with the query. The search uses cosine similarity on embeddings.

`orchestrator.py` is 3248 lines, chunked into ~20 pieces. Each chunk's embedding represents ~160 lines of arbitrary code. The query "how does the orchestrator process files" matches better against a focused 300-line doc about "HR Agent Adapter" that mentions "process", "files", and "orchestrator" in a compact, coherent semantic unit.

This is the "semantic fragmentation" problem. It requires one of:
- File-name keyword boosting (Phase 73.2 roadmap item 1A)
- Semantic meta-chunk injection (Phase 73.4 roadmap item 1E)
- BM25 hybrid retrieval (Phase 73.4 roadmap item 1C)

**Not a quick fix.** Leave for Phase 73.2+.

---

## New Opportunity A: Module Name Quality in Architecture Context

Looking at the output, there's a clear naming quality issue in the architecture section:
```
- **Ui Subsystem (Docs) #2** (46 files)
- **Ui Subsystem (Packages) #2** (41 files) 
- **Ui Subsystem (Tests) #77** (36 files)
- **Ui Subsystem (Packages) #3** (29 files)
- **Ui Subsystem (Packages) #5** (27 files)
- **Ui Subsystem (Packages) #8** (25 files)
```

These are clearly from the un-enriched module clustering—the `#2`, `#77` suffixes indicate they were auto-generated cluster IDs without LLM synthesis. There are 6+ modules named "Ui Subsystem" with different numbering. This is exactly the problem Fix 5 (improved module naming prompt) will address on the next pipeline run.

**Opportunity:** The architecture context endpoint could also deduplicate or collapse modules with nearly identical names.

---

## New Opportunity B: Architecture Context Budget

The `server.py:977` architecture injection uses `_truncate_section(arch_text, 3000, "architecture")`. Since we now have the tiered module list in the main overview section (Fix 1), the architecture section is partially redundant. We could:

1. Reduce the architecture budget from 3000 to 1500 chars
2. OR skip the architecture section entirely when `has_rules` is True (since the atlas is already in the system prompt)
3. OR only include modules that have annotations/ACRs/issues (the truly curated content)

---

## New Opportunity C: Concept Augmentation in Search

Looking at `server.py:831-850`, the search tool already tries to augment results with matching concepts from the concept store. This is a Phase 74 feature. If concepts are well-seeded, this could partially compensate for search retrieval misses by surfacing domain knowledge even when the embedding match is weak.

---

## Priority for Next Fixes

| Fix | File | Impact | Effort |
|-----|------|--------|--------|
| Atlas module cap (Issue 1) | `architecture.py:488` | High — eliminates 35 noisy lines | Small (5 lines) |
| Score display from chunks (Issue 2) | `server.py:820` | Medium — enables agent calibration | Small (3 lines) |
| Architecture budget reduction (Opp B) | `server.py:977` | Medium — saves ~1500 chars | Small (1 line) |

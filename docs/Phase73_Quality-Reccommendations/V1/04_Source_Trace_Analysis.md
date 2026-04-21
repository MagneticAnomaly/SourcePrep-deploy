# Source Trace Analysis — Where Problems Live in the Code

> Phase 73: Mapping quality issues to specific code locations and prompts
> Date: 2026-04-04

This document traces each quality issue identified in the README back to its source location in the codebase, identifies the root cause, and classifies the fix difficulty.

---

## Issue Map

```
Problem                          → Root Cause File                                    → Fix Type
───────────────────────────────────────────────────────────────────────────────────────────────────
600-module dump in prep         → search.py:448-464 (scope_modules loop)              → Code change
Hub content 3× duplicated        → search.py:524-549 (hub content assembly)             → Code change + dedup
Search misses large files         → search.py:876-904 (idx.get_context)                 → Embedding/retrieval fix
Audit flags lockfiles as critical → AutoAudit (not in search.py)                        → Filter heuristic
Module names are confusing       → cluster.py:113-135 (MODULE_SYNTHESIS_PROMPT)          → Prompt engineering
No relevance scores in search    → server.py:798-821 (tool_search markdown)             → Output format change
```

---

## Trace 1: The 600-Module Dump

### Where it happens

[search.py:448-464](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L448-L464) — `_assemble_ambient_context`

```python
if scope_modules:
    mod_header = "## Modules in scope\n"
    for m in sorted(scope_modules, key=lambda x: -x.get("file_count", 0)):
        # ... formats EVERY module that overlaps with included_paths
```

### Why it produces 600 modules

The `scope_modules` list is built by scanning `trace_modules.jsonl` (line 424-446) and checking if **any** member file falls under `included_paths`. Since the user's `included_paths` contains broad directories like `src/prep/core/`, `docs/`, etc., **every module that has even one file under those paths is included**. There's no filter on module size or significance.

### The fix

**Option A (Quick — code change):**
Add a tier filter immediately after the scope check:

```python
# Tier 1: Modules with ≥5 files and/or dependencies
significant_modules = [m for m in scope_modules if m.get("file_count", 0) >= 5 or m.get("dependencies")]
remaining_count = len(scope_modules) - len(significant_modules)

mod_header = "## Modules in scope\n"
for m in sorted(significant_modules, key=lambda x: -x.get("file_count", 0)):
    # ... format as before

if remaining_count > 0:
    mod_header += f"\n... and {remaining_count} smaller modules (1-2 files each)\n"
```

**Option B (Better — add LOD to module display):**
Apply the same LOD concept used for code to module listing. Top modules get full descriptions, smaller ones get names only, tiny ones get collapsed.

**Fix location:** [search.py:448-464](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L448-L464)
**Difficulty:** Easy (10 lines changed)
**Impact:** High (eliminates ~500 lines of noise from prep output)

---

## Trace 2: Hub Content Triplication

### Where it happens

[search.py:524-549](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L524-L549) — hub content assembly loop

```python
for fp, deg in hub_files:
    file_docs = doc_by_path.get(fp, [])
    # Pick the largest chunk for this file
    best_doc = max(file_docs, key=lambda d: len(str(d.get("content") or "")))
    content = str(best_doc.get("content") or "")
    # ... adds this to parts WITHOUT checking for duplicate content
```

### Why it duplicates

The same source document (`02_Prep_Epistemology.md`) appears as a hub because it has high connectivity. The `doc_by_path` index maps file paths to chunks, and the same file may have multiple chunks with overlapping content. The system picks the "largest chunk" for each file, but the same **underlying content** (the epistemology table + pipeline stages) appears in multiple chunks because the file is chunked at section boundaries and several sections share the preamble content.

Additionally, the `hub_files` list may contain the same file path multiple times if it appears through different scope paths.

### The fix

**Option A (Quick — dedup by content hash):**

```python
seen_content_hashes = set()

for fp, deg in hub_files:
    file_docs = doc_by_path.get(fp, [])
    best_doc = max(file_docs, key=lambda d: len(str(d.get("content") or "")))
    content = str(best_doc.get("content") or "")
    
    # Dedup: skip if we've already included substantially similar content
    content_hash = hashlib.md5(content.encode()).hexdigest()
    if content_hash in seen_content_hashes:
        continue
    seen_content_hashes.add(content_hash)
    # ... rest of assembly
```

**Option B (Better — dedup by file path):**

```python
seen_hub_paths = set()

for fp, deg in hub_files:
    if fp in seen_hub_paths:
        continue
    seen_hub_paths.add(fp)
    # ... rest of assembly
```

**Fix location:** [search.py:524-549](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L524-L549)
**Difficulty:** Easy (5 lines added)
**Impact:** Medium (saves ~85 lines / ~11% of output in this case)

---

## Trace 3: Search Misses Large Files

### Where it happens

The search pipeline goes through multiple layers:

1. **MCP server** [server.py:795](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/mcp/server.py#L795): `data = await self._api_post(f"/projects/{project_id}/context", payload)`
2. **API router** [search.py:876-904](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L876-L904): `ctx = idx.get_context(req.query, k=req.k, ...)`
3. **LayeredIndex.get_context()** — the actual embedding search (in a different file)

### Why large files are missed

The `idx.get_context()` call performs embedding-based retrieval. Large files (like `orchestrator.py` at 2,643 lines) are split into ~20-30 chunks during Stage 4 (chunking). Each chunk's embedding represents only 100-200 lines of code to the embedding model. When a user asks "how does the orchestrator process files", the query embedding is compared against these small chunk embeddings.

The problem: **no chunk from orchestrator.py contains enough context to embed "orchestrator" and "process files" together**, because:
- The file header/imports chunk might embed "orchestrator" but not "process files"
- The file processing logic chunks embed the logic but don't reinforce "orchestrator"
- Smaller, more focused files like `watcher.py` have coherent single-chunk embeddings that accidentally match better

### The fix cascade

This is the hardest problem because it requires changes across the retrieval pipeline:

**Fix 3A: File-name keyword boosting (moderate effort)**
In [search.py:876-886](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L876-L886), before calling `idx.get_context()`, parse the query for structural signals and boost matching files:

```python
# Extract potential file/module names from query
query_terms = set(req.query.lower().split())
# Boost files whose names or paths contain query terms
file_name_boost_paths = set()
for d in (getattr(idx, '_documents', None) or []):
    sp = str(d.get("source_path") or "")
    basename = sp.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    if basename in query_terms or any(t in sp.lower() for t in query_terms if len(t) > 3):
        file_name_boost_paths.add(sp)

if file_name_boost_paths:
    if _segment_file_paths is None:
        _segment_file_paths = file_name_boost_paths
    else:
        _segment_file_paths = _segment_file_paths | file_name_boost_paths
    _sr6_segment_boost = max(_sr6_segment_boost, 0.20)
```

**Fix 3B: File-level meta-embedding (larger effort)**
During Stage 4/5, generate a file-level "meta chunk" that includes the file path, top-level docstring, class/function names, and the file's role from epistemic enrichment. This meta chunk acts as a high-level summary that semantically represents the whole file.

**Fix 3C: Hybrid BM25+embedding search (larger effort)**
Add a BM25 index alongside the embedding index. For keyword-heavy queries ("orchestrator", "MCP", "server"), BM25 provides exact matches that embeddings miss. Blend scores: `final = 0.6 * embedding_score + 0.4 * bm25_score`.

**Fix location:** [search.py:876-904](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/api/routers/projects/search.py#L876-L904)  
**Difficulty:** 3A = moderate, 3B = large, 3C = large  
**Impact:** Critical (fixes the core retrieval quality problem)

---

## Trace 4: Module Names Are Confusing

### Where the names come from

[cluster.py:113-135](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/core/cluster.py#L113-L135) — `MODULE_SYNTHESIS_PROMPT`

The LLM generates the `name` field from the prompt:

```
"name": "human-readable subsystem name"
```

### Why names like "Ui Subsystem (Docs) #23" appear

The clustering algorithm (Leiden-based, lines 444-660) can produce many small clusters, especially in the `docs` layer. When the LLM synthesizes modules for clusters of 1-2 files, it often produces generic names because there's not enough context. The numbering (#23) comes from the cluster deduplication — when multiple clusters get synthesized with the same name "Ui Subsystem (Docs)", they get sequential suffixes.

### The fix

**Option A: Prompt improvement (easy)**

Add to `MODULE_SYNTHESIS_PROMPT`:

```
IMPORTANT: The "name" MUST be specific and descriptive. Do NOT use generic names 
like "UI Subsystem" or "Configuration Module". Instead, describe what this specific 
subsystem DOES, e.g., "LLM Model Readiness Detection" or "File Watch & Auto-Rebuild".
For clusters with 1-2 files, use the most descriptive file name as the basis for 
the module name.
```

**Option B: Post-processing dedup (easy)**
After synthesis, detect duplicate names and disambiguate using directory paths or file names rather than sequential numbers.

**Option C: Raise min_cluster_size (easy but lossy)**
Increasing `min_cluster_size` from 2 to 3 or 4 would reduce the number of tiny modules. But this loses granularity. Better to keep granularity in the data but collapse it in the *display*.

**Fix location:** [cluster.py:113-135](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/core/cluster.py#L113-L135)
**Difficulty:** Easy (prompt text change)
**Impact:** Medium (better names improve agent comprehension of module list)

---

## Trace 5: No Relevance Scores in Search Output

### Where the score is lost

[server.py:776-821](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/mcp/server.py#L776-L821) — `tool_search`

```python
payload: Dict[str, Any] = {
    "query": query,
    "k": k,
    "max_chars": max_chars,
    "include_sources": True,
    "include_scores": False,      # ← SCORES ARE DISABLED
    "structured": True,
    "trace_expand": bool(trace_expand),
}
```

The scores are explicitly turned off at line 781: `"include_scores": False`.

### Why it was disabled

Likely a deliberate choice to keep the response clean and avoid confusing AI agents with raw similarity numbers. But this decision removes a critical quality signal.

### The fix

**Option A: Include scores in metadata (not in main text)**

In [server.py:781](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/mcp/server.py#L781):
```python
"include_scores": True,
```

Then in the markdown assembly (line 820-821), add a brief header:

```python
if context_str:
    # Add relevance indicator
    avg_score = sum(s.get("score", 0) for s in sources) / max(len(sources), 1)
    confidence = "high" if avg_score > 0.7 else "medium" if avg_score > 0.4 else "low"
    result["_to_markdown"] = f"[relevance: {confidence}]\n" + context_str
```

**Fix location:** [server.py:781](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/mcp/server.py#L781)
**Difficulty:** Easy (2 lines changed)
**Impact:** Medium (agents can calibrate trust in results)

---

## Trace 6: Atlas Content in `prep` vs Rules File

### An interesting design decision

[server.py:858-868](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/mcp/server.py#L858-L868):

```python
# ISSUE-6: Adaptive atlas inclusion.
# If a Prep rules file exists, the atlas is already in the AI's
# system prompt (via alwaysApply/always_on). Skipping the atlas
# prepend saves ~500-2500 chars of budget
has_rules = self._project_has_rules_file(project_id)
payload: Dict[str, Any] = {
    "query": "",
    "max_chars": max_chars,
    "include_atlas": not has_rules,
}
```

This is **actually well-designed** — it avoids redundancy by checking if the atlas is already in the system prompt. The problem is that the `_assemble_ambient_context` function then dumps the exhaustive module list regardless of whether the atlas was included. The module list is not gated by a similar dedup check.

---

## Trace 7: The `tool_context` Budget System

### OPP-W5 Adaptive Budget

[server.py:845-846](file:///Volumes/4TB-BAD/HumanAI/Prep/src/prep/mcp/server.py#L845-L846):

```python
if max_chars <= 0:
    max_chars = self._get_context_budget()
```

This calls a client-aware budget function. The idea is right (different AI tools have different context windows), but the budget is currently spent on low-value content (602 module names) rather than being directed toward high-value content (code from hub files, actual module summaries for significant modules only).

### The opportunity

The budget system exists but isn't quality-aware. Adding a **content priority queue** would dramatically improve signal:

1. Atlas preamble (if not in rules file) — high priority
2. Top 3-5 module summaries (with dependencies) — high priority
3. Hub file code (LOD 0) — high priority
4. Neighbor code (LOD 2) — medium priority
5. Remaining module names — low priority (collapse if budget is tight)

This is essentially what happens today, but without collapsing step 5.

---

## Quick Win Inventory

| Fix | Location | Lines Changed | Impact | Effort |
|-----|----------|---------------|--------|--------|
| Tier module display | search.py:448-464 | ~10 | 🟢 High | 30 min |
| Dedup hub content | search.py:524 | ~5 | 🟡 Medium | 15 min |
| Enable scores | server.py:781 | 2 | 🟡 Medium | 5 min |
| Improve module name prompt | cluster.py:113-135 | ~5 | 🟡 Medium | 10 min |
| File-name keyword boost | search.py:~880 | ~15 | 🟢 High | 2 hours |
| Filter lockfiles from audit | audit engine | ~10 | 🟡 Medium | 30 min |

**Total quick wins: ~5 changes, ~3.5 hours of work, would dramatically improve signal quality.**

---

## Architecture Observation

The `_assemble_ambient_context` function in `search.py` is doing too many jobs at once:
1. Loading and filtering modules
2. Resolving hub files
3. Expanding neighbors via trace
4. Assembling LOD-compressed content
5. Budget management

This is a 270-line function (401-632) that would benefit from extraction into a dedicated `ContextAssembler` class with pluggable strategies for each step. This matches the Phase 72 Pipeline Refactor philosophy of decomposing god functions.

But that's a larger refactor. The quick wins above can ship immediately without architectural changes.

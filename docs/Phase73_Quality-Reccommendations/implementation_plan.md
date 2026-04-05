# Phase 73.1: Quick-Win MCP Quality Fixes

Implement the 5 highest-impact, lowest-effort fixes identified during the Phase 73 quality audit. These changes collectively transform the MCP tool signal-to-noise ratio from ~13% to an estimated ~60-70%.

## User Review Required

> [!IMPORTANT]
> **All changes are in the MCP response-formatting layer.** No schema changes, no database migrations, no embedding rebuilds. The pipeline and index remain untouched. The dev server must be restarted after the changes to pick them up.

> [!WARNING]  
> **Fix 3 (Audit always-refresh)** changes behavior: the `codrag_audit scan` action will always trigger a fresh audit run instead of serving cached results. This is a ~1-2 second latency increase per audit call. This is intentional — stale results are worse than slow results for an AI agent. If you'd prefer a `force_refresh` parameter instead, let me know.

---

## Proposed Changes

### Fix 1: Tiered Module Display (search.py)
**The Problem:** `codrag` overview dumps all 602 modules in a flat list, consuming ~500 lines of output.  
**The Fix:** Tier modules into 3 groups — significant (≥5 files), small (2-4 files), and tiny (1 file) — and only show details for significant modules, collapsing the rest into counts.

#### [MODIFY] [search.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/api/routers/projects/search.py)

Replace lines 448-465 (the `if scope_modules:` block) with tiered display logic:

```python
if scope_modules:
    # Phase 73.1: Tier modules to reduce noise
    significant = [m for m in scope_modules if m.get("file_count", 0) >= 5]
    small = [m for m in scope_modules if 2 <= m.get("file_count", 0) < 5]
    tiny = [m for m in scope_modules if m.get("file_count", 0) < 2]

    mod_header = "## Modules in scope\n"
    for m in sorted(significant, key=lambda x: -x.get("file_count", 0)):
        name = m.get("name", m.get("module_id", "?"))
        summary = m.get("summary", "")
        fc = m.get("file_count", 0)
        deps = ", ".join(m.get("dependencies", [])[:3])
        line = f"- **{name}** ({fc} files)"
        if summary:
            line += f": {summary}"
        if deps:
            line += f" → {deps}"
        mod_header += line + "\n"
    if small:
        mod_header += f"\n*Plus {len(small)} smaller modules (2-4 files each)*\n"
    if tiny:
        mod_header += f"*Plus {len(tiny)} single-file modules*\n"
    parts.append(mod_header.strip())
    total_chars += len(parts[-1])
```

**Expected impact:** ~500 lines → ~30 lines. The collapsed count lines let the agent know the data exists and can be explored via `codrag_search`.

---

### Fix 2: Hub Content Deduplication (search.py)
**The Problem:** The same file's content appears multiple times in the hub assembly because `hub_files` can contain duplicate paths.  
**The Fix:** Track seen file paths and skip duplicates.

#### [MODIFY] [search.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/api/routers/projects/search.py)

Add dedup tracking before the hub assembly loop at line 523:

```python
hub_chars = 0
seen_hub_paths: set = set()  # Phase 73.1: dedup hub files
for fp, deg in hub_files:
    if hub_chars >= hub_budget:
        break
    if fp in seen_hub_paths:  # Phase 73.1: skip duplicate file paths
        continue
    seen_hub_paths.add(fp)
    file_docs = doc_by_path.get(fp, [])
    # ... rest unchanged
```

**Expected impact:** Eliminates ~85 lines of duplicated content (11% of output).

---

### Fix 3: Audit Always-Refresh (server.py)
**The Problem:** `codrag_audit scan` serves stale cached findings from disk, even when the analyzer logic has been updated (e.g., `package-lock.json` ignore rule). Agents see findings that no longer exist.  
**The Fix:** Always trigger a fresh audit run on `scan`, never just return stale disk data.

#### [MODIFY] [server.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/mcp/server.py)

Replace the conditional fresh-run logic at lines 1302-1310 with unconditional refresh:

```python
# Phase 73.1: Always run fresh audit — stale results mislead agents
try:
    payload: Dict[str, Any] = {"synthesize": synthesize}
    if category:
        payload["categories"] = [category]
    await self._api_post(f"/projects/{project_id}/audit", payload)

    import asyncio
    for _ in range(30):
        await asyncio.sleep(1)
        status = await self._api_get(f"/projects/{project_id}/audit/status")
        if isinstance(status, dict) and not status.get("running", True):
            break

    data = await self._api_get(f"/projects/{project_id}/audit/findings")
    findings = data.get("findings", []) if isinstance(data, dict) else []
except Exception as e:
    return {"project_id": project_id, "error": f"Audit failed: {e}"}
```

**Expected impact:** Agents always see accurate findings. `package-lock.json` stops appearing as "critical".

---

### Fix 4: Enable Relevance Scores in Search (server.py)
**The Problem:** Search results have `include_scores: False` hardcoded, so agents can't distinguish strong matches from weak ones.  
**The Fix:** Enable scores and add a confidence indicator to the markdown output.

#### [MODIFY] [server.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/mcp/server.py)

Change line 781 from `"include_scores": False` to `"include_scores": True`, and update the markdown assembly at line 820 to include a confidence summary:

```python
# Line 781:
"include_scores": True,

# Lines 820-823 (replace):
if context_str:
    # Phase 73.1: Add retrieval confidence indicator
    sources = data.get("sources", []) if isinstance(data, dict) else []
    if sources:
        scores = [s.get("score", 0) for s in sources if isinstance(s, dict)]
        if scores:
            avg_score = sum(scores) / len(scores)
            confidence = "high" if avg_score > 0.7 else "medium" if avg_score > 0.4 else "low"
            confidence_line = f"[retrieval confidence: {confidence} | top score: {max(scores):.2f} | {len(scores)} chunks]\n"
            context_str = confidence_line + context_str
    result["_to_markdown"] = subsystem_hint + context_str if subsystem_hint else context_str
else:
    result["_to_markdown"] = f"No results found for: {query}"
```

**Expected impact:** Agents can now calibrate trust. A "low confidence" signal tells them to reformulate or use `codrag_impact` instead.

---

### Fix 5: Improve Module Naming Prompt (cluster.py)
**The Problem:** The LLM generates generic names like "UI Subsystem" for many modules, causing confusion in the module list.  
**The Fix:** Add explicit naming constraints to the synthesis prompt.

#### [MODIFY] [cluster.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/cluster.py)

Update `MODULE_SYNTHESIS_PROMPT` (line 113) to add naming guidance:

```python
MODULE_SYNTHESIS_PROMPT = """Synthesize a module-level understanding of this subsystem cluster.

Cluster name: {cluster_name}
Domain tags: {domain_tags}
File count: {file_count}

Member files and their enriched summaries:
{member_summaries}

Inter-cluster dependencies (files outside this cluster that members reference):
{external_deps}

Respond with this exact JSON format:
{{"name": "human-readable subsystem name",
"summary": "2-4 sentence description of what this subsystem does, its role in the codebase, and its current state",
"component_status": "complete|partial|stubbed|deprecated",
"data_flow": "brief description of how data flows through this subsystem",
"dependencies": ["other-subsystem-1", "other-subsystem-2"],
"tech_debt_summary": "brief summary of tech debt across the subsystem, or null if none"}}

NAMING RULES for "name":
- Must be SPECIFIC and DESCRIPTIVE. Bad: "UI Subsystem", "Config Module". Good: "Dashboard State Management", "LLM Concurrency Scheduler".
- For clusters with 1-3 files, derive the name from the most prominent file's purpose.
- Never use the word "Subsystem" alone as a name — always pair it with a specific domain.

Where component_status describes the overall implementation completeness of this subsystem.

JSON response:"""
```

> [!NOTE]
> This prompt change only affects *future* module synthesis runs. Existing module names in `trace_modules.jsonl` won't change until the next enrichment pipeline run. To see the effect immediately, you'd need to re-run the cluster stage.

---

## Open Questions

> [!IMPORTANT]
> **Fix 3 behavior choice:** Should `codrag_audit scan` always refresh (my recommendation), or should we add an explicit `force_refresh` boolean parameter? Always-refresh is simpler and correct for AI agents (they always want fresh data), but adds ~1-2s latency.

---

## Verification Plan

### Automated Tests
1. Restart dev server after changes: `scripts/dev.sh`
2. Call `codrag` and verify:
   - Module list is ≤ 30 lines (not 600+)
   - No duplicated hub content blocks
3. Call `codrag_search query="orchestrator"` and verify:
   - Output includes `[retrieval confidence: ...]` line
   - Scores are visible in the response
4. Call `codrag_audit action="scan"` and verify:
   - `package-lock.json` no longer appears as a "critical" finding
   - Results are fresh (check `generated_at` timestamp)

### Manual Verification
- Compare before/after token counts for `codrag` overview output
- Target: < 200 lines with > 60% useful signal (up from 745 lines at 13%)

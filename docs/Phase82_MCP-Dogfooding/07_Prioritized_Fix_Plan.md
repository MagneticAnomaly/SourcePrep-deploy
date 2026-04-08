# 07 — Prioritized Fix Plan

Fixes ranked by **impact × effort** — highest-value, lowest-effort first.

---

## Tier 1: Quick Wins (1-2 hours each, high impact)

### FIX-1: Format `codrag_impact` direction="all" as markdown
**Impact:** High — eliminates the worst UX inconsistency
**Effort:** Low — the markdown formatter already exists in `tool_impact`
**Files to change:**
- `src/codrag/mcp/server.py:3203-3246` — change dispatcher to use `tool_impact` formatting for all directions, or add `_to_markdown` to `tool_trace_neighbors` (lines 1365-1413)

**Implementation sketch:**
```python
# In tool_trace_neighbors, add markdown formatting:
lines = [f"## Trace Neighbors: {center_name}", ""]
for node in nodes:
    if not node.get("metadata", {}).get("external"):
        lines.append(f"- **{node['name']}** (`{node['file_path']}`) [{node['kind']}]")
result["_to_markdown"] = "\n".join(lines)
```

---

### FIX-2: Filter stdlib/external nodes from impact results
**Impact:** High — removes 75% noise from dependency analysis
**Effort:** Low — filter on existing `metadata.external` flag
**Files to change:**
- `src/codrag/mcp/server.py:1480-1511` (tool_impact)
- `src/codrag/mcp/server.py:1401-1413` (tool_trace_neighbors)

**Implementation sketch:**
```python
# Filter external nodes
internal_nodes = [n for n in nodes if not n.get("metadata", {}).get("external")]
# Summarize externals
ext_count = len(nodes) - len(internal_nodes)
if ext_count:
    lines.append(f"\n*Plus {ext_count} external/stdlib imports (filtered)*")
```

---

### FIX-3: Add code context to symbol search results
**Impact:** High — makes symbol search actually useful
**Effort:** Low — data exists in trace node metadata, just needs surfacing
**Files to change:**
- `src/codrag/mcp/server.py:1335-1352` — expand node field extraction and markdown template

**Implementation sketch:**
```python
# In tool_trace_search, extract more fields:
for node in results:
    meta = node.get("metadata", {})
    qualname = meta.get("qualname", node["name"])
    docstring = (meta.get("docstring") or "")[:200]
    line = node.get("line", "?")
    # Format with more context:
    md_lines.append(f"- `{qualname}` ({node['kind']}) @ `{node['path']}:{line}`")
    if docstring:
        md_lines.append(f"  {docstring}")
```

---

### FIX-4: Exclude lock files and log files from critical audit findings
**Impact:** Medium — reduces critical count from 32 to ~25, improves signal
**Effort:** Low — verify/fix existing exclusion logic
**Files to change:**
- `src/codrag/core/audit/analyzers/large_files.py:62-71` — verify EXPECTED_LARGE_BASENAMES filter is applied
- Add patterns: `logs/*.json`, `*.log`, nested `package-lock.json`

**Implementation sketch:**
```python
# Expand exclusion to match nested lock files and log directories
EXPECTED_LARGE_BASENAMES = {
    "package-lock.json", "yarn.lock", "Cargo.lock", "pnpm-lock.yaml",
    "composer.lock", "Gemfile.lock", "poetry.lock",
}
EXCLUDED_DIRS = {"logs", "node_modules", ".git", "vendor"}
# Also exclude by directory:
if any(part in EXCLUDED_DIRS for part in path.parts):
    return  # skip entirely
```

---

## Tier 2: Medium Effort (half-day each, high impact)

### FIX-5: Deduplicate audit bottleneck findings by file
**Impact:** High — reduces noise significantly, makes critical count meaningful
**Effort:** Medium — requires a post-processing dedup step in the MCP handler
**Files to change:**
- `src/codrag/mcp/server.py:1754-1841` — add dedup pass in tool_audit
- Or: `src/codrag/core/audit/analyzers/misplaced_imports.py:82-105` — group by bottleneck file

**Implementation sketch:**
```python
# In tool_audit, after collecting findings:
bottleneck_groups = defaultdict(list)
for f in findings:
    if "bottleneck" in f.get("tags", []):
        key = f["files"][0]  # the bottleneck file
        bottleneck_groups[key].append(f)
    else:
        ungrouped.append(f)

for file, group in bottleneck_groups.items():
    modules = [f["description"].split("imported by ")[-1] for f in group]
    merged = group[0].copy()
    merged["description"] = f"Bottleneck: {file} imported by {len(modules)} modules: {', '.join(modules)}"
    ungrouped.append(merged)
```

---

### FIX-6: Fix role-based atlas projection for intern/beginner roles
**Impact:** Medium — role atlas is a differentiating feature but currently misleading
**Effort:** Medium — requires tuning TAG_TO_AUDIENCE weights and adding negative signals
**Files to change:**
- `src/codrag/core/atlas/role_projection.py:192` — adjust TAG_TO_AUDIENCE for intern
- `src/codrag/core/atlas/role_projection.py:297-355` — add negative weight for `.d.ts` files
- `src/codrag/core/atlas/role_resolver.py:389-399` — review intern modifier values

**Key changes:**
1. Add a negative signal for type declaration files (`.d.ts`, `.d.mts`) in `compute_role_relevance()`
2. For intern role, boost README files, getting-started docs, and entry-point files
3. Reduce weight of "ui" → "intern" mapping — interns benefit from docs, not component source

---

### FIX-7: Add cross-tool "Next Steps" suggestions
**Impact:** Medium — transforms isolated tools into a guided workflow
**Effort:** Medium — each tool handler needs a few lines of suggestion logic
**Files to change:**
- `src/codrag/mcp/server.py` — all tool handlers

**Implementation sketch:**
```python
# At end of tool_audit response:
tips = []
for f in top_findings:
    if f["severity"] == "critical" and "bottleneck" in f.get("tags", []):
        tips.append(f"→ codrag_impact(file_path='{f['files'][0]}') for blast radius")
    if f["category"] == "circular_dependency":
        tips.append(f"→ codrag_search(query='{f['files'][0]} {f['files'][1]}') for context")
if tips:
    result["_to_markdown"] += "\n\n## Suggested Next Steps\n" + "\n".join(tips)
```

---

## Tier 3: Larger Efforts (1-2 days each, strategic impact)

### FIX-8: Add `detail` parameter for progressive disclosure
**Impact:** High (strategic) — reduces token waste across all tools
**Effort:** High — requires modifying all 5 tool schemas and handlers
**Files to change:**
- `src/codrag/mcp_tools.py` — add `detail` parameter to all tool schemas
- `src/codrag/mcp/server.py` — all tool handlers to respect detail level
- MCP description updates

### FIX-9: Add staleness indicator to all responses
**Impact:** Medium (trust) — prevents agents from acting on stale data
**Effort:** Medium — watcher already tracks change events; need to surface in MCP
**Files to change:**
- `src/codrag/mcp/server.py` — add freshness check to response envelope
- `src/codrag/core/watcher.py` — expose last-build timestamp and pending-changes count

### FIX-10: Improve hub file selection to prefer code over docs
**Impact:** Medium — affects default `codrag` orientation quality
**Effort:** Medium-High — requires changing the hub scoring algorithm
**Files to change:**
- `src/codrag/core/atlas/generator.py` — hub file selection logic
- May need edge-type weighting (code imports > doc references)

### FIX-11: Clarify observe vs concepts boundary
**Impact:** Low-Medium — reduces user confusion
**Effort:** Low (docs) or High (merge tools)
**Options:**
1. **Low effort:** Update tool descriptions to clearly differentiate use cases
2. **High effort:** Merge into a single tool with a `durability` parameter

---

## Summary Matrix

| Fix | Impact | Effort | Priority |
|-----|--------|--------|----------|
| FIX-1: Impact markdown formatting | High | Low | **P0** |
| FIX-2: Filter stdlib from impact | High | Low | **P0** |
| FIX-3: Symbol search code context | High | Low | **P0** |
| FIX-4: Exclude lock files from audit | Medium | Low | **P1** |
| FIX-5: Dedup audit bottleneck findings | High | Medium | **P1** |
| FIX-6: Fix intern role projection | Medium | Medium | **P1** |
| FIX-7: Cross-tool "Next Steps" | Medium | Medium | **P2** |
| FIX-8: Progressive disclosure (`detail`) | High | High | **P2** |
| FIX-9: Staleness indicator | Medium | Medium | **P2** |
| FIX-10: Hub file code preference | Medium | Medium-High | **P2** |
| FIX-11: Observe/concepts boundary | Low-Medium | Low-High | **P3** |

**Recommended sprint:** FIX-1 through FIX-4 (the four P0/quick-win items) in a single session. These are all isolated changes in the MCP handler layer with no cross-dependencies.

# 03 — `codrag_impact` Tool (Dependency Analysis)

**Grade: C+**
**Calls tested:** 2 (server.py direction="all", mcp_tools.py direction="dependents")

## What Works Well

### Direct vs transitive dependent split is valuable
For `mcp_tools.py`, the tool correctly separated 14 direct dependents from 9 transitive dependents. This distinction helps agents understand blast radius: "if I change the tool schemas, what breaks directly vs what might break downstream?"

### Cross-file-type dependency tracking
The `mcp_tools.py` impact analysis found dependents across `.py`, `.md`, and plan files. Knowing that CLAUDE.md references `mcp_tools.py` is genuinely useful — it means changing tool schemas should also update documentation.

---

## Issues Found

### ISSUE 1: Raw JSON output breaks agent UX (HIGH)

**Test:** `codrag_impact(file_path="src/codrag/mcp/server.py", direction="all")`
**Expected:** Markdown-formatted summary like other tools provide.
**Got:** A raw JSON object with `nodes` array (16 items), `edges` array (15 items), each with nested `id`, `kind`, `metadata` fields.

Every other CoDRAG tool returns human-readable markdown. `codrag_impact` returns structured JSON that an agent must mentally parse. This is the most jarring inconsistency across the tool suite.

**Root cause:** `src/codrag/mcp/server.py`

The tool has **two code paths** with different formatting:
- `tool_impact` (lines 1438-1511): Returns markdown via `_to_markdown` with "Direct dependents" and "Transitive dependents" sections. This is the good path.
- `tool_trace_neighbors` (lines 1365-1413): Returns raw JSON with node/edge arrays. **No `_to_markdown` field.** This is the bad path.

The dispatcher (lines 3203-3246) routes to `tool_trace_neighbors` when `direction="all"` or `direction="dependencies"` (lines 3212, 3224), but routes to `tool_impact` for the default `direction="dependents"` (line 3232). So the default case looks fine, but the other two directions return raw JSON.

**Evidence:** My `mcp_tools.py` call used `direction="dependents"` (default) and got nice markdown. My `server.py` call used `direction="all"` and got raw JSON. Same tool, wildly different output format.

**Suggested fix:**
1. Apply the same markdown formatter from `tool_impact` to `tool_trace_neighbors` output
2. Or: make all directions route through `tool_impact` with appropriate filtering
3. At minimum, add a `_to_markdown` field to `tool_trace_neighbors` that formats nodes and edges into a readable summary

**Code pointers:**
- `src/codrag/mcp/server.py:3203-3246` — dispatcher routing logic
- `src/codrag/mcp/server.py:1438-1511` — tool_impact (markdown output)
- `src/codrag/mcp/server.py:1365-1413` — tool_trace_neighbors (raw JSON output)

---

### ISSUE 2: Stdlib imports dominate the graph for direction="all" (HIGH)

**Test:** `codrag_impact(file_path="src/codrag/mcp/server.py", direction="all")`
**Result:** 16 nodes total. 12 are external/stdlib modules: `json`, `os`, `re`, `logging`, `sys`, `uuid`, `asyncio`, `httpx`, `Optional`, `Path`, `RotatingFileHandler`.

Only 4 of 16 nodes are project-internal files:
- `src/codrag/mcp/__init__.py`
- `src/codrag/mcp_server.py`
- `src/codrag/mcp/errors.py`
- `src/codrag/mcp/server.py` (self)

**Impact:** 75% of the response is noise. An agent asking "what breaks if I change server.py?" doesn't care that it imports `json`. The useful signal (3 internal dependents) is buried.

**Root cause:** Neither `tool_impact` nor `tool_trace_neighbors` filters external/stdlib nodes. The backend API returns everything, and the MCP handler passes it through unfiltered.

**Suggested fix:**
1. Filter nodes where `metadata.external == true` by default
2. Or: move external nodes to a separate "External dependencies" section that's collapsed/summarized ("Imports 12 stdlib/external modules")
3. Add an `include_external=false` parameter (default false) for the rare case when someone wants to see stdlib deps

**Code pointers:**
- `src/codrag/mcp/server.py:1480-1511` — tool_impact processes all dependents without filtering
- `src/codrag/mcp/server.py:1401-1413` — tool_trace_neighbors returns all nodes/edges
- Node metadata includes `"external": true` flag — the data is there, just not used

---

### ISSUE 3: Missing internal code dependencies for server.py (MEDIUM)

**Test:** `codrag_impact(file_path="src/codrag/mcp/server.py", direction="all")`
**Expected:** server.py imports from `codrag.mcp_tools` (TOOLS), `codrag.core.*`, `codrag.api.*`, etc.
**Got:** Only `TOOLS` (as ext:TOOLS, not even linked to `mcp_tools.py`) and `errors.py` as internal dependencies.

`server.py` is a 2251-line file that certainly imports more than 2 internal modules. The trace graph appears to be missing many edges. The `TOOLS` import from `codrag.mcp_tools` is classified as `ext:TOOLS` (external) instead of being linked to the actual `mcp_tools.py` file — suggesting the import resolver failed to trace `from codrag.mcp_tools import TOOLS` to its source file.

**Root cause:** Likely in the Rust parser or the edge inference stage. The import `from codrag.mcp_tools import TOOLS` may not be resolved because the parser doesn't handle relative-to-package imports, or the `mcp_tools` module isn't in the file discovery scope.

**Suggested fix:**
1. Verify that `src/codrag/mcp_tools.py` is indexed and its `TOOLS` export is a trace node
2. Check if the Rust parser resolves `from codrag.mcp_tools import TOOLS` to the correct file
3. Run a coverage check: for each import in `server.py`, confirm the trace graph has a corresponding edge

---

### ISSUE 4: mcp_tools.py dependents are almost all docs (LOW)

**Test:** `codrag_impact(file_path="src/codrag/mcp_tools.py", direction="dependents")`
**Result:** 14 direct dependents — ALL are `.md` files with `[references]` edge type. Zero code imports.

This is technically correct (those docs do reference `mcp_tools.py`), but it's low-value for the primary use case: "what code breaks if I change this file?" A doc referencing a file by name doesn't "break" when the file changes.

**Suggested fix:**
1. Split dependents into "Code dependents" (imports) and "Documentation references" (references) in the output
2. Prioritize code dependents in the summary
3. Add a `code_only=true` parameter that filters to import edges only

---

## Opportunities

### OPPORTUNITY 1: Show the actual import chain
Instead of just listing dependent files, show *what* each dependent imports:
```
src/codrag/mcp/__init__.py imports: configure_logging (line 7)
src/codrag/mcp_server.py imports: codrag.mcp.server (line 37)
```
This is already in the edge metadata (`import`, `line` fields) — it just needs to be surfaced in the markdown output.

### OPPORTUNITY 2: Risk-weighted impact scoring
Not all dependents are equal. A file that imports 5 symbols from the target is more at risk than one that imports 1. Weight dependents by import count or by whether the imported symbols are in the changed region.

### OPPORTUNITY 3: "What if I change function X?" — symbol-level impact
Currently impact works at file granularity. Being able to ask "what calls `handle_tools_list`?" without scanning the whole file would be more precise. The trace graph has symbol-level nodes — expose them through impact analysis.

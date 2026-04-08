# 01 — `codrag` Tool (Structural Overview)

**Grade: B+**
**Calls tested:** 2 (default, role="intern")

## What Works Well

### Module summaries are genuinely useful
The Pipeline Orchestration Engine and LLM Orchestration Engine summaries give immediate orientation. The 11-stage pipeline diagram (Fast Sync vs Deep Enrichment) is exactly what a new agent needs. This content alone saves 10+ minutes of `grep` + `Read` exploration.

### Hub file excerpts provide real context
The Phase 62 epistemology and adapter architecture excerpts give architectural intent — why CoDRAG exists and how it's designed. This is information you cannot get from code alone.

### The pipeline stage table is excellent
```
Stage 1:  File Discovery (scan repo)
...
Stage 11: Finalization (manifest, cleanup)
```
This is the kind of structural overview that makes `codrag` more valuable than a README.

---

## Issues Found

### ISSUE 1: Role-based atlas projection returns irrelevant content (HIGH)

**Test:** `codrag(role="intern")`
**Expected:** Beginner-friendly orientation — entry points, README, getting started docs, simple components.
**Got:** Storybook `.d.ts` declaration files (CitationBlock.stories.d.ts, CopyButton.stories.d.ts, SiteFooter.stories.d.ts).

**Root cause:** `src/codrag/core/atlas/role_projection.py`

The `TAG_TO_AUDIENCE` mapping (line 192) includes `"intern"` in the `"ui"` audience. When `.d.ts` files are tagged with `"ui"`, `"documentation"`, `"component-testing"`, or `"storybook"` (inferred from path patterns), the `_compute_audience_bonus()` function (lines 263-281) awards bonus score to interns. Combined with the intern detail_level boost (+0.2, in `role_resolver.py` lines 389-399) and the 1.3x max_chars multiplier, `.d.ts` type definition files bubble to the top.

**The real problem:** The scoring function treats "documentation" as universally good for interns, but `.d.ts` files are TypeScript compiler artifacts, not human-readable docs. The tag inference system doesn't distinguish "documentation about code" from "type declaration files that happen to live near docs."

**Suggested fix:**
1. Add a negative signal for `.d.ts` files in `compute_role_relevance()` — they are never useful for human consumption
2. Weight the `"ui"` → `"intern"` audience mapping lower, or scope it to actual component files (`.tsx`, `.jsx`), not type stubs
3. Consider an explicit "getting started" tag or a curated intern-friendly file list rather than relying on generic tag matching

**Code pointers:**
- `src/codrag/core/atlas/role_projection.py:192` — TAG_TO_AUDIENCE mapping
- `src/codrag/core/atlas/role_projection.py:263-281` — audience bonus calculation
- `src/codrag/core/atlas/role_projection.py:297-355` — compute_role_relevance scoring
- `src/codrag/core/atlas/role_projection.py:759-815` — _assemble_practitioner output
- `src/codrag/core/atlas/role_resolver.py:389-399` — intern-specific modifiers

---

### ISSUE 2: Hub file selection favors docs over code (MEDIUM)

**Observation:** Both hub file excerpts in the default `codrag` call are Phase 62 research documents, not actual code files. For an AI coding agent, the most useful hub files would be:
- `src/codrag/mcp/server.py` (2251 lines, MCP tool handlers)
- `src/codrag/services/pipeline/orchestrator.py` (2459 lines, pipeline engine)
- `src/codrag/core/index.py` (1843 lines, core index)
- `src/codrag/mcp_tools.py` (tool schemas)

These are the files with the highest in-degree from actual code imports, but the hub selection appears to use a broader "in-degree" metric that counts doc references equally with code imports.

**Root cause:** Hub file selection in the atlas generator (`src/codrag/core/atlas/generator.py`) likely treats all edge types (imports, references, semantic links) equally. Research docs that are referenced by many other docs score high on in-degree but provide no coding value for the default (agent) use case.

**Suggested fix:**
1. Weight code import edges higher than doc reference edges when selecting hub files for the default (no-role) view
2. Or: separate "code hubs" from "knowledge hubs" in the output, showing both but labeling them differently
3. Or: use the `role` mechanism — the default (no-role) call should behave like `role="engineer"`, not `role="researcher"`

---

### ISSUE 3: No deduplication across repeated calls (LOW)

**Observation:** Calling `codrag` twice in the same session returns nearly identical content. The CLAUDE.md recommends re-calling after 5+ tool calls, but the tool doesn't know what it already returned.

**Impact:** In a long session, the agent wastes ~3-4K tokens getting the same module summaries and hub excerpts it already has.

**Suggested fix:**
- This is a protocol-level issue — MCP doesn't have session state. A pragmatic fix would be to accept a `refresh=true` parameter that only returns *changed* modules (files modified since last call) or *different* hub excerpts.
- Alternatively, document that agents should NOT re-call `codrag` unless the codebase has changed, and instead use `codrag_search` for targeted lookups mid-task.

---

## Opportunities

### OPPORTUNITY 1: Add a "quick" mode
The default `codrag` response is ~4K tokens. For quick orientation, a 1K token summary (just module names + file counts + top 3 hub files by name) would be valuable. The full response is great for task start; the quick version would be better for mid-task refreshes.

### OPPORTUNITY 2: Include working_dir context in default call
The `codrag_search` tool supports `working_dir` for scoped results. The `codrag` tool doesn't. If I'm working in `src/codrag/mcp/`, the overview should emphasize the MCP module, not the pipeline orchestrator.

### OPPORTUNITY 3: Surface focus areas more prominently
The CLAUDE.md lists focus areas but the `codrag` tool response doesn't surface them. If the user has flagged specific files as focus areas, those should appear in the structural overview — they represent explicit user intent about what matters.

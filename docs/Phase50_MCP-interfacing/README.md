# Phase 50: MCP Interfacing -- Deep Research

> How CoDRAG's MCP server interfaces with AI coding tools, why the AI doesn't always call it, and what we can do to make it the always-on structural brain for every prompt.

---

## 1. The Core Problem

**Vision:** Every prompt to Cursor/Windsurf/Claude should have instant (<100ms) epistemological understanding of the codebase -- the trace graph, module structure, hub files, and knowledge base files -- in the most compact context window possible.

**Reality:** The AI tool decides *if and when* to call CoDRAG MCP tools. It often doesn't. The user has to say "use codrag" or the AI has to independently decide CoDRAG is relevant. Knowledge base files that the user selected in the dashboard may never reach the AI's context unless the AI happens to call `codrag`.

This is a **protocol-level constraint**, not a bug. Understanding it is the key to solving it.

---

## 2. How MCP Actually Works (Protocol Spec 2025-06-18)

The MCP protocol defines three server-side primitives:

| Primitive | Who Controls It | How It Works |
|-----------|----------------|--------------|
| **Tools** | The AI model | AI sees tool descriptions in its system prompt, decides when to call them. Requires a tool-call turn. |
| **Resources** | The host application | Host (Cursor/Windsurf) reads resources and can inject them into context. AI does NOT control this. |
| **Prompts** | The user | Pre-built templates the user explicitly triggers (like slash commands). |

### What CoDRAG currently exposes: **Tools only.**

We have 15 tools (`codrag`, `codrag_search`, `codrag_status`, `codrag_build`, `codrag_trace_search`, `codrag_trace_neighbors`, `codrag_trace_coverage`, `codrag_impact`, `codrag_save_observation`, `codrag_get_observations`, `codrag_audit`, `codrag_audit_refactor`, `codrag_audit_check`, `codrag_audit_report`, `hi_codrag`).

**We expose zero Resources. Zero Prompts.**

This is the root cause. Tools are model-controlled -- the AI has to *decide* to call them. Resources are application-controlled -- the host can inject them automatically.

---

## 3. How Cursor Consumes MCP

Source: https://cursor.com/docs/context/mcp

### What Cursor supports
- **Tools** -- Supported. Agent automatically uses MCP tools listed under "Available Tools" when relevant. Includes Plan Mode.
- **Resources** -- Supported. Structured data sources that can be read and referenced.
- **Prompts** -- Supported. Templated messages and workflows for users.
- **Roots** -- Supported. Server-initiated inquiries into URI or filesystem boundaries.
- **Elicitation** -- Supported. Server-initiated requests for additional information from users.
- **Apps** -- Supported. Interactive UI views returned by MCP tools.

### When Cursor calls MCP tools
- Agent mode: Automatically, based on tool descriptions and user query relevance.
- Tool approval: Required by default. Can be set to auto-run (like terminal commands).
- The AI model sees ALL available tool descriptions in its system prompt and decides which to invoke.

### The "15 tools" problem
Every tool description consumes system prompt tokens. With 15 CoDRAG tools plus Cursor's own built-in tools (read_file, grep_search, run_command, edit, etc.), the AI has 30+ tools to choose from. **CoDRAG tools are competing with native tools the AI already trusts and knows.**

The AI will prefer `read_file` (which it knows works) over `codrag_search` (which is an unknown MCP tool) unless the description is extremely compelling or the user explicitly requests it.

### Cursor Rules (.cursorrules / .cursor/rules)
Cursor supports project-level rule files that get injected into the system prompt. This is a **critical** mechanism -- we can instruct the AI to always call `codrag` at the start of every conversation.

---

## 4. How Windsurf/Cascade Consumes MCP

Source: https://docs.windsurf.com/windsurf/cascade/mcp

### Key behaviors
- Cascade has built-in tools (Search, Analyze, Web Search, terminal, file editing).
- MCP tools are additional capabilities that Cascade can invoke.
- MCP tool calls require user approval (can be auto-approved via settings).
- Cascade detects which tools are relevant and invokes them based on context.

### Same fundamental constraint
Like Cursor, Cascade decides *when* to call MCP tools. If the AI doesn't think CoDRAG is relevant to the current prompt, it won't call it.

### Windsurf-specific: User Rules & Memories
Windsurf supports user rules (global) and workspace rules that get injected into the system prompt. These can instruct the AI to call CoDRAG tools. Additionally, Windsurf's memory system (retrieved memories) can remind the AI about CoDRAG.

---

## 5. Current CoDRAG MCP Architecture (What Gets Returned)

### `codrag` (ambient context tool)
- Calls `POST /projects/{id}/context` with empty query
- Returns: module summaries, hub files (full content, LOD 0), neighbor files (LOD 2 signatures)
- Budget: 70% hubs, 30% neighbors, within `max_chars` (default 12000)
- Includes: `included_paths` from project config (knowledge base files)
- Latency: Requires HTTP round-trip to daemon (localhost:8400) -- typically 10-50ms

### `codrag_search` (query-based context)
- Calls `POST /projects/{id}/context` with query
- Pipeline: query preprocessing -> scope boost (included_paths) -> atlas routing -> knowledge routing -> embedding search -> trace expansion -> LOD compression -> observation injection
- Returns: LOD-compressed code context with structural trace expansion

### `hi_codrag` (discovery tool)
- Parallel fetches: status, included_paths, path_weights, coverage, projects, hub_files
- Returns: conversational markdown summary + file inventory + diagnostics + suggested prompts
- **Heavy**: 7 parallel API calls, topic detection, doc previews, file categorization

### Response format
All tool responses are serialized as `json.dumps(result, indent=2)` wrapped in MCP `content[{type: "text", text: ...}]`. This means the AI sees a JSON blob, not clean prose.

---

## 6. Gap Analysis: What's Missing

### GAP-1: No MCP Resources
**CORRECTED (from deeper research):** Resources are NOT auto-injected by the host. Per Cursor docs: *"The model determines when it needs additional context, then requests specific resources."* Resources are more like a cached read-only data API -- cheaper than a tool call (no approval needed) but the AI still has to decide to read them.

This means Resources are a **secondary optimization**, not the primary always-on mechanism. The rules file (`alwaysApply: true`) is the real solution for always-on context.

CoDRAG should expose lightweight Resources (<500 tokens each):
- `codrag://structure` -- Module map + hub files + connectivity (~500 tok)
- `codrag://atlas` -- Architectural overview (~400 tok)
- `codrag://files` -- Selected KB file list + previews (~300 tok)
- `codrag://health` -- Index freshness, coverage %, build status (~100 tok)

See PLAN.md GAP-1 for full implementation strategy and risk assessment.

### GAP-2: No MCP Prompts
Prompts are user-triggered templates. We could expose:
- `codrag://prompts/analyze` -- "Analyze this codebase using CoDRAG's trace graph"
- `codrag://prompts/review` -- "Review this code using CoDRAG's structural understanding"

These would appear as slash commands in the IDE.

### GAP-3: Tool description doesn't say "call me always"
The `codrag` tool description says: *"Get ambient codebase context -- the primary CoDRAG tool."* This is passive. It doesn't tell the AI: "You should call this tool at the beginning of every task to get structural understanding of the codebase."

Compare with how Windsurf's own `code_search` tool is described in its system prompt: it tells the AI *"you should always use this tool to start your search."*

### GAP-4: Too many tools dilute attention
15 tools is too many. The AI's system prompt has finite space. Every CoDRAG tool description that's NOT `codrag` or `codrag_search` is stealing attention from those two primary tools.

### GAP-5: Knowledge base files aren't surfaced like "dragged files"
When a user drags a file into Windsurf's Cascade window, the file content is injected directly into the conversation context. When a user selects files in CoDRAG's dashboard Knowledge Base panel, those files are only accessible if the AI calls `codrag` (ambient context), and even then they're mediated through the hub/neighbor LOD pipeline rather than passed as direct file content.

### GAP-6: Response format is JSON, not optimized for AI consumption
The MCP response is `json.dumps(result, indent=2)`. The AI has to parse a JSON blob to extract the context. If the response were clean markdown or a structured text block, the AI could use it more effectively.

### GAP-7: No rules file auto-generation (.cursor/rules/, .windsurf/rules/, CLAUDE.md, etc.)
We could generate a project-level rules file that instructs the AI to call CoDRAG automatically. This is the most reliable way to ensure CoDRAG gets called on every prompt.

---

## 7. How Native File Inclusion Works (for comparison)

### Windsurf: @-mentions and drag-drop
When a user drags `src/auth/login.py` into the Cascade window:
1. Windsurf reads the file content directly from disk
2. The full file content is injected into the conversation as a user message attachment
3. The AI sees `[File: src/auth/login.py]` with the full source code
4. No MCP call needed -- it's a host-level operation

### Cursor: @-mentions
When a user types `@src/auth/login.py`:
1. Cursor reads the file and injects it into context
2. Similar direct injection -- no MCP involved

### What CoDRAG's knowledge base selection needs to feel like
When a user selects files in CoDRAG's dashboard, the AI should see those files with the SAME immediacy as drag-drop. The difference: CoDRAG adds structural context (trace graph connections, module membership, hub status) on top of the raw file content.

---

## 8. Recommendations

### R-1: Expose MCP Resources (HIGH PRIORITY)
Implement `resources/list` and `resources/read` in the MCP server. Expose:

```
codrag://project/atlas       -- Compact atlas (500 chars)
codrag://project/modules     -- Module summaries (LOD 5)
codrag://project/structure   -- Hub files + connectivity map
codrag://project/files       -- Selected knowledge base files (included_paths)
```

The `structure` resource should be the always-on epistemological summary: which files are most connected, which modules exist, what the dependency graph looks like -- all in <2000 tokens.

**Test:** Does Cursor/Windsurf auto-inject resources into context? If yes, this alone solves the "always-on" problem.

### R-2: Generate rules files automatically (HIGH PRIORITY)
When CoDRAG indexes a project, auto-generate rules files (.cursor/rules/codrag.mdc, .windsurf/rules/codrag.md, CLAUDE.md section, AGENTS.md section):

```
# .cursor/rules/codrag.mdrule
---
description: CoDRAG structural context
globs: ["**/*"]
alwaysApply: true
---
You have access to CoDRAG, a structural code intelligence tool.
At the START of every task, call the `codrag` tool (no arguments needed) to get:
- Module structure and connectivity
- Hub files (most important/connected files)
- Selected knowledge base files

For specific code searches, use `codrag_search` with a natural language query.
CoDRAG's trace graph understands imports, calls, and structural relationships
between files -- use this to navigate the codebase structurally, not just textually.
```

This gets injected into the AI's system prompt on every turn. It costs ~100 tokens but guarantees the AI knows about and uses CoDRAG.

### R-3: Consolidate tools (MEDIUM PRIORITY)
Reduce from 15 to 5-7 tools:

| Keep | Merge Into | Remove |
|------|-----------|--------|
| `codrag` (ambient) | -- | -- |
| `codrag_search` (query) | -- | -- |
| `codrag_trace` (merged) | `codrag_trace_search` + `codrag_trace_neighbors` + `codrag_trace_coverage` | Individual trace tools |
| `codrag_impact` | -- | -- |
| `codrag_audit` (merged) | `codrag_audit` + `codrag_audit_refactor` + `codrag_audit_check` + `codrag_audit_report` | Individual audit tools |
| `codrag_observe` (merged) | `codrag_save_observation` + `codrag_get_observations` | Individual observation tools |
| -- | -- | `codrag_status`, `codrag_build`, `codrag_context` (alias), `hi_codrag` |

Rationale: `codrag_status` and `codrag_build` are admin operations that don't need to be in the AI's tool list. `hi_codrag` can be handled by `codrag` with a flag. Fewer tools = the AI pays more attention to each one.

### R-4: Optimize `codrag` response for AI consumption (MEDIUM PRIORITY)
Instead of returning JSON, return a structured text block optimized for LLM consumption:

```
## Codebase: MyProject (547 nodes, 656 edges)

### Modules
- Core Engine (89 files): indexing, search, trace graph, embedding [core, search, embedder]
- API Layer (24 files): REST endpoints, middleware [api, http]
- Dashboard (31 files): React UI, state management [ui, react]

### Hub Files (most connected)
1. src/core/index.py (42 connections) -- search index and context assembly
2. src/core/trace.py (38 connections) -- trace graph loading and querying
3. src/server.py (35 connections) -- main server, route registration

### Selected Files (knowledge base)
- docs/ARCHITECTURE.md -- project architecture overview
- src/core/index.py -- [included, hub, LOD 0]
- src/api/routers/projects/ -- [included, 8 files]

### Recent Changes
- src/core/embedder.py (modified 2h ago, stale)
```

This is ~400 tokens and gives the AI instant structural understanding. Much better than a JSON blob.

### R-5: Include knowledge base files as direct content (MEDIUM PRIORITY)
When the user has selected files in the dashboard (included_paths), the `codrag` ambient response should include those files' content directly -- similar to how drag-drop works in Cursor/Windsurf. The LOD pipeline should still apply (hub files at LOD 0, others at LOD 2-4), but the result should feel like the AI "has" those files.

Currently `_assemble_ambient_context` does this, but the content is behind a tool call. With R-1 (Resources), it could be always-on.

### R-6: Sub-100ms response time budget (HIGH PRIORITY)
The daemon is on localhost. The context assembly pipeline should complete in <100ms:
- Project resolution: cached (0ms after first call)
- Module summaries: read from `trace_modules.jsonl` (disk, ~5ms)
- Hub files: read from trace index (in-memory, ~1ms)
- Ambient assembly: string concatenation (~1ms)
- HTTP overhead: ~10ms localhost

Total: ~20ms realistic. **We're already there for the ambient path.** The bottleneck is the AI deciding to call the tool, not the tool's speed.

### R-7: Explore MCP Prompts for common workflows (LOW PRIORITY)
Expose prompts like:
- `/codrag-analyze` -- Full codebase analysis with audit
- `/codrag-review` -- Review selected files with structural context
- `/codrag-plan` -- Plan a change with impact analysis

These are lower priority because most AI tools handle prompts differently and the UX is inconsistent.

---

## 9. Implementation Priority

| # | Item | Impact | Effort | Notes |
|---|------|--------|--------|-------|
| 1 | R-2: Auto-generate .cursorrules | **Critical** | 2h | Most reliable way to ensure AI calls CoDRAG. Single file write. |
| 2 | R-4: Optimize response format | High | 4h | Makes every CoDRAG call more useful. Text > JSON. |
| 3 | R-1: MCP Resources | High | 8h | Protocol-level always-on context. Needs testing with Cursor/Windsurf. |
| 4 | R-3: Consolidate tools | Medium | 4h | Reduces noise, increases per-tool attention. |
| 5 | R-5: Direct file inclusion | Medium | 4h | Makes KB files feel like native file attachments. |
| 6 | R-6: Response time audit | Low | 2h | Already fast. Verify and document. |
| 7 | R-7: MCP Prompts | Low | 4h | UX varies by host. Nice-to-have. |

---

## 10. The Ideal Flow (Post-Implementation)

### Every prompt in Cursor/Windsurf:
1. **Rules file** tells the AI: "You have CoDRAG. Call `codrag` first."
2. **MCP Resource** `codrag://project/structure` is auto-injected by the host (if supported), giving ~400 tokens of structural overview without a tool call.
3. AI calls `codrag` tool -> gets ambient context in <50ms: module summaries, hub file content, selected knowledge base files -- all in optimized markdown, ~3000 tokens.
4. AI now has epistemological understanding: it knows the modules, the hub files, the structural connections, and the user's focus area.
5. For specific queries, AI calls `codrag_search` with the user's question -> gets LOD-compressed, trace-expanded, atlas-routed context.

### Total context cost: ~3000-4000 tokens per prompt
This is well within the "safe zone" identified in Phase 28 research (4K-16K saturation point). The AI gets maximum structural understanding for minimum context budget.

---

## 11. Open Questions

- **Q1:** How aggressively does Cursor auto-inject MCP Resources? Does it require user @-mention, or does it proactively include them?
- **Q2:** Does Windsurf support MCP Resources at all? (Docs mention tools, prompts, but resources are unclear.)
- **Q3:** Can we detect which IDE is the MCP client and tailor the response format? (Cursor vs. Windsurf vs. Claude Desktop)
- **Q4:** Should the rules file be auto-generated on every build, or a one-time setup?
- **Q5:** How do we handle the case where CoDRAG is being developed inside a CoDRAG-indexed repo (the "meta-project" problem from Phase 34)?

---

## 12. Files Referenced

| File | Role |
|------|------|
| `src/codrag/mcp_tools.py` | Tool definitions (15 tools) |
| `src/codrag/mcp/server.py` | MCP server implementation (1853 lines) |
| `src/codrag/api/routers/projects/search.py` | Context endpoint + ambient assembly |
| `src/codrag/api/routers/projects/models.py` | ContextRequest model |
| `public/codrag-mcp/README.md` | User-facing MCP setup docs |

---

## Appendix A: MCP Protocol Quick Reference

```
Client (Cursor/Windsurf)          Server (CoDRAG)
        |                               |
        |--- initialize --------------->|  (sends roots/workspace URIs)
        |<-- capabilities --------------|  (tools, resources, prompts)
        |                               |
        |--- tools/list --------------->|  (discover available tools)
        |<-- tool definitions ----------|
        |                               |
        |--- resources/list ----------->|  (discover available resources)  [NOT IMPLEMENTED]
        |<-- resource descriptors ------|
        |                               |
        |--- resources/read ----------->|  (fetch resource content)        [NOT IMPLEMENTED]
        |<-- resource data -------------|
        |                               |
        |--- tools/call --------------->|  (AI decides to invoke a tool)
        |<-- tool result ---------------|
```

## Appendix B: Cursor Rules File Format

Cursor supports `.cursor/rules/*.mdrule` files with YAML frontmatter:

```yaml
---
description: Short description of the rule
globs: ["**/*"]         # which files this rule applies to
alwaysApply: true       # inject into every prompt
---
<markdown instructions for the AI>
```

The `alwaysApply: true` flag is the key -- it means the rule content is injected into the AI's system prompt on every turn, regardless of which files are open.

## Appendix C: Windsurf Rules

Windsurf supports global user rules and workspace-level rules files.

**UPDATED:** Rules are now in `.windsurf/rules/*.md` with YAML frontmatter (NOT `.windsurfrules`).
See `DEEP_DIVE.md` Correction #1 for details.

Format is markdown with YAML frontmatter:
```
Always call the `codrag` MCP tool at the start of every task to get
structural codebase context before making changes.
```

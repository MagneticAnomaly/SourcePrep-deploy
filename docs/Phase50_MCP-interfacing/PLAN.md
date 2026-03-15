# Phase 50: MCP Interfacing -- Implementation Plan

> Concrete implementation plan for making CoDRAG the always-on structural brain for AI coding tools.

---

## 1. Tool Audit: Every Tool, Scored

### Methodology
Each tool scored on 4 dimensions (1-5 scale):
- **Frequency**: How often would an AI realistically call this per session?
- **Value**: How much does this improve the AI's output when called?
- **Uniqueness**: Does this do something the AI can't do with native tools?
- **Token cost**: How many tokens does the tool definition consume? (lower = better)

### The 16 Tools, Ranked

```
TOOL                     FREQ  VALUE  UNIQUE  TOKENS  VERDICT
-----------------------------------------------------------------
codrag                      5     5      5     241    KEEP (primary)
codrag_search               5     5      5     481    KEEP (primary)
codrag_impact               3     5      5     264    KEEP (high value)
codrag_trace_search         3     4      4     243    CONSOLIDATE -> codrag_search
codrag_trace_neighbors      2     4      4     286    CONSOLIDATE -> codrag_search
codrag_audit                2     5      5     236    CONSOLIDATE -> codrag_audit (merged)
codrag_audit_refactor       2     5      5     248    CONSOLIDATE -> codrag_audit (merged)
codrag_audit_check          1     3      3     192    CONSOLIDATE -> codrag_audit (merged)
codrag_audit_report         1     3      3     183    CONSOLIDATE -> codrag_audit (merged)
codrag_save_observation     2     3      4     327    CONSOLIDATE -> codrag_observe
codrag_get_observations     2     3      4     265    CONSOLIDATE -> codrag_observe
codrag_context              1     5      1     239    REMOVE (exact alias of codrag)
hi_codrag                   1     3      2     164    REMOVE (subsume into codrag)
codrag_status               1     2      1      95    REMOVE (admin, not AI workflow)
codrag_build                1     1      1     127    REMOVE (admin, not AI workflow)
codrag_trace_coverage       1     2      2     106    REMOVE (diagnostic, rarely needed)
-----------------------------------------------------------------
CURRENT TOTAL: 16 tools, ~3,697 tokens in system prompt
```

---

## 2. Proposed Tool Set: 4 Tools

### The "Big 4" Design

| # | Tool | Purpose | Tokens (est.) |
|---|------|---------|---------------|
| 1 | `codrag` | Ambient structural context. Always call first. | ~300 |
| 2 | `codrag_search` | Query-based retrieval with trace/symbol/neighbor support. | ~400 |
| 3 | `codrag_impact` | Blast radius analysis before changes. | ~200 |
| 4 | `codrag_audit` | Codebase health audit with refactor guidance. | ~250 |

**Estimated total: ~1,150 tokens** (down from 3,697 -- a 69% reduction)

### What each tool absorbs

**`codrag` (primary -- ambient context)**
- Absorbs: `codrag_context` (alias), `hi_codrag` (greeting mode), `codrag_status` (health info), `codrag_get_observations` (session memory)
- New behavior: Returns structural overview + health status + observations in one call. No separate "hi" needed.
- New param: `mode` = `"ambient"` (default) | `"status"` | `"observations"`
- Actually, the mode param adds complexity. Better: always return the structural overview, and include health/observations as lightweight sections at the end. One call, one shape.

**`codrag_search` (query-based -- the workhorse)**
- Absorbs: `codrag_trace_search` (symbol search), `codrag_trace_neighbors` (graph traversal)
- New behavior: `type` param selects retrieval strategy
  - `type: "context"` (default) -- semantic search + trace expansion + LOD (current codrag_search behavior)
  - `type: "symbol"` -- search trace graph by symbol name (current codrag_trace_search)
  - `type: "neighbors"` -- graph traversal from a node (current codrag_trace_neighbors, requires `node_id`)
- This is the right consolidation because all three are "search for something" operations. The AI can naturally express "search for the UserService class" (symbol) vs "what code handles authentication" (context) vs "what depends on this node" (neighbors).

**`codrag_impact` (kept as-is)**
- High value, unique functionality, clean interface.
- "What breaks if I change X?" is a distinct mental model from search.
- No changes needed. Already well-designed.

**`codrag_audit` (merged audit suite)**
- Absorbs: `codrag_audit_refactor`, `codrag_audit_check`, `codrag_audit_report`
- New behavior: `action` param selects operation
  - `action: "scan"` (default) -- run audit, return findings
  - `action: "refactor"` -- get findings + trace context for implementation (needs `finding_ids`)
  - `action: "verify"` -- re-run specific analyzers to check fixes (needs `analyzers`)
  - `action: "report"` -- retrieve a named report document (needs `report_name`)
- All four operations share the same conceptual domain (codebase health). Merging them reduces the AI's decision surface from 4 audit tools to 1.

### Tools removed entirely

| Tool | Reason | Alternative |
|------|--------|-------------|
| `codrag_context` | Exact duplicate of `codrag` | Use `codrag` |
| `hi_codrag` | Greeting mode. Overly specialized. | `codrag` returns the same structural info. Rules file tells AI to present it conversationally. |
| `codrag_status` | Admin operation. AI doesn't need daemon health to write code. | Health info included in `codrag` response footer. |
| `codrag_build` | Admin operation. Rebuilding an index is not an AI coding task. | User triggers builds from dashboard. If index is stale, `codrag` response says so. |
| `codrag_trace_coverage` | Diagnostic. Rarely actionable during coding. | Coverage summary included in `codrag` response. |
| `codrag_save_observation` | Important but can be a sub-action of `codrag`. | Add `save_observation` param to `codrag` OR keep as 5th tool if testing shows observations are valuable. |

### Decision point: Observations

`codrag_save_observation` is the one tool I'm uncertain about removing. It's write-oriented (all others are read). Two options:

**Option A: Keep as 5th tool `codrag_observe`**
- Merges save + get into one tool with `action: "save" | "get"`
- 5 tools total instead of 4
- Pro: Clean separation of read vs write
- Con: One more tool description in the system prompt (~250 tokens)

**Option B: Add `observation` param to `codrag`**
- `codrag` accepts optional `save_observation: {content, file_path, category}` object
- When present, saves the observation AND returns normal ambient context
- Pro: Fewer tools
- Con: Overloads the primary tool with a write operation

**Recommendation: Option A** -- 5 tools is still a massive reduction from 16. Keep observations as a dedicated tool because saving notes is a fundamentally different intent than retrieving context.

### Final proposed set: 5 tools, ~1,400 tokens

| # | Tool | ~Tokens |
|---|------|---------|
| 1 | `codrag` | 300 |
| 2 | `codrag_search` | 400 |
| 3 | `codrag_impact` | 200 |
| 4 | `codrag_audit` | 250 |
| 5 | `codrag_observe` | 250 |

**62% token reduction** (3,697 -> ~1,400)

---

## 3. Tool Description Design (Research-Informed)

The arxiv paper (arXiv:2602.14878) identifies 6 quality components for tool descriptions:

1. **Purpose** -- What does the tool do? (56% of MCP tools fail here)
2. **Guidelines** -- When and how to use it? (89.3% lack this!)
3. **Limitations** -- What can't it do?
4. **Parameter Explanation** -- What do inputs mean?
5. **Examples** -- Concrete usage patterns
6. **Length/Completeness** -- Not too long, not too short

The paper finds that **Purpose + Guidelines** alone is the highest-leverage combination. Adding all 6 components can actually *hurt* performance due to token bloat.

### Design principle: Purpose + Guidelines, nothing else in the description

Each tool description should follow this template:
```
[One sentence: what it does]
[When to use: 2-3 bullet-like activation criteria]
[When NOT to use: 1 contrasting tool reference]
```

### Proposed descriptions

**`codrag`**
```
Get structural codebase context -- modules, hub files, and knowledge base content.
Call this FIRST at the start of every task to understand the codebase architecture
before reading or editing files. Returns module summaries, the most-connected files,
and any files the user has selected as focus areas. No arguments needed.
Use codrag_search instead when you need to find something specific.
```
~70 tokens. Clear purpose + activation criteria + disambiguation.

**`codrag_search`**
```
Search for code context using a natural language query, symbol name, or graph traversal.
Use this when you need to find specific code, understand a symbol, or explore
structural relationships. Supports three modes via the 'type' parameter:
'context' (default) for semantic search with structural expansion,
'symbol' for finding functions/classes/modules by name,
'neighbors' for traversing the code graph from a known node.
```
~80 tokens.

**`codrag_impact`**
```
Analyze what depends on a file or symbol -- 'what breaks if I change X?'
Call this BEFORE making changes to understand the blast radius.
Returns direct and transitive dependents from the code graph.
```
~40 tokens.

**`codrag_audit`**
```
Run or retrieve a codebase health audit. Returns findings about architecture,
code quality, and tech debt from trace graph analysis.
Use action='scan' to audit, 'refactor' to get findings with code context,
'verify' to re-check after fixes, 'report' to retrieve a full report.
```
~50 tokens.

**`codrag_observe`**
```
Save or retrieve observations about the codebase for cross-session memory.
Observations persist across sessions and are flagged stale when linked files change.
Use action='save' to record a decision, bug, or pattern.
Use action='get' to retrieve previous observations (searched by query or file).
```
~50 tokens.

**Total description tokens: ~290** (down from ~3,697 in schema+description combined)

---

## 4. MCP Resources Implementation

### What to expose

| Resource URI | Content | Size | Update frequency |
|-------------|---------|------|-----------------|
| `codrag://project/structure` | Module summaries + hub files + connectivity map | ~2000 chars | On index rebuild |
| `codrag://project/atlas` | Codebase atlas (architectural overview) | ~1500 chars | On pipeline completion |
| `codrag://project/files` | Selected knowledge base file list + previews | ~1000 chars | On dashboard change |

### Implementation in `mcp/server.py`

Add `handle_resources_list` and `handle_resources_read` methods:

```python
async def handle_resources_list(self, params):
    project_id = await self._resolve_project_id()
    return {"resources": [
        {
            "uri": f"codrag://project/{project_id}/structure",
            "name": "Codebase Structure",
            "description": "Module summaries, hub files, and connectivity map",
            "mimeType": "text/markdown",
        },
        {
            "uri": f"codrag://project/{project_id}/atlas",
            "name": "Codebase Atlas",
            "description": "Architectural overview of the codebase",
            "mimeType": "text/markdown",
        },
        {
            "uri": f"codrag://project/{project_id}/files",
            "name": "Selected Files",
            "description": "Knowledge base files selected by the user",
            "mimeType": "text/markdown",
        },
    ]}
```

### Key question: Do hosts auto-inject?

- **Cursor**: Supports resources. Behavior unclear -- may require user @-mention.
- **Windsurf**: Supports resources per MCP spec. Behavior unclear.
- **Claude Desktop**: Supports resources. Can auto-include based on configuration.

**Testing plan:** Implement resources, test with each host, document behavior.

Even if hosts don't auto-inject, resources are valuable because:
1. The rules file can instruct the AI to read `codrag://project/structure` on every turn
2. Resources are cached by the host -- no tool-call overhead
3. Future hosts may auto-inject high-value resources

---

## 5. Rules File Auto-Generation

### Cursor: `.cursor/rules/codrag.mdrule`

```yaml
---
description: CoDRAG structural codebase intelligence
globs: ["**/*"]
alwaysApply: true
---

You have access to CoDRAG, a structural code intelligence system that understands
this codebase's architecture through a trace graph of imports, calls, and
structural relationships.

ALWAYS call the `codrag` tool (no arguments) at the START of every task.
This gives you:
- Module structure (which groups of files work together)
- Hub files (the most connected/important files)
- Knowledge base files (user's selected focus areas)

For specific code lookups, use `codrag_search` with a natural language query.
For impact analysis before changes, use `codrag_impact`.
For codebase health, use `codrag_audit`.

CoDRAG's structural understanding is BETTER than grep/ripgrep for navigating
relationships between files. Use it to understand how files connect before
making cross-file changes.
```

### Windsurf: `.windsurf/rules/codrag.md` (standalone file with frontmatter)

```markdown
---
trigger: always_on
description: CoDRAG structural codebase intelligence
---

You have access to CoDRAG MCP tools for structural codebase intelligence.
ALWAYS call `codrag` (no arguments) at the start of every task to get module
structure, hub files, and knowledge base context. Use `codrag_search` for
specific code lookups. Use `codrag_impact` before making changes.
```

### When to generate

- On `codrag add <project>` (CLI)
- On first index build (daemon)
- On "Generate rules file" button click (dashboard)
- **NOT** auto-overwrite if user has modified the file

### Implementation

New function in `src/codrag/core/rules_generator.py`:

```python
def generate_cursor_rules(project_path: Path, project_name: str) -> str:
    """Generate .cursor/rules/codrag.mdrule content."""
    ...

def generate_windsurf_rules(project_path: Path, project_name: str) -> str:
    """Generate .windsurf/rules/codrag.md content with frontmatter."""
    ...

def write_rules_file(project_path: Path, project_name: str, ide: str = "auto"):
    """Write the appropriate rules file. IDE auto-detected from directory contents."""
    cursor_dir = project_path / ".cursor"
    windsurf_dir = project_path / ".windsurf"

    if ide == "auto":
        if cursor_dir.exists():
            ide = "cursor"
        elif windsurf_dir.exists():
            ide = "windsurf"
        else:
            ide = "cursor"  # default

    if ide == "cursor":
        rules_dir = cursor_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        target = rules_dir / "codrag.mdc"
        if not target.exists():
            target.write_text(generate_cursor_rules(project_path, project_name))

    elif ide == "windsurf":
        rules_dir = windsurf_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        target = rules_dir / "codrag.md"
        if not target.exists():
            target.write_text(generate_windsurf_rules(project_path, project_name))
```

---

## 6. Response Format Optimization

### Current: JSON blob

```json
{
  "project_id": "abc123",
  "context": "[hub | in-degree:42 | @src/core/index.py]\ndef search(self, query...",
  "chunks_used": 5,
  "total_chars": 8420,
  "estimated_tokens": 2105,
  "ambient": true,
  "hub_files": 3,
  "modules_in_scope": 2,
  "neighbor_files": 8
}
```

The AI has to parse this JSON to extract the useful `context` string. The metadata fields (`chunks_used`, `total_chars`, etc.) are diagnostic noise that consumes tokens.

### Proposed: Clean markdown for `codrag` ambient tool

```markdown
## CoDRAG: ProjectName (547 nodes, 656 edges, 92% coverage)

### Modules in Scope
- **Core Engine** (89 files): indexing, search, trace graph, embedding
  Dependencies: -> API Layer, -> Dashboard
- **API Layer** (24 files): REST endpoints, middleware, auth
  Dependencies: -> Core Engine

### Hub Files (most connected)
1. `src/core/index.py` (42 deps) -- search index, context assembly
2. `src/core/trace.py` (38 deps) -- trace graph, structural queries
3. `src/server.py` (35 deps) -- server setup, route registration

### Knowledge Base (user-selected)
- `docs/ARCHITECTURE.md` (design doc, 2.1K chars)
- `src/core/` (directory, 89 files selected)

### Session Memory
- [note] TraceBuilder needs error handling for corrupted JSONL [src/core/trace.py]

### Health
Index: fresh (built 12m ago) | Watch: active | Trace: 92% coverage
```

This is ~250 tokens and gives the AI everything it needs. Compare to the current JSON which is ~300+ tokens but requires parsing.

### Implementation

In `_format_context_response()` and `tool_context()`, return text content directly instead of JSON:

```python
# In handle_tools_call, for codrag/codrag_context:
result = await self.tool_context(...)
return {
    "content": [
        {"type": "text", "text": result["markdown"]}  # Direct markdown, not json.dumps
    ],
    "isError": False,
}
```

For `codrag_search`, keep the existing context string format (it's already optimized with LOD headers). Just strip the JSON wrapper metadata.

---

## 7. Backward Compatibility

### Tool name aliases

The dispatch in `handle_tools_call` should continue accepting old tool names:

```python
# Old names -> new handlers
TOOL_ALIASES = {
    "codrag_context": "codrag",          # alias
    "codrag_": "codrag",                 # alias
    "hi_codrag": "codrag",              # absorbed
    "codrag_status": "codrag",          # absorbed (mode=status)
    "codrag_trace_search": "codrag_search",  # consolidated
    "codrag_trace_neighbors": "codrag_search", # consolidated
    "codrag_trace_coverage": "codrag",   # absorbed
    "codrag_build": None,                # removed (return helpful error)
    "codrag_audit_refactor": "codrag_audit",
    "codrag_audit_check": "codrag_audit",
    "codrag_audit_report": "codrag_audit",
    "codrag_save_observation": "codrag_observe",
    "codrag_get_observations": "codrag_observe",
}
```

Old tool names still work but are NOT listed in `tools/list`. This means:
- Existing .cursorrules or user habits that reference old tool names keep working
- New AI sessions only see the 5 clean tools
- Gradual migration with zero breakage

### Version flag

Add to `handle_initialize` response:

```python
"serverInfo": {
    "name": "codrag",
    "version": "2.0.0",  # Major version bump for tool consolidation
}
```

---

## 8. Implementation Sprints

### Sprint 1: Rules file generation (2h)
- [ ] Create `src/codrag/core/rules_generator.py`
- [ ] Cursor `.mdrule` template
- [ ] Windsurf `.windsurf/rules/codrag.md` template (with frontmatter)
- [ ] Wire into `codrag add` CLI command
- [ ] Wire into dashboard "Generate Rules" button (or auto on first build)
- [ ] Test: verify rules file appears and AI calls `codrag` automatically

### Sprint 2: Tool consolidation (4h)
- [ ] Create new tool definitions in `mcp_tools.py` (5 tools)
- [ ] Keep old definitions in `LEGACY_TOOLS` list for backward compat
- [ ] Update `handle_tools_list` to return only new tools
- [ ] Update `handle_tools_call` with alias dispatch table
- [ ] Implement `codrag_search` `type` param routing (context/symbol/neighbors)
- [ ] Implement `codrag_audit` `action` param routing (scan/refactor/verify/report)
- [ ] Implement `codrag_observe` `action` param routing (save/get)
- [ ] Test: all 16 old tool names still work, new tools work
- [ ] Measure: token count of new tool definitions

### Sprint 3: Response format optimization (3h)
- [ ] Design markdown templates for each tool response
- [ ] Implement `_format_ambient_markdown()` for `codrag` tool
- [ ] Update `tool_context()` to return markdown instead of JSON
- [ ] Update `tool_search()` to strip metadata wrapper, return context directly
- [ ] Update `tool_impact()` -- already returns formatted text, verify
- [ ] Update `tool_audit()` -- format findings as markdown, not JSON
- [ ] Test: AI consumes responses correctly

### Sprint 4: MCP Resources (4h)
- [ ] Implement `handle_resources_list` in `mcp/server.py`
- [ ] Implement `handle_resources_read` for structure/atlas/files resources
- [ ] Register `resources/list` and `resources/read` in `handle_request` dispatch
- [ ] Add `resources` to server capabilities in `handle_initialize`
- [ ] Build lightweight resource content generators (must be <50ms)
- [ ] Test with Cursor, Windsurf, Claude Desktop -- document behavior

### Sprint 5: Integration testing + description tuning (2h)
- [ ] End-to-end test: fresh project, build index, open in Cursor
- [ ] Verify: AI calls `codrag` on first prompt (with rules file)
- [ ] Verify: `codrag_search` works for all three types
- [ ] Verify: old tool names still resolve
- [ ] Tune descriptions based on observed AI behavior
- [ ] Document: which hosts auto-read resources, which need hints

---

## 9. Token Budget Analysis

### Before (current)

```
16 tool definitions:          ~3,697 tokens
Cursor built-in tools:        ~2,000 tokens (estimated)
Rules/system prompt:          ~500 tokens
-------------------------------------------------
Total tool overhead:          ~6,197 tokens per prompt
```

### After (proposed)

```
5 tool definitions:           ~1,400 tokens
Cursor built-in tools:        ~2,000 tokens (unchanged)
CoDRAG rules file:            ~150 tokens
Resource (structure):         ~500 tokens (if auto-injected)
-------------------------------------------------
Total tool overhead:          ~4,050 tokens per prompt
```

**Savings: ~2,147 tokens per prompt** in tool definition overhead alone.

Plus: the `codrag` ambient response is ~250 tokens of clean markdown instead of ~400+ tokens of JSON. Net benefit compounds over multi-turn conversations.

### Context window usage per prompt (ideal flow)

```
System prompt + tools:        ~4,050 tokens
codrag ambient response:      ~250 tokens (structural overview)
codrag_search response:       ~3,000 tokens (LOD-compressed code)
User message:                 ~200 tokens
-------------------------------------------------
Total per turn:               ~7,500 tokens
```

This is well within the 4K-16K "safe zone" from Phase 28 research. The AI gets maximum structural understanding in minimum space.

---

## 10. Measuring Success

### Metrics

| Metric | Current (est.) | Target |
|--------|---------------|--------|
| CoDRAG tool calls per session | 0-1 (when user asks) | 3-5 (every task) |
| First-prompt codrag call rate | ~10% | >90% (with rules file) |
| Tool definition tokens | 3,697 | <1,400 |
| Ambient response tokens | ~400 (JSON) | ~250 (markdown) |
| Time to structural understanding | N/A (usually never) | <100ms |

### How to measure

1. **MCP audit log** (`_audit_mcp_call` already records every tool call) -- aggregate by tool name, session
2. **Rules file adoption** -- track if `.cursor/rules/codrag.mdrule` exists in indexed projects
3. **Resource read frequency** -- log `resources/read` calls if/when implemented

---

## 11. Open Research Questions

- **Q1: Resource auto-injection** -- Need empirical testing. If Cursor/Windsurf auto-inject resources, this changes the entire strategy (resources become primary, tools become secondary).
- **Q2: Cursor tool limit** -- Reported as ~40-80 tools. We're well under with 5, but worth verifying.
- **Q3: Description length vs. quality** -- The arxiv paper finds Purpose + Guidelines is optimal. But does *shorter* always win, or is there a minimum threshold?
- **Q4: Multi-tool-call behavior** -- Can the AI call `codrag` + `codrag_search` in the same turn? If yes, the rules file should encourage this pattern.
- **Q5: Observation persistence** -- Is session memory (`codrag_observe`) valuable enough to justify a 5th tool? Could it be a Resource instead?

---

## 12. Deep Gap Analysis: Strategy for Each Gap

### Updated understanding of MCP Resources (critical correction)

Our initial README stated Resources could be "auto-injected by the host." **This is wrong.**

Per Cursor docs and the Webrix analysis of Cursor's MCP implementation:
> "Unlike prompts (user-initiated), resources are **application-initiated. The model determines when it needs additional context**, then requests specific resources from your MCP server."

Resources are NOT injected on every prompt. The AI model still has to *decide* to read them. This makes Resources behave more like a **cached, read-only data API** -- cheaper than a tool call (no approval needed, no write side-effects) but still requiring the AI to initiate.

**Implication:** Resources alone cannot solve the "always-on context" problem. The rules file (`alwaysApply: true`) remains the primary mechanism for ensuring CoDRAG is used on every turn. Resources are a secondary optimization -- they give the AI a fast, low-friction way to pull CoDRAG data once it knows CoDRAG exists (via the rules file).

---

### GAP-1: No MCP Resources

**Problem:** CoDRAG exposes zero Resources. All data access requires tool calls with approval overhead.

**Revised strategy:** Resources as a *secondary context layer*, not the primary always-on mechanism.

**What to expose:**

| Resource URI | Content | ~Size | When useful |
|-------------|---------|-------|-------------|
| `codrag://structure` | Module map + hub files + connectivity | ~500 tok | AI wants codebase overview without a full tool call |
| `codrag://atlas` | Architectural atlas narrative | ~400 tok | AI needs big-picture before diving into code |
| `codrag://files` | Selected KB file list + first-line previews | ~300 tok | AI wants to know what user has selected |
| `codrag://health` | Index freshness, coverage %, build status | ~100 tok | AI wants to check if data is stale |

**Key design principle:** Each resource must be **small enough that reading it is never wasteful** (<500 tokens each). If the AI reads all 4, that's ~1,300 tokens -- comparable to one `codrag` tool call but without approval friction.

**When the AI would read resources:**
1. The rules file tells it "CoDRAG resources are available for lightweight context" 
2. The AI decides it needs structural overview before making changes
3. The AI needs to check if the index is stale before trusting search results

**What Resources do NOT replace:** The `codrag` tool call for full ambient context (LOD-compressed hub file content, neighbor expansion). Resources are metadata; tools deliver actual code content.

**Implementation:**
```python
async def handle_resources_list(self, params):
    project_id = await self._resolve_project_id()
    return {"resources": [
        {
            "uri": f"codrag://{project_id}/structure",
            "name": "Codebase Structure",
            "description": "Module summaries, hub files, and dependency map. ~500 tokens.",
            "mimeType": "text/markdown",
        },
        # ... atlas, files, health
    ]}

async def handle_resources_read(self, params):
    uri = params.get("uri", "")
    # Parse project_id and resource type from URI
    # Return pre-computed markdown (cached, <50ms)
```

**Risk assessment:**
- Token waste on every chat: **LOW** -- Resources are not auto-injected. AI requests them on-demand.
- Stale data: **MEDIUM** -- Resources should include a `last_updated` timestamp so the AI knows freshness.
- Host compatibility: **NEEDS TESTING** -- Cursor supports resources. Windsurf unclear. Claude Desktop supports them.

**Verdict: IMPLEMENT, but as Sprint 4 (after rules file and tool consolidation prove the concept).**

---

### GAP-2: No MCP Prompts

**Problem:** No slash-command-style entry points for CoDRAG workflows.

**What MCP Prompts are:** User-triggered templates that appear as slash commands in the IDE. When the user types `/codrag-analyze`, the host sends the prompt template to the AI with pre-filled instructions.

**What to expose:**

| Prompt | Trigger | What it does |
|--------|---------|-------------|
| `/codrag-analyze` | User types in chat | "Call `codrag` for structural context, then analyze the codebase architecture. Identify patterns, potential issues, and suggest improvements." |
| `/codrag-review` | User types in chat | "Call `codrag` for context, then review the currently open file. Check for bugs, style issues, and structural problems using trace graph connections." |
| `/codrag-plan` | User types in chat | "Call `codrag_impact` on the files I'm about to change, then create a plan that accounts for all dependencies." |

**How prompts work in practice:**
- Cursor: Shows as slash commands in the chat input. User selects one, it generates the full prompt text.
- Claude Code: Similar concept via `/skill-name` commands.
- Windsurf: Unclear support level.

**Risk assessment:**
- Inconsistent UX across hosts: **HIGH** -- Each IDE renders prompts differently.
- Discovery problem: **MEDIUM** -- Users need to know prompts exist.
- Value vs. rules file: **LOW** -- Rules file already tells the AI to use CoDRAG. Prompts are a convenience for user-initiated workflows, not AI-initiated ones.

**Verdict: IMPLEMENT as Sprint 6 (nice-to-have, after core strategies are proven). Start with 2-3 prompts.**

---

### GAP-3: Tool description doesn't say "call me always"

**Problem:** The `codrag` tool description is passive. It describes what the tool does but doesn't tell the AI *when* to call it.

**Research finding (arXiv:2602.14878):** 89.3% of MCP tools lack "Usage Guidelines" -- the "when and how to use" component. Tools with clear activation criteria are significantly more likely to be called correctly.

**Strategy: Three-layer approach**

**Layer 1: Rules file (highest reliability, ~150 tokens)**
The `.cursor/rules/codrag.mdc` file with `alwaysApply: true` is injected into the system prompt on every turn. This is the most reliable mechanism because it's not competing with other tool descriptions -- it's a direct instruction to the AI.

```
---
description: CoDRAG structural codebase intelligence
alwaysApply: true
---

You have access to CoDRAG, a structural code intelligence system.

ALWAYS call `codrag` (or `codrag_context`) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.
For specific code searches, use `codrag_search`.
Before making changes, use `codrag_impact` to check dependencies.
```

**Layer 2: Tool description with activation criteria (~80 tokens)**
The tool description itself should include "When to use" guidance per the arxiv rubric:

```
Get structural codebase context -- modules, hub files, and knowledge base content.
Call this FIRST at the start of every task to understand codebase architecture
before reading or editing files. No arguments needed.
Use codrag_search instead when you need to find something specific.
```

**Layer 3: Response-embedded nudges (0 additional system prompt tokens)**
When the AI calls `codrag_search` but hasn't called `codrag` first, include a gentle nudge in the response:

```
[tip: Call `codrag` first for structural overview before targeted searches.]
```

This costs nothing in the system prompt and trains the AI over multi-turn conversations.

**Cross-IDE coverage:**

| IDE | Layer 1 mechanism | Layer 2 | Layer 3 |
|-----|------------------|---------|---------|
| Cursor | `.cursor/rules/codrag.mdc` (alwaysApply: true) | Tool description | Response nudge |
| Windsurf | `.windsurf/rules/codrag.md` (trigger: always_on) | Tool description | Response nudge |
| Claude Code | `CLAUDE.md` (project root, auto-loaded) | Tool description | Response nudge |
| Claude Desktop | MCP config (no rules equivalent) | Tool description | Response nudge |

**For Claude Code specifically**, the `CLAUDE.md` file is the equivalent of Cursor rules:
```markdown
# CLAUDE.md
This project uses CoDRAG for structural code intelligence.
Always call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for specific code queries with structural trace expansion.
Use `codrag_impact` before making changes to understand dependencies.
```

**Verdict: IMPLEMENT all three layers. Sprint 1 (rules file) + Sprint 2 (tool descriptions) + Sprint 3 (response nudges).**

---

### GAP-4: Too many tools dilute attention

**Problem:** 16 tools at ~3,697 tokens. Cursor caps at 40 tools total. Our 16 compete with ~15 built-in tools for attention.

**Research findings:**
- Microsoft Research: LLMs decline to act with ambiguous/excessive tools
- arXiv paper: Purpose + Guidelines is highest-leverage; more components can *hurt* due to token bloat
- Lunar.dev: Cursor enforces ~40-tool limit. 150 tools = 30K-60K token overhead.

**Strategy: Consolidate to 5 tools + 1 dev alias (see Section 2)**

The `codrag_context` alias is kept as a *listed tool* during development for testability:
- Listed in `tools/list` alongside `codrag` (identical schema)
- Allows testing by name in MCP inspector and this codebase
- Can be removed from listing (kept only as dispatch alias) before production launch
- Cost: ~240 tokens for the duplicate listing. Acceptable during dev.

**Token budget comparison:**

| Configuration | Tools | Tokens | % of Cursor's 40-tool budget |
|--------------|-------|--------|------------------------------|
| Current | 16 | 3,697 | 40% |
| Proposed (5 + alias) | 6 | ~1,640 | 15% |
| Proposed (5, no alias) | 5 | ~1,400 | 12.5% |

**Verdict: Already planned in Section 2. The `codrag_context` alias adds ~240 tokens -- acceptable for dev, removable for launch.**

---

### GAP-5: Knowledge base files aren't surfaced like "dragged files"

**Problem:** When users drag files into Cursor/Windsurf, the content is injected directly. When users select files in CoDRAG's dashboard, the content is only accessible via the `codrag` tool call, and even then it goes through the hub/neighbor LOD pipeline rather than being passed as direct file content.

**Research context:**
- Cursor's `@file` mechanism injects full file content as a user message attachment
- Windsurf's drag-drop does the same
- Both bypass the MCP layer entirely -- they're host-native features

**Strategy: Two-tier file delivery**

**Tier 1: Rules file tells AI about selected files (~50 tokens)**
The auto-generated rules file can dynamically include the selected file list:

```
---
description: CoDRAG context for MyProject
alwaysApply: true
---
...
The user has selected these focus areas in CoDRAG:
- src/core/ (89 files)
- docs/ARCHITECTURE.md
Call `codrag` to get their content with structural context.
```

This is regenerated when `included_paths` changes. The AI sees what's selected and knows to call `codrag` for the content.

**Tier 2: `codrag` returns selected files with priority**
When the user has `included_paths` set:
1. Selected files get LOD 0 (full content) with highest priority in the budget
2. Hub files that are also selected get extra weight
3. Files the user selected but that aren't in the trace graph still get included via the knowledge index

Current implementation already does this in `_assemble_ambient_context()` -- hub budget is 70%, selected files feed into hub file selection. The gap is that the AI doesn't *know* these are the user's selected files vs. random hubs.

**Tier 3: Response format makes selection explicit**
The optimized markdown response should clearly label user-selected content:

```markdown
### User's Focus Areas
- `src/core/` (89 files selected)
- `docs/ARCHITECTURE.md` (selected)

### Hub Files [from trace graph, highest connectivity]
1. `src/core/index.py` (42 deps) -- [SELECTED + HUB]
   <full file content here>

2. `src/core/trace.py` (38 deps) -- [HUB]
   <LOD 2 signatures>
```

The `[SELECTED + HUB]` label tells the AI these files have *double* significance: the user chose them AND the trace graph says they're important.

**Verdict: Implement across Sprints 1 (rules file with file list), 3 (response format labels), and 4 (resources for file list).**

---

### GAP-6: Response format is JSON, not optimized for AI consumption

**Problem:** Tool responses are `json.dumps(result, indent=2)`. The AI has to parse a JSON blob to extract useful context. Metadata fields (`chunks_used`, `total_chars`, `estimated_tokens`) are diagnostic noise.

**Research context:**
- LLMs process natural language more efficiently than structured JSON
- Markdown with headers provides scannable structure
- The `context` field inside the JSON is already formatted text -- the JSON wrapper just adds overhead

**Strategy: Direct markdown responses for all tools**

For each tool, return the `content[{type: "text", text: ...}]` as clean markdown, not `json.dumps`:

**`codrag` response (~250 tokens):**
```markdown
## MyProject (547 nodes, 656 edges, 92% coverage)

### Modules
- **Core Engine** (89 files): indexing, search, trace graph -> API Layer, Dashboard
- **API Layer** (24 files): REST endpoints, auth -> Core Engine

### Hub Files [most connected]
1. `src/core/index.py` (42 deps) [SELECTED]
2. `src/core/trace.py` (38 deps)
3. `src/server.py` (35 deps)

### Focus Areas [user-selected]
- `docs/ARCHITECTURE.md`
- `src/core/` (89 files)

### Health
Index fresh (12m ago) | Watch active | 92% coverage | 3 stale files
```

**`codrag_search` response (~3,000 tokens):**
Keep the existing LOD-formatted context blocks (they're already optimized):
```
[@src/core/index.py | lod=0]
def search(self, query, k=5, ...):
    ...

---

[@src/core/trace.py | lod=2 | trace-expanded]
class TraceIndex:
    def search(query, ...) -> List[Node]
    def get_neighbors(node_id, ...) -> Dict
```

Just strip the JSON wrapper. Return the `context` string directly.

**`codrag_impact` response:**
Already returns formatted text in `summary` field. Just return it directly instead of wrapping in JSON.

**Implementation detail:** The dispatch in `handle_tools_call` changes from:
```python
return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```
to:
```python
return {"content": [{"type": "text", "text": result["markdown"]}]}
```

Each tool method gains a `_to_markdown()` formatter.

**Verdict: Sprint 3. Estimated savings: ~100-200 tokens per response from eliminated JSON overhead.**

---

### GAP-7: No rules file auto-generation

**Problem:** The most reliable mechanism (rules files) requires manual setup. CoDRAG should generate them automatically.

**Strategy: Multi-IDE auto-generation with dynamic content**

**Cursor: `.cursor/rules/codrag.mdc`**

Format confirmed from Cursor docs: `.mdc` files in `.cursor/rules/` with YAML frontmatter.

```yaml
---
description: CoDRAG structural codebase intelligence
alwaysApply: true
---

You have access to CoDRAG, a structural code intelligence system that
understands this codebase through a trace graph of imports, calls, and
structural relationships.

ALWAYS call `codrag` (no arguments) at the START of every task. This gives you:
- Module structure (which groups of files work together and their dependencies)
- Hub files (the most connected/important files with full content)
- User's selected focus areas from the knowledge base

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes to a file, use `codrag_impact` to understand dependencies.

CoDRAG understands structural relationships between files. Use it instead of
grep when you need to understand how files connect to each other.
```

**Windsurf: `.windsurf/rules/codrag.md`**

Standalone file with YAML frontmatter (`trigger: always_on`). Windsurf injects all always-on rules into the system prompt.

```markdown
## CoDRAG Structural Context

This project uses CoDRAG for structural code intelligence via MCP.
ALWAYS call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for code queries. Use `codrag_impact` before changes.
```

**Claude Code: `CLAUDE.md`**

Plain markdown in project root, auto-loaded at startup.

```markdown
# CoDRAG Integration

This project is indexed by CoDRAG. Always call `codrag` (MCP tool) at the
start of every task for structural codebase context -- modules, hub files,
and selected knowledge base content. Use `codrag_search` for specific queries.
Use `codrag_impact` before making changes.
```

**Dynamic content:** The rules file can include a small dynamic section updated on each build:

```
Last indexed: 2026-03-14T17:30:00Z | 547 nodes, 656 edges | 92% coverage
Focus areas: src/core/, docs/ARCHITECTURE.md
```

This is regenerated by `write_rules_file()` after each index build.

**When to generate:**
1. `codrag add <project>` CLI command
2. First index build completion
3. Dashboard "Generate Rules" button
4. Never auto-overwrite if the user has added custom content to the file

**Detection of existing content:** Before writing, check if file exists and contains "CoDRAG" section. If yes and user has modified it (content differs from template), skip. If no, write/append.

**Verdict: Sprint 1 (highest priority). This is the single highest-impact change.**

---

### GAP-8: codrag_context alias for development (NEW)

**Decision:** Keep `codrag_context` as a listed tool (not just a dispatch alias) during development.

**Rationale:**
- When developing CoDRAG itself, the tool name `codrag` is confusing because the repo is also called CoDRAG
- `codrag_context` is unambiguous in test scripts and MCP inspector
- The alias already exists in the current dispatch (`name in ("codrag", "codrag_context", "codrag_")`)
- Listing it as a separate tool adds ~240 tokens but provides clear disambiguation

**Implementation:**
- `tools/list` returns both `codrag` and `codrag_context` with identical schemas
- `codrag_context` description says "Alias for `codrag` -- get ambient codebase context."
- Before v1.0 launch: move `codrag_context` from listed tools to dispatch-only alias
- Add a `CODRAG_DEV_MODE` env var or config flag to control whether aliases are listed

**Verdict: Include in Sprint 2 (tool consolidation). Flag for removal before launch.**

---

## 13. Strategy Summary: What Makes the AI Call CoDRAG

The research identifies **5 independent mechanisms** that influence whether an AI calls an MCP tool. CoDRAG should use all 5:

```
MECHANISM                      WHO CONTROLS IT    ALWAYS ON?    COST
---------------------------------------------------------------------
1. Rules file (alwaysApply)    The developer      Yes           ~150 tok/prompt
2. Tool description quality    MCP server         Yes           ~300 tok total
3. MCP Resources               AI model (pull)    No (on-demand) ~500 tok when read
4. Response nudges             MCP server         Per-response   0 tok system prompt
5. MCP Prompts (slash cmds)    The user           No (manual)    0 tok system prompt
---------------------------------------------------------------------
```

**Priority order by reliability:**
1. Rules file -- most reliable, always in system prompt
2. Tool descriptions -- always visible, but compete with other tools
3. Response nudges -- free, compound over multi-turn conversations
4. Resources -- available on-demand, good for lightweight metadata
5. Prompts -- user-initiated only, but good for structured workflows

**The ideal user journey:**
1. User installs CoDRAG, adds their project
2. CoDRAG auto-generates `.cursor/rules/codrag.mdc` (or `.windsurf/rules/codrag.md` / `CLAUDE.md`)
3. User opens Cursor/Windsurf/Claude Code on the project
4. Rules file is injected into every prompt: "You have CoDRAG. Call `codrag` first."
5. AI calls `codrag` on first prompt -> gets structural overview in ~250 tokens
6. AI now understands the codebase architecture and knows what files the user cares about
7. For specific work, AI calls `codrag_search` -> gets LOD-compressed, trace-expanded code
8. Before changes, AI calls `codrag_impact` -> understands blast radius
9. Session memory persists via `codrag_observe`

**Total context cost per prompt:** ~4,000-7,500 tokens (well within the 4K-16K safe zone from Phase 28).

---

## 15. Hybrid Strategy: Atlas Injection + Resources On-Demand (GAP-9)

### The Idea

Embed the **root atlas** directly in the rules file so the AI has a structural birds-eye view on *every single prompt* -- without needing a tool call. Then the AI has enough context to realize CoDRAG has deeper knowledge and is motivated to call `codrag` for the full structural payload.

This is a **priming strategy**: give the AI just enough structural awareness that it naturally reaches for the deeper tools.

### Why This Works (Research Backing)

**Pattern priming in LLMs** is well-documented: when the system prompt contains domain-specific context, the model's tool selection shifts toward tools that operate in that domain. The atlas contains file paths, module names, and architectural relationships -- exactly the vocabulary that triggers code-structural tool calls.

The mechanism is:
1. AI sees atlas in system prompt: "ARCHITECTURE: Core Engine (src/codrag/core/) connects to API Layer (src/codrag/api/) which serves..."
2. User asks about authentication
3. AI thinks: "I know from the atlas that auth is in the API layer. CoDRAG has structural tools that understand these connections. I should call `codrag_search` to get the actual code."
4. Without the atlas: AI would just `grep_search` or `read_file` -- no structural awareness.

### Token Budget: Is It Affordable?

Atlas sizes from `compute_root_atlas_budget()`:

| Project Size | Root Atlas | ~Tokens | % of 128K context |
|-------------|-----------|---------|-------------------|
| Small (2-50 files) | 1,200 chars | ~300 tok | 0.23% |
| Medium (50-200 files) | 1,200-1,375 chars | ~300-345 tok | 0.27% |
| Large (200-1000 files) | 1,375-2,500 chars | ~345-625 tok | 0.49% |
| Huge (1000+ files) | capped at 2,500 chars | ~625 tok | 0.49% |

**Maximum cost: 625 tokens per prompt.** This is comparable to what Windsurf already spends on its own system prompt preamble. For context:
- Cursor's built-in tool definitions: ~2,000 tokens
- A single `@file` inclusion in Cursor: ~500-5,000 tokens depending on file size
- Our CoDRAG tool definitions (after consolidation): ~1,400 tokens
- **Atlas injection: 300-625 tokens**

The atlas is *cheaper than including one medium-sized file* and provides structural orientation across the entire codebase.

### What About the Selected Files?

Two options for knowledge base files:

**Option A: File pointers only (~50-100 tokens)**
```
FOCUS AREAS (user-selected in CoDRAG dashboard):
- src/codrag/core/ (89 files)
- docs/ARCHITECTURE.md
- src/codrag/api/routers/
Call `codrag` for their content with structural context.
```

This tells the AI *what* files matter without consuming tokens on content. The AI knows to call `codrag` to get the actual code. Cost is minimal and scales with number of selections, not file sizes.

**Option B: File pointers + one-line summaries (~100-200 tokens)**
```
FOCUS AREAS:
- src/codrag/core/ (89 files) -- search index, trace graph, embedding, LLM clients
- docs/ARCHITECTURE.md -- project architecture overview
- src/codrag/api/routers/ (8 files) -- REST API endpoints
```

Slightly richer but still pointer-based. The one-line summaries come from module data we already have.

**Recommendation: Option A for launch, Option B if we have module summaries available.** The key principle is: never put file *content* in the rules file -- that's what the `codrag` tool call is for. The rules file is a map, not the territory.

### The Complete Hybrid Rules File

```yaml
---
description: CoDRAG structural codebase intelligence
alwaysApply: true
---

You have access to CoDRAG, a structural code intelligence system.
ALWAYS call `codrag` at the START of every task for full structural context.

## Codebase Atlas

IDENTITY: CoDRAG is a code intelligence daemon providing structural context to AI tools via MCP.
STACK: Python 3.11, FastAPI, Rust (codrag-engine via PyO3), React/TypeScript (dashboard), ONNX (embeddings).
ARCHITECTURE: Core Engine (src/codrag/core/) provides indexing, trace graph, and embedding. API Layer (src/codrag/api/) serves REST endpoints consumed by the dashboard and MCP server. Pipeline services (src/codrag/services/) orchestrate multi-stage enrichment. Rust engine (engine/) handles fast parsing and graph operations.
SUBSYSTEMS: trace: src/codrag/core/trace/, atlas: src/codrag/core/atlas/, search: src/codrag/core/index.py, pipeline: src/codrag/services/pipeline/
FLOW: MCP request -> mcp/server.py -> api/routers/projects/search.py -> core/index.py (search) + core/trace/ (expansion) -> LOD compression -> response

## Focus Areas
- src/codrag/core/ (89 files)
- docs/ARCHITECTURE.md
Call `codrag` for detailed content from these areas.

## Tools
- `codrag` -- structural overview + hub files + selected file content (call FIRST)
- `codrag_search` -- find specific code with trace expansion
- `codrag_impact` -- blast radius analysis before changes
```

**Total estimated size: ~400-700 tokens** depending on project/atlas size.

### Regeneration Strategy

The rules file embeds the atlas, so it must be regenerated when the atlas changes. But atlas generation is already part of the pipeline (Stage 3), so:

1. **Pipeline completes** -> atlas is written to `atlas.json`
2. **Post-pipeline hook** -> `write_rules_file()` reads the atlas, formats the rules file, writes it
3. **Rules file includes a timestamp** so the AI can see freshness: `Last indexed: 2026-03-14T18:00Z`
4. **Never overwrite user customizations**: Check for a `# USER ADDITIONS BELOW` marker. Everything above the marker is CoDRAG-managed. Everything below is user content that's preserved across regenerations.

```yaml
---
description: CoDRAG structural codebase intelligence
alwaysApply: true
---

# --- CoDRAG-managed section (auto-generated, do not edit above the marker) ---
# Last updated: 2026-03-14T18:00:00Z | 547 nodes, 656 edges | 92% coverage

<atlas content here>
<focus areas here>
<tool instructions here>

# --- USER ADDITIONS BELOW (your custom rules are preserved) ---
```

### Interaction With Resources and Tool Calls

The hybrid creates a **three-tier context funnel**:

```
TIER 1: Rules file (always-on, ~500 tokens)
   Contains: atlas + focus area pointers + tool instructions
   Purpose: Primes the AI with structural awareness
   Cost: Every prompt, but cheap and high-signal

         |
         v  "I know the structure, let me get details"

TIER 2: codrag tool call (on first prompt, ~250 tokens)
   Contains: Full module summaries, LOD-compressed hub files, selected file content
   Purpose: Deep structural + code context for the current task
   Cost: One tool call per task, approval may be needed

         |
         v  "I need specific code for this query"

TIER 3: codrag_search / codrag_impact (as needed, ~3000 tokens)
   Contains: LOD-compressed search results with trace expansion
   Purpose: Targeted code retrieval for specific questions
   Cost: Per-query, but precisely scoped

TIER 4: Resources (on-demand, ~100-500 tokens each)
   Contains: Health check, file list updates, atlas freshness
   Purpose: Lightweight metadata checks without tool call overhead
   Cost: Only when AI decides it needs a quick check
```

Each tier is progressively more expensive but also more detailed. The atlas in Tier 1 primes the AI to use Tier 2, which gives enough context to make Tier 3 queries precise.

### Risk Analysis

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Token waste on trivial prompts ("fix this typo") | LOW | 500 tokens is < 0.5% of context. The AI benefits from structural awareness even for small tasks. |
| Stale atlas after code changes | MEDIUM | Timestamp in rules file. AI sees "Last updated: 2h ago" and decides if it trusts the atlas. Regenerated on pipeline completion. |
| Rules file grows too large for huge projects | LOW | Root atlas is capped at 2,500 chars (~625 tok). Focus area pointers are capped at ~10 entries. Total never exceeds ~800 tokens. |
| User edits rules file, CoDRAG overwrites | HIGH | Marker-based split: CoDRAG manages top section, user content preserved below marker. |
| Atlas not yet generated (new project) | LOW | Rules file falls back to tool instructions only (no atlas section). Regenerated once pipeline runs. |

### Verdict

**This hybrid is the right strategy.** The atlas injection costs 300-625 tokens -- less than a single file inclusion -- and provides exactly the priming the AI needs to leverage CoDRAG's deeper tools. Combined with on-demand Resources for lightweight metadata checks, this creates a smooth context funnel from "birds-eye awareness" to "deep structural understanding."

**Implementation adds ~1h to Sprint 1** (rules file generation now reads atlas.json and embeds it).

---

## 16. Updated Sprint Plan

| Sprint | Focus | Hours | Dependencies |
|--------|-------|-------|-------------|
| 1 | Rules file auto-generation with embedded atlas (Cursor `.mdc`, Windsurf `.windsurf/rules/`, Claude `CLAUDE.md`) | 4h | None |
| 2 | Tool consolidation (16 -> 5+alias) + research-informed descriptions | 4h | None |
| 3 | Response format optimization (JSON -> markdown) + response nudges | 3h | Sprint 2 |
| 4 | MCP Resources implementation (structure, atlas, files, health) | 4h | Sprint 2 |
| 5 | MCP Prompts (2-3 slash commands) | 2h | Sprint 2 |
| 6 | Integration testing across Cursor, Windsurf, Claude Code | 3h | Sprints 1-4 |

**Total: ~20 hours across 6 sprints**

Sprints 1 and 2 can run in parallel (no dependencies). Sprint 3 depends on Sprint 2 (needs new tool methods). Sprint 4 depends on Sprint 2 (needs `handle_resources_*` methods). Sprint 5 is independent but low priority. Sprint 6 is the final validation.

---

## 17. Plan Review: Issues Found & Improvements

Full re-read of Sections 1-16 identified the following issues and opportunities.

---

### ISSUE-1: `codrag_search` type=neighbors is fundamentally different from type=context

**Problem:** The consolidation merges three tools into `codrag_search` with a `type` param. But `type: "context"` takes a `query` string, while `type: "neighbors"` takes a `node_id` (like `sym:UserService@src/auth/service.py:10`). These are *different input shapes*. An AI seeing one tool with a `query` param and a `node_id` param has to understand when to use which -- and the `required` array can't be conditional on `type`.

**Options:**

**A) Keep neighbors as a separate tool** -- 6 tools total instead of 5+alias. Adds ~200 tokens but avoids confusion. The `neighbors` operation is conceptually "graph traversal from a known point", which is distinct from "search for something."

**B) Make node_id optional on codrag_search** -- When `node_id` is provided, ignore `query` and do neighbor traversal. This is technically cleaner but the description has to explain two input modes, which adds complexity.

**C) Fold neighbors into codrag_impact** -- "What connects to this node?" is conceptually close to "What depends on this node?" Impact analysis already takes `file_path` and `symbol` params. We could add `direction: "dependents" | "all"` to impact. `direction: "dependents"` (default) = current blast radius. `direction: "all"` = neighbors in both directions.

**Recommendation: Option C.** This keeps the tool count at 5+alias and puts graph traversal where it conceptually belongs -- understanding relationships around a node. The `codrag_impact` tool becomes "understand a node's relationships" rather than just "what breaks." Rename consideration: `codrag_impact` -> `codrag_deps` or keep `codrag_impact` with a broader description.

Actually, even simpler: **keep `codrag_search` as context-only (query-based), and keep `codrag_impact` as the node-relationship tool.** The `codrag_impact` description already says it takes `file_path` or `symbol`. We just broaden it to "explore what connects to a file or symbol" instead of only "what depends on it."

**Revised `codrag_search`:** Only `type: "context"` and `type: "symbol"`. Both take a `query` string. No `node_id`. Much cleaner.

**Revised `codrag_impact`:** Takes `file_path` or `symbol` + optional `direction: "dependents" | "dependencies" | "all"` (default: dependents). This absorbs the neighbors use case.

---

### ISSUE-2: Tool approval friction kills "always call codrag" strategy

**Problem:** Cursor and Windsurf require user approval before executing MCP tools by default. If the AI calls `codrag` on every first prompt and the user has to click "Approve" every time, it's annoying and users will disable CoDRAG.

**Strategy: Recommend auto-approve for read-only tools**

The rules file should include a comment telling users how to enable auto-run:

```
# To avoid approval prompts, enable auto-run for CoDRAG's read-only tools:
# Cursor: Settings > Features > MCP > enable auto-run for codrag server
# Windsurf: Settings > Cascade > MCP > allow auto-run
```

Additionally, CoDRAG's MCP setup docs should prominently recommend auto-approve configuration. Our tools are all read-only (except `codrag_observe` save action) -- there's no security risk in auto-approving them.

**In the tool descriptions themselves**, add a hint: the `_meta` field could include a `readOnly: true` flag (non-standard but some hosts may respect it). More practically, the tool description can include "(read-only, safe to auto-approve)" which the human user sees when approving.

---

### ISSUE-3: First-run experience -- index not built yet

**Problem:** The rules file says "ALWAYS call `codrag` first." But if the user just installed CoDRAG and hasn't built the index yet, `codrag` will return an error: `INDEX_NOT_BUILT`. The AI gets a failure on its very first attempt to use CoDRAG, which trains it to *avoid* CoDRAG in future prompts.

**Strategy: Graceful degradation with onboarding guidance**

When the index isn't built, `codrag` should NOT return an error. Instead, return a helpful markdown response:

```markdown
## CoDRAG: ProjectName (setup in progress)

The codebase index hasn't been built yet. CoDRAG needs to scan your code
before it can provide structural context.

To build the index:
1. Open the CoDRAG dashboard (http://localhost:8400)
2. Click "Rebuild Knowledge Base"
-- OR run: codrag build /path/to/project

Once built, call `codrag` again for module structure, hub files, and
structural relationships.

For now, I'll work with the code directly using read_file and grep_search.
```

This is a **successful tool call** (isError: false) that guides both the user and the AI. The AI sees "for now, work directly" and falls back gracefully, while the user sees actionable steps.

The rules file should also handle this case:

```
If `codrag` returns "setup in progress", the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.
```

---

### ISSUE-4: Multi-turn context decay

**Problem:** The AI calls `codrag` on turn 1 and gets the structural overview. By turn 5-10, that response has scrolled out of the context window (depending on model context size and conversation length). The AI loses structural awareness mid-task.

**Strategy: Two approaches**

**A) The atlas in the rules file persists across all turns** -- Because it's in the system prompt (via `alwaysApply: true`), the atlas is present on EVERY turn. This is a major advantage of the hybrid strategy. Even if the `codrag` tool response scrolls out, the atlas stays.

**B) Response nudge on later turns** -- When the AI calls `codrag_search` on turn 5+, the response can include:

```
[context: Structural overview from `codrag` may be out of your context window.
Call `codrag` again if you need module structure or hub file refresher.]
```

The MCP server can track call history per session (it already has `_mcp_call_times` for rate limiting). If `codrag` was called >N turns ago and `codrag_search` is being called now, include the nudge.

**C) Rules file says "periodically refresh"** -- Add to the rules template:

```
For long tasks (5+ tool calls), call `codrag` again to refresh your
structural context.
```

**Recommendation: A is automatic (already solved by hybrid atlas). B for additional reinforcement. C as a lightweight addition to the rules file.**

---

### ISSUE-5: Should codrag_build be kept as a hidden/admin tool?

**Problem:** We removed `codrag_build` because "rebuilding an index is not an AI coding task." But consider: the AI detects that the index is stale (from `codrag` response), and it has no way to fix it. The user has to switch to the dashboard, click rebuild, wait, then come back.

**Revised strategy: Keep codrag_build as a dispatch alias, not a listed tool**

`codrag_build` stays in the `TOOL_ALIASES` dispatch table but is NOT listed in `tools/list`. This means:
- The AI won't spontaneously decide to build (it doesn't know the tool exists)
- But the rules file can mention it as a fallback: "If `codrag` says the index is stale and the user asks you to rebuild, call `codrag_build`."
- And if the user explicitly says "rebuild my index", the AI can call `codrag_build` because it saw the name in the rules file

This is the best of both worlds: no tool-list bloat, but the capability is there when needed.

---

### ISSUE-6: `codrag` response redundancy with atlas in rules file

**Problem:** With the hybrid strategy, the atlas is already in the rules file. When the AI calls `codrag`, the response currently returns module summaries and hub files -- which substantially overlaps with the atlas content.

**Opportunity: Adaptive response based on rules file presence**

The MCP server can detect whether a rules file exists for this project (check if `.cursor/rules/codrag.mdc` or `.windsurf/rules/codrag.md` exists in the project path). If yes, the `codrag` response skips the structural overview and goes straight to the high-value content the atlas *doesn't* have:

**With rules file (atlas already in system prompt):**
```markdown
## CoDRAG Context (deep)

### Hub File Content [LOD 0 -- full source]
[@src/core/index.py]
class CodeIndex:
    def search(self, query, k=5, ...):
        ...

### Neighbor Signatures [LOD 2]
[@src/core/trace.py]
class TraceIndex:
    def search(query, ...) -> List[Node]
    def get_neighbors(node_id, ...) -> Dict

### Session Memory
- [note] TraceBuilder needs error handling for corrupted JSONL

### Health
Index fresh (12m) | Watch active | 92% coverage
```

**Without rules file (no atlas priming):**
```markdown
## CoDRAG: ProjectName (547 nodes, 656 edges)

### Modules
- Core Engine (89 files): indexing, search, trace graph
- API Layer (24 files): REST endpoints, middleware

### Hub Files [with content]
[@src/core/index.py | 42 deps]
class CodeIndex:
    ...

### Health
Index fresh (12m) | Watch active | 92% coverage
```

The key difference: when the atlas is already primed, the `codrag` response budget shifts from "structural overview" (redundant) to "actual code content" (new value). This makes the tool call more worthwhile -- the AI gets code it can actually use, not a repeat of what it already knows.

**Implementation:** Add a `has_rules_file` check in `tool_context()`:
```python
rules_exists = (Path(proj.path) / ".cursor" / "rules" / "codrag.mdc").exists()
# Adjust response: skip module overview if rules_exists, allocate more budget to hub content
```

---

### ISSUE-7: Stale early sections (4, 5, 8, 9)

**Problem:** Sections 4, 5, 8, 9 were written before the deeper research in Sections 12-16. They contain:
- Section 4: Old resource URIs with `/project/{id}/` paths (Section 12/GAP-1 uses simpler URIs)
- Section 5: `.mdrule` extension (should be `.mdc` per Cursor docs)
- Section 5: Rules template without atlas injection (Section 15 has the hybrid version)
- Section 8: Old sprint plan (Section 16 is the current one)
- Section 9: Token budget doesn't include atlas cost

**Resolution:** These sections should be treated as "initial draft" and the later sections as authoritative. During implementation, follow Sections 12-16. A cleanup pass before Sprint 1 should reconcile them, but this is cosmetic -- the authoritative plans are clear.

**Note for Section 5:** The file extension must be `.mdc` (not `.mdrule`). Cursor docs confirm `.md` and `.mdc` are supported. `.mdc` enables YAML frontmatter with `alwaysApply`, `globs`, and `description` fields.

---

### OPPORTUNITY-1: Parallel tool calls on first prompt

**Problem:** The rules file says "call `codrag` FIRST." But some AI models and hosts support parallel tool calls -- calling `codrag` and `codrag_search` simultaneously on the first turn. If the user's question is specific ("how does authentication work?"), the AI could call both in parallel: `codrag` for structural context + `codrag_search` for specific auth code.

**Strategy:** Update the rules file to encourage this:

```
For your first response, you can call `codrag` and `codrag_search` in parallel:
`codrag` for structural overview + `codrag_search` with the user's specific question.
```

**Risk:** Not all hosts support parallel MCP calls. If a host serializes them, this just adds latency. Keep this as a suggestion, not a requirement.

---

### OPPORTUNITY-2: Resource subscriptions for live freshness

The MCP spec supports `resources/subscribe` -- the server notifies the client when a resource changes. CoDRAG could notify the host when:
- The atlas is regenerated (pipeline completion)
- The file selection changes (dashboard interaction)
- The index becomes stale (file watcher detects changes)

This is lower priority but would keep the AI's cached resource data fresh without polling. File under Sprint 4 (Resources).

---

### OPPORTUNITY-3: Detect host IDE and tailor behavior

The MCP `initialize` request includes `clientInfo` with the host's name and version. CoDRAG already extracts workspace roots from initialize. We could also extract the client name:

```python
client_name = params.get("clientInfo", {}).get("name", "unknown")
# "cursor", "windsurf", "claude-code", etc.
```

This enables:
- Tailoring response format (Cursor may handle markdown differently than Claude)
- Adjusting tool descriptions (Cursor's agent may respond to different phrasing than Claude)
- Logging which hosts are being used (product analytics)

Low effort, high diagnostic value. Add to Sprint 2.

---

### OPPORTUNITY-4: codrag_observe as write-through -- return context with every save

Currently `codrag_observe` with `action: "save"` would just return a confirmation. But what if it also returned the ambient context? The AI saves an observation AND gets refreshed structural context in one round-trip. This encourages the AI to use observations more frequently because it gets "free" context with every save.

```
AI: codrag_observe(action="save", content="Auth flow uses JWT with refresh tokens", file_path="src/auth/middleware.py")

Response:
Observation saved (id=obs_42). It will persist across sessions.

## Updated Context
### Hub Files [most connected]
1. src/auth/middleware.py (28 deps) [OBSERVED]
...
```

This is a small change but makes the observation tool feel integrated rather than separate.

---

### Summary of changes needed before implementation

| # | Type | Priority | Impact on existing plan |
|---|------|----------|----------------------|
| ISSUE-1 | Redesign codrag_search types | **HIGH** | Remove `type: "neighbors"` from codrag_search. Broaden codrag_impact to handle all node-relationship queries. |
| ISSUE-2 | Auto-approve guidance | **HIGH** | Add to rules file template + setup docs. No code change needed. |
| ISSUE-3 | First-run graceful degradation | **HIGH** | Change `codrag` to return helpful markdown instead of error when index not built. Sprint 2. |
| ISSUE-4 | Multi-turn decay mitigation | **MEDIUM** | Already solved by atlas in rules file. Add refresh nudge in Sprint 3. |
| ISSUE-5 | codrag_build as hidden alias | **MEDIUM** | Keep in dispatch table, mention in rules file as fallback. Sprint 2. |
| ISSUE-6 | Adaptive codrag response | **HIGH** | Skip structural overview when rules file exists, allocate budget to code content. Sprint 3. |
| ISSUE-7 | Reconcile stale sections | **LOW** | Cosmetic cleanup before implementation. |
| OPP-1 | Parallel tool calls | **LOW** | Add suggestion to rules file. No code change. |
| OPP-2 | Resource subscriptions | **LOW** | Sprint 4 addition. |
| OPP-3 | Detect host IDE | **MEDIUM** | Extract clientInfo in initialize. Sprint 2. |
| OPP-4 | Observe write-through | **LOW** | Return context with observation saves. Sprint 3. |

---

## 18. Preliminary Atlas & Atlas Freshness Lifecycle

### The Timeline Problem

The full LLM-generated atlas is produced at **Stage 9 (ATLAS)** in the deep enrichment group. On a first-run for a large repo, the pipeline stages run:

```
Stage 1: STRUCTURAL (Rust trace)     -- 5-30 seconds
Stage 2: INFERRED_EDGES (LLM)        -- minutes to hours
Stage 3: CATALOGUE (LLM augmenter)   -- minutes to hours
Stage 4: VALIDATION (Rust)            -- seconds
Stage 5: KNOWLEDGE (embedding)        -- seconds to minutes
  --- fast_sync complete, deep_enrichment starts ---
Stage 6: ENRICHMENT (epistemic, LLM)  -- minutes to hours
Stage 7: GROUP_REASONING (LLM)        -- minutes
Stage 8: CLUSTERING (LLM)             -- minutes
Stage 9: ATLAS (LLM)                  -- minutes        <-- ATLAS GENERATED HERE
Stage 10: DEEPENING (LLM)             -- minutes to hours
Stage 11: DEEP_KNOWLEDGE (embedding)  -- minutes
```

The user installs CoDRAG, the rules file says "call `codrag`", but the atlas section in the rules file is empty because Stage 9 hasn't run yet. The AI gets a rules file without the structural birds-eye view. This is potentially **hours** of running without the priming effect.

### What Data Exists After Stage 1?

After the Rust trace completes (~5-30s), these files exist:

| File | Content | Useful for atlas? |
|------|---------|------------------|
| `trace_nodes.jsonl` | Every file/function/class/method node | YES -- file paths, symbol names, kinds |
| `trace_edges.jsonl` | Imports, calls, inherits edges | YES -- connectivity, hub detection |
| `trace_manifest.json` | File counts, hashes, timing | YES -- project stats |

**NOT yet available:** `trace_modules.jsonl` (Stage 8), `trace_epistemic.jsonl` (Stage 6), `trace_augmented.jsonl` (Stage 3), `trace_inferred_edges.jsonl` (Stage 2).

### Can We Build Something Useful? Yes.

The existing `generate_structural()` method already handles the no-modules, no-epistemic case. Looking at `_build_structural_content()` in `@generator.py:1284-1334`:

With only Stage 1 data it would produce:
```
Project: 547 files. Languages: .py (245), .ts (142), .tsx (89), .rs (31), .js (20).
Graph: 2847 nodes, 3542 edges.
Hub files (highest connectivity): src/codrag/server.py (42), src/codrag/core/index.py (38), src/codrag/core/trace.py (35).
```

That's ~50 tokens. Useful but thin. We can do better.

### Enriched Preliminary Atlas (no LLM, ~200-300 tokens)

By adding directory-based segment detection (which `compute_segments()` in `@routing.py:100-143` already does from `trace_nodes.jsonl` alone), we can produce:

```
IDENTITY: (project name from config or directory name)
STACK: Python (.py: 245), TypeScript (.ts/.tsx: 231), Rust (.rs: 31), config (.json/.yaml: 35)
STRUCTURE: 547 files across 2847 graph nodes and 3542 edges.
SUBSYSTEMS:
  src/codrag/core/ (89 files) -- core engine
  src/codrag/api/ (32 files) -- api layer
  src/codrag/services/ (24 files) -- services
  src/codrag/dashboard/ (142 files) -- dashboard ui
  engine/ (31 files) -- rust engine
  packages/ui/ (89 files) -- ui package
  tests/ (72 files) -- test suite
HUB FILES: src/codrag/server.py (42 edges), src/codrag/core/index.py (38), src/codrag/core/trace.py (35)
```

This is ~200 tokens and gives the AI:
- What languages the project uses
- How the codebase is organized (directory-based subsystems)
- Which files are most important (hub detection)
- Rough project scale (file count, graph density)

**This is enough for priming.** The AI sees directory structure and hub files -- it knows where to look. When the full LLM atlas arrives hours later, it replaces this with richer content (module summaries, architecture layers, data flow descriptions).

### Quality Assessment: Will the AI Trust It?

**The preliminary atlas must NOT look incomplete or broken.** If the AI sees something that looks like a failed generation, it will discount CoDRAG's value. Design principles:

1. **Never include empty sections.** If modules aren't available, don't show "Modules: (none)". Just omit the section.
2. **Use confident language.** "SUBSYSTEMS:" not "Preliminary subsystems (will be refined later):".
3. **Include a freshness indicator but not an apology.** `Last indexed: just now | Full analysis in progress` tells the AI the data is fresh and improving, without undermining confidence.
4. **The format should be identical to the full atlas.** Same section labels (IDENTITY, STACK, SUBSYSTEMS, HUB FILES). When the LLM atlas replaces it, the AI doesn't notice a format change -- just richer content.

### Implementation: Where to Hook the Preliminary Atlas

The preliminary atlas should be generated as a **post-Stage-1 hook** in the pipeline orchestrator. Looking at `_on_build_transition()` in `@orchestrator.py`:

When Stage 1 (STRUCTURAL) completes:
1. `trace_nodes.jsonl` and `trace_edges.jsonl` are written
2. The orchestrator transitions to Stage 2
3. **NEW: Before advancing, generate preliminary atlas + write rules file**

```python
# In _on_build_transition(), after stage STRUCTURAL completes:
if stage == StageId.STRUCTURAL:
    self._generate_preliminary_atlas_and_rules(run.project_id)
```

The new method:
```python
def _generate_preliminary_atlas_and_rules(self, project_id: str) -> None:
    """Generate a structural-only atlas and write/update rules files.
    
    Called after Stage 1 (Rust trace) completes. Takes ~100ms (no LLM).
    The atlas is replaced by the full LLM-generated version at Stage 9.
    """
    try:
        from codrag.services.project_helpers import require_project
        from codrag.core.project_registry import project_index_dir
        from codrag.core.atlas import CodebaseAtlas

        project = require_project(project_id)
        idx_dir = project_index_dir(project)
        
        # Generate structural atlas (no LLM, reads trace_nodes + trace_edges)
        atlas = CodebaseAtlas(idx_dir, llm=None, project_root=Path(project.path))
        doc = atlas.generate_structural()
        
        if doc and doc.content:
            # Write rules file with this preliminary atlas
            from codrag.core.rules_generator import write_rules_file
            write_rules_file(
                project_path=Path(project.path),
                project_name=project.name or project_id,
                atlas_content=doc.content,
                is_preliminary=True,  # Adds "Full analysis in progress" note
            )
            logger.info(
                "Preliminary atlas + rules file written for %s (%d chars)",
                project_id, doc.char_count,
            )
    except Exception:
        logger.debug("Preliminary atlas generation failed (non-fatal)", exc_info=True)
```

**Cost:** ~100ms (reads two JSONL files, computes segments, writes two files). Zero LLM calls. Non-blocking.

### Atlas Freshness Lifecycle

The atlas and rules file should be regenerated at specific pipeline events:

```
EVENT                           ATLAS ACTION                    RULES FILE ACTION
─────────────────────────────────────────────────────────────────────────────────
Stage 1 completes               Generate structural (prelim)    Write/update with prelim
Stage 8 completes (clustering)  --                              --
Stage 9 completes (ATLAS)       LLM atlas replaces structural   Write/update with full atlas
included_paths changes          --                              Update focus areas section
Index rebuild (manual)          Regenerate structural            Write/update
Pipeline re-run                 Replaced at Stage 9              Updated at Stage 9
```

The rules file `write_rules_file()` function needs an **update mode** that:
1. Reads existing file
2. Replaces the CoDRAG-managed section (above the `USER ADDITIONS BELOW` marker)
3. Preserves user content below the marker

### Resource Subscriptions for Live Freshness (OPP-2 expanded)

When the atlas changes (Stage 1 preliminary, or Stage 9 full), CoDRAG sends a `notifications/resources/updated` notification to the MCP client:

```python
# After writing atlas and rules file:
if self._client:  # MCP client connection
    await self._notify_resource_changed("codrag://structure")
    await self._notify_resource_changed("codrag://atlas")
```

This tells the host (Cursor/Windsurf) that cached resource data is stale. If the host supports subscriptions, it will re-read the resource on the next prompt. If not, the rules file update is the primary mechanism (it's always fresh because it's read from disk on each prompt).

**Implementation in `mcp/server.py`:**
```python
async def _notify_resource_changed(self, uri: str) -> None:
    """Send resource-updated notification to the host (MCP spec).
    
    Non-fatal -- hosts that don't support subscriptions ignore this.
    """
    try:
        # MCP spec: notifications/resources/updated
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/resources/updated",
            "params": {"uri": uri},
        }
        # Write to stdout (stdio transport) or send via SSE
        # This depends on the transport mechanism
    except Exception:
        pass  # Best-effort
```

**Caveat:** Sending notifications requires the server to write to stdout unprompted, which only works in stdio transport. For SSE transport, the client polls or the server pushes via the SSE stream. This needs transport-aware handling in the MCP server's IO layer.

---

## 19. Implementation Pitfalls & Nuanced Code References

### PITFALL-1: `_build_structural_content()` returns short/empty string for small projects

**Location:** `@generator.py:1284-1334`

The structural builder returns `""` when `file_count < MIN_FILES_FOR_ATLAS` (which is 2). For projects with only 1 file, there's no atlas at all. This is fine for the atlas itself, but it means the **rules file would have no atlas section** for trivial projects.

**Fix:** The rules file generator should handle `atlas_content=""` gracefully -- just emit the tool instructions without the atlas section. Already accounted for in the hybrid design (Section 15, risk table: "Atlas not yet generated" -> "falls back to tool instructions only").

### PITFALL-2: `compute_segments()` calls `_load_modules_for_segments()` which reads `trace_modules.jsonl`

**Location:** `@routing.py:140`

```python
modules = _load_modules_for_segments(index_dir)
segments = _build_segments(dir_groups, modules)
```

After Stage 1, `trace_modules.jsonl` doesn't exist. `_load_modules_for_segments()` will return an empty dict. This is fine -- `_build_segments()` will create segments without domain tag annotations. But we should verify it doesn't crash on a missing file.

**Verification needed:** Check that `_load_modules_for_segments()` gracefully handles `FileNotFoundError`. Looking at the function pattern in this codebase, it likely does (most loaders use `if not path.exists(): return`), but needs explicit verification.

### PITFALL-3: Rules file extension must be `.mdc` not `.mdrule`

**Location:** Section 5 of this doc (PLAN.md)

Cursor docs confirm `.md` and `.mdc` extensions. The `.mdc` format supports YAML frontmatter with `alwaysApply`, `globs`, and `description` fields. `.mdrule` was used in Section 5 but is NOT a valid extension.

**Fix:** All rules file generation code must use `.mdc`:
```python
target = rules_dir / "codrag.mdc"  # NOT codrag.mdrule
```

### PITFALL-4: Windsurf `.windsurf/rules/codrag.md` could create duplicates

**Location:** Section 5, `write_rules_file()` implementation

The current plan checks `if "CoDRAG" not in existing:` before appending. But if the user modifies the CoDRAG section (e.g., removes the word "CoDRAG" but keeps the content), the next write would append a duplicate.

**Better approach:** Use a unique marker comment:
```python
MARKER = "<!-- codrag-managed-start -->"
END_MARKER = "<!-- codrag-managed-end -->"

def update_windsurfrules(path: Path, content: str) -> None:
    if path.exists():
        existing = path.read_text()
        if MARKER in existing:
            # Replace existing CoDRAG section
            before = existing[:existing.index(MARKER)]
            after_end = existing.find(END_MARKER)
            after = existing[after_end + len(END_MARKER):] if after_end >= 0 else ""
            path.write_text(before + MARKER + "\n" + content + "\n" + END_MARKER + after)
        else:
            path.write_text(existing + "\n\n" + MARKER + "\n" + content + "\n" + END_MARKER)
    else:
        path.write_text(MARKER + "\n" + content + "\n" + END_MARKER)
```

### PITFALL-5: `handle_tools_call` returns `json.dumps` -- changing to markdown breaks programmatic consumers

**Location:** `@mcp/server.py:1789-1794`

```python
return {
    "content": [
        {"type": "text", "text": json.dumps(result, indent=2)}
    ],
    "isError": False,
}
```

The MCP spec says tool results are `content: [{type: "text", text: string}]`. The `text` field is opaque -- the host passes it to the AI as-is. Changing from JSON to markdown is safe for the AI, but if any **programmatic consumer** (tests, scripts) parses the tool result as JSON, it will break.

**Check needed:** Grep for any code that calls `json.loads()` on MCP tool results. The MCP server tests (`tests/test_mcp_server.py`) likely parse results as JSON.

**Migration strategy:**
1. Add a `_format` param to tool methods: `_format="markdown"` (new default) or `_format="json"` (legacy)
2. The MCP dispatch always uses `_format="markdown"`
3. The REST API endpoints continue using JSON (they serve the dashboard)
4. Tests updated to expect markdown from MCP path, JSON from REST path

### PITFALL-6: `_resolve_project_id()` is async but `generate_structural()` is sync

**Location:** `@mcp/server.py:270` and `@generator.py:219`

The MCP server is async (`handle_tools_call` is `async def`). But `CodebaseAtlas.generate_structural()` is synchronous -- it reads JSONL files from disk, which is blocking I/O.

For the preliminary atlas (called from the pipeline orchestrator, which runs in a thread pool), this is fine. But if we ever call atlas generation from the MCP server's async path (e.g., to build a resource response on the fly), we'd need `asyncio.to_thread()`:

```python
async def handle_resources_read(self, params):
    # DON'T: atlas.generate_structural()  -- blocks the event loop
    # DO:
    doc = await asyncio.to_thread(atlas.generate_structural)
```

For the normal flow (atlas is pre-computed on disk, MCP just reads `atlas.json`), this isn't an issue. But worth noting for the Resources implementation in Sprint 4.

### PITFALL-7: The `codrag_context` alias in `tools/list` doubles the tool count for Cursor's 40-tool limit

**Location:** Section 2, GAP-8

Cursor sends the **first 40 tools** to the agent. If CoDRAG lists 6 tools (5 + alias), and the user has other MCP servers, the alias consumes one slot that could go to another server's tool.

**Mitigation:** The `CODRAG_DEV_MODE` env var should control whether the alias is listed. Default: `false` (alias NOT listed, only dispatched). During development: `CODRAG_DEV_MODE=1` to list it.

```python
DEV_MODE = os.environ.get("CODRAG_DEV_MODE", "").lower() in ("1", "true", "yes")

async def handle_tools_list(self, params):
    tools = [t for t in TOOLS if t["name"] != "codrag_context" or DEV_MODE]
    return {"tools": tools}
```

### PITFALL-8: Rules file regeneration on `included_paths` change could be frequent

**Location:** Section 15 (regeneration strategy)

If the user is actively selecting/deselecting files in the dashboard, each change triggers `write_rules_file()`. This writes to disk every time, which could cause the IDE to reload the rules file mid-conversation.

**Fix:** Debounce rules file writes. The dashboard already debounces config saves (P48-F35). Tie rules file regeneration to the same debounce:

```python
# In the included_paths update handler:
def _on_included_paths_changed(self, project_id: str) -> None:
    # Debounce: schedule regeneration 2s from now, cancel previous
    self._rules_regen_timer = threading.Timer(
        2.0, self._regenerate_rules_file, args=[project_id]
    )
    self._rules_regen_timer.start()
```

### PITFALL-9: `_on_build_transition` stage completion detection

**Location:** `@orchestrator.py` -- the exact callback where we'd hook the preliminary atlas

The `_on_build_transition` method is called when the `BuildOrchestrator` reports a build slot completed. We need to verify that when Stage 1 (STRUCTURAL) completes, the `trace_nodes.jsonl` and `trace_edges.jsonl` are fully flushed to disk before we try to read them for the preliminary atlas.

The Rust engine writes these files synchronously in the worker thread, and the build transition fires after the worker returns. So the files should be fully written. But worth adding a defensive check:

```python
def _generate_preliminary_atlas_and_rules(self, project_id: str) -> None:
    idx_dir = project_index_dir(project)
    nodes_path = idx_dir / "trace_nodes.jsonl"
    edges_path = idx_dir / "trace_edges.jsonl"
    
    if not nodes_path.exists() or nodes_path.stat().st_size == 0:
        logger.warning("trace_nodes.jsonl missing after Stage 1 -- skipping preliminary atlas")
        return
    # Proceed with atlas generation...
```

---

## Appendix: Research Citations

1. **"Tool-space interference in the MCP era"** (Microsoft Research, 2025)
   - Common tool names like `search` appear across dozens of MCP servers
   - LLMs "decline to act at all when faced with ambiguous or excessive tool options"
   - Overloaded prompts push important data out of context window

2. **"MCP Tool Descriptions Are Smelly!"** (arXiv:2602.14878, 2025)
   - 56% of MCP tools have Unclear Purpose
   - 89.3% lack Usage Guidance
   - Purpose + Guidelines is the highest-leverage combination
   - FM-augmented descriptions lift quality scores from 1-2 to ~5.0
   - Token-aware prioritization: optimize high-impact components first

3. **"MCP Tool Overload and How to Solve It"** (Lunar.dev, 2025)
   - 150 tools = 30,000-60,000 tokens just in metadata
   - Cursor enforces ~40-80 tool limit
   - Scoped tool groups dramatically improve accuracy

4. **CoDRAG Phase 28: Context Volume Research**
   - RAG performance saturates at 4K-16K tokens
   - CoDRAG defaults (K=5, max_chars=12000) are in the safe zone
   - "Give the LLM the RIGHT code, not MORE code"

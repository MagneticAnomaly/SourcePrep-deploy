# Prep Integration: Actionable Guidance

> Concrete implementation recommendations derived from the integration research across 20+ AI coding tools. This document answers: "What should Prep do differently to serve all these tools well?"

**Last updated:** 2026-03-14 (deep dive update)

---

## 1. The Three Layers of Universal Context Delivery

Research reveals three independent mechanisms Prep should use simultaneously. Each reaches a different subset of tools:

```
LAYER 1: MCP Server Instructions (protocol-level)
  Reach: Gemini CLI, Claude Code, Qwen Code (+ any spec-compliant host)
  Cost: Zero user setup. Automatic.
  Content: Brief directive (~100 tokens)
  Implementation: Add `instructions` field to MCP initialize response

LAYER 2: AGENTS.md + Tool-Specific Rules Files (file-level)
  Reach: 20+ tools (AGENTS.md), Cursor/Windsurf/Claude Code (specific files)
  Cost: One-time auto-generation per project
  Content: Atlas + tool instructions + focus areas (~400-700 tokens)
  Implementation: `write_rules_files()` after each pipeline run

LAYER 3: Tool Descriptions (MCP tool-level)
  Reach: Every MCP client (universal)
  Cost: Always-on in system prompt (~1,400 tokens for 5 tools)
  Content: Self-contained purpose + activation criteria
  Implementation: Already in Phase 50 PLAN.md Sprint 2
```

These layers are **redundant by design**. A tool that ignores `instructions` still gets AGENTS.md. A framework that skips file reading (DeepAgents) still gets tool descriptions. Coverage gaps are minimized.

---

## 2. Context Format: Universal Markdown

### Decision: All Prep Tool Responses Must Be Markdown

Every tool in the ecosystem processes markdown natively. JSON wrapping adds overhead and no value.

**Current (bad):**
```json
{
  "context": "## Modules\n- Core Engine...",
  "chunks_used": 12,
  "total_chars": 4500,
  "estimated_tokens": 1125
}
```

**Target (good):**
```markdown
## Prep: ProjectName (547 nodes, 656 edges)

### Modules
- **Core Engine** (89 files): indexing, search, trace graph -> API Layer, Dashboard
- **API Layer** (24 files): REST endpoints, middleware -> Core Engine

### Hub Files
1. `src/core/index.py` (42 deps) [SELECTED]
2. `src/core/trace.py` (38 deps)

### Health
Index: fresh (12m) | Watch: active | Coverage: 92%
```

**Why:**
- Scans identically in Claude, GPT, Gemini, Llama, Qwen
- Headers create navigable structure in any context window
- Zero diagnostic noise (no `chunks_used`, `total_chars`)
- Code blocks with paths are naturally understood by all coding models
- ~100-200 tokens saved per response from eliminated JSON wrapper

---

## 3. Rules File Generation: The Multi-File Strategy

### What to Generate (Priority Order)

| Priority | File | Why |
|----------|------|-----|
| **P0** | `AGENTS.md` section | Universal. 20+ tools read it. |
| **P0** | `.cursor/rules/prep.mdc` | Largest IDE user base. `alwaysApply: true` is critical. |
| **P1** | `CLAUDE.md` section | Claude Code is primary CLI tool. |
| **P1** | MCP `instructions` field | Zero-effort. Protocol-level. Gemini CLI, Claude Code, Qwen Code. |
| **P1** | `.windsurf/rules/prep.md` | Second-largest IDE. `trigger: always_on` frontmatter. |
| **P2** | `GEMINI.md` section | Growing CLI user base (or just use AGENTS.md). |
| **P2** | `.github/copilot-instructions.md` | Largest install base (Copilot). |
| **P3** | `.clinerules` section | Popular open-source extension. |
| **P3** | `.roo/rules/prep.md` | Growing extension, mode-specific. |
| **P3** | `.junie/guidelines.md` section | JetBrains expansion. |

### Content Template (Universal Core)

All files share the same core content, adapted to each format:

```markdown
## Prep Integration

This project is indexed by Prep for structural code intelligence via MCP.

ALWAYS call `prep` (no arguments) at the START of every task. This gives you:
- Module structure (which groups of files work together and their dependencies)
- Hub files (most connected/important files with full content)
- User's selected focus areas from the knowledge base

For specific code lookups, use `prep_search` with a natural language query.
Before making changes, use `prep_impact` to understand blast radius.

Prep's read-only tools are safe to auto-approve.

### Codebase Atlas
IDENTITY: [project identity]
STACK: [tech stack]
ARCHITECTURE: [module relationships]
SUBSYSTEMS: [key subsystems with paths]
FLOW: [request flow]

### Focus Areas
- [user-selected paths]

Last indexed: [timestamp] | [node_count] nodes | [coverage]% coverage
```

### Format Adaptation Per Tool

**Cursor (.mdc):** Add YAML frontmatter with `alwaysApply: true`
**CLAUDE.md:** Plain markdown section, appended
**AGENTS.md:** Plain markdown section, appended
**Windsurf (.windsurf/rules/prep.md):** YAML frontmatter with `trigger: always_on` (standalone file, NOT appended)
**GEMINI.md:** Plain markdown section, standalone or appended
**Copilot (.vscode/mcp.json):** Config uses `servers` key (NOT `mcpServers`). Rules in `.github/copilot-instructions.md`
**Cline (.clinerules):** Include keyword trigger phrases for MCP activation
**Roo Code (.roo/rules/):** General + mode-specific (`.roo/rules-architect/prep.md`)

---

## 4. MCP Server Instructions (NEW -- Immediate Action)

### Implementation

Add to Prep's MCP server `initialize` response:

```python
# In mcp/server.py, in the initialize handler:
async def handle_initialize(self, params):
    return {
        "serverInfo": {
            "name": "prep",
            "version": "2.0.0",
        },
        "instructions": (
            "Prep provides structural codebase context via trace graph analysis. "
            "ALWAYS call `prep` at the start of every coding task for module structure, "
            "hub files, and focus areas. Use `prep_search` for specific code queries "
            "with structural trace expansion. Use `prep_impact` before making changes "
            "to understand blast radius and dependencies."
        ),
        "capabilities": {
            "tools": {},
            "resources": {},
        },
    }
```

**Cost:** ~60 tokens in system prompt
**Reach:** Gemini CLI (confirmed), Claude Code (likely), Qwen Code (likely)
**Effort:** ~30 minutes

This is the single cheapest, highest-impact change for CLI tools.

---

## 5. Tool Description Design (Reinforced)

### Self-Contained Descriptions for Framework Tools

DeepAgents (LangChain), CrewAI, and other agent frameworks only see tool descriptions -- no rules files, no instructions field. Descriptions must be fully self-contained:

**Current (passive):**
```
"Get ambient codebase context"
```

**Target (active, self-contained):**
```
"Get structural codebase context -- module map, hub files, and focus areas.
Call this FIRST at the start of every coding task to understand how files
connect to each other. Returns architecture overview in ~250 tokens.
Read-only, safe to auto-approve."
```

Key elements:
- **Purpose**: what it returns
- **When to call**: "FIRST at the start of every task"
- **What it adds**: "how files connect" (differentiates from grep/search)
- **Cost signal**: "~250 tokens" (reassures AI it's cheap to call)
- **Safety signal**: "read-only, safe to auto-approve" (encourages auto-approve)

---

## 6. Atlas Design: Optimized for Diverse AI Models

### Size Constraints

| Model Context | Atlas Budget | Justification |
|--------------|-------------|---------------|
| 4K (small local LLM) | ~150 tokens | Must fit with tools + conversation |
| 32K (mid local LLM) | ~400 tokens | Comfortable, standard atlas |
| 128K (Claude, GPT) | ~625 tokens | Full atlas, no concern |
| 1M (Gemini) | ~625 tokens | Capped regardless (attention decay) |

### Atlas Content Tiers

**Tier 1 (minimal, ~150 tokens):** For small-context models
```
STACK: Python 3.11, FastAPI, React/TypeScript
MODULES: Core(89), API(24), Dashboard(15), Pipeline(12)
HUBS: index.py(42d), trace.py(38d), server.py(35d)
```

**Tier 2 (standard, ~400 tokens):** Default for most tools
```
IDENTITY: Prep -- code intelligence daemon for AI tools via MCP
STACK: Python 3.11, FastAPI, Rust (PyO3), React/TypeScript, ONNX
ARCHITECTURE:
  Core Engine (src/prep/core/) -> API Layer (src/prep/api/)
  API Layer -> Dashboard (packages/ui/)
  Pipeline (src/prep/services/) -> Core Engine
SUBSYSTEMS: trace, atlas, search (index.py), pipeline
FLOW: MCP -> mcp/server.py -> api/routers/ -> core/ -> response
```

**Tier 3 (full, ~625 tokens):** For Cursor/Windsurf/Claude Code rules files
Full atlas with subsystem details, flow, and focus areas.

### Adaptive Atlas Selection
Prep should detect the host via `clientInfo.name` in MCP initialize and serve the appropriate tier. Unknown hosts get Tier 2.

---

## 7. Auto-Approve Guidance Per Tool

### Include in Rules File and Documentation

```markdown
### Auto-Approve Prep (all tools are read-only)

**Cursor:** Settings > Features > MCP > enable auto-run for prep server
  NOTE: YOLO mode does NOT auto-approve MCP tools. You must enable per-server.
**Windsurf:** MCP panel > prep server > enable auto-run
**Claude Code:** Add `"allow": ["mcp__prep"]` to permissions in .claude/settings.json
  (Single rule covers ALL Prep tools. No wildcards needed.)
**Copilot (macOS/Linux):** Add `"sandboxEnabled": true` to .vscode/mcp.json
  (Sandboxed = auto-approved. Windows users must approve manually.)
**Gemini CLI:** Add `"trust": true` to prep server in ~/.gemini/settings.json
**Qwen Code:** Add `"trust": true` to prep server config
**Cline:** Auto-approve toggle per tool (Settings > Advanced > Auto-Approve)
**Roo Code:** Per-server auto-approve in settings
**Zed:** Set mcp:prep:* to always_allow in tool permissions
```

This should be in:
1. Prep setup documentation
2. The generated rules file (as a comment)
3. The dashboard MCP setup wizard (future)

---

## 8. Host Detection for Tailored Behavior

### Implementation

Extract `clientInfo.name` from MCP initialize:

```python
async def handle_initialize(self, params):
    client_name = params.get("clientInfo", {}).get("name", "unknown")
    self._host_name = client_name.lower()
    # Use for:
    # 1. Adaptive atlas tier selection
    # 2. Response format tailoring (if needed)
    # 3. Analytics (which hosts use Prep)
    # 4. Conditional rules file regeneration
```

### Known Client Names (to be verified empirically)
| Tool | Expected `clientInfo.name` |
|------|---------------------------|
| Cursor | `"cursor"` |
| Windsurf | `"windsurf"` or `"cascade"` |
| Claude Code | `"claude-code"` |
| Gemini CLI | `"gemini-cli"` |
| Qwen Code | `"qwen-code"` |
| Cline | `"cline"` |
| Roo Code | `"roo-code"` |
| Continue | `"continue"` |
| Zed | `"zed"` |

---

## 9. Cloud Agent Strategy (Jules, Copilot Agent, Devin, OpenHands)

### The Problem
Cloud agents run in remote sandboxes. They cannot access Prep's local daemon.

### The Solution: Static Context in AGENTS.md

For cloud agents, the atlas in AGENTS.md IS the entire Prep experience:

```
AGENTS.md (committed to repo)
  |
  +-- Prep Atlas section
  |     - Module structure
  |     - Hub files (paths only, not content)
  |     - Architectural flow
  |     - Focus areas
  |
  +-- Tool instructions (for when MCP IS available)
```

The atlas must be **self-sufficient** -- it should give a cloud agent enough structural awareness to make good architectural decisions even without live MCP tool access.

### Future: Remote Prep Server
Prep could support HTTP/SSE transport for remote access. This would allow cloud agents to call Prep tools from their sandboxes. This is a major deployment feature beyond Phase 50 scope.

---

## 10. Updated Phase 50 Sprint Adjustments

Based on this research, the following changes to Phase 50's sprint plan are recommended:

### Sprint 1 Additions
- **Add** `instructions` field to MCP initialize response (30min)
- **Add** AGENTS.md generation alongside Cursor/Windsurf/Claude rules files (1h)
- **Add** host detection via `clientInfo.name` (30min)

### Sprint 2 Adjustments
- Tool descriptions should include the "~250 tokens, read-only" signal
- Tool descriptions must work standalone (for framework tools like DeepAgents)

### Sprint 6 Additions (Integration Testing)
- Test across: Cursor, Windsurf, Claude Code, Gemini CLI, Cline, Roo Code
- Verify AGENTS.md reading in: Gemini CLI, Claude Code, Cursor
- Verify MCP instructions in: Gemini CLI
- Test with local LLMs via Cline/Roo Code (tool-calling quality)

### New Sprint 7 (Documentation)
- Per-tool setup guides
- Auto-approve instructions per tool
- AGENTS.md explanation for users
- DeepAgents/LangChain integration example

---

## 11. Key Metrics to Track Post-Launch

| Metric | How to Measure |
|--------|---------------|
| Which hosts connect to Prep | `clientInfo.name` from initialize |
| How often `prep` is called first | MCP call order tracking |
| Which tools trigger `prep_search` most | MCP call frequency per tool |
| Rules file adoption rate | Check if auto-generated files exist |
| Tool approval friction | Track user complaints / support requests |
| Cloud agent atlas effectiveness | User feedback on Jules/Copilot coding agent |

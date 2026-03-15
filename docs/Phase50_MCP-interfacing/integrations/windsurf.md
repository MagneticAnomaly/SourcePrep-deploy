# Windsurf (Cascade) Integration Research

> How Windsurf/Cascade consumes MCP, its unique context features, and how CoDRAG should optimize for it.

**Status:** UPDATED with confirmed docs deep-dive
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | IDE (VS Code fork) with Cascade AI agent |
| **Vendor** | Codeium (acquired by Cognition) |
| **Model** | Claude Sonnet, GPT-4o, custom (configurable) |
| **MCP Spec** | Tools + Resources confirmed. Prompts unclear. |
| **Transport** | stdio |
| **Rules File** | `.windsurf/rules/*.md` (YAML frontmatter) -- **NOT** `.windsurfrules` (legacy) |
| **AGENTS.md** | YES (confirmed on agents.md site, listed as "Windsurf from Cognition") |
| **Tool Limit** | **100 total tools** across all MCP servers (toggleable per tool) |
| **MCP Config** | `~/.codeium/windsurf/mcp_config.json` |
| **Unique Features** | Cascade Hooks (pre/post MCP tool use), Memories system, Skills |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support. Cascade agent calls MCP tools. Supports stdio, Streamable HTTP, SSE transports + OAuth.
- **Resources**: Supported. Cascade can read MCP resources when needed.
- **Prompts**: Not documented. Likely not exposed as slash commands.
- **Instructions**: Not documented. Unknown if server instructions are appended.

### Tool Limit: 100 Tools
"Cascade has a limit of 100 total tools that it has access to at any given time." Users can toggle individual tools on/off per MCP server settings page. CoDRAG's 5 tools are well within budget.

### Cascade Hooks (pre/post MCP tool use)
Windsurf supports lifecycle hooks that fire before and after MCP tool calls:
- `pre_mcp_tool_use`: fires before tool execution, can BLOCK (exit code 2)
- `post_mcp_tool_use`: fires after tool execution

Hook input includes `mcp_server_name`, `mcp_tool_name`, `mcp_tool_arguments`.
Future opportunity: CoDRAG could provide a hook script for usage analytics.

### Confirmation Model
- Default: Cascade asks user to approve each MCP tool call
- Settings > Cascade > MCP: can allow auto-run per server
- CoDRAG recommendation: enable auto-run for codrag server

### Key Difference from Cursor
Windsurf's Cascade agent has a "Flows" architecture -- it plans multi-step operations and executes them with less back-and-forth than Cursor's agent mode. This means:
- CoDRAG's `codrag` tool is more likely to be called at the start of a flow
- The AI plans its tool usage upfront, so clear tool descriptions matter more
- Response nudges ("call codrag_search for deeper code") may trigger follow-up flow steps

---

## 3. System Prompt & Context Architecture

### How Rules Work (CORRECTED -- `.windsurfrules` is legacy)
Rules now live in `.windsurf/rules/*.md` with YAML frontmatter:
- **Global**: `~/.codeium/windsurf/memories/global_rules.md` (6,000 char limit)
- **Workspace**: `.windsurf/rules/*.md` (12,000 char limit per file)
- **AGENTS.md**: Any directory in workspace (auto-scoped)
- **System (Enterprise)**: OS-specific (e.g. `/etc/windsurf/rules/`)

### Activation Modes (YAML frontmatter `trigger` field)
| Mode | `trigger:` | Behavior | Context cost |
|------|-----------|----------|-------------|
| **Always On** | `always_on` | Full content in system prompt every message | Every message |
| **Model Decision** | `model_decision` | Only description shown; full content on demand | Low |
| **Glob** | `glob` | Applied when matching files touched | Conditional |
| **Manual** | `manual` | Only when user types `@rule-name` | Zero until invoked |

CoDRAG needs `trigger: always_on`.

### Native Tools
Windsurf's native tools are similar to Cursor's:
- File reading/writing
- Terminal commands
- Code search (grep-based)
- Browser preview

### Key Insight: Less Aggressive Native Search
From our Phase 50 research, Windsurf's Cascade tends to be slightly more willing to use MCP tools than Cursor's agent, possibly because its "Flows" architecture plans tool sequences rather than reactively calling tools one at a time. This is anecdotal and needs empirical validation.

---

## 4. Rules File: `.windsurf/rules/codrag.md` (CORRECTED)

### Format
Markdown with YAML frontmatter. One file = one rule.

### CoDRAG Template
```markdown
---
trigger: always_on
description: CoDRAG structural codebase intelligence
---

You have access to CoDRAG, a structural code intelligence system.
ALWAYS call `codrag` (no arguments) at the START of every task.
This gives you module structure, hub files, and focus areas.

For specific code searches, use `codrag_search` with a natural language query.
Before making changes, use `codrag_impact` to understand blast radius.

CoDRAG's tools are read-only and safe to auto-approve.

## Codebase Atlas
[auto-generated structural overview]

## Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [stats]
```

### Generation Strategy
This is a standalone file (not appended to user content). CoDRAG creates/overwrites
`.windsurf/rules/codrag.md` entirely -- no marker-based merge needed since it's our file.

### AGENTS.md as Alternative
Root-level `AGENTS.md` is treated as **always-on** by Windsurf (same as `trigger: always_on`).
So generating AGENTS.md with CoDRAG content achieves the same effect. We generate BOTH
for redundancy.

---

## 5. Context Interpretation

### Response Format
- Markdown is optimal (same as all tools)
- Windsurf renders markdown in its chat panel
- Code blocks are preserved and formatted

### Multi-Turn Behavior
- Context window depends on model
- Windsurf has its own context management (memories system)
- Atlas in `.windsurf/rules/codrag.md` persists across all turns (always_on)
- Root-level AGENTS.md also persists (always-on by location)

---

## 6. CoDRAG Optimization Checklist

- [x] AGENTS.md reading behavior confirmed (root = always-on, subdir = auto-glob)
- [x] Rules file format confirmed (`.windsurf/rules/*.md` with frontmatter, 12K char limit)
- [x] 100-tool limit confirmed
- [x] Cascade Hooks confirmed (pre/post MCP tool use)
- [x] MCP config path confirmed (`~/.codeium/windsurf/mcp_config.json`)
- [ ] Empirically test: does Windsurf support MCP server `instructions`?
- [ ] Empirically test: does Windsurf support MCP prompts as slash commands?
- [ ] Empirically test: what is `clientInfo.name` in Windsurf's initialize request?
- [ ] Test auto-approve setup in Windsurf settings
- [ ] Test Cascade's flow behavior: does it call `codrag` at flow start?

---

## 7. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Windsurf/Cognition acquisition changes MCP behavior | MEDIUM | Monitor updates. Cognition (Devin) may shift architecture. |
| Rules format evolves again | LOW | `.windsurf/rules/` with frontmatter is the current standard. |
| Cascade prefers native search over CoDRAG | MEDIUM | Rules file (`always_on`) mitigates. |
| 100-tool limit pressure from many MCP servers | LOW | CoDRAG's 5 tools are minimal. Users can toggle. |

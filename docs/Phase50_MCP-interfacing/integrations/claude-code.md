# Claude Code Integration Research

> How Claude Code (CLI) consumes MCP, its unique context architecture, and how CoDRAG should optimize for it.

**Status:** UPDATED with confirmed docs deep-dive
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | CLI agent (terminal-based, NOT an IDE) |
| **Vendor** | Anthropic |
| **Model** | Claude Sonnet 4, Claude Opus 4 (selectable via `/model` or `--model`) |
| **MCP Spec** | Full (tools, resources, prompts, roots) |
| **Transport** | stdio |
| **Rules File** | `CLAUDE.md` (project root, auto-loaded at session start) |
| **AGENTS.md** | YES (reads as fallback/complement) |
| **Context Window** | 200K tokens (Claude Sonnet 4) |
| **Interfaces** | Terminal CLI, VS Code extension, JetBrains extension |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support. Claude Code can call MCP tools in its agentic loop.
- **Resources**: Supported. User can type `@` to see resources from connected MCP servers.
- **Prompts**: Supported. Appear as slash commands.
- **Roots**: Supported. Sends workspace roots in initialize.
- **Instructions**: Likely supported (Claude Code implements full MCP spec).

### Tool Discovery & MCP Tool Search (CRITICAL DISCOVERY)
- MCP tools appear alongside built-in tools (Read, Write, Edit, Bash, etc.)
- When many MCP servers are configured, Claude Code **defers** MCP tools
- **MCP Tool Search**: Claude uses an internal `MCPSearch` tool to discover relevant tools on-demand
- Deferred tools are NOT in the initial context -- Claude searches for them when needed
- Triggered automatically when total tools exceed a threshold
- Configurable: `ENABLE_TOOL_SEARCH=auto:<N>` (e.g. `auto:5` = 5% threshold)
- Can be disabled: `ENABLE_TOOL_SEARCH=false`

**Critical implication:** If user has many MCP servers, CoDRAG tools may be **invisible**
until Claude searches for them. CLAUDE.md and `instructions` field are the mitigations --
they tell Claude "CoDRAG exists, search for it."

**For MCP server authors (from Claude Code docs):** Include in server description:
"What category of tasks your tools handle, when Claude should search for your tools,
key capabilities your server provides."

**CoDRAG action:** MCP `instructions` field should include category hints:
"CoDRAG handles structural code intelligence, module architecture, dependency analysis,
and codebase navigation."

### MCP Output Limits
- **Default max:** 25,000 tokens per MCP tool response
- **Warning threshold:** 10,000 tokens
- Configurable via `MAX_MCP_OUTPUT_TOKENS` env var
- CoDRAG responses are typically 250-3,000 tokens -- well within limits

### Confirmation Model (CONFIRMED EXACT SYNTAX)
- Default: confirm each tool call
- Permission modes: `default`, `acceptEdits`, `plan`, `dontAsk` (bypass all)
- `bypassPermissions` mode available (can be disabled by managed settings)
- Per-tool permissions via `/permissions` command or settings files

**Exact MCP permission syntax (confirmed from docs):**
```
mcp__codrag           -- matches ANY tool from the codrag server
mcp__codrag__*        -- wildcard, same effect
mcp__codrag__codrag   -- matches only the `codrag` tool
mcp__codrag__codrag_search  -- matches only `codrag_search`
```

**CoDRAG recommendation (simplest):**
```json
{
  "permissions": {
    "allow": ["mcp__codrag"]
  }
}
```
This single rule auto-approves ALL CoDRAG tools. No need to list each one.

**Settings file locations:**
- `~/.claude/settings.json` (user-level)
- `.claude/settings.json` (project-level)
- Managed settings (enterprise, cannot be overridden)

### MCP Configuration
```json
// ~/.claude/settings.json or project .claude/settings.json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"],
      "env": {}
    }
  }
}
```

---

## 3. System Prompt & Context Architecture

### What Claude Code Accesses (in order)
1. **System prompt** -- Anthropic's base instructions for Claude Code agent behavior
2. **CLAUDE.md** -- project-root instructions, loaded at session start
3. **MEMORY.md** -- auto-memory, first 200 lines loaded at session start
4. **MCP tool definitions** -- all connected MCP tools
5. **Git state** -- current branch, uncommitted changes, recent history
6. **File system** -- project files via built-in Read/Write/Edit tools

### Native Tools That Compete With CoDRAG
| Claude Code Native | CoDRAG Equivalent | Competition Level |
|-------------------|-------------------|------------------|
| `Read` (file read) | `codrag` (hub file content) | LOW -- different purpose |
| `Grep` (ripgrep) | `codrag_search` | HIGH -- same intent, AI trusts native |
| `Bash` (any command) | N/A | LOW -- orthogonal |
| `Edit` (file edit) | N/A | NONE -- CoDRAG is read-only |
| `WebSearch` | N/A | NONE |

### Key Insight: Skills and Subagents
Claude Code has two powerful extension mechanisms:
- **Skills**: Prompt-based meta-tools that inject context and instructions at runtime
- **Subagents**: Isolated agents with their own context windows, tools, and permissions

CoDRAG's compact ambient response (~250 tokens) is ideal for sub-agent injection. A CoDRAG skill could be defined that automatically calls `codrag` and injects the result.

### Context Window Management
- Claude Code uses `/compact` to summarize conversation when context fills up
- `/compact focus on the API changes` allows focused compaction
- **Critical**: MCP tool responses from early turns get summarized/dropped during compaction
- **Mitigation**: Atlas in CLAUDE.md persists across all compactions (it's loaded fresh each session)
- **Mitigation**: MCP server `instructions` field persists in system prompt

---

## 4. Rules File: `CLAUDE.md`

### Format
Plain markdown in project root. No frontmatter needed -- entire file is loaded at session start.

### Hierarchy
- `~/.claude/CLAUDE.md` -- global (user-level)
- `./CLAUDE.md` -- project root (most common)
- `./src/CLAUDE.md` -- directory-level (loaded when working in that directory)

### Auto-Memory
Claude Code also maintains `MEMORY.md` (auto-generated). First 200 lines loaded per session. CoDRAG should NOT write to MEMORY.md -- that's Claude Code's domain.

### CoDRAG Template for CLAUDE.md
```markdown
## CoDRAG Integration

This project is indexed by CoDRAG for structural code intelligence via MCP.

ALWAYS call `codrag` (MCP tool, no arguments) at the START of every task.
This gives you:
- Module structure (which groups of files work together)
- Hub files (most connected/important files with content)
- User's selected focus areas from the knowledge base

For specific code searches, use `codrag_search` with a natural language query.
Before making changes, use `codrag_impact` to understand blast radius.

### Codebase Atlas
[auto-generated structural overview]

### Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [stats]
```

### Important: Don't Overwrite User Content
CLAUDE.md typically contains user instructions. CoDRAG should:
1. Check if CLAUDE.md exists
2. If yes, check for `## CoDRAG Integration` section
3. If section exists, update it (between markers)
4. If section doesn't exist, append it
5. Never touch content outside the CoDRAG section

---

## 5. Unique Claude Code Features Relevant to CoDRAG

### Skills (Prompt-Based Meta-Tools)
A CoDRAG skill could be created at `.claude/skills/codrag-context.md`:
```markdown
---
description: Get structural codebase context from CoDRAG
tools: ["mcp__codrag__codrag", "mcp__codrag__codrag_search"]
---
Call `codrag` to get the structural overview of this codebase,
then use that context to inform your approach to the current task.
```

This would allow users to invoke `/codrag-context` as a skill.

### Subagents
Claude Code can spawn subagents with `--agents` flag. CoDRAG's compact response format is critical here -- subagents have isolated context windows, so every token counts.

### Hooks
Claude Code supports lifecycle hooks (pre/post tool execution). A hook could automatically call `codrag` at session start:
```json
{
  "hooks": {
    "session_start": {
      "command": "echo 'Call codrag for structural context'"
    }
  }
}
```
(This is speculative -- hooks may not support MCP tool invocation directly)

---

## 6. Context Interpretation

### Response Format
- Claude models process markdown natively and extremely well
- JSON is functional but suboptimal (Claude can parse it, but markdown is more natural)
- Code blocks with language tags are well-handled
- **Recommendation**: Clean markdown (same as all other tools)

### Token Efficiency
- Claude Sonnet 4 has 200K context -- generous but compaction still matters
- CoDRAG's 250-token ambient response is <0.2% of context -- negligible
- The atlas in CLAUDE.md (~500 tokens) is similarly cheap

### Multi-Turn Decay
- Without `/compact`, context grows linearly
- With `/compact`, early tool responses are summarized
- Atlas in CLAUDE.md survives compaction (reloaded each session)
- MCP server instructions survive compaction (system prompt level)

---

## 7. CoDRAG Optimization Checklist

- [ ] Empirically test: does Claude Code support MCP server `instructions` field?
- [ ] Empirically test: what is `clientInfo.name` in Claude Code's initialize request?
- [ ] Test: do Claude Code subagents inherit MCP server access?
- [ ] Test: does `/compact` preserve or summarize `codrag` tool responses?
- [ ] Create example `.claude/skills/codrag-context.md` skill
- [ ] Test `allowedTools: ["mcp__codrag__*"]` wildcard for auto-approve
- [ ] Verify CLAUDE.md section append logic doesn't break existing content
- [ ] Test CoDRAG in Claude Code's VS Code and JetBrains extensions (same behavior?)

---

## 8. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| **MCP Tool Search defers CoDRAG tools** | **HIGH** | Many MCP servers = deferred. CLAUDE.md + instructions field mitigate. |
| AI prefers native `Grep` over `codrag_search` | HIGH | CLAUDE.md instructions mitigate. CoDRAG offers structural expansion that Grep cannot. |
| Context compaction drops early `codrag` responses | MEDIUM | Atlas in CLAUDE.md persists. Response nudges remind AI to re-call. |
| CLAUDE.md section append breaks user content | LOW | Marker-based updates, section-scoped. |
| Subagents can't access MCP tools | MEDIUM | Needs empirical test. If true, CoDRAG skill could bridge the gap. |
| `/compact` summarizes CoDRAG's structural context poorly | MEDIUM | The compact focus parameter could help: `/compact preserve structural context from codrag` |
| MCP output exceeds 25K limit | LOW | CoDRAG responses are 250-3K tokens. Only a concern for future massive context dumps. |

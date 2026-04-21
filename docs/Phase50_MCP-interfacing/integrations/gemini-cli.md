# Gemini CLI Integration Research

> How Gemini CLI consumes MCP, its unique features, and how Prep should optimize for it.

**Status:** UPDATED with confirmed docs deep-dive
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | CLI agent (terminal-based) |
| **Vendor** | Google |
| **Model** | Gemini 2.5 Pro / Flash (selectable) |
| **MCP Spec** | Full (tools, resources, prompts, roots, **instructions**) |
| **Transport** | stdio, SSE, Streamable HTTP |
| **Rules File** | `GEMINI.md` + `AGENTS.md` |
| **Open Source** | YES (github.com/google-gemini/gemini-cli) |
| **Config** | `.gemini/settings.json` |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support via `discoverMcpTools()` in `mcp-client.ts`
- **Resources**: Full support. Discovered automatically. User references via `@resource` in chat.
- **Prompts**: Full support. Exposed as slash commands (`/prompt_name`).
- **Instructions**: **YES -- confirmed.** "MCP server instructions will be appended to the system instructions."
- **Roots**: Supported via initialize.

### Architecture (from source code)
- **Discovery Layer** (`mcp-client.ts`): iterates configured servers, establishes connections, fetches tool definitions, sanitizes schemas, registers tools with conflict resolution, fetches resources.
- **Execution Layer** (`mcp-tool.ts`): each tool wrapped in `DiscoveredMCPTool` instance handling confirmation, execution, response processing.

### Tool Discovery Details
1. Iterates servers from `settings.json` `mcpServers` config
2. Establishes connection via appropriate transport
3. Fetches tool definitions from server
4. Sanitizes schemas: strips `$schema`, `additionalProperties`
5. Resolves name conflicts via automatic prefixing (`serverName__toolName`)
6. Fetches and registers resources

### Response Handling
Responses split into two parts:
- `llmContent`: raw response parts fed to the language model
- `returnDisplay`: formatted output shown to user (often JSON in markdown code blocks)

**Important**: The LLM sees `llmContent` directly. Prep's markdown responses flow straight into the model's context without additional formatting.

### Confirmation Model
- Default: confirm each tool call
- Trust bypass: `"trust": true` in server config skips all confirmations
- Dynamic allow-listing: per-server or per-tool trust built during session
- User choices: proceed once / always allow this tool / always allow this server / cancel

### Transport Support
- **stdio**: spawns subprocess, communicates via stdin/stdout (Prep's current method)
- **SSE**: connects to Server-Sent Events endpoints
- **Streamable HTTP**: HTTP streaming (newest transport)

### Schema Compatibility Notes
- `$schema` property stripped automatically
- `additionalProperties` stripped automatically
- Tool names sanitized to meet Gemini API requirements
- Name conflicts resolved via `serverName__toolName` prefix

---

## 3. System Prompt & Context Architecture

### MCP Server Instructions (KEY FEATURE)
Gemini CLI appends the MCP server's `instructions` field to its system instructions. This means Prep can inject guidance **without any rules file generation**:

```json
{
  "serverInfo": { "name": "prep", "version": "2.0.0" },
  "instructions": "Prep provides structural codebase context. ALWAYS call `prep` at the start of every task for module structure, hub files, and focus areas. Use `prep_search` for specific code queries. Use `prep_impact` before making changes.",
  "capabilities": { "tools": {}, "resources": {} }
}
```

This is **always-on** and **zero-effort for users** -- no file to generate, no config to edit.

### Native Tools
Gemini CLI's built-in tools include file operations, web search, shell commands, and Google-specific integrations. The competition landscape is similar to Claude Code.

### Context Window
Gemini 2.5 Pro: 1M tokens (enormous context)
Gemini 2.5 Flash: 1M tokens
- Context compaction is less of a concern with 1M tokens
- However, attention degradation in long contexts means Prep's compact format still matters

---

## 4. Rules File: `GEMINI.md`

### Format
Plain markdown. Loaded at session start via configuration:

```json
// .gemini/settings.json
{
  "context": {
    "fileName": "GEMINI.md"  // or "AGENTS.md"
  }
}
```

### AGENTS.md Support (CONFIRMED from agents.md FAQ)
Gemini CLI reads AGENTS.md when configured in `.gemini/settings.json`.
Confirmed by the AGENTS.md FAQ (agents.md site, stewarded by Agentic AI Foundation / Linux Foundation):
```json
{
  "context": { "fileName": "AGENTS.md" }
}
```
Gemini CLI is listed as a confirmed AGENTS.md reader on the agents.md site.
AGENTS.md is used by 60,000+ open-source projects.

### Prep Template for GEMINI.md
```markdown
## Prep Integration

This project uses Prep for structural code intelligence via MCP.

ALWAYS call `prep` at the start of every task for:
- Module structure and architectural overview
- Hub files (most connected code with full content)
- User's focus areas from the knowledge base

Use `prep_search` for natural language code queries.
Use `prep_impact` before making changes to understand blast radius.

### Codebase Atlas
[auto-generated]

### Focus Areas
[auto-generated]
```

### Strategy
Since Gemini CLI supports MCP server instructions, Prep should:
1. **Primary**: Use `instructions` field (automatic, zero user setup)
2. **Secondary**: Generate AGENTS.md section (persists across sessions, contains atlas)
3. **Optional**: Generate GEMINI.md if `.gemini/` directory detected

---

## 5. Resources in Gemini CLI

### How Resources Work
- Discovered automatically when server registers them
- User references resources via `/mcp` command to list, then `@resource_name` in chat
- Resources provide read-only data without tool call overhead

### Prep Resources for Gemini CLI
```
prep://atlas          -- structural overview (atlas.json content)
prep://health         -- index freshness, coverage stats
prep://files          -- list of user-selected focus files
prep://modules        -- module breakdown
```

These are lightweight (100-500 tokens each) and let the AI pull metadata without a full `prep` tool call.

---

## 6. Prompts as Slash Commands

### How They Work
MCP servers can define prompts that appear as `/slash_commands` in Gemini CLI.

### Prep Prompts
```
/prep-overview   -- "Give me a structural overview of this codebase"
/prep-review     -- "Review this code using structural context"
/prep-plan       -- "Plan this change using dependency analysis"
```

These are user-initiated, zero token cost until invoked.

---

## 7. Unique Gemini CLI Features

### Open Source Advantage
Gemini CLI is open source. We can:
- Read the exact source code for MCP integration
- Understand exactly how tool descriptions are processed
- Verify schema sanitization behavior
- Test integration without black-box assumptions

### `/mcp` Command
Users can type `/mcp` to see all connected MCP servers, their status, and available tools. This helps debugging Prep connections.

### Rich Content Return
Gemini CLI supports returning text + images from MCP tools. Prep could potentially return visual dependency graphs in the future (low priority).

### Sandbox Compatibility
Gemini CLI has sandboxing features. MCP servers must be accessible within the sandbox environment. Prep runs as a local daemon, so this should work out of the box.

---

## 8. Prep Optimization Checklist

- [x] MCP `instructions` field confirmed (appended to system instructions)
- [x] AGENTS.md support confirmed (via `.gemini/settings.json` context config)
- [x] `trust: true` auto-approve confirmed (in server config)
- [x] MCP resources confirmed (auto-discovered, referenced via `@resource`)
- [x] MCP prompts confirmed (exposed as `/slash_commands`)
- [x] Schema sanitization behavior confirmed (strips `$schema`, `additionalProperties`)
- [x] Open source confirmed (can verify all behavior from source code)
- [ ] Implement `instructions` field in Prep MCP server's initialize response
- [ ] Empirically test: verify instructions appear in Gemini CLI system prompt
- [ ] Empirically test: what is `clientInfo.name` in Gemini CLI's initialize request?
- [ ] Implement MCP resources (prep://atlas, prep://health)
- [ ] Implement MCP prompts (/prep-overview, /prep-review)
- [ ] Test schema sanitization with Prep's actual tool schemas
- [ ] Verify `trust: true` behavior with Prep daemon

---

## 9. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Gemini's 1M context makes Prep seem less necessary | LOW | Prep provides *structure*, not just *content*. Raw file dumps don't show architectural relationships. |
| Schema sanitization breaks Prep tool schemas | LOW | Prep uses simple JSON Schema. `$schema` and `additionalProperties` are not critical. |
| `instructions` field too short for atlas | MEDIUM | Keep instructions brief (~100 tokens). Atlas goes in AGENTS.md/GEMINI.md. |
| Tool name conflict with other MCP servers | LOW | `prep` is a unique name. Prefix fallback is `prep__prep`. |

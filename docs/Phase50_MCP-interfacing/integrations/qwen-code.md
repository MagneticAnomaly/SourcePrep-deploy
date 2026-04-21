# Qwen Code Integration Research

> How Qwen Code consumes MCP, its relationship to Gemini CLI, and how Prep should optimize for it.

**Status:** PRELIMINARY -- needs empirical validation
**Last updated:** 2026-03-14

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | CLI agent (terminal-based) |
| **Vendor** | Alibaba (Qwen team) |
| **Model** | Qwen3-Coder, Qwen3 (selectable) |
| **MCP Spec** | Full (tools, resources, prompts) |
| **Transport** | stdio, SSE, Streamable HTTP |
| **Rules File** | `AGENTS.md` |
| **Open Source** | YES (GitHub: QwenLM/qwen-code) |
| **Config** | `settings.json` |

---

## 2. Critical Finding: Architecture Mirrors Gemini CLI

Qwen Code's MCP documentation is **structurally identical** to Gemini CLI's docs. Same section headings, same architecture descriptions, same code structure (`packages/core/src/tools/`, `mcp-client.ts`, `mcp-tool.ts`). This strongly indicates a shared codebase or fork.

### Implications:
- MCP behavior in Qwen Code is highly likely to match Gemini CLI
- Schema sanitization rules are the same (`$schema` stripped, `additionalProperties` stripped)
- Tool name conflict resolution is identical (`serverName__toolName` prefix)
- Confirmation model is identical (`trust: true` bypass)
- Resource discovery is identical

### Differences from Gemini CLI:
- **Tool name length limit**: Qwen Code truncates names >63 characters (Gemini CLI docs don't mention a limit)
- **Tool name sanitization**: Invalid characters replaced with underscores (same pattern but Qwen API-specific requirements)
- **`includeTools`/`excludeTools`**: Qwen Code supports per-server tool filtering (Gemini CLI may also but less documented)
- **Global allow/deny lists**: `mcp.allowed` and `mcp.excluded` in settings.json for server-level control

---

## 3. MCP Implementation Details

### Tool Discovery
1. Iterates servers from `settings.json` `mcpServers` config
2. Establishes connection via transport (httpUrl -> Streamable HTTP, url -> SSE, command -> stdio)
3. Fetches tool definitions
4. Applies `includeTools`/`excludeTools` filter
5. Sanitizes names (invalid chars -> underscore, >63 chars truncated with `___`)
6. Resolves conflicts (first registration wins, subsequent get `serverName__toolName`)
7. Strips `$schema`, `additionalProperties`, `anyOf` defaults

### Confirmation Model
- Default: confirm each tool call
- `"trust": true` per server: bypasses all confirmations
- Per-server and per-tool allow-listing during session

### Tool Filtering (Unique Feature)
```json
{
  "mcpServers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"],
      "includeTools": ["prep", "prep_search", "prep_impact"],
      "trust": true
    }
  }
}
```

This allows users to expose only specific Prep tools, hiding administrative ones like `prep_audit` or `prep_observe` if not needed.

---

## 4. MCP Server Instructions

### Unknown but Likely
Given the Gemini CLI architectural similarity, Qwen Code likely supports the `instructions` field in server capabilities. **Needs empirical verification.**

If confirmed, Prep's instructions field works here too -- zero-effort always-on context injection.

---

## 5. Rules File: `AGENTS.md`

Qwen Code reads `AGENTS.md` as its primary instruction file. No tool-specific alternative documented.

### Prep Strategy
Generate `AGENTS.md` section (same as universal template). Since Qwen Code is AGENTS.md-first, this is all that's needed.

---

## 6. Unique Qwen Code Features

### Model-Agnostic Base
Qwen Code works with Qwen models by default but can connect to other providers. The Qwen3-Coder model is specifically optimized for code tasks with tool-calling.

### IDE Integrations
Qwen Code integrates with:
- VS Code (via extension)
- Zed (via ACP -- Agent Client Protocol)
- Terminal (native CLI)

### Qwen3-Coder Tool Calling
Qwen3-Coder has native API tool call interface support (via vLLM). This means tool descriptions are processed through a dedicated tool-calling path, not just as text in the system prompt.

---

## 7. Prep Optimization Checklist

- [ ] Empirically test: does Qwen Code support MCP server `instructions`?
- [ ] Empirically test: what is `clientInfo.name` in Qwen Code's initialize request?
- [ ] Verify Prep tool names are <63 characters (they are -- longest is `prep_observe`)
- [ ] Test `trust: true` auto-approve with Prep
- [ ] Test `includeTools` filtering with Prep tools
- [ ] Confirm AGENTS.md reading behavior
- [ ] Test schema compatibility after `$schema`/`additionalProperties` stripping

---

## 8. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Tool name truncation | NONE | Prep's names are all <20 chars |
| Schema stripping breaks Prep | LOW | Prep uses simple schemas |
| Qwen3-Coder's tool-call quality differs from Claude/GPT | MEDIUM | Tool descriptions may need tuning for Qwen models |
| Qwen Code diverges from Gemini CLI in future | LOW | Monitor for architectural divergence |

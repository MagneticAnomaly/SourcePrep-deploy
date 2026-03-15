# Cline Integration Research

> How Cline (VS Code extension) consumes MCP, its autonomous agent architecture, and CoDRAG optimization.

**Status:** UPDATED with confirmed docs deep-dive
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | VS Code extension (autonomous coding agent) |
| **Vendor** | Community (open source, Apache 2.0) |
| **Model** | Any (Claude, GPT, Gemini, local -- user-configurable) |
| **MCP Spec** | Full (tools, resources) |
| **Transport** | stdio |
| **MCP Config** | `cline_mcp_settings.json` (via Settings > MCP Servers > Configure) |
| **Rules File** | `.clinerules` (project root, keyword-based MCP triggers) |
| **AGENTS.md** | Not natively confirmed -- use `.clinerules` as primary |
| **Market Share** | One of the most-installed VS Code AI extensions |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support. Cline's agentic loop calls MCP tools alongside built-in tools.
- **Resources**: Supported. Cline can read MCP resources for context.
- **Prompts**: Not documented.

### Architecture
Cline operates as an autonomous agent that:
1. Reads user request
2. Plans approach (may involve multiple tool calls)
3. Executes tools (file read/write, terminal, MCP tools)
4. Verifies results
5. Iterates until task complete

This "plan, implement, verify, fix" loop means CoDRAG tools are most useful in the **planning phase** -- structural context informs the approach.

### MCP Configuration
- Config file: `cline_mcp_settings.json`
- Access: MCP Servers icon > Configure tab > Configure MCP Servers
- Supports stdio and SSE transports
- Enable/disable individual servers via toggle
- Network timeout configurable per server
- **Global MCP Mode**: Settings > Advanced MCP Settings > `Cline>Mcp:Mode`

### Confirmation Model
- Default: user approves each action (human-in-the-loop GUI)
- **Auto-approve available**: see [auto-approval docs](https://docs.cline.bot/features/auto-approve)
- Cline shows what the AI wants to do before executing
- CoDRAG recommendation: enable auto-approve for CoDRAG tools (read-only, safe)

### .clinerules for MCP Activation
From Cline docs: "When you have a lot of MCP servers enabled, it can be useful to define
when to use each server. Utilize a `.clinerules` file to support intelligent MCP server
activation through keyword-based triggers."

This means CoDRAG's `.clinerules` content should include trigger keywords:
```markdown
When asked about code structure, architecture, dependencies, modules,
hub files, or blast radius, use the CoDRAG MCP tools.
```

### Key Feature: Model Agnostic
Cline works with ANY model provider. This means:
- Tool descriptions must work across Claude, GPT, Gemini, Llama, Qwen, etc.
- CoDRAG's tool descriptions need to be model-agnostic (no Claude-specific phrasing)
- Local LLM users (Ollama, LM Studio) are a significant Cline demographic

---

## 3. Rules File: `.clinerules`

### Format
Plain text/markdown in project root. Injected into system prompt.

### CoDRAG Template
```markdown
## CoDRAG Structural Context

This project uses CoDRAG for structural code intelligence via MCP.
ALWAYS call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for code queries with structural trace expansion.
Use `codrag_impact` before making changes to understand dependencies.

### Codebase Atlas
[auto-generated]

### Focus Areas
[auto-generated]
```

---

## 4. Special Considerations

### Local LLM Users
Cline's user base includes many local LLM users. CoDRAG implications:
- Local models have smaller context windows (4K-32K typical)
- CoDRAG's compact 250-token ambient response is critical
- Tool descriptions must be concise -- local models are more sensitive to token budget
- The atlas in `.clinerules` must be short for small-context models

### Model Quality Variance
Different models handle MCP tool calls with varying quality:
- Claude Sonnet: excellent tool calling
- GPT-4o: good tool calling
- Llama 3.3: adequate but less reliable
- Smaller models (7B-14B): may struggle with tool selection

CoDRAG's rules file instructions must be clear and direct to work with weaker models.

---

## 5. CoDRAG Optimization Checklist

- [x] MCP config file confirmed (`cline_mcp_settings.json`)
- [x] Auto-approve feature confirmed (per-tool)
- [x] `.clinerules` keyword-based MCP activation confirmed
- [x] Global MCP Mode confirmed
- [ ] Test CoDRAG MCP integration in Cline
- [ ] Verify `.clinerules` injection behavior empirically
- [ ] Test with local LLMs (Ollama, LM Studio) via Cline
- [ ] Test auto-approve setup for CoDRAG tools
- [ ] Confirm: does Cline read AGENTS.md? (likely not natively)
- [ ] Test CoDRAG with Cline's plan-execute-verify loop
- [ ] Empirically test: what is `clientInfo.name` in Cline's initialize request?

---

## 6. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Local LLM tool-calling quality | HIGH | Smaller models may not reliably call CoDRAG. Rules file critical. |
| Model-agnostic tool descriptions needed | MEDIUM | CoDRAG descriptions already model-agnostic. |
| No native AGENTS.md support | LOW | `.clinerules` is the primary mechanism. AGENTS.md is a nice-to-have. |
| Cline's autonomous loop calls CoDRAG too often | LOW | CoDRAG has rate limiting. Tools are read-only. |

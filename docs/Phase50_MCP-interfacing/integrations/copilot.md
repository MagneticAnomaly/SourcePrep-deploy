# GitHub Copilot Integration Research

> How GitHub Copilot (agent mode + coding agent) consumes MCP, and how Prep should optimize for it.

**Status:** UPDATED with confirmed VS Code docs deep-dive
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | IDE extension (VS Code, JetBrains) + cloud coding agent |
| **Vendor** | GitHub / Microsoft |
| **Model** | GPT-4o, Claude Sonnet, Gemini (multi-model, user-selectable) |
| **MCP Spec** | Full (tools, resources, prompts, apps) in VS Code agent mode |
| **Transport** | stdio, SSE, Streamable HTTP |
| **MCP Config** | `.vscode/mcp.json` (workspace) or user profile `mcp.json` |
| **Rules File** | `.github/copilot-instructions.md` + `AGENTS.md` |
| **Sandboxing** | Yes (macOS/Linux) -- auto-approves sandboxed servers |
| **Market Share** | Largest AI coding assistant by install base |

---

## 2. Two Distinct Products

### Copilot Chat (Agent Mode)
- Runs inside VS Code
- Agent mode enables MCP tool usage
- User activates agent mode in chat panel
- MCP servers configured in VS Code settings

### Copilot Coding Agent (Cloud)
- Runs asynchronously in GitHub cloud
- Triggered from GitHub Issues or VS Code
- Can create PRs, run tests, deploy
- Reads `AGENTS.md` for project instructions
- MCP support for external tool access

### Key Distinction for Prep
- **Agent mode (local)**: Prep works via stdio MCP connection. Tools available in real-time.
- **Coding agent (cloud)**: Prep would need to be accessible remotely (HTTP transport) or the agent needs local access. This is a **deployment consideration** -- Prep currently runs as a local daemon.

---

## 3. MCP Implementation Details

### Agent Mode (VS Code) -- CONFIRMED FROM DOCS
- MCP tools available alongside Copilot's built-in tools
- **Config location:** `.vscode/mcp.json` in workspace (NOT VS Code settings JSON)
- **Config format uses `servers` key** (NOT `mcpServers`):
```json
{
  "servers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"]
    }
  }
}
```
- Also installable via CLI: `code --add-mcp "{\"name\":\"prep\",\"command\":\"prep\",\"args\":[\"mcp\"]}"`
- MCP server gallery: `@mcp` search in Extensions view discovers servers
- Supports MCP Apps (interactive UI views from tool responses)
- Supports MCP Prompts as slash commands: `/<server>.<prompt>`
- Dev Containers: can include MCP config in `devcontainer.json` via `customizations.vscode.mcp`
- Config sync: MCP servers can be synced across devices via Settings Sync

### Coding Agent (Cloud)
- Reads `AGENTS.md` for project context
- MCP support is newer and less documented
- The agent runs in a cloud container -- Prep daemon must be accessible

### Confirmation Model
- Agent mode: user approves tool calls in VS Code
- **Trust model**: First use of an MCP server prompts trust dialog. Must confirm before tools activate.
- **Sandboxing (macOS/Linux ONLY)**: `"sandboxEnabled": true` runs server in isolated environment
  - Restricts filesystem and network access to explicit allowlists
  - **When sandboxed, tool calls are auto-approved** (runs in controlled environment)
  - Prep config with sandboxing:
```json
{
  "servers": {
    "prep": {
      "command": "prep",
      "args": ["mcp"],
      "sandboxEnabled": true,
      "sandbox": {
        "filesystem": {
          "allowWrite": []
        },
        "network": {
          "allowedDomains": ["localhost"]
        }
      }
    }
  }
}
```
  - Prep is read-only, so empty `allowWrite` + localhost-only network is safe
  - **NOT available on Windows** -- Windows users still need manual approval
- **Enterprise**: Centrally managed MCP access via GitHub policies

---

## 4. Rules File: `.github/copilot-instructions.md`

### Format
Plain markdown in `.github/` directory. VS Code reads this for Copilot context.

### AGENTS.md Support
The coding agent reads `AGENTS.md`. This is the primary mechanism for the cloud agent.

### Prep Template
```markdown
## Prep Integration

This project is indexed by Prep for structural code intelligence.

When using MCP tools:
- Call `prep` at the start of every task for module structure and hub files
- Use `prep_search` for natural language code queries
- Use `prep_impact` before making changes

### Codebase Atlas
[auto-generated]
```

### Strategy
Generate both:
1. `AGENTS.md` section (for coding agent)
2. `.github/copilot-instructions.md` section (for agent mode in VS Code)

---

## 5. Native Tools Competition

| Copilot Native | Prep Equivalent | Competition |
|---------------|-------------------|-------------|
| `@workspace` search | `prep_search` | HIGH |
| File reading | `prep` hub content | MEDIUM |
| Terminal commands | N/A | NONE |
| Code generation | N/A | NONE |

Copilot's `@workspace` is a powerful semantic search over the entire workspace. Prep differentiates by providing *structural* context (trace graph, module relationships, blast radius) that `@workspace` cannot.

---

## 6. Cloud Agent Considerations

### Prep Deployment for Cloud Agents
The Copilot coding agent runs in GitHub's cloud. For Prep to work:
- **Option A**: Prep builds a static context snapshot that's committed to the repo (rules file with atlas)
- **Option B**: Prep runs as a remote MCP server (HTTP transport) accessible from GitHub's cloud
- **Option C**: The coding agent uses only the `AGENTS.md` atlas (no live MCP)

**Recommendation**: Option A + C for launch. The atlas in `AGENTS.md` gives the cloud agent structural awareness without requiring a live Prep daemon. Live MCP is a future enhancement.

---

## 7. Prep Optimization Checklist

- [x] MCP config format confirmed (`.vscode/mcp.json` with `servers` key)
- [x] Sandboxing confirmed (auto-approve for sandboxed servers, macOS/Linux)
- [x] MCP Prompts confirmed (slash commands: `/<server>.<prompt>`)
- [x] MCP Apps confirmed (interactive UI views)
- [x] Enterprise management confirmed (GitHub policies)
- [x] AGENTS.md confirmed (agents.md site lists GitHub Copilot coding agent)
- [ ] Verify `.github/copilot-instructions.md` injection behavior empirically
- [ ] Test sandboxing with Prep (localhost network access)
- [ ] Determine: can coding agent access local MCP servers?
- [ ] Test multi-model behavior (GPT-4o vs Claude vs Gemini with Prep tools)
- [ ] Empirically test: what is `clientInfo.name` in Copilot's initialize request?

---

## 8. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| Cloud agent can't access local Prep daemon | HIGH | Atlas in AGENTS.md provides offline structural context |
| `@workspace` makes Prep search seem redundant | MEDIUM | Prep offers structural relationships, not just content search |
| Multi-model inconsistency in tool usage | MEDIUM | Tool descriptions must be model-agnostic |
| Copilot evolves rapidly, breaking MCP integration | MEDIUM | Monitor GitHub Copilot changelog |
| **Sandboxing not available on Windows** | MEDIUM | Windows users need manual approval -- setup docs must cover both paths |
| `.vscode/mcp.json` config key is `servers` not `mcpServers` | LOW | Different from Cursor/Claude Code format. Setup docs must be exact. |

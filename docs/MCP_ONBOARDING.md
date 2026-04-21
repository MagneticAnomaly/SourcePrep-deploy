# MCP Onboarding Guide

This guide explains how to integrate CoDRAG with AI coding assistants using the Model Context Protocol (MCP).

## What is MCP?

The Model Context Protocol (MCP) is a standard that allows AI assistants to access external tools and data sources. CoDRAG provides an MCP server that gives your AI assistant semantic code search and context assembly capabilities.

## Supported Clients

CoDRAG's MCP server works with:

- **Claude Code** (Anthropic CLI)
- **Claude Desktop** (Anthropic)
- **Cursor**
- **Windsurf** (Codeium)
- **GitHub Copilot** (VS Code Agent Mode)
- **Gemini CLI** (Google)
- **Zed**, **Cline**, **Roo Code**, **Amp**, **OpenAI Codex**
- **Any MCP-compatible client**

## Quick Setup

### 1. Start CoDRAG Daemon

First, ensure CoDRAG is running:

```bash
codrag serve
```

### 2. Configure Your AI Assistant

Pick your tool below. All configs assume `codrag` is on your PATH — if not, use the absolute path to the binary (e.g. `/path/to/.venv/bin/codrag`).

> **Server mode (default)** connects to the running daemon at :8400 with full multi-project support. **Direct mode** (`--mode direct`) runs in-process without a daemon but only supports a single project and a reduced tool set.

#### Claude Code (CLI)

**Project-scoped** — add `.claude/mcp.json` to your project root:

```json
{
  "servers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  }
}
```

**Global** — add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  },
  "permissions": {
    "allow": ["mcp__codrag"]
  }
}
```

The `permissions.allow` line auto-approves all CoDRAG tools (they are read-only and safe). You can also add via CLI: `claude mcp add codrag -- codrag mcp`

CoDRAG also generates a `CLAUDE.md` file for your project that tells Claude Code about the available MCP tools, how to call them, and when to prefer them over grep/file reads.

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  }
}
```

#### Cursor

Add `.cursor/mcp.json` to your project root:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  }
}
```

#### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"],
      "disabled": false
    }
  }
}
```

#### GitHub Copilot (VS Code)

Add `.vscode/mcp.json` to your project root (**note: `servers`, not `mcpServers`**):

```json
{
  "servers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  }
}
```

#### Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"],
      "trust": true
    }
  }
}
```

#### Other Tools

CoDRAG works with any MCP-compatible client. Run `codrag mcp-config --ide all` to generate configs for all supported tools, or see the [full config reference](./Phase50_MCP-interfacing/MCP_CONFIGS.md).

### 3. Restart Your AI Assistant

After updating the configuration, restart your AI assistant to load the MCP server.

## Available Tools

CoDRAG exposes these tools to your AI assistant:

### `codrag`

Get structural codebase context — modules, hub files, focus areas. **Call this first at the start of every task.** No arguments required.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_id` | string | auto-detected | CoDRAG project ID |
| `role` | string | none | Role filter (e.g. `"security"`, `"design engineer"`, `"ceo"`) |
| `max_chars` | integer | auto | Max context size (auto-sized per client) |

Returns: Module summaries, hub files, cross-cutting concerns, focus areas, and optionally a role-filtered atlas view.

### `codrag_search`

Semantic code search — find code by intent, not just keywords.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Natural language search query |
| `type` | string | `"context"` | `"context"` for semantic search, `"symbol"` for symbol lookup |
| `k` | integer | 5 | Number of results |
| `max_chars` | integer | 12000 | Max response size |

Returns: Matching code chunks with file paths, scores, and previews.

### `codrag_impact`

Dependency impact analysis — understand blast radius before making changes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | string | — | File to analyze |
| `symbol` | string | — | Or a specific symbol name |
| `direction` | string | `"all"` | `"dependents"`, `"dependencies"`, or `"all"` |
| `max_hops` | integer | 3 | How far to follow the graph |

Returns: Dependency tree showing what depends on and what is depended on by the target.

### `codrag_audit`

Codebase health and tech debt analysis.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | string | `"scan"` | `"scan"`, `"refactor"`, `"verify"`, `"report"`, `"advise"` |
| `category` | string | none | Filter by category |
| `analyzers` | array | all | Specific analyzers to run |

Returns: Health findings, tech debt items, and actionable recommendations.

### `codrag_observe`

Cross-session memory — save and retrieve notes about the codebase.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `action` | string | required | `"save"` or `"get"` |
| `content` | string | — | Note content (for save) |
| `file_path` | string | — | Associate with a file |
| `category` | string | — | Categorize the observation |
| `query` | string | — | Search notes (for get) |

Returns: Saved confirmation or matching observations.

## Example Prompts

Once MCP is configured, your AI assistant can use CoDRAG automatically. Try prompts like:

### Code Search
> "Search for how authentication is implemented in this project"

### Context Assembly
> "Get context about the database models so you can help me add a new table"

### Understanding Architecture
> "What files are involved in the API routing?"

## Project Selection

### Automatic Detection

CoDRAG attempts to detect the current project based on your working directory. If you're inside a registered project's directory, it will be selected automatically.

### Manual Selection

If automatic detection fails or you want a different project:

```bash
# List projects
codrag list

# Set default project
export CODRAG_PROJECT_ID="proj_abc123"
```

Or configure in your MCP server env:

```json
{
  "env": {
    "CODRAG_API_URL": "http://127.0.0.1:8400",
    "CODRAG_PROJECT_ID": "proj_abc123"
  }
}
```

## Direct MCP Mode

For single-repository use without the daemon, CoDRAG supports direct MCP mode:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp", "--direct", "--repo", "/path/to/repo"],
      "env": {}
    }
  }
}
```

This embeds the index directly in the MCP server process—simpler but doesn't support multiple projects or the dashboard.

## Troubleshooting

### "DAEMON_UNAVAILABLE"

The CoDRAG daemon is not running or not reachable.

**Solution:**
```bash
# Check if daemon is running
curl http://127.0.0.1:8400/health

# Start if needed
codrag serve
```

### "PROJECT_NOT_FOUND"

No project is selected or the project ID is invalid.

**Solution:**
```bash
# List available projects
codrag list

# Add a project if needed
codrag add /path/to/repo
```

### "PROJECT_SELECTION_AMBIGUOUS"

Multiple projects match the current directory.

**Solution:**
- Set `CODRAG_PROJECT_ID` explicitly
- Or navigate to a more specific directory

### "INDEX_NOT_BUILT"

The project's index hasn't been built yet.

**Solution:**
```bash
codrag build
```

Or ask your AI assistant: "Build the CoDRAG index for this project"

### Tools Not Appearing

If CoDRAG tools don't appear in your AI assistant:

1. Check the MCP configuration path is correct
2. Verify the `codrag` command is in your PATH
3. Check assistant logs for MCP errors
4. Restart the assistant after config changes

## Best Practices

### 1. Keep Index Fresh

Enable auto-rebuild to keep your index up-to-date:

```bash
codrag watch start
```

### 2. Add a Primer File

Create `AGENTS.md` in your repo root with project context:

```markdown
# Project Context

## Tech Stack
- Python 3.10, FastAPI
- PostgreSQL, SQLAlchemy

## Architecture
- src/api/ - REST endpoints
- src/core/ - Business logic
- src/models/ - Database models
```

### 3. Tune Search Parameters

For large codebases, adjust search parameters:

```bash
# Increase result count for comprehensive searches
codrag config set default_k 10

# Lower threshold for broader matches
codrag config set default_min_score 0.1
```

### 4. Exclude Irrelevant Files

Keep the index focused:

```bash
codrag config set exclude_globs '["**/node_modules/**", "**/dist/**", "**/*.min.js"]'
```

### 5. Use Role-Aware Context with Agents

If you're running multiple AI agents (e.g., via Paperclip, CrewAI, or LangGraph), give each agent a focused context view:

```
codrag(role="security")          → auth, data access, infra
codrag(role="ux designer")       → components, design tokens, layouts
codrag(role="ceo")               → module summaries, health metrics
```

See the [Agentic Integration Guide](./AGENTIC_INTEGRATION_GUIDE.md) for framework-specific setup.

## Security Considerations

### Local-First

CoDRAG runs entirely locally. Your code never leaves your machine:

- Index is stored in `~/.prep/` or `.prep/` in your repo
- MCP communication happens over localhost
- No external API calls (except to local Ollama)

### Network Mode

If running CoDRAG in network mode (not default):

- Use HTTPS
- Set strong API keys
- Restrict bind address

## Related Documentation

- [Getting Started](./GETTING_STARTED.md) — Basic installation and usage
- [API Reference](./API.md) — HTTP API documentation
- [Role-Aware Context](./ROLE_AWARE_CONTEXT.md) — How CoDRAG shapes context per role
- [Agentic Integration Guide](./AGENTIC_INTEGRATION_GUIDE.md) — Using CoDRAG with Paperclip, CrewAI, and multi-agent frameworks
- [Error Codes](./ERROR_CODES.md) — Error handling reference
- [Budgets Policy](./BUDGETS_POLICY.md) — Understanding limits

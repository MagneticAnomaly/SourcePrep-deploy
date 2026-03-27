# CoDRAG MCP Setup Guide: Per-Tool Configuration

> Exact configuration, auto-approve setup, and rules file placement for every supported tool.
> This document is the source of truth for CoDRAG's setup documentation.

**Last updated:** 2026-03-14 (deep dive update)

---

## Universal Prerequisites

1. CoDRAG daemon running (`codrag serve` or via Tauri app)
2. CoDRAG index built for the project (`codrag build` or dashboard "Rebuild Knowledge Base")
3. CoDRAG binary path known (see below)

### CRITICAL: Absolute Path Required

MCP configs spawn a child process. The child process does **NOT** inherit your
shell PATH, nvm, pyenv, or conda environment. You **must** use the absolute
path to the `codrag` binary in all MCP configs.

**Find your path:**
```bash
which codrag                          # if installed system-wide
ls /path/to/CoDRAG/.venv/bin/codrag   # if using venv (dev setup)
```

**Dev setup example:** `/Volumes/4TB-BAD/HumanAI/CoDRAG/.venv/bin/codrag`

For ready-to-copy configs with your absolute path pre-filled, see:
**[MCP_CONFIGS.md](MCP_CONFIGS.md)** -- one JSON block per tool, copy-paste into the right file.

### Ollama Concurrency Requirement

If you are using **Ollama** as your local provider and you want the CoDRAG pipeline to run models in parallel, you **must set the `OLLAMA_NUM_PARALLEL` environment variable** before starting the Ollama server.

By default, Ollama queues all requests sequentially (one at a time), which will bottleneck CoDRAG's concurrent pipeline execution even if Cloud Concurrency is set > 1 in the UI.

**macOS/Linux:**
```bash
export OLLAMA_NUM_PARALLEL=4
ollama serve
```

**macOS App (Launchd):**
```bash
launchctl setenv OLLAMA_NUM_PARALLEL 4
```

**Systemd (Linux / WSL):**
Add `Environment="OLLAMA_NUM_PARALLEL=4"` to `/etc/systemd/system/ollama.service`.

### Multi-Project Routing

CoDRAG automatically detects which project to target for each MCP tool call.
In most cases, **zero configuration is needed** -- the MCP server resolves the
correct project from your IDE's workspace context.

**How auto-detection works (priority order):**

1. **`project_id` parameter** — explicitly passed per tool call (rarely needed)
2. **CLI `--project` flag** — `codrag mcp --project <id>` pins a project for the session
3. **Workspace roots** — your IDE sends workspace folder URIs during the MCP handshake; CoDRAG matches these against registered project paths
4. **CWD** — if launched from within a project directory, that project is used
5. **`CODRAG_PROJECT` env var** — match by project name or ID
6. **Single-project shortcut** — if only one project exists, it's used automatically
7. **Most-recently-active** — falls back to the project with the most recent build/update

**`.codrag` auto-registration:** If your workspace root or CWD contains a `.codrag/`
folder (created by `codrag init`), the MCP server will automatically register it
as an embedded project — no manual `codrag add` needed.

**Pinning a specific project** (for users with multiple active projects):

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"],
      "env": {
        "CODRAG_PROJECT": "MyProjectName"
      }
    }
  }
}
```

For the full routing architecture, see [PROJECT_ROUTING.md](PROJECT_ROUTING.md).

---

## 1. Cursor (VS Code Fork)

### MCP Server Config
Location: `.cursor/mcp.json` (project root) or user settings

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"]
    }
  }
}
```
Replace `/path/to/.venv/bin/codrag` with your absolute path (see Prerequisites).

### Auto-Approve
**WARNING: YOLO mode does NOT auto-approve MCP tools.**

Steps:
1. Open Settings (Cmd+,)
2. Search "MCP"
3. Find the codrag server
4. Enable "Auto-run" for the codrag server specifically

### Rules File
**File:** `.cursor/rules/codrag.mdc`

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
- Hub files (most connected/important files with full content)
- User's selected focus areas from the knowledge base

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes, use `codrag_impact` to understand blast radius.

CoDRAG's tools are read-only and safe to auto-approve.

## Codebase Atlas
[auto-generated from atlas.json]

## Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [node_count] nodes, [edge_count] edges
```

### Also Generate
- `AGENTS.md` section (Cursor reads AGENTS.md too)

---

## 2. Windsurf / Cascade

### MCP Server Config
Location: `~/.codeium/windsurf/mcp_config.json` (global, applies to all projects)

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"],
      "disabled": false
    }
  }
}
```
Replace `/path/to/.venv/bin/codrag` with your absolute path.

### Auto-Approve
1. Click MCPs icon in Cascade panel top-right
2. Click on the codrag server
3. Enable auto-run / auto-approve

### Rules File
**File:** `.windsurf/rules/codrag.md`

```markdown
---
trigger: always_on
description: CoDRAG structural codebase intelligence
---

You have access to CoDRAG, a structural code intelligence system that
understands this codebase through a trace graph of imports, calls, and
structural relationships.

ALWAYS call `codrag` (no arguments) at the START of every task. This gives you:
- Module structure (which groups of files work together and their dependencies)
- Hub files (most connected/important files with full content)
- User's selected focus areas from the knowledge base

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes, use `codrag_impact` to understand blast radius.

CoDRAG's tools are read-only and safe to auto-approve.

## Codebase Atlas
[auto-generated from atlas.json]

## Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [node_count] nodes, [edge_count] edges
```

### Also Generate
- `AGENTS.md` section (Windsurf treats root AGENTS.md as always-on)

### Note
`.windsurfrules` is legacy. The current system uses `.windsurf/rules/*.md` with
YAML frontmatter. Windsurf has a **100-tool limit** across all MCP servers.

---

## 3. Claude Code (CLI)

### MCP Server Config
Location: `~/.claude/settings.json` (user) or `.claude/settings.json` (project)

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"]
    }
  },
  "permissions": {
    "allow": ["mcp__codrag"]
  }
}
```

The `permissions.allow` line auto-approves ALL CoDRAG tools.

Or add via CLI: `claude mcp add codrag -- /path/to/.venv/bin/codrag mcp`

### Auto-Approve
**Single rule auto-approves ALL CoDRAG tools:**

In `.claude/settings.json` (project-level) or `~/.claude/settings.json` (user-level):
```json
{
  "permissions": {
    "allow": ["mcp__codrag"]
  }
}
```

Alternatively: `/permissions` command in Claude Code, then add `mcp__codrag` to allow list.

**Permission syntax reference:**
```
mcp__codrag              -- ALL tools from codrag server
mcp__codrag__*           -- wildcard, same effect
mcp__codrag__codrag      -- only the codrag tool
mcp__codrag__codrag_search  -- only codrag_search
```

### Rules File
**File:** `CLAUDE.md` (append CoDRAG section)

```markdown
<!-- CODRAG:BEGIN (auto-generated, do not edit between markers) -->
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
[auto-generated from atlas.json]

### Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [stats]
<!-- CODRAG:END -->
```

### Important: Append, Don't Overwrite
CLAUDE.md is user-owned. CoDRAG only modifies content between `CODRAG:BEGIN` / `CODRAG:END` markers.

### Optional: CoDRAG Skill
**File:** `.claude/skills/codrag-context.md`
```markdown
---
description: Get structural codebase context from CoDRAG
tools: ["mcp__codrag__codrag", "mcp__codrag__codrag_search"]
---
Call `codrag` to get the structural overview of this codebase,
then use that context to inform your approach to the current task.
```
Creates `/codrag-context` slash command.

### Claude Code Gotchas
- **MCP Tool Search**: If you have many MCP servers, Claude may defer CoDRAG tools.
  CLAUDE.md mitigates this. Or disable deferral: `ENABLE_TOOL_SEARCH=false claude`
- **Output limit**: 25,000 tokens max per tool response (CoDRAG is 250-3K, no issue)
- **Compaction**: `/compact` summarizes early tool responses. Atlas in CLAUDE.md survives.

---

## 4. GitHub Copilot (VS Code Agent Mode)

### MCP Server Config
Location: `.vscode/mcp.json` (workspace)

**NOTE: Uses `servers` key, NOT `mcpServers`**

```json
{
  "servers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"]
    }
  }
}
````

### Auto-Approve

**Option A: Sandboxing (macOS/Linux only, recommended)**
```json
{
  "servers": {
    "codrag": {
      "command": "codrag",
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
Sandboxed servers are auto-approved. CoDRAG is read-only, so empty write + localhost is safe.

**Option B: Trust Dialog (all platforms)**
First use prompts trust dialog. Once trusted, tools still require per-call approval.
No documented way to auto-approve MCP tools without sandboxing.

**NOT available on Windows** -- Windows users must approve each tool call.

### Rules File
**File:** `.github/copilot-instructions.md`

```markdown
<!-- CODRAG:BEGIN -->
## CoDRAG Integration

This project uses CoDRAG for structural code intelligence via MCP.
ALWAYS call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for code queries. Use `codrag_impact` before changes.

### Codebase Atlas
[auto-generated]

### Focus Areas
[auto-generated]

Last indexed: [timestamp] | [stats]
<!-- CODRAG:END -->
```

### Also Generate
- `AGENTS.md` section (Copilot coding agent reads this in cloud)

### Copilot Coding Agent (Cloud)
The cloud agent reads `AGENTS.md` but **cannot access local CoDRAG daemon**.
Atlas in AGENTS.md is the only structural context for cloud builds.

---

## 5. Gemini CLI

### MCP Server Config
Location: `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"],
      "trust": true
    }
  }
}
```

`trust: true` bypasses all confirmation dialogs. Safe for CoDRAG (read-only).

### Auto-Approve
Setting `"trust": true` in config handles this. No separate step needed.

### MCP Server Instructions (AUTOMATIC)
Gemini CLI appends MCP server `instructions` to the system prompt automatically.
CoDRAG's instructions field (set in MCP initialize response) provides:
```
CoDRAG provides structural codebase context via trace graph analysis.
Call `codrag` at the start of every coding task for module structure,
hub files, and focus areas. Use `codrag_search` for code queries with
structural expansion. Use `codrag_impact` before changes. All tools
are read-only. Categories: code intelligence, architecture, dependencies.
```

### Rules File
**Option A:** Configure Gemini to read `AGENTS.md`:
```json
{
  "context": {
    "fileName": "AGENTS.md"
  }
}
```

**Option B:** Use `GEMINI.md` if the user wants separate Gemini-specific instructions.

### Resources
Gemini CLI auto-discovers MCP resources. User accesses via `@resource` syntax.
CoDRAG should implement:
- `codrag://atlas` -- structural overview
- `codrag://health` -- index freshness check

### Prompts
Gemini CLI exposes MCP prompts as slash commands.
CoDRAG should implement:
- `/codrag-overview` -- full structural context
- `/codrag-review` -- structural review prompt

---

## 6. Cline (VS Code Extension)

### MCP Server Config
1. Click MCP Servers icon in Cline sidebar
2. Select "Configure" tab
3. Click "Configure MCP Servers"
4. Edit `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"]
    }
  }
}
```

### Auto-Approve
Cline has per-tool auto-approval. Enable via:
1. Settings > Advanced > Auto-Approve settings
2. Or use the auto-approve toggle in Cline's UI when prompted

See: https://docs.cline.bot/features/auto-approve

### Rules File
**File:** `.clinerules` (project root)

```markdown
## CoDRAG Structural Context

This project uses CoDRAG for structural code intelligence via MCP.
ALWAYS call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for code queries with structural trace expansion.
Use `codrag_impact` before making changes to understand dependencies.

When asked about code structure, architecture, dependencies, modules,
hub files, or blast radius, use the CoDRAG MCP tools.

### Codebase Atlas
[auto-generated]

### Focus Areas
[auto-generated]

Last indexed: [timestamp] | [stats]
```

### Local LLM Note
Cline is popular with Ollama/LM Studio users. For local models:
- Keep rules content short and direct
- CoDRAG's compact 250-token response is critical
- Tool descriptions must be simple and unambiguous

---

## 7. Roo Code (VS Code Extension)

### MCP Server Config
Via VS Code settings or `mcp_settings.json`:

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"]
    }
  }
}
```

### Auto-Approve
Per-server auto-approve available in Roo Code settings.

### Rules Files (3 files for full mode support)

**General (all modes):** `.roo/rules/codrag.md`
```markdown
# CoDRAG Structural Intelligence

This project uses CoDRAG for structural code intelligence via MCP.
ALWAYS call `codrag` at the start of every task for module structure and hub files.
Use `codrag_search` for natural language code queries.
Use `codrag_impact` before making changes to understand blast radius.

When asked about code structure, architecture, dependencies, modules,
hub files, or blast radius, use the CoDRAG MCP tools.

## Codebase Atlas
[auto-generated]

## Focus Areas
[auto-generated]
```

**Architect mode:** `.roo/rules-architect/codrag.md`
```markdown
# CoDRAG for Architecture Analysis

In Architect mode, CoDRAG is your primary structural intelligence tool.
ALWAYS call `codrag` first for comprehensive module overview.
Use `codrag_audit` for codebase health assessment.
Use `codrag_search` to explore specific module relationships.
```

**Code mode:** `.roo/rules-code/codrag.md`
```markdown
# CoDRAG for Coding

Before making changes, call `codrag_impact` to understand blast radius.
Call `codrag` for module context when entering an unfamiliar area.
```

### AGENTS.md
Roo Code reads `AGENTS.md` by default (disableable via `roo-cline.useAgentRules: false`).
CoDRAG's AGENTS.md section provides universal fallback.

---

## 8. Qwen Code (CLI)

### MCP Server Config
Mirrors Gemini CLI format. In `~/.qwen/settings.json` (or equivalent):

```json
{
  "mcpServers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"],
      "trust": true
    }
  }
}
```

### Rules File
Use `AGENTS.md` (universal). Qwen Code reads AGENTS.md natively.

---

## 8b. Zed

### MCP Server Config
Location: `~/.config/zed/settings.json` or project `.zed/settings.json`

**NOTE: Uses `context_servers` key (different from other tools)**

```json
{
  "context_servers": {
    "codrag": {
      "command": "/path/to/.venv/bin/codrag",
      "args": ["mcp"]
    }
  }
}
```
Replace `/path/to/.venv/bin/codrag` with your absolute path. Zed uses flat `command`/`args` keys (not nested).

### Rules File
Zed reads AGENTS.md and `.rules` files automatically.

---

## 9. AGENTS.md (Universal)

**This is the single highest-ROI file.** 20+ tools read it.

### File: `AGENTS.md` (project root, marker-based section)

```markdown
<!-- CODRAG:BEGIN (auto-generated, do not edit between markers) -->
## CoDRAG Integration

This project is indexed by CoDRAG for structural code intelligence.

### Quick Start
- Call `codrag` (MCP tool) at the start of every task
- Use `codrag_search` for code queries with structural context
- Use `codrag_impact` before making changes

### Codebase Atlas
[auto-generated from atlas.json -- IDENTITY, STACK, ARCHITECTURE, SUBSYSTEMS, FLOW]

### Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [node_count] nodes, [edge_count] edges | [coverage]% coverage
<!-- CODRAG:END -->
```

### Who reads AGENTS.md (confirmed)
Cursor, Windsurf, Claude Code, GitHub Copilot (coding agent), Gemini CLI,
Qwen Code, Roo Code, Zed, Amp, OpenAI Codex, Jules, Devin, Junie, Kilo Code,
Goose, Warp, Augment Code, Factory.ai, Semgrep, Phoenix, opencode, UiPath

### Stewardship
AGENTS.md is stewarded by the **Agentic AI Foundation** under the **Linux Foundation**.
Used by 60,000+ open-source projects. Case-insensitive (`AGENTS.md` or `agents.md`).

---

## Config Key Differences (Critical Reference)

| Tool | Config File | Server Key | Notes |
|------|------------|------------|-------|
| **Cursor** | `.cursor/mcp.json` | `mcpServers` | |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | 100-tool limit |
| **Claude Code** | `~/.claude/settings.json` | `mcpServers` | + permissions block |
| **Copilot (VS Code)** | `.vscode/mcp.json` | **`servers`** | Different key! |
| **Gemini CLI** | `~/.gemini/settings.json` | `mcpServers` | + `trust` field |
| **Cline** | `cline_mcp_settings.json` | `mcpServers` | |
| **Roo Code** | `mcp_settings.json` | `mcpServers` | |

### Auto-Approve Methods

| Tool | Method | Platform Notes |
|------|--------|---------------|
| **Cursor** | Per-server MCP auto-run in Settings | YOLO mode does NOT cover MCP |
| **Windsurf** | Per-server toggle in MCP panel | |
| **Claude Code** | `"allow": ["mcp__codrag"]` in settings | Single rule covers all tools |
| **Copilot** | Sandboxing (`sandboxEnabled: true`) | macOS/Linux only |
| **Gemini CLI** | `"trust": true` in server config | |
| **Cline** | Per-tool auto-approve toggle | |
| **Roo Code** | Per-server auto-approve | |

### Rules File Paths

| Tool | Path | Format |
|------|------|--------|
| **Cursor** | `.cursor/rules/codrag.mdc` | YAML frontmatter (`alwaysApply: true`) |
| **Windsurf** | `.windsurf/rules/codrag.md` | YAML frontmatter (`trigger: always_on`) |
| **Claude Code** | `CLAUDE.md` (append section) | Plain markdown with markers |
| **Copilot** | `.github/copilot-instructions.md` | Plain markdown |
| **Gemini CLI** | `AGENTS.md` (via context config) | Plain markdown |
| **Cline** | `.clinerules` | Plain markdown with keyword triggers |
| **Roo Code** | `.roo/rules/codrag.md` + mode dirs | Plain markdown |
| **Universal** | `AGENTS.md` | Plain markdown with markers |

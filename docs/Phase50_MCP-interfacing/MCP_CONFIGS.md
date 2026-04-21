# Prep MCP Configuration: Copy-Paste Reference

> Ready-to-use MCP config JSON for every supported AI coding tool.
> Each config is self-contained -- copy the entire block into the correct file.

**Your Prep binary:** `/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep`

**IMPORTANT:** MCP configs spawn a child process. The child process does NOT
inherit your shell's PATH, nvm, pyenv, or conda. You MUST use the absolute
path to the `prep` binary. If you install Prep system-wide later, you
can simplify to just `"command": "prep"`.

---

## Quick Fix: Your Windsurf Config

Your current `~/.codeium/windsurf/mcp_config.json` points to a mock script.
Replace its contents with:

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"],
      "disabled": false
    }
  }
}
```

---

## 1. Cursor

**File:** `.cursor/mcp.json` (in your project root)

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

**Auto-approve:** Settings > Features > MCP > enable auto-run for prep.
(YOLO mode does NOT cover MCP tools.)

---

## 2. Windsurf / Cascade

**File:** `~/.codeium/windsurf/mcp_config.json` (global, applies to all projects)

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"],
      "disabled": false
    }
  }
}
```

**Auto-approve:** Click MCPs icon in Cascade panel > click prep > enable auto-run.

---

## 3. Claude Code (CLI)

**File:** `~/.claude/settings.json`

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  },
  "permissions": {
    "allow": ["mcp__prep"]
  }
}
```

The `permissions.allow` line auto-approves ALL Prep tools with a single rule.

**Alternative (CLI):** `claude mcp add prep -- /Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep mcp`

---

## 4. GitHub Copilot (VS Code Agent Mode)

**File:** `.vscode/mcp.json` (in your project root)

**NOTE: Uses `servers` key, NOT `mcpServers`!**

```json
{
  "servers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

**Auto-approve (macOS/Linux only -- sandbox mode):**

```json
{
  "servers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"],
      "sandboxEnabled": true,
      "sandbox": {
        "filesystem": { "allowWrite": [] },
        "network": { "allowedDomains": ["localhost"] }
      }
    }
  }
}
```

---

## 5. Gemini CLI / Antigravity

Gemini CLI and Antigravity use the same MCP format but **different config file paths**.

### Gemini CLI

**File:** `~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"],
      "trust": true
    }
  }
}
```

### Antigravity

**File:** `~/.gemini/antigravity/mcp_config.json`

> **IMPORTANT:** Antigravity does not send workspace roots and launches with `cwd=/`.
> You MUST set `PREP_WORKSPACE` to the project root for correct routing.

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"],
      "env": {
        "PREP_WORKSPACE": "/path/to/your/project"
      },
      "trust": true
    }
  }
}
```

`trust: true` auto-approves all tool calls. Safe for Prep (read-only).

### Troubleshooting: "server name prep not found"

This means the stdio process launched but the MCP handshake failed. Check:
1. **Prep daemon must be running** on port 8400: `curl http://127.0.0.1:8400/health`
2. **Test the MCP server directly:**
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","clientInfo":{"name":"test"}}}' | /Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep mcp
   ```
   You should see a JSON response with `"serverInfo":{"name":"prep"}`. If you get a Python error or nothing, the binary isn't working.
3. **Check stderr output:** The MCP server prints startup info to stderr. Run manually to see errors:
   ```bash
   /Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep mcp --debug 2>&1 | head -5
   ```

---

## 6. Zed

**File:** Zed settings (`~/.config/zed/settings.json` or project `.zed/settings.json`)

```json
{
  "context_servers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

Zed uses `context_servers` with flat `command`/`args` keys (not `mcpServers`, not nested `command.path`). Reads AGENTS.md automatically.

---

## 7. Cline (VS Code Extension)

**File:** Open Cline sidebar > MCP Servers > Configure > `cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

**Auto-approve:** Toggle per-tool auto-approve in Cline's UI when prompted.

---

## 8. Roo Code (VS Code Extension)

**File:** `mcp_settings.json` (via Roo Code settings)

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

---

## 9. Amp (Sourcegraph)

Amp reads AGENTS.md. For explicit MCP config, use the standard format:

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

---

## 10. OpenAI Codex (CLI)

Codex reads AGENTS.md natively. For explicit MCP:

```json
{
  "mcpServers": {
    "prep": {
      "command": "/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep",
      "args": ["mcp"]
    }
  }
}
```

---

## Config Key Cheat Sheet

| Tool | Config File | Server Key | Special |
|------|------------|------------|---------|
| Cursor | `.cursor/mcp.json` | `mcpServers` | |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | `disabled` field |
| Claude Code | `~/.claude/settings.json` | `mcpServers` | + `permissions` block |
| Copilot | `.vscode/mcp.json` | **`servers`** | Different key! |
| Gemini CLI | `~/.gemini/settings.json` | `mcpServers` | + `trust` field |
| Antigravity | `~/.gemini/antigravity/mcp_config.json` | `mcpServers` | + `trust` field |
| Zed | `~/.config/zed/settings.json` | **`context_servers`** | Flat `command`/`args` |
| Cline | `cline_mcp_settings.json` | `mcpServers` | |
| Roo Code | `mcp_settings.json` | `mcpServers` | |

---

## Troubleshooting

### "command not found" or server won't start
The MCP host spawns `prep` as a child process. It does NOT use your shell
PATH. Use the absolute path: `/Volumes/4TB-BAD/HumanAI/Prep/.venv/bin/prep`

### For system-wide install (future)
Once Prep is installed via pip/brew/binary, you can simplify all configs to:
```json
"command": "prep",
"args": ["mcp"]
```

### Prep daemon must be running
The MCP server (stdio mode) connects to the Prep daemon at `http://127.0.0.1:8400`.
Start it first:
```bash
cd /Volumes/4TB-BAD/HumanAI/Prep
.venv/bin/python -m prep serve
```

### Verify MCP is working
Enable logging to see what the MCP server receives:
```json
"args": ["mcp", "--log-file", "~/.prep/mcp.log", "--debug"]
```
Then check: `tail -f ~/.prep/mcp.log`

### Multiple projects
Prep auto-detects which project you're working on from the workspace root.
If it can't determine the project, it returns an actionable error with the
project list. You can pin a project with:
```json
"args": ["mcp", "--project", "YOUR_PROJECT_ID"]
```

# MCP Project Routing: Research & Implementation

## Problem Statement

When a user configures CoDRAG as an MCP server, every tool call must resolve **which project** to query. This must work automatically — the user adds the MCP JSON and it just works.

**Goal:** Zero-config for >95% of users.

---

## Architecture

### Data Flow

```
┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│  AI Client   │  stdio/   │  MCP Server  │  HTTP/    │   CoDRAG     │
│  (Cursor,    │  JSON-RPC │  (server.py) │  REST     │   Daemon     │
│  Claude,etc) ├──────────►│  per-session │──────────►│  (port 8400) │
│              │           │              │           │              │
│  Sends:      │           │  Resolves:   │           │  Stores:     │
│  - roots     │           │  - project   │           │  - registry  │
│  - rootUri   │           │    auto-det  │           │  - indexes   │
│  - cwd       │           │              │           │  - activity  │
└──────────────┘           └──────────────┘           └──────────────┘
```

### Resolution Priority (`_resolve_project_id`)

```
1. Pointer check (.codrag/project.json)             ← instant, absolute priority
2. Tool-call override (project_id param)            ← explicit per-call
3. CLI pinned (codrag mcp --project <id>)           ← session-level
4. Active project signal (~/.codrag/active...)      ← dashboard click sync
5. Initialize roots (workspace URIs from client)    ← IDE handshake
6. CWD (process working directory)                  ← runtime
7. CODRAG_PROJECT env var                           ← config-time
8. Single-project shortcut (only 1 project)         ← trivial case
9. Most-recently-active (updated_at timestamp)      ← last-resort
10. PROJECT_SELECTION_AMBIGUOUS error
```

### How It Decides

`_best_project_match` uses **path matching only**:
- Exact match: highest priority
- CWD is subfolder of project: high priority 
- Project is subfolder of CWD: lower priority
- `cwd=/` is skipped entirely (root FS is not a useful signal)

**The daemon filters which projects are candidates** via `activity_status`. Only `active` and `inactive` projects are served. Frozen/locked projects are excluded. This is the toggle in the dashboard UI.

### What Clients Send (empirical)

| Client | `roots` array | `rootUri` | `workspaceFolders` | `cwd` |
|--------|--------------|-----------|-------------------|-------|
| Cursor | ❌ | ✅ workspace root | ✅ | Workspace root |
| Windsurf | ❌ | ✅ workspace root | ✅ | Workspace root |
| Claude Code | ✅ file:// URIs | ❌ | ❌ | User's shell CWD |
| Gemini CLI | ✅ file:// URIs | ❌ | ❌ | User's shell CWD |
| Antigravity | ❌ | ❌ | ❌ | `/` (root FS) |
| Cline (VS Code) | ❌ | ✅ | ✅ | Workspace root |

---

## `.codrag/project.json` — Universal Pointer

### How It Works

Every CoDRAG project now gets a `.codrag/project.json` pointer in its root:

```json
{
  "id": "1d6f0b35-45cb-427b-ae9d-aac3c6371a4b",
  "mode": "embedded",
  "daemon": "http://127.0.0.1:8400"
}
```

**Created by:** `ProjectRegistry.add_project()` (via `ensure_codrag_pointer()`)
**Read by:** MCP server step 2b in `_resolve_project_id()` (via `read_codrag_pointer()`)

### What It Solves

| Mode | Index lives at | `.codrag/` in root | Routing |
|------|---------------|----------------------------|---|
| `standalone` | `~/.local/share/codrag/projects/<id>/` | ✅ pointer only | MCP reads pointer → instant |
| `embedded` | `<project-root>/.codrag/` | ✅ pointer + full index | MCP reads pointer → instant |
| `custom` | User-specified path | ✅ pointer only | MCP reads pointer → instant |

### Key Properties

- **Minimal:** Just `{id, mode, daemon}` — 3 fields
- **Instant:** MCP server reads the pointer before querying the daemon
- **Safe:** `ensure_codrag_pointer` is wrapped in try/except — non-fatal on read-only FS
- **Idempotent:** Safe to call multiple times, overwrites with current values
- **Git-friendly:** Can be committed to share project ID with team members

---

## Implemented Changes

| Change | File | Description |
|--------|------|-------------|
| `.codrag/project.json` pointer | `project_registry.py` | Created on `add_project()` for all modes |
| `read_codrag_pointer()` | `project_registry.py` | Reads pointer from any directory |
| Pointer-first routing | `server.py` | Step 2b: reads pointer before daemon query |
| Path-only scoring | `server.py` | `_best_project_match` uses only filesystem paths |
| Skip `cwd=/` | `server.py` | Root FS paths are skipped in scoring loop |
| `CODRAG_PROJECT` env var | `server.py` | Pin project by name or ID via MCP config |
| Recently-active fallback | `server.py` | Uses `updated_at` timestamp as last resort |
| `.codrag` auto-register | `server.py` | Workspace roots with `.codrag/` auto-registered |
| Docs | `SETUP_GUIDE.md` | Multi-Project Routing section |

---

*Created: 2026-03-25 as part of Phase55 audit*
*Related: Phase50 MCP Interfacing, `server.py::_resolve_project_id`*

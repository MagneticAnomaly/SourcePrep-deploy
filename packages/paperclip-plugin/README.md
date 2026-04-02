# @codrag/paperclip-plugin

CoDRAG codebase intelligence plugin for [Paperclip](https://paperclip.ing).

Gives every Paperclip agent structural codebase knowledge — module maps, dependency graphs, semantic search, and health analysis.

## Installation

```bash
pnpm paperclipai plugin install @codrag/paperclip-plugin
```

**Requires:** CoDRAG desktop app running (daemon at localhost:8400).

## Tools

Once installed, all Paperclip agents can use these tools during their runs:

| Tool | What |
|------|------|
| `codrag:context` | Structural overview (modules, hubs, atlas) |
| `codrag:search` | Semantic code search with trace expansion |
| `codrag:impact` | Dependency/dependent analysis (blast radius) |
| `codrag:audit` | Codebase health findings |
| `codrag:observe` | Save cross-session observations |

## UI

- **Dashboard Widget** — Codebase health metrics (readiness, roles, runs)
- **Agent Detail Tab** — Knowledge Scope file list per agent
- **Settings Page** — Connection status and tool reference

## Configuration

Set in Paperclip Plugin Settings:

| Key | Default | Description |
|-----|---------|-------------|
| `daemon_url` | `http://127.0.0.1:8400` | CoDRAG daemon URL |
| `project_id` | (auto-detected) | CoDRAG project ID |
| `auto_context` | `true` | Auto-attach context to new issues |

## Development

```bash
npm install
npm run build
npm run dev  # watch mode
```

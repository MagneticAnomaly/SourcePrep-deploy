<p align="center">
  <img src="codrag-github-header.png" alt="CoDRAG" width="100%">
</p>

# @codrag/paperclip-plugin

> Give every Paperclip agent deep structural codebase knowledge.

**CoDRAG** indexes your codebase with embeddings, a structural graph, and epistemic analysis. This plugin makes that intelligence available to **every agent** in your Paperclip instance — no per-agent configuration needed.

## The Problem

AI agents working on code operate blind. They grep files, read READMEs, and hope they stumble onto the right architecture. When they modify a file, they don't know what depends on it. When they search for code, they match keywords instead of meaning. When they finish a task, the next agent starts from scratch.

## The Solution

CoDRAG pre-computes your codebase's structural graph — modules, dependencies, hub files, domain clusters — and serves it on demand. The Paperclip plugin registers 5 tools that any agent can call during their runs:

| Tool | What It Does |
|------|-------------|
| `codrag:context` | Structural overview — modules, hub files, atlas. Call at the start of every task. |
| `codrag:search` | Semantic code search. Finds code by meaning, with structural trace expansion. |
| `codrag:impact` | Blast radius analysis. See exactly what depends on a file before changing it. |
| `codrag:audit` | Codebase health findings — tech debt, dead code, architecture issues. |
| `codrag:observe` | Cross-session memory. Agents save observations for the next agent. |

## Why This Is Novel

This is **epistemic-first agent orchestration** — instead of agents discovering codebase structure through trial and error, CoDRAG pre-computes it and serves it on demand:

- **Pre-computed structure** — Module clusters, import chains, and hub files are already indexed
- **Role-scoped context** — Backend agents see backend files. Frontend agents see frontend files
- **Impact-aware changes** — Agents know the blast radius before modifying code
- **Persistent memory** — Observations survive across agent runs and sessions

## Installation

### Prerequisites

1. **CoDRAG Desktop App** — Download from [codrag.io](https://codrag.io). The daemon must be running. 
2. **A CoDRAG project** — `codrag add /path/to/your/repo`
3. **A Paperclip instance** — Running locally or deployed

### Install

```bash
pnpm paperclipai plugin install @codrag/paperclip-plugin
```

### Configure

In Paperclip Settings → Plugins → CoDRAG:

| Setting | Default | Description |
|---------|---------|-------------|
| `daemon_url` | `http://127.0.0.1:8400` | CoDRAG daemon URL |
| `project_id` | *(auto-detected)* | CoDRAG project ID. Auto-detects if you have one project. |
| `auto_context` | `true` | Automatically enrich new issues with CoDRAG context |

## Dashboard Extensions

The plugin adds UI components directly into Paperclip:

- **Codebase Health Widget** — Readiness score, role count, research runs at a glance
- **Agent Knowledge Scope Tab** — Which files CoDRAG assigned to each agent's role
- **Issue Context Tab** — Structural context for issues created from audit findings
- **Settings Page** — Connection status and tool reference

## Architecture

```
Paperclip (orchestration)
    ↓ agent calls codrag:search during run
CoDRAG Plugin (JSON-RPC worker)
    ↓ proxies to HTTP API
CoDRAG Daemon (localhost:8400)
    ↓ queries
Sovereign Index (embeddings + graph + atlas)
```

The plugin runs as an **out-of-process worker** communicating via JSON-RPC over stdio. It has no direct database access — all data flows through the CoDRAG daemon's HTTP API. Worker failure is isolated and doesn't affect other plugins or Paperclip core.

## Capabilities Required

```
agent.tools.register       — Register the 5 codrag:* tools
projects.read              — Read project context for routing
issues.read                — Read issues to provide context
agents.read                — Read agent roles for scoped context
events.subscribe           — React to agent/issue lifecycle events
jobs.schedule              — Scheduled reindex health checks
http.outbound              — Call CoDRAG daemon API
plugin.state.read/write    — Cache project-agent mappings
ui.dashboardWidget.register — Codebase health widget
ui.detailTab.register       — Agent + issue detail tabs
ui.page.register            — Settings page
```

## Development

```bash
# Install dependencies
npm install

# Build (worker + manifest + UI bundles)
npm run build

# Watch mode
npm run dev

# Type check
npm run typecheck
```

### Local development with Paperclip

```bash
# Install from local path
pnpm paperclipai plugin install ./packages/paperclip-plugin-codrag

# Or use the dev server (hot reload)
npx paperclip-plugin-dev-server
```

## Documentation

Full documentation at [docs.codrag.io/mcp/paperclip](https://docs.codrag.io/mcp/paperclip).

## License

MIT

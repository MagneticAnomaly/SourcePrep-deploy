# Phase 69 — Public Release Strategy (code_index)

## Goal
Release the `code_index` module as a standalone GitHub repo that others can:
- Use as a git submodule in their projects
- Run against any codebase for local RAG
- Integrate with their own MCP-compatible IDE (Windsurf, etc.)

## Naming
- **Public name**: `code-index` (or `codrag`)
- **Internal name**: `codrag`

## Core features for v1.0 release
- [x] Semantic search via Ollama embeddings
- [x] Hybrid search (vector + FTS5 keyword)
- [x] Configurable roots, include/exclude globs, file size limits
- [x] MCP stdio server for IDE integration
- [x] Standalone HTTP server (FastAPI)
- [ ] Standalone HTML UI for index management (in progress)

### Context window / limits (important for UX)
There are multiple, independent limits that shape how “big” the system can think:

- **LLM context window (tokens)**
  - This is configured in the chat model/runtime.
  - Current value: `8192` tokens.
  - This is the *hard ceiling* for the final prompt sent to the chat model.

- **RAG retrieval context cap (characters)**
  - The `/projects/{id}/context` endpoint has a default `max_chars=6000`.
  - This is an *application-level safety/UX limit* to avoid injecting too much retrieved text.
  - It can be overridden per request by passing `max_chars`.

- **Chunking limits (characters)**
  - `chunk_markdown` / `chunk_text` default to roughly `max_chars=1800` per chunk.
  - This shapes recall granularity: smaller chunks can improve precision but increase index size.

---

## Future research: Automated code tracing

### Concept
Automatically trace code relationships during indexing:
- **Call graphs**: which functions call which
- **Import graphs**: module dependencies
- **Type flow**: how data moves through the codebase

### Why this matters
Current chunking is "dumb" — it splits by size/headings without understanding code structure. Tracing would let us:
- Retrieve not just the function, but its callers/callees
- Understand "what would break if I change this?"
- Build richer context for LLM queries

### Implementation ideas
- **Tree-sitter**: parse AST, extract function definitions + calls
- **LSP integration**: leverage existing language servers for type info
- **Incremental updates**: only re-trace changed files

### Status
**Research only** — not started

---

## Standalone UI: Index Manager

### Goal
A simple HTML page (no React build required) that lets users:
- View current indexed roots
- Add/remove "working roots" (task-specific folders)
- Trigger rebuilds
- Persist core vs working roots config

### UI roadmap
- **Split-screen layout**
  - Left: very tall, scrollable folder tree of roots.
  - Right: status/build controls + advanced config.

- **Folder tree (instead of flat list)**
  - Present roots as a collapsible tree (e.g. `docs → PhaseXX_*`).
  - Keep the “core vs working” concept visible.
  - Core roots remain protected (cannot be unchecked).

- **Expose retrieval limits**
  - Display the default RAG retrieval cap (`/context` default `max_chars`).
  - Optionally display LLM `context.max_tokens` (if readable from config).

### Architecture
- Served by the HTTP server
- Pure HTML + vanilla JS + fetch API
- Calls existing endpoints: `/status`, `/build`, `/config`

### Data model
```json
{
  "core_roots": [
    "_MASTER_CROSSREFERENCE",
    "src",
    "code_index"
  ],
  "working_roots": [
    "docs/PhaseXX_Example"
  ],
  "include_globs": ["**/*.md", "**/*.py", "**/*.ts", "**/*.tsx"],
  "exclude_globs": ["**/.git/**", "**/node_modules/**"],
  "max_file_bytes": 400000
}
```

### Status
**In progress** — building now.

---

## Release checklist (future)
- [ ] Clean up any project-specific paths/references in `code_index/`
- [ ] Add LICENSE file (MIT or Apache 2.0)
- [ ] Create standalone repo with:
  - `code_index/` core
  - `mcp_codrag_py/` MCP server
  - `dashboard/` React UI (optional)
  - `ui/` standalone HTML UI
- [ ] Write public README with:
  - Quick start
  - Ollama setup instructions
  - MCP configuration examples
  - API reference
- [ ] Test on a fresh repo (not LinuxBrain)
- [ ] Publish to GitHub

---

## Progress log

### 2026-01-30
- Created this document
- Started standalone HTML UI implementation
- Discussed compression integration strategy

# CoDRAG Development Roadmap

## Overview

This document outlines the phased development plan for CoDRAG, from initial foundation through MVP release with Tauri native app.

**Target:** Local-first, enterprise-friendly semantic search platform for codebases.

**Development Strategy:**
1. Web UI for rapid development iteration
2. Tauri wrapper for MVP launch (native app experience)
3. Treat team/enterprise as first-class **design constraints** (case studies + guardrails), but keep enterprise deployment features **post-MVP implementation**

Workflow backbone:
- `WORKFLOW_RESEARCH.md` (journey maps, acceptance criteria, MVP boundaries)

---

## Timeline Summary

| Phase | Name | Duration | Cumulative |
|-------|------|----------|------------|
| 01 | Foundation | 2 weeks | Week 2 |
| 02 | Dashboard | 2 weeks | Week 4 |
| 03 | Auto-Rebuild | 1 week | Week 5 |
| 04 | Trace Index | 2 weeks | Week 7 |
| 05 | MCP Integration | 1 week | Week 8 |
| 06 | Team & Enterprise | 1 week | Week 9 |
| 07 | Polish & Testing | 1 week | Week 10 |
| 08 | Tauri MVP (MVP milestone) | 2 weeks | Week 12 |
| 09 | Post-MVP | TBD | TBD |
| 10 | Business & Competitive Research | TBD | TBD |
| 11 | Deployment | TBD | TBD |
| 12 | Marketing / Docs / Website | TBD | TBD |
| 13 | Storybook | TBD | TBD |
| 16 | Context Intelligence | TBD | TBD |
| 19 | Alt Dev Workflows (Context MVC) | TBD | TBD |

**Total: ~12 weeks to MVP**

---

## Phase 0: Foundation (Week 1-2)

### Goals
- Core engine working end-to-end
- CLI for all basic operations
- HTTP API for dashboard integration

### Deliverables

#### Week 1: Core Engine

- [ ] **Project structure**
  - `src/codrag/` Python package
  - `pyproject.toml` with dependencies
  - Basic test structure

- [ ] **ProjectRegistry**
  - SQLite database schema
  - CRUD operations for projects
  - Config storage and retrieval

- [ ] **EmbeddingIndex (port from code_index)**
  - File scanning with glob patterns
  - Chunking logic
  - Embedding via Ollama
  - Vector similarity search
  - Save/load to disk

- [ ] **LLMCoordinator**
  - OllamaClient (embed, generate)
  - Connection status checks
  - Basic error handling

#### Week 2: CLI & API

- [ ] **CLI (`codrag` command)**
  - `serve` — start/stop daemon
  - `add` / `list` / `remove` — project management
  - `build` / `status` — indexing
  - `search` / `context` — queries

- [ ] **FastAPI Server**
  - `/projects` routes
  - `/projects/{id}/build` routes
  - `/projects/{id}/search` routes
  - `/projects/{id}/context` routes
  - `/llm/status` route

- [ ] **Basic tests**
  - Unit tests for registry, index
  - Integration test: add project → build → search

### Success Criteria
```bash
# These commands work:
codrag add /path/to/project --name "Test"
codrag build test
codrag search test "how does X work?"
codrag context test "how does X work?" --max-chars 4000

# API responds:
curl http://localhost:8400/projects
curl -X POST http://localhost:8400/projects/test/search \
  -H "Content-Type: application/json" \
  -d '{"query": "how does X work?", "k": 10}'
```

---

## Phase 1: Dashboard (Week 3-4)

### Goals
- React dashboard with project tabs
- Visual search interface
- Settings management

### Deliverables

#### Week 3: Core UI

- [ ] **Project scaffolding**
  - Vite + React + TypeScript
  - TailwindCSS + Tremor setup
  - API client (TanStack Query)

- [ ] **Layout**
  - Sidebar with project list
  - Project tabs (open/close)
  - Main content area

- [ ] **Project list**
  - Show all registered projects
  - Add project dialog (path picker)
  - Remove project (with confirmation)

- [ ] **Status page**
  - Index statistics (documents, embeddings)
  - Last build time
  - LLM connection status
  - Build button

#### Week 4: Search & Settings

- [ ] **Search page**
  - Query input
  - Results list with file previews
  - Score display
  - Click to show full chunk

- [ ] **Context page**
  - Query input
  - Assembled context display
  - Copy to clipboard
  - Source citations

- [ ] **Settings page (per-project)**
  - Include/exclude globs
  - Trace enabled toggle
  - Auto-rebuild toggle

- [ ] **Global settings modal**
  - Ollama URL
  - Embedding model
  - Data directory

### Success Criteria
- Dashboard loads at `http://localhost:5173`
- Can add/remove projects via UI
- Can trigger builds and see status
- Can search and view results
- Settings persist across sessions

---

## Phase 2: Auto-Rebuild (Week 5)

### Goals
- File watching for all projects
- Debounced incremental rebuilds
- Staleness indicators in UI

### Deliverables

- [ ] **FileWatcher service**
  - Watch project directories
  - Filter by include/exclude globs
  - Debounce rapid changes (5s default)

- [ ] **Incremental build**
  - Hash-based file change detection
  - Only re-embed changed files
  - Update manifest with new hashes

- [ ] **UI indicators**
  - "X files changed since last build"
  - "Auto-rebuilding in Xs" countdown
  - Build progress indicator

- [ ] **Config options**
  - Enable/disable per project
  - Global debounce setting
  - Rebuild on app start option

### Success Criteria
- Edit a file in watched project
- See "1 file changed" in dashboard within seconds
- Auto-rebuild triggers after debounce
- Only changed file is re-embedded (verify via logs)

---

## Phase 3: Trace Index (Week 6-7)

### Goals
- Structural understanding of code
- Symbol search and graph traversal
- Integration with semantic search

### Deliverables

#### Week 6: Symbol Extraction

- [ ] **Python analyzer**
  - AST parsing for symbols
  - Extract: functions, classes, methods
  - Extract: imports (edges)
  - Span information (line numbers)

- [ ] **TypeScript analyzer** (basic)
  - Regex-based or tree-sitter
  - Extract: functions, classes, exports
  - Extract: import statements

- [ ] **Trace storage**
  - `trace_nodes.jsonl` format
  - `trace_edges.jsonl` format
  - `trace_manifest.json`

#### Week 7: Query & UI

- [ ] **Trace API**
  - `/trace/status` — index stats
  - `/trace/search` — find nodes by name
  - `/trace/node/{id}` — get node details
  - `/trace/neighbors/{id}` — graph traversal

- [ ] **Dashboard Trace page**
  - Symbol search input
  - Node details view
  - Incoming/outgoing edges list
  - Link to source file

- [ ] **Search integration**
  - Option: "Include trace expansion"
  - Retrieves related symbols automatically
  - Shows trace info in search results

### Success Criteria
```bash
# CLI works:
codrag trace test "generate_image"
# Returns: node details, callers, callees

# API works:
curl http://localhost:8400/projects/test/trace/search \
  -d '{"query": "generate_image"}'
```
- Dashboard shows trace page
- Can browse symbol graph

---

## Phase 4: MCP Integration (Week 8)

### Goals
- Windsurf/Cursor integration via MCP
- Auto-detect project from working directory
- Seamless IDE experience

### Deliverables

- [ ] **MCP server mode**
  - `codrag mcp --project <id>` — serve specific project
  - `codrag mcp --auto` — detect from cwd

- [ ] **MCP tools**
  - `codrag_status` — index status
  - `codrag_build` — trigger build
  - `codrag_search` — semantic search
  - [x] `codrag` tool (smart context assembly)
  - `codrag_trace` — symbol lookup

- [ ] **Config generator**
  - `codrag mcp-config` — output JSON for mcp_config.json
  - Dashboard button: "Copy MCP config"

- [ ] **Documentation**
  - Windsurf setup guide
  - Cursor setup guide
  - Example workflows

### Success Criteria
```json
// ~/.codeium/windsurf/mcp_config.json
{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp", "--auto"]
    }
  }
}
```
- Windsurf can call `codrag_search` tool
- Results appear in Cascade context

---

## Post-MVP: Team/Enterprise Features (implementation)

 **Note:** This section is post-MVP implementation. MVP carries team/enterprise requirements as UX case studies and guardrails in `WORKFLOW_RESEARCH.md`.
 
 ### Goals
 - Embedded mode for git-tracked indexes
 - Network mode for shared server
 - Onboarding workflow
 - **Team Tier Features (Shared Configs)**

 ### Deliverables

 #### Embedded Mode
 
 - [ ] **Embedded index location**
  - `codrag add <path> --embedded`
  - Index stored in `<project>/.prep/`
  - Detect existing `.prep/` on add

- [ ] **Git integration**
  - Auto-add `.prep/` to `.gitignore` patterns file
  - Or: explicit "commit index" workflow
  - Handle merge conflicts (rebuild on conflict)

- [ ] **Team Shared Configs (Team Tier)**
  - `codrag config export` -> `.prep/team_config.json`
  - Standardized `include/exclude` patterns
  - Pre-defined LLM/Embedding endpoints
  - Enforced policy checks (e.g. "No secrets")

- [ ] **Team onboarding**
  - Clone repo → `codrag add . --embedded`
  - Instant search (no rebuild needed)
  - Dashboard shows "Using committed index"

 #### Network Mode
 
 - [ ] **Server binding**
  - `codrag serve --host 0.0.0.0`
  - API key authentication
  - TLS support (optional)

- [ ] **Client mode**
  - `codrag config set server.remote_url http://team:8400`
  - All requests proxy to remote server
  - Local CLI still works

- [ ] **Access control (basic)**
  - API key per user
  - Read-only vs read-write
  - Audit log (who searched what)

### Success Criteria
- Team member clones repo with `.prep/`
- Runs `codrag add . --embedded`
- Instant search without rebuild
- OR: Connects to team server, searches remote index

---

## Phase 6: Polish, Testing, & Licensing (Week 9)

### Goals
- Stability and error handling
- Performance optimization
- Documentation completeness
- **Licensing & Feature Gating Implementation**

### Deliverables

- [ ] **Licensing Engine**
  - Verify offline signed keys (Ed25519)
  - "Founder's Edition" / "Pro" capability flags

- [ ] **Feature Gating Logic**
  - `ProjectRegistry`: Enforce 2-project limit for Free tier
  - `TraceManager`: Enable/Disable based on license status
  - Dashboard: "Upgrade to Pro" UI triggers

- [ ] **Error handling**
  - Graceful Ollama disconnection
  - Build failure recovery

  - File permission errors

- [ ] **Performance**
  - Lazy index loading
  - Search result caching
  - Batch embedding requests

- [ ] **Testing**
  - Unit test coverage >80%
  - Integration tests for all flows
  - E2E tests for dashboard

- [ ] **Documentation**
  - README complete
  - API documentation
  - Troubleshooting guide
  - Video walkthrough

- [ ] **UX polish**
  - Loading states
  - Error messages
  - Keyboard shortcuts
  - Responsive design

### Success Criteria
- No crashes in normal usage
- All documented features work
- Tests pass in CI
- README is complete and accurate

---

## MVP: Tauri Wrapper (Week 10)

### Goals
- Native app experience
- System tray integration
- One-click installation

### Deliverables

- [ ] **Tauri setup**
  - Rust project scaffolding
  - React dashboard integration
  - Build configuration

- [ ] **Python sidecar**
  - PyInstaller/PyOxidizer bundle
  - Auto-start on app launch
  - Health monitoring

- [ ] **Native features**
  - System tray icon with menu
  - Auto-start on login (optional)
  - Native file picker dialogs
  - Notifications

- [ ] **Installers**
  - macOS: .dmg
  - Windows: .msi / .exe
  - Linux: .AppImage / .deb

- [ ] **Auto-update**
  - Version check on startup
  - Download and install updates

### Success Criteria
- Double-click to install
- App appears in system tray
- Dashboard opens in native window
- All features from web UI work
- Updates install seamlessly

---

## Post-MVP Roadmap

### Near-term (Months 2-3)

- [ ] **Cross-project search** — Search across all projects (opt-in)
- [x] **LOD compression** — Built-in structural code compression (shipped)
- [ ] **AGENTS.md generation** — Export from trace index
- [ ] **VS Code extension** — Native IDE integration
- [ ] **More languages** — Java, Go, Rust analyzers

### Medium-term (Months 4-6)

- [ ] **LLM augmentation** — Per-symbol summaries
- [ ] **Diff-aware search** — "What changed that relates to X?"
- [ ] **Graph visualization** — Interactive code map
- [ ] **Alt Dev Workflows (Phase 19)** — Context MVC for Gemini CLI / Qwen Code
- [ ] **Custom embeddings** — BYOK embedding models
- [ ] **Plugin system** — Custom analyzers

### Long-term (6+ months)

- [ ] **Cloud sync** — Optional index backup
- [ ] **Enterprise SSO** — SAML/OIDC integration
- [ ] **Code review integration** — GitHub/GitLab PR search
- [ ] **AI assistant** — "Explain this codebase" chat

---

## Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Ollama API changes | Medium | Low | Abstract behind client, pin version |
| Tauri complexity | High | Medium | Delay Tauri to MVP, web works standalone |
| Performance at scale | High | Medium | Test with large repos early |
| Cross-platform bugs | Medium | Medium | CI for all platforms |
| Team adoption friction | High | Medium | Focus on onboarding UX |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-30 | Name: CoDRAG | "Code Documentation and RAG" — clear, memorable |
| 2026-01-30 | Web UI first, Tauri for MVP | Faster iteration, proven approach |
| 2026-01-31 | Enterprise features post-MVP | Enforce MVP boundaries; keep enterprise UX case studies |
| 2026-01-30 | Repo at HumanAI root | Sibling to LinuxBrain for testing |

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical design
- [API.md](API.md) — Full API specification
- [../README.md](../README.md) — Project overview

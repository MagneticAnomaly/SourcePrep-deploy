# Phase 05 — MCP Integration TODO

## Links
- Spec: `README.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`
- API contract: `../API.md`

## Research completion checklist (P05-R*)
- [x] P05-R1 Decide MCP architecture (daemon HTTP proxy vs in-process engine) ✅ **DONE: HTTP proxy to daemon**
- [x] P05-R2 Finalize tool schemas + error shapes + limits policy ✅ **DONE: See `mcp_server.py`**
- [x] P05-R3 Specify project selection and conflict-resolution rules (pinned vs auto-detect) ✅ **DONE: --project and --auto flags**

## Implementation backlog (P05-I*)
### Server mode + transport
- [x] P05-I1 MCP stdio server that proxies to daemon HTTP API (default `127.0.0.1:8400`) ✅ **DONE: `src/prep/mcp_server.py`**
- [x] P05-I2 Health check behavior: ✅ **DONE**
  - on startup, `GET /health`
  - actionable `DAEMON_UNAVAILABLE` errors

### Tool surface
- [x] P05-I3 Implement tools: ✅ **DONE**
  - `prep_status` ✅
  - `prep_build` ✅
  - `prep_search` ✅
  - `prep` (context) ✅
  - `prep_trace` (when trace available) — deferred
- [x] P05-I4 Ensure tool outputs mirror `API.md` shapes (avoid schema drift) ✅ **DONE**

### Project selection
- [x] P05-I5 Pinned project mode (`--project <id>`) ✅ **DONE: `prep mcp --project`**
- [x] P05-I6 Auto-detect mode (`--auto`): longest-prefix rule for `cwd` vs registered project paths ✅ **DONE: `prep mcp --auto`**
- [x] P05-I7 Ambiguity handling (`PROJECT_SELECTION_AMBIGUOUS`) with debuggable output

### Token efficiency + robustness
- [x] P05-I8 Never corrupt JSON-RPC output (no accidental stdout logging) ✅ **DONE: All logs to stderr**
- [x] P05-I9 Lean outputs by default (optionally emit markdown summaries) ✅ **DONE**
- [x] P05-I10 Enforce conservative defaults + hard caps (k/max_chars/neighbors) ✅ **DONE**
- [x] P05-I11 Debug mode writes logs to file (opt-in) for diagnosis

### Config generation
- [x] P05-I12 `prep mcp-config` prints ready-to-paste client config (pinned + auto) ✅ **DONE: Multi-IDE support**
- [x] S-16.3 PyPI Package Verification for MCP Registry (P05-I19)
- [x] S-16.4 Tool Icons & Metadata Polish (P05-R9) ✅ **DONE**

## Testing & validation (P05-T*)
- [x] P05-T1 Integration test: MCP tool calls against known project (status/build/search/context) ✅ **DONE: `tests/test_mcp_server.py`**
- [x] P05-T2 Failure test: daemon down → stable `DAEMON_UNAVAILABLE` error ✅ **DONE**
- [x] P05-T3 Budget test: large requests are rejected with actionable errors

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [ ] STR-01 API envelope + error codes
- [ ] STR-05 Output budgets

## Notes / blockers
- [ ] Decide how MCP should behave when index is missing (prompt to build vs hard error)
- [ ] Decide whether MCP should support an “assemble context as markdown” output mode for LLMs
- [ ] Verify MCP Server mode remains aligned with canonical `/projects/*` routes (avoid legacy `/api/code-index/*` drift)
- [ ] Smoke test: `prep mcp --mode direct` against `tests/fixtures/mini_repo` (and decide if Direct Mode stays supported)
- [ ] Track: CLI `ApiEnvelope` unwrap mismatch (master gap) impacts MCP only if MCP consumes CLI helpers

---

## MCP Standards & IDE Compatibility Research (Feb 2026)

### Current MCP Specification
- **Latest revision**: `2025-11-25` (released Nov 25, 2025)
- **JSON Schema dialect**: JSON Schema 2020-12 (SEP-1613)
- **Protocol**: JSON-RPC over UTF-8

### Transport Mechanisms (must support both)
1. **stdio** (PRIMARY) — Client launches server as subprocess; JSON-RPC over stdin/stdout
   - Clients **SHOULD** support stdio whenever possible
   - Messages delimited by newlines, **MUST NOT** contain embedded newlines
   - Server **MUST NOT** write anything to stdout except valid MCP messages
2. **Streamable HTTP** — Server as independent process handling multiple clients
   - Replaces deprecated HTTP+SSE from 2024-11-05
   - Single endpoint supporting POST/GET (e.g., `https://example.com/mcp`)
   - **Security**: MUST validate `Origin` header, bind to localhost when local, implement auth

### Key 2025-11-25 Changes Relevant to Prep
- **Tasks** (SEP-1686): Async operations for long-running tasks (e.g., index builds)
- **Elicitation** (SEP-1036): URL mode for secure out-of-band interactions
- **Tool icons** (SEP-973): Metadata icons for tools/resources/prompts
- **JSON Schema 2020-12** default dialect
- **Tool name format** guidance (SEP-986)
- **OAuth Client ID Metadata Documents** (SEP-991)

### Official SDKs (use Python SDK for Prep)
| Language   | Repository |
|------------|------------|
| **Python** | github.com/modelcontextprotocol/python-sdk |
| TypeScript | github.com/modelcontextprotocol/typescript-sdk |
| Go         | github.com/modelcontextprotocol/go-sdk |
| Kotlin     | github.com/modelcontextprotocol/kotlin-sdk |
| Java       | github.com/modelcontextprotocol/java-sdk |
| Rust       | github.com/modelcontextprotocol/rust-sdk |
| C#         | github.com/modelcontextprotocol/csharp-sdk |

### Major IDE/Client MCP Support (as of Jan 2026)

| Client | Local MCP | Remote MCP | Transport | Notes |
|--------|-----------|------------|-----------|-------|
| **VS Code** (Copilot) | | | stdio, SSE | Native support |
| **Cursor** | | | stdio, SSE | Tools, prompts, roots, elicitation |
| **Windsurf** | | | stdio, SSE | Full tool support |
| **JetBrains IDEs** | | | stdio | v2025.2+; also acts as MCP server |
| **Claude Desktop** | | | stdio, SSE | Full resources, prompts, tools |
| **Claude.ai** | — | | SSE | Remote only via integrations |
| **Claude Code** | | | stdio | Full MCP + acts as MCP server |
| **Cline** (VS Code) | | — | stdio | Natural language tool creation |
| **Continue** | | — | stdio | VS Code + JetBrains |
| **Amazon Q CLI/IDE** | | — | stdio | VS Code, JetBrains, VS, Eclipse |
| **Xcode** | | | stdio, SSE | Apple ecosystem |
| **Eclipse** | | | stdio, SSE | Via Amazon Q |
| **Visual Studio** | | | stdio, SSE | Via Copilot |
| **Emacs** | | — | stdio | Via emacs-mcp plugin |
| **Neovim** | | — | stdio | Via Amp |

### Prep Compatibility Checklist
- [x] P05-R5 Support **both** stdio AND Streamable HTTP transports (stdio done, HTTP implemented via `/sse` + `/message`)
- [x] P05-R6 Implement proper `Origin` validation for HTTP transport ✅ **DONE: `TrustedOriginMiddleware` in `mcp_server.py`**
- [ ] P05-R7 Consider async **Tasks** for `prep_build` (long-running)
- [x] P05-R9 Provide tool icons via `_meta.icons` field ✅ **DONE**

### Config Generation for Major IDEs
`prep mcp-config` should output ready-to-paste JSON for:
- [x] P05-I19 Add verification info for PyPI package ownership ✅ **DONE**
- [x] P05-I13 Claude Desktop (`claude_desktop_config.json`) ✅ **DONE**
- [x] P05-I14 Cursor (`.cursor/mcp.json`) ✅ **DONE**
- [x] P05-I15 VS Code (`settings.json` or `.vscode/mcp.json`) ✅ **DONE**
- [x] P05-I16 JetBrains (AI Assistant MCP settings) ✅ **DONE**
- [x] P05-I17 Windsurf (workspace MCP config) ✅ **DONE**

### MCP Registry (for discoverability)
- Registry GA expected Q1 2026
- [x] P05-I18 Create `server.json` for MCP Registry publishing ✅ **DONE: `/mcp-server.json`**
- [ ] P05-I19 Add verification info for PyPI package ownership

### Recommendations
1. **Use Python SDK** — Official, well-maintained, matches Prep stack
2. **stdio first** — All major IDEs support it; simplest to implement
3. **Add Streamable HTTP** — Enables remote/enterprise deployments
4. **Implement Tasks** — `prep_build` can take minutes; use async Tasks pattern
5. **Generate multi-IDE configs** — Single command to output all IDE configs
6. **Publish to MCP Registry** — Increases discoverability once GA

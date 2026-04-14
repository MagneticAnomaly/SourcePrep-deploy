

<!-- codrag-managed-start -->
## CoDRAG Integration

Last updated: 2026-04-14T04:09:35Z

codrag_project_id: 1d6f0b35-45cb-427b-ae9d-aac3c6371a4b

**ROUTING: When calling ANY CoDRAG tool, ALWAYS include `project_id: "1d6f0b35-45cb-427b-ae9d-aac3c6371a4b"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `codrag` | START of every task — structural overview, modules, hub files, immune system alerts |
| `codrag_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). |
| `codrag_impact` | BEFORE editing — check what depends on a file |
| `codrag_audit` | Structural findings (coupling, cycles, concept violations) OR enrich external lint findings with `findings` param. Use `action="antibodies"` for immune system. |
| `codrag_observe` | Save/retrieve cross-session notes |
| `codrag_concepts` | Record/query business rationale and design decisions |

Call `codrag` first. Call `codrag_impact` before modifying hub files.
All read-only tools are safe to auto-approve.

### Audit Enrichment
Enrich external lint/analysis findings with structural context:
```
codrag_audit(findings=[{file, line, message, severity, tool}])
```
CoDRAG adds: dependent count, hub status, concepts, risk score, recommendation.
Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.

### Search Intent
`codrag_search` auto-detects query intent: "where is X" → symbol lookup,
"why X" → concepts, "who imports X" → trace graph. Override with `intent` param if needed.

You have access to CoDRAG, a structural code intelligence system.
ALWAYS call `codrag` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `codrag_search` with a natural language query.
Before making changes to a file, use `codrag_impact` to understand dependencies.
CoDRAG understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `codrag_audit`.
For cross-session memory, use `codrag_observe` to save/retrieve notes.
All CoDRAG tools are read-only and safe to auto-approve.

### Auto-Approve Configuration
To skip approval prompts for CoDRAG's read-only tools, add to your settings:
```json
{ "permissions": { "allow": ["mcp__codrag"] } }
```
In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings.

<!-- codrag-atlas-hash:bd2cdbb1b9d4 -->
## Codebase Atlas

IDENTITY: Codrag is a multi-segment AI coding assistant platform with a Model Context Protocol (MCP) server, Python backend services, React/TypeScript UI components, VS Code extension, and Rust-based code analysis engine.

STACK: Python 323 files, TypeScript/TSX 334 files, Rust 18 files, Markdown 569 files. React, Storybook, Paperclip. MCP, FastAPI, RAG pipeline. Build tools: dashboard build-system, test_ui_build.sh.

WORKSPACE MAP:
_root (1012 files): MCP server, Python services, testing infrastructure, marketing, UI coordination
Ui (packages/ui, 291 files): Enterprise and architecture component libraries, Storybook documentation, TypeScript UI foundation
Dashboard (src/codrag/dashboard, 42 files): Project management dashboard with state management and build-system integration
Vscode (packages/vscode, 20 files): VS Code extension with daemon integration, RAG features, project management
Webview Ui (packages/vscode/webview-ui, 14 files): React-based code navigation and context management within VS Code
Paperclip Plugin Codrag (packages/paperclip-plugin-codrag, 12 files): Paperclip design tool plugin with TypeScript configuration system

CROSS-CUTTING: Five entry points anchor the graph: enterprise components, CLI, Rust walker, MCP server, architecture components. Shared domains across segments: ui, dashboard, typescript, project-management, vscode-extension. Hub dependencies: typing 223 edges, pathlib 168 edges, logging 156 edges, json 153 edges. Import chains link UI components through backend_config.py to pipeline orchestrator and scheduler; CLI chains through server to project registry, rules generator, watcher, and trace builder. 124 import cycles present. Directory dependencies: docs, engine, packages, public, scripts, src each expose symbols to other segments.

If `codrag` returns 'setup in progress', the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.

For long tasks (5+ tool calls), call `codrag` again to refresh your
structural context.

You can call `codrag` and `codrag_search` in parallel on your first
prompt -- structural overview + targeted code lookup in one round-trip.

### Tool Calling Rules
1. **Never announce** 'I will now call...' - just call the tool
2. **No permission needed** - simple keywords = immediate invocation
3. **Single word triggers** - 'codrag' alone is enough to call the tool
4. **Context is cheap** - prefer calling codrag to using grep for structural understanding

**Remember: The word "codrag" anywhere in user input is a tool invocation signal. Call immediately without asking permission.**

### MCP Resources (browse with @)
CoDRAG also exposes browsable resources via MCP. In supported clients,
type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.
Resources provide on-demand context without a tool call.

### MCP Prompts (invoke with /)
Available workflow prompts: `codrag-onboard` (orientation), `codrag-review` (file review),
`codrag-plan` (change planning), `codrag-investigate` (deep dive), `codrag-health` (audit).
In Claude Code: `/mcp__codrag__codrag-onboard`. In other clients: check prompt menu.
<!-- codrag-managed-end -->



<!-- codrag-managed-start -->
## CoDRAG Integration

Last updated: 2026-04-18T06:41:12Z

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

<!-- codrag-atlas-hash:f0799a4d1cae -->
## Codebase Atlas

IDENTITY: Codrag is a code intelligence platform with a VSCode extension, web dashboard, documentation site, marketing site, and supporting services for AI-assisted code analysis and visualization.

STACK: TypeScript, React, Python, Rust. React ecosystem via ext:react (182 edges). Python standard library via ext:typing (237 edges), ext:__future__ (236 edges), ext:logging (162 edges), ext:pathlib (148 edges). Build tooling implied by package structure across packages/ and websites/apps/ directories.

WORKSPACE MAP:
Root (_root, 1306 files): monorepo root and shared configuration
Ui (packages/ui, 332 files): shared React component library with trace visualization, patterns, project views, and AtlasLensPanel
Marketing (websites/apps/marketing, 66 files): public marketing website
Docs (websites/apps/docs, 54 files): documentation site with CLOUD_SINGLE, sampleIndexStats, EMBEDDING_MODELS symbols
Dashboard (src/codrag/dashboard, 47 files): main application dashboard interface
Support (websites/apps/support, 29 files): customer support application
Vscode (packages/vscode, 20 files): VSCode extension host
Payments (websites/apps/payments, 17 files): billing and subscription management
Webview Ui (packages/vscode/webview-ui, 14 files): VSCode extension webview UI components
Paperclip Plugin Codrag (packages/paperclip-plugin-codrag, 12 files): Paperclip design tool integration

CROSS-CUTTING: Active development zones cluster in packages/ui/src/ (381 .tsx files, entry points for trace/AtlasLensPanel, patterns, project, viz), src/codrag/core/, src/codrag/dashboard/, and src/codrag/services/. Engine layer in Rust (codrag-chunking/src/lib.rs entry point) handles Python parsing and chunking with test_inferred_boost_on_structural_match, parse_python, test_assign_lod_mid_score symbols. UI components import chain through AtlasLensPanel -> RoleLens -> BudgetSlider with 4-cycle import dependency. Python services layer contains UseRoleOverridesReturn, _normalize_path_weights, RoleOverride.to_dict. Shared infrastructure includes ArchStats, SwarmBuild, ErrorPermissionDenied in packages; main, handler, trigger_sync in public; test_daemon_thread_count, generate_license, should_skip in scripts. Test coverage spans specs/ (8 files), tests-old/ (7 files), __tests__/ (4 files). 4 import cycles detected across 10134 graph edges.

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

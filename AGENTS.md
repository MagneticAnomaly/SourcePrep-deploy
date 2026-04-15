

<!-- codrag-managed-start -->
## CoDRAG Integration

Last updated: 2026-04-15T04:02:52Z | Full analysis in progress

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

<!-- codrag-atlas-hash:1c8ff779c80d -->
## Codebase Atlas

IDENTITY: CoDRAG
STACK: .md 34%, .tsx 16%, .ts 16%, .py 13%, .js 12%, .json 5%, .css 2%, .html 1%
STRUCTURE: 2345 files, 8840 nodes, 10832 edges
EDGE TYPES: contains: 5800, imports: 5032
CIRCULAR DEPS (3): src/codrag/core/audit/synthesizer.py <-> src/codrag/core/audit/__init__.py; src/codrag/api/routers/projects/__init__.py <-> src/codrag/api/routers/projects/__init__.py; src/codrag/api/routers/trace_routes/__init__.py <-> src/codrag/api/routers/trace_routes/__init__.py
ENTRY POINTS: packages/ui/src/components/marketing/heroes/index.ts, src/codrag/__main__.py, docs/Phase13_Storybook/theme-examples/tremor-preview/src/components/index.ts, packages/ui/src/components/viz/index.ts, packages/ui/src/components/team/index.ts
SUBSYSTEMS:
  _root/ (1262 files)
  packages/ui/ (825 files)
  websites/apps/marketing/ (66 files)
  websites/apps/docs/ (54 files)
  src/codrag/dashboard/ (46 files)
  websites/apps/support/ (29 files)
  packages/vscode/ (20 files)
  websites/apps/payments/ (17 files)
  packages/vscode/webview-ui/ (14 files)
  packages/paperclip-plugin-codrag/ (12 files)
TESTS: tests-old/ (7 files), specs/ (7 files), test_scheduler.py/ (1 files)
HUB FILES: ext:typing (232 edges), ext:__future__ (227 edges), ext:react (198 edges), ext:logging (158 edges), ext:lucide-react (144 edges)
CALL CHAINS:
  packages/ui/src/components/marketing/heroes/index.ts -> packages/ui/src/components/marketing/heroes/split.tsx -> packages/ui/src/components/marketing/heroes/studio.tsx -> sym:StudioHero@packages/ui/src/components/marketing/heroes/studio.tsx:15
  src/codrag/__main__.py -> src/codrag/server.py -> ext:codrag.api.routers.agents
  docs/Phase13_Storybook/theme-examples/tremor-preview/src/components/index.ts -> docs/Phase13_Storybook/theme-examples/tremor-preview/src/components/MarketingHero.tsx -> sym:FocusHero@docs/Phase13_Storybook/theme-examples/tremor-preview/src/components/MarketingHero.tsx:557

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

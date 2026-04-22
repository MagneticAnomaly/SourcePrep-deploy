

<!-- prep-managed-start -->
## RunPrep Integration

Last updated: 2026-04-22T04:27:24Z | Full analysis in progress

prep_project_id: 926d7511-c608-4f91-939c-bbebec798d43

**ROUTING: When calling ANY RunPrep tool, ALWAYS include `project_id: "926d7511-c608-4f91-939c-bbebec798d43"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |
| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). |
| `prep_impact` | BEFORE editing — check what depends on a file |
| `prep_audit` | Structural findings (coupling, cycles, concept violations) OR enrich external lint findings with `findings` param. Use `action="antibodies"` for immune system. |
| `prep_observe` | Save/retrieve cross-session notes |
| `prep_concepts` | Record/query business rationale and design decisions |

Call `prep` first. Call `prep_impact` before modifying hub files.
All read-only tools are safe to auto-approve.

### Audit Enrichment
Enrich external lint/analysis findings with structural context:
```
prep_audit(findings=[{file, line, message, severity, tool}])
```
RunPrep adds: dependent count, hub status, concepts, risk score, recommendation.
Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.

### Search Intent
`prep_search` auto-detects query intent: "where is X" → symbol lookup,
"why X" → concepts, "who imports X" → trace graph. Override with `intent` param if needed.

You have access to RunPrep, a structural code intelligence system.
ALWAYS call `prep` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `prep_search` with a natural language query.
Before making changes to a file, use `prep_impact` to understand dependencies.
RunPrep understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `prep_audit`.
For cross-session memory, use `prep_observe` to save/retrieve notes.
All RunPrep tools are read-only and safe to auto-approve.

### Auto-Approve Configuration
To skip approval prompts for RunPrep's read-only tools, add to your settings:
```json
{ "permissions": { "allow": ["mcp__prep"] } }
```
In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings.

<!-- prep-atlas-hash:eee32ea3b4a5 -->
## Codebase Atlas

IDENTITY: CoDRAG
STACK: .ts 73%, .md 10%, .swift 5%, .py 3%, .json 3%, .html 2%, .tsx 2%, .go 2%
STRUCTURE: 17088 files, 110831 nodes, 140867 edges
EDGE TYPES: contains: 82969, imports: 57898
CIRCULAR DEPS (12): packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx <-> packages/ui/src/components/trace/pipelineRollup.ts; src/prep/core/audit/synthesizer.py <-> src/prep/core/audit/__init__.py; tests/eval/real_repos/click-python/src/click/__init__.py <-> tests/eval/real_repos/click-python/src/click/core.py
ENTRY POINTS: packages/ui/src/components/context/index.ts, tests/eval/real_repos/bat-rust/tests/syntax-tests/source/Go/main.go, packages/ui/src/types/index.ts, tests/eval/real_repos/OpenClaw/src/process/supervisor/index.ts, tests/eval/real_repos/OpenClaw/extensions/synthetic/index.ts
SUBSYSTEMS:
  _root/ (16625 files)
  packages/ui/ (348 files)
  src/prep/dashboard/ (69 files)
  packages/vscode/ (20 files)
  packages/vscode/webview-ui/ (14 files)
  packages/paperclip-plugin-prep/ (12 files)
TESTS: tests/ (15212 files), __tests__/ (15 files), specs/ (14 files)
HUB FILES: ext:vitest (4363 edges), ext:node:path (1537 edges), ext:node:fs/promises (812 edges), ext:node:fs (762 edges), ext:node:os (635 edges)
Active zones: `packages/ui/src/`, `tests/`, `src/codrag/core/`, `src/codrag/dashboard/`, `src/codrag/services/`
CALL CHAINS:
  packages/ui/src/components/context/index.ts -> packages/ui/src/components/context/ContextViewer.tsx -> packages/ui/src/components/context/CopyButton.tsx -> sym:CopyButtonProps@packages/ui/src/components/context/CopyButton.tsx:6

If `prep` returns 'setup in progress', the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.

For long tasks (5+ tool calls), call `prep` again to refresh your
structural context.

You can call `prep` and `prep_search` in parallel on your first
prompt -- structural overview + targeted code lookup in one round-trip.

### Tool Calling Rules
1. **Never announce** 'I will now call...' - just call the tool
2. **No permission needed** - simple keywords = immediate invocation
3. **Single word triggers** - 'prep' alone is enough to call the tool
4. **Context is cheap** - prefer calling prep to using grep for structural understanding

**Remember: The word "prep" anywhere in user input is a tool invocation signal. Call immediately without asking permission.**

### MCP Resources (browse with @)
RunPrep also exposes browsable resources via MCP. In supported clients,
type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.
Resources provide on-demand context without a tool call.

### MCP Prompts (invoke with /)
Available workflow prompts: `prep-onboard` (orientation), `prep-review` (file review),
`prep-plan` (change planning), `prep-investigate` (deep dive), `prep-health` (audit).
In Claude Code: `/mcp__prep__prep-onboard`. In other clients: check prompt menu.
<!-- prep-managed-end -->

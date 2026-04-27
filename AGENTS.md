

<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-04-27T14:26:52Z

prep_project_id: f1636374-abc6-410d-99ee-822120379e79

**ROUTING: When calling ANY SourcePrep tool, ALWAYS include `project_id: "f1636374-abc6-410d-99ee-822120379e79"` in the arguments.**

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
SourcePrep adds: dependent count, hub status, concepts, risk score, recommendation.
Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.

### Search Intent
`prep_search` auto-detects query intent: "where is X" → symbol lookup,
"why X" → concepts, "who imports X" → trace graph. Override with `intent` param if needed.

### Concurrency limits
If your queries to the cloud LLM seem unexpectedly throttled, check
`prep_search "concurrency ceiling"` for the current discovered limit
and how to reset it. The limit is auto-discovered and locked for 24h.

You have access to SourcePrep, a structural code intelligence system.
ALWAYS call `prep` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `prep_search` with a natural language query.
Before making changes to a file, use `prep_impact` to understand dependencies.
SourcePrep understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `prep_audit`.
For cross-session memory, use `prep_observe` to save/retrieve notes.
All SourcePrep tools are read-only and safe to auto-approve.

### Auto-Approve Configuration
To skip approval prompts for SourcePrep's read-only tools, add to your settings:
```json
{ "permissions": { "allow": ["mcp__prep"] } }
```
In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings.

<!-- prep-atlas-hash:955d828358fd -->
## Codebase Atlas

IDENTITY: This is a local-first AI productivity platform with a multi-segment workspace spanning a React/Tailwind design system, NextJS marketing sites, a Tauri desktop dashboard, VS Code extension, documentation, support portal, and payments micro-frontend, unified by shared UI components and cross-cutting Python services.

STACK: Languages: .md (830), .tsx (428), .py (304), .ts (152), .json (114), .js (16). Frameworks: React, NextJS, Tauri, TailwindCSS, Storybook. Build tools: TypeScript. Graph: 7665 nodes, 10070 edges, 4 import cycles. Hub dependencies: __future__ (244 edges), typing (241), react (191), logging (169), lucide-react (155).

WORKSPACE MAP: Root (_root, 1222 files): mcp, marketing, local-first, security, rag. Ui (packages/ui, 355 files): storybook, design-system, tailwind, ui, react. Marketing (websites/apps/marketing, 66 files): marketing, nextjs, seo, layout, metadata. Dashboard (src/prep/dashboard, 62 files): dashboard, tauri, react-hooks, state-management, react. Docs (websites/apps/docs, 54 files): documentation, marketing, nextjs, react, seo. Support (websites/apps/support, 27 files): nextjs, typescript, client-component, frontend, micro-frontend. Vscode (packages/vscode, 20 files): vscode-extension, file-navigation, ide-integration, webview, daemon-client. Payments (websites/apps/payments, 15 files): micro-frontend, nextjs, navigation, payments, app-router. Paperclip Plugin Prep (packages/paperclip-plugin-prep, 12 files): typescript, dashboard, plugin-ui, paperclip, plugin. Webview Ui (packages/vscode/webview-ui, 11 files): dashboard, tailwindcss, testing, typescript, vscode-extension.

CROSS-CUTTING: Shared domains across segments: nextjs, marketing, react, dashboard, typescript, seo, micro-frontend, vscode-extension. Active zones: packages/ui/src/, tests/, src/codrag/core/, src/codrag/dashboard/, src/codrag/services/. UI components serve as the primary integration layer with five entry points: patterns/index.ts, enterprise/index.ts, status/index.ts, site/index.ts, marketing/research/index.ts. Directory dependencies flow through symbol exports: docs -> FALLBACK_SINGLE_MODEL, ChatMessage, CLOUD_SINGLE; packages -> ConceptStats, ConceptsPanel, useEventStream; public -> trigger_sync, main, handler; src -> build_concept_from_observation, A2ATask.fail, StructuralFinding; tools -> RunContext.log, Api.cancel, RunContext.snap; websites -> PATCH, DemoTab, isHeroSelection. VS Code extension bridges IDE and dashboard via webview-ui. Paperclip plugin connects dashboard UI to extension ecosystem.

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
SourcePrep also exposes browsable resources via MCP. In supported clients,
type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.
Resources provide on-demand context without a tool call.

### MCP Prompts (invoke with /)
Available workflow prompts: `prep-onboard` (orientation), `prep-review` (file review),
`prep-plan` (change planning), `prep-investigate` (deep dive), `prep-health` (audit).
In Claude Code: `/mcp__prep__prep-onboard`. In other clients: check prompt menu.
<!-- prep-managed-end -->

## Operational notes (user-maintained)

### Reset cloud LLM concurrency discovery (Phase 119)

If the user reports that a cloud endpoint's parallelism looks wrong
(stuck at an old number after a plan upgrade, climbed too high without
ever backing off, or just generally unhealthy), the canonical answer is
to reset the discovered ceiling for that node.

- **From the dashboard:** AI Gateway header → wrench icon →
  Reset next to the cloud node (typically `cloud:default_ollama`).
  Same control also lives at Settings → AI Models → Pipeline Activity.
- **From the API:**
  `POST /compute/concurrency/clear?node_id=cloud:default_ollama`.
  Returns `{status, node_id, old_limit, new_limit, new_mode}` so you
  can confirm the in-memory `current_limit` actually dropped.
- **What it does:** clears the persisted record, re-seeds
  `current_limit` from a fresh Ollama probe (or jumpstart=5 for
  non-Ollama cloud nodes), resets the AIMD streak/backoff timestamps,
  and lets natural backoffs rediscover the real ceiling.

For more context call
`prep_search "concurrency reset"` —
the seeded "Cloud LLM concurrency ceiling lock" concept covers the
mechanism in detail with anchors into `scheduler.py`,
`concurrency_store.py`, and `compute.py`.

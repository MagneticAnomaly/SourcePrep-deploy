

<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-05-01T17:36:56Z

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

<!-- prep-atlas-hash:7674926cedb3 -->
## Codebase Atlas

IDENTITY: A local-first, MCP-powered developer platform with a shared React/Next.js UI monorepo, FastAPI backend, VS Code extension, and marketing/docs/support web properties.

STACK: TypeScript/React/Next.js frontend, Python/FastAPI backend, VS Code extension with webview UI, Storybook design system, Vite build tooling, 835 markdown docs, 429 TSX components, 305 Python files.

WORKSPACE MAP: Project Root (_root, 1228 files): marketing, MCP, local-first, dashboard, fastapi orchestration. Ui (packages/ui, 357 files): storybook, design-system, react primitives, documentation, marketing components. Marketing (websites/apps/marketing, 65 files): nextjs SEO marketing-site. Dashboard (src/prep/dashboard, 63 files): react-hooks, state-management, polling. Docs (websites/apps/docs, 53 files): nextjs documentation, static-analysis, fastapi. Support (websites/apps/support, 26 files): nextjs error-handling frontend. Vscode (packages/vscode, 19 files): vscode-extension, semantic-search, lifecycle-management, webview, MCP. Payments (websites/apps/payments, 14 files): nextjs payments API marketing-site. Paperclip Plugin Prep (packages/paperclip-plugin-prep, 12 files): plugin-architecture, MCP, health-monitoring, codebase-intelligence, local-first. Webview Ui (packages/vscode/webview-ui, 11 files): vscode-extension monorepo pricing-conversion vite webview.

CROSS-CUTTING: Shared domains across segments: marketing, nextjs, mcp, local-first, dashboard, fastapi, react, documentation. Hub files: docs/ARCHITECTURE.md, ext:__future__, ext:typing, ext:react, ext:logging. Active zones: packages/ui/src/, tests/, src/codrag/core/, src/codrag/dashboard/, websites/apps/marketing/. Entry points cluster in packages/ui/src/components/primitives/index.ts, status/index.ts, goalposts/index.ts, console/index.ts, navigation/index.ts. Directory dependencies: docs -> sym:prepFeatures, sym:FileStatus, sym:GPU_PLATFORMS; packages -> sym:toggle, sym:CheckIcon, sym:EmptyStateProps; public -> sym:main, sym:trigger_sync, sym:handler; src -> sym:KnowledgeIndex._content_hash, sym:concurrency_history, sym:Project; tools -> sym:Api.status, sym:drive_scoped_reset_ui, sym:run_rebuild; websites -> sym:AnchorHeading, sym:SearchResults, sym:PaymentForm. 48 import cycles detected. Longest chains: status/index.ts -> StatusCard.tsx -> StatusBadge.tsx -> utils.ts -> sym:cn; goalposts/index.ts -> RoadmapPanel.tsx -> RoadmapTimeline.tsx -> colors.ts -> sym:CATEGORY_LABEL; primitives/index.ts -> PathInput.tsx -> sym:PathInputProps.

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



<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-05-11T17:30:54Z

prep_project_id: f1636374-abc6-410d-99ee-822120379e79

**ROUTING: When calling ANY SourcePrep tool, ALWAYS include `project_id: "f1636374-abc6-410d-99ee-822120379e79"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |
| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, COMPARE, DISCOVER). |
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

<!-- prep-atlas-hash:eee0abe03719 -->
## Codebase Atlas

IDENTITY: A multi-segment platform combining a React design system, NextJS marketing sites, a FastAPI MCP server, VSCode extension tooling, and documentation, with shared UI components powering dashboard, marketing, docs, support, and payments surfaces.

STACK: Languages: .md 878, .tsx 428, .py 323, .ts 157, .json 118, .js 16. Frameworks: react, nextjs, fastapi, storybook. Build tools inferred from package ecosystems. Graph: 1920 files, 8062 nodes, 12888 edges. Edge types: contains 5737, imports 4970, implements 1307, configures 745, listens_to 64. Import cycles: 61.

WORKSPACE MAP: Root (_root, 1293 files): mcp, marketing, react, fastapi, storybook hub. Ui (packages/ui, 364 files): react design-system, storybook, ui-component, dashboard component library. Marketing (websites/apps/marketing, 64 files): nextjs, seo, mcp, marketing-site. Dashboard (src/prep/dashboard, 63 files): react, state-management, react-hooks, dashboard, settings-ui. Docs (websites/apps/docs, 51 files): documentation, nextjs, react, configuration, marketing. Support (websites/apps/support, 27 files): seo, nextjs, authentication, navigation, bug-reporting. Vscode (packages/vscode, 20 files): vscode-extension, ide-integration, reactive-ui, llm-context, project-management. Payments (websites/apps/payments, 15 files): nextjs, payments, marketing, mcp, react. Paperclip Plugin Prep (packages/paperclip-plugin-prep, 12 files): paperclip-integration, plugin-architecture, react, plugin-ui, public-api. Webview Ui (packages/vscode/webview-ui, 11 files): vscode-extension, webview, react, entry-point, strict-mode.

CROSS-CUTTING: Shared domains: react, marketing, nextjs, mcp, storybook, dashboard, seo, vscode-extension. Hub files: docs/ARCHITECTURE.md, ext:__future__, ext:typing, ext:react, ext:logging. Active zones: packages/ui/src/, tests/, websites/apps/marketing/, websites/apps/docs/, src/prep/core/. Entry points: packages/ui/src/components/architecture/index.ts, packages/ui/src/components/layout/index.ts, docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/app.py, src/prep/mcp/server.py, packages/ui/src/components/dashboard/index.ts. Test dirs: __tests__/ 19 files, specs/ 18 files, TEST_STATUS.md/ 1 file. Directory dependencies: docs -> sym:HeroLayout, sym:NeoBrutalistHero, sym:Feature; packages -> sym:Collapsible, sym:MissingProvenance, sym:StageHealth; public -> sym:trigger_sync, sym:main, sym:handler; src -> sym:PaperclipClient.pause_agent, sym:GroupReasoningEngine.load_edges, sym:NamingConsistencyAnalyzer.

## Top docs per module

Planning docs that mention this module's code (Phase 124 T9). Use these as a starting point to understand a module's *why* before reading source. Generated from `atlas_markdown_links.json`.

- **Prep CLI & Developer Tooling Surface**
  - `docs/MASTER_TODO.md`
  - `docs/Phase06_Team_And_Enterprise/TEAM_ENTERPRISE_CODE_AUDIT.md`
  - `docs/Phase06_Team_And_Enterprise/TODO.md`
- **AI Roadmap & Sprint Planning System**
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
  - `docs/Phase67_AGENTS/Paperclip-Plugin/02_Hybrid_MCP_Architecture.md`
  - `docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md`
- **LLM Provider Configuration & Endpoint Orchestrator**
  - `docs/Phase119_ConcurrencyStability/06_Phase_A_Plan.md`
  - `docs/Phase119_ConcurrencyStability/03_Validation_Report.md`
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
- **MCP Protocol Server & IDE Integration Surface**
  - `docs/Phase120_NamedScopes/IMPLEMENTATION_PLAN.md`
  - `docs/Phase120_NamedScopes/README.md`
  - `docs/Phase50_MCP-interfacing/README.md`
- **Project Lifecycle & Build Orchestrator**
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
  - `docs/Phase80_mempalace/01_MemPalace_Integration_Research_Strategy.md`
  - `docs/Phase120_NamedScopes/IMPLEMENTATION_PLAN.md`
- **SourcePrep Design System Primitives**
  - `docs/Phase81_UI-bugfixes/07_Stage3_Loading_States.md`
  - `.agents/content_marketing_strategist/KNOWLEDGE.md`
  - `.agents/content_marketing_strategist/SOUL.md`
- **AutoAudit Static Analysis Engine**
  - `docs/Phase134_ChangesetDrivenPipeline/IMPLEMENTATION_PLAN.md`
  - `docs/Phase99_Content/blogs/00_feasibility_audit.md`
  - `docs/Phase116_strategic-oversight/03_CANDIDATE_CHECKPOINTS.md`
- **Dashboard State & Component Refactoring Tracker**
  - `docs/superpowers/plans/2026-04-19-phase117-rebuild-granularity.md`
- **Enrichment Pipeline State Machine & Resource Scheduler**
  - `docs/Phase96-fix-pipeline/00_DIAGNOSTIC_REPORT.md`
  - `docs/Phase128_PipelineRecoveryHardening/IMPLEMENTATION_PLAN.md`
  - `docs/Phase96-fix-pipeline/UI+tweaks/PLAN.md`

## Focus Areas
- docs/MASTER_ROADMAP.md
Call `prep` for detailed content from these areas.

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
